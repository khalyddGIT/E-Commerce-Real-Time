"""
pages/store/cart_page.py
Page Object para el carrito y checkout de la tienda.
"""
from selenium.webdriver.common.by import By
from pages.base_page import BasePage


class StoreCartPage(BasePage):
    """POM del carrito de compras."""

    URL = '/store/cart'
    URL_CHECKOUT = '/store/checkout'

    # ─── Locators ─────────────────────────────────────────────────────────────
    CART_ITEMS_LIST = (By.ID, 'cart-items-list')
    EMPTY_CART = (By.ID, 'empty-cart-message')
    BTN_CHECKOUT = (By.ID, 'btn-proceed-checkout')
    BTN_CONTINUE = (By.ID, 'btn-continue-shopping')
    CART_TOTAL = (By.ID, 'cart-grand-total')
    CART_COUNT = (By.ID, 'cart-count')

    # Checkout
    CHECKOUT_FORM = (By.ID, 'checkout-form')
    CHECKOUT_NAME = (By.ID, 'checkout-name')
    CHECKOUT_EMAIL = (By.ID, 'checkout-email')
    CHECKOUT_ADDRESS = (By.ID, 'checkout-address')
    BTN_CONFIRM_ORDER = (By.ID, 'btn-confirm-order')
    CHECKOUT_ERROR = (By.ID, 'checkout-error')

    # Order Success
    ORDER_SUCCESS = (By.ID, 'order-success-container')
    ORDER_ID = (By.ID, 'order-id')
    CUSTOMER_NAME = (By.ID, 'customer-name')

    # ─── Actions ──────────────────────────────────────────────────────────────

    def navigate(self):
        """Navega al carrito."""
        self.open(self.URL)
        return self

    def proceed_to_checkout(self):
        """Hace click en 'Proceder al Pago'."""
        self.click(self.BTN_CHECKOUT)
        self.find(self.CHECKOUT_FORM)
        return self

    def fill_checkout_form(self, name: str, email: str, address: str):
        """Completa el formulario de checkout."""
        self.type_text(self.CHECKOUT_NAME, name)
        self.type_text(self.CHECKOUT_EMAIL, email)
        self.type_text(self.CHECKOUT_ADDRESS, address)
        return self

    def confirm_order(self):
        """Hace click en 'Confirmar Pedido'."""
        self.click(self.BTN_CONFIRM_ORDER)
        return self

    def complete_checkout(self, name: str, email: str, address: str):
        """
        Flujo completo de checkout:
        carrito → formulario → confirmar → página de éxito.
        """
        self.proceed_to_checkout()
        self.fill_checkout_form(name, email, address)
        self.confirm_order()
        # Esperar redirección a la página de éxito
        self.wait_for_url('/store/order/')
        self.find(self.ORDER_SUCCESS)
        return self

    # ─── Validaciones ─────────────────────────────────────────────────────────

    def is_cart_empty(self) -> bool:
        """Verifica si el carrito está vacío."""
        return self.is_displayed(self.EMPTY_CART)

    def is_product_in_cart(self, product_id: int) -> bool:
        """Verifica si un producto está en el carrito."""
        locator = (By.ID, f'cart-item-{product_id}')
        return self.is_displayed(locator)

    def get_cart_total(self) -> str:
        """Retorna el texto del total del carrito."""
        return self.get_text(self.CART_TOTAL)

    def get_order_id(self) -> str:
        """Retorna el ID del pedido confirmado."""
        return self.get_text(self.ORDER_ID)

    def get_order_customer_name(self) -> str:
        """Retorna el nombre del cliente en la confirmación."""
        return self.get_text(self.CUSTOMER_NAME)

    def wait_for_order_success(self, timeout: int = 15):
        """Espera a que aparezca la página de confirmación del pedido."""
        self.wait_for_url('/store/order/')
        return self.find(self.ORDER_SUCCESS)

    def get_checkout_error(self) -> str:
        """Retorna el mensaje de error en checkout (ej: sin stock)."""
        return self.get_text(self.CHECKOUT_ERROR)

    def has_checkout_error(self) -> bool:
        """Verifica si hay un error en el checkout."""
        return self.is_displayed(self.CHECKOUT_ERROR)
