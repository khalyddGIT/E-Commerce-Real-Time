"""
pages/admin/inventory_page.py
Page Object para el panel de inventario del administrador.
Clave para CP01 (CSV), CP02 (edición de stock + Toast) y CP12 (real-time).
"""
import os
from selenium.webdriver.common.by import By
from pages.base_page import BasePage


class AdminInventoryPage(BasePage):
    """POM del inventario del admin."""

    URL = '/admin/inventory'
    URL_UPLOAD_CSV = '/admin/upload-csv'

    # ─── Locators ─────────────────────────────────────────────────────────────
    INVENTORY_TABLE = (By.ID, 'inventory-table')
    INVENTORY_TBODY = (By.ID, 'inventory-tbody')
    BTN_ADD_PRODUCT = (By.ID, 'btn-add-product')
    BTN_GO_UPLOAD_CSV = (By.ID, 'btn-go-upload-csv')
    TOAST_CONTAINER = (By.ID, 'toast-container')

    # ─── Actions ──────────────────────────────────────────────────────────────

    def navigate(self):
        """Navega al inventario y espera que la tabla cargue."""
        self.open(self.URL)
        self.find(self.INVENTORY_TABLE)
        return self

    def navigate_to_upload_csv(self):
        """Navega a la página de carga CSV."""
        self.open(self.URL_UPLOAD_CSV)
        return self

    # ─── CP01: Carga masiva CSV ────────────────────────────────────────────────

    def upload_csv(self, filepath: str):
        """
        Sube un archivo CSV al admin.
        Usa el input type=file con ruta absoluta.
        """
        self.navigate_to_upload_csv()
        # Esperar el input de archivo
        file_input = self.find_present((By.ID, 'csv-file-input'))
        # Enviar la ruta del archivo al input (sin click — es invisible)
        file_input.send_keys(os.path.abspath(filepath))
        # Verificar que el nombre aparece
        self.find((By.ID, 'selected-file-name'))
        # Hacer click en el botón de upload
        self.click((By.ID, 'btn-upload-csv'))
        return self

    def wait_for_csv_result(self, expected_text: str = None, timeout: int = 15):
        """
        Espera el mensaje de resultado de la carga CSV.
        Puede ser éxito, warning o error.
        """
        locator = (By.CSS_SELECTOR,
                   '#csv-result-message, .toast-notification, .alert')

        def _message_visible(drv):
            elements = drv.find_elements(*locator)
            for el in elements:
                if el.is_displayed():
                    if expected_text is None or expected_text in el.text:
                        return el
            return False

        from selenium.webdriver.support.ui import WebDriverWait
        return WebDriverWait(self.driver, timeout).until(_message_visible)

    # ─── CP02: Edición de stock + Toast ───────────────────────────────────────

    def set_stock(self, product_id: int, new_stock: int):
        """
        Modifica el stock de un producto y guarda vía AJAX.
        Regla de Oro #2: no usa time.sleep().
        """
        input_locator = (By.ID, f'stock-input-{product_id}')
        btn_locator = (By.ID, f'btn-save-stock-{product_id}')

        stock_input = self.find(input_locator)
        stock_input.clear()
        stock_input.send_keys(str(new_stock))
        self.click(btn_locator)
        return self

    def wait_for_toast_message(self, text: str = None, timeout: int = 10):
        """
        Espera el toast de confirmación del admin (CP02).
        Retorna el elemento del toast con el mensaje.
        """
        return self.helpers.wait_for_toast(text, timeout)

    def get_stock_badge_text(self, product_id: int) -> str:
        """Retorna el texto del badge de stock (Disponible / Stock Bajo / Sin Stock)."""
        badge_locator = (By.ID, f'stock-badge-{product_id}')
        return self.get_text(badge_locator)

    # ─── Validaciones de tabla ─────────────────────────────────────────────────

    def wait_for_product_in_table(self, sku: str, timeout: int = 15) -> bool:
        """
        Espera a que un producto con el SKU dado aparezca en la tabla.
        Regla de Oro #2: usa WebDriverWait.
        """
        locator = (By.ID, f'sku-{sku}')

        def _sku_visible(drv):
            elements = drv.find_elements(*locator)
            return len(elements) > 0 and elements[0].is_displayed()

        from selenium.webdriver.support.ui import WebDriverWait
        try:
            return WebDriverWait(self.driver, timeout).until(_sku_visible)
        except Exception:
            # Recargar y buscar
            self.navigate()
            return self.helpers.is_element_present(locator)

    def get_product_count(self) -> int:
        """Retorna el número de filas en la tabla de inventario."""
        rows = self.driver.find_elements(By.CSS_SELECTOR, '#inventory-tbody tr')
        # Excluir la fila vacía
        return sum(1 for r in rows if r.get_attribute('id') != 'empty-row'
                   and 'product-row' in (r.get_attribute('id') or ''))

    def is_product_in_table(self, text: str) -> bool:
        """Verifica si un texto aparece en la tabla."""
        try:
            table = self.find(self.INVENTORY_TABLE)
            return text in table.text
        except Exception:
            return False

    def get_product_stock_from_table(self, product_id: int) -> int:
        """Retorna el stock actual de un producto en la tabla."""
        input_locator = (By.ID, f'stock-input-{product_id}')
        value = self.get_attribute(input_locator, 'value')
        return int(value)
