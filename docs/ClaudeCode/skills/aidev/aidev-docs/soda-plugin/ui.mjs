// 画面（script-html のアプリ画面・静的な代替・帯/パネル・端末版の Markdown）。
// データは `display.send` の JSON で届き、画面側は textContent だけで描く（HTML として解釈しない）。
// 静的に組む HTML（代替・帯）は、値をすべて `esc` に通す。
import { summarize } from './operations.mjs';

export const esc = (v = '') => String(v).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const clip = (s, n) => { const t = String(s ?? ''); return t.length > n ? t.slice(0, n - 1) + '…' : t; };
const plain = (s, n = 120) => clip(String(s ?? '').replace(/[\u0000-\u001f\u007f]+/g, ' ').replace(/\s+/g, ' ').trim(), n);

export const STATUS_LABEL = { none: '未起動', starting: '起動中', working: '作業中', idle: '待機', blocked: '承認待ち', stopped: '停止（再開できる）', failed: '失敗' };
const FROM_LABEL = { user: '利用者', supervisor: '監督', worker: '担当', app: 'アプリ' };

// ---- 画面へ送るデータ（小さく切る） -------------------------------------------------------------------

/** 画面（script-html）へ送る形。長い文は切る。一覧は呼び出し側が `chunkItems` で小分けにする。 */
export function uiModel(model) {
  const agent = (a) => a && { ...a, error: a.error ? plain(a.error, 300) : null, lastReport: a.lastReport ? { ...a.lastReport, message: plain(a.lastReport.message, 400) } : a.lastReport, linkErrors: (a.linkErrors ?? []).map((e) => plain(e, 200)) };
  return {
    state: {
      project: model.project, root: model.root, available: model.available, cli: model.cli, truncated: model.truncated, total: model.total, current: model.current,
      supervisor: agent(model.supervisor), settings: model.settings, kinds: model.kinds, summary: summarize(model),
      log: model.log.slice(0, 40).map((e) => ({ ...e, message: plain(e.message, 400) })),
    },
    lists: {
      works: model.works.map(({ worker, ...w }) => ({ ...w, ws: worker?.status ?? '' })),
      workers: model.workers.map(agent),
      backlog: model.backlog,
      related: model.related ?? [],
    },
  };
}
/** JSON にしたときの大きさが maxBytes 以下になるように配列を分ける。 */
export function chunkItems(items, maxBytes = 40000) {
  const parts = [];
  let cur = [], size = 2;
  for (const item of items) {
    const n = Buffer.byteLength(JSON.stringify(item)) + 1;
    if (cur.length && size + n > maxBytes) { parts.push(cur); cur = []; size = 2; }
    cur.push(item); size += n;
  }
  parts.push(cur);
  return parts;
}
/** 文字列を maxBytes（JSON にしたときの概算）以下の断片に分ける。制御文字は呼び出し側で除いておく。 */
export function chunkText(text, maxBytes = 40000) {
  const parts = [];
  let cur = '', size = 0;
  for (const ch of String(text)) {
    const n = Buffer.byteLength(ch) + (ch === '"' || ch === '\\' || ch === '\n' || ch === '\t' ? 1 : 0);
    if (size + n > maxBytes) { parts.push(cur); cur = ''; size = 0; }
    cur += ch; size += n;
  }
  parts.push(cur);
  return parts;
}
export const stripControl = (s) => String(s).replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/g, '');

// ---- 帯・パネル（静的 HTML） --------------------------------------------------------------------------

const BASE_CSS = 'body{margin:0;font:13px/1.6 system-ui;background:var(--soda-bg);color:var(--soda-fg)}main{padding:8px 12px}h1{font-size:15px;margin:0 0 6px}table{border-collapse:collapse;width:100%}th,td{text-align:left;padding:2px 8px 2px 0;border-bottom:1px solid rgba(128,128,128,.3);overflow-wrap:anywhere}small,.muted{opacity:.7}';

export function summaryLine(model) {
  const s = summarize(model);
  const parts = [`監督: ${STATUS_LABEL[s.supervisor] ?? s.supervisor}`, `進行中 ${s.active} 件`];
  if (s.current) parts.push(`現在: ${s.current.slug}${s.current.phase ? `（${s.current.phase}）` : ''}`);
  parts.push(`担当 作業中 ${s.working}・承認待ち ${s.blocked}`);
  if (s.questions) parts.push(`質問 ${s.questions}`);
  return parts.join(' · ');
}
export function bandHtml(model) {
  const line = model.available ? summaryLine(model) : '.aidev が見つかりません';
  return `<style>${BASE_CSS}</style><main><strong>aidev</strong> <span>${esc(line)}</span></main>`;
}

/** スクリプトの面が出せないとき（設定が無効）の、読むだけの画面。 */
export function staticHtml(model, note = '') {
  const active = model.works.filter((w) => w.state === 'active').slice(0, 50);
  const rows = active.map((w) => `<tr><td>${w.isCurrent ? '● ' : ''}${esc(w.slug)}</td><td>${esc(w.current)}${w.next ? ` → ${esc(w.next)}` : ''}</td><td>${w.tasks.done}/${w.tasks.total}</td><td>${esc(STATUS_LABEL[w.worker?.status ?? 'none'])}</td></tr>`).join('');
  const log = model.log.slice(0, 10).map((e) => `<li><small>${esc(e.at)} [${esc(FROM_LABEL[e.from] ?? e.from)}]</small> ${esc(plain(e.message, 200))}</li>`).join('');
  return `<style>${BASE_CSS}</style><main><h1>aidev · ${esc(model.project)}</h1>${note ? `<p role="status">${esc(note)}</p>` : ''}<p>${esc(summaryLine(model))}</p>`
    + `<table><thead><tr><th>作業</th><th>工程</th><th>tasks</th><th>担当</th></tr></thead><tbody>${rows}</tbody></table><h2>最近のログ</h2><ul>${log}</ul></main>`;
}

// ---- 端末版（Markdown） -------------------------------------------------------------------------------

// 端末版 Markdown に入る信頼できない文字: HTML と、リンク・画像の記法（クリックできる形にしない）を無効にする
const md = (s, n) => plain(s, n).replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/[[\]()!]/g, '\\$&');
const cell = (s) => md(s, 60).replace(/\|/g, '\\|').replace(/`/g, "'");
export function terminalMarkdown(model) {
  if (!model.available) return `# aidev — ${plain(model.project, 60)}\n\n.aidev が見つかりません。\n`;
  const sup = model.supervisor;
  const lines = [`# aidev — ${plain(model.project, 60)}`, '', `- ${summaryLine(model)}`];
  if (sup) lines.push(`- 監督: \`${plain(sup.name, 40)}\` セッション \`${plain(sup.sessionId, 36)}\``);
  lines.push('', '| 作業 | 工程 | 次 | tasks | 担当 |', '|---|---|---|---|---|');
  for (const w of model.works.filter((x) => x.state === 'active').slice(-30).reverse()) {
    lines.push(`| ${w.isCurrent ? '● ' : ''}${cell(w.slug)} | ${cell(w.current)} | ${cell(w.next)} | ${w.tasks.done}/${w.tasks.total} | ${STATUS_LABEL[w.worker?.status ?? 'none']} |`);
  }
  lines.push('', '## 最近のログ', '');
  for (const e of model.log.slice(0, 10)) lines.push(`- ${plain(e.at, 40)} [${FROM_LABEL[e.from] ?? e.from}${e.slug ? `:${plain(e.slug, 40)}` : ''}${e.level === 'question' ? '・質問' : ''}] ${md(e.message, 160)}`);
  return lines.join('\n') + '\n';
}

// ---- アプリ画面（script-html） ------------------------------------------------------------------------

const APP_CSS = String.raw`
[hidden]{display:none!important}*{box-sizing:border-box}
body{margin:0;background:var(--soda-bg);color:var(--soda-fg);font:14px/1.6 system-ui}
main{padding:12px 16px;max-width:1200px;margin:auto}
h1{font-size:18px;margin:0}h2{font-size:15px;margin:16px 0 6px;border-bottom:1px solid rgba(128,128,128,.35);padding-bottom:2px}h3{font-size:14px;margin:10px 0 4px}
button,input,select,textarea{font:inherit;color:inherit;background:rgba(128,128,128,.12);border:1px solid rgba(128,128,128,.45);border-radius:4px;padding:4px 10px}
button{cursor:pointer;min-height:32px}button:disabled{opacity:.45;cursor:default}
textarea{width:100%;min-height:64px;resize:vertical}
.row{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:6px 0}
.muted,small{opacity:.72}
.badge{display:inline-block;padding:0 8px;border-radius:10px;border:1px solid rgba(128,128,128,.5);font-size:12px;white-space:nowrap}
.badge.working{background:rgba(60,160,60,.25)}.badge.blocked,.badge.question{background:rgba(230,150,0,.3)}.badge.failed,.badge.error{background:rgba(220,50,50,.3)}.badge.idle,.badge.starting{background:rgba(70,130,220,.25)}
.cols{display:grid;grid-template-columns:1fr;gap:0 24px}@media(min-width:960px){.cols{grid-template-columns:minmax(0,1fr) minmax(0,1.2fr)}}
.work{display:block;width:100%;text-align:left;margin:3px 0;padding:6px 10px}
.work.sel{border-color:currentColor;border-width:2px}
.work .slug{font-weight:600;overflow-wrap:anywhere}
.phases{display:flex;flex-wrap:wrap;gap:4px;margin:6px 0}
.phase{padding:0 8px;border:1px solid rgba(128,128,128,.5);border-radius:4px;font-size:12px}
.phase.approved{background:rgba(60,160,60,.25)}.phase.current{border-width:2px;font-weight:700;background:rgba(70,130,220,.25)}.phase.dim{opacity:.4}
.log{margin:0;padding:0;list-style:none}.log li{padding:3px 0;border-bottom:1px solid rgba(128,128,128,.2);overflow-wrap:anywhere}.log li.question{background:rgba(230,150,0,.18);border-left:4px solid rgba(230,150,0,.9);padding-left:8px}.log li.warn,.log li.error{border-left:4px solid rgba(220,50,50,.8);padding-left:8px}
.doc{border:1px solid rgba(128,128,128,.35);border-radius:4px;padding:8px 12px;max-height:60vh;overflow:auto}
.doc h4{margin:8px 0 2px}.doc p{margin:2px 0;overflow-wrap:anywhere}.doc pre{margin:2px 0;font:12px/1.5 ui-monospace,monospace;white-space:pre-wrap;overflow-wrap:anywhere}.doc .li{padding-left:1.2em;text-indent:-1em;overflow-wrap:anywhere}
.term{height:320px;width:100%;margin:6px 0}.term.tall{height:400px}.rel{border:1px solid rgba(128,128,128,.35);border-radius:4px;padding:6px 8px;margin:4px 0}.rel .row{margin:2px 0}.rel input.relp{flex:1;min-width:8em}
dl{margin:0;display:grid;grid-template-columns:max-content 1fr;gap:0 12px}dd{margin:0;overflow-wrap:anywhere}
input.sid{width:100%;font:12px ui-monospace,monospace}
progress{width:90px;vertical-align:middle}
.err{color:inherit;border-left:4px solid rgba(220,50,50,.8);padding-left:8px}
`;

const APP_BODY = String.raw`
<main id="app">
<header>
 <h1 id="project">aidev</h1>
 <div id="top"></div>
 <div class="row">
  <button id="b-sup-start" type="button">監督を起動</button>
  <button id="b-sup-resume" type="button">監督を再開</button>
  <button id="b-sup-fresh" type="button" title="再開できる会話があっても、新しい会話で始める（前の会話の ID は台帳に残す）">新しい会話で始める</button>
  <button id="b-refresh" type="button">読み直す</button>
  <label>種類 <select id="sup-kind"><option value="">既定</option></select></label>
  <label>モデル <input id="sup-model" maxlength="64" placeholder="既定"></label>
 </div>
 <details id="sup-term-box" open><summary>監督の端末（ここで直接操作できます）</summary>
  <p id="term-sup-note" class="muted"></p><div id="term-sup" class="term"></div></details>
 <details id="settings"><summary>設定（モデル・権限のモード・自動起動）</summary>
  <div class="row"><label>エージェントの起動先 <select id="s-execution"><option value="server">接続先PC（従来）</option><option value="operator">操作元PC（Claude Code / Codex）</option></select></label></div><p class="muted">操作元では起動確認が表示されます。ファイル・スキル・テストは接続先、質問は操作元です。モデルは空にし、権限は専用MCPに固定されます。端末埋め込み・自動終了・会話再開・グラフ連携は接続先モードの機能です。</p>
  <div class="row"><label>監督のモデル <input id="s-supmodel" maxlength="64" placeholder="空なら指定しない"></label>
  <label>担当のモデル <input id="s-wmodel" maxlength="64" placeholder="空なら指定しない"></label></div>
  <p id="kinds-note" class="muted"></p>
  <div class="row"><label>監督の種類 <select id="s-supkind"></select></label>
  <label>担当の種類 <select id="s-wkind"></select></label>
  <label>Codex の権限 <select id="s-codexperm"><option value="">指定しない</option><option value="read-only">read-only（承認は必要時）</option><option value="workspace-write">workspace-write（承認は必要時）</option><option value="workspace-write-never">workspace-write（承認しない）</option></select></label></div>
  <div class="row"><label>権限のモード（Claude Code） <select id="s-perm"><option value="">指定しない</option><option value="default">default</option><option value="acceptEdits">acceptEdits</option><option value="auto">auto</option><option value="plan">plan</option></select></label>
  <label><input id="s-auto" type="checkbox"> アプリを開いたとき監督を自動で起動・再開する</label>
  <label><input id="s-exit" type="checkbox"> 作業が完了したら、担当と関連するエージェントを終了する（会話 ID は記録。再開できる）</label>
  <button id="b-settings" type="button">設定を保存</button></div>
 </details>
</header>
<section id="notice" role="status" hidden></section>
<section>
 <h2>監督への指示</h2>
 <textarea id="sup-text" maxlength="16000" placeholder="監督への指示（Ctrl+Enter で送る）"></textarea>
 <div class="row"><button id="b-send" type="button">送る</button>
  <button class="quick" type="button" data-text="状況をまとめて">状況をまとめて</button>
  <button class="quick" type="button" data-text="次に進めるべき作業を提案して">次に進めるべき作業を提案して</button>
  <button class="quick" type="button" data-text="backlog から次の作業を始めて">backlog から次の作業を始めて</button></div>
</section>
<section><h2>ログ</h2><ul id="log" class="log"></ul></section>
<div class="cols">
 <section>
  <h2>作業 <small id="works-count"></small></h2>
  <div class="row"><button id="f-active" type="button">進行中</button><button id="f-all" type="button">すべて</button></div>
  <div id="works"></div>
 </section>
 <section id="detail-box" hidden>
  <h2 id="d-title"></h2>
  <div id="d-head"></div>
  <div id="d-phases" class="phases"></div>
  <h3>担当</h3>
  <div id="w-status"></div>
  <textarea id="w-text" maxlength="16000" placeholder="担当への指示"></textarea>
  <div class="row">
   <button id="w-start" type="button">担当を起動</button><button id="w-resume" type="button">再開</button>
   <button id="w-fresh" type="button" title="再開できる会話があっても、新しい会話で始める">新しい会話で始める</button>
   <button id="w-send" type="button">指示を送る</button>
   <button id="w-delegate" type="button">監督に任せる</button>
   <label>種類 <select id="w-kind"><option value="">既定</option></select></label>
   <label>モデル <input id="w-model" maxlength="64" placeholder="既定"></label></div>
  <details id="w-term-box" open><summary>担当の端末（ここで直接操作できます）</summary>
   <p id="term-w-note" class="muted"></p><div id="term-w" class="term tall"></div></details>
  <h3>関連するエージェント <small id="d-related-count"></small></h3>
  <p class="muted">担当が <code>sodactl</code> で起こしたエージェントです（担当の pane から起こすと自動で並びます）。</p>
  <div id="d-related"></div><div id="term-rel"></div>
  <h3>state</h3><dl id="d-values"></dl>
  <h3>tasks <small id="d-taskcount"></small></h3><ul id="d-tasks" class="log"></ul>
  <h3>文書</h3><div id="d-docs" class="row"></div><div id="d-doc" class="doc" hidden></div>
  <h3>events（新しい順）</h3><div id="d-events"></div>
 </section>
</div>
<section><h2>backlog</h2><div id="backlog"></div></section>
</main>`;

const APP_SCRIPT = String.raw`
(function () {
  'use strict';
  var STATUS = { none: '未起動', starting: '起動中', working: '作業中', idle: '待機', blocked: '承認待ち', stopped: '停止（再開できる）', failed: '失敗' };
  var FROM = { user: '利用者', supervisor: '監督', worker: '担当', app: 'アプリ' };
  var S = { st: null, works: [], workers: [], backlog: [], related: [], relTerm: {}, mountFail: {}, filter: 'active', limit: 100, sel: null, detail: null, tasks: [], events: [], docName: null, docText: '', docTrunc: false, gens: {}, bufs: {}, mounted: {}, dirty: false };
  var $ = function (id) { return document.getElementById(id); };
  function clear(e) { while (e.firstChild) e.removeChild(e.firstChild); return e; }
  function h(tag, props, kids) {
    var e = document.createElement(tag);
    for (var k in (props || {})) {
      var v = props[k];
      if (v === false || v == null) continue;
      if (k === 'class') e.className = v; else if (k === 'text') e.textContent = v;
      else if (k.slice(0, 2) === 'on') e.addEventListener(k.slice(2), v); else e.setAttribute(k, v);
    }
    (kids || []).forEach(function (c) { if (c != null) e.appendChild(typeof c === 'string' ? document.createTextNode(c) : c); });
    return e;
  }
  // 画面からの操作の値は 8 KiB（JSON）まで。超える指示は黙って捨てず、知らせる
  function tooLong(text) { try { return new TextEncoder().encode(text).length > 6000; } catch (e) { return text.length > 2000; } }
  function act(name, data) {
    var d = {};
    for (var k in (data || {})) d[k] = String(data[k]);
    var ok = true;
    try { ok = soda.action(name, d) !== false; } catch (e) { ok = false; }
    if (!ok) notice('warn', '送れませんでした。指示が長すぎる可能性があります（画面からは 6000 バイトまで。長い指示は sodactl plugin call を使ってください）');
    return ok;
  }
  function badge(status) { return h('span', { class: 'badge ' + status, text: STATUS[status] || status }); }
  function when(s) { return s ? String(s).replace('T', ' ').replace(/\.\d+Z$/, 'Z').slice(0, 19) : ''; }
  function notice(level, text) {
    var n = $('notice');
    n.hidden = !text; n.className = 'badge ' + (level || 'info'); n.textContent = text || '';
    n.style.whiteSpace = 'normal'; n.style.display = text ? 'block' : 'none';
  }
  function supAlive() { var s = S.st && S.st.supervisor; return !!(s && s.alive); }
  function workerOf(slug) { for (var i = 0; i < S.workers.length; i++) if (S.workers[i].slug === slug) return S.workers[i]; return null; }

  function copyButton(value) {
    return h('button', { type: 'button', text: 'コピー', onclick: function () {
      var done = function () { notice('info', 'セッション ID をコピーしました'); };
      try { navigator.clipboard.writeText(value).then(done, function () { notice('warn', 'コピーできませんでした。欄を選んで Ctrl+C を使ってください'); }); }
      catch (e) { notice('warn', 'コピーできませんでした。欄を選んで Ctrl+C を使ってください'); }
    } });
  }
  var KIND_LABELS = { claude: 'Claude Code', codex: 'Codex', copilot: 'Copilot CLI', bob: 'Bob Shell' };
  function kindLabel(k) { return KIND_LABELS[k] || String(k || ''); }
  // 種類の選択肢は、設定「エージェント連携」で導入済みのものだけ。保存済みの種類が未導入なら、理由を添えて無効で残す
  function fillKinds(sel, st, blank, current) {
    var kinds = st.kinds || { available: ['claude', 'codex'], details: {} }, key = kinds.available.join(',') + '|' + blank + '|' + current + '|' + JSON.stringify(kinds.details);
    if (sel.getAttribute('data-kinds') === key) return;
    var keep = sel.value; clear(sel);
    if (blank) sel.appendChild(h('option', { value: '', text: '既定' }));
    kinds.available.forEach(function (k) {
      var d = (kinds.details || {})[k] || {};
      sel.appendChild(h('option', { value: k, text: kindLabel(k) + (d.needsUpdate ? '（更新が必要）' : '') }));
    });
    if (current && kinds.available.indexOf(current) < 0) sel.appendChild(h('option', { value: current, disabled: 'disabled', text: kindLabel(current) + '（未導入）' }));
    sel.setAttribute('data-kinds', key);
    if (keep) sel.value = keep;
  }
  function kindsNote(k) {
    if (!k) return '';
    if(k.operator)return '操作元のClaude Code / Codexを使います。導入・ログインは操作元で確認します。';
    if (k.legacy) return '古いサーバのため、選べる種類は Claude Code と Codex だけです。';
    if (k.unreadable) return '導入状況を読めませんでした（' + (k.reason || '理由不明') + '）。Claude Code と Codex だけ選べます。';
    var extra = (k.available || []).filter(function (x) { return x !== 'claude' && x !== 'codex'; });
    return extra.length ? 'Sodashitsu の設定「エージェント連携」で導入済みの種類だけ選べます。'
      : '導入済みの追加の種類がありません（Copilot CLI・Bob Shell は、設定「エージェント連携」で導入すると選べます）。';
  }
  function renderKinds(st) {
    fillKinds($('sup-kind'), st, true, ''); fillKinds($('w-kind'), st, true, '');
    fillKinds($('s-supkind'), st, false, st.settings.supervisorKind || 'claude'); fillKinds($('s-wkind'), st, false, st.settings.workerKind || 'claude');
    $('kinds-note').textContent = kindsNote(st.kinds);
  }
  function agentBlock(a, label) {
    var box = h('div', null, []);
    if (!a) { box.appendChild(h('p', { class: 'muted', text: label + ': 記録なし' })); return box; }
    var head = h('div', { class: 'row' }, [h('strong', { text: label }), a.execution==='operator'&&a.status==='stopped'?h('span',{class:'badge',text:'停止・接続要確認'}):badge(a.status), h('small', { text: a.name + ' · ' + kindLabel(a.kind) })]);
    box.appendChild(head);
    if(a.execution==='operator')box.appendChild(h('p',{class:'muted',text:'操作元PC · '+(a.operatorWaiting?'起動の承認待ち':'担当の状態は操作元から取得')+(a.taskStatus?.instruction?' · 追加指示: '+a.taskStatus.instruction.state:'')}));
    if (a.sessionPending) box.appendChild(h('p', { class: 'muted', text: '会話 ID はまだ取得できていません（起動後に払い出されたものを自動で記録します。取得できるまで再開はできません）' }));
    if (a.sessionId) box.appendChild(h('div', { class: 'row' }, [h('small', { text: 'セッション ' + a.sessionId.slice(0, 8) }), h('input', { class: 'sid', readonly: 'readonly', value: a.sessionId, 'aria-label': 'セッション ID の全体', onclick: function (ev) { ev.target.select(); } }), copyButton(a.sessionId)]));
    if (a.error) box.appendChild(h('p', { class: 'err', text: a.error }));
    if (a.pending && a.pending.length) box.appendChild(h('p', { class: 'muted', text: '役割・線がまだ届いていません（承認などの確認に答えると、待機になった時点で自動で届けます。［起動］を押し直しても届きます）' }));
    if (a.previousSessions) box.appendChild(h('small', { text: '以前の会話 ' + a.previousSessions + ' 件を台帳に記録' }));
    if (a.startedAt) box.appendChild(h('small', { text: '起動 ' + when(a.startedAt) + (a.resumedAt ? ' / 再開 ' + when(a.resumedAt) : '') + (a.model ? ' / モデル ' + a.model : '') }));
    return box;
  }

  function renderTop() {
    var st = S.st; if (!st) return;
    renderKinds(st);
    $('project').textContent = 'aidev · ' + st.project;
    var top = clear($('top'));
    if (!st.available) top.appendChild(h('p', { class: 'err', text: '.aidev が見つかりません。aidev を始めた PJ で開いてください。' }));
    else top.appendChild(h('p', { class: 'muted', text: '進行中 ' + st.summary.active + ' 件 · 全 ' + st.total + ' 件' + (st.truncated ? '（新しい 1000 件まで）' : '') + (st.current ? ' · 現在: ' + st.current : '') + (st.cli ? '' : ' · aidev CLI なし（next は空）') }));
    top.appendChild(agentBlock(st.supervisor, '監督'));
    var sup = st.supervisor, alive = !!(sup && sup.alive);
    var supPending = alive && sup.pending && sup.pending.length > 0;
    $('b-sup-start').textContent = supPending ? '役割を届ける' : '監督を起動';
    $('b-sup-start').disabled = (alive && !supPending) || !!(sup && sup.resumable);
    $('b-sup-resume').disabled = alive || !(sup && sup.resumable);
    $('b-sup-fresh').disabled = alive || !!sup?.operatorWaiting || !sup;
    $('b-send').disabled = !alive;
    syncTerm('sup', $('term-sup'), alive && sup.execution!=='operator' ? sup.paneId : null, $('term-sup-note'), sup && sup.execution==='operator' ? '操作元の作業ペインで直接操作してください。起動待ちは操作元で承認してください。' : '監督が動いていません。起動すると、ここに端末が出ます。');
    if (!S.dirty) {
      $('s-execution').value=st.settings.execution||'server';
      $('s-supmodel').value = st.settings.supervisorModel || ''; $('s-wmodel').value = st.settings.workerModel || '';
      $('s-perm').value = st.settings.permissionMode || ''; $('s-auto').checked = st.settings.autoStartSupervisor !== false;
      $('s-exit').checked = st.settings.exitOnDone !== false;
      $('s-supkind').value = st.settings.supervisorKind || 'claude'; $('s-wkind').value = st.settings.workerKind || 'claude'; $('s-codexperm').value = st.settings.codexPermission || '';
    }
  }
  function renderLog() {
    var ul = clear($('log')), log = (S.st && S.st.log) || [];
    if (!log.length) { ul.appendChild(h('li', { class: 'muted', text: 'まだ記録はありません' })); return; }
    log.forEach(function (e) {
      var cls = e.level === 'question' ? 'question' : e.level === 'warn' || e.kind === 'error' ? 'warn' : '';
      var who = (FROM[e.from] || e.from) + (e.slug ? ':' + e.slug : '');
      ul.appendChild(h('li', { class: cls }, [h('small', { text: when(e.at) + ' [' + who + (e.kind === 'instruction' ? ' への指示' : e.kind === 'report' ? ' の報告' : '') + (e.level === 'question' ? '・質問' : '') + '] ' }), document.createTextNode(e.message)]));
    });
  }
  function renderWorks() {
    var box = clear($('works'));
    var list = S.works.filter(function (w) { return S.filter === 'all' || w.state === 'active'; }).slice().sort(function (a, b) { return a.slug < b.slug ? 1 : -1; });
    $('works-count').textContent = list.length + ' 件';
    $('f-active').setAttribute('aria-pressed', String(S.filter === 'active')); $('f-all').setAttribute('aria-pressed', String(S.filter === 'all'));
    if (!list.length) box.appendChild(h('p', { class: 'muted', text: '該当する作業はありません' }));
    list.slice(0, S.limit).forEach(function (w) {
      var line1 = [h('span', { class: 'slug', text: (w.isCurrent ? '● ' : '') + w.slug })];
      if (w.state !== 'active') line1.push(h('span', { class: 'badge', text: { done: '完了', abandoned: '廃止', broken: 'state なし' }[w.state] || w.state }));
      if (w.ws && w.ws !== 'none') line1.push(badge(w.ws));
      var line2 = [(w.current || '-') + ' → ' + (w.next || '-') + ' · ' + (w.mode || '-') + (w.profile ? '/' + w.profile : '') + ' · tasks ' + w.tasks.done + '/' + w.tasks.total + ' ', h('progress', { max: String(Math.max(1, w.tasks.total)), value: String(w.tasks.done) })];
      if (w.deps && w.deps !== 'ok') line2.push(h('span', { class: 'badge warn', text: '⚠ ' + w.deps }));
      box.appendChild(h('button', { type: 'button', class: 'work' + (S.sel === w.slug ? ' sel' : ''), onclick: function () { select(w.slug); } }, [h('div', null, line1), h('small', null, line2)]));
    });
    if (list.length > S.limit) box.appendChild(h('button', { type: 'button', text: 'さらに表示（残り ' + (list.length - S.limit) + ' 件）', onclick: function () { S.limit += 100; renderWorks(); } }));
  }
  function select(slug) { S.sel = slug; S.detail = null; S.tasks = []; S.events = []; S.docName = null; S.docText = ''; renderWorks(); renderDetail(); act('select', { slug: slug }); }

  function renderDetail() {
    var box = $('detail-box'); box.hidden = !S.sel;
    if (!S.sel) { syncTerm('w', $('term-w'), null); renderRelated(); return; }
    $('d-title').textContent = S.sel;
    var d = S.detail && S.detail.slug === S.sel ? S.detail : null;
    var head = clear($('d-head')), ph = clear($('d-phases'));
    if (d) {
      head.appendChild(h('p', { class: 'muted', text: (d.state === 'active' ? '進行中' : d.state === 'done' ? '完了' : d.state === 'abandoned' ? '廃止' : 'state.yml なし') + ' · mode ' + (d.mode || '-') + ' · profile ' + (d.profile || '-') + (d.dependsOn && d.dependsOn.length ? ' · 依存 ' + d.dependsOn.join(', ') : '') }));
      d.phases.forEach(function (p) { ph.appendChild(h('span', { class: 'phase ' + p.status + (p.dim ? ' dim' : ''), text: p.phase + (p.hasDoc ? ' 📄' : '') })); });
    } else head.appendChild(h('p', { class: 'muted', text: '読み込み中…' }));
    var dl = clear($('d-values'));
    if (d) Object.keys(d.values || {}).forEach(function (k) { var v = d.values[k]; dl.appendChild(h('dt', { text: k })); dl.appendChild(h('dd', { text: Array.isArray(v) ? '[' + v.join(', ') + ']' : String(v) })); });
    var tl = clear($('d-tasks'));
    $('d-taskcount').textContent = d ? d.tasks.done + '/' + d.tasks.total : '';
    S.tasks.forEach(function (t) { tl.appendChild(h('li', { text: (t.done ? '☑ ' : '☐ ') + t.text })); });
    var docs = clear($('d-docs'));
    if (d) d.docs.forEach(function (f) { docs.appendChild(h('button', { type: 'button', class: S.docName === f.name ? 'sel' : '', text: f.name, onclick: function () { S.docName = f.name; S.docText = ''; renderDoc(); act('doc', { slug: S.sel, name: f.name }); } })); });
    renderDoc();
    var ev = clear($('d-events'));
    if (!S.events.length) ev.appendChild(h('p', { class: 'muted', text: 'events はありません' }));
    else { var tb = h('table'); S.events.forEach(function (e) { tb.appendChild(h('tr', null, [h('td', { text: when(e.ts) }), h('td', { text: e.phase }), h('td', { text: e.event }), h('td', { text: e.note })])); }); ev.appendChild(tb); }
    renderWorker();
  }
  function renderDoc() {
    var box = $('d-doc'); box.hidden = !S.docName; if (!S.docName) return;
    clear(box);
    if (!S.docText) { box.appendChild(h('p', { class: 'muted', text: '読み込み中…' })); return; }
    var FENCE = String.fromCharCode(96, 96, 96), inCode = false, pre = null;
    S.docText.split('\n').forEach(function (line) {
      if (line.replace(/^\s+/, '').indexOf(FENCE) === 0) { inCode = !inCode; pre = null; return; }
      if (inCode) { if (!pre) { pre = h('pre'); box.appendChild(pre); } pre.textContent += line + '\n'; return; }
      var m = /^(#{1,6})\s+(.*)$/.exec(line);
      if (m) box.appendChild(h('h4', { text: m[2] }));
      else if (/^\s*[-*]\s+/.test(line) || /^\s*\d+\.\s+/.test(line)) box.appendChild(h('div', { class: 'li', text: '・' + line.replace(/^\s*([-*]|\d+\.)\s+/, '') }));
      else if (/^\s*\|/.test(line)) box.appendChild(h('pre', { text: line }));
      else if (line.trim()) box.appendChild(h('p', { text: line }));
    });
    if (S.docTrunc) box.appendChild(h('p', { class: 'muted', text: '（512 KiB で切りました）' }));
  }
  function renderWorker() {
    var slug = S.sel; if (!slug) return;
    var w = workerOf(slug), box = clear($('w-status'));
    box.appendChild(agentBlock(w, '担当'));
    if (w && w.lastReport) box.appendChild(h('p', { text: '最後の報告 [' + w.lastReport.status + '] ' + when(w.lastReport.at) + ' ' + w.lastReport.message }));
    (w && w.linkErrors || []).forEach(function (e) { box.appendChild(h('p', { class: 'err', text: e })); });
    var alive = !!(w && w.alive), sup = supAlive();
    var wPending = alive && w.pending && w.pending.length > 0;
    $('w-start').textContent = wPending ? '役割と線を届ける' : '担当を起動';
    $('w-start').disabled = (alive && !wPending) || !sup || !!(w && w.resumable);
    $('w-fresh').disabled = alive || !!w?.operatorWaiting || !sup || !w;
    $('w-resume').disabled = alive || !sup || !(w && w.resumable);
    $('w-send').disabled = !alive;
    $('w-delegate').disabled = !sup;
    syncTerm('w', $('term-w'), alive && w.execution!=='operator' ? w.paneId : null, $('term-w-note'), w && w.execution==='operator' ? '操作元の作業ペインで直接操作してください。' : alive ? '' : '担当が動いていません。起動（または再開）すると、ここに端末が出ます。');
    renderRelated();
  }
  function renderRelated() {
    var list = S.related.filter(function (a) { return a.slug === S.sel; });
    $('d-related-count').textContent = S.sel ? list.length + ' 件' : '';
    var box = clear($('d-related'));
    if (!list.length) box.appendChild(h('p', { class: 'muted', text: '関連するエージェントはありません' }));
    list.forEach(function (a) {
      var input = h('input', { class: 'relp', maxlength: '2000', placeholder: 'このエージェントへの指示' });
      var send = h('button', { type: 'button', text: '送る', onclick: function () {
        var t = input.value.trim(); if (!t) return;
        if (tooLong(t)) { notice('warn', '指示が長すぎます（6000 バイトまで）'); return; }
        if (act('work-agent-prompt', { slug: a.slug, paneId: a.paneId, text: t })) input.value = '';
      } });
      input.addEventListener('keydown', function (e) { if (e.key === 'Enter' && !e.isComposing) { e.preventDefault(); send.click(); } });
      box.appendChild(h('div', { class: 'rel' }, [
        h('div', { class: 'row' }, [badge(a.status), h('strong', { text: kindLabel(a.kind) }), h('small', { text: (a.label ? a.label + ' · ' : '') + 'pane ' + a.paneId.slice(0, 8) + (a.depth > 1 ? ' · 孫' : '') + (a.registered ? ' · 登録' : '') }),
          h('button', { type: 'button', text: S.relTerm[a.paneId] ? '端末を閉じる' : '端末を表示', onclick: function () { S.relTerm[a.paneId] = !S.relTerm[a.paneId]; syncRelTerms(); renderRelated(); } })]),
        h('div', { class: 'row' }, [input, send]),
      ]));
    });
    syncRelTerms();
  }
  // 関連するエージェントの端末は、描き直しで消えないよう、固定の入れ物（#term-rel）の中に置く
  function syncRelTerms() {
    var host = $('term-rel'), want = {};
    S.related.forEach(function (a) { if (a.slug === S.sel && S.relTerm[a.paneId]) want[a.paneId] = true; });
    Object.keys(S.mounted).forEach(function (k) { if (k.indexOf('r:') === 0 && !want[k.slice(2)]) { syncTerm(k, null, null); } });
    Array.prototype.slice.call(host.children).forEach(function (c) { if (!want[c.getAttribute('data-pane')]) host.removeChild(c); });
    Object.keys(want).forEach(function (id) {
      var slot = null;
      Array.prototype.forEach.call(host.children, function (c) { if (c.getAttribute('data-pane') === id) slot = c; });
      if (!slot) { slot = h('div', { class: 'term', 'data-pane': id }); host.appendChild(slot); }
      syncTerm('r:' + id, slot, id, null, '');
    });
  }
  function renderBacklog() {
    var box = clear($('backlog'));
    if (!S.backlog.length) { box.appendChild(h('p', { class: 'muted', text: 'backlog はありません' })); return; }
    S.backlog.forEach(function (b) {
      var det = h('details', null, [h('summary', { text: b.file + '（未着手 ' + b.todo + ' / 完了 ' + b.done + '）' })]);
      var ul = h('ul', { class: 'log' });
      b.items.forEach(function (t) { ul.appendChild(h('li', { text: '☐ ' + t })); });
      if (b.todo > b.items.length) ul.appendChild(h('li', { class: 'muted', text: '…ほか ' + (b.todo - b.items.length) + ' 件' }));
      det.appendChild(ul); box.appendChild(det);
    });
  }
  function renderAll() { renderTop(); renderLog(); renderWorks(); renderBacklog(); renderDetail(); }

  // 端末は同時に 4 つまで（監督・担当・関連 2）。pane が変わったときだけ付け直す。box が null なら外すだけ
  function mountedCount() { return Object.keys(S.mounted).length; }
  function syncTerm(key, box, paneId, note, idleText) {
    var cur = S.mounted[key];
    if (cur && cur.paneId === paneId) return;
    if (cur) {
      try { cur.handle.dispose(); } catch (e) { /* 無視 */ }
      delete S.mounted[key];
      if (cur.box) clear(cur.box);
    }
    if (note) note.textContent = '';
    if (!paneId || !box) { if (note && idleText) note.textContent = idleText; return; }
    if (typeof soda.mount !== 'function') { if (note) note.textContent = 'この環境では端末を埋め込めません。作業画面で操作してください。'; return; }
    var failKey = key + ':' + paneId;
    if (S.mountFail[failKey]) { if (note) note.textContent = '端末を表示できませんでした。作業画面で操作してください。'; return; }
    if (mountedCount() >= 4) { notice('warn', '端末は同時に 4 つまでです。関連するエージェントの端末を閉じてください'); return; }
    clear(box);
    var handle = soda.mount('terminal', box, { paneId: paneId, interactive: true });
    if (!handle) { S.mountFail[failKey] = true; if (note) note.textContent = '端末を表示できませんでした。作業画面で操作してください。'; return; }
    S.mounted[key] = { paneId: paneId, handle: handle, box: box };
  }

  function collect(m) {
    var key = m.name + ':' + (m.key || '');
    if (S.gens[key] !== m.gen) { S.gens[key] = m.gen; S.bufs[key] = []; }
    S.bufs[key][m.part] = m.items;
    for (var i = 0; i < m.parts; i++) if (!S.bufs[key][i]) return;
    var all = [].concat.apply([], S.bufs[key]);
    if (m.name === 'works') { S.works = all; renderWorks(); }
    else if (m.name === 'workers') { S.workers = all; renderWorks(); renderWorker(); }
    else if (m.name === 'backlog') { S.backlog = all; renderBacklog(); }
    else if (m.name === 'related') { S.related = all; renderRelated(); }
    else if (m.name === 'tasks' && m.key === S.sel) { S.tasks = all; renderDetail(); }
    else if (m.name === 'events' && m.key === S.sel) { S.events = all; renderDetail(); }
  }
  soda.onMessage(function (m) {
    if (!m || typeof m !== 'object') return;
    if (m.type === 'state') { S.st = m.state; renderTop(); renderLog(); renderWorker(); }
    else if (m.type === 'list') collect(m);
    else if (m.type === 'detail') { if (m.detail && m.detail.slug === S.sel) { S.detail = m.detail; renderDetail(); } }
    else if (m.type === 'doc') {
      if (m.slug !== S.sel || m.name !== S.docName) return;
      var key = 'doc:' + m.name;
      if (S.gens[key] !== m.gen) { S.gens[key] = m.gen; S.bufs[key] = []; }
      S.bufs[key][m.part] = m.text;
      for (var i = 0; i < m.parts; i++) if (typeof S.bufs[key][i] !== 'string') return;
      S.docText = S.bufs[key].join('') || '（空の文書です）'; S.docTrunc = !!m.truncated; renderDoc();
    }
    else if (m.type === 'notice') notice(m.level, m.text);
  });

  function sendSupervisor(text) {
    var t = (text || '').trim();
    if (!t) return false;
    if (tooLong(t)) { notice('warn', '指示が長すぎます（画面からは 6000 バイトまで。長い指示は sodactl plugin call aidev supervisor-prompt を使ってください）'); return false; }
    return act('supervisor-prompt', { text: t });
  }
  $('b-sup-start').onclick = function () { act('supervisor-start', { kind: $('sup-kind').value, model: $('sup-model').value.trim() }); };
  $('b-sup-resume').onclick = function () { act('supervisor-resume', {}); };
  $('b-refresh').onclick = function () { act('refresh', {}); };
  $('b-send').onclick = function () { if (sendSupervisor($('sup-text').value)) $('sup-text').value = ''; };
  $('sup-text').addEventListener('keydown', function (e) { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey) && !e.isComposing) { e.preventDefault(); $('b-send').click(); } });
  Array.prototype.forEach.call(document.querySelectorAll('.quick'), function (b) { b.onclick = function () { sendSupervisor(b.getAttribute('data-text')); }; });
  ['s-execution','s-supmodel', 's-wmodel', 's-perm', 's-auto', 's-exit', 's-supkind', 's-wkind', 's-codexperm'].forEach(function (id) { $(id).addEventListener('input', function () { S.dirty = true; }); });
  $('b-settings').onclick = function () {
    act('settings-save', { execution:$('s-execution').value, supervisorModel: $('s-supmodel').value.trim(), workerModel: $('s-wmodel').value.trim(), permissionMode: $('s-perm').value, autoStartSupervisor: $('s-auto').checked, exitOnDone: $('s-exit').checked, supervisorKind: $('s-supkind').value, workerKind: $('s-wkind').value, codexPermission: $('s-codexperm').value });
    S.dirty = false;
  };
  $('b-sup-fresh').onclick = function () { act('supervisor-start', { kind: $('sup-kind').value, model: $('sup-model').value.trim(), fresh: true }); };
  $('w-fresh').onclick = function () { var t = $('w-text').value.trim(); if (tooLong(t)) { notice('warn', '指示が長すぎます（6000 バイトまで）'); return; } act('worker-start', { slug: S.sel, instruction: t, kind: $('w-kind').value, model: $('w-model').value.trim(), fresh: true }); };
  $('f-active').onclick = function () { S.filter = 'active'; renderWorks(); };
  $('f-all').onclick = function () { S.filter = 'all'; renderWorks(); };
  $('w-start').onclick = function () { var t = $('w-text').value.trim(); if (tooLong(t)) { notice('warn', '指示が長すぎます（6000 バイトまで）'); return; } act('worker-start', { slug: S.sel, instruction: t, kind: $('w-kind').value, model: $('w-model').value.trim() }); };
  $('w-resume').onclick = function () { act('worker-resume', { slug: S.sel }); };
  $('w-send').onclick = function () { var t = $('w-text').value.trim(); if (!t) return; if (tooLong(t)) { notice('warn', '指示が長すぎます（6000 バイトまで）'); return; } if (act('worker-prompt', { slug: S.sel, text: t })) $('w-text').value = ''; };
  $('w-delegate').onclick = function () { act('delegate', { slug: S.sel }); };
  $('w-text').addEventListener('keydown', function (e) { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey) && !e.isComposing) { e.preventDefault(); $('w-send').click(); } });
  act('ready', {});
})();
`;

/** 画面の本体（データを埋め込まない。同じ内容を出し続ける）。 */
export function appHtml() {
  return `<style>${APP_CSS}</style>${APP_BODY}<script>${APP_SCRIPT}</script>`;
}
