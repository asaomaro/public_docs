/* motion-video parts-extra — 図解の部品（漏斗・ピラミッド・ベン図・循環・四象限・暦・チェックリスト・対決・順位・キー操作）。
 * どれも (s, lt, d) だけで決まる描画。X は engine.js の描画の道具（HELP）で、今の Canvas は X.g()。
 * 効果音のきっかけ（X.sfxEv）と揺れ（X.shakeEv）は、場面の最初に一度集めるので条件の外で呼ぶ。 */
if (!window.__mvPartsExtra) { window.__mvPartsExtra = 1; (window.MotionVideoParts = window.MotionVideoParts || []).push(function (R, X) {
  "use strict";
  var C = X.C, F = X.F, P = X.P, lin = X.lin, eo = X.eo, eio = X.eio, back = X.back, clamp = X.clamp, mix = X.mix;
  var txt = X.txt, tw = X.tw, rr = X.rr, acc = X.accentAt, ev = X.sfxEv, g = X.g, fmt = X.fmtNum, PI2 = Math.PI * 2;
  function top(s) { return s.heading ? 300 : 190; }
  function num(v) { var n = parseFloat(String(v).replace(/,/g, "")); return isFinite(n) ? n : 0; }
  function lab(it) { return typeof it === "string" ? it : (it && (it.label || it.text || it.title)) || ""; }
  function fit(s, maxW, o) { var size = o.size; while (size > 14 && tw(s, Object.assign({}, o, { size: size })) > maxW) size -= 2; return Object.assign({}, o, { size: size }); }

  /* ---- 漏斗: 段が上から落ちて重なり、段の間に歩留まり（%） ---- */
  R.funnel = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var items = s.items || [], n = Math.max(1, items.length), y0 = top(s) - 20, hTot = 880 - y0, gap = 14, bh = (hTot - gap * (n - 1)) / n, cx = 760, wTop = 1080, wBot = 300;
    var at = X.slots(n, d, 500, Math.max(1200, d * .3)), v0 = num(items[0] && items[0].value);
    items.forEach(function (it, i) {
      ev(at[i], "appear", { i: i });
      var k = P(lt, at[i], at[i] + 650, back), a = clamp(P(lt, at[i], at[i] + 300) * 1.2); if (a <= 0) return;
      var y = y0 + i * (bh + gap), w1 = mix(wTop, wBot, i / n), w2 = mix(wTop, wBot, (i + 1) / n), dy = (1 - k) * -120;
      ctx.save(); ctx.globalAlpha *= a; ctx.translate(0, dy);
      ctx.beginPath(); ctx.moveTo(cx - w1 / 2, y); ctx.lineTo(cx + w1 / 2, y); ctx.lineTo(cx + w2 / 2, y + bh); ctx.lineTo(cx - w2 / 2, y + bh); ctx.closePath();
      var gr = ctx.createLinearGradient(cx - w1 / 2, 0, cx + w1 / 2, 0); gr.addColorStop(0, acc(i)); gr.addColorStop(1, C.panel2); ctx.fillStyle = gr; ctx.fill();
      var sh = P(lt, at[i] + 400, at[i] + 1100); if (sh > 0 && sh < 1) { ctx.save(); ctx.clip(); ctx.fillStyle = "rgba(255,255,255,.28)"; ctx.fillRect(cx - w1 / 2 + (w1 + 200) * sh - 200, y, 90, bh); ctx.restore(); }
      var lo = fit(lab(it), w2 - 60, { size: Math.min(40, bh * .42), weight: 800 });
      txt(lab(it), cx, y + bh / 2 + lo.size * .36, Object.assign(lo, { align: "center", color: C.onAccent }));
      var vk = P(lt, at[i] + 200, at[i] + 1100), vx = cx + wTop / 2 + 60;
      if (it.value !== undefined) txt(fmt(String(it.value) + (s.unit || ""), vk), vx, y + bh / 2 + 6, { size: Math.min(46, bh * .45), weight: 800, font: F.display, color: acc(i) });
      if (i > 0 && v0 && it.value !== undefined) { var pv = num(items[i - 1].value), rate = pv ? Math.round(num(it.value) / pv * 100) : 0;
        txt("↓ " + rate + "%", vx, y + bh / 2 + 6 + Math.min(46, bh * .45) * .9, { size: 24, weight: 700, color: C.muted, alpha: P(lt, at[i] + 700, at[i] + 1200) }); }
      ctx.restore();
    });
  };

  /* ---- ピラミッド: 下の段から積み上がる。items は上から順 ---- */
  R.pyramid = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var items = s.items || [], n = Math.max(1, items.length), y0 = top(s) - 10, yB = 900, cx = 640, halfB = 520, gap = 8, bh = (yB - y0 - gap * (n - 1)) / n;
    var at = X.slots(n, d, 400, Math.max(1200, d * .3));
    for (var j = n - 1; j >= 0; j--) (function (i, order) {
      var a = at[order], it = items[i]; ev(a, "step", { i: order });
      var k = P(lt, a, a + 700, back); if (k <= 0) return;
      var yt = y0 + i * (bh + gap), yb = yt + bh, ht = (yt - y0) / (yB - y0) * halfB, hb = (yb - y0) / (yB - y0) * halfB;
      ctx.save(); ctx.globalAlpha *= clamp(k * 2); ctx.translate(0, (1 - k) * 90);
      ctx.beginPath(); ctx.moveTo(cx - ht, yt); ctx.lineTo(cx + ht, yt); ctx.lineTo(cx + hb, yb); ctx.lineTo(cx - hb, yb); ctx.closePath();
      ctx.fillStyle = acc(i); ctx.fill(); ctx.globalAlpha *= .25; ctx.fillStyle = "#000"; ctx.beginPath(); ctx.moveTo(cx, yt); ctx.lineTo(cx + ht, yt); ctx.lineTo(cx + hb, yb); ctx.lineTo(cx, yb); ctx.closePath(); ctx.fill(); ctx.restore();
      var tk = P(lt, a + 300, a + 900), ly = (yt + yb) / 2, lx = cx + (ht + hb) / 2 + 30;
      ctx.save(); ctx.strokeStyle = acc(i); ctx.lineWidth = 2; ctx.setLineDash([6, 6]); ctx.globalAlpha *= tk; ctx.beginPath(); ctx.moveTo(lx, ly); ctx.lineTo(mix(lx, 1180, tk), ly); ctx.stroke(); ctx.restore();
      txt(lab(it), 1200, ly - (it.text ? 4 : -12), { size: 40, weight: 800, alpha: tk });
      if (it.text) txt(it.text, 1200, ly + 38, { size: 26, color: C.muted, alpha: P(lt, a + 500, a + 1100) });
    })(j, n - 1 - j);
  };

  /* ---- ベン図: 円が外から寄って重なり、重なりに言葉が弾む ---- */
  R.venn = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var sets = (s.sets || []).slice(0, 3), n = sets.length, cy = top(s) + 330, rad = n === 3 ? 250 : 290, off = n === 3 ? 170 : 200;
    var pos = n === 3 ? [[-off, -off * .55], [off, -off * .55], [0, off * .75]] : n === 2 ? [[-off, 0], [off, 0]] : [[0, 0]];
    sets.forEach(function (st, i) {
      var a = 400 + i * 400, k = P(lt, a, a + 900, back), p = pos[i], ang = Math.atan2(p[1] || -1, p[0] || .01), far = (1 - k) * 700;
      ev(a, "appear", { i: i }); if (k <= 0) return;
      var x = 960 + p[0] + Math.cos(ang) * far, y = cy + p[1] + Math.sin(ang) * far;
      ctx.save(); ctx.globalCompositeOperation = "source-over"; ctx.globalAlpha *= .3 * clamp(k * 2); ctx.fillStyle = acc(i); ctx.beginPath(); ctx.arc(x, y, rad, 0, PI2); ctx.fill();
      ctx.globalAlpha = clamp(k * 2); ctx.strokeStyle = acc(i); ctx.lineWidth = 4; ctx.stroke(); ctx.restore();
      var lx = x + (p[0] ? Math.sign(p[0]) * rad * .45 : 0), ly = y + (p[1] > 0 ? rad * .45 : p[1] < 0 ? -rad * .25 : 0);
      txt(lab(st), lx, ly, { size: 38, weight: 800, align: "center", color: acc(i), alpha: P(lt, a + 500, a + 900) });
      if (st.text) txt(st.text, lx, ly + 40, { size: 24, align: "center", color: C.muted, alpha: P(lt, a + 700, a + 1100) });
    });
    if (s.center) { var ca = 400 + n * 400 + 300, ck = P(lt, ca, ca + 600, back); ev(ca, "emphasize");
      if (ck > 0) { var cyy = cy + (n === 3 ? 10 : 0), cw = tw(s.center, { size: 34, weight: 800 }) + 44;
        ctx.save(); ctx.translate(960, cyy); ctx.scale(ck, ck); rr(-cw / 2, -32, cw, 64, 32); ctx.fillStyle = C.accent; ctx.shadowColor = C.accent; ctx.shadowBlur = 20 + 10 * Math.sin(lt / 300); ctx.fill();
        ctx.shadowBlur = 0; txt(s.center, 0, 12, { size: 34, weight: 800, align: "center", color: C.onAccent }); ctx.restore(); } }
  };

  /* ---- 循環: 項目が輪に並び、矢印が順につながり、印が回り続ける ---- */
  R.cycle = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var items = s.items || [], n = Math.max(1, items.length), cx = 960, cy = top(s) + 320, Rr = 300, nr = 92;
    var at = X.slots(n, d, 400, Math.max(1500, d * .35)), done = at[n - 1] + 900;
    var ang = function (i) { return -Math.PI / 2 + i * PI2 / n; };
    items.forEach(function (it, i) {
      var a = at[i], a2 = a + 450, k2 = P(lt, a2, a2 + 600, eio); ev(a2, "connect", { i: i });
      if (k2 <= 0) return; var a0 = ang(i) + nr / Rr * 1.1, a1 = ang(i + 1) - nr / Rr * 1.1, ae = mix(a0, a1, k2);
      ctx.save(); ctx.strokeStyle = C.edge; ctx.lineWidth = 6; ctx.lineCap = "round"; ctx.beginPath(); ctx.arc(cx, cy, Rr, a0, ae); ctx.stroke();
      ctx.fillStyle = C.edge; ctx.translate(cx + Math.cos(ae) * Rr, cy + Math.sin(ae) * Rr); ctx.rotate(ae + Math.PI / 2); ctx.beginPath(); ctx.moveTo(12, 0); ctx.lineTo(-10, -11); ctx.lineTo(-10, 11); ctx.closePath(); ctx.fill(); ctx.restore();
    });
    if (lt > done) { var rot = ((lt - done) / 2600) * PI2 - Math.PI / 2; ctx.save(); ctx.fillStyle = C.accent2; ctx.shadowColor = C.accent2; ctx.shadowBlur = 18;
      ctx.beginPath(); ctx.arc(cx + Math.cos(rot) * Rr, cy + Math.sin(rot) * Rr, 11, 0, PI2); ctx.fill(); ctx.restore(); }
    var hot = lt > done ? Math.floor((((lt - done) / 2600) * n + .5) % n) : -1;
    items.forEach(function (it, i) {
      var a = at[i], k = P(lt, a, a + 600, back); ev(a, "appear", { i: i }); if (k <= 0) return;
      var x = cx + Math.cos(ang(i)) * Rr, y = cy + Math.sin(ang(i)) * Rr, on = i === hot;
      ctx.save(); ctx.translate(x, y); ctx.scale(k * (on ? 1.08 : 1), k * (on ? 1.08 : 1));
      ctx.beginPath(); ctx.arc(0, 0, nr, 0, PI2); ctx.fillStyle = C.panel; ctx.shadowColor = C.shadow; ctx.shadowBlur = 24; ctx.fill(); ctx.shadowBlur = 0;
      ctx.lineWidth = on ? 7 : 4; ctx.strokeStyle = acc(i); ctx.stroke();
      if (it.icon) X.iconAny(it.icon, 0, -26, 46, acc(i), P(lt, a, a + 900), lt);
      var lo = fit(lab(it), nr * 1.7, { size: 30, weight: 800 }); txt(lab(it), 0, it.icon ? 38 : 11, Object.assign(lo, { align: "center" })); ctx.restore();
    });
    if (s.center) txt(s.center, cx, cy + 14, { size: 42, weight: 800, align: "center", font: F.display, color: C.accent, alpha: P(lt, 300, 900) });
  };

  /* ---- 四象限: 軸が伸び、象限の名前、点が弾んで置かれる。x・y は 0..1 ---- */
  R.matrix = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var L = 560, T = top(s) - 30, S = 900 - T, Rr = L + S * 1.25, B = T + S, cxm = (L + Rr) / 2, cym = (T + B) / 2, ak = P(lt, 200, 1000, eio);
    ev(200, "grow");
    var q = s.quadrants || [], qp = [[L, T], [cxm, T], [L, cym], [cxm, cym]];
    qp.forEach(function (p, i) { var qk = P(lt, 700 + i * 150, 1200 + i * 150); ctx.save(); ctx.globalAlpha *= qk * (s.highlight === i ? .22 + .08 * Math.sin(lt / 300) : .08);
      ctx.fillStyle = s.highlight === i ? C.accent : acc(i); ctx.fillRect(p[0] + 3, p[1] + 3, (Rr - L) / 2 - 6, S / 2 - 6); ctx.restore();
      if (q[i]) txt(q[i], p[0] + (Rr - L) / 4, p[1] + (i < 2 ? 50 : S / 2 - 26), { size: 28, weight: 800, align: "center", color: s.highlight === i ? C.accent : C.muted, alpha: qk }); });
    ctx.save(); ctx.strokeStyle = C.ink; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(cxm, cym); ctx.lineTo(mix(cxm, Rr, ak), cym); ctx.moveTo(cxm, cym); ctx.lineTo(mix(cxm, L, ak), cym);
    ctx.moveTo(cxm, cym); ctx.lineTo(cxm, mix(cym, T, ak)); ctx.moveTo(cxm, cym); ctx.lineTo(cxm, mix(cym, B, ak)); ctx.stroke(); ctx.restore();
    if (s.xLabel) txt(s.xLabel + " →", Rr, B + 44, { size: 26, weight: 700, align: "right", color: C.muted, alpha: ak });
    if (s.yLabel) txt("↑ " + s.yLabel, L - 20, T + 10, { size: 26, weight: 700, align: "right", color: C.muted, alpha: ak });
    var items = s.items || [], at = X.slots(items.length, d, 1300, Math.max(1000, d * .25));
    items.forEach(function (it, i) { ev(at[i], "appear", { i: i }); var k = P(lt, at[i], at[i] + 600, back); if (k <= 0) return;
      var x = mix(L, Rr, clamp(it.x)), y = mix(B, T, clamp(it.y)), r = (it.size || 1) * 16;
      ctx.save(); ctx.fillStyle = acc(i); ctx.beginPath(); ctx.arc(x, y, r * k, 0, PI2); ctx.fill();
      ctx.strokeStyle = acc(i); ctx.lineWidth = 2; ctx.globalAlpha *= (1 - P(lt, at[i], at[i] + 900)) * .8; ctx.beginPath(); ctx.arc(x, y, r + 50 * P(lt, at[i], at[i] + 900), 0, PI2); ctx.stroke(); ctx.restore();
      txt(lab(it), x + r + 12, y + 9, { size: 26, weight: 700, alpha: P(lt, at[i] + 200, at[i] + 600) }); });
  };

  /* ---- 暦: ひと月のマスが斜めの波で並び、予定の日に印が付く ---- */
  R.calendar = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var days = s.days || 30, start = s.start || 0, wk = s.weekdays || ["日", "月", "火", "水", "木", "金", "土"], rows = Math.ceil((start + days) / 7);
    var y0 = top(s) + (s.month ? 40 : 0), cw = 150, ch = Math.min(110, (880 - y0 - 50) / rows), x0 = 960 - cw * 3.5 - (s.side ? 250 : 0), evs = s.events || [];
    if (s.month) txt(s.month, x0, y0 - 30, { size: 44, weight: 800, font: F.display, alpha: P(lt, 100, 600) });
    wk.forEach(function (w, i) { txt(w, x0 + cw * i + cw / 2, y0 + 30, { size: 24, weight: 700, align: "center", color: i === 0 ? C.warn : C.muted, alpha: P(lt, 200 + i * 40, 600 + i * 40) }); });
    for (var dd = 1; dd <= days; dd++) { var p = start + dd - 1, c = p % 7, r = Math.floor(p / 7), a = 300 + (c + r) * 60, k = P(lt, a, a + 400, back); if (k <= 0) continue;
      var x = x0 + c * cw, y = y0 + 50 + r * ch; ctx.save(); ctx.translate(x + cw / 2, y + ch / 2); ctx.scale(k, k);
      rr(-cw / 2 + 4, -ch / 2 + 4, cw - 8, ch - 8, 10); ctx.fillStyle = C.panel; ctx.fill(); ctx.restore();
      txt(String(dd), x + 16, y + 36, { size: 24, weight: 700, color: c === 0 ? C.warn : C.ink, alpha: k }); }
    ev(300, "appear");
    var at = X.slots(evs.length, d, 300 + (rows + 7) * 60 + 300, Math.max(1000, d * .2));
    evs.forEach(function (e, i) { ev(at[i], "badge", { i: i }); var k = P(lt, at[i], at[i] + 600, back); if (k <= 0) return;
      var p = start + (e.day || 1) - 1, c = p % 7, r = Math.floor(p / 7), x = x0 + c * cw, y = y0 + 50 + r * ch, col = acc(i);
      ctx.save(); ctx.strokeStyle = col; ctx.lineWidth = 4; ctx.globalAlpha *= clamp(k); rr(x + 4, y + 4, cw - 8, ch - 8, 10); ctx.stroke();
      if (e.day === s.highlight) { ctx.globalAlpha *= .4 + .3 * Math.sin(lt / 250); ctx.lineWidth = 10; rr(x - 2, y - 2, cw + 4, ch + 4, 14); ctx.stroke(); } ctx.restore();
      ctx.save(); ctx.translate(x + cw - 22, y + 24); ctx.scale(k, k); ctx.fillStyle = col; ctx.beginPath(); ctx.arc(0, 0, 9, 0, PI2); ctx.fill(); ctx.restore();
      var lo = fit(e.label || "", cw - 24, { size: 20, weight: 700 }); txt(e.label || "", x + 14, y + ch - 20, Object.assign(lo, { color: col, alpha: P(lt, at[i] + 200, at[i] + 600) }));
      if (s.side) { var sy = y0 + 60 + i * 64; txt("● " + (e.day) + "日", x0 + cw * 7 + 60, sy, { size: 26, weight: 800, color: col, alpha: P(lt, at[i] + 200, at[i] + 700) });
        txt(e.label || "", x0 + cw * 7 + 190, sy, { size: 26, weight: 600, alpha: P(lt, at[i] + 200, at[i] + 700) }); } });
  };

  /* ---- チェックリスト: 項目が並び、印が描かれ、下の進み具合が伸びる ---- */
  R.checklist = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var items = s.items || [], n = items.length, y0 = top(s) + 10, lh = Math.min(96, (760 - y0) / Math.max(1, n)), at = X.slots(n, d, 600, Math.max(1500, d * .3)), done = 0, total = 0;
    items.forEach(function (it, i) {
      var o = typeof it === "string" ? { text: it, done: true } : Object.assign({ done: true }, it), y = y0 + i * lh, a = at[i];
      total++; ev(a - 300, "appear", { i: i }); if (o.done) ev(a + 250, "done", { i: i });
      var ak = P(lt, a - 400, a); if (ak <= 0) return;
      var ck = o.done ? P(lt, a, a + 500, eio) : 0; if (ck >= 1) done++;
      ctx.save(); ctx.globalAlpha *= ak; ctx.translate((1 - ak) * -30, 0);
      rr(300, y - 30, 48, 48, 10); ctx.lineWidth = 3; ctx.strokeStyle = o.done && ck > 0 ? C.ok : C.edge; ctx.stroke();
      if (ck > 0) { ctx.save(); ctx.globalAlpha *= ck; rr(300, y - 30, 48, 48, 10); ctx.fillStyle = C.ok; ctx.fill(); ctx.restore();
        ctx.strokeStyle = C.bg0; ctx.lineWidth = 6; ctx.lineCap = "round"; ctx.lineJoin = "round"; ctx.beginPath(); var c1 = clamp(ck * 2), c2 = clamp(ck * 2 - 1);
        ctx.moveTo(312, y - 6); ctx.lineTo(mix(312, 322, c1), mix(y - 6, y + 4, c1)); if (c2 > 0) ctx.lineTo(mix(322, 338, c2), mix(y + 4, y - 16, c2)); ctx.stroke(); }
      txt(o.text || "", 380, y + 7, { size: 38, weight: 600, color: ck >= 1 ? C.ink : C.muted });
      if (o.note) txt(o.note, 1620, y + 7, { size: 26, weight: 700, align: "right", color: ck >= 1 ? C.ok : C.warn, alpha: P(lt, a + 300, a + 700) });
      ctx.restore();
    });
    var bk = P(lt, at[0] || 0, (at[n - 1] || 0) + 500), frac = clamp(done / Math.max(1, total)), by = Math.min(900, y0 + n * lh + 30);
    ctx.save(); ctx.globalAlpha *= P(lt, 300, 800); rr(300, by, 1320, 18, 9); ctx.fillStyle = C.edge; ctx.fill();
    if (frac > 0) { rr(300, by, 1320 * frac, 18, 9); ctx.fillStyle = C.ok; ctx.fill(); } ctx.restore();
    txt(Math.round(frac * 100) + "%", 1620, by - 14, { size: 30, weight: 800, align: "right", font: F.display, color: C.ok, alpha: bk });
  };

  /* ---- 対決: 左右が斜めの境目で滑り込み、VS が叩きつけられる。winner で勝者が光る ---- */
  R.versus = function (s, lt, d) {
    var ctx = g(), L = s.left || {}, Rt = s.right || {}, k = P(lt, 150, 850, eo), vs = 950, vk = P(lt, vs, vs + 300);
    ev(150, "enter"); ev(vs, "hit"); X.shakeEv(vs + 200, 16, 420);
    var sl = 110;
    [[L, -1, C.accent], [Rt, 1, C.accent2]].forEach(function (q) {
      var side = q[0], sd = q[1], col = side.color ? (C[side.color] || side.color) : q[2], off = (1 - k) * 1100 * sd;
      ctx.save(); ctx.translate(off, 0); ctx.beginPath();
      if (sd < 0) { ctx.moveTo(0, 0); ctx.lineTo(960 + sl, 0); ctx.lineTo(960 - sl, 1080); ctx.lineTo(0, 1080); } else { ctx.moveTo(960 + sl, 0); ctx.lineTo(1920, 0); ctx.lineTo(1920, 1080); ctx.lineTo(960 - sl, 1080); }
      ctx.closePath(); ctx.globalAlpha *= .9; var gr = ctx.createLinearGradient(sd < 0 ? 0 : 1920, 0, 960, 0); gr.addColorStop(0, C.bg0); gr.addColorStop(1, col);
      ctx.fillStyle = gr; ctx.globalAlpha *= .55; ctx.fill(); ctx.restore();
      var cx = 960 + sd * 470 + off, win = s.winner === (sd < 0 ? "left" : "right"), wk = win ? P(lt, vs + 900, vs + 1500, back) : 0;
      if (side.icon) X.iconAny(side.icon, cx, 380, 150, col, P(lt, 300, 1200), lt);
      var lo = fit(side.label || "", 700, { size: 84, weight: 900, font: F.display });
      txt(side.label || "", cx, side.icon ? 560 : 480, Object.assign(lo, { align: "center", color: C.ink }));
      if (side.value !== undefined) txt(fmt(String(side.value), P(lt, 900, 2200)), cx, (side.icon ? 560 : 480) + 110, { size: 72, weight: 800, align: "center", font: F.display, color: col });
      (side.points || []).forEach(function (p, i) { var pa = 1400 + i * 300; ev(pa, "appear", { i: i }); txt(p, cx, (side.icon ? 560 : 480) + 180 + i * 50, { size: 30, align: "center", color: C.muted, alpha: P(lt, pa, pa + 400) }); });
      if (wk > 0) { ctx.save(); ctx.translate(cx, 250); ctx.scale(wk, wk); ctx.fillStyle = C.warn; ctx.beginPath();
        ctx.moveTo(-60, 30); ctx.lineTo(-70, -30); ctx.lineTo(-30, 0); ctx.lineTo(0, -45); ctx.lineTo(30, 0); ctx.lineTo(70, -30); ctx.lineTo(60, 30); ctx.closePath(); ctx.fill(); ctx.restore();
        ctx.save(); ctx.strokeStyle = col; ctx.lineWidth = 6; ctx.globalAlpha *= .5 + .3 * Math.sin(lt / 250); rr(cx - 400, 170, 800, 700, 30); ctx.stroke(); ctx.restore(); }
    });
    if (s.winner) ev(vs + 900, "emphasize");
    if (vk > 0) { var sc = mix(3.2, 1, eo(vk)); ctx.save(); ctx.translate(960, 540); ctx.scale(sc, sc); ctx.rotate(-.12);
      ctx.fillStyle = C.bg0; ctx.beginPath(); ctx.arc(0, 0, 105, 0, PI2); ctx.fill(); ctx.strokeStyle = C.warn; ctx.lineWidth = 8; ctx.stroke();
      txt(s.vs || "VS", 0, 30, { size: 88, weight: 900, align: "center", font: F.display, color: C.warn, alpha: clamp(vk * 3) }); ctx.restore(); }
    X.burst(960, 540, lt - vs - 200, { n: 40, seed: 9, r: 520 });
    if (s.heading) X.animText(s.heading, 960, 130, { size: 46, weight: 800, align: "center", font: F.display }, "rise", lt, 200, 600);
  };

  /* ---- 順位: 下の順位から棒が伸び、1 位が最後に光る ---- */
  R.ranking = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var items = (s.items || []).slice().map(function (it, i) { return { label: lab(it), value: num(it.value), raw: it.value, icon: it.icon, i: i }; });
    if (s.sort !== false) items.sort(function (a, b) { return b.value - a.value; });
    var n = items.length, y0 = top(s), lh = Math.min(110, (900 - y0) / Math.max(1, n)), max = Math.max.apply(null, items.map(function (x) { return x.value; }).concat([1]));
    var at = X.slots(n, d, 500, Math.max(1500, d * .3)), medal = ["#e7b53c", "#b9c3cc", "#c98a4b"];
    items.forEach(function (it, rank) {
      var a = at[n - 1 - rank], k = P(lt, a, a + 900, eio), y = y0 + rank * lh; ev(a, rank === 0 ? "emphasize" : "grow", { i: rank }); if (rank === 0) ev(a + 900, "countEnd");
      var ap = P(lt, a - 250, a); if (ap <= 0) return;
      ctx.save(); ctx.globalAlpha *= ap;
      ctx.beginPath(); ctx.arc(260, y + lh / 2 - 6, 30, 0, PI2); ctx.fillStyle = rank < 3 ? medal[rank] : C.panel2; ctx.fill();
      txt(String(rank + 1), 260, y + lh / 2 + 5, { size: 30, weight: 900, align: "center", color: rank < 3 ? "#1b1b1b" : C.ink });
      txt(it.label, 320, y + lh / 2 + 6, Object.assign(fit(it.label, 330, { size: 34, weight: 700 }), {}));
      var bx = 680, bw = 1000 * it.value / max * k, bh = Math.min(56, lh * .6);
      rr(bx, y + lh / 2 - 6 - bh / 2, Math.max(bh * .5, bw), bh, bh / 2); ctx.fillStyle = rank === 0 ? C.accent : acc(rank + 1); ctx.globalAlpha *= rank === 0 ? 1 : .8; ctx.fill();
      if (rank === 0 && k >= 1) { ctx.save(); ctx.clip(); var sh = ((lt - a - 900) % 1800) / 1800; ctx.fillStyle = "rgba(255,255,255,.3)"; ctx.fillRect(bx + (bw + 200) * sh - 200, 0, 80, 1080); ctx.restore(); }
      ctx.globalAlpha = ap; txt(fmt(String(it.raw) + (s.unit || ""), k), bx + Math.max(bh * .5, bw) + 18, y + lh / 2 + 6, { size: 32, weight: 800, font: F.display, color: rank === 0 ? C.accent : C.ink });
      ctx.restore();
      if (rank === 0) X.burst(bx + bw, y + lh / 2 - 6, lt - a - 900, { n: 26, seed: 4, r: 260 });
    });
  };

  /* ---- キー操作: キーの頭が落ちてきて、順に押し込まれる。combos: [{keys:[…], label}] ---- */
  R.keys = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var combos = s.combos || (s.keys ? [{ keys: s.keys, label: s.label }] : []), n = combos.length, y0 = top(s) + (n === 1 ? 180 : 40), lh = n === 1 ? 0 : Math.min(190, (860 - y0) / n);
    var at = X.slots(n, d, 400, Math.max(1200, d * .25));
    combos.forEach(function (cb, i) {
      var keys = cb.keys || [], a = at[i], y = y0 + i * lh, big = n === 1, kh = big ? 170 : 110, fs = big ? 60 : 40;
      var widths = keys.map(function (k) { return Math.max(kh, tw(k, { size: fs, weight: 800 }) + (big ? 90 : 60)); }), plus = big ? 80 : 56;
      var tot = widths.reduce(function (p, w) { return p + w; }, 0) + plus * Math.max(0, keys.length - 1), x = big ? 960 - tot / 2 : 180, press = a + 300 + keys.length * 160;
      keys.forEach(function (k, j) {
        var ka = a + j * 160, kk = P(lt, ka, ka + 500, back); ev(ka, "type", { i: j }); if (kk <= 0) { x += widths[j] + plus; return; }
        var down = clamp(P(lt, press + j * 70, press + j * 70 + 90) - P(lt, press + 700, press + 850)), w = widths[j], dy = down * (big ? 12 : 8);
        ctx.save(); ctx.translate(0, (1 - kk) * -160); ctx.globalAlpha *= clamp(kk * 2);
        rr(x, y + (big ? 16 : 10), w, kh, 18); ctx.fillStyle = C.edge; ctx.fill();
        rr(x, y + dy, w, kh, 18); ctx.fillStyle = down > .5 ? C.accent : C.panel; ctx.fill(); ctx.lineWidth = 2; ctx.strokeStyle = C.edge; ctx.stroke();
        txt(k, x + w / 2, y + dy + kh / 2 + fs * .36, { size: fs, weight: 800, align: "center", font: F.mono, color: down > .5 ? C.onAccent : C.ink });
        ctx.restore();
        if (j < keys.length - 1) txt("+", x + w + plus / 2, y + kh / 2 + fs * .3, { size: fs * .8, weight: 700, align: "center", color: C.muted, alpha: kk });
        x += w + plus;
      });
      ev(press, "click", { i: i });
      if (cb.label) { var lk = P(lt, press + 150, press + 650); if (big) X.animText(cb.label, 960, y + kh + 130, { size: 52, weight: 800, align: "center", font: F.display }, "pop", lt, press + 150, 600);
        else txt("→ " + cb.label, x + 10, y + kh / 2 + 14, { size: 36, weight: 700, color: C.accent, alpha: lk }); }
      if (P(lt, press, press + 200) > 0 && lt < press + 900) { ctx.save(); ctx.strokeStyle = C.accent; ctx.lineWidth = 3; var rq = lin(lt, press, press + 900); ctx.globalAlpha *= 1 - rq;
        rr((big ? 960 - tot / 2 : 180) - 20 - rq * 40, y - 20 - rq * 40, tot + 40 + rq * 80, kh + 56 + rq * 80, 26); ctx.stroke(); ctx.restore(); }
    });
  };
}); }
