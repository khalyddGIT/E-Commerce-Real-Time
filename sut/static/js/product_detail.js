/**
 * product_detail.js - Detalle de producto con actualizacion en tiempo real.
 */

const socket = io();

socket.on('stock_update', (data) => {
    if (data.product_id !== PRODUCT_ID) return;

    const stock = data.stock;
    const outOfStock = data.out_of_stock;

    const stockCount = document.getElementById('stock-count');
    if (stockCount) stockCount.textContent = stock;

    const statusText = document.getElementById('stock-status-text');
    if (statusText) {
        statusText.innerHTML = outOfStock
            ? '<span class="status-outofstock">Agotado</span>'
            : '<span class="status-available">En stock</span>';
    }

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
            btn.textContent = 'Anadir al carrito';
            btn.disabled = false;
            btn.classList.remove('btn-out-of-stock');
            btn.classList.add('btn-available');
            if (qtyInput) {
                qtyInput.disabled = false;
                qtyInput.max = stock;
            }
        }
    }
});

function changeQty(delta) {
    const input = document.getElementById('qty-input');
    if (!input) return;

    let val = parseInt(input.value, 10) || 1;
    const max = parseInt(input.max, 10) || 9999;
    val = Math.max(1, Math.min(max, val + delta));
    input.value = val;
}

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
                btn.textContent = 'Agregado';
                setTimeout(() => {
                    btn.textContent = 'Anadir al carrito';
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
                btn.textContent = 'Anadir al carrito';
                btn.disabled = false;
            }
        })
        .catch(() => {
            btn.textContent = 'Anadir juanito';
            btn.disabled = false;
        });
}
