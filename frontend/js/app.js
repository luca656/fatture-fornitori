/* Fatture Fornitori – frontend app */
const API = '';  // same origin

// ── Utilities ────────────────────────────────────────────────────────────────

function fmt(n, decimals = 2) {
  if (n == null) return '—';
  return new Intl.NumberFormat('it-IT', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(n) + ' €';
}

function fmtQty(n, unit) {
  if (n == null) return '—';
  return new Intl.NumberFormat('it-IT', { maximumFractionDigits: 3 }).format(n) + (unit ? ' ' + unit : '');
}

function fmtDate(s) {
  if (!s) return '—';
  try {
    return new Date(s).toLocaleDateString('it-IT', { day: '2-digit', month: '2-digit', year: 'numeric' });
  } catch {
    return s;
  }
}

async function api(path, opts = {}) {
  const res = await fetch(API + path, opts);
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(text || res.statusText);
  }
  return res.json();
}

function show(id) { document.getElementById(id)?.classList.remove('hidden'); }
function hide(id) { document.getElementById(id)?.classList.add('hidden'); }
function setText(id, t) { const el = document.getElementById(id); if (el) el.textContent = t; }

// ── Tabs ─────────────────────────────────────────────────────────────────────

function switchTab(name) {
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(el => el.classList.remove('active'));
  document.getElementById('tab-' + name)?.classList.add('active');
  document.querySelector(`[data-tab="${name}"]`)?.classList.add('active');

  if (name === 'comparison') loadComparison();
  if (name === 'invoices') loadInvoices();
  if (name === 'suppliers') loadSuppliers();
}

document.querySelectorAll('.nav-btn').forEach(btn => {
  btn.addEventListener('click', () => switchTab(btn.dataset.tab));
});

// ── Comparison ───────────────────────────────────────────────────────────────

let allComparisons = [];
let allSupplierNames = [];

async function loadComparison() {
  show('comparison-loading');
  document.getElementById('comparison-content').innerHTML = '';
  try {
    const [data, categories] = await Promise.all([
      api('/api/products/comparison'),
      api('/api/products/categories'),
    ]);
    allComparisons = data;

    // Collect all unique supplier names preserving order of appearance
    const names = new Set();
    data.forEach(row => row.prices.forEach(p => names.add(p.supplier_name)));
    allSupplierNames = [...names];

    // Populate category filter
    const catSelect = document.getElementById('category-filter');
    const currentCat = catSelect.value;
    catSelect.innerHTML = '<option value="">Tutte le categorie</option>';
    categories.forEach(c => {
      const opt = document.createElement('option');
      opt.value = c;
      opt.textContent = c;
      if (c === currentCat) opt.selected = true;
      catSelect.appendChild(opt);
    });

    renderComparison();
  } catch (e) {
    document.getElementById('comparison-content').innerHTML =
      `<div class="no-data"><p>Errore nel caricamento: ${e.message}</p></div>`;
  } finally {
    hide('comparison-loading');
  }
}

function renderComparison() {
  const search = document.getElementById('product-search').value.toLowerCase();
  const cat = document.getElementById('category-filter').value;

  let rows = allComparisons.filter(row => {
    if (cat && row.product.category !== cat) return false;
    if (search && !row.product.name.toLowerCase().includes(search)) return false;
    return true;
  });

  const container = document.getElementById('comparison-content');

  if (!rows.length) {
    container.innerHTML = `
      <div class="no-data">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
        </svg>
        <h3>${allComparisons.length ? 'Nessun risultato' : 'Nessuna fattura caricata'}</h3>
        <p>${allComparisons.length ? 'Prova a cambiare i filtri.' : 'Carica una fattura per iniziare il confronto.'}</p>
      </div>`;
    return;
  }

  // Gather all supplier names across filtered rows
  const supplierNames = [];
  const seen = new Set();
  rows.forEach(row => row.prices.forEach(p => {
    if (!seen.has(p.supplier_name)) { seen.add(p.supplier_name); supplierNames.push(p.supplier_name); }
  }));

  let html = `
    <div class="comparison-table-container">
    <table class="comparison-table">
      <thead>
        <tr>
          <th>Prodotto</th>
          <th>Categoria</th>
          ${supplierNames.map(n => `<th class="text-right">${escHtml(n)}</th>`).join('')}
          <th class="text-right">Risparmio %</th>
          <th></th>
        </tr>
      </thead>
      <tbody>`;

  rows.forEach(row => {
    const priceMap = {};
    row.prices.forEach(p => {
      // If same supplier appears multiple times, keep the most recent (first in sorted-by-date list)
      if (!(p.supplier_name in priceMap)) priceMap[p.supplier_name] = p;
    });

    const pricesWithValue = Object.values(priceMap);
    const savingPct = (row.best_price != null && row.worst_price != null && row.worst_price > 0)
      ? Math.round((1 - row.best_price / row.worst_price) * 100)
      : null;

    html += `<tr>
      <td class="product-name">
        ${escHtml(row.product.name)}
        ${row.product.unit ? `<small>${escHtml(row.product.unit)}</small>` : ''}
      </td>
      <td>${row.product.category ? `<span class="category-badge">${escHtml(row.product.category)}</span>` : '<span style="color:var(--gray-400)">—</span>'}</td>`;

    supplierNames.forEach(sname => {
      const p = priceMap[sname];
      if (!p) {
        html += `<td class="price-cell" style="color:var(--gray-300)">—</td>`;
      } else {
        const isBest = pricesWithValue.length > 1 && p.unit_price === row.best_price;
        const isWorst = pricesWithValue.length > 1 && p.unit_price === row.worst_price;
        const cls = isBest ? 'price-best' : (isWorst ? 'price-worst' : '');
        const badge = isBest
          ? `<span class="price-badge badge-best">↓ migliore</span>`
          : (isWorst ? `<span class="price-badge badge-worst">↑ più caro</span>` : '');
        html += `<td class="price-cell ${cls}">
          ${fmt(p.unit_price)} ${badge}
          <div style="font-size:.75rem;color:var(--gray-400);margin-top:1px">${fmtDate(p.invoice_date)}</div>
        </td>`;
      }
    });

    html += `<td class="price-cell">${savingPct != null && savingPct > 0 ? `<span class="saving-pill">-${savingPct}%</span>` : '—'}</td>`;
    html += `<td>
      <button class="merge-btn" onclick="openMergeModal(${row.product.id}, '${escHtml(row.product.name).replace(/'/g, "\\'")}')">
        Unisci
      </button>
    </td>`;
    html += `</tr>`;
  });

  html += `</tbody></table></div>`;
  container.innerHTML = html;
}

document.getElementById('product-search').addEventListener('input', renderComparison);
document.getElementById('category-filter').addEventListener('change', renderComparison);

// ── Invoices ─────────────────────────────────────────────────────────────────

async function loadInvoices() {
  show('invoices-loading');
  document.getElementById('invoices-list').innerHTML = '';
  try {
    const invoices = await api('/api/invoices/');
    hide('invoices-loading');
    if (!invoices.length) {
      document.getElementById('invoices-list').innerHTML =
        '<div class="no-data"><h3>Nessuna fattura</h3><p>Carica la prima fattura dalla scheda "Carica Fattura".</p></div>';
      return;
    }
    document.getElementById('invoices-list').innerHTML =
      `<div class="invoice-grid">${invoices.map(renderInvoiceCard).join('')}</div>`;
  } catch (e) {
    hide('invoices-loading');
    document.getElementById('invoices-list').innerHTML =
      `<div class="no-data"><p>Errore: ${e.message}</p></div>`;
  }
}

function renderInvoiceCard(inv) {
  const itemsHtml = inv.items.length
    ? `<button class="items-toggle" onclick="toggleItems(${inv.id})">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="6 9 12 15 18 9"/></svg>
        ${inv.items.length} articoli
      </button>
      <div class="invoice-items-list" id="items-${inv.id}">
        <table class="items-mini-table">
          <thead><tr>
            <th>Descrizione</th><th>Qtà</th><th>Prezzo unit.</th><th>Totale</th>
          </tr></thead>
          <tbody>
            ${inv.items.map(it => `<tr>
              <td>${escHtml(it.raw_description)}</td>
              <td>${fmtQty(it.quantity, it.unit)}</td>
              <td class="text-right">${fmt(it.unit_price)}</td>
              <td class="text-right">${fmt(it.total_price)}</td>
            </tr>`).join('')}
          </tbody>
        </table>
      </div>`
    : '<span style="font-size:.82rem;color:var(--gray-400)">Nessun articolo estratto</span>';

  return `
    <div class="invoice-card" id="inv-card-${inv.id}">
      <div>
        <div class="invoice-card-header">
          <div class="invoice-icon">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
            </svg>
          </div>
          <div class="invoice-meta">
            <h3>${escHtml(inv.file_name)}</h3>
            <p>${escHtml(inv.supplier.name)}</p>
          </div>
        </div>
        <div class="invoice-details">
          ${inv.invoice_number ? `<span class="detail-chip">N° ${escHtml(inv.invoice_number)}</span>` : ''}
          ${inv.invoice_date ? `<span class="detail-chip">${fmtDate(inv.invoice_date)}</span>` : ''}
          ${inv.total_amount != null ? `<span class="detail-chip" style="font-weight:600">${fmt(inv.total_amount)}</span>` : ''}
        </div>
        ${itemsHtml}
      </div>
      <div class="invoice-actions">
        <button class="btn btn-sm btn-danger" onclick="deleteInvoice(${inv.id})">Elimina</button>
      </div>
    </div>`;
}

function toggleItems(id) {
  const el = document.getElementById('items-' + id);
  el?.classList.toggle('open');
}

async function deleteInvoice(id) {
  if (!confirm('Eliminare questa fattura? Tutti i prezzi associati saranno rimossi.')) return;
  try {
    await api('/api/invoices/' + id, { method: 'DELETE' });
    document.getElementById('inv-card-' + id)?.remove();
    loadComparison();
  } catch (e) {
    alert('Errore: ' + e.message);
  }
}

// ── Suppliers ────────────────────────────────────────────────────────────────

async function loadSuppliers() {
  show('suppliers-loading');
  document.getElementById('suppliers-list').innerHTML = '';
  try {
    const suppliers = await api('/api/suppliers/');
    hide('suppliers-loading');
    if (!suppliers.length) {
      document.getElementById('suppliers-list').innerHTML =
        '<div class="no-data"><h3>Nessun fornitore</h3><p>I fornitori vengono aggiunti automaticamente al caricamento delle fatture.</p></div>';
      return;
    }
    document.getElementById('suppliers-list').innerHTML =
      `<div class="supplier-grid">${suppliers.map(renderSupplierCard).join('')}</div>`;
  } catch (e) {
    hide('suppliers-loading');
    document.getElementById('suppliers-list').innerHTML =
      `<div class="no-data"><p>Errore: ${e.message}</p></div>`;
  }
}

function renderSupplierCard(s) {
  return `
    <div class="supplier-card">
      <h3>${escHtml(s.name)}</h3>
      ${s.vat_number ? `<p><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg> P.IVA ${escHtml(s.vat_number)}</p>` : ''}
      ${s.address ? `<p><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg> ${escHtml(s.address)}</p>` : ''}
      ${s.email ? `<p><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg> ${escHtml(s.email)}</p>` : ''}
      ${s.phone ? `<p><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.69 13a19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 3.6 2.18h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L7.91 9.91a16 16 0 0 0 6 6l.92-.92a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 21.73 17z"/></svg> ${escHtml(s.phone)}</p>` : ''}
    </div>`;
}

// ── Upload ───────────────────────────────────────────────────────────────────

const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const uploadBtn = document.getElementById('upload-btn');
let selectedFile = null;

dropZone.addEventListener('click', () => fileInput.click());
dropZone.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') fileInput.click(); });

dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file) setFile(file);
});

fileInput.addEventListener('change', () => {
  if (fileInput.files[0]) setFile(fileInput.files[0]);
});

function setFile(file) {
  selectedFile = file;
  const el = document.getElementById('selected-file');
  el.textContent = `📄 ${file.name} (${(file.size / 1024).toFixed(0)} KB)`;
  el.classList.remove('hidden');
  uploadBtn.disabled = false;
  hide('upload-status');
  hide('upload-result');
}

uploadBtn.addEventListener('click', async () => {
  if (!selectedFile) return;

  uploadBtn.disabled = true;
  const status = document.getElementById('upload-status');
  status.className = 'upload-status info';
  status.innerHTML = '<div class="spinner"></div> Analisi AI in corso — potrebbe richiedere qualche secondo...';
  show('upload-status');
  hide('upload-result');

  try {
    const formData = new FormData();
    formData.append('file', selectedFile);
    const invoice = await api('/api/invoices/upload', { method: 'POST', body: formData });

    status.className = 'upload-status success';
    status.innerHTML = `✓ Fattura caricata con successo — ${invoice.items.length} articoli estratti da ${escHtml(invoice.supplier.name)}`;

    renderUploadResult(invoice);
    show('upload-result');

    // Reset
    selectedFile = null;
    fileInput.value = '';
    document.getElementById('selected-file').classList.add('hidden');
  } catch (e) {
    let msg = e.message;
    try { msg = JSON.parse(msg)?.detail || msg; } catch {}
    status.className = 'upload-status error';
    status.innerHTML = `✗ Errore: ${escHtml(msg)}`;
  } finally {
    uploadBtn.disabled = false;
  }
});

function renderUploadResult(invoice) {
  const el = document.getElementById('upload-result');
  el.innerHTML = `
    <h3>Fattura di ${escHtml(invoice.supplier.name)}</h3>
    <div class="result-items">
      ${invoice.items.map(it => `
        <div class="result-item">
          <span class="result-item-desc">${escHtml(it.raw_description)}</span>
          <span class="result-item-qty">${fmtQty(it.quantity, it.unit)}</span>
          <span class="result-item-price">${fmt(it.unit_price)}</span>
        </div>`).join('')}
    </div>`;
}

// ── Merge Modal ───────────────────────────────────────────────────────────────

let mergeSourceId = null;

async function openMergeModal(productId, productName) {
  mergeSourceId = productId;
  document.getElementById('modal-title').textContent = `Unisci "${productName}"`;

  try {
    const products = await api('/api/products/');
    const others = products.filter(p => p.id !== productId);

    document.getElementById('modal-body').innerHTML = `
      <p style="margin-bottom:12px">Seleziona il prodotto principale in cui unire <strong>${escHtml(productName)}</strong>:</p>
      <select id="merge-target" style="width:100%;padding:9px 12px;border:1px solid var(--gray-300);border-radius:var(--radius);font-size:.9rem">
        <option value="">— Seleziona prodotto —</option>
        ${others.map(p => `<option value="${p.id}">${escHtml(p.name)}</option>`).join('')}
      </select>
      <p style="margin-top:12px;font-size:.82rem;color:var(--gray-500)">
        Tutti gli articoli del prodotto selezionato verranno trasferiti nel prodotto principale.
      </p>`;

    show('modal-overlay');
  } catch (e) {
    alert('Errore: ' + e.message);
  }
}

document.getElementById('modal-confirm').addEventListener('click', async () => {
  const targetId = document.getElementById('merge-target')?.value;
  if (!targetId) { alert('Seleziona un prodotto di destinazione.'); return; }

  try {
    await api(`/api/products/${targetId}/merge/${mergeSourceId}`, { method: 'POST' });
    hide('modal-overlay');
    await loadComparison();
  } catch (e) {
    alert('Errore: ' + e.message);
  }
});

document.getElementById('modal-cancel').addEventListener('click', () => hide('modal-overlay'));
document.getElementById('modal-close').addEventListener('click', () => hide('modal-overlay'));
document.getElementById('modal-overlay').addEventListener('click', e => {
  if (e.target === document.getElementById('modal-overlay')) hide('modal-overlay');
});

// ── XSS-safe escape ──────────────────────────────────────────────────────────

function escHtml(str) {
  if (str == null) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// ── Boot ─────────────────────────────────────────────────────────────────────

loadComparison();
