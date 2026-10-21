# aidevアプリの操作元エージェント

## 1. 文書は実態に追いついているか

接続先PCにCLIがない場合も、操作元のClaude Code / Codexで監督・担当を起動する。Sodashitsuのtask.start(execution:operator)、task.status/prompt、remote_workの固定plugin操作を使う。

設定でserver/operatorを選び、operatorはBの導入判定・pane作成・graph・terminal embed・native resume・capture・自動終了に渡さない。初期指示と追加指示はBのPJに一意ファイルで保存。報告はBの台帳へ、質問はask_userでAへ送る。状態取得失敗は停止表示、Bへの自動代行なし。operations.mjsの公開説明も起動先ごとの動作に合わせた。

## 2. README のメンテナンス

soda-plugin/README.mdに、操作元を使う前提・設定・agent-start許可の更新・起動確認・追加指示・失効と制約を追記した。Sodashitsu本体のdocs/plugin-agents.mdへの案内も追加。aidev CLIのコマンドと工程規約は変更していない。

## 3. 実走（サブエージェント）

aidevの工程規約を変更していないため、サブエージェントで工程を歩く実走は行っていない。プラグインの差分全体と修正差分は、別コンテキストのレビューで承認された。shouldの一時エラー残留・公開操作の旧説明と停止バッジを修正し、再点検APPROVE。

`node --test docs/ClaudeCode/skills/aidev/aidev-docs/soda-plugin/*.test.mjs`: 118 passed。追加5件で重複起動、B CLI未使用、状態/指示ファイル/報告、未対応kind/model、失効後の代行なしを確認。実CLIでパッケージ生成も通過。

Sodashitsu本体の実A/Bサーバ+CLI+MCP+Chromium試験では起動承認、BアプリDOMの進捗、Aの質問フォームを検証。実際のaidevプラグインも、隔離したA/BサーバとネイティブCLI fixtureで、設定保存→監督の起動要求→Aで起動承認→BアプリDOMへのMCP進捗反映を確認した。aidevアプリの実モデルによる制作・会話resumeはこの検証には含まない。

修正追記: 最初のCIはこの記録の必須見出し不足でlint-docsの2検査が失敗した。記録を上記3見出しへ修正し、CLI・プラグインの実装は変更していない。
