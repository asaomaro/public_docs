/* motion-video の部品を、プレイヤー無しの「動く図」として文書に置く（md-to-doc の ```motion ブロック）。
   - 画面に入ったら最初から再生し、最後のコマで止まる（data-loop="1" なら繰り返す）。図をクリックするか「もう一度」で再生し直す
   - 動きを減らす設定・印刷では、最後のコマ（完成した図）を出す
   - 文書のライト・ダーク（<html data-theme> と OS の設定）に合わせて、映像の配色を切り替える
   描画は engine.js（window.MotionVideo）の時刻だけで決まる描き方をそのまま使い、seek で時刻を送る（音は鳴らさない） */
(function () {
  if (window.MotionFigure) return;
  var RM = window.matchMedia ? matchMedia("(prefers-reduced-motion: reduce)") : null;
  var MQ = window.matchMedia ? matchMedia("(prefers-color-scheme: dark)") : null;
  function docDark() {
    var a = document.documentElement.getAttribute("data-theme");
    if (a === "dark") return true; if (a === "light") return false;
    return !!(MQ && MQ.matches);
  }
  var FIGS = [];
  function MotionFigure(fig) {
    var el = fig.querySelector(".mv-player"), sp = el && el.querySelector("script[data-mv-spec]"), ths = fig.querySelector("script[data-mvfig-themes]");
    if (!sp || !ths || !window.MotionVideo) return null;
    var THS = JSON.parse(ths.textContent), mode = docDark() ? "dark" : "light";
    var theme = JSON.parse(JSON.stringify(THS[mode]));   /* エンジンはこの物を読み続ける。配色の切り替えは中身を差し替える */
    var api = window.MotionVideo(el, JSON.parse(sp.textContent), theme);
    var loop = fig.getAttribute("data-loop") === "1", raf = 0, t0 = 0, visible = false, played = false, done = false;
    function show(ms) { api.seek(Math.max(0, Math.min(api.DUR - 1, ms))); }
    function finish() { cancel(); show(api.DUR - 1); done = true; fig.classList.add("mvfig-done"); }
    function cancel() { if (raf) cancelAnimationFrame(raf); raf = 0; }
    function step(now) {
      raf = 0; if (!visible) return;
      var t = now - t0;
      if (t >= api.DUR) { if (loop) { t0 = now; t = 0; } else { finish(); return; } }
      show(t); raf = requestAnimationFrame(step);
    }
    function start() {
      played = true; done = false; fig.classList.remove("mvfig-done");
      if (RM && RM.matches) { finish(); return; }
      t0 = performance.now(); cancel(); raf = requestAnimationFrame(step);
    }
    function resume() { if (done || !played) return; t0 = performance.now() - api.t; cancel(); raf = requestAnimationFrame(step); }
    function setMode(m) {
      if (m === mode) return; mode = m; var src = THS[m];
      ["canvas", "fonts"].forEach(function (k) { Object.keys(src[k]).forEach(function (x) { theme[k][x] = src[k][x]; }); });
      theme.pattern = src.pattern; show(api.t);
    }
    /* 図のどこをクリックしても再生し直す（エンジンの「クリックで再生・一時停止」より先に受ける） */
    fig.addEventListener("click", function (e) { e.stopPropagation(); e.preventDefault(); visible = true; start(); }, true);
    show(0);
    var me = {
      el: fig, api: api,
      visible: function (v) { visible = v; if (!v) { cancel(); return; } if (!played) start(); else if (!done) resume(); },
      setMode: setMode, final: function () { cancel(); show(api.DUR - 1); }, replay: start
    };
    FIGS.push(me); fig.__mvfig = me;
    return me;
  }
  function boot() {
    var list = [].slice.call(document.querySelectorAll(".mvfig:not([data-mvfig-ready])"));
    list.forEach(function (fig) { fig.setAttribute("data-mvfig-ready", ""); try { MotionFigure(fig); } catch (e) { console.error("motion figure:", e); } });
    var io = "IntersectionObserver" in window ? new IntersectionObserver(function (es) {
      es.forEach(function (en) { var f = en.target.__mvfig; if (f) f.visible(en.isIntersecting && en.intersectionRatio >= .35); });
    }, { threshold: [0, .35, .6] }) : null;
    FIGS.forEach(function (f) { if (io) io.observe(f.el); else f.visible(true); });
    var sync = function () { var m = docDark() ? "dark" : "light"; FIGS.forEach(function (f) { f.setMode(m); }); };
    if (MQ) { if (MQ.addEventListener) MQ.addEventListener("change", sync); else if (MQ.addListener) MQ.addListener(sync); }
    new MutationObserver(sync).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    /* 印刷: 明るい配色で完成した図を出す */
    window.addEventListener("beforeprint", function () { FIGS.forEach(function (f) { f.setMode("light"); f.final(); }); });
    window.addEventListener("afterprint", sync);
  }
  window.MotionFigure = MotionFigure;
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot); else boot();
})();
