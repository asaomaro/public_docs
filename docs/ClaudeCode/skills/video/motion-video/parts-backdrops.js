/* motion-video parts-backdrops — ループする動く背景（台本・章・場面の bg に名前を書く）。
 * どれも「周期の中の位置 u（0..1）」だけで描く。u に掛ける回数を整数にしているので、周期の終わりと始まりが必ずつながる。
 * 色は配色（C）から取る。足すときは def(名前, 周期 ms, function (u, o) {...}) を書き、build.py の BACKDROPS に説明を足す。 */
if (!window.__mvPartsBackdrops) { window.__mvPartsBackdrops = 1; (window.MotionVideoParts = window.MotionVideoParts || []).push(function (R, X) {
  "use strict";
  var C = X.C, F = X.F, W = X.W, H = X.H, g = X.g, clamp = X.clamp, B = X.backdrops, PI = Math.PI, PI2 = Math.PI * 2;
  var ctx = null, GA = 1, CACHE = {};
  function hex(c) { var m = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(String(c)); if (!m) return null; var h = m[1]; if (h.length === 3) h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
    return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)]; }
  function rgba(c, a) { var h = hex(c); return h ? "rgba(" + h.join(",") + "," + a + ")" : a === 0 ? "rgba(0,0,0,0)" : c; }
  var b0 = hex(C.bg0) || [0, 0, 0], DARK = (b0[0] * .299 + b0[1] * .587 + b0[2] * .114) < 128;
  var LITE = DARK ? C.ink : C.muted;   /* 星・雪・雨の色（暗い地では明るく、明るい地では灰色） */
  function AC(i) { return C.accents[((i % C.accents.length) + C.accents.length) % C.accents.length]; }
  function c1(o) { return o.color ? (C[o.color] || o.color) : C.accent2; }   /* 主な色（bg の color で替えられる） */
  function c2(o) { return o.color ? (C[o.color] || o.color) : C.accent; }
  function al(a) { ctx.globalAlpha = GA * clamp(a); }
  function S(u, n, ph) { return Math.sin(PI2 * n * u + (ph || 0)); }   /* n は整数（周期の中で n 回） */
  function fr(v) { return v - Math.floor(v); }
  function mod(v, m) { return ((v % m) + m) % m; }
  function base() { var gr = ctx.createLinearGradient(0, 0, 0, H); gr.addColorStop(0, C.bg1); gr.addColorStop(1, C.bg0); ctx.fillStyle = gr; al(1); ctx.fillRect(0, 0, W, H); }
  function glow(x, y, r, c, a) { var gr = ctx.createRadialGradient(x, y, 0, x, y, r); gr.addColorStop(0, rgba(c, 1)); gr.addColorStop(1, rgba(c, 0)); ctx.fillStyle = gr; al(a); ctx.fillRect(x - r, y - r, r * 2, r * 2); }
  function dot(x, y, r) { ctx.beginPath(); ctx.arc(x, y, Math.max(.1, r), 0, PI2); ctx.fill(); }
  function line(x0, y0, x1, y1) { ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); ctx.stroke(); }
  function seeded(key, seed, n, fn) { if (!CACHE[key]) { var r = X.rand(seed), a = []; for (var i = 0; i < n; i++) a.push(fn(r, i)); CACHE[key] = a; } return CACHE[key]; }
  function int(r, a, b) { return a + Math.floor(r() * (b - a + 1)); }
  function def(name, period, fn) { B[name] = { period: period, draw: function (u, o) { ctx = g(); GA = ctx.globalAlpha; base(); fn(u, o || {}); } }; }

  /* ---- 色と光 ---- */
  def("flow", 20000, function (u) {
    for (var i = 0; i < 5; i++) glow(960 + 760 * S(u, 1, i * 1.3), 540 + 400 * S(u, i % 2 ? 2 : 1, i * 2.1 + 1), 640 + 120 * S(u, 2, i), AC(i), .2);
  });
  def("aurora", 16000, function (u) {
    for (var i = 0; i < 4; i++) { var y0 = 240 + i * 110, c = AC(i + 1), d = i % 2 ? -1 : 1, x;
      var gr = ctx.createLinearGradient(0, y0 - 240, 0, y0 + 300); gr.addColorStop(0, rgba(c, 0)); gr.addColorStop(.42, rgba(c, 1)); gr.addColorStop(1, rgba(c, 0));
      ctx.fillStyle = gr; al(.2 - i * .025); ctx.beginPath();
      for (x = 0; x <= W; x += 40) ctx.lineTo(x, y0 - 200 + 70 * Math.sin(x / 310 + d * PI2 * u + i) + 40 * Math.sin(x / 170 + PI2 * 2 * u + i * 2));
      for (x = W; x >= 0; x -= 40) ctx.lineTo(x, y0 + 240 + 50 * Math.sin(x / 260 + PI2 * u + i));
      ctx.closePath(); ctx.fill(); }
  });
  def("bokeh", 24000, function (u) {
    seeded("bokeh", 31, 20, function (r) { return { x: r() * W, y: r() * H, rad: 80 + r() * 150, ax: 60 + r() * 160, ay: 40 + r() * 110, n: int(r, 1, 2), m: int(r, 1, 2), p: r() * PI2, q: r() * PI2, c: int(r, 0, 3) }; })
      .forEach(function (p) { var x = p.x + p.ax * S(u, p.n, p.p), y = p.y + p.ay * S(u, p.m, p.q);
        glow(x, y, p.rad, AC(p.c), .13 + .06 * S(u, 2, p.p)); ctx.strokeStyle = AC(p.c); ctx.lineWidth = 2; al(.08); ctx.beginPath(); ctx.arc(x, y, p.rad * .62, 0, PI2); ctx.stroke(); });
  });
  def("rays", 14000, function (u, o) {
    for (var i = 0; i < 9; i++) { var a = PI / 2 + (i - 4) * .17 + .08 * S(u, 1, i * 1.1), hw = .04 + .018 * S(u, 2, i), L = 1600, ox = 960, oy = -220;
      var gr = ctx.createLinearGradient(ox, oy, ox + Math.cos(a) * L, oy + Math.sin(a) * L); gr.addColorStop(0, rgba(i % 2 ? c2(o) : c1(o), 1)); gr.addColorStop(1, rgba(c1(o), 0));
      ctx.fillStyle = gr; al(.13 + .05 * S(u, 1, i * 2)); ctx.beginPath(); ctx.moveTo(ox, oy); ctx.lineTo(ox + Math.cos(a - hw) * L, oy + Math.sin(a - hw) * L); ctx.lineTo(ox + Math.cos(a + hw) * L, oy + Math.sin(a + hw) * L); ctx.closePath(); ctx.fill(); }
  });
  def("spotlights", 10000, function (u) {
    [200, 700, 1220, 1720].forEach(function (ox, i) { var a = -PI / 2 + .42 * S(u, 1, i * 1.6), hw = .09, L = 1500, oy = H + 60;
      var gr = ctx.createLinearGradient(ox, oy, ox + Math.cos(a) * L, oy + Math.sin(a) * L); gr.addColorStop(0, rgba(AC(i), 1)); gr.addColorStop(1, rgba(AC(i), 0));
      ctx.fillStyle = gr; al(.17); ctx.beginPath(); ctx.moveTo(ox, oy); ctx.lineTo(ox + Math.cos(a - hw) * L, oy + Math.sin(a - hw) * L); ctx.lineTo(ox + Math.cos(a + hw) * L, oy + Math.sin(a + hw) * L); ctx.closePath(); ctx.fill(); });
  });
  def("blobs", 16000, function (u) {
    [[300, 230, 330], [1660, 300, 300], [1520, 900, 340], [340, 900, 280]].forEach(function (q, i) {
      ctx.beginPath(); for (var k = 0; k <= 64; k++) { var th = k / 64 * PI2, r = q[2] * (1 + .12 * Math.sin(3 * th + PI2 * u + i) + .08 * Math.sin(5 * th - PI2 * 2 * u + i * 2));
        ctx.lineTo(q[0] + 40 * S(u, 1, i) + Math.cos(th) * r, q[1] + 30 * S(u, 1, i + 2) + Math.sin(th) * r); }
      ctx.closePath(); ctx.fillStyle = AC(i); al(.15); ctx.fill(); });
  });

  /* ---- 波と線 ---- */
  def("waves", 12000, function (u, o) {
    for (var i = 0; i < 5; i++) { var y0 = 610 + i * 95, d = i % 2 ? -1 : 1;
      ctx.beginPath(); ctx.moveTo(0, H); for (var x = 0; x <= W; x += 24) ctx.lineTo(x, y0 + (34 - i * 3) * Math.sin(x / (260 + i * 40) + d * PI2 * u + i * 1.7) + 14 * Math.sin(x / 97 + PI2 * 2 * u + i));
      ctx.lineTo(W, H); ctx.closePath(); ctx.fillStyle = i % 2 ? c2(o) : c1(o); al(.07 + i * .025); ctx.fill(); }
  });
  def("ribbons", 14000, function (u, o) {
    ctx.lineWidth = 2;
    for (var i = 0; i < 16; i++) { ctx.beginPath();
      for (var x = -20; x <= W + 20; x += 30) ctx.lineTo(x, 560 + (i - 7.5) * 16 * (1 + .6 * Math.sin(x / 420 + PI2 * u)) + 150 * Math.sin(x / 520 + PI2 * u + i * .09) + 60 * Math.sin(x / 230 - PI2 * u + i * .05));
      ctx.strokeStyle = i % 2 ? c2(o) : c1(o); al(.1 + .2 * i / 16); ctx.stroke(); }
  });
  def("ridges", 10000, function (u, o) {
    ctx.lineWidth = 2.5; ctx.strokeStyle = c1(o);
    for (var i = 0; i < 17; i++) { var y0 = 250 + i * 46, d = i % 2 ? 1 : -1, pts = [], x;
      for (x = 0; x <= W; x += 16) { var bump = Math.exp(-Math.pow((x - 960) / 420, 2));
        pts.push([x, y0 - bump * 34 * (1 + Math.sin(x / 58 + d * PI2 * u + i * 1.9)) * (.6 + .4 * Math.sin(x / 143 + PI2 * u + i))]); }
      ctx.beginPath(); ctx.moveTo(0, y0 + 46); pts.forEach(function (p) { ctx.lineTo(p[0], p[1]); }); ctx.lineTo(W, y0 + 46); ctx.closePath(); ctx.fillStyle = C.bg0; al(.9); ctx.fill();
      ctx.beginPath(); pts.forEach(function (p) { ctx.lineTo(p[0], p[1]); }); al(.16 + .22 * i / 17); ctx.stroke(); }
  });
  def("ocean", 10000, function (u, o) {
    var hy = 470; glow(960, hy, 460, C.warn, .28); ctx.strokeStyle = c1(o); al(.35); ctx.lineWidth = 2; line(0, hy, W, hy);
    for (var i = 1; i <= 24; i++) { var z = i / 24, y = hy + (H - hy) * Math.pow(z, 1.8), amp = 2 + 11 * z, wl = 60 + 240 * z, d = i % 2 ? 1 : -1;
      ctx.beginPath(); for (var x = 0; x <= W; x += 20) ctx.lineTo(x, y + amp * Math.sin(x / wl + d * PI2 * u + i * 1.3)); ctx.lineWidth = 1 + 2 * z; al(.1 + .3 * z); ctx.stroke(); }
    ctx.fillStyle = C.warn; for (var k = 0; k < 16; k++) { var zz = (k + .5) / 16, yy = hy + (H - hy) * Math.pow(zz, 1.8), ww = (40 + 300 * zz) * (.6 + .4 * S(u, 2 + k % 3, k * 1.7));
      al(.16 * (1 - zz * .5)); ctx.fillRect(960 - ww / 2 + 30 * S(u, 1, k), yy - 2, ww, 3 + 3 * zz); }
  });
  def("stripes", 6000, function (u, o) {
    ctx.translate(960, 540); ctx.rotate(-PI / 4); ctx.fillStyle = c1(o); al(.06);
    for (var x = -1400 + u * 160; x < 1400; x += 160) ctx.fillRect(x, -1400, 80, 2800);
  });
  def("sunburst", 12000, function (u, o) {
    var cx = 960, cy = 620, n = 24, rot = u * PI2 / 12; ctx.fillStyle = c2(o); al(.07);
    for (var i = 0; i < n; i += 2) { var a0 = rot + i * PI2 / n, a1 = a0 + PI2 / n; ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(cx + Math.cos(a0) * 1500, cy + Math.sin(a0) * 1500); ctx.lineTo(cx + Math.cos(a1) * 1500, cy + Math.sin(a1) * 1500); ctx.closePath(); ctx.fill(); }
    glow(cx, cy, 520, c2(o), .2);
  });

  /* ---- 空と粒 ---- */
  def("stars", 60000, function (u) {
    glow(1500, 200, 900, C.accent2, .1); ctx.fillStyle = LITE;
    seeded("stars", 3, 240, function (r) { return { x: r() * W, y: r() * H, s: .8 + r() * 2, p: r() * PI2, n: int(r, 12, 36), d: int(r, 1, 2) }; })
      .forEach(function (p) { al(.2 + .6 * (.5 + .5 * S(u, p.n, p.p))); dot(mod(p.x - u * W * p.d, W), p.y, p.s); });
  });
  def("meteors", 12000, function (u) {
    ctx.fillStyle = LITE;
    seeded("meteors-s", 5, 150, function (r) { return { x: r() * W, y: r() * H, s: .7 + r() * 1.8, p: r() * PI2, n: int(r, 3, 9) }; })
      .forEach(function (p) { al(.2 + .5 * (.5 + .5 * S(u, p.n, p.p))); dot(p.x, p.y, p.s); });
    ctx.lineCap = "round";
    seeded("meteors-m", 8, 7, function (r, i) { return { x: 300 + r() * 1700, y: -60 + r() * 420, off: i / 7 + r() * .05, len: 180 + r() * 160 }; })
      .forEach(function (p) { var k = fr(u + p.off) / .1; if (k >= 1) return;
        var x = p.x - k * 760, y = p.y + k * 430, dx = .87 * p.len, dy = -.49 * p.len, gr = ctx.createLinearGradient(x, y, x + dx, y + dy);
        gr.addColorStop(0, rgba(LITE, 1)); gr.addColorStop(1, rgba(LITE, 0)); ctx.strokeStyle = gr; ctx.lineWidth = 3; al(Math.sin(PI * k) * .9); line(x, y, x + dx, y + dy); });
  });
  def("warp", 6000, function (u) {
    glow(960, 540, 700, C.accent2, .12); ctx.strokeStyle = LITE; ctx.lineCap = "round";
    seeded("warp", 9, 220, function (r) { return { a: r() * PI2, off: r(), n: int(r, 1, 3), w: .6 + r() * 2 }; })
      .forEach(function (p) { var z = fr(u * p.n + p.off), r1 = 40 + z * z * 1250, r0 = 40 + Math.pow(Math.max(0, z - .06), 2) * 1250, cs = Math.cos(p.a), sn = Math.sin(p.a);
        al(z * .8); ctx.lineWidth = p.w * (.5 + z * 1.5); line(960 + cs * r0, 540 + sn * r0, 960 + cs * r1, 540 + sn * r1); });
  });
  def("galaxy", 24000, function (u) {
    glow(960, 540, 520, C.accent, .22); ctx.translate(960, 540); ctx.rotate(-.3); ctx.scale(1, .55);
    seeded("galaxy", 14, 100, function (r) { var t = Math.pow(r(), .7); return { t: t, j: (r() - .5) * (.25 + t * .5), s: 1 + r() * 3.4, c: int(r, 0, 3) }; })
      .forEach(function (p) { for (var arm = 0; arm < 3; arm++) { var a = arm * PI2 / 3 + p.t * 5 + p.j + u * PI2 / 3, rad = 40 + p.t * 760;   /* 3 本の腕は同じ形（1/3 回って元に重なる） */
        ctx.fillStyle = p.c ? AC(p.c) : LITE; al(.3 + .4 * (1 - p.t)); dot(Math.cos(a) * rad, Math.sin(a) * rad, p.s); } });
  });
  function fall(key, seed, n, u, o, draw) {
    seeded(key, seed, n, function (r) { return { x: r() * (W + 200) - 100, y: r() * (H + 160), s: r(), n: int(r, 1, o.maxLaps || 2), p: r() * PI2, q: r() * PI2, c: int(r, 0, 3), k: int(r, 1, 3) }; })
      .forEach(function (p) { var y = mod(p.y + (o.up ? -1 : 1) * u * p.n * (H + 160), H + 160) - 80; draw(p, p.x + (o.sway || 0) * S(u, p.k, p.p) + (o.slant || 0) * y, y); });
  }
  def("rise", 20000, function (u) {
    fall("rise", 21, 90, u, { up: 1, sway: 30, maxLaps: 3 }, function (p, x, y) { ctx.fillStyle = AC(p.c); al(.18 + .3 * (.5 + .5 * S(u, p.n * 2, p.q))); dot(x, y, 2 + p.s * 5); });
  });
  def("snow", 16000, function (u) {
    ctx.fillStyle = LITE; fall("snow", 22, 130, u, { sway: 40 }, function (p, x, y) { al(.25 + .45 * p.s); dot(x, y, 1.5 + p.s * 4.5); });
  });
  def("rain", 4000, function (u, o) {
    ctx.strokeStyle = c1(o); ctx.lineCap = "round"; ctx.lineWidth = 2;
    seeded("rain", 23, 150, function (r) { return { x: r() * (W + 400), y: r() * (H + 200), n: int(r, 2, 4), l: 40 + r() * 60, a: .12 + r() * .25 }; })
      .forEach(function (p) { var y = mod(p.y + u * p.n * (H + 200), H + 200) - 100, x = p.x - y * .18; al(p.a); line(x, y, x - p.l * .18, y + p.l); });
  });
  def("bubbles", 18000, function (u, o) {
    ctx.lineWidth = 2; ctx.strokeStyle = c1(o); ctx.fillStyle = c1(o);
    fall("bubbles", 24, 44, u, { up: 1, sway: 26 }, function (p, x, y) { var r = 10 + p.s * 38; ctx.beginPath(); ctx.arc(x, y, r, 0, PI2); al(.05); ctx.fill(); al(.32); ctx.stroke();
      ctx.beginPath(); ctx.arc(x, y, r * .68, -2.4, -1.5); al(.4); ctx.stroke(); });
  });
  def("fireflies", 20000, function (u) {
    seeded("fireflies", 25, 42, function (r) { return { x: r() * W, y: r() * H, a: int(r, 1, 3), b: int(r, 1, 3), n: int(r, 3, 8), p: r() * PI2, q: r() * PI2 }; })
      .forEach(function (p) { var x = p.x + 130 * S(u, p.a, p.p) + 50 * S(u, p.a + 1, p.q), y = p.y + 90 * S(u, p.b, p.q) + 40 * S(u, p.b + 2, p.p), k = Math.pow(Math.max(0, S(u, p.n, p.p)), 2);
        if (k < .02) return; glow(x, y, 30, C.warn, k * .7); ctx.fillStyle = C.warn; al(k); dot(x, y, 2.6); });
  });
  def("petals", 16000, function (u, o) {
    ctx.fillStyle = o.color ? (C[o.color] || o.color) : "#f6b0c6";
    fall("petals", 26, 64, u, { sway: 90, slant: -.12 }, function (p, x, y) { var s = 9 + p.s * 12; ctx.save(); ctx.translate(x, y); ctx.rotate(PI2 * (u * p.k + p.s)); ctx.scale(1, .25 + .75 * Math.abs(Math.cos(PI2 * u * (p.k + 1) + p.q)));
      al(.45 + .35 * p.s); ctx.beginPath(); ctx.ellipse(0, 0, s, s * .55, 0, 0, PI2); ctx.fill(); ctx.restore(); });
  });
  def("confetti", 12000, function (u) {
    fall("confetti", 27, 96, u, { sway: 60 }, function (p, x, y) { var s = 8 + p.s * 10; ctx.save(); ctx.translate(x, y); ctx.rotate(PI2 * (u * p.k + p.s)); ctx.scale(1, Math.cos(PI2 * u * (p.k + 2) + p.q));
      ctx.fillStyle = AC(p.c); al(.55); ctx.fillRect(-s, -s * .4, s * 2, s * .8); ctx.restore(); });
  });
  def("sparkles", 8000, function (u) {
    seeded("sparkles", 28, 48, function (r) { return { x: r() * W, y: r() * H, s: 10 + r() * 24, n: int(r, 1, 4), p: r() * PI2, c: r() < .5 }; })
      .forEach(function (p) { var k = Math.pow(Math.max(0, S(u, p.n, p.p)), 2); if (k < .02) return; var s = p.s * k, t = s * .18;
        ctx.fillStyle = p.c ? C.warn : LITE; al(.75 * k); ctx.beginPath(); ctx.moveTo(p.x, p.y - s); ctx.lineTo(p.x + t, p.y - t); ctx.lineTo(p.x + s, p.y); ctx.lineTo(p.x + t, p.y + t);
        ctx.lineTo(p.x, p.y + s); ctx.lineTo(p.x - t, p.y + t); ctx.lineTo(p.x - s, p.y); ctx.lineTo(p.x - t, p.y - t); ctx.closePath(); ctx.fill(); });
  });
  def("clouds", 60000, function (u) {
    glow(960, -100, 1100, C.accent2, .14); ctx.fillStyle = C.panel2;
    seeded("clouds", 29, 9, function (r) { var bl = []; for (var k = 0; k < 6; k++) bl.push([(k - 2.5) * 62 + (r() - .5) * 30, (r() - .5) * 36, 52 + r() * 40]);
      return { x: r() * (W + 700), y: 110 + r() * 760, sc: .7 + r() * 1.1, n: int(r, 1, 2), bl: bl }; })
      .forEach(function (p) { var x = mod(p.x + u * p.n * (W + 700), W + 700) - 350; al(DARK ? .3 : .7);
        ctx.beginPath(); p.bl.forEach(function (b) { ctx.moveTo(x + b[0] * p.sc + b[2] * p.sc, p.y + b[1] * p.sc); ctx.arc(x + b[0] * p.sc, p.y + b[1] * p.sc, b[2] * p.sc, 0, PI2); });
        ctx.rect(x - 190 * p.sc, p.y, 380 * p.sc, 46 * p.sc); ctx.fill(); });
  });

  /* ---- 格子と図形 ---- */
  def("grid-floor", 2400, function (u, o) {
    var hy = 600, n = 14; glow(960, hy, 520, c2(o), .32); ctx.strokeStyle = c1(o); ctx.lineWidth = 2;
    for (var i = 0; i < n; i++) { var z = (i + u) / n, y = hy + (H - hy) * Math.pow(z, 2.4); al(.08 + .5 * z); line(0, y, W, y); }
    al(.3); for (var j = -18; j <= 18; j++) line(960 + j * 14, hy, 960 + j * 210, H);
    al(.5); line(0, hy, W, hy);
  });
  def("grid-scroll", 16000, function (u, o) {
    var cell = 96, off = u * cell * 4, i; glow(300, 200, 800, c1(o), .1); ctx.strokeStyle = c1(o);
    for (i = -4; i < W / cell + 1; i++) { var x = i * cell + off % (cell * 4), mj = mod(i, 4) === 0; ctx.lineWidth = mj ? 2 : 1; al(mj ? .2 : .09); line(x, 0, x, H); }
    for (i = -4; i < H / cell + 1; i++) { var y = i * cell + off % (cell * 4), mk = mod(i, 4) === 0; ctx.lineWidth = mk ? 2 : 1; al(mk ? .2 : .09); line(0, y, W, y); }
  });
  def("dots-wave", 6000, function (u, o) {
    ctx.fillStyle = c1(o); al(.3); ctx.beginPath();
    for (var x = 24; x < W; x += 48) for (var y = 12; y < H; y += 48) { var r = 1.5 + 5.5 * (.5 + .5 * Math.sin(PI2 * u - Math.hypot(x - 960, y - 540) / 90)); ctx.moveTo(x + r, y); ctx.arc(x, y, r, 0, PI2); }
    ctx.fill();
  });
  def("halftone", 7000, function (u, o) {
    ctx.fillStyle = c2(o); al(.24); ctx.beginPath();
    for (var x = 18; x < W; x += 36) for (var y = 18; y < H; y += 36) { var w = clamp(Math.hypot((x - 960) / 960, (y - 540) / 540) - .3), r = 15 * w * Math.pow(Math.max(0, .5 + .5 * Math.sin(PI2 * u + (x - y) / 260)), 1.5);
      if (r > .4) { ctx.moveTo(x + r, y); ctx.arc(x, y, r, 0, PI2); } }
    ctx.fill();
  });
  def("hex-pulse", 8000, function (u, o) {
    var r = 64, hw = r * 1.5, hh = r * Math.sqrt(3); ctx.strokeStyle = c1(o); ctx.fillStyle = c1(o); ctx.lineWidth = 2;
    for (var i = -1; i * hw < W + r; i++) for (var j = -1; j * hh < H + hh; j++) { var x = i * hw, y = j * hh + (mod(i, 2) ? hh / 2 : 0), k = Math.pow(Math.max(0, Math.sin(PI2 * u - Math.hypot(x - 960, y - 540) / 170)), 2);
      ctx.beginPath(); for (var q = 0; q < 6; q++) ctx.lineTo(x + Math.cos(q * PI / 3) * (r - 5), y + Math.sin(q * PI / 3) * (r - 5)); ctx.closePath();
      al(.07 + .25 * k); ctx.stroke(); if (k > .05) { al(.08 * k); ctx.fill(); } }
  });
  def("tiles", 8000, function (u) {
    seeded("tiles", 41, 16 * 9, function (r, i) { return { x: (i % 16) * 120, y: Math.floor(i / 16) * 120, p: r() * PI2, c: int(r, 0, 3), n: int(r, 1, 2) }; })
      .forEach(function (p) { var k = Math.pow(Math.max(0, S(u, p.n, p.p)), 4); if (k < .02) return; ctx.fillStyle = AC(p.c); al(.16 * k); ctx.fillRect(p.x + 5, p.y + 5, 110, 110); });
  });
  def("pixels", 8000, function (u) {
    seeded("pixels", 42, 32 * 18, function (r, i) { return { x: (i % 32) * 60, y: Math.floor(i / 32) * 60, p: r() * PI2, c: int(r, 0, 3), n: int(r, 1, 3) }; })
      .forEach(function (p) { var k = Math.pow(Math.max(0, S(u, p.n, p.p)), 6); if (k < .03) return; ctx.fillStyle = AC(p.c); al(.24 * k); ctx.fillRect(p.x + 3, p.y + 3, 54, 54); });
  });
  def("ripples", 8000, function (u, o) {
    [[1340, 400, c1(o), 0], [430, 820, c2(o), .5]].forEach(function (q) { ctx.strokeStyle = q[2];
      for (var i = 0; i < 7; i++) { var k = fr(i / 7 + u + q[3] / 7); ctx.lineWidth = 2 + (1 - k) * 3; al((1 - k) * .34); ctx.beginPath(); ctx.arc(q[0], q[1], 8 + k * 1500, 0, PI2); ctx.stroke(); } });
  });
  def("radar", 6000, function (u, o) {
    var cx = 960, cy = 540, a = u * PI2, i; ctx.strokeStyle = c1(o); ctx.lineWidth = 2;
    for (i = 1; i <= 5; i++) { al(.16); ctx.beginPath(); ctx.arc(cx, cy, i * 210, 0, PI2); ctx.stroke(); }
    al(.12); line(0, cy, W, cy); line(cx, 0, cx, H);
    ctx.fillStyle = c1(o); for (i = 0; i < 48; i++) { al(.2 * Math.pow(1 - i / 48, 2)); ctx.beginPath(); ctx.moveTo(cx, cy); ctx.arc(cx, cy, 1150, a - (i + 1) * .03, a - i * .03 + .004); ctx.closePath(); ctx.fill(); }
    seeded("radar", 51, 10, function (r) { return { a: r() * PI2, d: 150 + r() * 800 }; })
      .forEach(function (p) { var k = Math.pow(1 - mod(a - p.a, PI2) / PI2, 3), x = cx + Math.cos(p.a) * p.d, y = cy + Math.sin(p.a) * p.d; glow(x, y, 34, C.accent, k * .8); ctx.fillStyle = C.accent; al(k); dot(x, y, 5); ctx.fillStyle = c1(o); });
  });
  def("tunnel", 3000, function (u, o) {
    ctx.translate(960, 540); ctx.strokeStyle = c1(o);
    for (var i = 0; i < 14; i++) { var q = i + u, s = 26 * Math.pow(1.45, q); ctx.save(); ctx.rotate(q * .06); ctx.lineWidth = 2 + q * .35; al(Math.min(1, q / 3) * .3); X.rr(-s, -s * .5625, s * 2, s * 1.125, s * .12); ctx.stroke(); ctx.restore(); }
  });
  def("prism", 24000, function (u) {
    ctx.translate(960, 540); ctx.lineWidth = 2; ctx.lineJoin = "round";
    for (var i = 0; i < 9; i++) { var rad = 130 + i * 115, rot = i * .2 + (i % 2 ? 1 : -1) * u * PI2 / 3; ctx.strokeStyle = AC(i); al(.26 - i * .018);
      ctx.beginPath(); for (var k = 0; k < 3; k++) ctx.lineTo(Math.cos(rot + k * PI2 / 3) * rad, Math.sin(rot + k * PI2 / 3) * rad); ctx.closePath(); ctx.stroke(); }
  });
  def("orbits", 30000, function (u) {
    glow(960, 540, 300, C.accent, .3); ctx.translate(960, 540); ctx.rotate(-.22); ctx.lineWidth = 2;
    [5, 3, 2, 1, 1].forEach(function (n, i) { var rx = 250 + i * 175, ry = rx * .36, a = PI2 * (u * n + i * .37);
      ctx.strokeStyle = C.accent2; al(.16); ctx.beginPath(); ctx.ellipse(0, 0, rx, ry, 0, 0, PI2); ctx.stroke();
      ctx.fillStyle = AC(i); al(.75); dot(Math.cos(a) * rx, Math.sin(a) * ry, 7 + (i % 3) * 4); });
  });
  def("helix", 8000, function (u) {
    ctx.translate(960, 540); ctx.rotate(-.3);
    for (var x = -1200; x <= 1200; x += 46) { var th = x / 150 + PI2 * u, y = 150 * Math.sin(th), z = Math.cos(th);
      ctx.strokeStyle = C.muted; ctx.lineWidth = 2; al(.14); line(x, y, x, -y);
      ctx.fillStyle = C.accent2; al(.2 + .16 * z); dot(x, y, 9 + 4 * z); ctx.fillStyle = C.accent; al(.2 - .16 * z); dot(x, -y, 9 - 4 * z); }
  });
  def("plexus", 30000, function (u, o) {
    var ps = seeded("plexus", 61, 50, function (r) { return { x: r() * W, y: r() * H, ax: 60 + r() * 150, ay: 50 + r() * 120, n: int(r, 1, 3), m: int(r, 1, 3), p: r() * PI2, q: r() * PI2 }; })
      .map(function (p) { return [p.x + p.ax * S(u, p.n, p.p), p.y + p.ay * S(u, p.m, p.q)]; });
    ctx.strokeStyle = c1(o); ctx.lineWidth = 1.5;
    for (var i = 0; i < ps.length; i++) for (var j = i + 1; j < ps.length; j++) { var d = Math.hypot(ps[i][0] - ps[j][0], ps[i][1] - ps[j][1]); if (d < 240) { al((1 - d / 240) * .35); line(ps[i][0], ps[i][1], ps[j][0], ps[j][1]); } }
    ctx.fillStyle = c2(o); al(.6); ps.forEach(function (p) { dot(p[0], p[1], 3.5); });
  });
  def("circuit", 10000, function (u, o) {
    var tr = seeded("circuit", 71, 28, function (r) { var x = int(r, 1, 46) * 40, y = int(r, 1, 25) * 40, pts = [[x, y]], hz = r() < .5, len = 0;
      for (var k = 0; k < int(r, 3, 5); k++) { var d = int(r, 2, 9) * 40 * (r() < .5 ? -1 : 1); if (hz) x = Math.max(40, Math.min(W - 40, x + d)); else y = Math.max(40, Math.min(H - 40, y + d)); hz = !hz;
        len += Math.abs(x - pts[pts.length - 1][0]) + Math.abs(y - pts[pts.length - 1][1]); pts.push([x, y]); }
      return { pts: pts, len: len, n: int(r, 1, 2), off: r() }; });
    ctx.lineWidth = 2; ctx.lineJoin = "round";
    tr.forEach(function (t) { var a = t.pts[0], z = t.pts[t.pts.length - 1];
      ctx.strokeStyle = c1(o); ctx.fillStyle = c1(o); al(.16); ctx.beginPath(); t.pts.forEach(function (p) { ctx.lineTo(p[0], p[1]); }); ctx.stroke(); al(.3); dot(a[0], a[1], 5); dot(z[0], z[1], 5);
      var want = fr(u * t.n + t.off) * t.len, x = a[0], y = a[1];
      for (var k = 1; k < t.pts.length; k++) { var p0 = t.pts[k - 1], p1 = t.pts[k], sl = Math.abs(p1[0] - p0[0]) + Math.abs(p1[1] - p0[1]); if (want <= sl && sl) { x = p0[0] + (p1[0] - p0[0]) * want / sl; y = p0[1] + (p1[1] - p0[1]) * want / sl; break; } want -= sl; x = p1[0]; y = p1[1]; }
      var e = Math.sin(PI * fr(u * t.n + t.off)); glow(x, y, 22, c2(o), .7 * e); ctx.fillStyle = c2(o); al(e); dot(x, y, 3.5); });
  });
  def("matrix", 12000, function (u, o) {
    var CH = "01アイウエオカキクケコサシスセソ01ｦﾘﾑﾈﾜ", cw = 40, rh = 30, rows = Math.ceil(H / rh), len = 16, col = o.color ? (C[o.color] || o.color) : C.ok;
    ctx.font = "700 26px " + F.mono; ctx.textAlign = "center";
    seeded("matrix", 81, W / cw, function (r, i) { var g2 = []; for (var k = 0; k < rows; k++) g2.push(CH[int(r, 0, CH.length - 1)]); return { x: i * cw + cw / 2, n: int(r, 1, 3), off: r(), g: g2 }; })
      .forEach(function (c) { var head = fr(u * c.n + c.off) * (rows + len);
        for (var k = 0; k < len; k++) { var row = Math.floor(head) - k; if (row < 0 || row >= rows) continue; ctx.fillStyle = k === 0 ? LITE : col; al(k === 0 ? .7 : .42 * (1 - k / len)); ctx.fillText(c.g[row], c.x, row * rh + 26); } });
  });
  def("equalizer", 8000, function (u) {
    var n = 56, bw = 22, gr = ctx.createLinearGradient(0, H - 420, 0, H); gr.addColorStop(0, C.accent); gr.addColorStop(1, C.accent2); ctx.fillStyle = gr; al(.3);
    seeded("equalizer", 91, n, function (r) { return { a: int(r, 1, 3), b: int(r, 2, 5), c: int(r, 4, 8), p: r() * PI2, q: r() * PI2, s: r() * PI2 }; })
      .forEach(function (p, i) { var env = .35 + .65 * Math.sin(PI * (i + .5) / n), h = 30 + 380 * env * (.5 + .5 * (.5 * S(u, p.a, p.p) + .3 * S(u, p.b, p.q) + .2 * S(u, p.c, p.s)));
        ctx.fillRect(14 + i * 34, H - h, bw, h); });
  });
  def("scan", 5000, function (u, o) {
    var i, y = u * (H + 320) - 160; ctx.strokeStyle = c1(o); ctx.lineWidth = 1;
    al(.07); ctx.beginPath(); for (i = 0; i < H; i += 8) { ctx.moveTo(0, i + .5); ctx.lineTo(W, i + .5); } ctx.stroke();
    al(.1); for (i = 120; i < W; i += 240) line(i, 0, i, H);
    var gr = ctx.createLinearGradient(0, y - 160, 0, y + 20); gr.addColorStop(0, rgba(c1(o), 0)); gr.addColorStop(1, rgba(c1(o), 1)); ctx.fillStyle = gr; al(.2); ctx.fillRect(0, y - 160, W, 180);
    al(.55); ctx.lineWidth = 2; line(0, y + 20, W, y + 20);
  });

  /* ---- AI・判断・データの流れ（2026-10-07。解説動画「Jev」のために足した） ---- */
  /* neural: 層になった点の網。左の層から右の層へ、光の粒が線の上を渡っていく（入力 → 判断 → 出力） */
  def("neural", 12000, function (u, o) {
    var cols = [5, 7, 8, 7, 4], xs = [260, 610, 960, 1310, 1660], nodes = cols.map(function (n, ci) { var a = []; for (var k = 0; k < n; k++) a.push([xs[ci] + 26 * S(u, 1, ci * 1.7 + k), 540 + (k - (n - 1) / 2) * (860 / Math.max(n, 6)) + 14 * S(u, 2, k * 1.3 + ci)]); return a; });
    var links = seeded("neural", 91, 64, function (r) { var ci = int(r, 0, 3); return { c: ci, a: int(r, 0, cols[ci] - 1), b: int(r, 0, cols[ci + 1] - 1), n: int(r, 1, 3), off: r(), hot: r() < .45 }; });
    ctx.lineWidth = 1.5; ctx.strokeStyle = c1(o);
    links.forEach(function (L) { var p = nodes[L.c][L.a], q = nodes[L.c + 1][L.b]; al(.13); line(p[0], p[1], q[0], q[1]); });
    links.forEach(function (L) { if (!L.hot) return; var p = nodes[L.c][L.a], q = nodes[L.c + 1][L.b], t = fr(u * L.n + L.off), x = p[0] + (q[0] - p[0]) * t, y = p[1] + (q[1] - p[1]) * t;
      glow(x, y, 26, c2(o), .5 * Math.sin(PI * t)); ctx.fillStyle = c2(o); al(.85 * Math.sin(PI * t)); dot(x, y, 3.5); });
    nodes.forEach(function (col, ci) { col.forEach(function (p, k) { var beat = .5 + .5 * S(u, 2, ci * 1.1 + k * .9);
      ctx.fillStyle = C.bg0; al(1); dot(p[0], p[1], 13); ctx.strokeStyle = ci === 4 ? c2(o) : c1(o); ctx.lineWidth = 2.5; al(.35 + .4 * beat); ctx.beginPath(); ctx.arc(p[0], p[1], 13, 0, PI2); ctx.stroke();
      ctx.fillStyle = ci === 4 ? c2(o) : c1(o); al(.15 + .5 * beat); dot(p[0], p[1], 5); }); });
  });
  /* tokens: 小さな札（トークン）が、何本もの列になって左から右へ流れる。ところどころの札が光る（文を、札に分けて読む） */
  def("tokens", 16000, function (u, o) {
    var rows = seeded("tokens", 97, 9, function (r, i) { var a = [], x = 0; while (x < W + 400) { var w = 46 + int(r, 0, 5) * 26; a.push({ x: x, w: w, hot: r() < .16, ph: r() * PI2 }); x += w + 16; }
      return { y: 70 + i * 118, n: int(r, 1, 2), dir: i % 2 ? -1 : 1, items: a, span: x }; });
    rows.forEach(function (R) { R.items.forEach(function (t) { var x = mod(t.x + R.dir * u * R.n * R.span, R.span) - 200;
      if (x > W || x + t.w < 0) return; var lit = t.hot ? .5 + .5 * Math.sin(PI2 * 3 * u + t.ph) : 0;
      ctx.beginPath(); if (ctx.roundRect) ctx.roundRect(x, R.y, t.w, 34, 8); else ctx.rect(x, R.y, t.w, 34);
      ctx.fillStyle = t.hot ? c2(o) : c1(o); al(t.hot ? .1 + .3 * lit : .07); ctx.fill(); ctx.strokeStyle = t.hot ? c2(o) : c1(o); ctx.lineWidth = 1.5; al(t.hot ? .3 + .5 * lit : .2); ctx.stroke();
      ctx.fillStyle = t.hot ? c2(o) : c1(o); al(t.hot ? .35 + .4 * lit : .16); ctx.fillRect(x + 10, R.y + 15, t.w - 20, 4); }); });
  });
  /* branch: 左の 1 点から枝分かれする道。光が根元から走り、分かれ道のたびに 1 本を選んで、右の端の 1 点を灯す（選ぶ・決める） */
  def("branch", 9000, function (u, o) {
    var LV = 4, turns = 3, pick = Math.floor(u * turns) % turns, t = fr(u * turns), paths = [[0, 1, 0, 1], [1, 0, 1, 1], [1, 1, 0, 0]][pick];
    function pos(l, i) { var n = 1 << l; return [220 + l * 370, 540 + (i - (n - 1) / 2) * (860 / n)]; }
    ctx.lineWidth = 2; ctx.strokeStyle = c1(o); ctx.lineJoin = "round";
    for (var l = 0; l < LV; l++) for (var i = 0; i < (1 << l); i++) { var p = pos(l, i); for (var k = 0; k < 2; k++) { var q = pos(l + 1, i * 2 + k), mx = (p[0] + q[0]) / 2;
      al(.14); ctx.beginPath(); ctx.moveTo(p[0], p[1]); ctx.bezierCurveTo(mx, p[1], mx, q[1], q[0], q[1]); ctx.stroke(); } }
    for (l = 0; l <= LV; l++) for (i = 0; i < (1 << l); i++) { p = pos(l, i); ctx.fillStyle = c1(o); al(l === LV ? .22 : .3); dot(p[0], p[1], l === LV ? 6 : 8); }
    var idx = 0, head = t * (LV + .8), fade = clamp((1 - t) * 6);
    for (l = 0; l < LV; l++) { p = pos(l, idx); var ni = idx * 2 + paths[l], q2 = pos(l + 1, ni), seg = clamp(head - l); if (seg <= 0) break;
      var m2 = (p[0] + q2[0]) / 2; ctx.strokeStyle = c2(o); ctx.lineWidth = 4; al(.75 * fade); ctx.beginPath(); ctx.moveTo(p[0], p[1]);
      for (var s2 = 1; s2 <= 16; s2++) { var w = s2 / 16 * seg, a1 = 1 - w; ctx.lineTo(a1 * a1 * a1 * p[0] + 3 * a1 * a1 * w * m2 + 3 * a1 * w * w * m2 + w * w * w * q2[0], a1 * a1 * a1 * p[1] + 3 * a1 * a1 * w * p[1] + 3 * a1 * w * w * q2[1] + w * w * w * q2[1]); }
      ctx.stroke(); ctx.fillStyle = c2(o); al(.9 * fade); dot(p[0], p[1], 9);
      if (seg >= 1) { glow(q2[0], q2[1], l === LV - 1 ? 90 : 40, c2(o), (l === LV - 1 ? .55 : .3) * fade); al(.95 * fade); dot(q2[0], q2[1], l === LV - 1 ? 12 : 9); }
      idx = ni; }
  });
  /* ==== 2026-10-07 に足した 32 種（題材ごと。話と関係のない静止画を敷くかわりに使う） ==== */
  /* ---- 科学 ---- */
  /* molecules: 原子の玉と結合の棒でできた分子が、回りながら漂う（まん中は空ける） */
  def("molecules", 24000, function (u, o) {
    var P = [[250, 220], [1660, 240], [300, 860], [1620, 850], [960, 120], [960, 975], [1820, 560], [100, 540]], cols = [c1(o), c2(o), LITE];
    seeded("molecules", 101, 8, function (r, i) { var kind = i % 4, at = [], bd = [], k;
      if (kind === 0) { for (k = 0; k < 6; k++) { at.push([Math.cos(k * PI / 3) * 70, Math.sin(k * PI / 3) * 70, 13, 0]); bd.push([k, (k + 1) % 6]); } at.push([140, 0, 17, 1]); bd.push([0, 6]); }
      else if (kind === 1) { at = [[0, 0, 22, 1], [-62, 44, 13, 2], [62, 44, 13, 2]]; bd = [[0, 1], [0, 2]]; }
      else if (kind === 2) { at = [[0, 0, 20, 0]]; for (k = 0; k < 4; k++) { at.push([Math.cos(k * PI / 2 + .4) * 78, Math.sin(k * PI / 2 + .4) * 78, 12, 2]); bd.push([0, k + 1]); } }
      else { for (k = 0; k < 5; k++) { at.push([(k - 2) * 62, k % 2 ? -26 : 26, k === 4 ? 18 : 14, k === 4 ? 1 : 0]); if (k) bd.push([k - 1, k]); } }
      return { at: at, bd: bd, d: i % 2 ? 1 : -1, p: r() * PI2, q: r() * PI2, n: int(r, 1, 2), sc: .9 + r() * .5 }; })
      .forEach(function (m, i) { ctx.save(); ctx.translate(P[i][0] + 60 * S(u, m.n, m.p), P[i][1] + 40 * S(u, 1, m.q)); ctx.rotate(m.d * PI2 * u + m.p); ctx.scale(m.sc, m.sc);
        ctx.strokeStyle = C.muted; ctx.lineWidth = 5; al(.24); ctx.beginPath(); m.bd.forEach(function (b) { ctx.moveTo(m.at[b[0]][0], m.at[b[0]][1]); ctx.lineTo(m.at[b[1]][0], m.at[b[1]][1]); }); ctx.stroke();
        m.at.forEach(function (a) { ctx.fillStyle = C.bg0; al(1); dot(a[0], a[1], a[2]); ctx.fillStyle = cols[a[3]]; al(.28); dot(a[0], a[1], a[2]); ctx.strokeStyle = cols[a[3]]; ctx.lineWidth = 2; al(.5); ctx.beginPath(); ctx.arc(a[0], a[1], a[2], 0, PI2); ctx.stroke(); });
        ctx.restore(); });
  });
  /* waveform: 2 つの波と、その足し合わせ。軸の上に、とびとびの値（標本）の棒が立つ */
  def("waveform", 12000, function (u, o) {
    var x, y0 = 560; ctx.strokeStyle = C.muted; ctx.lineWidth = 1.5; al(.18); line(0, y0, W, y0);
    al(.12); ctx.beginPath(); for (x = 60; x < W; x += 120) { ctx.moveTo(x, y0 - 10); ctx.lineTo(x, y0 + 10); } ctx.stroke();
    function f1(x) { return 150 * Math.sin(x / 190 - PI2 * u); } function f2(x) { return 70 * Math.sin(x / 61 + PI2 * 2 * u + 1); }
    ctx.lineWidth = 2; [[f1, c1(o), .22], [f2, c2(o), .18]].forEach(function (q) { ctx.strokeStyle = q[1]; al(q[2]); ctx.beginPath(); for (x = 0; x <= W; x += 12) ctx.lineTo(x, y0 - q[0](x)); ctx.stroke(); });
    ctx.strokeStyle = LITE; ctx.lineWidth = 3; al(.28); ctx.beginPath(); for (x = 0; x <= W; x += 12) ctx.lineTo(x, y0 - f1(x) - f2(x)); ctx.stroke();
    ctx.strokeStyle = c1(o); ctx.lineWidth = 1.5; al(.14); ctx.beginPath(); for (x = 30; x < W; x += 60) { ctx.moveTo(x, y0); ctx.lineTo(x, y0 - f1(x) - f2(x)); } ctx.stroke();
    ctx.fillStyle = c1(o); al(.4); for (x = 30; x < W; x += 60) dot(x, y0 - f1(x) - f2(x), 4);
  });
  /* microscope: 顕微鏡の丸い視野の中で、小さな生きものが泳ぐ */
  def("microscope", 30000, function (u, o) {
    var cx = 960, cy = 540, R = 500, i; glow(cx, cy, R * 1.1, c1(o), .1);
    seeded("microscope", 111, 22, function (r, i) { var a = r() * PI2, d = Math.sqrt(r()) * (R - 70); return { x: cx + Math.cos(a) * d, y: cy + Math.sin(a) * d, kind: i % 3, s: .7 + r() * .8, n: int(r, 1, 2), m: int(r, 1, 2), p: r() * PI2, q: r() * PI2, d: r() < .5 ? 1 : -1, c: int(r, 0, 3) }; })
      .forEach(function (p) { var k, j; ctx.save(); ctx.translate(p.x + 50 * S(u, p.n, p.p), p.y + 40 * S(u, p.m, p.q)); ctx.rotate(p.d * PI2 * u + p.p); ctx.scale(p.s, p.s); ctx.strokeStyle = ctx.fillStyle = AC(p.c); ctx.lineWidth = 2.5;
        if (p.kind === 0) { X.rr(-34, -11, 68, 22, 11); al(.1); ctx.fill(); al(.32); ctx.stroke(); }
        else if (p.kind === 1) { for (k = 0; k < 4; k++) { ctx.beginPath(); ctx.arc((k - 1.5) * 22, 6 * Math.sin(k * 1.7 + PI2 * u * 2), 10, 0, PI2); al(.1); ctx.fill(); al(.3); ctx.stroke(); } }
        else { ctx.beginPath(); for (j = 0; j < 24; j++) { var th = j / 24 * PI2, rr = 34 * (1 + .14 * Math.sin(3 * th + PI2 * u * 2 + p.q) + .08 * Math.sin(5 * th - PI2 * u + p.p)); ctx.lineTo(Math.cos(th) * rr, Math.sin(th) * rr); } ctx.closePath(); al(.08); ctx.fill(); al(.3); ctx.stroke(); al(.3); dot(6, -4, 8); }
        ctx.restore(); });
    ctx.fillStyle = DARK ? "#000000" : C.muted; al(DARK ? .5 : .18); ctx.beginPath(); ctx.rect(0, 0, W, H); ctx.arc(cx, cy, R, 0, PI2, true); ctx.fill();
    ctx.strokeStyle = c1(o); ctx.lineWidth = 3; al(.3); ctx.beginPath(); ctx.arc(cx, cy, R, 0, PI2); ctx.stroke();
    ctx.lineWidth = 1.5; al(.2); ctx.beginPath(); for (i = 0; i < 72; i++) { var a = i / 72 * PI2, l = i % 6 ? 12 : 26; ctx.moveTo(cx + Math.cos(a) * (R - l), cy + Math.sin(a) * (R - l)); ctx.lineTo(cx + Math.cos(a) * R, cy + Math.sin(a) * R); } ctx.stroke();
  });
  /* ---- 医療・体 ---- */
  /* cells: 膜と核のある細胞が、ゆっくり形を変えながら漂う */
  def("cells", 20000, function (u) {
    seeded("cells", 113, 13, function (r, i) { return { x: 120 + (i % 5) * 420 + r() * 160, y: 150 + Math.floor(i / 5) * 380 + r() * 160, rad: 90 + r() * 80, n: int(r, 1, 2), m: int(r, 1, 2), p: r() * PI2, q: r() * PI2, c: int(r, 0, 3) }; })
      .forEach(function (p) { var x = p.x + 70 * S(u, p.n, p.p), y = p.y + 50 * S(u, p.m, p.q), R = p.rad * (1 + .06 * S(u, 3, p.q)), k, th, rr;
        ctx.beginPath(); for (k = 0; k < 36; k++) { th = k / 36 * PI2; rr = R * (1 + .08 * Math.sin(3 * th + PI2 * u + p.p) + .05 * Math.sin(5 * th - PI2 * 2 * u + p.q)); ctx.lineTo(x + Math.cos(th) * rr, y + Math.sin(th) * rr); } ctx.closePath();
        ctx.fillStyle = AC(p.c); al(.07); ctx.fill(); ctx.strokeStyle = AC(p.c); ctx.lineWidth = 3; al(.24); ctx.stroke();
        var nx = x + R * .2 * S(u, 1, p.q), ny = y + R * .15 * S(u, 2, p.p); glow(nx, ny, R * .5, AC(p.c), .22); ctx.fillStyle = AC(p.c); al(.22); dot(nx, ny, R * .2);
        al(.2); for (k = 0; k < 5; k++) dot(x + R * .55 * Math.cos(k * 1.26 + p.p + PI2 * u), y + R * .55 * Math.sin(k * 1.26 + p.p + PI2 * u), 4); });
  });
  /* ecg: 心電図の線を、光る点が左から右へなぞっていく（color で色） */
  def("ecg", 6000, function (u, o) {
    var y0 = 660, col = o.color ? (C[o.color] || o.color) : C.ok, head = u * W, x, i, e = clamp(u * 20) * clamp((1 - u) * 20);
    function gs(p, m, s) { return Math.exp(-Math.pow((p - m) / s, 2)); }
    function f(x) { var p = fr(x / 640 + .1); return 14 * gs(p, .2, .035) - 22 * gs(p, .365, .012) + 210 * gs(p, .4, .014) - 46 * gs(p, .44, .014) + 34 * gs(p, .64, .05); }
    ctx.strokeStyle = col; ctx.lineWidth = 1; al(.06); ctx.beginPath(); for (x = 0; x < W; x += 80) { ctx.moveTo(x, 0); ctx.lineTo(x, H); } for (i = 20; i < H; i += 80) { ctx.moveTo(0, i); ctx.lineTo(W, i); } ctx.stroke();
    ctx.lineWidth = 3; ctx.lineJoin = "round"; ctx.lineCap = "round";
    for (i = 0; i < 32; i++) { var x0 = i * 60, k = 1 - mod(head - x0 - 30, W) / W; al(.05 + .6 * Math.pow(k, 2.2)); ctx.beginPath(); for (x = x0; x <= x0 + 60; x += 4) ctx.lineTo(x, y0 - f(x)); ctx.stroke(); }
    glow(head, y0 - f(head), 46, col, .6 * e); ctx.fillStyle = col; al(.9 * e); dot(head, y0 - f(head), 5);
  });
  /* ---- 数学 ---- */
  /* plot: 方眼と軸の上に、関数のグラフが 1 本ずつ引かれていく（放物線 → 波 → S 字） */
  def("plot", 15000, function (u, o) {
    var ox = 240, oy = 860, i, x, k = Math.floor(u * 3) % 3, t = fr(u * 3);
    ctx.strokeStyle = c1(o); ctx.lineWidth = 1; al(.08); ctx.beginPath(); for (x = ox % 120; x < W; x += 120) { ctx.moveTo(x, 0); ctx.lineTo(x, H); } for (i = oy % 120; i < H; i += 120) { ctx.moveTo(0, i); ctx.lineTo(W, i); } ctx.stroke();
    ctx.lineWidth = 2.5; al(.3); line(ox, 80, ox, oy + 60); line(ox - 60, oy, W - 100, oy);
    ctx.beginPath(); for (x = ox + 120; x < W - 120; x += 120) { ctx.moveTo(x, oy - 8); ctx.lineTo(x, oy + 8); } for (i = oy - 120; i > 100; i -= 120) { ctx.moveTo(ox - 8, i); ctx.lineTo(ox + 8, i); } ctx.stroke();
    var FN = [function (s) { return 80 + 620 * s * s; }, function (s) { return 360 + 250 * Math.sin(s * PI * 3); }, function (s) { return 60 + 640 / (1 + Math.exp(-(s - .5) * 11)); }];
    function curve(fn, upto) { ctx.beginPath(); for (var j = 0; j <= 80; j++) { var s = j / 80 * upto; ctx.lineTo(ox + s * 1500, oy - fn(s)); } ctx.stroke(); }
    ctx.lineWidth = 2; ctx.strokeStyle = C.muted; al(.1); FN.forEach(function (fn) { curve(fn, 1); });
    var prog = clamp(t / .6), fade = clamp(t * 12) * clamp((1 - t) * 5), col = [c2(o), c1(o), C.warn][k], hx = ox + prog * 1500, hy = oy - FN[k](prog);
    ctx.strokeStyle = col; ctx.lineWidth = 4; ctx.lineCap = "round"; al(.45 * fade); curve(FN[k], prog);
    glow(hx, hy, 40, col, .6 * fade); ctx.fillStyle = col; al(.9 * fade); dot(hx, hy, 6);
    ctx.setLineDash([6, 8]); ctx.lineWidth = 1.5; al(.3 * fade); line(hx, hy, hx, oy); line(hx, hy, ox, hy); ctx.setLineDash([]);
  });
  /* geometry: コンパスで円を描き、中に多角形を引く。四隅で順に（作図） */
  def("geometry", 20000, function (u, o) {
    var FG = [[400, 320, 220, 3], [1500, 760, 250, 6], [1520, 250, 160, 4], [380, 830, 170, 5]], k = Math.floor(u * 4) % 4, t = fr(u * 4), j;
    function vx(f, j) { return f[0] + Math.cos(-PI / 2 + j * PI2 / f[3]) * f[2]; } function vy(f, j) { return f[1] + Math.sin(-PI / 2 + j * PI2 / f[3]) * f[2]; }
    function ngon(f, upto) { var tot = f[3] * upto, j0 = Math.min(f[3], Math.floor(tot)), rest = tot - j0; ctx.beginPath(); for (var j = 0; j <= j0; j++) ctx.lineTo(vx(f, j), vy(f, j));
      if (rest > 0 && j0 < f[3]) ctx.lineTo(vx(f, j0) + (vx(f, j0 + 1) - vx(f, j0)) * rest, vy(f, j0) + (vy(f, j0 + 1) - vy(f, j0)) * rest); ctx.stroke(); }
    ctx.lineWidth = 1.5; ctx.strokeStyle = c1(o); ctx.lineJoin = "round";
    FG.forEach(function (f) { al(.12); ctx.beginPath(); ctx.arc(f[0], f[1], f[2], 0, PI2); ctx.stroke(); ngon(f, 1); al(.08); line(f[0] - f[2] - 60, f[1], f[0] + f[2] + 60, f[1]); line(f[0], f[1] - f[2] - 60, f[0], f[1] + f[2] + 60); });
    var f = FG[k], fade = clamp(t * 12) * clamp((1 - t) * 5), sw = clamp(t / .4), a = -PI / 2 + PI2 * sw, px = f[0] + Math.cos(a) * f[2], py = f[1] + Math.sin(a) * f[2], arm = 1 - clamp((t - .4) / .1);
    ctx.strokeStyle = c2(o); ctx.lineWidth = 3; ctx.lineCap = "round"; al(.55 * fade); ctx.beginPath(); ctx.arc(f[0], f[1], f[2], -PI / 2, a); ctx.stroke();
    ctx.lineWidth = 2; al(.4 * fade * arm); line(f[0], f[1], px, py); ctx.fillStyle = c2(o); al(.8 * fade); dot(f[0], f[1], 5); al(.8 * fade * arm); dot(px, py, 6);
    if (t > .4) { ctx.strokeStyle = C.warn; ctx.lineWidth = 3; al(.55 * fade); ngon(f, clamp((t - .4) / .4)); }
    ctx.fillStyle = C.warn; al(.8 * fade * clamp((t - .8) * 20)); for (j = 0; j < f[3]; j++) dot(vx(f, j), vy(f, j), 5);
  });
  /* lissajous: 2 本の閉じた曲線（リサージュ）が、ゆっくり形を変える */
  def("lissajous", 24000, function (u, o) {
    ctx.translate(960, 540); ctx.lineWidth = 2; ctx.lineJoin = "round";
    [[3, 2, 820, 430, c1(o), .24, 1], [5, 4, 890, 480, c2(o), .13, -1]].forEach(function (q) { ctx.strokeStyle = q[4]; al(q[5]); ctx.beginPath();
      for (var j = 0; j <= 360; j++) { var th = j / 360 * PI2; ctx.lineTo(q[2] * Math.sin(q[0] * th + q[6] * PI2 * u), q[3] * Math.sin(q[1] * th)); } ctx.stroke(); });
    var t2 = PI2 * 2 * u, x = 820 * Math.sin(3 * t2 + PI2 * u), y = 430 * Math.sin(2 * t2); glow(x, y, 30, c2(o), .5); ctx.fillStyle = c2(o); al(.8); dot(x, y, 4.5);
  });
  /* ---- 歴史・文化 ---- */
  /* sumi: 墨のしみが、にじんで広がり、薄れて消える */
  def("sumi", 24000, function (u) {
    var ink = DARK ? C.muted : C.ink;
    seeded("sumi", 121, 7, function (r, i) { var sat = [], sp = [], k, a, d; for (k = 0; k < 5; k++) { a = r() * PI2; d = .35 + r() * .5; sat.push([Math.cos(a) * d, Math.sin(a) * d, .35 + r() * .4]); }
      for (k = 0; k < 7; k++) { a = r() * PI2; d = .9 + r() * .7; sp.push([Math.cos(a) * d, Math.sin(a) * d, 3 + r() * 9]); }
      return { x: [300, 1600, 520, 1420, 180, 1760, 960][i] + (r() - .5) * 160, y: [260, 300, 860, 820, 620, 600, 140][i] + (r() - .5) * 120, R: 170 + r() * 150, off: i / 7 + r() * .06, sat: sat, sp: sp }; })
      .forEach(function (p) { var k = fr(u + p.off), R = p.R * (1 - Math.pow(1 - k, 3)), a = clamp(k * 14) * Math.pow(1 - k, 1.3) * (DARK ? .3 : .26);
        if (a < .003) return; glow(p.x, p.y, R, ink, a); p.sat.forEach(function (s) { glow(p.x + s[0] * R, p.y + s[1] * R, R * s[2], ink, a * .8); });
        ctx.fillStyle = ink; al(a * 1.3); p.sp.forEach(function (s) { dot(p.x + s[0] * R, p.y + s[1] * R, s[2] * clamp(k * 6)); }); });
  });
  /* treerings: 年輪。ゆがんだ輪が、中心から外へゆっくり広がり続ける */
  def("treerings", 30000, function (u, o) {
    var cx = 1320, cy = 640, sp = 52; ctx.strokeStyle = c2(o); glow(cx, cy, 320, c2(o), .1);
    for (var i = 0; i < 34; i++) { var r0 = (i + u) * sp; ctx.lineWidth = 1.5 + 2.5 * (.5 + .5 * Math.sin(r0 / 83)); al(clamp(r0 / 60) * (.1 + .12 * (.5 + .5 * Math.sin(r0 / 131 + 1))));
      ctx.beginPath(); for (var k = 0; k < 60; k++) { var th = k / 60 * PI2, rr = r0 * (1 + .07 * Math.sin(2 * th + r0 / 400) + .035 * Math.sin(5 * th - r0 / 170) + .02 * Math.sin(9 * th + r0 / 60)); ctx.lineTo(cx + Math.cos(th) * rr * 1.08, cy + Math.sin(th) * rr * .94); } ctx.closePath(); ctx.stroke(); }
  });
  /* emaki: 絵巻の「すやり霞」。端の丸い霞の帯が、段になって横へ流れ、金の砂子がまたたく */
  def("emaki", 60000, function (u, o) {
    var col = c2(o), span = W + 1500;
    seeded("emaki", 131, 10, function (r, i) { return { x: r() * span, y: 80 + i * 100 + (r() - .5) * 50, w: 420 + r() * 520, n: int(r, 1, 2), sh: .3 + r() * .4 }; })
      .forEach(function (p, i) { var x = mod(p.x + u * p.n * span, span) - 1400, h = 34; ctx.fillStyle = col; al(i % 3 === 0 ? .17 : .11);
        X.rr(x, p.y, p.w, h, h / 2); ctx.fill(); X.rr(x + p.w * p.sh, p.y + h + 8, p.w * .7, h, h / 2); ctx.fill(); X.rr(x - 60, p.y - 16, p.w * .5, 8, 4); ctx.fill(); });
    ctx.fillStyle = C.warn; seeded("emaki-g", 132, 70, function (r) { return { x: r() * W, y: r() * H, s: 3 + r() * 5, n: int(r, 2, 6), p: r() * PI2 }; })
      .forEach(function (p) { al(.1 + .3 * (.5 + .5 * S(u, p.n, p.p))); ctx.fillRect(p.x, p.y, p.s, p.s); });
  });
  /* ---- 地理・旅 ---- */
  /* contours: 地図の等高線が、ゆっくり形を変える */
  def("contours", 24000, function (u, o) {
    ctx.strokeStyle = c1(o);
    [[420, 300, 2.1, 1], [1500, 780, .4, -1], [1700, 150, 4, 1]].forEach(function (q) {
      for (var k = 1; k <= 9; k++) { var R = k * 70 * (1 + .05 * S(u, 1, q[2] + k * .2)); ctx.beginPath();
        for (var j = 0; j < 48; j++) { var th = j / 48 * PI2, w = 1 + .18 * Math.sin(2 * th + q[2] + q[3] * PI2 * u) + .1 * Math.sin(3 * th + 2 * q[2] - q[3] * PI2 * u) + .05 * Math.sin(5 * th + k * .3 + PI2 * 2 * u); ctx.lineTo(q[0] + Math.cos(th) * R * w, q[1] + Math.sin(th) * R * w); }
        ctx.closePath(); ctx.lineWidth = k % 3 === 0 ? 2.5 : 1.5; al(k % 3 === 0 ? .26 : .15); ctx.stroke(); } });
  });
  /* route: 地図の上を、点線の道のりが延びていき、通った地点の印が灯る */
  def("route", 16000, function (u, o) {
    var WP = [[140, 930], [430, 820], [560, 560], [500, 300], [860, 170], [1260, 230], [1500, 420], [1440, 720], [1720, 900]], i, x;
    var pts = seeded("route", 141, 1, function () { var a = [], i, j; function cr(p0, p1, p2, p3, s) { return .5 * (2 * p1 + (p2 - p0) * s + (2 * p0 - 5 * p1 + 4 * p2 - p3) * s * s + (3 * p1 - p0 - 3 * p2 + p3) * s * s * s); }
      for (i = 0; i < WP.length - 1; i++) { var p0 = WP[Math.max(0, i - 1)], p1 = WP[i], p2 = WP[i + 1], p3 = WP[Math.min(WP.length - 1, i + 2)]; for (j = 0; j < 20; j++) a.push([cr(p0[0], p1[0], p2[0], p3[0], j / 20), cr(p0[1], p1[1], p2[1], p3[1], j / 20)]); }
      a.push(WP[WP.length - 1]); return a; })[0];
    ctx.strokeStyle = c1(o); ctx.lineWidth = 1; al(.07); ctx.beginPath(); for (x = 80; x < W; x += 160) { ctx.moveTo(x, 0); ctx.lineTo(x, H); } for (i = 60; i < H; i += 160) { ctx.moveTo(0, i); ctx.lineTo(W, i); } ctx.stroke();
    ctx.lineWidth = 14; ctx.lineCap = "round"; al(.05); line(-20, 420, 700, 1100); line(900, -20, 1940, 640); line(1100, 1100, 1940, 300);
    var N = pts.length - 1, prog = clamp(u / .8), fade = clamp(u * 12) * clamp((1 - u) * 6), hi = prog * N, h0 = Math.min(N - 1, Math.floor(hi)), hf = hi - h0, hx = pts[h0][0] + (pts[h0 + 1][0] - pts[h0][0]) * hf, hy = pts[h0][1] + (pts[h0 + 1][1] - pts[h0][1]) * hf;
    ctx.lineWidth = 3; ctx.lineJoin = "round"; ctx.setLineDash([14, 12]); al(.16); ctx.beginPath(); pts.forEach(function (p) { ctx.lineTo(p[0], p[1]); }); ctx.stroke(); ctx.setLineDash([]);
    ctx.strokeStyle = c2(o); ctx.lineWidth = 4; al(.6 * fade); ctx.beginPath(); for (i = 0; i <= h0; i++) ctx.lineTo(pts[i][0], pts[i][1]); ctx.lineTo(hx, hy); ctx.stroke();
    WP.forEach(function (p, i) { var lit = clamp((prog * (WP.length - 1) - i) * 4 + .01) * fade; ctx.fillStyle = C.bg0; al(1); dot(p[0], p[1], 11); ctx.strokeStyle = c1(o); ctx.lineWidth = 2.5; al(.35); ctx.beginPath(); ctx.arc(p[0], p[1], 11, 0, PI2); ctx.stroke();
      if (lit > .01) { glow(p[0], p[1], 46, c2(o), .4 * lit); ctx.fillStyle = c2(o); al(.9 * lit); dot(p[0], p[1], 7); } });
    glow(hx, hy, 36, C.warn, .7 * fade); ctx.fillStyle = C.warn; al(fade); dot(hx, hy, 6);
  });
  /* ---- お金・経済 ---- */
  /* candles: 値動きのローソク足と出来高の棒が、右から左へ流れる */
  def("candles", 32000, function (u, o) {
    var N = 40, sp = 60, base = 900, amp = 340, i;
    function pr(i) { var a = PI2 * i / N; return .5 + .27 * Math.sin(a + 1) + .13 * Math.sin(3 * a + 2) + .07 * Math.sin(7 * a + .5) + .04 * Math.sin(11 * a); }
    var wk = seeded("candles", 151, N, function (r) { return [r() * .05, r() * .05, .3 + r() * .7]; });
    ctx.strokeStyle = C.muted; ctx.lineWidth = 1; al(.1); for (i = 0; i < 4; i++) line(0, base - i * 110, W, base - i * 110);
    for (i = 0; i < N; i++) { var x = mod(i * sp - u * N * sp, N * sp) - sp; if (x > W + sp) continue;
      var a = pr(i), b = pr(i + 1), up = b >= a, col = up ? c1(o) : c2(o), ya = base - a * amp, yb = base - b * amp;
      ctx.strokeStyle = col; ctx.lineWidth = 2; al(.3); line(x, base - (Math.max(a, b) + wk[i][0]) * amp, x, base - (Math.min(a, b) - wk[i][1]) * amp);
      ctx.fillStyle = col; al(up ? .28 : .2); ctx.fillRect(x - 15, Math.min(ya, yb), 30, Math.max(3, Math.abs(ya - yb)));
      al(.1); ctx.fillRect(x - 15, H - 10 - 80 * wk[i][2], 30, 80 * wk[i][2]); }
  });
  /* coins: 硬貨が、くるくる回りながら昇っていく（color で色） */
  def("coins", 16000, function (u, o) {
    var col = o.color ? (C[o.color] || o.color) : C.warn;
    fall("coins", 152, 30, u, { up: 1, sway: 30 }, function (p, x, y) { var R = 18 + p.s * 22, sx = Math.cos(PI2 * u * (p.k + 1) + p.q); ctx.save(); ctx.translate(x, y); ctx.rotate(.3 * Math.sin(p.p)); ctx.scale(Math.max(.08, Math.abs(sx)), 1);
      ctx.fillStyle = col; ctx.strokeStyle = col; al(.14 + .1 * p.s); dot(0, 0, R); ctx.lineWidth = 2.5; al(.45); ctx.beginPath(); ctx.arc(0, 0, R, 0, PI2); ctx.stroke(); al(.3); ctx.beginPath(); ctx.arc(0, 0, R * .68, 0, PI2); ctx.stroke(); ctx.fillRect(-1.5, -R * .4, 3, R * .8); ctx.restore(); });
  });
  /* ---- 宇宙 ---- */
  /* constellation: またたく星空に、星座の線が 1 つずつ結ばれては消える */
  def("constellation", 24000, function (u, o) {
    var CS = [[[150, 260], [300, 170], [450, 250], [570, 150], [720, 220]], [[1250, 150], [1400, 230], [1540, 170], [1680, 300], [1800, 210]], [[140, 700], [260, 840], [420, 790], [480, 930], [300, 980], [260, 840]],
      [[1380, 860], [1500, 760], [1650, 820], [1780, 700], [1700, 950], [1650, 820]], [[760, 960], [900, 900], [1040, 970], [1160, 890]]];
    glow(400, 900, 800, C.accent2, .08); ctx.fillStyle = LITE;
    seeded("constellation", 161, 110, function (r) { return { x: r() * W, y: r() * H, s: .8 + r() * 1.6, p: r() * PI2, n: int(r, 2, 6) }; }).forEach(function (p) { al(.15 + .4 * (.5 + .5 * S(u, p.n, p.p))); dot(p.x, p.y, p.s); });
    ctx.lineCap = "round"; ctx.lineJoin = "round";
    CS.forEach(function (c, k) { var t = fr(u + k / 5), env = clamp(t * 20) * clamp((.85 - t) * 6), tot = (c.length - 1) * clamp(t / .35), j0 = Math.min(c.length - 1, Math.floor(tot)), rest = tot - j0, j;
      if (env > 0) { ctx.strokeStyle = c1(o); ctx.lineWidth = 2; al(.5 * env); ctx.beginPath(); for (j = 0; j <= j0; j++) ctx.lineTo(c[j][0], c[j][1]); if (j0 < c.length - 1) ctx.lineTo(c[j0][0] + (c[j0 + 1][0] - c[j0][0]) * rest, c[j0][1] + (c[j0 + 1][1] - c[j0][1]) * rest); ctx.stroke(); }
      c.forEach(function (p) { if (env > 0) glow(p[0], p[1], 26, c1(o), .5 * env); ctx.fillStyle = LITE; al(.45 + .45 * env); dot(p[0], p[1], 3.6); }); });
  });
  /* ---- 自然 ---- */
  /* komorebi: 木もれ日。葉のかげの間で、光のまだらがゆれる */
  def("komorebi", 20000, function (u) {
    var lc = DARK ? C.warn : C.bg1; ctx.fillStyle = C.ok; al(DARK ? .06 : .12); ctx.fillRect(0, 0, W, H);
    seeded("komorebi", 165, 30, function (r) { return { x: r() * W, y: r() * H, rad: 60 + r() * 130, n: int(r, 1, 2), p: r() * PI2, q: r() * PI2, m: int(r, 1, 3) }; })
      .forEach(function (p) { var k = .55 + .45 * S(u, p.m, p.q); glow(p.x + 36 * Math.sin(PI2 * u + p.y / 300) + 20 * S(u, 2, p.p), p.y + 14 * S(u, p.n, p.q), p.rad * (.8 + .2 * k), lc, (DARK ? .2 : .8) * k); });
    ctx.fillStyle = C.ok; seeded("komorebi-l", 166, 30, function (r, i) { var t = r(); return { x: i % 2 ? W - 40 - t * 620 : 40 + t * 560, y: 20 + r() * (260 - t * 150), a: r() * PI, s: 50 + r() * 50, p: r() * PI2 }; })
      .forEach(function (p) { ctx.save(); ctx.translate(p.x + 14 * Math.sin(PI2 * u + p.p), p.y); ctx.rotate(p.a + .2 * Math.sin(PI2 * u + p.p)); al(DARK ? .16 : .2); ctx.beginPath(); ctx.moveTo(-p.s, 0); ctx.quadraticCurveTo(0, -p.s * .55, p.s, 0); ctx.quadraticCurveTo(0, p.s * .55, -p.s, 0); ctx.fill(); ctx.restore(); });
  });
  /* leaves: 色づいた落ち葉が、ひるがえりながら舞い落ちる */
  def("leaves", 18000, function (u) {
    var LC = ["#d9843b", "#c8553a", "#d9b13b", "#a8632e"];
    fall("leaves", 171, 46, u, { sway: 110, slant: -.1 }, function (p, x, y) { var s = 14 + p.s * 16; ctx.save(); ctx.translate(x, y); ctx.rotate(PI2 * (u * p.k + p.s)); ctx.scale(1, .3 + .7 * Math.abs(Math.cos(PI2 * u * (p.k + 1) + p.q)));
      ctx.fillStyle = LC[p.c]; al(.4 + .3 * p.s); ctx.beginPath(); ctx.moveTo(-s, 0); ctx.quadraticCurveTo(0, -s * .8, s, 0); ctx.quadraticCurveTo(0, s * .8, -s, 0); ctx.fill();
      ctx.strokeStyle = LC[p.c]; ctx.lineWidth = 1.6; al(.5); line(-s * .8, 0, s * 1.3, 0); ctx.restore(); });
  });
  /* grass: 下に並ぶ草が、風の波でそよぐ。綿毛が横へ流れる */
  def("grass", 8000, function (u, o) {
    glow(960, H + 200, 900, C.ok, .14);
    seeded("grass", 173, 110, function (r) { return { x: r() * (W + 80) - 40, h: 110 + r() * 230 * (.4 + .6 * r()), w: 5 + r() * 7, p: r() * PI2, c: r() < .3 }; })
      .forEach(function (p) { var sw = p.h * (.22 * Math.sin(PI2 * u - p.x / 330) + .07 * Math.sin(PI2 * 2 * u + p.p));
        ctx.beginPath(); ctx.moveTo(p.x - p.w, H + 4); ctx.quadraticCurveTo(p.x - p.w * .4 + sw * .25, H - p.h * .55, p.x + sw, H - p.h); ctx.quadraticCurveTo(p.x + p.w * .9 + sw * .25, H - p.h * .5, p.x + p.w, H + 4); ctx.closePath();
        ctx.fillStyle = p.c ? c1(o) : C.ok; al(.16 + .14 * (p.h / 340)); ctx.fill(); });
    ctx.fillStyle = LITE; seeded("grass-s", 174, 16, function (r) { return { x: r() * (W + 100), y: 300 + r() * 560, n: int(r, 1, 2), m: int(r, 1, 3), p: r() * PI2, s: 2 + r() * 2.5 }; })
      .forEach(function (p) { al(.4); dot(mod(p.x + u * p.n * (W + 100), W + 100) - 50, p.y + 40 * S(u, p.m, p.p), p.s); });
  });
  /* ---- 技術 ---- */
  /* servers: 機械の棚（ラック）が並び、小さな灯がまたたく */
  def("servers", 10000, function (u, o) {
    var RX = [40, 330, 620, 1090, 1380, 1670];
    seeded("servers", 177, 6 * 12, function (r) { return { n: int(r, 1, 4), p: r() * PI2, m: int(r, 2, 6), q: r() * PI2, c: int(r, 0, 5), k: int(r, 1, 3), s: r() * PI2 }; })
      .forEach(function (p, i) { var x = RX[i % 6], y = 80 + Math.floor(i / 6) * 78; ctx.strokeStyle = c1(o); ctx.lineWidth = 1.5; X.rr(x + 12, y, 186, 62, 5); al(.14); ctx.stroke();
        ctx.fillStyle = C.ok; al(.25 + .5 * (.5 + .5 * S(u, p.n, p.p))); dot(x + 32, y + 31, 4.5);
        ctx.fillStyle = p.c === 0 ? C.warn : c2(o); al(S(u, p.m, p.q) > .2 ? .75 : .12); dot(x + 52, y + 31, 4.5);
        ctx.fillStyle = c1(o); al(.1); ctx.fillRect(x + 76, y + 22, 104, 4); ctx.fillRect(x + 76, y + 36, 104, 4); al(.34); ctx.fillRect(x + 76, y + 22, 104 * (.5 + .45 * S(u, p.k, p.s)), 4); });
    ctx.strokeStyle = c1(o); ctx.lineWidth = 2.5; al(.2); RX.forEach(function (x) { X.rr(x, 60, 210, 964, 10); ctx.stroke(); });
  });
  /* packets: つながった機械の間を、データの包み（パケット）が行き来する */
  def("packets", 12000, function (u, o) {
    var ND = [[200, 190], [640, 130], [1300, 150], [1740, 250], [1770, 810], [1320, 950], [640, 940], [170, 790], [420, 500], [1520, 560]],
      LK = [[0, 1], [1, 2], [2, 3], [3, 4], [4, 5], [5, 6], [6, 7], [7, 0], [8, 0], [8, 1], [8, 6], [8, 7], [9, 2], [9, 3], [9, 4], [9, 5], [8, 9]];
    ctx.strokeStyle = c1(o); ctx.lineWidth = 2; al(.14); ctx.beginPath(); LK.forEach(function (l) { ctx.moveTo(ND[l[0]][0], ND[l[0]][1]); ctx.lineTo(ND[l[1]][0], ND[l[1]][1]); }); ctx.stroke();
    seeded("packets", 181, 26, function (r, i) { return { l: i % LK.length, d: r() < .5, n: int(r, 1, 3), off: r(), c: r() < .35 }; })
      .forEach(function (p) { var l = LK[p.l], a = ND[l[p.d ? 0 : 1]], b = ND[l[p.d ? 1 : 0]], t = fr(u * p.n + p.off), e = Math.sin(PI * t);
        ctx.save(); ctx.translate(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t); ctx.rotate(Math.atan2(b[1] - a[1], b[0] - a[0])); ctx.fillStyle = p.c ? c2(o) : c1(o); al(.75 * e); ctx.fillRect(-9, -6, 18, 12); al(.35 * e); ctx.fillRect(-26, -4, 11, 8); al(.18 * e); ctx.fillRect(-40, -3, 9, 6); ctx.restore(); });
    ND.forEach(function (p, i) { var hub = i >= 8, s = hub ? 34 : 24, beat = .5 + .5 * S(u, 2, i * 1.3), col = hub ? c2(o) : c1(o); ctx.fillStyle = C.bg0; al(1); X.rr(p[0] - s, p[1] - s, s * 2, s * 2, 8); ctx.fill();
      ctx.strokeStyle = col; ctx.lineWidth = 2.5; al(.4 + .3 * beat); ctx.stroke(); ctx.fillStyle = col; al(.2 + .4 * beat); for (var k = 0; k < 3; k++) ctx.fillRect(p[0] - s * .55, p[1] - s * .5 + k * s * .4, s * 1.1, s * .16); });
  });
  /* stack: ブロックが上から落ちて、列ごとに積み上がっては消える（まん中は低く） */
  def("stack", 14000, function (u) {
    var bw = 120, bh = 72;
    seeded("stack", 191, 16, function (r, i) { return { h: 1 + Math.round(Math.abs(i - 7.5) / 7.5 * 4 + r() * 2), off: r(), c: int(r, 0, 3) }; })
      .forEach(function (p, i) { var t = fr(u + p.off), fade = clamp((1 - t) * 6);
        for (var j = 0; j < p.h; j++) { var q = clamp((t - j / (p.h + 1) * .65) / .07); if (q <= 0) break;
          X.rr(i * bw + 6, H - (j + 1) * bh - 6 - Math.pow(1 - q, 2) * 260, bw - 12, bh - 8, 8); ctx.fillStyle = AC(p.c + j); al(.14 * q * fade); ctx.fill(); ctx.strokeStyle = AC(p.c + j); ctx.lineWidth = 2; al(.36 * q * fade); ctx.stroke(); } });
  });
  /* ---- セキュリティ ---- */
  /* vault: 金庫のダイヤル。目盛りの輪が、互い違いに回る。まん中に鍵穴 */
  def("vault", 30000, function (u, o) {
    ctx.translate(960, 540); glow(0, 0, 520, c1(o), .1); ctx.strokeStyle = c1(o); ctx.lineCap = "round";
    [[170, 24, 2], [300, 36, -1], [440, 48, 1], [590, 60, -1], [760, 72, 1], [950, 96, -1]].forEach(function (q, i) { var R = q[0], rot = q[2] * PI2 * u, k;
      ctx.lineWidth = 2; al(.16); ctx.beginPath(); ctx.arc(0, 0, R, 0, PI2); ctx.stroke();
      ctx.lineWidth = 1.5; al(.24); ctx.beginPath(); for (k = 0; k < q[1]; k++) { var a = rot + k * PI2 / q[1], l = k % 6 ? 10 : 24; ctx.moveTo(Math.cos(a) * R, Math.sin(a) * R); ctx.lineTo(Math.cos(a) * (R - l), Math.sin(a) * (R - l)); } ctx.stroke();
      ctx.lineWidth = 7; al(.12); for (k = 0; k < 3; k++) { ctx.beginPath(); ctx.arc(0, 0, R - 40, rot + k * PI2 / 3 + i, rot + k * PI2 / 3 + i + .7); ctx.stroke(); } });
    ctx.strokeStyle = c2(o); ctx.lineWidth = 3; al(.4); ctx.beginPath(); ctx.arc(0, -14, 24, PI * .65, PI * .35); ctx.lineTo(22, 46); ctx.lineTo(-22, 46); ctx.closePath(); ctx.stroke();
    al(.3); for (var s = 0; s < 3; s++) { var b = -PI2 * u + s * PI2 / 3; line(Math.cos(b) * 78, Math.sin(b) * 78, Math.cos(b) * 128, Math.sin(b) * 128); }
  });
  /* fingerprint: 指紋のうずを、読み取りの光が上下になぞる */
  def("fingerprint", 9000, function (u, o) {
    var cx = 1380, cy = 540, sy = cy + 400 * S(u, 1);
    var arcs = seeded("fingerprint", 201, 15, function (r) { var g = [], a = r() * PI2; for (var k = 0; k < 3; k++) { var len = .6 + r() * 1.3; g.push([a, a + len]); a += len + .14 + r() * .25; } return g; });
    ctx.lineCap = "round"; ctx.lineWidth = 5;
    arcs.forEach(function (g, i) { var rx = 22 + i * 21, ry = rx * 1.28; g.forEach(function (s) { var k = Math.exp(-Math.pow((cy + Math.sin((s[0] + s[1]) / 2) * ry - sy) / 90, 2));
      ctx.beginPath(); ctx.ellipse(cx, cy, rx, ry, 0, s[0], s[1]); ctx.strokeStyle = c1(o); al(.18); ctx.stroke(); if (k > .02) { ctx.strokeStyle = c2(o); al(.6 * k); ctx.stroke(); } }); });
    var gr = ctx.createLinearGradient(0, sy - 60, 0, sy + 60); gr.addColorStop(0, rgba(c2(o), 0)); gr.addColorStop(.5, rgba(c2(o), 1)); gr.addColorStop(1, rgba(c2(o), 0)); ctx.fillStyle = gr; al(.14); ctx.fillRect(cx - 380, sy - 60, 760, 120);
    ctx.strokeStyle = c2(o); ctx.lineWidth = 2; al(.55); line(cx - 380, sy, cx + 380, sy);
    ctx.strokeStyle = c1(o); ctx.lineWidth = 3; al(.3); [[-1, -1], [1, -1], [1, 1], [-1, 1]].forEach(function (q) { var x = cx + q[0] * 400, y = cy + q[1] * 450; ctx.beginPath(); ctx.moveTo(x - q[0] * 60, y); ctx.lineTo(x, y); ctx.lineTo(x, y - q[1] * 60); ctx.stroke(); });
  });
  /* ---- 落ち着いた地 ---- */
  /* fibers: 紙の繊維。すき込まれた細い繊維の上を、淡い光がゆっくり移る */
  def("fibers", 40000, function (u, o) {
    glow(960 + 700 * S(u, 1), 400 + 200 * S(u, 2, 1), 900, c2(o), .1); glow(960 - 600 * S(u, 1, 2), 800, 700, c1(o), .07);
    var fb = seeded("fibers", 211, 170, function (r) { var x = r() * W, y = r() * H, a = r() * PI2, l = 20 + r() * 60; return [x, y, x + Math.cos(a) * l / 2 + (r() - .5) * 24, y + Math.sin(a) * l / 2 + (r() - .5) * 24, x + Math.cos(a) * l, y + Math.sin(a) * l]; });
    ctx.strokeStyle = C.muted; ctx.lineWidth = 1.4; ctx.lineCap = "round";
    for (var b = 0; b < 5; b++) { al(.16 + .09 * S(u, 1, b * 1.26)); ctx.beginPath(); for (var i = b; i < fb.length; i += 5) { ctx.moveTo(fb[i][0], fb[i][1]); ctx.quadraticCurveTo(fb[i][2], fb[i][3], fb[i][4], fb[i][5]); } ctx.stroke(); }
    ctx.fillStyle = C.faint; al(.3); ctx.beginPath(); seeded("fibers-d", 212, 70, function (r) { return [r() * W, r() * H, .8 + r() * 1.6]; }).forEach(function (p) { ctx.moveTo(p[0] + p[2], p[1]); ctx.arc(p[0], p[1], p[2], 0, PI2); }); ctx.fill();
  });
  /* sheen: ほぼ無地。斜めの淡い光の帯が、ゆっくり横切る */
  def("sheen", 18000, function (u, o) {
    glow(300, 200, 800, c1(o), .06); ctx.translate(960, 540); ctx.rotate(.42);
    [[0, c1(o), 620, .16], [.5, c2(o), 380, .12]].forEach(function (q) { var x = -1750 + fr(u + q[0]) * 3500, gr = ctx.createLinearGradient(x, 0, x + q[2], 0);
      gr.addColorStop(0, rgba(q[1], 0)); gr.addColorStop(.5, rgba(q[1], 1)); gr.addColorStop(1, rgba(q[1], 0)); ctx.fillStyle = gr; al(q[3]); ctx.fillRect(x, -1300, q[2], 2600); });
  });
  /* dust: 斜めに差す光の中を、ほこりの粒がゆっくり漂う */
  def("dust", 30000, function (u) {
    var gr = ctx.createLinearGradient(200, -100, 1300, 1000); gr.addColorStop(0, rgba(C.warn, 1)); gr.addColorStop(1, rgba(C.warn, 0)); ctx.fillStyle = gr; al(.13 + .03 * S(u, 2));
    ctx.beginPath(); ctx.moveTo(60, -40); ctx.lineTo(620, -40); ctx.lineTo(1750, 1120); ctx.lineTo(700, 1120); ctx.closePath(); ctx.fill();
    ctx.fillStyle = DARK ? C.ink : C.warn;
    seeded("dust", 221, 90, function (r) { return { x: r() * W, y: r() * H, ax: 60 + r() * 120, ay: 40 + r() * 90, n: int(r, 1, 2), m: int(r, 1, 2), p: r() * PI2, q: r() * PI2, s: 1.4 + r() * 2.8, t: int(r, 2, 5) }; })
      .forEach(function (p) { var x = p.x + p.ax * S(u, p.n, p.p), y = p.y + p.ay * S(u, p.m, p.q), k = .3 + .7 * clamp(1.3 - Math.abs((x - 340) * .795 - (y + 40) * .607) / 380);
        al((.12 + .45 * (.5 + .5 * S(u, p.t, p.q))) * k); dot(x, y, p.s); });
  });
  /* ---- 和風 ---- */
  /* seigaiha-flow: 青海波のうろこが横へゆっくり流れ、光の波が上へ渡る */
  def("seigaiha-flow", 24000, function (u, o) {
    var R = 100, hh = 50, RS = [100, 72, 44];
    var dl = seeded("seigaiha-flow", 231, 1, function () { return RS.map(function (r) { for (var th = 0; th < PI; th += .01) if (Math.pow(r * Math.sin(th) - R, 2) + Math.pow(-r * Math.cos(th) - hh, 2) < R * R) break; return th; }); })[0];   /* 下の段のうろこに隠れない角度 */
    ctx.strokeStyle = c1(o); ctx.lineWidth = 2.5;
    for (var j = 0; j * hh < H + R + hh; j++) { var y = j * hh; al(.1 + .16 * (.5 + .5 * Math.sin(PI2 * 2 * u + y / 170))); ctx.beginPath();
      for (var x = (j % 2 ? R : 0) + u * 2 * R - 2 * R; x < W + R; x += 2 * R) for (var k = 0; k < 3; k++) { ctx.moveTo(x + RS[k] * Math.cos(-PI / 2 - dl[k]), y + RS[k] * Math.sin(-PI / 2 - dl[k])); ctx.arc(x, y, RS[k], -PI / 2 - dl[k], -PI / 2 + dl[k]); }
      ctx.stroke(); }
  });
  /* asanoha-pulse: 麻の葉の模様に、まん中から光の波が広がる */
  def("asanoha-pulse", 10000, function (u, o) {
    var s = 160, h = s * Math.sqrt(3) / 2; ctx.strokeStyle = c2(o); ctx.lineWidth = 1.6; ctx.lineJoin = "round";
    for (var j = -1; (j - 1) * h < H; j++) for (var i = -1; i * s < W + s; i++) { var x0 = i * s + (mod(j, 2) ? s / 2 : 0), y0 = j * h;
      for (var up = 0; up < 2; up++) { var cx = x0 + s / 2, cy = y0 + (up ? -h : h), gx = x0 + s / 2, gy = (y0 * 2 + cy) / 3, k = Math.pow(Math.max(0, Math.sin(PI2 * u - Math.hypot(gx - 960, gy - 540) / 200)), 2);
        ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x0 + s, y0); ctx.lineTo(cx, cy); ctx.closePath(); ctx.moveTo(gx, gy); ctx.lineTo(x0, y0); ctx.moveTo(gx, gy); ctx.lineTo(x0 + s, y0); ctx.moveTo(gx, gy); ctx.lineTo(cx, cy); al(.07 + .26 * k); ctx.stroke(); } }
  });
  /* ichimatsu: 市松の 2 色が、斜めの波でゆっくり入れ替わる */
  def("ichimatsu", 16000, function (u, o) {
    var s = 160; glow(960, 540, 900, c1(o), .06);
    for (var j = 0; j * s < H; j++) for (var i = 0; i * s < W; i++) { var k = .5 + .5 * Math.sin(PI2 * u + ((i + j) % 2) * PI + (i - j) * .22); k = k * k * (3 - 2 * k);
      if (k < .02) continue; ctx.fillStyle = (i + j) % 2 ? c1(o) : C.ink; al(((i + j) % 2 ? .11 : .055) * k); ctx.fillRect(i * s, j * s, s, s); }
  });
  /* ---- ポップ ---- */
  /* polka: 水玉の列が、段ごとに左右へ流れながら、ふくらんだり縮んだりする */
  def("polka", 12000, function (u) {
    var sx = 170, sy = 150;
    for (var j = -1; j * sy < H + sy; j++) { ctx.fillStyle = AC(j + 8); al(.14); ctx.beginPath();
      for (var i = -2; i * sx < W + 2 * sx; i++) { var x = i * sx + (mod(j, 2) ? sx / 2 - u * sx : u * sx), y = j * sy + 40, r = 30 * (.72 + .28 * Math.sin(PI2 * 2 * u + x / 260 + j)); ctx.moveTo(x + r, y); ctx.arc(x, y, r, 0, PI2); }
      ctx.fill(); }
  });
  /* balloons: 色とりどりの風船が、ゆれながら昇っていく */
  def("balloons", 22000, function (u) {
    seeded("balloons", 241, 15, function (r) { return { x: 80 + r() * (W - 160), y: r() * (H + 520), s: r(), p: r() * PI2, c: int(r, 0, 3), k: int(r, 1, 2) }; })
      .forEach(function (p) { var rx = 40 + p.s * 26, ry = rx * 1.2; ctx.save(); ctx.translate(p.x + 46 * S(u, p.k, p.p), H + 130 - mod(p.y + u * (H + 520), H + 520)); ctx.rotate(.1 * Math.cos(PI2 * p.k * u + p.p)); ctx.fillStyle = ctx.strokeStyle = AC(p.c);
        al(.2); ctx.beginPath(); ctx.ellipse(0, 0, rx, ry, 0, 0, PI2); ctx.fill(); ctx.lineWidth = 2; al(.42); ctx.stroke();
        al(.42); ctx.beginPath(); ctx.moveTo(0, ry); ctx.lineTo(-7, ry + 12); ctx.lineTo(7, ry + 12); ctx.closePath(); ctx.fill();
        ctx.fillStyle = LITE; al(.22); ctx.beginPath(); ctx.ellipse(-rx * .35, -ry * .4, rx * .16, ry * .24, .5, 0, PI2); ctx.fill();
        ctx.strokeStyle = C.muted; ctx.lineWidth = 1.5; al(.4); ctx.beginPath(); ctx.moveTo(0, ry + 12); ctx.bezierCurveTo(14, ry + 60, -14, ry + 110, 4, ry + 170); ctx.stroke(); ctx.restore(); });
  });
}); }
