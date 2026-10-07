---
title: 受付システム刷新の報告
subtitle: 半年の試行で分かったことと、次の一手
date: 2026-10-07
tags: 見本, 追加分
eyebrow: 追加した見せ方の見本
author: 業務改善チーム
org: 情報システム部
version: 1.2
docno: DOC-2026-014
status: 確定
---

## 概要

この文書は、md-to-doc に足した **テーマ・コールアウト・表・コード・図・表紙の書誌** を一通り使う見本です。
窓口の受付を紙からシステムに移した半年の試行について、`受付時間` と `差し戻し` の 2 つの数字を中心に報告します。
本文の段落は、行間・字間・両端の揃え方がテーマごとに変わります。長めの文を 1 つ置いて、折り返しの様子を確かめます。

> [!SUMMARY]
> 受付にかかる時間は **平均 11 分** まで下がり、差し戻しは 4 割減った。残る課題は入力ミスに集中している。

> [!ABSTRACT]
> 本稿は、受付業務の電子化が処理時間のばらつきに与える影響を、半年分の記録から分析する。

> [!DEFINITION]
> **差し戻し** とは、受付後に不備が見つかり、申請者へ書類を返すことを指す。

> [!EXAMPLE]
> 添付の漏れで 1 回、記入の誤りでもう 1 回返した申請は、差し戻し 2 件と数える。

> [!QUESTION]
> 入力ミスは、画面の作りと申請者の慣れのどちらに由来するのか。

> [!SUCCESS]
> 10 月 1 日に全窓口への展開が完了した。

> [!DECISION]
> 紙の申請は 2027 年 3 月末で受付を終える。

> [!TODO]
> 入力ミスの内訳を、項目ごとに 11 月の定例までに集計する（担当: 佐藤）。

## 進み具合

<!-- table: status -->
| 作業 | 担当 | 状態 | 期限 |
|---|---|---|---|
| 窓口への展開 | 山田 | 完了 | 10/01 |
| 入力画面の見直し | 佐藤 | 進行中 | 11/15 |
| 手引きの改訂 | 鈴木 | 確認中 | 11/30 |
| 旧システムの停止 | 田中 | 未着手 | 03/31 |
| 帳票の移行 | 高橋 | 遅延 | 10/20 |

### 窓口ごとの件数

<!-- table: heat -->
| 窓口 | 4月 | 5月 | 6月 | 7月 |
|---|---|---|---|---|
| 本庁 | 320 | 410 | 480 | 610 |
| 北支所 | 120 | 150 | 140 | 210 |
| 南支所 | 80 | 95 | 160 | 180 |
| 出張所 | 20 | 35 | 30 | 55 |

### 費用の内訳

<!-- table: total -->
| 費目 | 計画（万円） | 実績（万円） |
|---|---|---|
| 開発 | 1,200 | 1,150 |
| 機器 | 300 | 340 |
| 研修 | 80 | 60 |
| 合計 | 1,580 | 1,550 |

## 設定の例

題（ファイル名）と行番号、強調する行を付けたコードです。

```yaml:config/reception.yml {numbers 3-4}
reception:
  window: 本庁
  timeout_min: 15
  retry: 2
  notify: mail
```

```python:check.py
def is_complete(form):
    return all(form.get(k) for k in ("name", "address", "attachment"))
```

```bash {2}
soda reception import forms.csv
soda reception check --strict
soda reception report
```

素のコード（これまでどおり）:

```bash
soda serve
```

## 分析の図

### 増減の内訳（waterfall）

```figkit
{"type":"waterfall","unit":"件","caption":"図 1 月間の受付件数の増減","items":[
 {"label":"4月","value":540,"total":true},{"label":"新規の窓口","value":260},{"label":"オンライン","value":190},
 {"label":"紙の終了","value":-120},{"label":"重複の整理","value":-45},{"label":"9月","total":true}]}
```

### 差し戻しの原因（pareto）

```figkit
{"type":"pareto","unit":"件","threshold":80,"caption":"図 2 差し戻しの原因（累積の割合）","items":[
 {"label":"入力ミス","value":42},{"label":"添付の漏れ","value":27},{"label":"仕様の誤解","value":12},
 {"label":"期限切れ","value":8},{"label":"その他","value":6}]}
```

### 受付時間のばらつき（box）

```figkit
{"type":"box","unit":"分","caption":"図 3 受付にかかった時間（紙とシステム）","items":[
 {"label":"紙","values":[12,15,18,19,21,22,24,26,31,38,45]},
 {"label":"システム（春）","values":[8,9,11,12,13,14,15,17,19,24]},
 {"label":"システム（秋）","min":5,"q1":8,"median":11,"q3":13,"max":18}]}
```

### 受付時間の分布（histogram）

```figkit
{"type":"histogram","unit":"分","bins":7,"xlabel":"受付にかかった時間（分）","caption":"図 4 秋の受付時間の分布",
 "values":[5,6,6,7,7,8,8,8,9,9,9,10,10,10,10,11,11,11,11,11,12,12,12,12,13,13,13,14,14,15,15,16,17,18]}
```

### データの持ち方（er）

```figkit
{"type":"er","cols":3,"caption":"図 5 申請まわりのデータ","entities":[
 {"id":"app","label":"申請者","fields":[{"name":"id","type":"int","key":"PK"},{"name":"氏名","type":"text"},{"name":"連絡先","type":"text"}]},
 {"id":"form","label":"申請","fields":[{"name":"id","type":"int","key":"PK"},{"name":"申請者_id","type":"int","key":"FK"},{"name":"種別","type":"text"},{"name":"状態","type":"text"}]},
 {"id":"att","label":"添付","fields":[{"name":"id","type":"int","key":"PK"},{"name":"申請_id","type":"int","key":"FK"},{"name":"ファイル名","type":"text"}]},
 {"id":"win","label":"窓口","fields":[{"name":"id","type":"int","key":"PK"},{"name":"名前","type":"text"}]},
 {"id":"ret","label":"差し戻し","fields":[{"name":"id","type":"int","key":"PK"},{"name":"申請_id","type":"int","key":"FK"},{"name":"理由","type":"text"}]}],
 "relations":[{"from":"app","to":"form","label":"出す","from_card":"1","to_card":"多"},
  {"from":"form","to":"att","label":"持つ","from_card":"1","to_card":"多"},
  {"from":"win","to":"ret","label":"記録する","dashed":true},
  {"from":"form","to":"ret","from_card":"1","to_card":"0..多"}]}
```

### 原因の洗い出し（fishbone）

```figkit
{"type":"fishbone","effect":"差し戻しが多い","caption":"図 6 差し戻しの要因","causes":[
 {"label":"人","items":["窓口の経験の差","繁忙期の応援"]},
 {"label":"方法","items":["確認の手順が口頭","二重の点検なし"]},
 {"label":"画面","items":["必須の印が小さい","住所の入力が長い","添付の案内が下"]},
 {"label":"書類","items":["様式が 3 種類","記入例が古い"]},
 {"label":"環境","items":["窓口が混む時間帯"]}]}
```

## これまでの部品との並び

### 導入の手順
<!-- layout: timeline -->
1. 窓口の端末にアプリを入れる
2. 担当者のアカウントを作る
3. 試しの申請を 1 件通す

### できること
<!-- layout: cards -->
- :check-circle: 承認の流れ {新機能}
- :doc: 控えの印刷 {帳票}
- :clock: 変更の履歴 {監査}

### ふつうの表と引用

| 項目 | 値 | 備考 |
|---|---|---|
| 平均の受付時間 | 11 分 | 春は 14 分 |
| 差し戻しの割合 | 6% | 春は 10% |

> 紙のときは、窓口が閉まってから 1 時間は片付けだった。— 本庁の担当者

- ふつうの箇条書き
  - 入れ子の項目
- **強調** と `code` と [リンク](https://example.com)

> [!NOTE]
> これまでのコールアウト（NOTE）も同じ形で並びます。

> [!WARNING]
> 旧システムのデータは、停止の前に書き出してください。
