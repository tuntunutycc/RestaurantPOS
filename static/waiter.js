const API_BASE = '';

let menuItems = [];
const cart = new Map(); // menu_item_id -> { menu_item, quantity }

async function fetchMenuItems() {
  const res = await fetch(`${API_BASE}/api/menu-items/`);
  if (!res.ok) throw new Error('Failed to fetch menu items');
  return res.json();
}

function renderMenu() {
  const grid = document.getElementById('menu-grid');
  if (!menuItems.length) {
    grid.innerHTML = '<p class="col-span-full text-slate-500">No menu items. Add some from the main menu first.</p>';
    return;
  }
  grid.innerHTML = menuItems
    .map(
      (m) => `
      <button
        type="button"
        data-id="${m.id}"
        data-name="${escapeAttr(m.name)}"
        data-price="${m.price}"
        class="menu-item-btn text-left p-3 bg-white rounded-lg shadow hover:bg-blue-50 border border-slate-200"
      >
        <span class="font-medium text-slate-800 block">${escapeHtml(m.name)}</span>
        <span class="text-sm text-slate-600">$${Number(m.price).toFixed(2)}</span>
      </button>
    `
    )
    .join('');

  grid.querySelectorAll('.menu-item-btn').forEach((btn) => {
    btn.addEventListener('click', () => addToCart(Number(btn.dataset.id), btn.dataset.name, parseFloat(btn.dataset.price)));
  });
}

function addToCart(id, name, price) {
  const current = cart.get(id);
  if (current) {
    current.quantity += 1;
  } else {
    cart.set(id, { menu_item: { id, name, price }, quantity: 1 });
  }
  renderCart();
}

function updateCartQuantity(id, delta) {
  const item = cart.get(id);
  if (!item) return;
  item.quantity += delta;
  if (item.quantity <= 0) cart.delete(id);
  renderCart();
}

function renderCart() {
  const list = document.getElementById('cart-list');
  const totalEl = document.getElementById('cart-total');
  const submitBtn = document.getElementById('submit-order');

  if (cart.size === 0) {
    list.innerHTML = '<li class="text-slate-500">Cart is empty</li>';
    totalEl.textContent = '$0.00';
    submitBtn.disabled = true;
    return;
  }

  let total = 0;
  list.innerHTML = '';
  cart.forEach(({ menu_item, quantity }, id) => {
    const subtotal = menu_item.price * quantity;
    total += subtotal;
    const li = document.createElement('li');
    li.className = 'flex items-center justify-between gap-2';
    li.innerHTML = `
      <span class="flex-1 truncate">${escapeHtml(menu_item.name)} × ${quantity}</span>
      <span class="font-medium">$${subtotal.toFixed(2)}</span>
      <div class="flex items-center gap-0">
        <button type="button" data-id="${id}" class="qty-btn minus w-7 h-7 rounded border border-slate-300 bg-slate-100 hover:bg-slate-200">−</button>
        <span class="w-6 text-center text-sm">${quantity}</span>
        <button type="button" data-id="${id}" class="qty-btn plus w-7 h-7 rounded border border-slate-300 bg-slate-100 hover:bg-slate-200">+</button>
      </div>
    `;
    list.appendChild(li);
  });

  list.querySelectorAll('.qty-btn.minus').forEach((btn) => {
    btn.addEventListener('click', () => updateCartQuantity(Number(btn.dataset.id), -1));
  });
  list.querySelectorAll('.qty-btn.plus').forEach((btn) => {
    btn.addEventListener('click', () => updateCartQuantity(Number(btn.dataset.id), 1));
  });

  totalEl.textContent = `$${total.toFixed(2)}`;
  submitBtn.disabled = false;
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function escapeAttr(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML.replace(/"/g, '&quot;');
}

document.getElementById('submit-order').addEventListener('click', async () => {
  const tableInput = document.getElementById('table-number');
  const tableNumber = parseInt(tableInput.value, 10);
  if (!tableNumber || tableNumber < 1) {
    alert('Please enter a valid table number.');
    return;
  }
  if (cart.size === 0) {
    alert('Cart is empty.');
    return;
  }

  const items = [];
  cart.forEach(({ menu_item, quantity }) => {
    items.push({ menu_item_id: menu_item.id, quantity });
  });

  try {
    const res = await fetch(`${API_BASE}/api/orders/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ table_number: tableNumber, items }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      alert(data.detail || 'Failed to submit order');
      return;
    }
    cart.clear();
    renderCart();
    tableInput.value = '';
    alert(`Order #${data.id} submitted for table ${data.table_number}. Total: $${Number(data.total_amount).toFixed(2)}`);
  } catch (err) {
    console.error(err);
    alert('Failed to submit order');
  }
});

(async function init() {
  try {
    menuItems = await fetchMenuItems();
    renderMenu();
  } catch (e) {
    console.error(e);
    document.getElementById('menu-grid').innerHTML =
      '<p class="col-span-full text-red-600">Error loading menu.</p>';
  }
})();
