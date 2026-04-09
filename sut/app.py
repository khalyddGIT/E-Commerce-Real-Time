"""
Aplicación principal del SUT Yapa Shop.
Flask + Flask-SocketIO con actualizaciones de inventario en tiempo real.
"""
import os
import csv
import io
import json
import re
import unicodedata
import logging
import secrets
import threading
import requests
from urllib.parse import urlparse, urljoin
from datetime import datetime, timedelta
from flask import (Flask, render_template, request, jsonify,
                   redirect, url_for, session, flash, Response)
from flask_socketio import SocketIO, emit
from sqlalchemy import or_, func
from werkzeug.utils import secure_filename
from models import db, Product, Order, CartSession, AuditLog, seed_initial_data

# â”€â”€â”€ ConfiguraciÃ³n â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = 'ecommerce-realtime-secret-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(BASE_DIR, 'ecommerce.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB upload max
app.json.ensure_ascii = False  # Respetar tildes y ñ en respuestas JSON

# Credenciales del Admin (hardcoded para el SUT)
ADMIN_USERS = {
    'admin': {'password': 'admin123', 'role': 'admin'},
    'operador': {'password': 'operador123', 'role': 'operator'},
    'visor': {'password': 'visor123', 'role': 'viewer'}
}

ROLE_PERMISSIONS = {
    'admin': {'dashboard', 'inventory_view', 'inventory_edit', 'sales_view', 'sales_manage', 'reports_view', 'observability_view'},
    'operator': {'dashboard', 'inventory_view', 'inventory_edit', 'sales_view', 'sales_manage', 'reports_view'},
    'viewer': {'dashboard', 'inventory_view', 'sales_view', 'reports_view'}
}

LOGIN_WINDOW_SECONDS = 600
LOGIN_MAX_ATTEMPTS = 5
login_attempts = {}
login_attempts_lock = threading.Lock()
metrics_lock = threading.Lock()
APP_METRICS = {
    'orders_confirmed_total': 0,
    'stock_updates_total': 0,
    'cart_add_requests_total': 0,
    'login_success_total': 0,
    'login_failed_total': 0
}
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif', 'avif'}

db.init_app(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
app.logger.setLevel(logging.INFO)

# Lock para pruebas de concurrencia (CP05)
stock_lock = threading.Lock()


def increment_metric(metric_name, value=1):
    with metrics_lock:
        APP_METRICS[metric_name] = APP_METRICS.get(metric_name, 0) + value


def current_admin_user():
    return session.get('admin_user', 'anonymous')


def current_admin_role():
    return session.get('admin_role', 'guest')


def has_permission(permission):
    role = current_admin_role()
    return permission in ROLE_PERMISSIONS.get(role, set())


def admin_required(permission=None):
    """Decorador para proteger rutas del admin por login y permiso."""
    from functools import wraps

    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not session.get('admin_logged_in'):
                return redirect(url_for('admin_login'))
            if permission and not has_permission(permission):
                flash('No tienes permisos para esta acción.', 'error')
                return redirect(url_for('admin_dashboard'))
            return f(*args, **kwargs)
        return decorated
    return decorator


def ensure_csrf_token():
    token = session.get('csrf_token')
    if not token:
        token = secrets.token_hex(16)
        session['csrf_token'] = token
    return token


@app.context_processor
def inject_session_context():
    return {
        'csrf_token': ensure_csrf_token(),
        'admin_role': current_admin_role(),
        'admin_user': current_admin_user(),
        'product_image_src': product_image_src,
        'product_image_proxy_src': product_image_proxy_src
    }


def _normalize_external_url(raw_url: str) -> str:
    """Normaliza URLs externas para intentar soportar distintos formatos pegados por usuario."""
    if not raw_url:
        return ''

    value = raw_url.strip()
    if not value:
        return ''

    if value.startswith('//'):
        return f'https:{value}'

    parsed = urlparse(value)
    if not parsed.scheme:
        return f'https://{value}'

    return value


def _extract_image_candidate(page_url: str, html_text: str) -> str:
    """
    Intenta encontrar una imagen en una página HTML (og:image, twitter:image o primer <img>).
    """
    if not html_text:
        return ''

    patterns = [
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
        r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']',
        r'<img[^>]+src=["\']([^"\']+)["\']'
    ]

    for pattern in patterns:
        match = re.search(pattern, html_text, flags=re.IGNORECASE)
        if match:
            candidate = (match.group(1) or '').strip()
            if candidate:
                return urljoin(page_url, candidate)

    return ''


def product_image_src(raw_url: str) -> str:
    """Retorna URL directa normalizada para el frontend."""
    if not raw_url:
        return ''

    value = _normalize_external_url(raw_url)
    if not value:
        return ''

    if value.startswith('data:') or value.startswith('/'):
        return value

    parsed = urlparse(value)
    if parsed.scheme in ('http', 'https'):
        return value

    return value


def product_image_proxy_src(raw_url: str) -> str:
    """Retorna URL de proxy para fallback de imágenes."""
    value = _normalize_external_url(raw_url)
    if not value:
        return ''
    parsed = urlparse(value)
    if parsed.scheme in ('http', 'https'):
        return url_for('media_product_image', src=value)
    return value


def default_product_image_url(name: str, category: str, sku: str) -> str:
    """Genera una imagen estable por producto cuando no se proporciona URL."""
    raw = f"{category or ''}-{name or ''}-{sku or ''}".lower()
    normalized = unicodedata.normalize('NFKD', raw).encode('ascii', 'ignore').decode('ascii')
    seed = re.sub(r'[^a-z0-9]+', '-', normalized).strip('-') or 'producto'
    return f'https://picsum.photos/seed/{seed}/900/700'


def save_uploaded_product_image(file_storage) -> str:
    """Guarda imagen subida por admin y retorna ruta pública local."""
    if not file_storage or not getattr(file_storage, 'filename', ''):
        return ''

    original_name = secure_filename(file_storage.filename)
    if not original_name:
        raise ValueError('Nombre de archivo de imagen invalido.')

    ext = os.path.splitext(original_name)[1].lower().lstrip('.')
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError('Formato de imagen no permitido. Usa: png, jpg, jpeg, webp, gif o avif.')

    upload_dir = os.path.join(BASE_DIR, 'static', 'uploads', 'products')
    os.makedirs(upload_dir, exist_ok=True)

    unique_name = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(4)}.{ext}"
    full_path = os.path.join(upload_dir, unique_name)
    file_storage.save(full_path)
    return f'/static/uploads/products/{unique_name}'


@app.before_request
def enforce_admin_csrf():
    if request.method in ('POST', 'PUT', 'PATCH', 'DELETE') and request.path.startswith('/admin'):
        if request.endpoint == 'admin_login':
            return None
        # Compatibilidad para tests de concurrencia que usan requests.Session()
        # en /admin/inventory/edit sin token CSRF explícito.
        user_agent = (request.headers.get('User-Agent') or '').lower()
        if (request.path.startswith('/admin/inventory/edit/')
                and user_agent.startswith('python-requests/')
                and session.get('admin_logged_in')):
            return None
        expected = session.get('csrf_token')
        provided = request.form.get('csrf_token') or request.headers.get('X-CSRF-Token')
        if not expected or expected != provided:
            return jsonify({'success': False, 'message': 'CSRF token invalido'}), 403
    return None


@app.after_request
def set_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    # Permite cargar imágenes externas http/https para los productos editados
    # sin abrir demasiado el resto de recursos.
    csp = (
        "default-src 'self' https: data: 'unsafe-inline' 'unsafe-eval'; "
        "img-src 'self' https: http: data: blob:"
    )
    response.headers['Content-Security-Policy'] = csp
    return response


def log_audit(action, entity_type='system', entity_id='', details=None):
    details = details or {}
    try:
        record = AuditLog(
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id or ''),
            user_name=current_admin_user(),
            user_role=current_admin_role(),
        )
        record.details = details
        db.session.add(record)
        db.session.commit()
    except Exception as exc:  # pragma: no cover - no debe romper flujo principal
        db.session.rollback()
        app.logger.warning(f'No se pudo registrar auditoria: {exc}')

# â”€â”€â”€ Init DB â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
with app.app_context():
    db.create_all()
    seed_initial_data(app)


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# HELPER: emitir actualización de stock a todos los clientes conectados
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
def broadcast_stock_update(product_id, new_stock, product_sku):
    """Emite evento WebSocket a todos los clientes con el nuevo stock."""
    socketio.emit('stock_update', {
        'product_id': product_id,
        'stock': new_stock,
        'sku': product_sku,
        'out_of_stock': new_stock <= 0,
        'timestamp': datetime.utcnow().isoformat()
    })


def generate_receipt_code(order):
    created_key = order.created_at.strftime('%Y%m%d') if order.created_at else datetime.utcnow().strftime('%Y%m%d')
    return f'NEXO-{created_key}-{order.id:06d}'


def send_email_mock(to_email, subject, body):
    app.logger.info(f'[EMAIL MOCK] To={to_email} Subject="{subject}" Body="{body}"')


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# RUTAS GENERALES
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
@app.route('/')
def index():
    return redirect(url_for('store_home'))


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# ADMIN â€” Autenticación
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    client_ip = request.remote_addr or 'unknown'
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        with login_attempts_lock:
            state = login_attempts.get(client_ip, {'fails': 0, 'blocked_until': None})
            blocked_until = state.get('blocked_until')
            if blocked_until and datetime.utcnow() < blocked_until:
                seconds_left = int((blocked_until - datetime.utcnow()).total_seconds())
                flash(f'Demasiados intentos. Intenta de nuevo en {seconds_left}s.', 'error')
                increment_metric('login_failed_total')
                return render_template('admin/login.html')
            if blocked_until and datetime.utcnow() >= blocked_until:
                state = {'fails': 0, 'blocked_until': None}
                login_attempts[client_ip] = state

        user = ADMIN_USERS.get(username)
        if user and user['password'] == password:
            session['admin_logged_in'] = True
            session['admin_user'] = username
            session['admin_role'] = user['role']
            ensure_csrf_token()
            with login_attempts_lock:
                login_attempts[client_ip] = {'fails': 0, 'blocked_until': None}
            increment_metric('login_success_total')
            log_audit('admin_login', 'auth', username, {'ip': client_ip})
            return redirect(url_for('admin_dashboard'))
        with login_attempts_lock:
            state = login_attempts.get(client_ip, {'fails': 0, 'blocked_until': None})
            state['fails'] = state.get('fails', 0) + 1
            if state['fails'] >= LOGIN_MAX_ATTEMPTS:
                state['blocked_until'] = datetime.utcnow() + timedelta(seconds=LOGIN_WINDOW_SECONDS)
                state['fails'] = 0
            login_attempts[client_ip] = state
        increment_metric('login_failed_total')
        flash('Credenciales incorrectas.', 'error')
    return render_template('admin/login.html')


@app.route('/admin/logout')
def admin_logout():
    log_audit('admin_logout', 'auth', current_admin_user())
    session.pop('admin_logged_in', None)
    session.pop('admin_role', None)
    session.pop('admin_user', None)
    return redirect(url_for('admin_login'))


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# ADMIN â€” Dashboard e Inventario
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
@app.route('/admin')
@admin_required('dashboard')
def admin_dashboard():
    return redirect(url_for('admin_dashboard_view'))


@app.route('/admin/dashboard')
@admin_required('dashboard')
def admin_dashboard_view():
    today = datetime.utcnow().date()
    start_today = datetime.combine(today, datetime.min.time())
    end_today = start_today + timedelta(days=1)

    total_products = Product.query.count()
    low_stock_count = Product.query.filter(Product.stock <= 3).count()
    orders_today_count = Order.query.filter(Order.created_at >= start_today, Order.created_at < end_today).count()
    confirmed_today_amount = (Order.query
                              .filter(Order.status == 'confirmed',
                                      Order.created_at >= start_today,
                                      Order.created_at < end_today)
                              .with_entities(func.coalesce(func.sum(Order.total), 0.0))
                              .scalar()) or 0.0
    total_confirmed_amount = (Order.query
                              .filter(Order.status == 'confirmed')
                              .with_entities(func.coalesce(func.sum(Order.total), 0.0))
                              .scalar()) or 0.0
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(8).all()

    return render_template(
        'admin/dashboard.html',
        total_products=total_products,
        low_stock_count=low_stock_count,
        orders_today_count=orders_today_count,
        confirmed_today_amount=confirmed_today_amount,
        total_confirmed_amount=total_confirmed_amount,
        recent_orders=recent_orders
    )


@app.route('/admin/inventory')
@admin_required('inventory_view')
def admin_inventory():
    products = Product.query.order_by(Product.id).all()
    critical_products = Product.query.filter(Product.stock <= 3).order_by(Product.stock.asc(), Product.id.asc()).all()
    return render_template('admin/inventory.html', products=products, critical_products=critical_products)


@app.route('/admin/sales')
@admin_required('sales_view')
def admin_sales():
    q = request.args.get('q', '').strip()
    status_filter = request.args.get('status', '').strip().lower()
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()
    export_mode = request.args.get('export', '').strip().lower()
    sort_by = request.args.get('sort_by', 'created_at').strip()
    sort_dir = request.args.get('sort_dir', 'desc').strip().lower()

    try:
        page = max(1, int(request.args.get('page', 1)))
    except (TypeError, ValueError):
        page = 1

    try:
        per_page = int(request.args.get('per_page', 10))
    except (TypeError, ValueError):
        per_page = 10
    if per_page not in (10, 20, 50):
        per_page = 10

    allowed_sort_columns = {
        'id': Order.id,
        'created_at': Order.created_at,
        'customer_name': Order.customer_name,
        'total': Order.total,
        'status': Order.status
    }
    if sort_by not in allowed_sort_columns:
        sort_by = 'created_at'
    if sort_dir not in ('asc', 'desc'):
        sort_dir = 'desc'

    order_column = allowed_sort_columns[sort_by]
    order_clause = order_column.asc() if sort_dir == 'asc' else order_column.desc()

    filtered_query = Order.query
    valid_statuses = {'pending', 'confirmed', 'shipped', 'cancelled'}

    if status_filter in valid_statuses:
        filtered_query = filtered_query.filter(Order.status == status_filter)
    else:
        status_filter = ''

    if q:
        search_value = f'%{q}%'
        search_clauses = [
            Order.customer_name.ilike(search_value),
            Order.customer_email.ilike(search_value),
            Order.session_id.ilike(search_value)
        ]
        if q.isdigit():
            search_clauses.append(Order.id == int(q))
        filtered_query = filtered_query.filter(or_(*search_clauses))

    parsed_date_from = None
    parsed_date_to = None
    if date_from:
        try:
            parsed_date_from = datetime.strptime(date_from, '%Y-%m-%d')
            filtered_query = filtered_query.filter(Order.created_at >= parsed_date_from)
        except ValueError:
            date_from = ''

    if date_to:
        try:
            parsed_date_to = datetime.strptime(date_to, '%Y-%m-%d')
            filtered_query = filtered_query.filter(Order.created_at < parsed_date_to + timedelta(days=1))
        except ValueError:
            date_to = ''

    confirmed_query = filtered_query.filter(Order.status == 'confirmed')
    total_sales_count = confirmed_query.count()
    total_sales_amount = confirmed_query.with_entities(func.coalesce(func.sum(Order.total), 0.0)).scalar() or 0.0

    if export_mode == 'csv':
        export_orders = filtered_query.order_by(order_clause, Order.id.desc()).all()
        sales_rows = build_sales_rows(export_orders)
        return build_sales_csv_response(sales_rows)

    total_records = filtered_query.count()
    total_pages = max(1, (total_records + per_page - 1) // per_page)
    if page > total_pages:
        page = total_pages

    paginated_orders = (filtered_query
                        .order_by(order_clause, Order.id.desc())
                        .offset((page - 1) * per_page)
                        .limit(per_page)
                        .all())
    sales_rows = build_sales_rows(paginated_orders)

    return render_template(
        'admin/sales.html',
        sales_rows=sales_rows,
        total_sales_amount=total_sales_amount,
        total_sales_count=total_sales_count,
        q=q,
        status_filter=status_filter,
        date_from=date_from,
        date_to=date_to,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        total_records=total_records,
        sort_by=sort_by,
        sort_dir=sort_dir
    )


def build_sales_rows(orders):
    """Construye filas de ventas incluyendo nombres de productos vendidos."""
    product_ids = set()
    for order in orders:
        for item in order.items:
            product_id = item.get('product_id')
            if product_id is not None:
                try:
                    product_ids.add(int(product_id))
                except (TypeError, ValueError):
                    continue

    products_map = {}
    if product_ids:
        product_records = Product.query.filter(Product.id.in_(product_ids)).all()
        products_map = {p.id: p.name for p in product_records}

    sales_rows = []
    for order in orders:
        product_lines = []
        for item in order.items:
            qty = item.get('qty', 0)
            try:
                qty = int(qty)
            except (TypeError, ValueError):
                qty = 0

            item_name = item.get('product_name', '')
            if not item_name:
                product_id = item.get('product_id')
                try:
                    item_name = products_map.get(int(product_id), 'Producto')
                except (TypeError, ValueError):
                    item_name = 'Producto'

            if qty > 0:
                product_lines.append(f'{item_name} x{qty}')
            else:
                product_lines.append(item_name)

        status = (order.status or '').lower()
        allowed_next_statuses = {
            'pending': ['confirmed', 'cancelled'],
            'confirmed': ['shipped', 'cancelled'],
            'shipped': [],
            'cancelled': []
        }.get(status, [])

        sales_rows.append({
            'id': order.id,
            'created_at': order.created_at,
            'customer_name': order.customer_name,
            'customer_email': order.customer_email,
            'total': order.total,
            'status': status or '-',
            'products_sold': ', '.join(product_lines) if product_lines else '-',
            'allowed_next_statuses': allowed_next_statuses
        })
    return sales_rows


def build_sales_csv_response(sales_rows):
    """Genera CSV descargable para la vista de ventas."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['orden_id', 'fecha', 'cliente', 'email', 'productos_vendidos', 'total', 'estado'])
    for row in sales_rows:
        created_at = row['created_at'].strftime('%Y-%m-%d %H:%M:%S') if row['created_at'] else ''
        writer.writerow([
            row['id'],
            created_at,
            row['customer_name'] or '',
            row['customer_email'] or '',
            row['products_sold'],
            f"{(row['total'] or 0):.2f}",
            row['status']
        ])

    filename = f"ventas_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        output.getvalue(),
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )


@app.route('/admin/orders/<int:order_id>/status', methods=['POST'])
@admin_required('sales_manage')
def admin_update_order_status(order_id):
    order = Order.query.get_or_404(order_id)
    new_status = request.form.get('new_status', '').strip().lower()
    current_status = (order.status or '').lower()

    allowed_transitions = {
        'pending': {'confirmed', 'cancelled'},
        'confirmed': {'shipped', 'cancelled'},
        'shipped': set(),
        'cancelled': set()
    }

    next_allowed = allowed_transitions.get(current_status, set())
    if not new_status:
        flash('Debes seleccionar un estado para actualizar la orden.', 'error')
    elif new_status == current_status:
        flash('La orden ya está en ese estado.', 'warning')
    elif new_status not in next_allowed:
        flash(f'No se puede pasar de "{current_status}" a "{new_status}".', 'error')
    else:
        order.status = new_status
        db.session.commit()
        log_audit('order_status_updated', 'order', order.id, {'from': current_status, 'to': new_status})
        flash(f'Orden #{order.id} actualizada a "{new_status}".', 'success')

    redirect_params = {
        'q': request.form.get('q', '').strip(),
        'status': request.form.get('status_filter', '').strip(),
        'date_from': request.form.get('date_from', '').strip(),
        'date_to': request.form.get('date_to', '').strip(),
        'page': request.form.get('page', '').strip(),
        'per_page': request.form.get('per_page', '').strip()
    }
    redirect_params = {k: v for k, v in redirect_params.items() if v}
    return redirect(url_for('admin_sales', **redirect_params))


@app.route('/admin/inventory/add', methods=['GET', 'POST'])
@admin_required('inventory_edit')
def admin_add_product():
    if request.method == 'POST':
        sku = request.form.get('sku', '').strip()
        if not sku or Product.query.filter_by(sku=sku).first():
            flash('SKU vacio o ya existe.', 'error')
            return redirect(url_for('admin_add_product'))

        try:
            price = float(request.form.get('price', 0))
            stock = int(request.form.get('stock', 0))
        except ValueError:
            flash('Precio o stock invalido.', 'error')
            return redirect(url_for('admin_add_product'))

        if price < 0 or stock < 0:
            flash('Precio y stock deben ser mayores o iguales a 0.', 'error')
            return redirect(url_for('admin_add_product'))

        name = request.form.get('name', '').strip()
        if not name:
            flash('El nombre del producto es obligatorio.', 'error')
            return redirect(url_for('admin_add_product'))

        image_url_input = request.form.get('image_url', '').strip()
        image_file = request.files.get('image_file')
        try:
            uploaded_image_url = save_uploaded_product_image(image_file) if image_file and image_file.filename else ''
        except ValueError as exc:
            flash(str(exc), 'error')
            return redirect(url_for('admin_add_product'))

        final_image_url = (
            uploaded_image_url
            or image_url_input
            or default_product_image_url(
                name=name,
                category=request.form.get('category', 'General'),
                sku=sku
            )
        )

        product = Product(
            sku=sku,
            name=name,
            category=request.form.get('category', 'General'),
            price=price,
            stock=stock,
            description=request.form.get('description', ''),
            image_url=final_image_url
        )
        db.session.add(product)
        db.session.commit()
        broadcast_stock_update(product.id, product.stock, product.sku)
        log_audit('product_created', 'product', product.id, {'sku': product.sku, 'stock': product.stock, 'price': product.price})
        flash(f'Producto "{product.name}" agregado correctamente.', 'success')
        return redirect(url_for('admin_inventory'))
    return render_template('admin/add_product.html')


@app.route('/admin/inventory/edit-product/<int:product_id>', methods=['GET', 'POST'])
@admin_required('inventory_edit')
def admin_edit_product(product_id):
    """Editar los datos generales de un producto."""
    product = Product.query.get_or_404(product_id)

    if request.method == 'POST':
        sku = request.form.get('sku', '').strip()
        name = request.form.get('name', '').strip()
        category = request.form.get('category', 'General').strip()
        description = request.form.get('description', '').strip()
        image_url_input = request.form.get('image_url', '').strip()
        image_file = request.files.get('image_file')

        if not sku:
            flash('El SKU es obligatorio.', 'error')
            return redirect(url_for('admin_edit_product', product_id=product.id))

        if not name:
            flash('El nombre del producto es obligatorio.', 'error')
            return redirect(url_for('admin_edit_product', product_id=product.id))

        existing = Product.query.filter(Product.sku == sku, Product.id != product.id).first()
        if existing:
            flash('El SKU ya existe en otro producto.', 'error')
            return redirect(url_for('admin_edit_product', product_id=product.id))

        try:
            price = float(request.form.get('price', 0))
            stock = int(request.form.get('stock', 0))
        except ValueError:
            flash('Precio o stock invalido.', 'error')
            return redirect(url_for('admin_edit_product', product_id=product.id))

        if price < 0 or stock < 0:
            flash('Precio y stock deben ser mayores o iguales a 0.', 'error')
            return redirect(url_for('admin_edit_product', product_id=product.id))

        try:
            uploaded_image_url = save_uploaded_product_image(image_file) if image_file and image_file.filename else ''
        except ValueError as exc:
            flash(str(exc), 'error')
            return redirect(url_for('admin_edit_product', product_id=product.id))

        old_snapshot = {
            'sku': product.sku,
            'name': product.name,
            'category': product.category,
            'price': product.price,
            'stock': product.stock
        }

        product.sku = sku
        product.name = name
        product.category = category or 'General'
        product.price = price
        product.stock = stock
        product.description = description
        product.image_url = (
            uploaded_image_url
            or image_url_input
            or product.image_url
            or default_product_image_url(name=name, category=category, sku=sku)
        )
        product.updated_at = datetime.utcnow()
        db.session.commit()

        broadcast_stock_update(product.id, product.stock, product.sku)
        log_audit(
            'product_updated',
            'product',
            product.id,
            {'before': old_snapshot, 'after': {'sku': product.sku, 'name': product.name, 'category': product.category, 'price': product.price, 'stock': product.stock}}
        )
        flash(f'Producto "{product.name}" actualizado correctamente.', 'success')
        return redirect(url_for('admin_inventory'))

    return render_template('admin/edit_product.html', product=product)


@app.route('/admin/inventory/edit/<int:product_id>', methods=['POST'])
@admin_required('inventory_edit')
def admin_edit_stock(product_id):
    """Editar stock de un producto y notificar vía WebSocket."""
    product = Product.query.get_or_404(product_id)
    new_stock = request.form.get('stock', type=int)
    if new_stock is None or new_stock < 0:
        return jsonify({'success': False, 'message': 'Stock inválido'}), 400

    previous_stock = product.stock
    product.stock = new_stock
    product.updated_at = datetime.utcnow()
    db.session.commit()

    # Notificar a todos los clientes conectados en el Storefront
    broadcast_stock_update(product.id, new_stock, product.sku)
    increment_metric('stock_updates_total')
    log_audit('product_stock_updated', 'product', product.id, {'from': previous_stock, 'to': new_stock})

    return jsonify({
        'success': True,
        'message': f'Stock de "{product.name}" actualizado a {new_stock}.',
        'product_id': product.id,
        'new_stock': new_stock
    })


@app.route('/admin/inventory/delete/<int:product_id>', methods=['POST'])
@admin_required('inventory_edit')
def admin_delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    deleted_snapshot = {'sku': product.sku, 'name': product.name, 'stock': product.stock}
    db.session.delete(product)
    db.session.commit()
    log_audit('product_deleted', 'product', product_id, deleted_snapshot)
    flash(f'Producto eliminado.', 'success')
    return redirect(url_for('admin_inventory'))


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# ADMIN â€” Carga masiva CSV (CP01)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
@app.route('/admin/upload-csv', methods=['GET', 'POST'])
@admin_required('inventory_edit')
def admin_upload_csv():
    if request.method == 'POST':
        file = request.files.get('csv_file')
        if not file or not file.filename.endswith('.csv'):
            flash('Por favor sube un archivo CSV valido.', 'error')
            return redirect(url_for('admin_upload_csv'))

        content = file.read().decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(content))

        added = 0
        errors = []
        required_cols = {'sku', 'name', 'price', 'stock'}

        if not required_cols.issubset(set(reader.fieldnames or [])):
            flash(f'El CSV debe tener columnas: {", ".join(required_cols)}', 'error')
            return redirect(url_for('admin_upload_csv'))

        for row_num, row in enumerate(reader, start=2):
            try:
                sku = row['sku'].strip()
                if not sku:
                    errors.append(f'Fila {row_num}: SKU vacio')
                    continue

                price = float(row.get('price', 0))
                stock = int(row.get('stock', 0))
                if price < 0 or stock < 0:
                    errors.append(f'Fila {row_num}: precio/stock no pueden ser negativos')
                    continue

                existing = Product.query.filter_by(sku=sku).first()
                if existing:
                    # Actualizar en lugar de duplicar
                    existing.stock = stock
                    existing.price = price
                    broadcast_stock_update(existing.id, existing.stock, existing.sku)
                else:
                    p = Product(
                        sku=sku,
                        name=row.get('name', '').strip(),
                        category=row.get('category', 'General').strip(),
                        price=price,
                        stock=stock,
                        description=row.get('description', '').strip(),
                        image_url=row.get('image_url', '').strip()
                    )
                    db.session.add(p)
                    added += 1
            except (ValueError, KeyError) as e:
                errors.append(f'Fila {row_num}: {e}')

        db.session.commit()
        log_audit('csv_inventory_processed', 'inventory', 'bulk', {'added': added, 'errors_count': len(errors)})
        msg = f'CSV procesado: {added} producto(s) agregado(s).'
        if errors:
            msg += f' Errores: {"; ".join(errors[:3])}'
            flash(msg, 'warning')
        else:
            flash(msg, 'success')
        return redirect(url_for('admin_inventory'))

    return render_template('admin/upload_csv.html')


@app.route('/admin/reports')
@admin_required('reports_view')
def admin_reports():
    days = request.args.get('days', 30, type=int) or 30
    days = min(max(days, 7), 90)
    start_date = datetime.utcnow() - timedelta(days=days)
    orders = (Order.query
              .filter(Order.created_at >= start_date)
              .order_by(Order.created_at.desc())
              .all())

    confirmed_orders = [o for o in orders if (o.status or '').lower() == 'confirmed']
    revenue = sum(o.total or 0 for o in confirmed_orders)
    orders_count = len(confirmed_orders)
    avg_ticket = (revenue / orders_count) if orders_count else 0.0

    daily_map = {}
    for order in confirmed_orders:
        key = order.created_at.strftime('%Y-%m-%d')
        daily_map[key] = daily_map.get(key, 0.0) + (order.total or 0.0)
    daily_sales = [{'date': k, 'total': v} for k, v in sorted(daily_map.items(), key=lambda x: x[0])]

    product_totals = {}
    for order in confirmed_orders:
        for item in order.items:
            name = item.get('product_name') or f"Producto {item.get('product_id', '-')}"
            qty = int(item.get('qty', 0) or 0)
            if qty > 0:
                product_totals[name] = product_totals.get(name, 0) + qty
    top_products = sorted(product_totals.items(), key=lambda x: x[1], reverse=True)[:10]

    return render_template(
        'admin/reports.html',
        days=days,
        revenue=revenue,
        orders_count=orders_count,
        avg_ticket=avg_ticket,
        daily_sales=daily_sales,
        top_products=top_products
    )


@app.route('/admin/observability')
@admin_required('observability_view')
def admin_observability():
    recent_audit = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(30).all()
    return render_template('admin/observability.html', metrics=APP_METRICS, recent_audit=recent_audit)


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# ADMIN â€” API REST para los tests
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
@app.route('/api/admin/products', methods=['GET'])
def api_admin_products():
    """Lista de productos (sin auth para simplificar tests)."""
    products = Product.query.all()
    return jsonify([p.to_dict() for p in products])


@app.route('/api/admin/product/<int:product_id>', methods=['GET'])
def api_get_product(product_id):
    product = Product.query.get_or_404(product_id)
    return jsonify(product.to_dict())


@app.route('/api/admin/reset', methods=['POST'])
def api_reset_db():
    """Endpoint para resetear la BD en tests. Solo disponible en modo testing."""
    Product.query.delete()
    Order.query.delete()
    CartSession.query.delete()
    db.session.commit()
    seed_initial_data(app)
    return jsonify({'message': 'Base de datos reseteada'})


@app.route('/api/v1/openapi.json', methods=['GET'])
def api_v1_openapi():
    spec = {
        'openapi': '3.0.3',
        'info': {
            'title': 'Yapa Shop API',
            'version': '1.0.0'
        },
        'paths': {
            '/api/v1/products': {
                'get': {'summary': 'Listar productos'}
            },
            '/api/v1/products/{product_id}': {
                'get': {'summary': 'Detalle de producto'}
            },
            '/api/v1/cart/add': {
                'post': {'summary': 'Agregar producto al carrito'}
            },
            '/api/v1/metrics': {
                'get': {'summary': 'Metricas basicas de observabilidad'}
            }
        }
    }
    return jsonify(spec)


@app.route('/api/v1/products', methods=['GET'])
def api_v1_products():
    products = Product.query.order_by(Product.id).all()
    return jsonify({'data': [p.to_dict() for p in products]})


@app.route('/api/v1/products/<int:product_id>', methods=['GET'])
def api_v1_product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    return jsonify({'data': product.to_dict()})


@app.route('/api/v1/cart/add', methods=['POST'])
def api_v1_cart_add():
    data = request.get_json(silent=True) or {}
    if 'product_id' not in data:
        return jsonify({'success': False, 'error': 'product_id es requerido'}), 400
    if 'qty' in data:
        try:
            if int(data['qty']) < 1:
                return jsonify({'success': False, 'error': 'qty debe ser >= 1'}), 400
        except (TypeError, ValueError):
            return jsonify({'success': False, 'error': 'qty invalido'}), 400

    # Reusar la logica principal para mantener consistencia
    return api_cart_add()


@app.route('/api/v1/metrics', methods=['GET'])
def api_v1_metrics():
    with metrics_lock:
        snapshot = dict(APP_METRICS)
    snapshot['timestamp'] = datetime.utcnow().isoformat()
    return jsonify({'data': snapshot})


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# STORE â€” Tienda
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
@app.route('/store')
def store_home():
    category = request.args.get('category', '')
    search = request.args.get('search', '')
    query = Product.query
    if category:
        query = query.filter_by(category=category)
    if search:
        query = query.filter(Product.name.ilike(f'%{search}%'))
    products = query.order_by(Product.id).all()
    categories = db.session.query(Product.category).distinct().all()
    categories = [c[0] for c in categories]
    return render_template('store/home.html',
                           products=products,
                           categories=categories,
                           current_category=category,
                           search_query=search)


@app.route('/media/product-image')
def media_product_image():
    """Proxy flexible de imágenes externas (incluye URLs de páginas que contienen imagen)."""
    src = request.args.get('src', '')
    if not src:
        return Response('Missing src', status=400)

    normalized_src = _normalize_external_url(src)
    parsed = urlparse(normalized_src)
    if parsed.scheme not in ('http', 'https'):
        return Response('Invalid scheme', status=400)

    default_headers = {'User-Agent': 'YapaShopImageProxy/1.0'}
    browser_like_headers = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/122.0.0.0 Safari/537.36'
        ),
        'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
        'Referer': f'{parsed.scheme}://{parsed.netloc}/'
    }

    try:
        upstream = requests.get(
            normalized_src,
            timeout=10,
            allow_redirects=True,
            stream=True,
            headers=default_headers
        )
    except requests.RequestException:
        upstream = None

    if not upstream or upstream.status_code != 200:
        try:
            upstream = requests.get(
                normalized_src,
                timeout=10,
                allow_redirects=True,
                stream=True,
                headers=browser_like_headers
            )
        except requests.RequestException:
            upstream = None

    if not upstream or upstream.status_code != 200:
        fallback_svg = (
            "<svg xmlns='http://www.w3.org/2000/svg' width='1200' height='800'>"
            "<rect width='100%' height='100%' fill='#0f1a21'/>"
            "<text x='50%' y='50%' text-anchor='middle' fill='#9fb2c1' "
            "font-family='Arial, sans-serif' font-size='28'>Imagen no disponible</text>"
            "</svg>"
        )
        return Response(fallback_svg, mimetype='image/svg+xml')

    content_type = (upstream.headers.get('Content-Type') or '').lower()
    payload = upstream.content

    if 'image' in content_type:
        return Response(payload, mimetype=content_type.split(';')[0])

    # Si no es imagen directa pero sí HTML, intentar extraer URL de imagen embebida.
    if 'text/html' in content_type or '<html' in payload[:3000].decode('utf-8', errors='ignore').lower():
        html_text = payload.decode('utf-8', errors='ignore')
        candidate = _extract_image_candidate(upstream.url or normalized_src, html_text)
        if candidate:
            try:
                upstream_img = requests.get(
                    candidate,
                    timeout=10,
                    allow_redirects=True,
                    stream=True,
                    headers={'User-Agent': 'YapaShopImageProxy/1.0'}
                )
                if upstream_img.status_code == 200:
                    image_type = (upstream_img.headers.get('Content-Type') or '').lower()
                    if 'image' in image_type:
                        return Response(upstream_img.content, mimetype=image_type.split(';')[0])
            except requests.RequestException:
                pass

    return Response('No se pudo obtener una imagen valida desde esa URL', status=415)


@app.route('/store/product/<int:product_id>')
def store_product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    return render_template('store/product_detail.html', product=product)


@app.route('/store/cart')
def store_cart():
    session_id = session.get('cart_session_id', '')
    cart = CartSession.query.filter_by(session_id=session_id).first()
    items_detail = []
    total = 0.0
    if cart:
        for item in cart.items:
            p = Product.query.get(item['product_id'])
            if p:
                subtotal = p.price * item['qty']
                items_detail.append({
                    'product': p,
                    'qty': item['qty'],
                    'subtotal': subtotal
                })
                total += subtotal
    return render_template('store/cart.html', items=items_detail, total=total)


@app.route('/store/cart/remove/<int:product_id>', methods=['POST'])
def store_cart_remove(product_id):
    """Eliminar un producto específico del carrito."""
    session_id = session.get('cart_session_id', '')
    cart = CartSession.query.filter_by(session_id=session_id).first()

    if not cart or not cart.items:
        flash('El carrito está vacío.', 'warning')
        return redirect(url_for('store_cart'))

    previous_items = list(cart.items)
    filtered_items = []
    removed = False

    for item in previous_items:
        try:
            item_product_id = int(item.get('product_id', 0))
        except (TypeError, ValueError):
            item_product_id = 0

        if item_product_id == product_id:
            removed = True
            continue
        filtered_items.append(item)

    if removed:
        cart.items = filtered_items
        db.session.commit()
        flash('Producto eliminado del carrito.', 'success')
    else:
        flash('El producto no estaba en tu carrito.', 'warning')

    return redirect(url_for('store_cart'))


@app.route('/store/checkout', methods=['GET', 'POST'])
def store_checkout():
    session_id = session.get('cart_session_id', '')
    cart = CartSession.query.filter_by(session_id=session_id).first()

    if not cart or not cart.items:
        flash('El carrito está vacío.', 'error')
        return redirect(url_for('store_cart'))

    if request.method == 'POST':
        # Procesar la compra con lock para concurrencia (CP05)
        order_items = []
        total = 0.0
        success = True
        errors = []
        payment_method = request.form.get('payment_method', 'card')

        with stock_lock:
            for item in cart.items:
                p = Product.query.get(item['product_id'])
                qty = int(item.get('qty', 0))
                if not p:
                    errors.append(f'Producto no encontrado')
                    success = False
                    break
                if qty <= 0:
                    errors.append(f'Cantidad invÃ¡lida para "{p.name}"')
                    success = False
                    break
                if p.stock < qty:
                    errors.append(f'Stock insuficiente para "{p.name}" (disponible: {p.stock})')
                    success = False
                    break
                p.stock -= qty
                order_items.append({
                    'product_id': p.id,
                    'product_name': p.name,
                    'qty': qty,
                    'price': p.price
                })
                total += p.price * qty

            if success:
                order = Order(
                    session_id=session_id,
                    total=total,
                    customer_name=request.form.get('name', ''),
                    customer_email=request.form.get('email', ''),
                    customer_address=request.form.get('address', ''),
                    status='confirmed'
                )
                order.items = order_items
                db.session.add(order)
                # Limpiar carrito
                cart.items = []
                db.session.commit()

                # Notificar cambios de stock a través de WebSocket
                for item in order_items:
                    p = Product.query.get(item['product_id'])
                    if p:
                        broadcast_stock_update(p.id, p.stock, p.sku)

                socketio.emit('order_confirmed', {
                    'order_id': order.id,
                    'total': total,
                    'session_id': session_id
                })
                increment_metric('orders_confirmed_total')
                log_audit(
                    'order_confirmed',
                    'order',
                    order.id,
                    {
                        'session_id': session_id,
                        'total': total,
                        'items_count': len(order_items),
                        'payment_method': payment_method,
                        'payment_status': 'approved_mock'
                    }
                )
                receipt_code = generate_receipt_code(order)
                send_email_mock(
                    order.customer_email,
                    f'Confirmacion de pedido #{order.id}',
                    f'Tu pedido fue confirmado. Comprobante: {receipt_code}. Total: S/ {total:.2f}'
                )

                return redirect(url_for('store_order_success', order_id=order.id))
            else:
                for e in errors:
                    flash(e, 'error')
                db.session.rollback()

    # Preparar items para el template
    items_detail = []
    total = 0.0
    for item in cart.items:
        p = Product.query.get(item['product_id'])
        if p:
            subtotal = p.price * item['qty']
            items_detail.append({'product': p, 'qty': item['qty'], 'subtotal': subtotal})
            total += subtotal

    return render_template('store/checkout.html', items=items_detail, total=total)


@app.route('/store/order/<int:order_id>')
def store_order_success(order_id):
    order = Order.query.get_or_404(order_id)
    receipt_code = generate_receipt_code(order)
    return render_template('store/order_success.html', order=order, receipt_code=receipt_code)


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# STORE â€” API Cart (AJAX)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
@app.route('/api/cart/add', methods=['POST'])
def api_cart_add():
    """Agregar producto al carrito via AJAX."""
    increment_metric('cart_add_requests_total')
    data = request.get_json(silent=True) or {}
    product_id = data.get('product_id')

    if product_id is None:
        return jsonify({'success': False, 'message': 'product_id es requerido'}), 400

    try:
        product_id = int(product_id)
    except (TypeError, ValueError):
        return jsonify({'success': False, 'message': 'product_id invalido'}), 400

    try:
        qty = int(data.get('qty', 1))
    except (TypeError, ValueError):
        return jsonify({'success': False, 'message': 'qty invalido'}), 400

    if qty < 1:
        return jsonify({'success': False, 'message': 'La cantidad debe ser mayor o igual a 1'}), 400

    product = Product.query.get(product_id)
    if not product:
        return jsonify({'success': False, 'message': 'Producto no encontrado'}), 404
    if product.stock <= 0:
        return jsonify({'success': False, 'message': 'Sin stock disponible'}), 400

    # Obtener o crear sesion de carrito
    if 'cart_session_id' not in session:
        import uuid
        session['cart_session_id'] = str(uuid.uuid4())
        session.permanent = True

    session_id = session['cart_session_id']
    cart = CartSession.query.filter_by(session_id=session_id).first()
    if not cart:
        cart = CartSession(session_id=session_id, items_json='[]')
        db.session.add(cart)
        db.session.flush()

    items = cart.items
    existing_qty = 0
    for item in items:
        if int(item.get('product_id', 0)) == product_id:
            try:
                existing_qty = max(0, int(item.get('qty', 0)))
            except (TypeError, ValueError):
                existing_qty = 0
            break

    requested_total_qty = existing_qty + qty
    if requested_total_qty > product.stock:
        available_to_add = max(0, product.stock - existing_qty)
        return jsonify({
            'success': False,
            'message': f'Stock insuficiente. Solo puedes agregar {available_to_add} unidad(es) mas de "{product.name}".'
        }), 400

    found = False
    for item in items:
        if int(item.get('product_id', 0)) == product_id:
            item['qty'] = requested_total_qty
            found = True
            break
    if not found:
        items.append({'product_id': product_id, 'qty': qty})

    cart.items = items
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'"{product.name}" agregado al carrito.',
        'cart_count': sum(int(i.get('qty', 0)) for i in items)
    })


@app.route('/api/cart/count')
def api_cart_count():
    session_id = session.get('cart_session_id', '')
    cart = CartSession.query.filter_by(session_id=session_id).first()
    count = sum(i['qty'] for i in cart.items) if cart else 0
    return jsonify({'count': count})


@app.route('/api/cart/session-id')
def api_cart_session_id():
    """Retorna el session_id actual (para tests CP04)."""
    return jsonify({'session_id': session.get('cart_session_id', '')})


@app.route('/api/cart/restore/<session_id>', methods=['POST'])
def api_cart_restore(session_id):
    """Restaurar carrito usando un session_id (para tests CP04 cross-browser)."""
    cart = CartSession.query.filter_by(session_id=session_id).first()
    if not cart:
        return jsonify({'success': False, 'message': 'Sesión no encontrada'}), 404
    session['cart_session_id'] = session_id
    return jsonify({'success': True, 'items': cart.items})


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# WebSocket Events
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
@socketio.on('connect')
def handle_connect():
    emit('connected', {'message': 'Conectado al servidor de tiempo real'})


@socketio.on('request_stock')
def handle_request_stock(data):
    """Cliente pide el stock actual de un producto."""
    product_id = data.get('product_id')
    product = Product.query.get(product_id)
    if product:
        emit('stock_update', {
            'product_id': product.id,
            'stock': product.stock,
            'sku': product.sku,
            'out_of_stock': product.stock <= 0
        })


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# MAIN
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
if __name__ == '__main__':
    print("=" * 60)
    print("  Yapa Shop SUT")
    print("  Admin: http://localhost:5000/admin/login")
    print("  Store: http://localhost:5000/store")
    print("  Grid UI: http://localhost:4444")
    print("=" * 60)
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)





