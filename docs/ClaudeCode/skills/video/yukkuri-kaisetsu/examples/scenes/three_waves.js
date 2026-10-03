/* 紫は、青よりもっと波が短い: 短い順に、紫・青・赤の波を並べ、紫に「？」 */
var B = s.box, X0 = B.x + 290, X1 = B.x + B.w - 70, k = H.eo(H.clamp((lt - 150) / 1200));
[["紫", "#b47cff", 90, "もっと短い"], ["青", "#4aa8ff", 130, "短い"], ["赤", "#ff6a5c", 260, "長い"]].forEach(function (w, i) {
  var y = B.y + B.h * (.24 + i * .27), xe = X0 + (X1 - X0) * k; ctx.strokeStyle = w[1]; ctx.lineWidth = 11; ctx.lineCap = "round"; ctx.beginPath();
  for (var x = X0; x <= xe; x += 4) { var yy = y + Math.sin((x - X0) / w[2] * 6.2832 - lt / 280) * 36; x === X0 ? ctx.moveTo(x, yy) : ctx.lineTo(x, yy); } ctx.stroke();
  H.txt(w[0], B.x + 110, y + 18, { size: 60, weight: 900, align: "center", color: w[1] });
  H.txt(w[3], B.x + 205, y + 14, { size: 30, weight: 800, align: "center", color: "#ffffff" });
});
var q = H.clamp((lt - 1300) / 300); if (q > 0) { ctx.globalAlpha = q; H.txt("？", X1 - 10, B.y + B.h * .24 - 40, { size: 96, weight: 900, align: "center", color: "#ffe45c" }); ctx.globalAlpha = 1; }
