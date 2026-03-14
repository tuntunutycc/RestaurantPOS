const API_BASE = '';

(function guard() {
  if (!window.auth) return;
  if (!window.auth.requireAuth()) return;
  if (!window.auth.requireRole(['admin'])) return;
  window.auth.renderNav('pos-nav');
  window.auth.consumeUnauthorizedFlag();
})();

async function fetchCategories() {
  const res = await fetch(`${API_BASE}/api/categories/`, {
    headers: { ...window.auth.getAuthHeaders() },
  });
  if (window.auth && window.auth.checkUnauthorized(res)) return [];
  if (!res.ok) throw new Error('Failed to fetch categories');
  return res.json();
}

async function fetchMenuItems() {
  const res = await fetch(`${API_BASE}/api/menu-items/`, {
    headers: { ...window.auth.getAuthHeaders() },
  });
  if (window.auth && window.auth.checkUnauthorized(res)) return [];
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
    .map((m) => {
      const img = m.image_url
        ? `<img src="${escapeAttr(m.image_url)}" alt="" class="w-10 h-10 object-cover rounded inline-block mr-2 align-middle" />`
        : '';
      return `<li class="py-2 flex items-center gap-2">${img}<span>${escapeHtml(m.name)} — $${Number(m.price).toFixed(2)}</span></li>`;
    })
    .join('');
}

function escapeAttr(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML.replace(/"/g, '&quot;');
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
      headers: { 'Content-Type': 'application/json', ...window.auth.getAuthHeaders() },
      body: JSON.stringify({ name }),
    });
    if (window.auth && window.auth.checkUnauthorized(res)) return;
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

document.getElementById('item-image-file').addEventListener('change', async (e) => {
  const file = e.target.files?.[0];
  if (!file) return;
  const fd = new FormData();
  fd.append('file', file);
  try {
    const res = await fetch(`${API_BASE}/api/upload`, {
      method: 'POST',
      headers: { ...window.auth.getAuthHeaders() },
      body: fd,
    });
    if (window.auth && window.auth.checkUnauthorized(res)) return;
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      alert(data.detail || 'Upload failed');
      return;
    }
    document.getElementById('item-image-url').value = data.url || '';
  } catch (err) {
    console.error(err);
    alert('Upload failed');
  }
  e.target.value = '';
});

document.getElementById('form-menu-item').addEventListener('submit', async (e) => {
  e.preventDefault();
  const name = document.getElementById('item-name').value.trim();
  const price = parseFloat(document.getElementById('item-price').value);
  const description = document.getElementById('item-description').value.trim() || null;
  const categoryId = document.getElementById('item-category').value;
  const imageUrl = document.getElementById('item-image-url').value.trim() || null;
  const imageFile = document.getElementById('item-image-file').files?.[0];
  if (!name || isNaN(price) || price < 0 || !categoryId) return;
  try {
    let res;
    if (imageFile) {
      const fd = new FormData();
      fd.append('name', name);
      fd.append('price', String(price));
      fd.append('category_id', categoryId);
      if (description) fd.append('description', description);
      fd.append('image', imageFile);
      res = await fetch(`${API_BASE}/api/menu-items/upload`, {
        method: 'POST',
        headers: { ...window.auth.getAuthHeaders() },
        body: fd,
      });
    } else {
      res = await fetch(`${API_BASE}/api/menu-items/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...window.auth.getAuthHeaders() },
        body: JSON.stringify({ name, price, category_id: parseInt(categoryId, 10), description: description, image_url: imageUrl }),
      });
    }
    if (window.auth && window.auth.checkUnauthorized(res)) return;
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      alert(Array.isArray(data.detail) ? data.detail.map((x) => x.msg || x).join(', ') : (data.detail || 'Failed to create menu item'));
      return;
    }
    document.getElementById('item-name').value = '';
    document.getElementById('item-price').value = '';
    document.getElementById('item-description').value = '';
    document.getElementById('item-category').value = '';
    document.getElementById('item-image-url').value = '';
    document.getElementById('item-image-file').value = '';
    await loadAll();
  } catch (err) {
    console.error(err);
    alert('Failed to create menu item');
  }
});

if (window.auth && window.auth.getToken()) {
  loadAll();
}
