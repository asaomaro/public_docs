/* 散らばった青い光が、空じゅうから目に届く: 空のドームに青い光の点がちらばり、あちこちから下の人の目へ届く */
var B = s.box, CX = B.x + B.w / 2, GY = B.y + B.h - 60, R = Math.min(B.w * .46, B.h - 90), k = H.eo(H.clamp((lt - 150) / 900)), ar = H.clamp((lt - 900) / 1400);
ctx.fillStyle = "rgba(74,168,255,.18)"; ctx.beginPath(); ctx.arc(CX, GY, R * k, Math.PI, 0); ctx.closePath(); ctx.fill();
ctx.strokeStyle = "#9fd0ff"; ctx.lineWidth = 6; ctx.beginPath(); ctx.arc(CX, GY, R * k, Math.PI, 0); ctx.stroke();
ctx.fillStyle = "#3c7a4a"; ctx.fillRect(B.x + 30, GY, B.w - 60, 14);
var rnd = H.rand(9), pts = [];
for (var i = 0; i < 16; i++) { var a = Math.PI + (i + .5) / 16 * Math.PI, rr = R * (.55 + rnd() * .38); pts.push([CX + Math.cos(a) * rr, GY + Math.sin(a) * rr]); }
pts.forEach(function (p, i) { var a = H.clamp(k * 3 - i * .12); ctx.globalAlpha = a; ctx.fillStyle = "#4aa8ff"; ctx.beginPath(); ctx.arc(p[0], p[1], 13 + 4 * Math.sin(lt / 300 + i), 0, 6.2832); ctx.fill(); });
ctx.globalAlpha = 1;
if (ar > 0) { ctx.strokeStyle = "#4aa8ff"; ctx.lineWidth = 6; ctx.setLineDash([14, 12]); ctx.lineDashOffset = -lt / 16;
  pts.forEach(function (p, i) { if (i % 2) return; var t = H.clamp(ar * 2 - i * .05); ctx.beginPath(); ctx.moveTo(p[0], p[1]); ctx.lineTo(p[0] + (CX - p[0]) * t * .92, p[1] + (GY - 70 - p[1]) * t * .92); ctx.stroke(); });
  ctx.setLineDash([]); }
ctx.fillStyle = "#ffffff"; ctx.beginPath(); ctx.arc(CX, GY - 52, 20, 0, 6.2832); ctx.fill(); ctx.beginPath(); ctx.moveTo(CX - 22, GY); ctx.lineTo(CX, GY - 34); ctx.lineTo(CX + 22, GY); ctx.closePath(); ctx.fill();
ctx.globalAlpha = ar; H.txt("空じゅうから、目に届く", CX, B.y + 66, { size: 50, weight: 900, align: "center", color: "#ffffff" }); ctx.globalAlpha = 1;
