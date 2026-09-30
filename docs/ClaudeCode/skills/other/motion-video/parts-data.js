/* motion-video parts-data — グラフ・画面・図の部品（engine.js が起動時に R へ登録する）。
 * どれも (s, lt, d) だけで決まる描画。X は engine.js の描画の道具（HELP）で、今の Canvas は X.g()。
 * 効果音のきっかけ（X.sfxEv）と揺れ（X.shakeEv）は、場面の最初に一度集めるので条件の外で呼ぶ。 */
if (!window.__mvPartsData) { window.__mvPartsData = 1; (window.MotionVideoParts = window.MotionVideoParts || []).push(function (R, X) {
  "use strict";
  var C = X.C, F = X.F, P = X.P, lin = X.lin, eo = X.eo, eio = X.eio, back = X.back, clamp = X.clamp, mix = X.mix;
  var txt = X.txt, tw = X.tw, rr = X.rr, acc = X.accentAt, ev = X.sfxEv, shakeEv = X.shakeEv, g = X.g, fmt = X.fmtNum;
  var PI2 = Math.PI * 2;
  function top(s) { return s.heading ? 300 : 190; }
  function niceMax(v) { if (!(v > 0)) return 1; var e = Math.pow(10, Math.floor(Math.log10(v))), ms = [1, 2, 2.5, 5, 10]; for (var i = 0; i < ms.length; i++) if (v <= ms[i] * e) return ms[i] * e; return 10 * e; }
  function num(v) { var n = parseFloat(String(v).replace(/,/g, "")); return isFinite(n) ? n : 0; }
  function legend(series, x, y, lt) { var cx = x; series.forEach(function (se, i) { var t = "● " + (se.name || ""); txt(t, cx, y, { size: 24, weight: 700, color: acc(i), alpha: P(lt, 300, 900) }); cx += tw(t, { size: 24, weight: 700 }) + 40; }); }
  function yGrid(L, Rr, T0, B, hi, lt, unit) {
    var ctx = g(), gk = P(lt, 0, 700);
    for (var i = 0; i <= 4; i++) { var v = hi * i / 4, y = B - (B - T0) * i / 4;
      ctx.save(); ctx.globalAlpha *= gk * (i ? .6 : 1); ctx.strokeStyle = C.edge; ctx.lineWidth = i ? 1 : 2; ctx.beginPath(); ctx.moveTo(L, y); ctx.lineTo(Rr, y); ctx.stroke(); ctx.restore();
      txt(fmt(String(Math.round(v)), 1) + (i === 4 && unit ? unit : ""), L - 18, y + 8, { size: 22, color: C.muted, align: "right", alpha: gk }); }
  }

  /* ================= グラフ ================= */
  R.area = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var labels = s.labels || [], series = s.series || [], n = labels.length, stacked = !!s.stacked;
    var sums = labels.map(function (_, i) { return series.reduce(function (a, se) { return a + num(se.values[i]); }, 0); });
    var hi = niceMax(stacked ? Math.max.apply(null, sums) : Math.max.apply(null, series.map(function (se) { return Math.max.apply(null, se.values.map(num)); })));
    var L = 220, Rr = 1700, T0 = top(s) + (series.length > 1 ? 60 : 10), B = 850, xOf = function (i) { return L + (Rr - L) * i / Math.max(1, n - 1); }, yOf = function (v) { return B - (B - T0) * v / hi; };
    yGrid(L, Rr, T0, B, hi, lt, s.unit);
    labels.forEach(function (lb, i) { txt(lb, xOf(i), B + 44, { size: 24, color: C.muted, align: "center", alpha: P(lt, 0, 700) }); });
    var base = labels.map(function () { return 0; });
    series.forEach(function (se, si) {
      var a = 600 + si * 450, dur = Math.max(1400, d * .3), k = P(lt, a, a + dur, eio); ev(a, "grow", { i: si });
      var tops = se.values.map(function (v, i) { return (stacked ? base[i] : 0) + num(v); }), bot = stacked ? base.slice() : base.map(function () { return 0; });
      if (k > 0) {
        ctx.save(); ctx.beginPath(); ctx.rect(L - 10, 0, (Rr - L + 20) * k, 1080); ctx.clip();
        ctx.beginPath(); tops.forEach(function (v, i) { i ? ctx.lineTo(xOf(i), yOf(v)) : ctx.moveTo(xOf(i), yOf(v)); });
        for (var i = n - 1; i >= 0; i--) ctx.lineTo(xOf(i), yOf(bot[i])); ctx.closePath();
        ctx.globalAlpha *= .3; ctx.fillStyle = acc(si); ctx.fill(); ctx.globalAlpha /= .3;
        ctx.beginPath(); tops.forEach(function (v, i) { i ? ctx.lineTo(xOf(i), yOf(v)) : ctx.moveTo(xOf(i), yOf(v)); });
        ctx.strokeStyle = acc(si); ctx.lineWidth = 5; ctx.lineJoin = "round"; ctx.stroke(); ctx.restore();
      }
      if (k >= 1) txt(fmt(String(se.values[n - 1]) + (s.unit || ""), P(lt, a + dur, a + dur + 800)), xOf(n - 1) + 18, yOf(tops[n - 1]) + 10, { size: 30, weight: 800, color: acc(si), font: F.display });
      if (stacked) base = tops;
    });
    if (series.length > 1) legend(series, L, top(s) + 10, lt);
  };

  R.stack = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var labels = s.labels || [], series = s.series || [], n = labels.length;
    var sums = labels.map(function (_, i) { return series.reduce(function (a, se) { return a + num(se.values[i]); }, 0); }), hi = niceMax(Math.max.apply(null, sums));
    var L = 220, Rr = 1700, T0 = top(s) + 70, B = 850, slot = (Rr - L) / Math.max(1, n), bw = Math.min(150, slot * .56), step = Math.min(160, d * .03);
    yGrid(L, Rr, T0, B, hi, lt, s.unit);
    labels.forEach(function (lb, i) {
      var cx = L + slot * (i + .5), acc0 = 0;
      txt(lb, cx, B + 44, { size: 24, color: C.muted, align: "center", alpha: P(lt, 0, 700) });
      series.forEach(function (se, si) {
        var v = num(se.values[i]), a = 500 + i * step + si * 280, k = P(lt, a, a + 520, eio); if (si === 0) ev(a, "grow", { i: i });
        var y0 = B - (B - T0) * acc0 / hi, h = (B - T0) * v / hi * k;
        if (k > 0) { ctx.save(); ctx.fillStyle = acc(si); rr(cx - bw / 2, y0 - h, bw, Math.max(1, h), si === series.length - 1 ? 8 : 2); ctx.fill(); ctx.restore(); }
        acc0 += v;
      });
      var ta = 500 + i * step + series.length * 280, tk = P(lt, ta, ta + 500);
      txt(fmt(String(sums[i]) + (s.unit || ""), tk), cx, B - (B - T0) * sums[i] / hi - 16, { size: 26, weight: 800, align: "center", alpha: tk, font: F.display });
    });
    if (series.length > 1) legend(series, L, top(s) + 10, lt);
  };

  R.scatter = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var pts = s.points || [], xs = pts.map(function (p) { return num(p.x); }), ys = pts.map(function (p) { return num(p.y); });
    var xm = s.xmax || niceMax(Math.max.apply(null, xs)), ym = s.ymax || niceMax(Math.max.apply(null, ys));
    var L = 240, Rr = 1680, T0 = top(s) + 20, B = 820, xOf = function (v) { return L + (Rr - L) * v / xm; }, yOf = function (v) { return B - (B - T0) * v / ym; };
    yGrid(L, Rr, T0, B, ym, lt);
    var ak = P(lt, 0, 800, eio);
    for (var i = 0; i <= 4; i++) txt(fmt(String(Math.round(xm * i / 4)), 1), xOf(xm * i / 4), B + 40, { size: 22, color: C.muted, align: "center", alpha: ak });
    if (s.xLabel) txt(s.xLabel, Rr, B + 80, { size: 24, weight: 700, color: C.muted, align: "right", alpha: ak });
    if (s.yLabel) txt(s.yLabel, L, T0 - 26, { size: 24, weight: 700, color: C.muted, alpha: ak });
    var at = X.slots(pts.length, d * .7, 700, 0);
    pts.forEach(function (p, i) {
      ev(at[i], "tick", { i: Math.min(i, 12) }); var k = P(lt, at[i], at[i] + 450, back); if (k <= 0) return;
      var px = xOf(num(p.x)), py = yOf(num(p.y)), r = (p.size || 12) * Math.max(0, k), hl = s.highlight === i;
      ctx.save(); ctx.fillStyle = acc(p.group || 0); ctx.globalAlpha *= hl ? 1 : .8; ctx.beginPath(); ctx.arc(px, py, r, 0, PI2); ctx.fill();
      if (hl && k >= 1) { ctx.strokeStyle = C.accent; ctx.lineWidth = 3; ctx.globalAlpha = .5 + .5 * Math.sin(lt / 250); ctx.beginPath(); ctx.arc(px, py, r + 12, 0, PI2); ctx.stroke(); }
      ctx.restore();
      if (p.label && (hl || s.labels !== false)) txt(p.label, px + r + 8, py - r - 4, { size: hl ? 28 : 20, weight: hl ? 800 : 600, color: hl ? C.accent : C.muted, alpha: P(lt, at[i] + 200, at[i] + 600) });
    });
    if (s.trend && pts.length > 1) {
      var n = pts.length, mx = xs.reduce(function (a, b) { return a + b; }, 0) / n, my = ys.reduce(function (a, b) { return a + b; }, 0) / n, sxy = 0, sxx = 0;
      pts.forEach(function (p, i) { sxy += (xs[i] - mx) * (ys[i] - my); sxx += (xs[i] - mx) * (xs[i] - mx); });
      var b = sxx ? sxy / sxx : 0, a0 = my - b * mx, ta = d * .72, tk = P(lt, ta, ta + 900, eio); ev(ta, "connect");
      if (tk > 0) { ctx.save(); ctx.strokeStyle = C.accent2; ctx.lineWidth = 4; ctx.setLineDash([14, 10]); ctx.beginPath(); ctx.moveTo(xOf(0), yOf(a0)); ctx.lineTo(xOf(xm * tk), yOf(a0 + b * xm * tk)); ctx.stroke(); ctx.restore(); }
    }
  };

  R.heatmap = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var rows = s.rows || [], cols = s.cols || [], vals = s.values || [], nr = rows.length, nc = cols.length, flat = [];
    vals.forEach(function (r) { r.forEach(function (v) { flat.push(num(v)); }); });
    var mx = Math.max.apply(null, flat.concat([1])), lw = Math.max.apply(null, rows.map(function (r) { return tw(r, { size: 24, weight: 700 }); }).concat([60]));
    var y0 = top(s) + 50, cw = Math.min(280, (1760 - 184 - lw) / Math.max(1, nc)), ch = Math.min(140, (860 - y0) / Math.max(1, nr)), mi = flat.indexOf(mx), step = Math.min(70, d * .012);
    var x0 = Math.max(160 + lw + 24, 960 - cw * nc / 2 + (lw + 24) / 2);
    cols.forEach(function (c, j) { txt(c, x0 + cw * (j + .5), y0 - 14, { size: 22, color: C.muted, align: "center", alpha: P(lt, 0, 600) }); });
    rows.forEach(function (rw, i) {
      txt(rw, x0 - 16, y0 + ch * (i + .5) + 8, { size: 24, weight: 700, align: "right", alpha: P(lt, 0, 600) });
      cols.forEach(function (_, j) {
        var v = num((vals[i] || [])[j]), a = 400 + (i + j) * step, k = P(lt, a, a + 400); if (k <= 0) return;
        ctx.save(); ctx.globalAlpha *= k * (.12 + .88 * v / mx); ctx.fillStyle = acc(s.color || 0); rr(x0 + cw * j + 3, y0 + ch * i + 3, cw - 6, ch - 6, 6); ctx.fill(); ctx.restore();
        if (s.showValues !== false && ch > 40) txt(String((vals[i] || [])[j]), x0 + cw * (j + .5), y0 + ch * (i + .5) + 11, { size: Math.min(34, ch * .32), weight: 700, align: "center", color: v / mx > .55 ? C.onAccent : C.ink, alpha: k });
      });
    });
    var ha = 400 + (nr + nc) * step + 300; ev(ha, "emphasize");
    if (lt > ha && mi >= 0) { var ri = Math.floor(mi / nc), cj = mi % nc; ctx.save(); ctx.strokeStyle = C.ink; ctx.lineWidth = 4; ctx.globalAlpha *= .6 + .4 * Math.sin(lt / 260);
      rr(x0 + cw * cj, y0 + ch * ri, cw, ch, 8); ctx.stroke(); ctx.restore(); }
  };

  R.gauge = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var cx = 960, cy = top(s) + 420, Rg = 340, mx = s.max || 100, f = clamp(num(s.value) / mx), k = P(lt, 500, 2000, eio);
    ev(500, "grow"); ev(2000, "countEnd");
    ctx.save(); ctx.lineWidth = 46; ctx.lineCap = "round"; ctx.strokeStyle = C.edge; ctx.beginPath(); ctx.arc(cx, cy, Rg, Math.PI, PI2); ctx.stroke();
    (s.zones || []).forEach(function (z) { ctx.strokeStyle = z.tone === "bad" ? C.warn : z.tone === "good" ? C.ok : C.accent2; ctx.globalAlpha = .35; ctx.lineCap = "butt";
      ctx.beginPath(); ctx.arc(cx, cy, Rg, Math.PI + Math.PI * z.from / mx, Math.PI + Math.PI * z.to / mx); ctx.stroke(); });
    ctx.globalAlpha = 1; ctx.lineCap = "round"; ctx.strokeStyle = C.accent; if (k > 0) { ctx.beginPath(); ctx.arc(cx, cy, Rg, Math.PI, Math.PI + Math.PI * f * k); ctx.stroke(); }
    var na = Math.PI + Math.PI * f * back(clamp(lin(lt, 500, 2100))); ctx.strokeStyle = C.ink; ctx.lineWidth = 8;
    ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(cx + Math.cos(na) * (Rg - 70), cy + Math.sin(na) * (Rg - 70)); ctx.stroke();
    ctx.fillStyle = C.ink; ctx.beginPath(); ctx.arc(cx, cy, 20, 0, PI2); ctx.fill(); ctx.restore();
    txt(fmt(String(s.value) + (s.unit || ""), k), cx, cy + 135, { size: 90, weight: 800, align: "center", font: F.display, color: C.accent });
    if (s.label) txt(s.label, cx, cy + 188, { size: 32, weight: 700, align: "center", color: C.muted, alpha: P(lt, 900, 1500) });
    txt("0", cx - Rg, cy + 60, { size: 24, color: C.muted, align: "center" }); txt(String(mx), cx + Rg, cy + 60, { size: 24, color: C.muted, align: "center" });
  };

  R.rings = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var items = s.items || [], n = items.length, gap = 1600 / Math.max(1, n), rad = Math.min(170, gap * .36), cy = top(s) + 300;
    items.forEach(function (it, i) {
      var cx = 160 + gap * (i + .5), a = 500 + i * 350, k = P(lt, a, a + 1500, eio), v = clamp(num(it.value) / (it.max || 100)), ap = P(lt, a - 300, a);
      ev(a, "grow", { i: i }); ev(a + 1500, "countEnd", { i: i });
      ctx.save(); ctx.lineWidth = 30; ctx.lineCap = "round"; ctx.globalAlpha *= ap; ctx.strokeStyle = C.edge; ctx.beginPath(); ctx.arc(cx, cy, rad, 0, PI2); ctx.stroke();
      if (k > 0) { ctx.strokeStyle = acc(i); ctx.beginPath(); ctx.arc(cx, cy, rad, -Math.PI / 2, -Math.PI / 2 + PI2 * v * k); ctx.stroke(); } ctx.restore();
      txt(fmt(String(it.value) + (it.unit === undefined ? "%" : it.unit), k), cx, cy + 22, { size: 64, weight: 800, align: "center", font: F.display, alpha: ap });
      txt(it.label || "", cx, cy + rad + 80, { size: 32, weight: 700, align: "center", alpha: P(lt, a + 300, a + 800) });
      if (it.sub) txt(it.sub, cx, cy + rad + 124, { size: 22, align: "center", color: C.muted, alpha: P(lt, a + 450, a + 950) });
    });
  };

  function squarify(vals, x, y, w, h) {
    var out = [], rest = vals.slice();
    function worst(row, len) { var sm = 0, mx = -Infinity, mn = Infinity; row.forEach(function (v) { sm += v; mx = Math.max(mx, v); mn = Math.min(mn, v); }); return Math.max(len * len * mx / (sm * sm), sm * sm / (len * len * mn)); }
    while (rest.length) {
      var len = Math.min(w, h), row = [rest[0]], i = 1;
      while (i < rest.length && worst(row.concat([rest[i]]), len) <= worst(row, len)) { row.push(rest[i]); i++; }
      var sm = row.reduce(function (a, b) { return a + b; }, 0), t = sm / len, off = 0;
      row.forEach(function (v) { var l = v / t; out.push(w >= h ? { x: x, y: y + off, w: t, h: l } : { x: x + off, y: y, w: l, h: t }); off += l; });
      if (w >= h) { x += t; w -= t; } else { y += t; h -= t; }
      rest = rest.slice(i);
    }
    return out;
  }
  R.treemap = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var items = (s.items || []).map(function (it, i) { return { it: it, v: Math.max(.0001, num(it.value)), i: i }; }).sort(function (a, b) { return b.v - a.v; });
    var x0 = 160, y0 = top(s) + 10, w = 1600, h = 880 - y0, sum = items.reduce(function (a, b) { return a + b.v; }, 0);
    var boxes = squarify(items.map(function (o) { return o.v * w * h / sum; }), x0, y0, w, h);
    items.forEach(function (o, n) {
      var b = boxes[n], a = 400 + n * Math.min(260, d * .05), k = P(lt, a, a + 600, back); ev(a, "appear", { i: n }); if (k <= 0) return;
      var cx = b.x + b.w / 2, cy = b.y + b.h / 2;
      ctx.save(); ctx.translate(cx, cy); ctx.scale(k, k); ctx.fillStyle = acc(o.i); ctx.globalAlpha *= .88; rr(-b.w / 2 + 4, -b.h / 2 + 4, b.w - 8, b.h - 8, 12); ctx.fill(); ctx.restore();
      var fs = Math.min(b.w, b.h) > 150 ? 36 : 24, la = P(lt, a + 250, a + 650);
      if (b.w > 90 && b.h > 60) { txt(o.it.label || "", b.x + 24, b.y + 22 + fs, { size: fs, weight: 800, color: C.onAccent, alpha: la });
        txt(fmt(String(o.it.value) + (s.unit || ""), P(lt, a + 250, a + 1200)), b.x + 24, b.y + 30 + fs * 2.2, { size: fs * .8, weight: 700, color: C.onAccent, alpha: la }); }
    });
  };

  R.radar = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var axes = s.axes || [], n = axes.length, series = s.series || [], mx = s.max || niceMax(Math.max.apply(null, series.map(function (se) { return Math.max.apply(null, se.values.map(num)); })));
    var cx = 960, cy = top(s) + (870 - top(s)) / 2 + 20, Rd = Math.min(330, (870 - top(s)) / 2 - 40), ang = function (i) { return -Math.PI / 2 + PI2 * i / n; }, gk = P(lt, 0, 900, eio), i, l;
    ctx.save(); ctx.strokeStyle = C.edge; ctx.lineWidth = 1.5;
    for (l = 1; l <= 4; l++) { ctx.beginPath(); for (i = 0; i <= n; i++) { var r = Rd * l / 4 * gk, x = cx + Math.cos(ang(i)) * r, y = cy + Math.sin(ang(i)) * r; i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); } ctx.stroke(); }
    axes.forEach(function (a, j) { ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(cx + Math.cos(ang(j)) * Rd * gk, cy + Math.sin(ang(j)) * Rd * gk); ctx.stroke();
      var c = Math.cos(ang(j)); txt(a, cx + c * (Rd + 50), cy + Math.sin(ang(j)) * (Rd + 40) + 9, { size: 26, weight: 700, align: Math.abs(c) < .2 ? "center" : c > 0 ? "left" : "right", alpha: gk }); });
    ctx.restore();
    series.forEach(function (se, si) {
      var a = 800 + si * 500, k = P(lt, a, a + 900, back); ev(a, "grow", { i: si }); if (k <= 0) return;
      ctx.save(); ctx.beginPath();
      for (var q = 0; q <= n; q++) { var r2 = Rd * num(se.values[q % n]) / mx * k, x2 = cx + Math.cos(ang(q)) * r2, y2 = cy + Math.sin(ang(q)) * r2; q ? ctx.lineTo(x2, y2) : ctx.moveTo(x2, y2); }
      ctx.fillStyle = acc(si); ctx.globalAlpha *= .22; ctx.fill(); ctx.globalAlpha /= .22; ctx.strokeStyle = acc(si); ctx.lineWidth = 4; ctx.stroke();
      for (var j = 0; j < n; j++) { var r3 = Rd * num(se.values[j]) / mx * k; ctx.fillStyle = acc(si); ctx.beginPath(); ctx.arc(cx + Math.cos(ang(j)) * r3, cy + Math.sin(ang(j)) * r3, 7, 0, PI2); ctx.fill(); }
      ctx.restore();
    });
    if (series.length > 1) legend(series, 160, top(s) + 10, lt);
  };

  /* ================= 画面（UI） ================= */
  function phoneFrame(x, y, w, h) {
    var ctx = g(); ctx.save(); ctx.shadowColor = C.shadow; ctx.shadowBlur = 50; ctx.shadowOffsetY = 20; rr(x, y, w, h, 56); ctx.fillStyle = "#0b0f14"; ctx.fill(); ctx.restore();
    ctx.save(); rr(x + 14, y + 14, w - 28, h - 28, 44); ctx.fillStyle = C.bg1; ctx.fill(); ctx.restore();
    ctx.save(); rr(x + w / 2 - 70, y + 26, 140, 30, 15); ctx.fillStyle = "#0b0f14"; ctx.fill(); ctx.restore();
    return { x: x + 14, y: y + 14, w: w - 28, h: h - 28 };
  }
  function appList(scr, sc, lt, a0, first) {
    var ctx = g(), items = sc.items || [], y = scr.y + 170;
    txt(sc.title || "", scr.x + 30, scr.y + 130, { size: 38, weight: 800, font: F.display });
    items.forEach(function (it, i) {
      var a = a0 + 300 + i * 260, k = P(lt, a, a + 450), lab = typeof it === "string" ? it : it.title, sub = it.sub, hh = sub ? 96 : 76; if (first) ev(a, "appear", { i: i });
      if (k > 0) { ctx.save(); ctx.globalAlpha *= k; ctx.translate(0, (1 - k) * 30); rr(scr.x + 22, y, scr.w - 44, hh, 18); ctx.fillStyle = C.panel; ctx.fill();
        var ix = scr.x + 40; if (it.icon) { X.iconAny(it.icon, scr.x + 66, y + hh / 2, 34, acc(i), P(lt, a + 100, a + 700), lt); ix = scr.x + 100; }
        txt(lab || "", ix, y + (sub ? 42 : 48), { size: 26, weight: 700 }); if (sub) txt(sub, ix, y + 76, { size: 20, color: C.muted });
        if (it.badge) { var bw = tw(String(it.badge), { size: 18, weight: 800 }) + 22; rr(scr.x + scr.w - 44 - bw, y + 22, bw, 32, 16); ctx.fillStyle = C.accent; ctx.fill();
          txt(String(it.badge), scr.x + scr.w - 44 - bw / 2, y + 45, { size: 18, weight: 800, align: "center", color: C.onAccent }); }
        ctx.restore(); }
      y += hh + 16;
    });
  }
  R.phone = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var side = s.points && s.points.length, pw = 470, ph = 900, px = side ? 330 : 960 - pw / 2, py = s.heading ? 150 : 110, k = P(lt, 0, 800, back);
    ctx.save(); ctx.translate(px + pw / 2, py + ph); ctx.scale(Math.max(.01, k), Math.max(.01, k)); ctx.translate(-(px + pw / 2), -(py + ph));
    var scr = phoneFrame(px, py, pw, ph), screens = s.screens || [{ title: s.title, items: s.items || [] }], n = screens.length;
    ctx.save(); rr(scr.x, scr.y, scr.w, scr.h, 44); ctx.clip();
    txt("9:41", scr.x + 40, scr.y + 44, { size: 20, weight: 700 });
    var seg = d / n, ci = Math.min(n - 1, Math.floor(lt / seg)), slide = ci < n - 1 ? eio(clamp(lin(lt, (ci + 1) * seg - 500, (ci + 1) * seg))) : 0;
    for (var i = 0; i < n; i++) { if (i > 0) ev(i * seg - 500, "tr.slide");
      var off = (i - ci - slide) * scr.w; if (Math.abs(off) >= scr.w) continue; ctx.save(); ctx.translate(off, 0); appList(scr, screens[i], lt, i * seg, i === 0); ctx.restore(); }
    if (s.notify) { var na = (s.notify.at || .5) * d, nk = P(lt, na, na + 500, back) * (1 - P(lt, na + 2600, na + 3000)); ev(na, "notify");
      if (nk > 0) { ctx.save(); ctx.translate(0, (nk - 1) * 140); rr(scr.x + 16, scr.y + 70, scr.w - 32, 110, 22); ctx.fillStyle = C.panel2; ctx.fill(); ctx.strokeStyle = C.accent; ctx.lineWidth = 2; ctx.stroke();
        txt(s.notify.title || "", scr.x + 40, scr.y + 112, { size: 22, weight: 800 }); txt(s.notify.text || "", scr.x + 40, scr.y + 150, { size: 20, color: C.muted }); ctx.restore(); } }
    if (s.tap) { var ta = (s.tap.at || .5) * d, tk = lin(lt, ta, ta + 700); ev(ta, "click");
      if (tk > 0 && tk < 1) { ctx.save(); ctx.strokeStyle = C.accent; ctx.lineWidth = 4; ctx.globalAlpha = 1 - tk; ctx.beginPath(); ctx.arc(scr.x + scr.w * (s.tap.x || .5), scr.y + scr.h * (s.tap.y || .5), 20 + 50 * tk, 0, PI2); ctx.stroke(); ctx.restore(); } }
    ctx.restore(); ctx.restore();
    if (side) { var at = X.slots(s.points.length, d, 900, d * .3);
      s.points.forEach(function (p, j) { ev(at[j], "appear", { i: j }); var pk = P(lt, at[j], at[j] + 500); if (pk <= 0) return;
        ctx.save(); ctx.globalAlpha *= pk; ctx.translate((1 - pk) * 40, 0); ctx.fillStyle = acc(j); ctx.beginPath(); ctx.arc(960, 400 + j * 120, 10, 0, PI2); ctx.fill(); ctx.restore();
        X.rich(p, 1000, 412 + j * 120, { size: 40, weight: 700, alpha: pk }); }); }
  };

  R.dashboard = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var y0 = s.heading ? 260 : 150, k = P(lt, 0, 700); ctx.save(); ctx.globalAlpha *= k; ctx.translate(0, (1 - k) * 30);
    var win = X.appWindow(120, y0, 1680, 880 - y0 + 60, s.title || "Dashboard");
    ctx.fillStyle = C.bg1; ctx.fillRect(win.x, win.y, 230, win.h);
    (s.nav || ["概要", "分析", "設定"]).forEach(function (nv, i) { if (i === 0) { rr(win.x + 14, win.y + 26, 202, 42, 10); ctx.fillStyle = C.panel2; ctx.fill(); }
      txt(nv, win.x + 36, win.y + 55 + i * 54, { size: 22, weight: i ? 400 : 700, color: i ? C.muted : C.ink }); });
    var kp = s.kpis || [], cx0 = win.x + 260, kw = (win.w - 290 - 20 * (kp.length - 1)) / Math.max(1, kp.length);
    kp.forEach(function (it, i) { var a = 500 + i * 220, kk = P(lt, a, a + 500, back), cc = P(lt, a + 150, a + 1500); ev(a, "appear", { i: i }); if (kk <= 0) return;
      var x = cx0 + i * (kw + 20); ctx.save(); ctx.translate(x + kw / 2, win.y + 90); ctx.scale(kk, kk); ctx.translate(-(x + kw / 2), -(win.y + 90));
      X.panel(x, win.y + 26, kw, 130, { shadow: false }); ctx.fillStyle = acc(i); ctx.fillRect(x, win.y + 26, 6, 130);
      txt(it.label || "", x + 26, win.y + 66, { size: 22, color: C.muted }); txt(fmt(String(it.value), cc), x + 26, win.y + 128, { size: 48, weight: 800, font: F.display, color: acc(i) });
      if (it.delta) txt(it.delta, x + kw - 20, win.y + 128, { size: 22, weight: 700, align: "right", color: /^-|↓/.test(it.delta) ? C.warn : C.ok }); ctx.restore(); });
    var bars = s.bars || [], bx = cx0, by = win.y + 190, bwid = (win.w - 290) * .58, bh = win.h - 220;
    X.panel(bx, by, bwid, bh, { shadow: false }); txt(s.chartTitle || "推移", bx + 24, by + 42, { size: 22, weight: 700 });
    var mx = Math.max.apply(null, bars.map(num).concat([1])), slot = (bwid - 60) / Math.max(1, bars.length);
    bars.forEach(function (v, i) { var a = 1100 + i * 90, kk = P(lt, a, a + 600, eio), hh = (bh - 110) * num(v) / mx * kk; if (i === 0) ev(a, "grow");
      ctx.save(); ctx.fillStyle = i === bars.length - 1 ? C.accent : C.accent2; ctx.globalAlpha *= i === bars.length - 1 ? 1 : .55; rr(bx + 30 + slot * i + slot * .18, by + bh - 30 - hh, slot * .64, Math.max(1, hh), 6); ctx.fill(); ctx.restore(); });
    var lx = bx + bwid + 20, lwid = win.w - 290 - bwid - 20; X.panel(lx, by, lwid, bh, { shadow: false }); txt(s.listTitle || "最近の動き", lx + 24, by + 42, { size: 22, weight: 700 });
    (s.rows || []).forEach(function (r, i) { var a = 1500 + i * 220, kk = P(lt, a, a + 400); if (i === 0) ev(a, "row"); if (kk <= 0) return;
      ctx.save(); ctx.globalAlpha *= kk; ctx.translate((1 - kk) * 30, 0); X.stateMark(lx + 36, by + 88 + i * 56, typeof r === "object" ? r.state || "done" : "done", lt, 9);
      txt(typeof r === "object" ? r.text : r, lx + 60, by + 96 + i * 56, { size: 22 }); ctx.restore(); });
    ctx.restore();
  };

  R.form = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var fields = s.fields || [], n = fields.length, fw = 900, fx = 960 - fw / 2, fy = s.heading ? 270 : 170, fh = 120 + n * 118 + 110, k = P(lt, 0, 600);
    var slot = (d * .72 - 700) / Math.max(1, n + 1), cur = null, doneA = 700 + slot * (n + 1);
    ctx.save(); ctx.globalAlpha *= k; X.panel(fx, fy, fw, fh, {}); txt(s.title || "", fx + 50, fy + 70, { size: 38, weight: 800 });
    fields.forEach(function (f, i) {
      var a = 700 + slot * i, y = fy + 120 + i * 118, val = String(f.value || ""), type = f.type || "text", typeD = Math.max(200, Math.min(slot - 400, val.length * 60));
      ev(a, "click"); if (type === "text" && val) ev(a + 250, "type", { n: val.length, dur: typeD });
      txt(f.label || "", fx + 50, y + 24, { size: 22, weight: 700, color: C.muted });
      var on = lt >= a && lt < a + slot, bx = fx + 50, by = y + 38, bw = fw - 100;
      if (type === "check") { rr(bx, by, 40, 40, 8); ctx.strokeStyle = on ? C.accent : C.edge; ctx.lineWidth = 2.5; ctx.stroke();
        var ck = P(lt, a + 300, a + 600); if (ck > 0) X.drawIcon("check", bx + 20, by + 20, 34, { color: C.accent, k: ck }); txt(val, bx + 60, by + 30, { size: 24 }); }
      else { rr(bx, by, bw, 56, 10); ctx.fillStyle = C.bg1; ctx.fill(); ctx.strokeStyle = on ? C.accent : C.edge; ctx.lineWidth = on ? 3 : 1.5; ctx.stroke();
        var shown = type === "select" ? (lt >= a + 700 ? val : "") : val.slice(0, Math.floor(val.length * clamp(lin(lt, a + 250, a + 250 + typeD))));
        txt(shown || (f.placeholder || ""), bx + 18, by + 37, { size: 24, color: shown ? C.ink : C.faint });
        if (type === "select") { txt("▾", bx + bw - 30, by + 37, { size: 24, color: C.muted }); var dk = P(lt, a + 200, a + 400) * (1 - P(lt, a + 700, a + 800));
          if (dk > 0) { var opts = f.options || [val]; ctx.save(); ctx.globalAlpha *= dk; X.panel(bx, by + 60, bw, opts.length * 48 + 10, {});
            opts.forEach(function (o, j) { if (o === val) { rr(bx + 6, by + 66 + j * 48, bw - 12, 44, 8); ctx.fillStyle = C.panel2; ctx.fill(); } txt(o, bx + 22, by + 96 + j * 48, { size: 22 }); }); ctx.restore(); } }
        else if (on && Math.floor(lt / 400) % 2 === 0) { ctx.fillStyle = C.accent2; ctx.fillRect(bx + 22 + tw(shown, { size: 24 }), by + 14, 3, 30); } }
      if (on) cur = { x: bx + (type === "check" ? 20 : bw * .7), y: by + 30 };
    });
    var sbA = 700 + slot * n, sb = { x: fx + fw - 290, y: fy + fh - 90, w: 240, h: 60 }, pressed = lt >= sbA + 350 && lt < sbA + 550; ev(sbA + 350, "click"); ev(sbA + 420, "send");
    ctx.save(); if (pressed) { ctx.translate(sb.x + sb.w / 2, sb.y + sb.h / 2); ctx.scale(.94, .94); ctx.translate(-(sb.x + sb.w / 2), -(sb.y + sb.h / 2)); }
    rr(sb.x, sb.y, sb.w, sb.h, 30); ctx.fillStyle = C.accent; ctx.fill(); txt(s.submit || "送信", sb.x + sb.w / 2, sb.y + 40, { size: 26, weight: 800, align: "center", color: C.onAccent }); ctx.restore();
    if (lt >= sbA && lt < doneA) cur = { x: sb.x + sb.w / 2, y: sb.y + sb.h / 2 };
    ctx.restore();
    if (cur) X.cursor(cur.x + 10, cur.y + 6, pressed, lt);
    ev(doneA, "done"); var dk2 = P(lt, doneA, doneA + 500, back);
    if (dk2 > 0) { ctx.save(); ctx.fillStyle = "rgba(0,0,0,.45)"; ctx.globalAlpha *= clamp(dk2); ctx.fillRect(0, 0, 1920, 1080); ctx.restore();
      ctx.save(); ctx.translate(960, 520); ctx.scale(dk2, dk2); X.panel(-300, -170, 600, 340, {}); X.drawIcon("check", 0, -50, 110, { color: C.ok, k: P(lt, doneA + 200, doneA + 900) });
      txt(s.done || "送信しました", 0, 110, { size: 36, weight: 800, align: "center" }); ctx.restore(); }
  };

  R.notifs = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var items = s.items || [], n = items.length, at = X.slots(n, d, 500, Math.max(1000, d * .25)), side = !!s.text, x = side ? 1000 : 960 - 380, w = 760, h = 118, y0 = s.heading ? 280 : 180;
    var shown = 0; at.forEach(function (a) { if (lt >= a) shown++; });
    var push = shown > 0 ? P(lt, at[shown - 1], at[shown - 1] + 500, eio) : 1;
    items.forEach(function (it, i) {
      ev(at[i], "notify"); if (lt < at[i]) return;
      var k = P(lt, at[i], at[i] + 500, back), order = shown - 1 - i, yy = y0 + (order - (order > 0 ? 1 - push : 0)) * (h + 18), fade = Math.max(.35, 1 - order * .15);
      if (yy > 900) return;
      ctx.save(); ctx.globalAlpha *= clamp(k) * fade; ctx.translate(0, (1 - clamp(k)) * -80); X.panel(x, yy, w, h, { r: 22 });
      if (it.icon) X.iconAny(it.icon, x + 58, yy + h / 2, 44, acc(i), P(lt, at[i] + 100, at[i] + 700), lt); else { ctx.fillStyle = acc(i); ctx.beginPath(); ctx.arc(x + 58, yy + h / 2, 22, 0, PI2); ctx.fill(); }
      txt(it.app || "", x + 104, yy + 38, { size: 20, weight: 700, color: C.muted }); txt(it.time || "今", x + w - 30, yy + 38, { size: 18, color: C.faint, align: "right" });
      txt(it.title || "", x + 104, yy + 72, { size: 26, weight: 800 }); if (it.text) txt(it.text, x + 104, yy + 102, { size: 20, color: C.muted });
      ctx.restore();
    });
    if (side) { var sk = P(lt, 200, 900); X.wrap(s.text, 700, { size: 56, weight: 800, font: F.display }).forEach(function (ln, i) { X.rich(ln, 140, 460 + i * 76, { size: 56, weight: 800, font: F.display, alpha: sk }); }); }
  };

  R.scroll = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var y0 = s.heading ? 260 : 150, W0 = 1400, x0 = 960 - W0 / 2, H0 = 900 - y0 + 40, k = P(lt, 0, 700);
    ctx.save(); ctx.globalAlpha *= k; var win = X.appWindow(x0, y0, W0, H0, s.url || s.title || "");
    var secs = s.sections || [], blocks = [], yy = 40;
    secs.forEach(function (sc) { var lines = X.wrap(sc.text || "", W0 - 200, { size: 26 }), hgt = 90 + lines.length * 40 + (sc.image ? 260 : 0) + 50; blocks.push({ sc: sc, y: yy, h: hgt, lines: lines }); yy += hgt; });
    var total = yy, maxOff = Math.max(0, total - win.h + 20), focus = s.focus === undefined ? secs.length - 1 : s.focus;
    var at = X.slots(secs.length, d, 800, 900), off = 0;
    blocks.forEach(function (b, i) { if (i === 0) return; ev(at[i], "tr.slide"); off = mix(off, Math.min(maxOff, b.y - 20), eio(lin(lt, at[i], at[i] + 900))); });
    ctx.save(); ctx.beginPath(); ctx.rect(win.x, win.y, win.w, win.h); ctx.clip(); ctx.translate(win.x + 100, win.y - off);
    blocks.forEach(function (b, i) {
      if (i === focus && lt > at[i] + 700) { ctx.save(); ctx.strokeStyle = C.accent; ctx.lineWidth = 4; ctx.globalAlpha *= .6 + .4 * Math.sin(lt / 260); rr(-30, b.y - 10, W0 - 140, b.h - 20, 16); ctx.stroke(); ctx.restore(); }
      txt(b.sc.heading || "", 0, b.y + 50, { size: 38, weight: 800, font: F.display });
      b.lines.forEach(function (ln, j) { X.rich(ln, 0, b.y + 100 + j * 40, { size: 26, color: C.muted }); });
      if (b.sc.image) { var iy = b.y + 110 + b.lines.length * 40; rr(0, iy, W0 - 200, 220, 14); ctx.fillStyle = C.panel2; ctx.fill(); txt(b.sc.image, (W0 - 200) / 2, iy + 120, { size: 26, color: C.muted, align: "center" }); }
    });
    ctx.restore();
    var th = win.h * win.h / Math.max(win.h, total), ty = win.y + (win.h - th) * (maxOff ? off / maxOff : 0);
    rr(win.x + win.w - 16, ty, 8, th, 4); ctx.fillStyle = C.edge; ctx.fill();
    ctx.restore();
  };

  R.drag = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var cols = (s.columns || []).map(function (c) { return { title: c.title, cards: (c.cards || []).slice() }; }), nc = cols.length;
    var y0 = s.heading ? 280 : 180, gap = 30, cw = (1680 - gap * (nc - 1)) / Math.max(1, nc), x0 = 120, ch = 90;
    var moves = s.moves || (s.move ? [s.move] : []), slot = (d * .8 - 900) / Math.max(1, moves.length), active = null;
    var cardY = function (i) { return y0 + 90 + i * (ch + 16); }, colX = function (c) { return x0 + c * (cw + gap); };
    moves.forEach(function (m, i) {
      var a = 900 + slot * i; ev(a + slot * .2, "click"); ev(a + slot * .75, "arrive");
      var fromC = -1, idx = -1; cols.forEach(function (c, ci) { var j = c.cards.indexOf(m.card); if (j >= 0) { fromC = ci; idx = j; } });
      var toC = typeof m.to === "number" ? m.to : cols.map(function (c) { return c.title; }).indexOf(m.to); if (fromC < 0 || toC < 0) return;
      if (lt >= a + slot * .75) { cols[fromC].cards.splice(idx, 1); cols[toC].cards.push(m.card); return; }
      if (lt < a) return;
      var p0 = { x: colX(fromC) + cw / 2, y: cardY(idx) + ch / 2 }, p1 = { x: colX(toC) + cw / 2, y: cardY(cols[toC].cards.length) + ch / 2 };
      var u = eio(lin(lt, a + slot * .25, a + slot * .7)), lift = P(lt, a + slot * .15, a + slot * .25) * (1 - P(lt, a + slot * .68, a + slot * .75));
      active = { card: m.card, from: fromC, idx: idx, x: mix(p0.x, p1.x, u), y: mix(p0.y, p1.y, u) - 12 * lift, lift: lift, held: lt >= a + slot * .15 };
      if (!active.held) active.cursor = { x: mix(960, p0.x, eio(lin(lt, a, a + slot * .15))), y: mix(900, p0.y, eio(lin(lt, a, a + slot * .15))) };
    });
    var k = P(lt, 0, 600);
    cols.forEach(function (c, ci) {
      var x = colX(ci); ctx.save(); ctx.globalAlpha *= k; rr(x, y0, cw, 860 - y0, 18); ctx.fillStyle = C.bg1; ctx.fill();
      txt(c.title || "", x + 24, y0 + 50, { size: 28, weight: 800 }); txt(String(c.cards.length), x + cw - 24, y0 + 50, { size: 24, weight: 700, color: C.muted, align: "right" });
      c.cards.forEach(function (cd, j) { if (active && active.held && active.from === ci && active.idx === j) return;
        X.panel(x + 16, cardY(j), cw - 32, ch, { shadow: false, r: 12 }); ctx.fillStyle = acc(ci); ctx.fillRect(x + 16, cardY(j), 6, ch); txt(cd, x + 40, cardY(j) + ch / 2 + 9, { size: 24, weight: 600 }); });
      ctx.restore();
    });
    if (active && active.held) { ctx.save(); ctx.translate(active.x, active.y); ctx.rotate(.04 * active.lift); var sc = 1 + .05 * active.lift; ctx.scale(sc, sc);
      ctx.shadowColor = C.shadow; ctx.shadowBlur = 30 * active.lift; X.panel(-(cw - 32) / 2, -ch / 2, cw - 32, ch, { r: 12, stroke: C.accent, lw: 2 }); ctx.shadowBlur = 0;
      txt(active.card, -(cw - 32) / 2 + 24, 9, { size: 24, weight: 600 }); ctx.restore(); X.cursor(active.x + 30, active.y + 10, active.lift > .5, lt); }
    else if (active && active.cursor) X.cursor(active.cursor.x, active.cursor.y, false, lt);
  };

  /* ================= 図 ================= */
  var NETL = new WeakMap();
  function netLayout(s) {
    var c = NETL.get(s); if (c) return c;
    var nodes = s.nodes || [], ids = nodes.map(function (n) { return n.id; }), n = ids.length, pos = ids.map(function (_, i) { var a = PI2 * i / Math.max(1, n); return { x: Math.cos(a) * 300, y: Math.sin(a) * 200 }; });
    var edges = (s.edges || []).map(function (e) { return [ids.indexOf(e[0] || e.from), ids.indexOf(e[1] || e.to)]; }).filter(function (e) { return e[0] >= 0 && e[1] >= 0; });
    var kk = 190, temp = 60, it, i, j;
    for (it = 0; it < 260; it++) {
      var disp = pos.map(function () { return { x: 0, y: 0 }; });
      for (i = 0; i < n; i++) for (j = i + 1; j < n; j++) { var dx = pos[i].x - pos[j].x, dy = pos[i].y - pos[j].y, dd = Math.max(1, Math.hypot(dx, dy)), f = kk * kk / dd;
        disp[i].x += dx / dd * f; disp[i].y += dy / dd * f; disp[j].x -= dx / dd * f; disp[j].y -= dy / dd * f; }
      edges.forEach(function (e) { var a = pos[e[0]], b = pos[e[1]], dx = a.x - b.x, dy = a.y - b.y, dd = Math.max(1, Math.hypot(dx, dy)), f = dd * dd / kk;
        disp[e[0]].x -= dx / dd * f; disp[e[0]].y -= dy / dd * f; disp[e[1]].x += dx / dd * f; disp[e[1]].y += dy / dd * f; });
      pos.forEach(function (p, q) { var m = Math.max(1, Math.hypot(disp[q].x, disp[q].y)); p.x += disp[q].x / m * Math.min(m, temp); p.y += disp[q].y / m * Math.min(m, temp) * .8; });
      temp *= .985;
    }
    /* 主な向きを横にそろえる（画面の横長を使う） */
    var mx0 = 0, my0 = 0; pos.forEach(function (p) { mx0 += p.x / n; my0 += p.y / n; });
    var sxx = 0, syy = 0, sxy = 0; pos.forEach(function (p) { var dx = p.x - mx0, dy = p.y - my0; sxx += dx * dx; syy += dy * dy; sxy += dx * dy; });
    var th = .5 * Math.atan2(2 * sxy, sxx - syy), ct = Math.cos(-th), st = Math.sin(-th);
    pos = pos.map(function (p) { var dx = p.x - mx0, dy = p.y - my0; return { x: dx * ct - dy * st, y: dx * st + dy * ct }; });
    var xs = pos.map(function (p) { return p.x; }), ys = pos.map(function (p) { return p.y; }), mnx = Math.min.apply(null, xs), mxx = Math.max.apply(null, xs), mny = Math.min.apply(null, ys), mxy = Math.max.apply(null, ys);
    var T0 = top(s) + 60, sc = Math.min(1500 / Math.max(1, mxx - mnx), (820 - T0) / Math.max(1, mxy - mny));
    pos = pos.map(function (p) { return { x: 960 + (p.x - (mnx + mxx) / 2) * sc, y: (T0 + 820) / 2 + (p.y - (mny + mxy) / 2) * sc }; });
    var deg = ids.map(function (_, q) { return edges.filter(function (e) { return e[0] === q || e[1] === q; }).length; });
    var order = [0], seen = { 0: 1 }; for (var q = 0; q < order.length; q++) edges.forEach(function (e) { var o = e[0] === order[q] ? e[1] : e[1] === order[q] ? e[0] : -1; if (o >= 0 && !seen[o]) { seen[o] = 1; order.push(o); } });
    ids.forEach(function (_, q) { if (!seen[q]) order.push(q); });
    c = { pos: pos, edges: edges, deg: deg, rank: order.reduce(function (m, v, q) { m[v] = q; return m; }, {}) };
    NETL.set(s, c); return c;
  }
  R.network = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var L = netLayout(s), nodes = s.nodes || [], per = Math.min(300, d * .5 / Math.max(1, nodes.length)), inAt = function (i) { return 400 + L.rank[i] * per; };
    L.edges.forEach(function (e, j) { var a = Math.max(inAt(e[0]), inAt(e[1])) + 250, k = P(lt, a, a + 500, eio); if (j < 12) ev(a, "connect", { i: j }); if (k <= 0) return;
      var p = L.pos[e[0]], q = L.pos[e[1]]; ctx.save(); ctx.strokeStyle = C.edge; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(mix(p.x, q.x, k), mix(p.y, q.y, k)); ctx.stroke();
      if (k >= 1) { var u = ((lt + j * 397) % 1800) / 1800; ctx.fillStyle = C.accent; ctx.globalAlpha = Math.sin(u * Math.PI); ctx.beginPath(); ctx.arc(mix(p.x, q.x, u), mix(p.y, q.y, u), 6, 0, PI2); ctx.fill(); }
      ctx.restore(); });
    nodes.forEach(function (nd, i) { var a = inAt(i), k = P(lt, a, a + 500, back); ev(a, "appear", { i: Math.min(L.rank[i], 10) }); if (k <= 0) return;
      var p = L.pos[i], r = 26 + 8 * Math.min(4, L.deg[i]), hot = s.center === nd.id || (i === 0 && s.center === undefined);
      ctx.save(); ctx.translate(p.x, p.y); ctx.scale(k, k); ctx.fillStyle = hot ? C.accent : C.panel; ctx.beginPath(); ctx.arc(0, 0, r, 0, PI2); ctx.fill();
      ctx.strokeStyle = acc(nd.group || 0); ctx.lineWidth = 3; ctx.stroke();
      if (nd.icon) X.iconAny(nd.icon, 0, 0, r * 1.1, hot ? C.onAccent : acc(nd.group || 0), 1, lt);
      ctx.restore();
      txt(nd.label || nd.id, p.x, p.y + r + 30, { size: 24, weight: 700, align: "center", alpha: P(lt, a + 200, a + 600) }); });
  };

  R.tree = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var nodes = [], leaves = 0, maxD = 0;
    (function walk(n, dep, par) { var me = { n: n, d: dep, par: par, kids: [] }; nodes.push(me); maxD = Math.max(maxD, dep); if (par) par.kids.push(me);
      var ch = typeof n === "string" ? [] : n.children || []; if (!ch.length) me.leaf = leaves++; ch.forEach(function (c) { walk(c, dep + 1, me); }); })(s.root || { label: "" }, 0, null);
    var T0 = top(s) + 30, lh = Math.min(170, (840 - T0) / Math.max(1, maxD)), lw = 1640 / Math.max(1, leaves), per = Math.min(700, d * .6 / Math.max(1, maxD + 1));
    (function place(m) { if (m.leaf !== undefined) m.x = 140 + lw * (m.leaf + .5); else { m.kids.forEach(place); m.x = (m.kids[0].x + m.kids[m.kids.length - 1].x) / 2; } m.y = T0 + m.d * lh; })(nodes[0]);
    nodes.forEach(function (m) {
      var a = 300 + m.d * per, k = P(lt, a, a + 500, back), lab = typeof m.n === "string" ? m.n : m.n.label || "", sub = typeof m.n === "string" ? "" : m.n.sub;
      if (m.kids.length) ev(a + 300, "connect", { i: m.d });
      if (m.par) { var pa = 300 + m.par.d * per + 300, bk = P(lt, pa, pa + 500, eio);
        if (bk > 0) { ctx.save(); ctx.strokeStyle = acc(m.d); ctx.lineWidth = 3; var my = (m.par.y + m.y) / 2; ctx.beginPath(); ctx.moveTo(m.par.x, m.par.y + 30);
          ctx.lineTo(m.par.x, mix(m.par.y + 30, my, clamp(bk * 2))); if (bk > .5) { var q = (bk - .5) * 2; ctx.lineTo(mix(m.par.x, m.x, q), my); if (q >= 1) ctx.lineTo(m.x, m.y - 30); } ctx.stroke(); ctx.restore(); } }
      if (k <= 0) return;
      var w = Math.max(tw(lab, { size: 26, weight: 800 }), sub ? tw(sub, { size: 18 }) : 0) + 44, h = sub ? 72 : 56;
      ctx.save(); ctx.translate(m.x, m.y); ctx.scale(k, k); X.panel(-w / 2, -h / 2, w, h, { r: 14, stroke: acc(m.d), lw: 2.5, fill: m.d === 0 ? C.accent : C.panel });
      txt(lab, 0, sub ? -2 : 9, { size: 26, weight: 800, align: "center", color: m.d === 0 ? C.onAccent : C.ink }); if (sub) txt(sub, 0, 24, { size: 18, align: "center", color: C.muted }); ctx.restore();
    });
  };

  R.states = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var st = s.states || [], n = st.length, ids = st.map(function (x) { return x.id; }), T0 = top(s) + 40, cy = (T0 + 870) / 2, rx = Math.min(640, 250 + n * 60), ry = (870 - T0) / 2 - 70;
    var pos = st.map(function (_, i) { var a = -Math.PI / 2 + PI2 * i / Math.max(1, n); return { x: 960 + Math.cos(a) * rx, y: cy + Math.sin(a) * ry }; });
    var tr = (s.transitions || []).map(function (t) { return { a: ids.indexOf(t.from), b: ids.indexOf(t.to), label: t.label }; }).filter(function (t) { return t.a >= 0 && t.b >= 0; });
    var curve = function (t) { var p = pos[t.a], q = pos[t.b], nx = -(q.y - p.y), ny = q.x - p.x, nl = Math.max(1, Math.hypot(nx, ny)); return { p: p, q: q, c: { x: (p.x + q.x) / 2 + nx / nl * 60, y: (p.y + q.y) / 2 + ny / nl * 60 } }; };
    var shrink = function (p, t) { var dx = t.x - p.x, dy = t.y - p.y, l = Math.max(1, Math.hypot(dx, dy)); return { x: p.x + dx / l * 70, y: p.y + dy / l * 70 }; };
    var buildEnd = 400 + n * 250 + 600;
    tr.forEach(function (t, j) { var cv = curve(t), a = 400 + n * 250 + j * 120, k = P(lt, a, a + 500, eio); if (k <= 0) return;
      X.arrow(shrink(cv.p, cv.c), cv.c, shrink(cv.q, cv.c), k, { color: C.edge, width: 3 });
      if (t.label && k >= 1) { var m = X.qpt(cv.p, cv.c, cv.q, .5); txt(t.label, m.x, m.y - 10, { size: 20, weight: 700, color: C.muted, align: "center" }); } });
    var path = (s.path || []).map(function (id) { return ids.indexOf(id); }).filter(function (i) { return i >= 0; }), seg = (d - buildEnd - 800) / Math.max(1, path.length - 1), cur = -1, tok = null;
    path.forEach(function (pi, j) { var a = buildEnd + j * seg; if (j > 0) ev(a, "step", { i: j }); if (lt >= a) cur = pi;
      if (j > 0 && lt >= a - seg * .6 && lt < a) { var cv = curve({ a: path[j - 1], b: pi }); tok = X.qpt(cv.p, cv.c, cv.q, eio(lin(lt, a - seg * .6, a))); } });
    st.forEach(function (x, i) { var a = 400 + i * 250, k = P(lt, a, a + 500, back); ev(a, "appear", { i: i }); if (k <= 0) return;
      var on = i === cur, p = pos[i], sc = k * (on ? 1.08 : 1); ctx.save(); ctx.translate(p.x, p.y); ctx.scale(sc, sc);
      ctx.fillStyle = on ? C.accent : C.panel; ctx.beginPath(); ctx.arc(0, 0, 64, 0, PI2); ctx.fill(); ctx.strokeStyle = on ? C.accent : acc(i); ctx.lineWidth = 3; ctx.stroke();
      if (on) { ctx.globalAlpha = .3 + .2 * Math.sin(lt / 200); ctx.beginPath(); ctx.arc(0, 0, 80, 0, PI2); ctx.stroke(); ctx.globalAlpha = 1; }
      txt(x.label || x.id, 0, 9, { size: 24, weight: 800, align: "center", color: on ? C.onAccent : C.ink }); ctx.restore(); });
    if (tok) { ctx.save(); ctx.fillStyle = C.accent2; ctx.shadowColor = C.accent2; ctx.shadowBlur = 20; ctx.beginPath(); ctx.arc(tok.x, tok.y, 12, 0, PI2); ctx.fill(); ctx.restore(); }
  };

  R.map = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var x0 = 160, y0 = top(s) + 10, w = 1600, h = 870 - y0, r = X.rand(s.seed || 4), k = P(lt, 0, 900), bs = 90, i, j;
    ctx.save(); rr(x0, y0, w, h, 20); ctx.clip(); ctx.fillStyle = C.bg1; ctx.fillRect(x0, y0, w, h);
    for (i = 0; i * bs < w; i++) for (j = 0; j * bs < h; j++) { var skip = r() < .18, park = r() < .12; if (skip) continue;
      ctx.fillStyle = park ? C.ok : C.edge; ctx.globalAlpha = k * (park ? .3 : .45); rr(x0 + i * bs + 10, y0 + j * bs + 10, bs - 20, bs - 20, 8); ctx.fill(); }
    ctx.globalAlpha = k * .25; ctx.strokeStyle = C.accent2; ctx.lineWidth = 16; ctx.beginPath(); ctx.moveTo(x0, y0 + h * .62); ctx.bezierCurveTo(x0 + w * .3, y0 + h * .4, x0 + w * .6, y0 + h * .9, x0 + w, y0 + h * .55); ctx.stroke();
    ctx.restore();
    var pins = s.pins || [], P0 = function (p) { return { x: x0 + w * (p ? p.x : 0), y: y0 + h * (p ? p.y : 0) }; };
    (s.routes || []).forEach(function (rt, ri) { var a = 900 + pins.length * 250 + ri * 500, kk = P(lt, a, a + 900, eio), p = P0(pins[rt[0]]), q = P0(pins[rt[1]]); ev(a, "connect", { i: ri }); if (kk <= 0) return;
      var c = { x: (p.x + q.x) / 2, y: Math.min(p.y, q.y) - 120 }; X.arrow(p, c, q, kk, { color: C.accent, width: 5, dashed: true, head: false });
      if (kk >= 1) X.packet(p, c, q, ((lt - a) % 2200) / 2200, "", { r: 9 }); });
    pins.forEach(function (pn, i2) { var a = 700 + i2 * 250, p = P0(pn); ev(a, "appear", { i: i2 }); if (lt < a) return;
      var dy = (1 - eo(clamp(lin(lt, a, a + 400)))) * -120;
      ctx.save(); ctx.translate(p.x, p.y + dy); ctx.fillStyle = pn.color === "warn" ? C.warn : C.accent; ctx.beginPath(); ctx.moveTo(0, 0); ctx.bezierCurveTo(-26, -34, -26, -70, 0, -70); ctx.bezierCurveTo(26, -70, 26, -34, 0, 0); ctx.fill();
      ctx.fillStyle = C.bg0; ctx.beginPath(); ctx.arc(0, -46, 9, 0, PI2); ctx.fill(); ctx.restore();
      var sk = lin(lt, a + 380, a + 700); if (sk > 0 && sk < 1) { ctx.save(); ctx.strokeStyle = C.accent; ctx.globalAlpha = 1 - sk; ctx.lineWidth = 3; ctx.beginPath(); ctx.ellipse(p.x, p.y, 10 + 40 * sk, 4 + 14 * sk, 0, 0, PI2); ctx.stroke(); ctx.restore(); }
      if (pn.label) { var lw2 = tw(pn.label, { size: 24, weight: 800 }) + 28; ctx.save(); ctx.globalAlpha *= P(lt, a + 300, a + 700); X.panel(p.x - lw2 / 2, p.y - 132, lw2, 44, { r: 22, shadow: false });
        txt(pn.label, p.x, p.y - 102, { size: 24, weight: 800, align: "center" }); ctx.restore(); } });
  };

  R.layers = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var items = s.items || [], n = items.length, cx = 760, base = 830, lwid = 760, dep = 150, gap0 = Math.min(110, (base - top(s) - 120) / Math.max(1, n));
    var ex = P(lt, d * .5, d * .5 + 900, eio) * (1 - P(lt, d * .82, d * .82 + 700, eio)), gap = gap0 * (1 + .45 * ex);
    ev(d * .5, "reveal");
    items.forEach(function (it, i) {
      var a = 400 + i * Math.min(500, d * .08), k = P(lt, a, a + 600, back), y = base - i * gap - (1 - Math.min(1, k)) * 160; ev(a, "step", { i: i }); if (lt < a) return;
      ctx.save(); ctx.globalAlpha *= clamp(k * 1.5);
      ctx.beginPath(); ctx.moveTo(cx - lwid / 2, y); ctx.lineTo(cx, y + dep / 2); ctx.lineTo(cx + lwid / 2, y); ctx.lineTo(cx, y - dep / 2); ctx.closePath();
      ctx.fillStyle = acc(i); ctx.globalAlpha *= .9; ctx.fill(); ctx.globalAlpha /= .9;
      ctx.beginPath(); ctx.moveTo(cx - lwid / 2, y); ctx.lineTo(cx - lwid / 2, y + 22); ctx.lineTo(cx, y + dep / 2 + 22); ctx.lineTo(cx, y + dep / 2); ctx.closePath(); ctx.fillStyle = "rgba(0,0,0,.35)"; ctx.fill();
      ctx.beginPath(); ctx.moveTo(cx + lwid / 2, y); ctx.lineTo(cx + lwid / 2, y + 22); ctx.lineTo(cx, y + dep / 2 + 22); ctx.lineTo(cx, y + dep / 2); ctx.closePath(); ctx.fillStyle = "rgba(0,0,0,.2)"; ctx.fill();
      ctx.restore();
      var lk = P(lt, a + 300, a + 800), label = typeof it === "string" ? it : it.label;
      ctx.save(); ctx.globalAlpha *= lk; ctx.strokeStyle = acc(i); ctx.lineWidth = 2; ctx.setLineDash([6, 6]); ctx.beginPath(); ctx.moveTo(cx + lwid / 2 - 30, y); ctx.lineTo(cx + lwid / 2 + 90, y); ctx.stroke(); ctx.restore();
      txt(label || "", cx + lwid / 2 + 110, y + 10, { size: 32, weight: 800, alpha: lk }); if (it.sub) txt(it.sub, cx + lwid / 2 + 110, y + 46, { size: 22, color: C.muted, alpha: lk });
    });
  };

  R.pipeline = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var stages = s.stages || [], n = stages.length, y = (top(s) + 860) / 2 + 40, x0 = 180, x1 = 1740, sw = Math.min(260, (x1 - x0) / Math.max(1, n) - 60), gapX = (x1 - x0 - sw) / Math.max(1, n - 1);
    var sx = function (i) { return n > 1 ? x0 + sw / 2 + gapX * i : 960; }, bk = P(lt, 200, 1100, eio);
    ctx.save(); ctx.strokeStyle = C.edge; ctx.lineWidth = 10; ctx.lineCap = "round"; ctx.beginPath(); ctx.moveTo(x0 - 60, y); ctx.lineTo(mix(x0 - 60, x1 + 60, bk), y); ctx.stroke();
    ctx.setLineDash([4, 26]); ctx.lineDashOffset = -lt * .08; ctx.strokeStyle = C.muted; ctx.lineWidth = 4; ctx.beginPath(); ctx.moveTo(x0 - 60, y); ctx.lineTo(mix(x0 - 60, x1 + 60, bk), y); ctx.stroke(); ctx.restore();
    var every = s.every || 900, start = 1300, speed = (x1 - x0 + 120) / (s.travel || 3600), made = Math.max(0, Math.floor((lt - start) / every) + 1), passed = stages.map(function () { return 0; });
    for (var t = 0; t < Math.min(made, 80); t++) { var age = lt - (start + t * every), px = x0 - 60 + age * speed;
      stages.forEach(function (_, i) { if (px >= sx(i)) passed[i]++; });
      if (px > x1 + 60) continue;
      ctx.save(); ctx.fillStyle = acc(t); ctx.translate(px, y); ctx.rotate(age * .002); rr(-16, -16, 32, 32, 7); ctx.fill(); ctx.restore(); }
    stages.forEach(function (st, i) { var a = 300 + i * 220, k = P(lt, a, a + 500, back); ev(a, "appear", { i: i }); if (k <= 0) return;
      var label = typeof st === "string" ? st : st.label, reach = (sx(i) - x0 + 60) / speed, since = ((lt - start - reach) % every + every) % every, hot = lt > start + reach && since < 300;
      var sc = k * (hot ? 1.05 : 1); ctx.save(); ctx.translate(sx(i), y - 130); ctx.scale(sc, sc); X.panel(-sw / 2, -60, sw, 120, { stroke: hot ? C.accent : acc(i), lw: hot ? 3.5 : 2 });
      if (st.icon) X.iconAny(st.icon, -sw / 2 + 44, 0, 40, acc(i), 1, lt); txt(label || "", st.icon ? 24 : 0, 10, { size: 28, weight: 800, align: "center" }); ctx.restore();
      txt(String(passed[i]), sx(i), y + 70, { size: 34, weight: 800, align: "center", color: acc(i), font: F.display, alpha: P(lt, start, start + 400) });
      ctx.save(); ctx.strokeStyle = acc(i); ctx.lineWidth = 3; ctx.globalAlpha *= k; ctx.beginPath(); ctx.moveTo(sx(i), y - 70); ctx.lineTo(sx(i), y - 14); ctx.stroke(); ctx.restore(); });
    if (s.label) txt(s.label, 960, y + 150, { size: 26, color: C.muted, align: "center", alpha: P(lt, 900, 1500) });
  };
}); }
