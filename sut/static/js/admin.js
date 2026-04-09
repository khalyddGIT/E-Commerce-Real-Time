/**
 * admin.js - Panel de administracion
 * Incluye: actualizacion de stock, toasts, filtros rapidos y estados de carga.
 */

function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    if (!container) return;
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

function updateStock(productId, productName) {
    const input = document.getElementById(`stock-input-${productId}`);
    if (!input) return;
    const newStock = parseInt(input.value, 10);

    if (isNaN(newStock) || newStock < 0) {
        showToast('Stock invalido. Ingrese un numero >= 0.', 'error');
        return;
    }

    const btn = document.getElementById(`btn-save-stock-${productId}`);
    if (btn) {
        btn.disabled = true;
        btn.textContent = 'Guardando...';
    }

    fetch(`/admin/inventory/edit/${productId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-CSRF-Token': window.CSRF_TOKEN || ''
        },
        body: `stock=${newStock}`
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
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
            showToast(data.message, 'success');
        } else {
            showToast(data.message || `Error al actualizar ${productName}.`, 'error');
        }
    })
    .catch(() => showToast('Error de conexion al actualizar stock.', 'error'))
    .finally(() => {
        if (btn) {
            btn.disabled = false;
            btn.textContent = 'Guardar';
        }
    });
}

function initQuickTableFilter(inputId, rowSelector, counterId, emptyRowId) {
    const input = document.getElementById(inputId);
    if (!input) return;

    const rows = Array.from(document.querySelectorAll(rowSelector))
        .filter(row => row.id !== emptyRowId);
    const counter = document.getElementById(counterId);
    const emptyRow = document.getElementById(emptyRowId);

    const applyFilter = () => {
        const query = input.value.trim().toLowerCase();
        let visible = 0;

        rows.forEach(row => {
            const text = row.innerText.toLowerCase();
            const show = !query || text.includes(query);
            row.style.display = show ? '' : 'none';
            if (show) visible += 1;
        });

        if (counter) counter.textContent = `${visible}/${rows.length} visibles`;

        if (emptyRow) {
            emptyRow.style.display = (visible === 0) ? '' : 'none';
            const cell = emptyRow.querySelector('td');
            if (cell && query && visible === 0) {
                cell.textContent = 'Sin resultados para la busqueda actual.';
            }
        }
    };

    input.addEventListener('input', applyFilter);
    applyFilter();
}

function bindStatusFormsLoadingState() {
    document.querySelectorAll('.order-status-form').forEach(form => {
        form.addEventListener('submit', () => {
            const btn = form.querySelector('button[type="submit"]');
            if (btn) {
                btn.disabled = true;
                btn.textContent = 'Actualizando...';
            }
        });
    });
}

function initSidebarToggle() {
    const sidebar = document.getElementById('admin-sidebar');
    const toggleBtn = document.getElementById('sidebar-toggle');
    const overlay = document.getElementById('sidebar-overlay');

    if (!sidebar || !toggleBtn || !overlay) return;

    const closeSidebar = () => {
        sidebar.classList.remove('is-open');
        overlay.classList.remove('is-open');
        document.body.classList.remove('no-scroll');
        toggleBtn.setAttribute('aria-expanded', 'false');
    };

    const openSidebar = () => {
        sidebar.classList.add('is-open');
        overlay.classList.add('is-open');
        document.body.classList.add('no-scroll');
        toggleBtn.setAttribute('aria-expanded', 'true');
    };

    toggleBtn.addEventListener('click', () => {
        if (sidebar.classList.contains('is-open')) {
            closeSidebar();
        } else {
            openSidebar();
        }
    });

    overlay.addEventListener('click', closeSidebar);
    document.querySelectorAll('.sidebar .nav-item').forEach(link => {
        link.addEventListener('click', closeSidebar);
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') closeSidebar();
    });
}

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.toast-notification').forEach(el => {
        setTimeout(() => {
            el.style.opacity = '0';
            el.style.transition = 'opacity 0.5s';
            setTimeout(() => el.remove(), 500);
        }, 4000);
    });

    initQuickTableFilter('inventory-quick-search', '#inventory-tbody tr', 'inventory-search-count', 'empty-row');
    initQuickTableFilter('sales-quick-search', '#sales-tbody tr', 'sales-search-count', 'empty-sales-row');
    bindStatusFormsLoadingState();
    initSidebarToggle();
});
