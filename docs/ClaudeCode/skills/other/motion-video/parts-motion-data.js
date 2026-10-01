/* motion-video parts-motion-data — 時間とともに動くデータ（順位の入れ替わり・泡・伸びる線・地域の塗り分け・流れ・
 * 回る数字・升目・傾き）と、画面の解説（スクリーンショットの上を移るカメラ・長い画面のスクロール・前後の画面の比較）。
 * どれも (s, lt, d) だけで決まる描画。X は engine.js の描画の道具（HELP）。区切りの時刻は X.slots（ナレーションの文に合わせられる）。 */
if (!window.__mvPartsMotionData) { window.__mvPartsMotionData = 1; (window.MotionVideoParts = window.MotionVideoParts || []).push(function (R, X) {
  "use strict";
  var C = X.C, F = X.F, P = X.P, lin = X.lin, eo = X.eo, eio = X.eio, back = X.back, clamp = X.clamp, mix = X.mix;
  var txt = X.txt, tw = X.tw, rr = X.rr, acc = X.accentAt, ev = X.sfxEv, g = X.g, fmt = X.fmtNum;
  var PI2 = Math.PI * 2;
  function top(s) { return s.heading ? 300 : 190; }
  function num(v) { var n = parseFloat(String(v).replace(/,/g, "")); return isFinite(n) ? n : 0; }
  function lab(it) { return typeof it === "string" ? it : (it && (it.label || it.name || it.text)) || ""; }
  function fit(s, maxW, o) { var size = o.size; while (size > 14 && tw(s, Object.assign({}, o, { size: size })) > maxW) size -= 2; return Object.assign({}, o, { size: size }); }
  function niceMax(v) { if (!(v > 0)) return 1; var e = Math.pow(10, Math.floor(Math.log10(v))), ms = [1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10]; for (var i = 0; i < ms.length; i++) if (v <= ms[i] * e) return ms[i] * e; return 10 * e; }
  function fmtV(v, dec) { var s2 = Math.abs(v) >= 100 || !dec ? String(Math.round(v)) : v.toFixed(dec); var q = s2.split("."); q[0] = q[0].replace(/\B(?=(\d{3})+(?!\d))/g, ","); return q.join("."); }
  function decOf(arr) { return arr.some(function (v) { return Math.abs(v - Math.round(v)) > 1e-9; }) ? 1 : 0; }
  /* 色: テーマの色（#rrggbb・rgb()）を数に直して混ぜる（Canvas は color-mix を使えないため） */
  function rgb(c) { var m = /^#([0-9a-f]{6})$/i.exec(c || ""); if (m) { var n = parseInt(m[1], 16); return [n >> 16 & 255, n >> 8 & 255, n & 255]; }
    m = /rgba?\(([^)]+)\)/.exec(c || ""); if (m) { var p = m[1].split(",").map(parseFloat); return [p[0], p[1], p[2]]; } return [128, 128, 128]; }
  function cmix(a, b, k) { var x = rgb(a), y = rgb(b); return "rgb(" + [0, 1, 2].map(function (i) { return Math.round(mix(x[i], y[i], clamp(k))); }).join(",") + ")"; }
  /* 期間（periods）の間を補間する: 場面の [a, b] ms に periods を均等に置き、今の位置 {i, f（0..1 の緩急つき）, q（連続）} */
  function periodAt(n, lt, a, b) { var q = clamp((lt - a) / Math.max(1, b - a)) * Math.max(0, n - 1), i = Math.min(n - 2, Math.floor(q)); if (n < 2) return { i: 0, f: 0, q: 0 };
    var f = q - i; return { i: i, f: eio(f), raw: f, q: q }; }
  function bigLabel(t, x, y, k, o) { txt(t, x, y, Object.assign({ size: 150, weight: 900, font: F.display, color: C.faint, align: "right", alpha: k }, o || {})); }
  function cardNote(text, x, y, w, k, o) {
    o = o || {}; var ctx = g(), lines = X.wrap(text, w - 48, { size: o.size || 30, weight: 600 }), h = 36 + lines.length * (o.size || 30) * 1.45;
    ctx.save(); ctx.globalAlpha *= k; ctx.translate(x, y + (1 - k) * 18);
    ctx.shadowColor = C.shadow; ctx.shadowBlur = 30; ctx.shadowOffsetY = 10; rr(0, 0, w, h, 16); ctx.fillStyle = C.panel; ctx.fill(); ctx.shadowColor = "transparent";
    ctx.lineWidth = 3; ctx.strokeStyle = C.accent; ctx.stroke();
    lines.forEach(function (ln, i) { X.rich(ln, 24, 18 + (o.size || 30) * (1.1 + i * 1.45), { size: o.size || 30, weight: 600 }, 1); });
    ctx.restore(); return h;
  }
  function badgeNum(n, x, y, k) { var ctx = g(); if (k <= 0) return; ctx.save(); ctx.translate(x, y); ctx.scale(k, k); ctx.beginPath(); ctx.arc(0, 0, 30, 0, PI2); ctx.fillStyle = C.accent; ctx.fill();
    ctx.lineWidth = 4; ctx.strokeStyle = C.bg0; ctx.stroke(); ctx.restore(); txt(String(n), x, y + 11, { size: 32, weight: 900, align: "center", color: C.onAccent, alpha: clamp(k) }); }

  /* ================= 順位が入れ替わる棒（バーチャートレース） =================
     periods: ["2020", …], items: [{label, values: [...]}]、top（見せる数。既定 8）、unit */
  R.race = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var per = s.periods || [], np = per.length, items = (s.items || []).map(function (it, i) { return { label: lab(it), v: (it.values || []).map(num), i: i, color: it.color }; });
    var N = Math.min(s.top || 8, items.length), a0 = 700, b0 = Math.max(a0 + 1000, d - 1600), pa = periodAt(np, lt, a0, b0), j = Math.min(np - 1, pa.i + 1);
    var rankAt = function (pi) { var o = items.slice().sort(function (p, q) { return (q.v[pi] || 0) - (p.v[pi] || 0) || p.i - q.i; }), r = {}; o.forEach(function (it, k) { r[it.i] = k; }); return r; };
    var r0 = rankAt(pa.i), r1 = rankAt(j), y0 = top(s) + 20, lh = (900 - y0) / N, k0 = P(lt, 0, 700);
    var vals = items.map(function (it) { return mix(it.v[pa.i] || 0, it.v[j] || 0, pa.raw === undefined ? 0 : clamp((lt - a0) / Math.max(1, b0 - a0) * (np - 1) - pa.i)); });
    var hi = Math.max.apply(null, vals.concat([1])) * 1.08, L = 420, Wd = 1220, dec = decOf([].concat.apply([], items.map(function (it) { return it.v; })));
    /* 目盛り（最大値に合わせて伸び縮みする） */
    var step = niceMax(hi / 4) / (niceMax(hi / 4) > hi / 4 * 1.6 ? 2 : 1);
    for (var gv = step; gv < hi; gv += step) { var gx = L + Wd * gv / hi; ctx.save(); ctx.globalAlpha *= .5 * k0; ctx.strokeStyle = C.edge; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(gx, y0 - 20); ctx.lineTo(gx, 900); ctx.stroke(); ctx.restore();
      txt(fmtV(gv, 0), gx, y0 - 30, { size: 20, color: C.muted, align: "center", alpha: k0 }); }
    items.forEach(function (it, idx) {
      var ry = mix(r0[it.i], r1[it.i], pa.f); if (ry > N + .2) return;
      var y = y0 + ry * lh, vis = clamp(N + .3 - ry) * k0, bh = Math.min(64, lh * .72), w = Wd * vals[idx] / hi * P(lt, 100, 900, eo), col = it.color || acc(it.i);
      ctx.save(); ctx.globalAlpha *= vis; rr(L, y, Math.max(bh * .4, w), bh, 10); ctx.fillStyle = col; ctx.fill(); ctx.restore();
      txt(it.label, L - 20, y + bh / 2 + 11, Object.assign(fit(it.label, 380, { size: 30, weight: 700 }), { align: "right", alpha: vis }));
      txt(fmtV(vals[idx], dec) + (s.unit || ""), L + Math.max(bh * .4, w) + 16, y + bh / 2 + 11, { size: 28, weight: 800, font: F.display, color: C.ink, alpha: vis });
    });
    var curP = per[Math.min(np - 1, Math.round(pa.q || 0))] || "";
    bigLabel(String(curP), 1800, 880, k0);
    /* 出来事: 期間が進むたびに小さく、首位が入れ替わったら強く */
    for (var pi = 1; pi < np; pi++) { var tAt = a0 + (b0 - a0) * pi / (np - 1); ev(tAt, "tick", { v: .5 }); var A = rankAt(pi - 1), B = rankAt(pi);
      var lead = function (r) { for (var k in r) if (r[k] === 0) return k; }; if (lead(A) !== lead(B)) ev(tAt - 300, "emphasize"); }
  };

  /* ================= 時間とともに動く泡（バブルチャート） =================
     periods, items: [{label, x: [...], y: [...], r: [...]}]、xLabel・yLabel、trail（軌跡。既定 true） */
  R.bubble = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var per = s.periods || [], np = per.length, items = s.items || [], a0 = 900, b0 = Math.max(a0 + 1000, d - 1500), pa = periodAt(np, lt, a0, b0), j = Math.min(np - 1, pa.i + 1);
    var all = function (key) { return [].concat.apply([], items.map(function (it) { return (it[key] || []).map(num); })); };
    var xs = all("x"), ys = all("y"), rs = all("r"), xmx = niceMax(Math.max.apply(null, xs.concat([1]))), ymx = niceMax(Math.max.apply(null, ys.concat([1]))), rmx = Math.max.apply(null, rs.concat([1]));
    var L = 260, Rr = 1720, T0 = top(s) + 20, B = 860, k0 = P(lt, 0, 700);
    var px = function (v) { return L + (Rr - L) * v / xmx; }, py = function (v) { return B - (B - T0) * v / ymx; };
    ctx.save(); ctx.globalAlpha *= k0; ctx.strokeStyle = C.edge; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(L, T0); ctx.lineTo(L, B); ctx.lineTo(Rr, B); ctx.stroke();
    ctx.lineWidth = 1; ctx.globalAlpha *= .45; for (var q = 1; q <= 4; q++) { ctx.beginPath(); ctx.moveTo(L, py(ymx * q / 4)); ctx.lineTo(Rr, py(ymx * q / 4)); ctx.stroke(); ctx.beginPath(); ctx.moveTo(px(xmx * q / 4), T0); ctx.lineTo(px(xmx * q / 4), B); ctx.stroke(); } ctx.restore();
    for (q = 0; q <= 4; q++) { txt(fmtV(ymx * q / 4, 0), L - 16, py(ymx * q / 4) + 8, { size: 20, color: C.muted, align: "right", alpha: k0 }); txt(fmtV(xmx * q / 4, 0), px(xmx * q / 4), B + 34, { size: 20, color: C.muted, align: "center", alpha: k0 }); }
    if (s.xLabel) txt(s.xLabel, Rr, B + 70, { size: 24, weight: 700, color: C.muted, align: "right", alpha: k0 });
    if (s.yLabel) txt(s.yLabel, L, T0 - 20, { size: 24, weight: 700, color: C.muted, alpha: k0 });
    bigLabel(String(per[Math.min(np - 1, Math.round(pa.q || 0))] || ""), Rr - 20, T0 + 150, k0 * .9, { size: 170 });
    var posOf = function (it, i0, i1, f) { return { x: mix(num((it.x || [])[i0]), num((it.x || [])[i1]), f), y: mix(num((it.y || [])[i0]), num((it.y || [])[i1]), f), r: mix(num((it.r || [])[i0] || 1), num((it.r || [])[i1] || 1), f) }; };
    var fRaw = clamp((lt - a0) / Math.max(1, b0 - a0)) * (np - 1) - pa.i;
    items.map(function (it, i) { return { it: it, i: i, p: posOf(it, pa.i, j, eio(clamp(fRaw))) }; }).sort(function (p, q2) { return q2.p.r - p.p.r; }).forEach(function (o) {
      var it = o.it, p = o.p, col = it.color || acc(o.i), rad = 18 + 70 * Math.sqrt(p.r / rmx), pop = P(lt, 300 + o.i * 120, 900 + o.i * 120, back);
      if (s.trail !== false) for (var t2 = 0; t2 <= pa.i; t2++) { var tp = posOf(it, t2, t2, 0); ctx.save(); ctx.globalAlpha *= .25 * k0; ctx.beginPath(); ctx.arc(px(tp.x), py(tp.y), 7, 0, PI2); ctx.fillStyle = col; ctx.fill(); ctx.restore(); }
      ctx.save(); ctx.globalAlpha *= .78 * clamp(pop); ctx.beginPath(); ctx.arc(px(p.x), py(p.y), rad * pop, 0, PI2); ctx.fillStyle = col; ctx.fill(); ctx.globalAlpha = clamp(pop); ctx.lineWidth = 3; ctx.strokeStyle = C.bg0; ctx.stroke(); ctx.restore();
      txt(lab(it), px(p.x), py(p.y) - rad * pop - 12, Object.assign(fit(lab(it), 260, { size: 26, weight: 800 }), { align: "center", alpha: clamp(pop) }));
      ev(300 + o.i * 120, "appear", { i: o.i });
    });
    for (var pi = 1; pi < np; pi++) ev(a0 + (b0 - a0) * pi / (np - 1), "tick", { v: .5 });
  };

  /* ================= 伸びていく線（ラインレース）: 線の先に名前と値が付いて走る =================
     labels: [...], series: [{name, values}]、unit */
  R.linerace = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var labels = s.labels || [], n = labels.length, series = s.series || [], a0 = 700, b0 = Math.max(a0 + 1200, d - 1400);
    var q = clamp((lt - a0) / Math.max(1, b0 - a0)) * Math.max(0, n - 1), qi = Math.floor(q), qf = q - qi, k0 = P(lt, 0, 700);
    var at = function (se, x) { var i = Math.min(n - 1, Math.floor(x)), f = x - i; return mix(num(se.values[i]), num(se.values[Math.min(n - 1, i + 1)]), f); };
    var seen = 0; series.forEach(function (se) { for (var i = 0; i <= Math.min(n - 1, qi + 1); i++) seen = Math.max(seen, i <= qi ? num(se.values[i]) : at(se, q)); });
    var hi = Math.max(seen, 1) * 1.15, L = 220, Rr = 1500, T0 = top(s) + 20, B = 850, dec = decOf([].concat.apply([], series.map(function (se) { return se.values.map(num); })));
    var xOf = function (x) { return L + (Rr - L) * x / Math.max(1, n - 1); }, yOf = function (v) { return B - (B - T0) * v / hi; };
    var step = niceMax(hi / 4); if (hi / step < 2.5) step /= 2;
    for (var gv = 0; gv < hi; gv += step) { ctx.save(); ctx.globalAlpha *= k0 * (gv ? .45 : 1); ctx.strokeStyle = C.edge; ctx.lineWidth = gv ? 1 : 2; ctx.beginPath(); ctx.moveTo(L, yOf(gv)); ctx.lineTo(Rr, yOf(gv)); ctx.stroke(); ctx.restore();
      txt(fmtV(gv, 0), L - 16, yOf(gv) + 8, { size: 20, color: C.muted, align: "right", alpha: k0 }); }
    labels.forEach(function (lb, i) { if (i > q + .01) return; txt(lb, xOf(i), B + 40, { size: 22, color: C.muted, align: "center", alpha: P(lt, a0 + (b0 - a0) * i / Math.max(1, n - 1) - 200, a0 + (b0 - a0) * i / Math.max(1, n - 1) + 200) }); });
    var ends = [];
    series.forEach(function (se, si) {
      var col = se.color || acc(si); ctx.save(); ctx.globalAlpha *= k0; ctx.strokeStyle = col; ctx.lineWidth = 6; ctx.lineJoin = "round"; ctx.lineCap = "round"; ctx.beginPath();
      for (var i = 0; i <= qi; i++) { var y = yOf(num(se.values[i])); if (i) ctx.lineTo(xOf(i), y); else ctx.moveTo(xOf(i), y); }
      var ex = xOf(q), ey = yOf(at(se, q)); ctx.lineTo(ex, ey); ctx.stroke(); ctx.restore();
      ends.push({ y: ey, x: ex, col: col, name: se.name || "", v: at(se, q) });
    });
    /* 線の先の名前が重ならないよう縦に押し広げる */
    var ord = ends.slice().sort(function (a, b) { return a.y - b.y; }); for (var it = 0; it < 4; it++) for (var m = 1; m < ord.length; m++) if (ord[m].y - ord[m - 1].y < 44) { var push = (44 - (ord[m].y - ord[m - 1].y)) / 2; ord[m].y += push; ord[m - 1].y -= push; }
    ends.forEach(function (e) { var ctx2 = g(); ctx2.save(); ctx2.globalAlpha *= k0; ctx2.beginPath(); ctx2.arc(e.x, yOf(e.v), 10 + 3 * Math.sin(lt / 160), 0, PI2); ctx2.fillStyle = e.col; ctx2.fill(); ctx2.restore();
      txt(e.name + "  " + fmtV(e.v, dec) + (s.unit || ""), e.x + 22, e.y + 9, { size: 26, weight: 800, color: e.col, alpha: k0 }); });
    ev(a0, "grow"); ev(b0, "countEnd"); for (var pi = 1; pi < n; pi++) ev(a0 + (b0 - a0) * pi / (n - 1), "tick", { v: .35 });
  };

  /* ================= 地域の塗り分け（タイルの地図） =================
     preset: "japan"（8 地方）か tiles: [{label, col, row, w, h}]。items: [{label, value}]、unit。値が大きいほど濃い */
  var PRESETS = { japan: [["北海道", 5, 0, 1.3, 1], ["東北", 5, 1, 1, 1.6], ["関東", 5, 2.6, 1, 1], ["中部", 4, 1.8, 1, 1.6], ["近畿", 3, 2.6, 1, 1],
                          ["中国", 2, 2.6, 1, 0.9], ["四国", 2.3, 3.6, 1.2, 0.7], ["九州・沖縄", 1, 3.2, 1, 1.6]] };
  R.regions = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var tiles = (s.tiles || PRESETS[s.preset || "japan"] || []).map(function (t) { return Array.isArray(t) ? { label: t[0], col: t[1], row: t[2], w: t[3], h: t[4] } : t; });
    var vals = {}; (s.items || []).forEach(function (it) { vals[lab(it)] = num(it.value); });
    var vs = tiles.map(function (t) { return vals[t.label]; }).filter(function (v) { return v !== undefined; }), lo = Math.min.apply(null, vs.concat([0])), hi = Math.max.apply(null, vs.concat([1]));
    var cols = Math.max.apply(null, tiles.map(function (t) { return t.col + (t.w || 1); })), rows = Math.max.apply(null, tiles.map(function (t) { return t.row + (t.h || 1); }));
    var T0 = top(s) + 10, cell = Math.min(1120 / cols, (960 - T0) / rows), ox = 120 + (1120 - cell * cols) / 2, oy = T0;
    var order = tiles.map(function (t, i) { return i; }).sort(function (a, b) { return (vals[tiles[b].label] || 0) - (vals[tiles[a].label] || 0); });
    var at = X.slots(tiles.length, d, 500, Math.max(1300, d * .3)), maxI = order[0];
    order.forEach(function (ti, k) {
      var t = tiles[ti], a = at[k], kk = P(lt, a, a + 600, back), v = vals[t.label], has = v !== undefined, frac = has ? (v - lo) / Math.max(1e-9, hi - lo) : 0;
      var x = ox + t.col * cell + 6, y = oy + t.row * cell + 6, w = (t.w || 1) * cell - 12, h = (t.h || 1) * cell - 12;
      ctx.save(); ctx.globalAlpha *= P(lt, 0, 500); rr(x, y, w, h, 14); ctx.fillStyle = C.panel2; ctx.fill(); ctx.restore();
      if (kk > 0 && has) { ctx.save(); ctx.translate(x + w / 2, y + h / 2); ctx.scale(clamp(kk, 0, 1.2), clamp(kk, 0, 1.2)); rr(-w / 2, -h / 2, w, h, 14); ctx.fillStyle = cmix(C.panel2, C.accent, .25 + .75 * frac); ctx.fill();
        if (ti === maxI && kk >= 1) { ctx.lineWidth = 5; ctx.strokeStyle = C.warn; ctx.globalAlpha *= .6 + .4 * Math.sin(lt / 220); ctx.stroke(); } ctx.restore(); }
      var dark = frac > .55 && kk > .5, tc = dark ? C.onAccent : C.ink;
      txt(t.label, x + w / 2, y + h / 2 - (has ? 6 : -10), Object.assign(fit(t.label, w - 16, { size: 26, weight: 800 }), { align: "center", color: tc, alpha: P(lt, 200, 700) }));
      if (has) txt(fmtV(v * clamp(kk), decOf([v])) + (s.unit || ""), x + w / 2, y + h / 2 + 30, Object.assign(fit(fmtV(v, 1) + (s.unit || ""), w - 16, { size: 26, weight: 700, font: F.display }), { align: "center", color: tc, alpha: clamp(kk) }));
      if (has) ev(a, k === 0 ? "emphasize" : "appear", { i: k });
    });
    /* 凡例（薄い → 濃い） */
    var lx = 1340, ly = T0 + 40, lk = P(lt, 400, 1000);
    for (var i = 0; i < 20; i++) { ctx.save(); ctx.globalAlpha *= lk; ctx.fillStyle = cmix(C.panel2, C.accent, .25 + .75 * i / 19); ctx.fillRect(lx + i * 20, ly, 20, 24); ctx.restore(); }
    txt(fmtV(lo, decOf([lo])) + (s.unit || ""), lx, ly + 58, { size: 22, color: C.muted, alpha: lk }); txt(fmtV(hi, decOf([hi])) + (s.unit || ""), lx + 400, ly + 58, { size: 22, color: C.muted, align: "right", alpha: lk });
    if (s.note) X.rich(s.note, lx, ly + 140, { size: 30, weight: 600, color: C.ink, alpha: P(lt, d * .5, d * .5 + 600) }, P(lt, d * .5 + 300, d * .5 + 1100));
  };

  /* ================= 流れ（サンキー図） =================
     flows: [{from, to, value}]、unit。列は流れのつながりから自動。帯が列ごとに伸び、粒が流れ続ける */
  R.sankey = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var flows = s.flows || [], names = [], col = {}, inV = {}, outV = {};
    flows.forEach(function (f) { [f.from, f.to].forEach(function (nm) { if (names.indexOf(nm) < 0) names.push(nm); }); outV[f.from] = (outV[f.from] || 0) + num(f.value); inV[f.to] = (inV[f.to] || 0) + num(f.value); });
    names.forEach(function (nm) { col[nm] = 0; }); for (var it = 0; it < names.length; it++) flows.forEach(function (f) { col[f.to] = Math.max(col[f.to], col[f.from] + 1); });
    var ncol = Math.max.apply(null, names.map(function (nm) { return col[nm]; }).concat([0])) + 1, T0 = top(s) + 10, B = 880, L = 200, Rr = 1720, nw = 26;
    var tot = function (nm) { return Math.max(inV[nm] || 0, outV[nm] || 0); }, byCol = [];
    for (var c = 0; c < ncol; c++) byCol.push(names.filter(function (nm) { return col[nm] === c; }));
    var scale = Math.min.apply(null, byCol.map(function (ns) { var sum = ns.reduce(function (a, nm) { return a + tot(nm); }, 0); return (B - T0 - (ns.length - 1) * 30) / Math.max(1, sum); }));
    var pos = {}; byCol.forEach(function (ns, c) { var sum = ns.reduce(function (a, nm) { return a + tot(nm) * scale; }, 0) + (ns.length - 1) * 30, y = T0 + (B - T0 - sum) / 2;
      ns.forEach(function (nm) { pos[nm] = { x: L + (Rr - L - nw) * c / Math.max(1, ncol - 1), y: y, h: tot(nm) * scale, o: 0, i: 0 }; y += tot(nm) * scale + 30; }); });
    var at = X.slots(ncol, d, 500, Math.max(1500, d * .3));
    var cIdx = 0; flows.forEach(function (f, fi) {
      var a = pos[f.from], b = pos[f.to], h = num(f.value) * scale, y1 = a.y + a.o, y2 = b.y + b.i; a.o += h; b.i += h;
      var t0 = at[Math.min(ncol - 1, col[f.from] + 1)] - 300, k = P(lt, t0, t0 + 1100, eio), x1 = a.x + nw, x2 = b.x, cx = (x1 + x2) / 2, colr = acc(names.indexOf(f.from));
      if (k > 0) { ctx.save(); ctx.beginPath(); ctx.rect(x1, 0, (x2 - x1) * k, 1080); ctx.clip(); ctx.globalAlpha *= .42;
        ctx.beginPath(); ctx.moveTo(x1, y1); ctx.bezierCurveTo(cx, y1, cx, y2, x2, y2); ctx.lineTo(x2, y2 + h); ctx.bezierCurveTo(cx, y2 + h, cx, y1 + h, x1, y1 + h); ctx.closePath(); ctx.fillStyle = colr; ctx.fill(); ctx.restore();
        if (k >= 1) { var r = X.rand(fi * 31 + 7); for (var p = 0; p < 3 + Math.round(h / 30); p++) { var off = r(), u = ((lt - t0) / (2600 + r() * 900) + off) % 1, yy = r() * h;
          var bx = Math.pow(1 - u, 3) * x1 + 3 * Math.pow(1 - u, 2) * u * cx + 3 * (1 - u) * u * u * cx + u * u * u * x2, by = Math.pow(1 - u, 3) * y1 + 3 * Math.pow(1 - u, 2) * u * y1 + 3 * (1 - u) * u * u * y2 + u * u * u * y2;
          ctx.save(); ctx.globalAlpha *= .85; ctx.beginPath(); ctx.arc(bx, by + yy, 4, 0, PI2); ctx.fillStyle = colr; ctx.fill(); ctx.restore(); } } }
      cIdx++;
    });
    names.forEach(function (nm, i) { var p = pos[nm], a = at[col[nm]], k = P(lt, a - 300, a + 300, eo); if (k <= 0) return;
      ctx.save(); ctx.globalAlpha *= k; rr(p.x, p.y, nw, Math.max(4, p.h * k), 6); ctx.fillStyle = acc(i); ctx.fill(); ctx.restore();
      var right = col[nm] < ncol - 1, lx = right ? p.x - 14 : p.x + nw + 14, lab2 = nm + "  " + fmtV(tot(nm), 0) + (s.unit || "");
      if (col[nm] === 0) { lx = p.x + nw + 14; right = false; }
      txt(lab2, lx, p.y + p.h / 2 + 10, Object.assign(fit(lab2, 360, { size: 26, weight: 800 }), { align: right && col[nm] !== 0 ? "right" : "left", alpha: k })); });
    at.forEach(function (a, c) { ev(a, c ? "travel" : "appear", { i: c }); });
  };

  /* ================= 回る数字（オドメーター） =================
     items: [{label, value, from, unit}]（1〜4 個）。桁が機械式のカウンターのように回って止まる */
  R.odometer = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var items = (s.items || []).slice(0, 4), n = items.length, T0 = top(s), at = X.slots(n, d, 500, Math.max(2600, d * .35));
    var rowH = Math.min(260, (900 - T0) / Math.max(1, n)), dig = Math.min(110, rowH * .55);
    items.forEach(function (it, i) {
      var target = num(it.value), from = num(it.from || 0), a = at[i], dur = Math.min(2600, Math.max(1400, d * .25)), k = P(lt, a, a + dur, eio), v = mix(from, target, k);
      var digits = Math.max(1, String(Math.floor(Math.abs(target))).length), w = dig * .72, gap = dig * .16, groups = Math.floor((digits - 1) / 3);
      var totalW = digits * w + groups * gap * 2, cx = 960, x0 = cx - totalW / 2 - 60, y = T0 + i * rowH + 10, ap = P(lt, a - 400, a);
      if (ap <= 0) return;
      txt(it.label || "", x0, y + 20, { size: 30, weight: 700, color: C.muted, alpha: ap });
      var f = v - Math.floor(v), rolls = [], dg = [];
      for (var p = 0; p < digits; p++) { var r2 = Math.floor(v / Math.pow(10, p)); dg.push(r2 % 10); rolls.push(p === 0 ? f : (dg[p - 1] === 9 ? rolls[p - 1] : 0)); }
      var x = x0;
      for (p = digits - 1; p >= 0; p--) {
        ctx.save(); ctx.globalAlpha *= ap; rr(x, y + 36, w, dig * 1.25, 12); ctx.fillStyle = C.code; ctx.fill(); ctx.lineWidth = 2; ctx.strokeStyle = C.edge; ctx.stroke(); ctx.clip();
        var off = rolls[p] * dig * 1.25, d0 = dg[p];
        [0, 1].forEach(function (m) { txt(String((d0 + m) % 10), x + w / 2, y + 36 + dig * 1.0 - off + m * dig * 1.25, { size: dig, weight: 800, font: F.mono, color: C.codeInk, align: "center" }); });
        var grd = ctx.createLinearGradient(0, y + 36, 0, y + 36 + dig * 1.25); grd.addColorStop(0, "rgba(0,0,0,.45)"); grd.addColorStop(.25, "rgba(0,0,0,0)"); grd.addColorStop(.75, "rgba(0,0,0,0)"); grd.addColorStop(1, "rgba(0,0,0,.45)");
        ctx.fillStyle = grd; ctx.fillRect(x, y + 36, w, dig * 1.25); ctx.restore();
        x += w + 4; if (p && p % 3 === 0) { txt(",", x + gap * .3, y + 36 + dig * 1.1, { size: dig * .7, weight: 800, color: C.muted, alpha: ap }); x += gap * 2; }
      }
      if (it.unit) txt(it.unit, x + 14, y + 36 + dig, { size: dig * .55, weight: 800, font: F.display, color: k >= 1 ? C.accent : C.ink, alpha: ap });
      if (k >= 1) { var gl = P(lt, a + dur, a + dur + 500) * (1 - P(lt, a + dur + 500, a + dur + 1400)); ctx.save(); ctx.globalAlpha *= gl * .8; ctx.strokeStyle = C.accent; ctx.lineWidth = 5; rr(x0 - 12, y + 24, x - x0 + 24, dig * 1.25 + 24, 18); ctx.stroke(); ctx.restore(); }
      ev(a, "count", { dur: dur }); ev(a + dur, "countEnd", { i: i });
    });
  };

  /* ================= 升目で割合（ワッフル） =================
     items: [{label, value}]、total（既定は合計）、cols（既定 10）、icon（線のアイコン名で升目を描く） */
  R.waffle = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var items = s.items || [], sum = items.reduce(function (a, it) { return a + num(it.value); }, 0), total = num(s.total) || sum || 1, cols = s.cols || 10, cells = s.cells || 100, rows = Math.ceil(cells / cols);
    var T0 = top(s) + 10, size = Math.min(70, (880 - T0) / rows - 8), gap = size * .16, gx = 160, at = X.slots(items.length, d, 500, Math.max(1300, d * .3));
    var counts = [], acc0 = 0; items.forEach(function (it) { var c = Math.round((acc0 + num(it.value)) / total * cells) - Math.round(acc0 / total * cells); counts.push(c); acc0 += num(it.value); });
    var owner = [], start = []; counts.forEach(function (c, i) { start.push(owner.length); for (var q = 0; q < c; q++) owner.push(i); });
    for (var cI = 0; cI < cells; cI++) {
      var r = Math.floor(cI / cols), c2 = cI % cols, x = gx + c2 * (size + gap), y = T0 + r * (size + gap), o = owner[cI];
      var k = o === undefined ? 0 : P(lt, at[o] + (cI - start[o]) * 28, at[o] + (cI - start[o]) * 28 + 380, back);
      ctx.save(); ctx.globalAlpha *= P(lt, 0, 500); rr(x, y, size, size, size * .22); ctx.fillStyle = C.panel2; ctx.fill(); ctx.restore();
      if (k > 0) { ctx.save(); ctx.translate(x + size / 2, y + size / 2); ctx.scale(k, k);
        if (s.icon) { ctx.restore(); X.icon(s.icon, x + size / 2, y + size / 2, size * .9 * clamp(k, 0, 1.2), { color: acc(o), k: 1, lt: 0, anim: "none" }); }
        else { rr(-size / 2, -size / 2, size, size, size * .22); ctx.fillStyle = acc(o); ctx.fill(); ctx.restore(); } }
    }
    var lx = gx + cols * (size + gap) + 90, ly = T0 + 40;
    items.forEach(function (it, i) { var a = at[i], k = P(lt, a, a + 600); if (k <= 0) return; var y = ly + i * 110;
      ctx.save(); ctx.globalAlpha *= k; rr(lx, y - 30, 36, 36, 8); ctx.fillStyle = acc(i); ctx.fill(); ctx.restore();
      txt(lab(it), lx + 56, y, Object.assign(fit(lab(it), 520, { size: 34, weight: 700 }), { alpha: k }));
      var pct = num(it.value) / total * 100 * P(lt, a, a + counts[i] * 28 + 400);
      txt(fmtV(pct, pct < 10 ? 1 : 0) + "%", lx + 56, y + 50, { size: 34, weight: 800, font: F.display, color: acc(i), alpha: k });
      ev(a, i ? "grow" : "appear", { i: i }); });
  };

  /* ================= 傾きで変化を見せる（スロープチャート） =================
     from・to（左右の見出し）、items: [{label, a, b}]、unit。線は平らな所から右の値へ傾き、上がりは ok・下がりは warn の色 */
  R.slope = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var items = s.items || [], n = items.length, T0 = top(s) + 70, B = 860, xl = 640, xr = 1280, k0 = P(lt, 0, 700);
    var vs = [].concat.apply([], items.map(function (it) { return [num(it.a), num(it.b)]; })), lo = Math.min.apply(null, vs), hi = Math.max.apply(null, vs), pad = (hi - lo) * .12 || 1;
    var yOf = function (v) { return B - (B - T0) * (v - lo + pad) / (hi - lo + pad * 2); }, at = X.slots(n, d, 600, Math.max(1300, d * .3)), dec = decOf(vs);
    [[xl, s.from || "前"], [xr, s.to || "後"]].forEach(function (p) { ctx.save(); ctx.globalAlpha *= k0; ctx.strokeStyle = C.edge; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(p[0], T0 - 20); ctx.lineTo(p[0], B + 20); ctx.stroke(); ctx.restore();
      txt(p[1], p[0], T0 - 44, { size: 34, weight: 800, font: F.display, align: "center", alpha: k0 }); });
    items.forEach(function (it, i) {
      var a0 = num(it.a), b0 = num(it.b), up = b0 >= a0, col = it.color || (up ? C.ok : C.warn), a = at[i], k = P(lt, a, a + 1000, eio), ap = P(lt, a - 300, a);
      if (ap <= 0) return;
      var y1 = yOf(a0), y2 = mix(y1, yOf(b0), k), hl = s.highlight === undefined || s.highlight === i, al = hl ? 1 : .45;
      ctx.save(); ctx.globalAlpha *= ap * al; ctx.strokeStyle = col; ctx.lineWidth = hl ? 7 : 4; ctx.lineCap = "round"; ctx.beginPath(); ctx.moveTo(xl, y1); ctx.lineTo(mix(xl, xr, Math.max(.02, k)), mix(y1, y2, 1)); ctx.stroke();
      [[xl, y1], [mix(xl, xr, Math.max(.02, k)), y2]].forEach(function (p) { ctx.beginPath(); ctx.arc(p[0], p[1], 11, 0, PI2); ctx.fillStyle = col; ctx.fill(); }); ctx.restore();
      txt(lab(it) + "  " + fmtV(a0, dec) + (s.unit || ""), xl - 26, y1 + 10, Object.assign(fit(lab(it) + "  " + fmtV(a0, dec), 470, { size: 28, weight: 700 }), { align: "right", alpha: ap * al }));
      if (k > .05) { var pc = a0 ? (b0 - a0) / Math.abs(a0) * 100 : 0, lb = fmtV(mix(a0, b0, k), dec) + (s.unit || "") + "  " + (up ? "▲" : "▼") + fmtV(Math.abs(pc * k), 0) + "%";
        txt(lb, mix(xl, xr, k) + 26, y2 + 10, { size: 28, weight: 800, color: col, alpha: ap * al * P(lt, a + 200, a + 700) }); }
      ev(a, up ? "grow" : "blocked", { i: i });
    });
  };

  /* ================= 画面の解説（スクリーンショットの上をカメラが移る） =================
     src（画像）、steps: [{rect: [x, y, w, h], note, cursor: [x, y], click, zoom}]。rect・cursor は画像の画素か 0..1 の割合。
     各手順は X.slots の時刻（ナレーションの文に合わせられる）に始まり、寄って枠と番号・注記・カーソルで見せる。frame: "browser" で窓の枠 */
  function imgBox(s, im, area) {
    var iw = im && im.naturalWidth || 1600, ih = im && im.naturalHeight || 1000, sc = Math.min(area.w / iw, area.h / ih);
    return { iw: iw, ih: ih, sc: sc, x: area.x + (area.w - iw * sc) / 2, y: area.y + (area.h - ih * sc) / 2, w: iw * sc, h: ih * sc };
  }
  function holePath(x, y, w, h, r) { var ctx = g(); r = Math.max(0, Math.min(r, w / 2, h / 2)); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath(); }
  function toPx(v, size) { return v <= 1.0001 ? v * size : v; }
  function rectPx(r, bx) { if (!r) return null; return [toPx(r[0], bx.iw), toPx(r[1], bx.ih), toPx(r[2], bx.iw), toPx(r[3], bx.ih)]; }
  function frameChrome(x, y, w, h, title, k) {
    var ctx = g(); ctx.save(); ctx.globalAlpha *= k; ctx.shadowColor = C.shadow; ctx.shadowBlur = 40; ctx.shadowOffsetY = 16; rr(x, y - 52, w, h + 52, 16); ctx.fillStyle = C.panel; ctx.fill(); ctx.shadowColor = "transparent";
    ctx.strokeStyle = C.edge; ctx.lineWidth = 1.5; ctx.stroke(); ["#ff5f57", "#febc2e", "#28c840"].forEach(function (c, i) { ctx.beginPath(); ctx.arc(x + 26 + i * 24, y - 26, 7, 0, PI2); ctx.fillStyle = c; ctx.fill(); });
    rr(x + 110, y - 40, Math.min(560, w - 140), 28, 14); ctx.fillStyle = C.panel2; ctx.fill(); ctx.restore();
    if (title) txt(title, x + 130, y - 19, { size: 18, color: C.muted, alpha: k, font: F.mono });
  }
  function drawImg(im, x, y, w, h) { var ctx = g(); if (im && im.complete && im.naturalWidth) ctx.drawImage(im, x, y, w, h); else { ctx.save(); ctx.fillStyle = C.panel2; ctx.fillRect(x, y, w, h); ctx.restore(); txt("画像を読み込み中…", x + w / 2, y + h / 2, { size: 28, color: C.muted, align: "center" }); } }
  R.tour = function (s, lt, d) {
    var ctx = g(), im = X.img(s.src), browser = s.frame === "browser", steps = s.steps || [], n = steps.length;
    var area = browser ? { x: 140, y: 150, w: 1640, h: 860 } : { x: 80, y: 60, w: 1760, h: 960 }, bx = imgBox(s, im, area), k0 = P(lt, 0, 700, eo);
    var at = X.slots(n, d, 1100, Math.max(1200, d * .14)), MOVE = 1000;
    /* 手順 i のカメラ（画像の画素の中心と倍率）。全体は {cx, cy, z: 1} */
    var camOf = function (i) { if (i < 0) return { cx: bx.iw / 2, cy: bx.ih / 2, z: 1 }; var r = rectPx(steps[i].rect, bx); if (!r) return camOf(i - 1);
      var z = steps[i].zoom || clamp(Math.min(bx.iw * .55 / r[2], bx.ih * .55 / r[3]), 1, 2.4); return { cx: r[0] + r[2] / 2, cy: r[1] + r[3] / 2, z: z }; };
    var cur = -1; for (var i = 0; i < n; i++) if (lt >= at[i]) cur = i;
    var back2 = s.overview !== false && lt > d - 1100, from = camOf(cur - 1), to = camOf(cur), mk = cur >= 0 ? P(lt, at[cur], at[cur] + MOVE, eio) : 0;
    var cam = { cx: mix(from.cx, to.cx, mk), cy: mix(from.cy, to.cy, mk), z: mix(from.z, to.z, mk) };
    if (back2) { var bk = P(lt, d - 1100, d - 200, eio), ov = camOf(-1); cam = { cx: mix(cam.cx, ov.cx, bk), cy: mix(cam.cy, ov.cy, bk), z: mix(cam.z, 1, bk) }; }
    /* カメラは画像の外が見えないように中心をおさえる */
    var vw = bx.iw / cam.z, vh = bx.ih / cam.z; cam.cx = clamp(cam.cx, vw / 2, bx.iw - vw / 2); cam.cy = clamp(cam.cy, vh / 2, bx.ih - vh / 2);
    var S = bx.sc * cam.z, tx = bx.x + bx.w / 2 - cam.cx * S, ty = bx.y + bx.h / 2 - cam.cy * S, toScr = function (px, py) { return [tx + px * S, ty + py * S]; };
    if (browser) frameChrome(bx.x, bx.y, bx.w, bx.h, s.url || "", k0);
    ctx.save(); ctx.globalAlpha *= k0; rr(bx.x, bx.y, bx.w, bx.h, browser ? 0 : 14); ctx.clip(); ctx.translate(tx, ty); ctx.scale(S, S); drawImg(im, 0, 0, bx.iw, bx.ih); ctx.restore();
    if (!browser) { ctx.save(); ctx.globalAlpha *= k0 * .9; rr(bx.x, bx.y, bx.w, bx.h, 14); ctx.strokeStyle = C.edge; ctx.lineWidth = 2; ctx.stroke(); ctx.restore(); }
    if (cur >= 0 && !back2) {
      var st = steps[cur], r = rectPx(st.rect, bx), hk = P(lt, at[cur] + MOVE * .7, at[cur] + MOVE + 300, eo);
      if (r) { var p1 = toScr(r[0], r[1]), p2 = toScr(r[0] + r[2], r[1] + r[3]), w = p2[0] - p1[0], h = p2[1] - p1[1];
        if (st.spotlight !== false) { /* 枠の外を暗くする（rr は経路を新しく始めるので、穴は手で足す） */
          ctx.save(); ctx.beginPath(); ctx.rect(bx.x, bx.y, bx.w, bx.h); holePath(p1[0] - 10, p1[1] - 10, w + 20, h + 20, 14); ctx.fillStyle = "rgba(0,0,0," + (.5 * hk) + ")"; ctx.fill("evenodd"); ctx.restore(); }
        ctx.save(); ctx.globalAlpha *= hk; ctx.lineWidth = 5; ctx.strokeStyle = C.accent; rr(p1[0] - 10, p1[1] - 10, w + 20, h + 20, 14); ctx.stroke(); ctx.restore();
        badgeNum(cur + 1, p1[0] - 10, p1[1] - 10, P(lt, at[cur] + MOVE * .8, at[cur] + MOVE + 300, back));
        if (st.note) { var nk = P(lt, at[cur] + MOVE, at[cur] + MOVE + 500, eo), nw = 520, right = p2[0] + 40 + nw < 1880, nx = right ? p2[0] + 40 : Math.max(40, p1[0] - 40 - nw), ny = clamp(p1[1], 80, 760);
          if (!right && nx + nw > p1[0] - 20) { nx = clamp(p1[0], 40, 1880 - nw); ny = p2[1] + 40 > 880 ? Math.max(80, p1[1] - 200) : p2[1] + 40; }
          cardNote(st.note, nx, ny, nw, nk); }
        if (st.cursor !== false) {
          var prevR = cur > 0 ? rectPx(steps[cur - 1].rect, bx) : null, cp = st.cursor ? [toPx(st.cursor[0], bx.iw), toPx(st.cursor[1], bx.ih)] : [r[0] + r[2] * .5, r[1] + r[3] * .55];
          var pp = cur > 0 && steps[cur - 1].cursor ? [toPx(steps[cur - 1].cursor[0], bx.iw), toPx(steps[cur - 1].cursor[1], bx.ih)] : prevR ? [prevR[0] + prevR[2] * .5, prevR[1] + prevR[3] * .55] : [bx.iw * .5, bx.ih * .9];
          var ck = P(lt, at[cur] + MOVE * .5, at[cur] + MOVE + 500, eio), sp = toScr(mix(pp[0], cp[0], ck), mix(pp[1], cp[1], ck)), clickAt = at[cur] + MOVE + 650, down = st.click && lt >= clickAt && lt < clickAt + 260;
          if (st.click && lt >= clickAt) { var rk = P(lt, clickAt, clickAt + 700); ctx.save(); ctx.globalAlpha *= 1 - rk; ctx.strokeStyle = C.accent; ctx.lineWidth = 4; ctx.beginPath(); ctx.arc(sp[0], sp[1], 10 + 50 * rk, 0, PI2); ctx.stroke(); ctx.restore(); }
          X.cursor(sp[0], sp[1], down, lt); }
      }
    }
    /* 効果音のきっかけは条件の外で（場面の最後のコマで集めるため） */
    for (i = 0; i < n; i++) { ev(at[i], "nav", { i: i }); if (steps[i].note) ev(at[i] + MOVE, "note", { i: i }); if (steps[i].click) ev(at[i] + MOVE + 650, "click", { i: i }); }
    if (s.caption) txt(s.caption, 960, 1060, { size: 26, color: C.muted, align: "center", alpha: k0 });
  };

  /* ================= 長い画面をスクロールして見せる =================
     src（縦に長いスクリーンショット）、stops: [{y, note, rect}]（y は 0..1 の位置か画素。そこで止まって注記）、url */
  R.scrollshot = function (s, lt, d) {
    var ctx = g(), im = X.img(s.src), stops = s.stops || [], n = stops.length, k0 = P(lt, 0, 700, eo);
    var fx = 160, fy = 150, fw = 1120, fh = 860, iw = im && im.naturalWidth || 1200, ih = im && im.naturalHeight || 3000, sc = fw / iw, maxScroll = Math.max(0, ih * sc - fh);
    var at = X.slots(n, d, 900, Math.max(1200, d * .15)), MOVE = 1100;
    var yOf = function (i) { if (i < 0) return 0; var v = stops[i].y; v = v <= 1.0001 ? v * maxScroll : v * sc - fh * .25; return clamp(v, 0, maxScroll); };
    var cur = -1; for (var i = 0; i < n; i++) if (lt >= at[i]) cur = i;
    var y = cur < 0 ? 0 : mix(yOf(cur - 1), yOf(cur), P(lt, at[cur], at[cur] + MOVE, eio));
    frameChrome(fx, fy, fw, fh, s.url || "", k0);
    ctx.save(); ctx.globalAlpha *= k0; ctx.beginPath(); ctx.rect(fx, fy, fw, fh); ctx.clip(); drawImg(im, fx, fy - y, fw, ih * sc); ctx.restore();
    /* スクロールバー */
    if (maxScroll > 0) { var th = fh * fh / (ih * sc), tyy = fy + (fh - th) * y / maxScroll; ctx.save(); ctx.globalAlpha *= k0 * .7; rr(fx + fw - 12, tyy + 4, 6, th - 8, 3); ctx.fillStyle = C.muted; ctx.fill(); ctx.restore(); }
    if (cur >= 0) { var st = stops[cur], nk = P(lt, at[cur] + MOVE * .8, at[cur] + MOVE + 400, eo);
      if (st.rect) { var r = st.rect, rx = fx + toPx(r[0], iw) * sc, ry = fy + toPx(r[1], ih) * sc - y, rw = toPx(r[2], iw) * sc, rh = toPx(r[3], ih) * sc;
        ctx.save(); ctx.globalAlpha *= nk; ctx.lineWidth = 5; ctx.strokeStyle = C.accent; rr(rx - 8, ry - 8, rw + 16, rh + 16, 12); ctx.stroke(); ctx.restore(); badgeNum(cur + 1, rx - 8, ry - 8, nk); }
      if (st.note) cardNote(st.note, fx + fw + 50, clamp(fy + 100 + cur % 3 * 60, 100, 760), 1880 - fx - fw - 50, nk, { size: 30 }); }
    for (i = 0; i < n; i++) { ev(at[i], "sweep", { i: i }); if (stops[i].note) ev(at[i] + MOVE, "note", { i: i }); }
  };

  /* ================= 前と後の画面をなぞって比べる =================
     before・after（画像）、labels: ["前", "後"]、境目が左右に動いて比べ、最後は後の画面に */
  R.swipe = function (s, lt, d) {
    var ctx = g(), A = X.img(s.before), B = X.img(s.after), k0 = P(lt, 0, 700, eo), area = { x: 120, y: s.heading ? 270 : 120, w: 1680, h: s.heading ? 760 : 880 };
    X.heading(s, lt);
    var bx = imgBox(s, B || A, area), labels = s.labels || ["Before", "After"], a1 = 900, a2 = d * .45, a3 = d * .7;
    var sx = lt < a2 ? mix(1, .5, P(lt, a1, a1 + 1100, eio)) : lt < a3 ? .5 + .22 * Math.sin((lt - a2) / (a3 - a2) * PI2) : mix(.5, 0, P(lt, a3, a3 + 1100, eio));
    ctx.save(); ctx.globalAlpha *= k0; ctx.shadowColor = C.shadow; ctx.shadowBlur = 36; ctx.shadowOffsetY = 14; rr(bx.x, bx.y, bx.w, bx.h, 16); ctx.fillStyle = C.panel; ctx.fill(); ctx.restore();
    ctx.save(); ctx.globalAlpha *= k0; rr(bx.x, bx.y, bx.w, bx.h, 16); ctx.clip(); drawImg(B, bx.x, bx.y, bx.w, bx.h);
    ctx.beginPath(); ctx.rect(bx.x, bx.y, bx.w * sx, bx.h); ctx.clip(); drawImg(A, bx.x, bx.y, bx.w, bx.h); ctx.restore();
    var lx = bx.x + bx.w * sx;
    if (sx > .001 && sx < .999) { ctx.save(); ctx.globalAlpha *= k0; ctx.fillStyle = C.accent; ctx.fillRect(lx - 3, bx.y, 6, bx.h); ctx.beginPath(); ctx.arc(lx, bx.y + bx.h / 2, 30, 0, PI2); ctx.fill(); ctx.restore();
      txt("◀ ▶", lx, bx.y + bx.h / 2 + 8, { size: 20, weight: 900, align: "center", color: C.onAccent, alpha: k0 }); }
    var chip = function (t, x, y, al, on) { var w = tw(t, { size: 26, weight: 800 }) + 40; ctx.save(); ctx.globalAlpha *= al; rr(x, y, w, 46, 23); ctx.fillStyle = on ? C.accent : "rgba(0,0,0,.6)"; ctx.fill(); ctx.restore();
      txt(t, x + 20, y + 32, { size: 26, weight: 800, color: on ? C.onAccent : "#ffffff", alpha: al }); return w; };
    chip(labels[0], bx.x + 20, bx.y + 20, k0 * clamp(sx * 4), false);
    var w2 = tw(labels[1], { size: 26, weight: 800 }) + 40; chip(labels[1], bx.x + bx.w - 20 - w2, bx.y + 20, k0 * clamp((1 - sx) * 4), sx < .05);
    if (s.caption) txt(s.caption, 960, Math.min(1060, bx.y + bx.h + 50), { size: 28, color: C.muted, align: "center", alpha: k0 });
    ev(a1, "sweep"); ev(a3 + 1100, "reveal");
  };
}); }
