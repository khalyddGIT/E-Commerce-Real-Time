import argparse
import csv
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description='Importa productos desde CSV a NexoShop (insert/update por SKU).')
    parser.add_argument('--file', required=True, help='Ruta al archivo CSV')
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    sut_dir = root / 'sut'
    if str(sut_dir) not in sys.path:
        sys.path.insert(0, str(sut_dir))

    from app import app  # pylint: disable=import-error
    from models import db, Product  # pylint: disable=import-error

    csv_path = Path(args.file)
    if not csv_path.is_absolute():
        csv_path = (root / csv_path).resolve()

    if not csv_path.exists():
        print(f'ERROR: No existe el archivo: {csv_path}')
        sys.exit(1)

    required_cols = {'sku', 'name', 'price', 'stock'}
    inserted = 0
    updated = 0
    skipped = 0

    with app.app_context():
        with csv_path.open('r', encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            if not required_cols.issubset(set(reader.fieldnames or [])):
                print(f'ERROR: El CSV debe incluir columnas: {sorted(required_cols)}')
                sys.exit(1)

            for row_num, row in enumerate(reader, start=2):
                try:
                    sku = (row.get('sku') or '').strip()
                    name = (row.get('name') or '').strip()
                    category = (row.get('category') or 'General').strip()
                    description = (row.get('description') or '').strip()
                    image_url = (row.get('image_url') or '').strip()
                    price = float(row.get('price', 0))
                    stock = int(row.get('stock', 0))

                    if not sku or not name:
                        skipped += 1
                        continue
                    if price < 0 or stock < 0:
                        skipped += 1
                        continue

                    existing = Product.query.filter_by(sku=sku).first()
                    if existing:
                        existing.name = name
                        existing.category = category
                        existing.price = price
                        existing.stock = stock
                        existing.description = description
                        existing.image_url = image_url
                        updated += 1
                    else:
                        db.session.add(Product(
                            sku=sku,
                            name=name,
                            category=category,
                            price=price,
                            stock=stock,
                            description=description,
                            image_url=image_url
                        ))
                        inserted += 1
                except (TypeError, ValueError):
                    print(f'WARNING: Fila {row_num} inválida, se omite.')
                    skipped += 1

        db.session.commit()
        total = Product.query.count()

    print(f'IMPORT OK | inserted={inserted} updated={updated} skipped={skipped} total_products={total}')


if __name__ == '__main__':
    main()
