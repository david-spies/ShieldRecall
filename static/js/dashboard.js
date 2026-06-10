/**
 * dashboard.js — Shield Recall client-side enhancements.
 *
 * Responsibilities:
 *  - Keyboard accessibility for the toggle switch (Enter / Space)
 *  - HTMX after-settle hooks to update aria-live regions
 *  - Snapshot bar colour sync after HTMX counter updates
 *  - Purge result feedback formatting
 *  - Reduced-motion detection
 */

(function () {
  "use strict";

  // ── Accessibility: toggle via keyboard ──────────────────────────────────
  document.addEventListener("keydown", function (e) {
    const toggle = document.getElementById("recall-toggle");
    if (document.activeElement === toggle && (e.key === "Enter" || e.key === " ")) {
      e.preventDefault();
      toggle.click();
    }
  });

  // ── HTMX: after counter partial swaps, re-colour the snap-counter ────────
  document.body.addEventListener("htmx:afterSwap", function (e) {
    const target = e.detail.target;

    // Snapshot counter colouring
    if (target && target.id === "snap-count") {
      const count = parseInt(target.textContent, 10);
      target.classList.remove("val-teal", "val-amber", "val-red");
      if (count > 150)     target.classList.add("val-red");
      else if (count > 80) target.classList.add("val-amber");
      else                 target.classList.add("val-teal");
    }

    // Purge result prettify
    if (target && target.id === "purge-result") {
      if (target.textContent && !target.textContent.includes("error")) {
        target.style.color = "var(--teal)";
      } else {
        target.style.color = "var(--red)";
      }
    }

    // Danger zone wipe result
    if (target && target.id === "danger-result") {
      target.style.color = "var(--amber)";
    }
  });

  // ── HTMX: show a loading spinner on the counter while polling ───────────
  document.body.addEventListener("htmx:beforeRequest", function (e) {
    const el = e.detail.elt;
    if (el && el.getAttribute("hx-get") === "/api/telemetry/counter") {
      const count = document.getElementById("snap-count");
      if (count) count.style.opacity = "0.6";
    }
  });

  document.body.addEventListener("htmx:afterRequest", function () {
    const count = document.getElementById("snap-count");
    if (count) count.style.opacity = "1";
  });

  // ── Reduced motion: pause any CSS animations ────────────────────────────
  const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
  function handleReducedMotion(mq) {
    document.querySelectorAll(".pulse-dot").forEach(function (dot) {
      dot.style.animationPlayState = mq.matches ? "paused" : "running";
    });
  }
  mq.addEventListener("change", handleReducedMotion);
  handleReducedMotion(mq);

  // ── Auto-dismiss transient banners ──────────────────────────────────────
  document.body.addEventListener("htmx:afterSettle", function () {
    const banners = document.querySelectorAll(".error-banner");
    banners.forEach(function (b) {
      if (!b._timer) {
        b._timer = setTimeout(function () {
          b.style.transition = "opacity .5s";
          b.style.opacity = "0";
          setTimeout(function () { b.remove(); }, 600);
        }, 6000);
      }
    });
  });

  // ── Confirm guard for dangerous hx-confirm actions ──────────────────────
  // HTMX built-in hx-confirm already handles this, but we add a class flash
  // on the button so users see visual feedback even if they cancel.
  document.querySelectorAll("[hx-confirm]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      btn.classList.add("confirming");
      setTimeout(function () { btn.classList.remove("confirming"); }, 1500);
    });
  });

})();
