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

  var SCHEMA = "diff-review/1";
  var STORAGE_KEY_PREFIX = "diff-review-html/v1/";
  var LAZY_LINE_LIMIT = 2000;
  var REVIEW_STATES = ["APPROVED", "CHANGES_REQUESTED", "COMMENTED"];
  var SIDES = ["LEFT", "RIGHT"];

  var diffData = readEmbedded("diff-data");
  var embeddedReview = readEmbedded("review-data");
  var target = diffData.target || {};
  var storageKey = STORAGE_KEY_PREFIX + (target.diff_digest || "unknown");

  var state = { reviews: [], threads: [] };
  var drafts = {};
  var seq = 0;
  var dirty = false;
  var storageOk = true;
  var currentRow = null;

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

  function banner(message, buttons) {
    var box = el("div", { class: "banner" }, [el("div", { text: message })]);
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
    if (record.schema !== SCHEMA) {
      problems.push("スキーマが " + SCHEMA + " ではありません（" + String(record.schema) + "）");
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
      banner("読み込めませんでした（" + source + "）: " + problems.join(" / "), []);
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
    document.getElementById("meta").textContent = parts.join(" ・ ");
  }

  function renderFileList() {
    var nav = document.getElementById("filelist");
    clear(nav);
    if (!(diffData.files || []).length) {
      nav.appendChild(el("p", { class: "empty", text: "変更ファイルなし" }));
      return;
    }
    (diffData.files || []).forEach(function (file, index) {
      var link = el("a", { href: "#file-" + index }, [
        el("span", { text: file.path }),
        el("span", {}, [
          el("span", { class: "stat-add", text: "+" + file.additions }),
          document.createTextNode(" "),
          el("span", { class: "stat-del", text: "-" + file.deletions })
        ])
      ]);
      nav.appendChild(link);
    });
  }

  function lineCount(file) {
    return (file.hunks || []).reduce(function (sum, hunk) { return sum + hunk.lines.length; }, 0);
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
      var big = lineCount(file) > LAZY_LINE_LIMIT;
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
      if (big) { tags.push(lineCount(file) + " 行・既定で折りたたみ"); }
      tags.push("+" + file.additions + " -" + file.deletions);

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

      section.appendChild(el("div", { class: "file-head" }, [
        el("div", { class: "path" }, [toggle]),
        el("div", { class: "tags", text: tags.join(" ・ ") }),
        commentButton
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
    var collapsed = section.getAttribute("data-collapsed") === "true";
    var body = section.querySelector(".file-body");
    if (collapsed && !body.childNodes.length) { fillFileBody(body, file); }
    section.setAttribute("data-collapsed", collapsed ? "false" : "true");
    section.querySelector(".file-toggle").setAttribute("aria-expanded", collapsed ? "true" : "false");
    renderThreads();
  }

  function fillFileBody(body, file) {
    if (file.binary) {
      body.appendChild(el("p", { class: "empty", text: "バイナリのため差分は表示しません（ファイル単位のコメントは付けられます）" }));
      return;
    }
    if (!file.hunks || !file.hunks.length) {
      body.appendChild(el("p", { class: "empty", text: "表示できる差分の本文がありません" }));
      return;
    }
    file.hunks.forEach(function (hunk) {
      body.appendChild(el("div", { class: "hunk-head", text: hunk.header }));
      hunk.lines.forEach(function (line) {
        body.appendChild(renderRow(file, line));
      });
    });
  }

  function renderRow(file, line) {
    var side = line.kind === "del" ? "LEFT" : "RIGHT";
    var number = line.kind === "del" ? line.old : line.new;
    var key = rowKey(file.path, side, number);
    var mark = line.kind === "add" ? "+" : (line.kind === "del" ? "-" : " ");

    var button = el("button", {
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

    var row = el("div", {
      class: "row",
      "data-kind": line.kind,
      "data-key": key,
      tabindex: "-1"
    }, [
      el("div", { class: "line" }, [
        el("span", { class: "gutter", text: line.old === null ? "" : String(line.old) }),
        el("span", { class: "gutter", text: line.new === null ? "" : String(line.new) }),
        button,
        el("span", { class: "mark", text: mark }),
        el("span", { class: "code", text: line.text })
      ])
    ]);
    row.addEventListener("focus", function () { setCurrentRow(row); });
    row.appendChild(el("div", { class: "threads", "data-threads": key }));
    row.appendChild(el("div", { class: "composer-slot", "data-composer": key }));
    return row;
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
    var resolveButton = el("button", {
      type: "button",
      text: thread.resolved ? "未解決に戻す" : "解決にする"
    });
    resolveButton.addEventListener("click", function () {
      thread.resolved = !thread.resolved;
      persist();
      renderThreads();
    });

    var replyButton = el("button", { type: "button", "aria-expanded": "false", text: "返信" });
    replyButton.addEventListener("click", function () {
      toggleComposer("reply:" + thread.id, replyButton, null, thread);
    });

    var node = el("div", { class: "thread", "data-resolved": thread.resolved ? "true" : "false" }, [
      el("div", { class: "thread-head" }, [
        el("span", {
          class: thread.resolved ? "state-resolved" : "",
          text: locationLabel(thread) + (thread.resolved ? " ・ 解決済み" : "")
        }),
        el("span", {}, [resolveButton, replyButton])
      ])
    ]);

    thread.comments.forEach(function (comment) {
      node.appendChild(renderComment(thread, comment));
    });
    node.appendChild(el("div", { class: "composer-slot", "data-composer": "reply:" + thread.id }));
    return node;
  }

  function renderComment(thread, comment) {
    var who = el("div", { class: "who" }, [
      el("span", { text: comment.author || "unknown" })
    ]);
    if (!comment.review_id) {
      who.appendChild(document.createTextNode(" "));
      who.appendChild(el("span", { class: "pending", text: "未提出" }));
    }
    var node = el("div", { class: "comment" }, [who, el("div", { class: "body", text: comment.body })]);
    if (!comment.review_id) {
      var cancel = el("button", { type: "button", text: "取り消し" });
      cancel.addEventListener("click", function () { cancelComment(thread, comment); });
      node.appendChild(el("div", { class: "row-actions" }, [cancel]));
    }
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

  // ------------------------------------------------------------- 入力欄

  function toggleComposer(key, trigger, location, thread) {
    var slot = document.querySelector('[data-composer="' + cssEscape(key) + '"]');
    if (!slot) { return; }
    if (slot.firstChild) { closeComposer(key, trigger); return; }
    openComposer(key, trigger, location, thread);
  }

  function openComposer(key, trigger, location, thread) {
    var slot = document.querySelector('[data-composer="' + cssEscape(key) + '"]');
    if (!slot || slot.firstChild) { return; }
    var area = el("textarea", { rows: "3", placeholder: "コメント（Ctrl/⌘ + Enter で確定）" });
    area.value = drafts[key] || "";
    area.addEventListener("input", function () {
      drafts[key] = area.value;
      persist();
    });
    area.addEventListener("keydown", function (event) {
      if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
        event.preventDefault();
        confirmComment(key, trigger, location, thread, area.value);
      } else if (event.key === "Escape") {
        event.preventDefault();
        closeComposer(key, trigger);
      }
    });

    var submit = el("button", { type: "button", text: "コメントする" });
    submit.addEventListener("click", function () {
      confirmComment(key, trigger, location, thread, area.value);
    });
    var close = el("button", { type: "button", text: "閉じる" });
    close.addEventListener("click", function () { closeComposer(key, trigger); });

    slot.appendChild(el("div", { class: "composer" }, [
      area,
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

  function confirmComment(key, trigger, location, thread, text) {
    var body = (text || "").trim();
    if (!body) { return; }
    if (thread) {
      var parent = thread.comments.length ? thread.comments[thread.comments.length - 1].id : null;
      thread.comments.push({
        id: nextId("c"),
        review_id: null,
        author: "human",
        body: body,
        in_reply_to: parent
      });
    } else {
      state.threads.push({
        id: nextId("t"),
        _order: state.threads.length,
        path: location.path,
        line: location.line,
        side: location.side,
        start_line: null,
        start_side: null,
        resolved: false,
        comments: [{ id: nextId("c"), review_id: null, author: "human", body: body, in_reply_to: null }]
      });
    }
    delete drafts[key];
    persist();
    closeComposer(key, trigger);
    renderThreads();
  }

  // --------------------------------------------------------------- 提出

  function pendingComments() {
    var out = [];
    state.threads.forEach(function (thread) {
      thread.comments.forEach(function (comment) {
        if (!comment.review_id) { out.push(comment); }
      });
    });
    return out;
  }

  function updatePendingCount() {
    var node = document.getElementById("pending-count");
    if (node) { node.textContent = "未提出のコメント: " + pendingComments().length + " 件"; }
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
    persist();
    renderThreads();
    banner("レビューを提出しました（" + stateValue + "）。JSON を書き出して渡してください。", []);
  }

  function discardPending() {
    state.threads.forEach(function (thread) {
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

  function readFile(file) {
    var reader = new FileReader();
    reader.onload = function () {
      var record;
      try {
        record = JSON.parse(String(reader.result));
      } catch (err) {
        banner("JSON として読めません: " + err.message, []);
        return;
      }
      importRecord(record, file.name);
    };
    reader.onerror = function () { banner("ファイルを読めませんでした。", []); };
    reader.readAsText(file, "utf-8");
  }

  // ------------------------------------------------------------ パネル

  function showPanel(id, show) {
    var panel = document.getElementById(id);
    if (!panel) { return; }
    panel.hidden = !show;
  }

  // --------------------------------------------------------- キーボード

  function rows() {
    return Array.prototype.slice.call(document.querySelectorAll(".row"));
  }

  function setCurrentRow(row) {
    if (currentRow && currentRow !== row) { currentRow.removeAttribute("data-current"); }
    currentRow = row;
    if (row) { row.setAttribute("data-current", "true"); }
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

    var key = event.key;
    if (key === "j" || key === "ArrowDown") { event.preventDefault(); moveRow(1); return; }
    if (key === "k" || key === "ArrowUp") { event.preventDefault(); moveRow(-1); return; }
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
    if (key === "f") {
      if (currentRow) {
        var section = currentRow.closest(".file");
        if (section) {
          event.preventDefault();
          section.querySelector(".file-toggle").click();
        }
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
    renderFileList();
    renderFiles();
    renderThreads();
  }

  function wire() {
    document.getElementById("btn-submit-open").addEventListener("click", function () {
      var panel = document.getElementById("submit-panel");
      showPanel("submit-panel", panel.hidden);
      updatePendingCount();
    });
    document.getElementById("btn-submit-do").addEventListener("click", submitReview);
    document.getElementById("btn-submit-discard").addEventListener("click", discardPending);
    document.getElementById("btn-submit-close").addEventListener("click", function () {
      showPanel("submit-panel", false);
    });
    document.getElementById("btn-export-open").addEventListener("click", openExport);
    document.getElementById("btn-export-close").addEventListener("click", function () {
      showPanel("export-panel", false);
    });
    document.getElementById("btn-download").addEventListener("click", download);
    document.getElementById("btn-help-open").addEventListener("click", function () {
      var help = document.getElementById("help");
      showPanel("help", help.hidden);
      this.setAttribute("aria-expanded", help.hidden ? "false" : "true");
    });
    document.getElementById("file-import").addEventListener("change", function (event) {
      if (event.target.files && event.target.files[0]) { readFile(event.target.files[0]); }
      event.target.value = "";
    });
    var overallButton = document.querySelector('#overall .comment-open');
    overallButton.addEventListener("click", function () {
      toggleComposer("overall", overallButton, { path: null, line: null, side: null });
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

  function boot() {
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
    wire();
    renderAll();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
