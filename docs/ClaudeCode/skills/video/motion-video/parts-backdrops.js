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
}); }
