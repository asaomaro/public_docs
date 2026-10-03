/* 空が紫に見えない理由（3 段）: 色ごとの光の量を棒で見せ、① 太陽の光に紫は少ない → ② 上空で吸収される（と言われる）→ ③ 目が紫に鈍い、の順に紫の棒が小さくなる。
   段は せりふに合わせる: s.cue(1) で ②、s.cue(3) で ③（このあとに 5 つのせりふが続く） */
var B = s.box, st2 = H.clamp((lt - s.cue(1) - 300) / 800), st3 = H.clamp((lt - s.cue(3) - 300) / 800), k = H.eo(H.clamp((lt - 150) / 900));
var COL = ["#8b5cf6", "#3d5bd9", "#3b9bff", "#2f9e62", "#f5d90a", "#f08a24", "#e5484d"], NAME = ["紫", "藍", "青", "緑", "黄", "橙", "赤"];
var base = [.55, .8, .95, 1, .97, .93, .88], vio = base[0] * (1 - .35 * st2) * (1 - .45 * st3);
var X0 = B.x + B.w * .46, W = (B.w * .5) / 7, GY = B.y + B.h - 70, HMAX = B.h - 190;
COL.forEach(function (c, i) { var h = (i ? base[i] : vio) * HMAX * k; ctx.fillStyle = c; ctx.globalAlpha = i === 0 ? 1 - .35 * st3 : 1;
  ctx.fillRect(X0 + i * W + 6, GY - h, W - 12, h); ctx.globalAlpha = 1;
  H.txt(NAME[i], X0 + i * W + W / 2, GY + 44, { size: 38, weight: 800, align: "center", color: "#ffffff" }); });
ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 4; ctx.beginPath(); ctx.moveTo(X0 - 6, GY); ctx.lineTo(X0 + 7 * W, GY); ctx.stroke();
var steps = [["① 太陽の光に、紫は少ない", 1], ["② 上空で吸収される", st2], ["③ 人の目が、紫に鈍い", st3]];
steps.forEach(function (sp, i) { if (sp[1] <= 0) return; ctx.globalAlpha = sp[1]; H.txt(sp[0], B.x + 40, B.y + 140 + i * 120, { size: 54, weight: 900, color: i === 0 ? "#ffffff" : "#d8c4ff" }); ctx.globalAlpha = 1; });
H.txt("光の量（色ごと）", X0 + 3.5 * W, B.y + 64, { size: 34, weight: 800, align: "center", color: "#cfd8e6" });
