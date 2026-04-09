"""
Aplicación principal del SUT NexoShop.
Flask + Flask-SocketIO con actualizaciones de inventario en tiempo real.
"""
import os
import csv
import io
import json
import threading
from datetime import datetime, timedelta
from flask import (Flask, render_template, request, jsonify,
                   redirect, url_for, session, flash, Response)
from flask_socketio import SocketIO, emit
from sqlalchemy import or_, func
from models import db, Product, Order, CartSession, seed_initial_data

# ─── Configuración ──────────────────────────────────────────────────────────
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = 'ecommerce-realtime-secret-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(BASE_DIR, 'ecommerce.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB upload max

# Credenciales del Admin (hardcoded para el SUT)
ADMIN_USER = 'admin'
ADMIN_PASS = 'admin123'

db.init_app(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Lock para pruebas de concurrencia (CP05)
stock_lock = threading.Lock()

# ─── Init DB ────────────────────────────────────────────────────────────────
with app.app_context():
    db.create_all()
    seed_initial_data(app)


# ═══════════════════════════════════════════════════════════════════════════
# HELPER: emitir actualización de stock a todos los clientes conectados
# ═══════════════════════════════════════════════════════════════════════════
def broadcast_stock_update(product_id, new_stock, product_sku):
    """Emite evento WebSocket a todos los clientes con el nuevo stock."""
    socketio.emit('stock_update', {
        'product_id': product_id,
        'stock': new_stock,
        'sku': product_sku,
        'out_of_stock': new_stock <= 0,
        'timestamp': datetime.utcnow().isoformat()
    })


# ═══════════════════════════════════════════════════════════════════════════
# RUTAS GENERALES
# ═══════════════════════════════════════════════════════════════════════════
@app.route('/')
def index():
    return redirect(url_for('store_home'))


# ═══════════════════════════════════════════════════════════════════════════
# ADMIN — Autenticación
# ═══════════════════════════════════════════════════════════════════════════
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        if username == ADMIN_USER and password == ADMIN_PASS:
            session['admin_logged_in'] = True
            session['admin_user'] = username
            return redirect(url_for('admin_dashboard'))
        flash('Credenciales incorrectas.', 'error')
    return render_template('admin/login.html')


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))


def admin_required(f):
    """Decorador para proteger rutas del admin."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated


# ═══════════════════════════════════════════════════════════════════════════
# ADMIN — Dashboard e Inventario
# ═══════════════════════════════════════════════════════════════════════════
@app.route('/admin')
@admin_required
def admin_dashboard():
    return redirect(url_for('admin_inventory'))


@app.route('/admin/inventory')
@admin_required
def admin_inventory():
    products = Product.query.order_by(Product.id).all()
    return render_template('admin/inventory.html', products=products)


@app.route('/admin/sales')
@admin_required
def admin_sales():
    q = request.args.get('q', '').strip()
    status_filter = request.args.get('status', '').strip().lower()
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()
    export_mode = request.args.get('export', '').strip().lower()

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
        export_orders = filtered_query.order_by(Order.created_at.desc()).all()
        sales_rows = build_sales_rows(export_orders)
        return build_sales_csv_response(sales_rows)

    total_records = filtered_query.count()
    total_pages = max(1, (total_records + per_page - 1) // per_page)
    if page > total_pages:
        page = total_pages

    paginated_orders = (filtered_query
                        .order_by(Order.created_at.desc())
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
        total_records=total_records
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
@admin_required
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
@admin_required
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

        product = Product(
            sku=sku,
            name=name,
            category=request.form.get('category', 'General'),
            price=price,
            stock=stock,
            description=request.form.get('description', ''),
            image_url=request.form.get('image_url', '')
        )
        db.session.add(product)
        db.session.commit()
        broadcast_stock_update(product.id, product.stock, product.sku)
        flash(f'Producto "{product.name}" agregado correctamente.', 'success')
        return redirect(url_for('admin_inventory'))
    return render_template('admin/add_product.html')


@app.route('/admin/inventory/edit/<int:product_id>', methods=['POST'])
@admin_required
def admin_edit_stock(product_id):
    """Editar stock de un producto y notificar vía WebSocket."""
    product = Product.query.get_or_404(product_id)
    new_stock = request.form.get('stock', type=int)
    if new_stock is None or new_stock < 0:
        return jsonify({'success': False, 'message': 'Stock inválido'}), 400

    product.stock = new_stock
    product.updated_at = datetime.utcnow()
    db.session.commit()

    # Notificar a todos los clientes conectados en el Storefront
    broadcast_stock_update(product.id, new_stock, product.sku)

    return jsonify({
        'success': True,
        'message': f'Stock de "{product.name}" actualizado a {new_stock}.',
        'product_id': product.id,
        'new_stock': new_stock
    })


@app.route('/admin/inventory/delete/<int:product_id>', methods=['POST'])
@admin_required
def admin_delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    db.session.delete(product)
    db.session.commit()
    flash(f'Producto eliminado.', 'success')
    return redirect(url_for('admin_inventory'))


# ═══════════════════════════════════════════════════════════════════════════
# ADMIN — Carga masiva CSV (CP01)
# ═══════════════════════════════════════════════════════════════════════════
@app.route('/admin/upload-csv', methods=['GET', 'POST'])
@admin_required
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
        msg = f'CSV procesado: {added} producto(s) agregado(s).'
        if errors:
            msg += f' Errores: {"; ".join(errors[:3])}'
            flash(msg, 'warning')
        else:
            flash(msg, 'success')
        return redirect(url_for('admin_inventory'))

    return render_template('admin/upload_csv.html')


# ═══════════════════════════════════════════════════════════════════════════
# ADMIN — API REST para los tests
# ═══════════════════════════════════════════════════════════════════════════
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


# ═══════════════════════════════════════════════════════════════════════════
# STORE — Tienda
# ═══════════════════════════════════════════════════════════════════════════
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

        with stock_lock:
            for item in cart.items:
                p = Product.query.get(item['product_id'])
                qty = int(item.get('qty', 0))
                if not p:
                    errors.append(f'Producto no encontrado')
                    success = False
                    break
                if qty <= 0:
                    errors.append(f'Cantidad inválida para "{p.name}"')
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
    return render_template('store/order_success.html', order=order)


# ═══════════════════════════════════════════════════════════════════════════
# STORE — API Cart (AJAX)
# ═══════════════════════════════════════════════════════════════════════════
@app.route('/api/cart/add', methods=['POST'])
def api_cart_add():
    """Agregar producto al carrito via AJAX."""
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


# ═══════════════════════════════════════════════════════════════════════════
# WebSocket Events
# ═══════════════════════════════════════════════════════════════════════════
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


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    print("=" * 60)
    print("  NexoShop SUT")
    print("  Admin: http://localhost:5000/admin/login")
    print("  Store: http://localhost:5000/store")
    print("  Grid UI: http://localhost:4444")
    print("=" * 60)
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)



