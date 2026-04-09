"""
utils/driver_factory.py
Fábrica de WebDrivers: soporta Chrome/Firefox local y Selenium Grid remoto.
"""
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
import os


# ─── Configuración ──────────────────────────────────────────────────────────
GRID_URL = "http://localhost:4444"
SUT_BASE_URL = "http://localhost:5000"
IMPLICIT_WAIT = 0  # NUNCA usar implicit wait con explicit wait — son incompatibles
PAGE_LOAD_TIMEOUT = 30


class DriverFactory:
    """
    Crea instancias de WebDriver para pruebas locales o remotas (Grid).

    Regla de Oro #2: PROHIBIDO time.sleep().
    Todas las esperas deben implementarse en los Page Objects usando WebDriverWait.
    """

    @staticmethod
    def _chrome_options(headless: bool = False) -> ChromeOptions:
        opts = ChromeOptions()
        if headless:
            opts.add_argument('--headless=new')
        opts.add_argument('--no-sandbox')
        opts.add_argument('--disable-dev-shm-usage')
        opts.add_argument('--disable-gpu')
        opts.add_argument('--window-size=1920,1080')
        opts.add_argument('--disable-extensions')
        opts.add_experimental_option('excludeSwitches', ['enable-logging'])
        return opts

    @staticmethod
    def _firefox_options(headless: bool = False) -> FirefoxOptions:
        opts = FirefoxOptions()
        if headless:
            opts.add_argument('--headless')
        opts.add_argument('--width=1920')
        opts.add_argument('--height=1080')
        return opts

    @classmethod
    def get_local_chrome(cls, headless: bool = True) -> webdriver.Chrome:
        """Driver Chrome local. Usa webdriver-manager para el chromedriver."""
        from selenium.webdriver.chrome.service import Service
        from webdriver_manager.chrome import ChromeDriverManager
        opts = cls._chrome_options(headless)
        installed_path = ChromeDriverManager().install()
        driver_path = cls._resolve_driver_binary(installed_path, ('chromedriver.exe', 'chromedriver'))
        service = Service(driver_path)
        driver = webdriver.Chrome(service=service, options=opts)
        driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
        return driver

    @classmethod
    def get_local_firefox(cls, headless: bool = True) -> webdriver.Firefox:
        """Driver Firefox local. Usa webdriver-manager para el geckodriver."""
        from selenium.webdriver.firefox.service import Service
        from webdriver_manager.firefox import GeckoDriverManager
        opts = cls._firefox_options(headless)
        installed_path = GeckoDriverManager().install()
        driver_path = cls._resolve_driver_binary(installed_path, ('geckodriver.exe', 'geckodriver'))
        service = Service(driver_path)
        driver = webdriver.Firefox(service=service, options=opts)
        driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
        return driver

    @classmethod
    def get_grid_chrome(cls, headless: bool = True) -> webdriver.Remote:
        """Driver Chrome remoto via Selenium Grid."""
        opts = cls._chrome_options(headless)
        driver = webdriver.Remote(
            command_executor=GRID_URL,
            options=opts
        )
        driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
        return driver

    @classmethod
    def get_grid_firefox(cls, headless: bool = True) -> webdriver.Remote:
        """Driver Firefox remoto via Selenium Grid."""
        opts = cls._firefox_options(headless)
        driver = webdriver.Remote(
            command_executor=GRID_URL,
            options=opts
        )
        driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
        return driver

    @classmethod
    def get_driver(cls, browser: str = 'chrome',
                   remote: bool = False,
                   headless: bool = True):
        """
        Método principal para obtener un driver.

        Args:
            browser: 'chrome' o 'firefox'
            remote: True para Selenium Grid, False para local
            headless: True para modo sin interfaz
        """
        browser = browser.lower()
        if remote:
            if browser == 'chrome':
                return cls.get_grid_chrome(headless)
            elif browser == 'firefox':
                return cls.get_grid_firefox(headless)
            else:
                raise ValueError(f"Browser no soportado: {browser}")
        else:
            if browser == 'chrome':
                return cls.get_local_chrome(headless)
            elif browser == 'firefox':
                return cls.get_local_firefox(headless)
            else:
                raise ValueError(f"Browser no soportado: {browser}")
    @staticmethod
    def _resolve_driver_binary(candidate_path: str, expected_names: tuple[str, ...]) -> str:
        """
        Resuelve la ruta real del ejecutable del driver.
        webdriver-manager en algunos entornos devuelve un archivo de notices en vez del binario.
        """
        if not candidate_path:
            raise ValueError('Ruta de driver vacia')

        filename = os.path.basename(candidate_path).lower()
        if filename in expected_names:
            return candidate_path

        search_root = os.path.dirname(candidate_path)
        for root, _, files in os.walk(search_root):
            for f in files:
                if f.lower() in expected_names:
                    return os.path.join(root, f)

        raise FileNotFoundError(f'No se encontro ejecutable del driver en {search_root}')
