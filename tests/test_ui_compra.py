from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
import json


BASE_URL = "http://localhost:5000"


class TestFlujosUISimilarCompra:
    def setup_method(self, method):
        self.driver = webdriver.Chrome()
        self.wait = WebDriverWait(self.driver, 20)
        self.driver.set_window_size(1366, 900)

    def teardown_method(self, method):
        self.driver.quit()

    def _reset(self):
        self.driver.get(f"{BASE_URL}/api/admin/reset")

    def _add_to_cart_by_api_in_browser_session(self, product_id=1, qty=1):
        result = self.driver.execute_async_script(
            """
            const done = arguments[arguments.length - 1];
            fetch('/api/cart/add', {
              method: 'POST',
              headers: {'Content-Type': 'application/json'},
              body: JSON.stringify({product_id: arguments[0], qty: arguments[1]})
            })
            .then(r => r.json())
            .then(done)
            .catch(() => done({success:false}));
            """,
            product_id,
            qty,
        )
        assert result and result.get("success"), f"No se pudo agregar al carrito: {result}"

    def test_flujo_compra_completo(self):
        self._reset()
        self.driver.get(f"{BASE_URL}/store")

        self._add_to_cart_by_api_in_browser_session(product_id=2, qty=1)

        self.driver.get(f"{BASE_URL}/store/cart")
        self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".cart-item")))
        self.wait.until(EC.element_to_be_clickable((By.ID, "btn-proceed-checkout"))).click()

        self.wait.until(EC.visibility_of_element_located((By.ID, "checkout-name"))).send_keys("Cliente UI")
        self.driver.find_element(By.ID, "checkout-email").send_keys("cliente.ui@test.com")
        self.driver.find_element(By.ID, "checkout-address").send_keys("Av. Test 123")
        self.driver.find_element(By.ID, "payment_method").send_keys("Tarjeta")
        self.wait.until(EC.element_to_be_clickable((By.ID, "btn-confirm-order"))).click()

        title = self.wait.until(EC.visibility_of_element_located((By.ID, "order-success-title"))).text
        order_id = self.driver.find_element(By.ID, "order-id").text
        assert "Pedido Confirmado" in title
        assert "Pedido #" in order_id

    def test_flujo_admin_actualiza_stock(self):
        self._reset()
        self.driver.get(f"{BASE_URL}/admin/login")

        self.wait.until(EC.visibility_of_element_located((By.ID, "username"))).send_keys("admin")
        self.driver.find_element(By.ID, "password").send_keys("admin123")
        self.driver.find_element(By.ID, "btn-login").click()

        self.wait.until(lambda d: "/admin/dashboard" in d.current_url or "/admin/inventory" in d.current_url)
        self.driver.get(f"{BASE_URL}/admin/inventory")

        stock_input = self.wait.until(EC.visibility_of_element_located((By.ID, "stock-input-1")))
        csrf_token = self.driver.execute_script("return window.CSRF_TOKEN;")
        current_stock = int(stock_input.get_attribute("value"))
        new_stock = current_stock + 3

        update_result = self.driver.execute_async_script(
            """
            const done = arguments[arguments.length - 1];
            const stock = arguments[0];
            const csrf = arguments[1];
            fetch('/admin/inventory/edit/1', {
              method: 'POST',
              headers: {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'},
              body: `stock=${encodeURIComponent(stock)}&csrf_token=${encodeURIComponent(csrf)}`
            })
            .then(r => r.json())
            .then(done)
            .catch(() => done({success: false}));
            """,
            str(new_stock),
            csrf_token,
        )
        assert update_result and update_result.get("success"), f"No se actualizó stock: {update_result}"

        self.driver.get(f"{BASE_URL}/api/admin/product/1")
        body_text = self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body"))).text
        data = json.loads(body_text)
        assert int(data.get("stock", -1)) == new_stock

    def test_flujo_sin_stock_desde_admin_hacia_tienda(self):
        self._reset()

        self.driver.get(f"{BASE_URL}/admin/login")
        self.wait.until(EC.visibility_of_element_located((By.ID, "username"))).send_keys("admin")
        self.driver.find_element(By.ID, "password").send_keys("admin123")
        self.driver.find_element(By.ID, "btn-login").click()
        self.wait.until(lambda d: "/admin/dashboard" in d.current_url or "/admin/inventory" in d.current_url)
        self.driver.get(f"{BASE_URL}/admin/inventory")

        self.wait.until(EC.visibility_of_element_located((By.ID, "stock-input-1")))
        csrf_token = self.driver.execute_script("return window.CSRF_TOKEN;")
        update_result = self.driver.execute_async_script(
            """
            const done = arguments[arguments.length - 1];
            const csrf = arguments[0];
            fetch('/admin/inventory/edit/1', {
              method: 'POST',
              headers: {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'},
              body: `stock=0&csrf_token=${encodeURIComponent(csrf)}`
            })
            .then(r => r.json())
            .then(done)
            .catch(() => done({success: false}));
            """,
            csrf_token,
        )
        assert update_result and update_result.get("success"), f"No se actualizó stock a 0: {update_result}"

        self.driver.get(f"{BASE_URL}/store?refresh=1")
        add_btn = self.wait.until(EC.presence_of_element_located((By.ID, "btn-add-to-cart-1")))
        self.wait.until(lambda d: "Sin Stock" in d.find_element(By.ID, "btn-add-to-cart-1").text)
        assert "Sin Stock" in add_btn.text
        assert not add_btn.is_enabled()
