"""
tests/conftest.py
Fixtures globales para todos los tests de Selenium.
Configura drivers, URLs base, reporting de screenshots y reset de base de datos.
"""
import sys
import os
import pytest
import requests
import logging
from datetime import datetime

# Aseguramos que los módulos del proyecto sean encontrados
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils.driver_factory import DriverFactory, SUT_BASE_URL
from utils.screenshot_helper import take_screenshot
from utils.csv_generator import generate_products_csv

logger = logging.getLogger(__name__)


# ─── Configuración global ────────────────────────────────────────────────────

def pytest_configure(config):
    """Configuración de pytest al inicio."""
    os.makedirs('reports', exist_ok=True)
    os.makedirs('reports/screenshots', exist_ok=True)
    # Generar reporte HTML con timestamp para no sobrescribir ejecuciones previas
    htmlpath = getattr(config.option, 'htmlpath', None)
    if not htmlpath:
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        config.option.htmlpath = os.path.join('reports', f'report_{ts}.html')
    if hasattr(config.option, 'self_contained_html'):
        config.option.self_contained_html = True


# ─── Hook para captura de screenshots en fallos ───────────────────────────────

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Hook que captura screenshot cuando un test falla (para el reporte HTML)."""
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f'rep_{rep.when}', rep)


@pytest.fixture(autouse=True)
def screenshot_on_failure(request):
    """
    Fixture automático: toma screenshot si el test falla.
    Se ejecuta para TODOS los tests que usan el fixture 'driver'.
    """
    yield
    # Se ejecuta DESPUÉS del test
    if hasattr(request.node, 'rep_call') and request.node.rep_call.failed:
        driver = request.node.funcargs.get('driver') or \
                 request.node.funcargs.get('admin_driver') or \
                 request.node.funcargs.get('store_driver')
        if driver:
            screenshot_path = take_screenshot(driver, request.node.name)
            if screenshot_path:
                logger.info(f"Screenshot de fallo: {screenshot_path}")


# ─── Fixtures de Driver ───────────────────────────────────────────────────────

@pytest.fixture(scope='function')
def driver():
    """
    Driver Chrome local para tests individuales.
    Scope 'function': se crea y destruye por cada test.
    """
    d = DriverFactory.get_driver(browser='chrome', remote=False, headless=True)
    yield d
    d.quit()


@pytest.fixture(scope='function')
def chrome_driver():
    """Driver Chrome local (alias explícito)."""
    d = DriverFactory.get_driver(browser='chrome', remote=False, headless=True)
    yield d
    d.quit()


@pytest.fixture(scope='function')
def firefox_driver():
    """Driver Firefox local."""
    d = DriverFactory.get_driver(browser='firefox', remote=False, headless=True)
    yield d
    d.quit()


@pytest.fixture(scope='function')
def grid_chrome_driver():
    """Driver Chrome remoto vía Selenium Grid."""
    d = DriverFactory.get_driver(browser='chrome', remote=True, headless=True)
    yield d
    d.quit()


@pytest.fixture(scope='function')
def grid_firefox_driver():
    """Driver Firefox remoto vía Selenium Grid."""
    d = DriverFactory.get_driver(browser='firefox', remote=True, headless=True)
    yield d
    d.quit()


# ─── Fixture de URL base ──────────────────────────────────────────────────────

@pytest.fixture(scope='session')
def base_url():
    """URL base del SUT."""
    return SUT_BASE_URL


# ─── Fixture de reset de base de datos ───────────────────────────────────────

@pytest.fixture(scope='function')
def reset_db():
    """
    Resetea la base de datos del SUT antes de un test.
    Llama al endpoint /api/admin/reset del SUT.
    """
    try:
        response = requests.post(f"{SUT_BASE_URL}/api/admin/reset", timeout=5)
        assert response.status_code == 200, f"Error reseteando DB: {response.text}"
        logger.info("[Fixture] Base de datos reseteada")
    except requests.ConnectionError:
        pytest.fail("No se puede conectar al SUT. ¿Está corriendo en localhost:5000?")
    yield


# ─── Fixture de datos CSV ─────────────────────────────────────────────────────

@pytest.fixture(scope='session')
def bulk_csv_path():
    """Genera el CSV de prueba para CP01 y retorna su ruta."""
    return generate_products_csv('products_bulk.csv', n=5, prefix='BULK')


@pytest.fixture(scope='function')
def fresh_bulk_csv():
    """Genera un nuevo CSV con SKUs únicos cada vez que se llama."""
    import random
    import string
    prefix = ''.join(random.choices(string.ascii_uppercase, k=4))
    return generate_products_csv(f'bulk_{prefix}.csv', n=5, prefix=prefix)


# ─── Fixtures de Page Objects ─────────────────────────────────────────────────

@pytest.fixture(scope='function')
def admin_driver(driver):
    """Driver ya autenticado en el admin."""
    from pages.admin.login_page import AdminLoginPage
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    login = AdminLoginPage(driver)
    login.navigate()
    login.login_as_admin()
    WebDriverWait(driver, 10).until(
        lambda d: '/admin/dashboard' in d.current_url or '/admin/inventory' in d.current_url
    )
    driver.get(f"{SUT_BASE_URL}/admin/inventory")
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, 'inventory-table')))
    return driver


# ─── Fixture para CP04: dos browsers ─────────────────────────────────────────

@pytest.fixture(scope='function')
def two_browsers():
    """
    Fixture que provee dos drivers independientes para CP04 usando Selenium Grid.
    Retorna (chrome_driver, firefox_driver).
    """
    d1 = DriverFactory.get_driver(browser='chrome', remote=True, headless=True)
    d2 = DriverFactory.get_driver(browser='firefox', remote=True, headless=True)
    yield d1, d2
    d1.quit()
    d2.quit()


# ─── Verificación de conexión al SUT ─────────────────────────────────────────

@pytest.fixture(scope='session', autouse=True)
def verify_sut_running():
    """Verifica al inicio que el SUT esté disponible."""
    if os.getenv('SKIP_SUT_CHECK', '0') == '1':
        logger.info('[SUT] Verificacion omitida por SKIP_SUT_CHECK=1')
        return

    try:
        r = requests.get(f"{SUT_BASE_URL}/store", timeout=5)
        if r.status_code != 200:
            pytest.exit(f"SUT no disponible en {SUT_BASE_URL}. HTTP {r.status_code}.")
        logger.info(f"[SUT] Disponible en {SUT_BASE_URL}")
    except requests.ConnectionError:
        pytest.exit(
            f"\n{'='*60}\n"
            f"ERROR: El SUT no está corriendo en {SUT_BASE_URL}\n"
            f"Ejecuta primero: cd sut && python app.py\n"
            f"{'='*60}"
        )
