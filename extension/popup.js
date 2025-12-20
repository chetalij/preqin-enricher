// popup.js — full updated version (services list: comma-separated only, then ", and more.")
const statusEl = document.getElementById("status");
function setStatus(msg) {
  const t = `${new Date().toLocaleTimeString()} — ${msg}`;
  if (statusEl) statusEl.innerText = t;
  console.log("[popup] " + msg);
}

document.getElementById("run").addEventListener("click", runEnrich);

// helper: pick up to n items preserving order
function pickItems(arr, n) {
  if (!Array.isArray(arr)) return [];
  return arr.map(a => (a || "").toString().trim()).filter(Boolean).slice(0, n);
}
function joinWithOxford(list) {
  if (!list || list.length === 0) return "";
  if (list.length === 1) return list[0];
  if (list.length === 2) return `${list[0]} and ${list[1]}`;
  return `${list.slice(0, -1).join(", ")}, and ${list[list.length - 1]}`;
}

// article choice (best-effort on sound)
function chooseArticle(word) {
  if (!word) return "a";
  const w = word.trim().toLowerCase();
  // special pronunciations
  const consonantSoundExceptions = ["university", "unicorn", "use", "user", "european"];
  const vowelSoundExceptions = ["hour", "honest", "honour"];
  if (consonantSoundExceptions.includes(w)) return "a";
  if (vowelSoundExceptions.includes(w)) return "an";
  const first = w[0];
  if ("aeiou".includes(first)) return "an";
  return "a";
}

// normalize firm type to lowercased phrase; ensure "firm" present (except exact "law firm")
function normalizeFirmTypeLower(raw) {
  if (!raw) return "firm";
  let s = raw.trim().toLowerCase();
  if (s === "law firm") return "law firm";
  if (!s.endsWith("firm")) s = `${s} firm`;
  return s;
}

// Extract city/state from parsed hq or best-effort from raw address
function chooseLocation(parsed, raw) {
  if (parsed) {
    const state = parsed.state && parsed.state.trim();
    const city = parsed.city && parsed.city.trim();
    const country = parsed.country && parsed.country.trim();
    if (state) return { primary: state, country: country || "" };
    if (city) return { primary: city, country: country || "" };
  }
  // best-effort parse from raw: split by commas, remove postcode-like tokens and country, return last remaining token
  if (raw && raw.trim()) {
    const parts = raw.split(",").map(p => p.trim()).filter(Boolean);
    if (parts.length === 0) return { primary: null, country: null };
    // last token is likely country
    const country = parts[parts.length - 1];
    // build candidate tokens excluding obvious postcode tokens (tokens that contain digits)
    const candidates = parts.slice(0, -1).filter(tok => {
      if (/\d/.test(tok)) return false;
      return true;
    });
    if (candidates.length > 0) {
      const primary = candidates[candidates.length - 1];
      return { primary: primary, country: country || "" };
    } else {
      if (parts.length >= 2) {
        const candidate = parts[parts.length - 2];
        const subparts = candidate.split(" ").map(s => s.trim()).filter(Boolean).filter(sp => !/\d/.test(sp));
        const primary = subparts.length ? subparts.join(" ") : candidate;
        return { primary: primary, country: country || "" };
      } else {
        return { primary: null, country: country || "" };
      }
    }
  }
  return { primary: null, country: null };
}

// services -> lowercase formatting
function formatService(s) {
  if (!s) return "";
  return s.trim().toLowerCase();
}

// funds -> preserve uppercase acronyms (CLO etc.), otherwise lowercase
function formatFund(f) {
  if (!f) return "";
  const t = f.trim();
  if (/^[A-Z]{2,4}$/.test(t)) return t;
  return t.toLowerCase();
}

// Build about text following exact template and rules
function buildAbout(opts) {
  // opts: { firmName, firmTypeRaw, hq_parsed, hq_raw, servicesArr, fundsArr }
  const firmName = (opts.firmName || "").trim() || "The firm";
  const firmTypeRaw = (opts.firmTypeRaw || "").trim();
  const firmType = normalizeFirmTypeLower(firmTypeRaw); // lowercased
  const article = chooseArticle(firmTypeRaw || firmType);

  const loc = chooseLocation(opts.hq_parsed || {}, opts.hq_raw || "");
  const primary = loc.primary;
  const country = loc.country || "";

  const servicesIn = Array.isArray(opts.servicesArr) ? opts.servicesArr : [];
  const fundsIn = Array.isArray(opts.fundsArr) ? opts.fundsArr : [];

  // Services selection & formatting (comma-separated, NO 'and' before last item, then append ", and more.")
  let servicesClause = "";
  if (!servicesIn || servicesIn.length === 0) {
    servicesClause = "It provides a wide range of financial services,";
  } else {
    const chosen = pickItems(servicesIn, 5).map(formatService);
    const joined = chosen.join(", "); // NO 'and'
    servicesClause = `It provides services including ${joined}, and more.`;
  }

  // Funds selection & formatting (Oxford rule applies here)
  let fundClause = "";
  if (!fundsIn || fundsIn.length === 0) {
    fundClause = "The firm advises various types of funds.";
  } else {
    const chosenFunds = pickItems(fundsIn, 4).map(formatFund);
    const joinedFunds = joinWithOxford(chosenFunds);
    const verb = (chosenFunds.length === 1) ? "is" : "are";
    fundClause = `The fund ${chosenFunds.length === 1 ? "type" : "types"} advised by the firm ${verb} ${joinedFunds}, among others.`;
  }

  const locationPart = primary ? `${primary}, ${country}`.trim() : (country ? `${country}` : "an unknown location");

  const firstSentence = `${firmName} is ${article} ${firmType} headquartered in ${locationPart}.`;
  let servicesSentence = servicesClause;
  if (!servicesSentence.endsWith(".")) servicesSentence = servicesSentence.endsWith(",") ? servicesSentence + " and more." : servicesSentence + ".";
  const about = `${firstSentence} ${servicesSentence} ${fundClause}`;
  return about;
}

// Main flow (scrape, post to backend, apply formatting, build About)
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
    const aboutText = buildAbout(aboutOpts);
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

    // ---- M&A UI Rendering ----
const ma = json.m_and_a || null;

await chrome.scripting.executeScript({
  target: { tabId: tab.id },
  world: "MAIN",
  func: (maData) => {
    const noneEl = document.getElementById("ma-none");
    const foundEl = document.getElementById("ma-found");
    const snippetEl = document.getElementById("ma-snippet");
    const confEl = document.getElementById("ma-confidence");
    const srcEl = document.getElementById("ma-sources");

    if (!noneEl || !foundEl) return;

    // If nothing detected
    if (!maData || !maData.ma_snippet) {
      noneEl.style.display = "block";
      foundEl.style.display = "none";
      return;
    }

    // If detected
    noneEl.style.display = "none";
    foundEl.style.display = "block";

    if (snippetEl) snippetEl.textContent = maData.ma_snippet || "";
    if (confEl) confEl.textContent = maData.confidence || "";

    if (srcEl) {
      srcEl.innerHTML = "";
      (maData.provenance || []).forEach(src => {
        const p = document.createElement("p");
        const a = document.createElement("a");
        a.href = src.url;
        a.target = "_blank";
        a.rel = "noopener noreferrer";
        a.textContent = src.url;

        p.appendChild(a);

        if (src.excerpt) {
          const em = document.createElement("em");
          em.textContent = ` — ${src.excerpt}`;
          p.appendChild(em);
        }

        srcEl.appendChild(p);
      });
    }
  },
  args: [ma]
});

    setStatus("Done — About populated.");
  } catch (err) {
    console.error("runEnrich error:", err);
    setStatus("Error: " + (err && err.message ? err.message : String(err)));
  }
}
