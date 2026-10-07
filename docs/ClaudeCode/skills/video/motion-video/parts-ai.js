/* motion-video parts-ai — 言葉・確率・くり返しの図解（確率の横棒・札に分ける・関わりの線・回って増える）。
 * 2026-10-07 に、解説動画「LLM」（yukkuri-work の kaisetsu-llm）の組み立て役が描き下ろした図解を、ほかの題材でも使える部品に直して足した。
 * どれも (s, lt, d) だけで決まる描画。色は配色（C）から取る。 */
if (!window.__mvPartsAi) { window.__mvPartsAi = 1; (window.MotionVideoParts = window.MotionVideoParts || []).push(function (R, X) {
  "use strict";
  var C = X.C, F = X.F, P = X.P, eo = X.eo, back = X.back, clamp = X.clamp, mix = X.mix;
  var txt = X.txt, tw = X.tw, rr = X.rr, acc = X.accentAt, ev = X.sfxEv, g = X.g, PI2 = Math.PI * 2;
  function top(s) { return s.heading ? 300 : 190; }
  function num(v) { var n = parseFloat(String(v).replace(/,/g, "")); return isFinite(n) ? n : 0; }
  function lab(it) { return typeof it === "string" ? it : (it && (it.label || it.text || it.title)) || ""; }
  function fit(t, maxW, o) { var size = o.size; while (size > 16 && tw(t, Object.assign({}, o, { size: size })) > maxW) size -= 2; return Object.assign({}, o, { size: size }); }
  function chip(ctx, x, y, w, h, t, fill, ink, a, size) { ctx.save(); ctx.globalAlpha *= clamp(a); rr(x, y, w, h, 14); ctx.fillStyle = fill; ctx.fill();
    txt(t, x + w / 2, y + h / 2 + size * .36, { size: size, weight: 800, align: "center", color: ink }); ctx.restore(); }
  /* 札の列を、幅に合わせて 1〜2 行に並べる → [{t, x, y, w}] */
  function layoutChips(toks, x0, x1, y, size, gap, h) { var ws = toks.map(function (t) { return tw(t, { size: size, weight: 800 }) + 44; }), rows = [[]], cur = 0, maxW = x1 - x0;
    toks.forEach(function (t, i) { if (cur + ws[i] > maxW && rows[rows.length - 1].length) { rows.push([]); cur = 0; } rows[rows.length - 1].push(i); cur += ws[i] + gap; });
    var out = []; rows.forEach(function (r, ri) { var tot = r.reduce(function (a, i) { return a + ws[i] + gap; }, -gap), x = (x0 + x1) / 2 - tot / 2;
      r.forEach(function (i) { out[i] = { t: toks[i], x: x, y: y + ri * (h + 26), w: ws[i] }; x += ws[i] + gap; }); }); return out; }

  /* ---- 確率の横棒: 候補の棒が伸び、数字は「？」のまま。順に、数字に替わる（当てたい物だけ大きく・色つき） ----
     {type:"probbars", heading, lead:"文の頭（次に来る言葉の前）", items:[{label, value}], unit:"%", highlight:[0, 3]} */
  R.probbars = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var items = (s.items || []).slice(0, 7), n = Math.max(1, items.length), y0 = top(s) + (s.lead ? 110 : 20), pit = Math.min(118, (900 - y0) / n), bh = Math.min(62, pit * .58);
    var vmax = Math.max.apply(null, items.map(function (it) { return num(it.value); }).concat([1e-9])), lx = 640, bx = lx + 30, bw = 760, hi = s.highlight || [0], unit = s.unit === undefined ? "%" : s.unit;
    var tGrow = Math.min(2600, d * .3), tRev = tGrow + 500, step = Math.max(500, (d - tRev - 900) / n);
    if (s.lead) { var a0 = P(lt, 0, 500); txt(s.lead, 960, y0 - 60, fit(s.lead, 1500, { size: 46, weight: 800, align: "center", color: C.ink, alpha: a0 })); }
    var order = hi.concat(items.map(function (_, i) { return i; }).filter(function (i) { return hi.indexOf(i) < 0; }));
    items.forEach(function (it, i) {
      var k = P(lt, 250 + i * (tGrow / n) * .7, 250 + i * (tGrow / n) * .7 + 800, eo), y = y0 + i * pit + pit / 2, hot = hi.indexOf(i) >= 0, at = tRev + order.indexOf(i) * step, kk = P(lt, at, at + 420, back);
      if (k <= 0) return; ev(at, hot ? "pop" : "tick", { i: i });
      var col = kk > 0 && hot ? acc(hi.indexOf(i)) : C.muted, w = Math.max(10, bw * num(it.value) / vmax * k);
      txt(lab(it), lx, y + 16, fit(lab(it), 520, { size: 40, weight: 800, align: "right", color: kk > 0 && hot ? col : C.ink, alpha: k }));
      ctx.save(); ctx.globalAlpha *= k * (hot || kk <= 0 ? 1 : .75); rr(bx, y - bh / 2, w, bh, 12); ctx.fillStyle = col; ctx.fill(); ctx.restore();
      if (kk < 1) txt("？", bx + w + 24, y + 18, { size: 46, weight: 800, color: C.muted, alpha: k * (1 - clamp(kk)) });
      if (kk > 0) { var z = hot ? 66 : 42; txt(String(it.value) + unit, bx + w + 24, y + z * .36, { size: z * (hot ? mix(.7, 1, clamp(kk)) : 1), weight: 800, font: F.display, color: hot ? col : C.ink, alpha: clamp(kk) * (hot ? 1 : .85) }); }
    });
  };

  /* ---- 札に分ける: 1 枚の文に切れ目が入り、札に分かれる。1 枚に名前が付く ----
     {type:"tokensplit", heading, tokens:["ずんだ","餅","は",…], mark:1（名前を付ける札）, label:"これが 1 トークン", note:"下に出す一言"} */
  R.tokensplit = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var toks = (s.tokens || []).map(String), n = Math.max(1, toks.length), size = n > 9 ? 44 : 54, h = size + 44, y = top(s) + 200;
    var tight = layoutChips(toks, 160, 1760, y, size, 0, h), wide = layoutChips(toks, 160, 1760, y, size, 18, h);
    var tCut = Math.min(1400, d * .2), tOpen = tCut + Math.min(1600, d * .22), kOpen = P(lt, tOpen, tOpen + 900, eo), tMark = tOpen + 1300;
    ev(tCut, "tick"); ev(tOpen, "whoosh");
    toks.forEach(function (t, i) { var a = tight[i], b = wide[i], x = mix(a.x, b.x, kOpen), yy = mix(a.y, b.y, kOpen), w = mix(a.w, b.w, kOpen), k = P(lt, 100, 600);
      var marked = s.mark === i && lt >= tMark, km = marked ? P(lt, tMark, tMark + 450, back) : 0;
      ctx.save(); ctx.globalAlpha *= k; rr(x, yy, w, h, kOpen > .02 ? 14 : 0); ctx.fillStyle = marked ? acc(0) : kOpen > .5 ? acc(i % 3 + 1) : C.panel; ctx.globalAlpha *= marked ? 1 : kOpen > .5 ? .9 : 1; ctx.fill();
      txt(t, x + w / 2, yy + h / 2 + size * .36, { size: size, weight: 800, align: "center", color: marked || kOpen > .5 ? C.onAccent : C.ink }); ctx.restore();
      if (i > 0 && kOpen < .98 && tight[i].y === tight[i - 1].y) { var kc = P(lt, tCut + i * 90, tCut + i * 90 + 300); if (kc > 0) { ctx.save(); ctx.globalAlpha *= kc * (1 - kOpen); ctx.strokeStyle = acc(0); ctx.lineWidth = 5; ctx.setLineDash([10, 8]); ctx.beginPath(); ctx.moveTo(x, yy - 16); ctx.lineTo(x, yy - 16 + (h + 32) * kc); ctx.stroke(); ctx.restore(); } }
      if (marked && s.label) { ev(tMark, "pop"); var lw = tw(s.label, { size: 34, weight: 800 }) + 40, lx2 = clamp((x + w / 2 - lw / 2 - 40) / 1e9) + Math.max(60, Math.min(1860 - lw, x + w / 2 - lw / 2)), ly = yy - 96;
        ctx.save(); ctx.globalAlpha *= clamp(km); ctx.strokeStyle = acc(0); ctx.lineWidth = 4; ctx.beginPath(); ctx.moveTo(x + w / 2, yy - 6); ctx.lineTo(x + w / 2, ly + 56); ctx.stroke(); ctx.restore();
        chip(ctx, lx2, ly, lw, 56, s.label, C.panel2 || C.panel, C.ink, km, 34); }
    });
    if (s.note) txt(s.note, 960, 930, fit(s.note, 1600, { size: 40, weight: 700, align: "center", color: C.muted, alpha: P(lt, tMark + 600, tMark + 1100) }));
  };

  /* ---- 関わりの線: 札の 1 枚から、ほかの札へ弧。関わりの強い 1 本だけ太くなる ----
     {type:"attention", heading, tokens:["猫","が","魚","を","食べた"], from:4, links:[{to:0, weight:0.7},{to:2, weight:0.9}], note} */
  R.attention = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var toks = (s.tokens || []).map(String), size = toks.length > 9 ? 42 : 52, h = size + 44, y = top(s) + 330, ch = layoutChips(toks, 140, 1780, y, size, 22, h);
    var from = Math.max(0, Math.min(toks.length - 1, s.from === undefined ? toks.length - 1 : s.from)), links = (s.links || []).filter(function (L) { return ch[L.to] && L.to !== from; });
    var wmax = Math.max.apply(null, links.map(function (L) { return num(L.weight); }).concat([1e-9])), t0 = Math.min(1200, d * .18), step = Math.max(450, Math.min(900, (d * .5) / Math.max(1, links.length))), tPick = t0 + links.length * step + 300;
    toks.forEach(function (t, i) { var c = ch[i], k = P(lt, i * 70, i * 70 + 420, back), isFrom = i === from, strong = links.some(function (L) { return L.to === i && num(L.weight) === wmax; }) && lt >= tPick;
      chip(ctx, c.x, c.y + (1 - clamp(k)) * 30, c.w, h, t, isFrom ? acc(0) : strong ? acc(1) : C.panel, isFrom || strong ? C.onAccent : C.ink, k, size); });
    var f = ch[from]; if (!f) return;
    links.forEach(function (L, li) { var c = ch[L.to], at = t0 + li * step, k = P(lt, at, at + 600, eo); if (k <= 0) return; ev(at, "tick", { i: li });
      var strong = num(L.weight) === wmax, kp = strong ? P(lt, tPick, tPick + 500) : 0, x1 = f.x + f.w / 2, x2 = c.x + c.w / 2, y1 = Math.min(f.y, c.y) - 8, lift = 90 + Math.abs(x2 - x1) * .28;
      ctx.save(); ctx.strokeStyle = strong ? acc(1) : C.muted; ctx.lineWidth = mix(3, 3 + 11 * num(L.weight) / wmax, strong ? .35 + .65 * kp : .35); ctx.globalAlpha *= strong ? mix(.5, 1, kp) : mix(.5, lt >= tPick ? .28 : .5, P(lt, tPick, tPick + 500)); ctx.lineCap = "round";
      ctx.beginPath(); for (var q = 0; q <= 24; q++) { var u = q / 24 * k, bx2 = mix(x1, x2, u), by2 = y1 - lift * 4 * u * (1 - u) * (1 / Math.max(k, .001)) * k; if (q) ctx.lineTo(bx2, by2); else ctx.moveTo(bx2, by2); } ctx.stroke(); ctx.restore();
      if (strong && kp > 0 && L.label) txt(L.label, (x1 + x2) / 2, y1 - lift - 22, { size: 36, weight: 800, align: "center", color: acc(1), alpha: kp }); });
    ev(tPick, "pop");
    if (s.note) txt(s.note, 960, 930, fit(s.note, 1600, { size: 40, weight: 700, align: "center", color: C.muted, alpha: P(lt, tPick + 500, tPick + 1000) }));
  };

  /* ---- 回って増える: 段の輪を光が回り、1 周ごとに、上の列に札が 1 枚増える ----
     {type:"loopgrow", heading, steps:["読む","当てる","選ぶ","足す"], items:["むかし","むかし","ある","ところに"], seed:"最初からある札"} */
  R.loopgrow = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var steps = (s.steps || []).map(lab).slice(0, 6), ns = Math.max(2, steps.length), items = (s.items || []).map(String), laps = Math.max(1, items.length), cx = 960, cy = top(s) + 370, rad = 170;
    var t0 = 700, lap = Math.max(1100, (d - t0 - 700) / laps), u = clamp((lt - t0) / (lap * laps)) * laps, done = Math.floor(u + 1e-6), ph = u - Math.floor(u);
    ctx.save(); ctx.globalAlpha *= P(lt, 0, 500); ctx.strokeStyle = C.line || C.muted; ctx.lineWidth = 6; ctx.beginPath(); ctx.arc(cx, cy, rad, 0, PI2); ctx.stroke(); ctx.restore();
    steps.forEach(function (t, i) { var a = -Math.PI / 2 + PI2 * i / ns, x = cx + Math.cos(a) * rad, y = cy + Math.sin(a) * rad, k = P(lt, 150 + i * 120, 650 + i * 120, back), on = lt > t0 && u < laps && Math.floor(ph * ns) === i;
      var w = Math.max(150, tw(t, { size: 36, weight: 800 }) + 48);
      chip(ctx, x - w / 2, y - 34, w, 68, t, on ? acc(0) : C.panel, on ? C.onAccent : C.ink, k, 36); });
    if (lt > t0 && u < laps) { var a2 = -Math.PI / 2 + PI2 * ph, px = cx + Math.cos(a2) * rad, py = cy + Math.sin(a2) * rad; ctx.save(); ctx.fillStyle = acc(1); ctx.globalAlpha *= .9; ctx.beginPath(); ctx.arc(px, py, 13, 0, PI2); ctx.fill(); ctx.globalAlpha *= .3; ctx.beginPath(); ctx.arc(px, py, 26, 0, PI2); ctx.fill(); ctx.restore(); }
    var row = (s.seed ? [String(s.seed)] : []).concat(items.slice(0, Math.min(laps, done + 1))), shown = layoutChips(row, 140, 1780, top(s) + 30, 44, 16, 84);
    row.forEach(function (t, i) { var isSeed = s.seed && i === 0, li = i - (s.seed ? 1 : 0), at = isSeed ? 200 : t0 + (li + 1) * lap - 250, k = isSeed ? P(lt, 200, 700, back) : P(lt, at, at + 450, back); if (k <= 0) return;
      if (!isSeed) ev(at, "pop", { i: li }); var c = shown[i], fresh = !isSeed && li === done - 1 && u < laps;
      chip(ctx, c.x, c.y + (1 - clamp(k)) * 60, c.w, 84, t, isSeed ? C.panel : fresh ? acc(1) : acc(0), isSeed ? C.ink : C.onAccent, k, 44); });
    if (s.note) txt(s.note, 960, Math.min(1030, cy + rad + 110), fit(s.note, 1600, { size: 38, weight: 700, align: "center", color: C.muted, alpha: P(lt, t0 + lap, t0 + lap + 500) }));
  };
}); }
