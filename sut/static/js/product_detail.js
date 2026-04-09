/**
 * product_detail.js — JavaScript de la página de detalle de producto
 * Maneja WebSocket para actualización en tiempo real del stock y botón Sin Stock
 */

const socket = io();

socket.on('stock_update', (data) => {
    if (data.product_id !== PRODUCT_ID) return;

    const stock = data.stock;
    const outOfStock = data.out_of_stock;

    // Actualizar contador de stock
    const stockCount = document.getElementById('stock-count');
    if (stockCount) stockCount.textContent = stock;

    // Actualizar texto de estado
    const statusText = document.getElementById('stock-status-text');
    if (statusText) {
        statusText.innerHTML = outOfStock
            ? '<span class="status-outofstock">❌ Agotado</span>'
            : '<span class="status-available">✅ En Stock</span>';
    }

    // REGLA DE ORO #1 — Cambiar botón
    const btn = document.getElementById('btn-add-to-cart');
    const qtyInput = document.getElementById('qty-input');
    if (btn) {
        if (outOfStock) {
            btn.textContent = 'Sin Stock';
            btn.disabled = true;
            btn.classList.remove('btn-available');
            btn.classList.add('btn-out-of-stock');
            if (qtyInput) qtyInput.disabled = true;
        } else {
            btn.textContent = 'Añadir al Carrito';
            btn.disabled = false;
            btn.classList.remove('btn-out-of-stock');
            btn.classList.add('btn-available');
            if (qtyInput) {
                qtyInput.disabled = false;
                qtyInput.max = stock;
            }
        }
    }

    console.log(`[RT] Producto ${PRODUCT_SKU}: stock actualizado a ${stock}`);
});

// ─── Controles de cantidad ──────────────────────────────────────────────────
function changeQty(delta) {
    const input = document.getElementById('qty-input');
    if (!input) return;
    let val = parseInt(input.value, 10) || 1;
    val = Math.max(1, val + delta);
    input.value = val;
}

// ─── Agregar al carrito desde detalle ──────────────────────────────────────
function addToCartDetail() {
    const btn = document.getElementById('btn-add-to-cart');
    const qtyInput = document.getElementById('qty-input');
    const qty = parseInt(qtyInput ? qtyInput.value : 1, 10);

    if (!btn || btn.disabled) return;

    btn.disabled = true;
    btn.textContent = 'Agregando...';

    fetch('/api/cart/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ product_id: PRODUCT_ID, qty })
    })
    .then(r => r.json())
    .then(data => {
        const feedback = document.getElementById('cart-feedback');
        if (data.success) {
            if (feedback) {
                feedback.style.display = 'block';
                feedback.style.background = '#dcfce7';
                feedback.style.color = '#15803d';
                feedback.textContent = data.message;
            }
            const cartCount = document.getElementById('cart-count');
            if (cartCount) cartCount.textContent = data.cart_count;
            btn.textContent = '✓ ¡Agregado!';
            setTimeout(() => {
                btn.textContent = 'Añadir al Carrito';
                btn.disabled = false;
                if (feedback) feedback.style.display = 'none';
            }, 2000);
        } else {
            if (feedback) {
                feedback.style.display = 'block';
                feedback.style.background = '#fee2e2';
                feedback.style.color = '#b91c1c';
                feedback.textContent = data.message;
            }
            btn.textContent = 'Añadir al Carrito';
            btn.disabled = false;
        }
    })
    .catch(() => {
        btn.textContent = 'Añadir al Carrito';
        btn.disabled = false;
    });
}
