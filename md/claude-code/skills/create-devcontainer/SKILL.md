---
name: create-devcontainer
description: Analyze a project's structure and generate .devcontainer/devcontainer.json and .devcontainer/setup.sh for VS Code Remote Containers and GitHub Codespaces. Trigger whenever the user mentions "devcontainer", "dev container", "development container", "GitHub Codespaces", "VS Code Remote", "Remote Containers", "コンテナ開発環境", "devcontainerを作って", "開発環境をコンテナ化", or asks to create/update a reproducible development environment. Also trigger when someone says "set up my dev environment", "share my dev setup with the team", or wants to make the project runnable in one click — the devcontainer approach is almost always the right answer for these cases.
---

# create-devcontainer

Generate a complete `.devcontainer/` setup for VS Code Remote Containers and GitHub Codespaces by analyzing the project structure. Output two files: `devcontainer.json` (configuration) and `setup.sh` (post-create installation steps).

---

## Step 1: Analyze the project

Gather facts before writing anything. Read these files if they exist:

**Runtime/language detection** (check in order):

| File | What to extract |
|---|---|
| `package.json` | `engines.node`, `engines.npm`; check `devDependencies` for framework clues |
| `.nvmrc` / `.node-version` | Preferred Node.js version |
| `pyproject.toml` / `Pipfile` / `requirements.txt` | Python version (`python_requires`, `[tool.poetry.dependencies].python`) |
| `.python-version` | Preferred Python version |
| `go.mod` | Go version (`go` directive) |
| `Cargo.toml` | Rust edition |
| `pom.xml` / `build.gradle` | Java version |
| `.tool-versions` | asdf multi-tool versions |

**Services and tooling**:

| File | What it means |
|---|---|
| `firebase.json` | Firebase project — needs `firebase-tools` CLI; read emulator ports |
| `functions/package.json` | Firebase Cloud Functions sub-package |
| `supabase/config.toml` | Supabase CLI needed |
| `docker-compose.yml` | Existing services — consider `dockerComposeFile` approach |
| `Makefile` | Check targets for common dev commands |

**Port detection** — collect ALL ports the dev server exposes:

| Tech | Default port | Where to verify |
|---|---|---|
| Vite | 5173 | `vite.config.*` → `server.port` |
| Next.js | 3000 | `package.json` scripts |
| Create React App | 3000 | — |
| Express / Fastify | 3000 or 8080 | entry file |
| FastAPI / uvicorn | 8000 | run command |
| Django | 8000 | manage.py runserver |
| Firebase Auth emulator | 9099 | `firebase.json` → `emulators.auth.port` |
| Firebase Firestore emulator | 8080 | `firebase.json` → `emulators.firestore.port` |
| Firebase Storage emulator | 9199 | `firebase.json` → `emulators.storage.port` |
| Firebase Functions emulator | 5001 | `firebase.json` → `emulators.functions.port` |
| Firebase Emulator UI | 4000 | `firebase.json` → `emulators.ui.port` |

**Environment variables** — read `.env.example` or `.env.template`. These become `remoteEnv` entries so the host can supply secrets without committing them.

**Runtime dependency check** — for each major tool or service detected above, ask: "Does this tool need something that the base image doesn't provide?" Common examples:

| Detected tool | What it might need |
|---|---|
| Firebase Emulators (`firebase.json` with `emulators`) | JVM — emulators are Java apps. Add `ghcr.io/devcontainers/features/java:1` |
| Puppeteer / Playwright | Chromium system packages — add via apt in setup.sh or Dockerfile |
| `psycopg2` (not `-binary`) | `libpq-dev` system package |
| `wkhtmltopdf` | Additional system packages not available as features |
| `mysqlclient` | `libmysqlclient-dev` |
| Canvas / sharp | `libcairo2-dev`, `libpng-dev`, etc. |

If a tool has a known runtime dependency, add the corresponding devcontainer feature or note it for a Dockerfile. If you're unsure whether a tool needs extra runtime deps, think about whether it bundles its dependencies (e.g., `psycopg2-binary` bundles libpq — no extra package needed) or relies on system libraries.

**Package manager**:
- `package-lock.json` → npm
- `yarn.lock` → yarn
- `pnpm-lock.yaml` → pnpm
- `bun.lockb` → bun

---

## Step 2: Choose the base image

Use Microsoft's official devcontainers images — they include git, zsh, common tools, and are regularly updated.

| Project type | Base image |
|---|---|
| Node.js | `mcr.microsoft.com/devcontainers/node:{version}-bookworm` |
| Python | `mcr.microsoft.com/devcontainers/python:{version}-bookworm` |
| Go | `mcr.microsoft.com/devcontainers/go:{version}-bookworm` |
| Rust | `mcr.microsoft.com/devcontainers/rust:latest-bookworm` |
| Java | `mcr.microsoft.com/devcontainers/java:{version}-bookworm` |
| Multi-language / unclear | `mcr.microsoft.com/devcontainers/universal:latest` |

**Version resolution**: prefer `engines.node` from `package.json` → `.nvmrc` → LTS (currently 20). Use major version only (e.g., `20`, not `20.11.0`). Same for Python, Go, Java.

If the project needs **custom system packages** (apt packages not available via devcontainer features), note this and offer a Dockerfile approach at the end (see Step 6).

---

## Step 3: Write `.devcontainer/devcontainer.json`

```json
{
  "name": "<project-name from package.json or directory name>",
  "image": "<chosen base image>",

  "features": {
    // Add features for global CLI tools.
    // Firebase CLI (if firebase.json present):
    //   "ghcr.io/devcontainers-contrib/features/firebase-tools:latest": {}
    // GitHub CLI (almost always useful):
    //   "ghcr.io/devcontainers/features/github-cli:1": {}
    // Node.js version switcher (if using non-node base image):
    //   "ghcr.io/devcontainers/features/node:1": { "version": "20" }
  },

  "forwardPorts": [/* all detected ports as integers */],

  "portsAttributes": {
    // Label each port so users see human-readable names in VS Code
    "5173": { "label": "Vite Dev Server", "onAutoForward": "notify" }
    // "4000": { "label": "Firebase Emulator UI", "onAutoForward": "openBrowser" }
  },

  "postCreateCommand": "bash .devcontainer/setup.sh",

  "remoteEnv": {
    // Inherit secrets from host environment — values stay out of the repo
    // "VITE_FIREBASE_API_KEY": "${localEnv:VITE_FIREBASE_API_KEY}"
  },

  "customizations": {
    "vscode": {
      "extensions": [/* see extension table below */],
      "settings": {
        "editor.formatOnSave": true
      }
    }
  }
}
```

**Extension selection by stack**:

| Tech | Extensions to add |
|---|---|
| TypeScript / JS | `dbaeumer.vscode-eslint`, `esbenp.prettier-vscode`, `ms-vscode.vscode-typescript-next` |
| React | `dsznajder.es7-react-js-snippets` |
| Tailwind CSS | `bradlc.vscode-tailwindcss` |
| Firebase | `toba.vsfire` |
| Python | `ms-python.python`, `ms-python.black-formatter`, `ms-python.isort` |
| Go | `golang.go` |
| Rust | `rust-lang.rust-analyzer` |
| Docker | `ms-azuretools.vscode-docker` (if docker-compose.yml exists) |
| Git (always) | `eamodio.gitlens` |
| Markdown | `yzhang.markdown-all-in-one` (if .md files are prominent) |
| Mermaid | `bierner.markdown-mermaid` (if mermaid is a dependency) |

**`onAutoForward` guidance**:
- `"notify"` — show a notification popup (good for dev servers)
- `"openBrowser"` — automatically open in browser (good for UI dashboards like Firebase Emulator UI)
- `"silent"` — forward silently (good for background services)

---

## Step 4: Write `.devcontainer/setup.sh`

The script runs once after container creation (`postCreateCommand`). Design it to be **idempotent** — safe if run a second time.

```bash
#!/bin/bash
set -e

echo "Setting up development environment..."

# --- 1. Install project dependencies ---
npm install

# If there are sub-packages (e.g., Firebase Functions):
# (cd functions && npm install)

# --- 2. One-time initialization ---
# Copy .env template only if .env doesn't already exist
if [ ! -f .env ]; then
  cp .env.example .env
  echo ""
  echo "⚠️  .env created from .env.example"
  echo "   Fill in the secret values before running the app."
fi

# --- 3. Done ---
echo ""
echo "✅ Setup complete!"
echo "   Run 'npm run dev' to start the development server."
```

**Common patterns by stack**:

```bash
# Python (pip)
pip install --user -r requirements.txt

# Python (poetry)
poetry install

# Multiple npm workspaces
npm install              # root
(cd functions && npm install)   # sub-package

# Firebase CLI (if not using devcontainer feature)
npm install -g firebase-tools

# Make the script itself executable (run this after writing setup.sh):
chmod +x .devcontainer/setup.sh
```

Keep setup.sh focused on:
- Installing npm/pip/go dependencies
- Copying config templates
- Printing next-step instructions

Do NOT put system-level apt installs here — use devcontainer features or a Dockerfile for those.

---

## Step 5: Output the files

1. Create `.devcontainer/` directory if it doesn't exist.
2. Write `.devcontainer/devcontainer.json`.
3. Write `.devcontainer/setup.sh`.
4. Make setup.sh executable: run `chmod +x .devcontainer/setup.sh` (Bash tool).
5. Print a clear summary:
   - What base image was chosen and why
   - Which ports are forwarded
   - Any env vars that need to be filled in manually
   - How to open in a devcontainer (Cmd/Ctrl+Shift+P → "Reopen in Container")

---

## Step 6: Suggest optional enhancements

After creating the files, briefly offer these if relevant:

### Dockerfile (custom system packages)
If the project needs apt packages unavailable as devcontainer features (e.g., `libcairo2-dev`, `wkhtmltopdf`), offer to:
- Create `.devcontainer/Dockerfile` using the same base image plus `RUN apt-get install ...`
- Switch devcontainer.json from `"image"` to:
  ```json
  "build": { "dockerfile": "Dockerfile" }
  ```

### docker-compose (backing services)
If the project uses or needs PostgreSQL, Redis, MySQL, etc., offer to:
- Create `.devcontainer/docker-compose.yml` with the services
- Update devcontainer.json to use:
  ```json
  "dockerComposeFile": "docker-compose.yml",
  "service": "app",
  "workspaceFolder": "/workspace"
  ```

### GitHub Codespaces optimization
- `"onCreateCommand"` runs during prebuilds (before the user opens the codespace) — put slow, cacheable steps here (e.g., `npm install`).
- `"postCreateCommand"` runs after the codespace is opened — put steps that need user context or secrets here (e.g., `.env` setup).
- Splitting these can make Codespaces startup dramatically faster.

---

## Handling existing `.devcontainer/`

If `.devcontainer/devcontainer.json` already exists:
1. Read the existing file first.
2. Identify what's missing or outdated (e.g., missing ports, extensions, new env vars).
3. Propose a diff / updated version rather than blindly overwriting.
4. Ask the user to confirm before writing.
