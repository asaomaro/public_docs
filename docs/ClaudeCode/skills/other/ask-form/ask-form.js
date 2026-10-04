/* <ask-form> — 質問のフォームの部品（カスタム要素・依存なし・Shadow DOM）。
 *
 * ask-form の単独ウィンドウ（form.html が殻）と、ほかの画面（Sodashitsu の sodactl ask のダイアログ）が、同じこのファイルを使う。
 * 部品は「定義を描く・回答を集める・質問の目次を出す」だけを行い、通信・ウィンドウの操作・閉じることは置いた側（殻・枠）が行う。
 *
 * 受け渡し
 *   el.spec = 検査済みの定義（fixtures/normalize.json の「正規化後」の形）。入れ替えると描き直す
 *   el.busy = true の間は、決定・キャンセルを押せない（送信中）
 *   el.resolveMedia = (ref, "image" | "audio") => 出してよい URL か null。無ければ画像・音のプレビューを出さない
 *   el.submit() / el.step(±1)（次・前の質問へ） / el.relayout() / el.notify(文, 警告か) / el.value / el.contentHeight / el.indexWidth（目次の幅。出ていなければ 0）
 *     el.pageCount は互換のために残す（いつも 1。ページには分けない）
 *   イベント（bubbles・composed）: ask-submit {answers, custom?, edited?, comments?, note?} / ask-cancel / ask-unsupported {reason}
 *     未回答があるときは ask-submit を出さず、その質問を示す。Esc では ask-cancel を出さない（取り消しは置いた側）
 *   配色: --ask-bg --ask-fg --ask-border --ask-accent --ask-accent-fg --ask-error --ask-warn（任意で --ask-card --ask-muted --ask-accent-soft）
 *   印: data-ask-title -question -note -status -submit -cancel -index（目次の項目。値は質問の id、補足は空）
 *
 * 決まり（置いた側の安全のため）
 *   定義の文字は textContent で出す（innerHTML を使わない）。色・数は確かめてから個別のプロパティに入れる。
 *   通信しない。window・document に触らない（リスナーは Shadow DOM の中・部品の要素・自分に付けた ResizeObserver だけで、外すときに外す）。
 */
const VERSION = '1.3.0';
const TYPES = ['single', 'multi', 'text', 'edit', 'rank', 'table'];
const FIELDS = ['title', 'intro', 'submit', 'note', 'notePlaceholder', 'paging', 'comments', 'comment',
  'id', 'label', 'type', 'help', 'page', 'options', 'default', 'allowOther', 'otherLabel', 'otherPlaceholder', 'showIf', 'required',
  'multiline', 'placeholder', 'minWidth', 'preview', 'thumb', 'filter', 'showValue', 'text', 'rows', 'mono', 'rowLabel', 'pickLabel',
  'value', 'desc', 'recommended', 'colors', 'group', 'image', 'audio', 'code', 'lang'];
const TEXT_MAX = 10000;   // 自由入力・補足の文字数の上限

const STYLE = `
:host{display:flex;flex-direction:column;min-height:0;box-sizing:border-box;font:inherit;line-height:1.6;
  --_bg:var(--ask-bg,#f6f7f9);--_fg:var(--ask-fg,#1c2330);--_line:var(--ask-border,#dfe3ea);
  --_accent:var(--ask-accent,#2f5fe0);--_on:var(--ask-accent-fg,#fff);--_err:var(--ask-error,#b4540a);--_warn:var(--ask-warn,#b4540a);
  --_card:var(--ask-card,color-mix(in srgb,var(--_bg) 93%,var(--_fg)));
  --_muted:var(--ask-muted,color-mix(in srgb,var(--_fg) 62%,var(--_bg)));
  --_soft:var(--ask-accent-soft,color-mix(in srgb,var(--_accent) 14%,var(--_bg)));
  background:var(--_bg);color:var(--_fg)}
:host([hidden]){display:none}
:host(:focus){outline:none}
*{box-sizing:border-box}
[hidden]{display:none !important}
.body{flex:1 1 auto;min-width:0;min-height:0;overflow-y:auto;overscroll-behavior:contain}
.main{flex:1 1 auto;min-height:0;display:flex}
.inner{padding:20px 22px 12px}
h1{font-size:18px;margin:0 0 2px;outline:none;overflow-wrap:anywhere}
.intro{color:var(--_muted);margin:0 0 14px;white-space:pre-wrap;overflow-wrap:anywhere}
.recall{display:flex;gap:10px;align-items:center;margin:-6px 0 12px;font-size:13px;color:var(--_muted)}
fieldset{border:1px solid var(--_line);background:var(--_card);border-radius:12px;
  margin:0 0 12px;padding:12px 14px 14px;min-width:0}
fieldset.missing{border-color:var(--_err)}
fieldset.off{display:none}
/* 目次（質問が多いとき、質問の題を横に並べる。今見ている質問に印が付く） */
.index{flex:none;width:212px;min-height:0;overflow-y:auto;overscroll-behavior:contain;scrollbar-width:thin;padding:20px 4px 12px 14px}
.index>*{flex:none}
.index .sec{margin:10px 0 2px 8px;font-size:11px;font-weight:700;color:var(--_muted);letter-spacing:.04em;overflow-wrap:anywhere}
.index .sec:first-child{margin-top:0}
.index button{display:flex;gap:7px;align-items:baseline;width:100%;margin:0 0 1px;text-align:left;padding:4px 8px;font-size:13px;line-height:1.45;
  border:0;border-left:3px solid transparent;border-radius:0 7px 7px 0;background:none;color:var(--_muted)}
.index button:hover{color:var(--_fg);background:var(--_card)}
.index button .n{flex:none;min-width:18px;text-align:right;font-size:11px;font-variant-numeric:tabular-nums}
.index button .t{min-width:0;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow-wrap:anywhere}
.index button.cur{color:var(--_accent);font-weight:700;border-left-color:var(--_accent);background:var(--_soft)}
.index button.lack:not(.cur){color:var(--_warn)}
.index button.lack .n::after{content:"●";margin-left:2px;font-size:8px;vertical-align:2px;color:var(--_warn)}
legend{float:left;width:100%;padding:0;margin:0 0 2px;font-weight:700;font-size:15px;overflow-wrap:anywhere}
legend .num{display:inline-block;min-width:22px;height:22px;line-height:22px;text-align:center;
  border-radius:11px;background:var(--_soft);color:var(--_accent);font-size:12px;margin-right:8px}
legend .kind{font-weight:400;font-size:12px;color:var(--_muted);margin-left:8px}
legend .tag{font-weight:600;font-size:11px;line-height:18px;padding:0 7px;margin-left:8px;border-radius:9px;
  border:1px solid var(--_line);color:var(--_muted);vertical-align:1px}
.help{clear:both;color:var(--_muted);font-size:13px;margin:0 0 8px;white-space:pre-wrap;overflow-wrap:anywhere}
.clear{clear:both}
.opts{clear:both;display:grid;gap:8px;grid-template-columns:repeat(auto-fill,minmax(var(--min,220px),1fr))}
.grp{grid-column:1/-1;margin:6px 0 -2px;font-size:12px;font-weight:700;color:var(--_muted);letter-spacing:.04em}
.grp:first-child{margin-top:0}
.opt{position:relative;display:block;border:1.5px solid var(--_line);border-radius:10px;
  padding:8px 10px 8px 34px;cursor:pointer;background:var(--_card);transition:border-color .1s,background .1s;overflow-wrap:anywhere}
.opt:hover{border-color:var(--_accent)}
.opt input[type=radio],.opt input[type=checkbox]{position:absolute;left:10px;top:11px;margin:0;
  width:16px;height:16px;accent-color:var(--_accent)}
.opt:has(input:checked){border-color:var(--_accent);background:var(--_soft)}
.opt:has(input:focus-visible){outline:2px solid var(--_accent);outline-offset:2px}
.name{font-weight:600}
.opt .key{font:12px ui-monospace,Consolas,monospace;color:var(--_muted);margin-left:6px}
.opt .badge{display:inline-block;font-size:11px;font-weight:700;line-height:18px;padding:0 7px;margin-left:6px;
  border-radius:9px;background:var(--_accent);color:var(--_on);vertical-align:1px}
.desc{display:block;color:var(--_muted);font-size:12.5px;line-height:1.5;margin-top:1px}
.opt .sw{display:flex;gap:3px;margin-top:6px}
.opt .sw i{flex:1;height:8px;border-radius:4px;border:1px solid color-mix(in srgb,var(--_fg) 25%,transparent)}
.filterbar{clear:both;display:flex;gap:10px;align-items:center;margin:0 0 8px}
.filterbar .cnt{font-size:12px;color:var(--_muted);white-space:nowrap}
.mini,.play,.zoom{padding:1px 9px;font-size:12px;border-radius:7px}
.play{display:inline-block;margin-top:6px}
/* プレビュー（画像・コード） */
.thumb{position:relative;display:block;margin:6px 0 0 -24px;border:1px solid var(--_line);border-radius:7px;
  background:var(--_bg);overflow:hidden}
.thumb img{display:block;width:100%;height:var(--thumb,130px);object-fit:contain}
.zoom{position:absolute;right:5px;bottom:5px;opacity:.85}
pre.code{margin:0;padding:9px 11px;font:12.5px/1.5 ui-monospace,"Cascadia Mono",Consolas,Menlo,monospace;
  white-space:pre;tab-size:2;overflow:auto}
pre.code span{display:block;min-height:1.5em}
pre.code .add{background:rgba(46,160,67,.2)}
pre.code .del{background:rgba(248,81,73,.2)}
pre.code .hunk{color:var(--_muted)}
.opt pre.code{margin:6px 0 0 -24px;max-height:190px;border:1px solid var(--_line);border-radius:7px;background:var(--_bg);cursor:text}
.sidewrap{clear:both;display:grid;grid-template-columns:minmax(190px,36%) 1fr;gap:10px;align-items:start}
.sidewrap .opts{grid-template-columns:1fr}
.pv{position:sticky;top:8px;border:1px solid var(--_line);border-radius:10px;background:var(--_bg);
  min-height:110px;max-height:min(640px,70vh);overflow:auto}
.pv-h{position:sticky;top:0;display:flex;gap:8px;justify-content:space-between;padding:5px 11px;font-size:12px;
  color:var(--_muted);background:var(--_bg);border-bottom:1px solid var(--_line)}
.pv-h b{color:var(--_fg)}
.pv img{display:block;max-width:100%;margin:0 auto;cursor:zoom-in}
.pv .none{padding:30px 11px;text-align:center;color:var(--_muted);font-size:13px}
.lb{position:fixed;inset:0;z-index:10;display:flex;flex-direction:column;align-items:center;justify-content:center;
  gap:10px;padding:14px;background:rgba(8,10,14,.9);color:#fff}
.lb img{max-width:100%;max-height:calc(100% - 96px);object-fit:contain;background:#fff;border-radius:6px}
.lb .cap{font-size:14px;text-align:center}
.lb .bar{display:flex;gap:8px;align-items:center}
/* 並べ替え */
.rank{clear:both;list-style:none;margin:0;padding:0;counter-reset:rk;display:grid;gap:6px}
.rank li{counter-increment:rk;display:flex;align-items:center;gap:10px;border:1.5px solid var(--_line);border-radius:10px;
  padding:7px 10px;background:var(--_card);cursor:grab}
.rank li::before{content:counter(rk);min-width:24px;height:24px;line-height:24px;text-align:center;border-radius:12px;
  background:var(--_soft);color:var(--_accent);font-weight:700;font-size:12px}
.rank li:focus-visible{outline:2px solid var(--_accent);outline-offset:2px}
.rank li.dragging{opacity:.45;border-style:dashed}
.rank .grip{color:var(--_muted);font-size:16px;line-height:1}
.rank .body{flex:1;min-width:0;overflow:visible}
.rank button{padding:0 9px;font-size:13px;line-height:24px}
/* 表（行ごとに 1 つ選ぶ） */
.tblwrap{clear:both;overflow:auto;border:1px solid var(--_line);border-radius:10px}
.tbl{width:100%;border-collapse:collapse}
.tbl th{position:sticky;top:0;text-align:left;font-size:12px;color:var(--_muted);font-weight:700;padding:6px 10px;
  background:var(--_bg);border-bottom:1px solid var(--_line)}
.tbl td{padding:6px 10px;border-top:1px solid var(--_line);vertical-align:middle}
.tbl tr:first-child td{border-top:0}
.tbl td.pick{white-space:nowrap}
.tbl tr.changed td:first-child{box-shadow:inset 3px 0 0 var(--_accent)}
.tbl select{font:inherit;color:inherit;background:var(--_bg);border:1.5px solid var(--_line);border-radius:8px;padding:4px 6px;max-width:260px}
.seg{display:inline-flex;border:1.5px solid var(--_line);border-radius:8px;overflow:hidden}
.seg label{padding:3px 11px;cursor:pointer;font-size:13px;border-left:1px solid var(--_line)}
.seg label:first-child{border-left:0}
.seg input{position:absolute;opacity:0;pointer-events:none}
.seg label:has(input:checked){background:var(--_accent);color:var(--_on);font-weight:700}
.seg label:has(input:focus-visible){outline:2px solid var(--_accent);outline-offset:-2px}
/* 入力欄 */
input[type=text],input[type=search],textarea{width:100%;font:inherit;color:inherit;background:var(--_bg);
  border:1.5px solid var(--_line);border-radius:8px;padding:6px 9px}
input[type=text]:focus,input[type=search]:focus,textarea:focus,select:focus{outline:none;border-color:var(--_accent)}
.opt.other input[type=text]{margin-top:4px}
textarea{resize:vertical;min-height:54px}
textarea.mono{font:12.5px/1.55 ui-monospace,"Cascadia Mono",Consolas,Menlo,monospace;white-space:pre;tab-size:2}
.editbar{display:flex;justify-content:flex-end;margin-top:6px;min-height:22px}
/* 質問ごとの自由記述（ボタンで開く） */
.cmt{clear:both;margin-top:8px}
.cmt textarea{margin-top:6px}
.cmt .mini.has{border-color:var(--_accent);color:var(--_accent);font-weight:700}
footer{flex:none;display:flex;align-items:center;flex-wrap:wrap;gap:10px;padding:10px 22px;
  background:var(--_bg);border-top:1px solid var(--_line)}
.status{flex:1 1 120px;color:var(--_muted);font-size:13px}
.status.warn{color:var(--_warn);font-weight:600}
button{font:inherit;border-radius:9px;padding:7px 16px;cursor:pointer;border:1.5px solid var(--_line);
  background:var(--_card);color:var(--_fg)}
button:disabled{opacity:.45;cursor:default}
button.primary{background:var(--_accent);border-color:var(--_accent);color:var(--_on);font-weight:700}
button kbd{font:11px ui-monospace,Consolas,monospace;opacity:.75;margin-left:6px}
.unsupported{padding:40px 22px;text-align:center;color:var(--_muted)}
@media (max-width:767px){.index{display:none}.opts{grid-template-columns:1fr}.sidewrap{grid-template-columns:1fr}.pv{position:static;max-height:50vh}
  .inner{padding:14px 14px 8px}footer{padding:8px 14px}button kbd{display:none}}
@media (pointer:coarse){input[type=text],input[type=search],textarea,select{font-size:max(16px,1em)}}
`;

const COLOR_RE = /^#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$/;
const norm = (s) => String(s ?? '').normalize('NFKC').toLowerCase();
const arr = (v) => (v == null ? [] : Array.isArray(v) ? v : [v]);
const num = (v, lo, hi) => (typeof v === 'number' && isFinite(v) ? Math.min(hi, Math.max(lo, v)) : null);
const composing = (e) => e.isComposing || e.keyCode === 229;

function el(tag, attrs, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === false || v == null) continue;
    if (k === 'class') n.className = v; else if (k === 'text') n.textContent = v; else n.setAttribute(k, v === true ? '' : v);
  }
  for (const kid of kids) if (kid) n.append(kid);
  return n;
}

/** 定義を描く。返り値は、部品の要素（host）が呼ぶ操作。 */
function mount(host, root, SPEC) {
  const QS = SPEC.questions;
  const ctl = {};            // 質問の id → { get, miss, set?, custom?, edited? }
  const FS = new Map();      // 質問の id → その枠（fieldset）
  const media = (ref, kind) => {   // 出してよい URL だけを返す（置いた側が決める）
    if (!ref || typeof host.resolveMedia !== 'function') return null;
    try { const u = host.resolveMedia(String(ref), kind); return typeof u === 'string' && u ? u : null; } catch (e) { return null; }
  };
  const fire = (type, detail) => host.dispatchEvent(new CustomEvent(type, { detail, bubbles: true, composed: true }));

  const body = el('div', { class: 'body' }), inner = el('div', { class: 'inner' });
  const status = el('span', { class: 'status', role: 'status', 'data-ask-status': true });
  const cancelBtn = el('button', { type: 'button', 'data-ask-cancel': true }, 'キャンセル', el('kbd', { text: 'Esc' }));
  const submitBtn = el('button', { type: 'button', class: 'primary', 'data-ask-submit': true }, SPEC.submit || '決定', el('kbd', { text: 'Ctrl+Enter' }));
  const footer = el('footer', null, status, cancelBtn, submitBtn);
  const index = el('nav', { class: 'index', hidden: true, 'aria-label': '質問の一覧' });
  body.append(inner);
  const main = el('div', { class: 'main' }, index, body);   // 目次は、質問の並び（body）の外。自分の高さの中でスクロールする

  // ── プレビュー（選択肢の image・code） ──
  function codeBlock(o) {
    const pre = el('pre', { class: 'code' });
    if (o.lang === 'diff') {
      for (const line of String(o.code).split('\n')) {
        const c = line.startsWith('@@') ? 'hunk' : line.startsWith('+') ? 'add' : line.startsWith('-') ? 'del' : '';
        pre.append(el('span', { class: c, text: line }));
      }
    } else pre.textContent = String(o.code);
    return pre;
  }
  const inputOf = (q, o) => FS.get(q.id).querySelector(`input[name="${CSS.escape(q.id)}"][value="${CSS.escape(o.value)}"]:not([data-other])`);

  // 画像の拡大表示（←→ で同じ質問の画像を移り、Enter でその選択肢を選ぶ）
  const lbImg = el('img', { alt: '' }), lbCap = el('div', { class: 'cap' });
  const lbPrev = el('button', { type: 'button', 'aria-label': '前へ', text: '‹' }), lbNext = el('button', { type: 'button', 'aria-label': '次へ', text: '›' });
  const lbPickBtn = el('button', { type: 'button', class: 'primary' }, 'これを選ぶ', el('kbd', { text: 'Enter' }));
  const lbCloseBtn = el('button', { type: 'button' }, '閉じる', el('kbd', { text: 'Esc' }));
  const lb = el('div', { class: 'lb', hidden: true }, lbImg, lbCap, el('div', { class: 'bar' }, lbPrev, lbPickBtn, lbNext, lbCloseBtn));
  let lbState = null;
  let how = '';   // 直前の操作（'pointer' か、押したキー）。即確定で、何で選んだかを見る
  function lbDraw() {
    const { items, i } = lbState, o = items[i];
    lbImg.src = o._image;
    lbCap.textContent = `${o.label}（${i + 1} / ${items.length}）`;
    lbPrev.hidden = lbNext.hidden = items.length < 2;
  }
  function lbShow(q, o) {
    const items = q.options.filter(x => x._image);
    lbState = { q, items, i: Math.max(0, items.indexOf(o)) };
    lbDraw();
    root.append(lb);
    lb.hidden = false;
    lbPickBtn.focus();
  }
  function lbMove(d) { const n = lbState.items.length; lbState.i = (lbState.i + d + n) % n; lbDraw(); }
  function lbClose() { lb.hidden = true; lb.remove(); lbState = null; }
  function lbPick() {
    const { q, items, i } = lbState, inp = inputOf(q, items[i]);
    lbClose();
    how = '';   // 下の click では決定させない（決定は、この後の 1 回だけ）
    if (!inp.checked) inp.click();
    inp.focus();
    if (instant) submit();
  }
  lbPrev.addEventListener('click', () => lbMove(-1));
  lbNext.addEventListener('click', () => lbMove(1));
  lbPickBtn.addEventListener('click', lbPick);
  lbCloseBtn.addEventListener('click', lbClose);
  lb.addEventListener('click', (e) => { if (e.target === lb) lbClose(); });

  // ── 試聴（選択肢の audio。鳴らすのは 1 つだけ） ──
  let playing = null;
  function stopAudio() {
    if (!playing) return;
    playing.audio.pause();
    playing.audio.currentTime = 0;
    playing.btn.textContent = '▶ 試聴';
    playing = null;
  }
  function audioButton(src) {
    const btn = el('button', { type: 'button', class: 'play', text: '▶ 試聴' });
    let audio = null;
    const fail = () => { if (playing && playing.btn === btn) playing = null; btn.textContent = '再生できません'; btn.disabled = true; };
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const mine = playing && playing.btn === btn;
      stopAudio();
      if (mine) return;
      if (!audio) { audio = new Audio(src); audio.onended = stopAudio; audio.onerror = fail; }
      playing = { audio, btn };
      btn.textContent = '■ 停止';
      audio.play().catch(fail);
    });
    return btn;
  }

  // ── 質問の型ごとの組み立て ──
  const showPvLater = [];  // 画面に入れてから、最初のプレビューを出す

  // 選ぶ（single・multi）
  function buildChoice(q, fs) {
    const box = el('div', { class: 'opts' });
    for (const o of q.options) { o._image = media(o.image, 'image'); o._audio = media(o.audio, 'audio'); }
    const hasDesc = q.options.some(o => o.desc);
    const hasPv = q.options.some(o => o.code != null || o._image);
    // 既定: コードがあれば横の枠（side）、画像だけならカードの中（inline）
    const mode = !hasPv ? null : (q.preview === 'side' || q.preview === 'inline') ? q.preview : (q.options.some(o => o.code != null) ? 'side' : 'inline');
    box.style.setProperty('--min', (num(q.minWidth, 60, 2000) ?? (hasDesc || mode === 'inline' ? 220 : 150)) + 'px');
    if (num(q.thumb, 20, 2000) != null) box.style.setProperty('--thumb', num(q.thumb, 20, 2000) + 'px');
    const itype = q.type === 'multi' ? 'checkbox' : 'radio';
    const defs = arr(q.default).map(String);
    const pv = mode === 'side' ? el('div', { class: 'pv' }) : null;
    // 横の枠に、その選択肢のプレビューを出す（触れている選択肢 → 無ければ選択中 → 無ければ先頭）
    const showPv = (o) => {
      o = o || q.options.find(x => (inputOf(q, x) || {}).checked) || q.options[0];
      if (pv.dataset.v === o.value) return;
      pv.dataset.v = o.value;
      pv.replaceChildren(el('div', { class: 'pv-h' }, el('b', { text: o.label }), el('span', { text: o.lang || '' })));
      if (o._image) {
        const img = el('img', { src: o._image, alt: o.label });
        img.addEventListener('click', () => lbShow(q, o));
        pv.append(img);
      }
      if (o.code != null) pv.append(codeBlock(o));
      if (!o._image && o.code == null) pv.append(el('div', { class: 'none', text: 'プレビューはありません' }));
    };
    const cards = [];
    let group;
    for (const o of q.options) {
      if (o.group && o.group !== group) box.append(el('div', { class: 'grp', text: (group = o.group) }));
      const lab = el('label', { class: 'opt' },
        el('input', { type: itype, name: q.id, value: o.value, checked: defs.includes(o.value) }),
        el('span', { class: 'name', text: o.label }),
        o.label !== o.value && q.showValue !== false && el('span', { class: 'key', text: o.value }),
        o.recommended === true && el('span', { class: 'badge', text: 'おすすめ' }),
        o.desc && el('span', { class: 'desc', text: o.desc }));
      const colors = arr(o.colors).filter(c => typeof c === 'string' && COLOR_RE.test(c)).slice(0, 16);
      if (colors.length) {
        const sw = el('span', { class: 'sw' });
        for (const c of colors) { const i = el('i'); i.style.backgroundColor = c; sw.append(i); }
        lab.append(sw);
      }
      if (o._audio) lab.append(audioButton(o._audio));
      if (mode === 'inline') {
        if (o._image) {
          const zoom = el('button', { type: 'button', class: 'zoom', text: '拡大' });
          zoom.addEventListener('click', (e) => { e.preventDefault(); lbShow(q, o); });
          lab.append(el('span', { class: 'thumb' }, el('img', { src: o._image, alt: '', loading: 'lazy' }), zoom));
        }
        if (o.code != null) lab.append(codeBlock(o));
      } else if (mode === 'side') {
        lab.addEventListener('mouseenter', () => showPv(o));
        lab.addEventListener('focusin', () => showPv(o));
      }
      lab._text = norm([o.label, o.value, o.desc, o.group].join(' '));
      cards.push(lab);
      box.append(lab);
    }
    let otherPick = null, otherText = null;
    if (q.allowOther) {
      otherText = el('input', { type: 'text', maxlength: TEXT_MAX, placeholder: q.otherPlaceholder || '自由に入力', 'aria-label': (q.otherLabel || 'その他') + 'の内容' });
      otherPick = el('input', { type: itype, name: q.id, value: '', 'data-other': true });   // 「その他」は値ではなく印で見分ける（定義の値とぶつからない）
      otherText.addEventListener('input', () => { if (otherText.value) otherPick.checked = true; refresh(); });
      otherText.addEventListener('focus', () => { otherPick.checked = true; refresh(); });
      box.append(el('label', { class: 'opt other' }, otherPick, el('span', { class: 'name', text: q.otherLabel || 'その他' }), otherText));
    }
    // 絞り込み（選択肢が 12 件以上なら自動で付く。選択中のものは隠さない）
    if (q.filter ?? q.options.length >= 12) {
      const inp = el('input', { type: 'search', placeholder: '絞り込み（名前・説明・分類）', 'aria-label': q.label + ' の絞り込み' });
      const cnt = el('span', { class: 'cnt' });
      const apply = () => {
        const words = norm(inp.value).split(/\s+/).filter(Boolean);
        let n = 0;
        for (const lab of cards) {
          const hit = words.every(w => lab._text.includes(w));
          lab.hidden = !(hit || lab.querySelector('input').checked);
          if (hit) n++;
        }
        for (const g of box.querySelectorAll('.grp')) {
          let any = false;
          for (let s = g.nextElementSibling; s && !s.classList.contains('grp'); s = s.nextElementSibling) any = any || !s.hidden;
          g.hidden = !any;
        }
        cnt.textContent = words.length ? `${n} / ${cards.length} 件` : `${cards.length} 件`;
      };
      inp.addEventListener('input', apply);
      fs.append(el('div', { class: 'filterbar' }, inp, cnt));
      apply();
    }
    if (pv) {
      box.addEventListener('mouseleave', () => showPv());
      box.addEventListener('change', () => showPv());
      fs.append(el('div', { class: 'sidewrap' }, box, pv));
      showPvLater.push(showPv);
    } else fs.append(box);

    const inputs = () => [...box.querySelectorAll(`input[name="${CSS.escape(q.id)}"]`)];
    ctl[q.id] = {
      get() {
        const vals = inputs().filter(i => i.checked && !(i === otherPick && otherText.value.trim() === ''))
          .map(i => i === otherPick ? otherText.value.trim() : i.value);
        return q.type === 'multi' ? vals : (vals[0] ?? null);
      },
      miss: (v) => q.type === 'single' ? v == null : (q.required ? v.length === 0 : false),
      custom: () => !!(otherPick && otherPick.checked),
      set(d) {
        const want = arr(d).map(String);
        for (const i of inputs()) i.checked = i !== otherPick && want.includes(i.value);
        if (pv) showPv();
      },
    };
  }

  // 書く（text）
  function buildText(q, fs) {
    const inp = q.multiline ? el('textarea', { name: q.id, class: 'clear', maxlength: TEXT_MAX, placeholder: q.placeholder, 'aria-label': q.label })
                            : el('input', { type: 'text', name: q.id, class: 'clear', maxlength: TEXT_MAX, placeholder: q.placeholder, 'aria-label': q.label });
    inp.value = typeof q.default === 'string' ? q.default : '';
    fs.append(inp);
    ctl[q.id] = { get: () => inp.value.trim(), miss: (v) => !!q.required && v === '', set: (d) => { inp.value = d || ''; } };
  }

  // 文面を直して返す（edit）
  function buildEdit(q, fs) {
    const orig = String(q.text ?? q.default ?? '');
    const ta = el('textarea', { name: q.id, class: 'clear' + (q.mono === false ? '' : ' mono'), spellcheck: 'false', 'aria-label': q.label });
    ta.value = orig;
    ta.rows = num(q.rows, 1, 60) ?? Math.min(Math.max(orig.split('\n').length + 1, 5), 22);
    const back = el('button', { type: 'button', class: 'mini', text: '元に戻す', hidden: true });
    back.addEventListener('click', () => { ta.value = orig; back.hidden = true; refresh(); });
    ta.addEventListener('input', () => { back.hidden = ta.value === orig; });
    fs.append(ta, el('div', { class: 'editbar' }, back));
    ctl[q.id] = {
      get: () => ta.value.replace(/\s+$/, ''),
      miss: (v) => q.required !== false && v === '',
      edited: () => ta.value !== orig,
    };
  }

  // 並べ替える（rank）
  function buildRank(q, fs) {
    const list = el('ol', { class: 'rank' });
    const byValue = new Map(q.options.map(o => [o.value, o]));
    let drag = null;
    const move = (li, d) => {
      const to = d < 0 ? li.previousElementSibling : li.nextElementSibling;
      if (!to) return;
      list.insertBefore(li, d < 0 ? to : to.nextElementSibling);
      li.focus();
      refresh();
    };
    const item = (o) => {
      const up = el('button', { type: 'button', text: '↑', 'aria-label': '上へ' });
      const down = el('button', { type: 'button', text: '↓', 'aria-label': '下へ' });
      const li = el('li', { draggable: 'true', tabindex: '0', 'data-v': o.value },
        el('span', { class: 'grip', text: '⠿', 'aria-hidden': 'true' }),
        el('span', { class: 'body' }, el('span', { class: 'name', text: o.label }), o.desc && el('span', { class: 'desc', text: o.desc })),
        up, down);
      up.addEventListener('click', () => move(li, -1));
      down.addEventListener('click', () => move(li, 1));
      li.addEventListener('keydown', (e) => {
        if (e.target !== li || e.altKey || (e.key !== 'ArrowUp' && e.key !== 'ArrowDown')) return;
        e.preventDefault();
        e.stopPropagation();
        move(li, e.key === 'ArrowUp' ? -1 : 1);
      });
      li.addEventListener('dragstart', (e) => {
        drag = li;
        li.classList.add('dragging');
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/plain', o.value);
      });
      li.addEventListener('dragend', () => { li.classList.remove('dragging'); drag = null; refresh(); });
      return li;
    };
    list.addEventListener('dragover', (e) => {
      if (!drag) return;
      e.preventDefault();
      const over = e.target.closest('li');
      if (!over || over === drag || over.parentNode !== list) return;
      const r = over.getBoundingClientRect();
      list.insertBefore(drag, e.clientY < r.top + r.height / 2 ? over : over.nextElementSibling);
    });
    const set = (d) => {
      const want = Array.isArray(d) ? d.map(String) : [];
      const ok = want.length === byValue.size && want.every(v => byValue.has(v)) && new Set(want).size === want.length;
      list.replaceChildren(...(ok ? want : [...byValue.keys()]).map(v => item(byValue.get(v))));
    };
    set(q.default);
    fs.append(list);
    ctl[q.id] = { get: () => [...list.children].map(li => li.dataset.v), miss: () => false, set };
  }

  // 表（行ごとに 1 つ選ぶ）。選択肢が 5 つまでは並んだボタン、それより多ければ選択欄
  function buildTable(q, fs) {
    const first = q.options[0].value;
    const picks = new Map();  // 行の value → { get, set }
    const tbody = el('tbody');
    for (const r of q.rows) {
      const init = String(r.default ?? q.default ?? first);
      const tr = el('tr', null, el('td', null, el('span', { class: 'name', text: r.label }), r.desc && el('span', { class: 'desc', text: r.desc })));
      const cell = el('td', { class: 'pick' });
      let get, set;
      if (q.options.length > 5) {
        const sel = el('select', { 'aria-label': r.label });
        let parent = sel, group;
        for (const o of q.options) {
          if (o.group !== group) { group = o.group; parent = group ? sel.appendChild(el('optgroup', { label: group })) : sel; }
          parent.append(el('option', { value: o.value, text: o.label === o.value ? o.label : `${o.label}（${o.value}）` }));
        }
        get = () => sel.value;
        set = (v) => { sel.value = v; };
        cell.append(sel);
      } else {
        const seg = el('span', { class: 'seg' });
        for (const o of q.options) {
          seg.append(el('label', { title: o.desc }, el('input', { type: 'radio', name: `${q.id}/${r.value}`, value: o.value }), o.label));
        }
        get = () => (seg.querySelector('input:checked') || {}).value;
        set = (v) => { for (const i of seg.querySelectorAll('input')) i.checked = i.value === v; };
        cell.append(seg);
      }
      const mark = () => tr.classList.toggle('changed', get() !== init);
      cell.addEventListener('change', mark);
      set(init);
      picks.set(r.value, { get, set: (v) => { set(v); mark(); } });
      tr.append(cell);
      tbody.append(tr);
    }
    const head = el('thead', null, el('tr', null, el('th', { text: q.rowLabel || '項目' }), el('th', { text: q.pickLabel || '選ぶ' })));
    fs.append(el('div', { class: 'tblwrap' }, el('table', { class: 'tbl' }, head, tbody)));
    ctl[q.id] = {
      get: () => Object.fromEntries([...picks].map(([k, p]) => [k, p.get()])),
      miss: () => false,
      // d は { 行: 値 }。書かれていない行は、その行の最初の既定（r._default0 が無ければ今の既定）へ
      set(d) { for (const r of q.rows) picks.get(r.value).set(String((d || {})[r.value] ?? r._default0 ?? r.default ?? q.default ?? first)); },
    };
  }

  // 質問ごとの自由記述: ボタンを押すと欄が開く（選択肢では言い切れない希望・条件を、その質問に添えて書く）。
  // 書く質問（text）には付けない。定義の comments: false で全部、質問の comment: false でその質問だけ付けない。
  // 選んだ時点で決定するフォーム（質問 1 つ・補足なし）にも付けない
  const CMT = new Map();     // 質問の id → その自由記述の欄（textarea）
  const commentable = (q) => SPEC.comments !== false && q.comment !== false && q.type !== 'text' && !(QS.length === 1 && QS[0].type === 'single' && SPEC.note === false);
  function addComment(q, fs) {
    const ta = el('textarea', { hidden: true, maxlength: TEXT_MAX, rows: '2', 'aria-label': q.label + ' の自由記述', 'data-ask-comment': q.id,
      placeholder: 'この質問について伝えたいこと（選択肢に無い希望・条件など）' });
    const btn = el('button', { type: 'button', class: 'mini', 'aria-expanded': 'false', 'data-ask-comment-toggle': q.id });
    const label = () => {
      btn.textContent = ta.hidden ? (ta.value.trim() ? '自由記述（入力あり）を開く' : '＋ 自由記述') : '自由記述を閉じる';
      btn.classList.toggle('has', ta.hidden && !!ta.value.trim());
    };
    btn.addEventListener('click', () => {
      ta.hidden = !ta.hidden;
      btn.setAttribute('aria-expanded', String(!ta.hidden));
      label();
      if (!ta.hidden) ta.focus();
    });
    label();
    fs.append(el('div', { class: 'cmt' }, btn, ta));
    CMT.set(q.id, ta);
  }

  const BUILD = { single: buildChoice, multi: buildChoice, text: buildText, edit: buildEdit, rank: buildRank, table: buildTable };
  const KIND = { multi: '複数選べます', rank: 'ドラッグか ↑↓ で並べ替え', edit: 'そのまま直せます' };

  // ── 画面を組む ──
  const title = el('h1', { text: SPEC.title || '質問', tabindex: '-1', 'data-ask-title': true });
  inner.append(title);
  const intro = SPEC.intro ? el('p', { class: 'intro', text: SPEC.intro }) : null;
  if (intro) inner.append(intro);

  // 前回の回答を既定にしているとき（定義の remember）は、そのことを示し、元の既定へ戻せるようにする
  const recalled = QS.filter(q => q._remembered);
  if (recalled.length) {
    const back = el('button', { type: 'button', class: 'mini', text: '今回の既定に戻す' });
    const bar = el('div', { class: 'recall' }, el('span', { text: `前回の回答を既定にしています（${recalled.length} 件）` }), back);
    back.addEventListener('click', () => {
      for (const q of recalled) ctl[q.id].set(q.type === 'table' ? null : q._default0);
      for (const t of inner.querySelectorAll('legend .tag')) t.remove();
      bar.remove();
      refresh();
    });
    inner.append(bar);
  }

  const ITEMS = [];  // 画面に並ぶ枠（質問と補足）
  for (const q of QS) {
    const fs = el('fieldset', { 'data-ask-question': q.id });
    const kind = KIND[q.type] || (q.type === 'text' && !q.required ? '任意' : '');
    fs.append(el('legend', null, el('span', { class: 'num' }), q.label, kind && el('span', { class: 'kind', text: kind }),
      q._remembered && el('span', { class: 'tag', text: '前回の回答' })));
    if (q.help) fs.append(el('p', { class: 'help', text: q.help }));
    FS.set(q.id, fs);
    BUILD[q.type](q, fs);
    if (commentable(q)) addComment(q, fs);
    inner.append(fs);
    ITEMS.push(fs);
  }
  for (const show of showPvLater) show();
  let noteBox = null, noteInput = null;
  if (SPEC.note !== false) {
    noteInput = el('textarea', { class: 'clear', maxlength: TEXT_MAX, 'aria-label': '補足',
      placeholder: SPEC.notePlaceholder || (typeof SPEC.note === 'string' ? SPEC.note : '') });
    noteBox = el('fieldset', { 'data-ask-note': true },
      el('legend', null, '補足', el('span', { class: 'kind', text: '任意・選択肢に無い希望があれば' })), noteInput);
    inner.append(noteBox);
    ITEMS.push(noteBox);
  }
  root.replaceChildren(el('style', { text: STYLE }), main, footer);   // 拡大表示（lb）は、開いたときにだけ入れる

  // ── 目次 ──
  // 質問の題を横に並べる。スクロールに合わせて、今見ている質問に印が付く。押すとその質問へ移る。
  // 出すかどうかは定義の paging に従う: 無指定（"auto"）なら与えられた高さに収まらないときだけ、true・数なら必ず、false なら出さない。
  // 質問の page（まとまりの題。同じ題が続くあいだが 1 つのまとまり）は、目次の見出しになる（page を書いたら、収まっていても出す。
  // ただし paging が false なら、page があっても出さない）。
  // 幅の狭い画面（viewport の幅が 767px 以下）では出さない。見るのは画面の幅で、部品を置いた場所の幅ではない——
  // 置いた側は、目次が出ているときは indexWidth の分だけ場所を広げる（広げないと、質問の並びがその分せまくなる）
  const ENTRIES = [];        // 目次の項目 { fs, btn, n, sec }（ITEMS と同じ並び）
  let cur = 0, want = null;  // 今見ている項目・選んだ項目（目次で押した・フォーカスが入った・未回答で移された。その質問が見えている間は、そちらを今の項目にする）
  let hold = 0;              // 選んだ項目へ移っている途中（なめらかなスクロールの間）は、まだ見えていなくても選んだ項目のままにする。その期限
  const choose = (i) => { want = i; hold = performance.now() + 900; mark(i); };
  {
    let name = null, sec = null;
    ITEMS.forEach((fs, i) => {
      const q = QS[i];   // 補足には無い
      if (q && q.page != null && String(q.page) !== name) { name = String(q.page); sec = el('div', { class: 'sec', text: name }); index.append(sec); }
      const n = el('span', { class: 'n' });
      const btn = el('button', { type: 'button', 'data-ask-index': q ? q.id : '' }, n, el('span', { class: 't', text: q ? q.label : '補足' }));
      btn.addEventListener('click', () => go(i));
      index.append(btn);
      ENTRIES.push({ fs, btn, n, sec });
    });
  }
  const explicit = QS.some(q => q.page != null);
  const topOf = (fs) => fs.getBoundingClientRect().top - body.getBoundingClientRect().top + body.scrollTop;
  function mark(i) {
    cur = i;
    ENTRIES.forEach((e, k) => { e.btn.classList.toggle('cur', k === i); e.btn.setAttribute('aria-current', k === i ? 'true' : 'false'); });
    if (index.hidden) return;
    // 目次が長くてスクロールするときは、今の項目が見える所へ目次も動かす（前後の項目が 1〜2 個見える余白を残す）
    const b = ENTRIES[i].btn, r = b.getBoundingClientRect(), box = index.getBoundingClientRect(), pad = Math.min(56, box.height / 4);
    if (r.top < box.top + pad) index.scrollTop -= box.top + pad - r.top;
    else if (r.bottom > box.bottom - pad) index.scrollTop += r.bottom - box.bottom + pad;
  }
  // 今見ている質問: 「読んでいる線」を過ぎた最後の質問。線は、ふだんは上の端のすぐ下。
  // 下の端に近づくと（残りが画面 1 枚分を切ると）、線を上の端から下の端へ少しずつ下げる。こうすると、最後の画面に
  // 並んで収まっている短い質問にも順に印が移り、いちばん下まで下げたときに最後の項目に印が付く。
  // 目次で選んだ質問が見えている間は、その質問を今の項目にする
  function spy() {
    const y = body.scrollTop, h = body.clientHeight, max = Math.max(0, body.scrollHeight - h);
    // スクロールできない（全部が収まっている）ときは線を下げない——最初の質問に印を付ける。印はフォーカスで移る（下の focusin）
    const tail = Math.min(h, max), k0 = tail > 0 ? Math.min(1, Math.max(0, (y - (max - tail)) / tail)) : 0;
    const line = y + 40 + k0 * (h - 40);
    let at = -1;
    ENTRIES.forEach((e, k) => { if (!e.fs.hidden && (at < 0 || topOf(e.fs) <= line)) at = k; });
    if (want != null) {
      const t = ENTRIES[want].fs.hidden ? -1 : topOf(ENTRIES[want].fs);
      if ((t >= y - 2 && t < y + h) || (t >= 0 && performance.now() < hold)) at = want; else want = null;
    }
    if (at >= 0) mark(at);
  }
  function go(i, quiet) {
    if (i < 0 || i >= ENTRIES.length || ENTRIES[i].fs.hidden) return;
    choose(i);
    body.scrollTop = Math.max(0, topOf(ENTRIES[i].fs) - 10);
    if (quiet) return;
    const t = [...ENTRIES[i].fs.querySelectorAll('input:not([type=search]),textarea:not([data-ask-comment]),select,li[tabindex]')].find(x => !x.closest('[hidden]'));
    const pick = t && t.type === 'radio' ? (ENTRIES[i].fs.querySelector('input[type=radio]:checked') || t) : t;   // ラジオは、選ばれているものへ
    if (pick) pick.focus({ preventScroll: true });
  }
  // 次・前の質問へ（表示条件で隠れている質問は飛ばす）
  function step(d) {
    let i = cur + d;
    while (i >= 0 && i < ENTRIES.length && ENTRIES[i].fs.hidden) i += d;
    go(i);
  }
  // 目次を、今の状態（出ている質問・番号・未回答）に合わせる
  function paint(lacking) {
    for (const e of ENTRIES) {
      e.btn.hidden = e.fs.hidden;
      const num = e.fs.querySelector('.num');
      e.n.textContent = num ? num.textContent : '';
    }
    if (lacking) { const ids = new Set(lacking.map(q => q.id)); for (const e of ENTRIES) e.btn.classList.toggle('lack', ids.has(e.fs.dataset.askQuestion)); }
    for (const sec of new Set(ENTRIES.map(e => e.sec).filter(Boolean))) sec.hidden = !ENTRIES.some(e => e.sec === sec && !e.fs.hidden);
    if (ENTRIES[cur].fs.hidden) spy();
  }
  // 目次を出すかを決める（部品に与えられた高さで決める）
  function layout() {
    if (!body.clientHeight) return false;
    const mode = SPEC.paging;
    let show = false;
    if (mode !== false && ENTRIES.length > 1) {
      if (explicit || mode === true || typeof mode === 'number') show = true;
      else { index.hidden = true; show = inner.offsetHeight > body.clientHeight + 1; }
    }
    index.hidden = !show;
    spy();
    return true;
  }
  body.addEventListener('scroll', spy, { passive: true });
  // フォーカスが質問に入ったら、その質問を今の項目にする（Tab で移ったとき・未回答の質問へ移されたとき。
  // スクロールだけでは印が届かない所——全部が収まっているフォーム・画面の途中にある質問——にも印が付く）
  inner.addEventListener('focusin', (e) => {
    const fs = e.target.closest && e.target.closest('fieldset'), i = ENTRIES.findIndex(x => x.fs === fs);
    if (i >= 0) choose(i);
  });
  for (const t of ['wheel', 'touchmove']) body.addEventListener(t, () => { want = null; hold = 0; }, { passive: true });

  // ── 回答を読む ──
  function visible(q, answers) {
    for (const [dep, want] of Object.entries(q.showIf || {})) {
      if (!(dep in answers)) return false;
      const have = arr(answers[dep]);
      if (!arr(want).map(String).some(w => have.includes(w))) return false;
    }
    return true;
  }
  // 上から順に見て、表示条件（showIf）を満たす質問だけを回答に入れる
  function collect() {
    const answers = {}, custom = [], edited = [], lacking = [], comments = {};
    let n = 0;
    for (const q of QS) {
      const fs = FS.get(q.id), c = ctl[q.id];
      const show = visible(q, answers);
      fs.hidden = !show;
      if (!show) continue;
      fs.querySelector('.num').textContent = ++n;
      const v = c.get();
      const miss = c.miss(v);
      if (miss) lacking.push(q); else { fs.classList.remove('missing'); fs.removeAttribute('aria-invalid'); }
      if (!miss || q.type !== 'single') answers[q.id] = v;
      if (c.custom && c.custom()) custom.push(q.id);
      if (c.edited && c.edited()) edited.push(q.id);
      const cm = CMT.has(q.id) ? CMT.get(q.id).value.trim() : '';   // 閉じていても、書いてあれば入れる
      if (cm) comments[q.id] = cm;
    }
    return { answers, custom, edited, lacking, comments };
  }
  function refresh() {
    const { lacking } = collect();
    status.textContent = lacking.length ? `未回答 ${lacking.length} 件` : 'すべて回答済み';
    status.classList.remove('warn');
    paint(lacking);
    return lacking;
  }

  // 今の回答（決定のときに知らせる形）と、未回答の質問
  function value() {
    const { answers, custom, edited, lacking, comments } = collect();
    const out = { answers };
    if (custom.length) out.custom = custom;
    if (edited.length) out.edited = edited;
    if (Object.keys(comments).length) out.comments = comments;
    const note = noteInput ? noteInput.value.trim() : '';
    if (note) out.note = note;
    return { out, lacking };
  }

  // ── 決定・取り消し（送るのは置いた側。ここは知らせるだけ） ──
  function submit() {
    if (host.busy) return;
    const { out, lacking } = value();
    if (lacking.length) {
      for (const q of lacking) { FS.get(q.id).classList.add('missing'); FS.get(q.id).setAttribute('aria-invalid', 'true'); }
      const firstFs = FS.get(lacking[0].id);
      const target = [...firstFs.querySelectorAll('input:not([type=search]),textarea:not([data-ask-comment]),select')].find(x => !x.closest('[hidden]'));   // 絞り込みで隠れていないもの
      if (target) target.focus({ preventScroll: true });   // その質問へフォーカスを移す
      const at = ENTRIES.findIndex(x => x.fs === firstFs);
      if (at >= 0) choose(at);                             // 目次の印も、その質問へ
      firstFs.scrollIntoView({ behavior: 'smooth', block: 'center' });
      status.textContent = `未回答 ${lacking.length} 件 — 答えてから決定してください`;
      status.classList.add('warn');
      return;
    }
    stopAudio();
    fire('ask-submit', out);
  }

  // 質問が 1 つだけ（単一選択・補足なし）なら、選んだ時点で決定する。ただしクリック・タップ・Space・Enter で選んだときだけ
  // （矢印キーで移っただけでは決定しない——見て回っている途中で決まってしまうため）
  const instant = QS.length === 1 && QS[0].type === 'single' && SPEC.note === false;
  root.addEventListener('pointerdown', () => { how = 'pointer'; }, true);
  root.addEventListener('keydown', (e) => { how = e.key; }, true);
  inner.addEventListener('change', refresh);
  // 選択肢のクリック・タップ。既に選ばれている選択肢でも決定する（change は起きないので、click で見る）。
  // キーが元の click（矢印キーで移ったとき・まだ選ばれていない選択肢で Space を押したときにブラウザが出す）では決定しない。
  // Space・Enter は keydown で受ける（既に選ばれているラジオでは、Space を押してもブラウザが click を出さないため）
  inner.addEventListener('click', (e) => {
    const t = e.target;
    if (!instant || t.type !== 'radio' || t.dataset.other != null || how !== 'pointer') return;
    t.checked = true;
    refresh();
    submit();
  });
  inner.addEventListener('input', refresh);
  submitBtn.addEventListener('click', submit);
  cancelBtn.addEventListener('click', () => { if (!host.busy) { stopAudio(); fire('ask-cancel', {}); } });
  // キーは部品の要素で受ける（中の欄からも、部品そのものにフォーカスがあるときも届く）。扱ったキーは外へ流さない
  // （置いた側の同じキーと二重に効かないように）
  const onKey = (e) => {
    if (composing(e)) return;
    const used = () => { e.preventDefault(); e.stopPropagation(); };
    if (lbState) {  // 拡大表示の間は、キーを拡大表示だけが受ける
      if (e.key === 'Escape') lbClose();
      else if (e.key === 'ArrowLeft') lbMove(-1);
      else if (e.key === 'ArrowRight') lbMove(1);
      else if (e.key === 'Enter') lbPick();
      else return;
      return used();
    }
    const t = e.composedPath()[0], search = t.matches && t.matches('input[type=search]');
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { used(); submit(); }
    else if (e.altKey && (e.key === 'PageDown' || e.key === 'PageUp')) { used(); step(e.key === 'PageUp' ? -1 : 1); }  // 次・前の質問へ
    else if (e.key === 'Escape' && search && t.value) {  // 絞り込み中の Esc は、まず絞り込みを消す（それ以外の Esc は外へ流す）
      used();
      t.value = '';
      t.dispatchEvent(new Event('input', { bubbles: true }));
    }
    else if (e.key === 'Enter' && search) e.preventDefault();
    else if (e.key === 'Enter' && t.matches && t.matches('input[type=text]')) {  // 目次が出ている（質問が多い）ときは次の質問へ、最後の質問では決定
      used();
      const fs = t.closest('fieldset'), at = ENTRIES.findIndex(x => x.fs === fs);
      const later = ENTRIES.some((x, k) => k > at && !x.fs.hidden && x.fs !== noteBox);
      if (index.hidden || !later) submit(); else { cur = at; step(1); }
    }
    else if ((e.key === 'Enter' || e.key === ' ') && instant && t.matches && t.matches('input[type=radio]:not([data-other])')) {  // 即確定: Space・Enter で選んで決定
      used();
      t.checked = true;
      refresh();
      submit();
    }
  };
  host.addEventListener('keydown', onKey);

  refresh();
  return {
    submit,
    step,
    layout,
    value() { const { out, lacking } = value(); return Object.assign(out, { lacking: lacking.map(q => q.id) }); },
    setBusy(b) { submitBtn.disabled = cancelBtn.disabled = !!b; },
    notify(msg, warn) { status.textContent = msg; status.classList.toggle('warn', !!warn); },
    // 中身の高さ（置いた側が、ウィンドウの高さを決めるのに使う）と、目次の幅（出ていなければ 0）
    contentHeight: () => inner.offsetHeight + footer.offsetHeight,
    indexWidth: () => (index.hidden ? 0 : index.offsetWidth),
    destroy() { stopAudio(); host.removeEventListener('keydown', onKey); },
  };
}

export class AskFormElement extends HTMLElement {
  static version = VERSION;
  /** 出せる型と、読む項目（置いた側が「この画面が出せるもの」を知るのに使う）。 */
  static supports = { types: TYPES.slice(), fields: FIELDS.slice() };

  #spec = null;
  #busy = false;
  #ui = null;
  #sized = false;
  #ro = null;
  /** (ref, "image" | "audio") => 出してよい URL か null。 */
  resolveMedia = null;

  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
  }

  connectedCallback() {
    // 目次を出すかは、最初に高さが決まったときに 1 回だけ決める（そのあと高さが変わっても変えない。
    // 画面のキーボードで高さが縮んだときに、目次が出て入力中の欄が動かないように）
    this.#ro = new ResizeObserver(() => { if (!this.#sized && this.#ui) this.#sized = this.#ui.layout(); });
    this.#ro.observe(this);
    if (this.#spec && !this.#ui) this.#render();
  }

  disconnectedCallback() {
    if (this.#ro) { this.#ro.disconnect(); this.#ro = null; }
    if (this.#ui) { this.#ui.destroy(); this.#ui = null; }
  }

  get spec() { return this.#spec; }
  set spec(v) {
    this.#spec = v || null;
    if (this.isConnected) this.#render();
  }

  get busy() { return this.#busy; }
  set busy(v) {
    this.#busy = !!v;
    if (this.#ui) this.#ui.setBusy(this.#busy);
  }

  /** 今の回答で決定する（未回答があれば、決定せずにその質問を示す）。 */
  submit() { if (this.#ui) this.#ui.submit(); }
  /** 次・前の質問へ移る（+1 で次・-1 で前。隠れている質問は飛ばす）。部品の外でキーを受けたとき用。 */
  step(delta) { if (this.#ui && (delta > 0 || delta < 0)) this.#ui.step(delta < 0 ? -1 : 1); }
  /** 目次を出すかを決め直す（置いた側が高さを決め直したとき）。 */
  relayout() { if (this.#ui) this.#sized = this.#ui.layout(); }
  /** 状態の行に文を出す（送れなかった、など）。 */
  notify(message, warn) { if (this.#ui) this.#ui.notify(String(message), warn); }
  /** 今の回答 { answers, custom?, edited?, note?, lacking: [未回答の質問の id] }（読むだけ。決定はしない）。 */
  get value() { return this.#ui ? this.#ui.value() : null; }
  /** 互換のために残す（ページには分けないので、いつも 1）。 */
  get pageCount() { return this.#ui ? 1 : 0; }
  get contentHeight() { return this.#ui ? this.#ui.contentHeight() : 0; }
  /** 目次の幅（px。出ていなければ 0）。置いた側が、ウィンドウの幅を広げるのに使う。 */
  get indexWidth() { return this.#ui ? this.#ui.indexWidth() : 0; }

  #render() {
    if (this.#ui) { this.#ui.destroy(); this.#ui = null; }
    this.#sized = false;
    const root = this.shadowRoot, spec = this.#spec;
    root.replaceChildren();
    if (!spec) return;
    const bad = unsupported(spec);
    if (bad) {   // 出せない定義は描かない（質問が欠けたまま決定されるのを防ぐ）
      root.replaceChildren(el('style', { text: STYLE }), el('div', { class: 'unsupported', text: 'このフォームは、この画面では出せません。' }));
      queueMicrotask(() => this.dispatchEvent(new CustomEvent('ask-unsupported', { detail: { reason: bad }, bubbles: true, composed: true })));
      return;
    }
    try {
      this.#ui = mount(this, root, spec);
    } catch (e) {
      root.replaceChildren(el('style', { text: STYLE }), el('div', { class: 'unsupported', text: 'このフォームは、この画面では出せません。' }));
      queueMicrotask(() => this.dispatchEvent(new CustomEvent('ask-unsupported', { detail: { reason: 'render failed: ' + (e && e.message) }, bubbles: true, composed: true })));
      return;
    }
    this.#ui.setBusy(this.#busy);
    if (this.clientHeight) this.#sized = this.#ui.layout();
  }
}

/** 出せない定義なら理由を返す（知らない型・形の壊れた質問）。出せるなら null。 */
function unsupported(spec) {
  if (!spec || typeof spec !== 'object' || !Array.isArray(spec.questions) || !spec.questions.length) return 'spec has no questions';
  for (const q of spec.questions) {
    if (!q || typeof q !== 'object' || typeof q.id !== 'string' || !q.id) return 'a question has no id';
    if (!TYPES.includes(q.type)) return `question "${q.id}" has an unsupported type "${q.type}"`;
    const needs = q.type !== 'text' && q.type !== 'edit';
    if (needs && !Array.isArray(q.options)) return `question "${q.id}" has no options`;   // 渡された定義は書き換えない
    if (needs && (!q.options.length || q.options.some(o => !o || typeof o.value !== 'string'))) return `question "${q.id}" has broken options`;
    if (q.type === 'table' && (!Array.isArray(q.rows) || !q.rows.length || q.rows.some(r => !r || typeof r.value !== 'string'))) return `question "${q.id}" has broken rows`;
  }
  return null;
}

if (!customElements.get('ask-form')) customElements.define('ask-form', AskFormElement);
