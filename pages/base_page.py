"""
pages/base_page.py
Clase base para todos los Page Objects.
Implementa la Regla de Oro #3 (POM) y Regla de Oro #2 (sin time.sleep).
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from utils.wait_helpers import WaitHelpers
from utils.screenshot_helper import take_screenshot
import logging

logger = logging.getLogger(__name__)

BASE_URL = os.getenv("BROWSER_BASE_URL", "http://localhost:5000")
DEFAULT_TIMEOUT = 15


class BasePage:
    """
    Clase base de Page Object Model.

    Todas las páginas heredan de aquí.
    REGLA: ningún método llama a time.sleep().
    """

    def __init__(self, driver):
        self.driver = driver
        self.wait = WebDriverWait(driver, DEFAULT_TIMEOUT)
        self.helpers = WaitHelpers(driver, DEFAULT_TIMEOUT)
        self.base_url = BASE_URL

    # ─── Navegación ──────────────────────────────────────────────────────────

    def open(self, path: str = ''):
        """Navega a la URL base + path."""
        url = f"{self.base_url}{path}"
        logger.info(f"[NAV] Abriendo: {url}")
        self.driver.get(url)
        return self

    def get_current_url(self) -> str:
        return self.driver.current_url

    def get_title(self) -> str:
        return self.driver.title

    # ─── Elementos ───────────────────────────────────────────────────────────

    def find(self, locator: tuple):
        """Encuentra un elemento con espera explícita."""
        return self.helpers.wait_for_element_visible(locator)

    def find_present(self, locator: tuple):
        """Encuentra elemento solo presente en DOM (no necesariamente visible)."""
        return self.helpers.wait_for_element_present(locator)

    def find_clickable(self, locator: tuple):
        """Encuentra elemento clickable."""
        return self.helpers.wait_for_element_clickable(locator)

    def find_all(self, locator: tuple):
        """Encuentra todos los elementos que coinciden."""
        return self.helpers.wait_for_elements(locator)

    def click(self, locator: tuple):
        """Hace click en el elemento esperando que sea clickable."""
        el = self.find_clickable(locator)
        el.click()
        return el

    def type_text(self, locator: tuple, text: str, clear: bool = True):
        """Escribe texto en el elemento."""
        el = self.find(locator)
        if clear:
            el.clear()
        el.send_keys(text)
        return el

    def get_text(self, locator: tuple) -> str:
        """Retorna el texto visible de un elemento."""
        return self.find(locator).text.strip()

    def get_attribute(self, locator: tuple, attribute: str) -> str:
        """Retorna el valor de un atributo del elemento."""
        return self.find(locator).get_attribute(attribute)

    def is_displayed(self, locator: tuple) -> bool:
        """Verifica si el elemento es visible."""
        try:
            el = WebDriverWait(self.driver, 5).until(
                EC.visibility_of_element_located(locator))
            return el.is_displayed()
        except (TimeoutException, NoSuchElementException):
            return False

    def is_enabled(self, locator: tuple) -> bool:
        """Verifica si el elemento está habilitado."""
        try:
            el = self.driver.find_element(*locator)
            return el.is_enabled()
        except NoSuchElementException:
            return False

    # ─── Esperas específicas ─────────────────────────────────────────────────

    def wait_for_text(self, locator: tuple, text: str):
        """Espera texto en elemento."""
        return self.helpers.wait_for_text_in_element(locator, text)

    def wait_for_url(self, partial_url: str):
        """Espera URL parcial."""
        return self.helpers.wait_for_url_contains(partial_url)

    def wait_for_toast(self, text: str = None):
        """Espera toast de confirmación."""
        return self.helpers.wait_for_toast(text)

    def wait_for_table_row(self, table_locator: tuple, text: str):
        """Espera fila en tabla con texto específico."""
        return self.helpers.wait_for_table_row_with_text(table_locator, text)

    # ─── Scroll ──────────────────────────────────────────────────────────────

    def scroll_to_element(self, locator: tuple):
        """Hace scroll hasta el elemento."""
        el = self.find(locator)
        self.driver.execute_script("arguments[0].scrollIntoView(true);", el)
        return el

    def scroll_to_bottom(self):
        """Hace scroll al fondo de la página."""
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

    # ─── JavaScript ──────────────────────────────────────────────────────────

    def execute_js(self, script: str, *args):
        """Ejecuta JavaScript en la página."""
        return self.driver.execute_script(script, *args)

    def click_js(self, locator: tuple):
        """Click vía JavaScript (útil para elementos solapados)."""
        el = self.find_present(locator)
        self.driver.execute_script("arguments[0].click();", el)

    # ─── Screenshots ──────────────────────────────────────────────────────────

    def take_screenshot(self, name: str = 'screenshot') -> str:
        """Toma captura de pantalla."""
        return take_screenshot(self.driver, name)
