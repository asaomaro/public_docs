/* irasutoya-canvas — いらすとやの絵を Canvas に描いて動かす。irasutoya.py canvas が、絵（SVG か PNG の data URI）とこの道具と描き方（*.draw.js）を 1 つにまとめて作る。
   絵のデータが長いので、このファイルは開かない。描き方は *.draw.js を直し、irasutoya.py canvas --update で作り直す。
   motion-video の custom の本体としてそのまま動く: (ctx, lt, d, H, s)。座標は 1920×1080、lt は場面の中の経過 ms。時刻だけで姿が決まる。 */
var IRA = s._ira || (s._ira = (function () {
  var DATA = __DATA__;
  /* 絵が読めたら、止まっている画面も描き直させる */
  function poke() { try { window.dispatchEvent(new Event("resize")); } catch (e) {} }
  Object.keys(DATA).forEach(function (k) { DATA[k].parts.forEach(function (p) { var im = new Image(); im.onload = poke; im.src = p.src; p.im = im; p.src = null; }); });

  function cl(v) { return v < 0 ? 0 : v > 1 ? 1 : v; }
  function eo(k) { return 1 - Math.pow(1 - k, 3); }
  function back(k) { var c = 1.70158; k -= 1; return 1 + (c + 1) * k * k * k + c * k * k; }
  function bounce(k) { var n = 7.5625, q = 2.75;
    if (k < 1 / q) return n * k * k; if (k < 2 / q) { k -= 1.5 / q; return n * k * k + .75; }
    if (k < 2.5 / q) { k -= 2.25 / q; return n * k * k + .9375; } k -= 2.625 / q; return n * k * k + .984375; }
  function frac(v) { return ((v % 1) + 1) % 1; }

  /* 出方・去り方: 進み k（0..1）→ ずれ・大きさ・回転・濃さ。u は絵（部品）の高さ */
  var ENTER = {
    none: function () { return {}; },
    fade: function (k) { return { a: k }; },
    pop: function (k) { var e = back(k); return { sx: e, sy: e, a: cl(k * 3) }; },
    zoom: function (k) { var e = eo(k); return { sx: 1.6 - .6 * e, sy: 1.6 - .6 * e, a: e }; },
    drop: function (k, u) { return { dy: -(1 - bounce(k)) * u * 1.2, a: cl(k * 4) }; },
    rise: function (k, u) { return { dy: (1 - eo(k)) * u * .35, a: eo(k) }; },
    left: function (k, u) { return { dx: -(1 - eo(k)) * u * .8, a: eo(k) }; },
    right: function (k, u) { return { dx: (1 - eo(k)) * u * .8, a: eo(k) }; },
    spin: function (k) { var e = eo(k); return { rot: (1 - e) * -Math.PI * 1.5, sx: e, sy: e, a: cl(k * 3) }; }
  };
  /* 居るあいだの動き: 経過 ms t・強さ a・高さ u・ずれ ph（部品ごとに変えて、そろいすぎないようにする） */
  var IDLE = {
    float: function (t, a, u, ph) { return { dy: Math.sin(t / 900 + ph) * u * .025 * a }; },
    sway: function (t, a, u, ph) { return { rot: Math.sin(t / 1100 + ph) * .045 * a }; },
    breathe: function (t, a, u, ph) { var v = Math.sin(t / 1000 + ph) * .018 * a; return { sx: 1 - v, sy: 1 + v }; },
    bounce: function (t, a, u, ph) { var c = frac(t / 700 + ph / 6.2832), q = c < .12 ? 1 - c / .12 : 0;
      return { dy: -4 * c * (1 - c) * u * .09 * a, sx: 1 + q * .06 * a, sy: 1 - q * .08 * a }; },
    shake: function (t, a, u, ph) { return { dx: Math.sin(t / 37 + ph) * u * .008 * a, dy: Math.cos(t / 29 + ph * 2) * u * .006 * a }; },
    pulse: function (t, a, u, ph) { var v = 1 + Math.sin(t / 420 + ph) * .04 * a; return { sx: v, sy: v }; },
    nod: function (t, a, u, ph) { var c = frac(t / 1600 + ph / 6.2832), v = c < .25 ? Math.sin(c / .25 * Math.PI) : 0; return { rot: v * .07 * a, dy: v * u * .012 * a }; },
    spin: function (t, a, u, ph) { return { rot: (t / 4000 * a + ph / 6.2832) * 6.2832 }; }
  };
  function add(m, e) { m.dx += e.dx || 0; m.dy += e.dy || 0; m.rot += e.rot || 0; m.sx *= e.sx == null ? 1 : e.sx; m.sy *= e.sy == null ? 1 : e.sy; m.a *= e.a == null ? 1 : e.a; }

  /* 1 つの絵（か部品）の、その時刻の姿 */
  function state(o, t, u, ph, enter) {
    var m = { dx: 0, dy: 0, sx: 1, sy: 1, rot: 0, a: 1, on: true }, at = o.at || 0;
    if (t < at && enter !== "none") { m.on = false; return m; }
    add(m, (ENTER[enter] || ENTER.pop)(cl((t - at) / (o.enterDur || 600)), u));
    if (o.out != null) { var xd = o.exitDur || 400;
      if (t >= o.out + xd) { m.on = false; return m; }
      if (t > o.out) add(m, (ENTER[o.exit || "fade"] || ENTER.fade)(1 - cl((t - o.out) / xd), u)); }
    var amp = o.amp == null ? 1 : o.amp, tt = Math.max(0, t - at) * (o.speed || 1);
    (o.idle == null ? [] : [].concat(o.idle)).forEach(function (n) { if (IDLE[n]) add(m, IDLE[n](tt, amp, u, ph)); });
    return m;
  }

  /* 部品が出る順（stagger）。既定は大きい順。"left" "right" "top" "bottom" か、部品の番号の並び */
  function ranks(sp, order) {
    var n = sp.parts.length, idx = [], i;
    for (i = 0; i < n; i++) idx.push(i);
    if (Array.isArray(order)) idx = order.map(function (k) { return k - 1; }).filter(function (k) { return k >= 0 && k < n; }).concat(idx.filter(function (k) { return order.indexOf(k + 1) < 0; }));
    else if (order && order !== "size") { var key = function (p) { return order === "left" ? p.x + p.w / 2 : order === "right" ? -(p.x + p.w / 2) : order === "top" ? p.y + p.h / 2 : -(p.y + p.h / 2); };
      idx.sort(function (a, b) { return key(sp.parts[a]) - key(sp.parts[b]); }); }
    var r = []; idx.forEach(function (k, j) { r[k] = j; }); return r;
  }

  /* 部品を描く。wave があれば、絵と同じ画素の大きさの別の Canvas の上で、横に細く切って上ほど大きくゆらしてから描く（足もとは動かない。切れ目に筋が出ない） */
  function blit(ctx, sp, p, x, y, wave, t) {
    if (!wave) { ctx.drawImage(p.im, x, y, p.w, p.h); return; }
    var mg = Math.ceil(sp.w * .012 * Math.abs(wave)) + 2, cv = p.cv || (p.cv = document.createElement("canvas")), hs = 4;
    if (cv.width !== p.w + mg * 2 || cv.height !== p.h) { cv.width = p.w + mg * 2; cv.height = p.h; }
    var g = cv.getContext("2d"); g.clearRect(0, 0, cv.width, cv.height);
    for (var yy = 0; yy < p.h; yy += hs) { var ay = p.y + yy, hh = Math.min(hs, p.h - yy), off = Math.sin(t / 600 + ay / sp.h * 5) * sp.w * .012 * wave * (1 - ay / sp.h);
      g.drawImage(p.im, 0, yy, p.w, hh, mg + off, yy, p.w, hh); }
    ctx.drawImage(cv, x - mg, y, cv.width, p.h);
  }

  function draw(ctx, name, lt, o) {
    var sp = DATA[name]; o = o || {};
    if (!sp) { if (!draw.warned) { draw.warned = 1; console.error("irasutoya-canvas: 絵がありません: " + name + "（ある名前: " + Object.keys(DATA).join("・") + "）"); } return null; }
    var S = o.w ? o.w / sp.w : (o.h || 520) / sp.h, w = sp.w * S, h = sp.h * S, x = o.x == null ? 960 : o.x, y = o.y == null ? 540 : o.y;
    var box = { x: x - w / 2, y: y - h / 2, w: w, h: h }, i;
    for (i = 0; i < sp.parts.length; i++) if (!sp.parts[i].im.complete || !sp.parts[i].im.naturalWidth) return box;
    var m = state(o, lt, h, 0, o.enter || (o.stagger ? "none" : "pop")); if (!m.on) return box;
    var pv = o.pivot === "center" ? 0 : h / 2, po = o.parts || {}, rk = ranks(sp, o.order), tw = Math.max(0, lt - (o.at || 0)) * (o.speed || 1);
    ctx.save(); ctx.globalAlpha *= cl(m.a) * (o.alpha == null ? 1 : o.alpha);
    if (o.shadow) { var up = cl(1 + m.dy / h);    /* 足もとの影。浮くほど小さく薄い */
      ctx.save(); ctx.globalAlpha *= .16 * up * cl((lt - (o.at || 0)) / 300); ctx.fillStyle = "#000"; ctx.beginPath(); ctx.ellipse(x + m.dx, y + h / 2, w * .34 * (.6 + .4 * up) * Math.abs(m.sx), h * .035, 0, 0, 6.2832); ctx.fill(); ctx.restore(); }
    ctx.translate(x + m.dx, y + pv + m.dy); ctx.rotate(m.rot + (o.rot || 0) * Math.PI / 180); ctx.scale(m.sx * (o.flip ? -1 : 1), m.sy); ctx.translate(0, -pv); ctx.scale(S, S);
    sp.parts.forEach(function (p, k) {       /* ここからは、絵の中心が原点・絵の画素が単位 */
      var q = po[k + 1] || {}; if (q.hide) return;
      var pm = null;
      if (o.stagger || o.partIdle || o.partEnter || po[k + 1]) {
        pm = state({ at: q.at != null ? q.at : (o.at || 0) + rk[k] * (o.stagger || 0), enterDur: q.enterDur || o.enterDur, idle: q.idle !== undefined ? q.idle : o.partIdle,
                     amp: q.amp != null ? q.amp : o.amp, speed: q.speed || o.speed, out: q.out, exit: q.exit, exitDur: q.exitDur },
                   lt, p.h, k * 1.7, q.enter || o.partEnter || (o.stagger || q.at != null ? "pop" : "none"));
        if (!pm.on) return; }
      ctx.save(); ctx.translate(p.x + p.w / 2 - sp.w / 2 + (q.dx || 0), p.y + p.h / 2 - sp.h / 2 + (q.dy || 0));
      if (pm) { ctx.globalAlpha *= cl(pm.a); ctx.translate(pm.dx, pm.dy); ctx.rotate(pm.rot); ctx.scale(pm.sx, pm.sy); }
      blit(ctx, sp, p, -p.w / 2, -p.h / 2, q.wave != null ? q.wave : o.wave, tw);
      ctx.restore();
    });
    ctx.restore(); return box;
  }
  return { draw: draw, data: DATA, names: Object.keys(DATA), enters: Object.keys(ENTER), idles: Object.keys(IDLE).concat(["wave"]) };
})());
/* draw(名前, {…}) → 描いた枠 {x, y, w, h}（動く前の位置）。項目は irasutoya の SKILL.md「Canvas で動かす」 */
function draw(name, o) { return IRA.draw(ctx, name, lt, o); }
/* ---- ここから描き方（__DRAW__ の中身。直すのはそちら） ---- */
