---
name: wiki-lint
description: Health-check the LLM Wiki — finds contradictions between pages, stale claims superseded by newer sources, orphan pages with no inbound links, concepts mentioned but lacking their own page, missing cross-references, and naming inconsistencies. Presents a triaged report and applies selected fixes. Use this when the user says "wikiを点検", "wikiを健全化", "wikiをチェックして", "wikiの整合性を確認", "lint wiki", "check the wiki", "wiki health check", or periodically after adding many sources.
---

# wiki-lint: Health-Check the Wiki

Audit the wiki for structural and content issues, present a triaged report, and apply fixes the user selects.

## Step 1: Verify wiki exists

Check that `CLAUDE.md` and `wiki/` exist. If not, stop and tell the user to run `/wiki-init` first.

Read `CLAUDE.md` to load wiki conventions.

## Step 2: Inventory the wiki

Gather the full picture before looking for problems:

```bash
# All wiki pages
find wiki/ -name "*.md" | sort

# All internal wikilinks across wiki/
grep -rh "\[\[" wiki/ --include="*.md" | grep -o '\[\[[^]]*\]\]' | sort | uniq -c | sort -rn

# All pages referenced in index.md
grep -o '\[\[[^]]*\]\]' wiki/index.md
```

Also read `wiki/index.md` and `wiki/log.md` (last 20 entries: `tail -80 wiki/log.md`).

## Step 3: Check for issues

Work through each check below. Read pages as needed with the Read tool. Build a findings list as you go.

### 3a. Orphan pages

An orphan is a page in `wiki/sources/`, `wiki/entities/`, `wiki/concepts/`, or `wiki/synthesis/` that appears in **zero** inbound `[[wikilinks]]` from other wiki pages.

Cross-reference the page list against the extracted wikilinks. Pages not linked from anywhere (except `index.md`) are orphans.

### 3b. Missing entity / concept pages

Scan all wiki pages for `[[slug]]` references. Check whether `wiki/entities/<slug>.md` or `wiki/concepts/<slug>.md` exists for each. Any `[[slug]]` that points to a non-existent file is a **missing page** (broken link).

### 3c. Concepts mentioned but not linked

Read a sample of 10–20 pages (prioritize recently updated ones). If a page's body text mentions a concept or entity name **without** linking it as `[[slug]]`, it is a missing cross-reference.

Focus on proper nouns, technical terms, and entity names that appear elsewhere in the wiki as page titles.

### 3d. Contradictions

Compare claims across source summary pages and entity/concept pages. Look for:
- Dates, numbers, or facts stated differently across pages
- Positions attributed differently to the same entity
- Conclusions that directly conflict

Check whether existing `> [!warning] 矛盾` admonitions are still current.

### 3e. Stale claims

Read the log (`wiki/log.md`) to understand ingestion order. For entity/concept pages updated early in the wiki's life, check if newer source pages contain superseding information not yet reflected.

### 3f. Naming inconsistencies

Check if the same entity or concept is referenced under multiple slug variants (e.g., `[[gpt-4]]` and `[[gpt4]]` and `[[GPT-4]]`). Find candidates using:

```bash
grep -roh '\[\[[^]]*\]\]' wiki/ | sed 's/\[\[//;s/\]\]//' | sort | uniq
```

### 3g. Data gaps

Based on what the wiki covers, note topics that appear frequently in cross-references but have only thin coverage — concepts that deserve a richer page, or entities that appear in many source pages but lack a standalone page.

Also: suggest 2–3 new questions worth asking, and 1–2 types of sources that could strengthen the wiki.

## Step 4: Build the triaged report

Present findings grouped by priority:

```
## Wiki Lint レポート（<date +%F>）

### 🔴 High（構造的な問題）

- **孤立ページ** (N件): wiki/entities/foo.md, wiki/sources/bar.md, …
  → どこからもリンクされていない。index.md 以外からリンクするか削除を検討。

- **リンク切れ** (N件): [[missing-slug]] が N箇所で参照されているがページが存在しない。
  → ページを作成するか、リンクを修正する。

### 🟡 Medium（整合性の問題）

- **矛盾** (N件):
  - [[page-a]] と [[page-b]] で〜の値が異なる（page-a: X, page-b: Y）
  - …

- **ステール** (N件):
  - [[concept-x]] の「〜」という記述は [[newer-source]] で更新されている可能性。

### 🟢 Low（改善提案）

- **未リンクの言及** (N件): [[concept-y]] が page-z 本文に登場するがリンクなし。
- **命名の揺れ** (N件): [[foo-bar]] と [[foobar]] が混在。
- **薄いページ** (N件): [[entity-x]] は N件のソースで参照されているが内容が薄い。

### 💡 提案

- 追加を検討するソース: 〜
- 深掘りする価値がある質問: 〜
```

If no issues are found in a category, write "(なし)" instead.

## Step 5: Ask which fixes to apply

After the report, ask:

> "どの問題から修正しますか？番号または種類（例: "孤立ページを直して", "リンク切れを全部修正して", "矛盾だけ直して"）を教えてください。「全部」と言えばすべて適用します。「スキップ」または「あとで」で終了できます。"

## Step 6: Apply selected fixes

For each selected fix:

- **孤立ページ**: Add a `[[wikilink]]` to the orphan from the most logical related page, OR ask the user if they want to delete it.
- **リンク切れ**: Create a minimal stub page for the missing slug (frontmatter + 1-sentence description), OR ask the user to confirm deletion of the stale link.
- **矛盾**: Add `> [!warning] 矛盾` admonition to both pages if not already present. Ask the user to adjudicate if they want a definitive claim.
- **ステール**: Update the stale page with the newer claim. If contradictory, add admonition.
- **未リンクの言及**: Replace plain text mention with `[[slug]]` wikilink.
- **命名の揺れ**: Pick a canonical slug, update all references to match, optionally create a redirect alias comment in the non-canonical page.
- **薄いページ**: Offer to expand if a relevant source page exists. Do not invent content.

Update `wiki/index.md` if any pages are created or removed.

## Step 7: Append to wiki/log.md

```bash
date +%F
```

Append:

```markdown
## [<date>] lint | <一行サマリ（例: "孤立ページ3件修正、矛盾2件フラグ"）>

- 検出: 孤立ページ N件, リンク切れ N件, 矛盾 N件, ステール N件
- 修正: <適用した修正の箇条書き>
- スキップ: <適用しなかった修正（あれば）>
```
