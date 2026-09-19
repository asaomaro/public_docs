export interface TextReplace {
  start: number;
  end: number;
  insert: string;
}

function isHigh(code: number): boolean { return code >= 0xd800 && code <= 0xdbff; }
function isLow(code: number): boolean { return code >= 0xdc00 && code <= 0xdfff; }

// 範囲の境目がサロゲートペアや CRLF の途中に来ると、位置に直したときに文字を割ってしまう。
function unsafeCut(text: string, at: number): boolean {
  if (at <= 0 || at >= text.length) { return false; }
  const before = text.charCodeAt(at - 1);
  const after = text.charCodeAt(at);
  return (isHigh(before) && isLow(after)) || (before === 13 && after === 10);
}

// 形式を知らない文字列の差分。共通の前後を除いた範囲だけを置き換える（元に戻すの単位と文書の変更を小さく保つ）。
export function minimalEdit(oldText: string, newText: string): TextReplace | null {
  if (oldText === newText) { return null; }
  const limit = Math.min(oldText.length, newText.length);
  let prefix = 0;
  while (prefix < limit && oldText.charCodeAt(prefix) === newText.charCodeAt(prefix)) { prefix += 1; }
  while (prefix > 0 && (unsafeCut(oldText, prefix) || unsafeCut(newText, prefix))) { prefix -= 1; }

  let suffix = 0;
  const maxSuffix = limit - prefix;
  while (suffix < maxSuffix
    && oldText.charCodeAt(oldText.length - 1 - suffix) === newText.charCodeAt(newText.length - 1 - suffix)) {
    suffix += 1;
  }
  while (suffix > 0
    && (unsafeCut(oldText, oldText.length - suffix) || unsafeCut(newText, newText.length - suffix))) {
    suffix -= 1;
  }

  return {
    start: prefix,
    end: oldText.length - suffix,
    insert: newText.slice(prefix, newText.length - suffix),
  };
}

export function applyReplace(text: string, edit: TextReplace | null): string {
  return edit ? text.slice(0, edit.start) + edit.insert + text.slice(edit.end) : text;
}
