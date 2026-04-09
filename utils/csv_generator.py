"""
utils/csv_generator.py
Generador de archivos CSV de prueba para el CP01 (carga masiva).
"""
import csv
import os
import random
import string
from faker import Faker

fake = Faker('es_PE')

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
CATEGORIES = ['Electrónica', 'Ropa', 'Libros', 'Muebles', 'Deportes', 'Hogar']


def random_sku(prefix: str = 'CSV') -> str:
    """Genera un SKU único aleatorio."""
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"{prefix}-{suffix}"


def generate_products_csv(filename: str = 'products_bulk.csv',
                           n: int = 10,
                           prefix: str = 'BULK') -> str:
    """
    Genera un CSV con N productos de prueba válidos.

    Args:
        filename: nombre del archivo CSV
        n: número de productos a generar
        prefix: prefijo para los SKUs

    Returns:
        Ruta absoluta del archivo generado
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    filepath = os.path.join(DATA_DIR, filename)

    fieldnames = ['sku', 'name', 'category', 'price', 'stock', 'description', 'image_url']

    with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for i in range(n):
            category = random.choice(CATEGORIES)
            writer.writerow({
                'sku': random_sku(prefix),
                'name': f"{fake.word().capitalize()} {fake.word().capitalize()} Pro {i+1}",
                'category': category,
                'price': round(random.uniform(29.99, 999.99), 2),
                'stock': random.randint(5, 50),
                'description': fake.sentence(nb_words=10),
                'image_url': f"https://picsum.photos/seed/{random.randint(1,1000)}/400/300"
            })

    return filepath


def generate_invalid_csv(filename: str = 'products_invalid.csv') -> str:
    """
    Genera un CSV inválido (columnas incorrectas) para CP07.
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    filepath = os.path.join(DATA_DIR, filename)
    with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=['producto', 'cantidad'])
        writer.writeheader()
        writer.writerow({'producto': 'Item 1', 'cantidad': 10})
    return filepath


def generate_single_product_csv(sku: str, name: str, stock: int = 1,
                                  price: float = 99.99) -> str:
    """Genera CSV de un solo producto con SKU específico."""
    os.makedirs(DATA_DIR, exist_ok=True)
    filepath = os.path.join(DATA_DIR, f'single_{sku}.csv')
    with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f,
                                fieldnames=['sku', 'name', 'category', 'price', 'stock'])
        writer.writeheader()
        writer.writerow({'sku': sku, 'name': name, 'category': 'Test',
                         'price': price, 'stock': stock})
    return filepath
