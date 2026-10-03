/* 約 5.9 倍: 青（450nm）と赤（700nm）の散らばりやすさを、太い棒で比べる。青の棒が赤の 5.9 倍まで伸びる */
ctx.lineJoin = "round"; var B = s.box, X0 = B.x + 250, W = B.w - 330, k = H.eo(H.clamp((lt - 200) / 1400)), unit = W / 6.2;
[["青", "450nm", "#4aa8ff", 5.9, .36], ["赤", "700nm", "#ff6a5c", 1, .72]].forEach(function (r) {
  var y = B.y + B.h * r[4], w = unit * r[3] * (r[3] > 1 ? k : H.clamp(k * 4));
  ctx.fillStyle = r[2]; H.rr(X0, y - 50, Math.max(4, w), 100, 14); ctx.fill();
  H.txt(r[0], B.x + 90, y + 20, { size: 64, weight: 900, align: "center", color: r[2] });
  H.txt(r[1], B.x + 180, y + 16, { size: 30, weight: 800, align: "center", color: "#ffffff" });
  if (r[3] === 1) H.txt("1", X0 + w + 40, y + 18, { size: 50, weight: 900, align: "center", color: "#ffffff" });
});
var a = H.clamp((lt - 1500) / 300);
if (a > 0) { ctx.globalAlpha = a; H.txt("約 5.9 倍", B.x + B.w / 2, B.y + B.h * .36 - 90, { size: 150, weight: 900, align: "center", color: "#ffe45c" }); ctx.globalAlpha = 1; }

