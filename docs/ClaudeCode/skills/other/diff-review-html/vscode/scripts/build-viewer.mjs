// 拡張が載せる画面（media/viewer.html）を diff_review.py view から生成する。
// 生成物はコミットしない——テンプレートの写しを 2 つ持つと片方だけ古くなる（decisions.md D5）。
import { spawnSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const script = join(root, "..", "diff_review.py");
const out = join(root, "media", "viewer.html");
const python = process.env.PYTHON || (process.platform === "win32" ? "python" : "python3");

mkdirSync(dirname(out), { recursive: true });
const result = spawnSync(python, [script, "view", "--out", out], { stdio: "inherit" });
if (result.error) {
  console.error(`${python} を起動できません（環境変数 PYTHON で指定できます）: ${result.error.message}`);
  process.exit(1);
}
process.exit(result.status ?? 1);
