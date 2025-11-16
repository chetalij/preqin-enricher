async function runEnrichment() {
    const resultBox = document.getElementById("result");

    // Read values from inputs
    const address_line = document.getElementById("address_line").value;
    const city = document.getElementById("city").value;
    const state = document.getElementById("state").value;
    const postal_code = document.getElementById("postal_code").value;
    const country = document.getElementById("country").value;
    const phone = document.getElementById("phone").value;

    // Basic validation
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

// Attach event listener after DOM is ready
document.addEventListener("DOMContentLoaded", () => {
    const btn = document.getElementById("enrichBtn");
    if (btn) {
        btn.addEventListener("click", runEnrichment);
    }
});
