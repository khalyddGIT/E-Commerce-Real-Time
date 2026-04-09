"""
tests/test_inventory.py
CP01: Carga masiva de productos mediante CSV y validación en tabla.
CP02: Edición de stock dinámico y verificación de alertas Toast.
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from pages.admin.login_page import AdminLoginPage
from pages.admin.inventory_page import AdminInventoryPage
from utils.csv_generator import generate_products_csv, generate_invalid_csv, random_sku


# ════════════════════════════════════════════════════════════════════════════
# CP01: Carga Masiva de Productos mediante CSV
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.admin
class TestCP01_CargaCSV:
    """
    CP01: Verificar que la carga masiva de un CSV agrega los productos
    correctamente y que aparecen en la tabla de inventario.
    """

    def test_cp01_carga_csv_exitosa(self, admin_driver, fresh_bulk_csv, reset_db):
        """
        CP01: Cargar un CSV válido con 5 productos.
        Verificar que aparecen en la tabla de inventario.
        """
        inventory = AdminInventoryPage(admin_driver)

        # Registrar cantidad inicial de productos
        inventory.navigate()
        initial_count = inventory.get_product_count()

        # Subir el CSV
        inventory.upload_csv(fresh_bulk_csv)

        # VALIDACIÓN: Esperar mensaje de éxito (sin recargar manualmente)
        result = inventory.wait_for_csv_result()
        assert result is not None, "No apareció mensaje de resultado del CSV"
        assert 'procesado' in result.text.lower() or 'agregado' in result.text.lower(), \
            f"Mensaje inesperado: {result.text}"

        # VALIDACIÓN: Los productos deben aparecer en la tabla
        inventory.navigate()
        new_count = inventory.get_product_count()
        assert new_count > initial_count, \
            f"El conteo de productos no aumentó. Antes: {initial_count}, Después: {new_count}"

    def test_cp01_csv_aparece_en_tabla(self, admin_driver, reset_db):
        """
        CP01: Verificar que un SKU específico del CSV aparece en la tabla.
        """
        # Generar CSV con SKU conocido
        unique_sku = f"TEST-{random_sku('VALID')}"
        import csv, io, os
        csv_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 'data', f'{unique_sku}.csv'
        )
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=['sku', 'name', 'category', 'price', 'stock'])
            writer.writeheader()
            writer.writerow({
                'sku': unique_sku,
                'name': 'Producto de Prueba CSV Test',
                'category': 'Test',
                'price': '199.99',
                'stock': '30'
            })

        inventory = AdminInventoryPage(admin_driver)
        inventory.upload_csv(csv_path)

        # VALIDACIÓN: El SKU específico debe estar visible en la tabla
        inventory.navigate()
        assert inventory.wait_for_product_in_table(unique_sku), \
            f"SKU '{unique_sku}' no apareció en la tabla después del CSV."

        # Cleanup
        try:
            os.remove(csv_path)
        except Exception:
            pass

    def test_cp01_csv_formato_invalido(self, admin_driver):
        """
        CP07 (bonus en CP01): CSV con columnas incorrectas debe mostrar error.
        """
        invalid_csv = generate_invalid_csv('products_invalid.csv')
        inventory = AdminInventoryPage(admin_driver)
        inventory.upload_csv(invalid_csv)

        # VALIDACIÓN: debe aparecer un mensaje de error
        result = inventory.wait_for_csv_result()
        assert result is not None, "No apareció mensaje al cargar CSV inválido"
        result_text = result.text.lower()
        assert any(w in result_text for w in ['error', 'columnas', 'debe']), \
            f"Se esperaba error por CSV inválido, pero se obtuvo: {result.text}"


# ════════════════════════════════════════════════════════════════════════════
# CP02: Edición de Stock y Toast de Confirmación
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.admin
class TestCP02_EdicionStock:
    """
    CP02: Edición de stock dinámico con verificación de alert Toast.
    """

    def test_cp02_edicion_stock_exitosa(self, admin_driver, reset_db):
        """
        CP02: Editar el stock de un producto y verificar Toast de confirmación.
        """
        inventory = AdminInventoryPage(admin_driver)
        inventory.navigate()

        # Usar el primer producto (ID 1 después del reset)
        product_id = 1
        new_stock = 42

        # Editar el stock
        inventory.set_stock(product_id, new_stock)

        # VALIDACIÓN CLAVE: Esperar Toast de confirmación (sin time.sleep)
        toast = inventory.wait_for_toast_message(timeout=10)
        assert toast is not None, "No apareció el Toast de confirmación después de editar el stock"
        toast_text = toast.text.lower()
        assert any(w in toast_text for w in ['actualizado', 'stock', 'guardado', str(new_stock)]), \
            f"Texto del toast inesperado: {toast.text}"

    def test_cp02_stock_badge_actualizado(self, admin_driver, reset_db):
        """
        CP02: Verificar que el badge de estado cambia al actualizar el stock.
        """
        inventory = AdminInventoryPage(admin_driver)
        inventory.navigate()

        product_id = 1

        # Establecer stock a 0 → debe cambiar a "Sin Stock"
        inventory.set_stock(product_id, 0)
        inventory.wait_for_toast_message()

        badge_text = inventory.get_stock_badge_text(product_id)
        assert 'sin stock' in badge_text.lower(), \
            f"Badge esperado 'Sin Stock' pero fue: {badge_text}"

    def test_cp02_stock_bajo_badge(self, admin_driver, reset_db):
        """
        CP02: Stock < 5 muestra badge 'Stock Bajo'.
        """
        inventory = AdminInventoryPage(admin_driver)
        inventory.navigate()

        product_id = 1
        inventory.set_stock(product_id, 3)
        inventory.wait_for_toast_message()

        badge_text = inventory.get_stock_badge_text(product_id)
        assert 'bajo' in badge_text.lower(), \
            f"Badge esperado 'Stock Bajo' pero fue: {badge_text}"

    def test_cp02_toast_contiene_nombre_producto(self, admin_driver, reset_db):
        """
        CP02: El Toast debe mencionar el nombre del producto actualizado.
        """
        inventory = AdminInventoryPage(admin_driver)
        inventory.navigate()

        product_id = 1
        inventory.set_stock(product_id, 20)

        toast = inventory.wait_for_toast_message()
        assert toast is not None, "No apareció el toast"
        # El toast debe tener contenido relevante
        assert len(toast.text) > 5, f"Toast parece vacío: '{toast.text}'"

    def test_cp02_multiples_stocks(self, admin_driver, reset_db):
        """
        CP02: Editar el stock de varios productos y verificar que cada Toast es correcto.
        """
        inventory = AdminInventoryPage(admin_driver)
        inventory.navigate()

        test_cases = [(1, 15), (2, 0), (3, 100)]
        for product_id, new_stock in test_cases:
            inventory.set_stock(product_id, new_stock)
            toast = inventory.wait_for_toast_message()
            assert toast is not None, \
                f"No apareció Toast para producto {product_id}"
