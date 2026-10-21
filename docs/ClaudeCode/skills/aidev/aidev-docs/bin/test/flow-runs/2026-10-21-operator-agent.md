# aidevアプリの操作元エージェント

接続先PCにCLIがない場合も、操作元のClaude Code / Codexで監督・担当を起動する。Sodashitsuのtask.start(execution:operator)、task.status/prompt、remote_workの固定plugin操作を使う。

設定でserver/operatorを選び、operatorはBの導入判定・pane作成・graph・terminal embed・native resume・capture・自動終了に渡さない。初期指示と追加指示はBのPJに一意ファイルで保存。報告はBの台帳へ、質問はask_userでAへ送る。状態取得失敗は停止表示、Bへの自動代行なし。

`node --test docs/ClaudeCode/skills/aidev/aidev-docs/soda-plugin/*.test.mjs`: 118 passed。追加5件で重複起動、B CLI未使用、状態/指示ファイル/報告、未対応kind/model、失効後の代行なしを確認。

差分全体を独立コンテキストで点検しmustなし。shouldの一時エラー残留・公開操作の旧説明と停止バッジを修正し、再点検APPROVE。

Sodashitsu本体の実A/Bサーバ+CLI+MCP+Chromium試験では起動承認、BアプリDOMの進捗、Aの質問フォームを検証。aidevアプリの実モデルによる制作・会話resumeはこの検証には含まない。
