/* Paper to Playground - generic page runtime (DOM glue).
 * Builds the controls declared in the page spec, keeps the learner's state,
 * and on every change calls the generated pure functions:
 *   compute(state) -> result         (all numbers shown on the page)
 *   render(state, result) -> SVG     (the visual)
 *   show(state, result) -> [items]   (intermediate values)
 *   checks(state, result) -> [items] (live invariant checks)
 * Each call is isolated so one failure is reported without breaking the rest.
 * This file is generic: it contains no paper-specific content.
 */
(function () {
  'use strict';
  var specEl = document.getElementById('p2p-spec');
  var SPEC = specEl ? JSON.parse(specEl.textContent) : { controls: [], explorations: [] };
  var CONTROLS = SPEC.controls || [];
  var state = {};

  function $(id) { return document.getElementById(id); }
  /* The generated code may declare its functions with `function` or `const`;
   * only the former become window properties, so resolve names lexically. */
  function fn(name) {
    try { var f = (0, eval)(name); return typeof f === 'function' ? f : null; } catch (e) { return null; }
  }
  var MODEL = { compute: fn('compute'), render: fn('render'), show: fn('show'), checks: fn('checks') };
  function el(tag, cls, html) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html != null) e.innerHTML = html;
    return e;
  }
  function esc(s) { return L.esc(s == null ? '' : s); }
  function decimalsOf(step) {
    var s = String(step == null ? 1 : step);
    return s.indexOf('.') >= 0 ? s.split('.')[1].length : 0;
  }
  function fmtControl(c, v) { return L.fmt(Number(v), Math.max(decimalsOf(c.step), 0)); }

  // ------------------------------------------------------------ dimensions
  function dimValue(d, fallback) {
    if (typeof d === 'number') return Math.max(1, Math.round(d));
    if (typeof d === 'string' && state[d] != null && isFinite(Number(state[d]))) return Math.max(1, Math.round(Number(state[d])));
    return fallback;
  }
  function fillValue(c) { return c.fill != null ? Number(c.fill) : 0; }
  function resizeVector(v, n, fill) {
    v = Array.isArray(v) ? v.slice(0, n) : [];
    while (v.length < n) v.push(fill);
    return v.map(function (x) { return isFinite(Number(x)) ? Number(x) : fill; });
  }
  function resizeMatrix(M, r, c, fill) {
    M = Array.isArray(M) ? M.slice(0, r) : [];
    while (M.length < r) M.push([]);
    return M.map(function (row) { return resizeVector(row, c, fill); });
  }
  function conform(c) {
    if (c.type === 'vector') {
      var n = dimValue(c.length, Array.isArray(c.value) ? c.value.length : 3);
      state[c.id] = resizeVector(state[c.id], n, fillValue(c));
    } else if (c.type === 'matrix') {
      var r0 = Array.isArray(c.value) ? c.value.length : 2, c0 = r0 && Array.isArray(c.value[0]) ? c.value[0].length : 2;
      state[c.id] = resizeMatrix(state[c.id], dimValue(c.rows, r0), dimValue(c.cols, c0), fillValue(c));
    }
  }
  function conformAll() { CONTROLS.forEach(conform); }
  function dependsOn(c, id) { return c.length === id || c.rows === id || c.cols === id; }

  function defaults() {
    var s = {};
    CONTROLS.forEach(function (c) { s[c.id] = L.copy(c.value); });
    return s;
  }
  function labelOf(c) { return c.labelHtml || esc(c.label || c.id); }
  function itemLabel(labels, i, fallback) { return labels && labels[i] != null ? esc(labels[i]) : fallback; }

  // -------------------------------------------------------------- controls
  function numberInput(c, value, onValue, title) {
    var inp = el('input', 'p2p-num');
    inp.type = 'number';
    if (c.min != null) inp.min = c.min;
    if (c.max != null) inp.max = c.max;
    inp.step = c.step != null ? c.step : 'any';
    inp.value = value;
    if (title) inp.title = title;
    inp.addEventListener('input', function () {
      var v = parseFloat(inp.value);
      var ok = isFinite(v) && (c.min == null || v >= c.min) && (c.max == null || v <= c.max);
      inp.classList.toggle('p2p-invalid', !ok);
      if (ok) onValue(v);
    });
    inp.addEventListener('change', function () {
      var v = parseFloat(inp.value);
      if (!isFinite(v)) v = Number(value);
      if (c.min != null) v = Math.max(c.min, v);
      if (c.max != null) v = Math.min(c.max, v);
      inp.value = v;
      inp.classList.remove('p2p-invalid');
      onValue(v);
    });
    return inp;
  }
  function rangeInput(c, value, onValue, readout) {
    var inp = el('input', 'p2p-range');
    inp.type = 'range';
    inp.min = c.min != null ? c.min : 0;
    inp.max = c.max != null ? c.max : 1;
    inp.step = c.step != null ? c.step : 'any';
    inp.value = value;
    inp.addEventListener('input', function () {
      var v = parseFloat(inp.value);
      if (readout) readout.textContent = fmtControl(c, v);
      onValue(v);
    });
    return inp;
  }

  function buildControl(c) {
    var box = el('div', 'p2p-control p2p-control-' + c.type);
    box.setAttribute('data-control', c.id);
    var id = 'p2p-c-' + c.id;
    var v = state[c.id];
    if (c.type === 'range' || c.type === 'number') {
      var head = el('div', 'p2p-control-head');
      var lab = el('label', 'p2p-label', labelOf(c));
      lab.htmlFor = id;
      head.appendChild(lab);
      var inp;
      if (c.type === 'range') {
        var out = el('output', 'p2p-readout', esc(fmtControl(c, v)));
        head.appendChild(out);
        inp = rangeInput(c, v, function (x) { setValue(c, x); }, out);
      } else {
        inp = numberInput(c, v, function (x) { setValue(c, x); });
      }
      inp.id = id;
      box.appendChild(head);
      box.appendChild(inp);
    } else if (c.type === 'toggle') {
      var tl = el('label', 'p2p-toggle');
      var cb = el('input');
      cb.type = 'checkbox';
      cb.id = id;
      cb.checked = !!v;
      cb.addEventListener('change', function () { setValue(c, cb.checked); });
      tl.appendChild(cb);
      tl.appendChild(el('span', 'p2p-label', labelOf(c)));
      box.appendChild(tl);
    } else if (c.type === 'select') {
      var sl = el('label', 'p2p-label', labelOf(c));
      sl.htmlFor = id;
      var sel = el('select', 'p2p-select');
      sel.id = id;
      (c.options || []).forEach(function (o) {
        var ov = typeof o === 'object' ? o.value : o, ol = typeof o === 'object' ? (o.label != null ? o.label : o.value) : o;
        var opt = el('option', null, esc(ol));
        opt.value = JSON.stringify(ov);
        if (JSON.stringify(ov) === JSON.stringify(v)) opt.selected = true;
        sel.appendChild(opt);
      });
      sel.addEventListener('change', function () { setValue(c, JSON.parse(sel.value)); });
      box.appendChild(sl);
      box.appendChild(sel);
    } else if (c.type === 'vector') {
      box.appendChild(el('div', 'p2p-label', labelOf(c)));
      var list = el('div', 'p2p-vector');
      var useSlider = c.widget ? c.widget === 'slider' : (c.min != null && c.max != null);
      v.forEach(function (x, i) {
        var row = el('div', 'p2p-vector-item');
        var name = itemLabel(c.labels, i, String(i + 1));
        row.appendChild(el('span', 'p2p-vector-name', name));
        var setI = function (val) { var arr = state[c.id].slice(); arr[i] = val; setValue(c, arr); };
        if (useSlider) {
          var ro = el('output', 'p2p-readout', esc(fmtControl(c, x)));
          var r = rangeInput(c, x, setI, ro);
          r.setAttribute('aria-label', (c.label || c.id) + ' ' + (c.labels && c.labels[i] != null ? c.labels[i] : i + 1));
          row.appendChild(r);
          row.appendChild(ro);
        } else {
          var n = numberInput(c, x, setI);
          n.setAttribute('aria-label', (c.label || c.id) + ' ' + (i + 1));
          row.appendChild(n);
        }
        list.appendChild(row);
      });
      box.appendChild(list);
    } else if (c.type === 'matrix') {
      box.appendChild(el('div', 'p2p-label', labelOf(c)));
      var table = el('table', 'p2p-matrix-input');
      if (c.colLabels) {
        var hr = el('tr');
        hr.appendChild(el('th'));
        v[0].forEach(function (_, j) { hr.appendChild(el('th', null, itemLabel(c.colLabels, j, ''))); });
        table.appendChild(hr);
      }
      v.forEach(function (rowv, i) {
        var tr = el('tr');
        tr.appendChild(el('th', null, itemLabel(c.rowLabels, i, c.colLabels ? String(i + 1) : '')));
        rowv.forEach(function (x, j) {
          var td = el('td');
          var n = numberInput(c, x, function (val) {
            var M = L.copy(state[c.id]); M[i][j] = val; setValue(c, M);
          }, (c.label || c.id) + ' [' + (i + 1) + ',' + (j + 1) + ']');
          n.setAttribute('aria-label', (c.label || c.id) + ' row ' + (i + 1) + ' column ' + (j + 1));
          td.appendChild(n);
          tr.appendChild(td);
        });
        table.appendChild(tr);
      });
      box.appendChild(table);
    }
    if (c.help) box.appendChild(el('div', 'p2p-help', c.helpHtml || esc(c.help)));
    return box;
  }

  function buildControls() {
    var host = $('p2p-controls');
    if (!host) return;
    host.innerHTML = '';
    CONTROLS.forEach(function (c) { host.appendChild(buildControl(c)); });
  }

  function setValue(c, v) {
    state[c.id] = v;
    var dependents = CONTROLS.filter(function (d) { return dependsOn(d, c.id); });
    if (dependents.length) {
      conformAll();
      dependents.forEach(function (d) {
        var old = document.querySelector('[data-control="' + d.id + '"]');
        if (old) old.parentNode.replaceChild(buildControl(d), old);
      });
    }
    update();
  }

  // -------------------------------------------------------------- outputs
  function cellText(x, digits) { return typeof x === 'number' ? L.fmt(x, digits) : esc(x); }
  function valueHtml(it) {
    var v = it.value, d = it.digits != null ? it.digits : 3;
    if (Array.isArray(v) && v.length && Array.isArray(v[0])) {
      var h = '<table class="p2p-matrix">';
      if (it.colLabels) h += '<tr><th></th>' + v[0].map(function (_, j) { return '<th>' + itemLabel(it.colLabels, j, '') + '</th>'; }).join('') + '</tr>';
      v.forEach(function (row, i) {
        h += '<tr><th>' + itemLabel(it.rowLabels, i, '') + '</th>' + row.map(function (x) { return '<td>' + cellText(x, d) + '</td>'; }).join('') + '</tr>';
      });
      return h + '</table>';
    }
    if (Array.isArray(v)) {
      var t = '<table class="p2p-matrix p2p-vector-out">';
      if (it.colLabels) t += '<tr>' + v.map(function (_, j) { return '<th>' + itemLabel(it.colLabels, j, '') + '</th>'; }).join('') + '</tr>';
      return t + '<tr>' + v.map(function (x) { return '<td>' + cellText(x, d) + '</td>'; }).join('') + '</tr></table>';
    }
    return '<span class="p2p-scalar">' + cellText(v, d) + '</span>';
  }
  function showError(where, err) {
    var box = $('p2p-error');
    if (!box) return;
    box.hidden = false;
    box.appendChild(el('div', null, '<strong>' + esc(where) + ' error:</strong> ' + esc(err && err.message ? err.message : err)));
  }

  function update() {
    var errBox = $('p2p-error');
    if (errBox) { errBox.innerHTML = ''; errBox.hidden = true; }
    if (!MODEL.compute) { showError('Setup', 'interactive code did not load'); return; }
    var result;
    try { result = MODEL.compute(L.copy(state)); } catch (e) { showError('compute', e); return; }
    try {
      var vis = $('p2p-visual');
      if (vis && MODEL.render) vis.innerHTML = MODEL.render(L.copy(state), result);
    } catch (e) { showError('render', e); }
    try {
      var vals = $('p2p-values');
      if (vals && MODEL.show) {
        var items = MODEL.show(L.copy(state), result) || [];
        vals.innerHTML = items.map(function (it) {
          return '<div class="p2p-value' + (it.highlight ? ' p2p-value-hl' : '') + '"><div class="p2p-value-label">' + esc(it.label) + '</div>' +
            '<div class="p2p-value-body">' + valueHtml(it) + '</div>' + (it.note ? '<div class="p2p-value-note">' + esc(it.note) + '</div>' : '') + '</div>';
        }).join('');
      }
    } catch (e) { showError('values', e); }
    try {
      var chk = $('p2p-checks');
      if (chk && MODEL.checks) {
        var cs = MODEL.checks(L.copy(state), result) || [];
        chk.innerHTML = cs.map(function (c) {
          return '<li class="' + (c.pass ? 'p2p-pass' : 'p2p-fail') + '"><span class="p2p-mark" aria-hidden="true">' + (c.pass ? '✓' : '✗') + '</span> ' +
            '<span class="p2p-check-name">' + esc(c.name) + '</span>' + (c.detail != null && c.detail !== '' ? ' <span class="p2p-check-detail">' + esc(c.detail) + '</span>' : '') + '</li>';
        }).join('');
      }
    } catch (e) { showError('checks', e); }
  }

  // ---------------------------------------------------------- explorations
  function applyPreset(i) {
    var ex = (SPEC.explorations || [])[i];
    if (!ex || !ex.preset) return;
    state = defaults();
    Object.keys(ex.preset).forEach(function (k) { if (k in state) state[k] = L.copy(ex.preset[k]); });
    conformAll();
    buildControls();
    update();
    document.querySelectorAll('.p2p-exploration').forEach(function (card, j) { card.classList.toggle('p2p-active', j === i); });
    var pg = $('p2p-playground');
    if (pg && pg.scrollIntoView) pg.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function init() {
    state = defaults();
    conformAll();
    buildControls();
    document.querySelectorAll('[data-p2p-preset]').forEach(function (btn) {
      btn.addEventListener('click', function () { applyPreset(Number(btn.getAttribute('data-p2p-preset'))); });
    });
    var reset = $('p2p-reset');
    if (reset) reset.addEventListener('click', function () {
      state = defaults(); conformAll(); buildControls(); update();
      document.querySelectorAll('.p2p-exploration').forEach(function (card) { card.classList.remove('p2p-active'); });
    });
    update();
    window.P2P = { get state() { return L.copy(state); }, update: update, applyPreset: applyPreset };
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
