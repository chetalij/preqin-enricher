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
 * IMPORTANT:
 * - These are placeholder selectors.
 * - When you are on the actual Preqin CRM form on your work laptop,
 *   you will Inspect each form field and replace these selectors with the real ones.
 */
function scrapeFirmDataFromPage() {
    const addressInput = pickElement([
        'input[name="hq_address"]',
        '#hq_address',
        '.hq-address',
        'input[name="address"]',
        'input[placeholder*="Address"]'
    ]);

    const cityInput = pickElement([
        'input[name="hq_city"]',
        '#hq_city',
        '.hq-city',
        'input[placeholder*="City"]'
    ]);

    const stateInput = pickElement([
        'input[name="hq_state"]',
        '#hq_state',
        '.hq-state',
        'input[placeholder*="State"]'
    ]);

    const postalInput = pickElement([
        'input[name="hq_postal"]',
        '#hq_postal',
        '.hq-postal',
        'input[placeholder*="Postal"]',
        'input[placeholder*="Zip"]'
    ]);

    const countryInput = pickElement([
        'input[name="hq_country"]',
        '#hq_country',
        '.hq-country',
        'select[name="hq_country"]',
        'select[placeholder*="Country"]'
    ]);

    const phoneInput = pickElement([
        'input[name="phone"]',
        '#phone',
        '.phone',
        'input[placeholder*="Phone"]'
    ]);

    const data = {
        address_line: addressInput ? addressInput.value : "",
        city: cityInput ? cityInput.value : "",
        state: stateInput ? stateInput.value : "",
        postal_code: postalInput ? postalInput.value : "",
        country: countryInput ? countryInput.value : "",
        phone: phoneInput ? phoneInput.value : ""
    };

    console.log("Preqin Enricher - scraped form data:", data);
    return data;
}

/**
 * Listens for messages from popup.js
 */
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message?.type === "SCRAPE_FORM") {
        const scraped = scrapeFirmDataFromPage();
        sendResponse(scraped);
    }
});
