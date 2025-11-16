// content.js
// Listen for the popup message
window.addEventListener('message', async (event) => {
  if (!event.data) return;
  if (event.data.type !== 'PREQIN_ENRICH_REQUEST') return;
  runEnrichment();
});

async function runEnrichment() {
  // === 1) Read fields from the page ===
  // Update these selectors to the actual Preqin form field selectors.
  // For example:
  const hqAddress = document.querySelector('#hq-address')?.value || '';
  const hqCity = document.querySelector('#hq-city')?.value || '';
  const hqState = document.querySelector('#hq-state')?.value || '';
  const hqPostal = document.querySelector('#hq-postal')?.value || '';
  const hqCountry = document.querySelector('#hq-country')?.value || '';

  const phone = document.querySelector('#phone')?.value || '';

  const payload = {
    firm_id: document.querySelector('#firm-id')?.value || null,
    hq: {
      address_line: hqAddress,
      city: hqCity,
      state: hqState,
      postal_code: hqPostal,
      country: hqCountry
    },
    phone: phone,
    alt_offices: []
  };

  // === 2) Call local backend ===
  let result;
  try {
    const res = await fetch('http://127.0.0.1:8000/enrich', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload)
    });
    result = await res.json();
  } catch (e) {
    showFloatingPanel({error: 'Could not reach local API (is backend running?). ' + e});
    return;
  }

  // === 3) Show suggestions in a floating panel ===
  showFloatingPanel(result);
}

function showFloatingPanel(data) {
  // Remove existing panel
  const existing = document.getElementById('preqin-enricher-panel');
  if (existing) existing.remove();

  const panel = document.createElement('div');
  panel.id = 'preqin-enricher-panel';
  panel.style.position = 'fixed';
  panel.style.right = '12px';
  panel.style.bottom = '12px';
  panel.style.width = '320px';
  panel.style.zIndex = 999999;
  panel.style.background = '#fff';
  panel.style.border = '1px solid rgba(0,0,0,0.12)';
  panel.style.boxShadow = '0 6px 18px rgba(0,0,0,0.12)';
  panel.style.padding = '12px';
  panel.style.borderRadius = '8px';
  panel.style.fontFamily = 'Arial, sans-serif';

  if (data.error) {
    panel.innerHTML = `<b>Error</b><div>${data.error}</div>`;
    document.body.appendChild(panel);
    return;
  }

  panel.innerHTML = `
    <div style="font-weight:600;margin-bottom:6px">Enrichment suggestions</div>
    <div><b>HQ Country:</b> ${data.hq_country_iso || '<i>Unknown</i>'}</div>
    <div><b>Phone:</b> ${data.formatted_phone || '<i>Unchanged</i>'} ${data.phone_valid ? '' : '<span style="color:#b33">(invalid)</span>'}</div>
    <div><b>Firm Currency:</b> ${data.firm_currency}</div>
    <div style="margin-top:10px; display:flex; gap:8px;">
      <button id="apply-enrich" style="flex:1;padding:8px">Apply</button>
      <button id="close-enrich" style="flex:1;padding:8px">Close</button>
    </div>
  `;

  document.body.appendChild(panel);

  document.getElementById('close-enrich').onclick = () => panel.remove();
  document.getElementById('apply-enrich').onclick = () => {
    applyToForm(data);
    panel.remove();
  };
}

function applyToForm(data) {
  // IMPORTANT: update selectors to match actual CRM fields.
  if (data.hq_country_iso) {
    const countryField = document.querySelector('#hq-country');
    if (countryField) countryField.value = data.hq_country_iso;
  }
  if (data.formatted_phone) {
    const phoneField = document.querySelector('#phone');
    if (phoneField) phoneField.value = data.formatted_phone;
  }
  if (data.firm_currency) {
    const currencyField = document.querySelector('#firm-currency');
    if (currencyField) currencyField.value = data.firm_currency;
  }

  // Optionally trigger change events for CRM to pick up the changes:
  ['#hq-country', '#phone', '#firm-currency'].forEach(sel => {
    const el = document.querySelector(sel);
    if (el) {
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
    }
  });
}
