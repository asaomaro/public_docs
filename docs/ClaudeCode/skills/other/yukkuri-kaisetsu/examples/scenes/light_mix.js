/* 白い光は、色のまぜもの: 左から虹の 7 色の光が来て、1 本にまとまると白い光になる。(ctx, lt, d, H, s) の本体。s.box が描く範囲 */
var B = s.box, X0 = B.x + 90, XM = B.x + B.w * .55, X1 = B.x + B.w - 90, CY = B.y + B.h * .55;
var COL = ["#e5484d", "#f08a24", "#f5d90a", "#2f9e62", "#3b9bff", "#3d5bd9", "#8b5cf6"], k = H.eo(H.clamp((lt - 200) / 1200)), m = H.eo(H.clamp((lt - 1300) / 900));
ctx.lineCap = "round";
COL.forEach(function (c, i) {
  var y0 = CY + (i - 3) * 46, x = X0 + (XM - X0) * k;
  ctx.strokeStyle = c; ctx.lineWidth = 16; ctx.beginPath(); ctx.moveTo(X0, y0); ctx.quadraticCurveTo((X0 + XM) / 2, y0, x, y0 + (CY - y0) * Math.min(1, k * 1.2)); ctx.stroke();
});
if (m > 0) { ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 34; ctx.shadowColor = "#fff6c8"; ctx.shadowBlur = 40 * m;
  ctx.beginPath(); ctx.moveTo(XM, CY); ctx.lineTo(XM + (X1 - XM) * m, CY); ctx.stroke(); ctx.shadowBlur = 0; }
ctx.globalAlpha = k; H.txt("虹の色が ぜんぶ", (X0 + XM) / 2, B.y + 80, { size: 48, weight: 900, align: "center", color: "#ffffff" });
ctx.globalAlpha = m; H.txt("まざると 白い光", (XM + X1) / 2 + 40, B.y + 80, { size: 48, weight: 900, align: "center", color: "#fff6c8" });
ctx.globalAlpha = 1;
