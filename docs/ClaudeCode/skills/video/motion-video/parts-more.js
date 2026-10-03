/* motion-video parts-more — 場面の割り付けの型（layout）・語の雲（wordcloud）・巨大な文字（bigtype）。
 * layout は、部品を縮小して枠に並べる型。枠の中身（slots）は普通の部品の台本（type と項目）を書く。 */
if (!window.__mvPartsMore) { window.__mvPartsMore = 1; (window.MotionVideoParts = window.MotionVideoParts || []).push(function (R, X) {
  "use strict";
  var C = X.C, F = X.F, P = X.P, lin = X.lin, eo = X.eo, eio = X.eio, back = X.back, clamp = X.clamp, mix = X.mix;
  var txt = X.txt, tw = X.tw, rr = X.rr, acc = X.accentAt, ev = X.sfxEv, g = X.g, PI2 = Math.PI * 2;
  function title(s, lt, x, y, size, align) {
    if (!s.title) return 0;
    var lines = X.wrap(s.title, align === "center" ? 1500 : 760, { size: size, weight: 800, font: F.display });
    lines.forEach(function (ln, i) { X.animText(ln, x, y + i * size * 1.25, { size: size, weight: 800, font: F.display, align: align }, s.anim || "rise", lt, 200 + i * 180, 700); });
    return lines.length * size * 1.25;
  }
  /* 枠の中に部品を縮小して描く（x, y は枠の左上、w は枠の幅。16:9 で収める） */
  function slot(sp, lt, d, x, y, w, frame, i) {
    var ctx = g(), sc = w / 1920, h = 1080 * sc;
    if (frame) { ctx.save(); ctx.shadowColor = C.shadow; ctx.shadowBlur = 30; ctx.shadowOffsetY = 12; rr(x, y, w, h, 18); ctx.fillStyle = C.bg1; ctx.fill(); ctx.restore();
      ctx.save(); rr(x, y, w, h, 18); ctx.clip(); }
    X.sub(sp.type || "statement", sp, lt, d, { x: x, y: y, scale: sc });
    if (frame) { ctx.restore(); ctx.save(); ctx.strokeStyle = acc(i || 0); ctx.lineWidth = 2.5; rr(x, y, w, h, 18); ctx.stroke(); ctx.restore(); }
    return h;
  }
  function cap(t, x, y, lt, a, align) { if (t) txt(t, x, y, { size: 30, weight: 800, align: align || "center", alpha: P(lt, a, a + 500) }); }

  R.layout = function (s, lt, d) {
    var ctx = g(), sl = s.slots || [], tp = s.template || "trio";
    if (tp === "trio") {
      var th = title(s, lt, 960, 210, 56, "center"), n = Math.min(3, sl.length), w = 520, gap = 60, x0 = 960 - (w * n + gap * (n - 1)) / 2, y = 230 + th;
      sl.slice(0, 3).forEach(function (sp, i) { var a = 500 + i * 350, k = P(lt, a, a + 600, back); ev(a, "appear", { i: i }); if (k <= 0) return;
        var x = x0 + i * (w + gap); ctx.save(); ctx.translate(x + w / 2, y + 150); ctx.scale(k, k); ctx.translate(-(x + w / 2), -(y + 150));
        var h = slot(sp, lt - a, d - a, x, y, w, true, i); ctx.restore(); cap(sp.caption, x + w / 2, y + h + 50, lt, a + 300); });
    } else if (tp === "inset") {
      var y1 = 300, th2 = title(s, lt, 140, y1, 64, "left");
      if (s.text) X.wrap(s.text, 700, { size: 30 }).forEach(function (ln, i) { X.rich(ln, 140, y1 + th2 + 30 + i * 46, { size: 30, color: C.muted, alpha: P(lt, 700 + i * 120, 1200 + i * 120) }); });
      var sp = sl[0] || {}, a2 = 500, k2 = P(lt, a2, a2 + 800, eio); ev(a2, "appear");
      if (k2 > 0) { ctx.save(); ctx.globalAlpha *= k2; ctx.translate((1 - k2) * 120, 0); var wx = 960, wy = 190, ww = 860;
        var inner = X.appWindow(wx, wy, ww, ww * 9 / 16 + 46, sp.windowTitle || ""); ctx.save(); ctx.beginPath(); ctx.rect(inner.x, inner.y, inner.w, inner.h); ctx.clip();
        X.sub(sp.type || "statement", sp, lt - a2, d - a2, { x: inner.x, y: inner.y, scale: inner.w / 1920 }); ctx.restore(); ctx.restore(); }
    } else if (tp === "collage") {
      var pos = [[140, 200, -4], [1000, 170, 3], [260, 560, 2.5], [1060, 540, -3]];
      title(s, lt, 960, 540, 60, "center");
      sl.slice(0, 4).forEach(function (sp, i) { var a = 300 + i * 300, k = P(lt, a, a + 700, back), p = pos[i]; ev(a, "appear", { i: i }); if (k <= 0) return;
        var w = 700, h = w * 9 / 16; ctx.save(); ctx.translate(p[0] + w / 2, p[1] + h / 2); ctx.rotate(p[2] * Math.PI / 180 * k); ctx.scale(k, k); ctx.translate(-(p[0] + w / 2), -(p[1] + h / 2));
        ctx.fillStyle = "#fff"; ctx.shadowColor = C.shadow; ctx.shadowBlur = 40; rr(p[0] - 12, p[1] - 12, w + 24, h + 60, 8); ctx.fill(); ctx.shadowBlur = 0;
        slot(sp, lt - a, d - a, p[0], p[1], w, false, i); if (sp.caption) txt(sp.caption, p[0] + w / 2, p[1] + h + 36, { size: 24, weight: 700, align: "center", color: "#333" }); ctx.restore(); });
      if (s.title) { var tk = P(lt, 300 + sl.length * 300, 900 + sl.length * 300); ctx.save(); ctx.globalAlpha *= tk; var tw0 = tw(s.title, { size: 60, weight: 800, font: F.display }) + 80;
        X.panel(960 - tw0 / 2, 470, tw0, 110, { fill: C.accent, stroke: C.accent, r: 55 }); txt(s.title, 960, 545, { size: 60, weight: 800, align: "center", font: F.display, color: C.onAccent }); ctx.restore(); }
    } else if (tp === "fullbleed") {
      var img = X.img(s.src), kb = mix(1.04, 1.14, lt / d);
      if (img && img.complete && img.naturalWidth) { var iw = img.naturalWidth, ih = img.naturalHeight, sc = Math.max(1920 / iw, 1080 / ih) * kb;
        ctx.save(); ctx.globalAlpha *= P(lt, 0, 900); ctx.drawImage(img, 960 - iw * sc / 2 + (s.pan === "left" ? -60 : 60) * lt / d, 540 - ih * sc / 2, iw * sc, ih * sc); ctx.restore(); }
      else { var bgG = ctx.createLinearGradient(0, 0, 1920, 1080); bgG.addColorStop(0, C.accent); bgG.addColorStop(1, C.accent2); ctx.save(); ctx.globalAlpha *= .35; ctx.fillStyle = bgG; ctx.fillRect(0, 0, 1920, 1080); ctx.restore(); }
      var shade = ctx.createLinearGradient(0, 400, 0, 1080); shade.addColorStop(0, "rgba(0,0,0,0)"); shade.addColorStop(1, "rgba(0,0,0,.75)"); ctx.fillStyle = shade; ctx.fillRect(0, 400, 1920, 680);
      var ty = 760 - (s.text ? 60 : 0); if (s.title) X.animText(s.title, 140, ty, { size: 84, weight: 900, font: F.display, color: "#ffffff" }, s.anim || "mask", lt, 400, 800);
      if (s.text) X.animText(s.text, 140, ty + 80, { size: 34, weight: 600, color: "#e6edf3" }, "rise", lt, 900, 700);
    } else if (tp === "focus") {
      var sp2 = sl[0] || {}, a3 = 300, k3 = P(lt, a3, a3 + 800, eio), w3 = 1180, h3 = w3 * 9 / 16, x3 = 960 - w3 / 2, y3 = 200;
      ctx.save(); ctx.fillStyle = "rgba(0,0,0,.45)"; ctx.globalAlpha *= k3; ctx.fillRect(0, 0, 1920, 1080); ctx.restore();
      if (s.title) X.animText(s.title, 960, 150, { size: 46, weight: 800, align: "center", font: F.display }, s.anim || "rise", lt, 200, 700);
      ctx.save(); ctx.translate(960, y3 + h3 / 2); var zk = mix(.8, 1, k3); ctx.scale(zk, zk); ctx.translate(-960, -(y3 + h3 / 2)); ctx.globalAlpha *= k3;
      ctx.save(); ctx.strokeStyle = C.accent; ctx.globalAlpha *= .4 + .3 * Math.sin(lt / 400); ctx.lineWidth = 6; rr(x3 - 14, y3 - 14, w3 + 28, h3 + 28, 26); ctx.stroke(); ctx.restore();
      slot(sp2, lt - a3, d - a3, x3, y3, w3, true, 0); ctx.restore(); ev(a3, "highlight");
      cap(sp2.caption, 960, y3 + h3 + 60, lt, a3 + 600);
    } else if (tp === "split2") {
      title(s, lt, 960, 210, 52, "center");
      var w4 = 800, y4 = 300; [0, 1].forEach(function (i) { var sp3 = sl[i]; if (!sp3) return; var a = 400 + i * 450, k = P(lt, a, a + 700, eo); ev(a, "appear", { i: i }); if (k <= 0) return;
        var x = i ? 1920 - 120 - w4 : 120; ctx.save(); ctx.globalAlpha *= k; ctx.translate((1 - k) * (i ? 80 : -80), 0); var h = slot(sp3, lt - a, d - a, x, y4, w4, true, i); ctx.restore(); cap(sp3.caption, x + w4 / 2, y4 + h + 54, lt, a + 300); });
      var bk = P(lt, 1200, 1700, back), btw = s.between || "vs";
      if (bk > 0) { ctx.save(); ctx.translate(960, y4 + 225); ctx.scale(bk, bk); ctx.fillStyle = C.accent; ctx.beginPath(); ctx.arc(0, 0, 50, 0, PI2); ctx.fill();
        if (btw === "arrow") X.drawIcon("arrow-right", 0, 0, 54, { color: C.onAccent, k: 1 }); else txt(btw === "vs" ? "VS" : btw, 0, 12, { size: 32, weight: 900, align: "center", color: C.onAccent }); ctx.restore(); ev(1200, "hit"); }
    }
  };

  var WC = new WeakMap();
  function cloudLayout(s) {
    var c = WC.get(s); if (c) return c;
    var words = (s.words || []).map(function (w, i) { return typeof w === "string" ? { text: w, weight: 1, i: i } : { text: w.text, weight: w.weight || 1, i: i }; });
    var mx = Math.max.apply(null, words.map(function (w) { return w.weight; }).concat([1]));
    words.sort(function (a, b) { return b.weight - a.weight; });
    var placed = [], cx = 960, cy = s.heading ? 590 : 540;
    words.forEach(function (w) {
      var size = 34 + 86 * (w.weight / mx), bw = tw(w.text, { size: size, weight: 800, font: F.display }) + 24, bh = size * 1.15, t = 0, x = cx, y = cy, ok = false;
      for (var step = 0; step < 2500 && !ok; step++) { t = step * .35; x = cx + Math.cos(t) * t * 6.5 * 1.6; y = cy + Math.sin(t) * t * 6.5 * .8;
        ok = x - bw / 2 > 100 && x + bw / 2 < 1820 && y - bh / 2 > (s.heading ? 280 : 150) && y + bh / 2 < 900 && placed.every(function (p) { return Math.abs(p.x - x) * 2 > p.w + bw || Math.abs(p.y - y) * 2 > p.h + bh; }); }
      if (ok) placed.push({ text: w.text, x: x, y: y, w: bw, h: bh, size: size, i: w.i, big: w.weight / mx });
    });
    c = placed; WC.set(s, c); return c;
  }
  R.wordcloud = function (s, lt, d) {
    var ctx = g(); X.heading(s, lt);
    var ws = cloudLayout(s), per = Math.min(160, d * .6 / Math.max(1, ws.length));
    ws.forEach(function (w, n) { var a = 300 + n * per, k = P(lt, a, a + 500, back); if (n < 14) ev(a, "word", { i: n }); if (k <= 0) return;
      var dx = Math.sin(lt / 1800 + w.i) * 6, dy = Math.cos(lt / 2100 + w.i * 1.7) * 5;
      ctx.save(); ctx.translate(w.x + dx, w.y + dy); ctx.scale(k, k); if (w.big > .8 && s.rotate !== false) {}
      txt(w.text, 0, w.size * .36, { size: w.size, weight: 800, align: "center", font: F.display, color: n === 0 ? C.accent : w.big > .5 ? acc(n) : C.muted, alpha: .4 + .6 * w.big });
      ctx.restore(); });
  };

  R.bigtype = function (s, lt, d) {
    var ctx = g(), big = s.big || s.text || "", o = { size: s.size || 380, weight: 900, font: F.display }, w = Math.max(400, tw(big, o) + 160), sp = (s.speed || 1) * .05;
    var off = (lt * sp) % w, k = P(lt, 0, 900);
    ctx.save(); ctx.globalAlpha *= k * .9; ctx.font = X.fontOf ? X.fontOf(o) : (o.weight + " " + o.size + "px " + o.font); ctx.lineWidth = 3; ctx.strokeStyle = C.edge;
    for (var x = -off; x < 1920; x += w) ctx.strokeText(big, x, 540 + o.size * .35);
    ctx.restore();
    if (s.text && s.big) X.wrap(s.text, 1400, { size: 76, weight: 800, font: F.display }).forEach(function (ln, i, arr) {
      X.animText(ln, 960, 540 - (arr.length - 1) * 50 + i * 100 + 26, { size: 76, weight: 800, font: F.display, align: "center" }, s.anim || "mask", lt, 400 + i * 200, 800); });
    if (s.sub) X.animText(s.sub, 960, 800, { size: 34, weight: 700, align: "center", color: C.accent }, "rise", lt, 1200, 700);
    ev(400, "hit");
  };
}); }
