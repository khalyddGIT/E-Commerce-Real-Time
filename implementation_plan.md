# E-Commerce Real-Time — Framework de Automatización
## Plan de Implementación

## Objetivo
Construir el **sistema completo** en dos partes:
1. **SUT (Sistema Bajo Prueba)**: Aplicación E-Commerce real-time con Admin Panel + Storefront.
2. **Framework de Automatización**: Pruebas con Selenium WebDriver 4.x + Pytest + Selenium Grid (Docker).

---

## Arquitectura General

```
E-Commerce Real-Time/
├── sut/                          # Sistema Bajo Prueba (Flask + WebSockets)
│   ├── app.py                    # App principal Flask
│   ├── models.py                 # Modelos de datos (SQLite)
│   ├── templates/
│   │   ├── admin/                # Panel de administración
│   │   └── store/                # Storefront para clientes
│   ├── static/
│   │   ├── css/
│   │   └── js/                   # JS con WebSockets / AJAX
│   └── requirements.txt
│
├── pages/                        # Page Object Model (POM)
│   ├── base_page.py
│   ├── admin/
│   │   ├── login_page.py
│   │   ├── inventory_page.py
│   │   └── dashboard_page.py
│   └── store/
│       ├── home_page.py
│       ├── product_page.py
│       └── cart_page.py
│
├── tests/                        # Casos de prueba
│   ├── conftest.py               # Fixtures globales (driver, grid, etc.)
│   ├── test_inventory.py         # CP01, CP02 — Gestión de inventario
│   ├── test_realtime.py          # CP03, CP04, CP05 — Validación real-time
│   └── test_extended.py          # CP06 al CP15 — Escenarios adicionales
│
├── data/                         # Datos de prueba
│   ├── products_bulk.csv         # CSV para carga masiva (CP01)
│   ├── test_users.json
│   └── test_products.json
│
├── utils/                        # Utilidades
│   ├── driver_factory.py         # Fábrica de WebDrivers (local + Grid)
│   ├── wait_helpers.py           # Wrappers de WebDriverWait
│   ├── screenshot_helper.py      # Captura de pantallas en fallos
│   └── csv_generator.py         # Generador de CSVs de prueba
│
├── docker-compose.yml            # Selenium Grid (Hub + Nodes)
├── pytest.ini                    # Configuración Pytest + markers
├── setup.cfg                     # pytest-xdist + html report config
└── requirements.txt              # Dependencias Python
```

---

## Parte 1: SUT — Sistema E-Commerce Real-Time

### Tech Stack del SUT
- **Backend**: Flask (Python) + Flask-SocketIO (WebSockets)
- **Base de Datos**: SQLite con SQLAlchemy
- **Frontend**: HTML/CSS/JS con Socket.IO cliente
- **Servidor**: Gunicorn (producción) / Flask dev (testing)

### Módulos del SUT

#### [NEW] `sut/app.py`
- Endpoints REST: `/admin`, `/admin/products`, `/admin/upload-csv`
- Endpoints Store: `/`, `/product/<id>`, `/cart`, `/checkout`
- WebSocket events: `stock_update`, `order_confirmed`
- Autenticación básica para Admin

#### [NEW] `sut/models.py`
- Modelo `Product`: id, name, sku, price, stock, image_url
- Modelo `Order`: id, product_id, qty, status, timestamp
- Modelo `CartSession`: session_id, items (JSON)

#### [NEW] `sut/templates/admin/inventory.html`
- Tabla de productos con stock editable inline
- Botón "Cargar CSV" con progreso en tiempo real
- Toast notifications para confirmaciones
- Indicadores de stock crítico (rojo < 5 unidades)

#### [NEW] `sut/templates/store/product_detail.html`
- Botón "Añadir al Carrito" → cambia a **"Sin Stock"** (deshabilitado) vía WebSocket
- Contador de stock en tiempo real
- No requiere recarga de página

---

## Parte 2: Framework de Automatización

### Dependencias (requirements.txt)
```
selenium==4.x
pytest==7.x
pytest-xdist==3.x
pytest-html==4.x
pytest-rerunfailures==12.x
webdriver-manager==4.x
Faker==24.x
```

### Page Object Model (POM)

#### [NEW] `pages/base_page.py`
```python
class BasePage:
    def __init__(self, driver):
        self.driver = driver
        self.wait = WebDriverWait(driver, timeout=15)
    
    def wait_for_element(self, locator):
        return self.wait.until(EC.presence_of_element_located(locator))
    
    def wait_for_clickable(self, locator):
        return self.wait.until(EC.element_to_be_clickable(locator))
    
    def wait_for_text_in_element(self, locator, text):
        return self.wait.until(EC.text_to_be_present_in_element(locator, text))
```

#### [NEW] `pages/admin/inventory_page.py`
- `upload_csv(file_path)` — sube el CSV
- `edit_stock(sku, new_qty)` — modifica el stock
- `wait_for_toast(message)` — espera toast de confirmación
- `get_product_stock(sku)` — retorna stock actual

#### [NEW] `pages/store/product_page.py`
- `get_add_to_cart_button()` — retorna botón
- `wait_for_out_of_stock()` — espera cambio a "Sin Stock"
- `add_to_cart()` — agrega al carrito
- `get_current_stock()` — espera actualización WebSocket

### Casos de Prueba (15 mínimo)

| ID | Módulo | Descripción | Técnica Especial |
|----|--------|-------------|-----------------|
| CP01 | Admin | Carga masiva CSV → aparece en tabla | `wait_for_table_row()` |
| CP02 | Admin | Edición de stock → Toast de confirmación | `WebDriverWait + Toast` |
| CP03 | E2E | Compra completa → verifica decremento en Admin | Cross-page assertion |
| CP04 | Grid | Sesión Chrome → cerrar → Firefox → carrito persistente | Multi-browser Grid |
| CP05 | Concurrencia | 2 hilos comprando última unidad simultáneamente | `threading + pytest-xdist` |
| CP06 | Admin | Login con credenciales inválidas | Negative testing |
| CP07 | Admin | Carga CSV con formato inválido | Error handling |
| CP08 | Store | Filtro de productos por categoría | UI interaction |
| CP09 | Store | Búsqueda de producto por nombre | Dynamic content |
| CP10 | Store | Agregar múltiples productos al carrito | State management |
| CP11 | Store | Flujo de checkout completo con datos de envío | Form validation |
| CP12 | Real-Time | Stock se actualiza sin recarga al editar desde Admin | WebSocket assertion |
| CP13 | Admin | Exportar inventario como CSV | File download |
| CP14 | Store | Navegación responsive (viewport móvil) | Window resize |
| CP15 | Performance | Tiempo de respuesta del WebSocket < 2s | Timing assertion |

### Infrastructure: Selenium Grid con Docker

#### [NEW] `docker-compose.yml`
```yaml
version: '3.8'
services:
  selenium-hub:
    image: selenium/hub:4.18
    ports:
      - "4442:4442"
      - "4443:4443"
      - "4444:4444"
  
  chrome-node:
    image: selenium/node-chrome:4.18
    depends_on: [selenium-hub]
    environment:
      - SE_EVENT_BUS_HOST=selenium-hub
    deploy:
      replicas: 2
  
  firefox-node:
    image: selenium/node-firefox:4.18
    depends_on: [selenium-hub]
    environment:
      - SE_EVENT_BUS_HOST=selenium-hub
    deploy:
      replicas: 1
```

### Configuración Pytest

#### [NEW] `pytest.ini`
```ini
[pytest]
markers =
    admin: Tests del panel de administración
    store: Tests del storefront
    realtime: Tests de validación en tiempo real
    concurrent: Tests de concurrencia
addopts = --html=reports/report.html --self-contained-html -v
```

---

## Plan de Fases de Desarrollo

### Fase 1: SUT (2-3 horas)
1. Crear app Flask con modelos SQLite
2. Construir Admin Panel (HTML + JS)
3. Construir Storefront con WebSockets
4. Levantar y verificar manualmente

### Fase 2: Infraestructura de Testing (1 hora)
1. Crear `docker-compose.yml` para Selenium Grid
2. Crear `driver_factory.py` con soporte Grid + local
3. Configurar `pytest.ini` y fixtures base

### Fase 3: POM + Casos de Prueba (3-4 horas)
1. Implementar todas las Page Objects
2. Implementar CP01-CP05 (obligatorios)
3. Implementar CP06-CP15 (adicionales)
4. Asegurar 0 usos de `time.sleep()`

### Fase 4: Reportes y Documentación (30 min)
1. Verificar generación de reporte HTML
2. Asegurar capturas de pantalla en fallos
3. Ejecutar suite completa con `pytest -n 4`

---

## User Review Required

> [!IMPORTANT]
> **¿Construir el SUT?** El PDF describe un sistema E-Commerce como "Sistema Bajo Prueba". Para que las pruebas funcionen necesitamos una app real. ¿Debo construirla con Flask + SQLite + WebSockets, o ya tienes una URL/sistema existente para probar?

> [!WARNING]
> **Selenium Grid con Docker**: Las pruebas Grid (CP04, CP05) requieren Docker Desktop instalado y corriendo en tu máquina. ¿Lo tienes disponible?

> [!NOTE]
> **Python Version**: Usaré Python 3.10+ con todas las dependencias. Asegúrate de tener Python instalado.

---

## Verification Plan

### Automated
```bash
# Levantar el SUT
cd sut && python app.py

# Levantar Selenium Grid
docker-compose up -d

# Ejecutar todos los tests en paralelo (4 workers)
pytest tests/ -n 4 --html=reports/report.html

# Ejecutar solo casos de concurrencia
pytest tests/test_realtime.py -k "CP05" -v
```

### Manual
- Verificar que el reporte HTML se genera en `reports/report.html`
- Confirmar que las screenshots aparecen en los fallos
- Abrir `http://localhost:4444` para ver Selenium Grid UI
