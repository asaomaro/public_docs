---
name: create-pr
description: プルリクエストを作成する。「PRを作って」「プルリクを作って」「pull requestを出して」「PRを出して」「PRを作成して」「マージリクエストを作って」「レビュー依頼のPRを出して」など、PRの作成・提出を求める指示が来たら必ずこのスキルを使う。issue対応ブランチの場合はissue番号を自動検出してPR本文に `Closes #N` を付与し、マージ時にissueが自動クローズされるようにする。
allowed-tools: [Bash]
---

# Create Pull Request

## ステップ1: 現在のブランチとissue番号の確認

```bash
git branch --show-current
```

ブランチ名から issue 番号を推定する（パターン: `{prefix}/issue-{番号}`、例: `feature/issue-5`、`fix/issue-12`）。
正規表現 `issue-(\d+)` で番号を抽出する。

ブランチ名から判断できない場合は `gh pr view --json body 2>/dev/null` も試し、本文に `#数字` があれば参照する。

## ステップ2: issueの内容取得（issue番号がある場合）

issue 番号が特定できた場合:

```bash
gh issue view {番号} --json number,title,body,labels
```

タイトル・本文・ラベルを読み込む。

## ステップ3: ターゲットブランチのデフォルト推定

以下の手順でデフォルトのターゲットブランチを決定する。

### 3-1. develop 系ブランチの存在確認

```bash
git branch -a | grep -E "(^|\s+)(remotes/origin/)?(develop(/|$))"
```

develop 系ブランチが存在しない場合 → デフォルトは `main`。存在する場合は次へ。

### 3-2. 現在のブランチが develop から切られたか判定

```bash
# main との分岐点を取得
FORK=$(git merge-base HEAD main 2>/dev/null)
# その分岐点を含む develop 系ブランチを調べる
git branch -a --contains "$FORK" 2>/dev/null | grep -E "develop"
```

develop 系ブランチが fork point を含む場合 → 現在のブランチは develop から切られている。

複数の develop/* ブランチがヒットした場合は、それぞれとのマージベースを比較して最も近い（最近の）ブランチを選ぶ:

```bash
# 例: develop/sprint-1 と develop のどちらが近いか
git rev-list HEAD ^develop/sprint-1 --count
git rev-list HEAD ^develop --count
# カウントが少ない方が「より近い」ターゲット
```

develop 系ブランチが fork point を含まない場合 → デフォルトは `main`。

### 3-3. ユーザーへの確認

推定したソース・ターゲットをユーザーに提示して確認する:

> `{source-branch}` → `{target-branch}` へのPRを作成しますか？
> （変更があればお知らせください。なければそのまま進めます）

ユーザーから別のブランチ指定があればそれに従う。応答がなければデフォルトで進む。

## ステップ4: diffの分析

```bash
# コミット一覧
git log {target}..{source} --oneline

# 変更ファイルと行数サマリー
git diff {target}...{source} --stat

# 差分の詳細（大きい場合はファイル単位で確認）
git diff {target}...{source}
```

変更内容を分析し、以下を把握する:
- 変更・追加・削除されたファイルの一覧
- 主な変更の種別（新機能・バグ修正・リファクタリング・設定変更など）
- 変更の概要（1〜3行で表現できる要約）

## ステップ5: PRタイトルと本文の作成

### タイトル（70文字以内）

- issue がある場合: issue のタイトルをそのまま使うか、より適切な表現に調整する
- issue がない場合: diff から読み取った変更内容の要約（日本語）

### 本文テンプレート

```markdown
## 概要

{issueの本文要約、またはこのPRで解決する課題・目的}

## 変更内容

{diffの分析結果を箇条書きで。ファイル名・関数名・コンポーネント名を含めて具体的に}

## 動作確認

- [ ] {確認が必要な主要な動作や画面}

## 関連issue

Closes #{issue番号}
```

issue番号が特定できない場合は「関連issue」セクションを省略する。

「動作確認」セクションは、変更内容から確認が必要な項目を1〜3個程度推定して記載する。自明な場合や設定変更のみの場合は省略しても良い。

## ステップ6: PRの作成

```bash
gh pr create \
  --base {target-branch} \
  --head {source-branch} \
  --title "{title}" \
  --body "$(cat <<'EOF'
{body}
EOF
)"
```

作成後、PR の URL をユーザーに報告する。
