// pane が分割されながら 1 → 4 に増えていく（右に割る → 右を上下に → 左を上下に）
var f2 = H.P(lt, d * .18, d * .18 + 700, H.eio), f3 = H.P(lt, d * .32, d * .32 + 700, H.eio), f4 = H.P(lt, d * .46, d * .46 + 700, H.eio);
var box = H.appWindow(150, 150, 1620, 800, "Sodashitsu — api-server");
var sx = box.x, sy = box.y, sw = 280;
ctx.fillStyle = H.C.bg1; ctx.fillRect(sx, sy, sw, box.h);
H.txt("WORKSPACES", sx + 24, sy + 44, { size: 15, font: H.F.mono, color: H.C.accent, spacing: 2 });
var names = s.panes, vis = [H.P(lt, 200, 700), f2, f3, f4];
var states = ["working", lt > d * .2 ? "working" : "none", lt > d * .34 ? (lt > d * .8 ? "idle" : "working") : "none", "none"];
var yy = sy + 90;
H.txt("api-server", sx + 28, yy, { size: 21, weight: 700 }); yy += 42;
names.forEach(function (n, i) {
  if (vis[i] <= .01) return;
  ctx.save(); ctx.globalAlpha *= vis[i];
  H.stateMark(sx + 44, yy - 7, states[i], lt, 7); H.txt(n, sx + 64, yy, { size: 18 });
  ctx.restore(); yy += 34 * vis[i];
});
var gx = sx + sw + 10, gy = sy + 10, gw = box.w - sw - 20, gh = box.h - 20, gap = 8;
var lw = gw * (1 - .5 * f2), topH = gh * (1 - .5 * f4), rtop = gh * (1 - .5 * f3);
var rects = [[gx, gy, lw, topH], [gx + lw + gap, gy, gw - lw - gap, rtop], [gx + lw + gap, gy + rtop + gap, gw - lw - gap, gh - rtop - gap], [gx, gy + topH + gap, lw, gh - topH - gap]];
rects.forEach(function (r, i) {
  if (vis[i] <= .01 || r[2] < 40 || r[3] < 40) return;
  ctx.save(); ctx.globalAlpha *= vis[i];
  H.rr(r[0], r[1], r[2], r[3], 10); ctx.fillStyle = H.C.code; ctx.fill(); ctx.strokeStyle = H.C.edge; ctx.lineWidth = 1.2; ctx.stroke();
  ctx.save(); H.rr(r[0], r[1], r[2], r[3], 10); ctx.clip();
  ctx.fillStyle = H.C.panel2; ctx.fillRect(r[0], r[1], r[2], 40);
  H.stateMark(r[0] + 22, r[1] + 20, states[i], lt, 8);
  H.txt(names[i], r[0] + 42, r[1] + 28, { size: 20, weight: 700 });
  var start = [0.05, 0.2, 0.34, 0.48][i] * d, k = H.P(lt, start, start + d * .4, function (x) { return x; });
  var ls = s.lines[i], shown = ls.length * k, maxL = Math.floor((r[3] - 56) / 30);
  ls.slice(0, Math.ceil(shown)).slice(-maxL).forEach(function (ln, j, arr) {
    var last = j === arr.length - 1 && shown < ls.length;
    var col = /✓/.test(ln) ? H.C.ok : /^[›$]/.test(ln) ? H.C.codeInk : /[✗?]/.test(ln) ? H.C.warn : H.C.codeMuted;
    H.txt(last ? H.typed(ln, shown - Math.floor(shown)) : ln, r[0] + 16, r[1] + 72 + j * 30, { size: 18, font: H.F.mono, color: col });
  });
  ctx.restore(); ctx.restore();
});
