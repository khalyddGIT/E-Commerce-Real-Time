#!/usr/bin/env python3
"""
start.py — Script de inicio rápido del proyecto.
Instala dependencias y levanta el SUT automáticamente.
"""
import subprocess
import sys
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
SUT_DIR = os.path.join(ROOT, 'sut')


def run(cmd, cwd=None):
    print(f"\n> {cmd}")
    result = subprocess.run(cmd, shell=True, cwd=cwd or ROOT)
    return result.returncode


def main():
    print("=" * 60)
    print("  E-Commerce Real-Time — Inicio del Proyecto")
    print("=" * 60)

    # 1. Instalar dependencias del SUT
    print("\n[1/3] Instalando dependencias del SUT...")
    code = run(f"{sys.executable} -m pip install -r requirements.txt", cwd=SUT_DIR)
    if code != 0:
        print("Error instalando dependencias del SUT.")
        sys.exit(1)

    # 2. Instalar dependencias del framework de tests
    print("\n[2/3] Instalando dependencias del framework de tests...")
    code = run(f"{sys.executable} -m pip install -r requirements.txt", cwd=ROOT)
    if code != 0:
        print("Error instalando dependencias de testing.")
        sys.exit(1)

    # 3. Levantar el SUT
    print("\n[3/3] Levantando el SUT...")
    print("  → Admin: http://localhost:5000/admin/login (admin/admin123)")
    print("  → Tienda: http://localhost:5000/store")
    print("  → Para ejecutar tests: pytest tests/ -v")
    print("  → Presiona Ctrl+C para detener el servidor\n")

    run(f"{sys.executable} app.py", cwd=SUT_DIR)


if __name__ == '__main__':
    main()
