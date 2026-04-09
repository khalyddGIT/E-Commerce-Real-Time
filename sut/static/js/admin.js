/**
 * admin.js — JavaScript del Panel de Administración
 * Maneja: actualización de stock via AJAX + Toast notifications (CP02)
 */

// ─── Toast Helper ──────────────────────────────────────────────────────────
function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.id = `toast-msg-${Date.now()}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s';
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}

// ─── Actualizar Stock (CP02) ───────────────────────────────────────────────
// Llama a la API AJAX del admin para actualizar el stock sin recargar la página
function updateStock(productId, productName) {
    const input = document.getElementById(`stock-input-${productId}`);
    const newStock = parseInt(input.value, 10);

    if (isNaN(newStock) || newStock < 0) {
        showToast('Stock inválido. Ingrese un número >= 0.', 'error');
        return;
    }

    const btn = document.getElementById(`btn-save-stock-${productId}`);
    btn.disabled = true;
    btn.textContent = 'Guardando...';

    fetch(`/admin/inventory/edit/${productId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: `stock=${newStock}`
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            // Actualizar badge de stock
            const badge = document.getElementById(`stock-badge-${productId}`);
            if (badge) {
                badge.className = 'stock-badge';
                if (newStock === 0) {
                    badge.classList.add('badge-danger');
                    badge.textContent = 'Sin Stock';
                } else if (newStock < 5) {
                    badge.classList.add('badge-warning');
                    badge.textContent = 'Stock Bajo';
                } else {
                    badge.classList.add('badge-success');
                    badge.textContent = 'Disponible';
                }
            }
            // Toast de confirmación — OBLIGATORIO para CP02
            showToast(data.message, 'success');
        } else {
            showToast(data.message || 'Error al actualizar stock.', 'error');
        }
    })
    .catch(() => showToast('Error de conexión al actualizar stock.', 'error'))
    .finally(() => {
        btn.disabled = false;
        btn.textContent = 'Guardar';
    });
}

// ─── Auto-hide flash messages ──────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    // Ocultar los mensajes flash de Flask después de 4 segundos
    document.querySelectorAll('.toast-notification').forEach(el => {
        setTimeout(() => {
            el.style.opacity = '0';
            el.style.transition = 'opacity 0.5s';
            setTimeout(() => el.remove(), 500);
        }, 4000);
    });
});
