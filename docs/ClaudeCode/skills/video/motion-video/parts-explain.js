/* motion-video parts-explain — しくみ・変化・数を説明する図解（流れて満ちる・なだらかにする・段ごとの棒・ちぢんでも保つ・粗い目盛りへ寄せる・
 * 線を刈る・大ぜいから 1 つへ・点の年表・点の数・1 行ずつの表）。
 * 2026-10-07 に、解説動画「蒸留」「AI の暴走」（yukkuri-work の kaisetsu-distill・kaisetsu-ai-bousou）の組み立て役が描き下ろした図解を、
 * ほかの題材でも使える部品に直して足した。字・数字は、どれも場面の JSON で渡す（絵に書き込まない）。
 * どれも (s, lt, d) だけで決まる描画。色は配色（C）から取る。
 * 進む時: 既定は、場面の長さ d の中の割合（項目が並ぶ物は X.slots = 字幕の文の数が項目の数と同じなら、文が始まる時）。
 *         s.at に、場面の頭からの秒を並べると、その時に進む（at: [3.2, 7.5]。書かなかった所は既定）。 */
if (!window.__mvPartsExplain) { window.__mvPartsExplain = 1; (window.MotionVideoParts = window.MotionVideoParts || []).push(function (R, X) {
  "use strict";
  var C = X.C, F = X.F, P = X.P, eo = X.eo, back = X.back, clamp = X.clamp, mix = X.mix;
  var txt = X.txt, tw = X.tw, rr = X.rr, acc = X.accentAt, ev = X.sfxEv, g = X.g, PI2 = Math.PI * 2;
  function top(s) { return s.heading ? 300 : 190; }
  function num(v) { var n = parseFloat(String(v).replace(/,/g, "")); return isFinite(n) ? n : 0; }
  function int(v, def, lo, hi) { var n = Math.round(num(v === undefined || v === null ? def : v)); return Math.max(lo, Math.min(hi, n)); }
  function lab(it) { return typeof it === "string" ? it : (it && (it.label || it.text || it.title)) || ""; }
  function fit(t, maxW, o) { var size = o.size; while (size > 24 && tw(t, Object.assign({}, o, { size: size })) > maxW) size -= 2; return Object.assign({}, o, { size: size }); }
  /* s.at（秒）があれば、その時。無ければ既定（ms） */
  function when(s, defs) { var a = Array.isArray(s.at) ? s.at : s.at === undefined || s.at === null ? [] : [s.at];
    return defs.map(function (v, i) { return a[i] === undefined || a[i] === null ? v : num(a[i]) * 1000; }); }
  /* 色の名前: "warn"・"ok"・"ink"・"muted"・数（配色の何番目か）。無ければ def */
  function tone(v, def) { return v === "warn" ? C.warn : v === "ok" ? C.ok : v === "ink" ? C.ink : v === "muted" ? C.muted : typeof v === "number" ? acc(v) : def; }
  function pop(k) { return 1 + .16 * Math.sin(clamp(k) * Math.PI); }
  function line(ctx, x1, y1, x2, y2, col, w, a, dash) { if (a <= 0) return; ctx.save(); ctx.globalAlpha *= clamp(a); ctx.strokeStyle = col; ctx.lineWidth = w; ctx.lineCap = "round"; if (dash) ctx.setLineDash(dash);
    ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke(); ctx.restore(); }
  function dot(ctx, x, y, r, col, a) { if (a <= 0 || r <= 0) return; ctx.save(); ctx.globalAlpha *= clamp(a); ctx.fillStyle = col; ctx.beginPath(); ctx.arc(x, y, r, 0, PI2); ctx.fill(); ctx.restore(); }
  /* 枠と、うすい塗りの箱 */
  function box(ctx, x, y, w, h, col, a, fillA, r) { if (a <= 0) return; ctx.save(); ctx.globalAlpha *= clamp(a); rr(x, y, w, h, r || 22); ctx.save(); ctx.globalAlpha *= clamp(fillA); ctx.fillStyle = col; ctx.fill(); ctx.restore();
    ctx.strokeStyle = col; ctx.lineWidth = 9; ctx.lineJoin = "round"; ctx.stroke(); ctx.restore(); }
  function chip(ctx, cx, cy, t, fill, ink, k, size) { if (k <= 0) return; var w = Math.max(190, tw(t, { size: size, weight: 800 }) + 56), h = size + 32, z = pop(k); ctx.save(); ctx.globalAlpha *= clamp(k); ctx.translate(cx, cy); ctx.scale(z, z);
    rr(-w / 2, -h / 2, w, h, 16); ctx.fillStyle = fill; ctx.fill(); txt(t, 0, size * .36, { size: size, weight: 800, align: "center", color: ink }); ctx.restore(); }
  /* 幅に収まる 1〜maxN 行にする（"\n" か配列なら、そこで折る。収まらなければ字を小さく） */
  function fitLines(t, maxW, o, maxN) { var raw = Array.isArray(t) ? t.map(String) : String(t === undefined || t === null ? "" : t).split("\n"), size = o.size, L, oo; maxN = maxN || 2;
    for (;;) { oo = Object.assign({}, o, { size: size }); L = raw.length > 1 ? raw : X.wrap(raw[0], maxW, oo);
      if ((L.length <= maxN && !L.some(function (x) { return tw(x, oo) > maxW; })) || size <= 24) return { lines: L.slice(0, maxN), o: oo }; size -= 2; } }
  function drawLines(fl, x, cy, alpha, color) { var z = fl.o.size, n = fl.lines.length; fl.lines.forEach(function (t, i) {
    txt(t, x, cy + (i - (n - 1) / 2) * z * 1.28 + z * .36, Object.assign({}, fl.o, { align: "center", alpha: alpha, color: color || fl.o.color })); }); }
  function note(s, lt, at) { if (s.note) txt(s.note, 960, 945, fit(s.note, 1600, { size: 40, weight: 700, align: "center", color: C.muted, alpha: P(lt, at, at + 500) })); }
  function side(v) { return typeof v === "string" ? { label: v } : v || {}; }

  /* ---- 流れて満ちる: 大きな箱から小さな箱へ、つぶが流れ続け、受ける側が少しずつ明るくなる。後から名札 ----
     {type:"flowfill", heading, from:{label:"大きなモデル", name:"先生"}, to:{label:"小さなモデル", name:"生徒"}, label:"知識を移す", fill:0.5（最後の明るさ 0..1）, note, at:[名札 1, 名札 2]} */
  R.flowfill = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var A = side(s.from), B = side(s.to), cy = top(s) + (s.heading ? 300 : 340), LX = 540, RX = 1400, LS = 320, RS = 170, k0 = P(lt, 0, 500), c1 = acc(0), c2 = acc(1), i, j;
    var ts = when(s, [d * .5, d * .5 + 1100]), fillTo = s.fill === undefined ? .5 : clamp(num(s.fill)), glow = mix(.08, fillTo, clamp((lt - 1200) / Math.max(1, d - 2400)));
    box(ctx, LX - LS / 2, cy - LS / 2, LS, LS, c1, k0, .2, 26);
    for (i = 0; i < 5; i++) for (j = 0; j < 5; j++) dot(ctx, LX + (i - 2) * 56, cy + (j - 2) * 56, 11, c1, k0 * (.55 + .45 * Math.sin(lt / 420 + i * 1.7 + j * 2.3)));
    box(ctx, RX - RS / 2, cy - RS / 2, RS, RS, c2, k0, glow, 22);
    for (i = 0; i < 2; i++) for (j = 0; j < 2; j++) dot(ctx, RX + (i - .5) * 64, cy + (j - .5) * 64, 11, c2, k0 * clamp(.3 + glow));
    var x0 = LX + LS / 2 + 18, x1 = RX - RS / 2 - 18;
    if (lt >= 600) for (i = 0; i < 7; i++) { var p = ((lt - 600) / 2400 + i / 7) % 1, a = Math.sin(p * Math.PI); dot(ctx, mix(x0, x1, p), cy + (i % 3 - 1) * 36 * (1 - p) - a * 28, 14 - 5 * p, c2, k0 * a); }
    if (s.label) txt(s.label, (x0 + x1) / 2, cy + 124, fit(s.label, x1 - x0 - 20, { size: 42, weight: 800, align: "center", color: C.ink, alpha: k0 * P(lt, 900, 1400) }));
    if (A.label) txt(A.label, LX, cy + LS / 2 + 66, fit(A.label, 640, { size: 44, weight: 800, align: "center", color: C.ink, alpha: k0 }));
    if (B.label) txt(B.label, RX, cy + LS / 2 + 66, fit(B.label, 600, { size: 44, weight: 800, align: "center", color: C.ink, alpha: k0 }));
    if (A.name) { ev(ts[0], "pop"); chip(ctx, LX, cy - LS / 2 - 66, A.name, c1, C.onAccent, P(lt, ts[0], ts[0] + 450), 50); }
    if (B.name) { ev(ts[1], "pop"); chip(ctx, RX, cy - LS / 2 - 66, B.name, c2, C.onAccent, P(lt, ts[1], ts[1] + 450), 50); }
    note(s, lt, ts[1] + 600);
  };

  /* ---- なだらかにする: つまみを上げると、1 本だけ高かった棒が下がり、ほかがのびる（順位はそのまま） ----
     {type:"softenbars", heading, items:[{label, from, to}], knob:"温度", low:"低い", high:"高い", labels:["とがった答え","なだらかな答え"], note, at:[つまみが上がる時]} */
  var SOFT = [{ from: 340, to: 200 }, { from: 7, to: 104 }, { from: 4, to: 58 }, { from: 5, to: 76 }];
  R.softenbars = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var items = (s.items && s.items.length ? s.items : SOFT).slice(0, 8), n = items.length, T = top(s) + (s.heading ? 0 : 40), k0 = P(lt, 0, 500), ts = when(s, [d * .38]), k2 = P(lt, ts[0], ts[0] + Math.min(1800, d * .25), eo);
    var vmax = Math.max.apply(null, items.map(function (it) { return Math.max(num(it.from), num(it.to)); }).concat([1e-9])), hot = 0; items.forEach(function (it, i) { if (num(it.from) > num(items[hot].from)) hot = i; });
    var SX = 340, ST = T + 150, SB = T + 420, ky = mix(SB - 30, ST + 30, k2), kc = k2 > 0 ? acc(1) : C.ink, BASE = T + 490, HMAX = 330, cx = 1090, pit = Math.min(200, 1100 / n), bw = pit * .62, L = s.labels || [];
    ev(ts[0], "whoosh");
    line(ctx, SX, ST, SX, SB, C.muted, 12, k0 * .7);
    txt(s.high === undefined ? "高い" : s.high, SX, ST - 36, { size: 40, weight: 700, align: "center", color: C.muted, alpha: k0 });
    txt(s.low === undefined ? "低い" : s.low, SX, SB + 62, { size: 40, weight: 700, align: "center", color: C.muted, alpha: k0 });
    ctx.save(); ctx.globalAlpha *= k0; rr(SX - 48, ky - 24, 96, 48, 14); ctx.fillStyle = kc; ctx.fill(); ctx.restore();
    if (s.knob) txt(s.knob, SX, SB + 128, fit(s.knob, 420, { size: 48, weight: 800, align: "center", color: kc, alpha: k0 }));
    line(ctx, cx - pit * n / 2 - 20, BASE, cx + pit * n / 2 + 20, BASE, C.muted, 6, k0 * .8);
    items.forEach(function (it, i) { var gk = P(lt, 500 + i * 200, 1200 + i * 200, eo), h = Math.max(8, mix(num(it.from), num(it.to), k2) / vmax * HMAX * gk), x = cx + (i - (n - 1) / 2) * pit, col = i === hot ? acc(0) : k2 > .15 ? acc(1) : C.muted;
      ctx.save(); ctx.globalAlpha *= k0 * gk; rr(x - bw / 2, BASE - h, bw, h, 10); ctx.fillStyle = col; ctx.fill(); ctx.restore();
      if (lab(it)) txt(lab(it), x, BASE + 52, fit(lab(it), pit - 16, { size: 36, weight: 700, align: "center", color: C.ink, alpha: k0 * gk })); });
    var ta = clamp(k2 * 2), tb = clamp(k2 * 2 - 1);
    if (L[0] && ta < 1) txt(L[0], cx, T + 100, fit(L[0], 1000, { size: 50, weight: 800, align: "center", color: C.ink, alpha: k0 * (1 - ta) }));
    if (L[1] && tb > 0) txt(L[1], cx, T + 100, fit(L[1], 1000, { size: 50, weight: 800, align: "center", color: acc(1), alpha: k0 * tb }));
    note(s, lt, ts[0] + 2200);
  };

  /* ---- 段ごとの棒: 横棒が、指定した時（か、字幕の文）ごとに 1 本ずつのびて、数字が数え上がる ----
     {type:"stepbars", heading, lead:"まちがいの数", items:[{label, value}], unit:"", highlight:[1]（色を付ける棒。既定は最後）, note, at:[秒, 秒…]} */
  R.stepbars = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var items = (s.items || []).slice(0, 6), n = Math.max(1, items.length), y0 = top(s) + (s.lead ? 110 : 20), pit = Math.min(170, (890 - y0) / n), bh = Math.min(72, pit * .5); y0 += Math.max(0, (890 - y0 - pit * n) / 2 - 40);
    var vmax = Math.max.apply(null, items.map(function (it) { return num(it.value); }).concat([1e-9])), lx = 620, bx = 650, bw = 700, hi = s.highlight === undefined ? [items.length - 1] : [].concat(s.highlight), unit = s.unit || "";
    var ts = when(s, X.slots(n, d, 700, 1500));
    if (s.lead) txt(s.lead, 960, y0 - 40, fit(s.lead, 1500, { size: 44, weight: 800, align: "center", color: C.muted, alpha: P(lt, 0, 500) }));
    items.forEach(function (it, i) { var t = ts[i], la = P(lt, t, t + 400); if (la <= 0) return; ev(t + 250, "pop", { i: i });
      var k = P(lt, t + 250, t + 1150, eo), y = y0 + i * pit + pit / 2, hot = hi.indexOf(i) >= 0, col = hot ? acc(0) : C.muted, w = Math.max(10, bw * num(it.value) / vmax * k), v = X.count(String(it.value), k) + (it.unit === undefined ? unit : it.unit);
      txt(lab(it), lx, y + 15, fit(lab(it), 500, { size: 42, weight: 800, align: "right", color: hot ? col : C.ink, alpha: la }));
      if (k <= 0) return;
      ctx.save(); rr(bx, y - bh / 2, w, bh, 12); ctx.fillStyle = col; ctx.fill(); ctx.restore();
      var o = fit(v, 1840 - (bx + bw * num(it.value) / vmax + 24), { size: 76, weight: 800, font: F.display, color: hot ? col : C.ink });
      txt(v, bx + w + 24, y + o.size * .36, Object.assign({}, o, { size: o.size * pop(k) })); });
    note(s, lt, ts[n - 1] + 1500);
  };

  /* ---- ちぢんでも保つ: 同じ大きさの箱の片方がちぢんで「〇%減」。下に、ほぼ満ちたままのメーター ----
     {type:"shrinkkeep", heading, left:"元の物", right:"小さくした物", shrink:40（面積で何 % 減るか）, shrinkLabel:"大きさ", shrinkText:"40%減",
      meter:{label:"言葉を理解する力", value:97, max:100, unit:"%"}, note, at:[ちぢむ時, メーターの時]} */
  R.shrinkkeep = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var m = s.meter, T = top(s) + (s.heading ? 0 : 40), k0 = P(lt, 0, 500), ts = when(s, [900, d * .45]), ka = P(lt, ts[0], ts[0] + 1100, eo), sh = clamp(num(s.shrink === undefined ? 40 : s.shrink) / 100);
    var S0 = 260, S1 = S0 * mix(1, Math.sqrt(1 - sh), ka), LX = 420, RX = 800, BY = T + (m ? 290 : 380), c1 = acc(0), c2 = acc(1);
    ev(ts[0], "whoosh");
    box(ctx, LX - S0 / 2, BY - S0, S0, S0, c1, k0, .2, 20);
    if (s.left) txt(s.left, LX, BY + 60, fit(s.left, 350, { size: 42, weight: 800, align: "center", color: c1, alpha: k0 }));
    if (ka > 0) { ctx.save(); ctx.globalAlpha *= k0 * .6 * ka; ctx.strokeStyle = C.muted; ctx.lineWidth = 5; ctx.setLineDash([12, 14]); rr(RX - S0 / 2, BY - S0, S0, S0, 20); ctx.stroke(); ctx.restore(); }
    box(ctx, RX - S1 / 2, BY - S1, S1, S1, c2, k0, .3, 20);
    if (s.right) txt(s.right, RX, BY + 60, fit(s.right, 350, { size: 42, weight: 800, align: "center", color: c2, alpha: k0 }));
    var q = clamp((ka - .5) * 2), st = s.shrinkText === undefined ? Math.round(sh * 100) + "%減" : s.shrinkText;
    if (s.shrinkLabel) txt(s.shrinkLabel, 1400, BY - S0 + 46, fit(s.shrinkLabel, 700, { size: 46, weight: 800, align: "center", color: C.ink, alpha: k0 * P(lt, 300, 700) }));
    if (q > 0 && st) { var so = fit(st, 720, { size: 100, weight: 800, font: F.display, align: "center", color: c2, alpha: q }); txt(st, 1400, BY - 14, Object.assign({}, so, { size: so.size * pop(q) })); }
    if (m) { var la = P(lt, ts[1], ts[1] + 400), kb = P(lt, ts[1] + 500, ts[1] + 1400, eo), MX = 240, MW = 1060, MY = BY + 232, MH = 56, mv = String(m.value === undefined ? 100 : m.value), mmax = num(m.max === undefined ? 100 : m.max) || 100;
      ev(ts[1] + 500, "pop");
      if (m.label) txt(m.label, MX, MY - 54, fit(m.label, MW, { size: 42, weight: 800, color: C.ink, alpha: la }));
      ctx.save(); ctx.globalAlpha *= la; rr(MX, MY - MH / 2, MW, MH, 14); ctx.fillStyle = C.panel2 || C.panel; ctx.fill(); ctx.strokeStyle = C.muted; ctx.lineWidth = 5; ctx.stroke();
      if (kb > 0) { rr(MX, MY - MH / 2, Math.max(20, MW * clamp(num(mv) / mmax) * kb), MH, 14); ctx.fillStyle = c2; ctx.fill(); } ctx.restore();
      if (kb > 0) { var vt = X.count(mv, kb) + (m.unit === undefined ? "%" : m.unit), vo = fit(vt, 1860 - (MX + MW + 30), { size: 88, weight: 800, font: F.display, color: c2 }); txt(vt, MX + MW + 30, MY + vo.size * .36, Object.assign({}, vo, { size: vo.size * pop(kb) })); } }
    note(s, lt, ts[1] + 1800);
  };

  /* ---- 粗い目盛りへ寄せる: 細かい目盛りの上の点が、粗い目盛りの近い段へ落ちて寄る ----
     {type:"snapruler", heading, fine:32, coarse:4, points:[0.07, 0.19, …（0..1）], labels:["細かい目盛り","粗い目盛り"], result:["32ビット","8ビット"], note, at:[点が落ちる時, result の時]} */
  R.snapruler = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var T = top(s) + (s.heading ? 0 : 40), L = 260, Rx = 1660, TY = T + 160, BY = T + 370, NF = int(s.fine, 32, 2, 64), NC = int(s.coarse, 4, 1, 16), PV = (s.points || [.07, .19, .38, .56, .70, .93]).slice(0, 12).map(function (v) { return clamp(num(v)); });
    var Lb = s.labels || [], k0 = P(lt, 0, 500), t1 = Math.min(1300, d * .15), kb = P(lt, t1, t1 + 500), ts = when(s, [Math.max(t1 + 800, d * .3), d * .72]), stag = Math.min(260, d * .25 / Math.max(1, PV.length)), c2 = acc(1), i, cnt = {};
    if (Lb[0]) txt(Lb[0], 960, TY - 96, fit(Lb[0], 1400, { size: 44, weight: 800, align: "center", color: C.ink, alpha: k0 }));
    if (Lb[1]) txt(Lb[1], 960, BY + 78, fit(Lb[1], 1400, { size: 44, weight: 800, align: "center", color: c2, alpha: k0 * kb }));
    line(ctx, L, TY, Rx, TY, C.ink, 6, k0); for (i = 0; i <= NF; i++) line(ctx, mix(L, Rx, i / NF), TY, mix(L, Rx, i / NF), TY + (i * NC % NF === 0 ? 34 : 20), C.ink, 4, k0 * .9);
    line(ctx, L, BY, Rx, BY, c2, 10, k0 * kb); for (i = 0; i <= NC; i++) line(ctx, mix(L, Rx, i / NC), BY - 34, mix(L, Rx, i / NC), BY, c2, 10, k0 * kb);
    ev(t1, "tick");
    PV.forEach(function (pv, i) { var tg = Math.round(pv * NC), off = (cnt[tg] || 0) * 40; cnt[tg] = (cnt[tg] || 0) + 1; var at = ts[0] + i * stag, m = P(lt, at, at + 900, eo), sx = mix(L, Rx, pv), tx = mix(L, Rx, tg / NC), x = mix(sx, tx, m), y = mix(TY - 28, BY - 58 - off, m);
      ev(at + 800, "tick", { i: i });
      if (m > 0 && m < 1) line(ctx, sx, TY - 28, x, y, c2, 4, k0 * .6 * (1 - m), [6, 12]);
      dot(ctx, sx, TY - 28, 17, C.ink, k0 * (m > 0 ? .28 : 1)); if (m > 0) dot(ctx, x, y, 17, c2, k0); });
    var r = s.result, k1 = P(lt, ts[1], ts[1] + 500);
    if (r && k1 > 0) { ev(ts[1], "pop"); var z = 60 * pop(k1), ry = BY + 176; r = [].concat(r);
      if (r.length > 1) { txt(String(r[0]), 960 - 70, ry, fit(String(r[0]), 760, { size: z, weight: 800, align: "right", color: C.ink, alpha: k1 })); txt("→", 960, ry, { size: z, weight: 800, align: "center", color: c2, alpha: k1 });
        txt(String(r[1]), 960 + 70, ry, fit(String(r[1]), 760, { size: z * 1.12, weight: 800, color: c2, alpha: k1 })); }
      else txt(String(r[0]), 960, ry, fit(String(r[0]), 1500, { size: z, weight: 800, align: "center", color: c2, alpha: k1 })); }
    note(s, lt, ts[1] + 900);
  };

  /* ---- 線を刈る: 丸と線の網の線の何本かに×が付いて点線になり、消える（丸は残る） ----
     {type:"prunenet", heading, layers:[3,4,3], cut:9（刈る本数。番号の配列でもよい。既定は 4 割ほど）, seed:7, label:"つながりを刈る", note, at:[刈り始める時]} */
  R.prunenet = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var Ly = (s.layers && s.layers.length > 1 ? s.layers : [3, 4, 3]).slice(0, 5).map(function (v) { return int(v, 3, 1, 6); }), nl = Ly.length, T = top(s) + (s.heading ? 0 : 30), TOP = T + 10, BOT = T + (s.label ? 480 : 560), k0 = P(lt, 0, 500);
    function nx(c) { return mix(460, 1460, c / (nl - 1)); } function ny(c, r) { return TOP + (BOT - TOP) * (r + .5) / Ly[c]; }
    var E = [], c, i, j; for (c = 0; c < nl - 1; c++) for (i = 0; i < Ly[c]; i++) for (j = 0; j < Ly[c + 1]; j++) E.push([c, i, j]);
    var dead = {}, nd = 0, rnd = X.rand(int(s.seed, 7, 1, 1e9)), key = E.map(function () { return rnd(); });
    if (Array.isArray(s.cut)) s.cut.forEach(function (v) { v = int(v, 0, 0, 1e6); if (v < E.length && dead[v] === undefined) dead[v] = nd++; });
    else { var want = int(s.cut, Math.round(E.length * .38), 0, E.length), idx = E.map(function (_, q) { return q; }).sort(function (p, q) { return key[p] - key[q] || p - q; }).slice(0, want).sort(function (p, q) { return p - q; }); idx.forEach(function (v) { dead[v] = nd++; }); }
    var ts = when(s, [Math.max(1300, d * .25)]), stag = Math.min(190, d * .3 / Math.max(1, nd)), gs = Math.min(40, 1000 / E.length), r = nl > 3 || Math.max.apply(null, Ly) > 4 ? 24 : 30;
    E.forEach(function (e, n) { var gk = P(lt, 300 + n * gs, 800 + n * gs), x1 = nx(e[0]), y1 = ny(e[0], e[1]), x2 = nx(e[0] + 1), y2 = ny(e[0] + 1, e[2]);
      if (dead[n] === undefined) { line(ctx, x1, y1, x2, y2, C.ink, 6, k0 * gk * .6); return; }
      var t0 = ts[0] + dead[n] * stag, mk = P(lt, t0, t0 + 350), cut = P(lt, t0 + 500, t0 + 1200, eo); ev(t0, "tick", { i: dead[n] });
      line(ctx, x1, y1, x2, y2, mk > 0 ? C.warn : C.ink, 6, k0 * gk * (mk > 0 ? 1 : .6) * (1 - cut), mk > 0 ? [10, 16] : null);
      if (mk > 0 && cut < 1) { var mx = (x1 + x2) / 2, my = (y1 + y2) / 2, z = 20 * mk; line(ctx, mx - z, my - z, mx + z, my + z, C.warn, 10, k0 * (1 - cut)); line(ctx, mx + z, my - z, mx - z, my + z, C.warn, 10, k0 * (1 - cut)); } });
    for (c = 0; c < nl; c++) for (i = 0; i < Ly[c]; i++) dot(ctx, nx(c), ny(c, i), r, acc(0), k0);
    var kl = P(lt, ts[0], ts[0] + 500);
    if (s.label && kl > 0) { var lo = fit(s.label, 1500, { size: 56, weight: 800, align: "center", color: acc(1), alpha: kl }); txt(s.label, 960, BOT + 84, Object.assign({}, lo, { size: lo.size * pop(kl) })); }
    note(s, lt, ts[0] + nd * stag + 1200);
  };

  /* ---- 大ぜいから 1 つへ: 左の大ぜい → 中央の 1 つ → 右の 1 つへ、つぶが流れる。後から、中央の下に一言 ----
     {type:"funnelflow", heading, many:6, manyLabel:"たくさんの質問", mid:"よその\nAI", to:"自分の\nモデル", label:"答え", mark:"許しがない", note, at:[mark の時]} */
  R.funnelflow = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var T = top(s) + (s.heading ? 0 : 40), AX = 340, MX = 960, RX = 1540, CY = T + 255, MS = 240, RS = 170, nP = int(s.many, 6, 2, 8), k0 = P(lt, 0, 500), c1 = acc(0), c2 = acc(1), i, j;
    var ts = when(s, [d * .6]), glow = mix(.1, .55, clamp((lt - 2500) / Math.max(1, d - 3500)));
    for (i = 0; i < nP; i++) { var ay = mix(T + 40, T + 460, i / (nP - 1)), gk = P(lt, 200 + i * 110, 600 + i * 110, eo);
      dot(ctx, AX, ay - 14, 15, C.ink, k0 * gk); ctx.save(); ctx.globalAlpha *= k0 * gk; ctx.fillStyle = C.ink; ctx.beginPath(); ctx.arc(AX, ay + 28, 26, Math.PI, 0); ctx.fill(); ctx.restore();
      if (lt >= 700) for (j = 0; j < 3; j++) { var p = ((lt - 700) / 1500 + j / 3 + i * .17) % 1; dot(ctx, mix(AX + 46, MX - MS / 2 - 16, p), mix(ay, CY, p), 9, C.ink, k0 * Math.sin(p * Math.PI) * .85); } }
    box(ctx, MX - MS / 2, CY - MS / 2, MS, MS, c1, k0, .2, 24);
    if (s.mid) drawLines(fitLines(s.mid, MS - 44, { size: 50, weight: 800 }), MX, CY, k0, c1);
    box(ctx, RX - RS / 2, CY - RS / 2, RS, RS, c2, k0, glow, 20);
    if (lt >= 1900) for (i = 0; i < 6; i++) { var q = ((lt - 1900) / 1300 + i / 6) % 1; dot(ctx, mix(MX + MS / 2 + 14, RX - RS / 2 - 16, q), CY + (i % 3 - 1) * 30 * (1 - q), 11, c2, k0 * Math.sin(q * Math.PI)); }
    if (s.manyLabel) txt(s.manyLabel, AX, T + 556, fit(s.manyLabel, 520, { size: 42, weight: 800, align: "center", color: C.ink, alpha: k0 * P(lt, 700, 1200) }));
    if (s.label) txt(s.label, (MX + MS / 2 + RX - RS / 2) / 2, CY - 66, fit(s.label, RX - RS / 2 - MX - MS / 2 - 20, { size: 44, weight: 800, align: "center", color: c2, alpha: k0 * P(lt, 1900, 2400) }));
    if (s.to) { var fl = fitLines(s.to, 520, { size: 44, weight: 800 }); drawLines(fl, RX, CY + RS / 2 + 30 + fl.lines.length * fl.o.size * .64, k0, c2); }
    var k1 = P(lt, ts[0], ts[0] + 500);
    if (s.mark && k1 > 0) { ev(ts[0], "pop"); var mo = fit(s.mark, 620, { size: 58, weight: 800, align: "center", color: C.warn, alpha: k1 }); txt(s.mark, MX, CY + MS / 2 + 84, Object.assign({}, mo, { size: mo.size * pop(k1) })); }
    note(s, lt, ts[0] + 1000);
  };

  /* ---- 点の年表: 横の線の上に、点と日付が順に 1 つずつ出る。2 点の間に「◯日後」の印 ----
     {type:"dottimeline", heading, items:[{date:"7月8日", label:"伝言板", color}], gap:{from:2, to:3, label:"5日後", at:秒}（gaps で配列も）, note, at:[秒, 秒…]} */
  R.dottimeline = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var items = (s.items || []).slice(0, 6), n = Math.max(1, items.length), T = top(s) + (s.heading ? 0 : 40), LY = T + 310, L = 230, Rx = 1690, gaps = (s.gaps || (s.gap ? [s.gap] : [])).filter(function (G) { return items[G.from] && items[G.to]; });
    var colW = n > 1 ? (Rx - L) / (n - 1) - 40 : 900, ts = when(s, X.slots(n, d, 500, gaps.length ? 2600 : 1200)), k0 = P(lt, 0, 600), ext = (L - 110) + 130 * k0;
    function px(i) { var it = items[i] || {}; return it.pos !== undefined ? mix(L, Rx, clamp(num(it.pos))) : n < 2 ? 960 : mix(L, Rx, i / (n - 1)); }
    function col(i) { var gi = -1; gaps.forEach(function (G) { if (G.from === i) gi = 0; if (G.to === i) gi = 1; }); return tone((items[i] || {}).color, gi >= 0 ? acc(gi) : C.ink); }
    var A = items.map(function (_, i) { return P(lt, ts[i], ts[i] + 450, eo); });
    items.forEach(function (_, i) { ext = Math.max(ext, mix(L - 110, px(i) + (i === items.length - 1 ? 110 : 60), A[i])); });
    line(ctx, L - 110, LY, ext, LY, C.muted, 8, .8);
    items.forEach(function (it, i) { var a = A[i], x = px(i), c = col(i); if (a <= 0) return; ev(ts[i], "pop", { i: i });
      dot(ctx, x, LY, 20 * (1 + .5 * Math.sin(clamp(a) * Math.PI)), c, a);
      if (it.date) txt(String(it.date), x, LY - 52, fit(String(it.date), colW + 20, { size: 50, weight: 800, font: F.display, align: "center", color: c, alpha: a }));
      if (lab(it)) { var fl = fitLines(lab(it), colW, { size: 42, weight: 800 }); drawLines(fl, x, LY + 78 + fl.lines.length * fl.o.size * .64, a, C.ink); } });
    var last = ts[n - 1];
    gaps.forEach(function (G) { var tg = G.at !== undefined ? num(G.at) * 1000 : Math.max(ts[G.from], ts[G.to]) + 1000, k5 = P(lt, tg, tg + 500, eo); last = Math.max(last, tg); if (k5 <= 0) return; ev(tg, "whoosh");
      var x1 = px(G.from), x2 = px(G.to), yy = LY - 150, c = tone(G.color, acc(1));
      line(ctx, x1, yy, mix(x1, x2, k5), yy, c, 8, 1); line(ctx, x1, yy - 14, x1, yy + 14, c, 8, 1); if (k5 >= 1) line(ctx, x2, yy - 14, x2, yy + 14, c, 8, 1);
      if (G.label) { var go = fit(G.label, Math.max(300, Math.abs(x2 - x1) + 200), { size: 58, weight: 800, align: "center", color: c, alpha: k5 }); txt(G.label, (x1 + x2) / 2, yy - 34, Object.assign({}, go, { size: go.size * pop(k5) })); } });
    note(s, lt, last + 900);
  };

  /* ---- 点の数: 点 N 個（既定 100）のうち n 個が色づき、数字が上がる ----
     {type:"dotgrid", heading, total:100, count:79, cols:10, title:"o3", sub:"OpenAIのモデル", label:"100回のうち", unit:"回", color:"warn", order:"random"（"row" で頭から順）, seed:7, note, at:[色づく時]} */
  R.dotgrid = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var N = int(s.total, 100, 1, 400), n = int(s.count, 0, 0, N), cols = int(s.cols, Math.ceil(Math.sqrt(N)), 1, 40), rows = Math.ceil(N / cols), T = top(s) + (s.heading ? 0 : 30), hasT = s.title || s.sub;
    var GT = T + (hasT ? 100 : 10), GX = 220, PT = Math.min(700 / cols, (870 - GT) / rows, 70), GW = cols * PT, GH = rows * PT, k0 = P(lt, 0, 500), col = tone(s.color, acc(0)), i, j;
    var ts = when(s, [Math.min(d * .3, 2400)]), kh = P(lt, ts[0], ts[0] + 400), dur = Math.min(1600, d * .25), kn = clamp((lt - ts[0] - 700) / dur), cur = Math.round(n * eo(kn)), rank = [];
    if (s.order === "row") for (i = 0; i < N; i++) rank.push(i);
    else { var rnd = X.rand(int(s.seed, 7, 1, 1e9)), key = []; for (i = 0; i < N; i++) key.push(rnd()); for (i = 0; i < N; i++) { var rk = 0; for (j = 0; j < N; j++) if (key[j] < key[i] || (key[j] === key[i] && j < i)) rk++; rank.push(rk); } }
    if (s.title) txt(String(s.title), GX, T + 56, fit(String(s.title), 600, { size: 62, weight: 800, font: F.display, color: acc(1), alpha: k0 }));
    if (s.sub) { var sx = GX + (s.title ? tw(String(s.title), fit(String(s.title), 600, { size: 62, weight: 800, font: F.display })) + 28 : 0); txt(String(s.sub), sx, T + 54, fit(String(s.sub), 1800 - sx, { size: 42, weight: 800, color: C.ink, alpha: k0 })); }
    for (i = 0; i < N; i++) { var on = rank[i] < cur; dot(ctx, GX + PT * .5 + (i % cols) * PT, GT + PT * .5 + Math.floor(i / cols) * PT, PT * (on ? .4 : .32), on ? col : C.muted, k0 * clamp((lt - 200 - i * 900 / N) / 200) * (on ? 1 : kn > 0 ? .4 : .8)); }
    ev(ts[0] + 700, "count"); ev(ts[0] + 700 + dur, "pop");
    var RXc = (GX + GW + 1840) / 2, RW = 1840 - (GX + GW) - 80, gy = GT + GH / 2, vt = cur + (s.unit || ""), full = n + (s.unit || "");
    if (s.label) txt(s.label, RXc, gy - 110, fit(s.label, RW, { size: 52, weight: 800, align: "center", color: C.ink, alpha: kh }));
    if (kn > 0) { var no = fit(full, RW, { size: 170, weight: 800, font: F.display, align: "center", color: col }); txt(vt, RXc, gy + (s.label ? 110 : 60), Object.assign({}, no, { size: no.size * (kn >= 1 ? pop((lt - ts[0] - 700 - dur) / 400) : 1) })); }
    note(s, lt, ts[0] + 700 + dur + 600);
  };

  /* ---- 1 行ずつの表: 行の名前は先にうすく出し、1 行ずつ中身が出て、いまの行だけ明るい ----
     {type:"revealtable", heading, columns:["事例","どこで","実害"], rows:[["A の件","本番","あり"], …]（ます目は "\n" で 2 行に）, hot:["あり"]（この字のます目に色）, note, at:[秒, 秒…]} */
  R.revealtable = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var cols = (s.columns || []).slice(0, 5), rows = (s.rows || []).slice(0, 6).map(function (r) { return Array.isArray(r) ? r : (r && r.cells) || []; }), n = Math.max(1, rows.length), nc = Math.max(1, cols.length, Math.max.apply(null, rows.map(function (r) { return r.length; }).concat([0])));
    var T = top(s), X0 = 120, X1 = 1800, cw = (X1 - X0) / nc, HY = T + 46, R0 = T + 84, RH = Math.min(160, (935 - R0 - (s.note ? 50 : 0)) / n), size = RH < 110 ? 32 : 40, k0 = P(lt, 0, 500), hot = s.hot ? [].concat(s.hot).map(String) : [];
    var ts = when(s, X.slots(n, d, 900, 1400)), cur = -1, i; for (i = 0; i < rows.length; i++) if (lt >= ts[i]) cur = i;
    cols.forEach(function (t, j) { txt(String(t), X0 + cw * (j + .5), HY, fit(String(t), cw - 30, { size: 40, weight: 800, align: "center", color: acc(0), alpha: k0 })); });
    line(ctx, X0, T + 68, X1, T + 68, acc(0), 5, k0);
    rows.forEach(function (r, i) { var y = R0 + RH * i, a = P(lt, ts[i] + 150, ts[i] + 600, eo), dim = i < rows.length - 1 ? mix(1, .72, P(lt, ts[i + 1], ts[i + 1] + 400)) : 1; if (lt >= ts[i]) ev(ts[i], "tick", { i: i });
      if (i === cur) { ctx.save(); ctx.globalAlpha *= .14 * a; rr(X0, y + 4, X1 - X0, RH - 8, 14); ctx.fillStyle = acc(0); ctx.fill(); ctx.restore(); }
      if (i) line(ctx, X0, y, X1, y, C.muted, 2, k0 * .45);
      for (var j = 0; j < nc; j++) { var cell = r[j]; if (cell === undefined || cell === null || cell === "") continue; var flat = Array.isArray(cell) ? cell.join("") : String(cell).replace(/\n/g, "");
        var al = j === 0 ? k0 * mix(.45, 1, a) * dim : clamp((lt - ts[i] - 150 - (j - 1) * 260) / 350) * dim, c = j > 0 && hot.indexOf(flat) >= 0 ? C.warn : C.ink;
        if (al > 0) drawLines(fitLines(cell, cw - 36, { size: size, weight: 800 }), X0 + cw * (j + .5), y + RH / 2, al, c); } });
    if (s.note) txt(s.note, 960, 960, fit(s.note, 1600, { size: 38, weight: 700, align: "center", color: C.muted, alpha: P(lt, ts[n - 1] + 1200, ts[n - 1] + 1700) }));
  };
}); }
