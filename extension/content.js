// content.js
console.log("Preqin Enricher content script loaded");

/**
 * Helper: try multiple CSS selectors in order
 */
function pickElement(selectors) {
    for (const sel of selectors) {
        const el = document.querySelector(sel);
        if (el) return el;
    }
    return null;
}

/**
 * SCRAPE FIELDS FROM THE CURRENT WEBPAGE
 *
 * For your local test form:
 *   Address  -> #hq_address
 *   City     -> #hq_city
 *   State    -> #hq_state
 *   Postal   -> #hq_postal
 *   Country  -> #hq_country
 *   Phone    -> #phone
 *   Currency -> #currency (optional)
 */
function scrapeFirmDataFromPage() {
    const addressInput = pickElement(['#hq_address']);
    const cityInput    = pickElement(['#hq_city']);
    const stateInput   = pickElement(['#hq_state']);
    const postalInput  = pickElement(['#hq_postal']);
    const countryInput = pickElement(['#hq_country']);
    const phoneInput   = pickElement(['#phone']);

    const data = {
        address_line: addressInput ? addressInput.value : "",
        city:         cityInput ? cityInput.value : "",
        state:        stateInput ? stateInput.value : "",
        postal_code:  postalInput ? postalInput.value : "",
        country:      countryInput ? countryInput.value : "",
        phone:        phoneInput ? phoneInput.value : ""
    };

    console.log("Preqin Enricher - scraped form data:", data);
    return data;
}

/**
 * APPLY ENRICHED DATA BACK INTO THE PAGE FORM
 *
 * We update:
 *   - #hq_country  <- hq_country_iso
 *   - #phone       <- formatted_phone
 *   - #currency    <- firm_currency
 */
function applyEnrichmentToPage(data) {
    console.log("Preqin Enricher - applying enrichment:", data);

    const countryInput  = pickElement(['#hq_country']);
    const phoneInput    = pickElement(['#phone']);
    const currencyInput = pickElement(['#currency']);

    // Set country (ISO2 code, e.g. "JP")
    if (countryInput && data.hq_country_iso) {
        countryInput.value = data.hq_country_iso;
    }

    // Set formatted phone (e.g. "+81 3 1234 5678")
    if (phoneInput && data.formatted_phone) {
        phoneInput.value = data.formatted_phone;
    }

    // Set currency (e.g. "JPY")
    if (currencyInput && data.firm_currency) {
        currencyInput.value = data.firm_currency;
    }

    // Fire input/change events so the page detects changes
    [countryInput, phoneInput, currencyInput].forEach(el => {
        if (el) {
            el.dispatchEvent(new Event("input", { bubbles: true }));
            el.dispatchEvent(new Event("change", { bubbles: true }));
        }
    });

    console.log("Preqin Enricher - finished applying enrichment");
}

/**
 * Listen for messages from popup.js
 */
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message?.type === "SCRAPE_FORM") {
        const scraped = scrapeFirmDataFromPage();
        sendResponse(scraped);
    }

    if (message?.type === "APPLY_ENRICHMENT") {
        applyEnrichmentToPage(message.payload);
        sendResponse({ ok: true });
    }
});
