"""
pages/admin/login_page.py
Page Object para la página de login del administrador.
"""
from selenium.webdriver.common.by import By
from pages.base_page import BasePage


class AdminLoginPage(BasePage):
    """POM de la página de login del admin."""

    URL = '/admin/login'

    # ─── Locators ────────────────────────────────────────────────────────────
    USERNAME_INPUT = (By.ID, 'username')
    PASSWORD_INPUT = (By.ID, 'password')
    LOGIN_BUTTON = (By.ID, 'btn-login')
    FLASH_MESSAGE = (By.ID, 'flash-message')
    LOGIN_FORM = (By.ID, 'admin-login-form')

    # ─── Actions ─────────────────────────────────────────────────────────────

    def navigate(self):
        """Navega a la página de login."""
        self.open(self.URL)
        self.find(self.LOGIN_FORM)
        return self

    def login(self, username: str, password: str):
        """Completa el formulario de login y lo envía."""
        self.type_text(self.USERNAME_INPUT, username)
        self.type_text(self.PASSWORD_INPUT, password)
        self.click(self.LOGIN_BUTTON)
        return self

    def login_as_admin(self):
        """Login con credenciales de administrador válidas."""
        return self.login('admin', 'admin123')

    # ─── Validations ─────────────────────────────────────────────────────────

    def get_error_message(self) -> str:
        """Retorna el mensaje de error de credenciales inválidas."""
        return self.get_text(self.FLASH_MESSAGE)

    def is_login_failed(self) -> bool:
        """Verifica si el login falló (aparece mensaje de error)."""
        return self.is_displayed(self.FLASH_MESSAGE)

    def is_on_login_page(self) -> bool:
        """Verifica si estamos en la página de login."""
        return 'login' in self.get_current_url()
