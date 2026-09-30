// update(el, lt, d, H, s): 毎コマ呼ばれる。ここでは中央の円の中に、場面の進み（%）を文字で出す
var core = el.querySelector(".core");
if (core) core.setAttribute("r", String(110 + 8 * Math.sin(lt / 400)));
