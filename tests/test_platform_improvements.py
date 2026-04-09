import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SUT_DIR = ROOT / 'sut'
if str(SUT_DIR) not in sys.path:
    sys.path.insert(0, str(SUT_DIR))

spec = importlib.util.spec_from_file_location('sut_app_module', SUT_DIR / 'app.py')
sut_app_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sut_app_module)


@pytest.fixture()
def client():
    sut_app_module.app.config['TESTING'] = True
    sut_app_module.app.template_folder = str(SUT_DIR / 'templates')
    sut_app_module.app.static_folder = str(SUT_DIR / 'static')
    with sut_app_module.app.test_client() as client:
        yield client


def login_session(client, role='admin'):
    user_map = {
        'admin': 'admin',
        'operator': 'operador',
        'viewer': 'visor'
    }
    with client.session_transaction() as sess:
        sess['admin_logged_in'] = True
        sess['admin_user'] = user_map[role]
        sess['admin_role'] = role if role != 'operator' else 'operator'
        sess['csrf_token'] = 'test-csrf-token'


@pytest.mark.unit
@pytest.mark.api
def test_api_v1_products_ok(client):
    response = client.get('/api/v1/products')
    assert response.status_code == 200
    payload = response.get_json()
    assert 'data' in payload
    assert isinstance(payload['data'], list)


@pytest.mark.integration
@pytest.mark.security
def test_admin_csrf_blocks_post_without_token(client):
    login_session(client, role='admin')
    response = client.post('/admin/inventory/edit/1', data={'stock': 9})
    assert response.status_code == 403
    payload = response.get_json()
    assert payload['success'] is False


@pytest.mark.integration
@pytest.mark.security
def test_viewer_cannot_edit_inventory(client):
    login_session(client, role='viewer')
    with sut_app_module.app.app_context():
        stock_before = sut_app_module.Product.query.get(1).stock
    response = client.post(
        '/admin/inventory/edit/1',
        data={'stock': 7, 'csrf_token': 'test-csrf-token'},
        follow_redirects=True
    )
    assert response.status_code == 200
    assert b'Dashboard' in response.data
    with sut_app_module.app.app_context():
        stock_after = sut_app_module.Product.query.get(1).stock
    assert stock_after == stock_before


@pytest.mark.e2e
def test_checkout_generates_receipt_text(client):
    # Agregar un producto al carrito de la sesion actual
    add_resp = client.post('/api/cart/add', json={'product_id': 1, 'qty': 1})
    assert add_resp.status_code == 200

    checkout_resp = client.post('/store/checkout', data={
        'name': 'QA User',
        'email': 'qa@example.com',
        'address': 'Calle Test 123',
        'payment_method': 'card'
    }, follow_redirects=True)

    assert checkout_resp.status_code == 200
    assert b'Comprobante:' in checkout_resp.data
