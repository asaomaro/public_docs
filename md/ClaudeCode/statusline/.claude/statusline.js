#!/usr/bin/env node
//
// Claude Code statusline script
//
// 【表示レイアウト】
//
// 1行目: モデル・セッション情報 / リソース使用状況 / コスト
//   Sonnet 4.6 | v2.1.97 | 27m53s api:25% | in:440 | out:25.7k | ctx:29% ▂ | cache:99% █ | mem:10.6G ▅ | $1.045 | $1.05 ░░░░█░░
//   ├ モデル名            input.model.display_name
//   ├ バージョン          input.version
//   ├ セッション経過時間   input.cost.total_duration_ms
//   ├ API待機率           input.cost.total_api_duration_ms / total_duration_ms（総時間のうちAPI応答待ちの割合）
//   ├ 累積inputトークン   input.context_window.total_input_tokens（セッション合計）
//   ├ 累積outputトークン  input.context_window.total_output_tokens（セッション合計）
//   ├ コンテキスト使用率  input.context_window.used_percentage（モデルの最大ウィンドウに対する割合）
//   ├ キャッシュヒット率  cache_read / (cache_read + cache_creation + input)（高いほどコスト削減効果大）
//   ├ メモリ空き容量      os.freemem() / os.totalmem()（空き容量GB・使用率で色変化）
//   ├ セッションコスト    input.cost.total_cost_usd（今セッションの累積API費用）
//   └ 週間コスト+棒グラフ ~/.claude/weekly-usage.json にキャッシュした日別コストを集計
//                         7文字のスパークライン（日月火水木金土、曜日ごとに色分け、今日はボールド）
//
// 2行目: レート制限 / 作業ディレクトリ / Git状態
//   5h:7% ▁ →02:00 | 7d:1% ░ →4/14 22:00 | git/team-task-manager | main | +234/-84
//   ├ 5時間レート制限     input.rate_limits.five_hour.used_percentage / resets_at
//   ├ 7日レート制限       input.rate_limits.seven_day.used_percentage / resets_at
//   ├ カレントディレクトリ input.workspace.current_dir（末尾2セグメント）
//   ├ Gitブランチ         git rev-parse --abbrev-ref HEAD
//   ├ コード変更量        input.cost.total_lines_added / total_lines_removed（セッション累積）
//   ├ セッション名        input.session_name（/rename で設定時のみ表示）
//   └ Vimモード           input.vim.mode（Vimモード有効時のみ表示: NORMAL / INSERT）
//
// 【色の凡例】
//   緑: 正常（0–49%）  黄: 注意（50–79%）  赤: 警告（80%+）
//   ※ mem は空き容量が少ないほど使用率が高いとみなして色変化

import { execSync } from 'child_process';
import { readFileSync, writeFileSync } from 'fs';
import { freemem, totalmem } from 'os';

function run(cmd) {
  try {
    return execSync(cmd, { encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'] }).trim();
  } catch {
    return null;
  }
}

// Read JSON input from stdin
let input = {};
try {
  const raw = readFileSync(0, 'utf8');
  input = JSON.parse(raw);
} catch {
  // Fallback: use empty object
}

// ANSI color helpers
const C = {
  blue:    s => `\x1b[34m${s}\x1b[0m`,
  magenta: s => `\x1b[35m${s}\x1b[0m`,
  yellow:  s => `\x1b[33m${s}\x1b[0m`,
  cyan:    s => `\x1b[36m${s}\x1b[0m`,
  green:   s => `\x1b[32m${s}\x1b[0m`,
  red:     s => `\x1b[31m${s}\x1b[0m`,
  dim:     s => `\x1b[2m${s}\x1b[0m`,
};

function colorPct(pct, text) {
  if (pct >= 80) return C.red(text);
  if (pct >= 50) return C.yellow(text);
  return C.green(text);
}

// 1-char level indicator (8 levels): ░▁▂▃▄▅▆▇█
const LEVEL_CHARS = ['░', '▁', '▂', '▃', '▄', '▅', '▆', '▇', '█'];
function levelChar(pct) {
  return LEVEL_CHARS[Math.round(pct / 100 * 8)];
}

// Single-char bar height from normalized ratio (0.0–1.0): ░▁▃▅▆█
function barChar(ratio) {
  if (ratio <= 0)   return '░';
  if (ratio < 0.2)  return '▁';
  if (ratio < 0.4)  return '▃';
  if (ratio < 0.6)  return '▅';
  if (ratio < 0.8)  return '▆';
  return '█';
}

function formatK(n) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000)     return `${(n / 1_000).toFixed(1)}k`;
  return `${n}`;
}

function formatDuration(ms) {
  const s = Math.floor(ms / 1000);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) return `${h}h${m}m`;
  if (m > 0) return `${m}m${sec}s`;
  return `${sec}s`;
}

function formatResetTime(unixSec) {
  const d = new Date(unixSec * 1000);
  return d.toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit', hour12: false });
}

function formatResetDate(unixSec) {
  const d = new Date(unixSec * 1000);
  const mo = d.getMonth() + 1;
  const dy = d.getDate();
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  return `${mo}/${dy} ${hh}:${mm}`;
}

function dateStr(d = new Date()) {
  return d.toISOString().slice(0, 10);
}

// ─── Weekly cost cache ───────────────────────────────────────────────────────
// セッションIDをキーにコストをキャッシュし、日別コストを集計する
// ファイル構造: { sessions: { [sessionId]: { date: "YYYY-MM-DD", cost: number } } }

const CACHE_PATH = 'C:/Users/makku/.claude/weekly-usage.json';

function loadCache() {
  try { return JSON.parse(readFileSync(CACHE_PATH, 'utf8')); }
  catch { return { sessions: {} }; }
}

function updateCache() {
  const sessionId = input.session_id;
  const cost = input.cost?.total_cost_usd;
  if (!sessionId || cost == null) return loadCache();

  const cache = loadCache();
  const today = dateStr();

  cache.sessions[sessionId] = { date: today, cost };

  // 8日以上前のエントリを削除
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - 8);
  const cutoffStr = dateStr(cutoff);
  for (const [id, entry] of Object.entries(cache.sessions)) {
    if (entry.date < cutoffStr) delete cache.sessions[id];
  }

  try { writeFileSync(CACHE_PATH, JSON.stringify(cache)); } catch {}
  return cache;
}

// 今週（日〜土）の曜日別コストを返す
function weeklyDayCosts(cache) {
  const byDate = {};
  for (const entry of Object.values(cache.sessions)) {
    byDate[entry.date] = (byDate[entry.date] || 0) + entry.cost;
  }

  const today = new Date();
  const dayOfWeek = today.getDay();
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(today);
    d.setDate(today.getDate() - dayOfWeek + i);
    return byDate[dateStr(d)] || 0;
  });
}

// 曜日の語源（惑星・元素）に対応した色: 日(黄) 月(青) 火(赤) 水(シアン) 木(緑) 金(明黄) 土(白)
const DAY_COLORS = ['\x1b[33m', '\x1b[34m', '\x1b[31m', '\x1b[36m', '\x1b[32m', '\x1b[93m', '\x1b[37m'];

function weeklySparkline(costs) {
  const maxCost = Math.max(...costs);
  const todayIdx = new Date().getDay(); // 0=Sun
  return costs.map((cost, i) => {
    const ratio = maxCost > 0 ? cost / maxCost : 0;
    const ch = barChar(ratio);
    const bold = i === todayIdx ? '\x1b[1m' : '';
    return `${DAY_COLORS[i]}${bold}${ch}\x1b[0m`;
  }).join('');
}

// ─── Build output ────────────────────────────────────────────────────────────

const cache = updateCache();
const sep = ` ${C.dim('|')} `;

// ── 1行目 ──────────────────────────────────────────────────────────────────
const parts1 = [];

// モデル名
const modelName = input.model?.display_name;
if (modelName) parts1.push(C.cyan(modelName));

// Claude Codeバージョン
const version = input.version;
if (version) parts1.push(C.dim(`v${version}`));

// セッション経過時間 + API待機率
const durationMs = input.cost?.total_duration_ms;
const apiDurationMs = input.cost?.total_api_duration_ms;
if (durationMs != null) {
  const apiRatio = (durationMs > 0 && apiDurationMs != null)
    ? ` ${C.dim(`api:${Math.round(apiDurationMs / durationMs * 100)}%`)}`
    : '';
  parts1.push(C.blue(formatDuration(durationMs)) + apiRatio);
}

// 累積inputトークン / outputトークン（セッション合計）
const totalIn  = input.context_window?.total_input_tokens;
const totalOut = input.context_window?.total_output_tokens;
if (totalIn  != null) parts1.push(C.green(`in:${formatK(totalIn)}`));
if (totalOut != null) parts1.push(C.yellow(`out:${formatK(totalOut)}`));

// コンテキストウィンドウ使用率
const ctxPct = input.context_window?.used_percentage;
if (ctxPct != null) parts1.push(colorPct(ctxPct, `ctx:${ctxPct}% ${levelChar(ctxPct)}`));

// プロンプトキャッシュヒット率（高いほどAPIコストが下がる）
const cu = input.context_window?.current_usage;
if (cu != null) {
  const cacheRead = cu.cache_read_input_tokens ?? 0;
  const cacheCreate = cu.cache_creation_input_tokens ?? 0;
  const fresh = cu.input_tokens ?? 0;
  const total = cacheRead + cacheCreate + fresh;
  if (total > 0) {
    const hitPct = Math.round((cacheRead / total) * 100);
    parts1.push(C.dim(`cache:${hitPct}% ${levelChar(hitPct)}`));
  }
}

// システムメモリ空き容量（空きが少ないほど使用率高とみなして赤に近づく）
const free = freemem();
const total = totalmem();
const freePct = Math.round(free / total * 100);
const freeGb = (free / 1024 ** 3).toFixed(1);
parts1.push(colorPct(100 - freePct, `mem:${freeGb}G ${levelChar(100 - freePct)}`));

// セッションコスト（今セッションの累積API費用）
const costUsd = input.cost?.total_cost_usd;
if (costUsd != null) parts1.push(C.magenta(`$${costUsd.toFixed(3)}`));

// 週間コスト + 曜日別スパークライン（今日はボールド）
const dayCosts = weeklyDayCosts(cache);
const weekTotal = dayCosts.reduce((a, b) => a + b, 0);
const sparkline = weeklySparkline(dayCosts);
parts1.push(`${C.cyan(`$${weekTotal.toFixed(2)}`)} ${sparkline}`);

// ── 2行目 ──────────────────────────────────────────────────────────────────
const parts2 = [];

// 5時間レート制限使用率 + リセット時刻
const fh = input.rate_limits?.five_hour;
if (fh != null) {
  const pct = Math.round(fh.used_percentage);
  const reset = fh.resets_at ? C.dim(`→${formatResetTime(fh.resets_at)}`) : '';
  parts2.push(colorPct(pct, `5h:${pct}% ${levelChar(pct)}`) + (reset ? ` ${reset}` : ''));
}

// 7日レート制限使用率 + リセット日時
const sd = input.rate_limits?.seven_day;
if (sd != null) {
  const pct = Math.round(sd.used_percentage);
  const reset = sd.resets_at ? C.dim(`→${formatResetDate(sd.resets_at)}`) : '';
  parts2.push(colorPct(pct, `7d:${pct}% ${levelChar(pct)}`) + (reset ? ` ${reset}` : ''));
}

// カレントディレクトリ（末尾2セグメントを表示）
const cwd = (input.workspace?.current_dir || input.cwd || '').replace(/\\/g, '/');
const cwdParts = cwd.split('/').filter(Boolean);
const shortCwd = cwdParts.length >= 2 ? cwdParts.slice(-2).join('/') : cwdParts.join('/') || cwd;
if (shortCwd) parts2.push(C.dim(shortCwd));

// Gitブランチ名
const gitBranch = run('git -c core.HooksPath=/dev/null rev-parse --abbrev-ref HEAD');
if (gitBranch) parts2.push(C.magenta(gitBranch));

// セッション累積コード変更量（追加行 / 削除行）
const added   = input.cost?.total_lines_added;
const removed = input.cost?.total_lines_removed;
if (added != null || removed != null) {
  const diffStr = [
    added   ? C.green(`+${added}`)  : null,
    removed ? C.red(`-${removed}`) : null,
  ].filter(Boolean).join('/');
  if (diffStr) parts2.push(diffStr);
}

// セッション名（/rename で設定した場合のみ表示）
const sessionName = input.session_name;
if (sessionName) parts2.push(C.cyan(sessionName));

// Vimモード（Vimモード有効時のみ表示）
const vimMode = input.vim?.mode;
if (vimMode) parts2.push(vimMode === 'INSERT' ? C.yellow('INSERT') : C.green('NORMAL'));

// ── 出力 ───────────────────────────────────────────────────────────────────
const lines = [];
if (parts1.length) lines.push(parts1.join(sep));
if (parts2.length) lines.push(parts2.join(sep));

process.stdout.write(lines.join('\n'));
