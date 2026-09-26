// Python 3 の呼び名を決める。**実際に動くものを選ぶ**のが肝で、名前を決め打ちにすると
// Windows で詰まる: `python` / `python3` は Microsoft Store のスタブ（実体の無い別名）が
// PATH に居ることがあり、起動はできるのに「Python was not found」と言って終わる
// （ユーザー報告）。--version を実行して「Python 3」と答えたものだけを採用する。
const { spawnSync } = require("node:child_process");

// 環境変数 PYTHON が優先。空白で区切って `PYTHON="py -3"` のような指定も受ける。
function pythonCandidates() {
  const forced = (process.env.PYTHON || "").trim();
  if (forced) { return [forced.split(/\s+/)]; }
  return process.platform === "win32"
    ? [["py", "-3"], ["python"], ["python3"]]
    : [["python3"], ["python"]];
}

function answersAsPython3(command, args) {
  const probe = spawnSync(command, [...args, "--version"], { encoding: "utf8" });
  if (probe.error || probe.status !== 0) { return false; }
  return /^Python 3\./m.test((probe.stdout || "") + (probe.stderr || ""));
}

// 見つかれば [command, ...args]、無ければ null。
function resolvePython() {
  for (const candidate of pythonCandidates()) {
    const [command, ...args] = candidate;
    if (answersAsPython3(command, args)) { return candidate; }
  }
  return null;
}

function pythonNotFoundMessage() {
  const tried = pythonCandidates().map((c) => c.join(" ")).join(" / ");
  return [
    `Python 3 が見つかりません（試したもの: ${tried}）。`,
    "入っていれば環境変数 PYTHON で指定できます（例: PYTHON=\"py -3\" / PYTHON=C:\\Python312\\python.exe）。",
    "Windows で `python` が Microsoft Store の案内を出す場合は、それは実体の無い別名です。",
  ].join("\n");
}

// CommonJS で書いてあるのは、テスト（TypeScript -> CommonJS）からも同じものを使うため。
// ESM 側（build-viewer.mjs）は createRequire で読む。
module.exports = { pythonCandidates, resolvePython, pythonNotFoundMessage };
