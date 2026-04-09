"""
pages/store/product_page.py
Page Object para la página de detalle de producto.
Implementa la Regla de Oro #1: stock 0 → botón Sin Stock deshabilitado vía WS.
"""
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from pages.base_page import BasePage


class StoreProductPage(BasePage):
    """POM de la página de detalle de producto."""

    # ─── Locators ─────────────────────────────────────────────────────────────
    PRODUCT_NAME = (By.ID, 'product-name')
    PRODUCT_SKU = (By.ID, 'product-sku')
    PRODUCT_PRICE = (By.ID, 'product-price')
    STOCK_COUNT = (By.ID, 'stock-count')
    STOCK_STATUS_TEXT = (By.ID, 'stock-status-text')
    ADD_TO_CART_BTN = (By.ID, 'btn-add-to-cart')
    QTY_INPUT = (By.ID, 'qty-input')
    QTY_DECREASE = (By.ID, 'btn-qty-decrease')
    QTY_INCREASE = (By.ID, 'btn-qty-increase')
    CART_FEEDBACK = (By.ID, 'cart-feedback')
    BREADCRUMB = (By.ID, 'breadcrumb-home')

    # ─── Actions ──────────────────────────────────────────────────────────────

    def navigate(self, product_id: int):
        """Navega a la página de detalle del producto."""
        self.open(f'/store/product/{product_id}')
        self.find(self.ADD_TO_CART_BTN)
        return self

    def set_quantity(self, qty: int):
        """Establece la cantidad a comprar."""
        qty_el = self.find(self.QTY_INPUT)
        qty_el.clear()
        qty_el.send_keys(str(qty))
        return self

    def add_to_cart(self):
        """Hace click en Añadir al carrito."""
        self.click(self.ADD_TO_CART_BTN)
        return self

    def go_back_to_store(self):
        """Navega de vuelta a la tienda."""
        self.click(self.BREADCRUMB)
        return self

    # ─── Validaciones de stock real-time ──────────────────────────────────────

    def get_current_stock(self) -> int:
        """Retorna el stock actual mostrado en la página."""
        try:
            return int(self.get_text(self.STOCK_COUNT))
        except (ValueError, Exception):
            return -1

    def get_add_to_cart_text(self) -> str:
        """Retorna el texto actual del botón."""
        return self.get_text(self.ADD_TO_CART_BTN)

    def is_add_to_cart_enabled(self) -> bool:
        """Verifica si el botón está habilitado."""
        return self.is_enabled(self.ADD_TO_CART_BTN)

    def wait_for_out_of_stock(self, timeout: int = 20):
        """
        REGLA DE ORO #1: Espera a que el botón cambie a 'Sin Stock'
        y se deshabilite vía WebSocket, SIN recargar la página.
        """
        # Paso 1: esperar que el texto cambie
        self.helpers.wait_for_text_in_element(self.ADD_TO_CART_BTN, 'Sin Stock', timeout)
        # Paso 2: esperar que el botón quede disabled
        self.helpers.wait_for_element_disabled(self.ADD_TO_CART_BTN, timeout)
        return self

    def wait_for_stock_value(self, expected: int, timeout: int = 20):
        """Espera a que el contador de stock muestre el valor esperado."""
        def _stock_matches(drv):
            try:
                el = drv.find_element(*self.STOCK_COUNT)
                return el.text.strip() == str(expected)
            except Exception:
                return False
        return WebDriverWait(self.driver, timeout).until(_stock_matches)

    def get_cart_feedback_text(self) -> str:
        """Retorna el texto de feedback al agregar al carrito."""
        return self.get_text(self.CART_FEEDBACK)

    # ─── Info del producto ─────────────────────────────────────────────────────

    def get_product_name(self) -> str:
        return self.get_text(self.PRODUCT_NAME)

    def get_product_sku(self) -> str:
        return self.get_text(self.PRODUCT_SKU)
