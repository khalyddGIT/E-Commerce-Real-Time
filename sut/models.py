"""
Modelos de base de datos para el SUT E-Commerce Real-Time.
Usa SQLAlchemy con SQLite.
"""
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

db = SQLAlchemy()


class Product(db.Model):
    """Modelo de producto con gestión de inventario."""
    __tablename__ = 'products'

    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(100), default='General')
    price = db.Column(db.Float, nullable=False, default=0.0)
    stock = db.Column(db.Integer, nullable=False, default=0)
    description = db.Column(db.Text, default='')
    image_url = db.Column(db.String(500), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'sku': self.sku,
            'name': self.name,
            'category': self.category,
            'price': self.price,
            'stock': self.stock,
            'description': self.description,
            'image_url': self.image_url,
        }

    def __repr__(self):
        return f'<Product {self.sku}: {self.name} (stock={self.stock})>'


class Order(db.Model):
    """Modelo de pedido."""
    __tablename__ = 'orders'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), nullable=False)
    items_json = db.Column(db.Text, nullable=False, default='[]')  # JSON list of {product_id, qty, price}
    total = db.Column(db.Float, default=0.0)
    customer_name = db.Column(db.String(200), default='')
    customer_email = db.Column(db.String(200), default='')
    customer_address = db.Column(db.Text, default='')
    status = db.Column(db.String(50), default='pending')  # pending, confirmed, shipped, cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def items(self):
        return json.loads(self.items_json)

    @items.setter
    def items(self, value):
        self.items_json = json.dumps(value)

    def to_dict(self):
        return {
            'id': self.id,
            'session_id': self.session_id,
            'items': self.items,
            'total': self.total,
            'customer_name': self.customer_name,
            'customer_email': self.customer_email,
            'status': self.status,
            'created_at': self.created_at.isoformat(),
        }


class CartSession(db.Model):
    """Carrito de compras persistente por session_id."""
    __tablename__ = 'cart_sessions'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), unique=True, nullable=False)
    items_json = db.Column(db.Text, default='[]')  # JSON list of {product_id, qty}
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def items(self):
        # Guard: items_json es None en memoria antes del primer flush
        if not self.items_json:
            return []
        return json.loads(self.items_json)

    @items.setter
    def items(self, value):
        self.items_json = json.dumps(value if value is not None else [])

    def to_dict(self):
        return {
            'session_id': self.session_id,
            'items': self.items,
        }


def seed_initial_data(app):
    """Carga datos iniciales de prueba si la BD está vacía."""
    with app.app_context():
        if Product.query.count() == 0:
            sample_products = [
                Product(sku='LAPTOP-001', name='Laptop UltraBook Pro', category='Electrónica',
                        price=2499.99, stock=10, description='Laptop de alto rendimiento',
                        image_url='https://picsum.photos/seed/laptop/400/300'),
                Product(sku='PHONE-002', name='Smartphone Galaxy X', category='Electrónica',
                        price=899.99, stock=25, description='Smartphone última generación',
                        image_url='https://picsum.photos/seed/phone/400/300'),
                Product(sku='SHIRT-003', name='Camiseta Básica Premium', category='Ropa',
                        price=49.99, stock=100, description='Camiseta 100% algodón',
                        image_url='https://picsum.photos/seed/shirt/400/300'),
                Product(sku='BOOK-004', name='Python Avanzado 3.10+', category='Libros',
                        price=89.99, stock=50, description='Programación avanzada en Python',
                        image_url='https://picsum.photos/seed/book/400/300'),
                Product(sku='CHAIR-005', name='Silla Ergonómica Gaming', category='Muebles',
                        price=599.99, stock=15, description='Silla profesional para gaming',
                        image_url='https://picsum.photos/seed/chair/400/300'),
            ]
            db.session.add_all(sample_products)
            db.session.commit()
            print("[DB] Datos iniciales cargados.")
