/* Paper to Playground - generic helper library "PG".
 * Pure functions only (no DOM): math utilities, number formatting and SVG
 * string builders. Loaded into every generated page and into the V8 checker,
 * so generated compute()/render() code behaves identically in both places.
 * This file is generic: it contains no paper-specific content.
 */
var PG = (function () {
  'use strict';
  var L = {};

  // ------------------------------------------------------------------ math
  L.isNum = function (x) { return typeof x === 'number' && isFinite(x); };
  L.range = function (n) { var a = []; for (var i = 0; i < n; i++) a.push(i); return a; };
  L.linspace = function (a, b, n) {
    if (n < 2) return [a];
    var s = (b - a) / (n - 1);
    return L.range(n).map(function (i) { return a + i * s; });
  };
  L.sum = function (a) { var s = 0; for (var i = 0; i < a.length; i++) s += a[i]; return s; };
  L.mean = function (a) { return a.length ? L.sum(a) / a.length : NaN; };
  L.max = function (a) { var m = -Infinity; for (var i = 0; i < a.length; i++) if (a[i] > m) m = a[i]; return m; };
  L.min = function (a) { var m = Infinity; for (var i = 0; i < a.length; i++) if (a[i] < m) m = a[i]; return m; };
  L.argmax = function (a) { var k = 0; for (var i = 1; i < a.length; i++) if (a[i] > a[k]) k = i; return k; };
  L.argmin = function (a) { var k = 0; for (var i = 1; i < a.length; i++) if (a[i] < a[k]) k = i; return k; };
  L.clamp = function (x, lo, hi) { return Math.min(hi, Math.max(lo, x)); };
  L.round = function (x, d) { var f = Math.pow(10, d == null ? 3 : d); return Math.round(x * f) / f; };
  L.log2 = function (x) { return Math.log(x) / Math.LN2; };
  L.copy = function (x) { return JSON.parse(JSON.stringify(x)); };
  L.zeros = function (r, c) {
    if (c == null) return L.range(r).map(function () { return 0; });
    return L.range(r).map(function () { return L.range(c).map(function () { return 0; }); });
  };
  L.dot = function (a, b) { var s = 0; for (var i = 0; i < a.length; i++) s += a[i] * b[i]; return s; };
  L.transpose = function (A) {
    if (!A.length) return [];
    return A[0].map(function (_, j) { return A.map(function (row) { return row[j]; }); });
  };
  L.matmul = function (A, B) {
    var Bt = L.transpose(B);
    return A.map(function (row) { return Bt.map(function (col) { return L.dot(row, col); }); });
  };
  L.matvec = function (A, v) { return A.map(function (row) { return L.dot(row, v); }); };
  L.mapM = function (A, f) { return A.map(function (row, i) { return row.map(function (x, j) { return f(x, i, j); }); }); };
  L.softmax = function (a, T) {
    T = T == null ? 1 : T;
    var m = L.max(a);
    var e = a.map(function (x) { return Math.exp((x - m) / T); });
    var s = L.sum(e);
    return e.map(function (x) { return x / s; });
  };
  /* Rescale non-negative weights to sum to 1. Returns all zeros if the sum is 0. */
  L.normalize = function (a) {
    var s = L.sum(a);
    return a.map(function (x) { return s > 0 ? x / s : 0; });
  };

  // ------------------------------------------------------------ formatting
  /* Format a number for display: d decimals, trailing zeros removed,
   * exponential notation for very small / very large magnitudes. */
  L.fmt = function (x, d) {
    d = d == null ? 3 : d;
    if (typeof x === 'boolean') return x ? 'true' : 'false';
    if (typeof x !== 'number') return String(x);
    if (isNaN(x)) return 'NaN';
    if (!isFinite(x)) return x > 0 ? '∞' : '-∞';
    var ax = Math.abs(x);
    if (ax !== 0 && (ax < Math.pow(10, -d) || ax >= 1e6)) return x.toExponential(Math.max(1, d - 1));
    var s = x.toFixed(d);
    if (s.indexOf('.') >= 0) s = s.replace(/0+$/, '').replace(/\.$/, '');
    if (s === '-0') s = '0';
    return s;
  };
  L.esc = function (s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  };

  /* Plain-text rendering of $TeX$ segments (SVG text and runtime labels
   * cannot show MathML): Greek letters, accents, sub/superscripts, fractions. */
  var SUB = { '0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄', '5': '₅', '6': '₆', '7': '₇', '8': '₈', '9': '₉', '+': '₊', '-': '₋', '=': '₌', '(': '₍', ')': '₎',
    a: 'ₐ', e: 'ₑ', o: 'ₒ', x: 'ₓ', h: 'ₕ', k: 'ₖ', l: 'ₗ', m: 'ₘ', n: 'ₙ', p: 'ₚ', s: 'ₛ', t: 'ₜ', i: 'ᵢ', j: 'ⱼ', r: 'ᵣ', u: 'ᵤ', v: 'ᵥ' };
  var SUP = { '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴', '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹', '+': '⁺', '-': '⁻', '=': '⁼', '(': '⁽', ')': '⁾',
    n: 'ⁿ', i: 'ⁱ', T: 'ᵀ', t: 'ᵗ', k: 'ᵏ', '⊤': 'ᵀ' };
  var SYM = { alpha: 'α', beta: 'β', gamma: 'γ', delta: 'δ', epsilon: 'ϵ', varepsilon: 'ε', zeta: 'ζ', eta: 'η', theta: 'θ', iota: 'ι', kappa: 'κ',
    lambda: 'λ', mu: 'μ', nu: 'ν', xi: 'ξ', pi: 'π', rho: 'ρ', sigma: 'σ', tau: 'τ', phi: 'ϕ', varphi: 'φ', chi: 'χ', psi: 'ψ', omega: 'ω',
    Gamma: 'Γ', Delta: 'Δ', Theta: 'Θ', Lambda: 'Λ', Xi: 'Ξ', Pi: 'Π', Sigma: 'Σ', Phi: 'Φ', Psi: 'Ψ', Omega: 'Ω', ell: 'ℓ',
    cdot: '·', times: '×', div: '÷', pm: '±', le: '≤', leq: '≤', ge: '≥', geq: '≥', ne: '≠', neq: '≠', approx: '≈', equiv: '≡', sim: '∼',
    propto: '∝', to: '→', rightarrow: '→', leftarrow: '←', infty: '∞', partial: '∂', nabla: '∇', sum: 'Σ', prod: 'Π', int: '∫', in: '∈',
    top: '⊤', ldots: '…', cdots: '⋯', dots: '…', mid: '|', odot: '⊙', otimes: '⊗', circ: '∘', quad: ' ', qquad: '  ' };
  function script(s, map, mark) {
    var ch = Array.from(s);
    if (ch.length && ch.every(function (c) { return map[c]; })) return ch.map(function (c) { return map[c]; }).join('');
    return mark + (ch.length > 1 ? '(' + s + ')' : s);
  }
  function texToPlain(t) {
    t = t.replace(/\\(?:mathrm|text|textrm|mathbf|mathit|boldsymbol|operatorname|mathsf)\{([^{}]*)\}/g, '$1');
    t = t.replace(/\\left|\\right|\\big|\\Big|\\displaystyle/g, '');
    t = t.replace(/\\([A-Za-z]+)/g, function (m, n) { return SYM[n] != null ? SYM[n] : m; });
    t = t.replace(/\\(?:hat|widehat)\{(.)\}/g, '$1̂').replace(/\\(?:bar|overline)\{(.)\}/g, '$1̄')
      .replace(/\\(?:tilde|widetilde)\{(.)\}/g, '$1̃').replace(/\\vec\{(.)\}/g, '$1⃗').replace(/\\dot\{(.)\}/g, '$1̇');
    for (var pass = 0, prev = ''; pass < 4 && prev !== t; pass++) {  /* inner groups first, e.g. \frac{1}{\sqrt{d}} */
      prev = t;
      t = t.replace(/\\sqrt\{([^{}]*)\}/g, function (m, a) { return '√' + (a.length > 1 ? '(' + a + ')' : a); });
      t = t.replace(/\\frac\{([^{}]*)\}\{([^{}]*)\}/g, function (m, a, b) { return (a.length > 1 ? '(' + a + ')' : a) + '/' + (b.length > 1 ? '(' + b + ')' : b); });
    }
    t = t.replace(/_\{([^{}]*)\}|_([^\s{}\\])/g, function (m, a, b) { return script(a != null ? a : b, SUB, '_'); });
    t = t.replace(/\^\{([^{}]*)\}|\^([^\s{}\\])/g, function (m, a, b) { return script(a != null ? a : b, SUP, '^'); });
    t = t.replace(/\\([,;:! ])/g, ' ').replace(/\\([A-Za-z]+)/g, '$1');
    return t.replace(/[{}]/g, '').replace(/\\/g, '');
  }
  L.plain = function (s) {
    s = String(s == null ? '' : s);
    return s.indexOf('$') < 0 ? s : s.replace(/\$([^$]+)\$/g, function (m, t) { return texToPlain(t); });
  };

  // ----------------------------------------------------------------- colors
  var PALETTE = ['#0072B2', '#E69F00', '#009E73', '#D55E00', '#CC79A7', '#56B4E9', '#8C6D1F', '#555555'];
  L.color = function (i) { return PALETTE[((i % PALETTE.length) + PALETTE.length) % PALETTE.length]; };
  function mix(c1, c2, t) {
    t = L.clamp(isFinite(t) ? t : 0, 0, 1);
    var r = Math.round(c1[0] + (c2[0] - c1[0]) * t), g = Math.round(c1[1] + (c2[1] - c1[1]) * t),
      b = Math.round(c1[2] + (c2[2] - c1[2]) * t);
    return 'rgb(' + r + ',' + g + ',' + b + ')';
  }
  /* Sequential color for t in [0,1] (light -> dark blue). */
  L.heat = function (t) { return mix([239, 245, 252], [8, 69, 148], t); };
  /* Diverging color for t in [-1,1] (red <- white -> blue). */
  L.diverge = function (t) {
    t = L.clamp(isFinite(t) ? t : 0, -1, 1);
    return t < 0 ? mix([255, 255, 255], [202, 0, 32], -t) : mix([255, 255, 255], [5, 113, 176], t);
  };
  function isDark(rgb) {
    var m = /rgb\((\d+),(\d+),(\d+)\)/.exec(rgb);
    if (!m) return false;
    return 0.299 * m[1] + 0.587 * m[2] + 0.114 * m[3] < 140;
  }

  // -------------------------------------------------------------- svg basics
  function attrs(o) {
    var s = '';
    for (var k in o) {
      if (o[k] === undefined || o[k] === null || o[k] === false) continue;
      s += ' ' + k + '="' + L.esc(o[k]) + '"';
    }
    return s;
  }
  function num(x) { return isFinite(x) ? Math.round(x * 100) / 100 : 0; }

  /* Wrap a body in a responsive <svg> with the given viewBox size. */
  L.svg = function (w, h, body, o) {
    o = o || {};
    return '<svg xmlns="http://www.w3.org/2000/svg" class="p2p-svg" viewBox="0 0 ' + num(w) + ' ' + num(h) +
      '" width="100%" style="max-width:' + num(w) + 'px;font-family:inherit" role="img"' +
      (o.title ? ' aria-label="' + L.esc(o.title) + '"' : '') + '>' +
      (o.title ? '<title>' + L.esc(o.title) + '</title>' : '') + body + '</svg>';
  };
  L.g = function (body, o) { o = o || {}; return '<g' + attrs({ transform: o.transform, opacity: o.opacity }) + '>' + body + '</g>'; };
  L.text = function (x, y, str, o) {
    o = o || {};
    var tr = o.rotate ? 'rotate(' + o.rotate + ' ' + num(x) + ' ' + num(y) + ')' : null;
    return '<text' + attrs({
      x: num(x), y: num(y), 'font-size': o.size || 13, 'text-anchor': o.anchor || 'start',
      'dominant-baseline': o.baseline || null, fill: o.color || '#1f2933',
      'font-weight': o.weight || null, 'font-style': o.italic ? 'italic' : null, transform: tr, class: o.cls || null
    }) + '>' + L.esc(L.plain(str)) + '</text>';
  };
  L.line = function (x1, y1, x2, y2, o) {
    o = o || {};
    return '<line' + attrs({
      x1: num(x1), y1: num(y1), x2: num(x2), y2: num(y2), stroke: o.color || '#52606d',
      'stroke-width': o.width || 1.5, 'stroke-dasharray': o.dash || null, opacity: o.opacity
    }) + '/>';
  };
  L.rect = function (x, y, w, h, o) {
    o = o || {};
    return '<rect' + attrs({
      x: num(x), y: num(y), width: num(Math.max(0, w)), height: num(Math.max(0, h)), rx: o.rx || null,
      fill: o.fill || 'none', stroke: o.stroke || null, 'stroke-width': o.stroke ? (o.width || 1) : null,
      opacity: o.opacity
    }) + '/>';
  };
  L.circle = function (cx, cy, r, o) {
    o = o || {};
    return '<circle' + attrs({
      cx: num(cx), cy: num(cy), r: num(Math.max(0, r)), fill: o.fill || '#0072B2', stroke: o.stroke || null,
      'stroke-width': o.stroke ? (o.width || 1) : null, opacity: o.opacity
    }) + '/>';
  };
  L.path = function (d, o) {
    o = o || {};
    return '<path' + attrs({
      d: d, fill: o.fill || 'none', stroke: o.color || '#0072B2', 'stroke-width': o.width || 2,
      'stroke-dasharray': o.dash || null, opacity: o.opacity
    }) + '/>';
  };
  /* Polyline through [[x,y],...]; non-finite points break the line. */
  L.polyline = function (pts, o) {
    var d = '', pen = false;
    for (var i = 0; i < pts.length; i++) {
      var p = pts[i];
      if (!p || !isFinite(p[0]) || !isFinite(p[1])) { pen = false; continue; }
      d += (pen ? 'L' : 'M') + num(p[0]) + ' ' + num(p[1]) + ' ';
      pen = true;
    }
    return d ? L.path(d.trim(), o) : '';
  };
  /* Straight arrow with a filled head (no <marker> ids needed). */
  L.arrow = function (x1, y1, x2, y2, o) {
    o = o || {};
    var c = o.color || '#52606d', hs = o.head || 8, ang = Math.atan2(y2 - y1, x2 - x1);
    var bx = x2 - hs * Math.cos(ang), by = y2 - hs * Math.sin(ang);
    var p1 = [bx + hs * 0.5 * Math.sin(ang), by - hs * 0.5 * Math.cos(ang)];
    var p2 = [bx - hs * 0.5 * Math.sin(ang), by + hs * 0.5 * Math.cos(ang)];
    var s = L.line(x1, y1, bx, by, { color: c, width: o.width || 1.5, dash: o.dash }) +
      '<polygon points="' + num(x2) + ',' + num(y2) + ' ' + num(p1[0]) + ',' + num(p1[1]) + ' ' +
      num(p2[0]) + ',' + num(p2[1]) + '" fill="' + L.esc(c) + '"/>';
    if (o.label) s += L.text((x1 + x2) / 2, (y1 + y2) / 2 - 6, o.label, { anchor: 'middle', size: o.size || 12, color: c });
    return s;
  };
  /* Legend items [{label,color}] laid out vertically from (x,y). */
  L.legend = function (x, y, items, o) {
    o = o || {};
    return items.map(function (it, i) {
      var yy = y + i * (o.gap || 18);
      return L.rect(x, yy - 6, 12, 12, { fill: it.color || L.color(i), rx: 2 }) +
        L.text(x + 18, yy, it.label, { size: o.size || 12, baseline: 'middle' });
    }).join('');
  };

  /* "Nice" tick values covering [a,b]. */
  L.ticks = function (a, b, n) {
    n = n || 5;
    if (!isFinite(a) || !isFinite(b)) return [];
    if (a === b) return [a];
    if (a > b) { var t = a; a = b; b = t; }
    var raw = (b - a) / Math.max(1, n - 1), mag = Math.pow(10, Math.floor(Math.log10(raw))), r = raw / mag;
    var step = (r <= 1 ? 1 : r <= 2 ? 2 : r <= 2.5 ? 2.5 : r <= 5 ? 5 : 10) * mag;
    var out = [];
    for (var v = Math.ceil(a / step - 1e-9) * step; v <= b + step * 1e-9; v += step) out.push(Math.abs(v) < step * 1e-9 ? 0 : v);
    return out;
  };
  L.scale = function (d0, d1, r0, r1) {
    return function (v) { return d1 === d0 ? (r0 + r1) / 2 : r0 + (v - d0) * (r1 - r0) / (d1 - d0); };
  };

  // ----------------------------------------------------------------- charts
  /* Bar chart inside box {x,y,w,h}. Handles negative values (baseline at 0).
   * o: values, labels, min, max, colors (array) | color, highlight (index or
   * array of indices), title, yLabel, fmt(v), showValues (default true),
   * refLines [{value,label,color}]. */
  L.bars = function (o) {
    var x = o.x || 0, y = o.y || 0, w = o.w || 320, h = o.h || 200, vals = o.values || [], n = vals.length;
    var fmt = o.fmt || function (v) { return L.fmt(v, 3); };
    var fin = vals.filter(isFinite);
    var lo = o.min != null ? o.min : Math.min(0, fin.length ? L.min(fin) : 0);
    var hi = o.max != null ? o.max : Math.max(0, fin.length ? L.max(fin) : 1);
    if (hi === lo) hi = lo + 1;
    var top = y + (o.title ? 22 : 6) + 16, bottom = y + h - (o.labels ? 22 : 6), left = x + (o.yLabel ? 46 : 34), right = x + w - 4;
    var sy = L.scale(lo, hi, bottom, top), s = '';
    if (o.title) s += L.text(x + w / 2, y + 14, o.title, { anchor: 'middle', size: 13, weight: 600 });
    if (o.yLabel) s += L.text(x + 11, (top + bottom) / 2, o.yLabel, { anchor: 'middle', size: 12, rotate: -90 });
    L.ticks(lo, hi, 4).forEach(function (t) {
      s += L.line(left, sy(t), right, sy(t), { color: '#e4e7eb', width: 1 }) +
        L.text(left - 4, sy(t), L.fmt(t, 3), { anchor: 'end', size: 10, baseline: 'middle', color: '#616e7c' });
    });
    var bw = (right - left) / Math.max(1, n), hl = o.highlight == null ? [] : [].concat(o.highlight);
    vals.forEach(function (v, i) {
      var bx = left + i * bw + bw * 0.15, bwi = bw * 0.7, vv = isFinite(v) ? L.clamp(v, lo, hi) : 0;
      var y0 = sy(L.clamp(0, lo, hi)), y1 = sy(vv), col = o.colors ? o.colors[i % o.colors.length] : (o.color || L.color(0));
      s += L.rect(bx, Math.min(y0, y1), bwi, Math.abs(y1 - y0), { fill: col, stroke: hl.indexOf(i) >= 0 ? '#1f2933' : null, width: 2, rx: 2 });
      if (o.showValues !== false) s += L.text(bx + bwi / 2, v >= 0 ? Math.min(y0, y1) - 4 : Math.max(y0, y1) + 12, isFinite(v) ? fmt(v) : String(v), { anchor: 'middle', size: 11 });
      if (o.labels) s += L.text(bx + bwi / 2, bottom + 15, o.labels[i] == null ? '' : o.labels[i], { anchor: 'middle', size: 12 });
    });
    s += L.line(left, sy(L.clamp(0, lo, hi)), right, sy(L.clamp(0, lo, hi)), { color: '#52606d', width: 1 });
    (o.refLines || []).forEach(function (r) {
      if (!isFinite(r.value)) return;
      var yy = sy(L.clamp(r.value, lo, hi));
      s += L.line(left, yy, right, yy, { color: r.color || '#D55E00', dash: '5 3', width: 1.5 });
      if (r.label) s += L.text(right, yy - 4, r.label, { anchor: 'end', size: 11, color: r.color || '#D55E00' });
    });
    return s;
  };

  /* Matrix heatmap inside box {x,y,w,h} with optional row/column labels.
   * o: matrix, rowLabels, colLabels, title, min, max, fmt(v), showValues,
   * highlight [[i,j],...]. Diverging colors when the range spans zero. */
  L.heatmap = function (o) {
    var M = o.matrix || [[]], rows = M.length, cols = rows ? M[0].length : 0;
    var x = o.x || 0, y = o.y || 0, w = o.w || 240, h = o.h || 200;
    var fmt = o.fmt || function (v) { return L.fmt(v, 2); };
    var flat = [].concat.apply([], M).filter(isFinite);
    var lo = o.min != null ? o.min : (flat.length ? L.min(flat) : 0), hi = o.max != null ? o.max : (flat.length ? L.max(flat) : 1);
    var div = lo < 0 && hi > 0, amax = Math.max(Math.abs(lo), Math.abs(hi)) || 1;
    var topH = (o.title ? 20 : 0) + (o.colLabels ? 18 : 0), leftW = o.rowLabels ? 40 : 0;
    var cell = Math.max(8, Math.min((w - leftW) / Math.max(1, cols), (h - topH) / Math.max(1, rows)));
    var s = '', gx = x + leftW, gy = y + topH, hl = o.highlight || [];
    if (o.title) s += L.text(gx + cols * cell / 2, y + 13, o.title, { anchor: 'middle', size: 13, weight: 600 });
    for (var j = 0; j < cols && o.colLabels; j++) s += L.text(gx + (j + 0.5) * cell, gy - 5, o.colLabels[j] == null ? '' : o.colLabels[j], { anchor: 'middle', size: 11, color: '#616e7c' });
    for (var i = 0; i < rows; i++) {
      if (o.rowLabels) s += L.text(gx - 5, gy + (i + 0.5) * cell, o.rowLabels[i] == null ? '' : o.rowLabels[i], { anchor: 'end', size: 11, baseline: 'middle', color: '#616e7c' });
      for (var k = 0; k < cols; k++) {
        var v = M[i][k], fill = !isFinite(v) ? '#f8d7da' : div ? L.diverge(v / amax) : L.heat(hi === lo ? 0.5 : (v - lo) / (hi - lo));
        var isH = hl.some(function (p) { return p[0] === i && p[1] === k; });
        s += L.rect(gx + k * cell, gy + i * cell, cell - 2, cell - 2, { fill: fill, stroke: isH ? '#1f2933' : '#ffffff', width: isH ? 2.5 : 1, rx: 3 });
        if (o.showValues !== false && cell >= 22) s += L.text(gx + k * cell + (cell - 2) / 2, gy + i * cell + (cell - 2) / 2, isFinite(v) ? fmt(v) : String(v), { anchor: 'middle', baseline: 'middle', size: Math.min(13, cell / 3.2), color: isDark(fill) ? '#ffffff' : '#1f2933' });
      }
    }
    return s;
  };

  /* Line/scatter plot inside box {x,y,w,h}.
   * o: series [{points:[[x,y],...], label, color, dash, width, dots}],
   * xDomain [a,b], yDomain [a,b] (auto if omitted), xLabel, yLabel, title,
   * markers [{x,y,label,color,r}], vlines [{x,label,color}], hlines [{y,label,color}],
   * legend (default true when any series has a label). Returns an SVG
   * fragment string. L.plotScales(o) with the same options returns the
   * {sx, sy} functions that map data coordinates to pixels. */
  L.plotScales = function (o) {
    var x = o.x || 0, y = o.y || 0, w = o.w || 360, h = o.h || 220, series = o.series || [];
    var xs = [], ys = [];
    series.forEach(function (sr) { (sr.points || []).forEach(function (p) { if (isFinite(p[0]) && isFinite(p[1])) { xs.push(p[0]); ys.push(p[1]); } }); });
    (o.markers || []).forEach(function (m) { if (isFinite(m.x) && isFinite(m.y)) { xs.push(m.x); ys.push(m.y); } });
    var xd = o.xDomain || [xs.length ? L.min(xs) : 0, xs.length ? L.max(xs) : 1];
    var yd = o.yDomain || [ys.length ? Math.min(0, L.min(ys)) : 0, ys.length ? L.max(ys) : 1];
    if (xd[0] === xd[1]) xd = [xd[0] - 1, xd[1] + 1];
    if (yd[0] === yd[1]) yd = [yd[0] - 1, yd[1] + 1];
    var left = x + (o.yLabel ? 52 : 40), right = x + w - 10, top = y + (o.title ? 24 : 8), bottom = y + h - (o.xLabel ? 38 : 24);
    return { sx: L.scale(xd[0], xd[1], left, right), sy: L.scale(yd[0], yd[1], bottom, top), xd: xd, yd: yd, left: left, right: right, top: top, bottom: bottom };
  };
  L.plot = function (o) {
    var S = L.plotScales(o), s = '', x = o.x || 0, y = o.y || 0, w = o.w || 360, h = o.h || 220;
    var cx = function (v) { return L.clamp(S.sx(v), S.left, S.right); }, cy = function (v) { return L.clamp(S.sy(v), S.top, S.bottom); };
    if (o.title) s += L.text(x + w / 2, y + 15, o.title, { anchor: 'middle', size: 13, weight: 600 });
    L.ticks(S.yd[0], S.yd[1], 5).forEach(function (t) {
      s += L.line(S.left, S.sy(t), S.right, S.sy(t), { color: '#e4e7eb', width: 1 }) +
        L.text(S.left - 5, S.sy(t), L.fmt(t, 3), { anchor: 'end', size: 10, baseline: 'middle', color: '#616e7c' });
    });
    L.ticks(S.xd[0], S.xd[1], 6).forEach(function (t) {
      s += L.line(S.sx(t), S.bottom, S.sx(t), S.bottom + 4, { color: '#52606d', width: 1 }) +
        L.text(S.sx(t), S.bottom + 15, L.fmt(t, 3), { anchor: 'middle', size: 10, color: '#616e7c' });
    });
    s += L.line(S.left, S.bottom, S.right, S.bottom, { color: '#52606d', width: 1 }) + L.line(S.left, S.top, S.left, S.bottom, { color: '#52606d', width: 1 });
    if (o.xLabel) s += L.text((S.left + S.right) / 2, y + h - 6, o.xLabel, { anchor: 'middle', size: 12 });
    if (o.yLabel) s += L.text(x + 12, (S.top + S.bottom) / 2, o.yLabel, { anchor: 'middle', size: 12, rotate: -90 });
    (o.hlines || []).forEach(function (r) {
      if (!isFinite(r.y) || r.y < S.yd[0] || r.y > S.yd[1]) return;
      s += L.line(S.left, S.sy(r.y), S.right, S.sy(r.y), { color: r.color || '#D55E00', dash: '5 3' });
      if (r.label) s += L.text(S.right - 2, S.sy(r.y) - 4, r.label, { anchor: 'end', size: 11, color: r.color || '#D55E00' });
    });
    (o.vlines || []).forEach(function (r) {
      if (!isFinite(r.x) || r.x < S.xd[0] || r.x > S.xd[1]) return;
      s += L.line(S.sx(r.x), S.top, S.sx(r.x), S.bottom, { color: r.color || '#D55E00', dash: '5 3' });
      if (r.label) s += L.text(S.sx(r.x) + 4, S.top + 10, r.label, { size: 11, color: r.color || '#D55E00' });
    });
    (o.series || []).forEach(function (sr, i) {
      var col = sr.color || L.color(i);
      var pts = (sr.points || []).map(function (p) {
        return isFinite(p[0]) && isFinite(p[1]) && p[1] >= S.yd[0] - 1e-12 && p[1] <= S.yd[1] + 1e-12 ? [S.sx(p[0]), S.sy(p[1])] : [NaN, NaN];
      });
      if (sr.line !== false) s += L.polyline(pts, { color: col, width: sr.width || 2, dash: sr.dash });
      if (sr.dots) pts.forEach(function (p) { if (isFinite(p[0])) s += L.circle(p[0], p[1], 3, { fill: col }); });
    });
    (o.markers || []).forEach(function (m) {
      if (!isFinite(m.x) || !isFinite(m.y)) return;
      s += L.circle(cx(m.x), cy(m.y), m.r || 5, { fill: m.color || '#D55E00', stroke: '#ffffff', width: 1.5 });
      if (m.label) s += L.text(cx(m.x) + 8, cy(m.y) - 8, m.label, { size: 11, color: m.color || '#D55E00', weight: 600 });
    });
    var labeled = (o.series || []).filter(function (sr) { return sr.label; });
    if (labeled.length && o.legend !== false) {
      s += L.legend(S.left + 10, S.top + 10, (o.series || []).map(function (sr, i) { return { label: sr.label || '', color: sr.color || L.color(i) }; }).filter(function (it) { return it.label; }));
    }
    return s;
  };

  return L;
})();
