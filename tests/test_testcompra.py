from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
import json


class TestTestcompra:
    def setup_method(self, method):
        self.driver = webdriver.Chrome()
        self.wait = WebDriverWait(self.driver, 15)

    def teardown_method(self, method):
        self.driver.quit()

    def test_testcompra(self):
        # Reset para asegurar stock y estado inicial del carrito
        self.driver.get("http://localhost:5000/api/admin/reset")

        self.driver.get("http://localhost:5000/store")
        self.driver.set_window_size(1280, 800)

        # Agregar 1 unidad por API usando la misma sesion del navegador
        add_result = self.driver.execute_async_script(
            """
            const done = arguments[arguments.length - 1];
            fetch('/api/cart/add', {
              method: 'POST',
              headers: {'Content-Type': 'application/json'},
              body: JSON.stringify({product_id: 2, qty: 1})
            })
            .then(r => r.json())
            .then(done)
            .catch(() => done({success: false}));
            """
        )
        assert add_result and add_result.get("success"), f"Error al agregar por API: {add_result}"

        # Validar por API que el carrito tiene al menos 1 item
        self.driver.get("http://localhost:5000/api/cart/count")
        body_text = self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body"))).text
        data = json.loads(body_text)
        assert int(data.get("count", 0)) >= 1, f"No se agrego al carrito. Respuesta: {data}"

        # Ir al carrito y verificar que hay al menos 1 item renderizado
        self.driver.get("http://localhost:5000/store/cart")
        self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".cart-item")))

        # Ir a checkout y completar compra
        self.wait.until(EC.element_to_be_clickable((By.ID, "btn-proceed-checkout"))).click()
        self.wait.until(EC.visibility_of_element_located((By.ID, "checkout-name"))).send_keys("Cliente Prueba")
        self.driver.find_element(By.ID, "checkout-email").send_keys("cliente.prueba@test.com")
        self.driver.find_element(By.ID, "checkout-address").send_keys("Av. Siempre Viva 123")
        self.driver.find_element(By.ID, "payment_method").send_keys("Tarjeta")
        self.wait.until(EC.element_to_be_clickable((By.ID, "btn-confirm-order"))).click()

        # Validar pagina de exito
        self.wait.until(EC.visibility_of_element_located((By.ID, "order-success-title")))
        order_title = self.driver.find_element(By.ID, "order-success-title").text
        order_id = self.driver.find_element(By.ID, "order-id").text
        assert "Pedido Confirmado" in order_title
        assert "Pedido #" in order_id
