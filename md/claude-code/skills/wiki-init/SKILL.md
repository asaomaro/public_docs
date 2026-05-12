---
name: wiki-init
description: Initialize a new LLM Wiki in the current working directory — scaffolds CLAUDE.md (the wiki schema), raw/, wiki/ subdirectories, index.md, log.md, and .gitignore. Use this when the user says "wikiを初期化", "新しいwikiを作って", "LLM Wikiをセットアップ", "ここでwikiを初期化して", "init wiki", "set up a knowledge base", "knowledge baseを作って", or similar initialization intent.
---

# wiki-init: Initialize a New LLM Wiki

Scaffold a fresh LLM Wiki in the current working directory (`cwd`). This creates the canonical directory layout, the schema file (`CLAUDE.md`), and seed index/log files — everything needed to start ingesting sources.

## Step 1: Check for existing wiki

Run:
```bash
ls CLAUDE.md wiki/ 2>/dev/null
```

If both `CLAUDE.md` **and** `wiki/` already exist, stop and ask the user:
> "This directory already contains a wiki (CLAUDE.md + wiki/ found). Initialize anyway and overwrite? (yes/no)"
>
> If they say no, exit. If yes, continue — files will be overwritten.

If only one of the two exists, mention which was found and continue (partial setup is safe to complete).

## Step 2: Offer git initialization

Check if the directory is a git repository:
```bash
git rev-parse --is-inside-work-tree 2>/dev/null
```

If the output is **not** `true`, ask:
> "This directory is not a git repository. The LLM Wiki pattern works best with version history — shall I run `git init`? (yes/no)"
>
> If yes: `git init`. If no: continue without.

## Step 3: Create the directory tree

Create these directories (safe if they already exist):
```bash
mkdir -p raw wiki/sources wiki/entities wiki/concepts wiki/synthesis
```

## Step 4: Write scaffold files

Read each template from `~/.claude/skills/wiki-init/templates/` and write it to the corresponding path in cwd. Use the Read tool on each template, then Write to the target path.

| Template file | Target path in cwd |
|---|---|
| `CLAUDE.md.tmpl` | `CLAUDE.md` |
| `index.md.tmpl` | `wiki/index.md` |
| `log.md.tmpl` | `wiki/log.md` |
| `raw-README.md.tmpl` | `raw/README.md` |
| `.gitignore.tmpl` | `.gitignore` |

Write each file **as-is** — do not modify the template content. The templates are already finalized.

## Step 5: Report to the user

Print a summary of what was created:

```
✅ LLM Wiki initialized in <cwd>

Created:
  CLAUDE.md          — wiki schema (edit to describe your wiki's purpose)
  raw/README.md      — drop source files here
  wiki/index.md      — living catalog of all wiki pages
  wiki/log.md        — append-only operations log
  wiki/sources/      — one page per ingested source
  wiki/entities/     — people, orgs, products, places
  wiki/concepts/     — ideas, frameworks, terms
  wiki/synthesis/    — analyses & query outputs filed back

Next steps:
  1. Edit CLAUDE.md — fill in the "このwikiの目的" section to describe what you're tracking.
  2. Drop a source file into raw/ (markdown, PDF, image, etc.)
  3. Say "ingestして" or "/wiki-ingest <path>" to process it into the wiki.
```
