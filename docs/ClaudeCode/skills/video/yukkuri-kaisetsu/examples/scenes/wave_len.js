/* 色のちがいは、波の長さのちがい: 上に赤（波が長い）、下に青（波が短い）。1 つ分の長さを、かっこで示す */
var B = s.box, X0 = B.x + 300, X1 = B.x + B.w - 70, k = H.eo(H.clamp((lt - 150) / 1300));
function wave(y, len, amp, col, lab, sub) {
  var xe = X0 + (X1 - X0) * k; ctx.strokeStyle = col; ctx.lineWidth = 12; ctx.lineCap = "round"; ctx.beginPath();
  for (var x = X0; x <= xe; x += 4) { var yy = y + Math.sin((x - X0) / len * 2 * Math.PI - lt / 260) * amp; x === X0 ? ctx.moveTo(x, yy) : ctx.lineTo(x, yy); } ctx.stroke();
  H.txt(lab, B.x + 160, y + 10, { size: 54, weight: 900, align: "center", color: col });
  H.txt(sub, B.x + 160, y + 62, { size: 34, weight: 800, align: "center", color: "#ffffff" });
  var a = H.clamp((lt - 1200) / 400); if (a > 0) { ctx.globalAlpha = a; ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 5; var by = y - amp - 26;
    ctx.beginPath(); ctx.moveTo(X0, by + 12); ctx.lineTo(X0, by); ctx.lineTo(X0 + len, by); ctx.lineTo(X0 + len, by + 12); ctx.stroke();
    H.txt("1 つ分", X0 + len / 2, by - 12, { size: 30, weight: 800, align: "center", color: "#ffffff" }); ctx.globalAlpha = 1; }
}
wave(B.y + B.h * .32, 300, 46, "#ff6a5c", "赤", "波が長い");
wave(B.y + B.h * .74, 120, 46, "#4aa8ff", "青", "波が短い");
