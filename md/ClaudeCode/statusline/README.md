# Claude Code statusline セットアップガイド

Claude Code のステータスラインをカスタマイズして、セッション情報・API使用状況・コスト・Git状態などをターミナルに常時表示する設定のドキュメントです。

---

## ファイル構成

```
~/.claude/
├── settings.json       # Claude Code 設定ファイル
├── statusline.js       # ステータスライン表示スクリプト
└── weekly-usage.json   # 週間コストキャッシュ（自動生成）
```

---

## 1. settings.json の設定

`~/.claude/settings.json` に以下を追加することでステータスラインが有効になります。

```json
{
  "statusLine": {
    "type": "command",
    "command": "node ~/.claude/statusline.js"
  }
}
```

### settings.json の主要項目

| キー | 説明 | 例 |
|------|------|-----|
| `statusLine.type` | ステータスライン取得方式 | `"command"` |
| `statusLine.command` | 実行するコマンド | `"node ~/.claude/statusline.js"` |
| `model` | デフォルトモデル | `"opusplan"`, `"sonnet"` など |
| `permissions.defaultMode` | デフォルト許可モード | `"default"`, `"bypassPermissions"` |
| `permissions.allow` | 常時許可するツール・コマンド | `["Edit", "Write", "Bash(npm run:*)"]` |
| `enabledPlugins` | 有効化するプラグイン | `{ "skill-creator@claude-plugins-official": true }` |

---

## 2. statusline.js の配置

`~/.claude/statusline.js` に配置します。スクリプトは Node.js で動作し、Claude Code から JSON を標準入力で受け取り、ANSI カラー付きの2行テキストを出力します。

### 動作の仕組み

1. Claude Code がツール実行後などのタイミングで `statusLine.command` を実行
2. スクリプトの標準入力にセッション情報の JSON が渡される
3. スクリプトが整形した文字列を標準出力に返す
4. Claude Code がターミナルのステータスラインに表示する

---

## 3. 表示される情報

ステータスラインは2行構成です。

### 表示例

```
Sonnet 4.6 | v2.1.97 | 27m53s api:25% | in:440 | out:25.7k | ctx:29% ▂ | cache:99% █ | mem:10.6G ▅ | $1.045 | $1.05 ░░░░█░░
5h:7% ▁ →02:00 | 7d:1% ░ →4/14 22:00 | git/team-task-manager | main | +234/-84
```

---

### 1行目：モデル・セッション情報 / リソース使用状況 / コスト

| 項目 | JSONフィールド | 説明 |
|------|--------------|------|
| モデル名 | `model.display_name` | 使用中のモデル名（例: `Sonnet 4.6`） |
| バージョン | `version` | Claude Code のバージョン（例: `v2.1.97`） |
| セッション経過時間 | `cost.total_duration_ms` | セッション開始からの経過時間（例: `27m53s`） |
| API待機率 | `cost.total_api_duration_ms / total_duration_ms` | 総時間のうちAPI応答待ちの割合（例: `api:25%`） |
| 累積inputトークン | `context_window.total_input_tokens` | セッション累計の入力トークン数（例: `in:440`） |
| 累積outputトークン | `context_window.total_output_tokens` | セッション累計の出力トークン数（例: `out:25.7k`） |
| コンテキスト使用率 | `context_window.used_percentage` | モデルの最大ウィンドウに対する使用割合（例: `ctx:29% ▂`） |
| キャッシュヒット率 | `current_usage` から計算 | `cache_read / (cache_read + cache_creation + input)`（例: `cache:99% █`） |
| メモリ空き容量 | `os.freemem() / os.totalmem()` | システムのメモリ空き容量（例: `mem:10.6G ▅`） |
| セッションコスト | `cost.total_cost_usd` | 今セッションの累積 API 費用（例: `$1.045`） |
| 週間コスト | `~/.claude/weekly-usage.json` | 過去7日間の合計コスト（例: `$1.05`） |
| 週間スパークライン | 同上 | 日〜土の日別コストを棒グラフで可視化（今日はボールド） |

---

### 2行目：レート制限 / 作業ディレクトリ / Git状態

| 項目 | JSONフィールド | 説明 |
|------|--------------|------|
| 5時間レート制限 | `rate_limits.five_hour` | 使用率 + リセット時刻（例: `5h:7% ▁ →02:00`） |
| 7日レート制限 | `rate_limits.seven_day` | 使用率 + リセット日時（例: `7d:1% ░ →4/14 22:00`） |
| カレントディレクトリ | `workspace.current_dir` | 末尾2セグメントを表示（例: `git/team-task-manager`） |
| Gitブランチ | `git rev-parse --abbrev-ref HEAD` | 現在のブランチ名（例: `main`） |
| コード変更量 | `cost.total_lines_added / removed` | セッション累積の追加・削除行数（例: `+234/-84`） |
| セッション名 | `session_name` | `/rename` で設定した場合のみ表示 |
| Vimモード | `vim.mode` | Vim モード有効時のみ表示（`NORMAL` / `INSERT`） |

---

### インジケーター文字（レベルバー）

使用率に応じて以下の文字で視覚的に表示されます。

```
░ ▁ ▂ ▃ ▄ ▅ ▆ ▇ █
0%                100%
```

---

### 色のルール

| 色 | 使用率 | 意味 |
|----|--------|------|
| 緑 | 0〜49% | 正常 |
| 黄 | 50〜79% | 注意 |
| 赤 | 80%〜 | 警告 |

> メモリは「空き容量が少ない = 使用率が高い」として色が変化します。

---

### 週間スパークラインの曜日別色

曜日の惑星・元素の語源に対応した色を使用しています。

| 曜日 | 色 |
|------|----|
| 日（Sun） | 黄 |
| 月（Moon） | 青 |
| 火（Mars） | 赤 |
| 水（Mercury） | シアン |
| 木（Jupiter） | 緑 |
| 金（Venus） | 明黄 |
| 土（Saturn） | 白 |

---

## 4. 週間コストキャッシュ（weekly-usage.json）

`~/.claude/weekly-usage.json` はスクリプトが自動的に作成・更新するファイルです。セッションIDをキーに日別コストをキャッシュし、週間コストの集計に使用します。8日以上前のエントリは自動削除されます。

```json
{
  "sessions": {
    "<session-id>": { "date": "2026-04-09", "cost": 1.045 }
  }
}
```

---

## 5. Claude Code に渡される JSON の構造（参考）

`statusLine.command` が受け取る JSON のフィールド一覧です（`statusline-debug.json` に最新のサンプルが保存されています）。

```json
{
  "session_id": "...",
  "cwd": "C:\\git\\team-task-manager",
  "model": { "id": "claude-sonnet-4-6", "display_name": "Sonnet 4.6" },
  "version": "2.1.97",
  "workspace": { "current_dir": "...", "project_dir": "...", "added_dirs": [] },
  "cost": {
    "total_cost_usd": 1.045,
    "total_duration_ms": 1673666,
    "total_api_duration_ms": 419306,
    "total_lines_added": 234,
    "total_lines_removed": 84
  },
  "context_window": {
    "total_input_tokens": 440,
    "total_output_tokens": 25718,
    "context_window_size": 200000,
    "used_percentage": 29,
    "current_usage": {
      "input_tokens": 1,
      "cache_creation_input_tokens": 731,
      "cache_read_input_tokens": 56783
    }
  },
  "rate_limits": {
    "five_hour": { "used_percentage": 7.0, "resets_at": 1775754000 },
    "seven_day": { "used_percentage": 1.0, "resets_at": 1776171600 }
  },
  "session_name": null,
  "vim": { "mode": null }
}
```
