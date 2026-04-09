/**
 * store.js — JavaScript del Storefront
 * Conecta via WebSocket y actualiza botones en tiempo real (Regla de Oro #1)
 */

// ─── Conexión WebSocket ─────────────────────────────────────────────────────
const socket = io();

socket.on('connect', () => {
    console.log('[WS] Conectado al servidor de tiempo real');
    const statusEl = document.getElementById('realtime-status');
    if (statusEl) {
        statusEl.textContent = '🟢 Tiempo Real Activo';
        statusEl.style.color = '#22c55e';
    }
});

socket.on('disconnect', () => {
    const statusEl = document.getElementById('realtime-status');
    if (statusEl) {
        statusEl.textContent = '🔴 Desconectado';
        statusEl.style.color = '#ef4444';
    }
});

// ─── REGLA DE ORO #1: Actualización Real-Time del Botón ────────────────────
// Cuando el Admin cambia el stock, este evento llega a TODOS los clientes
// conectados y el botón cambia SIN recargar la página
socket.on('stock_update', (data) => {
    const { product_id, stock, out_of_stock } = data;
    console.log(`[WS] stock_update: producto ${product_id}, stock=${stock}`);

    // Actualizar tarjeta de producto en el grid (si está visible)
    updateProductCardStock(product_id, stock, out_of_stock);
});

/**
 * Actualiza visualmente la tarjeta de un producto en el grid.
 * Implementa la Regla de Oro #1: stock 0 → botón "Sin Stock" + disabled.
 */
function updateProductCardStock(productId, stock, outOfStock) {
    // 1. Actualizar indicador de stock
    const indicator = document.getElementById(`stock-indicator-${productId}`);
    if (indicator) {
        indicator.textContent = outOfStock ? '❌ Sin stock' : `✅ ${stock} en stock`;
    }

    // 2. Actualizar botón "Añadir al carrito" — REGLA DE ORO #1
    const btn = document.getElementById(`btn-add-to-cart-${productId}`);
    if (btn) {
        if (outOfStock) {
            btn.textContent = 'Sin Stock';
            btn.disabled = true;
            btn.classList.remove('btn-available');
            btn.classList.add('btn-out-of-stock');
        } else {
            btn.textContent = 'Añadir al Carrito';
            btn.disabled = false;
            btn.classList.remove('btn-out-of-stock');
            btn.classList.add('btn-available');
        }
    }

    // 3. Actualizar data attribute
    const card = document.getElementById(`product-card-${productId}`);
    if (card) {
        card.dataset.stock = stock;
    }
}

// ─── AJAX: Agregar al Carrito ───────────────────────────────────────────────
function addToCart(productId) {
    productId = parseInt(productId, 10);  // dataset devuelve string, convertir a int
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
            btn.textContent = '✓ Agregado';
            setTimeout(() => {
                btn.textContent = 'Añadir al Carrito';
                btn.disabled = false;
            }, 1500);
        } else {
            showToast(data.message, 'error');
            btn.textContent = 'Añadir al Carrito';
            btn.disabled = false;
        }
    })
    .catch(() => {
        showToast('Error al agregar al carrito', 'error');
        btn.textContent = 'Añadir al Carrito';
        btn.disabled = false;
    });
}

// ─── Contador del carrito ───────────────────────────────────────────────────
function updateCartCount(count) {
    const countEl = document.getElementById('cart-count');
    if (countEl) countEl.textContent = count;
}

// Obtener count actual al cargar
fetch('/api/cart/count')
    .then(r => r.json())
    .then(data => updateCartCount(data.count))
    .catch(() => {});

// ─── Toast Helper ───────────────────────────────────────────────────────────
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
