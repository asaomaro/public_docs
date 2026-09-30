/* motion-video engine — 台本（SPEC）から、時刻だけで決まる映像を Canvas に描き、プレイヤーを動かす。
 * build.py が SPEC（durations 計算済み）・THEME・このファイルを 1 つの HTML に埋め込む。
 * 描画は draw(t) の純粋な関数（t = 動画の先頭からの ms）。シーク・倍速・巻き戻しでも同じ画になる。 */
window.MotionVideo = window.MotionVideo || function (root, SPEC, TH) {
  "use strict";
  var W = 1920, H = 1080;
  /* 要素はこのプレイヤーの中から data-mv で探す（1 ページに複数のプレイヤーを置けるように） */
  var $ = function (id) { return root.querySelector('[data-mv="' + id.replace(/^mv-/, "") + '"]'); };

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
      txt(p, cx, y, { size: o.size, weight: em ? Math.max(700, o.weight || 400) : o.weight, font: o.font, color: em ? (o.emColor || C.accent) : (o.color || C.ink), alpha: o.alpha });
      if (em && emK !== undefined) {
        ctx.save(); ctx.globalAlpha *= (o.alpha === undefined ? 1 : o.alpha); ctx.fillStyle = o.emColor || C.accent;
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
    sfxEv(250, "title"); if (s.subtitle) sfxEv(2000, "appear", { i: 0 });
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
      sfxEv(at[i], "appear", { i: i });
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
      sfxEv(st, "connect", { i: i }); if (e.travel !== undefined && e.travel !== false) { sfxEv(flowAt[i], "travel"); sfxEv(flowAt[i] + 1250, "arrive"); }
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
      sfxEv(nodeIn(id), "appear", { i: p.r });
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
      sfxEv(at[i], "step", { i: i });
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
      if (l.cmd) { var dd = l.cmd.length * rate; plan.push({ l: l, a: at, b: at + dd }); sfxEv(at, "type", { n: l.cmd.length, dur: dd }); sfxEv(at + dd + 60, "enter"); at += dd + 300; }
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
      sfxEv(a, "appear", { i: i }); if (parseNum(it.value)) { sfxEv(a + 200, "count", { dur: 1500 }); sfxEv(a + 1750, "countEnd", { i: i }); }
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
      sfxEv(a, "grow", { i: i }); if (s.highlight === i) sfxEv(a + 1100, "emphasize");
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
      sfxEv(200 + ci * 300, "appear", { i: ci });
      ctx.save(); ctx.globalAlpha *= k; ctx.translate((1 - k) * (ci === 0 ? -80 : 80), 0);
      var col = c.tone === "bad" ? C.warn : c.tone === "good" ? C.ok : accentAt(ci);
      panel(x, y, w, h, { stroke: col, lw: 2.5 });
      ctx.fillStyle = col; ctx.globalAlpha *= .14; rr(x, y, w, 96, 16); ctx.fill(); ctx.globalAlpha /= .14;
      txt(c.title || "", x + w / 2, y + 62, { size: 42, weight: 800, align: "center", color: col });
      pts[ci].forEach(function (p, i) {
        var a = at[i * 2 + ci]; sfxEv(a, "appear", { i: i }); var pk = P(lt, a, a + 500); if (pk <= 0) return;
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
    var vk = P(lt, 900, 1400, back); if (s.vs !== false) sfxEv(900, "hit");
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
      sfxEv(at[i], i === 0 ? "hit" : "appear", { i: i }); if (/\*\*/.test(ln)) sfxEv(at[i] + 550, "emphasize");
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
    var at = slots(hl.length, d, 900, 600), cur = -1; at.forEach(function (a, i) { if (lt >= a) cur = i; sfxEv(a, "emphasize", { i: i }); });
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
      sfxEv(a, "appear", { i: i }); (p.states || []).forEach(function (c0) { if ((c0.at || 0) > 0 && /^(done|blocked|working)$/.test(c0.state)) sfxEv(c0.at * d, c0.state); });
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
      sfxEv(a, "toast");
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
      sfxEv(700 + i * 700, "appear", { i: i });
      var k = P(lt, 700 + i * 700, 1300 + i * 700); if (k <= 0) return;
      var text = typeof r === "string" ? r : r.text, note = r.note, mono = r.mono !== false && /^[$>]/.test(text);
      ctx.save(); ctx.globalAlpha *= k;
      var w = Math.max(900, tw(text, { size: 32, font: mono ? F.mono : F.sans, weight: 600 }) + (note ? tw(note, { size: 24 }) + 80 : 60));
      panel(960 - w / 2, y + i * 96 - 50, w, 74, { shadow: false, fill: C.panel });
      txt(text, 960 - w / 2 + 30, y + i * 96, { size: 32, font: mono ? F.mono : F.sans, weight: 600, color: mono ? C.accent2 : C.ink });
      if (note) txt(note, 960 + w / 2 - 30, y + i * 96 - 2, { size: 24, color: C.muted, align: "right" });
      ctx.restore();
    });
    var fk = P(lt, 700 + rows.length * 700 + 400, 700 + rows.length * 700 + 1400, eio); sfxEv(700 + rows.length * 700 + 400, "outro");
    /* 字幕（画面の下 1 割）と重ならないよう、下端は 900 までに収める */
    txt(s.title || "", 960, 820, { size: 70, weight: 800, align: "center", font: F.display, alpha: fk });
    if (s.tagline) rich(s.tagline, 960, 884, { size: 32, align: "center", color: C.accent, alpha: P(lt, 700 + rows.length * 700 + 900, 700 + rows.length * 700 + 1900) });
  };

  /* ---------- 追加の部品 ---------- */
  R.cards = function (s, lt, d) {
    heading(s, lt);
    var items = s.items || [], n = items.length, cols = s.cols || (n <= 3 ? n : n === 4 ? 2 : 3), rows = Math.ceil(n / cols);
    var y0 = s.heading ? 290 : 190, gap = 32, cw = (1680 - gap * (cols - 1)) / cols, chh = Math.min(300, (880 - y0 - gap * (rows - 1)) / rows);
    var at = slots(n, d, 500, Math.max(1200, d * .35));
    items.forEach(function (it, i) {
      var c = i % cols, r = Math.floor(i / cols), x = 120 + c * (cw + gap), y = y0 + r * (chh + gap), k = P(lt, at[i], at[i] + 600, back);
      sfxEv(at[i], "appear", { i: i });
      if (k <= 0) return;
      ctx.save(); ctx.translate(x + cw / 2, y + chh / 2); ctx.scale(k, k); ctx.translate(-cw / 2, -chh / 2);
      panel(0, 0, cw, chh, {}); ctx.fillStyle = accentAt(i); ctx.fillRect(0, 0, cw, 6);
      var ix = 40; if (it.icon) { icon(it.icon, 58, 68, 48); ix = 104; }
      txt(it.title || "", ix, 84, { size: 42, weight: 800, color: accentAt(i) });
      wrap(it.text || "", cw - 80, { size: 32 }).slice(0, Math.floor((chh - 130) / 44)).forEach(function (ln, j) { rich(ln, 40, 156 + j * 44, { size: 32, color: C.muted }); });
      ctx.restore();
    });
  };
  R.timeline = function (s, lt, d) {
    heading(s, lt);
    var items = s.items || [], n = items.length, x0 = 170, x1 = 1750, y = s.heading ? 560 : 520;
    var at = slots(n, d, 900, Math.max(900, d * .2)), cur = -1; at.forEach(function (a, i) { if (lt >= a) cur = i; });
    ctx.save(); ctx.strokeStyle = C.edge; ctx.lineWidth = 6; ctx.lineCap = "round";
    ctx.beginPath(); ctx.moveTo(x0, y); ctx.lineTo(mix(x0, x1, P(lt, 0, 900, eio)), y); ctx.stroke(); ctx.restore();
    items.forEach(function (it, i) {
      var x = n > 1 ? mix(x0 + 60, x1 - 60, i / (n - 1)) : 960, k = P(lt, at[i], at[i] + 600, back), up = i % 2 === 0, act = i === cur;
      sfxEv(at[i], it.highlight ? "emphasize" : "tick", { i: i });
      if (k <= 0) return;
      ctx.save(); ctx.fillStyle = it.highlight || act ? C.accent : accentAt(i); ctx.beginPath(); ctx.arc(x, y, (act ? 18 : 13) * k, 0, Math.PI * 2); ctx.fill();
      if (it.highlight) { ctx.globalAlpha = .3 + .3 * Math.sin(lt / 260); ctx.beginPath(); ctx.arc(x, y, 30, 0, Math.PI * 2); ctx.fill(); }
      ctx.restore();
      var ty = up ? y - 70 : y + 90, a2 = P(lt, at[i] + 150, at[i] + 700);
      ctx.save(); ctx.strokeStyle = C.edge; ctx.lineWidth = 2; ctx.globalAlpha *= a2; ctx.beginPath(); ctx.moveTo(x, y + (up ? -20 : 20)); ctx.lineTo(x, up ? ty + 16 : ty - 44); ctx.stroke(); ctx.restore();
      txt(it.date || "", x, up ? ty - 70 : ty, { size: 30, weight: 800, align: "center", color: act ? C.accent : C.ink, alpha: a2, font: F.display });
      wrap(it.label || "", 300, { size: 26, weight: 700 }).slice(0, 2).forEach(function (ln, j) { txt(ln, x, (up ? ty - 30 : ty + 40) + j * 34, { size: 26, weight: 700, align: "center", alpha: a2 * (act || cur < 0 ? 1 : .75) }); });
      if (it.sub) txt(it.sub, x, (up ? ty + 36 : ty + 110), { size: 21, align: "center", color: C.muted, alpha: a2 });
    });
  };
  R.chat = function (s, lt, d) {
    heading(s, lt);
    var msgs = s.messages || [], at = slots(msgs.length, d, 700, 900), y0 = s.heading ? 280 : 170, bottom = 880, bubbles = [];
    msgs.forEach(function (m, i) {
      /* 右: 自分（user・me・side:right）。左: 相手。side を書けばそれに従う */
      var right = m.side ? m.side === "right" : /^(user|me|自分|ユーザー)$/i.test(m.from || "");
      var lines = wrap(m.text || "", 900, { size: 30 }), h = lines.length * 42 + 36 + (m.from ? 30 : 0);
      bubbles.push({ m: m, right: right, lines: lines, h: h, a: at[i] }); sfxEv(at[i], right ? "send" : "message");
    });
    var total = 0, shown = [];
    bubbles.forEach(function (b) { if (lt >= b.a - 700) shown.push(b); });
    shown.forEach(function (b) { total += b.h + 26; });
    var y = Math.min(y0, bottom - total);
    shown.forEach(function (b, i) {
      var typing = lt < b.a, k = typing ? 1 : P(lt, b.a, b.a + 450, back);
      var w = typing ? 130 : Math.max.apply(null, b.lines.map(function (l) { return tw(l.replace(/\*\*/g, ""), { size: 30 }); }).concat([tw(b.m.from || "", { size: 20 })])) + 56;
      var h = typing ? 70 : b.h, x = b.right ? 1780 - w : 140;
      ctx.save(); ctx.translate(x + (b.right ? w : 0), y); ctx.scale(k, k); ctx.translate(-(b.right ? w : 0), 0);
      rr(0, 0, w, h, 26); ctx.fillStyle = b.right ? C.accent : C.panel; ctx.fill();
      if (!b.right) { ctx.strokeStyle = C.edge; ctx.lineWidth = 1.5; ctx.stroke(); }
      var ink = b.right ? C.onAccent : C.ink;
      if (typing) { for (var j = 0; j < 3; j++) { ctx.fillStyle = ink; ctx.globalAlpha = .35 + .65 * Math.max(0, Math.sin(lt / 160 - j * .9)); ctx.beginPath(); ctx.arc(40 + j * 26, 35, 8, 0, Math.PI * 2); ctx.fill(); } }
      else {
        var ty = 50; if (b.m.from) { txt(b.m.from, 28, 38, { size: 20, weight: 700, color: b.right ? ink : C.accent2 }); ty = 80; }
        b.lines.forEach(function (ln, j) { rich(ln, 28, ty + j * 42, { size: 30, color: ink, emColor: b.right ? ink : C.accent }, b.right ? 1 : undefined); });
      }
      ctx.restore();
      y += (typing ? 70 : b.h) + 26;
    });
  };
  function niceMax(v) { if (v <= 0) return 1; var e = Math.pow(10, Math.floor(Math.log10(v))); var ms = [1, 2, 2.5, 5, 10]; for (var i = 0; i < ms.length; i++) if (v <= ms[i] * e) return ms[i] * e; return 10 * e; }
  R.line = function (s, lt, d) {
    heading(s, lt);
    var labels = s.labels || [], series = s.series || [], all = []; series.forEach(function (se) { all = all.concat(se.values); });
    var lo = s.min || 0, hi = niceMax(Math.max.apply(null, all) - lo) + lo, L = 220, Rr = 1700, T0 = s.heading ? 300 : 200, B = 850;
    var X = function (i) { return L + (Rr - L) * i / Math.max(1, labels.length - 1); }, Y = function (v) { return B - (B - T0) * (v - lo) / (hi - lo || 1); };
    var gk = P(lt, 0, 700);
    for (var g = 0; g <= 4; g++) { var gv = lo + (hi - lo) * g / 4, gy = Y(gv);
      ctx.save(); ctx.globalAlpha *= gk; ctx.strokeStyle = C.edge; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(L, gy); ctx.lineTo(Rr, gy); ctx.stroke(); ctx.restore();
      txt(fmtNum(String(Math.round(gv)), 1), L - 20, gy + 8, { size: 22, color: C.muted, align: "right", alpha: gk }); }
    labels.forEach(function (lb, i) { txt(lb, X(i), B + 44, { size: 24, color: C.muted, align: "center", alpha: gk }); });
    series.forEach(function (se, si) {
      var a = 700 + si * 500, k = P(lt, a, a + Math.max(1400, d * .35), function (x) { return x; }), col = accentAt(si), n = se.values.length;
      sfxEv(a, "grow", { i: si }); sfxEv(a + Math.max(1400, d * .35), "countEnd", { i: si });
      var upto = k * (n - 1);
      ctx.save(); ctx.strokeStyle = col; ctx.lineWidth = 6; ctx.lineJoin = "round"; ctx.lineCap = "round"; ctx.beginPath();
      for (var i = 0; i <= Math.floor(upto); i++) { var px = X(i), py = Y(se.values[i]); i ? ctx.lineTo(px, py) : ctx.moveTo(px, py); }
      var fi = Math.floor(upto); if (fi < n - 1) { var f = upto - fi; ctx.lineTo(mix(X(fi), X(fi + 1), f), mix(Y(se.values[fi]), Y(se.values[fi + 1]), f)); }
      ctx.stroke(); ctx.restore();
      for (var j = 0; j <= Math.floor(upto); j++) { ctx.save(); ctx.fillStyle = C.bg1; ctx.strokeStyle = col; ctx.lineWidth = 4; ctx.beginPath(); ctx.arc(X(j), Y(se.values[j]), 9, 0, Math.PI * 2); ctx.fill(); ctx.stroke(); ctx.restore(); }
      if (k >= 1) { var lv = se.values[n - 1]; txt(fmtNum(String(lv) + (s.unit || ""), P(lt, a + Math.max(1400, d * .35), a + Math.max(1400, d * .35) + 900)), X(n - 1) + 22, Y(lv) + 10, { size: 34, weight: 800, color: col, font: F.display }); }
      if (series.length > 1) { txt("● " + (se.name || ""), L + si * 260, T0 - 30, { size: 24, weight: 700, color: col, alpha: gk }); }
    });
  };
  R.donut = function (s, lt, d) {
    heading(s, lt);
    var items = s.items || [], total = items.reduce(function (a, it) { return a + (+it.value); }, 0) || 1;
    var cx = 700, cy = s.heading ? 580 : 540, rad = 250, sw = 90, a = -Math.PI / 2, k = P(lt, 400, 400 + Math.max(1600, d * .35), eio);
    var sweep = k * Math.PI * 2; sfxEv(400, "sweep");
    items.forEach(function (it, i) {
      sfxEv(800 + i * 300, "appear", { i: i });
      var frac = (+it.value) / total, a1 = a + frac * Math.PI * 2, e = Math.min(a1, -Math.PI / 2 + sweep);
      if (e > a) { ctx.save(); ctx.strokeStyle = accentAt(i); ctx.lineWidth = sw; ctx.beginPath(); ctx.arc(cx, cy, rad, a + .012, Math.max(a + .012, e - .012)); ctx.stroke(); ctx.restore(); }
      var lk = P(lt, 800 + i * 300, 1300 + i * 300), ly = cy - (items.length - 1) * 50 + i * 100;
      ctx.save(); ctx.globalAlpha *= lk; ctx.fillStyle = accentAt(i); rr(1080, ly - 22, 30, 30, 6); ctx.fill(); ctx.restore();
      txt(it.label || "", 1130, ly + 2, { size: 32, weight: 700, alpha: lk });
      txt(Math.round(100 * frac) + "%", 1720, ly + 2, { size: 34, weight: 800, color: accentAt(i), align: "right", alpha: lk, font: F.display });
      a = a1;
    });
    var cvv = s.center ? s.center.value : total.toLocaleString("en-US") + (s.unit || ""), cl = s.center ? s.center.label : "合計";
    txt(fmtNum(cvv, k), cx, cy + 16, { size: 64, weight: 800, align: "center", font: F.display });
    txt(cl || "", cx, cy + 62, { size: 26, align: "center", color: C.muted });
  };
  R.table = function (s, lt, d) {
    heading(s, lt);
    var cols = s.columns || [], rows = s.rows || [], n = rows.length, y0 = s.heading ? 290 : 190, rh = Math.min(92, (880 - y0 - 80) / Math.max(1, n));
    var FS = Math.max(24, Math.min(36, rh * .42));
    var cw = cols.map(function (c, i) { var m = tw(String(c), { size: FS, weight: 800 }); rows.forEach(function (r) { m = Math.max(m, tw(String(r[i] == null ? "" : r[i]), { size: FS })); }); return m + 80; });
    var sum = cw.reduce(function (a, b) { return a + b; }, 0), sc = Math.min(1680 / sum, Math.max(1, 1100 / sum)); cw = cw.map(function (w) { return w * sc; });
    var tot = cw.reduce(function (a, b) { return a + b; }, 0), x0 = 960 - tot / 2;
    var hl = s.highlight || [], hat = slots(hl.length, d, 900 + n * 200, 800), cur = -1; hat.forEach(function (a, i) { if (lt >= a) cur = hl[i]; sfxEv(a, "emphasize", { i: i }); });
    var num = cols.map(function (c, i) { return rows.every(function (r) { return /^[-+]?[¥$€]?[\d,.]+\s*[%％a-zA-Z一-龠ぁ-んァ-ヶ]{0,3}$/.test(String(r[i] || "0")); }); });
    var hk = P(lt, 0, 500);
    ctx.save(); ctx.globalAlpha *= hk; rr(x0, y0, tot, FS * 2.3, 12); ctx.fillStyle = C.panel2; ctx.fill(); ctx.restore();
    var x = x0; cols.forEach(function (c, i) { txt(String(c), num[i] ? x + cw[i] - 36 : x + 36, y0 + FS * 1.5, { size: FS, weight: 800, align: num[i] ? "right" : "left", alpha: hk }); x += cw[i]; });
    rows.forEach(function (r, j) {
      var a = 500 + j * Math.min(220, d * .03), k = P(lt, a, a + 450), y = y0 + FS * 2.3 + 8 + j * rh;
      sfxEv(a, "row", { i: j });
      if (k <= 0) return;
      ctx.save(); ctx.globalAlpha *= k; ctx.translate(0, (1 - k) * 12);
      if (cur === j) { rr(x0, y, tot, rh - 6, 10); ctx.fillStyle = C.accent; ctx.globalAlpha *= .18; ctx.fill(); ctx.globalAlpha /= .18; ctx.strokeStyle = C.accent; ctx.lineWidth = 2; ctx.stroke(); }
      else { ctx.strokeStyle = C.edge; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(x0, y + rh - 3); ctx.lineTo(x0 + tot, y + rh - 3); ctx.stroke(); }
      var xx = x0; cols.forEach(function (c, i) { txt(String(r[i] == null ? "" : r[i]), num[i] ? xx + cw[i] - 36 : xx + 36, y + rh / 2 + FS * .35, { size: FS, weight: cur === j ? 800 : 400, align: num[i] ? "right" : "left", color: cur === j ? C.ink : (i === 0 ? C.ink : C.muted) }); xx += cw[i]; });
      ctx.restore();
    });
  };
  R.quote = function (s, lt, d) {
    var lines = wrap(s.text || "", 1400, { size: 54, weight: 700, font: F.display }), n = lines.length, lh = 80, y0 = 540 - (n - 1) * lh / 2 - 20;
    txt("“", 240, y0 - 40, { size: 260, weight: 800, color: C.accent, alpha: P(lt, 0, 800) * .8, font: F.display });
    var at = slots(n, d * .6, 400, 0); sfxEv(0, "quote");
    lines.forEach(function (ln, i) { var k = P(lt, at[i], at[i] + 700); rich(ln, 360, y0 + i * lh + (1 - k) * 16, { size: 54, weight: 700, font: F.display, alpha: k }, P(lt, at[i] + 400, at[i] + 1100)); });
    var bk = P(lt, d * .55, d * .55 + 800); if (s.by) sfxEv(d * .55, "appear", { i: 0 });
    ctx.save(); ctx.globalAlpha *= bk; ctx.fillStyle = C.accent; ctx.fillRect(360, y0 + n * lh + 10, 60, 4); ctx.restore();
    if (s.by) txt(s.by, 440, y0 + n * lh + 26, { size: 32, weight: 800, alpha: bk });
    if (s.role) txt(s.role, 440, y0 + n * lh + 70, { size: 24, color: C.muted, alpha: bk });
  };
  R.kinetic = function (s, lt, d) {
    var text = s.text || "", toks = [], re = /\*\*([^*]+)\*\*|([^\s*]+)/g, m;
    while ((m = re.exec(text))) toks.push({ w: m[1] || m[2], em: !!m[1] });
    if (toks.length === 1 && /[^\x00-\x7f]/.test(toks[0].w)) { toks = toks[0].w.split(/(?<=[、。，．！？])/).map(function (w) { return { w: w, em: false }; }); }
    var size = s.size || 92, lines = [[]], lw = 0, gap = size * .32, maxW = 1600;
    toks.forEach(function (t0) { var w = tw(t0.w, { size: t0.em ? size * 1.12 : size, weight: 800, font: F.display }); if (lw + w > maxW && lines[lines.length - 1].length) { lines.push([]); lw = 0; } t0.width = w; lines[lines.length - 1].push(t0); lw += w + gap; });
    var total = toks.length, per = Math.min(420, (d * .6) / Math.max(1, total)), idx = 0, lh = size * 1.35, y0 = 540 - (lines.length - 1) * lh / 2 + size * .35;
    lines.forEach(function (ln, li) {
      var wsum = ln.reduce(function (a, t0) { return a + t0.width; }, 0) + gap * (ln.length - 1), x = 960 - wsum / 2;
      ln.forEach(function (t0) {
        var a = 300 + idx * per, k = P(lt, a, a + 520, back), sz = t0.em ? size * 1.12 : size;
        sfxEv(a, t0.em ? "hit" : "word", { i: idx });
        if (k > 0) { ctx.save(); ctx.translate(x + t0.width / 2, y0 + li * lh); ctx.scale(k, k);
          txt(t0.w, 0, (1 - Math.min(1, k)) * 30, { size: sz, weight: 800, align: "center", font: F.display, color: t0.em ? C.accent : C.ink });
          if (t0.em) { ctx.fillStyle = C.accent; ctx.fillRect(-t0.width / 2, sz * .2, t0.width * P(lt, a + 300, a + 800), Math.max(4, sz * .07)); }
          ctx.restore(); }
        x += t0.width + gap; idx++;
      });
    });
  };
  R.split = function (s, lt, d) {
    heading(s, lt);
    var y0 = s.heading ? 300 : 200, k = P(lt, 0, 700), L = s.left || {};
    ctx.save(); ctx.globalAlpha *= k; ctx.translate((1 - k) * -40, 0);
    var y = y0;
    if (L.title) { wrap(L.title, 720, { size: 48, weight: 800, font: F.display }).forEach(function (ln) { txt(ln, 120, y + 40, { size: 48, weight: 800, font: F.display }); y += 64; }); y += 20; }
    if (L.text) { wrap(L.text, 720, { size: 30 }).forEach(function (ln) { rich(ln, 120, y + 30, { size: 30, color: C.muted }); y += 44; }); y += 16; }
    var pts = L.points || [], at = slots(pts.length, d, 700, d * .3);
    pts.forEach(function (p, i) { sfxEv(at[i], "appear", { i: i }); var pk = P(lt, at[i], at[i] + 500); if (pk <= 0) return;
      ctx.save(); ctx.globalAlpha *= pk; ctx.fillStyle = accentAt(i); ctx.beginPath(); ctx.arc(136, y + 22, 8, 0, Math.PI * 2); ctx.fill(); ctx.restore();
      wrap(p, 680, { size: 30 }).forEach(function (ln, j) { rich(ln, 164, y + 32 + j * 42, { size: 30, alpha: pk }); }); y += wrap(p, 680, { size: 30 }).length * 42 + 18; });
    ctx.restore();
    if (s.right && R[s.right.type] && s.right.type !== "split") {
      var sub2 = s._rightSpec || (s._rightSpec = Object.assign({}, s.right, { heading: "" }));
      ctx.save(); ctx.globalAlpha *= P(lt, 300, 1000); ctx.translate(820, y0 - 120); ctx.scale(.58, .58);
      EVOFF += 300; try { R[sub2.type](sub2, Math.max(0, lt - 300), d - 300); drawOverlays(sub2, Math.max(0, lt - 300), d - 300); } finally { EVOFF -= 300; } ctx.restore();
    }
  };
  R.beforeafter = function (s, lt, d) {
    heading(s, lt);
    var y0 = s.heading ? 280 : 180, x0 = 140, w = 1640, h = 900 - y0, bf = s.before || {}, af = s.after || {};
    var u = P(lt, d * .35, d * .35 + Math.max(1400, d * .25), eio), sx = x0 + w * u; sfxEv(d * .35, "reveal");
    function side(o, tone, ax) {
      var col = tone === "good" ? C.ok : tone === "bad" ? C.warn : C.accent2;
      panel(x0, y0, w, h, { stroke: col, lw: 2.5, shadow: false });
      txt(o.label || (tone === "good" ? "After" : "Before"), ax, y0 + 64, { size: 30, weight: 800, color: col, align: ax > 960 ? "right" : "left" });
      if (o.title) txt(o.title, 960, y0 + 170, { size: 56, weight: 800, align: "center", font: F.display });
      (o.points || []).forEach(function (p, i) { rich(p, 960, y0 + 260 + i * 62, { size: 34, align: "center", color: C.muted }); });
      if (o.value) txt(o.value, 960, y0 + h - 70, { size: 90, weight: 800, align: "center", color: col, font: F.display });
    }
    ctx.save(); ctx.globalAlpha *= P(lt, 0, 600); side(bf, bf.tone || "bad", x0 + 40); ctx.restore();
    if (u > 0) { ctx.save(); ctx.beginPath(); ctx.rect(x0, y0 - 4, sx - x0, h + 8); ctx.clip(); rr(x0, y0, w, h, 16); ctx.fillStyle = C.bg1; ctx.fill(); side(af, af.tone || "good", x0 + w - 40); ctx.restore();
      if (u < 1) { ctx.fillStyle = C.accent; ctx.fillRect(sx - 3, y0 - 20, 6, h + 40); ctx.beginPath(); ctx.arc(sx, y0 + h / 2, 22, 0, Math.PI * 2); ctx.fill();
        txt("⇆", sx, y0 + h / 2 + 10, { size: 26, weight: 800, align: "center", color: C.onAccent }); } }
  };

  var CUSTOM = new WeakMap();
  R.custom = function (s, lt, d, T) {
    var fn = CUSTOM.get(s);
    if (!fn) { try { fn = new Function("ctx", "lt", "d", "H", "s", Array.isArray(s.code) ? s.code.join("\n") : s.code); } catch (e) { fn = function () {}; console.error("custom scene:", e); } CUSTOM.set(s, fn); }
    heading(s, lt);
    ctx.save(); try { fn(ctx, lt, d, HELP, s); } catch (e) { if (!s._err) { s._err = 1; console.error("custom scene:", e); } } ctx.restore();
  };
  /* ---- custom と重ねの層で使う道具 ---- */
  /* 乱数の種で決まる乱数（時刻だけで決まる描画のため。Math.random は使わない） */
  function rand(seed) { var a = (seed >>> 0) || 1; return function () { a |= 0; a = a + 0x6D2B79F5 | 0; var t2 = Math.imul(a ^ a >>> 15, 1 | a);
    t2 = t2 + Math.imul(t2 ^ t2 >>> 7, 61 | t2) ^ t2; return ((t2 ^ t2 >>> 14) >>> 0) / 4294967296; }; }
  function arrow(p0, c, p1, k, o) {
    o = o || {}; if (k <= 0) return; c = c || { x: (p0.x + p1.x) / 2, y: (p0.y + p1.y) / 2 };
    ctx.save(); ctx.strokeStyle = o.color || C.accent2; ctx.lineWidth = o.width || 4; ctx.lineCap = "round"; if (o.dashed) ctx.setLineDash([14, 10]);
    if (o.glow) { ctx.shadowColor = o.color || C.accent2; ctx.shadowBlur = 24 * o.glow; }
    ctx.beginPath(); var N = 40; for (var j = 0; j <= N * clamp(k); j++) { var q = qpt(p0, c, p1, j / N); j ? ctx.lineTo(q.x, q.y) : ctx.moveTo(q.x, q.y); } ctx.stroke();
    ctx.setLineDash([]); ctx.shadowBlur = 0;
    if (k >= 1 && o.head !== false) { var pe = qpt(p0, c, p1, 1), pb = qpt(p0, c, p1, .96); ctx.translate(pe.x, pe.y); ctx.rotate(Math.atan2(pe.y - pb.y, pe.x - pb.x));
      ctx.fillStyle = o.color || C.accent2; ctx.beginPath(); ctx.moveTo(6, 0); ctx.lineTo(-16, -11); ctx.lineTo(-16, 11); ctx.closePath(); ctx.fill(); }
    ctx.restore();
  }
  function packet(p0, c, p1, u, label, o) {
    o = o || {}; if (u <= 0 || u >= 1) return; c = c || { x: (p0.x + p1.x) / 2, y: (p0.y + p1.y) / 2 };
    var pt = qpt(p0, c, p1, eio(u)), col = o.color || C.accent; ctx.save(); ctx.shadowColor = col; ctx.shadowBlur = 20; ctx.fillStyle = col;
    if (label) { var w = tw(label, { size: 20, weight: 700, font: F.mono }) + 24; rr(pt.x - w / 2, pt.y - 20, w, 40, 10); ctx.fill(); ctx.shadowBlur = 0;
      txt(label, pt.x, pt.y + 7, { size: 20, weight: 700, font: F.mono, align: "center", color: C.onAccent }); }
    else { ctx.beginPath(); ctx.arc(pt.x, pt.y, o.r || 11, 0, Math.PI * 2); ctx.fill(); }
    ctx.restore();
  }
  function node(x, y, w, h, label, sub, o) {
    o = o || {}; panel(x, y, w, h, { stroke: o.stroke || (o.hot ? C.accent : C.edge), lw: o.hot ? 3 : 1.5, fill: o.fill || C.panel });
    var ink = o.ink || C.ink, cx = x + w / 2, cy = y + h / 2;
    if (o.state) { stateMark(x + 28, y + 28, o.state, o.t || 0, 10); }
    txt(label, cx, sub ? cy - 2 : cy + 12, { size: o.size || 34, weight: 800, align: "center", color: ink });
    if (sub) txt(sub, cx, cy + 34, { size: 21, align: "center", color: o.subColor || C.muted, font: F.mono });
  }
  function appWindow(x, y, w, h, title, o) {
    o = o || {}; panel(x, y, w, h, { r: 18 }); ctx.save(); rr(x, y, w, h, 18); ctx.clip();
    ctx.fillStyle = C.bg1; ctx.fillRect(x, y, w, 46);
    for (var i = 0; i < 3; i++) { ctx.fillStyle = C.edge; ctx.beginPath(); ctx.arc(x + 26 + i * 22, y + 23, 6.5, 0, Math.PI * 2); ctx.fill(); }
    txt(title || "", x + w / 2, y + 31, { size: 20, color: C.muted, align: "center" }); ctx.restore();
    return { x: x + 1, y: y + 47, w: w - 2, h: h - 48 };
  }
  function toast(x, y, w, title, sub, kind, k, t0) {
    if (k <= 0) return; ctx.save(); ctx.globalAlpha *= clamp(k); ctx.translate((1 - Math.min(1, k)) * 80, 0);
    panel(x, y, w, 96, { stroke: kind === "blocked" ? C.warn : C.ok, lw: 2 }); stateMark(x + 38, y + 36, kind || "done", t0 || 0, 11);
    txt(title || "", x + 64, y + 44, { size: 23, weight: 700 }); if (sub) txt(sub, x + 64, y + 74, { size: 17, font: F.mono, color: C.muted }); ctx.restore();
  }
  function typed(str, k) { str = String(str); return str.slice(0, Math.round(str.length * clamp(k))); }
  function particles(o, lt) {
    o = o || {}; var r = rand(o.seed || 7), n = o.n || 60, x = o.x || 0, y = o.y || 0, w = o.w || W, h = o.h || H, sp = o.speed || 1;
    ctx.save(); ctx.fillStyle = o.color || C.accent2;
    for (var i = 0; i < n; i++) { var px = r() * w, py = r() * h, vy = (r() * .6 + .2) * sp, ph = r() * Math.PI * 2, sz = (o.size || 3) * (r() * .8 + .4);
      var yy = (py - lt * vy * .03) % h; if (yy < 0) yy += h; ctx.globalAlpha = (o.alpha || .5) * (.5 + .5 * Math.sin(lt / 700 + ph));
      ctx.beginPath(); ctx.arc(x + px + Math.sin(lt / 1500 + ph) * 12, y + yy, sz, 0, Math.PI * 2); ctx.fill(); }
    ctx.restore();
  }
  function cursor(x, y, down, lt) {
    ctx.save(); ctx.translate(x, y);
    if (down) { ctx.strokeStyle = C.accent; ctx.lineWidth = 3; ctx.globalAlpha = .7; ctx.beginPath(); ctx.arc(0, 0, 18 + (lt % 400) / 20, 0, Math.PI * 2); ctx.stroke(); ctx.globalAlpha = 1; }
    ctx.fillStyle = "#ffffff"; ctx.strokeStyle = "#111111"; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(0, 34); ctx.lineTo(9, 26); ctx.lineTo(16, 40); ctx.lineTo(22, 37); ctx.lineTo(15, 24); ctx.lineTo(27, 24); ctx.closePath(); ctx.fill(); ctx.stroke();
    ctx.restore();
  }
  /* 部品を縮小して置く（custom で複数の部品を並べる。spec は s の中に置くと配置の計算が使い回される） */
  function sub(type, spec, lt, d, o) {
    o = o || {}; var sc = o.scale || 1; ctx.save(); if (o.alpha !== undefined) ctx.globalAlpha *= o.alpha;
    ctx.translate(o.x || 0, o.y || 0); ctx.scale(sc, sc);
    if (o.clip) { rr(0, 0, W, H, 24 / sc); ctx.clip(); }
    EVMUTE++; try { (R[type] || R.statement)(spec, Math.max(0, lt), d); drawOverlays(spec, lt, d); } finally { EVMUTE--; } ctx.restore();
  }
  /* カメラ: [{at:0..1, x, y, zoom}] を場面の進みで補間し、(x,y) を画面の中央に zoom 倍で映す */
  function camAt(keys, f) {
    if (!keys || !keys.length) return null;
    var a = keys[0], b = keys[keys.length - 1];
    for (var i = 0; i < keys.length - 1; i++) if (f >= (keys[i].at || 0) && f <= (keys[i + 1].at || 1)) { a = keys[i]; b = keys[i + 1]; break; }
    if (f <= (keys[0].at || 0)) b = a = keys[0];
    var k = a === b ? 0 : eio(lin(f, a.at || 0, b.at || 1));
    return { x: mix(a.x === undefined ? 960 : a.x, b.x === undefined ? 960 : b.x, k), y: mix(a.y === undefined ? 540 : a.y, b.y === undefined ? 540 : b.y, k),
             zoom: mix(a.zoom || 1, b.zoom || 1, k) };
  }
  function applyCam(cam) { if (!cam) return; ctx.translate(960, 540); ctx.scale(cam.zoom, cam.zoom); ctx.translate(-cam.x, -cam.y); }

  /* ---- 重ねの層（どの場面にも。座標は 1920×1080、at / until は場面の進み 0..1） ---- */
  function drawOverlays(s, lt, d) {
    (s.overlays || []).forEach(function (o) {
      var a = (o.at || 0) * d, b = o.until !== undefined ? o.until * d : d, k = P(lt, a, a + 450) * (1 - P(lt, b - 350, b));
      var kind = o.kind || "note";
      if (o.sfx !== false) {
        if (kind === "cursor") (o.click || []).forEach(function (ci) { var pts0 = o.path || [[960, 540]]; sfxEv(a + (b - 350 - a) * ci / Math.max(1, pts0.length - 1), "click"); });
        else sfxEv(a, typeof o.sfx === "string" ? o.sfx : kind === "notify" ? "notify" : kind === "highlight" ? "highlight" : kind === "badge" ? "badge" : kind === "arrow" ? "arrow" : "note");
      }
      if (k <= 0) return;
      ctx.save(); ctx.globalAlpha *= k;
      if (kind === "note") {
        var lines = wrap(o.text || "", o.width || 420, { size: 28, weight: 700 }), w = Math.min(o.width || 420, Math.max.apply(null, lines.map(function (l) { return tw(l, { size: 28, weight: 700 }); }))) + 40, h = lines.length * 38 + 30;
        var x = o.x === undefined ? 1400 : o.x, y = o.y === undefined ? 200 : o.y;
        if (o.target) { var tx = o.target[0], ty = o.target[1], ex = tx < x ? x : tx > x + w ? x + w : tx, ey = ty < y ? y : y + h;
          ctx.strokeStyle = C.accent; ctx.lineWidth = 2.5; ctx.setLineDash([6, 6]); ctx.beginPath(); ctx.moveTo(ex, ey); ctx.lineTo(mix(ex, tx, P(lt, a, a + 600)), mix(ey, ty, P(lt, a, a + 600))); ctx.stroke(); ctx.setLineDash([]);
          ctx.fillStyle = C.accent; ctx.beginPath(); ctx.arc(tx, ty, 7 * P(lt, a + 400, a + 700, back), 0, Math.PI * 2); ctx.fill(); }
        panel(x, y, w, h, { stroke: C.accent, lw: 2 });
        lines.forEach(function (l, i) { rich(l, x + 20, y + 44 + i * 38, { size: 28, weight: 700 }); });
      } else if (kind === "arrow") {
        var p0 = { x: o.from[0], y: o.from[1] }, p1 = { x: o.to[0], y: o.to[1] }, cv2 = o.curve ? { x: (p0.x + p1.x) / 2 - (p1.y - p0.y) * o.curve, y: (p0.y + p1.y) / 2 + (p1.x - p0.x) * o.curve } : null;
        arrow(p0, cv2, p1, P(lt, a, a + 700, eio), { color: C.accent, width: 5 });
        if (o.label) { var m = qpt(p0, cv2 || { x: (p0.x + p1.x) / 2, y: (p0.y + p1.y) / 2 }, p1, .5); txt(o.label, m.x, m.y - 16, { size: 26, weight: 700, color: C.accent, align: "center" }); }
      } else if (kind === "highlight") {
        var r = o.rect, pu = .5 + .5 * Math.sin(lt / 260);
        if (o.spotlight) { ctx.save(); ctx.fillStyle = "rgba(0,0,0," + (.55 * k) + ")"; ctx.beginPath(); ctx.rect(0, 0, W, H); rr(r[0] - 12, r[1] - 12, r[2] + 24, r[3] + 24, 16); ctx.fill("evenodd"); ctx.restore(); }
        ctx.strokeStyle = C.accent; ctx.lineWidth = 4 + 2 * pu; rr(r[0] - 12, r[1] - 12, r[2] + 24, r[3] + 24, 16); ctx.stroke();
        if (o.label) txt(o.label, r[0] - 12, r[1] - 26, { size: 26, weight: 700, color: C.accent });
      } else if (kind === "badge") {
        var bw = tw(o.text || "", { size: 24, weight: 800 }) + 32, bk = P(lt, a, a + 500, back);
        ctx.translate(o.x || 0, o.y || 0); ctx.scale(bk, bk); rr(-bw / 2, -22, bw, 44, 22); ctx.fillStyle = o.color === "warn" ? C.warn : C.accent; ctx.fill();
        txt(o.text || "", 0, 9, { size: 24, weight: 800, align: "center", color: C.onAccent });
      } else if (kind === "cursor") {
        var pts = o.path || [[960, 540]], f = lin(lt, a, b - 350), seg = Math.min(pts.length - 2, Math.floor(f * (pts.length - 1))), u = pts.length > 1 ? f * (pts.length - 1) - seg : 0;
        if (pts.length === 1) seg = 0;
        var pA = pts[Math.max(0, seg)], pB = pts[Math.min(pts.length - 1, seg + 1)], e = eio(clamp(u)), cx2 = mix(pA[0], pB[0], e), cy2 = mix(pA[1], pB[1], e);
        var down = (o.click || []).some(function (ci) { var ct = a + (b - 350 - a) * ci / Math.max(1, pts.length - 1); return lt >= ct && lt < ct + 400; });
        cursor(cx2, cy2, down, lt);
      } else if (kind === "notify") {
        var nw = 520, nx = W - nw - 48, ny = o.pos === "br" ? H - 330 : 110, nk = P(lt, a, a + 500);   /* 既定は右上（下は字幕と操作部が重なる） */
        ctx.translate(0, (1 - nk) * 30);
        ctx.save(); ctx.shadowColor = "rgba(0,0,0,.35)"; ctx.shadowBlur = 30; rr(nx, ny, nw, 110, 18); ctx.fillStyle = "#eef2f4"; ctx.fill(); ctx.restore();
        emblem("ring", nx + 52, ny + 55, 24, 0, 1, o.app || SPEC.title);
        txt(o.app || (SPEC.brand && SPEC.brand.name) || "", nx + 96, ny + 44, { size: 22, weight: 700, color: "#0f2230" });
        txt(o.text || "", nx + 96, ny + 78, { size: 22, color: "#35505b" });
      }
      ctx.restore();
    });
  }
  var HELP = { C: C, F: F, W: W, H: H, clamp: clamp, lin: lin, eo: eo, eio: eio, back: back, P: P, mix: mix, rr: rr, txt: txt, tw: tw, wrap: wrap,
               rich: rich, icon: icon, panel: panel, stateMark: stateMark, emblem: emblem, accentAt: accentAt, slots: slots,
               qpt: qpt, rand: rand, arrow: arrow, packet: packet, node: node, appWindow: appWindow, toast: toast, typed: typed, count: fmtNum,
               particles: particles, cursor: cursor, sub: sub, camAt: camAt, applyCam: applyCam, heading: heading,
               sfx: function (at, what, o) { sfxEv(at, what, o); } };

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
  var FADE = 450, SWEEP = 700;
  function trOf(k) { return SCENES[k].s.transition || SPEC.transition || "fade"; }
  function drawScene(k, t, o) {
    o = o || {};
    var sc = SCENES[k], lt = o.lt !== undefined ? o.lt : t - sc.t0, d = sc.d, tr = trOf(k);
    var last = k === SCENES.length - 1, nextTr = last ? "" : trOf(k + 1), sweepIn = tr === "wipe" || tr === "push", sweepOut = nextTr === "wipe" || nextTr === "push";
    var inK = k === 0 || sweepIn || tr === "cut" ? 1 : P(lt, 0, FADE), outK = last || sweepOut || nextTr === "cut" ? 1 : 1 - P(lt, d - FADE, d, eio);
    ctx.save(); ctx.globalAlpha = Math.min(inK, outK);
    if (o.clipX !== undefined) { ctx.beginPath(); ctx.rect(0, 0, o.clipX, H); ctx.clip(); backdrop(t); }
    if (o.dx) ctx.translate(o.dx, 0);
    if (tr === "slide") ctx.translate((1 - inK) * 80, 0);
    if (nextTr === "slide") ctx.translate(-(1 - outK) * 80, 0);
    if (tr === "zoom" || nextTr === "zoom") { var z = mix(.96, 1, inK) * mix(1.04, 1, outK); ctx.translate(960, 540); ctx.scale(z, z); ctx.translate(-960, -540); }
    var cam = camAt(sc.s.camera, clamp(lt / d));
    if (cam) { ctx.save(); applyCam(cam); }
    (R[sc.s.type] || R.statement)(sc.s, Math.max(0, lt), d, t);
    drawOverlays(sc.s, Math.max(0, lt), d);
    if (cam) ctx.restore();
    ctx.restore();
  }
  function burnCaption(t) {
    var c = CUES.filter(function (c) { return t >= c.a && t < c.b; })[0]; if (!c) return;
    var lines = wrap(c.text.replace(/\*\*/g, ""), 1500, { size: 40, weight: 700 }), y0 = H - 70 - (lines.length - 1) * 58;
    lines.forEach(function (ln, i) { var w = tw(ln, { size: 40, weight: 700 }) + 44;
      ctx.save(); ctx.fillStyle = "rgba(4,8,12,.8)"; rr(960 - w / 2, y0 + i * 58 - 46, w, 58, 8); ctx.fill(); ctx.restore();
      txt(ln, 960, y0 + i * 58 - 4, { size: 40, weight: 700, align: "center", color: "#f5f8f9" }); });
  }
  var thumbMode = false;
  function draw(t) {
    scaleCtx(); backdrop(t);
    var k = sceneAt(t), tr = trOf(k), lt = t - SCENES[k].t0;
    if (k > 0 && (tr === "wipe" || tr === "push") && lt < SWEEP) {
      var u = eio(lin(lt, 0, SWEEP)), prevD = SCENES[k - 1].d;
      if (tr === "push") { drawScene(k - 1, t, { lt: prevD - 1, dx: -W * u }); drawScene(k, t, { dx: W * (1 - u) }); }
      else { drawScene(k - 1, t, { lt: prevD - 1 }); drawScene(k, t, { clipX: W * u }); ctx.fillStyle = C.accent; ctx.fillRect(W * u - 3, 0, 6, H); }
    } else {
      if (k > 0 && lt < FADE && tr !== "cut") drawScene(k - 1, t);
      drawScene(k, t);
    }
    chrome(t);
    if (recording && captions) burnCaption(t);
    if (!thumbMode) syncDom(t);
  }

  /* ================= HTML・SVG で描く場面（dom） ================= */
  var domLayer = $("mv-dom"), domEls = {}, domScale = 1;
  R.dom = function (s, lt) { heading(s, lt); };
  function syncDom(t) {
    if (!domLayer) return;
    var k = sceneAt(t);
    SCENES.forEach(function (sc, i) {
      if (sc.s.type !== "dom") return;
      var el = domEls[i], lt = t - sc.t0, active = i === k || (i === k - 1 && t - SCENES[k].t0 < FADE);
      if (!active) { if (el) el.style.display = "none"; return; }
      if (!el) {
        el = document.createElement("div"); el.className = "mv-domscene";
        el.innerHTML = (sc.s.css ? "<style>" + sc.s.css + "</style>" : "") + (sc.s.html || "");
        domLayer.appendChild(el); domEls[i] = el;
        try { el.__up = sc.s.update ? new Function("el", "lt", "d", "H", "s", sc.s.update) : null; } catch (e) { console.error("dom scene:", e); }
      }
      var d = sc.d, inK = i === 0 ? 1 : P(lt, 0, FADE), outK = i === SCENES.length - 1 ? 1 : 1 - P(lt, d - FADE, d, eio);
      el.style.display = "block"; el.style.transform = "scale(" + domScale + ")"; el.style.opacity = String(Math.min(inK, outK));
      var cl = Math.max(0, Math.min(lt, d));
      el.style.setProperty("--lt", String(cl)); el.style.setProperty("--p", String(clamp(cl / d)));
      if (el.__up) { try { el.__up(el, cl, d, HELP, sc.s); } catch (e) { if (!sc.s._err) { sc.s._err = 1; console.error("dom scene:", e); } } }
    });
  }


  /* ================= 音声（読み上げ・音楽・効果音） ================= */
  var AUD = SPEC.audio || {}, MA = window.MotionAudio;
  var ac = null, master = null, recording = null, duckG = null, sfxBus = null;
  var MUS = AUD._music || {}, SFXD = AUD._sfx || {}, SFXCFG = AUD._sfxcfg || null, INSTX = Object.assign({}, (MA && MA.INST) || {}, AUD.instruments || {});
  var SFXBUF = {}, SFXFN = {};
  function ensureAudio() {
    if (ac || !MA) return;
    try { ac = new (window.AudioContext || window.webkitAudioContext)(); master = ac.createGain(); master.gain.value = audioOn ? 1 : 0;
      /* 出口に抑え（音楽・効果音が重なっても割れない） */
      var lim = ac.createDynamicsCompressor(); lim.threshold.value = -6; lim.knee.value = 6; lim.ratio.value = 12; lim.attack.value = .003; lim.release.value = .2;
      master.connect(lim); lim.connect(ac.destination);
      duckG = ac.createGain(); duckG.gain.value = 1; duckG.connect(master);
      sfxBus = ac.createGain(); sfxBus.gain.value = SFXCFG ? (SFXCFG.volume === undefined ? 1 : SFXCFG.volume) : 1; sfxBus.connect(master);
      /* ファイルの効果音は先に復号しておく */
      Object.keys(SFXD).forEach(function (k) { var r = SFXD[k]; if (!r.file) return;
        fetch(r.file).then(function (x) { return x.arrayBuffer(); }).then(function (buf) { return ac.decodeAudioData(buf); }).then(function (b) { SFXBUF[k] = b; }).catch(function (e) { console.warn("sfx file:", k, e); }); });
    } catch (e) { ac = null; } }

  /* ---- 音楽: 章ごとに曲の頭から。音符は「章の中の時刻」だけで決まる（MotionAudio.notes）。
   * 音楽の時計 mt は、読み上げを待って映像が止まっている間も進む（音が途切れない）。シーク・再生・速度の変更で映像の時刻に合わせ直す */
  var mclock = { mt: 0, upTo: 0, sec: -1, secStart: 0, bus: null, files: {}, fresh: false };
  var MUSVOL = AUD.musicVolume === undefined ? 1 : AUD.musicVolume;
  var musicOn = true, sfxOn = true;   /* 見る人の設定（設定の「音楽」「効果音」）。起動時に読み込む */
  function musicKeyOf(ci) { var ch = SPEC.chapters[ci]; return ch && ch._music !== undefined ? ch._music : AUD._musicKey; }
  function energyOf(ci) {
    var ch = SPEC.chapters[ci], n = CHAPTERS.length;
    if (ch && ch.energy) return ch.energy;
    if (Array.isArray(AUD.energy) && AUD.energy[ci]) return AUD.energy[ci];
    if (ci === 0 || (ci === n - 1 && n > 2)) return 1;
    return ci === n - 2 && n >= 4 ? 3 : 2;
  }
  function musicStop() {
    if (!ac) return;
    if (mclock.bus) { var old = mclock.bus; old.gain.cancelScheduledValues(ac.currentTime); old.gain.setTargetAtTime(0, ac.currentTime, .06);
      setTimeout(function () { try { old.disconnect(); } catch (e) {} }, 600); }
    mclock.bus = null; mclock.sec = -1;
    Object.keys(mclock.files).forEach(function (k) { try { mclock.files[k].el.pause(); } catch (e) {} });
  }
  function musicReset() { musicStop(); mclock.mt = t; }
  function fileOf(key, def) {
    var f = mclock.files[key]; if (f) return f;
    var el = new Audio(def.file); el.loop = def.loop !== false; el.preservesPitch = true;
    var g = ac.createGain(); g.gain.value = (def.volume === undefined ? .35 : def.volume) * MUSVOL;
    try { ac.createMediaElementSource(el).connect(g); g.connect(duckG); } catch (e) { console.warn("music file:", e); }
    return (mclock.files[key] = { el: el, g: g });
  }
  function musicTick(dtReal) {
    if (!ac || !audioOn || !playing || !MA || !musicOn) return;
    mclock.mt += dtReal * speed;
    var ci = chapterAt(t), key = musicKeyOf(ci), def = key ? MUS[key] : null, off = mclock.mt - t;
    if (ci !== mclock.sec) {
      mclock.sec = ci; mclock.secStart = CHAPTERS[ci].t + off; mclock.upTo = mclock.mt; mclock.fresh = true;
      if (!mclock.bus) { mclock.bus = ac.createGain(); mclock.bus.gain.value = MUSVOL * (def && def.g ? def.g : 1); mclock.bus.connect(duckG); }
      else mclock.bus.gain.setTargetAtTime(MUSVOL * (def && def.g ? def.g : 1), ac.currentTime, .3);
      Object.keys(mclock.files).forEach(function (k) { if (k !== key) try { mclock.files[k].el.pause(); } catch (e) {} });
    }
    if (!def) return;
    if (def.file) {
      /* ファイル: 映像の先頭（章の曲なら章の先頭）からの位置に合わせて鳴らし、0.3 秒よりずれたら合わせ直す */
      var f = fileOf(key, def), pos = (AUD._musicKey === key && !SPEC.chapters[ci]._music ? mclock.mt : mclock.mt - mclock.secStart) / 1000, dur = f.el.duration;
      if (dur && isFinite(dur)) pos = def.loop === false ? Math.min(pos, dur) : pos % dur;
      f.el.playbackRate = speed;
      if (f.el.paused) { try { f.el.currentTime = pos; } catch (e) {} f.el.play().catch(function () {}); }
      else if (Math.abs(f.el.currentTime - pos) > .3) { try { f.el.currentTime = pos; } catch (e) {} }
      return;
    }
    var secEnd = (ci < CHAPTERS.length - 1 ? CHAPTERS[ci + 1].t : DUR) + off, to = Math.min(mclock.mt + 300 * speed, secEnd), from = mclock.upTo;
    if (to <= from) return;
    var info = { ci: ci, energy: energyOf(ci), len: secEnd - mclock.secStart }, lf = from - mclock.secStart;
    MA.notes(def, info, mclock.fresh ? Math.max(0, lf - 12000) : lf, to - mclock.secStart).forEach(function (n) {
      var st = n.t, en = n.t + (n.d || 0);
      if (st < lf) { if (!mclock.fresh || n.drum || en <= lf + 60 || !MA.isSus(n.inst, INSTX)) return; }   /* 途中から: 伸ばしている音だけ */
      var tv = CHAPTERS[ci].t + st, fade = clamp(tv / 1200 + .15) * clamp((DUR - tv) / 2500);   /* 映像の最初と最後で下げる */
      if (fade <= 0) return;
      var when = ac.currentTime + Math.max(0, mclock.secStart + st - mclock.mt) / speed / 1000;
      MA.note(ac, mclock.bus, n, when, Math.max(.05, (en - Math.max(st, lf)) / speed / 1000), fade, INSTX, st < lf); mclock.count = (mclock.count || 0) + 1;
    });
    mclock.fresh = false; mclock.upTo = to;
  }
  var duckOn = false;
  function syncDuck() { if (!duckG) return; var want = !!speaking && AUD.narration !== false; if (want === duckOn) return; duckOn = want;
    duckG.gain.setTargetAtTime(want ? (AUD.duck === undefined ? .5 : AUD.duck) : 1, ac.currentTime, want ? .08 : .4); }

  /* ---- 効果音: 場面の部品・重ねの層が H.sfx / sfxEv で出来事を知らせる。起動時に場面ごとに一度だけ集めて、時刻の表にする ---- */
  var EVC = null, EVOFF = 0, EVMUTE = 0, SFXQ = [], sfxCount = 0;
  function sfxEv(at, ev, o) { if (EVC && !EVMUTE) EVC.push({ at: at + EVOFF, ev: ev, o: o || {} }); }
  function sfxPlay(name, delay, o) {
    if (!ac || !audioOn || !sfxOn || !name) return; var r = SFXD[name]; if (!r) return; sfxCount++;
    o = o || {}; var when = ac.currentTime + Math.max(0, delay || 0);
    if (r.file) { var b = SFXBUF[name]; if (!b) return; var src = ac.createBufferSource(), g = ac.createGain(); src.buffer = b;
      src.playbackRate.value = Math.pow(2, (o.pitch || 0) / 12); g.gain.value = (o.v === undefined ? 1 : o.v) * (r.v || 1); src.connect(g); g.connect(sfxBus); src.start(when); return; }
    if (r.code) { var fn = SFXFN[name]; if (!fn) { try { fn = SFXFN[name] = new Function("ac", "out", "when", "A", "o", r.code); } catch (e) { fn = SFXFN[name] = function () {}; console.error("sfx code:", e); } }
      try { fn(ac, sfxBus, when, MA, o); } catch (e) { console.error("sfx code:", e); } return; }
    MA.play(ac, sfxBus, r, when, o);
  }
  function buildSfxQueue() {
    if (!SFXCFG || !MA) return;
    var KIT = SFXCFG.kit || {}, dens = SFXCFG.density || 2, raw = [];
    var tc = document.createElement("canvas"); tc.width = 8; tc.height = 8;
    var cv0 = cv, ctx0 = ctx; cv = tc; ctx = tc.getContext("2d"); thumbMode = true;
    SCENES.forEach(function (sc, k) {
      var ss = sc.s.sfx, auto = !(ss === false || (ss && !Array.isArray(ss) && ss.auto === false)), smap = ss && !Array.isArray(ss) && ss.map || {};
      var push = function (T, ev, o, name) { raw.push({ T: T, ev: ev, o: o || {}, name: name, map: smap, k: k }); };
      if (k > 0) { if (SCENES[k - 1].ci !== sc.ci) push(sc.t0 + 60, "chapter"); else { var tr = trOf(k); push(sc.t0 - (tr === "cut" ? 0 : 150), "tr." + tr); } }
      if (auto) {
        EVC = []; EVOFF = 0; EVMUTE = 0;
        try { ctx.setTransform(1, 0, 0, 1, 0, 0); (R[sc.s.type] || R.statement)(sc.s, Math.max(0, sc.d - 1), sc.d, sc.t0 + sc.d - 1); drawOverlays(sc.s, Math.max(0, sc.d - 1), sc.d); }
        catch (e) { console.warn("sfx collect:", e); }
        EVC.forEach(function (e) { push(sc.t0 + clamp(e.at, 0, sc.d), e.ev, e.o, SFXD[e.ev] ? e.ev : null); });
        EVC = null;
      }
      (Array.isArray(ss) ? ss : ss && ss.add || []).forEach(function (a) {
        push(sc.t0 + (a.ms !== undefined ? a.ms : (a.at || 0) * sc.d), a.event, { v: a.v, pitch: a.pitch, force: true }, a.name);
      });
    });
    cv = cv0; ctx = ctx0; thumbMode = false;
    var last = {};
    raw.forEach(function (r, i) {
      var name = r.name, v = 1, step = 0, lv = 1;
      if (!name) {
        var m = r.map[r.ev] !== undefined ? r.map[r.ev] : KIT[r.ev];
        if (!m) return;
        if (typeof m === "string") m = [m, 1, 0, 1];
        name = m[0]; v = m[1] === undefined ? 1 : m[1]; step = m[2] || 0; lv = m[3] || EVLV[r.ev] || 1;
        if (lv > dens && !r.o.force) return;
      }
      if (!SFXD[name]) return;
      var o = r.o, pitch = (o.pitch || 0) + (o.i !== undefined ? Math.min(12, o.i * step) : 0), q = { T: r.T, name: name, v: v * (o.v === undefined ? 1 : o.v), pitch: pitch, seed: i + 1 };
      if (o.n || o.dur) { var rep = Math.max(1, Math.min(40, o.n || Math.round(o.dur / 70))); q.rep = rep; q.gap = (o.dur || rep * 70) / rep / 1000; }
      if (last[name] !== undefined && Math.abs(last[name] - r.T) < 45) return;   /* 同じ音の重なり（同時に出る項目）は 1 つに */
      last[name] = r.T; SFXQ.push(q);
    });
    SFXQ.sort(function (a, b) { return a.T - b.T; });
  }
  var EVLV = { chapter: 1, hit: 1, click: 1, title: 1, outro: 1, countEnd: 1, message: 1, send: 1, toast: 1, notify: 1, done: 1, blocked: 1, reveal: 1, nav: 1, row: 3, working: 3 };
  function kitPlay(ev, delay) { var m = SFXCFG && SFXCFG.kit[ev]; if (m) sfxPlay(m[0], delay, { v: m[1] }); }
  var synth = "speechSynthesis" in window ? window.speechSynthesis : null, voice = null, LANG = SPEC.lang || "ja";
  function pickVoice() {
    if (!synth) return; var vs = synth.getVoices(), re = new RegExp("^" + LANG, "i");
    voice = vs.filter(function (v) { return re.test(v.lang) && /Kyoko|Nanami|Otoya|Google|Samantha|Aria|Natural/i.test(v.name); })[0] || vs.filter(function (v) { return re.test(v.lang); })[0] || null;
    var note = $("mv-voicenote"); if (note) note.hidden = !(started && audioOn && AUD.narration !== false && vs.length && !voice);
  }
  if (synth) { pickVoice(); synth.onvoiceschanged = pickVoice; }
  /* 読み上げ中の字幕。字幕の終わりに来ても読み終わっていなければ、動画をそこで待たせる（audio.wait: false で無効） */
  var speaking = null;
  function say(text, cue) {
    if (!synth || !audioOn || !voice || AUD.narration === false) return;
    try { synth.cancel(); var s = text.replace(/\*\*/g, "");
      /* 長い語から置き換える（「ts5250」より先に「5250」を置き換えない。JS は数字だけのキーを先に並べるため順に頼らない） */
      Object.keys(AUD.pronounce || {}).sort(function (a, b) { return b.length - a.length; }).forEach(function (k) { s = s.split(k).join(AUD.pronounce[k]); });
      var u = new SpeechSynthesisUtterance(s); u.voice = voice; u.lang = voice.lang; u.rate = Math.min(2.4, (AUD.rate || 1.1) * speed);
      var me = { u: u, cue: cue || null, started: performance.now(), maxMs: 4000 + s.length * 420 / u.rate };
      u.onend = u.onerror = function () { if (speaking === me) { speaking = null; root.classList.remove("mv-waiting"); } };
      speaking = me; synth.speak(u); } catch (e) {}
  }
  function hush() { speaking = null; root.classList.remove("mv-waiting"); try { if (synth) synth.cancel(); } catch (e) {} }
  function crossed(a, b, x) { return a < x && b >= x; }
  function onAdvance(a, b) {
    if (!audioOn) return;
    CUES.forEach(function (c) { if (crossed(a, b, c.a)) say(c.text, c); });
    if (b - a > 400) return;   /* 大きく飛んだ（シーク相当）ときは鳴らさない */
    SFXQ.forEach(function (q) { if (crossed(a, b, q.T)) sfxPlay(q.name, 0, q); });
  }

  /* ================= プレイヤー ================= */
  var store = { get: function (k, d) { try { var v = localStorage.getItem("mv:" + k); return v === null ? d : v; } catch (e) { return d; } },
                set: function (k, v) { try { localStorage.setItem("mv:" + k, v); } catch (e) {} } };
  var KIOSK = root.getAttribute("data-player") === "kiosk";
  var t = 0, playing = false, started = false, needsDraw = true, lastNow = 0, dragging = false;
  var SLIDES = root.getAttribute("data-player") === "slides", lastSave = 0;
  var POSKEY = "pos:" + location.pathname + ":" + (SPEC.title || "");
  var speed = parseFloat(store.get("speed", "1")) || 1;
  var captions = store.get("cc", "1") === "1";
  var audioOn = KIOSK ? false : store.get("audio", AUD.default === "off" ? "0" : "1") === "1";
  var SPEEDS = [0.5, 0.75, 1, 1.25, 1.5, 2];
  var fmt = function (ms) { var s = Math.floor(ms / 1000); return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0"); };

  function resize() { if (recording) return; var r = cv.getBoundingClientRect(), dpr = Math.min(window.devicePixelRatio || 1, 2); domScale = r.width / W;
    var w = Math.max(1, Math.round(r.width * dpr)), h = Math.max(1, Math.round(r.height * dpr));
    if (cv.width !== w || cv.height !== h) { cv.width = w; cv.height = h; } needsDraw = true; }

  function play() {
    if (t >= DUR) t = 0;
    ensureAudio(); if (ac && ac.state === "suspended") ac.resume().catch(function () {});
    musicReset();
    playing = true; started = true; lastNow = performance.now();
    try { document.dispatchEvent(new CustomEvent("mv-exclusive", { detail: root })); } catch (e) {}
    var rb0 = $("mv-resume"); if (rb0) rb0.hidden = true;
    var c = CUES.filter(function (c) { return t >= c.a && t < c.b; })[0];
    if (c && audioOn && (t - c.a) < (c.b - c.a) * .35) say(c.text, c);
    pickVoice(); syncUI(); poke();
  }
  function pause() { playing = false; hush(); musicStop(); cancelRec(); syncUI(); poke(); }
  function stop() { playing = false; hush(); musicStop(); cancelRec(); t = 0; started = false; needsDraw = true; syncUI(); poke(); }
  function toggle() { playing ? pause() : play(); }
  function seek(ms) { t = clamp(ms, 0, DUR); hush(); needsDraw = true; started = true; if (playing) musicReset(); if (t >= DUR) { playing = false; musicStop(); } syncUI(); }
  function chapterStep(dir) { var i = chapterAt(t), n = i + dir; if (dir < 0 && t - CHAPTERS[i].t > 2000) n = i;
    n = clamp(n, 0, CHAPTERS.length - 1); seek(CHAPTERS[n].t); ensureAudio(); kitPlay("nav"); }
  function setSpeed(v) { speed = v; var sel = $("mv-speed"); if (sel) sel.value = String(v); store.set("speed", String(v)); if (playing) { hush(); musicReset(); } }
  function setCaptions(on) { captions = on; store.set("cc", on ? "1" : "0"); var b = $("mv-cc"); if (b) b.setAttribute("aria-pressed", String(on)); syncCaption(true); }
  function setAudio(on) { audioOn = on; store.set("audio", on ? "1" : "0"); var b = $("mv-audio");
    if (b) { b.setAttribute("aria-pressed", String(on)); b.setAttribute("aria-label", on ? "音声をオフにする" : "音声をオンにする"); }
    if (ac && master) master.gain.setTargetAtTime(on ? 1 : 0, ac.currentTime, .05);
    if (!on) { hush(); musicStop(); } else if (playing) { ensureAudio(); musicReset(); } pickVoice(); }

  /* シークバー（チャプターごとの区切り） */
  var seekEl = $("mv-seek"), track = $("mv-track");
  CHAPTERS.forEach(function (c, i) { var seg = document.createElement("div"); seg.className = "mv-seg"; seg.style.flex = String(chLen(i)); seg.appendChild(document.createElement("i")); track.appendChild(seg); });
  var segs = [].slice.call(track.children);
  function posToMs(x) { var r = seekEl.getBoundingClientRect(); return clamp((x - r.left) / r.width) * DUR; }
  /* シークバーのプレビュー: 描画は時刻だけで決まるので、その時刻の 1 コマを小さな Canvas に描く */
  var thumbRaf = 0, thumbAt = 0;
  function renderThumb(ms) {
    var tc = $("mv-thumb"); if (!tc || !tc.getClientRects().length) return;
    var cv0 = cv, ctx0 = ctx; cv = tc; ctx = tc.getContext("2d"); thumbMode = true;
    try { draw(ms); } catch (e) {} finally { thumbMode = false; cv = cv0; ctx = ctx0; }
  }
  function showTip(x) { var r = seekEl.getBoundingClientRect(), ms = posToMs(x), tip = $("mv-tip"); tip.hidden = false;
    $("mv-tiplabel").innerHTML = "<b>" + fmt(ms) + "</b>" + esc(CHAPTERS[chapterAt(ms)].name);
    thumbAt = ms; if (!thumbRaf) thumbRaf = requestAnimationFrame(function () { thumbRaf = 0; renderThumb(thumbAt); });
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
    if (e.target.tagName === "SELECT" || e.target.tagName === "INPUT" || e.altKey || e.ctrlKey || e.metaKey) return;
    var k = e.key, done = true;
    if (k === " " || k === "k" || k === "K") { if (e.target.tagName === "BUTTON" && k === " ") done = false; else toggle(); }
    else if (k === "s" || k === "S") stop();
    else if (k === "ArrowLeft") seek(t - 5000); else if (k === "ArrowRight") seek(t + 5000);
    else if (k === "[") chapterStep(-1); else if (k === "]") chapterStep(1);
    else if (k === "c" || k === "C") setCaptions(!captions); else if (k === "m" || k === "M") setAudio(!audioOn);
    else if (k === "f" || k === "F") $("mv-fs").click();
    else if (/^[0-9]$/.test(k)) seek(DUR * (+k) / 10);
    else if (k === "j" || k === "J") seek(t - 10000);
    else if (k === "l" || k === "L") seek(t + 10000);
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
    var big = $("mv-big");
    if (big && SLIDES) {
      var ci0 = chapterAt(t), atStart = t > 0 && t < DUR && Math.abs(t - CHAPTERS[ci0].t) < 50;
      var lab = !started || t === 0 ? "再生" : t >= DUR ? "もう一度" : atStart ? "次へ：" + CHAPTERS[ci0].name : "続きを再生";
      big.hidden = playing; big.setAttribute("aria-label", lab); var bl = big.querySelector(".mv-biglabel"); if (bl) bl.textContent = lab;
    } else if (big) { big.hidden = playing || (started && t > 0 && t < DUR); big.setAttribute("aria-label", t >= DUR ? "もう一度再生" : "再生"); }
    root.classList.toggle("mv-playing", playing);
    $("mv-time").innerHTML = "<b>" + fmt(t) + "</b> / " + fmt(DUR);
    var ci = chapterAt(t);
    if (ci !== lastChap) { lastChap = ci; var cn = $("mv-chapname"); if (cn) cn.textContent = CHAPTERS[ci].name;
      [].forEach.call(root.querySelectorAll('[data-mv="chapmenu"] button, [data-mv="chaplist"] button'), function (b) { b.setAttribute("aria-current", String(+b.dataset.i === ci)); });
      var cur = list && list.querySelector('[aria-current="true"]'); if (cur && root.getAttribute("data-player") === "presenter" && cur.scrollIntoView) cur.scrollIntoView({ block: "nearest" }); }
    if (tlist) {
      var cc = -1; CUES.forEach(function (c, i) { if (t >= c.a) cc = i; });
      if (cc !== lastCue) { lastCue = cc; [].forEach.call(tlist.querySelectorAll("button"), function (b) { b.setAttribute("aria-current", String(+b.dataset.i === cc)); });
        var cb = tlist.querySelector('[aria-current="true"]'), box = tlist.parentNode;
        if (cb && box && box.scrollHeight > box.clientHeight) { var r1 = cb.getBoundingClientRect(), r2 = box.getBoundingClientRect(); if (r1.top < r2.top || r1.bottom > r2.bottom) box.scrollTop += r1.top - r2.top - 60; } }
    }
    segs.forEach(function (s, i) { s.firstChild.style.width = (clamp((t - CHAPTERS[i].t) / chLen(i)) * 100) + "%"; });
    $("mv-knob").style.left = (t / DUR * 100) + "%";
    seekEl.setAttribute("aria-valuemax", String(Math.round(DUR / 1000)));
    seekEl.setAttribute("aria-valuenow", String(Math.round(t / 1000)));
    seekEl.setAttribute("aria-valuetext", Math.floor(t / 60000) + " 分 " + (Math.floor(t / 1000) % 60) + " 秒、" + CHAPTERS[ci].name);
    syncCaption(false);
  }
  function frame(now) {
    if (playing) {
      var nt = Math.min(DUR, t + Math.min(100, now - lastNow) * speed);
      /* 読み上げが字幕の終わりまでに終わらなければ、読み終わるまで字幕の終わりの手前で待つ（終わりの知らせが来ない時の上限つき） */
      if (speaking && speaking.cue && AUD.wait !== false) {
        if (performance.now() - speaking.started > speaking.maxMs) { speaking = null; root.classList.remove("mv-waiting"); }
        else if (nt > speaking.cue.b - 60) { nt = Math.max(t, speaking.cue.b - 60); root.classList.add("mv-waiting"); }
      }
      /* slides: 章の終わりで止まる（「次へ」で続きを再生） */
      var slideStop = false;
      if (SLIDES && !recording && nt < DUR && chapterAt(nt) > chapterAt(t)) { nt = CHAPTERS[chapterAt(nt)].t; slideStop = true; }
      var prev = t; t = nt; onAdvance(prev, t); musicTick(Math.min(100, now - lastNow)); syncDuck();
      if (now - lastSave > 2000) { lastSave = now; store.set(POSKEY, String(t >= DUR - 3000 ? 0 : Math.round(t))); }
      if (slideStop) { playing = false; hush(); musicStop(); }
      if (t >= DUR) { if (KIOSK && !recording) { t = 0; hush(); musicReset(); } else { playing = false; musicStop(); if (recording) finishRec(); } }
      syncUI(); needsDraw = true;
    }
    lastNow = now;
    if (needsDraw) { draw(started || t > 0 ? t : (SPEC.poster !== undefined ? SPEC.poster : Math.min(4300, DUR))); needsDraw = playing; }
    requestAnimationFrame(frame);
  }

  /* 文字起こし（theater で横に出す。クリックでその位置へ・検索） */
  var tlist = $("mv-tlist"), tsearch = $("mv-tsearch"), lastCue = -2;
  if (tlist) {
    CUES.forEach(function (c, i) {
      var li = document.createElement("li"), b = document.createElement("button"); b.type = "button"; b.dataset.i = i;
      b.innerHTML = '<span class="t">' + fmt(c.a) + "</span><span>" + esc(c.text.replace(/\*\*/g, "")) + "</span>";
      b.addEventListener("click", function () { seek(c.a); if (!playing) play(); }); li.appendChild(b); tlist.appendChild(li);
    });
    if (tsearch) tsearch.addEventListener("input", function () { var q = tsearch.value.trim().toLowerCase();
      [].forEach.call(tlist.children, function (li) { li.hidden = !!q && li.textContent.toLowerCase().indexOf(q) < 0; }); });
  }
  /* 続きから再生（このブラウザに位置を覚える） */
  var rb = $("mv-resume"), savedPos = parseFloat(store.get(POSKEY, "0")) || 0;
  if (rb && !KIOSK && savedPos > 5000 && savedPos < DUR - 5000) {
    rb.hidden = false; rb.textContent = "▶ 前回の続き（" + fmt(savedPos) + "）から再生";
    rb.addEventListener("click", function (e) { e.stopPropagation(); rb.hidden = true; seek(savedPos); play(); focusPlayer(); });
  }
  /* 設定（字幕の大きさ・小窓・保存） */
  var setBtn = $("mv-setbtn"), setPanel = $("mv-setpanel");
  function closeSet(refocus) { if (!setPanel || setPanel.hidden) return; setPanel.hidden = true; setBtn.setAttribute("aria-expanded", "false"); if (refocus) setBtn.focus(); }
  function setCap(v) { root.setAttribute("data-cap", v); store.set("cap", v);
    [].forEach.call(root.querySelectorAll("button[data-cap]"), function (b) { b.setAttribute("aria-pressed", String(b.getAttribute("data-cap") === v)); }); }
  if (setBtn && setPanel) {
    setBtn.addEventListener("click", function () { var o = setPanel.hidden; setPanel.hidden = !o; setBtn.setAttribute("aria-expanded", String(o)); if (o) { var f = setPanel.querySelector("button"); if (f) f.focus(); } });
    setPanel.addEventListener("keydown", function (e) { if (e.key === "Escape") { closeSet(true); e.preventDefault(); } e.stopPropagation(); });
    [].forEach.call(setPanel.querySelectorAll("button[data-cap]"), function (b) { b.addEventListener("click", function () { setCap(b.getAttribute("data-cap")); }); });
    document.addEventListener("pointerdown", function (e) { if (!setPanel.hidden && !e.target.closest('[data-mv="setpanel"]') && !e.target.closest('[data-mv="setbtn"]')) closeSet(false); });
  }
  setCap(store.get("cap", "m"));
  function setMus(on) { musicOn = on; store.set("mus", on ? "1" : "0");
    [].forEach.call(root.querySelectorAll("button[data-mus]"), function (b) { b.setAttribute("aria-pressed", String((b.getAttribute("data-mus") === "1") === on)); });
    if (!on) musicStop(); else if (playing) musicReset(); }
  function setSfx(on) { sfxOn = on; store.set("sfx", on ? "1" : "0");
    [].forEach.call(root.querySelectorAll("button[data-sfx]"), function (b) { b.setAttribute("aria-pressed", String((b.getAttribute("data-sfx") === "1") === on)); }); }
  [].forEach.call(root.querySelectorAll("button[data-mus]"), function (b) { b.addEventListener("click", function () { setMus(b.getAttribute("data-mus") === "1"); }); });
  [].forEach.call(root.querySelectorAll("button[data-sfx]"), function (b) { b.addEventListener("click", function () { setSfx(b.getAttribute("data-sfx") === "1"); }); });
  setMus(store.get("mus", "1") === "1"); setSfx(store.get("sfx", "1") === "1");
  var pipBtn = $("mv-pip"), pipVideo = null;
  if (pipBtn) {
    if (!(document.pictureInPictureEnabled && cv.captureStream)) pipBtn.hidden = true;
    pipBtn.addEventListener("click", function () {
      closeSet(false);
      try {
        if (document.pictureInPictureElement) { document.exitPictureInPicture(); return; }
        pipVideo = pipVideo || document.createElement("video"); pipVideo.muted = true; pipVideo.srcObject = cv.captureStream(30);
        pipVideo.play().then(function () { return pipVideo.requestPictureInPicture(); }).catch(function (e) { console.warn("pip:", e); });
        if (!playing) play();
      } catch (e) { console.warn("pip:", e); }
    });
  }
  /* 動画ファイル（WebM）で保存: 最初から 1 倍速で再生しながら Canvas を録画する（字幕は焼き込み。読み上げの声は録れない） */
  var recBtn = $("mv-rec"), recBadge = $("mv-recbadge");
  if (recBtn && !(window.MediaRecorder && cv.captureStream)) recBtn.hidden = true;
  function startRec() {
    closeSet(false);
    try {
      cv.width = 1280; cv.height = 720;
      var stream = cv.captureStream(30);
      ensureAudio();
      if (ac && master && ac.createMediaStreamDestination) { var dest = ac.createMediaStreamDestination(); master.connect(dest); dest.stream.getAudioTracks().forEach(function (tr) { stream.addTrack(tr); }); }
      var mime = window.MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported("video/webm;codecs=vp9") ? "video/webm;codecs=vp9" : "video/webm";
      var mr = new MediaRecorder(stream, { mimeType: mime }), chunks = [];
      mr.ondataavailable = function (e) { if (e.data && e.data.size) chunks.push(e.data); };
      var rec = { mr: mr, cancel: false, speed: speed };
      mr.onstop = function () {
        if (recBadge) recBadge.hidden = true;
        if (!rec.cancel) { var blob = new Blob(chunks, { type: "video/webm" }), a = document.createElement("a"); a.href = URL.createObjectURL(blob);
          a.download = (SPEC.title || "video").replace(/[\\/:*?"<>|]/g, "_") + ".webm"; document.body.appendChild(a); a.click(); a.remove();
          setTimeout(function () { URL.revokeObjectURL(a.href); }, 60000); }
      };
      setSpeed(1); t = 0; started = true; hush();
      recording = rec; if (recBadge) recBadge.hidden = false;
      mr.start(1000); play(); focusPlayer();
    } catch (e) { console.warn("rec:", e); recording = null; resize(); }
  }
  function finishRec() { var r = recording; if (!r) return; recording = null; try { r.mr.stop(); } catch (e) {} setSpeed(r.speed); resize(); }
  function cancelRec() { if (!recording) return; recording.cancel = true; finishRec(); }
  if (recBtn) recBtn.addEventListener("click", function () { if (recording) cancelRec(); else startRec(); });

  /* 起動 */
  var sel = $("mv-speed"); if (sel) sel.value = String(speed);
  var ccb = $("mv-cc"); if (ccb) ccb.setAttribute("aria-pressed", String(captions));
  var aub = $("mv-audio"); if (aub) { aub.setAttribute("aria-pressed", String(audioOn)); aub.setAttribute("aria-label", audioOn ? "音声をオフにする" : "音声をオンにする"); }
  SCENES.forEach(function (sc) { if (sc.s.type === "image" && sc.s.src && !IMGS[sc.s.src]) { var im = new Image(); im.onload = function () { needsDraw = true; }; im.src = sc.s.src; IMGS[sc.s.src] = im; } });
  try { buildSfxQueue(); } catch (e) { console.warn("sfx:", e); }
  new ResizeObserver(resize).observe(cv); resize(); syncUI(); requestAnimationFrame(frame);
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(function () { needsDraw = true; });
  if (KIOSK && !(window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches)) { started = true; playing = true; lastNow = performance.now(); syncUI(); }
  /* 同じページのほかのプレイヤーを再生したら、こちらは止める（読み上げの声は 1 つしか無いため） */
  document.addEventListener("mv-exclusive", function (e) { if (e.detail !== root && playing) pause(); });
  var api = { seek: seek, play: play, pause: pause, get t() { return t; }, get speaking() { return !!speaking; }, DUR: DUR, CHAPTERS: CHAPTERS, CUES: CUES, SFX: SFXQ,
              get audio() { return { ctx: ac, mt: mclock.mt, section: mclock.sec, notes: mclock.count || 0, sfx: sfxCount }; } };
  root.__mv = api; window.__MV__ = api;
  return api;
};
/* ページの中のプレイヤーを起動する（台本と配色はプレイヤーの中の JSON から読む。同じ HTML を 2 度読み込んでも 1 度だけ） */
(function () {
  function boot() {
    [].forEach.call(document.querySelectorAll(".mv-player:not([data-mv-ready])"), function (el) {
      var sp = el.querySelector("script[data-mv-spec]"), th = el.querySelector("script[data-mv-theme]");
      if (!sp || !th) return;
      el.setAttribute("data-mv-ready", "");
      try { window.MotionVideo(el, JSON.parse(sp.textContent), JSON.parse(th.textContent)); } catch (e) { console.error("motion-video:", e); }
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot); else boot();
})();
