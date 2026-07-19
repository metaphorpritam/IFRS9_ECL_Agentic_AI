/*
 * toc.js — collapsible, scroll-spy left sidebar table of contents for the
 * IFRS9 ECL study-notes pages (notes/index.html + notes/chapters/*.html).
 *
 * Self-contained (own <style> injected at runtime), vanilla JS, no external
 * dependencies. Reads the page's existing h2/h3 headings and existing CSS
 * custom properties (--accent, --boxbg, --rule, --ink, --muted, --page-bg)
 * defined in each page's own <style> block, so it themes itself for both
 * light and dark automatically (prefers-color-scheme + [data-theme]).
 *
 * Does NOT edit page content: reads headings, generates ids only for
 * headings that lack one (never mutates existing ids), and leaves the
 * existing inline top-of-page ".toc" block untouched (adds a body class so
 * CSS can de-emphasize it on wide screens instead).
 *
 * See notes/plan/conventions.md for the wider notes-authoring conventions
 * this file must stay consistent with (theming, box vocabulary, QA gate).
 */
(function () {
  'use strict';

  var BREAKPOINT = 1100;          // px — below this, sidebar is an overlay
  var SIDEBAR_W = 280;            // px — pinned/overlay sidebar width
  var GAP = 24;                   // px — gutter between sidebar and content
  var COLLAPSE_KEY = 'ifrs9-notes-toc-collapsed';

  function ready(fn) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', fn);
    } else {
      fn();
    }
  }

  ready(init);

  function init() {
    var headings = Array.prototype.slice.call(document.querySelectorAll('h2, h3'));
    if (!headings.length) { return; }

    // Pinning the sidebar shifts the whole body right by (SIDEBAR_W + GAP);
    // margin-right is left auto to reclaim the rest, but that reclaimed
    // right-hand margin is only ever >= the margin the page would have had
    // when simply centered (its normal, already-tested layout) once the
    // viewport is wide enough to give BOTH a left margin of that size AND
    // keep the content column at its full, unshrunk width. Below that
    // point, any content that already sits close to the content column's
    // edge (a wide inline SVG/table that doesn't reflow, say) would gain
    // *less* breathing room than it has in the page's normal centered
    // layout and could newly clip off the right edge of the viewport — so
    // the pinned/shifted layout only activates once that's mathematically
    // ruled out; narrower viewports keep the sidebar as a closed-by-default
    // overlay instead (never touches body margins). pageW varies per page
    // (960px chapters, 1120px index.html), so this is computed from each
    // page's own CSS rather than a single hardcoded breakpoint.
    var pinnedAt = Math.max(BREAKPOINT, 2 * (SIDEBAR_W + GAP) + pageContentWidthPx());

    injectStyle(pinnedAt);

    var usedIds = {};
    headings.forEach(function (h) {
      if (!h.id) { h.id = slugify(h.textContent, usedIds); }
      usedIds[h.id] = true;
    });

    var sidebar = buildSidebar(headings);
    document.body.insertBefore(sidebar, document.body.firstChild);

    var toggle = buildToggle();
    document.body.insertBefore(toggle, document.body.firstChild);

    document.body.classList.add('tocjs-ready');

    setupCollapse(toggle, pinnedAt);
    setupScrollSpy(headings, sidebar);
  }

  // -------------------------------------------------------------------
  // Reads the page's own body{max-width:var(--pageW)} (set in each page's
  // <style> block) so the pinned-layout breakpoint can be sized correctly
  // per page instead of assuming one fixed content width for every page.
  // -------------------------------------------------------------------
  function pageContentWidthPx() {
    var mw = parseFloat(window.getComputedStyle(document.body).maxWidth);
    return (isFinite(mw) && mw > 0) ? mw : (BREAKPOINT - SIDEBAR_W - GAP);
  }

  // -------------------------------------------------------------------
  // Slug generation for headings without an id (defensive — every
  // existing chapter/section heading already carries one; this only
  // fires for future headings added without an id).
  // -------------------------------------------------------------------
  function slugify(text, usedIds) {
    var base = (text || '')
      .toLowerCase()
      .trim()
      .replace(/[^a-z0-9\s-]/g, '')
      .replace(/\s+/g, '-')
      .replace(/-+/g, '-')
      .replace(/^-|-$/g, '');
    if (!base) { base = 'section'; }
    var slug = 'toc-' + base;
    var n = 2;
    while (usedIds[slug] || document.getElementById(slug)) {
      slug = 'toc-' + base + '-' + n;
      n += 1;
    }
    return slug;
  }

  // -------------------------------------------------------------------
  // Sidebar construction
  // -------------------------------------------------------------------
  function buildSidebar(headings) {
    var nav = document.createElement('nav');
    nav.id = 'toc-sidebar';
    nav.setAttribute('aria-label', 'Table of contents');

    var h1 = document.querySelector('h1');
    var title = document.createElement('div');
    title.id = 'toc-sidebar-title';
    title.textContent = h1 ? h1.textContent.replace(/\s+/g, ' ').trim() : 'Contents';
    nav.appendChild(title);

    if (/\/chapters\//.test(window.location.pathname)) {
      var home = document.createElement('a');
      home.id = 'toc-sidebar-home';
      home.href = '../index.html';
      home.textContent = '← All chapters';
      nav.appendChild(home);
    }

    var rootList = document.createElement('ul');
    rootList.className = 'toc-sb-list';
    nav.appendChild(rootList);

    var currentH2Item = null;
    var currentH2Sub = null;

    headings.forEach(function (h) {
      var li = document.createElement('li');
      var a = document.createElement('a');
      a.href = '#' + h.id;
      a.textContent = h.textContent.replace(/\s+/g, ' ').trim();
      a.dataset.tocTarget = h.id;
      li.appendChild(a);

      if (h.tagName === 'H2') {
        rootList.appendChild(li);
        currentH2Item = li;
        currentH2Sub = null;
      } else {
        // h3 — nest under the most recent h2, if any; otherwise fall back
        // to the root list so no heading is ever left un-navigable.
        if (currentH2Item) {
          if (!currentH2Sub) {
            currentH2Sub = document.createElement('ul');
            currentH2Sub.className = 'toc-sb-sublist';
            currentH2Item.appendChild(currentH2Sub);
          }
          currentH2Sub.appendChild(li);
        } else {
          rootList.appendChild(li);
        }
      }
    });

    return nav;
  }

  function buildToggle() {
    var btn = document.createElement('button');
    btn.id = 'toc-toggle';
    btn.type = 'button';
    btn.title = 'Toggle table of contents';
    btn.setAttribute('aria-label', 'Toggle table of contents');
    btn.setAttribute('aria-controls', 'toc-sidebar');
    btn.innerHTML = '&#9776;';
    return btn;
  }

  // -------------------------------------------------------------------
  // Collapse / expand + persistence
  // -------------------------------------------------------------------
  function setupCollapse(toggle, pinnedAt) {
    function isWide() { return window.innerWidth >= pinnedAt; }

    function storedPref() {
      var v = null;
      try { v = window.localStorage.getItem(COLLAPSE_KEY); } catch (e) { /* ignore */ }
      return v; // 'true' | 'false' | null
    }

    function apply(open) {
      document.body.classList.toggle('toc-open', open);
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    }

    var pref = storedPref();
    var open = pref === null ? isWide() : pref === 'false';
    apply(open);

    toggle.addEventListener('click', function () {
      var nowOpen = !document.body.classList.contains('toc-open');
      apply(nowOpen);
      try { window.localStorage.setItem(COLLAPSE_KEY, nowOpen ? 'false' : 'true'); } catch (e) { /* ignore */ }
    });

    // Visitors who never explicitly toggled get a viewport-appropriate
    // default even if they resize across the breakpoint mid-session.
    window.addEventListener('resize', function () {
      if (storedPref() !== null) { return; }
      apply(isWide());
    });
  }

  // -------------------------------------------------------------------
  // Active-section highlighting (IntersectionObserver scroll-spy) +
  // keeping the active sidebar entry scrolled into view.
  // -------------------------------------------------------------------
  function setupScrollSpy(headings, sidebar) {
    var linkFor = {};
    headings.forEach(function (h) {
      var a = sidebar.querySelector('a[data-toc-target="' + cssEscape(h.id) + '"]');
      if (a) { linkFor[h.id] = a; }
    });

    var activeLink = null;
    function setActive(id) {
      var link = linkFor[id];
      if (!link || link === activeLink) { return; }
      if (activeLink) { activeLink.classList.remove('active'); }
      link.classList.add('active');
      activeLink = link;
      if (typeof link.scrollIntoView === 'function') {
        link.scrollIntoView({ block: 'nearest' });
      }
    }

    if (!('IntersectionObserver' in window)) {
      if (headings[0]) { setActive(headings[0].id); }
      return;
    }

    // Thin band near the top of the viewport: a heading is "active" while
    // it sits inside that band, which reads naturally as "the section I'm
    // currently reading" while scrolling either direction.
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) { setActive(entry.target.id); }
      });
    }, { rootMargin: '0px 0px -80% 0px', threshold: 0 });

    headings.forEach(function (h) { observer.observe(h); });

    if (headings[0]) { setActive(headings[0].id); }
  }

  function cssEscape(s) {
    if (window.CSS && window.CSS.escape) { return window.CSS.escape(s); }
    return String(s).replace(/[^a-zA-Z0-9_-]/g, '\\$&');
  }

  // -------------------------------------------------------------------
  // Styles — injected here (not in the chapter HTML) so the patcher stays
  // a one-line insert. Uses the page's own CSS custom properties so both
  // themes (prefers-color-scheme + [data-theme] override) work for free.
  // -------------------------------------------------------------------
  function injectStyle(pinnedAt) {
    var css = ''
      + '#toc-sidebar{position:fixed;top:0;left:0;height:100vh;width:' + SIDEBAR_W + 'px;'
      + 'overflow-y:auto;overflow-x:hidden;box-sizing:border-box;'
      + 'background:var(--boxbg,#f7f5ee);border-right:1px solid var(--rule,#c8c8c8);'
      + 'padding:56px 14px 40px;font-size:12.8px;line-height:1.35;z-index:40;'
      + 'transform:translateX(-100%);transition:transform .18s ease;'
      + 'box-shadow:2px 0 10px rgba(0,0,0,0.18);}'
      + 'body.toc-open #toc-sidebar{transform:translateX(0);}'
      + '#toc-sidebar-title{font-weight:700;color:var(--accent,#1f3a5f);'
      + 'font-size:13.5px;margin:0 0 10px 0;padding-bottom:8px;'
      + 'border-bottom:1px solid var(--rule,#c8c8c8);}'
      + '#toc-sidebar-home{display:block;color:var(--muted,#4a4a4a);'
      + 'text-decoration:none;font-size:12px;margin-bottom:10px;}'
      + '#toc-sidebar-home:hover{color:var(--accent-soft,#2e5a94);text-decoration:underline;}'
      + 'ul.toc-sb-list,ul.toc-sb-sublist{list-style:none;margin:0;padding:0;}'
      + 'ul.toc-sb-sublist{padding-left:12px;margin-top:2px;}'
      + '#toc-sidebar li{margin:0;}'
      + '#toc-sidebar a{display:block;padding:4px 6px;margin:1px 0;border-radius:3px;'
      + 'color:var(--ink,#1a1a1a);text-decoration:none;border-left:3px solid transparent;'
      + 'overflow-wrap:break-word;}'
      + 'ul.toc-sb-sublist a{color:var(--muted,#4a4a4a);font-size:12px;}'
      + '#toc-sidebar a:hover{background:var(--noteBg,#eef3fb);color:var(--accent-soft,#2e5a94);}'
      + '#toc-sidebar a.active{border-left-color:var(--accent,#1f3a5f);'
      + 'background:var(--noteBg,#eef3fb);color:var(--accent,#1f3a5f);font-weight:600;}'
      + '#toc-toggle{position:fixed;top:14px;left:14px;z-index:60;'
      + 'width:34px;height:34px;border-radius:50%;'
      + 'border:1px solid var(--rule,#c8c8c8);background:var(--boxbg,#f7f5ee);'
      + 'color:var(--ink,#1a1a1a);font-size:15px;cursor:pointer;'
      + 'box-shadow:0 2px 8px rgba(0,0,0,0.15);'
      + 'display:flex;align-items:center;justify-content:center;}'
      + '#toc-toggle:hover{border-color:var(--accent-soft,#2e5a94);}'
      + '@media (min-width:' + pinnedAt + 'px){'
      + 'body.toc-open{margin-left:' + (SIDEBAR_W + GAP) + 'px !important;margin-right:auto !important;}'
      + 'body.tocjs-ready .toc{opacity:.55;transition:opacity .15s ease;}'
      + 'body.tocjs-ready .toc:hover,body.tocjs-ready .toc:focus-within{opacity:1;}'
      + '}'
      + '@media print{#toc-sidebar,#toc-toggle{display:none !important;}'
      + 'body.toc-open{margin-left:auto !important;}}';

    var style = document.createElement('style');
    style.id = 'toc-sidebar-style';
    style.appendChild(document.createTextNode(css));
    document.head.appendChild(style);
  }
})();
