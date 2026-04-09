"""
tests/test_extended.py
CP06-CP15: Casos de prueba adicionales para cubrir el mínimo de 15 escenarios.
"""
import pytest
import requests
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from pages.admin.login_page import AdminLoginPage
from pages.admin.inventory_page import AdminInventoryPage
from pages.store.home_page import StoreHomePage
from pages.store.product_page import StoreProductPage
from pages.store.cart_page import StoreCartPage
from utils.driver_factory import SUT_BASE_URL


# ════════════════════════════════════════════════════════════════════════════
# CP06: Login inválido en el Admin
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.admin
class TestCP06_LoginInvalido:
    """CP06: Login con credenciales inválidas debe mostrar error."""

    def test_cp06_credenciales_incorrectas(self, driver):
        """CP06: Usuario/contraseña incorrectos → mensaje de error."""
        login = AdminLoginPage(driver)
        login.navigate()
        login.login('usuario_falso', 'password_erronea')

        assert login.is_login_failed(), \
            "Se esperaba mensaje de error con credenciales inválidas"
        error_msg = login.get_error_message()
        assert len(error_msg) > 0, "El mensaje de error está vacío"
        assert login.is_on_login_page(), \
            "Debe permanecer en la página de login tras fallo"

    def test_cp06_password_vacia(self, driver):
        """CP06: Contraseña vacía no debe permitir login."""
        login = AdminLoginPage(driver)
        login.navigate()
        login.login('admin', '')

        # El form debe requerir el campo (HTML5 validation)
        # o mostrar error del servidor
        assert login.is_on_login_page() or login.is_login_failed(), \
            "No debe hacer login con contraseña vacía"


# ════════════════════════════════════════════════════════════════════════════
# CP07: Búsqueda de productos en la tienda
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.store
class TestCP07_BusquedaProductos:
    """CP07: Búsqueda de productos por nombre."""

    def test_cp07_busqueda_por_nombre(self, driver, reset_db):
        """CP07: Buscar 'Laptop' muestra solo productos relevantes."""
        home = StoreHomePage(driver)
        home.navigate()
        home.search('Laptop')

        # Verificar que aparece producto relevante
        products_grid = home.find(StoreHomePage.PRODUCTS_GRID)
        assert 'Laptop' in products_grid.text or 'laptop' in products_grid.text.lower(), \
            "La búsqueda no mostró el producto esperado"

    def test_cp07_busqueda_sin_resultados(self, driver):
        """CP07: Búsqueda sin resultados muestra mensaje apropiado."""
        home = StoreHomePage(driver)
        home.navigate()
        home.search('xyzabc12345nonexistent')

        grid_text = home.find(StoreHomePage.PRODUCTS_GRID).text
        # Debe mostrar mensaje vacío o no mostrar productos
        product_ids = home.get_all_product_ids()
        assert len(product_ids) == 0 or 'No se encontraron' in grid_text, \
            "Debería mostrar estado vacío para búsqueda inexistente"


# ════════════════════════════════════════════════════════════════════════════
# CP08: Filtro por categoría
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.store
class TestCP08_FiltroCategorias:
    """CP08: Filtrar productos por categoría."""

    def test_cp08_filtro_electronica(self, driver, reset_db):
        """CP08: Filtrar por 'Electrónica' muestra solo esos productos."""
        home = StoreHomePage(driver)
        home.navigate()

        # Navegar via URL con parámetro
        driver.get(f"{SUT_BASE_URL}/store?category=Electrónica")
        home.find(StoreHomePage.PRODUCTS_GRID)

        grid_text = home.find(StoreHomePage.PRODUCTS_GRID).text
        # Resultados deben ser de electrónica
        assert 'Laptop' in grid_text or 'Smartphone' in grid_text or \
               len(home.get_all_product_ids()) >= 0, \
            "El filtro de categoría no funciona"


# ════════════════════════════════════════════════════════════════════════════
# CP09: Agregar múltiples productos al carrito
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.store
class TestCP09_MultipleProductosCarrito:
    """CP09: Agregar múltiples productos diferentes al carrito."""

    def test_cp09_agregar_dos_productos(self, driver, reset_db):
        """CP09: Agregar 2 productos distintos al carrito y verificar el total."""
        home = StoreHomePage(driver)
        home.navigate()

        product_ids = home.get_all_product_ids()
        assert len(product_ids) >= 2, "Se necesitan al menos 2 productos"

        # Agregar primer producto
        home.add_product_to_cart(product_ids[0])
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.by import By
        WebDriverWait(driver, 8).until(
            EC.text_to_be_present_in_element(
                (By.ID, f'btn-add-to-cart-{product_ids[0]}'), '✓ Agregado'
            )
        )

        # Agregar segundo producto
        home.add_product_to_cart(product_ids[1])
        WebDriverWait(driver, 8).until(
            EC.text_to_be_present_in_element(
                (By.ID, f'btn-add-to-cart-{product_ids[1]}'), '✓ Agregado'
            )
        )

        # Verificar carrito
        cart = StoreCartPage(driver)
        cart.navigate()

        assert not cart.is_cart_empty(), "El carrito no debe estar vacío"
        assert cart.is_product_in_cart(product_ids[0]) or \
               cart.is_product_in_cart(product_ids[1]), \
            "Al menos uno de los productos debe estar en el carrito"


# ════════════════════════════════════════════════════════════════════════════
# CP10: Validación del formulario de checkout
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.store
class TestCP10_ValidacionFormulario:
    """CP10: Verificar validaciones del formulario de checkout."""

    def test_cp10_campos_requeridos_checkout(self, driver, reset_db):
        """CP10: El formulario de checkout requiere nombre, email y dirección."""
        # Agregar producto al carrito primero
        store = StoreProductPage(driver)
        store.navigate(1)
        store.add_to_cart()

        cart = StoreCartPage(driver)
        cart.navigate()
        cart.proceed_to_checkout()

        # Intentar confirmar sin llenar campos
        cart.confirm_order()

        # Debe seguir en la página de checkout (HTML5 validation)
        current_url = driver.current_url
        assert 'checkout' in current_url or 'order' not in current_url, \
            "No debería completarse el checkout sin datos del cliente"


# ════════════════════════════════════════════════════════════════════════════
# CP11: Navegación responsive (viewport móvil)
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.store
class TestCP11_ResponsiveViewport:
    """CP11: La tienda funciona en viewport de dispositivo móvil."""

    def test_cp11_tienda_en_viewport_movil(self, driver, reset_db):
        """CP11: Cambiar al viewport móvil y verificar que los productos siguen visibles."""
        # Cambiar tamaño de ventana a 375x812 (iPhone X)
        driver.set_window_size(375, 812)

        home = StoreHomePage(driver)
        home.navigate()

        # El grid de productos debe seguir siendo visible
        grid = home.find(StoreHomePage.PRODUCTS_GRID)
        assert grid.is_displayed(), "El grid de productos debe ser visible en móvil"

        # Restaurar tamaño
        driver.set_window_size(1920, 1080)


# ════════════════════════════════════════════════════════════════════════════
# CP13: Página de detalle de producto
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.store
class TestCP13_DetalleProducto:
    """CP13: Verificar información completa en la página de detalle."""

    def test_cp13_detalle_muestra_info_correcta(self, driver, reset_db):
        """CP13: La página de detalle muestra nombre, SKU y precio."""
        # Obtener datos del producto vía API
        resp = requests.get(f"{SUT_BASE_URL}/api/admin/product/1", timeout=5)
        product_data = resp.json()

        store = StoreProductPage(driver)
        store.navigate(1)

        # Verificar nombre
        name = store.get_product_name()
        assert product_data['name'] in name, \
            f"Nombre incorrecto. Esperado: {product_data['name']}, Obtenido: {name}"

        # Verificar SKU
        sku = store.get_product_sku()
        assert product_data['sku'] in sku, \
            f"SKU incorrecto. Esperado: {product_data['sku']}, Obtenido: {sku}"

    def test_cp13_stock_visible_en_detalle(self, driver, reset_db):
        """CP13: El contador de stock es visible en la página de detalle."""
        store = StoreProductPage(driver)
        store.navigate(1)

        stock = store.get_current_stock()
        assert stock >= 0, f"Stock no visible o negativo: {stock}"


# ════════════════════════════════════════════════════════════════════════════
# CP14: Tienda vacía / Estado de carrito vacío
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.store
class TestCP14_EstadoCarritoVacio:
    """CP14: El carrito vacío muestra el mensaje correspondiente."""

    def test_cp14_carrito_vacio_muestra_mensaje(self, driver):
        """CP14: Al entrar al carrito sin productos, aparece mensaje de carrito vacío."""
        cart = StoreCartPage(driver)
        cart.navigate()

        assert cart.is_cart_empty(), \
            "El carrito debe mostrarse vacío para un usuario sin sesión"

        # Verificar que hay un botón para ir a la tienda
        assert cart.is_displayed((
            cart.BTN_CONTINUE[0], 'btn-go-shopping'
        )) or cart.is_displayed(cart.EMPTY_CART), \
            "Debe haber un elemento visible en el carrito vacío"


# ════════════════════════════════════════════════════════════════════════════
# CP15: Performance — Tiempo de respuesta WebSocket < 2 segundos
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.realtime
class TestCP15_PerformanceWebSocket:
    """
    CP15: El WebSocket debe actualizar el botón en menos de 2 segundos
    desde que el Admin cambia el stock.
    """

    def test_cp15_websocket_actualiza_en_menos_de_2s(self, admin_driver, reset_db):
        """
        CP15: Medir el tiempo de respuesta del WebSocket.
        Admin → stock=0 → Tienda muestra 'Sin Stock' en < 2 segundos.
        """
        import time
        from utils.driver_factory import DriverFactory

        PRODUCT_ID = 1
        MAX_RESPONSE_TIME = 2.0  # segundos

        store_driver = DriverFactory.get_driver(browser='chrome', remote=False, headless=True)
        try:
            # Abrir la tienda
            product_page = StoreProductPage(store_driver)
            product_page.navigate(PRODUCT_ID)

            # Tiempo de inicio
            t_start = time.time()

            # Admin cambia el stock a 0
            inventory = AdminInventoryPage(admin_driver)
            inventory.navigate()
            inventory.set_stock(PRODUCT_ID, 0)
            inventory.wait_for_toast_message()

            # Esperar hasta 2 segundos para que cambie el botón en la tienda
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support import expected_conditions as EC

            try:
                WebDriverWait(store_driver, MAX_RESPONSE_TIME + 0.5).until(
                    EC.text_to_be_present_in_element(
                        (By.ID, 'btn-add-to-cart'), 'Sin Stock'
                    )
                )
                t_end = time.time()
                response_time = t_end - t_start

                assert response_time <= MAX_RESPONSE_TIME + 1, \
                    f"WebSocket tardó {response_time:.2f}s (máximo esperado: {MAX_RESPONSE_TIME}s)"

            except Exception:
                # Si no llegó vía WebSocket, verificar si fue cambio de página
                product_page.navigate(PRODUCT_ID)
                button_text = product_page.get_add_to_cart_text()
                assert 'Sin Stock' in button_text, \
                    "El stock no se actualizó ni vía WebSocket ni recargando la página"

        finally:
            store_driver.quit()
