// popup.js

// ---------------------------------------------------------
// 1. RUN ENRICHMENT (sends data to backend)
// ---------------------------------------------------------
async function runEnrichment() {
    const resultBox = document.getElementById("result");

    // Read values from popup input fields
    const address_line = document.getElementById("address_line").value;
    const city = document.getElementById("city").value;
    const state = document.getElementById("state").value;
    const postal_code = document.getElementById("postal_code").value;
    const country = document.getElementById("country").value;
    const phone = document.getElementById("phone").value;

    // Basic validation: at least something must be provided
    if (!address_line && !city && !postal_code && !country && !phone) {
        resultBox.textContent = "Please enter at least one field (address/phone).";
        return;
    }

    const payload = {
        firm_id: "test-from-popup",
        hq: {
            address_line,
            city,
            state,
            postal_code,
            country
        },
        alt_offices: [],
        phone
    };

    try {
        resultBox.textContent = "Calling backend...";

        const res = await fetch("http://127.0.0.1:8000/enrich", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        if (!res.ok) {
            const text = await res.text();
            resultBox.textContent = `Error from backend (${res.status}): ${text}`;
            return;
        }

        const data = await res.json();
        resultBox.textContent = JSON.stringify(data, null, 2);

    } catch (e) {
        resultBox.textContent = "Error calling backend: " + e;
    }
}



// ---------------------------------------------------------
// 2. SCRAPE FIELDS FROM CURRENT PAGE
// ---------------------------------------------------------
async function scrapeFromPage() {
    const resultBox = document.getElementById("result");
    resultBox.textContent = "Reading fields from current page...";

    try {
        // Get the active browser tab
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (!tab || !tab.id) {
            resultBox.textContent = "No active tab found.";
            return;
        }

        // Ask the content script for data
        const scraped = await chrome.tabs.sendMessage(tab.id, {
            type: "SCRAPE_FORM"
        });

        if (!scraped) {
            resultBox.textContent = "No data returned from page.";
            return;
        }

        // Populate popup UI fields
        document.getElementById("address_line").value = scraped.address_line || "";
        document.getElementById("city").value = scraped.city || "";
        document.getElementById("state").value = scraped.state || "";
        document.getElementById("postal_code").value = scraped.postal_code || "";
        document.getElementById("country").value = scraped.country || "";
        document.getElementById("phone").value = scraped.phone || "";

        resultBox.textContent = "Fields loaded from page. Now click 'Run Enrichment'.";

    } catch (e) {
        console.error(e);
        resultBox.textContent = "Error reading from page: " + e;
    }
}



// ---------------------------------------------------------
// 3. APPLY ENRICHED DATA BACK TO THE PAGE
// ---------------------------------------------------------
async function applyEnrichedDataToPage() {
    const resultBox = document.getElementById("result");

    let enrichedData;
    try {
        enrichedData = JSON.parse(resultBox.textContent);
    } catch {
        resultBox.textContent = "No enriched data to apply. Run enrichment first.";
        return;
    }

    if (!enrichedData || typeof enrichedData !== "object") {
        resultBox.textContent = "Invalid enriched data.";
        return;
    }

    try {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (!tab || !tab.id) {
            resultBox.textContent = "No active tab.";
            return;
        }

        await chrome.tabs.sendMessage(tab.id, {
            type: "APPLY_ENRICHMENT",
            payload: enrichedData
        });

        resultBox.textContent = "Enriched data applied to the page.";

    } catch (e) {
        console.error(e);
        resultBox.textContent = "Error applying data to page: " + e;
    }
}



// ---------------------------------------------------------
// 4. EVENT LISTENERS FOR THE THREE BUTTONS
// ---------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {

    const scrapeBtn = document.getElementById("scrapeBtn");
    if (scrapeBtn) {
        scrapeBtn.addEventListener("click", scrapeFromPage);
    }

    const enrichBtn = document.getElementById("enrichBtn");
    if (enrichBtn) {
        enrichBtn.addEventListener("click", runEnrichment);
    }

    const applyBtn = document.getElementById("applyBtn");
    if (applyBtn) {
        applyBtn.addEventListener("click", applyEnrichedDataToPage);
    }
});
