/* 光の散らばり（3 段）: ① 白い光が空気の分子に当たる → ② あちこちへ散らばる → ③ 次のせりふの途中で、青は強く散らばり、赤はほぼまっすぐ進む。
   (ctx, lt, d, H, s) の本体。s.box が描く範囲、lt はこの図が出てからの ms、s.cue(1) は次のせりふが始まる ms。 */
var B = s.box, CX = B.x + B.w * .5, Y = B.y + B.h * .55, X0 = B.x + 80, X1 = B.x + B.w - 80;
var k = H.eo(H.clamp((lt - 300) / 1100)),                 /* ① 光が届く */
    hit = H.clamp((lt - 1500) / 700),                     /* ② ぶつかって散らばる */
    split = H.eo(H.clamp((lt - s.cue(1) - 1100) / 1000)); /* ③「波の短い光ほど」で、色に分かれる */
ctx.lineCap = "round";
/* 白い光の筋 */
ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 26; ctx.shadowColor = "#fff2b0"; ctx.shadowBlur = 34;
if (k > 0) { ctx.beginPath(); ctx.moveTo(X0, Y); ctx.lineTo(X0 + (CX - 70 - X0) * k, Y); ctx.stroke(); }
ctx.shadowBlur = 0;
var ANG = [-2.55, -2.05, -1.25, -.75, .75, 1.25, 2.05, 2.55], R1 = Math.min(B.h * .3, 200);
/* ② 色に分かれる前: 白っぽい光が、あちこちへ */
if (hit > 0 && split < 1) {
  ctx.globalAlpha = hit * (1 - split); ctx.strokeStyle = "#e9eef5"; ctx.lineWidth = 9; ctx.setLineDash([20, 20]); ctx.lineDashOffset = -lt / 16;
  ANG.forEach(function (a) { ctx.beginPath(); ctx.moveTo(CX + Math.cos(a) * 84, Y + Math.sin(a) * 84); ctx.lineTo(CX + Math.cos(a) * (84 + R1 * .7 * hit), Y + Math.sin(a) * (84 + R1 * .7 * hit)); ctx.stroke(); });
  ctx.setLineDash([]); ctx.globalAlpha = 1;
}
/* ③ 青は強く散らばる・赤はほぼまっすぐ */
if (split > 0) {
  ctx.globalAlpha = split;
  ctx.strokeStyle = "#ff6a5c"; ctx.lineWidth = 20; ctx.beginPath(); ctx.moveTo(CX + 70, Y); ctx.lineTo(CX + 70 + (X1 - CX - 70) * split, Y); ctx.stroke();
  ctx.strokeStyle = "#4aa8ff"; ctx.lineWidth = 14; ctx.setLineDash([28, 20]); ctx.lineDashOffset = -lt / 12;
  ANG.forEach(function (a) { ctx.beginPath(); ctx.moveTo(CX + Math.cos(a) * 84, Y + Math.sin(a) * 84); ctx.lineTo(CX + Math.cos(a) * (84 + R1 * split), Y + Math.sin(a) * (84 + R1 * split)); ctx.stroke(); });
  ctx.setLineDash([]); ctx.globalAlpha = 1;
}
/* 空気の分子（ゆらゆら動く。光が当たると、少しはじかれる） */
var rnd = H.rand(5), bump = hit > 0 && hit < 1 ? Math.sin(hit * Math.PI) * 10 : 0;
for (var i = 0; i < 9; i++) {
  var ox = (rnd() - .5) * 120, oy = (rnd() - .5) * 130, r = 14 + rnd() * 8;
  ctx.globalAlpha = H.clamp((lt - 200 - i * 70) / 300); ctx.fillStyle = "#dfe9f5"; ctx.strokeStyle = "#6b7c93"; ctx.lineWidth = 4;
  ctx.beginPath(); ctx.arc(CX + ox * (1 + bump / 60) + Math.sin(lt / 700 + i) * 5, Y + oy * (1 + bump / 60) + Math.cos(lt / 800 + i * 2) * 5, r, 0, 6.2832); ctx.fill(); ctx.stroke();
}
ctx.globalAlpha = 1;
/* 名前は上と下の余白に置く（線と重ねない） */
var ty = B.y + 74, by = B.y + B.h - 30;
ctx.globalAlpha = k; H.txt("太陽の光", X0 + 120, ty, { size: 46, weight: 900, align: "center", color: "#ffffff" });
ctx.globalAlpha = H.clamp((lt - 500) / 400); H.txt("空気の分子", CX, Y - 120, { size: 46, weight: 900, align: "center", color: "#dfe9f5" });
ctx.globalAlpha = split; H.txt("赤はほぼまっすぐ", X1 - 190, Y + 80, { size: 46, weight: 900, align: "center", color: "#ff6a5c" });
H.txt("青は強く散らばる", CX, by, { size: 52, weight: 900, align: "center", color: "#4aa8ff" });
ctx.globalAlpha = hit * (1 - split); H.txt("ぶつかって、あちこちへ", CX, by, { size: 50, weight: 900, align: "center", color: "#ffffff" });
ctx.globalAlpha = 1;
