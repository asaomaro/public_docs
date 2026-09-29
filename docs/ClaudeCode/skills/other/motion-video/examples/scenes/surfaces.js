// 左にブラウザ（window の部品を縮小して置く）、右に端末版（罫線の文字で描く）
var m = H.P(lt, 200, 1100, H.eio);
H.sub("window", s.win, lt, d, { x: -40, y: 200, scale: .5, alpha: m });
H.txt("ブラウザ", 460, 260, { size: 30, weight: 800, color: H.C.accent2, align: "center", alpha: H.P(lt, 600, 1200) });
var tx = H.mix(1960, 990, m), ty = 290, tw0 = 820, th = 440;
ctx.save(); ctx.globalAlpha *= m;
H.panel(tx, ty, tw0, th, { fill: H.C.code, r: 14 });
ctx.save(); H.rr(tx, ty, tw0, th, 14); ctx.clip();
ctx.fillStyle = H.C.codeBar; ctx.fillRect(tx, ty, tw0, 40);
H.txt("~/src/api-server — soda", tx + tw0 / 2, ty + 27, { size: 16, font: H.F.mono, color: H.C.codeMuted, align: "center" });
var rows = s.tui, k = H.P(lt, 900, 900 + rows.length * 120, function (x) { return x; });
rows.slice(0, Math.floor(k * rows.length)).forEach(function (r, i) {
  H.txt(r, tx + 22, ty + 74 + i * 32, { size: 19, font: H.F.mono, color: /[✓◐!]/.test(r) ? H.C.codeInk : H.C.codeMuted });
});
if (k >= 1) { ctx.fillStyle = H.C.panel2; ctx.fillRect(tx, ty + th - 40, tw0, 40);
  H.txt(" NORMAL  prefix+? ヘルプ   prefix+o 通知へ移動", tx + 12, ty + th - 13, { size: 16, font: H.F.mono, color: H.C.codeInk }); }
ctx.restore(); ctx.restore();
H.txt("端末版　$ soda", 1400, 260, { size: 30, weight: 800, color: H.C.accent2, align: "center", alpha: H.P(lt, 900, 1500) });
H.txt("同じ session を、同じ操作で", 960, 160, { size: 34, color: H.C.muted, align: "center", alpha: H.P(lt, d * .45, d * .45 + 800) });
