// popup.js — popup-only, enrich + auto About-generator (follows user's strict template & rules)

const statusEl = document.getElementById("status");
function setStatus(msg) {
  const t = `${new Date().toLocaleTimeString()} — ${msg}`;
  if (statusEl) statusEl.innerText = t;
  console.log("[popup] " + msg);
}

document.getElementById("run").addEventListener("click", runEnrich);

function sentenceCase(s) {
  if (!s || typeof s !== "string") return "";
  s = s.trim();
  if (!s) return "";
  return s.charAt(0).toUpperCase() + s.slice(1).toLowerCase();
}

// Choose up to n items, return array (preserving input order)
function pickItems(arr, n) {
  if (!Array.isArray(arr)) return [];
  const clean = arr.map(a => (a || "").toString().trim()).filter(Boolean);
  return clean.slice(0, n);
}

// Join list with commas and an "and" before last item. Items are already in sentence-case.
function joinWithOxford(list) {
  if (!list || list.length === 0) return "";
  if (list.length === 1) return list[0];
  if (list.length === 2) return `${list[0]} and ${list[1]}`;
  return `${list.slice(0, -1).join(", ")}, and ${list[list.length - 1]}`;
}

// heuristics for choosing "a" vs "an" based on initial SOUND (best-effort)
function chooseArticle(phrase) {
  if (!phrase) return "a";
  const word = phrase.trim().split(/\s+/)[0].toLowerCase();
  // common vowel-starting words -> use "an"
  const vowels = ["a", "e", "i", "o", "u"];
  // handle some special cases where first letter vowel but pronounced consonant: (rare)
  const consonantSoundExceptions = ["university", "unicorn", "use", "user", "european"]; // pronounced 'yoo' -> 'a'
  const vowelSoundExceptions = ["hour", "honest", "honour"]; // silent h -> 'an'
  if (consonantSoundExceptions.includes(word)) return "a";
  if (vowelSoundExceptions.includes(word)) return "an";
  const first = word.charAt(0);
  if (vowels.includes(first)) return "an";
  return "a";
}

// Ensure firm type formatting: if not exactly "law firm" (case-insensitive), append "Firm" if not present
function normalizeFirmType(raw) {
  if (!raw) return "Firm";
  let s = raw.trim();
  // normalize casing to Title Case for readability
  s = s.split(/\s+/).map(t => t.charAt(0).toUpperCase() + t.slice(1).toLowerCase()).join(" ");
  if (s.toLowerCase() === "law firm") return "Law Firm";
  // if 'firm' not present at end, append 'Firm'
  if (!/firm$/i.test(s)) {
    s = `${s} Firm`;
  }
  return s;
}

// Extract services (array of strings) from page DOM
function readServicesFromPage() {
  try {
    const container = document.querySelector("#services_offered");
    if (!container) return [];
    return Array.from(container.querySelectorAll("input[type=checkbox]"))
      .filter(i => i.checked)
      .map(i => i.value)
      .filter(Boolean);
  } catch (e) {
    console.warn("readServicesFromPage error", e);
    return [];
  }
}

// Extract fund types from page DOM
function readFundsFromPage() {
  try {
    const container = document.querySelector("#funds_serviced");
    if (!container) return [];
    return Array.from(container.querySelectorAll("input[type=checkbox]"))
      .filter(i => i.checked)
      .map(i => i.value)
      .filter(Boolean);
  } catch (e) {
    console.warn("readFundsFromPage error", e);
    return [];
  }
}

// Build the about string according to user's strict template and rules
function buildAboutSentence(opts) {
  // opts: { firmName, firmTypeRaw, hq_parsed, hq_raw, servicesArr, fundsArr }
  const firmName = (opts.firmName || "").trim() || "The firm";
  const firmTypeRaw = (opts.firmTypeRaw || "").trim();
  const firmTypeNormalized = normalizeFirmType(firmTypeRaw);
  const article = chooseArticle(firmTypeNormalized);

  // Location: prioritize state, else city
  let state = null;
  let city = null;
  let country = null;
  if (opts.hq_parsed && typeof opts.hq_parsed === "object") {
    state = opts.hq_parsed.state || null;
    city = opts.hq_parsed.city || null;
    country = opts.hq_parsed.country || null;
  }
  // best-effort parse from raw address if parsed is missing values
  if (!country && opts.hq_raw) {
    const parts = opts.hq_raw.split(",").map(p => p.trim()).filter(Boolean);
    if (parts.length >= 1) country = parts[parts.length - 1];
    if (!state && parts.length >= 3) {
      // assume pattern: street, city, state/postcode, country — try parts[parts.length-2]
      state = parts[parts.length - 2];
    } else if (!city && parts.length >= 2) {
      city = parts[parts.length - 2];
    }
  }
  // prefer state if present, else city. If both absent, use 'an unknown location' (but template expects State, Country)
  const locPrimary = state || city || null;
  const locCountry = country || "";

  // Services handling
  let services = Array.isArray(opts.servicesArr) ? opts.servicesArr.slice() : [];
  // map to sentence case
  services = services.map(s => sentenceCase(s));
  let servicesClause = "";
  if (!services || services.length === 0) {
    servicesClause = "It provides a wide range of financial services,";
  } else {
    // choose up to 5
    const chosen = pickItems(services, 5);
    const joined = joinWithOxford(chosen);
    servicesClause = `It provides services including ${joined}, and more.`;
  }

  // Fund types handling
  let funds = Array.isArray(opts.fundsArr) ? opts.fundsArr.slice() : [];
  funds = funds.map(f => sentenceCase(f));
  let fundClause = "";
  if (!funds || funds.length === 0) {
    // Replace entire fund type clause with placeholder per instructions.
    fundClause = "The firm advises various types of funds.";
  } else {
    const chosenFunds = pickItems(funds, 4);
    const joinedFunds = joinWithOxford(chosenFunds);
    const verb = (chosenFunds.length === 1) ? "is" : "are";
    // decide singular/plural phrasing as requested
    fundClause = `The fund ${chosenFunds.length === 1 ? "type" : "types"} advised by the firm ${verb} ${joinedFunds}, among others.`;
  }

  // Assemble final sentence EXACTLY in template order:
  // "[Firm Name] is [a/an] [Firm Type] headquartered in [State], [Country]. It provides services including [...], and more. The fund type(s) advised by the firm [is/are] [...], among others."
  const locationPart = locPrimary ? `${locPrimary}, ${locCountry}` : (locCountry ? `${locCountry}` : "an unknown location");
  // Capitalize firmTypeNormalized appropriately (already Title Case)
  const firstSentence = `${firmName} is ${article} ${firmTypeNormalized} headquartered in ${locationPart}.`;

  // If we used placeholder for servicesClause, ensure it ends with a space/separator consistent with template.
  // The template expects the services sentence to be present before the fund clause.
  // We built servicesClause earlier to either be placeholder or the normal 'It provides services including ...'
  // Ensure punctuation: if servicesClause already ends with '.', keep it; otherwise add a period.
  let servicesSentence = servicesClause;
  if (!servicesSentence.endsWith(".")) servicesSentence = servicesSentence.endsWith(",") ? servicesSentence + " and more." : servicesSentence + ".";
  // If servicesClause already had 'and more.' we don't alter it.

  // If fundClause is the placeholder "The firm advises various types of funds.", it fits the template replacement.
  const about = `${firstSentence} ${servicesSentence} ${fundClause}`;
  return about;
}

// Main run: scrape page, call backend, write back results + build about
async function runEnrich() {
  setStatus("Starting scrape...");
  try {
    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tabs || !tabs.length) {
      setStatus("No active tab found.");
      return;
    }
    const tab = tabs[0];

    // Scrape page fields (HQ, alt offices, services, funds, firm name/type)
    const [{ result: scraped } = {}] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      world: "MAIN",
      func: () => {
        const get = sel => {
          const el = document.querySelector(sel);
          if (!el) return null;
          return ("value" in el) ? el.value.trim() : el.innerText.trim();
        };

        const hq_raw = get("#hq_address");
        const hq_phone = get("#phone") || get("#hq_phone");
        const hq_fax = get("#fax") || get("#hq_fax");
        const hq_website = get("#hq_website");
        const hq_email = get("#hq_email");

        const firmName = get("#firm_name") || get("#firm_name_display") || get(".firm-name");

        const firmType = get("#firm_type") || get(".firm-type") || null;

        const services = Array.from(document.querySelectorAll("#services_offered input[type=checkbox]"))
          .filter(i => i.checked).map(i => i.value);

        const funds = Array.from(document.querySelectorAll("#funds_serviced input[type=checkbox]"))
          .filter(i => i.checked).map(i => i.value);

        const alt_addresses = Array.from(document.querySelectorAll(".alt-office-address"));
        const alt_offices = alt_addresses.map(addrEl => {
          const row = addrEl.closest("div") || addrEl.parentElement;
          const phoneEl = row ? row.querySelector(".alt-office-phone") : null;
          const faxEl = row ? row.querySelector(".alt-office-fax") : null;
          const webEl = row ? row.querySelector(".alt-office-web") : null;
          const emailEl = row ? row.querySelector(".alt-office-email") : null;
          return {
            raw: (addrEl && addrEl.value) ? addrEl.value.trim() : null,
            phone: (phoneEl && phoneEl.value) ? phoneEl.value.trim() : null,
            fax: (faxEl && faxEl.value) ? faxEl.value.trim() : null,
            website: (webEl && webEl.value) ? webEl.value.trim() : null,
            email: (emailEl && emailEl.value) ? emailEl.value.trim() : null
          };
        });

        return {
          ok: true,
          hq: { raw: hq_raw || null, phone: hq_phone || null, fax: hq_fax || null, website: hq_website || null, email: hq_email || null },
          alt_offices: alt_offices,
          firm_name: firmName,
          firm_type: firmType,
          services: services,
          funds: funds
        };
      }
    });

    if (!scraped || !scraped.ok) {
      setStatus("Scrape failed or returned nothing.");
      console.log("scraped raw:", scraped);
      return;
    }

    const payload = { hq: scraped.hq, alt_offices: scraped.alt_offices || [], firm_name: scraped.firm_name || null, firm_type: scraped.firm_type || null, services: scraped.services || [], funds: scraped.funds || [] };

    console.log("Payload to backend:", payload);
    setStatus("Posting to backend...");

    const res = await fetch("http://127.0.0.1:8000/enrich", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).catch(e => { throw new Error("Network error: " + e.message); });

    if (!res.ok) {
      const body = await res.text().catch(() => "");
      setStatus(`Backend error ${res.status}`);
      console.error("backend body:", body);
      return;
    }
    const json = await res.json();
    console.log("Backend response:", json);

    // Inject HQ formatted phone/fax/currency
    const formattedPhone = json.formatted_phone || json.formattedPhone || null;
    const formattedFax = json.formatted_fax || json.formattedFax || null;
    const currency = json.currency || json.firm_currency || null;

    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      world: "MAIN",
      func: (phoneVal, faxVal, currencyVal) => {
        const set = (sel, val) => {
          const el = document.querySelector(sel);
          if (!el) return false;
          if ("value" in el) el.value = val || "";
          else el.innerText = val || "";
          try { el.dispatchEvent(new Event("input", { bubbles: true })); } catch (e) {}
          try { el.dispatchEvent(new Event("change", { bubbles: true })); } catch (e) {}
          return true;
        };
        set("#phone", phoneVal);
        set("#fax", faxVal);
        set("#currency", currencyVal);
      },
      args: [formattedPhone, formattedFax, currency]
    });

    setStatus("Applied HQ values. Processing alternate offices...");

    // Inject alt_offices formatted phones/faxes (map by index)
    const alt_offices_resp = json.alt_offices || [];
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      world: "MAIN",
      func: (altList) => {
        const addrEls = Array.from(document.querySelectorAll(".alt-office-address"));
        addrEls.forEach((addrEl, idx) => {
          const row = addrEl.closest("div") || addrEl.parentElement;
          const phoneEl = row ? row.querySelector(".alt-office-phone") : null;
          const faxEl = row ? row.querySelector(".alt-office-fax") : null;
          const info = altList[idx] || {};
          const fp = info.formatted_phone || info.formattedPhone || info.formatted || null;
          const ff = info.formatted_fax || info.formattedFax || null;
          if (phoneEl && fp) {
            if ("value" in phoneEl) phoneEl.value = fp;
            else phoneEl.innerText = fp;
            try { phoneEl.dispatchEvent(new Event("input", { bubbles: true })); } catch (e) {}
            try { phoneEl.dispatchEvent(new Event("change", { bubbles: true })); } catch (e) {}
          }
          if (faxEl && ff) {
            if ("value" in faxEl) faxEl.value = ff;
            else faxEl.innerText = ff;
            try { faxEl.dispatchEvent(new Event("input", { bubbles: true })); } catch (e) {}
            try { faxEl.dispatchEvent(new Event("change", { bubbles: true })); } catch (e) {}
          }
        });
        return true;
      },
      args: [alt_offices_resp]
    });

    setStatus("Alternate offices updated. Building About section...");

    // Build About using page-scraped services/funds/firm info and backend hq_parsed
    const aboutOpts = {
      firmName: payload.firm_name || "",
      firmTypeRaw: payload.firm_type || "",
      hq_parsed: json.hq_parsed || {},
      hq_raw: payload.hq.raw || "",
      servicesArr: payload.services || [],
      fundsArr: payload.funds || []
    };
    const aboutText = buildAboutSentence(aboutOpts);
    console.log("Generated About:", aboutText);

    // Inject About into page
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      world: "MAIN",
      func: (text) => {
        const el = document.querySelector("#about_section");
        if (!el) return false;
        if ("value" in el) el.value = text;
        else el.innerText = text;
        try { el.dispatchEvent(new Event("input", { bubbles: true })); } catch (e) { }
        try { el.dispatchEvent(new Event("change", { bubbles: true })); } catch (e) { }
        return true;
      },
      args: [aboutText]
    });

    setStatus("Done — About populated.");
  } catch (err) {
    console.error("runEnrich error:", err);
    setStatus("Error: " + (err && err.message ? err.message : String(err)));
  }
}
