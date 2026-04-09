"""
pages/store/home_page.py
Page Object para la página principal de la tienda.
"""
from selenium.webdriver.common.by import By
from pages.base_page import BasePage


class StoreHomePage(BasePage):
    """POM de la home de la tienda."""

    URL = '/store'

    # ─── Locators ─────────────────────────────────────────────────────────────
    PRODUCTS_GRID = (By.ID, 'products-grid')
    SEARCH_INPUT = (By.ID, 'search-input')
    SEARCH_BTN = (By.ID, 'btn-search')
    CART_BTN = (By.ID, 'btn-cart')
    CART_COUNT = (By.ID, 'cart-count')
    RT_STATUS = (By.ID, 'realtime-status')
    EMPTY_PRODUCTS = (By.ID, 'empty-products-message')

    # ─── Actions ──────────────────────────────────────────────────────────────

    def navigate(self):
        """Navega a la tienda y espera que cargue el grid."""
        self.open(self.URL)
        self.find(self.PRODUCTS_GRID)
        return self

    def search(self, query: str):
        """Busca un producto por nombre."""
        self.type_text(self.SEARCH_INPUT, query)
        self.click(self.SEARCH_BTN)
        return self

    def filter_by_category(self, category: str):
        """Filtra productos por categoría."""
        cat_link = (By.ID, f'nav-cat-{category.lower().replace(" ", "-")}')
        self.click(cat_link)
        return self

    def add_product_to_cart(self, product_id: int):
        """Hace click en el botón 'Añadir al carrito' de un producto."""
        btn_locator = (By.ID, f'btn-add-to-cart-{product_id}')
        self.click(btn_locator)
        return self

    def go_to_cart(self):
        """Navega al carrito."""
        self.click(self.CART_BTN)
        return self

    def go_to_product(self, product_id: int):
        """Navega a la página de detalle del producto."""
        link_locator = (By.CSS_SELECTOR, f'#product-card-{product_id} .product-link')
        self.click(link_locator)
        return self

    # ─── Validaciones ─────────────────────────────────────────────────────────

    def get_cart_count(self) -> int:
        """Retorna el número de items en el carrito (del header)."""
        text = self.get_text(self.CART_COUNT)
        try:
            return int(text)
        except ValueError:
            return 0

    def get_add_to_cart_btn(self, product_id: int):
        """Retorna el elemento del botón de agregar al carrito."""
        return self.find((By.ID, f'btn-add-to-cart-{product_id}'))

    def get_add_to_cart_btn_text(self, product_id: int) -> str:
        """Retorna el texto actual del botón."""
        return self.get_text((By.ID, f'btn-add-to-cart-{product_id}'))

    def is_add_to_cart_btn_enabled(self, product_id: int) -> bool:
        """Verifica si el botón está habilitado."""
        return self.is_enabled((By.ID, f'btn-add-to-cart-{product_id}'))

    def wait_for_out_of_stock_btn(self, product_id: int, timeout: int = 20):
        """
        Espera a que el botón cambie a 'Sin Stock' vía WebSocket.
        Implementa la Regla de Oro #1.
        """
        locator = (By.ID, f'btn-add-to-cart-{product_id}')
        return self.helpers.wait_for_button_text(locator, 'Sin Stock', timeout)

    def wait_for_btn_disabled(self, product_id: int, timeout: int = 20):
        """Espera a que el botón de agregar quede deshabilitado."""
        locator = (By.ID, f'btn-add-to-cart-{product_id}')
        return self.helpers.wait_for_element_disabled(locator, timeout)

    def get_stock_indicator_text(self, product_id: int) -> str:
        """Retorna el texto del indicador de stock de la tarjeta."""
        return self.get_text((By.ID, f'stock-indicator-{product_id}'))

    def get_all_product_ids(self) -> list:
        """Retorna los IDs de todos los productos visibles."""
        cards = self.driver.find_elements(By.CSS_SELECTOR, '[id^="product-card-"]')
        ids = []
        for card in cards:
            card_id = card.get_attribute('id').replace('product-card-', '')
            try:
                ids.append(int(card_id))
            except ValueError:
                pass
        return ids

    def wait_for_realtime_connected(self):
        """Espera a que el WebSocket esté conectado (estado verde)."""
        def _connected(drv):
            try:
                el = drv.find_element(*self.RT_STATUS)
                return '🟢' in el.text
            except Exception:
                return False
        from selenium.webdriver.support.ui import WebDriverWait
        return WebDriverWait(self.driver, 10).until(_connected)
