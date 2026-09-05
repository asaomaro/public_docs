---
name: conventional-commit
description: Stage tracked modified/deleted files, analyze the diff, generate a Conventional Commits style commit message, confirm with the user, and commit. Trigger this skill whenever the user wants to commit changes, stage and commit, write a commit message, or says things like "コミットして", "変更をコミット", "commit the changes", "stage and commit", "コミットメッセージを考えて", even if they don't explicitly mention Conventional Commits. Also trigger when the user asks to "commit with a good message" or just "commit" after making changes.
---

# Conventional Commit Skill

Git の変更をステージし、Conventional Commits スタイルのコミットメッセージを生成してユーザーに確認を取り、コミットするワークフロー。

## ワークフロー

### Step 1: 変更の確認とステージ

```bash
git status --short
```

で現在の状態を確認してから、tracked ファイル（modified / deleted）をまとめてステージする：

```bash
git add -u
```

untracked ファイル（`?` で始まる行）はユーザーが自分で `git add` する想定なので、自動ステージしない。

ステージ対象が 0 件だった場合は「ステージできる変更がありません」と伝えて終了する。

### Step 2: diff の分析

```bash
git diff --staged
```

の出力全体を読んで変更内容を把握する。

### Step 3: コミットメッセージの生成

diff を踏まえて Conventional Commits 形式のメッセージを考える。

**形式：**
```
<type>(<scope>): <description>
```

**type の選び方：**
| type | 使いどころ |
|------|-----------|
| `feat` | 新機能追加 |
| `fix` | バグ修正 |
| `refactor` | 動作を変えないリファクタリング |
| `style` | フォーマット・スタイルのみの変更 |
| `docs` | ドキュメント・コメントのみの変更 |
| `test` | テストの追加・修正 |
| `chore` | ビルド設定・依存関係など雑務 |
| `perf` | パフォーマンス改善 |
| `ci` | CI/CD 設定変更 |

**scope：**
- diff のファイルパスや変更内容から意味的に推定する（例: `auth`, `tasks`, `schedule`）
- 複数の機能領域にまたがる場合は省略してもよい

**breaking change：**
- 後方互換性を壊す変更（API・型・インターフェースの削除・変更）が含まれる場合は `!` を付与する
  - 例: `feat(auth)!: トークン形式を変更`
- このプロジェクトはフロントエンドアプリなので、外部公開 API でない限り `!` は使わないことが多い

**description：**
- 日本語で簡潔に（このプロジェクトは日本語ベース）
- 命令形・体言止め
- 50文字以内を目安

**例：**
```
feat(tasks): 着手期限日の表示を追加
fix(schedule): フィルタ適用時に0件になる不具合を修正
refactor(auth): AuthContext の型定義を整理
chore: Firebase Hosting キャッシュを更新
```

### Step 4: ユーザーへの確認

生成したメッセージを提示してユーザーに確認を求める。フォーマット：

```
以下のコミットメッセージでよいですか？

  <生成したメッセージ>

[問題なければ「OK」、修正点や追加指示があればお知らせください]
```

### Step 5: 分岐

**OK の場合：**
以下の形式でコミットする（HEREDOC を使って改行を正確に渡す）：

```bash
git commit -m "$(cat <<'EOF'
<メッセージ>
EOF
)"
```

コミット完了後、コミットハッシュと共に完了を伝える。

**NG・修正指示がある場合：**
ユーザーの指示（「スコープを変えて」「もっと具体的に」など）を踏まえて Step 3 に戻り、メッセージを再生成して再度確認を求める。ユーザーが直接メッセージを書いてきた場合はそれをそのままコミットに使う。

ユーザーが「やめる」「キャンセル」と言ったらステージを元に戻さずに終了する（`git reset HEAD` はしない）。
