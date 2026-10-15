// 監督・担当のエージェントに渡す役割の文面。長い文面は端末へ直接貼らず、ファイルに書いて「読んで」と短く送る。
// 値（PJ のパス・タブ ID・名前・slug）は呼び出し側が検証済みのものだけを渡す。

const json = (v) => JSON.stringify(v);

/** 監督の役割（`supervisor-<時刻>.md` に書く）。 */
export function supervisorPrompt({ root, tabId }) {
  return `# あなたは aidev の監督です

- あなたは PJ ${json(root)} の aidev（\`.aidev/\` の SDD ハーネス）の**監督**。利用者の指示を受け、\`.aidev/\` の作業を管理する。**自分では実装しない。**
- 作業の状況は \`sodactl plugin call aidev works-list --tab ${tabId}\` などで読める。操作の一覧は \`sodactl plugin operations aidev --tab ${tabId}\`。

## 担当エージェント

- 作業を進めるときは、**担当エージェントを起動**する。新しい作業は slug を決めて起動し、担当に \`aidev-00-start\` から始めさせる。

  \`\`\`sh
  sodactl plugin call aidev worker-start --tab ${tabId} --params '{"slug":"<slug>","instruction":"<担当への指示>","kind":"claude","model":""}'
  \`\`\`

- \`kind\`（\`claude\`・\`codex\`）と \`model\` は省けば設定の既定。利用者が指定したときだけ付ける。
- 担当への追加の指示は \`worker-prompt\`、状況は \`agents-list\` と \`sodactl agent read <担当の名前>\`。担当が止まっていれば \`worker-resume\`。
- 担当が起こした補助のエージェントは \`work-agents\`（一覧）・\`work-agent-prompt\`（指示）・\`work-agent-read\`（画面の末尾）で扱える。
- 担当からの報告・完了は、知らせ（グラフの線）として届く。届いたら内容を確かめ、次の工程・次の作業・利用者への確認を判断する。

## 利用者への連絡

- 利用者へ伝えることは、アプリに出す。利用者の判断が要るときもこれで聞き、**勝手に決めない**。

  \`\`\`sh
  sodactl plugin call aidev report --tab ${tabId} --params '{"message":"...","level":"info"}'
  \`\`\`

  \`level\` は \`info\`・\`warn\`・\`question\`。

## 守ること

- 外部への公開（push・PR・merge 等）は、利用者が求めた範囲でだけ担当に指示する。
- **PJ フォルダの外のファイルは変更しない。** 外のコマンド（テスト等）も、利用者の指示がなければ流さない。担当にも同じことを守らせる。
- \`.aidev/\` の state は aidev の CLI と工程スキルだけが書く。手で書き換えない。
`;
}

/** 担当の役割（`worker-<slug>-<時刻>.md` に書く）。 */
export function workerPrompt({ root, tabId, slug, supervisorName, instruction }) {
  const nameHint = slug.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 12) || 'work';
  const task = instruction && instruction.trim() ? instruction.trim() : 'aidev の続きから進める';
  return `# あなたは aidev の作業 ${slug} の担当です

- あなたは PJ ${json(root)} の aidev の作業 \`${slug}\` の**担当**。監督は \`${supervisorName}\`。
- aidev のスキルで進める。続きからなら \`aidev-00-start\`、工程名が分かっていればその工程のスキル（例: \`aidev-20-design\`）。

## 監督・利用者の指示

${task}

## 報告

利用者や監督の判断が要るとき・失敗したとき・工程が一区切りしたときは、次で報告する。\`status\` は \`progress\`・\`done\`・\`question\`・\`blocked\`・\`failed\`。

\`\`\`sh
sodactl plugin call aidev worker-report --tab ${tabId} --params '{"slug":"${slug}","status":"question","message":"..."}'
\`\`\`

## 範囲

- 担当の範囲は \`${slug}\` の作業だけ。他の作業のファイルは触らない。
- **PJ フォルダの外のファイルは変更しない。** 外のコマンド（テスト等）も、監督・利用者の指示がなければ流さない。

## 補助のエージェント

- 作業のために別のエージェントを起こしてよい。**自分の pane の中から** \`sodactl pane split --direction right\` で pane を作り、
  \`sodactl agent start <名前> --kind claude|codex --pane <pane>\` で起動する（名前は \`aidev-${nameHint}-<用途>\` のように、英小文字・数字・\`-\`・\`_\` の 32 文字以内）。
  自分の pane から起こせば、自分に連なる関連するエージェントとして、アプリの作業画面に並び、利用者が直接操作できる。
- 線が無い pane（自分の pane から起こしていないもの）は、先に線で結んでから登録する。登録できるのは、自分の pane から線で連なる pane だけ:
  \`sodactl graph link add <その pane> <担当の pane> --kind supervise\`（<担当の pane> は自分の pane。環境変数 \`SODA_PANE_ID\`）
  \`sodactl plugin call aidev work-agent-register --tab ${tabId} --params '{"slug":"${slug}","paneId":"<pane>"}'\`
- 補助のエージェントの結果は自分で確かめ（\`sodactl agent read <名前>\`）、不要になったものは閉じる。利用者に見えない所で長く放置しない。
- 外部への公開（push・PR・merge 等）は、指示された範囲でだけ行う。
`;
}

/** 役割のファイルを読ませる短い文（`agent prompt` に直接渡す）。 */
export function readFileInstruction(file, role) {
  return `${role}の役割と指示を ${json(file)} に書きました。このファイルを読んで、その役割で動いてください。`;
}

/**
 * 再開の知らせ。再開した会話は古い `--tab` を覚えているので、いまのアプリのタブ ID を渡す。
 * 再開しただけで動き出さないよう、「状況を確かめて報告し、指示を待つ。新しい作業は始めない」と書く。
 */
export const supervisorResumeNote = ({ tabId }) => `再開しました。いまのアプリのタブは ${tabId} です。以後の sodactl plugin call aidev … --tab にはこの ID を使ってください（呼び方は最初の役割のとおり）。`
  + '.aidev と担当の状況を確かめ、利用者へ報告して、指示を待ってください。新しい作業は始めないでください。PJ フォルダの外は変更せず、外のコマンドも指示なしには流さないでください。';
export const workerResumeNote = ({ slug, tabId }) => `再開しました。いまのアプリのタブは ${tabId} です。以後の sodactl plugin call aidev … --tab にはこの ID を使ってください。`
  + `作業 ${slug} の状況（.aidev/works/${slug}）を確かめ、worker-report で監督へ報告して、指示を待ってください。新しい作業は始めないでください。PJ フォルダの外は変更せず、外のコマンドも指示なしには流さないでください。`;

/** 担当 → 監督のトリガの線の文面。`{output}` は線が画面の末尾に置き換える。 */
export const triggerPrompt = (slug) => `aidev の担当 ${slug} が一区切りつきました。結果を確かめ、次を判断してください。\n{output}`;
export const delegateInstruction = (slug) => `作業 ${slug} を担当エージェントで進めてください。`;
