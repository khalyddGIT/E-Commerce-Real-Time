/**
 * store.js - JavaScript del storefront
 * Actualiza stock en tiempo real y maneja carrito via API.
 */

const socket = io();

socket.on('connect', () => {
    const statusEl = document.getElementById('realtime-status');
    if (statusEl) {
        statusEl.textContent = 'Conectado';
        statusEl.style.color = '#22c55e';
    }
});

socket.on('disconnect', () => {
    const statusEl = document.getElementById('realtime-status');
    if (statusEl) {
        statusEl.textContent = 'Desconectado';
        statusEl.style.color = '#ef4444';
    }
});

socket.on('stock_update', (data) => {
    const { product_id, stock, out_of_stock } = data;
    updateProductCardStock(product_id, stock, out_of_stock);
});

function updateProductCardStock(productId, stock, outOfStock) {
    const indicator = document.getElementById(`stock-indicator-${productId}`);
    if (indicator) {
        indicator.textContent = outOfStock ? 'Sin stock' : `Disponible: ${stock}`;
    }

    const btn = document.getElementById(`btn-add-to-cart-${productId}`);
    if (btn) {
        if (outOfStock) {
            btn.textContent = 'Sin Stock';
            btn.disabled = true;
            btn.classList.remove('btn-available');
            btn.classList.add('btn-out-of-stock');
        } else {
            btn.textContent = 'Añadir al carrito';
            btn.disabled = false;
            btn.classList.remove('btn-out-of-stock');
            btn.classList.add('btn-available');
        }
    }

    const card = document.getElementById(`product-card-${productId}`);
    if (card) {
        card.dataset.stock = stock;
    }
}

function addToCart(productId) {
    productId = parseInt(productId, 10);
    const btn = document.getElementById(`btn-add-to-cart-${productId}`);
    if (!btn || btn.disabled) return;

    btn.textContent = 'Agregando...';
    btn.disabled = true;

    fetch('/api/cart/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ product_id: productId, qty: 1 })
    })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                showToast(data.message, 'success');
                updateCartCount(data.cart_count);
                btn.textContent = 'Agregado';
                setTimeout(() => {
                    btn.textContent = 'Añadir al carrito';
                    btn.disabled = false;
                }, 1500);
            } else {
                showToast(data.message, 'error');
                btn.textContent = 'Añadir al carrito';
                btn.disabled = false;
            }
        })
        .catch(() => {
            showToast('Error al agregar al carrito', 'error');
            btn.textContent = 'Añadir al carrito';
            btn.disabled = false;
        });
}

function updateCartCount(count) {
    const countEl = document.getElementById('cart-count');
    if (countEl) countEl.textContent = count;
}

fetch('/api/cart/count')
    .then(r => r.json())
    .then(data => updateCartCount(data.count))
    .catch(() => {});

function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.id = `toast-${Date.now()}`;
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}
