# E-Commerce Real-Time — Framework de Automatización

## Descripción
Framework completo de pruebas de automatización para un sistema E-Commerce con actualización de inventario en tiempo real mediante WebSockets.

## Estructura del Proyecto
```
E-Commerce Real-Time/
├── sut/                    # Sistema Bajo Prueba (Flask + WebSockets)
│   ├── app.py              # Aplicación Flask principal
│   ├── models.py           # Modelos SQLAlchemy (Product, Order, CartSession)
│   ├── templates/          # Templates HTML (Admin + Storefront)
│   ├── static/             # CSS + JavaScript (Socket.IO)
│   └── requirements.txt
├── pages/                  # Page Object Model (POM)
│   ├── base_page.py
│   ├── admin/              # login_page, inventory_page
│   └── store/              # home_page, product_page, cart_page
├── tests/                  # Casos de prueba
│   ├── conftest.py         # Fixtures globales
│   ├── test_inventory.py   # CP01, CP02
│   ├── test_realtime.py    # CP03, CP04, CP05, CP12
│   └── test_extended.py    # CP06-CP11, CP13-CP15
├── utils/                  # Utilidades
│   ├── driver_factory.py   # Fábrica de WebDrivers
│   ├── wait_helpers.py     # WebDriverWait helpers
│   ├── screenshot_helper.py
│   └── csv_generator.py
├── data/                   # Datos de prueba
│   ├── products_bulk.csv
│   └── test_users.json
├── reports/                # Reportes HTML y screenshots
├── docker-compose.yml      # Selenium Grid (Hub + Chrome + Firefox)
├── pytest.ini
├── requirements.txt
└── start.py               # Script de inicio rápido
```

## Inicio Rápido

### 1. Instalar dependencias
```bash
# Dependencias del SUT
pip install -r sut/requirements.txt

# Dependencias del framework de testing
pip install -r requirements.txt
```

### 2. Levantar el SUT
```bash
cd sut
python app.py
```
- **Admin Panel**: http://localhost:5000/admin/login (admin / admin123)
- **Tienda**: http://localhost:5000/store

### 3. Levantar Selenium Grid (opcional, para CP04/CP05)
```bash
docker-compose up -d
# Grid UI: http://localhost:4444
```

### 4. Ejecutar los tests
```bash
# Todos los tests (secuencial)
pytest tests/ -v

# Con paralelismo (4 workers)
pytest tests/ -n 4 --html=reports/report.html

# Solo tests de inventario
pytest tests/test_inventory.py -v -m admin

# Solo tests de tiempo real
pytest tests/test_realtime.py -v -m realtime

# Tests de concurrencia
pytest tests/test_realtime.py -v -m concurrent
```

## Reglas de Oro Implementadas

| Regla | Descripción | Implementación |
|-------|-------------|----------------|
| #1 | Stock 0 → botón "Sin Stock" deshabilitado automáticamente | `product_detail.js` + `socket.on('stock_update')` |
| #2 | Prohibido `time.sleep()` | `WaitHelpers` con `WebDriverWait` en toda la suite |
| #3 | Patrón Page Object Model | `pages/base_page.py` + todas las páginas |

## Casos de Prueba (15 mínimo)

| CP | Descripción | Archivo | Marker |
|----|-------------|---------|--------|
| CP01 | Carga masiva CSV + validación tabla | test_inventory.py | @admin |
| CP02 | Edición stock + Toast confirmación | test_inventory.py | @admin |
| CP03 | Compra E2E + decremento stock Admin | test_realtime.py | @e2e |
| CP04 | Sesión carrito Chrome → Firefox | test_realtime.py | @grid |
| CP05 | Concurrencia: última unidad | test_realtime.py | @concurrent |
| CP06 | Login inválido | test_extended.py | @admin |
| CP07 | Búsqueda por nombre | test_extended.py | @store |
| CP08 | Filtro por categoría | test_extended.py | @store |
| CP09 | Múltiples productos en carrito | test_extended.py | @store |
| CP10 | Validación formulario checkout | test_extended.py | @store |
| CP11 | Viewport móvil responsive | test_extended.py | @store |
| CP12 | WebSocket real-time (Regla de Oro #1) | test_realtime.py | @realtime |
| CP13 | Detalle producto info correcta | test_extended.py | @store |
| CP14 | Estado carrito vacío | test_extended.py | @store |
| CP15 | Performance WebSocket < 2s | test_extended.py | @realtime |

## Tecnologías
- **Python 3.10+** / Selenium WebDriver 4.x
- **Pytest** + pytest-xdist + pytest-html
- **Flask** + Flask-SocketIO (SUT)
- **Selenium Grid** via Docker
- **Page Object Model (POM)** + WebDriverWait
