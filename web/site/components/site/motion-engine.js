/* Motion engine — PORTED VERBATIM from design/mockups/site/index.html (lines 580-786, Tur B).
 *
 * Transcribed, not rewritten: the polish signatures (staged conversation timing, ink-block ride,
 * razor draw, intro curtain, pill auto-hide) are part of the APPROVED visual contract. The only
 * change is the wrapper — the mockup's IIFE becomes an exported function that the React client
 * component calls once on mount. It still reads window.gsap / window.ScrollTrigger and still
 * degrades gracefully if they are absent, so the page works with the animation layer dead.
 */
export function runMotionEngine() {
  'use strict';
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var finePointer = window.matchMedia('(pointer: fine)').matches;
  var docEl = document.documentElement;

  /* ---- staged conversation — time-driven, plays once (reference DCLogic timings) ---- */
  var chatStarted = false;
  function startChat() {
    if (chatStarted) return;
    chatStarted = true;
    var msgs = document.querySelectorAll('.chat-body .msg');
    if (reduced) { // CSS already shows everything; keep DOM state consistent
      msgs.forEach(function (m) { m.classList.add('in'); });
      return;
    }
    function showMsg(step) {
      return function () {
        msgs.forEach(function (m) {
          if (Number(m.getAttribute('data-step')) <= step) m.classList.add('in');
        });
      };
    }
    function typing(step, on) {
      return function () {
        var t = document.querySelector('.typing[data-typing="' + step + '"]');
        if (t) t.classList.toggle('on', on);
      };
    }
    setTimeout(showMsg(1), 500);
    setTimeout(typing(2, true), 1150);
    setTimeout(typing(2, false), 2450);
    setTimeout(showMsg(3), 2450); // W12 confirm lands; the picked 'yes' chip pops via CSS
    setTimeout(showMsg(4), 3400);
    setTimeout(typing(5, true), 4000);
    setTimeout(typing(5, false), 5150);
    setTimeout(showMsg(6), 5150);
  }

  /* ---- intro curtain — the chat waits for the curtain so its opening isn't hidden ---- */
  var intro = document.querySelector('.intro');
  function endIntro() {
    docEl.classList.remove('intro-play');
    if (intro && intro.parentNode) intro.parentNode.removeChild(intro);
    intro = null;
    startChat();
  }
  if (docEl.classList.contains('intro-play')) {
    var introTimer = setTimeout(endIntro, 1180);
    intro.addEventListener('click', function () { clearTimeout(introTimer); endIntro(); });
  } else {
    endIntro();
  }

  /* ---- scroll reveals (menu rows, closer razor) — IO so no scroll-tied layout reads ---- */
  var revealEls = Array.prototype.slice.call(document.querySelectorAll('[data-reveal], .razor-closer'));
  if (reduced || !('IntersectionObserver' in window)) {
    revealEls.forEach(function (el) { el.classList.add('in'); });
  } else {
    var revealIO = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('in');
          revealIO.unobserve(entry.target);
        }
      });
    }, { threshold: 0.15, rootMargin: '0px 0px -6% 0px' });
    revealEls.forEach(function (el) { revealIO.observe(el); });
  }

  /* ---- CTA dedup — FAB yields whenever any section-level CTA is on screen ---- */
  var fab = document.querySelector('.fab');
  var sectionCtas = document.querySelectorAll('[data-secta]');
  if (fab && sectionCtas.length && 'IntersectionObserver' in window) {
    var ctaVisible = new Map();
    var fabIO = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) { ctaVisible.set(entry.target, entry.isIntersecting); });
      var any = false;
      ctaVisible.forEach(function (v) { if (v) any = true; });
      var panelOpen = document.getElementById('site-panel').classList.contains('is-open');
      fab.classList.toggle('is-hidden', any && !panelOpen);
    }, { threshold: 0.35 });
    sectionCtas.forEach(function (el) { fabIO.observe(el); });
  }

  /* ---- SITE WIDGET (Stage 2) — launcher toggle + one-shot staged reveal.
         Enhancement only: with JS off the panel is open and the whole thread is static. ---- */
  var sitePanel = document.getElementById('site-panel');
  var launcher = document.getElementById('widget-launcher');
  var widgetPlayed = false;
  function playWidgetThread() {
    if (widgetPlayed) return;
    widgetPlayed = true;
    var thread = sitePanel.querySelector('.thread');
    var msgs = thread.querySelectorAll('.msg');
    if (reduced) { msgs.forEach(function (m) { m.classList.add('in'); }); return; }
    var t = 350;
    msgs.forEach(function (m) {
      var step = m.getAttribute('data-step');
      var typing = thread.querySelector('.typing[data-typing="' + step + '"]');
      if (typing) {
        (function (ty, on, off) {
          setTimeout(function () { ty.classList.add('on'); }, on);
          setTimeout(function () { ty.classList.remove('on'); }, off);
        })(typing, t, t + 900);
        t += 900;
      }
      (function (mm, at) {
        setTimeout(function () {
          mm.classList.add('in');
          thread.scrollTop = thread.scrollHeight; // keep the newest bubble in view
        }, at);
      })(m, t);
      t += m.classList.contains('user') ? 700 : 900;
    });
  }
  function setWidgetOpen(open) {
    sitePanel.classList.toggle('is-open', open);
    launcher.setAttribute('aria-expanded', open ? 'true' : 'false');
    if (open) playWidgetThread();
  }
  if (sitePanel && launcher) {
    launcher.addEventListener('click', function () {
      setWidgetOpen(!sitePanel.classList.contains('is-open'));
    });
    sitePanel.querySelector('[data-close]').addEventListener('click', function () {
      setWidgetOpen(false);
      launcher.focus();
    });
  }

  /* ---- ink cursor trail — desktop only, idle-init so it never delays the hero ---- */
  function initInkTrail() {
    var canvas = document.querySelector('.ink-canvas');
    if (!canvas) return;
    var ctx = canvas.getContext('2d');
    var points = [];
    function size() { canvas.width = window.innerWidth; canvas.height = window.innerHeight; }
    size();
    window.addEventListener('resize', size);
    window.addEventListener('mousemove', function (e) {
      points.push({ x: e.clientX, y: e.clientY, t: performance.now() });
      if (points.length > 36) points.shift();
    });
    (function draw() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      var now = performance.now();
      while (points.length && now - points[0].t > 620) points.shift();
      if (points.length > 1) {
        ctx.lineJoin = 'round';
        ctx.lineCap = 'round';
        ctx.lineWidth = 1.4;
        for (var i = 1; i < points.length; i++) {
          var age = (now - points[i].t) / 620;
          ctx.strokeStyle = 'rgba(22,21,15,' + ((1 - age) * 0.16).toFixed(3) + ')';
          ctx.beginPath();
          ctx.moveTo(points[i - 1].x, points[i - 1].y);
          ctx.lineTo(points[i].x, points[i].y);
          ctx.stroke();
        }
      }
      requestAnimationFrame(draw);
    })();
  }
  if (!reduced && finePointer) {
    if ('requestIdleCallback' in window) requestIdleCallback(initInkTrail, { timeout: 1500 });
    else setTimeout(initInkTrail, 400);
  }

  /* ---- GSAP / ScrollTrigger — deferred CDN scripts run before DOMContentLoaded,
         so the guards below see the real load result; every path degrades cleanly ---- */
  function initMotionEngine() {
    if (reduced) return;
    // Wheel scrolling stays NATIVE (1:1, no smoothing engine) — a smooth-scroll library
    // intercepts every wheel tick and eases toward the target, which reads as a laggy
    // "limiter" on a long page. Only anchor-link jumps get an eased glide, via native
    // scrollTo({behavior:'smooth'}), honoring each section's scroll-margin-top.
    document.querySelectorAll('a[href^="#"]').forEach(function (a) {
      a.addEventListener('click', function (e) {
        var target = document.querySelector(a.getAttribute('href'));
        if (!target) return;
        e.preventDefault();
        var margin = parseFloat(getComputedStyle(target).scrollMarginTop) || 0;
        var y = target.getBoundingClientRect().top + window.scrollY - margin;
        window.scrollTo({ top: y, behavior: 'smooth' });
        history.pushState(null, '', a.getAttribute('href'));
      });
    });
    if (window.gsap && window.ScrollTrigger) {
      gsap.registerPlugin(ScrollTrigger);
      // ScrollTrigger binds to native scroll by default — no smooth-scroll bridge needed.
      // ink sections ride ~56px (≈8% viewport) into the cream above them — transform only
      document.querySelectorAll('[data-ride]').forEach(function (el) {
        gsap.fromTo(el, { y: 56 }, {
          y: 0,
          ease: 'none',
          scrollTrigger: { trigger: el, start: 'top bottom', end: 'top 15%', scrub: true }
        });
      });
    }
  }
  // React has already mounted the DOM when this runs, so the mockup's readyState guard is not
  // needed — but keeping the same entry point keeps the transcription honest.
  initMotionEngine();
}
