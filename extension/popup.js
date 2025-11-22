// popup.js
'use strict';

// ============================================================
// Configuration
// ============================================================

// FastAPI backend endpoint
const BACKEND_URL = 'http://127.0.0.1:8000/enrich';

// In-memory state in the popup
let hqSource = null;          // HQ data scraped from the page
let hqEnriched = null;        // HQ data returned from the backend
let altSources = [];          // Alternate office data scraped from the page
let altEnriched = [];         // Alternate office enriched responses

// ============================================================
// Utility helpers (popup context)
// ============================================================

/**
 * Append or replace status text in the popup "Status / Debug" box.
 */
function logStatus(message, append = true) {
  const statusEl = document.getElementById('status');
  if (!statusEl) return;

  const time = new Date().toLocaleTimeString();
  const line = `[${time}] ${message}`;

  if (append) {
    statusEl.textContent = statusEl.textContent
      ? statusEl.textContent + '\n' + line
      : line;
  } else {
    statusEl.textContent = line;
  }
}

/**
 * Get the currently active tab ID.
 */
function getActiveTabId(callback) {
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (!tabs || !tabs.length) {
      console.error('No active tab found.');
      logStatus('ERROR: No active tab found.');
      callback(null);
      return;
    }
    callback(tabs[0].id);
  });
}

// ============================================================
// Page-context functions (run inside test-form / CRM page)
// ============================================================

/**
 * Runs inside the test form / CRM page.
 *
 * Reads:
 *   HQ:
 *     #hq_address
 *     #hq_city
 *     #hq_state
 *     #hq_postal
 *     #hq_country
 *     #phone
 *     #fax
 *     #currency
 *
 *   Alternate offices:
 *     .alt-office-block
 *       .alt-office-country
 *       .alt-office-phone
 *       .alt-office-fax
 *
 * Returns: { hq, altOffices }
 */
function scrapeAllFromPage() {
  const getVal = (selector) => {
    const el = document.querySelector(selector);
    if (!el) return '';
    if (el.value !== undefined) return String(el.value).trim();
    return (el.textContent || '').trim();
  };

  // ---- HQ ----
  const addressSelector = '#hq_address';
  const citySelector = '#hq_city';
  const stateSelector = '#hq_state';
  const postalSelector = '#hq_postal';
  const countrySelector = '#hq_country';
  const phoneSelector = '#phone';
  const faxSelector = '#fax';
  const currencySelector = '#currency';

  const hq = {
    addressLine: getVal(addressSelector),
    city: getVal(citySelector),
    stateRegion: getVal(stateSelector),
    postalCode: getVal(postalSelector),
    country: getVal(countrySelector),
    phone: getVal(phoneSelector),
    fax: getVal(faxSelector),
    currency: getVal(currencySelector)
  };

  // ---- Alternate offices ----
  const altOffices = [];
  const blocks = document.querySelectorAll('.alt-office-block');

  blocks.forEach((block, index) => {
    const getInBlock = (selector) => {
      const el = block.querySelector(selector);
      if (!el) return '';
      if (el.value !== undefined) return String(el.value).trim();
      return (el.textContent || '').trim();
    };

    altOffices.push({
      index,
      label: block.querySelector('h3')?.textContent?.trim() || `Alternate Office ${index + 1}`,
      country: getInBlock('.alt-office-country'),
      phone: getInBlock('.alt-office-phone'),
      fax: getInBlock('.alt-office-fax')
    });
  });

  return { hq, altOffices };
}

/**
 * Runs inside the test form / CRM page.
 *
 * Applies enriched HQ data and enriched alternate office data
 * back into the DOM.
 *
 * HQ:
 *   formatted_phone -> #phone
 *   formatted_fax   -> #fax
 *   firm_currency   -> #currency
 *   hq_country_iso  -> #hq_country_iso (if present; safe no-op otherwise)
 *
 * Alternate offices (per .alt-office-block index):
 *   formatted_phone -> .alt-office-phone
 *   formatted_fax   -> .alt-office-fax
 */
function applyAllEnrichedToPage(hqEnrichedArg, altEnrichedArg) {
  const setVal = (element, value) => {
    if (!element) return;
    if ('value' in element) {
      element.value = value ?? '';
      element.dispatchEvent(new Event('input', { bubbles: true }));
      element.dispatchEvent(new Event('change', { bubbles: true }));
    } else {
      element.textContent = value ?? '';
    }
  };

  // ---- Apply HQ ----
  if (hqEnrichedArg) {
    const phoneEl = document.querySelector('#phone');
    const faxEl = document.querySelector('#fax');
    const currencyEl = document.querySelector('#currency');
    const isoEl = document.querySelector('#hq_country_iso'); // optional

    if (hqEnrichedArg.formatted_phone) {
      setVal(phoneEl, hqEnrichedArg.formatted_phone);
    }
    if (hqEnrichedArg.formatted_fax) {
      setVal(faxEl, hqEnrichedArg.formatted_fax);
    }
    if (hqEnrichedArg.firm_currency) {
      setVal(currencyEl, hqEnrichedArg.firm_currency);
    }
    if (hqEnrichedArg.hq_country_iso) {
      setVal(isoEl, hqEnrichedArg.hq_country_iso);
    }
  }

  // ---- Apply Alternate Offices ----
  if (Array.isArray(altEnrichedArg)) {
    const blocks = document.querySelectorAll('.alt-office-block');

    altEnrichedArg.forEach((alt) => {
      const block = blocks[alt.index];
      if (!block || !alt.response) return;

      const phoneEl = block.querySelector('.alt-office-phone');
      const faxEl = block.querySelector('.alt-office-fax');

      if (alt.response.formatted_phone) {
        setVal(phoneEl, alt.response.formatted_phone);
      }
      if (alt.response.formatted_fax) {
        setVal(faxEl, alt.response.formatted_fax);
      }
    });
  }
}

// ============================================================
// Button handlers (popup context)
// ============================================================

/**
 * "Use fields from current page"
 *
 * Scrapes HQ + alternate office data using chrome.scripting.executeScript
 * and stores them in popup state.
 */
function handleUseFieldsFromPage() {
  logStatus('Reading HQ and alternate office fields from current page...', false);

  getActiveTabId((tabId) => {
    if (!tabId) return;

    chrome.scripting.executeScript(
      {
        target: { tabId },
        func: scrapeAllFromPage
      },
      (results) => {
        if (chrome.runtime.lastError) {
          console.error('Error scraping page:', chrome.runtime.lastError);
          logStatus('ERROR reading from page (scripting). See DevTools console.');
          return;
        }

        const [res] = results || [];
        if (!res || !res.result) {
          logStatus('No data returned from page.');
          return;
        }

        hqSource = res.result.hq;
        altSources = res.result.altOffices || [];
        altEnriched = []; // reset previous enriched data

        console.log('[Preqin Enricher] HQ source data:', hqSource);
        console.log('[Preqin Enricher] Alternate office source data:', altSources);

        logStatus(
          'HQ fields read from page:\n' +
          JSON.stringify(hqSource, null, 2) +
          '\n\nAlternate offices:\n' +
          JSON.stringify(altSources, null, 2)
        );
      }
    );
  });
}

/**
 * "Run Enrichment"
 *
 *  - Enrich HQ once
 *  - Enrich each alternate office with a separate call to /enrich
 *
 * For each call we reuse the same schema the backend expects:
 *
 *   { "hq": { "country": "...", "phone": "...", "fax": "..." } }
 */
async function handleRunEnrichment() {
  if (!hqSource) {
    alert('No HQ data loaded. Click "Use fields from current page" first.');
    return;
  }

  logStatus('Running enrichment for HQ and alternate offices...', false);

  try {
    // ---- Enrich HQ ----
    const hqPayload = {
      hq: {
        country: hqSource.country,
        phone: hqSource.phone,
        fax: hqSource.fax
      }
    };

    console.log('[Preqin Enricher] Sending HQ payload to backend:', hqPayload);

    const respHq = await fetch(BACKEND_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(hqPayload)
    });

    if (!respHq.ok) {
      const text = await respHq.text();
      console.error('Backend HQ error:', respHq.status, text);
      logStatus(`Backend HQ error (${respHq.status}). Body:\n${text}`);
      return;
    }

    hqEnriched = await respHq.json();
    console.log('[Preqin Enricher] HQ enrichment response:', hqEnriched);

    // ---- Enrich Alternate Offices ----
    altEnriched = [];

    for (const office of altSources) {
      const altPayload = {
        hq: {
          country: office.country,
          phone: office.phone,
          fax: office.fax
        }
      };

      console.log(
        `[Preqin Enricher] Sending alt office payload (index ${office.index}) to backend:`,
        altPayload
      );

      const respAlt = await fetch(BACKEND_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(altPayload)
      });

      if (!respAlt.ok) {
        const textAlt = await respAlt.text();
        console.error(
          `Backend alt office error (index ${office.index}):`,
          respAlt.status,
          textAlt
        );
        altEnriched.push({
          index: office.index,
          label: office.label,
          error: true,
          errorStatus: respAlt.status,
          errorBody: textAlt
        });
      } else {
        const dataAlt = await respAlt.json();
        altEnriched.push({
          index: office.index,
          label: office.label,
          response: dataAlt
        });
      }
    }

    logStatus(
      'Enrichment success.\n\nHQ:\n' +
      JSON.stringify(hqEnriched, null, 2) +
      '\n\nAlternate offices enriched:\n' +
      JSON.stringify(altEnriched, null, 2)
    );
  } catch (err) {
    console.error('Enrichment failed:', err);
    logStatus('ERROR: Enrichment failed: ' + err.message);
  }
}

/**
 * "Apply enriched data to page"
 *
 * Writes enriched HQ + alternate office data back into the page
 * using chrome.scripting.executeScript.
 */
function handleApplyToPage() {
  if (!hqEnriched && !altEnriched.length) {
    alert('No enriched data available. Run enrichment first.');
    return;
  }

  logStatus('Applying enriched data back to page...', false);

  getActiveTabId((tabId) => {
    if (!tabId) return;

    chrome.scripting.executeScript(
      {
        target: { tabId },
        func: applyAllEnrichedToPage,
        args: [hqEnriched, altEnriched]
      },
      () => {
        if (chrome.runtime.lastError) {
          console.error('Error applying enriched data to page:', chrome.runtime.lastError);
          logStatus('ERROR applying enriched data. See DevTools console.');
        } else {
          console.log('[Preqin Enricher] Enriched HQ + alt office data applied to page.');
          logStatus('Enriched HQ + alternate office data applied to page.');
        }
      }
    );
  });
}

// ============================================================
// Initialization
// ============================================================

document.addEventListener('DOMContentLoaded', () => {
  const btnUse = document.getElementById('btn-use-fields-from-page');
  const btnEnrich = document.getElementById('btn-run-enrichment');
  const btnApply = document.getElementById('btn-apply-to-page');

  if (btnUse) btnUse.addEventListener('click', handleUseFieldsFromPage);
  if (btnEnrich) btnEnrich.addEventListener('click', handleRunEnrichment);
  if (btnApply) btnApply.addEventListener('click', handleApplyToPage);

  logStatus('Popup loaded. Ready.', false);
});
