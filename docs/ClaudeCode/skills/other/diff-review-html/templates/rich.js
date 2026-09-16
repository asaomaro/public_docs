/* rich diff の描画。**rich の対象が 1 件も無い差分では、このファイルは埋め込まれない**
 * （生成側が `__RICH_JS__` を空にする。decisions.md D4）。
 *
 * ここには解析器が無い。Markdown も mermaid も PDF も CSV も、解析は生成時に済んでいて、
 * 渡ってくるのは「描けるだけの構造」だけ。だからこのファイルは小さいままでいられる。
 *
 * 守っている約束:
 *  - `innerHTML` を使わない（ノード木は createElement ＋ textContent で組み立てる）。
 *  - タグと属性は白名簿。`href` はスキームを検査し、`src` は data:image/svg+xml だけ許す。
 *  - HTML の描画は `<iframe sandbox="" srcdoc>`（スクリプトを実行させない）。
 */
window.DiffReviewRich = (function () {
  "use strict";

  var TAGS = {
    p: 1, h2: 1, h3: 1, h4: 1, h5: 1, h6: 1, ul: 1, ol: 1, li: 1, pre: 1, code: 1,
    blockquote: 1, div: 1, span: 1, strong: 1, em: 1, a: 1, hr: 1, table: 1, thead: 1,
    tbody: 1, tr: 1, th: 1, td: 1, figure: 1, img: 1
  };
  var ATTRS = { "class": 1, href: 1, src: 1, alt: 1, colspan: 1 };
  var SAFE_HREF = /^(?:https?:|mailto:|#|[^:]*$)/;
  var SAFE_SRC = /^data:image\/svg\+xml;base64,/;

  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (k) {
        if (attrs[k] === null || attrs[k] === undefined) { return; }
        if (k === "text") { node.textContent = String(attrs[k]); return; }
        node.setAttribute(k, String(attrs[k]));
      });
    }
    (children || []).forEach(function (c) { if (c) { node.appendChild(c); } });
    return node;
  }

  /** ノード木 → DOM。未知のタグ・属性は落として、中身はテキストとして残す。 */
  function buildNode(spec) {
    if (typeof spec === "string") { return document.createTextNode(spec); }
    if (!Array.isArray(spec) || !spec.length) { return document.createTextNode(""); }
    var tag = String(spec[0]).toLowerCase();
    var attrs = spec[1] || {};
    var children = spec[2] || [];
    if (!TAGS[tag]) {
      var fallback = document.createElement("p");
      children.forEach(function (c) { fallback.appendChild(buildNode(c)); });
      return fallback;
    }
    var node = document.createElement(tag);
    Object.keys(attrs).forEach(function (name) {
      if (!ATTRS[name]) { return; }
      var value = String(attrs[name]);
      if (name === "href" && !SAFE_HREF.test(value)) { return; }
      if (name === "src" && !SAFE_SRC.test(value)) { return; }
      node.setAttribute(name, value);
    });
    if (tag === "a") { node.setAttribute("rel", "noopener noreferrer"); }
    children.forEach(function (child) { node.appendChild(buildNode(child)); });
    return node;
  }

  function renderDoc(payload) {
    var box = el("div", { "class": "rich-panes" });
    [["変更前", payload.before], ["変更後", payload.after]].forEach(function (pair) {
      var pane = el("div", { "class": "rich-pane" }, [el("h4", { text: pair[0] })]);
      if (!pair[1]) {
        pane.appendChild(el("p", { "class": "empty", text: "（この側にはファイルがありません）" }));
      } else {
        pair[1].forEach(function (node) { pane.appendChild(buildNode(node)); });
      }
      box.appendChild(pane);
    });
    return box;
  }

  function renderTable(payload) {
    var head = el("tr", {}, (payload.header || []).map(function (h) {
      return el("th", { text: h });
    }));
    var rows = (payload.rows || []).map(function (row) {
      var tr = el("tr", { "class": "rich-row-" + row.kind });
      (row.cells || []).forEach(function (cell) {
        var td = el("td", { "class": cell.changed ? "changed" : "", text: cell.text });
        if (cell.changed && cell.before !== undefined && cell.before !== cell.text) {
          td.appendChild(el("span", { "class": "cell-before", text: " ← " + cell.before }));
        }
        tr.appendChild(td);
      });
      return tr;
    });
    return el("table", { "class": "rich-table" }, [
      el("thead", {}, [head]),
      el("tbody", {}, rows)
    ]);
  }

  function renderHtml(payload) {
    var box = el("div", { "class": "rich-panes" });
    [["変更前", payload.before], ["変更後", payload.after]].forEach(function (pair) {
      var pane = el("div", { "class": "rich-pane" }, [el("h4", { text: pair[0] })]);
      if (pair[1] === null || pair[1] === undefined) {
        pane.appendChild(el("p", { "class": "empty", text: "（この側にはファイルがありません）" }));
      } else {
        // sandbox="" ＝ スクリプトもフォームも同一オリジンも全部禁止。ここを緩めない。
        var frame = el("iframe", { sandbox: "", "class": "rich-frame", title: pair[0] + "の描画" });
        frame.setAttribute("srcdoc", pair[1]);
        pane.appendChild(frame);
      }
      box.appendChild(pane);
    });
    return box;
  }

  function renderPdf(payload) {
    var box = el("div", { "class": "rich-pdf" });
    var pages = payload.pages || {};
    var bytes = payload.bytes || {};
    box.appendChild(el("p", { "class": "hint", text:
      "ページ数 " + (pages.before || 0) + " → " + (pages.after || 0)
      + "／サイズ " + Math.round((bytes.before || 0) / 1024) + "KB → "
      + Math.round((bytes.after || 0) / 1024) + "KB" }));
    if (!payload.text || !payload.text.length) {
      box.appendChild(el("p", { "class": "empty", text: "テキストの差分はありません" }));
      return box;
    }
    var list = el("div", { "class": "rich-pdf-text" });
    payload.text.forEach(function (row) {
      list.appendChild(el("div", { "class": "pdf-line pdf-" + row.kind, text: row.text }));
    });
    box.appendChild(list);
    return box;
  }

  /** 1 ファイル分の rich を描いて返す。描けない種別は null。 */
  function render(rich) {
    if (!rich) { return null; }
    var body = null;
    if (rich.kind === "doc") { body = renderDoc(rich.payload || {}); }
    else if (rich.kind === "table") { body = renderTable(rich.payload || {}); }
    else if (rich.kind === "html") { body = renderHtml(rich.payload || {}); }
    else if (rich.kind === "pdf") { body = renderPdf(rich.payload || {}); }
    if (!body) { return null; }
    var box = el("div", { "class": "rich" });
    if (rich.note) { box.appendChild(el("p", { "class": "hint", text: rich.note })); }
    box.appendChild(body);
    return box;
  }

  return { render: render };
})();
