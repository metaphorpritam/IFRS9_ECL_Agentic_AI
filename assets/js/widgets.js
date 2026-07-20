/*
 * widgets.js — vanilla-JS mini-library for interactive IFRS9 study-notes widgets.
 * No external dependencies. See notes/plan/conventions.md "Widgets" for the
 * usage pattern and notes/assets/widget_demo.html for a worked demo.
 *
 * Exposes window.Widgets = { makeSlider, makeNumberInput, makeLinePlot, makeLiveTable }
 *
 * Convention: every widget is mounted inside a container element (usually a
 * <div class="widget-controls"> for controls, or a plain <div> for a plot /
 * table). Controls call `onInput(value)` on every change — the chapter's own
 * script wires that to a redraw function that recomputes the real formula
 * (Vasicek PD_PIT, ECL, staging shares, …) and calls plot.update(...) /
 * table.update(...).
 */
(function (global) {
  'use strict';

  // ---------------------------------------------------------------------
  // makeSlider — a labeled <input type="range"> with a live value readout.
  // opts: { label, min, max, step, value, format(v)->string, onInput(v) }
  // ---------------------------------------------------------------------
  function makeSlider(container, opts) {
    opts = opts || {};
    var format = opts.format || function (v) { return String(v); };
    var wrap = document.createElement('div');
    wrap.className = 'widget-control';

    var label = document.createElement('label');
    label.textContent = opts.label || '';
    wrap.appendChild(label);

    var input = document.createElement('input');
    input.type = 'range';
    input.min = opts.min;
    input.max = opts.max;
    input.step = opts.step != null ? opts.step : 1;
    input.value = opts.value != null ? opts.value : opts.min;

    var out = document.createElement('span');
    out.className = 'val';
    out.textContent = format(parseFloat(input.value));

    input.addEventListener('input', function () {
      var v = parseFloat(input.value);
      out.textContent = format(v);
      if (typeof opts.onInput === 'function') opts.onInput(v);
    });

    label.appendChild(input);
    label.appendChild(out);
    container.appendChild(wrap);

    return {
      el: input,
      get value() { return parseFloat(input.value); },
      setValue: function (v) {
        input.value = v;
        out.textContent = format(v);
      }
    };
  }

  // ---------------------------------------------------------------------
  // makeNumberInput — a labeled <input type="number">.
  // opts: { label, min, max, step, value, format(v)->string, onInput(v) }
  // ---------------------------------------------------------------------
  function makeNumberInput(container, opts) {
    opts = opts || {};
    var format = opts.format || function (v) { return String(v); };
    var wrap = document.createElement('div');
    wrap.className = 'widget-control';

    var label = document.createElement('label');
    label.textContent = opts.label || '';
    wrap.appendChild(label);

    var input = document.createElement('input');
    input.type = 'number';
    if (opts.min != null) input.min = opts.min;
    if (opts.max != null) input.max = opts.max;
    input.step = opts.step != null ? opts.step : 1;
    input.value = opts.value != null ? opts.value : 0;

    var out = document.createElement('span');
    out.className = 'val';
    out.textContent = format(parseFloat(input.value));

    input.addEventListener('input', function () {
      var v = parseFloat(input.value);
      if (isNaN(v)) return;
      out.textContent = format(v);
      if (typeof opts.onInput === 'function') opts.onInput(v);
    });

    label.appendChild(input);
    label.appendChild(out);
    container.appendChild(wrap);

    return {
      el: input,
      get value() { return parseFloat(input.value); },
      setValue: function (v) {
        input.value = v;
        out.textContent = format(v);
      }
    };
  }

  // ---------------------------------------------------------------------
  // "Nice" tick generation — d3-style, dependency-free.
  // ---------------------------------------------------------------------
  function niceTicks(lo, hi, count) {
    if (lo === hi) return [lo];
    var span = hi - lo;
    var step0 = span / count;
    var mag = Math.pow(10, Math.floor(Math.log10(step0)));
    var frac = step0 / mag;
    var niceFrac = frac >= 7.5 ? 10 : frac >= 3.5 ? 5 : frac >= 1.5 ? 2 : 1;
    var step = niceFrac * mag;
    var start = Math.ceil(lo / step) * step;
    var ticks = [];
    for (var v = start; v <= hi + step * 1e-9; v += step) {
      ticks.push(Math.round(v / step) * step);
    }
    return ticks;
  }

  function fmtNum(v) {
    if (Math.abs(v) >= 100 || v === 0) return String(Math.round(v * 100) / 100);
    var s = Math.round(v * 1000) / 1000;
    return String(s);
  }

  // ---------------------------------------------------------------------
  // makeLinePlot — a lightweight SVG line-plot with axes, ticks, labels.
  // opts: { width, height, xDomain:[lo,hi], yDomain:[lo,hi], xLabel, yLabel,
  //         title, series:[{name,color,points:[[x,y],...]}] }
  // Returns { svg, update(series, newYDomain?) } — update() clears and
  // redraws so the axes always stay correct even when the domain changes.
  // ---------------------------------------------------------------------
  function makeLinePlot(container, opts) {
    opts = opts || {};
    var width = opts.width || 560;
    var height = opts.height || 320;
    var margin = { top: 26, right: 18, bottom: 42, left: 52 };
    var plotW = width - margin.left - margin.right;
    var plotH = height - margin.top - margin.bottom;

    var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 ' + width + ' ' + height);
    svg.setAttribute('width', '100%');
    container.appendChild(svg);

    var xDomain = opts.xDomain || [0, 1];
    var yDomain = opts.yDomain || [0, 1];

    function sx(x) { return margin.left + (x - xDomain[0]) / (xDomain[1] - xDomain[0]) * plotW; }
    function sy(y) { return margin.top + plotH - (y - yDomain[0]) / (yDomain[1] - yDomain[0]) * plotH; }

    function el(tag, attrs, text) {
      var e = document.createElementNS('http://www.w3.org/2000/svg', tag);
      for (var k in attrs) e.setAttribute(k, attrs[k]);
      if (text != null) e.textContent = text;
      return e;
    }

    function render(series, xLabel, yLabel, title) {
      while (svg.firstChild) svg.removeChild(svg.firstChild);

      // Background grid + axes ticks
      var xTicks = niceTicks(xDomain[0], xDomain[1], 6);
      var yTicks = niceTicks(yDomain[0], yDomain[1], 5);

      xTicks.forEach(function (t) {
        svg.appendChild(el('line', {
          x1: sx(t), x2: sx(t), y1: margin.top, y2: margin.top + plotH,
          stroke: '#888', 'stroke-opacity': 0.15
        }));
        svg.appendChild(el('text', {
          x: sx(t), y: margin.top + plotH + 16, 'text-anchor': 'middle', 'font-size': 10.5, fill: '#777'
        }, fmtNum(t)));
      });
      yTicks.forEach(function (t) {
        svg.appendChild(el('line', {
          x1: margin.left, x2: margin.left + plotW, y1: sy(t), y2: sy(t),
          stroke: '#888', 'stroke-opacity': 0.15
        }));
        svg.appendChild(el('text', {
          x: margin.left - 8, y: sy(t) + 3.5, 'text-anchor': 'end', 'font-size': 10.5, fill: '#777'
        }, fmtNum(t)));
      });

      // Axes lines
      svg.appendChild(el('line', { x1: margin.left, x2: margin.left, y1: margin.top, y2: margin.top + plotH, stroke: '#555' }));
      svg.appendChild(el('line', { x1: margin.left, x2: margin.left + plotW, y1: margin.top + plotH, y2: margin.top + plotH, stroke: '#555' }));

      // Axis labels
      if (xLabel) svg.appendChild(el('text', {
        x: margin.left + plotW / 2, y: height - 6, 'text-anchor': 'middle', 'font-size': 12, fill: '#555'
      }, xLabel));
      if (yLabel) svg.appendChild(el('text', {
        x: 14, y: margin.top + plotH / 2, 'text-anchor': 'middle', 'font-size': 12, fill: '#555',
        transform: 'rotate(-90 14 ' + (margin.top + plotH / 2) + ')'
      }, yLabel));
      if (title) svg.appendChild(el('text', {
        x: width / 2, y: 15, 'text-anchor': 'middle', 'font-size': 13, 'font-weight': 'bold', fill: '#333'
      }, title));

      // Series
      (series || []).forEach(function (s) {
        var d = s.points.map(function (p, i) {
          return (i === 0 ? 'M' : 'L') + sx(p[0]).toFixed(2) + ',' + sy(p[1]).toFixed(2);
        }).join(' ');
        svg.appendChild(el('path', { d: d, fill: 'none', stroke: s.color || '#1f3a5f', 'stroke-width': 2 }));
      });

      // Legend (top-right, only if >1 series or explicit names)
      var named = (series || []).filter(function (s) { return s.name; });
      if (named.length) {
        named.forEach(function (s, i) {
          var ly = margin.top + i * 14;
          svg.appendChild(el('line', { x1: width - margin.right - 60, x2: width - margin.right - 42, y1: ly, y2: ly, stroke: s.color || '#1f3a5f', 'stroke-width': 2 }));
          svg.appendChild(el('text', { x: width - margin.right - 38, y: ly + 3.5, 'font-size': 10.5, fill: '#555' }, s.name));
        });
      }
    }

    render(opts.series || [], opts.xLabel, opts.yLabel, opts.title);

    return {
      svg: svg,
      update: function (series, newYDomain, newXDomain) {
        if (newXDomain) xDomain = newXDomain;
        if (newYDomain) yDomain = newYDomain;
        render(series, opts.xLabel, opts.yLabel, opts.title);
      }
    };
  }

  // ---------------------------------------------------------------------
  // makeLiveTable — a small HTML table with an update(rows) refresh.
  // opts: { columns:[{key,label,format(v)->string}], rows:[{...}, ...] }
  // ---------------------------------------------------------------------
  function makeLiveTable(container, opts) {
    opts = opts || {};
    var columns = opts.columns || [];
    var table = document.createElement('table');
    var thead = document.createElement('thead');
    var headRow = document.createElement('tr');
    columns.forEach(function (c) {
      var th = document.createElement('th');
      th.textContent = c.label != null ? c.label : c.key;
      headRow.appendChild(th);
    });
    thead.appendChild(headRow);
    table.appendChild(thead);
    var tbody = document.createElement('tbody');
    table.appendChild(tbody);
    container.appendChild(table);

    function render(rows) {
      tbody.innerHTML = '';
      (rows || []).forEach(function (row) {
        var tr = document.createElement('tr');
        columns.forEach(function (c) {
          var td = document.createElement('td');
          var v = row[c.key];
          td.textContent = c.format ? c.format(v, row) : String(v);
          if (typeof v === 'number') td.className = 'num';
          tr.appendChild(td);
        });
        tbody.appendChild(tr);
      });
    }

    render(opts.rows || []);

    return { el: table, update: render };
  }

  global.Widgets = {
    makeSlider: makeSlider,
    makeNumberInput: makeNumberInput,
    makeLinePlot: makeLinePlot,
    makeLiveTable: makeLiveTable,
    niceTicks: niceTicks
  };
})(window);
