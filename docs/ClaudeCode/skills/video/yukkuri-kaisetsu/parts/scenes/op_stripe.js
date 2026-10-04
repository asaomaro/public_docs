/* オープニングのロゴ（帯）: 斜めの帯が左右から走り、帯の上にチャンネルの名前が滑り込む。s.label が名前。短いアイキャッチにも使える */
var k = H.eo(H.clamp(lt / 380)), k2 = H.eo(H.clamp((lt - 140) / 380)), slide = H.back(H.clamp((lt - 260) / 420));
ctx.save(); ctx.globalAlpha = .82 * H.clamp(lt / 200); ctx.fillStyle = "#101626"; ctx.fillRect(0, 0, 1920, 1080); ctx.restore();
ctx.save(); ctx.translate(960, 300); ctx.rotate(-.06);   /* 立ち絵の頭より上に置く */
ctx.fillStyle = "#e8384f"; ctx.fillRect(-1300, -150, 2600 * k, 150);
ctx.fillStyle = "#2f7ff2"; ctx.fillRect(1300 - 2600 * k2, 10, 2600 * k2, 150);
ctx.fillStyle = "#ffffff"; ctx.fillRect(-1300, 0, 2600 * k, 10);
var name = String(s.label || "チャンネル").replace(/\//g, ""), size = Math.min(160, 1250 / name.length);
ctx.globalAlpha = H.clamp((lt - 260) / 200);
H.txt(name, (1 - slide) * -500, size * .2, { size: size, weight: 900, align: "center", color: "#ffffff", stroke: "#16161d", strokeWidth: size * .16 });
ctx.restore();
