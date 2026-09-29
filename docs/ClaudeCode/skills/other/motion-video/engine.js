/* motion-video engine — 台本（SPEC）から、時刻だけで決まる映像を Canvas に描き、プレイヤーを動かす。
 * build.py が SPEC（durations 計算済み）・THEME・このファイルを 1 つの HTML に埋め込む。
 * 描画は draw(t) の純粋な関数（t = 動画の先頭からの ms）。シーク・倍速・巻き戻しでも同じ画になる。 */
(function () {
  "use strict";
  var SPEC = window.__MV_SPEC__, TH = window.__MV_THEME__;
  var W = 1920, H = 1080;
  var $ = function (id) { return document.getElementById(id); };

  /* ================= 時間割 ================= */
  var SCENES = [], CHAPTERS = [], CUES = [], DUR = 0;
  SPEC.chapters.forEach(function (ch, ci) {
    CHAPTERS.push({ t: DUR, name: ch.title, desc: ch.desc || "", i: ci });
    ch.scenes.forEach(function (s) {
      var d = s._dur;
      SCENES.push({ s: s, t0: DUR, d: d, ci: ci });
      (s._cues || []).forEach(function (c) { CUES.push({ a: DUR + c[0], b: DUR + c[1], text: c[2] }); });
      DUR += d;
    });
  });
  function chapterAt(t) { var i = 0; for (var k = 0; k < CHAPTERS.length; k++) if (t >= CHAPTERS[k].t) i = k; return i; }
  function chLen(i) { return (i < CHAPTERS.length - 1 ? CHAPTERS[i + 1].t : DUR) - CHAPTERS[i].t; }
  function sceneAt(t) { var i = 0; for (var k = 0; k < SCENES.length; k++) if (t >= SCENES[k].t0) i = k; return i; }

  /* ================= 描画の道具 ================= */
  var cv = $("mv-canvas"), ctx = cv.getContext("2d");
  var C = TH.canvas, F = TH.fonts;
  var clamp = function (v, a, b) { a = a === undefined ? 0 : a; b = b === undefined ? 1 : b; return Math.max(a, Math.min(b, v)); };
  var lin = function (x, a, b) { return clamp((x - a) / (b - a)); };
  var eo = function (x) { return 1 - Math.pow(1 - x, 3); };
  var eio = function (x) { return x < .5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; };
  var back = function (x) { var c1 = 1.5, c3 = c1 + 1; return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2); };
  var P = function (x, a, b, e) { return (e || eo)(lin(x, a, b)); };
  var mix = function (a, b, k) { return a + (b - a) * k; };
  function rr(x, y, w, h, r) {
    r = Math.max(0, Math.min(r, w / 2, h / 2));
    ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
  }
  function font(o) { return (o.weight || 400) + " " + (o.size || 30) + "px " + (o.font || F.sans); }
  function txt(s, x, y, o) {
    o = o || {}; ctx.save(); ctx.font = font(o); ctx.fillStyle = o.color || C.ink;
    ctx.textAlign = o.align || "left"; ctx.textBaseline = o.base || "alphabetic";
    if (o.alpha !== undefined) ctx.globalAlpha *= o.alpha;
    if (o.spacing && "letterSpacing" in ctx) ctx.letterSpacing = o.spacing + "px";
    ctx.fillText(s, x, y); ctx.restore();
  }
  function tw(s, o) { ctx.save(); ctx.font = font(o || {}); var w = ctx.measureText(s).width; ctx.restore(); return w; }
  /* 日本語を含む折り返し（行頭禁則の簡易版） */
  var NOSTART = "、。，．・：；？！）」』】〉》ー々ぁぃぅぇぉっゃゅょァィゥェォッャュョ";
  function wrap(s, maxW, o) {
    var out = [], cur = "";
    var tokens = String(s).match(/[A-Za-z0-9_\-./:@#%&+=~`'"(){}\[\]<>$*]+|\s+|./g) || [];
    tokens.forEach(function (tok) {
      var t2 = cur + tok;
      if (tw(t2.replace(/\*\*/g, ""), o) <= maxW || !cur) { cur = t2; return; }
      if (NOSTART.indexOf(tok[0]) >= 0) { cur = t2; return; }
      out.push(cur.replace(/\s+$/, "")); cur = tok.replace(/^\s+/, "");
    });
    if (cur) out.push(cur);
    return out;
  }
  /* **強調** を含む 1 行を描く（強調は accent の色と下線の伸び） */
  function rich(line, x, y, o, emK) {
    var parts = String(line).split("**"), cx = x, total = tw(line.replace(/\*\*/g, ""), o);
    if (o.align === "center") cx = x - total / 2; else if (o.align === "right") cx = x - total;
    parts.forEach(function (p, i) {
      if (!p) return;
      var em = i % 2 === 1, w = tw(p, o);
      txt(p, cx, y, { size: o.size, weight: em ? Math.max(700, o.weight || 400) : o.weight, font: o.font, color: em ? C.accent : (o.color || C.ink), alpha: o.alpha });
      if (em && emK !== undefined) {
        ctx.save(); ctx.globalAlpha *= (o.alpha === undefined ? 1 : o.alpha); ctx.fillStyle = C.accent;
        ctx.fillRect(cx, y + o.size * 0.18, w * clamp(emK), Math.max(3, o.size * 0.07)); ctx.restore();
      }
      cx += w;
    });
  }
  function icon(s, x, y, size, col) {
    if (!s) { ctx.save(); ctx.fillStyle = col || C.accent; ctx.beginPath(); ctx.arc(x, y, size * .22, 0, Math.PI * 2); ctx.fill(); ctx.restore(); return; }
    txt(s, x, y + size * .35, { size: size, align: "center", color: col || C.ink, font: '"Apple Color Emoji","Segoe UI Emoji","Noto Color Emoji",' + F.sans });
  }
  function stateMark(x, y, state, t, r) {
    r = r || 9; ctx.save();
    if (state === "working") {
      ctx.strokeStyle = C.edge; ctx.lineWidth = 3; ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.stroke();
      ctx.strokeStyle = C.accent; var a0 = (t / 180) % (Math.PI * 2);
      ctx.beginPath(); ctx.arc(x, y, r, a0, a0 + Math.PI * 1.2); ctx.stroke();
    } else if (state === "done") {
      ctx.fillStyle = C.ok; ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = C.bg0; ctx.lineWidth = 2.6; ctx.lineCap = "round"; ctx.lineJoin = "round";
      ctx.beginPath(); ctx.moveTo(x - r * .45, y); ctx.lineTo(x - r * .1, y + r * .38); ctx.lineTo(x + r * .5, y - r * .38); ctx.stroke();
    } else if (state === "blocked") {
      var pu = .5 + .5 * Math.sin(t / 160);
      ctx.globalAlpha *= .3 + .3 * pu; ctx.fillStyle = C.warn; ctx.beginPath(); ctx.arc(x, y, r + 5, 0, Math.PI * 2); ctx.fill();
      ctx.globalAlpha = 1; ctx.fillStyle = C.warn; ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = C.bg0; ctx.fillRect(x - 1.4, y - r * .55, 2.8, r * .7); ctx.fillRect(x - 1.4, y + r * .3, 2.8, 2.8);
    } else if (state === "idle") {
      ctx.strokeStyle = C.muted; ctx.lineWidth = 2.6; ctx.beginPath(); ctx.arc(x, y, r - 1, 0, Math.PI * 2); ctx.stroke();
    } else { ctx.fillStyle = C.faint; ctx.beginPath(); ctx.arc(x, y, 3.5, 0, Math.PI * 2); ctx.fill(); }
    ctx.restore();
  }
  function panel(x, y, w, h, o) {
    o = o || {}; ctx.save();
    if (o.shadow !== false) { ctx.shadowColor = C.shadow; ctx.shadowBlur = 36; ctx.shadowOffsetY = 14; }
    rr(x, y, w, h, o.r === undefined ? 16 : o.r); ctx.fillStyle = o.fill || C.panel; ctx.fill();
    ctx.shadowColor = "transparent"; ctx.lineWidth = o.lw || 1.5; ctx.strokeStyle = o.stroke || C.edge; ctx.stroke(); ctx.restore();
  }
  function accentAt(i) { return C.accents[i % C.accents.length]; }
  /* 共通の見出し（場面の左上） */
  function heading(s, lt) {
    if (!s.heading) return 0;
    var k = P(lt, 0, 600);
    txt(s.heading, 120, 190 + (1 - k) * 14, { size: 54, weight: 800, font: F.display, color: C.ink, alpha: k });
    ctx.save(); ctx.globalAlpha *= k; ctx.fillStyle = C.accent; ctx.fillRect(120, 214, 90 * P(lt, 200, 900), 6); ctx.restore();
    return 1;
  }
  /* 場面の中の「区切り」を、長さに応じた時刻に割り当てる（最初の in ms で入り、残りに均等） */
  function slots(n, d, lead, tail) {
    var a = lead || 500, b = Math.max(a + 200, d - (tail || 900)), out = [];
    for (var i = 0; i < n; i++) out.push(a + (b - a) * i / Math.max(1, n));
    return out;
  }

  /* ================= 紋章（タイトル・エンドで使う） ================= */
  function emblem(kind, cx, cy, r, rot, alpha, label) {
    if (kind === "none" || r <= 0) return;
    ctx.save(); ctx.globalAlpha *= alpha; ctx.translate(cx, cy);
    if (kind === "wheel") {
      ctx.rotate(rot); var s = r / 23; ctx.scale(s, s);
      for (var i = 0; i < 8; i++) { var a0 = -Math.PI / 2 + i * Math.PI / 4, a1 = a0 + Math.PI / 4;
        ctx.beginPath(); ctx.arc(0, 0, 23, a0, a1); ctx.arc(0, 0, 9, a1, a0, true); ctx.closePath(); ctx.fillStyle = i === 0 ? C.accent2 : C.panel2; ctx.fill(); }
      ctx.strokeStyle = C.accent; ctx.lineCap = "round"; ctx.lineWidth = 3;
      for (var j = 0; j < 4; j++) { var a = j * Math.PI / 4; ctx.beginPath(); ctx.moveTo(Math.cos(a) * -29, Math.sin(a) * -29); ctx.lineTo(Math.cos(a) * 29, Math.sin(a) * 29); ctx.stroke(); }
      ctx.lineWidth = 4; ctx.beginPath(); ctx.arc(0, 0, 23, 0, Math.PI * 2); ctx.stroke();
      ctx.fillStyle = C.bg0; ctx.lineWidth = 2.6; ctx.beginPath(); ctx.arc(0, 0, 9.5, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    } else {
      /* ring: 輪と頭文字 */
      ctx.rotate(rot * .3);
      ctx.strokeStyle = C.accent; ctx.lineWidth = r * .08; ctx.beginPath(); ctx.arc(0, 0, r, -Math.PI * .45, Math.PI * 1.35); ctx.stroke();
      ctx.strokeStyle = C.accent2; ctx.beginPath(); ctx.arc(0, 0, r * .72, Math.PI * .6, Math.PI * 2.3); ctx.stroke();
      ctx.rotate(-rot * .3);
      txt((label || "•").slice(0, 1), 0, r * .26, { size: r * .78, weight: 800, align: "center", font: F.display, color: C.ink });
    }
    ctx.restore();
  }

  /* ================= 場面の部品 ================= */
  var LAYOUT_CACHE = new WeakMap();
  var IMGS = {};
  var R = {};

  R.title = function (s, lt, d, T) {
    var k = P(lt, 0, 1500, back);
    for (var i = 0; i < 3; i++) { var ph = ((lt / 2600) + i / 3) % 1;
      ctx.save(); ctx.strokeStyle = C.accent2; ctx.globalAlpha *= (1 - ph) * .16 * P(lt, 600, 1600); ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(960, 400, 190 + ph * 260, 0, Math.PI * 2); ctx.stroke(); ctx.restore(); }
    emblem(s.mark || "ring", 960, 400, 160 * k, (1 - P(lt, 0, 2000)) * -2.4 + lt * .00012, clamp(k * 1.4), s.title);
    ctx.save(); ctx.font = font({ size: 116, weight: 800, font: F.display });
    var w = ctx.measureText(s.title).width, rv = P(lt, 1200, 2600, eio);
    ctx.beginPath(); ctx.rect(960 - w / 2 - 10, 600, (w + 20) * rv, 160); ctx.clip();
    txt(s.title, 960, 722, { size: 116, weight: 800, align: "center", font: F.display }); ctx.restore();
    if (rv > 0 && rv < 1) { ctx.fillStyle = C.accent2; ctx.fillRect(960 - w / 2 - 10 + (w + 20) * rv, 618, 5, 118); }
    if (s.subtitle) txt(s.subtitle, 960, 806, { size: 42, weight: 700, align: "center", color: C.accent, alpha: P(lt, 2000, 2900), spacing: 8 });
    var tg = P(lt, 3200, 4200);
    if (s.tagline) rich(s.tagline, 960, 888 + (1 - tg) * 16, { size: 36, align: "center", color: C.muted, alpha: tg });
  };

  R.bullets = function (s, lt, d, T) {
    heading(s, lt);
    var items = s.items || [], at = slots(items.length, d, 700, Math.min(1600, d * .25));
    var y = s.heading ? 330 : 230, cur = -1;
    at.forEach(function (a, i) { if (lt >= a) cur = i; });
    var lh = 112, maxW = 1540;
    items.forEach(function (it, i) {
      var k = P(lt, at[i], at[i] + 600), text = typeof it === "string" ? it : it.text;
      if (k <= 0) return;
      var lines = wrap(text, maxW - 120, { size: 40, weight: 500 });
      var yy = y, act = i === cur && s.focus !== false;
      ctx.save(); ctx.globalAlpha *= k * (act || cur < 0 ? 1 : .55);
      ctx.translate((1 - k) * -40, 0);
      if (act) { rr(96, yy - 58, 1728, lines.length * 54 + 44, 16); ctx.fillStyle = C.panel; ctx.fill(); ctx.fillStyle = C.accent; ctx.fillRect(96, yy - 58, 6, lines.length * 54 + 44); }
      icon(it.icon, 160, yy - 14, 44, accentAt(i));
      lines.forEach(function (ln, j) { rich(ln, 220, yy + j * 54, { size: 40, weight: 500 }, act ? P(lt, at[i] + 300, at[i] + 900) : 1); });
      ctx.restore();
      y += lines.length * 54 + 58;
    });
  };

  function flowLayout(s) {
    var c = LAYOUT_CACHE.get(s); if (c) return c;
    var nodes = s.nodes || [], edges = s.edges || [], ids = nodes.map(function (n) { return n.id; });
    var rank = {}; ids.forEach(function (i) { rank[i] = 0; });
    for (var it = 0; it < ids.length; it++) edges.forEach(function (e) {
      if (rank[e.from] === undefined || rank[e.to] === undefined || e.back) return;
      if (rank[e.to] <= rank[e.from]) rank[e.to] = rank[e.from] + 1; });
    var maxR = 0; ids.forEach(function (i) { maxR = Math.max(maxR, rank[i]); });
    var cols = []; for (var r = 0; r <= maxR; r++) cols.push([]);
    ids.forEach(function (i) { cols[rank[i]].push(i); });
    var pos = {}, span = Math.min(1600, 450 * (maxR + 1)), x0 = 960 - span / 2 + 170, x1 = 960 + span / 2 - 170, y0 = s.heading ? 330 : 240, y1 = 900;
    cols.forEach(function (col, r) {
      var x = maxR ? mix(x0, x1, r / maxR) : 960;
      col.forEach(function (id, k) { pos[id] = { x: x, y: mix(y0, y1, (k + 1) / (col.length + 1)), r: r }; });
    });
    var nw = maxR ? Math.min(330, (x1 - x0) / maxR - 70) : 330;
    c = { pos: pos, rank: rank, maxR: maxR, nw: Math.max(200, nw), nh: 124 };
    LAYOUT_CACHE.set(s, c); return c;
  }
  function qpt(p0, c, p1, u) { var v = 1 - u; return { x: v * v * p0.x + 2 * v * u * c.x + u * u * p1.x, y: v * v * p0.y + 2 * v * u * c.y + u * u * p1.y }; }
  R.flow = function (s, lt, d, T) {
    heading(s, lt);
    var L = flowLayout(s), byId = {}; (s.nodes || []).forEach(function (n) { byId[n.id] = n; });
    var nodeIn = function (id) { return 400 + L.pos[id].r * Math.min(700, d * .08); };
    var edges = s.edges || [], nE = edges.length;
    var buildEnd = 400 + L.maxR * Math.min(700, d * .08) + 900;
    var flowAt = slots(nE, d, buildEnd, 900);
    edges.forEach(function (e, i) {
      var a = L.pos[e.from], b = L.pos[e.to]; if (!a || !b) return;
      var p0, p1, c;
      if (e.back || b.r <= a.r) { p0 = { x: a.x, y: a.y + L.nh / 2 }; p1 = { x: b.x, y: b.y + L.nh / 2 + 4 }; c = { x: (a.x + b.x) / 2, y: Math.max(a.y, b.y) + 220 }; }
      else { p0 = { x: a.x + L.nw / 2, y: a.y }; p1 = { x: b.x - L.nw / 2 - 6, y: b.y }; c = { x: (p0.x + p1.x) / 2, y: (p0.y + p1.y) / 2 - (a.y === b.y ? 0 : 0) }; }
      var st = Math.max(nodeIn(e.from), nodeIn(e.to)) + 300, k = P(lt, st, st + 700, eio);
      if (k <= 0) return;
      ctx.save(); ctx.strokeStyle = e.color || C.accent2; ctx.lineWidth = 4; if (e.dashed) ctx.setLineDash([14, 10]);
      var glow = lt > flowAt[i] && lt < flowAt[i] + 1400 ? Math.sin(lin(lt, flowAt[i], flowAt[i] + 1400) * Math.PI) : 0;
      if (glow > 0) { ctx.shadowColor = C.accent2; ctx.shadowBlur = 24 * glow; }
      ctx.beginPath(); var N = 40;
      for (var j = 0; j <= N * k; j++) { var q = qpt(p0, c, p1, j / N); j ? ctx.lineTo(q.x, q.y) : ctx.moveTo(q.x, q.y); }
      ctx.stroke(); ctx.setLineDash([]); ctx.shadowBlur = 0;
      if (k >= 1) {
        var pe = qpt(p0, c, p1, 1), pb = qpt(p0, c, p1, .96), ang = Math.atan2(pe.y - pb.y, pe.x - pb.x);
        ctx.save(); ctx.fillStyle = e.color || C.accent2; ctx.translate(pe.x, pe.y); ctx.rotate(ang);
        ctx.beginPath(); ctx.moveTo(6, 0); ctx.lineTo(-16, -11); ctx.lineTo(-16, 11); ctx.closePath(); ctx.fill(); ctx.restore();
        if (e.label) { var m = qpt(p0, c, p1, .5), w = tw(e.label, { size: 22, weight: 700 }) + 28;
          rr(m.x - w / 2, m.y - 20, w, 40, 20); ctx.fillStyle = C.bg1; ctx.fill(); ctx.strokeStyle = C.edge; ctx.lineWidth = 1.5; ctx.stroke();
          txt(e.label, m.x, m.y + 8, { size: 22, weight: 700, align: "center", color: C.muted }); }
      }
      ctx.restore();
      if (e.travel !== undefined && e.travel !== false && lt > flowAt[i] && lt < flowAt[i] + 1400) {
        var u = eio(lin(lt, flowAt[i], flowAt[i] + 1400)), pt = qpt(p0, c, p1, u), lab = e.travel === true ? "" : String(e.travel);
        ctx.save(); ctx.shadowColor = C.accent; ctx.shadowBlur = 20; ctx.fillStyle = C.accent;
        if (lab) { var tw2 = tw(lab, { size: 20, weight: 700, font: F.mono }) + 24; rr(pt.x - tw2 / 2, pt.y - 20, tw2, 40, 10); ctx.fill(); ctx.shadowBlur = 0;
          txt(lab, pt.x, pt.y + 7, { size: 20, weight: 700, font: F.mono, align: "center", color: C.onAccent }); }
        else { ctx.beginPath(); ctx.arc(pt.x, pt.y, 11, 0, Math.PI * 2); ctx.fill(); }
        ctx.restore();
      }
    });
    Object.keys(L.pos).forEach(function (id, i) {
      var p = L.pos[id], n = byId[id], k = P(lt, nodeIn(id), nodeIn(id) + 600, back);
      if (k <= 0) return;
      var hot = edges.some(function (e, j) { return e.to === id && lt > flowAt[j] + 1200 && lt < flowAt[j] + 2600; });
      ctx.save(); ctx.translate(p.x, p.y); ctx.scale(k, k);
      panel(-L.nw / 2, -L.nh / 2, L.nw, L.nh, { stroke: hot ? C.accent : C.edge, lw: hot ? 3 : 1.5, fill: n.kind === "start" ? C.accent : C.panel });
      var ink = n.kind === "start" ? C.onAccent : C.ink;
      txt(n.label, 0, n.sub ? -2 : 13, { size: 36, weight: 800, align: "center", color: ink });
      if (n.sub) txt(n.sub, 0, 38, { size: 22, align: "center", color: n.kind === "start" ? ink : C.muted, font: F.mono });
      ctx.restore();
    });
  };

  R.steps = function (s, lt, d, T) {
    heading(s, lt);
    var items = s.items || [], n = items.length, at = slots(n, d, 600, Math.min(1400, d * .2));
    var y = s.heading ? 560 : 500, x0 = 220, x1 = 1700, cur = -1;
    at.forEach(function (a, i) { if (lt >= a) cur = i; });
    ctx.save(); ctx.strokeStyle = C.edge; ctx.lineWidth = 6; ctx.beginPath(); ctx.moveTo(x0, y); ctx.lineTo(x1, y); ctx.stroke();
    var prog = n > 1 ? clamp((cur + P(lt, at[Math.max(0, cur)], at[Math.max(0, cur)] + 700)) / (n - 1)) : 1;
    ctx.strokeStyle = C.accent; ctx.beginPath(); ctx.moveTo(x0, y); ctx.lineTo(mix(x0, x1, Math.min(1, prog)), y); ctx.stroke(); ctx.restore();
    items.forEach(function (it, i) {
      var x = n > 1 ? mix(x0, x1, i / (n - 1)) : 960, k = P(lt, at[i] - 200, at[i] + 400, back), act = i === cur;
      ctx.save(); ctx.translate(x, y); ctx.scale(Math.max(.001, k) * (act ? 1.12 : 1), Math.max(.001, k) * (act ? 1.12 : 1));
      ctx.fillStyle = i <= cur ? accentAt(i) : C.panel; ctx.beginPath(); ctx.arc(0, 0, 40, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = accentAt(i); ctx.lineWidth = 3; ctx.stroke();
      txt(String(i + 1), 0, 13, { size: 36, weight: 800, align: "center", color: i <= cur ? C.onAccent : C.ink });
      ctx.restore();
      var tk = P(lt, at[i], at[i] + 500);
      var lab = typeof it === "string" ? it : it.label;
      wrap(lab, 280, { size: 32, weight: 700 }).forEach(function (ln, j) { txt(ln, x, y + 110 + j * 40, { size: 32, weight: 700, align: "center", alpha: tk * (act ? 1 : .7) }); });
      if (it.sub) wrap(it.sub, 280, { size: 24 }).forEach(function (ln, j) { txt(ln, x, y + 190 + j * 32, { size: 24, align: "center", color: C.muted, alpha: tk }); });
    });
  };

  R.terminal = function (s, lt, d, T) {
    heading(s, lt);
    var x = 200, y = s.heading ? 290 : 190, w = 1520, h = s.heading ? 680 : 760;
    var k = P(lt, 0, 700); ctx.save(); ctx.globalAlpha *= k; ctx.translate(0, (1 - k) * 30);
    panel(x, y, w, h, { fill: C.code, r: 18 });
    ctx.save(); rr(x, y, w, h, 18); ctx.clip();
    ctx.fillStyle = C.codeBar; ctx.fillRect(x, y, w, 48);
    [C.warn, C.accent2, C.ok].forEach(function (c, i) { ctx.fillStyle = c; ctx.globalAlpha = .75; ctx.beginPath(); ctx.arc(x + 30 + i * 26, y + 24, 8, 0, Math.PI * 2); ctx.fill(); });
    ctx.globalAlpha = 1;
    txt(s.title || "terminal", x + w / 2, y + 32, { size: 20, font: F.mono, color: C.codeMuted, align: "center" });
    var lines = s.lines || [], prompt = s.prompt || "$", plan = [], at = 800, CH = 34;
    var totalChars = 0; lines.forEach(function (l) { if (l.cmd) totalChars += l.cmd.length; });
    var budget = Math.max(1, d * .75 - 800 - lines.length * 350), rate = Math.min(55, Math.max(14, budget / Math.max(1, totalChars)));
    lines.forEach(function (l) {
      if (l.cmd) { var dd = l.cmd.length * rate; plan.push({ l: l, a: at, b: at + dd }); at += dd + 300; }
      else { plan.push({ l: l, a: at, b: at }); at += 220; }
    });
    var row = 0, lh = 44, maxRows = Math.floor((h - 90) / lh), rows = [];
    plan.forEach(function (p) {
      if (lt < p.a) return;
      if (p.l.cmd) { var n = Math.floor(p.l.cmd.length * lin(lt, p.a, p.b)); rows.push({ cmd: true, text: p.l.cmd.slice(0, n), typing: lt < p.b }); }
      else String(p.l.out).split("\n").forEach(function (o) { rows.push({ cmd: false, text: o }); });
    });
    rows.slice(-maxRows).forEach(function (r, i) {
      var yy = y + 100 + i * lh;
      if (r.cmd) {
        txt(prompt, x + 36, yy, { size: 30, font: F.mono, color: C.accent2 });
        var px = x + 36 + tw(prompt + " ", { size: 30, font: F.mono });
        txt(r.text, px, yy, { size: 30, font: F.mono, color: C.codeInk });
        if (r.typing || (i === Math.min(rows.length, maxRows) - 1 && Math.floor(lt / 500) % 2 === 0)) {
          ctx.fillStyle = C.accent2; ctx.fillRect(px + tw(r.text, { size: 30, font: F.mono }) + 4, yy - 26, 14, 32); }
      } else txt(r.text, x + 36, yy, { size: 28, font: F.mono, color: C.codeMuted });
    });
    ctx.restore(); ctx.restore();
  };

  function parseNum(v) { var m = String(v).match(/-?[\d,]*\.?\d+/); if (!m) return null;
    return { m: m, n: parseFloat(m[0].replace(/,/g, "")), dec: (m[0].split(".")[1] || "").length, comma: m[0].indexOf(",") >= 0 }; }
  function fmtNum(orig, k) {
    var p = parseNum(orig); if (!p) return orig; var v = p.n * k, s2 = v.toFixed(p.dec);
    if (p.comma) { var q = s2.split("."); q[0] = q[0].replace(/\B(?=(\d{3})+(?!\d))/g, ","); s2 = q.join("."); }
    return String(orig).slice(0, p.m.index) + s2 + String(orig).slice(p.m.index + p.m[0].length);
  }
  R.stats = function (s, lt, d, T) {
    heading(s, lt);
    var items = s.items || [], n = items.length, gap = 40, tw0 = Math.min(480, (1680 - gap * (n - 1)) / n);
    var x = 960 - (tw0 * n + gap * (n - 1)) / 2, y = s.heading ? 380 : 320;
    items.forEach(function (it, i) {
      var a = 500 + i * 350, k = P(lt, a, a + 600, back), c = P(lt, a + 200, a + 1800);
      if (k <= 0) return;
      ctx.save(); ctx.translate(x + i * (tw0 + gap) + tw0 / 2, y + 190); ctx.scale(k, k);
      panel(-tw0 / 2, -190, tw0, 380, {}); ctx.fillStyle = accentAt(i); ctx.fillRect(-tw0 / 2, -190, tw0, 8);
      var val = fmtNum(it.value, c < 1 ? c : 1);
      txt(val, 0, 10, { size: Math.min(110, tw0 / Math.max(3, String(it.value).length) * 1.6), weight: 800, align: "center", color: accentAt(i), font: F.display });
      wrap(it.label || "", tw0 - 60, { size: 30, weight: 700 }).forEach(function (ln, j) { txt(ln, 0, 90 + j * 38, { size: 30, weight: 700, align: "center", color: C.muted }); });
      ctx.restore();
    });
  };

  R.bars = function (s, lt, d, T) {
    heading(s, lt);
    var items = s.items || [], n = items.length, max = s.max || Math.max.apply(null, items.map(function (i) { return +i.value; })) || 1;
    var y0 = s.heading ? 320 : 240, bh = Math.min(76, (900 - y0) / n - 26), lw = 0;
    items.forEach(function (it) { lw = Math.max(lw, tw(it.label, { size: 32, weight: 700 })); });
    var x0 = 140 + lw + 30, bw = 1720 - x0 - 200;
    items.forEach(function (it, i) {
      var y = y0 + i * (bh + 26), a = 500 + i * Math.min(400, d * .06), k = P(lt, a, a + 1100, eio);
      txt(it.label, x0 - 24, y + bh / 2 + 11, { size: 32, weight: 700, align: "right", alpha: P(lt, a - 200, a + 200) });
      var w = bw * (+it.value) / max * k, hl = s.highlight === i;
      ctx.save(); rr(x0, y, Math.max(2, w), bh, 10); ctx.fillStyle = accentAt(i); if (hl) { ctx.shadowColor = accentAt(i); ctx.shadowBlur = 24 * (.5 + .5 * Math.sin(lt / 300)); } ctx.fill(); ctx.restore();
      var disp = it.display || (String(it.value) + (s.unit || ""));
      txt(fmtNum(disp, k), x0 + w + 18, y + bh / 2 + 12, { size: 32, weight: 800, color: C.ink, alpha: k, font: F.display });
    });
  };

  R.compare = function (s, lt, d, T) {
    heading(s, lt);
    var cols = [s.left || {}, s.right || {}], y = s.heading ? 290 : 200, h = 1000 - y - 60, w = 760;
    var pts = cols.map(function (c) { return c.points || []; }), maxN = Math.max(pts[0].length, pts[1].length);
    var at = slots(maxN * 2, d, 1200, 900);
    cols.forEach(function (c, ci) {
      var x = ci === 0 ? 150 : 1010, k = P(lt, 200 + ci * 300, 900 + ci * 300);
      ctx.save(); ctx.globalAlpha *= k; ctx.translate((1 - k) * (ci === 0 ? -80 : 80), 0);
      var col = c.tone === "bad" ? C.warn : c.tone === "good" ? C.ok : accentAt(ci);
      panel(x, y, w, h, { stroke: col, lw: 2.5 });
      ctx.fillStyle = col; ctx.globalAlpha *= .14; rr(x, y, w, 96, 16); ctx.fill(); ctx.globalAlpha /= .14;
      txt(c.title || "", x + w / 2, y + 62, { size: 42, weight: 800, align: "center", color: col });
      pts[ci].forEach(function (p, i) {
        var a = at[i * 2 + ci], pk = P(lt, a, a + 500); if (pk <= 0) return;
        var lines = wrap(p, w - 120, { size: 34 });
        lines.forEach(function (ln, j) { rich(ln, x + 90, y + 170 + i * 110 + j * 44, { size: 34, alpha: pk }); });
        ctx.save(); ctx.globalAlpha *= pk; ctx.fillStyle = col;
        if (c.tone === "bad") txt("!", x + 52, y + 172 + i * 110, { size: 34, weight: 800, color: col, align: "center" });
        else if (c.tone === "good") txt("✓", x + 52, y + 172 + i * 110, { size: 32, weight: 800, color: col, align: "center" });
        else { ctx.beginPath(); ctx.arc(x + 52, y + 160 + i * 110, 8, 0, Math.PI * 2); ctx.fill(); }
        ctx.restore();
      });
      ctx.restore();
    });
    var vk = P(lt, 900, 1400, back);
    if (s.vs !== false && vk > 0) { ctx.save(); ctx.translate(960, y + h / 2); ctx.scale(vk, vk);
      ctx.fillStyle = C.bg1; ctx.beginPath(); ctx.arc(0, 0, 44, 0, Math.PI * 2); ctx.fill(); ctx.strokeStyle = C.edge; ctx.lineWidth = 2; ctx.stroke();
      txt(s.vs || "VS", 0, 12, { size: 30, weight: 800, align: "center", color: C.muted }); ctx.restore(); }
  };

  R.statement = function (s, lt, d, T) {
    var lines = []; (s.lines || [s.text || ""]).forEach(function (l) { wrap(l, 1500, { size: s.size || 76, weight: 800, font: F.display }).forEach(function (w) { lines.push(w); }); });
    var n = lines.length, size = s.size || 76, lh = size * 1.35, y0 = 540 - (n - 1) * lh / 2 + size * .35;
    var at = slots(n, d * .55, 300, 0);
    lines.forEach(function (ln, i) {
      var k = P(lt, at[i], at[i] + 700);
      rich(ln, 960, y0 + i * lh + (1 - k) * 24, { size: size, weight: 800, align: "center", font: F.display, alpha: k }, P(lt, at[i] + 500, at[i] + 1200));
    });
    if (s.note) txt(s.note, 960, y0 + n * lh + 30, { size: 30, align: "center", color: C.muted, alpha: P(lt, d * .5, d * .5 + 800) });
  };

  var KW = /\b(const|let|var|function|return|if|else|for|while|import|from|export|class|new|await|async|def|self|None|True|False|in|of|type|interface|public|private|static|void|int|string|bool|true|false|null|undefined)\b/g;
  function codeLine(src, x, y, size) {
    var parts = [], re = /(\/\/.*$|#.*$|"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|`[^`]*`)/g, last = 0, m;
    while ((m = re.exec(src))) { if (m.index > last) parts.push([src.slice(last, m.index), 0]); parts.push([m[0], /^(\/\/|#)/.test(m[0]) ? 2 : 1]); last = m.index + m[0].length; }
    if (last < src.length) parts.push([src.slice(last), 0]);
    var cx = x;
    parts.forEach(function (p) {
      if (p[1] === 0) {
        var seg = p[0], lastI = 0, mm; KW.lastIndex = 0;
        while ((mm = KW.exec(seg))) { var a = seg.slice(lastI, mm.index); txt(a, cx, y, { size: size, font: F.mono, color: C.codeInk }); cx += tw(a, { size: size, font: F.mono });
          txt(mm[0], cx, y, { size: size, font: F.mono, color: C.accent2, weight: 700 }); cx += tw(mm[0], { size: size, font: F.mono, weight: 700 }); lastI = mm.index + mm[0].length; }
        var rest = seg.slice(lastI); txt(rest, cx, y, { size: size, font: F.mono, color: C.codeInk }); cx += tw(rest, { size: size, font: F.mono });
      } else { var col = p[1] === 2 ? C.codeMuted : C.ok; txt(p[0], cx, y, { size: size, font: F.mono, color: col }); cx += tw(p[0], { size: size, font: F.mono }); }
    });
  }
  R.code = function (s, lt, d, T) {
    heading(s, lt);
    var lines = String(s.code || "").split("\n"), hl = s.highlight || [], y = s.heading ? 280 : 180, size = lines.length > 16 ? 24 : 28, lh = size * 1.6;
    var h = Math.min(1000 - y, lines.length * lh + 80), x = 160, w = 1600;
    var k = P(lt, 0, 600); ctx.save(); ctx.globalAlpha *= k;
    panel(x, y, w, h, { fill: C.code });
    var at = slots(hl.length, d, 900, 600), cur = -1; at.forEach(function (a, i) { if (lt >= a) cur = i; });
    lines.forEach(function (ln, i) {
      var yy = y + 60 + i * lh; if (yy > y + h - 10) return;
      var on = cur >= 0 && hl[cur] && i + 1 >= hl[cur].lines[0] && i + 1 <= hl[cur].lines[hl[cur].lines.length - 1];
      if (on) { ctx.save(); ctx.fillStyle = C.accent; ctx.globalAlpha = .16 * P(lt, at[cur], at[cur] + 400); ctx.fillRect(x + 8, yy - size * 1.05, w - 16, lh); ctx.restore(); }
      ctx.save(); ctx.globalAlpha *= cur >= 0 && !on ? .45 : 1;
      txt(String(i + 1), x + 60, yy, { size: size * .8, font: F.mono, color: C.codeMuted, align: "right" });
      codeLine(ln, x + 90, yy, size); ctx.restore();
    });
    if (cur >= 0 && hl[cur].note) {
      var nk = P(lt, at[cur] + 200, at[cur] + 700), nl = wrap(hl[cur].note, 520, { size: 28, weight: 700 }), nh = nl.length * 40 + 36;
      var ny = Math.min(y + 60 + (hl[cur].lines[0] - 1) * lh - size, 1000 - nh);
      ctx.save(); ctx.globalAlpha *= nk; panel(1780 - 560, ny, 560, nh, { stroke: C.accent, lw: 2 });
      nl.forEach(function (l, j) { txt(l, 1780 - 530, ny + 48 + j * 40, { size: 28, weight: 700 }); }); ctx.restore();
    }
    ctx.restore();
  };

  R.window = function (s, lt, d, T) {
    heading(s, lt);
    var x = 150, y = s.heading ? 270 : 170, w = 1620, h = 1000 - y - 30, side = s.sidebar ? 300 : 0;
    var k = P(lt, 0, 700); ctx.save(); ctx.globalAlpha *= k; ctx.translate(0, (1 - k) * 30);
    panel(x, y, w, h, { r: 18 }); ctx.save(); rr(x, y, w, h, 18); ctx.clip();
    ctx.fillStyle = C.bg1; ctx.fillRect(x, y, w, 46);
    for (var i = 0; i < 3; i++) { ctx.fillStyle = C.edge; ctx.beginPath(); ctx.arc(x + 26 + i * 22, y + 23, 6.5, 0, Math.PI * 2); ctx.fill(); }
    txt(s.title || "", x + w / 2, y + 31, { size: 20, color: C.muted, align: "center" });
    if (side) {
      ctx.fillStyle = C.bg1; ctx.fillRect(x, y + 46, side, h - 46);
      var yy = y + 100;
      (s.sidebar || []).forEach(function (it, i) {
        var label = typeof it === "string" ? it : it.label, on = it.active;
        if (on) { rr(x + 12, yy - 28, side - 24, 40, 8); ctx.fillStyle = C.panel2; ctx.fill(); }
        if (it.state) stateMark(x + 36, yy - 8, stateOf(it, lt, d), lt, 8);
        txt(label, x + (it.state ? 58 : 28), yy, { size: 22, weight: on ? 700 : 400, color: on ? C.ink : C.muted });
        yy += 44;
      });
    }
    var panes = s.panes || [], n = panes.length, gx = x + side + 12, gy = y + 58, gw = w - side - 24, gh = h - 70;
    var cols = n <= 1 ? 1 : 2, rows = Math.ceil(n / cols);
    panes.forEach(function (p, i) {
      var a = 300 + i * Math.min(900, d * .1), pk = P(lt, a, a + 600);
      if (pk <= 0) return;
      var c = i % cols, r = Math.floor(i / cols), pw = (gw - 10 * (cols - 1)) / cols, ph = (gh - 10 * (rows - 1)) / rows;
      if (n === 3 && i === 2) { pw = gw; }
      var px = gx + c * (pw + 10), py = gy + r * (ph + 10);
      ctx.save(); ctx.globalAlpha *= pk;
      rr(px, py, pw, ph, 10); ctx.fillStyle = C.code; ctx.fill(); ctx.strokeStyle = C.edge; ctx.lineWidth = 1.2; ctx.stroke();
      ctx.fillStyle = C.panel2; ctx.fillRect(px + 1, py + 1, pw - 2, 40);
      var st = stateOf(p, lt, d);
      stateMark(px + 24, py + 21, st, lt, 8);
      txt(p.title || "", px + 44, py + 29, { size: 21, weight: 700 });
      if (p.tag) { var tw1 = tw(p.tag, { size: 16, font: F.mono, weight: 600 }) + 18; rr(px + pw - tw1 - 12, py + 9, tw1, 24, 6); ctx.fillStyle = C.panel; ctx.fill();
        txt(p.tag, px + pw - 12 - tw1 / 2, py + 27, { size: 16, font: F.mono, weight: 600, color: C.accent2, align: "center" }); }
      var ls = p.lines || [], shown = ls.length * P(lt, a + 300, a + 300 + Math.max(1500, d * .5), function (q) { return q; });
      var maxL = Math.floor((ph - 60) / 30);
      ls.slice(0, Math.ceil(shown)).slice(-maxL).forEach(function (ln, j, arr) {
        var last = j === arr.length - 1 && shown < ls.length, frac = shown - Math.floor(shown);
        var col = /^[›$>]/.test(ln) ? C.codeInk : /✓/.test(ln) ? C.ok : /[✗?!]/.test(ln) ? C.warn : C.codeMuted;
        txt(last ? ln.slice(0, Math.floor(ln.length * frac)) : ln, px + 18, py + 74 + j * 30, { size: 19, font: F.mono, color: col });
      });
      ctx.restore();
    });
    (s.toasts || []).forEach(function (t0, i) {
      var a = (t0.at || .5) * d, tk = P(lt, a, a + 450, back) * (1 - P(lt, a + (t0.hold || 3200), a + (t0.hold || 3200) + 400));
      if (tk <= 0) return;
      var tw0 = 480, th = 96, tx = x + w - tw0 - 24 + (1 - tk) * 80, ty = y + 66 + i * 108;
      ctx.save(); ctx.globalAlpha *= tk; panel(tx, ty, tw0, th, { stroke: t0.kind === "blocked" ? C.warn : C.ok, lw: 2 });
      stateMark(tx + 38, ty + 36, t0.kind || "done", lt, 11);
      txt(t0.title || "", tx + 64, ty + 44, { size: 23, weight: 700 });
      if (t0.sub) txt(t0.sub, tx + 64, ty + 74, { size: 17, font: F.mono, color: C.muted });
      ctx.restore();
    });
    ctx.restore(); ctx.restore();
  };
  function stateOf(p, lt, d) {
    var st = p.state || "none";
    (p.states || []).forEach(function (c) { if (lt >= (c.at || 0) * d) st = c.state; });
    return st;
  }

  R.image = function (s, lt, d, T) {
    heading(s, lt);
    var img = IMGS[s.src]; if (!img || !img.complete || !img.naturalWidth) { txt("（画像）", 960, 560, { size: 30, color: C.muted, align: "center" }); return; }
    var y = s.heading ? 270 : 110, bh = (s.caption ? 880 : 940) - y, bw = 1680, iw = img.naturalWidth, ih = img.naturalHeight;
    var sc = Math.min(bw / iw, bh / ih), dw = iw * sc, dh = ih * sc, dx = 960 - dw / 2, dy = y + (bh - dh) / 2;
    var z = s.kenburns === false ? 1 : mix(1, 1.08, lt / d), k = P(lt, 0, 700);
    ctx.save(); ctx.globalAlpha *= k; rr(dx, dy, dw, dh, 14); ctx.clip();
    var zw = dw * z, zh = dh * z; ctx.drawImage(img, dx - (zw - dw) * (s.pan === "left" ? 1 : .5), dy - (zh - dh) * .5, zw, zh); ctx.restore();
    if (s.caption) txt(s.caption, 960, 960, { size: 30, color: C.muted, align: "center", alpha: P(lt, 600, 1200) });
  };

  R.end = function (s, lt, d, T) {
    emblem(s.mark || "ring", 960, 290, 110 * P(lt, 0, 1000, back), lt * .00018, 1, s.title);
    var rows = s.lines || [], y = 470;
    rows.forEach(function (r, i) {
      var k = P(lt, 700 + i * 700, 1300 + i * 700); if (k <= 0) return;
      var text = typeof r === "string" ? r : r.text, note = r.note, mono = r.mono !== false && /^[$>]/.test(text);
      ctx.save(); ctx.globalAlpha *= k;
      var w = Math.max(900, tw(text, { size: 32, font: mono ? F.mono : F.sans, weight: 600 }) + (note ? tw(note, { size: 24 }) + 80 : 60));
      panel(960 - w / 2, y + i * 96 - 50, w, 74, { shadow: false, fill: C.panel });
      txt(text, 960 - w / 2 + 30, y + i * 96, { size: 32, font: mono ? F.mono : F.sans, weight: 600, color: mono ? C.accent2 : C.ink });
      if (note) txt(note, 960 + w / 2 - 30, y + i * 96 - 2, { size: 24, color: C.muted, align: "right" });
      ctx.restore();
    });
    var fk = P(lt, 700 + rows.length * 700 + 400, 700 + rows.length * 700 + 1400, eio);
    /* 字幕（画面の下 1 割）と重ならないよう、下端は 900 までに収める */
    txt(s.title || "", 960, 820, { size: 70, weight: 800, align: "center", font: F.display, alpha: fk });
    if (s.tagline) rich(s.tagline, 960, 884, { size: 32, align: "center", color: C.accent, alpha: P(lt, 700 + rows.length * 700 + 900, 700 + rows.length * 700 + 1900) });
  };

  var CUSTOM = new WeakMap();
  R.custom = function (s, lt, d, T) {
    var fn = CUSTOM.get(s);
    if (!fn) { try { fn = new Function("ctx", "lt", "d", "H", "s", s.code); } catch (e) { fn = function () {}; console.error("custom scene:", e); } CUSTOM.set(s, fn); }
    heading(s, lt);
    ctx.save(); try { fn(ctx, lt, d, HELP, s); } catch (e) { if (!s._err) { s._err = 1; console.error("custom scene:", e); } } ctx.restore();
  };
  var HELP = { C: C, F: F, W: W, H: H, clamp: clamp, lin: lin, eo: eo, eio: eio, back: back, P: P, mix: mix, rr: rr, txt: txt, tw: tw, wrap: wrap,
               rich: rich, icon: icon, panel: panel, stateMark: stateMark, emblem: emblem, accentAt: accentAt, slots: slots };

  /* ================= 背景と 1 コマ ================= */
  function scaleCtx() { ctx.setTransform(cv.width / W, 0, 0, cv.height / H, 0, 0); }
  function backdrop(t) {
    var g = ctx.createLinearGradient(0, 0, 0, H); g.addColorStop(0, C.bg1); g.addColorStop(1, C.bg0);
    ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
    var pat = TH.pattern, drift = (t / 90) % 120;
    ctx.save();
    if (pat === "grid") { ctx.strokeStyle = C.grid; ctx.lineWidth = 1;
      for (var x = -120 + drift; x < W + 120; x += 120) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke(); }
      for (var y = 60; y < H; y += 120) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke(); } }
    else if (pat === "dots") { ctx.fillStyle = C.grid;
      for (var x2 = (drift / 2) % 48; x2 < W; x2 += 48) for (var y2 = 24; y2 < H; y2 += 48) ctx.fillRect(x2, y2, 3, 3); }
    else if (pat === "glow") { var rg = ctx.createRadialGradient(W * .75, H * .2, 50, W * .75, H * .2, 900);
      rg.addColorStop(0, C.grid); rg.addColorStop(1, "rgba(0,0,0,0)"); ctx.fillStyle = rg; ctx.fillRect(0, 0, W, H); }
    ctx.restore();
  }
  function chrome(t) {
    var i = chapterAt(t), lt = t - CHAPTERS[i].t, len = chLen(i);
    var a = P(lt, 200, 700) * (i < CHAPTERS.length - 1 ? 1 - P(lt, len - 500, len) : 1);
    if (SPEC.chrome === false) return;
    var n = CHAPTERS.length;
    txt(String(i + 1).padStart(2, "0") + " / " + String(n).padStart(2, "0"), 64, 72, { size: 22, font: F.mono, color: C.accent, alpha: a, spacing: 2 });
    txt(CHAPTERS[i].name, 64 + tw("00 / 00", { size: 22, font: F.mono }) + 34, 72, { size: 26, weight: 700, alpha: a });
    if (SPEC.brand && SPEC.brand.name) txt(SPEC.brand.name, W - 64, 72, { size: 22, weight: 700, color: C.muted, align: "right", alpha: .8 });
  }
  var FADE = 450;
  function drawScene(k, t) {
    var sc = SCENES[k], lt = t - sc.t0, d = sc.d, tr = sc.s.transition || SPEC.transition || "fade";
    var first = k === 0, last = k === SCENES.length - 1;
    var inK = first ? 1 : P(lt, 0, FADE), outK = last ? 1 : 1 - P(lt, d - FADE, d, eio);
    if (tr === "cut") { inK = 1; outK = 1; }
    ctx.save(); ctx.globalAlpha = Math.min(inK, outK);
    if (tr === "slide") ctx.translate((1 - inK) * 80 - (1 - outK) * 80, 0);
    if (tr === "zoom") { var z = mix(.96, 1, inK) * mix(1.04, 1, outK); ctx.translate(960, 540); ctx.scale(z, z); ctx.translate(-960, -540); }
    (R[sc.s.type] || R.statement)(sc.s, Math.max(0, lt), d, t);
    ctx.restore();
  }
  function draw(t) {
    scaleCtx(); backdrop(t);
    var k = sceneAt(t);
    if (k > 0 && t - SCENES[k].t0 < FADE && (SCENES[k].s.transition || SPEC.transition || "fade") !== "cut") drawScene(k - 1, t);
    drawScene(k, t);
    chrome(t);
  }

  /* ================= 音声（読み上げ・音楽・効果音） ================= */
  var AUD = SPEC.audio || {};
  var ac = null, master = null, pad = null;
  function ensureAudio() { if (ac) return; try { ac = new (window.AudioContext || window.webkitAudioContext)(); master = ac.createGain(); master.gain.value = audioOn ? 1 : 0; master.connect(ac.destination); } catch (e) { ac = null; } }
  var MUSIC = { calm: [73.42, 110, 146.83, 164.81, 220], bright: [98, 146.83, 196, 246.94, 293.66], deep: [55, 82.41, 110, 130.81, 164.81] };
  function startPad() {
    var chord = MUSIC[AUD.music]; if (!ac || pad || !chord) return;
    var g = ac.createGain(); g.gain.value = 0; g.connect(master);
    var lp = ac.createBiquadFilter(); lp.type = "lowpass"; lp.frequency.value = AUD.music === "bright" ? 1400 : 700; lp.connect(g);
    var oscs = chord.map(function (f, i) { var o = ac.createOscillator(); o.type = i % 2 ? "triangle" : "sine"; o.frequency.value = f; o.detune.value = (i - 2) * 4;
      var og = ac.createGain(); og.gain.value = .5 / chord.length; o.connect(og); og.connect(lp); o.start(); return o; });
    var lfo = ac.createOscillator(); lfo.frequency.value = .07; var lg = ac.createGain(); lg.gain.value = 260; lfo.connect(lg); lg.connect(lp.frequency); lfo.start();
    g.gain.linearRampToValueAtTime(AUD.musicVolume || .07, ac.currentTime + 1.5);
    pad = { g: g, oscs: oscs.concat([lfo]) };
  }
  function stopPad() { if (!pad || !ac) return; var p = pad; pad = null; p.g.gain.cancelScheduledValues(ac.currentTime);
    p.g.gain.setValueAtTime(p.g.gain.value, ac.currentTime); p.g.gain.linearRampToValueAtTime(0, ac.currentTime + .4);
    setTimeout(function () { p.oscs.forEach(function (o) { try { o.stop(); } catch (e) {} }); }, 500); }
  function bell(freq, vol, len) {
    if (!ac || !audioOn || AUD.sfx === false) return; var now = ac.currentTime;
    [1, 2.01, 3.02].forEach(function (m, i) { var o = ac.createOscillator(); o.type = "sine"; o.frequency.value = freq * m;
      var g = ac.createGain(); g.gain.setValueAtTime(0, now); g.gain.linearRampToValueAtTime(vol / (i + 1), now + .01); g.gain.exponentialRampToValueAtTime(.0001, now + len / (i + 1));
      o.connect(g); g.connect(master); o.start(now); o.stop(now + len); });
  }
  var synth = "speechSynthesis" in window ? window.speechSynthesis : null, voice = null, LANG = SPEC.lang || "ja";
  function pickVoice() {
    if (!synth) return; var vs = synth.getVoices(), re = new RegExp("^" + LANG, "i");
    voice = vs.filter(function (v) { return re.test(v.lang) && /Kyoko|Nanami|Otoya|Google|Samantha|Aria|Natural/i.test(v.name); })[0] || vs.filter(function (v) { return re.test(v.lang); })[0] || null;
    var note = $("mv-voicenote"); if (note) note.hidden = !(started && audioOn && AUD.narration !== false && vs.length && !voice);
  }
  if (synth) { pickVoice(); synth.onvoiceschanged = pickVoice; }
  function say(text) {
    if (!synth || !audioOn || !voice || AUD.narration === false) return;
    try { synth.cancel(); var s = text.replace(/\*\*/g, "");
      Object.keys(AUD.pronounce || {}).forEach(function (k) { s = s.split(k).join(AUD.pronounce[k]); });
      var u = new SpeechSynthesisUtterance(s); u.voice = voice; u.lang = voice.lang; u.rate = Math.min(2.4, (AUD.rate || 1.1) * speed); synth.speak(u); } catch (e) {}
  }
  function hush() { try { if (synth) synth.cancel(); } catch (e) {} }
  function crossed(a, b, x) { return a < x && b >= x; }
  function onAdvance(a, b) {
    if (!audioOn) return;
    CUES.forEach(function (c) { if (crossed(a, b, c.a)) say(c.text); });
    CHAPTERS.forEach(function (c, i) { if (crossed(a, b, c.t + 120)) bell(i === 0 ? 523.25 : 587.33, .09, 2.2); });
  }

  /* ================= プレイヤー ================= */
  var store = { get: function (k, d) { try { var v = localStorage.getItem("mv:" + k); return v === null ? d : v; } catch (e) { return d; } },
                set: function (k, v) { try { localStorage.setItem("mv:" + k, v); } catch (e) {} } };
  var root = $("mv-player"), KIOSK = root.getAttribute("data-player") === "kiosk";
  var t = 0, playing = false, started = false, needsDraw = true, lastNow = 0, dragging = false;
  var speed = parseFloat(store.get("speed", "1")) || 1;
  var captions = store.get("cc", "1") === "1";
  var audioOn = KIOSK ? false : store.get("audio", AUD.default === "off" ? "0" : "1") === "1";
  var SPEEDS = [0.5, 0.75, 1, 1.25, 1.5, 2];
  var fmt = function (ms) { var s = Math.floor(ms / 1000); return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0"); };

  function resize() { var r = cv.getBoundingClientRect(), dpr = Math.min(window.devicePixelRatio || 1, 2);
    var w = Math.max(1, Math.round(r.width * dpr)), h = Math.max(1, Math.round(r.height * dpr));
    if (cv.width !== w || cv.height !== h) { cv.width = w; cv.height = h; } needsDraw = true; }

  function play() {
    if (t >= DUR) t = 0;
    ensureAudio(); if (ac && ac.state === "suspended") ac.resume().catch(function () {});
    if (audioOn) startPad();
    playing = true; started = true; lastNow = performance.now();
    var c = CUES.filter(function (c) { return t >= c.a && t < c.b; })[0];
    if (c && audioOn && (t - c.a) < (c.b - c.a) * .35) say(c.text);
    pickVoice(); syncUI(); poke();
  }
  function pause() { playing = false; hush(); stopPad(); syncUI(); poke(); }
  function stop() { playing = false; hush(); stopPad(); t = 0; started = false; needsDraw = true; syncUI(); poke(); }
  function toggle() { playing ? pause() : play(); }
  function seek(ms) { t = clamp(ms, 0, DUR); hush(); needsDraw = true; started = true; if (t >= DUR) { playing = false; stopPad(); } syncUI(); }
  function chapterStep(dir) { var i = chapterAt(t), n = i + dir; if (dir < 0 && t - CHAPTERS[i].t > 2000) n = i;
    n = clamp(n, 0, CHAPTERS.length - 1); seek(CHAPTERS[n].t); bell(587.33, .07, 1.2); }
  function setSpeed(v) { speed = v; var sel = $("mv-speed"); if (sel) sel.value = String(v); store.set("speed", String(v)); if (playing) hush(); }
  function setCaptions(on) { captions = on; store.set("cc", on ? "1" : "0"); var b = $("mv-cc"); if (b) b.setAttribute("aria-pressed", String(on)); syncCaption(true); }
  function setAudio(on) { audioOn = on; store.set("audio", on ? "1" : "0"); var b = $("mv-audio");
    if (b) { b.setAttribute("aria-pressed", String(on)); b.setAttribute("aria-label", on ? "音声をオフにする" : "音声をオンにする"); }
    if (ac && master) master.gain.setTargetAtTime(on ? 1 : 0, ac.currentTime, .05);
    if (!on) { hush(); stopPad(); } else if (playing) { ensureAudio(); startPad(); } pickVoice(); }

  /* シークバー（チャプターごとの区切り） */
  var seekEl = $("mv-seek"), track = $("mv-track");
  CHAPTERS.forEach(function (c, i) { var seg = document.createElement("div"); seg.className = "mv-seg"; seg.style.flex = String(chLen(i)); seg.appendChild(document.createElement("i")); track.appendChild(seg); });
  var segs = [].slice.call(track.children);
  function posToMs(x) { var r = seekEl.getBoundingClientRect(); return clamp((x - r.left) / r.width) * DUR; }
  function showTip(x) { var r = seekEl.getBoundingClientRect(), ms = posToMs(x), tip = $("mv-tip"); tip.hidden = false;
    tip.innerHTML = "<b>" + fmt(ms) + "</b>" + esc(CHAPTERS[chapterAt(ms)].name);
    var half = tip.offsetWidth / 2; tip.style.left = clamp(x - r.left, half, r.width - half) + "px"; }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  seekEl.addEventListener("pointerdown", function (e) { dragging = true; seekEl.classList.add("drag"); seekEl.setPointerCapture(e.pointerId); seek(posToMs(e.clientX)); showTip(e.clientX); });
  seekEl.addEventListener("pointermove", function (e) { showTip(e.clientX); if (dragging) seek(posToMs(e.clientX)); });
  var endDrag = function () { dragging = false; seekEl.classList.remove("drag"); };
  seekEl.addEventListener("pointerup", endDrag); seekEl.addEventListener("pointercancel", endDrag);
  seekEl.addEventListener("pointerleave", function () { if (!dragging) $("mv-tip").hidden = true; });
  seekEl.addEventListener("keydown", function (e) {
    var m = { ArrowLeft: -5000, ArrowDown: -5000, ArrowRight: 5000, ArrowUp: 5000 }[e.key];
    if (m) seek(t + m); else if (e.key === "Home") seek(0); else if (e.key === "End") seek(DUR);
    else if (e.key === "PageUp") chapterStep(-1); else if (e.key === "PageDown") chapterStep(1); else return;
    e.preventDefault(); e.stopPropagation(); });

  /* チャプターの一覧（メニューと、テンプレートによっては横・下の一覧） */
  var menu = $("mv-chapmenu"), list = $("mv-chaplist");
  CHAPTERS.forEach(function (c, i) {
    var num = String(i + 1).padStart(2, "0");
    if (menu) { var b = document.createElement("button"); b.type = "button"; b.dataset.i = i;
      b.innerHTML = '<span class="n">' + num + "</span><span>" + esc(c.name) + '</span><span class="t">' + fmt(c.t) + "</span>";
      b.addEventListener("click", function () { seek(c.t); closeMenu(true); if (!playing) play(); }); menu.appendChild(b); }
    if (list) { var li = document.createElement("li"), b2 = document.createElement("button"); b2.type = "button"; b2.dataset.i = i;
      b2.innerHTML = '<span class="n">' + num + '</span><span class="nm">' + esc(c.name) + (c.desc ? '<span class="d">' + esc(c.desc) + "</span>" : "") + '</span><span class="t">' + fmt(c.t) + "</span>";
      b2.addEventListener("click", function () { seek(c.t); if (!playing) play(); }); li.appendChild(b2); list.appendChild(li); }
  });
  function openMenu() { menu.hidden = false; $("mv-chapbtn").setAttribute("aria-expanded", "true"); (menu.querySelector('[aria-current="true"]') || menu.firstChild).focus(); }
  function closeMenu(refocus) { if (!menu || menu.hidden) return; menu.hidden = true; $("mv-chapbtn").setAttribute("aria-expanded", "false"); if (refocus) $("mv-chapbtn").focus(); }
  if (menu) {
    $("mv-chapbtn").addEventListener("click", function () { menu.hidden ? openMenu() : closeMenu(false); });
    menu.addEventListener("keydown", function (e) { var it = [].slice.call(menu.children), i = it.indexOf(document.activeElement);
      if (e.key === "ArrowDown") { it[(i + 1) % it.length].focus(); e.preventDefault(); }
      else if (e.key === "ArrowUp") { it[(i - 1 + it.length) % it.length].focus(); e.preventDefault(); }
      else if (e.key === "Escape") { closeMenu(true); e.preventDefault(); } e.stopPropagation(); });
  }
  /* minimal の「⋯」メニュー（速度・字幕・音声・チャプターをまとめる） */
  var more = $("mv-more"), morePanel = $("mv-morepanel");
  if (more && morePanel && root.getAttribute("data-player") === "minimal") {
    more.addEventListener("click", function () { var open = morePanel.hidden; morePanel.hidden = !open; more.setAttribute("aria-expanded", String(open)); });
    morePanel.addEventListener("keydown", function (e) { if (e.key === "Escape") { morePanel.hidden = true; more.setAttribute("aria-expanded", "false"); more.focus(); } });
  }
  document.addEventListener("pointerdown", function (e) {
    if (menu && !menu.hidden && !e.target.closest(".mv-menuwrap")) closeMenu(false);
    if (morePanel && root.getAttribute("data-player") === "minimal" && !morePanel.hidden && !e.target.closest(".mv-morewrap")) { morePanel.hidden = true; more.setAttribute("aria-expanded", "false"); }
  });

  /* ボタン */
  function on(id, ev, fn) { var el = $(id); if (el) el.addEventListener(ev, fn); }
  on("mv-play", "click", toggle);
  /* 中央のボタンは再生で隠れるので、キー操作が効くようにプレイヤーへフォーカスを移す */
  function focusPlayer() { try { root.focus({ preventScroll: true }); } catch (e) { root.focus(); } }
  on("mv-big", "click", function (e) { e.stopPropagation(); play(); focusPlayer(); });
  on("mv-stage", "click", function () { if (KIOSK && !started) play(); else toggle(); focusPlayer(); });
  on("mv-stop", "click", stop);
  on("mv-prev", "click", function () { chapterStep(-1); });
  on("mv-next", "click", function () { chapterStep(1); });
  on("mv-speed", "change", function (e) { setSpeed(parseFloat(e.target.value)); });
  on("mv-cc", "click", function () { setCaptions(!captions); });
  on("mv-audio", "click", function () { setAudio(!audioOn); });
  on("mv-fs", "click", function () { try { if (document.fullscreenElement) document.exitFullscreen().catch(function () {}); else if (root.requestFullscreen) root.requestFullscreen().catch(function () {}); } catch (e) {} });
  document.addEventListener("fullscreenchange", function () { setTimeout(resize, 50); });
  root.addEventListener("keydown", function (e) {
    if (e.target.tagName === "SELECT" || e.altKey || e.ctrlKey || e.metaKey) return;
    var k = e.key, done = true;
    if (k === " " || k === "k" || k === "K") { if (e.target.tagName === "BUTTON" && k === " ") done = false; else toggle(); }
    else if (k === "s" || k === "S") stop();
    else if (k === "ArrowLeft") seek(t - 5000); else if (k === "ArrowRight") seek(t + 5000);
    else if (k === "[") chapterStep(-1); else if (k === "]") chapterStep(1);
    else if (k === "c" || k === "C") setCaptions(!captions); else if (k === "m" || k === "M") setAudio(!audioOn);
    else if (k === "f" || k === "F") $("mv-fs").click();
    else if (k === "<" || k === ",") setSpeed(SPEEDS[Math.max(0, SPEEDS.indexOf(speed) - 1)] || 1);
    else if (k === ">" || k === ".") setSpeed(SPEEDS[Math.min(SPEEDS.length - 1, SPEEDS.indexOf(speed) + 1)] || 1);
    else done = false;
    if (done) { e.preventDefault(); poke(); }
  });

  /* 操作部の自動で隠れる動き（cinema・minimal・kiosk） */
  var hideTimer = 0;
  function poke() { root.classList.add("mv-awake"); clearTimeout(hideTimer);
    hideTimer = setTimeout(function () {
      var a = document.activeElement, inControls = a && a.closest && a.closest(".mv-controls");
      if (playing && !dragging && !inControls) root.classList.remove("mv-awake");
    }, 2600); }
  root.addEventListener("pointermove", poke); root.addEventListener("focusin", poke);

  var lastCap = null, lastChap = -1;
  function syncCaption(force) {
    var c = CUES.filter(function (c) { return t >= c.a && t < c.b; })[0], text = captions && started && c ? c.text.replace(/\*\*/g, "") : "";
    if (text !== lastCap || force) { lastCap = text; var el = $("mv-captext"); el.textContent = text; el.hidden = !text; }
  }
  function syncUI() {
    var pb = $("mv-play"); pb.setAttribute("aria-label", playing ? "一時停止" : "再生");
    pb.querySelector(".i-play").hidden = playing; pb.querySelector(".i-pause").hidden = !playing;
    var big = $("mv-big"); if (big) { big.hidden = playing || (started && t > 0 && t < DUR); big.setAttribute("aria-label", t >= DUR ? "もう一度再生" : "再生"); }
    root.classList.toggle("mv-playing", playing);
    $("mv-time").innerHTML = "<b>" + fmt(t) + "</b> / " + fmt(DUR);
    var ci = chapterAt(t);
    if (ci !== lastChap) { lastChap = ci; var cn = $("mv-chapname"); if (cn) cn.textContent = CHAPTERS[ci].name;
      [].forEach.call(document.querySelectorAll("#mv-chapmenu button, #mv-chaplist button"), function (b) { b.setAttribute("aria-current", String(+b.dataset.i === ci)); });
      var cur = list && list.querySelector('[aria-current="true"]'); if (cur && root.getAttribute("data-player") === "presenter" && cur.scrollIntoView) cur.scrollIntoView({ block: "nearest" }); }
    segs.forEach(function (s, i) { s.firstChild.style.width = (clamp((t - CHAPTERS[i].t) / chLen(i)) * 100) + "%"; });
    $("mv-knob").style.left = (t / DUR * 100) + "%";
    seekEl.setAttribute("aria-valuemax", String(Math.round(DUR / 1000)));
    seekEl.setAttribute("aria-valuenow", String(Math.round(t / 1000)));
    seekEl.setAttribute("aria-valuetext", Math.floor(t / 60000) + " 分 " + (Math.floor(t / 1000) % 60) + " 秒、" + CHAPTERS[ci].name);
    syncCaption(false);
  }
  function frame(now) {
    if (playing) {
      var prev = t; t = Math.min(DUR, t + Math.min(100, now - lastNow) * speed); onAdvance(prev, t);
      if (t >= DUR) { if (KIOSK) { t = 0; hush(); } else { playing = false; stopPad(); } }
      syncUI(); needsDraw = true;
    }
    lastNow = now;
    if (needsDraw) { draw(started || t > 0 ? t : (SPEC.poster !== undefined ? SPEC.poster : Math.min(4300, DUR))); needsDraw = playing; }
    requestAnimationFrame(frame);
  }

  /* 起動 */
  var sel = $("mv-speed"); if (sel) sel.value = String(speed);
  var ccb = $("mv-cc"); if (ccb) ccb.setAttribute("aria-pressed", String(captions));
  var aub = $("mv-audio"); if (aub) { aub.setAttribute("aria-pressed", String(audioOn)); aub.setAttribute("aria-label", audioOn ? "音声をオフにする" : "音声をオンにする"); }
  SCENES.forEach(function (sc) { if (sc.s.type === "image" && sc.s.src && !IMGS[sc.s.src]) { var im = new Image(); im.onload = function () { needsDraw = true; }; im.src = sc.s.src; IMGS[sc.s.src] = im; } });
  new ResizeObserver(resize).observe(cv); resize(); syncUI(); requestAnimationFrame(frame);
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(function () { needsDraw = true; });
  if (KIOSK && !(window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches)) { started = true; playing = true; lastNow = performance.now(); syncUI(); }
  window.__MV__ = { seek: seek, play: play, pause: pause, get t() { return t; }, DUR: DUR, CHAPTERS: CHAPTERS, CUES: CUES };
})();
