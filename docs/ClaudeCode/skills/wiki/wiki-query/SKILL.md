---
name: wiki-query
description: Answer a question by searching the LLM Wiki — reads wiki/index.md, drills into relevant pages, synthesizes a cited Japanese answer, and optionally files novel synthesis back as a new wiki page. Use this when the user says "wikiに聞いて", "wikiから調べて", "wikiで〜について教えて", "wikiに質問", "ask the wiki", "query the wiki", "wikiを検索", or asks a substantive question while working in a wiki directory.
argument-hint: <質問>
---

# wiki-query: Answer a Question Against the Wiki

Search the wiki, synthesize a cited answer in Japanese, and optionally file the answer back as a new synthesis page.

**Argument**: `$ARGUMENTS` — the question to answer. If empty, ask the user:
> "どのような質問に答えますか？"

## Step 1: Verify wiki exists

Check that `CLAUDE.md` and `wiki/index.md` exist. If not, tell the user to run `/wiki-init` first.

Read `CLAUDE.md` to load wiki conventions.

## Step 2: Search the index

Read `wiki/index.md` to get the full catalog of pages. Identify 3–10 pages most likely to contain relevant information for the question. Use page titles and one-line summaries to judge relevance.

If the index has no obviously relevant pages, say so and offer to search for keywords:
```bash
grep -r "<keyword>" wiki/ --include="*.md" -l
```

## Step 3: Read candidate pages

Read each candidate page with the Read tool. Prioritize:
1. Concept and entity pages directly named in the question
2. Source pages that cover the topic
3. Synthesis pages on related themes

Read up to 10 pages. If a page contains links to other pages that seem relevant (`[[linked-page]]`), read those too (up to 5 additional hops).

## Step 4: Synthesize the answer

Write a Japanese answer that:

- **Directly addresses** the question asked.
- **Cites sources** using Obsidian wikilinks: `[[page-slug]]` for wiki pages, `[ソース名](raw/...)` for raw files.
- **Notes uncertainties** if the wiki does not fully cover the question — be explicit about gaps.
- **Flags contradictions** if relevant pages disagree. Mention both positions and which source supports each.

Default output format: flowing Japanese prose with inline `[[citations]]`.

**Alternative formats** (produce on request):
- Comparison table: "表で比較して" → Markdown table
- Slide deck: "スライドにして" → Marp-formatted Markdown
- Diagram: "図にして" → Mermaid diagram
- Bullet list: "箇条書きで" → concise bullet list

## Step 5: File-back decision

After presenting the answer, decide if it represents novel synthesis worth preserving:

**File back** if the answer:
- Compares multiple entities or concepts in a way no existing page does
- Identifies a pattern or relationship not explicitly stated in any source page
- Would take significant effort to reconstruct from the wiki alone

**Do not file back** if the answer:
- Simply retrieves and quotes an existing page
- Is a minor factual lookup
- Is highly time-sensitive or conversation-specific

If you decide to file back, ask the user:
> "この回答は [[synthesis/<slug>]] として wiki に保存する価値がありそうです。保存しますか？ (yes/no)"

If yes, create `wiki/synthesis/<slug>.md`:

```markdown
---
title: <日本語のタイトル>
type: synthesis
date: <date +%F>
tags: [<関連タグ>]
---

## 問い

<元の質問>

## 回答

<Step 4 の回答をそのまま>

## 参照ページ

- [[page1]]
- [[page2]]
```

Also update `wiki/index.md` to add the new synthesis page under `## Synthesis`.

## Step 6: Append to wiki/log.md

```bash
date +%F
```

Append:

```markdown
## [<date>] query | <質問文（50字以内に要約）>

- 参照: [[page1]], [[page2]], …
- ファイルバック: [[synthesis-slug]]（新規作成）  ← 保存した場合のみ
```

If the user chose not to file back, write:
```
- ファイルバック: なし
```
