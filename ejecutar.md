## Documentación rápida: ejecutar proyecto y tests

### 1) Requisitos
- Python 3.10+
- `pip`
- (Opcional) Docker Desktop para Selenium Grid

### 2) Instalación
En PowerShell, desde la raíz del proyecto:

```powershell
cd "d:\Escritorio\E-Commerce Real-Time"

python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -r sut\requirements.txt
pip install -r requirements.txt
```

### 3) Ejecutar el sistema
```powershell
cd sut
python app.py
```

URLs:
- Admin: `http://localhost:5000/admin/login` (usuario: `admin`, clave: `admin123`)
- Tienda: `http://localhost:5000/store`
- Ventas admin: `http://localhost:5000/admin/sales`

---

## Tests necesarios

### A) Tests base (imprescindibles)
En otra terminal (con el venv activo), desde la raíz:

```powershell
cd "d:\Escritorio\E-Commerce Real-Time"
pytest tests\test_inventory.py -v
pytest tests\test_realtime.py -v
pytest tests\test_extended.py -v
```

### B) Suite completa
```powershell
pytest tests\ -v
```

### C) Con reporte HTML
```powershell
pytest tests\ -v --html=reports\report.html --self-contained-html
```

### D) Tests que requieren Grid (cross-browser/concurrencia)
Primero levanta Grid:

```powershell
docker-compose up -d
```

Luego:

```powershell
pytest tests\test_realtime.py -v -m grid
pytest tests\test_realtime.py -v -m concurrent
```

Grid UI: `http://localhost:4444`
