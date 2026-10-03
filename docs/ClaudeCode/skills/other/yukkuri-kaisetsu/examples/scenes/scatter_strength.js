/* 波の短い光ほど、強く散らばる: 青い光は分子に当たって、あちこちへたくさん散らばる。赤い光は、ほとんど散らばらない */
var B = s.box, k = H.eo(H.clamp((lt - 200) / 900)), sp = H.eo(H.clamp((lt - 1000) / 900));
function row(y, col, len, n, lab) {
  var X0 = B.x + 60, PX = B.x + B.w * .42; ctx.strokeStyle = col; ctx.lineWidth = 10; ctx.lineCap = "round"; ctx.beginPath();
  for (var x = X0; x <= X0 + (PX - 60 - X0) * k; x += 4) { var yy = y + Math.sin((x - X0) / len * 6.2832) * 22; x === X0 ? ctx.moveTo(x, yy) : ctx.lineTo(x, yy); } ctx.stroke();
  ctx.fillStyle = "#dfe9f5"; ctx.strokeStyle = "#6b7c93"; ctx.lineWidth = 4; ctx.beginPath(); ctx.arc(PX, y, 26, 0, 6.2832); ctx.fill(); ctx.stroke();
  if (sp > 0) { ctx.strokeStyle = col; ctx.lineWidth = 9; ctx.setLineDash([18, 14]); ctx.lineDashOffset = -lt / 14;
    for (var i = 0; i < n; i++) { var a = -Math.PI * .85 + i * (Math.PI * 1.7 / Math.max(1, n - 1)), r = 150 * sp;
      ctx.beginPath(); ctx.moveTo(PX + Math.cos(a) * 40, y + Math.sin(a) * 40); ctx.lineTo(PX + Math.cos(a) * (40 + r), y + Math.sin(a) * (40 + r) * .55); ctx.stroke(); }
    ctx.setLineDash([]); }
  ctx.globalAlpha = sp; H.txt(lab, B.x + B.w * .8, y + 16, { size: 46, weight: 900, align: "center", color: col }); ctx.globalAlpha = 1;
}
row(B.y + B.h * .28, "#4aa8ff", 70, 9, "青: 強く散らばる");
row(B.y + B.h * .72, "#ff6a5c", 150, 2, "赤: あまり散らばらない");
