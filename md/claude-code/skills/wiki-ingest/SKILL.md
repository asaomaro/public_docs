---
name: wiki-ingest
description: Process a raw source file into the LLM Wiki — reads the source, discusses key takeaways with the user, writes a Japanese summary page under wiki/sources/, updates relevant entity and concept pages, refreshes wiki/index.md, and appends a log entry. Use this when the user says "ingestして", "このソースを取り込んで", "wikiに追加して", "wikiに食わせて", "このファイルをwikiに入れて", "ingest this", "process this source", "add to wiki", or when they drop a file in raw/ and ask for it to be processed.
argument-hint: <raw/ 以下のソースファイルパス>
---

# wiki-ingest: Process a Source into the Wiki

Integrate a raw source into the wiki by writing a Japanese summary page, updating related entity/concept pages, and keeping the index and log current.

**Argument**: `$ARGUMENTS` — path to the source file (relative to cwd or absolute). If empty, see Step 1.

## Step 1: Identify the source file

If `$ARGUMENTS` is provided, use that path. Otherwise:

```bash
ls raw/
```

Show the user which files are in `raw/`, compare against `wiki/sources/` to identify unprocessed ones, and ask which to ingest.

If the source path does not exist, tell the user and stop.

## Step 2: Read CLAUDE.md (schema)

Read `CLAUDE.md` in cwd to load the wiki's conventions. If it does not exist, stop and tell the user to run `/wiki-init` first.

## Step 3: Read the source

Use the Read tool on the source file.

- **Markdown / text**: Read directly.
- **PDF**: Read with the Read tool; if it's long (>10 pages), read page ranges incrementally.
- **Image** (`.png`, `.jpg`, `.webp` etc.): Read the image with the Read tool to view it visually.
- **Markdown with inline images** (e.g. from Obsidian Web Clipper): Read the text first, then Read each referenced image separately if additional context is needed.

## Step 4: Discuss key takeaways with the user

Before writing anything, present your reading to the user:

> "このソースから読み取った主なポイントは以下です。wiki に取り込む前に確認・補足をお願いします。
>
> 1. …
> 2. …
> 3. …
>
> 特に強調したい点や、追加の観点はありますか？"

Wait for the user's response. Incorporate their guidance into everything that follows.

## Step 5: Write the source summary page

Create `wiki/sources/<slug>.md` where `<slug>` is a lowercase hyphenated filename derived from the source title.

Page content (Japanese, following CLAUDE.md conventions):

```markdown
---
title: <ソースのタイトル（日本語）>
type: source
date: <今日の日付: date +%F で取得>
tags: [<関連タグ>]
---

## 概要

<200–400字のサマリ。このソースが何を主張しているか、なぜ重要かを簡潔に>

## 主要なポイント

- <ポイント1>
- <ポイント2>
- …

## 登場するエンティティ・概念

- [[entity-slug]] — <このソースでの役割>
- [[concept-slug]] — <このソースでの文脈>

## 原文への参照

[原文](<raw/ 以下の相対パス>)
```

## Step 6: Update entity and concept pages

For each entity and concept identified in the summary, update or create its wiki page:

1. Check if `wiki/entities/<slug>.md` or `wiki/concepts/<slug>.md` exists.
2. If it **exists**: Read the current content, then add a new section or update existing claims to reflect this source. If this source contradicts an existing claim, add an `> [!warning] 矛盾` admonition (see CLAUDE.md).
3. If it **does not exist**: Create a new page with frontmatter (`type: entity` or `type: concept`, `source_count: 1`) and an initial body.
4. Always add a `[[source-slug]]` backlink in the entity/concept page.

Typical ingest touches 5–15 pages. Do not create trivial stub pages — only create a page if there is meaningful content to write.

## Step 7: Update wiki/index.md

Read the current `wiki/index.md`, then:

1. Add the new source page under `## Sources`.
2. Add or update entries for any new or significantly updated entity/concept pages.
3. Update the `（N件）` counts in each section header.
4. Write the updated file.

## Step 8: Append to wiki/log.md

Get today's date:
```bash
date +%F
```

Append to `wiki/log.md`:

```markdown
## [<date>] ingest | <ソースのタイトル>

- 作成: [[<source-slug>]]
- 更新: [[page1]], [[page2]], …
- 新規: [[new-page]], …（なければ省略）
```

## Step 9: Report to the user

Print a concise diff summary:

```
✅ ingest 完了: <ソースタイトル>

  wiki/sources/<slug>.md       新規作成
  wiki/entities/<slug>.md      更新（矛盾1件あり）
  wiki/concepts/<slug>.md      新規作成
  wiki/index.md                更新（Sources: N件 → N+1件）
  wiki/log.md                  エントリ追記
```

If any contradictions were flagged, mention them explicitly so the user is aware.
