/* diff-review-html の「画面の形」だけを扱う層。
 *
 * ここは**レビューの状態を一切知らない**（差分もスレッドも触らない）。DOM と localStorage だけ。
 * だから app.js から切り離せる（decisions.md D7）。app.js との接点は pref() ひとつ。
 *
 * 守っている約束:
 *  - 保存キーは差分ごとではなく**そのブラウザごと**（decisions.md D5）。幅とテーマは人の設定であって
 *    差分の属性ではないので、レビューのたびに既定へ戻ってはいけない。
 *  - 保存できない環境（Firefox の file:// 等）では**黙って既定値で動く**（decisions.md D6）。
 *    下書きと違い、失われるのは「画面の形」だけなのでバナーは出さない。
 *  - レビュー記録の JSON には**一切入らない**。canonicalRecord() には触れない。
 */
(function () {
  "use strict";

  var PREFIX = "diff-review-html/ui/v1/";
  // 閉じた状態のストリップ幅（style.css の `.shell[data-left="collapsed"]` 等）と
  // 揃える。ドラッグでこれより狭くはできない——それ以上狭くしたいときは専用の
  // 開閉ボタンで畳む（要件: ドラッグの最小サイズは非展開状態まで）。
  var MIN_W = 40;
  var MAX_W = 600;
  var STEP = 10;
  var BIG_STEP = 50;
  var THEMES = ["auto", "light", "dark"];
  var THEME_LABEL = { auto: "テーマ: OS に従う", light: "テーマ: ライト", dark: "テーマ: ダーク" };
  // 太陽・月・半月の組は他の多くのアプリで確立した idiom（research.md F5）。
  var THEME_ICON = { auto: "◐", light: "☀", dark: "☾" };

  var DEFAULTS = {
    theme: "auto",
    split: "off",
    filetree: "off",
    "pane-left": "open",
    "pane-right": "open",
    "left-width": "260",
    "right-width": "320",
    "cl-unresolved": "off",
    "cl-severity": "",
    "cl-notes": "on"
  };

  function pref(name, value) {
    if (arguments.length === 1) { return read(name); }
    write(name, value);
    return value;
  }

  function read(name) {
    var fallback = DEFAULTS[name];
    try {
      var got = localStorage.getItem(PREFIX + name);
      return got === null ? fallback : got;
    } catch (err) {
      return fallback;    // 使えない環境。既定値で動く
    }
  }

  function write(name, value) {
    try {
      localStorage.setItem(PREFIX + name, String(value));
    } catch (err) {
      /* 保存できないだけ。この回の操作は効いている */
    }
  }

  // ------------------------------------------------------------------ テーマ

  function applyTheme(theme) {
    var root = document.documentElement;
    if (theme === "light" || theme === "dark") { root.setAttribute("data-theme", theme); }
    else { root.removeAttribute("data-theme"); }
    var button = document.getElementById("btn-theme");
    if (button) {
      var label = THEME_LABEL[theme] || THEME_LABEL.auto;
      button.textContent = THEME_ICON[theme] || THEME_ICON.auto;   // アイコンのみ（research.md F5）
      button.title = label;
      button.setAttribute("aria-label", label + "（押すと切り替え）");
    }
  }

  function cycleTheme() {
    var now = pref("theme");
    var index = THEMES.indexOf(now);
    var next = THEMES[(index < 0 ? 0 : index + 1) % THEMES.length];
    pref("theme", next);
    applyTheme(next);
  }

  // -------------------------------------------------------------- ペインの幅

  function clampWidth(px) {
    px = Math.round(Number(px));
    if (!isFinite(px)) { return 0; }
    return Math.max(MIN_W, Math.min(MAX_W, px));
  }

  function widthVar(which) { return which === "left" ? "--left" : "--right"; }
  function prefName(which) { return which === "left" ? "left-width" : "right-width"; }
  function paneId(which) { return which === "left" ? "pane-left" : "pane-right"; }

  function setWidth(which, px, save) {
    var shell = document.getElementById("shell");
    var value = clampWidth(px);
    shell.style.setProperty(widthVar(which), value + "px");
    var sep = document.getElementById("sep-" + which);
    if (sep) { sep.setAttribute("aria-valuenow", String(value)); }
    if (save) { pref(prefName(which), String(value)); }
    return value;
  }

  function currentWidth(which) {
    var pane = document.getElementById(paneId(which));
    return pane ? pane.getBoundingClientRect().width : 0;
  }

  // ドラッグ中の生の幅（MIN_W 未満にもなりうる）を実際の表示へ反映する。MIN_W は
  // clampWidth の下限であると同時に、畳んだときのストリップ幅でもある（style.css）。
  // その床まで縮めても「開いたまま 40px に潰れた」表示にはせず、開閉ボタンで畳んだときと
  // 同じ見た目（中身を隠す）に倒す（ユーザー報告: D&D で縮めても一覧の中身が隠れず見えたまま）。
  function applyWidth(which, rawWidth, save) {
    var width = clampWidth(rawWidth);
    if (width <= MIN_W) {
      if (isOpen(which)) { setPane(which, false, save); }
      // 畳んだときは `--left`/`--right`（＝ 再度開いたときに戻る幅）はあえて書き換えない
      // （setWidth を呼ぶとそれも上書きしてしまう）。ただし `aria-valuenow` だけは
      // 実際の表示幅（40px）に合わせておく——ここを更新しないと、支援技術には
      // 畳む直前の幅のまま止まって見える（review 工程の指摘）。
      var sep = document.getElementById("sep-" + which);
      if (sep) { sep.setAttribute("aria-valuenow", String(MIN_W)); }
    } else {
      if (!isOpen(which)) { setPane(which, true, save); }
      setWidth(which, width, save);
    }
  }

  // ------------------------------------------------------------ ペインの開閉

  function isOpen(which) {
    var shell = document.getElementById("shell");
    return shell.getAttribute("data-" + which) !== "collapsed";
  }

  var PANE_NAME = { left: "ファイル一覧", right: "コメント一覧" };

  // 開閉状態が変わる経路はボタンのクリックだけでなく、キーボードショートカット
  // （{ / } / [ / ]）・セパレータへの Enter/Space・ドラッグでの MIN_W 到達（applyWidth）など
  // 複数ある（review 工程の指摘）。それらをすべて app.js 側で個別に検知するのではなく、
  // 状態を実際に書き換えるここ（setPane）1箇所から、登録されていれば呼ぶ。
  // ui.js はフックの中身（バッジの更新等）を一切知らない——画面の形だけを扱うという
  // 既存の約束（decisions.md）を保ったまま、app.js に「変わった」ことだけを伝える。
  var onPaneChange = null;

  function setPane(which, open, save) {
    var shell = document.getElementById("shell");
    shell.setAttribute("data-" + which, open ? "open" : "collapsed");
    var button = document.getElementById("btn-pane-" + which);
    if (button) {
      button.setAttribute("aria-expanded", open ? "true" : "false");
      // アイコンだけのボタンなので、状態（開く/閉じる）は title/aria-label の動詞で伝える。
      var label = (PANE_NAME[which] || which) + (open ? "を閉じる" : "を開く");
      button.title = label;
      button.setAttribute("aria-label", label);
    }
    if (save) { pref("pane-" + which, open ? "open" : "collapsed"); }
    if (onPaneChange) { onPaneChange(which, open); }
  }

  function togglePane(which) {
    setPane(which, !isOpen(which), true);
  }

  function openPane(which) {
    if (!isOpen(which)) { setPane(which, true, true); }
  }

  // ---------------------------------------------------------------- 境界

  function wireSeparator(which) {
    var sep = document.getElementById("sep-" + which);
    if (!sep) { return; }

    sep.addEventListener("pointerdown", function (event) {
      if (event.button !== 0) { return; }
      // 畳んでいる状態からドラッグを始めても、ここでは開かない。開いた瞬間にパネル幅が
      // ストリップ幅(40px)から以前の幅へ飛び、マウス位置と罫線の位置がずれてしまう
      // （ユーザー報告）。現在の実際の幅（畳んでいれば 40px）をそのまま起点にする。
      var startX = event.clientX;
      var startW = currentWidth(which);
      sep.setPointerCapture(event.pointerId);

      function move(e) {
        var delta = e.clientX - startX;
        applyWidth(which, which === "left" ? startW + delta : startW - delta, false);
      }
      function up() {
        sep.removeEventListener("pointermove", move);
        sep.removeEventListener("pointerup", up);
        sep.removeEventListener("pointercancel", up);
        try { sep.releasePointerCapture(event.pointerId); } catch (err) { /* すでに解放済み */ }
        // **離した時点で確定**（ドラッグ中に毎回書くと localStorage への書き込みが多すぎる）
        if (isOpen(which)) {
          setWidth(which, currentWidth(which), true);
          pref("pane-" + which, "open");
        } else {
          pref("pane-" + which, "collapsed");
        }
      }
      sep.addEventListener("pointermove", move);
      sep.addEventListener("pointerup", up);
      sep.addEventListener("pointercancel", up);
      event.preventDefault();
    });

    sep.addEventListener("keydown", function (event) {
      if (event.ctrlKey || event.metaKey || event.altKey) { return; }
      var step = event.shiftKey ? BIG_STEP : STEP;
      var now = currentWidth(which);
      var key = event.key;
      // ドラッグと同じ `applyWidth` を通す（review 工程の指摘）。個別に `setWidth` を
      // 呼んでいたときは、`Home`（最小幅）で「開いたまま 40px に潰れた」状態を保存でき、
      // ドラッグ側で塞いだはずの不変条件（MIN_W 以下は畳む）に穴が残っていた。
      if (key === "ArrowLeft") { applyWidth(which, which === "left" ? now - step : now + step, true); }
      else if (key === "ArrowRight") { applyWidth(which, which === "left" ? now + step : now - step, true); }
      else if (key === "Home") { applyWidth(which, MIN_W, true); }
      else if (key === "End") { applyWidth(which, MAX_W, true); }
      else if (key === "Enter" || key === " " || key === "Spacebar") { togglePane(which); }
      else { return; }
      event.preventDefault();
    });
  }

  // ------------------------------------------------------- トップバーの高さ

  function syncTopbarHeight() {
    // .shell の高さは「画面の高さ − トップバー」。トップバーはボタンが折り返すと高さが変わるので、
    // 固定値ではなく実測を CSS 変数へ渡す。
    var bar = document.querySelector(".topbar");
    if (!bar) { return; }
    var extra = 0;
    // #help・#submit-panel はフローティング表示（style.css の .modal）になり、文書の
    // 流れから外れたので、開いても .shell の高さには影響しない——ここから外す
    // （ユーザー報告: 他の表示に影響を与えないでほしい）。
    ["banners", "export-panel"].forEach(function (id) {
      var node = document.getElementById(id);
      if (node && !node.hidden) { extra += node.getBoundingClientRect().height; }
    });
    var total = Math.round(bar.getBoundingClientRect().height + extra);
    document.documentElement.style.setProperty("--topbar-h", total + "px");
  }

  // ---------------------------------------------------------------- 起動

  function init() {
    applyTheme(pref("theme"));
    ["left", "right"].forEach(function (which) {
      var storedWidth = clampWidth(pref(prefName(which)));
      setWidth(which, storedWidth, false);
      // 保存された組み合わせが「幅は最小なのに開いたまま」という壊れた状態（同じ
      // ブラウザで以前のバージョンを使っていた等で作られ得る）なら、読み込み時にも
      // 畳んだ扱いにする——MIN_W 以下は畳む、という不変条件をドラッグ・キーボードだけで
      // なく読み込みでも保つ（review 工程の指摘: 保存状態の読み込みだけ穴が残っていた）。
      var storedOpen = pref("pane-" + which) !== "collapsed";
      setPane(which, storedOpen && storedWidth > MIN_W, false);
    });

    var theme = document.getElementById("btn-theme");
    if (theme) { theme.addEventListener("click", cycleTheme); }
    ["left", "right"].forEach(function (which) {
      wireSeparator(which);
      var button = document.getElementById("btn-pane-" + which);
      if (button) { button.addEventListener("click", function () { togglePane(which); }); }
    });

    syncTopbarHeight();
    window.addEventListener("resize", syncTopbarHeight);
  }

  window.DiffReviewUI = {
    pref: pref,
    init: init,
    togglePane: togglePane,
    openPane: openPane,
    syncTopbarHeight: syncTopbarHeight,
    onPaneChange: function (fn) { onPaneChange = fn; },
    defaults: DEFAULTS
  };
})();
