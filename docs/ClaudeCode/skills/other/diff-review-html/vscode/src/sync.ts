// 画面（WebView）と文書（TextDocument）の同期の判断。VSCode に依存しない（unit テストで順序を検査する）。
//
// 約束（design.md「SyncSession（1 本の列）」・decisions.md D10）:
//  - ready・編集・文書の変更の通知を 1 本の列で順に処理する。
//  - 画面の編集には、その編集への返事を 1 つだけ返す（ack か、conflict 付きの今の文書）。
//  - 基にした版が今の版と違う編集は書かない（古い内容で新しい変更を上書きしない）。
//  - 画面へは「画面に出ているはずの文書」（テキストと版）と違うときだけ送る（更新ループを作らない）。

export interface SyncHost {
  getText(): string;
  getVersion(): number;
  applyText(next: string): PromiseLike<boolean>;
  post(message: object): void;
  warn(message: string): void;
}

export const MessageType = {
  ready: "diff-review/ready",
  edit: "diff-review/edit",
  text: "diff-review/text",
  ack: "diff-review/ack",
} as const;

interface EditMessage {
  type: typeof MessageType.edit;
  id: string;
  text: string;
  baseVersion: number;
}

function typeOf(message: unknown): unknown {
  return message && typeof message === "object" ? (message as { type?: unknown }).type : undefined;
}

function isEdit(message: unknown): message is EditMessage {
  const m = message as Partial<EditMessage> | null;
  return typeOf(message) === MessageType.edit && !!m
    && typeof m.id === "string" && typeof m.text === "string" && typeof m.baseVersion === "number";
}

export class SyncSession {
  private ready = false;
  private lastShown: string | null = null;
  private lastShownVersion: number | null = null;
  private chain: Promise<void> = Promise.resolve();
  private timer: ReturnType<typeof setTimeout> | null = null;
  private disposed = false;

  constructor(private readonly host: SyncHost, private readonly debounceMs = 50) {}

  onWebviewMessage(message: unknown): void {
    if (typeOf(message) === MessageType.ready) {
      this.enqueue(() => {
        this.ready = true;
        this.showCurrent();
      });
    } else if (isEdit(message)) {
      this.enqueue(() => this.applyEdit(message));
    }
  }

  onDocumentChanged(): void {
    if (this.disposed) { return; }
    if (this.timer) { clearTimeout(this.timer); }
    this.timer = setTimeout(() => {
      this.timer = null;
      this.enqueue(() => this.flush());
    }, this.debounceMs);
  }

  // 列に積んだものがすべて終わるまで待つ。
  idle(): Promise<void> {
    return this.chain;
  }

  dispose(): void {
    this.disposed = true;
    if (this.timer) { clearTimeout(this.timer); }
    this.timer = null;
  }

  private enqueue(job: () => void | Promise<void>): void {
    this.chain = this.chain.then(async () => {
      if (this.disposed) { return; }
      try {
        await job();
      } catch (err) {
        this.host.warn(`Diff Review: ${err instanceof Error ? err.message : String(err)}`);
      }
    });
  }

  private flush(): void {
    if (!this.ready) { return; }
    // 中身が同じで版だけ進んだとき（元に戻す→やり直しの往復など）も送る。画面の版を今に揃えないと、
    // 次の編集が「同時に変更された」として退けられてしまう。
    if (this.host.getText() === this.lastShown && this.host.getVersion() === this.lastShownVersion) { return; }
    this.showCurrent();
  }

  private showCurrent(extra: Record<string, unknown> = {}): void {
    if (this.disposed) { return; }
    this.lastShown = this.host.getText();
    this.lastShownVersion = this.host.getVersion();
    this.host.post({ type: MessageType.text, text: this.lastShown, version: this.lastShownVersion, ...extra });
  }

  private async applyEdit(edit: EditMessage): Promise<void> {
    const conflict = { id: edit.id, conflict: true };
    if (edit.baseVersion !== this.host.getVersion()) {
      this.showCurrent(conflict);
      return;
    }
    if (edit.text !== this.host.getText()) {
      let ok = false;
      let reason = "";
      try {
        ok = await this.host.applyText(edit.text);
      } catch (err) {
        reason = `（${err instanceof Error ? err.message : String(err)}）`;
      }
      // 書いている間に閉じられたら、もう誰にも知らせない（破棄のあとは何も送らない）。
      if (this.disposed) { return; }
      if (!ok) {
        this.host.warn(`Diff Review: 画面での変更を文書に書き込めませんでした${reason}。表示を文書の内容に戻します。`);
        this.showCurrent(conflict);
        return;
      }
      if (this.host.getText() !== edit.text) {
        this.showCurrent(conflict);
        return;
      }
    }
    this.lastShown = this.host.getText();
    this.lastShownVersion = this.host.getVersion();
    this.host.post({ type: MessageType.ack, id: edit.id, version: this.lastShownVersion });
  }
}
