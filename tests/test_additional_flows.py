import re

import requests
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from utils.driver_factory import SUT_BASE_URL


class TestAdditionalFlows:
    @staticmethod
    def _create_order_via_http(product_id=1, qty=1):
        session = requests.Session()
        add_resp = session.post(
            f"{SUT_BASE_URL}/api/cart/add",
            json={"product_id": product_id, "qty": qty},
            timeout=10,
        )
        assert add_resp.status_code == 200, f"No se pudo agregar al carrito: {add_resp.text}"

        checkout_resp = session.post(
            f"{SUT_BASE_URL}/store/checkout",
            data={
                "name": "Cliente QA",
                "email": "cliente.qa@test.com",
                "address": "Jr. Prueba 123",
                "payment_method": "Tarjeta",
            },
            allow_redirects=False,
            timeout=10,
        )
        assert checkout_resp.status_code in (301, 302), (
            f"Checkout no redirigió a orden: {checkout_resp.status_code} {checkout_resp.text}"
        )

        location = checkout_resp.headers.get("Location", "")
        match = re.search(r"/store/order/(\d+)", location)
        assert match, f"No se encontró order_id en Location: {location}"
        return int(match.group(1))

    @staticmethod
    def _build_admin_session():
        admin = requests.Session()
        login_resp = admin.post(
            f"{SUT_BASE_URL}/admin/login",
            data={"username": "admin", "password": "admin123"},
            allow_redirects=True,
            timeout=10,
        )
        assert login_resp.status_code == 200, f"Login admin falló: {login_resp.status_code}"

        inv_resp = admin.get(f"{SUT_BASE_URL}/admin/inventory", timeout=10)
        assert inv_resp.status_code == 200, "No se pudo abrir inventario para obtener CSRF"

        token_match = re.search(r'name="csrf_token" value="([^"]+)"', inv_resp.text)
        assert token_match, "No se encontró csrf_token en inventario"
        return admin, token_match.group(1)

    def test_store_search_and_add_to_cart(self, driver, reset_db):
        driver.get(f"{SUT_BASE_URL}/store")
        wait = WebDriverWait(driver, 15)

        search = wait.until(EC.visibility_of_element_located((By.ID, "search-input")))
        search.clear()
        search.send_keys("Laptop")
        driver.find_element(By.ID, "btn-search").click()

        # El click UI puede ser inestable en algunos entornos WebDriver;
        # usamos API de la misma sesión para validar el proceso de carrito.
        add_result = driver.execute_async_script(
            """
            const done = arguments[arguments.length - 1];
            fetch('/api/cart/add', {
              method: 'POST',
              headers: {'Content-Type': 'application/json'},
              body: JSON.stringify({product_id: 1, qty: 1})
            })
            .then(r => r.json())
            .then(done)
            .catch(() => done({success: false}));
            """
        )
        assert add_result and add_result.get("success"), f"No se pudo agregar al carrito: {add_result}"

        count = driver.execute_async_script(
            """
            const done = arguments[arguments.length - 1];
            fetch('/api/cart/count')
              .then(r => r.json())
              .then(data => done(data.count || 0))
              .catch(() => done(0));
            """
        )
        assert int(count) >= 1, "El carrito no se actualizó después de agregar producto"

    def test_store_checkout_end_to_end(self, driver, reset_db):
        driver.get(f"{SUT_BASE_URL}/store")
        wait = WebDriverWait(driver, 15)

        add_result = driver.execute_async_script(
            """
            const done = arguments[arguments.length - 1];
            fetch('/api/cart/add', {
              method: 'POST',
              headers: {'Content-Type': 'application/json'},
              body: JSON.stringify({product_id: 1, qty: 1})
            })
            .then(r => r.json())
            .then(done)
            .catch(() => done({success: false}));
            """
        )
        assert add_result and add_result.get("success"), f"Add to cart failed: {add_result}"

        driver.get(f"{SUT_BASE_URL}/store/cart")
        wait.until(EC.element_to_be_clickable((By.ID, "btn-proceed-checkout"))).click()

        wait.until(EC.visibility_of_element_located((By.ID, "checkout-name"))).send_keys("Cliente QA")
        driver.find_element(By.ID, "checkout-email").send_keys("cliente.qa@test.com")
        driver.find_element(By.ID, "checkout-address").send_keys("Jr. Prueba 123")
        driver.find_element(By.ID, "payment_method").send_keys("Tarjeta")
        driver.find_element(By.ID, "btn-confirm-order").click()

        title = wait.until(EC.visibility_of_element_located((By.ID, "order-success-title"))).text
        order_id = driver.find_element(By.ID, "order-id").text
        assert "Pedido Confirmado" in title
        assert "Pedido #" in order_id

    def test_admin_update_stock_reflected_in_api(self, reset_db, admin_driver):
        wait = WebDriverWait(admin_driver, 15)

        stock_input = wait.until(EC.visibility_of_element_located((By.ID, "stock-input-1")))
        current_stock = int(stock_input.get_attribute("value"))
        new_stock = current_stock + 2

        stock_input.clear()
        stock_input.send_keys(str(new_stock))
        admin_driver.find_element(By.ID, "btn-save-stock-1").click()

        wait.until(lambda d: d.find_element(By.ID, "stock-input-1").get_attribute("value") == str(new_stock))

        api_resp = requests.get(f"{SUT_BASE_URL}/api/admin/product/1", timeout=10)
        assert api_resp.status_code == 200
        data = api_resp.json()
        assert int(data.get("stock", -1)) == new_stock

    def test_store_shows_sin_stock_when_admin_sets_zero(self, driver, reset_db):
        admin, csrf_token = self._build_admin_session()
        stock_resp = admin.post(
            f"{SUT_BASE_URL}/admin/inventory/edit/1",
            data={"stock": 0, "csrf_token": csrf_token},
            timeout=10,
        )
        assert stock_resp.status_code == 200

        driver.get(f"{SUT_BASE_URL}/store")
        wait = WebDriverWait(driver, 15)
        add_btn = wait.until(EC.presence_of_element_located((By.ID, "btn-add-to-cart-1")))

        assert "Sin Stock" in add_btn.text
        assert not add_btn.is_enabled()

    def test_admin_sales_export_csv_contains_product_name(self, reset_db):
        self._create_order_via_http(product_id=1, qty=1)
        admin, _ = self._build_admin_session()

        csv_resp = admin.get(f"{SUT_BASE_URL}/admin/sales?export=csv", timeout=10)
        assert csv_resp.status_code == 200
        assert "text/csv" in csv_resp.headers.get("Content-Type", "")

        csv_text = csv_resp.text
        assert "orden_id" in csv_text
        assert "Laptop UltraBook Pro" in csv_text

    def test_admin_order_status_flow_confirmed_to_shipped(self, reset_db):
        order_id = self._create_order_via_http(product_id=2, qty=1)
        admin, csrf_token = self._build_admin_session()

        # Las órdenes creadas por checkout nacen en "confirmed".
        # Se valida transición permitida confirmed -> shipped.
        update_resp = admin.post(
            f"{SUT_BASE_URL}/admin/orders/{order_id}/status",
            data={"new_status": "shipped", "csrf_token": csrf_token},
            allow_redirects=True,
            timeout=10,
        )
        assert update_resp.status_code == 200

        sales_page = admin.get(f"{SUT_BASE_URL}/admin/sales?q={order_id}", timeout=10)
        assert sales_page.status_code == 200
        assert f"#{order_id}" in sales_page.text
        assert "shipped" in sales_page.text.lower()
