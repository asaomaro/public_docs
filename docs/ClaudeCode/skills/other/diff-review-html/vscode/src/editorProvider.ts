import * as vscode from "vscode";
import { minimalEdit } from "./minimalEdit";
import { SyncSession } from "./sync";
import { makeNonce, withCsp } from "./viewerHtml";

export const VIEW_TYPE = "diffReview.editor";

// 拡張は文書（テキストと版）と画面をつなぐだけ。バンドルの解析・検証・描画・正規形の書き出しは、
// HTML 版と共通の画面の JS（templates/app.js）が行う（decisions.md D3, D4）。
export class DreviewEditorProvider implements vscode.CustomTextEditorProvider {
  constructor(private readonly template: string) {}

  resolveCustomTextEditor(document: vscode.TextDocument, panel: vscode.WebviewPanel): void {
    panel.webview.options = { enableScripts: true, localResourceRoots: [] };
    panel.webview.html = withCsp(this.template, makeNonce());

    const session = new SyncSession({
      getText: () => document.getText(),
      getVersion: () => document.version,
      applyText: (next) => replaceDocument(document, next),
      post: (message) => { void panel.webview.postMessage(message); },
      warn: (message) => { void vscode.window.showWarningMessage(message); },
    });
    const uri = document.uri.toString();
    const subscriptions = [
      panel.webview.onDidReceiveMessage((message) => session.onWebviewMessage(message)),
      vscode.workspace.onDidChangeTextDocument((event) => {
        if (event.document.uri.toString() === uri) { session.onDocumentChanged(); }
      }),
    ];
    panel.onDidDispose(() => {
      session.dispose();
      subscriptions.forEach((subscription) => subscription.dispose());
    });
  }
}

function replaceDocument(document: vscode.TextDocument, next: string): Thenable<boolean> {
  const current = document.getText();
  const edit = new vscode.WorkspaceEdit();
  if (document.eol === vscode.EndOfLine.CRLF) {
    // VSCode は挿入した改行を文書の改行（CRLF）に揃えるので、正規形（LF）にするには改行の種類ごと変える。
    // 範囲は文書全体にする（部分の範囲と改行の変更を混ぜない）。正規形でない文書の最初の編集でだけ起きる（D2）。
    const all = new vscode.Range(document.positionAt(0), document.positionAt(current.length));
    edit.set(document.uri, [vscode.TextEdit.setEndOfLine(vscode.EndOfLine.LF), vscode.TextEdit.replace(all, next)]);
  } else {
    const change = minimalEdit(current, next);
    if (!change) { return Promise.resolve(true); }
    const range = new vscode.Range(document.positionAt(change.start), document.positionAt(change.end));
    edit.replace(document.uri, range, change.insert);
  }
  return vscode.workspace.applyEdit(edit);
}
