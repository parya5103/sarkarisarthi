/* GoGo Company - central AdSense integration (Sarkari Sarthi copy).
   Loaded by the Sarkari Sarthi portal page (https://gogocompany.in/sarkari-sarthi/).
   Listing page: one unit between the category grid and the job
   listings - never beside job cards, Apply buttons, or within the
   listings grid. Job detail pages: one unit after the article. Games (/arrowout/, /crystalquest/) never load ads.

   STATUS (2026-11-03):
   1. DONE: publisherId set to the owner-verified ID
      ca-pub-2895136878543415.
   2. DONE: the exact AdSense loader tag is included directly in the
      <head> of the portal page and every job detail page. This script
      detects that tag and never injects a second copy.
   3. DONE: /ads.txt exists at the gogocompany.in site root with the
      real publisher ID (managed in the gogo-website repository).
   4. DONE (2026-11-03): CONFIG.slots filled with the owner-created
      AdSense units: responsive display 7200569170 on the listing
      page (sarkari-mid), in-article fluid 4574405834 on job detail
      pages (sarkari-detail-bottom).
   5. REMAINING (EEA / UK / Switzerland): ad units stay OFF for those
      regions until a Google-certified CMP (e.g. Funding Choices)
      handles consent. Set cmpReady to true only after that
      integration is verified. */
(function () {
  "use strict";

  var CONFIG = {
    publisherId: "ca-pub-2895136878543415",   /* owner-verified AdSense publisher ID (2026-11-03) */
    cmpReady: false,    /* true only after a Google-certified CMP handles consent */
    slots: {
      "sarkari-mid": "7200569170",           /* listing page: between the category grid and job listings */
      "sarkari-detail-bottom": "4574405834" /* job detail pages: in-article fluid unit, after the article */
    },
    /* Per-slot extra <ins> attributes. The in-article fluid unit
       needs data-ad-format and data-ad-layout-key besides the ID. */
    slotAttrs: {
      "sarkari-detail-bottom": {
        "data-ad-format": "fluid",
        "data-ad-layout-key": "-cs-h+4k-la+cg"
      }
    }
  };

  /* ISO 3166-1 alpha-2 codes for EEA, UK and Switzerland. */
  var CONSENT_REGIONS = ["GB", "IM", "JE", "GG", "AT", "BE", "BG", "HR", "CY", "CZ", "DK",
    "EE", "FI", "FR", "DE", "GR", "HU", "IS", "IE", "IT", "LV", "LI", "LT", "LU", "MT",
    "NL", "NO", "PL", "PT", "RO", "SK", "SI", "ES", "SE", "CH"];

  function regionFromLanguage() {
    var m = (navigator.language || "").match(/[-_]([A-Za-z]{2})$/);
    return m ? m[1].toUpperCase() : "";
  }

  function inConsentRequiredRegion() {
    var r = regionFromLanguage();
    if (r) return CONSENT_REGIONS.indexOf(r) !== -1;
    try {
      return /Europe\/|Atlantic\/(Madeira|Canary)/.test(
        Intl.DateTimeFormat().resolvedOptions().timeZone || ""
      );
    } catch (e) {
      return true; /* cannot tell -> safest default: treat as consent region */
    }
  }

  function adsAllowed() {
    if (!CONFIG.publisherId) return false; /* not configured -> nothing serves */
    if (!CONFIG.cmpReady && inConsentRequiredRegion()) return false;
    return true;
  }

  function activateSlots() {
    var slots = document.querySelectorAll(".ad-slot[hidden]");
    for (var i = 0; i < slots.length; i++) {
      var box = slots[i];
      var slotId = CONFIG.slots[box.getAttribute("data-ad-slot")];
      var ins = box.querySelector("ins.adsbygoogle");
      if (!slotId || !ins) continue;
      ins.setAttribute("data-ad-client", CONFIG.publisherId);
      ins.setAttribute("data-ad-slot", slotId);
      var extra = CONFIG.slotAttrs[box.getAttribute("data-ad-slot")];
      if (extra) {
        for (var k in extra) {
          if (Object.prototype.hasOwnProperty.call(extra, k)) ins.setAttribute(k, extra[k]);
        }
      }
      box.removeAttribute("hidden");
      (window.adsbygoogle = window.adsbygoogle || []).push({});
    }
  }

  function load() {
    if (!adsAllowed()) return;
    if (document.getElementById("sarkari-adsense-lib")) return; /* no duplicate scripts */
    if (document.querySelector('script[src*="adsbygoogle.js?client="]')) {
      /* Static AdSense loader already present in the page head - never inject twice. */
      activateSlots();
      return;
    }

    var s = document.createElement("script");
    s.id = "sarkari-adsense-lib";
    s.async = true;
    s.crossOrigin = "anonymous";
    s.src = "https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=" + CONFIG.publisherId;
    document.head.appendChild(s);
    activateSlots();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", load);
  } else {
    load();
  }
})();
