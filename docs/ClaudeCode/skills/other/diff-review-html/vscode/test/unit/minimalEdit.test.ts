import { test } from "node:test";
import assert from "node:assert/strict";
import { applyReplace, minimalEdit } from "../../src/minimalEdit";

// 境目がサロゲートペア・CRLF の途中に来ていないか（旧文の start / end と、新文側の対応する位置）。
function splits(text: string, at: number): boolean {
  if (at <= 0 || at >= text.length) { return false; }
  const before = text.charCodeAt(at - 1);
  const after = text.charCodeAt(at);
  return (before >= 0xd800 && before <= 0xdbff && after >= 0xdc00 && after <= 0xdfff)
    || (before === 13 && after === 10);
}

function roundTrip(a: string, b: string) {
  const edit = minimalEdit(a, b);
  const where = JSON.stringify({ a, b, edit });
  assert.equal(applyReplace(a, edit), b, where);
  if (edit) {
    assert.ok(0 <= edit.start && edit.start <= edit.end && edit.end <= a.length, where);
    assert.ok(!splits(a, edit.start) && !splits(a, edit.end), "旧文の境目 " + where);
    assert.ok(!splits(b, edit.start) && !splits(b, edit.start + edit.insert.length), "新文の境目 " + where);
  }
  return edit;
}

test("同じなら何もしない", () => {
  assert.equal(minimalEdit("abc", "abc"), null);
});

test("前後の共通部分を除いた範囲だけを置き換える", () => {
  assert.deepEqual(roundTrip('{"a": 1, "b": 2}', '{"a": 1, "b": 3}'), { start: 14, end: 15, insert: "3" });
  assert.deepEqual(roundTrip("abc", "abXc"), { start: 2, end: 2, insert: "X" });
  assert.deepEqual(roundTrip("abXc", "abc"), { start: 2, end: 3, insert: "" });
  roundTrip("", "all new");
  roundTrip("all old", "");
  roundTrip("aaa", "aaaa");
  roundTrip("abab", "ab");
});

test("サロゲートペアの途中で切らない", () => {
  const a = "x\u{1F600}y";
  const b = "x\u{1F601}y";
  const edit = roundTrip(a, b)!;
  assert.equal(edit.start, 1);
  assert.equal(edit.end, 3);
  assert.equal(edit.insert, "\u{1F601}");
  roundTrip("\u{1F600}", "\u{1F600}\u{1F600}");
  roundTrip("a\u{1F600}", "a\u{1F601}");
  // 低位サロゲートが同じで高位だけ違う: 後ろからの比較が低位で止まらないので、end の調整が要る。
  assert.deepEqual(roundTrip("a\u{1F600}", "a\u{1F200}"), { start: 1, end: 3, insert: "\u{1F200}" });
});

test("CRLF の途中で切らない（旧文の start / end、新文の境目）", () => {
  roundTrip("a\r\nb", "a\r\r\nb");
  assert.deepEqual(roundTrip("x\r\n", "x\n"), { start: 1, end: 3, insert: "\n" });   // end が旧文の CRLF の間に来ない
  roundTrip("x\n", "x\r\n");
  roundTrip("a\r\nb\r\n", "a\nb\n");
  assert.deepEqual(roundTrip("a\rb", "a\r\nb"), { start: 1, end: 2, insert: "\r\n" }); // 新文の CRLF の間で切らない
});

test("短い文字列の全組み合わせで、往復と境目の約束が成り立つ", () => {
  const alphabet = ["a", "\r", "\n", "\u{1F600}", "\u{1F601}", "\u{1F200}"];
  const words = [""];
  for (let length = 1; length <= 3; length += 1) {
    const grow = words.filter((w) => [...w].length === length - 1);
    grow.forEach((w) => alphabet.forEach((c) => words.push(w + c)));
  }
  for (const a of words) {
    for (const b of words) { roundTrip(a, b); }
  }
});

test("大きな全文の中の小さな変更は小さな範囲になる", () => {
  const body = "x".repeat(100000);
  const edit = roundTrip(body + "A" + body, body + "BB" + body)!;
  assert.equal(edit.end - edit.start, 1);
  assert.equal(edit.insert, "BB");
});
