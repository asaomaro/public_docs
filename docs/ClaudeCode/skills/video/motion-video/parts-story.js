/* motion-video parts-story — 話の筋を見せる図解（つまみと線・ふたをして当てる・面積で比べる・でこぼこの線・順番と同時・多角形の角の印・
 * らせんの回り道・太い棒と大きな数字・左右から引く・噴き出して降りもどる・軸の傾き）。
 * 2026-10-08 に、解説動画「AI の進歩」「城」「天体」（yukkuri-work の kaisetsu-ai-shinpo・10sen/shiro・10sen/tentai）の組み立て役が
 * その動画のために描き下ろした図解を、ほかの題材でも使える部品に直して足した。字・数字は、どれも場面の JSON で渡す（絵に書き込まない）。
 * 題材に固有の絵（星・城・ロボット）は、丸・箱・札に置きかえてある。
 * どれも (s, lt, d) だけで決まる描画。色は配色（C）から取る。
 * 進む時: 既定は、場面の長さ d の中の割合（項目が並ぶ物は X.slots = 字幕の文の数が項目の数と同じなら、文が始まる時）。
 *         s.at に、場面の頭からの秒を並べると、その時に進む（at: [3.2, 7.5]。書かなかった所は既定）。 */
if (!window.__mvPartsStory) { window.__mvPartsStory = 1; (window.MotionVideoParts = window.MotionVideoParts || []).push(function (R, X) {
  "use strict";
  var C = X.C, F = X.F, P = X.P, eo = X.eo, clamp = X.clamp, mix = X.mix;
  var txt = X.txt, tw = X.tw, rr = X.rr, acc = X.accentAt, ev = X.sfxEv, g = X.g, PI2 = Math.PI * 2;
  function top(s) { return s.heading ? 300 : 230; }
  function num(v) { var n = parseFloat(String(v).replace(/,/g, "")); return isFinite(n) ? n : 0; }
  function int(v, def, lo, hi) { var n = Math.round(num(v === undefined || v === null ? def : v)); return Math.max(lo, Math.min(hi, n)); }
  function lab(it) { return typeof it === "string" || typeof it === "number" ? String(it) : (it && (it.label || it.text || it.title)) || ""; }
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
  function ring(ctx, x, y, r, col, w, a, dash) { if (a <= 0 || r <= 0) return; ctx.save(); ctx.globalAlpha *= clamp(a); ctx.strokeStyle = col; ctx.lineWidth = w; if (dash) ctx.setLineDash(dash); ctx.beginPath(); ctx.arc(x, y, r, 0, PI2); ctx.stroke(); ctx.restore(); }
  /* 枠と、うすい塗りの箱 */
  function box(ctx, x, y, w, h, col, a, fillA, r, lw) { if (a <= 0) return; ctx.save(); ctx.globalAlpha *= clamp(a); rr(x, y, w, h, r || 18); ctx.save(); ctx.globalAlpha *= clamp(fillA); ctx.fillStyle = col; ctx.fill(); ctx.restore();
    ctx.strokeStyle = col; ctx.lineWidth = lw || 8; ctx.lineJoin = "round"; ctx.stroke(); ctx.restore(); }
  /* 矢じり（先が (x, y)。ang は進む向き） */
  function head(ctx, x, y, ang, col, a, z) { if (a <= 0) return; ctx.save(); ctx.globalAlpha *= clamp(a); ctx.fillStyle = col; ctx.beginPath(); ctx.moveTo(x + Math.cos(ang) * z, y + Math.sin(ang) * z);
    ctx.lineTo(x + Math.cos(ang + 2.5) * z, y + Math.sin(ang + 2.5) * z); ctx.lineTo(x + Math.cos(ang - 2.5) * z, y + Math.sin(ang - 2.5) * z); ctx.closePath(); ctx.fill(); ctx.restore(); }
  /* 横向きの太い矢印（x0 から x1 へ、a の分だけのびる） */
  function arw(ctx, x0, x1, y, w, col, a) { if (a <= 0) return; var dr = x1 > x0 ? 1 : -1, xe = x0 + (x1 - x0) * a, hd = w * 1.9; ctx.save(); ctx.globalAlpha *= Math.min(1, a * 2); ctx.strokeStyle = col; ctx.fillStyle = col; ctx.lineWidth = w; ctx.lineCap = "round";
    if (Math.abs(xe - x0) > hd) { ctx.beginPath(); ctx.moveTo(x0, y); ctx.lineTo(xe - dr * hd, y); ctx.stroke(); }
    ctx.beginPath(); ctx.moveTo(xe, y); ctx.lineTo(xe - dr * hd * 1.2, y - hd); ctx.lineTo(xe - dr * hd * 1.2, y + hd); ctx.closePath(); ctx.fill(); ctx.restore(); }
  /* 幅に収まる 1〜maxN 行にする（"\n" か配列なら、そこで折る。収まらなければ字を小さく） */
  function fitLines(t, maxW, o, maxN) { var raw = Array.isArray(t) ? t.map(String) : String(t === undefined || t === null ? "" : t).split("\n"), size = o.size, L, oo; maxN = maxN || 2;
    for (;;) { oo = Object.assign({}, o, { size: size }); L = raw.length > 1 ? raw : X.wrap(raw[0], maxW, oo);
      if ((L.length <= maxN && !L.some(function (x) { return tw(x, oo) > maxW; })) || size <= 24) return { lines: L.slice(0, maxN), o: oo }; size -= 2; } }
  function drawLines(fl, x, cy, alpha, color) { var z = fl.o.size, n = fl.lines.length; fl.lines.forEach(function (t, i) {
    txt(t, x, cy + (i - (n - 1) / 2) * z * 1.28 + z * .36, Object.assign({}, fl.o, { align: "center", alpha: alpha, color: color || fl.o.color })); }); }
  function note(s, lt, at, t, y) { t = t === undefined ? s.note : t; if (t) txt(t, 960, y || 945, fit(t, 1600, { size: 40, weight: 700, align: "center", color: C.muted, alpha: P(lt, at, at + 500) })); }
  /* 人の印（頭と肩）。アイコンの名前が無い・台本に入っていない時に使う */
  function person(ctx, x, y, z, col, a) { if (a <= 0) return; dot(ctx, x, y - z * .2, z * .2, col, a); ctx.save(); ctx.globalAlpha *= clamp(a); ctx.fillStyle = col; ctx.beginPath(); ctx.arc(x, y + z * .46, z * .38, Math.PI, 0); ctx.fill(); ctx.restore(); }
  function who(ctx, name, x, y, z, col, lt) { if (!(name && X.icon(name, x, y, z, { color: col, k: 1, lt: lt, anim: "none" }))) person(ctx, x, y, z, col, 1); }
  function side(v) { return typeof v === "string" || typeof v === "number" ? { label: String(v) } : v || {}; }
  function poly(ctx, cx, cy, r, n, rot) { ctx.beginPath(); for (var i = 0; i < n; i++) { var a = rot + i * PI2 / n, x = cx + r * Math.cos(a), y = cy + r * Math.sin(a); if (i) ctx.lineTo(x, y); else ctx.moveTo(x, y); } ctx.closePath(); }

  /* ---- つまみと線: 左のつまみ（2〜4 個）が右へ動くと、右の図の線がのびる。後から、線の下に同じ形の段 ----
     {type:"knobcurve", heading, knobs:["大きさ","データ","計算"], yLabel:"はずれ", xLabel:"規模 →", dir:"down"（"up" で右上がり。既定は "up"）, label:"決まった調子で減る",
      steps:3（線の下の段の数。0 で出さない）, note, at:[つまみが動く時, 段が出る時]} */
  R.knobcurve = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var NM = (s.knobs && s.knobs.length ? s.knobs : ["", "", ""]).slice(0, 4).map(lab), n = NM.length, T = top(s), nS = int(s.steps, 3, 0, 6), ts = when(s, [Math.max(n * 700 + 600, d * .3), d * .68]);
    var up = s.dir !== "down", c1 = acc(0), c2 = acc(1), SX0 = 140, SX1 = 700, pit = Math.min(180, 540 / n), y0 = T + 30 + (540 - pit * n) / 2, stag = Math.min(1100, Math.max(200, (ts[0] - 500) / n)), slide = Math.min(2800, Math.max(900, (nS ? ts[1] - ts[0] : d - ts[0]) * .7)), i;
    ev(ts[0], "whoosh");
    for (i = 0; i < n; i++) { var a = P(lt, 200 + i * stag, 600 + i * stag); if (a <= 0) continue; var y = y0 + pit * i + pit / 2, ky = y + 34, p = .1 + .86 * P(lt, ts[0] + 200 + i * 250, ts[0] + 200 + i * 250 + slide, eo), kx = mix(SX0 + 6, SX1, p);
      if (NM[i]) txt(NM[i], SX0, y - 22, fit(NM[i], SX1 - SX0, { size: 48, weight: 800, color: C.ink, alpha: a }));
      line(ctx, SX0 + 6, ky, SX1, ky, C.muted, 10, a * .5); line(ctx, SX0 + 6, ky, kx, ky, c1, 12, a); dot(ctx, kx, ky, 24, c1, a); ring(ctx, kx, ky, 24, C.ink, 5, a); }
    var ka = P(lt, ts[0], ts[0] + 450), OX = 900, OY = T + 500, TX = 1760, TY = T + 70;
    if (ka > 0) { line(ctx, OX, TY, OX, OY, C.ink, 8, ka * .8); line(ctx, OX, OY, TX, OY, C.ink, 8, ka * .8);
      if (s.yLabel) txt(s.yLabel, OX - 10, T + 36, fit(s.yLabel, 860, { size: 40, weight: 800, color: C.ink, alpha: ka }));
      if (s.xLabel) txt(s.xLabel, TX, OY + 60, fit(s.xLabel, 860, { size: 40, weight: 800, align: "right", color: C.ink, alpha: ka }));
      var x0 = OX + 80, x1 = TX - 50, yA = up ? OY - 60 : TY + 100, yB = up ? TY + 100 : OY - 60, kl = clamp((lt - ts[0] - 300) / (slide + 200));
      for (i = 0; i < nS; i++) { var ks = P(lt, ts[1] + 300 + i * 500, ts[1] + 750 + i * 500, eo); if (ks <= 0) continue; ev(ts[1] + 300 + i * 500, "tick", { i: i });
        var sx = mix(x0, x1, i / nS), sy = mix(yA, yB, i / nS), ex = mix(x0, x1, (i + 1) / nS), ey = mix(yA, yB, (i + 1) / nS);
        if (up) { line(ctx, sx, sy, mix(sx, ex, ks), sy, C.ink, 7, .95, [4, 14]); line(ctx, ex, sy, ex, mix(sy, ey, ks), C.ink, 7, .95 * (ks > 0 ? 1 : 0), [4, 14]); }
        else { line(ctx, sx, sy, sx, mix(sy, ey, ks), C.ink, 7, .95, [4, 14]); line(ctx, sx, ey, mix(sx, ex, ks), ey, C.ink, 7, .95, [4, 14]); } }
      if (kl > 0) { line(ctx, x0, yA, mix(x0, x1, kl), mix(yA, yB, kl), c2, 14, 1); dot(ctx, mix(x0, x1, kl), mix(yA, yB, kl), 15, c2, 1); }
      if (s.label) { var tl = ts[0] + 300 + slide * .8; txt(s.label, up ? OX + 50 : TX, TY + 52, fit(s.label, 640, { size: 42, weight: 800, align: up ? "left" : "right", color: c2, alpha: P(lt, tl, tl + 500) })); } }
    note(s, lt, nS ? ts[1] + nS * 500 + 700 : ts[0] + slide + 900);
  };

  /* ---- ふたをして当てる: 言葉の札の 1 枚にふたがかぶさり、下の人が当てにいく。ふたが開いて、その札に色が付く ----
     {type:"maskreveal", heading, lead:"データの中の文", tokens:["きょうは","いい","天気","です"], mask:2（かくす札。0 から数える。既定は後ろから 2 枚目）,
      who:"モデル"（当てる人の名前）, icon:"robot"（線のアイコンの名前。書かなければ、頭と肩の人の印。false で出さない）, guess:"当ててみる", answer:"かくした言葉 ＝ 正解", note, at:[ふたをする時, 開く時]} */
  R.maskreveal = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var WD = (s.tokens || []).slice(0, 8).map(String), n = WD.length, T = top(s), mi = int(s.mask, Math.max(0, n - 2), 0, Math.max(0, n - 1)), ts = when(s, [d * .25, d * .62]), c1 = acc(0), c2 = acc(1), i;
    var k0 = P(lt, 0, 500), kc = P(lt, ts[0] + 250, ts[0] + 750, eo), km = P(lt, ts[0] + 1000, ts[0] + 1450), ko = P(lt, ts[1] + 250, ts[1] + 800, eo), ke = P(lt, ts[1] + 900, ts[1] + 1350);
    var Z = 64, GAP = 18, PAD = 56, ws, tot; for (;;) { ws = WD.map(function (t) { return tw(t, { size: Z, weight: 800 }) + PAD; }); tot = ws.reduce(function (p, v) { return p + v + GAP; }, -GAP); if (tot <= 1640 || Z <= 30) break; Z -= 2; }
    var CH = Z + 50, RY = T + (s.lead ? 150 : 110), xs = [], x = 960 - tot / 2; for (i = 0; i < n; i++) { xs[i] = x + ws[i] / 2; x += ws[i] + GAP; }
    if (s.lead) txt(s.lead, 960, T + 30, fit(s.lead, 1500, { size: 44, weight: 800, align: "center", color: C.ink, alpha: k0 }));
    if (!n) return;
    ev(ts[0] + 250, "whoosh"); ev(ts[1] + 250, "pop");
    for (i = 0; i < n; i++) { var a = k0 * P(lt, i * 160, i * 160 + 350), hit = i === mi && ko > 0;
      box(ctx, xs[i] - ws[i] / 2, RY - CH / 2, ws[i], CH, hit ? c2 : C.ink, a, hit ? ko : .08, 18, 7);
      txt(WD[i], xs[i], RY + Z * .36, { size: Z, weight: 800, align: "center", color: hit && ko > .5 ? C.onAccent : C.ink, alpha: i === mi ? a * Math.max(1 - kc, ko) : a }); }
    if (kc > 0 && ko < 1) { var cw = ws[mi] + 14, ch = CH + 14, cy = RY - (1 - kc) * 30 - ko * 50, ca = kc * (1 - ko); ctx.save(); ctx.globalAlpha *= ca; rr(xs[mi] - cw / 2, cy - ch / 2, cw, ch, 20); ctx.fillStyle = C.panel; ctx.fill(); ctx.strokeStyle = c2; ctx.lineWidth = 9; ctx.stroke(); ctx.restore();
      txt("？", xs[mi], cy + Z * .4, { size: Z * 1.1, weight: 800, align: "center", color: c2, alpha: ca }); }
    if (km > 0 && s.icon !== false) { var MX = 420, MY = T + 465, gk = P(lt, ts[0] + 1400, ts[0] + 2100, eo), ax = MX + 80, ay = MY - 55, bx = xs[mi] + (xs[mi] > ax ? -20 : 20), by = RY + CH / 2 + 34;
      ctx.save(); ctx.globalAlpha *= km; who(ctx, s.icon, MX, MY, 130, c1, lt); ctx.restore();
      if (s.who) txt(s.who, MX, MY + 110, fit(s.who, 520, { size: 44, weight: 800, align: "center", color: c1, alpha: km }));
      if (ko < 1) { line(ctx, ax, ay, mix(ax, bx, gk), mix(ay, by, gk), c1, 9, km * (1 - ko), [4, 20]); if (gk >= 1) head(ctx, bx, by, Math.atan2(by - ay, bx - ax), c1, 1 - ko, 22);
        if (s.guess) txt(s.guess, MX + 110, MY + 16, fit(s.guess, 900, { size: 44, weight: 800, color: c1, alpha: gk * (1 - ko) })); } }
    if (ke > 0) { line(ctx, xs[mi], RY + CH / 2 + 16, xs[mi], T + (s.lead ? 300 : 260), c2, 10, ke); head(ctx, xs[mi], T + (s.lead ? 312 : 272), Math.PI / 2, c2, ke, 24);
      if (s.answer) { var ao = fit(s.answer, 1300, { size: 56, weight: 800, align: "center", color: c2, alpha: ke }), aw = tw(s.answer, ao);
        txt(s.answer, Math.max(140 + aw / 2, Math.min(1780 - aw / 2, xs[mi])), T + (s.lead ? 384 : 344), ao); } }
    note(s, lt, ts[1] + 1700);
  };

  /* ---- 面積で比べる: 面積が数の比になった 2 つの丸。後から、片方に「こっち」の札 ----
     {type:"areacompare", heading, items:[{label:"小さい方", value:13, text:"13億個"}, {label:"大きい方", value:1750, text:"1750億個"}]（value は面積の比に使う数。text は見せる字。無ければ value と unit）, unit:"",
      pick:0（札を付ける丸。書かなければ付けない）, pickLabel:"こっち", by:"人による評価"（まん中の下に、人の印と一言。{label, icon} でも）, note, at:[2 つ目が出る時, 札が出る時]} */
  R.areacompare = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var items = (s.items || []).slice(0, 2), T = top(s), RM = 215, CYc = T + 375, XS = [470, 1370], ts = when(s, [d * .3, d * .62]), unit = s.unit || "";
    var vm = Math.max.apply(null, items.map(function (it) { return num(it.value); }).concat([1e-9])), rs = items.map(function (it) { return Math.max(7, RM * Math.sqrt(Math.max(0, num(it.value)) / vm)); });
    ev(ts[0] + 400, "whoosh");
    items.forEach(function (it, i) { var k = i === 0 ? P(lt, 0, 500, eo) : P(lt, ts[0] + 400, ts[0] + 1100, eo), col = tone(it.color, acc(i)), r = rs[i] * (i === 0 ? pop(k) : k), x = XS[i]; if (k <= 0) return;
      if (rs[i] < 26) dot(ctx, x, CYc, r, col, k); else { dot(ctx, x, CYc, r, col, k * .24); ring(ctx, x, CYc, r, col, 10, k); }
      var vt = it.text === undefined ? (it.value === undefined ? "" : String(it.value) + (it.unit === undefined ? unit : it.unit)) : String(it.text);
      if (vt) txt(vt, x, T + 50, fit(vt, 800, { size: 64, weight: 800, font: F.display, align: "center", color: col, alpha: k }));
      if (lab(it) && it.label) txt(it.label, x, T + 112, fit(it.label, 800, { size: 44, weight: 800, align: "center", color: C.ink, alpha: k })); });
    var by = s.by ? side(s.by) : null, hasP = s.pick !== undefined && s.pick !== null && items.length > 1, pi = hasP ? int(s.pick, 0, 0, 1) : -1, MXc = 920, kp = P(lt, ts[1], ts[1] + 450), kf = P(lt, ts[1] + (by ? 900 : 0), ts[1] + (by ? 1350 : 450));
    if (by && kp > 0) { ctx.save(); ctx.globalAlpha *= kp; if (by.icon !== false) who(ctx, by.icon, MXc, CYc + 85, 110, C.ink, lt); ctx.restore();
      if (by.label) txt(by.label, MXc, CYc + 190, fit(by.label, 430, { size: 42, weight: 800, align: "center", color: C.ink, alpha: kp })); }
    if (pi >= 0 && kf > 0) { var pc = tone((items[pi] || {}).color, acc(pi)), px = XS[pi], pl = s.pickLabel; ev(ts[1] + (by ? 900 : 0), "pop");
      ring(ctx, px, CYc, rs[pi] + 24 + 6 * Math.sin(lt / 260), pc, 7, kf);
      if (pl) { var z = pop(kf), fo = fit(pl, 330, { size: 50, weight: 800, align: "center", color: C.onAccent }), fw = (tw(pl, fo) + 60) * z, fh = (fo.size + 30) * z, FY = CYc - 70, dr = pi === 0 ? -1 : 1, tx = px - dr * (rs[pi] + 46);
        ctx.save(); ctx.globalAlpha *= kf; rr(MXc - fw / 2, FY - fh / 2, fw, fh, 16); ctx.fillStyle = pc; ctx.fill(); ctx.restore(); txt(pl, MXc, FY + fo.size * .36, Object.assign({}, fo, { alpha: kf }));
        if (Math.abs(tx - MXc) > fw / 2 + 50) { line(ctx, MXc + dr * (fw / 2 + 14), FY, tx - dr * 20, mix(FY, CYc, .6), pc, 10, kf); head(ctx, tx, mix(FY, CYc, .6) + 3, Math.atan2((CYc - FY) * .6, tx - MXc - dr * (fw / 2 + 14)), pc, kf, 24); } } }
    note(s, lt, ts[1] + (by ? 1900 : 1000));
  };

  /* ---- でこぼこの線: 折れ線がのびて、山と谷に、順に名前が付く ----
     {type:"jaggedline", heading, points:[0.4, 0.5, 0.9, …]（高さ 0..1。目盛りは無い。既定は見本の形）, high:"↑ 得意", low:"↓ 苦手",
      marks:[{at:2（何番目の点か。0 から）, label:"数学の試験", value:"金メダルの点", badge:"金"（点の中の 1 字）, color:"ok"}, {at:5, label:"針の時計", value:"およそ半分", color:"warn"}], note, at:[秒, 秒…]（印が出る時）} */
  var JAG = [.42, .55, .9, .55, .66, .12, .55, .72, .58];
  R.jaggedline = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var PV = (s.points && s.points.length > 1 ? s.points : JAG).slice(0, 16).map(function (v) { return clamp(num(v)); }), n = PV.length - 1, marks = (s.marks || []).slice(0, 4), T = top(s), hint = s.high || s.low;
    var L = hint ? 440 : 220, Rx = 1720, YT = T + 160, YB = T + 430, grow = Math.min(1700, d * .3), kl = clamp((lt - 200) / grow), pos = kl * n, i;
    function px(i) { return mix(L, Rx, i / n); } function py(i) { return mix(YB, YT, PV[i]); }
    function yAt(x) { var f = clamp((x - L) / (Rx - L)) * n, a = Math.min(n - 1, Math.floor(f)); return mix(py(a), py(a + 1), f - a); }
    function ext(xa, xb, hi) { var v = hi ? Math.min(yAt(xa), yAt(xb)) : Math.max(yAt(xa), yAt(xb)); for (var q = 0; q <= n; q++) if (px(q) >= xa && px(q) <= xb) v = hi ? Math.min(v, py(q)) : Math.max(v, py(q)); return v; }
    if (kl > 0) { ctx.save(); ctx.strokeStyle = C.ink; ctx.lineWidth = 12; ctx.lineCap = "round"; ctx.lineJoin = "round"; ctx.beginPath(); ctx.moveTo(px(0), py(0));
      for (i = 1; i <= n; i++) { if (pos <= i - 1) break; var f = Math.min(1, pos - (i - 1)); ctx.lineTo(mix(px(i - 1), px(i), f), mix(py(i - 1), py(i), f)); } ctx.stroke(); ctx.restore(); }
    if (s.high) txt(s.high, 140, YT + 30, fit(s.high, 270, { size: 40, weight: 800, color: C.muted, alpha: kl }));
    if (s.low) txt(s.low, 140, YB + 10, fit(s.low, 270, { size: 40, weight: 800, color: C.muted, alpha: kl }));
    var hiI = 0, loI = 0; PV.forEach(function (v, q) { if (v > PV[hiI]) hiI = q; if (v < PV[loI]) loI = q; });
    var ts = when(s, X.slots(marks.length, d, Math.min(2300, d * .32), 1500));
    marks.forEach(function (m, j) { var q = int(m.at, j === 0 ? hiI : j === 1 ? loI : j, 0, n), k = P(lt, ts[j] + 200, ts[j] + 650), upS = m.side ? m.side !== "low" : PV[q] >= .5, col = tone(m.color, upS ? acc(0) : C.warn), x = px(q), y = py(q); if (k <= 0) return; ev(ts[j] + 200, "pop", { i: j });
      dot(ctx, x, y, (m.badge ? 30 : 22) * pop(k), col, k); if (m.badge) txt(String(m.badge), x, y + 11, { size: 30, weight: 800, align: "center", color: C.onAccent, alpha: k });
      var lo = m.label ? fit(m.label, 760, { size: 46, weight: 800, align: "center", color: C.ink, alpha: k }) : null, vo = m.value !== undefined && m.value !== "" ? fit(String(m.value), 760, { size: 54, weight: 800, align: "center", color: col, alpha: k }) : null;
      var w = Math.max(lo ? tw(m.label, lo) : 0, vo ? tw(String(m.value), vo) : 0), cx = Math.max(140 + w / 2, Math.min(1780 - w / 2, x)), e = ext(cx - w / 2 - 24, cx + w / 2 + 24, upS);
      if (upS) { var yb = Math.min(e, y - 30) - 44; if (vo) { txt(String(m.value), cx, yb, Object.assign({}, vo, { size: vo.size * pop(k) })); yb -= vo.size + 12; } if (lo) txt(m.label, cx, yb, lo); }
      else { var yt = Math.max(e, y + 30) + 44; if (lo) { txt(m.label, cx, yt + lo.size * .72, lo); yt += lo.size + 14; } if (vo) txt(String(m.value), cx, yt + vo.size * .72, Object.assign({}, vo, { size: vo.size * pop(k) })); } });
    note(s, lt, (marks.length ? ts[marks.length - 1] : 200 + grow) + 1300);
  };

  /* ---- 順番と同時: 上の列は箱が 1 つずつ光り、下の列は同時に光る。後から、列の下に時間の帯（上は長い・下は短い） ----
     {type:"seqparallel", heading, labels:["順番に\n1つずつ","並べて\nいっぺんに"], count:6（箱の数 2〜10）,
      time:{label:"かかる時間", ratio:0.2（下の帯の長さ。上を 1 として。既定は 1 ÷ 箱の数）, mark:"ずっと短い"}（書かなければ帯は出さない）, note, at:[下の列が出る時, 時間の帯が出る時]} */
  R.seqparallel = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var Lb = s.labels || [], N = int(s.count, 6, 2, 10), T = top(s), tm = s.time ? side(s.time === true ? {} : s.time) : null, ts = when(s, [d * .3, d * .62]), c1 = acc(0), c2 = acc(1), i, x;
    var BX0 = 640, BX1 = 1780, bw = (BX1 - BX0) / N, S = Math.min(104, bw * .64), R1 = T + (tm ? 80 : 130), R2 = T + (tm ? 370 : 400), TICK = 430, CYC = N * TICK + 900, k0 = P(lt, 0, 500), kb = P(lt, ts[0] + 200, ts[0] + 700), kt = tm ? P(lt, ts[1] + 300, ts[1] + 1100, eo) : 0;
    var done = Math.floor((lt % CYC) / TICK);
    if (Lb[0]) drawLines(fitLines(Lb[0], 460, { size: 46, weight: 800 }), 350, R1, k0, C.ink);
    for (i = 0; i < N; i++) { x = BX0 + bw * (i + .5); box(ctx, x - S / 2, R1 - S / 2, S, S, c1, k0, i === done ? .95 : i < done ? .5 : .08, 16); }
    if (kb > 0) { ev(ts[0] + 200, "pop"); if (Lb[1]) drawLines(fitLines(Lb[1], 460, { size: 46, weight: 800 }), 350, R2, kb, c2);
      var ph2 = Math.max(0, lt - ts[0]) % CYC, on2 = ph2 > TICK, fl = on2 && ph2 < TICK * 2;
      for (i = 0; i < N; i++) { x = BX0 + bw * (i + .5); box(ctx, x - S / 2, R2 - S / 2, S, S, c2, kb, fl ? .95 : on2 ? .5 : .08, 16); } }
    if (kt > 0) { ev(ts[1] + 300, "whoosh"); var Ln = BX1 - BX0 - 30, by1 = R1 + 125, by2 = R2 + 125, ratio = clamp(tm.ratio === undefined ? 1 / N : num(tm.ratio)), la = clamp(kt * 3);
      if (tm.label) { var to = fit(tm.label, 460, { size: 40, weight: 800, align: "center", color: C.muted, alpha: la }); txt(tm.label, 350, by1 + to.size * .36, to); txt(tm.label, 350, by2 + to.size * .36, to); }
      line(ctx, BX0 + 14, by1, BX0 + 14 + Ln * kt, by1, c1, 28, 1); line(ctx, BX0 + 14, by2, BX0 + 14 + Math.max(2, Ln * ratio * kt), by2, c2, 28, 1);
      if (tm.mark) { var mx = BX0 + 14 + Ln * ratio + 50, mo = fit(tm.mark, BX1 - mx, { size: 52, weight: 800, color: c2, alpha: kt }); txt(tm.mark, mx, by2 + mo.size * .36, Object.assign({}, mo, { size: mo.size * pop(kt) })); } }
    note(s, lt, (tm ? ts[1] : ts[0]) + 1600);
  };

  /* ---- 多角形の角の印: 多角形の角に、順に印が出て、右で数える。後から、まん中の形と仕切り ----
     {type:"polymarks", heading, sides:8（辺の数 3〜12）, rows:[{label:"角の塔", value:"8"}, {label:"1階の部屋", value:"8"}]（右の行 1〜3。value を書かなければ辺の数。1 行目は印の後、2 行目からは、まん中の形の後）,
      center:"中庭"（まん中の形の中の字。書かなければ、まん中の形は出さない）, spokes:true（まん中の形から角への仕切り。center があれば既定で出す）, note, at:[まん中の形が出る時, 印と数字がはずむ時]} */
  R.polymarks = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var N = int(s.sides, 8, 3, 12), rows = (s.rows || []).slice(0, 3).map(side), nr = rows.length, T = top(s), CX = 600, CY = T + 300, RR = 215, mr = N > 8 ? 34 : 42, ROT = -Math.PI / 2 + (N % 2 ? 0 : Math.PI / N);
    var hasC = s.center !== undefined && s.center !== null && s.center !== false, sp = s.spokes === undefined ? hasC : !!s.spokes, two = hasC || sp, tm = 500 + N * 160 + 400, ts = when(s, [Math.max(tm + 600, d * .4), d * .72]), t2 = lt - ts[1], c1 = acc(0), c2 = acc(1), i, a;
    var p0 = P(lt, 0, 700, eo); ctx.save(); ctx.globalAlpha *= p0; ctx.strokeStyle = C.ink; ctx.lineWidth = 12; ctx.lineJoin = "round"; ctx.lineCap = "round"; poly(ctx, CX, CY, RR, N, ROT); ctx.stroke(); ctx.restore();
    if (sp) { var p1 = P(lt, ts[0] + 500, ts[0] + 1400, eo); for (i = 0; i < N && p1 > 0; i++) { a = ROT + i * PI2 / N; line(ctx, CX + RR * .46 * Math.cos(a), CY + RR * .46 * Math.sin(a), CX + RR * mix(.46, 1, p1) * Math.cos(a), CY + RR * mix(.46, 1, p1) * Math.sin(a), C.ink, 10, p1); } }
    if (hasC || sp) { var pc = P(lt, ts[0], ts[0] + 600, eo); if (pc > 0) { ev(ts[0], "whoosh"); ctx.save(); ctx.globalAlpha *= pc; ctx.fillStyle = c2; poly(ctx, CX, CY, RR * .46 * pc, N, ROT); ctx.fill(); ctx.restore();
      if (hasC && s.center !== true && String(s.center)) { var co = fit(String(s.center), RR * .74, { size: 46, weight: 800, align: "center", color: C.onAccent, alpha: pc }); txt(String(s.center), CX, CY + co.size * .36, co); } } }
    for (i = 0; i < N; i++) { var k = P(lt, 500 + i * 160, 880 + i * 160, eo); if (k <= 0) continue; ev(500 + i * 160, "tick", { i: i }); a = ROT + i * PI2 / N;
      var pulse = t2 > 0 ? 1 + .12 * Math.max(0, Math.sin(t2 / 260 - i * .8)) : 1; ctx.save(); ctx.fillStyle = c1; poly(ctx, CX + RR * 1.06 * Math.cos(a), CY + RR * 1.06 * Math.sin(a), mr * k * pulse, N, ROT); ctx.fill(); ctx.restore(); }
    var RX = 1090, VX = 1560, pit = nr > 2 ? 160 : 190, big = t2 > 0 ? 1 + .08 * Math.sin(t2 / 300) * clamp(t2 / 400) : 1, last = tm;
    rows.forEach(function (r, j) { var t = j === 0 ? tm : two ? ts[0] + 1400 + (j - 1) * 600 : tm + j * 700, ra = P(lt, t, t + 400), y = CY + (j - (nr - 1) / 2) * pit, col = j === 0 ? c1 : C.ink, v = r.value === undefined || r.value === null ? String(N) : String(r.value); last = Math.max(last, t); if (ra <= 0) return; ev(t, "pop", { i: j });
      if (r.label) txt(r.label, RX, y + 18, fit(r.label, VX - RX - 30, { size: 50, weight: 800, color: col, alpha: ra }));
      var vo = fit(v, 1790 - VX, { size: 104, weight: 800, font: F.display, color: col, alpha: ra }); txt(v, VX, y + vo.size * .36, Object.assign({}, vo, { size: vo.size * big })); });
    note(s, lt, Math.max(last, two ? ts[0] : 0) + 1300);
  };

  /* ---- らせんの回り道: 入口と目的地を点線の直線で結ぶ → らせんの塀が伸びる → 印が、らせんの道をゆっくり進む ----
     {type:"spiralpath", heading, from:"入口", to:"目的地", turns:2.5（巻きの数 1〜4）, straight:{label:"直線", value:"約450m"}（value は書かなければ出さない）, path:"歩く道",
      reach:0.75（場面の終わりまでに、道のどこまで進むか 0..1）, captions:["入口から目的地まで","塀で、らせん状に囲む","見えているのに、着かない"]（段ごとに替わる下の一言。書かなければ note）, note, at:[らせんが伸びる時, 3 段目の時]} */
  R.spiralpath = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var T = top(s), TURNS = Math.max(1, Math.min(4, s.turns === undefined ? 2.5 : num(s.turns))), TH = TURNS * PI2, R0 = 62, R1 = 240, A0 = -Math.PI / 2, CX = 700, CY = T + 300, ts = when(s, [d * .25, d * .7]), t1 = lt - ts[0], c1 = acc(0), c2 = acc(1), i, p;
    function sp(f, off) { var th = TH * f, r = R0 + (R1 - R0) * f + (off || 0); return { x: CX + r * Math.cos(A0 + th) * 1.25, y: CY + r * Math.sin(A0 + th) * .92 }; }
    var EN = sp(1, 0), half = (R1 - R0) / TURNS / 2, pw = P(lt, ts[0] + 200, ts[0] + 2400, eo), st = s.straight === undefined ? {} : side(s.straight), reach = clamp(s.reach === undefined ? .75 : num(s.reach));
    ev(ts[0] + 200, "whoosh");
    if (pw > 0) { ctx.save(); ctx.strokeStyle = C.ink; ctx.lineWidth = 11; ctx.lineCap = "round"; ctx.lineJoin = "round"; ctx.beginPath(); for (i = 0; i <= 200; i++) { p = sp(1 - (i / 200) * pw * .97, half); if (i) ctx.lineTo(p.x, p.y); else ctx.moveTo(p.x, p.y); } ctx.stroke(); ctx.restore(); }
    var p0 = P(lt, 300, 1200, eo), fade = t1 > 0 ? mix(1, .45, clamp(t1 / 400)) : 1;
    line(ctx, EN.x, EN.y, mix(EN.x, CX, p0), mix(EN.y, CY + 30, p0), c1, 8, p0 * fade, [18, 16]);
    var k0 = P(lt, 0, 500); ctx.save(); ctx.globalAlpha *= k0; rr(CX - 32, CY - 32, 64, 64, 12); ctx.fillStyle = C.ink; ctx.fill(); ctx.restore(); dot(ctx, EN.x, EN.y, 18, c1, k0);
    var tw0 = ts[0] + 1200, kw = clamp((lt - tw0) / 400);
    if (kw > 0) { ev(tw0, "pop"); var gp = reach * clamp((lt - tw0) / Math.max(1, d - tw0 - 500)), q = sp(1 - gp, 0);
      ctx.save(); ctx.strokeStyle = c2; ctx.lineWidth = 9; ctx.lineCap = "round"; ctx.lineJoin = "round"; ctx.beginPath(); for (i = 0; i <= 80; i++) { p = sp(1 - gp * i / 80, 0); if (i) ctx.lineTo(p.x, p.y); else ctx.moveTo(p.x, p.y); } ctx.stroke(); ctx.restore();
      dot(ctx, q.x, q.y, 20 + 3 * Math.sin(lt / 180), c2, kw); }
    var RX = 1210, MW = 1790 - RX - 50, to = s.to === undefined ? "目的地" : s.to, fr = s.from === undefined ? "入口" : s.from, pt = s.path === undefined ? "歩く道" : s.path, sl = st.label === undefined ? "直線" : st.label;
    if (to) { ctx.save(); ctx.globalAlpha *= k0; rr(RX, T + 62, 34, 34, 7); ctx.fillStyle = C.ink; ctx.fill(); ctx.restore(); txt(to, RX + 50, T + 96, fit(to, MW, { size: 48, weight: 800, color: C.ink, alpha: k0 })); }
    if (fr) { dot(ctx, RX + 17, T + 159, 16, c1, k0); txt(fr, RX + 50, T + 176, fit(fr, MW, { size: 48, weight: 800, color: c1, alpha: k0 })); }
    if (sl) { line(ctx, RX, T + 262, RX + 34, T + 262, c1, 8, p0, [10, 9]); txt(sl, RX + 50, T + 278, fit(sl, MW, { size: 46, weight: 800, color: c1, alpha: p0 })); }
    if (st.value !== undefined && st.value !== "") txt(String(st.value), RX + 50, T + 356, fit(String(st.value), MW, { size: 64, weight: 800, font: F.display, color: c1, alpha: p0 }));
    if (pt && kw > 0) { dot(ctx, RX + 17, T + 459, 16, c2, kw); txt(pt, RX + 50, T + 476, fit(pt, MW, { size: 48, weight: 800, color: c2, alpha: kw })); }
    var cap = Array.isArray(s.captions) ? s.captions : null;
    if (cap) { var stg = lt < ts[0] ? 0 : lt < ts[1] ? 1 : 2, t0 = stg === 0 ? 300 : ts[stg - 1]; while (stg > 0 && !cap[stg]) { stg--; t0 = stg === 0 ? 300 : ts[stg - 1]; } note(s, lt, t0, cap[stg], 912); }
    else note(s, lt, ts[0] + 1800);
  };

  /* ---- 太い棒と大きな数字: 太い横棒 2〜3 本が、決めた時に 1 本ずつのびて、大きな数字が数え上がる（名前は棒の上。狭い画面でも読める大きさ） ----
     {type:"bigbars", heading, lead:"上下に動く大きさ", items:[{label:"固い地面（最大）", value:100, unit:"m", color, at:秒}, {label:"海の潮（最大）", value:18}], unit:"m",
      big:0（数字を大きくする棒。既定は、値が最大の棒）, max（棒の端にあたる値。既定は最大の値）, note, at:[秒, 秒…]} */
  R.bigbars = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var items = (s.items || []).slice(0, 3), n = Math.max(1, items.length), y0 = (s.heading ? 290 : 200) + (s.lead ? 80 : 0), pit = Math.min(270, (890 - y0) / n), ls = Math.max(38, Math.min(50, pit * .2)), bh = Math.max(60, Math.min(96, pit * .38)), unit = s.unit || "";
    var vals = items.map(function (it) { return num(it.value); }), vmax = Math.max(num(s.max), Math.max.apply(null, vals.concat([1e-9]))), bigI = 0; vals.forEach(function (v, i) { if (v > vals[bigI]) bigI = i; }); if (s.big !== undefined && s.big !== null) bigI = int(s.big, 0, 0, n - 1);
    var full = items.map(function (it) { return String(it.value === undefined ? "" : it.value) + (it.unit === undefined ? unit : it.unit); }), X0 = 140, zs = bh / 96;
    var os = full.map(function (t, i) { return fit(t, 560, { size: Math.round((i === bigI ? 112 : 88) * zs), weight: 800, font: F.display }); }), numW = Math.max.apply(null, full.map(function (t, i) { return tw(t, os[i]); }).concat([0])), WMAX = 1780 - X0 - numW - 30;
    var ts = when(s, X.slots(n, d, 300, 1600)), last = 0; y0 += Math.max(0, (890 - y0 - pit * n) / 2);
    if (s.lead) txt(s.lead, 960, y0 - 34, fit(s.lead, 1600, { size: 44, weight: 800, align: "center", color: C.muted, alpha: P(lt, 0, 500) }));
    items.forEach(function (it, i) { var t = it.at === undefined || it.at === null ? ts[i] : num(it.at) * 1000, la = P(lt, t, t + 300), a = P(lt, t, t + 1100, eo); last = Math.max(last, t); if (la <= 0) return; ev(t, "pop", { i: i });
      var yT = y0 + pit * i + (pit - ls - 22 - bh) / 2, col = tone(it.color, acc(i)), w = Math.max(WMAX * vals[i] / vmax * a, 8), by = yT + ls + 22;
      if (lab(it)) txt(lab(it), X0, yT + ls * .86, fit(lab(it), 1640, { size: ls, weight: 800, color: C.ink, alpha: la }));
      ctx.save(); ctx.globalAlpha *= la; rr(X0, by, w, bh, 14); ctx.fillStyle = col; ctx.fill(); ctx.restore();
      txt(X.count(full[i], a), X0 + w + 26, by + bh / 2 + os[i].size * .36, Object.assign({}, os[i], { color: col, alpha: la })); });
    note(s, lt, last + 1700);
  };

  /* ---- 左右から引く: まん中の物が、左から太く、右から細く引かれて、のびちぢみする ----
     {type:"tugofwar", heading, center:"イオ", left:{label:"木星", pull:"木星の強い重力"（矢印の下の一言）, strong:true}, right:[{label:"エウロパ"}, {label:"ガニメデ"}]（1〜2 個。strong:true で太い矢印）,
      mark:"引っぱり合うと…？"（のびちぢみが始まる時の一言）, note, at:[右が出る時, のびちぢみが始まる時]} */
  R.tugofwar = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var T = top(s), CY = T + 285, Lf = side(s.left), Cn = side(s.center), Rs = (s.right === undefined || s.right === null ? [] : [].concat(s.right)).slice(0, 2).map(side), nR = Rs.length, ts = when(s, [d * .32, d * .62]), t2 = lt - ts[1], c1 = acc(0), c2 = acc(1);
    var LX = 330, LR = 185, IX = 1000, IR = 70, p0 = P(lt, 0, 700, eo), kc = P(lt, 250, 650), st = t2 > 0 ? Math.sin(t2 / 330) * clamp(t2 / 500) : 0, rx = IR * (1 + .30 * st), ry = IR * (1 - .22 * st);
    dot(ctx, LX, CY, LR * mix(.8, 1, p0), c1, p0); ring(ctx, LX, CY, LR * .62, C.onAccent, 8, p0 * .25);
    if (Lf.label) txt(Lf.label, LX, CY - LR - 34, fit(Lf.label, 500, { size: 52, weight: 800, align: "center", color: c1, alpha: p0 }));
    ctx.save(); ctx.globalAlpha *= kc; ctx.fillStyle = c2; ctx.beginPath(); ctx.ellipse(IX, CY, rx, ry, 0, 0, PI2); ctx.fill(); ctx.restore();
    if (Cn.label) txt(Cn.label, IX, CY - IR - 50, fit(Cn.label, 420, { size: 56, weight: 800, align: "center", color: c2, alpha: kc }));
    ev(900, "whoosh"); arw(ctx, IX - IR - 30, LX + LR + 30, CY, Lf.strong === false ? 12 : 26, c1, P(lt, 900, 1700, eo));
    if (Lf.pull) txt(Lf.pull, (IX - IR + LX + LR) / 2, CY + 118, fit(Lf.pull, IX - IR - LX - LR - 30, { size: 42, weight: 800, align: "center", color: C.ink, alpha: P(lt, 1500, 1900) }));
    var p1 = P(lt, ts[0], ts[0] + 600, eo), a1 = P(lt, ts[0] + 500, ts[0] + 1200, eo), la = P(lt, ts[0] + 900, ts[0] + 1300);
    if (p1 > 0) { ev(ts[0], "pop"); Rs.forEach(function (r, i) { var bx = nR === 1 ? 1540 : i ? 1640 : 1430, by = nR === 1 ? CY : i ? CY + 95 : CY - 85, br = nR === 1 ? 50 : i ? 48 : 36, ay = nR === 1 ? CY : i ? CY + 44 : CY - 34, col = tone(r.color, acc(2 + i));
      dot(ctx, bx, by, br * p1, col, p1); arw(ctx, IX + IR + 26, bx - br - 34, ay, r.strong ? 26 : 11, C.ink, a1);
      if (r.label) txt(r.label, bx, i ? by + br + 58 : by - br - 26, fit(r.label, 2 * (1790 - bx), { size: 44, weight: 800, align: "center", color: C.ink, alpha: la })); }); }
    if (s.mark && t2 > 0) { ev(ts[1], "pop"); var km = clamp(t2 / 400), mo = fit(s.mark, 1500, { size: 54, weight: 800, align: "center", color: c2, alpha: km }); txt(s.mark, 960, T + 570, Object.assign({}, mo, { size: mo.size * pop(km) })); }
    note(s, lt, ts[1] + 1300);
  };

  /* ---- 噴き出して降りもどる: 下の物から粒が噴き出す → 一部は外（右上）へ → 残りは左右に降ってもどる ----
     {type:"fountain", heading, source:"エンケラドゥス"（下の物の名前）, top:"宇宙へ噴き出す氷のつぶ"（上の一言）, out:{label:"Eリング", text:"ごく一部"}, back:{text:"ほとんどは", label:"雪になって\nもどる"},
      note, at:[外へ出る時, 降ってもどる時]} */
  R.fountain = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var T = top(s), BOT = 900, CX = 820, Rb = 420, CYb = BOT + Rb * .52, TOPY = CYb - Rb, JH = 270, O = side(s.out), Bk = side(s.back), ts = when(s, [d * .3, d * .6]), t1 = lt - ts[0], t2 = lt - ts[1], c1 = acc(0), c2 = acc(1), k0 = P(lt, 0, 500), i;
    ctx.save(); ctx.beginPath(); ctx.rect(100, T - 30, 1720, BOT - T + 30); ctx.clip();
    var glow = t2 > 0 ? clamp((t2 - 1200) / 1200) : 0;
    ctx.save(); ctx.globalAlpha *= k0; ctx.beginPath(); ctx.arc(CX, CYb, Rb, 0, PI2); ctx.fillStyle = C.panel2 || C.panel; ctx.fill(); if (glow > 0) { ctx.save(); ctx.globalAlpha *= glow * (.34 + .08 * Math.sin(lt / 300)); ctx.fillStyle = c2; ctx.fill(); ctx.restore(); } ctx.strokeStyle = C.muted; ctx.lineWidth = 6; ctx.stroke(); ctx.restore();
    [-.16, 0, .16].forEach(function (a) { line(ctx, CX + Rb * Math.sin(a) * .99, CYb - Rb * Math.cos(a) * .99, CX + Rb * Math.sin(a) * .88, CYb - Rb * Math.cos(a) * .88, c1, 10, k0); });
    var rnd = X.rand(11);
    for (i = 0; i < 46; i++) { var ph = rnd(), sp = .7 + rnd() * .6, ox = rnd() - .5, k = ((lt / 1500) * sp + ph) % 1, pr = 6 + 5 * rnd(); dot(ctx, CX + ox * 60 + ox * 150 * k, TOPY - JH * k, pr, c1, k0 * (1 - k) * .95); }
    var SX = 1560, SY = T + 150, p1 = P(lt, ts[0], ts[0] + 700, eo);
    if (p1 > 0) { ev(ts[0], "whoosh"); ring(ctx, SX, SY, 74 * p1, c1, 10, p1, [26, 14]); dot(ctx, SX, SY, 30 * p1, c1, p1 * .55);
      var a1 = P(lt, ts[0] + 500, ts[0] + 1400, eo), x0 = CX + 80, y0 = TOPY - JH * .9, x1 = SX - 116, y1 = SY + 40, la = clamp((t1 - 1000) / 400);
      if (a1 > 0) { ctx.save(); ctx.globalAlpha *= a1; ctx.strokeStyle = c1; ctx.lineWidth = 7; ctx.lineCap = "round"; ctx.setLineDash([16, 16]); ctx.lineDashOffset = -lt / 30; ctx.beginPath(); ctx.moveTo(x0, y0); ctx.quadraticCurveTo((x0 + x1) / 2, y0 - 70, mix(x0, x1, a1), mix(y0, y1, a1)); ctx.stroke(); ctx.restore(); }
      if (O.label) txt(O.label, SX, SY + 140, fit(O.label, 440, { size: 52, weight: 800, align: "center", color: c1, alpha: la }));
      if (O.text) txt(O.text, (x0 + x1) / 2 + 30, Math.min(y0, y1) - 78, fit(O.text, 420, { size: 44, weight: 800, align: "center", color: C.ink, alpha: la })); }
    if (t2 > 0) { ev(ts[1], "whoosh"); var rs = X.rand(23), a2 = clamp(t2 / 600);
      for (i = 0; i < 70; i++) { var sd = i % 2 ? 1 : -1, ph2 = rs(), k2 = ((t2 / 2100) * (.7 + rs() * .6) + ph2) % 1, sx = 70 + rs() * 260, qr = 6 + 5 * rs();
        var x2 = CX + sd * (sx * (.25 + .75 * k2)), dx = Math.min(Math.abs(x2 - CX), Rb * .99), yy = TOPY - JH * (1 - k2 * k2) + (Rb - Math.sqrt(Math.max(0, Rb * Rb - dx * dx))) * k2;
        dot(ctx, x2 + Math.sin(t2 / 400 + i) * 6, yy, qr, c2, a2 * (k2 < .9 ? 1 : (1 - k2) * 10)); }
      var lb = clamp((t2 - 600) / 400), by = T + 240;
      if (Bk.text) txt(Bk.text, 290, by, fit(Bk.text, 330, { size: 46, weight: 800, align: "center", color: C.ink, alpha: lb }));
      if (Bk.label) { var fl = fitLines(Bk.label, 330, { size: 56, weight: 800 }); drawLines(fl, 290, by + 34 + fl.lines.length * fl.o.size * .64, lb, c2); } }
    ctx.restore();
    if (s.source) txt(s.source, CX, BOT - 40, fit(s.source, 620, { size: 50, weight: 800, align: "center", color: C.ink, alpha: k0 }));
    if (s.top) txt(s.top, 120, T + 50, fit(s.top, 880, { size: 46, weight: 800, color: C.ink, alpha: k0 }));
    note(s, lt, ts[1] + 1800);
  };

  /* ---- 軸の傾き: 回る面の線の上に 1〜2 つの球。軸が傾いていき、傾きを弧と数字で比べる ----
     {type:"axistilt", heading, items:[{label:"地球", angle:23.5, text:"23.5度", size:0.8}, {label:"天王星", angle:97.77, size:1.2}]（angle は度。text を書かなければ angle と unit。size は球の大きさの比 0.7〜1.25）,
      unit:"度", plane:"回る面"（点線の名前）, big:1（数字を大きくする球。既定は最後）, note, at:[2 つ目が出る時]} */
  R.axistilt = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var items = (s.items || []).slice(0, 2), n = items.length, T = top(s), CY = T + 300, ts = when(s, [d * .45]), hl = C.warn, p0 = P(lt, 0, 700, eo), XS = n < 2 ? [960] : [540, 1360], bigI = s.big === undefined || s.big === null ? n - 1 : int(s.big, 0, 0, n - 1), unit = s.unit === undefined ? "度" : s.unit;
    line(ctx, 140, CY, 140 + 1640 * p0, CY, C.muted, 6, p0 * .9, [22, 18]);
    if (s.plane) txt(s.plane, 140, CY + 54, fit(s.plane, 250, { size: 36, weight: 700, color: C.muted, alpha: p0 }));
    items.forEach(function (it, i) { var t0 = i === 0 ? 300 : ts[0], a = clamp((lt - t0) / (i === 0 ? 1400 : 1700)); if (a <= 0) return; ev(t0, "whoosh", { i: i });
      var x = XS[i], r = 100 * Math.max(.7, Math.min(1.25, it.size === undefined ? 1 : num(it.size))), th = num(it.angle) * Math.PI / 180 * eo(clamp((a - .25) / .75)), al = Math.min(1, a * 3), col = tone(it.color, acc(i)), j;
      line(ctx, x, CY - r * 1.55, x, CY + r * 1.55, C.muted, 6, al * .6);
      ctx.save(); ctx.globalAlpha *= al; ctx.translate(x, CY); ctx.rotate(th); ctx.fillStyle = col; ctx.beginPath(); ctx.arc(0, 0, r, 0, PI2); ctx.fill(); ctx.save(); ctx.clip();
      ctx.fillStyle = C.onAccent; ctx.globalAlpha *= .3; var off = (lt / 900) % 1; for (j = -3; j < 4; j++) { ctx.beginPath(); ctx.ellipse((j + off) * r * .62, 0, r * .10, r * 1.05, 0, 0, PI2); ctx.fill(); } ctx.restore();
      ctx.strokeStyle = hl; ctx.lineWidth = 12; ctx.lineCap = "round"; ctx.beginPath(); ctx.moveTo(0, -r * 1.6); ctx.lineTo(0, -r); ctx.moveTo(0, r); ctx.lineTo(0, r * 1.6); ctx.stroke(); ctx.restore();
      if (th > 0) { ctx.save(); ctx.globalAlpha *= al; ctx.strokeStyle = hl; ctx.lineWidth = 8; ctx.lineCap = "round"; ctx.beginPath(); ctx.arc(x, CY, r * 1.36, -Math.PI / 2, -Math.PI / 2 + th); ctx.stroke(); ctx.restore(); }
      if (it.label) txt(it.label, x, T + 56, fit(it.label, 700, { size: 52, weight: 800, align: "center", color: C.ink, alpha: al }));
      var vt = it.text === undefined ? (it.angle === undefined ? "" : String(it.angle) + unit) : String(it.text), ka = clamp((a - .7) / .3), t3 = lt - t0 - 1700;
      if (vt && ka > 0) { var vo = fit(vt, 720, { size: i === bigI ? 100 : 80, weight: 800, font: F.display, align: "center", color: hl, alpha: ka }); txt(vt, x, T + 580, Object.assign({}, vo, { size: vo.size * (i === bigI && n > 1 && t3 > 0 ? 1 + .04 * Math.sin(t3 / 260) * clamp(t3 / 400) : 1) })); } });
    note(s, lt, (n > 1 ? ts[0] : 300) + 2300);
  };
}); }
