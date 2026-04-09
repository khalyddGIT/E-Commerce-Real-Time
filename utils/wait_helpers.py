"""
utils/wait_helpers.py
Wrappers de WebDriverWait para cumplir la Regla de Oro #2:
PROHIBIDO time.sleep(). Toda espera = WebDriverWait + ExpectedConditions.
"""
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
import logging

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 15
LONG_TIMEOUT = 30
SHORT_TIMEOUT = 5


class WaitHelpers:
    """
    Clase de utilidades de espera explícita.
    NINGÚN método usa time.sleep() — Regla de Oro #2.
    """

    def __init__(self, driver, timeout: int = DEFAULT_TIMEOUT):
        self.driver = driver
        self.timeout = timeout
        self.wait = WebDriverWait(driver, timeout)

    # ─── Esperas de elementos ────────────────────────────────────────────────

    def wait_for_element_visible(self, locator: tuple):
        """Espera a que el elemento sea visible."""
        return self.wait.until(EC.visibility_of_element_located(locator))

    def wait_for_element_present(self, locator: tuple):
        """Espera a que el elemento esté presente en DOM (puede no ser visible)."""
        return self.wait.until(EC.presence_of_element_located(locator))

    def wait_for_element_clickable(self, locator: tuple):
        """Espera a que el elemento sea clickable."""
        return self.wait.until(EC.element_to_be_clickable(locator))

    def wait_for_element_invisible(self, locator: tuple):
        """Espera a que el elemento desaparezca."""
        return self.wait.until(EC.invisibility_of_element_located(locator))

    def wait_for_elements(self, locator: tuple):
        """Espera a que haya al menos un elemento con el locator."""
        return self.wait.until(EC.presence_of_all_elements_located(locator))

    # ─── Esperas de texto ────────────────────────────────────────────────────

    def wait_for_text_in_element(self, locator: tuple, text: str):
        """Espera a que el texto aparezca en el elemento."""
        return self.wait.until(EC.text_to_be_present_in_element(locator, text))

    def wait_for_text_in_value(self, locator: tuple, text: str):
        """Espera a que el texto aparezca en el atributo value del elemento."""
        return self.wait.until(EC.text_to_be_present_in_element_value(locator, text))

    # ─── Esperas de atributos ────────────────────────────────────────────────

    def wait_for_element_disabled(self, locator: tuple, timeout: int = None):
        """
        Espera a que el elemento tenga el atributo 'disabled'.
        Clave para Regla de Oro #1: botón Sin Stock debe estar disabled.
        """
        t = timeout or self.timeout

        def _is_disabled(drv):
            try:
                el = drv.find_element(*locator)
                return not el.is_enabled()
            except Exception:
                return False

        return WebDriverWait(self.driver, t).until(_is_disabled)

    def wait_for_element_enabled(self, locator: tuple, timeout: int = None):
        """Espera a que el elemento esté habilitado."""
        t = timeout or self.timeout

        def _is_enabled(drv):
            try:
                el = drv.find_element(*locator)
                return el.is_enabled()
            except Exception:
                return False

        return WebDriverWait(self.driver, t).until(_is_enabled)

    def wait_for_attribute(self, locator: tuple, attribute: str, value: str):
        """Espera a que el atributo del elemento tenga un valor específico."""
        def _check(drv):
            try:
                el = drv.find_element(*locator)
                return el.get_attribute(attribute) == value
            except Exception:
                return False
        return WebDriverWait(self.driver, self.timeout).until(_check)

    # ─── Esperas de URL / Page ───────────────────────────────────────────────

    def wait_for_url_contains(self, partial_url: str):
        """Espera a que la URL contenga el texto dado."""
        return self.wait.until(EC.url_contains(partial_url))

    def wait_for_url_to_be(self, url: str):
        """Espera URL exacta."""
        return self.wait.until(EC.url_to_be(url))

    def wait_for_page_title(self, title: str):
        """Espera a que el título de la página coincida."""
        return self.wait.until(EC.title_contains(title))

    # ─── Esperas de alertas ──────────────────────────────────────────────────

    def wait_for_alert(self):
        """Espera a que aparezca un alert del navegador."""
        return self.wait.until(EC.alert_is_present())

    # ─── Esperas de tablas ───────────────────────────────────────────────────

    def wait_for_table_row_with_text(self, table_locator: tuple, text: str,
                                      timeout: int = None):
        """
        Espera a que una fila de la tabla contenga el texto dado.
        Clave para CP01: verificar que el CSV se cargó en la tabla.
        """
        t = timeout or self.timeout

        def _row_exists(drv):
            try:
                table = drv.find_element(*table_locator)
                return text in table.text
            except Exception:
                return False

        return WebDriverWait(self.driver, t).until(_row_exists)

    # ─── Esperas de Toast ────────────────────────────────────────────────────

    def wait_for_toast(self, text: str = None, timeout: int = None):
        """
        Espera a que aparezca un toast notification (CP02).
        Si se proporciona text, espera que el toast contenga ese texto.
        """
        t = timeout or self.timeout
        toast_locator = (By.CSS_SELECTOR, '.toast, .toast-notification, .alert')

        def _toast_visible(drv):
            try:
                elements = drv.find_elements(*toast_locator)
                if not elements:
                    return False
                for el in elements:
                    if el.is_displayed():
                        if text is None or text in el.text:
                            return el
                return False
            except Exception:
                return False

        return WebDriverWait(self.driver, t).until(_toast_visible)

    # ─── Esperas de WebSocket ────────────────────────────────────────────────

    def wait_for_button_text(self, locator: tuple, expected_text: str,
                              timeout: int = None):
        """
        Espera a que el texto del botón cambie.
        Crítico para Regla de Oro #1: esperar que el botón diga 'Sin Stock'.
        """
        t = timeout or self.timeout
        return self.wait_for_text_in_element(locator, expected_text)

    def wait_for_stock_to_be(self, stock_locator: tuple, expected_stock: int,
                              timeout: int = None):
        """Espera a que el stock mostrado sea el esperado."""
        t = timeout or LONG_TIMEOUT

        def _stock_matches(drv):
            try:
                el = drv.find_element(*stock_locator)
                return str(expected_stock) in el.text
            except Exception:
                return False

        return WebDriverWait(self.driver, t).until(_stock_matches)

    # ─── Helpers de seguridad ────────────────────────────────────────────────

    def is_element_present(self, locator: tuple) -> bool:
        """Verifica si un elemento existe sin lanzar excepción."""
        try:
            WebDriverWait(self.driver, SHORT_TIMEOUT).until(
                EC.presence_of_element_located(locator)
            )
            return True
        except TimeoutException:
            return False

    def safe_find(self, locator: tuple, timeout: int = SHORT_TIMEOUT):
        """Busca un elemento con timeout reducido. Retorna None si no existe."""
        try:
            return WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located(locator)
            )
        except TimeoutException:
            return None
