/* diff-review-html の画面。フレームワークは使わない（オフライン・単一ファイルのため）。
 *
 * 守っている約束:
 *  - 描画は textContent だけ。innerHTML を使わないので、差分やコメントに何が入っていても
 *    HTML として解釈されない。
 *  - 書き出す JSON は正規形（キー昇順・インデント 2・末尾改行）。script 側と同じ形なので
 *    「書き出し → 読み込み → 再書き出し」でバイト一致する。
 *  - 下書きの保存キーには差分の digest を含める。file:// では全ページが 1 つの origin を
 *    共有するので、含めないと別レビューの下書きが混ざる。
 *  - localStorage は使えない環境がある（Firefox の file:// は例外を投げる）。握り潰さずに
 *    画面へ出して機能だけ落とす。
 */
(function () {
  "use strict";

  var SCHEMA = "diff-review/2";
  var SCHEMA_LEGACY = "diff-review/1";
  var STORAGE_KEY_PREFIX = "diff-review-html/v1/";
  var LAZY_LINE_LIMIT = 2000;
  var EXPAND_STEP = 20;                      // 展開ボタン 1 回で広がる行数
  var REVIEW_STATES = ["APPROVED", "CHANGES_REQUESTED", "COMMENTED"];
  var SIDES = ["LEFT", "RIGHT"];
  var THREAD_KINDS = ["review", "note"];     // note = 作者の説明（提出されない）
  var SEVERITIES = ["must", "should", "nit"];

  var BUNDLE_SCHEMA = "diff-review-bundle/1";

  // **差し替わり得る**。起動時は埋め込みから、あとから手でバンドルを開いても入れ替わる。
  // モジュール先頭で確定させると、読み込んだのに前の差分が出たままになる（design §2）。
  var diffData = { target: {}, files: [], rich_enabled: false, readonly: false };
  var target = {};
  var storageKey = STORAGE_KEY_PREFIX + "unknown";
  var readonly = false;
  var bundleSource = null;      // どこから来たか（画面の meta 行に出す）

  var state = { reviews: [], threads: [] };
  var drafts = {};
  var seq = 0;
  var dirty = false;
  var storageOk = true;
  var currentRow = null;

  // 画面の設定は ui.js が持つ（レビュー記録の JSON には入らない＝AC15）。
  // ui.js が読めていない不測の事態でも画面が死なないよう、既定値で動く形にしておく。
  var UI = window.DiffReviewUI || {
    pref: function (name, value) { return arguments.length === 1 ? null : value; },
    init: function () {},
    togglePane: function () {},
    syncTopbarHeight: function () {}
  };

  // ------------------------------------------------- 差分の差し替え（バンドル）

  function applyDiffData(data, source) {
    diffData = data;
    target = data.target || {};
    readonly = !!data.readonly;
    bundleSource = source || null;
    storageKey = STORAGE_KEY_PREFIX + (target.diff_digest || "unknown");
    // **画面の中だけの状態は全部作り直す**。取りこぼすと前の差分の展開や折りたたみが残る。
    viewModes = {};
    expandState = {};
    collapsed = {};
    treeOpen = {};
    currentRow = null;
    state = { reviews: [], threads: [] };
    drafts = {};
    seq = 0;
    dirty = false;
  }

  function validateBundle(bundle) {
    // 送り主は検査できない（file:// の origin は opaque）。**形で検査する**（research.md R2）。
    var problems = [];
    if (!bundle || typeof bundle !== "object" || Array.isArray(bundle)) {
      return ["オブジェクトではありません"];
    }
    if (bundle.schema !== BUNDLE_SCHEMA) {
      problems.push("バンドルではありません（期待: " + BUNDLE_SCHEMA + " / 実際: " + String(bundle.schema) + "）");
    }
    if (!bundle.target || typeof bundle.target !== "object") { problems.push("target がありません"); }
    if (!Array.isArray(bundle.files)) { problems.push("files が配列ではありません"); }
    if (bundle.review !== null && bundle.review !== undefined) {
      problems = problems.concat(validateRecord(bundle.review).map(function (p) { return "review: " + p; }));
    }
    return problems;
  }

  function adoptBundle(bundle, source) {
    var problems = validateBundle(bundle);
    if (problems.length) {
      // **いまの表示を壊さない**。読めなかったものに引きずられて画面を空にしない（要件 F6b）。
      banner("開けませんでした（" + (source || "不明") + "）: " + problems.join(" / "), [], "load");
      return false;
    }
    applyDiffData({
      target: bundle.target,
      files: bundle.files,
      rich_enabled: !!bundle.rich_enabled,
      readonly: readonly           // 参照専用かどうかは**ビューア側の性質**。バンドルでは変えない
    }, source);
    if (bundle.review) { adoptRecord(bundle.review, null); }   // adoptRecord が /1 の欠けも補う
    persist();
    renderAll();
    focusFirstRow();
    banner("読み込みました（" + (source || "不明") + "）: " + (bundle.files || []).length + " ファイル", [], "load");
    return true;
  }

  function focusFirstRow() {
    // 読み込んだのにフォーカスがボタンに残っていると、キーボードの現在位置が置き去りになる。
    var first = document.querySelector("#files .row[data-key]");
    if (first) { setCurrentRow(first); first.focus(); return; }
    var files = document.getElementById("files");
    if (files) { files.setAttribute("tabindex", "-1"); files.focus(); }
  }

  // ---------------------------------------------------------------- utilities

  function readEmbedded(id) {
    var node = document.getElementById(id);
    if (!node) { return null; }
    var text = node.textContent;
    if (!text || !text.trim()) { return null; }
    try {
      return JSON.parse(text);
    } catch (err) {
      return null;
    }
  }

  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (key) {
        var value = attrs[key];
        if (value === null || value === undefined || value === false) { return; }
        if (key === "text") { node.textContent = String(value); return; }
        if (key === "class") { node.className = value; return; }
        node.setAttribute(key, value === true ? "" : String(value));
      });
    }
    (children || []).forEach(function (child) {
      if (child) { node.appendChild(child); }
    });
    return node;
  }

  function clear(node) {
    while (node.firstChild) { node.removeChild(node.firstChild); }
  }

  function nextId(prefix) {
    seq += 1;
    return prefix + seq;
  }

  // ------------------------------------------------------- 正規形での書き出し

  function sortDeep(value) {
    if (Array.isArray(value)) { return value.map(sortDeep); }
    if (value && typeof value === "object") {
      var out = {};
      Object.keys(value).sort().forEach(function (key) { out[key] = sortDeep(value[key]); });
      return out;
    }
    return value;
  }

  function threadOrder(a, b) {
    var pa = a.path === null || a.path === undefined ? "" : a.path;
    var pb = b.path === null || b.path === undefined ? "" : b.path;
    if (pa !== pb) { return pa < pb ? -1 : 1; }
    var la = a.line === null || a.line === undefined ? -1 : a.line;
    var lb = b.line === null || b.line === undefined ? -1 : b.line;
    if (la !== lb) { return la - lb; }
    return a._order - b._order;
  }

  function canonicalRecord() {
    var reviewMap = {};
    var reviews = state.reviews.map(function (review, index) {
      var id = "r" + (index + 1);
      reviewMap[review.id] = id;
      return { id: id, author: review.author, state: review.state, body: review.body };
    });
    var threads = state.threads.slice().sort(threadOrder).map(function (thread, index) {
      var commentMap = {};
      thread.comments.forEach(function (comment, j) { commentMap[comment.id] = "c" + (j + 1); });
      return {
        id: "t" + (index + 1),
        kind: thread.kind === "note" ? "note" : "review",   // /1 には kind が無いので review を補う
        path: thread.path === undefined ? null : thread.path,
        line: thread.line === undefined ? null : thread.line,
        side: thread.side === undefined ? null : thread.side,
        start_line: thread.start_line === undefined ? null : thread.start_line,
        start_side: thread.start_side === undefined ? null : thread.start_side,
        resolved: !!thread.resolved,
        comments: thread.comments.map(function (comment, j) {
          return {
            id: "c" + (j + 1),
            review_id: comment.review_id ? (reviewMap[comment.review_id] || null) : null,
            author: comment.author,
            body: comment.body,
            severity: SEVERITIES.indexOf(comment.severity) === -1 ? null : comment.severity,
            in_reply_to: comment.in_reply_to ? (commentMap[comment.in_reply_to] || null) : null
          };
        })
      };
    });
    return { schema: SCHEMA, target: target, reviews: reviews, threads: threads };
  }

  function exportText() {
    return JSON.stringify(sortDeep(canonicalRecord()), null, 2) + "\n";
  }

  // ------------------------------------------------------------ 保存と復元

  function persist() {
    dirty = true;
    if (!storageOk) { return; }
    try {
      window.localStorage.setItem(storageKey, JSON.stringify({ state: state, drafts: drafts }));
    } catch (err) {
      storageOk = false;
      banner("このブラウザでは下書きが保存できません（" + err.name + "）。書き出しは使えます。", []);
    }
  }

  function restore() {
    try {
      var raw = window.localStorage.getItem(storageKey);
      if (!raw) { return null; }
      return JSON.parse(raw);
    } catch (err) {
      storageOk = false;
      return null;
    }
  }

  function dropSaved() {
    try { window.localStorage.removeItem(storageKey); } catch (err) { /* 保存できない環境 */ }
  }

  // --------------------------------------------------------------- バナー

  function banner(message, buttons, key) {
    // 同じ種類のバナー（key つき）は**置き換える**。ファイルを開くたびに積み上がると、
    // 画面の上半分がバナーで埋まって差分が見えなくなる。
    if (key) {
      var old = document.querySelector('#banners [data-banner="' + cssEscape(key) + '"]');
      if (old && old.parentNode) { old.parentNode.removeChild(old); }
    }
    var box = el("div", { class: "banner", "data-banner": key || null },
                [el("div", { text: message })]);
    if (buttons && buttons.length) {
      var actions = el("div", { class: "row-actions" }, buttons.map(function (spec) {
        var button = el("button", { type: "button", text: spec.label });
        button.addEventListener("click", function () {
          spec.onClick();
          if (spec.dismiss !== false && box.parentNode) { box.parentNode.removeChild(box); }
        });
        return button;
      }));
      box.appendChild(actions);
    }
    document.getElementById("banners").appendChild(box);
  }

  // ------------------------------------------------------- 記録の読み込み

  function adoptRecord(record, note) {
    state = { reviews: [], threads: [] };
    (record.reviews || []).forEach(function (review) {
      state.reviews.push({
        id: review.id || nextId("r"),
        author: review.author || "unknown",
        state: review.state,
        body: review.body || ""
      });
    });
    (record.threads || []).forEach(function (thread, index) {
      state.threads.push({
        id: thread.id || nextId("t"),
        _order: index,
        kind: thread.kind === "note" ? "note" : "review",   // /1 には kind が無いので review を補う
        path: thread.path === undefined ? null : thread.path,
        line: thread.line === undefined ? null : thread.line,
        side: thread.side === undefined ? null : thread.side,
        start_line: thread.start_line === undefined ? null : thread.start_line,
        start_side: thread.start_side === undefined ? null : thread.start_side,
        resolved: !!thread.resolved,
        comments: (thread.comments || []).map(function (comment) {
          return {
            id: comment.id || nextId("c"),
            review_id: comment.review_id === undefined ? null : comment.review_id,
            author: comment.author || "unknown",
            body: comment.body || "",
            severity: SEVERITIES.indexOf(comment.severity) === -1 ? null : comment.severity,
            in_reply_to: comment.in_reply_to === undefined ? null : comment.in_reply_to
          };
        })
      });
    });
    // 採番は「読み込んだ記録に実在する id の最大値」から続ける。件数から決めると、
    // t1001 のような id を持つ記録を読んだときに新規 id と衝突する。
    var maxSuffix = 0;
    var scan = function (id) {
      var m = /^[a-z](\d+)$/.exec(String(id || ""));
      if (m) { maxSuffix = Math.max(maxSuffix, parseInt(m[1], 10)); }
    };
    state.reviews.forEach(function (r) { scan(r.id); });
    state.threads.forEach(function (t) { scan(t.id); t.comments.forEach(function (c) { scan(c.id); }); });
    seq = Math.max(seq, maxSuffix);
    if (note) { banner(note, []); }
  }

  // 検査の規則は diff_review.py の validate() と対にする。片方だけ緩いと、
  // CLI が exit 3 で落とす記録を画面が黙って受け入れ、そのまま書き出してしまう。
  function validateRecord(record) {
    if (!record || typeof record !== "object") { return ["オブジェクトではありません"]; }
    var problems = [];
    if (record.schema !== SCHEMA && record.schema !== SCHEMA_LEGACY) {
      problems.push("スキーマが " + SCHEMA + "（または " + SCHEMA_LEGACY + "）ではありません（"
                    + String(record.schema) + "）");
    }
    if (!record.target || typeof record.target !== "object") { problems.push("target がありません"); }
    if (!Array.isArray(record.reviews)) { problems.push("reviews が配列ではありません"); }
    if (!Array.isArray(record.threads)) { problems.push("threads が配列ではありません"); }

    var reviewIds = {};
    (record.reviews || []).forEach(function (item, i) {
      if (!item || typeof item !== "object") { problems.push("reviews[" + i + "] がオブジェクトではありません"); return; }
      if (!item.id) { problems.push("reviews[" + i + "].id がありません"); }
      else if (reviewIds[item.id]) { problems.push("reviews[" + i + "].id が重複しています"); }
      else { reviewIds[item.id] = true; }
      if (REVIEW_STATES.indexOf(item.state) === -1) {
        problems.push("reviews[" + i + "].state が " + REVIEW_STATES.join("/") + " ではありません（" + String(item.state) + "）");
      }
    });

    var threadIds = {};
    (record.threads || []).forEach(function (thread, i) {
      var where = "threads[" + i + "]";
      if (!thread || typeof thread !== "object") { problems.push(where + " がオブジェクトではありません"); return; }
      if (!thread.id) { problems.push(where + ".id がありません"); }
      else if (threadIds[thread.id]) { problems.push(where + ".id が重複しています"); }
      else { threadIds[thread.id] = true; }

      var kind = thread.kind === undefined ? "review" : thread.kind;
      if (THREAD_KINDS.indexOf(kind) === -1) {
        problems.push(where + ".kind が " + THREAD_KINDS.join("/") + " ではありません");
      }

      var line = thread.line === undefined ? null : thread.line;
      var side = thread.side === undefined ? null : thread.side;
      var path = thread.path === undefined ? null : thread.path;
      if (line !== null) {
        if (typeof line !== "number") { problems.push(where + ".line が整数ではありません"); }
        if (path === null) { problems.push(where + ".path がありません（line があるなら必須）"); }
        if (SIDES.indexOf(side) === -1) { problems.push(where + ".side が LEFT/RIGHT ではありません"); }
      } else if (side !== null) {
        problems.push(where + ".side は line が null のとき null です");
      }

      if (!Array.isArray(thread.comments) || !thread.comments.length) {
        problems.push(where + " にコメントがありません");
        return;
      }
      var commentIds = {};
      thread.comments.forEach(function (comment, j) {
        var cwhere = where + ".comments[" + j + "]";
        if (!comment || typeof comment !== "object") { problems.push(cwhere + " がオブジェクトではありません"); return; }
        if (!comment.id) { problems.push(cwhere + ".id がありません"); }
        else if (commentIds[comment.id]) { problems.push(cwhere + ".id が重複しています"); }
        else { commentIds[comment.id] = true; }
        if (typeof comment.body !== "string" || !comment.body.trim()) { problems.push(cwhere + ".body が空です"); }
        if (comment.review_id && !reviewIds[comment.review_id]) {
          problems.push(cwhere + ".review_id が存在しないレビューを指しています");
        }
        if (kind === "note" && comment.review_id) {
          problems.push(cwhere + ".review_id は説明コメント（note）では持てません");
        }
        if (comment.severity !== undefined && comment.severity !== null
            && SEVERITIES.indexOf(comment.severity) === -1) {
          problems.push(cwhere + ".severity が " + SEVERITIES.join("/") + " ではありません");
        }
        if (kind === "note" && comment.severity) {
          problems.push(cwhere + ".severity は説明コメント（note）では持てません");
        }
      });
      thread.comments.forEach(function (comment, j) {
        if (comment && comment.in_reply_to && !commentIds[comment.in_reply_to]) {
          problems.push(where + ".comments[" + j + "].in_reply_to が同じスレッドにありません");
        }
      });
    });
    return problems;
  }

  function checkIdentity(record) {
    var recorded = record.target || {};
    var notes = [];
    if (recorded.diff_digest && target.diff_digest && recorded.diff_digest !== target.diff_digest) {
      notes.push("この記録は別の差分に対するものです（差分の内容が変わっています）");
    } else if (recorded.base_commit && target.base_commit && recorded.base_commit !== target.base_commit) {
      notes.push("この記録は別のコミットを基準にしています");
    }
    return notes;
  }

  function importRecord(record, source) {
    var problems = validateRecord(record);
    if (problems.length) {
      banner("読み込めませんでした（" + source + "）: " + problems.join(" / "), [], "load");
      return false;
    }
    adoptRecord(record, null);
    checkIdentity(record).forEach(function (note) { banner(note + " 位置が見つからない指摘は「位置不明」欄に出します。", []); });
    drafts = {};
    dirty = false;
    persist();
    renderAll();
    return true;
  }

  // ------------------------------------------------------------- 差分の描画

  function fileKey(path) { return "file:" + path; }
  function rowKey(path, side, line) { return "line:" + path + ":" + side + ":" + line; }

  function renderMeta() {
    var parts = [];
    parts.push(String(target.source || "unstaged"));
    if (target.range) { parts.push(target.range); }
    if (target.base_commit) { parts.push("base " + String(target.base_commit).slice(0, 7)); }
    if (target.diff_digest) { parts.push("diff " + String(target.diff_digest).slice(0, 7)); }
    parts.push((diffData.files || []).length + " ファイル");
    if (bundleSource) { parts.push("← " + bundleSource); }
    if (readonly) { parts.push("参照専用"); }
    document.getElementById("meta").textContent = parts.join(" ・ ");
  }

  function treeMode() { return UI.pref("filetree") === "on"; }

  function gotoFile(index) {
    // **移動には必ず focus() を伴う**。リンクだけではスクロールしてもフォーカスが動かず、
    // キーボードの現在位置が置き去りになる（research.md F7 で実測）。
    var section = document.getElementById("file-" + index);
    if (!section) { return; }
    section.setAttribute("tabindex", "-1");
    section.scrollIntoView({ block: "start" });
    section.focus();
  }

  function statsSpan(file) {
    return el("span", { class: "tree-stat" }, [
      el("span", { class: "stat-add", text: "+" + file.additions }),
      document.createTextNode(" "),
      el("span", { class: "stat-del", text: "-" + file.deletions })
    ]);
  }

  function renderFileList() {
    var nav = document.getElementById("filelist");
    clear(nav);
    nav.removeAttribute("role");
    nav.removeAttribute("aria-label");
    var button = document.getElementById("btn-tree");
    if (button) {
      button.setAttribute("aria-pressed", treeMode() ? "true" : "false");
      button.textContent = treeMode() ? "フラット" : "ツリー";
    }
    if (!(diffData.files || []).length) {
      nav.appendChild(el("p", { class: "empty", text: "変更ファイルなし" }));
      return;
    }
    if (treeMode()) { renderFileTree(nav); return; }
    (diffData.files || []).forEach(function (file, index) {
      var link = el("a", { href: "#file-" + index }, [
        el("span", { text: file.path }),
        el("span", {}, [
          el("span", { class: "stat-add", text: "+" + file.additions }),
          document.createTextNode(" "),
          el("span", { class: "stat-del", text: "-" + file.deletions })
        ])
      ]);
      link.addEventListener("click", function (event) {
        event.preventDefault();
        gotoFile(index);
      });
      nav.appendChild(link);
    });
  }

  // -------------------------------------------------------------- ツリー表示

  function buildTree(files) {
    var root = { name: "", dirs: {}, order: [], files: [] };
    files.forEach(function (file, index) {
      var parts = String(file.path).split("/");
      var leaf = parts.pop();
      var node = root;
      parts.forEach(function (part) {
        if (!node.dirs[part]) {
          node.dirs[part] = { name: part, dirs: {}, order: [], files: [] };
          node.order.push(part);
        }
        node = node.dirs[part];
      });
      node.files.push({ name: leaf, file: file, index: index });
    });
    return collapseSingles(root);
  }

  function collapseSingles(node) {
    // 子がディレクトリ 1 つだけなら、その名前を連結して 1 行にまとめる（decisions.md D10）。
    // 畳まないと docs/ClaudeCode/skills/other/... がファイルまで 5 段になり、構造が読めない。
    node.order.forEach(function (name) { collapseSingles(node.dirs[name]); });
    while (node.order.length === 1 && !node.files.length) {
      var only = node.dirs[node.order[0]];
      node.name = node.name ? node.name + "/" + only.name : only.name;
      node.dirs = only.dirs;
      node.order = only.order;
      node.files = only.files;
    }
    return node;
  }

  function renderFileTree(nav) {
    nav.setAttribute("role", "tree");
    nav.setAttribute("aria-label", "変更ファイル");
    var root = buildTree(diffData.files || []);
    appendTreeChildren(nav, root, "");
    var first = nav.querySelector('[role="treeitem"]');
    if (first) { first.setAttribute("tabindex", "0"); }   // ローミング: 木の中で 1 つだけ
    // キーの受け口は wire() で 1 回だけ張る。ここで張ると描き直すたびに重なる。
  }

  function appendTreeChildren(host, node, prefix) {
    node.order.forEach(function (name) {
      var dir = node.dirs[name];
      var path = (prefix ? prefix + "/" : "") + dir.name;
      var open = treeOpen[path] !== false;
      var item = el("div", {
        role: "treeitem",
        class: "tree-item tree-dir",
        tabindex: "-1",
        "aria-expanded": open ? "true" : "false"
      }, [
        el("span", { class: "tree-twisty", text: open ? "▾" : "▸" }),
        el("span", { class: "tree-name", text: dir.name })
      ]);
      var group = el("div", { role: "group", class: "tree-group" });
      appendTreeChildren(group, dir, path);
      item.addEventListener("click", function () { toggleTreeDir(item, path); });
      host.appendChild(item);
      host.appendChild(group);
    });
    node.files.forEach(function (entry) {
      var item = el("div", {
        role: "treeitem",
        class: "tree-item tree-file",
        tabindex: "-1",
        "data-index": entry.index
      }, [
        el("span", { class: "tree-twisty", text: "" }),
        el("span", { class: "tree-name", text: entry.name }),
        statsSpan(entry.file)
      ]);
      item.addEventListener("click", function () { gotoFile(entry.index); });
      host.appendChild(item);
    });
  }

  var treeOpen = {};    // ディレクトリのパス -> 開いているか（画面の中だけの状態。保存しない）

  function toggleTreeDir(item, path) {
    var open = item.getAttribute("aria-expanded") !== "true";
    item.setAttribute("aria-expanded", open ? "true" : "false");
    item.querySelector(".tree-twisty").textContent = open ? "▾" : "▸";
    treeOpen[path] = open;
  }

  function visibleTreeItems() {
    var nav = document.getElementById("filelist");
    return Array.prototype.filter.call(
      nav.querySelectorAll('[role="treeitem"]'),
      function (item) { return item.offsetParent !== null || item.getClientRects().length; }
    );
  }

  function focusTreeItem(item) {
    var nav = document.getElementById("filelist");
    Array.prototype.forEach.call(nav.querySelectorAll('[role="treeitem"]'), function (other) {
      other.setAttribute("tabindex", "-1");
    });
    item.setAttribute("tabindex", "0");
    item.focus();
  }

  function onTreeKeyDown(event) {
    var item = event.target;
    if (!item || !item.getAttribute || item.getAttribute("role") !== "treeitem") { return; }
    var items = visibleTreeItems();
    var index = items.indexOf(item);
    var key = event.key;
    var isDir = item.classList.contains("tree-dir");

    if (key === "ArrowDown") { if (index + 1 < items.length) { focusTreeItem(items[index + 1]); } }
    else if (key === "ArrowUp") { if (index > 0) { focusTreeItem(items[index - 1]); } }
    else if (key === "Home") { if (items.length) { focusTreeItem(items[0]); } }
    else if (key === "End") { if (items.length) { focusTreeItem(items[items.length - 1]); } }
    else if (key === "ArrowRight") {
      if (isDir && item.getAttribute("aria-expanded") === "false") { item.click(); }
      else if (isDir && index + 1 < items.length) { focusTreeItem(items[index + 1]); }
    } else if (key === "ArrowLeft") {
      if (isDir && item.getAttribute("aria-expanded") === "true") { item.click(); }
      else {
        // 親へ戻る: 自分を含む group の直前にある treeitem
        var group = item.parentNode;
        var parent = group && group.getAttribute && group.getAttribute("role") === "group"
          ? group.previousElementSibling : null;
        if (parent && parent.getAttribute("role") === "treeitem") { focusTreeItem(parent); }
      }
    } else if (key === "Enter" || key === " " || key === "Spacebar") {
      item.click();
      if (isDir) { focusTreeItem(item); }
    } else { return; }
    event.preventDefault();
  }

  function lineCount(file) {
    return (file.hunks || []).reduce(function (sum, hunk) { return sum + hunk.lines.length; }, 0);
  }

  // ---------------------------------------------------- ファイルと行の描画

  var viewModes = {};      // path -> "rich" | "source"
  var expandState = {};    // path -> { gapIndex: {top: 件数, bottom: 件数} }
  var collapsed = {};      // path -> 畳んでいるか（未設定なら行数から決める）

  function viewMode(file) {
    if (!file.rich || !window.DiffReviewRich) { return "source"; }
    return viewModes[file.path] || "rich";
  }

  function renderFiles() {
    var container = document.getElementById("files");
    clear(container);
    if (!(diffData.files || []).length) {
      // 差分が 0 件でも画面は無言にしない。ヘッダの「0 ファイル」だけだと、
      // 壊れているのか本当に差分が無いのかが利用者に区別できない。
      container.appendChild(el("p", { class: "empty", text: "差分がありません（この指定では変更が見つかりませんでした）。" }));
      container.appendChild(el("p", { class: "hint", text: "レビュー記録の JSON は読み込めます。別の差分を見るには --staged / --range などを指定して生成し直してください。" }));
      return;
    }
    (diffData.files || []).forEach(function (file, index) {
      // 既定は「大きいファイルは畳む」。ただし一度開いたら、表示形式を切り替えても開いたまま。
      var big = collapsed[file.path] === undefined
        ? lineCount(file) > LAZY_LINE_LIMIT
        : collapsed[file.path];
      var section = el("section", {
        class: "file",
        id: "file-" + index,
        "data-path": file.path,
        "data-collapsed": big ? "true" : "false"
      });

      var toggle = el("button", {
        type: "button",
        class: "file-toggle",
        "aria-expanded": big ? "false" : "true",
        text: file.path
      });
      toggle.addEventListener("click", function () { toggleFile(section, file); });

      var tags = [statusLabel(file.status)];
      if (file.old_path) { tags.push("← " + file.old_path); }
      if (file.binary) { tags.push("バイナリ"); }
      if (file.language) { tags.push(file.language); }
      if (big) { tags.push(lineCount(file) + " 行・既定で折りたたみ"); }
      tags.push("+" + file.additions + " -" + file.deletions);

      var actions = el("span", { class: "file-actions" });
      if (file.rich && window.DiffReviewRich) {
        var richButton = el("button", {
          type: "button",
          class: "view-toggle",
          "aria-pressed": viewMode(file) === "rich" ? "true" : "false",
          text: viewMode(file) === "rich" ? "rich 表示" : "source 表示"
        });
        richButton.addEventListener("click", function () { toggleView(section, file); });
        actions.appendChild(richButton);
      }
      if (!file.binary && file.expand && !file.expand.truncated) {
        var allButton = el("button", { type: "button", class: "expand-all", text: "すべて展開" });
        allButton.addEventListener("click", function () { expandAll(section, file); });
        actions.appendChild(allButton);
      }
      if (!readonly) {
        var commentButton = el("button", {
          type: "button",
          class: "comment-open",
          "data-scope": "file",
          "data-path": file.path,
          "aria-expanded": "false",
          text: "ファイルにコメント"
        });
        commentButton.addEventListener("click", function () {
          toggleComposer(fileKey(file.path), commentButton, { path: file.path, line: null, side: null });
        });
        actions.appendChild(commentButton);
      }

      section.appendChild(el("div", { class: "file-head" }, [
        el("div", { class: "path" }, [toggle]),
        el("div", { class: "tags", text: tags.join(" ・ ") }),
        actions
      ]));
      section.appendChild(el("div", { class: "threads", "data-threads": fileKey(file.path) }));
      section.appendChild(el("div", { class: "composer-slot", "data-composer": fileKey(file.path) }));

      var body = el("div", { class: "file-body" });
      section.appendChild(body);
      if (!big) { fillFileBody(body, file); }
      container.appendChild(section);
    });
  }

  function statusLabel(status) {
    var map = { A: "新規", M: "変更", D: "削除", R: "リネーム", C: "コピー", T: "モード変更" };
    var head = String(status || "").charAt(0);
    return map[head] || String(status || "");
  }

  function toggleFile(section, file) {
    var wasCollapsed = section.getAttribute("data-collapsed") === "true";
    var body = section.querySelector(".file-body");
    if (wasCollapsed && !body.childNodes.length) { fillFileBody(body, file); }
    section.setAttribute("data-collapsed", wasCollapsed ? "false" : "true");
    section.querySelector(".file-toggle").setAttribute("aria-expanded", wasCollapsed ? "true" : "false");
    collapsed[file.path] = !wasCollapsed;
    renderThreads();
  }

  function toggleView(section, file) {
    viewModes[file.path] = viewMode(file) === "rich" ? "source" : "rich";
    var button = section.querySelector(".view-toggle");
    if (button) {
      button.setAttribute("aria-pressed", viewMode(file) === "rich" ? "true" : "false");
      button.textContent = viewMode(file) === "rich" ? "rich 表示" : "source 表示";
    }
    var body = section.querySelector(".file-body");
    clear(body);
    fillFileBody(body, file);
    renderThreads();
    if (button) { button.focus(); }
  }

  function expandAll(section, file) {
    // ファイル内の隙間をすべて開く（AC12）。折りたたみ中なら先に開く。
    var gaps = gapsOf(file);
    var state = expandState[file.path] || (expandState[file.path] = {});
    gaps.forEach(function (gap, i) {
      state[i] = { top: gap.end - gap.start + 1, bottom: 0 };
    });
    section.setAttribute("data-collapsed", "false");
    section.querySelector(".file-toggle").setAttribute("aria-expanded", "true");
    collapsed[file.path] = false;
    // **フォーカスを落とさない**（AC-I4）。描き直しで行のノードが作り直されるので、
    // 元いた行を指し直し、見つからなければ押したボタンへ戻す。
    var currentKey = currentRow && currentRow.getAttribute ? currentRow.getAttribute("data-key") : null;
    var body = section.querySelector(".file-body");
    clear(body);
    fillFileBody(body, file);
    renderThreads();
    var again = currentKey
      ? section.querySelector('.row[data-key="' + cssEscape(currentKey) + '"]')
      : null;
    setCurrentRow(again);
    if (again) { again.focus(); }
    else {
      var button = section.querySelector(".expand-all");
      if (button) { button.focus(); }
    }
  }

  function hunkRange(hunk) {
    // そのハンクが新側で占める行番号の範囲（削除だけのハンクは空になる）
    var first = null, last = null;
    (hunk.lines || []).forEach(function (line) {
      if (line.new === null || line.new === undefined) { return; }
      if (first === null) { first = line.new; }
      last = line.new;
    });
    if (first === null) { return { start: hunk.new_start, end: hunk.new_start - 1 }; }
    return { start: first, end: last };
  }

  function gapsOf(file) {
    // ハンクとハンクの間・前後の「見えていない範囲」を出す
    if (!file.expand || file.expand.truncated || !file.expand.count) { return []; }
    var total = file.expand.count;
    var gaps = [];
    var cursor = 1;
    (file.hunks || []).forEach(function (hunk) {
      var range = hunkRange(hunk);
      if (range.start > cursor) { gaps.push({ start: cursor, end: range.start - 1 }); }
      else { gaps.push(null); }
      cursor = Math.max(cursor, range.end + 1);
    });
    gaps.push(cursor <= total ? { start: cursor, end: total } : null);
    return gaps;
  }

  function expandLine(file, no) {
    var ex = file.expand;
    if (!ex || ex.truncated) { return null; }
    if (ex.tokens) { return { tokens: ex.tokens[no - 1] || [], text: null }; }
    if (ex.lines) { return { tokens: null, text: ex.lines[no - 1] === undefined ? "" : ex.lines[no - 1] }; }
    return null;
  }

  function fillFileBody(body, file) {
    if (file.binary && !(file.rich && viewMode(file) === "rich")) {
      body.appendChild(el("p", { class: "empty", text: "バイナリのため差分は表示しません（ファイル単位のコメントは付けられます）" }));
      return;
    }
    if (viewMode(file) === "rich") {
      var rich = window.DiffReviewRich.render(file.rich);
      if (rich) { body.appendChild(rich); return; }
    }
    if (!file.hunks || !file.hunks.length) {
      body.appendChild(el("p", { class: "empty", text: "表示できる差分の本文がありません" }));
      return;
    }
    if (file.expand && file.expand.truncated) {
      body.appendChild(el("p", { class: "hint", text:
        "このファイルは " + file.expand.count + " 行あるため、前後の展開データを持っていません"
        + "（生成時に --expand-max-lines を上げてください）" }));
    }
    var split = splitMode();
    var gaps = gapsOf(file);
    file.hunks.forEach(function (hunk, index) {
      renderGap(body, file, gaps[index], index);
      body.appendChild(el("div", { class: "hunk-head", text: hunk.header }));
      if (split) {
        pairLines(hunk.lines).forEach(function (pair) {
          body.appendChild(renderRowSplit(file, pair.left, pair.right, false));
        });
      } else {
        hunk.lines.forEach(function (line) { body.appendChild(renderRow(file, line)); });
      }
    });
    renderGap(body, file, gaps[file.hunks.length], file.hunks.length);
  }

  function renderGap(body, file, gap, index) {
    if (!gap) { return; }
    var state = expandState[file.path] || (expandState[file.path] = {});
    var shown = state[index] || (state[index] = { top: 0, bottom: 0 });
    var size = gap.end - gap.start + 1;
    var topEnd = gap.start + Math.min(shown.top, size) - 1;
    var bottomStart = gap.end - Math.min(shown.bottom, size) + 1;
    var remaining = bottomStart - topEnd - 1;

    for (var n = gap.start; n <= topEnd; n += 1) { appendContext(body, file, n); }
    if (remaining > 0) {
      body.appendChild(expander(file, index, gap, shown, remaining));
      for (var m = bottomStart; m <= gap.end; m += 1) { appendContext(body, file, m); }
    } else {
      for (var k = topEnd + 1; k <= gap.end; k += 1) { appendContext(body, file, k); }
    }
  }

  function expander(file, index, gap, shown, remaining) {
    var row = el("div", { class: "expander", "data-gap": index });
    var label = el("span", { class: "expander-label", text: "… " + remaining + " 行" });
    var up = el("button", { type: "button", class: "expand-up", text: "↑ " + EXPAND_STEP + " 行" });
    up.addEventListener("click", function () {
      shown.bottom = Math.min(shown.bottom + EXPAND_STEP, gap.end - gap.start + 1);
      redrawFile(file);
    });
    var down = el("button", { type: "button", class: "expand-down", text: "↓ " + EXPAND_STEP + " 行" });
    down.addEventListener("click", function () {
      shown.top = Math.min(shown.top + EXPAND_STEP, gap.end - gap.start + 1);
      redrawFile(file);
    });
    row.appendChild(label);
    // 下に続くハンクがあるときだけ「↑」、上にハンクがあるときだけ「↓」を出す
    if (index < (file.hunks || []).length) { row.appendChild(up); }
    if (index > 0) { row.appendChild(down); }
    return row;
  }

  function redrawFile(file) {
    var section = document.querySelector('.file[data-path="' + cssEscape(file.path) + '"]');
    if (!section) { return; }
    // 再描画で行のノードが作り直されるので、**現在行を指し直す**。
    // 放っておくと currentRow が切り離されたノードのまま残り、closest(".file") が null を返して
    // 以降のキー操作（e / Shift+E / t / f）が黙って効かなくなる。
    var currentKey = currentRow && currentRow.getAttribute ? currentRow.getAttribute("data-key") : null;
    var body = section.querySelector(".file-body");
    clear(body);
    fillFileBody(body, file);
    renderThreads();
    var again = currentKey
      ? section.querySelector('.row[data-key="' + cssEscape(currentKey) + '"]')
      : null;
    setCurrentRow(again);
    var next = section.querySelector(".expander button");
    if (next) { next.focus(); }
  }

  function appendContext(body, file, no) {
    var data = expandLine(file, no);
    if (!data) { return; }
    var line = {
      kind: "ctx", old: null, new: no,
      text: data.text === null ? null : data.text,
      tokens: data.tokens
    };
    // split でも文脈行は**両側に同じ本文**を出す（decisions.md D9）。展開データは片側しか
    // 持たないので、知らない側の行番号は空になる。片側を空行にすると「削除された行」に見えて嘘になる。
    body.appendChild(splitMode() ? renderRowSplit(file, line, line, true)
                                 : renderRow(file, line, true));
  }

  function tokensFor(file, line) {
    // 行が自分でトークンを持っていればそれ。無ければ**展開データ側から行番号で引く**
    // （同じ配列を 2 回運ばないための取り決め。生成側 attach_tokens と対）。
    if (line.tokens) { return line.tokens; }
    var ex = file && file.expand;
    if (!ex || !ex.tokens) { return null; }
    var side = line.kind === "del" ? "old" : "new";
    if (ex.side !== side) { return null; }
    var number = line.kind === "del" ? line.old : line.new;
    if (!number) { return null; }
    return ex.tokens[number - 1] || null;
  }

  function codeCell(file, line) {
    // トークンがあれば span に分けて描く。無ければそのままテキスト（どちらも textContent）。
    var cell = el("span", { class: "code" });
    line = { kind: line.kind, old: line.old, new: line.new, text: line.text,
             tokens: tokensFor(file, line) };
    if (line.tokens && line.tokens.length) {
      line.tokens.forEach(function (token) {
        cell.appendChild(el("span", { class: "tok-" + token[0], text: token[1] }));
      });
      return cell;
    }
    cell.textContent = line.text === null || line.text === undefined ? "" : line.text;
    return cell;
  }

  function renderRow(file, line, expanded) {
    var side = line.kind === "del" ? "LEFT" : "RIGHT";
    var number = line.kind === "del" ? line.old : line.new;
    var key = rowKey(file.path, side, number);
    var mark = line.kind === "add" ? "+" : (line.kind === "del" ? "-" : " ");

    // 参照専用では**作らない**（隠さない）。DOM に無ければ、開発者ツールで戻すこともできない。
    var button = null;
    if (!readonly) {
      button = el("button", {
        type: "button",
        class: "comment-open",
        "aria-expanded": "false",
        "aria-label": "この行にコメントする",
        text: "+"
      });
      button.addEventListener("click", function (event) {
        event.stopPropagation();
        toggleComposer(key, button, { path: file.path, line: number, side: side });
      });
    }

    var row = el("div", {
      class: expanded ? "row expanded" : "row",
      "data-kind": line.kind,
      "data-key": key,
      tabindex: "-1"
    }, [
      el("div", { class: "line" }, [
        el("span", { class: "gutter", text: line.old === null || line.old === undefined ? "" : String(line.old) }),
        el("span", { class: "gutter", text: line.new === null || line.new === undefined ? "" : String(line.new) }),
        button,                                  // 参照専用では null（el が落とす）
        el("span", { class: "mark", text: mark }),
        codeCell(file, line)
      ])
    ]);
    row.addEventListener("focus", function () { setCurrentRow(row); });
    row.appendChild(el("div", { class: "threads", "data-threads": key }));
    row.appendChild(el("div", { class: "composer-slot", "data-composer": key }));
    return row;
  }


  // ------------------------------------------------------------- split 表示

  function splitMode() { return UI.pref("split") === "on"; }

  function pairLines(lines) {
    // 削除の連なりと追加の連なりを溜め、文脈行と終端で吐き出す（research.md F8 で実測）。
    // 左右の件数・順序は元の行列と一致し、行番号はそれぞれ単調増加になる。
    var rows = [];
    var dels = [];
    var adds = [];
    function flush() {
      var n = Math.max(dels.length, adds.length);
      for (var k = 0; k < n; k += 1) {
        rows.push({ left: dels[k] || null, right: adds[k] || null });
      }
      dels = [];
      adds = [];
    }
    (lines || []).forEach(function (line) {
      if (line.kind === "del") { dels.push(line); return; }
      if (line.kind === "add") { adds.push(line); return; }
      flush();
      rows.push({ left: line, right: line });
    });
    flush();
    return rows;
  }

  function anchorOf(line) {
    // コメントの位置づけは **unified とまったく同じ規則**にする。
    // ここがずれると、同じ指摘が表示形式を変えた瞬間に「位置不明」へ落ちる。
    if (!line) { return null; }
    var side = line.kind === "del" ? "LEFT" : "RIGHT";
    var number = line.kind === "del" ? line.old : line.new;
    if (number === null || number === undefined) { return null; }
    return { side: side, number: number };
  }

  function cellAnchor(line, side) {
    // 左のセルが位置を持つのは削除行のときだけ。文脈行は左右が同じ行なので、
    // unified と同じく**右（新側）**に 1 つだけ位置を持たせる。
    var anchor = anchorOf(line);
    if (!anchor || anchor.side !== side) { return null; }
    return anchor;
  }

  function splitCell(file, line, side, expanded) {
    var cls = "cell cell-" + (side === "LEFT" ? "left" : "right");
    if (!line) {
      return el("div", { class: cls, "data-kind": "none" }, [
        el("span", { class: "gutter", text: "" }),
        el("span", { class: "mark", text: "" }),
        el("span", { class: "code", text: "" })
      ]);
    }
    var number = side === "LEFT" ? line.old : line.new;
    var kind = expanded ? "ctx" : line.kind;
    var mark = line.kind === "add" ? "+" : (line.kind === "del" ? "-" : " ");
    var cell = el("div", { class: cls, "data-kind": kind }, [
      el("span", { class: "gutter", text: number === null || number === undefined ? "" : String(number) }),
      el("span", { class: "mark", text: mark })
    ]);
    var anchor = cellAnchor(line, side);
    if (anchor && !readonly) {
      var button = el("button", {
        type: "button",
        class: "comment-open",
        "aria-expanded": "false",
        "aria-label": (side === "LEFT" ? "変更前" : "変更後") + "のこの行にコメントする",
        text: "+"
      });
      var key = rowKey(file.path, anchor.side, anchor.number);
      button.addEventListener("click", function (event) {
        event.stopPropagation();
        toggleComposer(key, button, { path: file.path, line: anchor.number, side: anchor.side });
      });
      cell.appendChild(button);
    }
    cell.appendChild(codeCell(file, line));
    return cell;
  }

  function splitSlots(file, line, side, labelled) {
    // コメントの入れ物は**位置を持つ側にだけ**用意する（鍵は unified と同じ line:path:SIDE:n）。
    // こうしておけば slotFor() は鍵で引くだけなので変更が要らない（decisions.md D2）。
    var anchor = cellAnchor(line, side);
    if (!anchor) { return null; }
    var key = rowKey(file.path, anchor.side, anchor.number);
    var children = [];
    if (labelled) {
      children.push(el("div", { class: "slot-side", text: side === "LEFT" ? "変更前" : "変更後" }));
    }
    children.push(el("div", { class: "threads", "data-threads": key }));
    children.push(el("div", { class: "composer-slot", "data-composer": key }));
    return el("div", { class: "slots", "data-side": side }, children);
  }

  function renderRowSplit(file, left, right, expanded) {
    // 現在行は**1 行に 1 つ**。右（新側）を優先し、右が無ければ左を使う（decisions.md D2）。
    var anchor = anchorOf(right) || anchorOf(left);
    var key = anchor ? rowKey(file.path, anchor.side, anchor.number) : null;
    var row = el("div", {
      class: expanded ? "row split expanded" : "row split",
      "data-kind": (right && right.kind) || (left && left.kind) || "ctx",
      "data-key": key,
      tabindex: "-1"
    }, [
      splitCell(file, left, "LEFT", expanded),
      splitCell(file, right, "RIGHT", expanded)
    ]);
    row.addEventListener("focus", function () { setCurrentRow(row); });
    // 左右の両方が位置を持つとき（削除 ＋ 追加の組）だけ、どちら側かの見出しを添える。
    var both = !!(cellAnchor(left, "LEFT") && cellAnchor(right, "RIGHT"));
    var leftSlots = splitSlots(file, left, "LEFT", both);
    if (leftSlots) { row.appendChild(leftSlots); }
    var rightSlots = splitSlots(file, right, "RIGHT", both);
    if (rightSlots) { row.appendChild(rightSlots); }
    return row;
  }

  function toggleSplit() {
    UI.pref("split", splitMode() ? "off" : "on");
    var button = document.getElementById("btn-split");
    if (button) {
      button.setAttribute("aria-pressed", splitMode() ? "true" : "false");
      button.textContent = splitMode() ? "unified 表示" : "split 表示";
    }
    // **現在行を指し直す**（指さないと切り離されたノードが残り、キー操作が黙って効かなくなる）
    var currentKey = currentRow && currentRow.getAttribute ? currentRow.getAttribute("data-key") : null;
    renderFiles();
    renderThreads();
    var again = currentKey
      ? document.querySelector('.row[data-key="' + cssEscape(currentKey) + '"]')
      : null;
    setCurrentRow(again);
    if (again) { again.focus(); }
    else if (button) { button.focus(); }
  }

  // ------------------------------------------------------- コメントの描画

  function anchorKeyOf(thread) {
    if (thread.path === null || thread.path === undefined) { return "overall"; }
    if (thread.line === null || thread.line === undefined) { return fileKey(thread.path); }
    return rowKey(thread.path, thread.side, thread.line);
  }

  function renderThreads() {
    Array.prototype.forEach.call(document.querySelectorAll("[data-threads]"), clear);
    var orphans = [];
    state.threads.forEach(function (thread) {
      var slot = slotFor(thread);
      if (!slot) { orphans.push(thread); return; }
      slot.appendChild(renderThread(thread));
    });
    renderOrphans(orphans);
    renderCommentList();
    updatePendingCount();
  }

  function slotFor(thread) {
    // 行が描かれていない（折りたたみ中の大きいファイル）ときは、ファイル単位の置き場に落とす。
    // そこも無ければ「位置不明」。折りたたみを開くと renderThreads が呼ばれて行へ戻る。
    var key = anchorKeyOf(thread);
    var slot = document.querySelector('[data-threads="' + cssEscape(key) + '"]');
    if (slot) { return slot; }
    if (thread.path !== null && thread.path !== undefined) {
      return document.querySelector('[data-threads="' + cssEscape(fileKey(thread.path)) + '"]');
    }
    return null;
  }

  function cssEscape(value) {
    return String(value).replace(/["\\]/g, "\\$&");
  }

  function renderOrphans(threads) {
    var host = document.querySelector('[data-threads="overall"]');
    if (!threads.length || !host) { return; }
    var box = el("div", { class: "orphans" }, [
      el("p", { class: "hint", text: "位置不明（いまの差分に該当する行が見つからない指摘）" })
    ]);
    threads.forEach(function (thread) {
      box.appendChild(el("p", { class: "hint", text: locationLabel(thread) }));
      box.appendChild(renderThread(thread));
    });
    host.appendChild(box);
  }

  function locationLabel(thread) {
    if (thread.path === null || thread.path === undefined) { return "(全体)"; }
    if (thread.line === null || thread.line === undefined) { return thread.path; }
    return thread.path + ":" + thread.line + " (" + thread.side + ")";
  }

  function renderThread(thread) {
    var isNote = thread.kind === "note";
    var head = el("span", {
      class: thread.resolved ? "state-resolved" : "",
      text: locationLabel(thread) + (thread.resolved ? " ・ 解決済み" : "")
    });
    var actions = el("span", {});
    if (isNote) {
      // 説明は「解決する」ものではないので、解決ボタンを出さない（decisions.md D9）
      head.appendChild(document.createTextNode(" "));
      head.appendChild(el("span", { class: "badge badge-note", text: "説明" }));
    } else if (!readonly) {
      var resolveButton = el("button", {
        type: "button",
        text: thread.resolved ? "未解決に戻す" : "解決にする"
      });
      resolveButton.addEventListener("click", function () {
        thread.resolved = !thread.resolved;
        persist();
        renderThreads();
      });
      actions.appendChild(resolveButton);
    }

    var node = el("div", {
      class: isNote ? "thread thread-note" : "thread",
      "data-kind": thread.kind || "review",
      "data-thread": thread.id,
      tabindex: "-1",              // コメント一覧から飛んできたフォーカスの行き先（AC-I4）
      "data-resolved": thread.resolved ? "true" : "false"
    }, [el("div", { class: "thread-head" }, [head, actions])]);

    thread.comments.forEach(function (comment) {
      node.appendChild(renderComment(thread, comment));
    });
    return node;
  }

  function renderComment(thread, comment) {
    var who = el("div", { class: "who" }, [
      el("span", { text: comment.author || "unknown" })
    ]);
    if (comment.severity) {
      who.appendChild(document.createTextNode(" "));
      who.appendChild(el("span", { class: "badge sev-" + comment.severity, text: comment.severity }));
    }
    if (!comment.review_id && thread.kind !== "note") {
      who.appendChild(document.createTextNode(" "));
      who.appendChild(el("span", { class: "pending", text: "未提出" }));
    }
    var node = el("div", { class: "comment", "data-comment": comment.id },
                 [who, el("div", { class: "body", text: comment.body })]);

    if (readonly) { return node; }    // 参照専用では返信・取り消し・入力欄を作らない

    // **返信はコメント 1 件ごと**（返信への返信も同じ経路で、親はその返信になる）
    var replyKey = "reply:" + thread.id + ":" + comment.id;
    var replyButton = el("button", { type: "button", "aria-expanded": "false", text: "返信" });
    replyButton.addEventListener("click", function () {
      toggleComposer(replyKey, replyButton, null, thread, comment);
    });
    var buttons = [replyButton];
    if (!comment.review_id && thread.kind !== "note") {
      var cancel = el("button", { type: "button", text: "取り消し" });
      cancel.addEventListener("click", function () { cancelComment(thread, comment); });
      buttons.push(cancel);
    }
    node.appendChild(el("div", { class: "row-actions" }, buttons));
    node.appendChild(el("div", { class: "composer-slot", "data-composer": replyKey }));
    return node;
  }

  function cancelComment(thread, comment) {
    thread.comments = thread.comments.filter(function (item) { return item !== comment; });
    if (!thread.comments.length) {
      state.threads = state.threads.filter(function (item) { return item !== thread; });
    }
    persist();
    renderThreads();
  }

  // ------------------------------------------------------------ コメント一覧

  function clFilters() {
    return {
      unresolved: UI.pref("cl-unresolved") === "on",
      severity: UI.pref("cl-severity") || "",
      notes: UI.pref("cl-notes") !== "off"
    };
  }

  function threadSeverity(thread) {
    // スレッドの重大度＝最初のコメントのもの（返信で重大度は付けない）
    var first = thread.comments && thread.comments[0];
    return (first && first.severity) || null;
  }

  function clMatches(thread, filters) {
    var isNote = thread.kind === "note";
    if (isNote && !filters.notes) { return false; }
    if (filters.unresolved && (thread.resolved || isNote)) { return false; }
    if (filters.severity) {
      var sev = threadSeverity(thread);
      if (filters.severity === "none") { return sev === null; }
      if (sev !== filters.severity) { return false; }
    }
    return true;
  }

  function clSummary(thread) {
    var first = thread.comments && thread.comments[0];
    var body = (first && first.body) || "";
    body = body.replace(/\s+/g, " ").trim();
    return body.length > 80 ? body.slice(0, 80) + "…" : body;
  }

  function renderCommentList() {
    var host = document.getElementById("commentlist");
    if (!host) { return; }
    clear(host);
    var filters = clFilters();
    var all = state.threads.slice().sort(threadOrder);
    var shown = all.filter(function (thread) { return clMatches(thread, filters); });

    var count = document.getElementById("cl-count");
    if (count) {
      count.textContent = all.length
        ? "表示 " + shown.length + " 件 / 全 " + all.length + " 件"
        : "指摘はまだありません";
    }
    if (!shown.length) {
      host.appendChild(el("p", { class: "empty", text: all.length ? "この条件に合う指摘はありません" : "指摘はまだありません" }));
      return;
    }
    shown.forEach(function (thread) {
      host.appendChild(clItem(thread));
    });
  }

  function clItem(thread) {
    var isNote = thread.kind === "note";
    var sev = threadSeverity(thread);
    var tags = el("span", { class: "cl-tags" });
    if (sev) { tags.appendChild(el("span", { class: "badge sev-" + sev, text: sev })); }
    var stateClass = isNote ? "cl-state-note" : (thread.resolved ? "cl-state-resolved" : "cl-state-open");
    var stateText = isNote ? "説明" : (thread.resolved ? "解決済み" : "未解決");
    tags.appendChild(el("span", { class: stateClass, text: stateText }));
    if (thread.comments.length > 1) {
      tags.appendChild(el("span", { class: "cl-state-open", text: "返信 " + (thread.comments.length - 1) }));
    }

    var button = el("button", { type: "button", class: "cl-item" }, [
      el("span", { class: "cl-where", text: locationLabel(thread) }),
      tags,
      el("span", { class: "cl-body", text: clSummary(thread) })
    ]);
    button.addEventListener("click", function () { gotoThread(thread); });
    return button;
  }

  function gotoThread(thread) {
    // 1) 折りたたみ中のファイルにあるなら先に開く（開かないと行が存在しない）
    if (thread.path !== null && thread.path !== undefined) {
      var section = document.querySelector('.file[data-path="' + cssEscape(thread.path) + '"]');
      if (section && section.getAttribute("data-collapsed") === "true") {
        var file = (diffData.files || []).filter(function (f) { return f.path === thread.path; })[0];
        if (file) { toggleFile(section, file); }
      }
    }
    // 2) スレッドの DOM を探して、そこへスクロール ＋ **フォーカスを移す**（research.md F7）
    var node = document.querySelector('.thread[data-thread="' + cssEscape(thread.id) + '"]');
    if (!node) { return; }
    node.scrollIntoView({ block: "center" });
    node.focus();
    // 3) 行に紐づくなら現在行も更新する（j / k をそのまま続けられるように）
    var row = node.closest ? node.closest(".row") : null;
    if (row) { setCurrentRow(row); }
  }

  function wireCommentList() {
    var map = [
      ["cl-unresolved", "cl-unresolved", "checkbox"],
      ["cl-severity", "cl-severity", "select"],
      ["cl-notes", "cl-notes", "checkbox"]
    ];
    map.forEach(function (entry) {
      var node = document.getElementById(entry[0]);
      if (!node) { return; }
      if (entry[2] === "checkbox") {
        node.checked = UI.pref(entry[1]) === "on";
        node.addEventListener("change", function () {
          UI.pref(entry[1], node.checked ? "on" : "off");
          renderCommentList();
        });
      } else {
        node.value = UI.pref(entry[1]) || "";
        node.addEventListener("change", function () {
          UI.pref(entry[1], node.value);
          renderCommentList();
        });
      }
    });
  }

  // ------------------------------------------------------------- 入力欄

  function toggleComposer(key, trigger, location, thread, parent) {
    var slot = document.querySelector('[data-composer="' + cssEscape(key) + '"]');
    if (!slot) { return; }
    if (slot.firstChild) { closeComposer(key, trigger); return; }
    openComposer(key, trigger, location, thread, parent);
  }

  function draftOf(key) {
    var draft = drafts[key];
    if (typeof draft === "string") { return { body: draft, severity: "", note: false }; }  // 旧形式
    return draft || { body: "", severity: "", note: false };
  }

  function openComposer(key, trigger, location, thread, parent) {
    var slot = document.querySelector('[data-composer="' + cssEscape(key) + '"]');
    if (!slot || slot.firstChild) { return; }
    var draft = draftOf(key);
    var isReply = !!thread;
    var isNoteThread = isReply && thread.kind === "note";

    var area = el("textarea", { rows: "3", placeholder: "コメント（Ctrl/⌘ + Enter で確定）" });
    area.value = draft.body || "";

    // 重大度。説明（note）には付けないので、そのときは出さない。
    var severity = el("select", { class: "severity", "aria-label": "重大度" });
    [["", "重大度なし"], ["must", "must（直す）"], ["should", "should（直したい）"], ["nit", "nit（好み）"]]
      .forEach(function (pair) {
        var option = el("option", { value: pair[0], text: pair[1] });
        if (pair[0] === (draft.severity || "")) { option.setAttribute("selected", "selected"); }
        severity.appendChild(option);
      });
    severity.value = draft.severity || "";

    // 「説明として残す」= レビュー提出の対象外（kind: note）。新しいスレッドのときだけ選べる。
    var noteBox = el("input", { type: "checkbox", id: "note-" + cssEscape(key) });
    noteBox.checked = !!draft.note;
    var noteLabel = el("label", { class: "note-toggle" }, [
      noteBox, document.createTextNode(" 説明として残す（レビュー対象外）")
    ]);

    function save() {
      drafts[key] = { body: area.value, severity: severity.value, note: noteBox.checked };
      persist();
    }
    area.addEventListener("input", save);
    severity.addEventListener("change", save);
    noteBox.addEventListener("change", function () {
      save();
      severity.disabled = noteBox.checked;
    });
    severity.disabled = noteBox.checked || isNoteThread;

    area.addEventListener("keydown", function (event) {
      if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
        event.preventDefault();
        submitComposer();
      } else if (event.key === "Escape") {
        event.preventDefault();
        closeComposer(key, trigger);
      }
    });

    function submitComposer() {
      confirmComment(key, trigger, location, thread, parent, area.value,
                     severity.disabled ? "" : severity.value,
                     isReply ? (thread.kind === "note") : noteBox.checked);
    }

    var submit = el("button", { type: "button", text: isReply ? "返信する" : "コメントする" });
    submit.addEventListener("click", submitComposer);
    var close = el("button", { type: "button", text: "閉じる" });
    close.addEventListener("click", function () { closeComposer(key, trigger); });

    var controls = [severity];
    if (!isReply) { controls.push(noteLabel); }
    slot.appendChild(el("div", { class: "composer" }, [
      area,
      el("div", { class: "composer-controls" }, controls),
      el("div", { class: "row-actions" }, [submit, close])
    ]));
    if (trigger) { trigger.setAttribute("aria-expanded", "true"); }
    area.focus();
  }

  function closeComposer(key, trigger) {
    var slot = document.querySelector('[data-composer="' + cssEscape(key) + '"]');
    if (slot) { clear(slot); }
    if (trigger) {
      trigger.setAttribute("aria-expanded", "false");
      trigger.focus();
    }
  }

  function confirmComment(key, trigger, location, thread, parent, text, severity, asNote) {
    var body = (text || "").trim();
    if (!body) { return; }
    var sev = SEVERITIES.indexOf(severity) === -1 ? null : severity;
    if (thread) {
      thread.comments.push({
        id: nextId("c"),
        review_id: null,
        author: "human",
        body: body,
        severity: thread.kind === "note" ? null : sev,
        in_reply_to: parent ? parent.id : (thread.comments.length
          ? thread.comments[thread.comments.length - 1].id : null)
      });
    } else {
      state.threads.push({
        id: nextId("t"),
        _order: state.threads.length,
        kind: asNote ? "note" : "review",
        path: location.path,
        line: location.line,
        side: location.side,
        start_line: null,
        start_side: null,
        resolved: false,
        comments: [{
          id: nextId("c"),
          review_id: null,
          author: "human",
          body: body,
          severity: asNote ? null : sev,
          in_reply_to: null
        }]
      });
    }
    delete drafts[key];
    persist();
    closeComposer(key, trigger);
    renderThreads();
  }

  // --------------------------------------------------------------- 提出

  function pendingComments() {
    // 説明（note）は提出されないので数えない（decisions.md D9）
    var out = [];
    state.threads.forEach(function (thread) {
      if (thread.kind === "note") { return; }
      thread.comments.forEach(function (comment) {
        if (!comment.review_id) { out.push(comment); }
      });
    });
    return out;
  }

  var reviewStarted = false;

  function updatePendingCount() {
    var node = document.getElementById("pending-count");
    if (node) {
      node.textContent = "未提出のコメント: " + pendingComments().length + " 件"
        + (reviewStarted ? "（レビュー中）" : "");
    }
    var start = document.getElementById("btn-start-review");
    if (start) {
      var active = reviewStarted || pendingComments().length > 0;
      start.setAttribute("aria-pressed", active ? "true" : "false");
      start.textContent = active ? "レビュー中（提出する）" : "レビューを開始";
    }
  }

  function startReview() {
    reviewStarted = true;
    showPanel("submit-panel", true);
    updatePendingCount();
    var body = document.getElementById("review-body");
    if (body) { body.focus(); }
  }

  function submitReview() {
    var selected = document.querySelector('input[name="review-state"]:checked');
    var stateValue = selected ? selected.value : "COMMENTED";
    var body = document.getElementById("review-body").value.trim();
    var pending = pendingComments();
    if (!pending.length && !body) {
      banner("提出するコメントもサマリもありません。", []);
      return;
    }
    var review = { id: nextId("r"), author: "human", state: stateValue, body: body };
    state.reviews.push(review);
    pending.forEach(function (comment) { comment.review_id = review.id; });
    document.getElementById("review-body").value = "";
    reviewStarted = false;
    persist();
    renderThreads();
    banner("レビューを提出しました（" + stateValue + "）。JSON を書き出して渡してください。", []);
  }

  function discardPending() {
    state.threads.forEach(function (thread) {
      if (thread.kind === "note") { return; }   // 説明は提出の対象外なので破棄もしない
      thread.comments = thread.comments.filter(function (comment) { return !!comment.review_id; });
    });
    state.threads = state.threads.filter(function (thread) { return thread.comments.length; });
    persist();
    renderThreads();
  }

  // --------------------------------------------------- 書き出し / 読み込み

  function openExport() {
    var text = exportText();
    var area = document.getElementById("export-text");
    area.value = text;
    showPanel("export-panel", true);
    area.focus();
    area.select();
  }

  function download() {
    var text = exportText();
    var name = "review-" + String(target.base_commit || "nobase").slice(0, 7)
      + "-" + String(target.diff_digest || "nodiff").slice(0, 7) + ".json";
    var blob = new Blob([text], { type: "application/json" });
    var url = URL.createObjectURL(blob);
    var link = el("a", { href: url, download: name });
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
    dirty = false;
  }

  var BUNDLE_PREFIX = "window.__DIFF_REVIEW_BUNDLE__ = ";
  var BUNDLE_SUFFIX = ";\n";

  function parseBundleText(text) {
    // **実行しない**。前後の固定を確かめて剥がし、JSON として読むだけ（research.md F2）。
    // 末尾の空白は許す（エディタが改行を足すことがある）。生成側 parse_bundle と同じ寛容さ。
    var trimmed = text.replace(/\s+$/, "");
    if (trimmed.slice(0, BUNDLE_PREFIX.length) !== BUNDLE_PREFIX) { return null; }
    if (trimmed.charAt(trimmed.length - 1) !== ";") { return null; }
    return JSON.parse(trimmed.slice(BUNDLE_PREFIX.length, trimmed.length - 1));
  }

  function readFile(file) {
    var reader = new FileReader();
    reader.onload = function () {
      var text = String(reader.result);
      var trimmed = text.replace(/^\uFEFF/, "");
      if (trimmed.slice(0, BUNDLE_PREFIX.length) === BUNDLE_PREFIX) {
        var bundle;
        try {
          bundle = parseBundleText(trimmed);
        } catch (err) {
          banner("バンドルとして読めません（" + file.name + "）: " + err.message, [], "load");
          return;
        }
        adoptBundle(bundle, file.name);
        return;
      }
      var record;
      try {
        record = JSON.parse(trimmed);
      } catch (err) {
        banner("JSON としてもバンドルとしても読めません（" + file.name + "）: " + err.message, [], "load");
        return;
      }
      importRecord(record, file.name);
    };
    reader.onerror = function () { banner("ファイルを読めませんでした。", [], "load"); };
    reader.readAsText(file, "utf-8");
  }

  // ------------------------------------------------------------ パネル

  function showPanel(id, show) {
    var panel = document.getElementById(id);
    if (!panel) { return; }
    panel.hidden = !show;
    UI.syncTopbarHeight();   // .shell の高さは「画面 − トップバーとパネル」なので測り直す
  }

  // --------------------------------------------------------- キーボード

  function rows() {
    return Array.prototype.slice.call(document.querySelectorAll(".row"));
  }

  function setCurrentRow(row) {
    if (currentRow && currentRow !== row && currentRow.removeAttribute) {
      currentRow.removeAttribute("data-current");
    }
    currentRow = row || null;
    if (currentRow) { currentRow.setAttribute("data-current", "true"); }
  }

  function moveRow(step) {
    var all = rows();
    if (!all.length) { return; }
    var index = currentRow ? all.indexOf(currentRow) : -1;
    var next = all[Math.min(all.length - 1, Math.max(0, index + step))];
    if (index === -1) { next = all[0]; }
    setCurrentRow(next);
    next.focus();
    next.scrollIntoView({ block: "nearest" });
  }

  function focusPane(which) {
    var pane = document.getElementById("pane-" + which);
    if (!pane) { return; }
    UI.openPane(which);
    // そのペインで**いちばん使う操作**へ直に入る。入り口が入れ子だと、着いてから
    // もう何度も Tab を押すことになり、移動した意味が薄れる。
    // **順に**探す。セレクタをカンマで並べると「文書順で最初のもの」が返るので、
    // 望んだ優先順位にならない（絞り込みの入力がコメントの項目より前にあるため）。
    var wanted = which === "left"
      ? ['[role="treeitem"][tabindex="0"]', "#filelist a", "#btn-tree"]
      : [".cl-item", "#cl-unresolved"];
    var target = null;
    for (var i = 0; i < wanted.length && !target; i += 1) {
      target = pane.querySelector(wanted[i]);
    }
    if (!target) {
      pane.setAttribute("tabindex", "-1");
      target = pane;
    }
    target.scrollIntoView({ block: "nearest" });
    target.focus();
  }

  function currentSection() {
    // 現在行が生きていればそこから、そうでなければフォーカス位置から「いま見ているファイル」を引く。
    if (currentRow && currentRow.isConnected) { return currentRow.closest(".file"); }
    var active = document.activeElement;
    return active && active.closest ? active.closest(".file") : null;
  }

  function isTyping(event) {
    var node = event.target;
    if (!node || !node.tagName) { return false; }
    var tag = node.tagName.toLowerCase();
    return tag === "textarea" || tag === "input" || node.isContentEditable;
  }

  function onKeyDown(event) {
    // 入力欄の中では、閉じる（Esc）と確定（修飾キー + Enter）以外は画面側で処理しない。
    // ここを外すと、コメント本文に "c" や "f" を打った瞬間に画面が動く。
    if (isTyping(event)) { return; }
    if (event.ctrlKey || event.metaKey || event.altKey) { return; }
    // ツリーや境界が**もう処理したキー**をここで二重に扱わない。
    // これが無いと、ツリーの ↑ ↓ が同時に差分の行送りを起こす。
    if (event.defaultPrevented) { return; }

    var key = event.key;
    if (key === "j" || key === "ArrowDown") { event.preventDefault(); moveRow(1); return; }
    if (key === "k" || key === "ArrowUp") { event.preventDefault(); moveRow(-1); return; }
    if (readonly && (key === "c" || key === "Enter" || key === "r")) { return; }
    if (key === "c" || key === "Enter") {
      // Enter は**差分の行にフォーカスがあるときだけ**扱う。ページ全体で横取りすると、
      // ボタンを Enter で押せなくなる（ブラウザ標準の操作を奪う＝AC-I5 違反）。
      // c は行を選んでいれば効いてよいが、ボタン上では既定動作に譲る。
      // ガードを掛けるのは Enter だけ。c はボタンやリンクの標準操作ではないので、
      // 奪っているものが無い（ここまで塞ぐと、確定後にフォーカスがボタンへ戻った状態から
      // c で次のコメントを開けなくなり、キーボードだけの経路が切れる）。
      var onRow = event.target && event.target.classList && event.target.classList.contains("row");
      if (key === "Enter" && !onRow) { return; }
      if (currentRow) {
        event.preventDefault();
        var button = currentRow.querySelector(".comment-open");
        if (button) { button.click(); }
      }
      return;
    }
    if (key === "e" || key === "E") {
      var fileSection = currentSection();
      if (fileSection) {
        event.preventDefault();
        // e … 展開ボタンを 1 回 / Shift+E（= 大文字の E）… そのファイルを全部開く。
        // shiftKey だけを見ると、環境によって大文字 E が shiftKey なしで届いたときに
        // 「全部開く」が黙って効かなくなるので、キーが大文字であることも合図として使う。
        var wantAll = event.shiftKey || key === "E";
        var selector = wantAll ? ".expand-all" : ".expand-down, .expand-up";
        var target = fileSection.querySelector(selector);
        if (target) { target.click(); }
      }
      return;
    }
    if (key === "s") {
      event.preventDefault();
      toggleSplit();
      return;
    }
    // [ / ] は**そのペインへ移動**。畳む・戻すは Shift 併用（{ / }）とトップバーのボタン、境界の Enter。
    // 移動を優先するのは、畳む操作には他に 2 つ経路があるのに対し、
    // 差分の奥からコメント一覧へ**移る**手段が Tab しか無く、行の数だけ Tab を押す羽目になるため
    // （実測: Tab 60 回でも届かない）。
    if (key === "[") { event.preventDefault(); focusPane("left"); return; }
    if (key === "]") { event.preventDefault(); focusPane("right"); return; }
    if (key === "{") { event.preventDefault(); UI.togglePane("left"); return; }
    if (key === "}") { event.preventDefault(); UI.togglePane("right"); return; }
    if (key === "t") {
      var richSection = currentSection();
      var viewButton = richSection && richSection.querySelector(".view-toggle");
      if (viewButton) {
        event.preventDefault();
        viewButton.click();
      }
      return;
    }
    if (key === "f") {
      var section = currentSection();
      if (section) {
        event.preventDefault();
        section.querySelector(".file-toggle").click();
      }
      return;
    }
    if (key === "r") {
      event.preventDefault();
      showPanel("submit-panel", document.getElementById("submit-panel").hidden);
      if (!document.getElementById("submit-panel").hidden) {
        updatePendingCount();
        document.getElementById("review-body").focus();
      }
      return;
    }
    if (key === "?") {
      event.preventDefault();
      var help = document.getElementById("help");
      showPanel("help", help.hidden);
      document.getElementById("btn-help-open").setAttribute("aria-expanded", help.hidden ? "false" : "true");
      return;
    }
    if (key === "Escape") {
      showPanel("submit-panel", false);
      showPanel("export-panel", false);
      showPanel("help", false);
    }
  }

  // ------------------------------------------------------------- 起動

  function renderAll() {
    renderMeta();
    showOpenPrompt(!(diffData.files || []).length);
    renderFileList();
    renderFiles();
    renderThreads();
    UI.syncTopbarHeight();
  }

  function wire() {
    // 書き込みの導線は、参照専用では**そもそも HTML に無い**（生成時に切り落としてある）。
    // だから「あれば繋ぐ」形で書く。存在を前提にすると、参照専用で起動時に例外が出て
    // 読む機能まで巻き添えで死ぬ。
    var submitOpen = document.getElementById("btn-submit-open");
    if (submitOpen) {
      submitOpen.addEventListener("click", function () {
        var panel = document.getElementById("submit-panel");
        showPanel("submit-panel", panel.hidden);
        updatePendingCount();
      });
      document.getElementById("btn-submit-do").addEventListener("click", submitReview);
      document.getElementById("btn-submit-discard").addEventListener("click", discardPending);
      document.getElementById("btn-submit-close").addEventListener("click", function () {
        showPanel("submit-panel", false);
      });
    }
    var startButton = document.getElementById("btn-start-review");
    if (startButton) {
      startButton.addEventListener("click", function () {
        if (document.getElementById("submit-panel").hidden) { startReview(); }
        else { showPanel("submit-panel", false); }
      });
    }
    var exportOpen = document.getElementById("btn-export-open");
    if (exportOpen) {
      exportOpen.addEventListener("click", openExport);
      document.getElementById("btn-export-close").addEventListener("click", function () {
        showPanel("export-panel", false);
      });
      document.getElementById("btn-download").addEventListener("click", download);
    }
    document.getElementById("btn-help-open").addEventListener("click", function () {
      var help = document.getElementById("help");
      showPanel("help", help.hidden);
      this.setAttribute("aria-expanded", help.hidden ? "false" : "true");
    });
    // `<label for>` はキーボードで到達できない（`Tab` が止まらない）。**ボタンにして繋ぐ**。
    var openButton = document.getElementById("btn-open-file");
    if (openButton) {
      openButton.addEventListener("click", function () { document.getElementById("file-import").click(); });
    }
    document.getElementById("file-import").addEventListener("change", function (event) {
      if (event.target.files && event.target.files[0]) { readFile(event.target.files[0]); }
      event.target.value = "";
    });
    var splitButton = document.getElementById("btn-split");
    if (splitButton) {
      splitButton.setAttribute("aria-pressed", splitMode() ? "true" : "false");
      splitButton.textContent = splitMode() ? "unified 表示" : "split 表示";
      splitButton.addEventListener("click", toggleSplit);
    }
    var treeButton = document.getElementById("btn-tree");
    if (treeButton) {
      treeButton.addEventListener("click", function () {
        UI.pref("filetree", treeMode() ? "off" : "on");
        renderFileList();
        treeButton.focus();
      });
    }
    // ツリーのキー操作は**ここで 1 回だけ**張る（描き直しのたびに張ると重なる）
    var filelist = document.getElementById("filelist");
    if (filelist) { filelist.addEventListener("keydown", onTreeKeyDown); }
    wireCommentList();

    var overallButton = document.querySelector('#overall .comment-open');
    if (overallButton) {
      overallButton.addEventListener("click", function () {
        toggleComposer("overall", overallButton, { path: null, line: null, side: null });
      });
    }

    // 冒頭の「差分へ移動」も**フォーカスを運ぶ**。リンクだけではスクロールするだけで、
    // キーボードの現在位置がページ先頭に残る（research.md F7 と同じ落とし穴）。
    var skip = document.querySelector("a.skip");
    if (skip) {
      skip.addEventListener("click", function (event) {
        event.preventDefault();
        var files = document.getElementById("files");
        var first = files.querySelector(".row[data-key]") || files;
        first.setAttribute("tabindex", "-1");
        first.scrollIntoView({ block: "start" });
        first.focus();
      });
    }

    // ホスト（エディタ拡張・親フレーム）からの差し替え。**実行を伴わない**——
    // 受け取るのは構造化されたデータで、文字列を評価する経路はここに無い。
    // 埋め込みだけだと、ホストは中身を変えるたびに HTML を組み立て直す（＝再読み込み）ことになり、
    // スクロール位置と現在行が失われる。その一点のためにこの口を持つ。
    //
    // file:// では origin が opaque で送り主を検査できないので、**形で検査する**（research.md R2）。
    // 関係の無いメッセージは黙って無視する（ホストは自分の用事でも postMessage を使う）。
    window.addEventListener("message", function (event) {
      var data = event.data;
      if (!data || typeof data !== "object") { return; }
      var bundle = data.schema === BUNDLE_SCHEMA ? data
        : (data.type === "diff-review/bundle" ? data.bundle : null);
      if (!bundle) { return; }
      adoptBundle(bundle, "ホスト");
    });

    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("dragover", function (event) { event.preventDefault(); });
    document.addEventListener("drop", function (event) {
      event.preventDefault();
      if (event.dataTransfer && event.dataTransfer.files && event.dataTransfer.files[0]) {
        readFile(event.dataTransfer.files[0]);
      }
    });
    window.addEventListener("beforeunload", function (event) {
      if (!dirty) { return undefined; }
      event.preventDefault();
      event.returnValue = "";
      return "";
    });
  }

  function initialSource(embedded, embeddedBundle) {
    // **起動時**の取り込み口（decisions.md D10 / D11）:
    //   埋め込み  … #bundle-data（バンドルをそのまま） / #diff-data（html サブコマンドの出力）
    // どちらも無ければ「ファイルを開いてください」を出す（白い画面にしない）。
    //
    // **起動後**は、人がファイルを選ぶか、ホストが postMessage で渡すかのどちらか。
    // **外部ファイルを読む口は持たない**——`<script src>` は file:// で唯一動く手段だが、
    // どのバンドルを読むのかがファイル名任せになり、そのファイルを実行することにもなる。
    if (embeddedBundle) { return { kind: "bundle", data: embeddedBundle }; }
    if (embedded) { return { kind: "embedded", data: embedded }; }
    return { kind: "none", data: null };
  }

  function showOpenPrompt(show) {
    var prompt = document.getElementById("open-prompt");
    if (prompt) { prompt.hidden = !show; }
  }

  function boot() {
    // 埋め込みの JSON は**1 回だけ**読む。2 回 parse すると、大きな差分（実測 1.9MB で 1 回 6.4ms）で
    // 起動が二重に待たされる。
    var embedded = readEmbedded("diff-data");
    // ホスト（VSCode 拡張など）が流し込む HTML にバンドルを**そのまま**書き込む口。
    // 中身が空なら無視されるので、生成物は常に空で出す（決定論を壊さない）。
    var embeddedBundle = readEmbedded("bundle-data");
    var initial = initialSource(embedded, embeddedBundle);
    var embeddedReview = readEmbedded("review-data");
    // 参照専用かどうかは**ビューアの性質**なので、常に埋め込みの設定から取る
    // （開いたバンドルによって読み書きできたりできなかったりしては混乱する）。
    var viewerReadonly = !!(embedded || {}).readonly;

    if (initial.kind === "bundle") {
      var problems = validateBundle(initial.data);
      if (problems.length) {
        applyDiffData({ target: {}, files: [], rich_enabled: false, readonly: viewerReadonly }, null);
        banner("埋め込まれたバンドルが壊れています: " + problems.join(" / "), []);
      } else {
        applyDiffData({
          target: initial.data.target,
          files: initial.data.files,
          rich_enabled: !!initial.data.rich_enabled,
          readonly: viewerReadonly
        }, "埋め込み（バンドル）");
        if (initial.data.review) { embeddedReview = initial.data.review; }
      }
    } else if (initial.kind === "embedded") {
      applyDiffData(initial.data, "埋め込み");
    } else {
      applyDiffData({ target: {}, files: [], rich_enabled: false, readonly: viewerReadonly }, null);
    }

    var saved = restore();
    if (!storageOk) {
      banner("このブラウザでは下書きを保存できません（file:// の制限）。書き出し・読み込みは使えます。", []);
    }
    if (saved && saved.state) {
      adoptRecord(saved.state, null);
      drafts = saved.drafts || {};
      banner("このブラウザに保存されていた下書きを復元しました。", [
        {
          label: "下書きを破棄してやり直す",
          onClick: function () {
            dropSaved();
            drafts = {};
            if (embeddedReview) { adoptRecord(embeddedReview, null); } else { state = { reviews: [], threads: [] }; }
            renderAll();
          }
        }
      ]);
    } else if (embeddedReview) {
      adoptRecord(embeddedReview, null);
      checkIdentity(embeddedReview).forEach(function (note) { banner(note, []); });
    }
    UI.init();
    wire();
    renderAll();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
