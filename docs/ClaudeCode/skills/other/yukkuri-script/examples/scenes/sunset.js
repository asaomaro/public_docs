/* 夕焼けが赤いわけ（2 段）: ① 夕方は太陽が低く、光が空気の層を長く通る（昼の短い道と比べる）→ ② 次のせりふで、青が途中で散らばり、赤が残って届く。
   (ctx, lt, d, H, s) の本体。s.box が描く範囲、lt はこの図が出てからの ms、s.cue(1) は次のせりふが始まる ms。 */
var B = s.box, R = 1400, TH = 150, OX = B.x + B.w * .76, GY = B.y + B.h - 150, CY = GY + R;   /* 地面は大きな円の上の端。OX・GY が見る人の足もと */
var EY = GY - 46, LEN = Math.sqrt((R + TH) * (R + TH) - R * R);                                   /* 目の高さ・空気の層を横に通る長さ */
var k0 = H.clamp(lt / 500), noon = H.eo(H.clamp((lt - 500) / 700)), eve = H.eo(H.clamp((lt - 1500) / 1100)),
    lose = H.eo(H.clamp((lt - s.cue(1) - 300) / 1600));                                           /* ② 青が散らばっていく */
function tint(to, t) {   /* 白から to（#rrggbb）へ、t（0..1）だけ寄せた色 */
  var n = parseInt(to.slice(1), 16), c = [n >> 16, n >> 8 & 255, n & 255].map(function (v) { return Math.round(255 + (v - 255) * t); });
  return "rgb(" + c.join(",") + ")"; }
ctx.save(); H.rr(B.x, B.y, B.w, B.h, 26); ctx.clip(); ctx.lineCap = "round";
/* 空気の層と地面 */
ctx.globalAlpha = k0;
ctx.beginPath(); ctx.arc(OX, CY, R + TH, 0, 6.2832); ctx.fillStyle = "rgba(120,180,255,.28)"; ctx.fill();
ctx.beginPath(); ctx.arc(OX, CY, R, 0, 6.2832); ctx.fillStyle = "#3c7a4a"; ctx.fill(); ctx.strokeStyle = "#8fd6a0"; ctx.lineWidth = 5; ctx.stroke();
/* 見る人 */
ctx.fillStyle = "#ffffff"; ctx.beginPath(); ctx.arc(OX, EY - 6, 17, 0, 6.2832); ctx.fill();
ctx.beginPath(); ctx.moveTo(OX - 20, GY); ctx.lineTo(OX, EY + 10); ctx.lineTo(OX + 20, GY); ctx.closePath(); ctx.fill();
ctx.globalAlpha = 1;
/* 昼: 真上からの光は、空気の層を短く通る（うすく残す） */
if (noon > 0) {
  var ny = B.y + 150, na = eve > 0 ? 1 - .55 * eve : 1;
  ctx.globalAlpha = noon * na;
  ctx.fillStyle = "#fff6c8"; ctx.beginPath(); ctx.arc(OX, ny, 34, 0, 6.2832); ctx.fill();
  ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 12; ctx.setLineDash([4, 22]); ctx.beginPath(); ctx.moveTo(OX, ny + 50); ctx.lineTo(OX, ny + 50 + (GY - TH - ny - 50) * noon); ctx.stroke(); ctx.setLineDash([]);
  ctx.lineWidth = 16; ctx.beginPath(); ctx.moveTo(OX, GY - TH); ctx.lineTo(OX, GY - TH + (EY - 40 - GY + TH) * noon); ctx.stroke();
  H.txt("昼は短い", OX + 150, GY - TH + 44, { size: 44, weight: 900, align: "center", color: "#ffffff" });
  ctx.globalAlpha = 1;
}
/* 夕方: 低い太陽からの光は、空気の層を横に長く通る。② で、太陽から離れるほど 白 → 黄 → 赤 に変わる */
if (eve > 0) {
  var sx = OX - LEN - 70, x0 = OX - LEN, x1 = OX - 34, xe = x0 + (x1 - x0) * eve;
  ctx.globalAlpha = eve; ctx.fillStyle = lose > 0 ? "#ffb14a" : "#fff6c8"; ctx.shadowColor = "#ffb14a"; ctx.shadowBlur = 30 * lose;
  ctx.beginPath(); ctx.arc(sx, EY, 40, 0, 6.2832); ctx.fill(); ctx.shadowBlur = 0; ctx.globalAlpha = 1;
  var g = ctx.createLinearGradient(x0, 0, x1, 0);
  g.addColorStop(0, "#ffffff"); g.addColorStop(.45, tint("#ffd45c", lose)); g.addColorStop(1, tint("#ff5a4d", lose));
  ctx.strokeStyle = g; ctx.lineWidth = 18; ctx.beginPath(); ctx.moveTo(x0, EY); ctx.lineTo(xe, EY); ctx.stroke();
  /* ② 青が、道の途中で上へ下へ散らばっていく */
  if (lose > 0) {
    ctx.strokeStyle = "#4aa8ff"; ctx.lineWidth = 9; ctx.setLineDash([16, 14]); ctx.lineDashOffset = -lt / 14;
    for (var i = 0; i < 5; i++) {
      var px = x0 + (x1 - x0) * (.08 + i * .15), a = H.clamp(lose * 5 - i), len = 86 * a, dir = i % 2 ? -1 : 1;
      if (a <= 0) continue;
      ctx.globalAlpha = a; ctx.beginPath(); ctx.moveTo(px, EY + dir * 16); ctx.lineTo(px + 26 * a, EY + dir * (16 + len * (dir < 0 ? 1 : .5))); ctx.stroke();
    }
    ctx.setLineDash([]); ctx.globalAlpha = 1;
  }
  /* 言葉: ① は「夕方は長い」、② で「青は途中で散らばる」「赤が残る」に替わる */
  var ly = EY - 190;
  ctx.globalAlpha = eve * (1 - lose); H.txt("夕方は長い", (x0 + x1) / 2, EY - 60, { size: 52, weight: 900, align: "center", color: "#ffffff" });
  ctx.globalAlpha = lose; H.txt("青は途中で散らばる", (x0 + x1) / 2 - 40, ly, { size: 50, weight: 900, align: "center", color: "#4aa8ff" });
  ctx.globalAlpha = H.clamp(lose * 2 - 1); H.txt("赤が残る", OX - 150, EY - 36, { size: 50, weight: 900, align: "center", color: "#ff6a5c" });
  ctx.globalAlpha = 1;
}
ctx.restore();
