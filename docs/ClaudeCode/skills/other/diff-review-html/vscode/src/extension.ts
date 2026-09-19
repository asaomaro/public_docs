import * as vscode from "vscode";
import { readFileSync } from "node:fs";
import { DreviewEditorProvider, VIEW_TYPE } from "./editorProvider";

export function activate(context: vscode.ExtensionContext): void {
  // ビルド時に diff_review.py view で生成した画面（decisions.md D5）。無ければビルドを忘れている。
  const template = readFileSync(context.asAbsolutePath("media/viewer.html"), "utf8");
  context.subscriptions.push(vscode.window.registerCustomEditorProvider(
    VIEW_TYPE,
    new DreviewEditorProvider(template),
    // 隠したタブの画面は作り直され、ready からやり直す（research.md F9）。画面を持ち続けない。
    { webviewOptions: { retainContextWhenHidden: false } },
  ));
}

export function deactivate(): void {
  // 片付けは context.subscriptions が行う。
}
