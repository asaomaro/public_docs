// 手元と SSH のマシン（左）＋ sodactl を打つ端末（右。terminal の部品を縮小して置く）
var L = { x: 520, y: 700 }, G = { x: 250, y: 390 }, B = { x: 790, y: 390 };
function card(p, name, sub, rows, k) {
  if (k <= 0) return;
  ctx.save(); ctx.globalAlpha *= H.clamp(k); ctx.translate(p.x, p.y); ctx.scale(H.mix(.85, 1, H.clamp(k)), H.mix(.85, 1, H.clamp(k)));
  H.panel(-170, -90, 340, 180, {});
  H.txt(name, -148, -46, { size: 26, weight: 800 });
  H.txt(sub, 148, -46, { size: 16, font: H.F.mono, color: H.C.accent, align: "right" });
  rows.forEach(function (r, i) { H.stateMark(-136, -8 + i * 36, r[0], lt, 8); H.txt(r[1], -116, -1 + i * 36, { size: 19, font: H.F.mono }); });
  ctx.restore();
}
[[G, 900], [B, 1300]].forEach(function (a) {
  var k = H.P(lt, a[1], a[1] + 800, H.eio), p0 = { x: L.x, y: L.y - 90 }, p1 = { x: a[0].x, y: a[0].y + 90 };
  H.arrow(p0, null, p1, k, { dashed: true, head: false, color: H.C.accent, width: 3 });
  if (k >= 1) { var mx = (p0.x + p1.x) / 2, my = (p0.y + p1.y) / 2;
    H.rr(mx - 32, my - 16, 64, 32, 16); ctx.fillStyle = H.C.bg1; ctx.fill(); ctx.strokeStyle = H.C.accent; ctx.lineWidth = 1.5; ctx.stroke();
    H.txt("SSH", mx, my + 6, { size: 15, font: H.F.mono, weight: 700, color: H.C.accent, align: "center" }); }
});
H.packet({ x: L.x, y: L.y - 90 }, null, { x: G.x, y: G.y + 90 }, H.lin(lt, d * .55, d * .55 + 1100), "", {});
card(L, "手元", "soda serve", [["working", "impl        p1"], ["idle", "planner     p5"]], H.P(lt, 200, 900, H.back));
card(G, "gpu-box", "ssh", [[lt > d * .3 ? (lt > d * .64 ? "working" : "idle") : "none", "reviewer    p7"], ["working", "trainer     p2"]], H.P(lt, 1300, 2000, H.back));
card(B, "build-01", "ssh", [["idle", "ci-watch    p1"], ["none", "logs        p3"]], H.P(lt, 1700, 2400, H.back));
H.sub("terminal", s.term, lt - 600, d - 600, { x: 900, y: 150, scale: .5, alpha: H.P(lt, 400, 1200) });
