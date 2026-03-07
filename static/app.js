const API_BASE = '';

async function fetchCategories() {
  const res = await fetch(`${API_BASE}/api/categories/`);
  if (!res.ok) throw new Error('Failed to fetch categories');
  return res.json();
}

async function fetchMenuItems() {
  const res = await fetch(`${API_BASE}/api/menu-items/`);
  if (!res.ok) throw new Error('Failed to fetch menu items');
  return res.json();
}

function renderCategories(categories) {
  const el = document.getElementById('categories-list');
  if (!categories.length) {
    el.innerHTML = '<li class="text-slate-500">No categories yet.</li>';
    return;
  }
  el.innerHTML = categories
    .map((c) => `<li class="py-1">${escapeHtml(c.name)}</li>`)
    .join('');
}

function renderMenuItems(items) {
  const el = document.getElementById('menu-items-list');
  if (!items.length) {
    el.innerHTML = '<li class="text-slate-500">No menu items yet.</li>';
    return;
  }
  el.innerHTML = items
    .map(
      (m) =>
        `<li class="py-1">${escapeHtml(m.name)} — $${Number(m.price).toFixed(2)}</li>`
    )
    .join('');
}

function populateCategorySelect(categories) {
  const select = document.getElementById('item-category');
  const currentValue = select.value;
  select.innerHTML = '<option value="">Select category</option>';
  categories.forEach((c) => {
    const opt = document.createElement('option');
    opt.value = c.id;
    opt.textContent = c.name;
    select.appendChild(opt);
  });
  if (currentValue) select.value = currentValue;
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

async function loadAll() {
  try {
    const [categories, menuItems] = await Promise.all([
      fetchCategories(),
      fetchMenuItems(),
    ]);
    renderCategories(categories);
    renderMenuItems(menuItems);
    populateCategorySelect(categories);
  } catch (e) {
    console.error(e);
    document.getElementById('categories-list').innerHTML =
      '<li class="text-red-600">Error loading categories.</li>';
    document.getElementById('menu-items-list').innerHTML =
      '<li class="text-red-600">Error loading menu items.</li>';
  }
}

document.getElementById('form-category').addEventListener('submit', async (e) => {
  e.preventDefault();
  const input = document.getElementById('category-name');
  const name = input.value.trim();
  if (!name) return;
  try {
    const res = await fetch(`${API_BASE}/api/categories/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      alert(err.detail || 'Failed to create category');
      return;
    }
    input.value = '';
    await loadAll();
  } catch (err) {
    console.error(err);
    alert('Failed to create category');
  }
});

document.getElementById('form-menu-item').addEventListener('submit', async (e) => {
  e.preventDefault();
  const name = document.getElementById('item-name').value.trim();
  const price = parseFloat(document.getElementById('item-price').value);
  const categoryId = document.getElementById('item-category').value;
  if (!name || isNaN(price) || price < 0 || !categoryId) return;
  try {
    const res = await fetch(`${API_BASE}/api/menu-items/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, price, category_id: parseInt(categoryId, 10) }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      alert(err.detail || 'Failed to create menu item');
      return;
    }
    document.getElementById('item-name').value = '';
    document.getElementById('item-price').value = '';
    document.getElementById('item-category').value = '';
    await loadAll();
  } catch (err) {
    console.error(err);
    alert('Failed to create menu item');
  }
});

loadAll();
