// 拡張が載せる画面（media/viewer.html）を diff_review.py view から生成する。
// 生成物はコミットしない——テンプレートの写しを 2 つ持つと片方だけ古くなる（decisions.md D5）。
import { spawnSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const { pythonNotFoundMessage, resolvePython } = createRequire(import.meta.url)("./python.cjs");

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const script = join(root, "..", "diff_review.py");
const out = join(root, "media", "viewer.html");

const python = resolvePython();
if (!python) {
  console.error(pythonNotFoundMessage());
  process.exit(1);
}
const [command, ...prefix] = python;

mkdirSync(dirname(out), { recursive: true });
const result = spawnSync(command, [...prefix, script, "view", "--out", out], { stdio: "inherit" });
if (result.error) {
  console.error(`${python.join(" ")} を起動できません: ${result.error.message}`);
  process.exit(1);
}
process.exit(result.status ?? 1);
