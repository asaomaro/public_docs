/* motion-video parts-depth — 立体・奥行き（箱が回る・カードの輪・層の分解・奥へ進む・視差の風景・粒の文字・形の変身）と
 * 文字の演出（言葉の連打・入れ替わる語・線に沿う文字・強調語だけが動く文）。
 * 3D は透視の投影（焦点 1400）と、面の 3 隅からのアフィン変換で描く。どれも時刻だけで決まる。
 * custom には H.p3・H.rot3・H.plane・H.textPoints・H.shapePoints・H.morph を渡す。 */
if (!window.__mvPartsDepth) { window.__mvPartsDepth = 1; (window.MotionVideoParts = window.MotionVideoParts || []).push(function (R, X) {
  "use strict";
  var C = X.C, F = X.F, P = X.P, lin = X.lin, eo = X.eo, eio = X.eio, back = X.back, clamp = X.clamp, mix = X.mix;
  var txt = X.txt, tw = X.tw, rr = X.rr, acc = X.accentAt, ev = X.sfxEv, g = X.g, rand = X.rand, PI2 = Math.PI * 2;
  var FOCAL = 1400, W = X.W, H = X.H;

  /* ---- 3D の道具 ---- */
  /* 画面の中心を原点に、z は奥が正。返り値 {x, y, s（縮尺）, z} */
  function p3(x, y, z, cx, cy) { var s = FOCAL / Math.max(40, FOCAL + z); return { x: (cx === undefined ? 960 : cx) + x * s, y: (cy === undefined ? 540 : cy) + y * s, s: s, z: z }; }
  /* 点を回す（ラジアン）: まず縦軸（Y）で ay 回し（回転台）、次に横軸（X）で ax 傾ける（見下ろす角度。正で上から見る） */
  function rot3(pt, ax, ay) {
    var c = Math.cos(ay || 0), s = Math.sin(ay || 0), x1 = pt[0] * c + pt[2] * s, z1 = -pt[0] * s + pt[2] * c, y = pt[1];
    c = Math.cos(ax || 0); s = Math.sin(ax || 0); return [x1, y * c - z1 * s, y * s + z1 * c];
  }
  /* 3D の面（左上・右上・左下の 3 隅、どれも [x,y,z]）に、w×h の 2D の絵を貼る。裏向きなら false を返して描かない（both で両面） */
  function plane(tl, tr, bl, w, h, draw, o) {
    o = o || {}; var a = p3(tl[0], tl[1], tl[2], o.cx, o.cy), b = p3(tr[0], tr[1], tr[2], o.cx, o.cy), c = p3(bl[0], bl[1], bl[2], o.cx, o.cy);
    var ux = (b.x - a.x) / w, uy = (b.y - a.y) / w, vx = (c.x - a.x) / h, vy = (c.y - a.y) / h, cross = ux * vy - uy * vx;
    if (cross <= 0 && !o.both) return false;
    var ctx = g(); ctx.save(); ctx.transform(ux, uy, vx, vy, a.x, a.y); draw(ctx, cross); ctx.restore(); return true;
  }
  /* 文字を粒の点の並び（1920×1080 の座標）にする。同じ文字・書体なら覚えておく */
  var TPC = {};
  function textPoints(text, n, o) {
    o = o || {}; var size = o.size || 260, font = (o.weight || 900) + " " + size + "px " + (o.font || F.display), key = text + "|" + n + "|" + font;
    if (TPC[key]) return TPC[key];
    var c = document.createElement("canvas"), w = 1800, h = Math.round(size * 1.5); c.width = w; c.height = h;
    var q = c.getContext("2d"); q.font = font; q.textAlign = "center"; q.textBaseline = "middle"; q.fillStyle = "#000";
    var tw0 = q.measureText(text).width, sc = tw0 > w * .96 ? w * .96 / tw0 : 1; q.translate(w / 2, h / 2); q.scale(sc, sc); q.fillText(text, 0, 0);
    var data = q.getImageData(0, 0, w, h).data, pts = [], step = Math.max(3, Math.round(size / 34));
    for (var y = 0; y < h; y += step) for (var x = 0; x < w; x += step) if (data[(y * w + x) * 4 + 3] > 128) pts.push([960 - w / 2 + x, (o.y || 540) - h / 2 + y]);
    var out = [], r = rand(text.length * 131 + 7);
    if (!pts.length) for (var i = 0; i < n; i++) out.push([960, o.y || 540]);
    else { var idx = pts.map(function (_, i) { return i; }); idx.sort(function () { return r() - .5; });
      for (var j = 0; j < n; j++) out.push(pts[idx[j % idx.length]]); }
    var keys = Object.keys(TPC); if (keys.length > 40) TPC = {};
    TPC[key] = out; return out;
  }
  /* 形を n 点の多角形にする（中心 0,0・半径 1。始まりは真上から時計回り） */
  function shapePoints(shape, n) {
    var pts = [], i, a, k;
    var poly = function (vs) { /* 頂点の並びを周の長さで等分 */
      var per = [], L = 0; for (i = 0; i < vs.length; i++) { var p = vs[i], q = vs[(i + 1) % vs.length], l = Math.hypot(q[0] - p[0], q[1] - p[1]); per.push(l); L += l; }
      for (k = 0; k < n; k++) { var dd = L * k / n, e = 0; while (dd > per[e] && e < per.length - 1) { dd -= per[e]; e++; }
        var p0 = vs[e], p1 = vs[(e + 1) % vs.length], f = per[e] ? dd / per[e] : 0; pts.push([mix(p0[0], p1[0], f), mix(p0[1], p1[1], f)]); }
      return pts; };
    var reg = function (m, rot, r2) { var vs = []; for (var j = 0; j < m * (r2 ? 2 : 1); j++) { var an = -Math.PI / 2 + (rot || 0) + j * PI2 / (m * (r2 ? 2 : 1)), rr0 = r2 && j % 2 ? r2 : 1; vs.push([Math.cos(an) * rr0, Math.sin(an) * rr0]); } return vs; };
    switch (shape) {
      case "square": return poly([[0, -1], [1, -1], [1, 1], [-1, 1], [-1, -1]].map(function (p) { return [p[0] * .86, p[1] * .86]; }));
      case "triangle": return poly(reg(3));
      case "diamond": return poly([[0, -1], [.75, 0], [0, 1], [-.75, 0]]);
      case "hexagon": return poly(reg(6));
      case "star": return poly(reg(5, 0, .45));
      case "arrow": return poly([[0, -1], [.85, -.1], [.38, -.1], [.38, .95], [-.38, .95], [-.38, -.1], [-.85, -.1]]);
      case "plus": return poly([[-.3, -1], [.3, -1], [.3, -.3], [1, -.3], [1, .3], [.3, .3], [.3, 1], [-.3, 1], [-.3, .3], [-1, .3], [-1, -.3], [-.3, -.3]]);
      case "heart": for (i = 0; i < n; i++) { a = PI2 * i / n; pts.push([16 * Math.pow(Math.sin(a), 3) / 17, -(13 * Math.cos(a) - 5 * Math.cos(2 * a) - 2 * Math.cos(3 * a) - Math.cos(4 * a)) / 17 - .1]); } return pts;
      default: for (i = 0; i < n; i++) { a = -Math.PI / 2 + PI2 * i / n; pts.push([Math.cos(a), Math.sin(a)]); } return pts;
    }
  }
  function morph(A, B, k) { return A.map(function (p, i) { var q = B[i] || p; return [mix(p[0], q[0], k), mix(p[1], q[1], k)]; }); }
  function hexRgb(c) { var m = /^#([0-9a-f]{6})$/i.exec(c || ""); if (!m) return null; var n = parseInt(m[1], 16); return [n >> 16 & 255, n >> 8 & 255, n & 255]; }
  function mixColor(a, b, k) { var p = hexRgb(a), q = hexRgb(b); if (!p || !q) return k < .5 ? a : b;
    return "rgb(" + [0, 1, 2].map(function (i) { return Math.round(mix(p[i], q[i], k)); }).join(",") + ")"; }
  X.p3 = p3; X.rot3 = rot3; X.plane = plane; X.textPoints = textPoints; X.shapePoints = shapePoints; X.morph = morph; X.mixColor = mixColor;

  function head(s, lt) { return X.heading(s, lt); }
  function itemOf(it) { return typeof it === "string" ? { title: it } : (it || {}); }
  /* 区切りの時刻から、今いくつ目か（0..n-1）と、そこへ移る進み（0..1、移る時間 ms） */
  function stepAt(ts, lt, ms) { var i = 0; for (var j = 0; j < ts.length; j++) if (lt >= ts[j]) i = j; return { i: i, k: i === 0 ? 1 : eio(lin(lt, ts[i], ts[i] + (ms || 900))) }; }
  /* 面に貼るカード（w×h）: 地・枠・アイコン・題・説明 */
  function card(ctx, it, w, h, col, shade, o) {
    o = o || {}; ctx.save(); ctx.shadowColor = "rgba(0,0,0,0)";
    rr(0, 0, w, h, o.r === undefined ? 26 : o.r); ctx.fillStyle = C.panel; ctx.fill(); ctx.lineWidth = 4; ctx.strokeStyle = col; ctx.stroke();
    ctx.fillStyle = col; ctx.globalAlpha = .9; rr(0, 0, w, 14, 7); ctx.fill(); ctx.globalAlpha = 1;
    var y = o.pad || 70; if (it.icon) { X.iconAny(it.icon, w / 2, y + 40, 92, col); y += 120; }
    if (it.title) { txt(it.title, w / 2, y + 40, { size: o.ts || 54, weight: 800, align: "center", font: F.display }); y += 70; }
    if (it.text) X.wrap(it.text, w - 80, { size: 30 }).slice(0, 4).forEach(function (ln, i) { X.rich(ln, w / 2, y + 30 + i * 44, { size: 30, color: C.muted, align: "center" }); });
    if (shade > 0) { ctx.globalAlpha = Math.min(.75, shade); rr(0, 0, w, h, o.r === undefined ? 26 : o.r); ctx.fillStyle = C.bg0; ctx.fill(); }
    ctx.restore();
  }

  /* ---- cube: 箱が回って面ごとに見せる ---- */
  R.cube = function (s, lt, d) {
    var items = (s.faces || s.items || []).slice(0, 4).map(itemOf), n = Math.max(1, items.length), ts = X.slots(n, d, 500, 900);
    var hh = head(s, lt), st = stepAt(ts, lt, 950), ang = -(st.i - 1 + st.k) * Math.PI / 2; if (st.i === 0) ang = 0;
    ang += -.42 + Math.sin(lt / 2600) * .05;   /* 斜めから: 今の面と右の面が見える */
    ts.forEach(function (t0, i) { ev(t0, i ? "sweep" : "appear", { i: i }); });
    var w = 720, h = 480, D = w / 2, k0 = P(lt, 0, 800, back), tilt = .32 + Math.sin(lt / 2400) * .03, cy = 590 + hh * .2, z0 = 380;
    if (k0 <= 0) return;
    var faces = [];
    for (var f = 0; f < 4; f++) {
      var a = ang + f * Math.PI / 2, c3 = function (x, y, z) { var r0 = rot3([x, y, z], tilt, a); return [r0[0] * k0, r0[1] * k0, r0[2] * k0 + z0]; };
      var cz = rot3([0, 0, -D], tilt, a)[2];
      faces.push({ f: f, z: cz, tl: c3(-w / 2, -h / 2, -D), tr: c3(w / 2, -h / 2, -D), bl: c3(-w / 2, h / 2, -D), facing: Math.cos(a) });
    }
    /* 上の面（蓋） */
    var top = function (x, z) { var r0 = rot3([x, -h / 2, z], tilt, ang); return [r0[0] * k0, r0[1] * k0, r0[2] * k0 + z0]; };
    faces.sort(function (p, q) { return q.z - p.z; }).forEach(function (fc) {
      var it = items[fc.f % n] || {}, col = acc(fc.f);
      plane(fc.tl, fc.tr, fc.bl, w, h, function (ctx) { card(ctx, it, w, h, col, (1 - fc.facing) * .55, { r: 6 }); }, { cy: cy });
    });
    /* 蓋は上から見えるので最後に（模様の向きは問わないので両面） */
    plane(top(-D, D), top(D, D), top(-D, -D), w, w, function (ctx) { ctx.fillStyle = C.panel2; ctx.fillRect(0, 0, w, w); ctx.strokeStyle = C.edge; ctx.lineWidth = 3; ctx.strokeRect(0, 0, w, w);
      ctx.globalAlpha = .5; ctx.strokeStyle = acc(st.i); ctx.lineWidth = 2; ctx.strokeRect(40, 40, w - 80, w - 80); }, { cy: cy, both: true });
    /* 面の番号の点 */
    for (var j = 0; j < n; j++) { var on = j === st.i; var ctx = g(); ctx.save(); ctx.globalAlpha *= k0; ctx.fillStyle = on ? C.accent : C.faint;
      ctx.beginPath(); ctx.arc(960 + (j - (n - 1) / 2) * 34, 960, on ? 9 : 6, 0, PI2); ctx.fill(); ctx.restore(); }
  };

  /* ---- carousel: カードの輪が回り、今の 1 枚が手前に来る ---- */
  R.carousel = function (s, lt, d) {
    var items = (s.items || []).map(itemOf), n = Math.max(1, items.length), ts = X.slots(n, d, 500, 900);
    var hh = head(s, lt), st = stepAt(ts, lt, 900), pos = st.i === 0 ? 0 : st.i - 1 + st.k, k0 = P(lt, 0, 900, eio);
    ts.forEach(function (t0, i) { ev(t0, i ? "sweep" : "appear", { i: i }); });
    var Rr = Math.max(520, n * 105), w = 500, h = 380, cy = 520 + hh * .3, list = [];
    items.forEach(function (it, i) {
      var a = (i - pos) * PI2 / n + (1 - k0) * 1.6, x = Math.sin(a) * Rr, z = (1 - Math.cos(a)) * Rr * .9 + (1 - k0) * 1200;
      list.push({ i: i, it: it, a: a, x: x, z: z });
    });
    list.sort(function (p, q) { return q.z - p.z; }).forEach(function (c) {
      var yaw = c.a * .85, hw = w / 2, hh2 = h / 2, cs = Math.cos(yaw), sn = Math.sin(yaw);
      var corner = function (dx, dy) { return [c.x + dx * cs, dy, c.z - dx * sn]; };
      var front = 1 - clamp(Math.abs(Math.atan2(Math.sin(c.a), Math.cos(c.a))) / (PI2 / n) );
      plane(corner(-hw, -hh2), corner(hw, -hh2), corner(-hw, hh2), w, h, function (ctx) {
        card(ctx, c.it, w, h, acc(c.i), .6 * (1 - front), { ts: 46, pad: 50 }); }, { cy: cy, both: true });
    });
    var cur = items[Math.round(pos) % n] || {};
    if (cur.caption) txt(cur.caption, 960, 960, { size: 32, align: "center", color: C.muted, alpha: k0 });
  };

  /* ---- explode: 層が斜め上から見た板として積まれ、間が開いて分かれる ---- */
  R.explode = function (s, lt, d) {
    var items = (s.layers || s.items || []).map(itemOf), n = Math.max(1, items.length), ts = X.slots(n, d, 400, 1400);
    var hh = head(s, lt), gapK = P(lt, ts[n - 1] + 500, ts[n - 1] + 1500, eio), gap = mix(60, Math.min(260, 620 / Math.max(1, n - 1)), gapK), w = 680, dep = 360;
    var ax = 1.0, ay = .62 + Math.sin(lt / 3600) * .05, cy = 500 + hh * .15 + (n - 1) * gap * .5, base = 0;
    ts.forEach(function (t0, i) { ev(t0, "appear", { i: i }); }); ev(ts[n - 1] + 500, "sweep");
    items.forEach(function (it, i) {
      var k = P(lt, ts[i], ts[i] + 700, back); if (k <= 0) return;
      var y = base - i * gap - (1 - k) * -220, col = acc(i);
      var c3 = function (x, z) { var r0 = rot3([x, 0, z], ax, ay); return [r0[0], r0[1] + y, r0[2] + 300]; };
      var ctx = g(); ctx.save(); ctx.globalAlpha *= clamp(k * 1.5);
      plane(c3(-w / 2, dep / 2), c3(w / 2, dep / 2), c3(-w / 2, -dep / 2), w, dep, function (q) {
        q.fillStyle = C.panel; rr(0, 0, w, dep, 22); q.fill(); q.lineWidth = 5; q.strokeStyle = col; q.stroke();
        q.globalAlpha = .18; q.fillStyle = col; rr(0, 0, w, dep, 22); q.fill(); q.globalAlpha = 1;
        if (it.icon) X.iconAny(it.icon, 110, dep / 2, 120, col);
        txt(it.title || "", it.icon ? 200 : 60, dep / 2 + 26, { size: 74, weight: 800, font: F.display, color: C.ink }); }, { cy: cy, both: true });
      /* 横の注記と引き出し線 */
      var edge = p3.apply(null, c3(w / 2, 0).concat([960, cy])), lx = 1440 + (i % 2) * 40, la = P(lt, ts[i] + 300, ts[i] + 800);
      if (la > 0) { ctx.strokeStyle = col; ctx.lineWidth = 2.5; ctx.globalAlpha *= la; ctx.beginPath(); ctx.moveTo(edge.x, edge.y); ctx.lineTo(lx - 16, edge.y); ctx.stroke();
        txt(it.label || it.title || "", lx, edge.y - 6, { size: 30, weight: 800, color: col }); if (it.text) txt(it.text, lx, edge.y + 34, { size: 24, color: C.muted }); }
      ctx.restore();
    });
  };

  /* ---- tunnel: 奥に並んだ枠の中を進み、1 つずつ通り抜ける ---- */
  R.tunnel = function (s, lt, d) {
    var items = (s.items || []).map(itemOf), n = Math.max(1, items.length), ts = X.slots(n, d, 600, 1000), SP = 1800, ctx = g();
    var st = stepAt(ts, lt, 1100), camZ = (st.i === 0 ? 0 : st.i - 1 + st.k) * SP + (1 - P(lt, 0, 900, eo)) * -900 + Math.sin(lt / 1300) * 20;
    ts.forEach(function (t0, i) { ev(t0, i ? "travel" : "appear", { i: i }); });
    /* 奥へ流れる線（速さで伸びる） */
    var speed = st.i > 0 && st.k < 1 ? Math.sin(st.k * Math.PI) : 0, r = rand(17);
    ctx.save(); ctx.strokeStyle = C.accent2; for (var j = 0; j < 70; j++) { var an = r() * PI2, rad = 700 + r() * 500, z = ((r() * 6000 - camZ * 1.0) % 6000 + 6000) % 6000;
      var a = p3(Math.cos(an) * rad, Math.sin(an) * rad, z), b = p3(Math.cos(an) * rad, Math.sin(an) * rad, z + 200 + speed * 900);
      ctx.globalAlpha = .12 + .25 * speed; ctx.lineWidth = 2 * a.s; ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke(); } ctx.restore();
    for (var i = n - 1; i >= 0; i--) {
      var z0 = i * SP - camZ; if (z0 < -FOCAL + 120 || z0 > SP * 3.2) continue;
      var al = clamp((z0 + 900) / 700) * clamp((SP * 3.2 - z0) / (SP * 1.2)), it = items[i], col = acc(i), fw = 1240, fh = 700;
      ctx.save(); ctx.globalAlpha *= al;
      plane([-fw / 2, -fh / 2, z0], [fw / 2, -fh / 2, z0], [-fw / 2, fh / 2, z0], fw, fh, function (q) {
        q.lineWidth = 8; q.strokeStyle = col; rr(0, 0, fw, fh, 30); q.stroke(); q.globalAlpha = .9; q.fillStyle = C.bg1; rr(8, 8, fw - 16, fh - 16, 24); q.fill(); q.globalAlpha = 1;
        txt(String(i + 1).padStart(2, "0"), 70, 110, { size: 44, weight: 800, color: col, font: F.mono });
        if (it.icon) X.iconAny(it.icon, fw / 2, 230, 130, col);
        X.wrap(it.title || "", fw - 160, { size: 86, weight: 800, font: F.display }).slice(0, 2).forEach(function (ln, li) {
          X.rich(ln, fw / 2, (it.icon ? 400 : 330) + li * 100, { size: 86, weight: 800, align: "center", font: F.display }); });
        if (it.text) txt(it.text, fw / 2, (it.icon ? 400 : 330) + 120, { size: 34, color: C.muted, align: "center" }); });
      ctx.restore();
    }
  };

  /* ---- parallax: 奥行きのある風景（重なった層）を横に移り、手前ほど速く動く。中央に題 ---- */
  R.parallax = function (s, lt, d) {
    var ctx = g(), kind = s.scene || "hills", pan = (s.pan === undefined ? 1 : s.pan) * (lt / d) * 900, k0 = P(lt, 0, 1200, eo), r;
    var layers = kind === "city" ? 4 : 5;
    for (var L = 0; L < layers; L++) {
      var depth = (L + 1) / layers, off = pan * depth * depth + (1 - k0) * 300 * depth, base = 560 + depth * 330, col = mixColor(C.bg1, L % 2 ? C.accent : C.accent2, .12 + depth * .5);
      r = rand(31 + L * 17); ctx.save(); ctx.fillStyle = col; ctx.globalAlpha *= .35 + depth * .6; ctx.beginPath();
      if (kind === "city") { ctx.moveTo(-10, H); var x = -((off % 300) + 300); while (x < W + 300) { var bw = 70 + r() * 120, bh = 80 + r() * 260 * (1.3 - depth * .5); ctx.lineTo(x, base - bh); ctx.lineTo(x + bw, base - bh); x += bw + 6 + r() * 14; ctx.lineTo(x, base); } ctx.lineTo(W + 10, H); }
      else if (kind === "space") { ctx.restore(); ctx.save(); ctx.fillStyle = C.ink; for (var q = 0; q < 70; q++) { var sx = ((r() * W * 1.5 - off) % (W * 1.5) + W * 1.5) % (W * 1.5) - W * .25, sy = r() * H, sz = (1 + r() * 2.5) * depth * 1.6;
          ctx.globalAlpha = .25 + depth * .6; ctx.beginPath(); ctx.arc(sx, sy, sz, 0, PI2); ctx.fill(); } }
      else { ctx.moveTo(-10, H); var amp = 60 + (1 - depth) * 60, fr = .002 + r() * .002, ph = r() * 6;
        for (var px = -10; px <= W + 10; px += 20) ctx.lineTo(px, base - amp * (Math.sin((px + off) * fr + ph) * .6 + Math.sin((px + off) * fr * 2.3 + ph * 2) * .4) - 80 * (1 - depth));
        ctx.lineTo(W + 10, H); }
      ctx.closePath(); if (kind !== "space") ctx.fill(); ctx.restore();
    }
    if (kind === "space") { var pl = p3(-380 + pan * .05, -60, 600); ctx.save(); var gr = ctx.createRadialGradient(pl.x - 60, pl.y - 60, 10, pl.x, pl.y, 220 * pl.s);
      gr.addColorStop(0, C.accent2); gr.addColorStop(1, C.bg0); ctx.fillStyle = gr; ctx.globalAlpha *= k0; ctx.beginPath(); ctx.arc(pl.x, pl.y, 220 * pl.s, 0, PI2); ctx.fill(); ctx.restore(); }
    var ty = s.y || 420;
    if (s.title) X.animText(s.title, 960, ty, { size: 96, weight: 900, align: "center", font: F.display }, s.anim || "depth", lt, 300, 1100);
    if (s.text) X.animText(s.text, 960, ty + 90, { size: 36, align: "center", color: C.muted }, "rise", lt, 900, 700);
    ev(300, "title");
  };

  /* ---- swarm: 粒が集まって言葉になり、次の言葉へ形を変える ---- */
  R.swarm = function (s, lt, d) {
    var words = (s.words || s.items || []).map(function (w) { return typeof w === "string" ? w : w.text || w.title || ""; }), n = Math.max(1, words.length);
    var N = s.n || 1500, ts = X.slots(n, d, 300, 900), ctx = g(), size = s.size || 240, r = rand(77), start = [];
    for (var i = 0; i < N; i++) start.push([r() * W, r() * H]);
    var sets = words.map(function (w) { return textPoints(w, N, { size: size, y: 520 }); });
    var st = stepAt(ts, lt, 1300), from = st.i === 0 ? start : sets[st.i - 1], to = sets[st.i] || start, k = st.i === 0 ? eio(lin(lt, ts[0], ts[0] + 1500)) : st.k;
    ts.forEach(function (t0, j) { ev(t0, j ? "sweep" : "reveal", { i: j }); });
    var rr0 = rand(5), jit = rand(9);
    ctx.save();
    for (var p = 0; p < N; p++) {
      var a = from[p], b = to[p], delay = rr0() * .35, kk = clamp((k - delay) / (1 - .35)), e = eio(kk), sw = Math.sin(kk * Math.PI) * (80 + jit() * 140), an = p * 2.4;
      var x = mix(a[0], b[0], e) + Math.cos(an) * sw, y = mix(a[1], b[1], e) + Math.sin(an) * sw;
      if (kk >= 1) { x += Math.sin(lt / 700 + p) * 1.6; y += Math.cos(lt / 900 + p * .7) * 1.6; }
      ctx.fillStyle = acc(p % 3 === 0 ? 1 : 0); ctx.globalAlpha = .75 + .25 * (p % 5) / 4; ctx.fillRect(x - 3.2, y - 3.2, 6.4, 6.4);
    }
    ctx.restore();
    if (s.text) txt(s.text, 960, 880, { size: 36, align: "center", color: C.muted, alpha: P(lt, ts[0] + 900, ts[0] + 1500) });
  };

  /* ---- morph: 形が次の形へ変わり、名前が入れ替わる ---- */
  R.morph = function (s, lt, d) {
    var items = (s.items || []).map(function (it) { return typeof it === "string" ? { shape: it } : it || {}; }), n = Math.max(1, items.length);
    var ts = X.slots(n, d, 500, 900), hh = head(s, lt), st = stepAt(ts, lt, 900), ctx = g(), NP = 160;
    ts.forEach(function (t0, i) { ev(t0, i ? "sweep" : "appear", { i: i }); });
    var A = shapePoints((items[Math.max(0, st.i - 1)] || {}).shape || "circle", NP), B = shapePoints((items[st.i] || {}).shape || "circle", NP), k = st.i === 0 ? 1 : st.k;
    var pts = morph(A, B, k), cx = 700, cy = 560 + hh * .2, R0 = 260 * P(lt, 0, 800, back) * (1 + .03 * Math.sin(lt / 600)), rot = Math.sin(k * Math.PI) * .5;
    var col = st.i === 0 ? acc(0) : mixColor(acc(st.i - 1), acc(st.i), k);
    ctx.save(); ctx.translate(cx, cy); ctx.rotate(rot); ctx.beginPath(); pts.forEach(function (p, i) { if (i) ctx.lineTo(p[0] * R0, p[1] * R0); else ctx.moveTo(p[0] * R0, p[1] * R0); }); ctx.closePath();
    ctx.globalAlpha *= .22; ctx.fillStyle = col; ctx.fill(); ctx.globalAlpha /= .22; ctx.lineWidth = 10; ctx.lineJoin = "round"; ctx.strokeStyle = col; ctx.stroke(); ctx.restore();
    /* 名前（入れ替わる）と、手順の並び */
    items.forEach(function (it, i) {
      var y0 = 340 + i * 96 + hh * .2, on = i === st.i, past = i < st.i, a = P(lt, ts[i] - 200, ts[i] + 300);
      txt(String(i + 1), 1160, y0, { size: 30, weight: 800, color: on ? acc(i) : C.faint, font: F.mono, alpha: .4 + .6 * a });
      txt(it.label || it.shape || "", 1210, y0, { size: on ? 52 : 38, weight: on ? 800 : 600, color: on ? C.ink : past ? C.muted : C.faint, font: F.display, alpha: .4 + .6 * a });
      if (on && it.text) txt(it.text, 1210, y0 + 44, { size: 26, color: C.muted, alpha: k });
    });
  };

  /* ---- barrage: 短い言葉を大きく連打する（言葉ごとに組み方が変わる。**強調** は差し色） ---- */
  R.barrage = function (s, lt, d) {
    var ph = (s.phrases || s.items || []).map(function (p) { return typeof p === "string" ? p : p.text || ""; }), n = Math.max(1, ph.length), ts = X.slots(n, d, 300, 700), ctx = g();
    var st = stepAt(ts, lt, 1), i = st.i, a0 = ts[i], a1 = i < n - 1 ? ts[i + 1] : d, line = ph[i] || "", styles = ["stack", "punch", "slide", "spread"], sty = (s.styles || [])[i] || styles[i % 4];
    ts.forEach(function (t0, j) { ev(t0, j % 2 ? "hit" : "word", { i: j }); if (j % 4 === 1) X.shakeEv(t0 + 80, 10, 300); });
    var out = lin(lt, a1 - 260, a1), k = lin(lt, a0, a0 + 650), em = C.accent;
    /* 切り替わりの帯 */
    var fl = 1 - lin(lt, a0, a0 + 300); if (i > 0 && fl > 0) { ctx.save(); ctx.fillStyle = acc(i); ctx.globalAlpha = .9 * fl; ctx.fillRect(0, 540 - 560 * fl, W, 1120 * fl); ctx.restore(); }
    ctx.save(); ctx.globalAlpha *= 1 - (i < n - 1 ? out : 0); ctx.translate(0, -out * 80);
    var words = line.split(/\s+/).filter(Boolean); if (words.length < 2) words = [line];
    if (sty === "stack") {
      var size0 = Math.min(200, 1500 / Math.max(3, Math.max.apply(null, words.map(function (w) { return w.replace(/\*\*/g, "").length; })))), y = 540 - (words.length - 1) * size0 * .55;
      words.forEach(function (w, j) { var kk = lin(lt, a0 + j * 120, a0 + j * 120 + 450), sz = size0 * (j % 2 ? .78 : 1);
        if (kk <= 0) return; X.rich(w, 960 + (1 - eo(kk)) * (j % 2 ? 200 : -200), y + j * size0 * 1.05, { size: sz, weight: 900, align: "center", font: F.display, emColor: em, alpha: clamp(kk * 2) }); });
    } else if (sty === "punch") {
      var sc = mix(3.2, 1, eo(lin(lt, a0, a0 + 260))) * (1 + .03 * Math.sin(clamp(lin(lt, a0 + 260, a0 + 900)) * Math.PI * 3)), sz2 = Math.min(220, 1600 / Math.max(2, line.replace(/\*\*/g, "").length));
      ctx.translate(960, 520); ctx.scale(sc, sc); ctx.translate(-960, -520); X.rich(line, 960, 590, { size: sz2, weight: 900, align: "center", font: F.display, emColor: em, alpha: clamp(k * 4) });
    } else if (sty === "slide") {
      var sz3 = Math.min(170, 1500 / Math.max(3, line.replace(/\*\*/g, "").length)), wsum = 0, ws = words.map(function (w) { var x0 = tw(w.replace(/\*\*/g, ""), { size: sz3, weight: 900, font: F.display }); wsum += x0; return x0; }), gap = sz3 * .3, x = 960 - (wsum + gap * (words.length - 1)) / 2;
      words.forEach(function (w, j) { var kk = eo(lin(lt, a0 + j * 140, a0 + j * 140 + 500)), dir = j % 2 ? 1 : -1;
        X.rich(w, x + (1 - kk) * dir * 900, 590 + (1 - kk) * dir * 60, { size: sz3, weight: 900, font: F.display, emColor: em, alpha: clamp(kk * 2) }); x += ws[j] + gap; });
    } else {
      var sz4 = Math.min(150, 1400 / Math.max(4, line.replace(/\*\*/g, "").length)), sp = mix(.9, 0, eo(k));
      var plain = line.replace(/\*\*/g, ""), chars = Array.from(plain), wtot = tw(plain, { size: sz4, weight: 800, font: F.display }) + sp * sz4 * (chars.length - 1), cx = 960 - wtot / 2;
      chars.forEach(function (ch, j) { var cw = tw(ch, { size: sz4, weight: 800, font: F.display }); txt(ch, cx, 590, { size: sz4, weight: 800, font: F.display, color: j % 3 === 0 ? em : C.ink, alpha: clamp(k * 2) }); cx += cw + sp * sz4; });
    }
    ctx.restore();
    /* 下の小さな進み */
    for (var j = 0; j < n; j++) { ctx.save(); ctx.fillStyle = j <= i ? acc(j) : C.faint; ctx.fillRect(960 - n * 22 + j * 44, 940, 30, 6); ctx.restore(); }
  };

  /* ---- rotator: 前後の言葉は止まったまま、間の語だけが入れ替わる（「AI で [速く] 作る」） ---- */
  R.rotator = function (s, lt, d) {
    var words = s.words || [], n = Math.max(1, words.length), ts = X.slots(n, d, 600, 900), ctx = g(), size = s.size || 124;
    var o = { size: size, weight: 800, font: F.display }, bw = s.before ? tw(s.before, o) : 0, aw = s.after ? tw(s.after, o) : 0, gap = size * .3;
    var st = stepAt(ts, lt, 650), cur = words[st.i] || "", prev = words[Math.max(0, st.i - 1)] || "", k = st.i === 0 ? eo(lin(lt, ts[0], ts[0] + 650)) : st.k;
    ts.forEach(function (t0, i) { ev(t0, "word", { i: i }); });
    var wc = tw(cur, o) + size * .6, wp = st.i === 0 ? size * .6 : tw(prev, o) + size * .6, ww = mix(wp, wc, k), total = bw + gap + ww + (aw ? gap + aw : 0), x0 = 960 - total / 2, y = s.y || 560, k0 = P(lt, 0, 600);
    ctx.save(); ctx.globalAlpha *= k0;
    if (s.before) txt(s.before, x0, y, Object.assign({ color: C.ink }, o));
    var bx = x0 + bw + gap, col = acc(st.i);
    ctx.save(); rr(bx, y - size * 1.0, ww, size * 1.3, size * .22); ctx.fillStyle = col; ctx.globalAlpha *= .16; ctx.fill(); ctx.restore();
    ctx.save(); ctx.strokeStyle = col; ctx.lineWidth = 4; rr(bx, y - size * 1.0, ww, size * 1.3, size * .22); ctx.stroke(); ctx.clip();
    if (st.i > 0 && k < 1) txt(prev, bx + ww / 2, y - eo(k) * size * 1.3, Object.assign({ align: "center", color: acc(st.i - 1) }, o));
    txt(cur, bx + ww / 2, y + (1 - eo(k)) * size * 1.3, Object.assign({ align: "center", color: col }, o));
    ctx.restore();
    if (s.after) txt(s.after, bx + ww + gap, y, Object.assign({ color: C.ink }, o));
    ctx.restore();
    if (s.text) txt(s.text, 960, y + size * 1.2, { size: 34, align: "center", color: C.muted, alpha: P(lt, 600, 1200) });
  };

  /* ---- textpath: 文字が線（円・波・弧・渦）に沿って並び、流れる。中央に大きな言葉 ---- */
  R.textpath = function (s, lt, d) {
    var ctx = g(), kind = s.path || "circle", size = s.size || 40, o = { size: size, weight: 800, font: F.display }, base = (s.text || "").replace(/\*\*/g, "");
    var k = P(lt, 200, 1800, eio), spin = lt * .00012 * (s.speed === undefined ? 1 : s.speed);
    var path = function (u) { /* u: 0..1 → [x, y, 角度] */
      if (kind === "wave") { var x = -100 + u * 2120; return [x, 540 + Math.sin(x / 190 + lt / 900) * 110, Math.atan(Math.cos(x / 190 + lt / 900) * 110 / 190)]; }
      if (kind === "arc") { var a = Math.PI * (1.08 + u * .84), Ra = 620; return [960 + Math.cos(a) * Ra, 900 + Math.sin(a) * Ra, a + Math.PI / 2]; }
      if (kind === "spiral") { var a2 = -Math.PI / 2 + u * PI2 * 2.2 + spin * 3, R2 = 430 - u * 300; return [960 + Math.cos(a2) * R2, 540 + Math.sin(a2) * R2, a2 + Math.PI / 2]; }
      var a3 = -Math.PI / 2 + u * PI2 + spin * PI2, R3 = s.radius || 340; return [960 + Math.cos(a3) * R3, 540 + Math.sin(a3) * R3, a3 + Math.PI / 2];
    };
    var len = kind === "wave" ? 2300 : kind === "arc" ? 620 * Math.PI * .84 : kind === "spiral" ? 2 * Math.PI * 280 * 2.2 : 2 * Math.PI * (s.radius || 340);
    var text = base, sep = s.sep === undefined ? "  •  " : s.sep;
    if (kind === "circle" || kind === "wave") { while (tw(text + sep, o) < len && text.length < 400) text += sep + base; }
    var chars = Array.from(text), w = tw(text, o), off = kind === "wave" ? ((lt * .12) % (tw(base + sep, o))) : 0, u0 = kind === "arc" ? (1 - Math.min(1, w / len)) / 2 : 0, acc0 = 0;
    ctx.save(); ctx.font = o.weight + " " + size + "px " + o.font; ctx.textAlign = "center"; ctx.textBaseline = "middle";
    chars.forEach(function (ch, i) {
      var cw = tw(ch, o), pos = acc0 + cw / 2 - off; acc0 += cw; var u = u0 + pos / len; if (u < 0 || u > 1) return;
      var vis = clamp((k * chars.length - i) / 6); if (vis <= 0) return;
      var p = path(u); ctx.save(); ctx.translate(p[0], p[1]); ctx.rotate(p[2]); ctx.globalAlpha *= vis; ctx.fillStyle = (s.color && C[s.color]) || (i % 12 < 1 ? C.accent : C.ink);
      ctx.fillText(ch, 0, (1 - eo(vis)) * -30); ctx.restore();
    });
    ctx.restore();
    if (s.center) { X.animText(s.center, 960, (kind === "arc" ? 760 : 560) + (s.icon ? 60 : 0), { size: s.centerSize || 110, weight: 900, align: "center", font: F.display }, s.anim || "pop", lt, 500, 800); }
    if (s.icon) X.drawIcon(s.icon, 960, kind === "arc" ? 560 : 440, 130 * P(lt, 300, 900, back), { color: C.accent, lt: lt });
    if (s.sub) txt(s.sub, 960, kind === "arc" ? 860 : 680, { size: 32, align: "center", color: C.muted, alpha: P(lt, 900, 1500) });
    ev(200, "reveal");
  };

  /* ---- emphasis: 文章は静かに置き、**強調** の語だけが説明の順に光って動く ---- */
  R.emphasis = function (s, lt, d) {
    var ctx = g(), size = s.size || 64, maxW = 1560, text = s.text || "", hh = head(s, lt);
    /* 文字ごとに、強調の番号（-1 は地の文）を付けて折り返す */
    var segs = String(text).split("**"), units = [], emN = 0;
    segs.forEach(function (p, i) { if (!p) return; var em = i % 2 === 1 ? emN++ : -1; (p.match(/[A-Za-z0-9_\-.'’]+|\s+|./g) || []).forEach(function (u) { units.push({ t: u, em: em }); }); });
    var ts = X.slots(Math.max(1, emN), d, 900, 900), lines = [[]], lw = 0;
    units.forEach(function (u) { var o0 = { size: size, weight: u.em >= 0 ? 800 : 500, font: F.sans }, w = tw(u.t, o0);
      if (lw + w > maxW && lines[lines.length - 1].length && !/^\s+$/.test(u.t)) { lines.push([]); lw = 0; } if (!lines[lines.length - 1].length && /^\s+$/.test(u.t)) return;
      lines[lines.length - 1].push({ t: u.t, em: u.em, w: w, o: o0 }); lw += w; });
    var lh = size * 1.7, y0 = 540 - (lines.length - 1) * lh / 2 + hh * .3, k0 = P(lt, 0, 800);
    ts.forEach(function (t0, i) { ev(t0, "emphasize", { i: i }); });
    var focus = -1; ts.forEach(function (t0, i) { if (lt >= t0) focus = i; });
    lines.forEach(function (ln, li) {
      var tot = ln.reduce(function (a, u) { return a + u.w; }, 0), x = 960 - tot / 2, y = y0 + li * lh;
      ln.forEach(function (u) {
        var on = u.em >= 0 && lt >= ts[u.em], ka = on ? eo(lin(lt, ts[u.em], ts[u.em] + 500)) : 0, cur = u.em === focus, col = u.em >= 0 ? acc(u.em) : C.ink;
        var dim = u.em < 0 ? (focus >= 0 ? .55 : 1) : 1;
        if (on) { ctx.save(); ctx.fillStyle = col; ctx.globalAlpha *= (cur ? .22 : .1) * ka; rr(x - 6, y - size * .95, (u.w + 12) * ka, size * 1.25, 10); ctx.fill(); ctx.restore();
          if (cur) { ctx.save(); ctx.fillStyle = col; ctx.fillRect(x, y + size * .2, u.w * ka, 6); ctx.restore(); } }
        var pop = cur ? 1 + .12 * Math.sin(clamp(lin(lt, ts[u.em], ts[u.em] + 500)) * Math.PI) : 1;
        ctx.save(); ctx.translate(x + u.w / 2, y - size * .35); ctx.scale(pop, pop); ctx.translate(-(x + u.w / 2), -(y - size * .35));
        txt(u.t, x, y - (cur ? ka * 4 : 0), Object.assign({}, u.o, { color: on ? col : u.em >= 0 ? C.ink : C.ink, alpha: k0 * dim }));
        ctx.restore(); x += u.w;
      });
    });
  };

  /* ---- 文字の出方: depth 奥から迫る / unfold 下を軸に起き上がる（遠近） / swirl 渦を巻いて集まる ---- */
  X.textAnims.depth = function (line, x, y, o, k, lt, a0, dur) {
    var ctx = g(), cs = X.charLayout(line, x, o), n = cs.length, size = o.size || 30, al = o.alpha === undefined ? 1 : o.alpha;
    cs.forEach(function (c, i) { var kk = clamp(k * 1.6 - i / Math.max(1, n) * .6), e = eo(kk); if (kk <= 0) return;
      var z = (1 - e) * 2600, p = p3(c.x + c.w / 2 - 960, y - size * .35 - 540, z);
      ctx.save(); ctx.translate(p.x, p.y); ctx.scale(p.s, p.s);
      if ("filter" in ctx && kk < 1) ctx.filter = "blur(" + ((1 - e) * 6).toFixed(1) + "px)";
      txt(c.ch, 0, size * .35, { size: size, weight: c.o.weight, font: c.o.font, align: "center", color: c.em ? (o.emColor || C.accent) : (o.color || C.ink), alpha: al * clamp(kk * 2) }); ctx.restore(); });
  };
  X.textAnims.unfold = function (line, x, y, o, k, lt, a0, dur) {
    var ctx = g(), size = o.size || 30, total = tw(String(line).replace(/\*\*/g, ""), o), mid = o.align === "center" ? x : o.align === "right" ? x - total / 2 : x + total / 2;
    var e = back(k), sy = Math.max(.02, e), skew = (1 - Math.min(1, e)) * .5;
    ctx.translate(mid, y + size * .2); ctx.transform(1, 0, 0, sy, 0, 0); ctx.transform(1 + skew * .4, 0, 0, 1, 0, 0); ctx.translate(-mid, -(y + size * .2));
    X.rich(line, x, y, Object.assign({}, o, { alpha: (o.alpha === undefined ? 1 : o.alpha) * clamp(k * 3) }));
    ctx.globalAlpha = .25 * (1 - k); ctx.fillStyle = C.bg0; ctx.fillRect(mid - total / 2 - 10, y - size, total + 20, size * 1.3);
  };
  X.textAnims.swirl = function (line, x, y, o, k, lt, a0, dur) {
    var cs = X.charLayout(line, x, o), n = cs.length, size = o.size || 30, al = o.alpha === undefined ? 1 : o.alpha, ctx = g(), cx = 960, cy = y - size * .35;
    cs.forEach(function (c, i) { var kk = clamp(k * 1.5 - i / Math.max(1, n) * .5), e = eo(kk); if (kk <= 0) return;
      var tx = c.x + c.w / 2, an = (1 - e) * (4 + i * .15), rad = (1 - e) * (300 + i * 14), px = mix(cx, tx, e) + Math.cos(an + i) * rad, py = cy + Math.sin(an + i) * rad * .6;
      ctx.save(); ctx.translate(px, py); ctx.rotate((1 - e) * 3); txt(c.ch, 0, size * .35, { size: size, weight: c.o.weight, font: c.o.font, align: "center", color: c.em ? (o.emColor || C.accent) : (o.color || C.ink), alpha: al * clamp(kk * 2) }); ctx.restore(); });
  };

  /* ---- 切り替え: depth 前の場面が奥へ沈み、次が手前から定まる / swing 前の場面が左端を軸に扉のように奥へ開く ---- */
  X.transitions.depth = { ms: 850, draw: function (prev, next, u) {
    var ctx = g(), sp = mix(1, .55, u), sn = mix(1.5, 1, u);
    prev({ xf: function () { ctx.translate(960, 540); ctx.scale(sp, sp); ctx.translate(-960, -540); }, alpha: 1 - u, blur: u * 8 });
    next({ xf: function () { ctx.translate(960, 540); ctx.scale(sn, sn); ctx.translate(-960, -540); }, alpha: clamp(u * 1.6), blur: (1 - u) * 10 });
  } };
  X.transitions.swing = { ms: 900, draw: function (prev, next, u) {
    var ctx = g(), NS = 12, a = u * Math.PI * .55, wst = 1920 / NS;
    next();
    if (u >= 1) return;
    ctx.save(); ctx.fillStyle = "#000"; ctx.globalAlpha = .35 * (1 - u); ctx.fillRect(0, 0, 1920, 1080); ctx.restore();
    for (var i = 0; i < NS; i++) { (function (i) {
      var x0 = i * wst, x1 = x0 + wst, z0 = Math.sin(a) * x0, z1 = Math.sin(a) * x1, X0 = Math.cos(a) * x0, X1 = Math.cos(a) * x1;
      var p0 = p3(X0 - 960, 0, z0), p1 = p3(X1 - 960, 0, z1); if (p1.x <= p0.x + .5) return;
      var sc = mix(p0.s, p1.s, .5);
      prev({ xf: function () { ctx.translate(p0.x, 540); ctx.scale((p1.x - p0.x) / wst, sc); ctx.translate(-x0, -540); },
             clip: function () { ctx.beginPath(); ctx.rect(x0, 0, wst + 1, 1080); ctx.clip(); } });
    })(i); }
  } };

  /* ---- 演出の層: cubes 奥行きの中を回りながら漂う針金の箱 ---- */
  X.fxUnder.cubes = 1;
  X.fxs.cubes = function (o, lt) {
    var ctx = g(), r = rand(o.seed || 23), n = o.n || 14, E = [[0, 1], [1, 2], [2, 3], [3, 0], [4, 5], [5, 6], [6, 7], [7, 4], [0, 4], [1, 5], [2, 6], [3, 7]];
    ctx.save(); ctx.lineWidth = 2;
    for (var i = 0; i < n; i++) {
      var bx = (r() - .5) * 2600, by = (r() - .5) * 1400, z = ((r() * 3600 - lt * .08) % 3600 + 3600) % 3600 - 600, sz = 60 + r() * 120, ax = lt * .0004 * (r() + .3), ay = lt * .0005 * (r() + .3), col = i % 2 ? C.accent : C.accent2;
      var vs = [[-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1], [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1]].map(function (v) { var q = rot3([v[0] * sz, v[1] * sz, v[2] * sz], ax, ay); return p3(bx + q[0], by + q[1], z + q[2]); });
      ctx.strokeStyle = col; ctx.globalAlpha = (o.alpha === undefined ? .3 : o.alpha) * clamp((z + 600) / 800) * clamp((3000 - z) / 1200);
      ctx.beginPath(); E.forEach(function (e) { ctx.moveTo(vs[e[0]].x, vs[e[0]].y); ctx.lineTo(vs[e[1]].x, vs[e[1]].y); }); ctx.stroke();
    }
    ctx.restore();
  };
}); }
