"""
utils/screenshot_helper.py
Captura de pantallas automática en fallos para el reporte HTML.
"""
import os
import time
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

SCREENSHOT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'reports', 'screenshots')


def ensure_screenshot_dir():
    """Crea el directorio de screenshots si no existe."""
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)


def take_screenshot(driver, test_name: str = 'test') -> str:
    """
    Toma una captura de pantalla y la guarda en reports/screenshots/.

    Args:
        driver: instancia de WebDriver
        test_name: nombre del test para el nombre del archivo

    Returns:
        Ruta absoluta de la imagen guardada, o '' si falla.
    """
    ensure_screenshot_dir()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    # Limpiar nombre del test para usar como filename
    safe_name = ''.join(c if c.isalnum() or c in '-_' else '_' for c in test_name)
    filename = f"{safe_name}_{timestamp}.png"
    filepath = os.path.join(SCREENSHOT_DIR, filename)
    try:
        driver.save_screenshot(filepath)
        logger.info(f"[Screenshot] Guardado: {filepath}")
        return filepath
    except Exception as e:
        logger.error(f"[Screenshot] Error al guardar: {e}")
        return ''


def take_screenshot_on_failure(driver, request):
    """
    Helper para usar en conftest.py con el fixture request de pytest.
    Toma screenshot cuando el test falla.
    """
    if request.node.rep_call.failed if hasattr(request.node, 'rep_call') else False:
        take_screenshot(driver, request.node.name)


class ScreenshotOnFailure:
    """
    Context manager que toma screenshot si el bloque falla.

    Usage:
        with ScreenshotOnFailure(driver, 'test_name'):
            # código del test
    """
    def __init__(self, driver, test_name: str):
        self.driver = driver
        self.test_name = test_name

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            take_screenshot(self.driver, self.test_name)
        return False  # no suprimir la excepción
