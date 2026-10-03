"""motion-video の音（曲・効果音・効果音の組）の定義と、台本の audio を確かめて HTML に埋め込む形にする処理。

曲も効果音も Web Audio で合成する（audio.js）。音声ファイルが無くても鳴り、同じ台本からは同じ音になる。
- 曲（MUSIC）: テンポ・調・音階・和音の進行・層（楽器 × 型）・打楽器の型。章ごとに進行が変わり、章の盛り上がり（energy）で層が増える。
- 効果音（SFX）: 層（発振器・雑音・包絡・フィルタ）の並び。audio.js の冒頭に層の書き方がある。
- 効果音の組（KITS）: 映像の出来事（EVENTS。項目が出る・線がつながる・通知…）に、どの効果音を当てるか。
"""
import base64
import copy
import mimetypes
import os
import re
import sys

# ──────────────────────────────────────────────────────────────────────────
# audio.js と揃える名前（楽器・型・打楽器・音階・調）
# ──────────────────────────────────────────────────────────────────────────
INSTRUMENTS = {
    "pad": "シンセの和音（厚い・柔らか）", "warm": "温かい和音（三角波）", "glass": "ガラスの和音（澄んだ・遅い立ち上がり）",
    "strings": "弦楽の和音", "choir": "声の和音", "organ": "オルガン", "keys": "ピアノ風", "epiano": "エレピ",
    "pluck": "はじく音（シンセ）", "harp": "ハープ", "marimba": "マリンバ", "bell": "鐘・ベル", "kalimba": "カリンバ",
    "koto": "琴", "shaku": "尺八", "flute": "笛", "whistle": "口笛", "lead": "リード（旋律）", "saw": "のこぎり波（鋭い）",
    "brass": "金管", "chip": "8bit（パルス）", "chipsq": "8bit（矩形）", "chiptri": "8bit（三角・低音）", "pizz": "ピチカート",
    "clav": "クラビネット", "harpsi": "チェンバロ", "power": "歪んだギター風（5 度）", "bass": "ベース", "sub": "重低音",
    "fmbass": "FM ベース", "synthbass": "シンセベース", "acid": "アシッド（うねるベース）", "upright": "ウッドベース",
    "crackle": "レコードの雑音（質感）",
    "steel": "スチールドラム", "sitar": "シタール風", "shamisen": "三味線", "uke": "ウクレレ・アコースティック", "banjo": "バンジョー",
    "accordion": "アコーディオン", "bandoneon": "バンドネオン", "harmonica": "ハーモニカ", "oohs": "声の和音（ウー）", "sho": "笙",
    "vibes": "ビブラフォン", "glock": "鉄琴", "musicbox": "オルゴール", "tubular": "チューブラーベル", "supersaw": "分厚いシンセ（スーパーソウ）",
    "slap": "スラップ・ベース", "sub808": "808 の重低音",
    "kick": "バスドラム", "snare": "スネア", "clap": "クラップ", "hat": "ハイハット", "ohat": "オープンハイハット", "ride": "ライド",
    "rim": "リム", "tom": "タム", "taiko": "太鼓", "shaker": "シェイカー", "crash": "クラッシュ", "tick": "時計の刻み",
    "brush": "ブラシ", "timpani": "ティンパニ", "chipnoise": "8bit の雑音", "chipkick": "8bit のキック",
    "conga": "コンガ", "bongo": "ボンゴ", "tabla": "タブラ", "cowbell": "カウベル", "tamb": "タンバリン", "kick808": "808 のキック",
    "gated": "80 年代のスネア", "kane": "当たり鉦", "block": "ウッドブロック",
}
PATTERNS = {
    "hold": "和音を小節いっぱい伸ばす", "half": "和音を 2 分音符で", "beat": "和音を拍ごとに", "off": "和音を裏拍に",
    "stab": "和音を rhy の律動で（rhy: \"x..x..x.\" x=打つ X=強く g=弱く）", "strum": "和音をかき鳴らす（rhy の律動）",
    "arp8": "分散和音（8 分・上る）", "arp16": "分散和音（16 分・上る）", "arpud8": "分散和音（上り下り）", "arpud16": "分散和音（16 分・上り下り）",
    "arpdn8": "分散和音（下る）", "arpdn16": "分散和音（16 分・下る）", "arprnd8": "分散和音（ばらばら）", "arprnd16": "分散和音（16 分・ばらばら）",
    "broken8": "1-5-8-5 の分散", "alberti16": "アルベルティ・バス（1-5-3-5）",
    "root1": "根音を全音符", "root2": "根音を 2 分", "root4": "根音を 4 分", "root8": "根音を 8 分", "pulse16": "根音を 16 分で刻む",
    "oct8": "根音とオクターブを交互に", "fifth": "根音と 5 度を交互に", "walk": "ウォーキング・ベース", "syncop": "根音を跳ねる律動で（rhy で変更可）",
    "melody": "旋律を作る（dens: 0..1 で音の多さ。4 小節ずつくり返す）", "bells": "和音の音を所々に（p: 0..1 で出る割合）",
    "drone": "調の根音と 5 度を伸ばし続ける", "ostinato": "音階の度数の並び（seq）をくり返す（step: 刻み）", "counter": "和音の上の音を伸ばす（対旋律）",
    "skank": "和音を 2・4 拍の裏で短く（レゲエの刻み）", "pump8": "和音を 8 分で脈打たせる（ダンスの分厚い和音）", "tremolo": "和音を 16 分で細かく刻む（弦のトレモロ）",
    "tango": "和音を鋭く短く（タンゴの刻み。rhy で変更可）", "stride": "根音と和音を交互に（ブンチャッチャ・行進）", "gallop": "根音を駆ける律動で（x.xx）",
    "habanera": "ハバネラの低音（付点の律動）", "arpoct": "根音・オクターブ・5 度の 16 分", "pedal8": "調の根音を 8 分で持続（和音が変わっても動かない）",
    "arp3": "3 音ずつの分散（拍とずれて回る）", "run": "2 小節ごとに音階を駆け上がる（後半 2 拍）", "tanpura": "5 度と根音を順にはじく持続（タンプーラ）",
}
DRUMS = ["pulse", "soft", "four", "house", "backbeat", "rock", "halftime", "lofi", "breaks", "dnb", "trap", "funk", "bossa", "brush",
         "reggae", "march", "taiko", "matsuri", "cinematic", "tick", "clock", "heart", "shaker", "ostinato", "chip", "waltz", "sixeight",
         "boombap", "trap2", "futurebass", "reggaeton", "samba", "tango", "swing", "shuffle", "polka", "techno", "garage", "eighties", "salsa",
         "tabla", "ballad", "bon", "maqsum", "train", "palmas", "ska"]
SCALES = ["major", "minor", "dorian", "phrygian", "lydian", "mixolydian", "harmonic", "pentamaj", "pentamin", "blues",
          "yo", "in", "ryukyu", "hirajoshi", "whole", "hijaz", "bhairav", "melodic", "dim", "iwato"]
KEYS = ["C", "C#", "Db", "D", "D#", "Eb", "E", "F", "F#", "Gb", "G", "G#", "Ab", "A", "A#", "Bb", "B"]
LAYER_KEYS = {"w", "f", "fr", "ft", "fe", "a", "h", "d", "v", "at", "sus", "lin", "flt", "fk", "dt", "pe", "vib", "fm", "sh", "pan",
              "nr", "pw", "rep", "gap", "notes", "rf", "rv", "rj", "vj"}
WAVES = {"sine", "square", "sawtooth", "triangle", "pulse", "noise"}


# ──────────────────────────────────────────────────────────────────────────
# 曲
# ──────────────────────────────────────────────────────────────────────────
def L(inst, pat, oct=4, v=1.0, e=1, **kw):
    d = {"inst": inst, "pat": pat, "oct": oct, "v": v}
    if e != 1:
        d["e"] = e
    d.update(kw)
    return d


def M(cat, name, desc, bpm, key, scale, prog, layers, drum=None, **kw):
    d = {"cat": cat, "name": name, "desc": desc, "bpm": bpm, "key": key, "scale": scale, "prog": prog, "layers": layers}
    if drum:
        d["drum"] = drum
    d.update(kw)
    return d


MUSIC = {
    # ── 落ち着き
    "calm": M("落ち着き", "穏やか", "柔らかい和音に鈴が時々。製品紹介の既定", 72, "D", "major", [["1", "5", "6", "4"], ["6", "4", "1", "5"], ["4", "5", "3", "6"]],
              [L("warm", "hold", 3), L("sub", "root1", 2, .8), L("bell", "bells", 5, .5, p=.15), L("harp", "arpud8", 4, .45, e=2), L("strings", "counter", 4, .45, e=3)]),
    "deep": M("落ち着き", "深い", "低い弦と重低音。技術の解説・夜の雰囲気", 60, "A", "minor", [["1", "6", "3", "7"], ["1", "4", "6", "5"]],
              [L("strings", "hold", 3), L("sub", "root1", 2, .9), L("bell", "bells", 5, .4, p=.1), L("glass", "counter", 5, .5, e=2), L("pluck", "arpud8", 4, .35, e=3)]),
    "drift": M("落ち着き", "漂う", "リディアの浮遊感。考える・待つ場面", 64, "F", "lydian", [["1", "2", "1", "7"]],
               [L("glass", "hold", 4), L("pad", "hold", 3, .7), L("kalimba", "arpud8", 5, .35, e=2, hold=2), L("sub", "root2", 2, .6)]),
    "dawn": M("落ち着き", "夜明け", "ハープが上り下りし、少しずつ明るく", 80, "G", "major", [["4", "1", "5", "6"]],
              [L("warm", "hold", 3), L("harp", "arpud8", 4, .5), L("sub", "root2", 2, .7), L("flute", "melody", 5, .45, e=3, dens=.2)], drum="pulse", de=2),
    "mist": M("落ち着き", "霧", "声の和音と鐘。静かな導入・余韻", 56, "E", "dorian", [["1", "4", "1", "7"]],
              [L("choir", "hold", 3), L("bell", "bells", 5, .45, p=.12), L("sub", "root1", 2, .7), L("glass", "counter", 5, .4, e=2)]),
    "ocean": M("落ち着き", "海辺", "カリンバの粒とシェイカー。ゆったりした紹介", 68, "C", "major", [["1", "6", "4", "5"]],
               [L("pad", "hold", 3, .8), L("kalimba", "bells", 5, .6, p=.3), L("sub", "root2", 2, .7)], drum="shaker", de=2, dv=.6),
    "space": M("落ち着き", "宇宙", "広がる和音と遠い鐘。壮大・静か", 50, "C", "lydian", [["1", "2"]],
               [L("glass", "hold", 4), L("pad", "hold", 3), L("sub", "drone", 1, .8), L("bell", "bells", 6, .3, p=.12)], cb=2),
    "rain": M("落ち着き", "雨の日", "エレピとレコードの雑音。くつろいだ解説", 66, "Bb", "major", [["1", "4", "6", "5"]],
              [L("epiano", "half", 4, .7), L("sub", "root1", 2), L("crackle", "hold", 4, .8), L("bell", "bells", 5, .3, p=.1)], sevenths=True),
    "forest": M("落ち着き", "森", "五音音階のカリンバと笛。自然・やさしい", 76, "D", "pentamaj", [["1", "4", "5", "1"]],
                [L("kalimba", "arpud8", 5, .5), L("warm", "hold", 3, .8), L("flute", "melody", 5, .45, e=2, dens=.25)], drum="soft", de=2, dv=.5),
    # ── 企業・製品
    "bright": M("企業・製品", "明るい", "はじく音の分散和音と軽い拍。前向きな製品紹介", 110, "G", "major", [["1", "5", "6", "4"]],
                [L("pluck", "arp8", 4, .7), L("warm", "hold", 3, .6), L("bass", "root8", 2, .7), L("keys", "stab", 4, .5, e=3, rhy="x..x..x.")], drum="backbeat", de=2, dv=.6),
    "corporate": M("企業・製品", "企業", "ピアノの分散と弦。会社・サービスの紹介の定番", 100, "C", "major", [["1", "5", "6", "4"], ["4", "5", "1", "6"]],
                   [L("keys", "broken8", 4, .8), L("strings", "hold", 3, .6), L("bass", "root4", 2, .7)], drum="four", de=2, dv=.45),
    "innovate": M("企業・製品", "革新", "16 分の分散和音とシンセベース。新製品・技術の発表", 118, "E", "major", [["6", "4", "1", "5"]],
                  [L("pluck", "arp16", 4, .6), L("pad", "hold", 3, .6), L("synthbass", "oct8", 2, .7), L("lead", "melody", 5, .4, e=3, dens=.5)], drum="four", de=2),
    "trust": M("企業・製品", "信頼", "拍ごとのピアノと弦。落ち着いた説明・金融・医療", 90, "F", "major", [["1", "3", "4", "5"]],
               [L("keys", "beat", 4, .6), L("strings", "hold", 3, .7), L("bass", "root2", 2, .7)], drum="pulse", de=2, dv=.6),
    "growth": M("企業・製品", "成長", "裏拍のピアノが前へ進む。実績・成長の話", 108, "A", "mixolydian", [["1", "7", "4", "1"]],
                [L("keys", "off", 4, .6), L("pluck", "arp8", 5, .45, e=2), L("bass", "root8", 2, .7)], drum="backbeat", de=2, dv=.6),
    "clean": M("企業・製品", "清潔", "マリンバの粒。家庭・生活の製品", 96, "C", "major", [["1", "4", "6", "5"]],
               [L("marimba", "arp8", 4, .6), L("warm", "hold", 3, .5), L("bass", "root4", 2, .6)], drum="shaker", de=2, dv=.5),
    "keynote": M("企業・製品", "基調講演", "短調の 16 分と四つ打ち。発表会の高揚", 120, "D", "minor", [["1", "6", "3", "7"]],
                 [L("pluck", "arp16", 4, .5), L("strings", "hold", 3, .6), L("synthbass", "pulse16", 2, .55)], drum="four", de=2),
    "launch": M("企業・製品", "発表", "裏拍の和音と旋律。発売・公開の告知", 124, "A", "major", [["4", "5", "6", "1"]],
                [L("saw", "stab", 4, .5, rhy="..x...x...x...x."), L("pad", "hold", 3, .5), L("bass", "oct8", 2, .7), L("lead", "melody", 5, .45, e=3, dens=.6)], drum="four"),
    "pitch": M("企業・製品", "提案", "エレピと柔らかい拍。提案・企画の説明", 104, "Bb", "major", [["1", "5", "2", "4"]],
               [L("epiano", "beat", 4, .6), L("bass", "root4", 2), L("bell", "bells", 5, .3, e=2, p=.15)], drum="soft", de=2),
    "startup": M("企業・製品", "スタートアップ", "口笛の旋律と軽い拍。若い会社・アプリ", 116, "E", "major", [["1", "3", "6", "4"]],
                 [L("pluck", "arp8", 5, .5), L("keys", "off", 4, .5), L("bass", "root8", 2, .7), L("whistle", "melody", 5, .35, e=3, dens=.4)], drum="backbeat", de=2, dv=.7),
    # ── 技術
    "tech": M("技術", "技術", "16 分の分散と刻み。開発者向けの解説", 112, "E", "minor", [["1", "6", "7", "5"]],
              [L("pluck", "arp16", 4, .5), L("pad", "hold", 3, .5), L("fmbass", "pulse16", 2, .5)], drum="tick", de=2),
    "circuit": M("技術", "回路", "8bit の粒とうねるベース。電子・仕組みの話", 124, "A", "dorian", [["1", "4"]],
                 [L("chipsq", "arp16", 5, .35), L("acid", "syncop", 2, .7), L("pad", "hold", 3, .4)], drum="four", de=2, cb=2),
    "data": M("技術", "データ", "ばらばらの鐘の粒。データ・分析", 100, "C#", "minor", [["1", "6", "4", "5"]],
              [L("bell", "arprnd16", 5, .2), L("pad", "hold", 3, .6), L("sub", "root1", 2, .8)], drum="tick", de=2, dv=.6),
    "cyber": M("技術", "サイバー", "フリジアの暗さと四つ打ち。セキュリティ・攻撃と防御", 128, "F", "phrygian", [["1", "2", "1", "7"]],
               [L("pad", "hold", 3, .6), L("acid", "pulse16", 2, .6), L("lead", "melody", 5, .35, e=3, dens=.6)], drum="house", de=2),
    "synthwave": M("技術", "シンセウェーブ", "80 年代のシンセと旋律。レトロな未来", 96, "A", "minor", [["1", "6", "3", "7"]],
                   [L("pad", "hold", 3, .7), L("synthbass", "oct8", 2, .7), L("lead", "melody", 5, .45, e=2, dens=.4), L("saw", "arp16", 5, .25, e=3)], drum="backbeat", dv=.8),
    "neon": M("技術", "ネオン", "エレピの裏拍と跳ねるベース。都会的", 110, "F#", "minor", [["1", "4", "6", "5"]],
              [L("epiano", "off", 4, .6), L("pad", "hold", 3, .5), L("bass", "syncop", 2, .7)], drum="backbeat", de=2, dv=.7, sevenths=True),
    "hacker": M("技術", "ハッカー", "下る 16 分と速い拍。緊迫した作業", 140, "B", "minor", [["1", "1", "6", "7"]],
                [L("pluck", "arpdn16", 4, .45), L("sub", "pulse16", 2, .5), L("pad", "hold", 3, .4, e=2)], drum="dnb", de=2),
    "ai": M("技術", "知能", "澄んだ上り下りと広い和音。AI・未来の話", 90, "D", "lydian", [["1", "2", "5", "1"]],
            [L("glass", "hold", 4, .5), L("bell", "arpud16", 5, .25), L("pad", "hold", 3, .6), L("sub", "root2", 2, .7)], drum="pulse", de=2),
    "quantum": M("技術", "量子", "全音音階の不思議な和音。先端研究・謎", 84, "C", "whole", [["1", "2"]],
                 [L("glass", "hold", 4, .7), L("bell", "arpud8", 5, .3), L("sub", "drone", 1, .7)], cb=2),
    "robot": M("技術", "機械", "8bit のくり返しと FM ベース。自動化・ロボット", 118, "G", "minor", [["1", "4", "1", "5"]],
               [L("chipsq", "ostinato", 4, .35, seq=[0, 4, 7, 4, 2, 4, 7, 4], step=2), L("fmbass", "root8", 2, .6), L("clav", "stab", 4, .4, e=2, rhy="x..x....x..x....")], drum="tick"),
    # ── ポップ
    "pop": M("ポップ", "ポップ", "ピアノの刻みと旋律。親しみやすい紹介", 120, "C", "major", [["1", "5", "6", "4"]],
             [L("keys", "stab", 4, .6, rhy="x...x.x.x...x.x."), L("pluck", "arp8", 5, .4, e=2), L("bass", "root8", 2, .7), L("lead", "melody", 5, .4, e=2, dens=.5)], drum="backbeat"),
    "happy": M("ポップ", "楽しい", "マリンバと口笛。明るい・楽しいサービス", 132, "F", "major", [["1", "4", "5", "1"]],
               [L("marimba", "arp8", 4, .6), L("keys", "off", 4, .5), L("bass", "fifth", 2, .7), L("whistle", "melody", 5, .4, e=2, dens=.55)], drum="backbeat", dv=.7),
    "sunny": M("ポップ", "晴れ", "かき鳴らしとシェイカー。旅行・屋外", 116, "G", "mixolydian", [["1", "7", "4", "1"]],
               [L("pluck", "strum", 4, .5, rhy="x..x..x.x.x.x..."), L("bass", "root4", 2, .7), L("flute", "melody", 5, .35, e=3, dens=.4)], drum="shaker", dv=.7),
    "kids": M("ポップ", "子ども", "8bit の旋律とマリンバ。子ども・教育", 128, "C", "major", [["1", "4", "5", "1"]],
              [L("chip", "melody", 5, .5, dens=.5), L("marimba", "arp8", 4, .45), L("bass", "fifth", 2, .6)], drum="march", de=2, dv=.6),
    "summer": M("ポップ", "夏", "カリンバと裏拍・レゲエの拍。夏・休日", 104, "A", "major", [["1", "5", "6", "4"]],
                [L("kalimba", "arpud8", 5, .5), L("pluck", "off", 4, .45), L("bass", "syncop", 2, .7)], drum="reggae", dv=.7),
    "disco": M("ポップ", "ディスコ", "オクターブのベースと四つ打ち。イベント・祝い", 120, "A", "minor", [["1", "6", "4", "5"]],
               [L("epiano", "off", 4, .5), L("bass", "oct8", 2, .7), L("pluck", "arp16", 5, .3, e=3)], drum="house", sevenths=True),
    "idol": M("ポップ", "アイドル", "速い 16 分と旋律。元気・告知", 150, "E", "major", [["4", "5", "3", "6"]],
              [L("pluck", "arp16", 5, .4), L("keys", "stab", 4, .5, rhy="x.x.x.x.x.x.x.x."), L("bass", "oct8", 2, .7), L("lead", "melody", 5, .4, e=2, dens=.65)], drum="four"),
    # ── ジャズ・ローファイ
    "lofi": M("ジャズ・ローファイ", "ローファイ", "7 の和音のエレピ・跳ねる拍・レコードの雑音。作業・学習", 80, "F", "major", [["2", "5", "1", "6"]],
              [L("epiano", "hold", 4, .6), L("bass", "root2", 2, .7), L("crackle", "hold", 4), L("bell", "bells", 5, .25, e=2, p=.1)], drum="lofi", dv=.8, swing=.3, sevenths=True),
    "study": M("ジャズ・ローファイ", "勉強", "ピアノの分散と控えめな拍。研修・講義", 72, "C", "major", [["1", "6", "2", "5"]],
               [L("keys", "broken8", 4, .6), L("bass", "root2", 2, .6), L("crackle", "hold", 4, .8)], drum="lofi", de=2, dv=.6, swing=.25, sevenths=True),
    "jazz": M("ジャズ・ローファイ", "ジャズ", "ウォーキング・ベースとブラシ。大人の雰囲気", 120, "Bb", "major", [["2", "5", "1", "6"]],
              [L("upright", "walk", 2, .8), L("epiano", "stab", 4, .5, rhy="x.....x...x....."), L("flute", "melody", 5, .3, e=3, dens=.45)], drum="brush", swing=.55, sevenths=True),
    "bossa": M("ジャズ・ローファイ", "ボサノバ", "ギター風の刻みとボサノバの拍。カフェ・生活", 132, "D", "major", [["1", "6", "2", "5"]],
               [L("pluck", "stab", 4, .5, rhy="x..x..x...x..x.."), L("bass", "fifth", 2, .7), L("flute", "melody", 5, .35, e=2, dens=.35)], drum="bossa", dv=.7, sevenths=True),
    "night": M("ジャズ・ローファイ", "夜更け", "短調のエレピとブラシ。夜・落ち着いた", 68, "C#", "minor", [["1", "4", "6", "5"]],
               [L("epiano", "half", 4, .6), L("sub", "root2", 2, .7)], drum="brush", de=2, dv=.5, swing=.2, sevenths=True),
    "cafe": M("ジャズ・ローファイ", "カフェ", "エレピとウッドベース。飲食・店舗", 92, "G", "major", [["1", "3", "6", "2", "5", "1"]],
              [L("epiano", "beat", 4, .5), L("upright", "walk", 2, .7)], drum="brush", dv=.6, swing=.2, sevenths=True),
    "soul": M("ジャズ・ローファイ", "ソウル", "オルガンと跳ねるベース。温かい人物紹介", 88, "Eb", "major", [["1", "4", "2", "5"]],
              [L("organ", "hold", 4, .5), L("epiano", "off", 4, .4), L("bass", "syncop", 2, .7)], drum="backbeat", dv=.7, swing=.15, sevenths=True),
    # ── 物語・映画
    "epic": M("物語・映画", "壮大", "弦と金管と太鼓。大きな発表・ビジョン", 90, "D", "minor", [["1", "6", "3", "7"]],
              [L("strings", "hold", 3, .8), L("brass", "beat", 4, .4, e=2), L("choir", "hold", 4, .5, e=3), L("sub", "root1", 2, .7)], drum="cinematic", de=2),
    "hero": M("物語・映画", "英雄", "金管の旋律と行進の拍。挑戦・達成", 100, "C", "major", [["1", "5", "6", "4"], ["4", "5", "1", "1"]],
              [L("strings", "hold", 3, .7), L("brass", "melody", 4, .5, e=2, dens=.45), L("bass", "root4", 2, .6)], drum="march", de=2, dv=.7),
    "tension": M("物語・映画", "緊張", "弦の刻みと時計。課題・危機の提示", 100, "E", "harmonic", [["1", "1", "6", "5"]],
                 [L("strings", "ostinato", 3, .45, seq=[0, 0, 1, 0, 0, 0, 2, 1], step=1, hold=1.1), L("sub", "root1", 2, .8), L("bell", "bells", 6, .3, e=2, p=.08)], drum="tick", dv=.6),
    "mystery": M("物語・映画", "謎", "所々の鐘と暗い和音。謎・問いかけ", 70, "B", "phrygian", [["1", "2", "1", "7"]],
                 [L("bell", "bells", 5, .5, p=.2), L("pad", "hold", 3, .6), L("sub", "root1", 2, .7), L("glass", "counter", 5, .3, e=2)]),
    "sad": M("物語・映画", "切ない", "短調のピアノの分散。困りごと・過去の苦労", 66, "E", "minor", [["1", "6", "4", "5"]],
             [L("keys", "broken8", 4, .7), L("strings", "hold", 3, .6, e=2), L("sub", "root1", 2, .7)]),
    "hope": M("物語・映画", "希望", "ピアノの上り下りに弦が加わる。解決・前進", 76, "D", "major", [["4", "1", "5", "6"]],
              [L("keys", "arpud8", 4, .6), L("strings", "hold", 3, .6, e=2), L("bass", "root1", 2, .6), L("glass", "counter", 5, .4, e=3)]),
    "wonder": M("物語・映画", "驚き", "ハープの 16 分と鐘の旋律。発見・魔法", 84, "G", "lydian", [["1", "2", "1", "2"]],
                [L("harp", "arpud16", 4, .45), L("glass", "hold", 4, .6), L("strings", "hold", 3, .4, e=2), L("bell", "melody", 6, .3, e=3, dens=.3)]),
    "trailer": M("物語・映画", "予告", "遅い刻みと太鼓と金管。予告・ティザー", 60, "C", "minor", [["1", "6", "4", "5"]],
                 [L("strings", "ostinato", 3, .45, seq=[0], step=2, hold=.8), L("brass", "hold", 3, .45, e=2), L("sub", "root1", 1, .9)], drum="cinematic"),
    "documentary": M("物語・映画", "記録", "拍ごとのピアノと弦。記録・社会の話", 86, "D", "dorian", [["1", "4", "7", "1"]],
                     [L("keys", "beat", 4, .5), L("strings", "hold", 3, .5), L("bass", "root2", 2, .6)], drum="shaker", de=2, dv=.4),
    "adventure": M("物語・映画", "冒険", "弦の分散と金管の合いの手。旅・挑戦", 112, "D", "mixolydian", [["1", "7", "4", "1"]],
                   [L("strings", "arp8", 4, .45), L("brass", "stab", 4, .4, e=2, rhy="x.....x.x......."), L("bass", "root4", 2, .7)], drum="march", de=2, dv=.6),
    "memory": M("物語・映画", "思い出", "ピアノの分散と遠い鐘。沿革・振り返り", 70, "F", "major", [["1", "3", "4", "5"]],
                [L("keys", "broken8", 4, .6), L("strings", "counter", 4, .4, e=2), L("sub", "root2", 2, .6), L("bell", "bells", 6, .25, p=.08)]),
    "suspense": M("物語・映画", "不穏", "心音と重い和音。リスク・警告", 80, "C#", "harmonic", [["1", "6"]],
                  [L("pad", "hold", 3, .6), L("sub", "drone", 1, .7), L("bell", "arprnd8", 6, .12, e=2)], drum="heart", dv=.8, cb=2),
    # ── 和・民族
    "wa": M("和・民族", "和", "琴の分散と尺八と太鼓。日本の文化・伝統", 84, "D", "yo", [["1", "4", "5", "1"]],
            [L("koto", "arp8", 4, .5), L("shaku", "melody", 5, .5, e=2, dens=.3), L("warm", "hold", 3, .4)], drum="taiko", de=2, dv=.7),
    "matsuri": M("和・民族", "祭", "笛の旋律と祭りの太鼓。行事・にぎわい", 132, "G", "yo", [["1", "4", "1", "5"]],
                 [L("flute", "melody", 5, .5, dens=.7), L("koto", "stab", 4, .4, rhy="x.x.x.x."), L("bass", "root4", 2, .5)], drum="matsuri"),
    "kyoto": M("和・民族", "京", "都節の琴と鐘。和の落ち着き・老舗", 66, "E", "in", [["1", "4", "1", "5"]],
               [L("koto", "broken8", 4, .6), L("pad", "hold", 3, .4), L("bell", "bells", 5, .3, p=.12), L("shaku", "melody", 5, .35, e=2, dens=.2)]),
    "ryukyu": M("和・民族", "琉球", "琉球音階のはじく音。沖縄・南の島", 104, "C", "ryukyu", [["1", "4", "5", "1"]],
                [L("pluck", "arp8", 4, .5), L("bass", "fifth", 2, .6), L("flute", "melody", 5, .35, e=2, dens=.45)], drum="shaker", dv=.6),
    "zen": M("和・民族", "禅", "尺八と鐘だけの静けさ。瞑想・余白", 56, "A", "in", [["1", "1", "4", "1"]],
             [L("shaku", "melody", 5, .5, dens=.15), L("bell", "bells", 5, .35, p=.08), L("sub", "drone", 1, .7)]),
    "celtic": M("和・民族", "ケルト", "3 拍子の笛とハープ。物語・手作り", 116, "D", "dorian", [["1", "7", "1", "4"]],
                [L("flute", "melody", 5, .5, dens=.6), L("harp", "arp8", 4, .4), L("bass", "root1", 2, .6)], drum="sixeight", beats=3),
    "orient": M("和・民族", "東洋", "五音の琴と広い和音。アジア・旅", 78, "A", "pentamin", [["1", "4", "1", "5"]],
                [L("koto", "arpud8", 4, .45), L("glass", "hold", 3, .5), L("flute", "melody", 5, .35, e=2, dens=.3)], drum="taiko", de=2, dv=.4),
    "desert": M("和・民族", "砂漠", "フリジアのくり返しと重低音。異国・乾いた", 96, "D", "phrygian", [["1", "2", "1", "2"]],
                [L("pluck", "ostinato", 4, .45, seq=[0, 1, 2, 1, 0, 1, 4, 3], step=2), L("sub", "drone", 1, .7), L("flute", "melody", 5, .35, e=2, dens=.4)], drum="halftime", dv=.5),
    "island": M("和・民族", "南国", "カリンバとマリンバの裏拍。リゾート", 108, "F", "major", [["1", "4", "5", "4"]],
                [L("kalimba", "arp8", 5, .5), L("marimba", "off", 4, .45), L("bass", "root4", 2, .6)], drum="reggae", dv=.6),
    # ── ゲーム
    "chiptune": M("ゲーム", "8bit", "8bit の旋律と分散。ゲーム・レトロ", 140, "C", "major", [["1", "6", "4", "5"]],
                  [L("chip", "melody", 5, .5, dens=.6), L("chipsq", "arp16", 4, .3), L("chiptri", "root8", 2, .8)], drum="chip"),
    "arcade": M("ゲーム", "アーケード", "短調の速い 8bit。対戦・競争", 150, "A", "minor", [["1", "6", "7", "1"]],
                [L("chip", "melody", 5, .45, dens=.7), L("chipsq", "off", 4, .3), L("chiptri", "oct8", 2, .8)], drum="chip"),
    "puzzle": M("ゲーム", "パズル", "マリンバの旋律とピチカート。考える・解く", 110, "F", "major", [["1", "2", "5", "1"]],
                [L("marimba", "melody", 5, .5, dens=.5), L("pizz", "off", 4, .45), L("bass", "fifth", 2, .5)], drum="clock", dv=.6),
    "rpg": M("ゲーム", "冒険の旅", "笛とハープと行進。手順・旅の案内", 104, "D", "dorian", [["1", "7", "6", "7"]],
             [L("flute", "melody", 5, .45, dens=.45), L("harp", "arp8", 4, .4), L("bass", "root4", 2, .6)], drum="march", de=2, dv=.5),
    # ── クラシック風
    "waltz": M("クラシック風", "ワルツ", "3 拍子のブンチャッチャ。優雅・招待", 150, "F", "major", [["1", "4", "5", "1"]],
               [L("bass", "root1", 2, .7), L("pizz", "stab", 4, .5, rhy="....x...x..."), L("strings", "melody", 5, .45, e=2, dens=.4)], drum="waltz", de=2, dv=.4, beats=3),
    "baroque": M("クラシック風", "バロック", "チェンバロのアルベルティと歩くベース。格式・伝統", 100, "A", "harmonic", [["1", "4", "5", "1"]],
                 [L("harpsi", "alberti16", 4, .5), L("upright", "walk", 2, .6), L("strings", "counter", 5, .35, e=2)]),
    "piano": M("クラシック風", "ピアノ", "ピアノの分散と旋律だけ。語り・手紙", 70, "C", "major", [["1", "5", "6", "3", "4", "1", "4", "5"]],
               [L("keys", "broken8", 4, .7), L("keys", "melody", 5, .5, e=2, dens=.35)]),
    "strings": M("クラシック風", "弦楽", "弦の和音と旋律。感謝・式典", 64, "D", "minor", [["1", "4", "7", "3"]],
                 [L("strings", "hold", 3, .8), L("strings", "melody", 5, .45, e=2, dens=.3), L("sub", "root1", 2, .5)]),
    "chamber": M("クラシック風", "室内楽", "カノン進行のピチカートと弦。結婚・記念", 88, "G", "major", [["1", "5", "6", "3", "4", "1", "4", "5"]],
                 [L("pizz", "arp8", 4, .4), L("strings", "hold", 3, .6), L("strings", "melody", 5, .4, e=2, dens=.4), L("upright", "root4", 2, .5)]),
    "musicbox": M("クラシック風", "オルゴール", "鐘の旋律と分散。子ども・贈り物", 84, "E", "major", [["1", "4", "5", "1"]],
                  [L("bell", "melody", 6, .4, dens=.5), L("bell", "arp8", 5, .25)]),
    # ── エネルギー
    "drive": M("エネルギー", "疾走", "裏拍のシンセと速い拍。スピード・性能", 150, "E", "minor", [["1", "6", "7", "1"]],
               [L("saw", "off", 4, .45), L("bass", "pulse16", 2, .5), L("lead", "melody", 5, .35, e=3, dens=.6)], drum="dnb"),
    "sport": M("エネルギー", "スポーツ", "金管の合いの手と四つ打ち。スポーツ・勝負", 128, "D", "major", [["1", "4", "5", "5"]],
               [L("brass", "stab", 4, .45, rhy="x..x..x.x......."), L("bass", "oct8", 2, .7)], drum="four"),
    "rock": M("エネルギー", "ロック", "歪んだギター風と 8 ビート。力強い主張", 120, "E", "minor", [["1", "6", "7", "1"]],
              [L("power", "stab", 3, .6, rhy="x.x.x.x.x.x.x.x."), L("bass", "root8", 2, .7), L("lead", "melody", 5, .35, e=3, dens=.5)], drum="rock", dv=.9),
    "funk": M("エネルギー", "ファンク", "クラビとスラップ風のベース。遊び心", 108, "A", "dorian", [["1", "4"]],
              [L("clav", "stab", 4, .5, rhy="x.xx..x.x.xx..x."), L("bass", "syncop", 2, .8, rhy="x..x..x.x.x..x..")], drum="funk", swing16=.3, cb=2),
    "house": M("エネルギー", "ハウス", "エレピの裏拍と四つ打ち。イベント・夜", 124, "G", "minor", [["1", "6", "4", "5"]],
               [L("epiano", "off", 4, .5), L("bass", "syncop", 2, .6, rhy="..x...x...x...x."), L("pad", "hold", 3, .4, e=2)], drum="house", sevenths=True),
    "countdown": M("エネルギー", "秒読み", "時計の刻みと 16 分の低音。締め切り・カウントダウン", 120, "A", "minor", [["1", "1", "6", "5"]],
                   [L("pluck", "ostinato", 4, .4, seq=[0, 4], step=4), L("sub", "pulse16", 2, .5), L("strings", "hold", 3, .4, e=2)], drum="tick"),
    "pulse": M("エネルギー", "鼓動", "心音の拍と和音。命・医療・緊張", 60, "C", "minor", [["1", "6"]],
               [L("pad", "hold", 3, .6), L("sub", "root1", 2, .6)], drum="heart", dv=.9, cb=2),
    "hype": M("エネルギー", "高揚", "跳ねる和音と四つ打ち。盛り上がり・発表の山場", 140, "F", "minor", [["6", "4", "1", "5"]],
              [L("saw", "stab", 4, .45, rhy="x..x..x.x..x..x."), L("bass", "oct8", 2, .7), L("pluck", "arp16", 5, .3, e=2), L("lead", "melody", 5, .35, e=3, dens=.6)], drum="four"),
    # ── ミニマル
    "minimal": M("ミニマル", "ミニマル", "マリンバのくり返し。すっきりした説明", 100, "D", "major", [["1", "1", "4", "1"]],
                 [L("marimba", "ostinato", 4, .5, seq=[0, 2, 4, 7, 4, 2], step=2), L("glass", "hold", 4, .4, e=2)], drum="pulse", de=2, dv=.5),
    "clock": M("ミニマル", "時計", "時計の刻みと鐘の粒。時間・スケジュール", 120, "C", "major", [["1", "4", "5", "1"]],
               [L("bell", "arprnd8", 5, .15), L("pad", "hold", 3, .4)], drum="clock"),
    "glass": M("ミニマル", "ガラスの粒", "16 分の鐘の粒だけ。透明・精密", 100, "A", "lydian", [["1", "2"]],
               [L("bell", "arp16", 5, .2), L("sub", "root2", 2, .5)], cb=2),
    "steps": M("ミニマル", "反復", "ずれていく 2 つのくり返し。工程・仕組み", 120, "E", "minor", [["1", "6"]],
               [L("pluck", "ostinato", 4, .45, seq=[0, 4, 7, 4, 9, 4, 7, 4], step=1), L("marimba", "ostinato", 5, .3, e=2, seq=[0, 2, 4, 2], step=3), L("sub", "root1", 2, .5)], cb=2),
    # ── 追加: 落ち着き
    "snow": M("落ち着き", "雪", "オルゴールと鉄琴と柔らかい和音。冬・静かな喜び", 76, "A", "major", [["1", "5", "6", "4"]],
              [L("musicbox", "arpud8", 5, .35), L("glock", "bells", 6, .25, p=.12), L("warm", "hold", 3, .5), L("sub", "root1", 2, .5)]),
    "aurora": M("落ち着き", "オーロラ", "澄んだ和音と声と管の鐘。壮大な静けさ", 54, "B", "lydian", [["1", "2"]],
                [L("glass", "hold", 4, .5), L("oohs", "hold", 3, .4), L("tubular", "bells", 5, .2, p=.06), L("sub", "drone", 1, .5)], cb=2),
    "meditation": M("落ち着き", "瞑想", "5 度と根音を順にはじく持続と遠い鐘。呼吸・マインドフルネス", 48, "G", "pentamaj", [["1"]],
                    [L("warm", "tanpura", 3, .45), L("tubular", "bells", 5, .25, p=.05), L("sub", "drone", 1, .5)]),
    # ── 追加: ポップ
    "citypop": M("ポップ", "シティポップ", "スラップのベースとエレピと 80 年代の拍。夜景・都会", 112, "F", "major", [["4", "3", "2", "1"], ["4", "5", "3", "6"]],
                 [L("epiano", "stab", 4, .5, rhy="x..x..x...x..x.."), L("slap", "syncop", 2, .8, rhy="x..x..x.x.x..x.x"), L("brass", "stab", 4, .35, e=2, rhy="......x.x......."),
                  L("lead", "melody", 5, .35, e=3, dens=.5)], drum="eighties", sevenths=True, swing16=.15),
    "nursery": M("ポップ", "童謡", "鉄琴の歌とウクレレ。子ども・保育・絵本", 100, "C", "major", [["1", "4", "1", "5"], ["1", "4", "5", "1"]],
                 [L("glock", "melody", 5, .5, dens=.4), L("uke", "strum", 4, .45, rhy="x.x.x.x.x.x.x.x."), L("bass", "root4", 2, .5)], drum="soft", de=2, dv=.5),
    "picnic": M("ポップ", "遠足", "口笛とウクレレのかき鳴らし。お出かけ・休日", 124, "G", "major", [["1", "5", "4", "1"]],
                [L("uke", "strum", 4, .5, rhy="x.xx.xx.x.xx.xx."), L("whistle", "melody", 5, .4, e=2, dens=.5), L("bass", "fifth", 2, .6), L("glock", "bells", 6, .2, e=3, p=.12)], drum="shaker", dv=.6),
    "comedy": M("ポップ", "コミカル", "ブンチャッチャのピチカートと口笛。失敗談・笑い", 140, "F", "major", [["1", "5", "5", "1"]],
                [L("pizz", "stride", 3, .6), L("whistle", "melody", 5, .4, dens=.6), L("glock", "bells", 6, .25, e=2, p=.15)], drum="polka", dv=.6),
    # ── 追加: ジャズ・ローファイ
    "chillhop": M("ジャズ・ローファイ", "チルホップ", "ビブラフォンとウッドベースに跳ねるブーンバップ。作業・学習", 86, "Eb", "dorian", [["1", "4", "7", "3"]],
                  [L("vibes", "half", 4, .6), L("upright", "root2", 2, .8), L("crackle", "hold", 4, .9), L("epiano", "counter", 5, .35, e=2)], drum="boombap", dv=.8, swing=.35, sevenths=True),
    "swing": M("ジャズ・ローファイ", "スウィング", "金管の合いの手と歩くベース。にぎやかな大人の場", 168, "Bb", "major", [["1", "6", "2", "5"], ["3", "6", "2", "5"]],
               [L("upright", "walk", 2, .8), L("brass", "stab", 4, .45, rhy="...x......x.x..."), L("keys", "off", 4, .35), L("brass", "melody", 5, .35, e=3, dens=.55)], drum="swing", swing=.6, sevenths=True),
    "blues": M("ジャズ・ローファイ", "ブルース", "12 小節のオルガンとハーモニカ。渋い・人間味", 84, "E", "mixolydian", [["1", "1", "1", "1", "4", "4", "1", "1", "5", "4", "1", "5"]],
               [L("organ", "stab", 4, .4, rhy="x..x..x.x..x..x."), L("upright", "walk", 2, .7), L("harmonica", "melody", 5, .45, e=2, dens=.4)], drum="shuffle", swing=.55, sevenths=True),
    "gospel": M("ジャズ・ローファイ", "ゴスペル", "オルガンと声の和音と跳ねる拍。感謝・励まし", 76, "Ab", "major", [["1", "4", "1", "5"], ["4", "3", "6", "2"]],
                [L("organ", "hold", 4, .45), L("oohs", "hold", 4, .4, e=2), L("keys", "stab", 4, .4, rhy="x..x..x.x..x..x."), L("bass", "root4", 2, .6)], drum="shuffle", swing=.6, dv=.7, sevenths=True),
    # ── 追加: 物語・映画
    "detective": M("物語・映画", "探偵", "歩くベースとピチカートとビブラフォン。推理・調査", 96, "C", "minor", [["1", "4", "1", "5"]],
                   [L("upright", "walk", 2, .8), L("pizz", "stab", 4, .4, rhy="x...x.x.....x..."), L("vibes", "melody", 5, .4, e=2, dens=.35), L("sub", "root1", 1, .4, e=3)],
                   drum="swing", de=2, dv=.6, swing=.5, sevenths=True),
    "anthem": M("物語・映画", "賛歌", "声と弦と金管が重なり、ティンパニが支える。式典・理念", 72, "C", "major", [["1", "5", "6", "4"], ["4", "1", "5", "1"]],
                [L("choir", "hold", 4, .5), L("strings", "hold", 3, .6), L("brass", "counter", 4, .4, e=2), L("sub", "root1", 1, .6), L("strings", "melody", 5, .4, e=3, dens=.3)],
                drum="cinematic", de=2, dv=.7),
    "rise": M("物語・映画", "上昇", "弦の脈打つ和音が次第に分厚く。ビジョン・数字の伸び", 124, "A", "minor", [["6", "4", "1", "5"]],
              [L("strings", "pump8", 3, .4), L("pluck", "arpoct", 4, .3, e=2), L("brass", "hold", 3, .35, e=3), L("sub", "root1", 1, .6)], drum="four", de=2),
    "horror": M("物語・映画", "ホラー", "低い弦のトレモロと管の鐘と心音。恐怖・警告", 60, "C", "dim", [["1", "2"]],
                [L("strings", "tremolo", 2, .3), L("tubular", "bells", 4, .3, p=.06), L("sub", "drone", 1, .6), L("glass", "counter", 6, .25, e=2)], drum="heart", dv=.7, cb=2),
    "creepy": M("物語・映画", "不気味", "岩戸の音階でゆっくり回るオルゴール。謎の人物・違和感", 66, "F#", "iwato", [["1", "2"]],
                [L("musicbox", "melody", 5, .45, dens=.35), L("musicbox", "arp8", 4, .2), L("sub", "drone", 1, .4, e=2)], beats=3),
    "earth": M("物語・映画", "大地", "弦とハープと笛のリディア。自然・環境の記録", 80, "E", "lydian", [["1", "2", "1", "5"]],
               [L("strings", "hold", 3, .5), L("harp", "arpud8", 4, .35), L("flute", "melody", 5, .35, e=2, dens=.3), L("sub", "root1", 1, .5)]),
    "sneaky": M("物語・映画", "忍び足", "ピチカートの抜き足差し足と駆け上がり。いたずら・こっそり", 104, "D", "minor", [["1", "1", "4", "5"]],
                [L("pizz", "stab", 3, .5, rhy="x...x...x...x.x."), L("pizz", "run", 4, .3, e=2), L("glock", "bells", 6, .2, e=2, p=.1), L("upright", "root4", 2, .4)], drum="clock", dv=.4),
    "lullaby": M("物語・映画", "子守唄", "3 拍子のハープと声と鉄琴。眠り・安心", 60, "F", "major", [["1", "4", "1", "5"]],
                 [L("harp", "arp8", 4, .4), L("oohs", "hold", 4, .35), L("glock", "melody", 6, .25, e=2, dens=.25)], beats=3),
    # ── 追加: 和・民族
    "gagaku": M("和・民族", "雅楽風", "笙の和音の持続と篳篥風の笛。儀式・神社", 50, "E", "yo", [["1", "4"]],
                [L("sho", "hold", 4, .5), L("shaku", "melody", 5, .45, dens=.2), L("sub", "drone", 1, .4), L("taiko", "bells", 2, .4, e=2, p=.06)], cb=2),
    "enka": M("和・民族", "演歌風", "弦の旋律と三味線の合いの手。人情・故郷", 72, "A", "minor", [["1", "4", "5", "1"], ["6", "4", "5", "1"]],
              [L("strings", "hold", 3, .5), L("upright", "root2", 2, .6), L("strings", "melody", 5, .45, dens=.35), L("shamisen", "bells", 4, .35, e=2, p=.2), L("keys", "broken8", 4, .3, e=2)],
              drum="ballad", de=2, dv=.5),
    "edo": M("和・民族", "江戸", "三味線のくり返しと尺八と太鼓。時代劇・下町", 112, "D", "yo", [["1", "4", "1", "5"]],
             [L("shamisen", "ostinato", 4, .5, seq=[0, 2, 4, 2, 0, 4, 3, 2], step=2), L("shaku", "melody", 5, .35, e=2, dens=.4), L("bass", "root4", 2, .4)], drum="taiko", dv=.5),
    "bon": M("和・民族", "盆踊り", "太鼓と当たり鉦と笛。夏祭り・地域の行事", 116, "C", "yo", [["1", "1", "4", "1"]],
             [L("flute", "melody", 5, .5, dens=.55), L("shamisen", "stab", 4, .35, rhy="x.x.x.x.x.x.x.x."), L("bass", "root2", 2, .4)], drum="bon"),
    # ── 追加: ワールド
    "samba": M("ワールド", "サンバ", "打楽器の群れと笛と金管。カーニバル・祝祭", 104, "A", "major", [["1", "6", "2", "5"]],
               [L("uke", "strum", 4, .45, rhy="x.xx.x.xx.xx.x.x"), L("bass", "fifth", 2, .7), L("flute", "melody", 5, .4, e=2, dens=.6), L("brass", "stab", 4, .3, e=3, rhy="x......x..x.....")],
               drum="samba", sevenths=True),
    "reggae": M("ワールド", "レゲエ", "裏の刻み（スカンク）と太いベース。ゆるい・南国", 76, "G", "major", [["1", "4"]],
                [L("organ", "skank", 4, .45), L("bass", "syncop", 2, .8, rhy="x.....x.x..x...."), L("steel", "bells", 5, .3, e=2, p=.15)], drum="reggae", cb=2),
    "ska": M("ワールド", "スカ", "裏打ちの刻みと金管と走るベース。陽気・勢い", 168, "C", "major", [["1", "6", "2", "5"]],
             [L("pluck", "off", 4, .45), L("brass", "melody", 4, .4, e=2, dens=.5), L("upright", "walk", 2, .7), L("organ", "off", 4, .25, e=3)], drum="ska"),
    "tango": M("ワールド", "タンゴ", "バンドネオンの鋭い刻みとハバネラの低音。情熱・対決", 118, "D", "harmonic", [["1", "4", "5", "1"]],
               [L("bandoneon", "tango", 4, .5), L("upright", "habanera", 2, .7), L("strings", "melody", 5, .4, e=2, dens=.5), L("pizz", "run", 4, .35, e=3)], drum="tango", dv=.6),
    "musette": M("ワールド", "ミュゼット", "アコーディオンの 3 拍子。パリ・カフェ・手紙", 160, "G", "major", [["1", "5", "5", "1"], ["1", "4", "5", "1"]],
                 [L("bass", "root1", 2, .5), L("accordion", "stride", 3, .4), L("accordion", "melody", 5, .4, e=2, dens=.55)], drum="waltz", de=2, dv=.4, beats=3),
    "flamenco": M("ワールド", "フラメンコ", "フリジアのかき鳴らしと手拍子。情熱・スペイン", 120, "E", "phrygian", [["4", "3", "2", "1M"]],
                  [L("uke", "strum", 4, .5, rhy="X.x.xx.xX.x.x.x."), L("bass", "root4", 2, .6), L("strings", "melody", 5, .35, e=2, dens=.55)], drum="palmas"),
    "arabian": M("ワールド", "アラビア", "ヒジャーズの旋律と打楽器の型。砂漠・異国の市場", 100, "D", "hijaz", [["1", "2", "1", "7"]],
                 [L("sitar", "melody", 5, .45, dens=.55), L("sub", "drone", 1, .7), L("pluck", "ostinato", 4, .35, seq=[0, 2, 1, 0, 4, 3, 2, 1], step=2), L("oohs", "hold", 3, .3, e=2)], drum="maqsum"),
    "raga": M("ワールド", "ラーガ", "タンプーラの持続とシタールとタブラ。インド・瞑想・香辛料", 88, "C#", "bhairav", [["1"]],
              [L("sitar", "tanpura", 3, .35), L("sitar", "melody", 5, .45, dens=.45), L("sub", "drone", 1, .5), L("glass", "hold", 4, .2, e=3)], drum="tabla", de=2),
    "caribbean": M("ワールド", "カリブ", "スチールドラムの旋律と弾む低音。南の海・休暇", 110, "C", "major", [["1", "4", "5", "1"]],
                   [L("steel", "melody", 5, .5, dens=.55), L("steel", "arp8", 4, .3), L("bass", "habanera", 2, .6)], drum="salsa", dv=.6),
    "country": M("ワールド", "カントリー", "バンジョーの 16 分とハーモニカと列車の拍。田舎・旅", 116, "G", "major", [["1", "4", "1", "5"]],
                 [L("banjo", "arp16", 4, .35), L("upright", "fifth", 2, .7), L("harmonica", "melody", 5, .4, e=2, dens=.45), L("uke", "strum", 3, .3, e=3, rhy="x.x.x.x.x.x.x.x.")], drum="train"),
    # ── 追加: ゲーム
    "town": M("ゲーム", "村", "アコーディオンとハープの 3 拍子。町・拠点・ひと休み", 108, "F", "major", [["1", "4", "5", "1"], ["1", "6", "4", "5"]],
              [L("accordion", "melody", 5, .4, dens=.45), L("harp", "arp8", 4, .35), L("bass", "root1", 2, .5)], drum="waltz", de=2, dv=.35, beats=3),
    "battle": M("ゲーム", "戦闘", "弦のトレモロと金管と駆ける低音。対決・勝負どころ", 164, "C", "harmonic", [["1", "6", "4", "5"]],
                [L("strings", "tremolo", 3, .35), L("bass", "gallop", 2, .7), L("brass", "melody", 4, .45, dens=.55), L("choir", "hold", 4, .3, e=3)], drum="rock", dv=.7),
    "victory": M("ゲーム", "勝利", "金管のファンファーレと行進。達成・結果発表", 132, "Bb", "major", [["1", "4", "5", "1"], ["4", "5", "3", "6"]],
                 [L("brass", "melody", 4, .5, dens=.5), L("strings", "hold", 3, .45), L("bass", "oct8", 2, .6), L("glock", "arp8", 6, .2, e=2)], drum="march"),
    "dungeon": M("ゲーム", "迷宮", "岩戸の音階の鐘と重い持続。探索・危険", 70, "D", "iwato", [["1", "2"]],
                 [L("tubular", "bells", 4, .35, p=.1), L("sub", "drone", 1, .8), L("oohs", "hold", 3, .35), L("pizz", "ostinato", 4, .3, e=2, seq=[0, 1, 0, 4], step=4)], cb=2),
    "chipboss": M("ゲーム", "8bit のボス", "駆ける低音と短調の速い旋律。強敵・最終局面", 176, "E", "harmonic", [["1", "6", "4", "5"]],
                  [L("chip", "melody", 5, .45, dens=.7), L("chiptri", "gallop", 2, .8), L("chipsq", "arp16", 4, .25, e=2)], drum="chip"),
    "chiptown": M("ゲーム", "8bit の町", "ゆったり跳ねる 8bit の旋律。休憩・案内", 100, "G", "major", [["1", "3", "4", "5"]],
                  [L("chip", "melody", 5, .45, dens=.4), L("chipsq", "broken8", 4, .25), L("chiptri", "root4", 2, .8)], drum="chip", dv=.5, swing=.3),
    # ── 追加: エネルギー
    "parade": M("エネルギー", "パレード", "行進の太鼓とブンチャッチャの金管と鉄琴。開幕・記念", 116, "F", "major", [["1", "4", "5", "1"]],
                [L("brass", "stride", 3, .4), L("glock", "melody", 6, .35, dens=.45), L("strings", "hold", 3, .3, e=2)], drum="march"),
    # ── 追加: ダンス
    "outrun": M("ダンス", "アウトラン", "脈打つ分厚いシンセと 80 年代の拍。夜のドライブ", 118, "F#", "minor", [["1", "6", "3", "7"]],
                [L("supersaw", "pump8", 3, .5), L("synthbass", "arpoct", 2, .6), L("lead", "melody", 5, .35, e=2, dens=.45), L("glock", "arp16", 6, .15, e=3)], drum="eighties"),
    "dnb": M("ダンス", "ドラムンベース", "速い割れた拍と太い低音。スピード・未来", 172, "D", "minor", [["1", "6"], ["1", "7"]],
             [L("pad", "hold", 3, .5), L("sub", "root2", 1, .8), L("supersaw", "hold", 2, .3, e=2), L("pluck", "arprnd16", 5, .3, e=3)], drum="dnb", dv=.9, cb=2),
    "trap": M("ダンス", "トラップ", "808 の低音と刻み込むハイハット。強い・今っぽい", 140, "C#", "harmonic", [["1", "6", "4", "5"]],
              [L("sub808", "root2", 1, .8), L("bell", "melody", 5, .35, dens=.35), L("oohs", "hold", 4, .35, e=2), L("pluck", "arp3", 5, .25, e=3)], drum="trap2"),
    "techno": M("ダンス", "テクノ", "調の根音の持続にうねるベースと四つ打ち。没頭・工場", 130, "A", "phrygian", [["1", "1", "2", "1"]],
                [L("acid", "pedal8", 2, .6), L("pad", "hold", 3, .35, e=2), L("chipsq", "ostinato", 5, .15, e=3, seq=[0, 7, 3, 7], step=3)], drum="techno", cb=2),
    "garage": M("ダンス", "UK ガラージ", "オルガンの跳ねる和音と 2 ステップ。都会の夜", 132, "G", "minor", [["1", "4", "6", "5"]],
                [L("organ", "stab", 4, .4, rhy="x..x....x.x..x.."), L("sub", "syncop", 1, .8, rhy="x.....x...x..x.."), L("oohs", "counter", 5, .35, e=2)], drum="garage", swing16=.35, sevenths=True),
    "futurebass": M("ダンス", "フューチャーベース", "7 の和音の分厚い脈と重い半分の拍。明るい高揚", 150, "Eb", "major", [["4", "5", "3", "6"]],
                    [L("supersaw", "pump8", 4, .45), L("sub808", "root2", 1, .7), L("glock", "arp16", 6, .15, e=2), L("lead", "melody", 5, .3, e=3, dens=.55)], drum="futurebass", sevenths=True),
    "reggaeton": M("ダンス", "レゲトン", "3+3+2 のデンボウの拍とスチールの粒。夏・ダンス", 96, "A", "minor", [["1", "6", "7", "1"]],
                   [L("pluck", "stab", 4, .4, rhy="x..x..x.x..x..x."), L("sub808", "syncop", 1, .7, rhy="x..x..x.x..x..x."), L("steel", "melody", 5, .35, e=2, dens=.45)], drum="reggaeton"),
    # ── 追加: 番組・ラジオ
    "news": M("番組・ラジオ", "報道", "16 分の弦と金管の一撃と四つ打ち。ニュース・速報・決算", 120, "D", "minor", [["1", "6", "7", "1"]],
              [L("strings", "pulse16", 3, .25), L("brass", "stab", 4, .4, rhy="X.....x.x......."), L("synthbass", "root8", 2, .6), L("bell", "counter", 5, .3, e=2)], drum="four", de=2, dv=.6),
    "weather": M("番組・ラジオ", "天気予報", "ビブラフォンとマリンバの軽い拍。お知らせ・生活情報", 108, "C", "major", [["1", "6", "2", "5"]],
                 [L("vibes", "stab", 4, .4, rhy="x..x..x.x..x..x."), L("marimba", "arp8", 5, .3), L("bass", "root4", 2, .6)], drum="soft", swing=.2, sevenths=True),
    "variety": M("番組・ラジオ", "バラエティ", "金管とスラップのにぎやかな合いの手。企画・お楽しみ", 128, "Eb", "mixolydian", [["1", "4", "1", "5"]],
                 [L("brass", "stab", 4, .45, rhy="x..x..x...x.x..."), L("slap", "syncop", 2, .8), L("clav", "stab", 4, .35, rhy="..x...x...x..xx."), L("brass", "melody", 5, .35, e=2, dens=.6)],
                 drum="funk", swing16=.2),
    "podcast": M("番組・ラジオ", "ポッドキャスト", "ウクレレの刻みとエレピ、はっきりした拍。番組の始まり・区切り", 96, "D", "major", [["1", "3", "4", "5"]],
                 [L("uke", "stab", 4, .45, rhy="x..x..x.x..x..x."), L("epiano", "hold", 4, .35), L("bass", "root8", 2, .6), L("glock", "melody", 6, .25, e=2, dens=.35)], drum="boombap", dv=.6),
    "radio": M("番組・ラジオ", "ラジオ", "アコースティックの分散とシェイカー。語り・トーク", 92, "A", "major", [["1", "4", "6", "5"]],
               [L("uke", "arpud8", 4, .4), L("keys", "half", 4, .3), L("bass", "root2", 2, .6), L("whistle", "counter", 5, .25, e=3)], drum="shaker", dv=.5),
    "quiz": M("番組・ラジオ", "クイズ", "時計の刻みとピチカートの考える時間。問題・シンキングタイム", 112, "F", "minor", [["1", "1", "6", "5"]],
              [L("pizz", "ostinato", 4, .4, seq=[0, 4, 2, 4], step=2), L("glock", "bells", 6, .25, p=.1), L("sub", "root1", 1, .5)], drum="clock", dv=.6),
    "credits": M("番組・ラジオ", "エンドロール", "ピアノの分散に弦と鉄琴が重なる。締め・お礼", 84, "Eb", "major", [["1", "5", "6", "3", "4", "1", "4", "5"]],
                 [L("keys", "broken8", 4, .55), L("strings", "hold", 3, .45, e=2), L("glock", "melody", 6, .2, e=2, dens=.3), L("upright", "root2", 2, .5)], drum="ballad", de=3, dv=.45),
}
# 曲の音量の揃え（--sounds のページで合成した盛り上がり 3 の大きさから求めた倍率。ナレーションの後ろで流す大きさ。曲を足したら測り直す）
MUSIC_GAIN = {"calm": 0.289, "deep": 0.34, "drift": 0.409, "dawn": 0.312, "mist": 0.39, "ocean": 0.354, "space": 0.259, "rain": 0.304, "forest": 0.462, "bright": 0.411, "corporate": 0.499, "innovate": 0.38, "trust": 0.497, "growth": 0.509, "clean": 0.55, "keynote": 0.413, "launch": 0.382, "pitch": 0.376, "startup": 0.486, "tech": 0.484, "circuit": 0.459, "data": 0.34, "cyber": 0.455, "synthwave": 0.488, "neon": 0.398, "hacker": 0.317, "ai": 0.413, "quantum": 0.323, "robot": 0.49, "pop": 0.386, "happy": 0.434, "sunny": 0.499, "kids": 0.456, "summer": 0.526, "disco": 0.375, "idol": 0.334, "lofi": 0.413, "study": 0.539, "jazz": 0.406, "bossa": 0.397, "night": 0.433, "cafe": 0.589, "soul": 0.422, "epic": 0.302, "hero": 0.418, "tension": 0.367, "mystery": 0.376, "sad": 0.412, "hope": 0.519, "wonder": 0.824, "trailer": 0.299, "documentary": 0.552, "adventure": 0.507, "memory": 0.54, "suspense": 0.326, "wa": 0.509, "matsuri": 0.251, "kyoto": 1.157, "ryukyu": 0.605, "zen": 0.344, "celtic": 0.331, "orient": 0.703, "desert": 0.336, "island": 0.626, "chiptune": 0.605, "arcade": 0.798, "puzzle": 0.863, "rpg": 0.568, "waltz": 0.471, "baroque": 1.746, "piano": 1.529, "strings": 0.629, "chamber": 1.308, "musicbox": 2.889, "drive": 0.469, "sport": 0.388, "rock": 0.142, "funk": 0.299, "house": 0.38, "countdown": 0.529, "pulse": 0.419, "hype": 0.372, "minimal": 0.877, "clock": 1.988, "glass": 0.673, "steps": 0.613, "snow": 0.52, "aurora": 0.474, "meditation": 0.485, "citypop": 0.387, "nursery": 0.712, "picnic": 0.551, "comedy": 0.764, "chillhop": 0.379, "swing": 0.668, "blues": 0.44, "gospel": 0.392, "detective": 0.676, "anthem": 0.394, "rise": 0.355, "horror": 0.428, "creepy": 0.668, "earth": 0.57, "sneaky": 1.07, "lullaby": 1.809, "gagaku": 0.539, "enka": 0.825, "edo": 0.566, "bon": 0.258, "samba": 0.288, "reggae": 0.448, "ska": 0.364, "tango": 0.593, "musette": 0.641, "flamenco": 0.497, "arabian": 0.323, "raga": 0.385, "caribbean": 0.536, "country": 0.364, "town": 0.662, "battle": 0.394, "victory": 0.367, "dungeon": 0.336, "chipboss": 0.817, "chiptown": 0.827, "parade": 0.368, "outrun": 0.398, "dnb": 0.343, "trap": 0.237, "techno": 0.424, "garage": 0.304, "futurebass": 0.271, "reggaeton": 0.298, "news": 0.516, "weather": 0.413, "variety": 0.403, "podcast": 0.535, "radio": 0.58, "quiz": 0.644, "credits": 0.627}
for _k, _g in MUSIC_GAIN.items():
    MUSIC[_k]["g"] = _g
MUSIC_CATS = ["落ち着き", "企業・製品", "技術", "ポップ", "ジャズ・ローファイ", "物語・映画", "和・民族", "ワールド", "ゲーム", "クラシック風", "エネルギー", "ダンス", "ミニマル", "番組・ラジオ"]


# ──────────────────────────────────────────────────────────────────────────
# 効果音
# ──────────────────────────────────────────────────────────────────────────
def y(w, **kw):
    d = {"w": w}
    d.update(kw)
    return d


def S(cat, name, desc, *layers, **kw):
    d = {"cat": cat, "name": name, "desc": desc, "l": list(layers)}
    d.update(kw)
    return d


N = "noise"
SFX = {
    # ── 操作
    "click": S("操作", "クリック", "マウスのクリック", y(N, flt=["highpass", 3000], d=.018, v=.5), y("square", f=[2400, 1600], ft=.02, d=.02, v=.12)),
    "tap": S("操作", "タップ", "画面を軽く触る", y("sine", f=[900, 620], ft=.05, d=.07, v=.5)),
    "pop": S("操作", "ポン", "項目が飛び出す", y("sine", f=[380, 980], ft=.05, a=.002, d=.1, v=.55), y("triangle", f=[760, 1500], ft=.04, d=.05, v=.15)),
    "pop-soft": S("操作", "ぽっ", "柔らかく現れる", y("sine", f=[300, 560], ft=.06, a=.008, d=.13, v=.45, flt=["lowpass", 1600])),
    "blip": S("操作", "ピッ", "短い電子音", y("square", f=1320, d=.06, v=.14, flt=["lowpass", 3500])),
    "bloop": S("操作", "ポコッ", "下がる丸い音", y("sine", f=[700, 260], ft=.1, d=.13, v=.5)),
    "tick": S("操作", "カチ", "小さな刻み", y(N, flt=["bandpass", 3600, 8], d=.022, v=.6), y("sine", f=2200, d=.012, v=.15)),
    "toggle": S("操作", "トグル", "切り替えのスイッチ", y("square", f=1000, notes=[0, 7], gap=.05, d=.03, v=.12, flt=["lowpass", 4000])),
    "select": S("操作", "選択", "選ぶ・進む", y("sine", f=880, notes=[0, 12], gap=.06, d=.1, v=.35)),
    "confirm": S("操作", "決定", "3 音で上がる決定", y("triangle", f=660, notes=[0, 4, 7], gap=.05, d=.16, v=.35)),
    "back": S("操作", "戻る", "2 音で下がる", y("triangle", f=660, notes=[7, 0], gap=.06, d=.13, v=.35)),
    "hover": S("操作", "なぞる", "かすかに上がる", y("sine", f=[1200, 1550], ft=.05, a=.01, d=.05, v=.15)),
    "key": S("操作", "打鍵", "キーボードを打つ（連続にも使う）", y(N, flt=["bandpass", 2600, 3], d=.03, v=.45), y("square", f=170, d=.015, v=.08)),
    "key-soft": S("操作", "打鍵（静か）", "静かなキーボード", y(N, flt=["bandpass", 1800, 2], d=.025, v=.3)),
    "typewriter": S("操作", "タイプライター", "機械式の打鍵", y(N, flt=["bandpass", 3000, 1.4], d=.045, v=.6), y("square", f=120, d=.02, v=.15), y(N, at=.015, flt=["highpass", 5000], d=.01, v=.2)),
    "carriage": S("操作", "改行の鐘", "タイプライターのチン", y("sine", f=2637, d=1.0, v=.25), y("sine", f=7270, d=.4, v=.06), y(N, flt=["bandpass", 2000, 2], d=.08, v=.2)),
    "send": S("操作", "送信", "メッセージを送る", y("sine", f=[520, 1500], ft=.16, a=.005, d=.18, v=.35), y(N, a=.02, d=.14, v=.12, flt=["bandpass", [1500, 6000], 1])),
    "receive": S("操作", "受信", "メッセージが届く", y("sine", f=988, notes=[0, 5], gap=.09, d=.28, v=.32)),
    "message": S("操作", "メッセージ", "チャットの着信", y("sine", f=1318, notes=[0, -5], gap=.1, d=.22, v=.3), y("sine", f=5272, notes=[0, -5], gap=.1, d=.05, v=.05)),
    "delete": S("操作", "削除", "消す・捨てる", y(N, flt=["lowpass", [3000, 300], 1], d=.16, v=.4), y("square", f=[400, 100], ft=.12, d=.12, v=.08)),
    "nav": S("操作", "移動", "チャプターを移る", y("sine", f=740, notes=[0, 7], gap=.045, d=.09, v=.3)),
    "switch": S("操作", "スイッチ", "物理的なスイッチ", y(N, flt=["bandpass", 1800, 6], d=.012, v=.6), y(N, at=.05, flt=["bandpass", 2600, 6], d=.012, v=.45)),
    # ── 転換
    "whoosh": S("転換", "ヒュッ", "場面が流れる", y(N, a=.13, d=.26, v=.55, flt=["bandpass", [450, 2600], 1.3, .34])),
    "whoosh-long": S("転換", "ヒューッ", "長く大きく流れる", y(N, a=.35, d=.55, v=.5, flt=["bandpass", [300, 3800], 1.2, .9])),
    "whoosh-short": S("転換", "シュッ", "素早い動き", y(N, a=.035, d=.12, v=.5, flt=["bandpass", [1300, 5200], 1.4, .15])),
    "swoosh-up": S("転換", "上がる風", "上に抜ける", y(N, a=.16, d=.14, v=.45, flt=["highpass", [700, 6000], .9, .3]), y("sine", f=[200, 800], ft=.3, a=.15, d=.1, v=.08)),
    "swoosh-down": S("転換", "下がる風", "下に落ちる", y(N, a=.04, d=.36, v=.45, flt=["bandpass", [5000, 500], 1.2, .4])),
    "swipe": S("転換", "スワイプ", "指で払う", y(N, a=.02, d=.1, v=.45, pan=.3, flt=["bandpass", [2200, 6500], 1.6, .12])),
    "air": S("転換", "空気", "ほとんど聞こえない切り替え", y(N, a=.22, d=.32, v=.16, flt=["lowpass", [700, 1600], .5, .5])),
    "zoom-in": S("転換", "寄る", "近づく", y("sine", f=[160, 900], ft=.3, a=.25, d=.08, v=.2), y(N, a=.25, d=.1, v=.18, flt=["bandpass", [600, 3200], 2, .33])),
    "zoom-out": S("転換", "引く", "遠ざかる", y("sine", f=[900, 160], ft=.3, a=.03, d=.3, v=.2), y(N, a=.03, d=.3, v=.18, flt=["bandpass", [3200, 600], 2, .33])),
    "riser": S("転換", "盛り上がり", "1 秒かけて上がる", y("sawtooth", f=[200, 1200], ft=1.2, a=1.15, d=.08, v=.12, flt=["lowpass", [400, 5000], 1, 1.2]), y(N, a=1.15, d=.1, v=.15, flt=["highpass", [500, 8000], .7, 1.2])),
    "downer": S("転換", "下降", "1 秒かけて下がる", y("sawtooth", f=[1200, 110], ft=1, a=.01, d=1, v=.12, flt=["lowpass", [5000, 300], 1, 1])),
    "reverse": S("転換", "逆再生", "逆回しのシンバル", y(N, a=1, d=.04, v=.35, flt=["highpass", 5000, .5])),
    "shutter": S("転換", "シャッター", "カメラのシャッター", y(N, flt=["bandpass", 2500, 2], d=.03, v=.6, rep=2, gap=.07), y("square", f=900, d=.01, v=.1, rep=2, gap=.07)),
    "glitch": S("転換", "グリッチ", "映像の乱れ", y("square", f=300, notes=[0, 7, -5, 12, 3, -12, 9], gap=.028, d=.022, v=.12), y(N, flt=["highpass", 3000], rep=3, gap=.05, d=.02, v=.3, nr=.5)),
    "cut": S("転換", "カット", "パッと切り替わる", y(N, flt=["lowpass", 1800], d=.06, v=.5), y("sine", f=[120, 55], ft=.1, d=.12, v=.5)),
    "impact": S("転換", "衝撃", "重い一撃", y("sine", f=[95, 38], ft=.4, d=.6, v=.8), y(N, flt=["lowpass", [3000, 200], 1, .4], d=.45, v=.5)),
    "boom": S("転換", "ドーン", "低く長い爆発", y("sine", f=[62, 30], ft=1.2, a=.01, d=1.5, v=.9), y(N, flt=["lowpass", 380], d=1.1, v=.45)),
    "subdrop": S("転換", "重低音の落下", "低音が沈む", y("sine", f=[120, 32], ft=1, a=.01, d=1.3, v=.8)),
    "slide": S("転換", "スライド", "板が滑る", y(N, a=.06, d=.18, v=.35, flt=["bandpass", [1000, 2300], 1.2, .22]), y("triangle", f=[300, 520], ft=.2, d=.16, v=.06)),
    "page": S("転換", "ページ", "紙をめくる", y(N, a=.03, d=.2, v=.42, flt=["bandpass", [2600, 1200], 1, .22]), y(N, at=.09, d=.06, v=.2, flt=["highpass", 5000])),
    "curtain": S("転換", "幕", "幕が開く", y(N, a=.5, h=.2, d=.6, v=.25, flt=["lowpass", [400, 1400], .7, 1.2])),
    "flip": S("転換", "めくり", "カードをめくる", y(N, flt=["bandpass", [3500, 2000], 1], d=.06, v=.4, rep=3, gap=.04)),
    # ── 強調
    "ding": S("強調", "チーン", "澄んだ一音", y("sine", f=1760, d=1, v=.3), y("sine", f=4858, d=.45, v=.08)),
    "chime": S("強調", "チャイム", "3 音で上がる", y("sine", f=880, notes=[0, 7, 12], gap=.12, d=1, v=.22), y("sine", f=2429, notes=[0, 7, 12], gap=.12, d=.4, v=.06)),
    "bell": S("強調", "鐘", "丸い鐘", y("sine", f=523, d=2.2, v=.26), y("sine", f=1051, d=1.4, v=.12), y("sine", f=1580, d=.9, v=.07), y("sine", f=2197, d=.5, v=.04)),
    "rin": S("強調", "りん", "仏具のりん。長くうなる", y("sine", f=1320, d=3, v=.25), y("sine", f=1327, d=3, v=.12), y("sine", f=3600, d=1.5, v=.08)),
    "sparkle": S("強調", "きらり", "上がる粒", y("sine", f=1760, notes=[0, 4, 7, 11, 14, 19], gap=.04, d=.3, v=.14)),
    "shimmer": S("強調", "きらめき", "揺れる光", y("triangle", f=1046, notes=[12, 19, 16, 24, 21, 28, 24, 31], gap=.03, d=.35, v=.08), y(N, a=.2, d=.4, v=.04, flt=["highpass", 8000])),
    "twinkle": S("強調", "星", "高い 4 音", y("sine", f=1568, notes=[0, 12, 7, 19], gap=.07, d=.4, v=.15)),
    "magic": S("強調", "魔法", "駆け上がる粒", y("sine", f=784, notes=[0, 2, 4, 7, 9, 12, 14, 16, 19, 21, 24], gap=.035, d=.45, v=.1), y(N, a=.3, d=.4, v=.05, flt=["highpass", 7000])),
    "bling": S("強調", "キラーン", "光る", y("sine", f=[2600, 3200], ft=.05, a=.003, d=.6, v=.18), y("sine", f=5200, d=.4, v=.07, vib=[7, 25, .05])),
    "success": S("強調", "成功", "4 音で上がる", y("triangle", f=523, notes=[0, 4, 7, 12], gap=.08, d=.38, v=.3)),
    "fanfare": S("強調", "ファンファーレ", "金管の短い祝い", y("sawtooth", f=523, notes=[0, 4, 7], gap=.12, d=.14, v=.09, flt=["lowpass", 2600]),
                 y("sawtooth", f=1046, at=.36, h=.35, d=.5, v=.1, flt=["lowpass", 2800], vib=[5, 12, .2]), y("sawtooth", f=659, at=.36, h=.35, d=.5, v=.06, flt=["lowpass", 2600])),
    "orchestra": S("強調", "オーケストラヒット", "ジャン！", y("sawtooth", f=262, d=.5, v=.1, flt=["lowpass", [5000, 800], 1, .4]), y("sawtooth", f=330, d=.5, v=.1, flt=["lowpass", [5000, 800], 1, .4]),
                   y("sawtooth", f=392, d=.5, v=.1, flt=["lowpass", [5000, 800], 1, .4]), y("sawtooth", f=523, d=.5, v=.08, flt=["lowpass", [5000, 800], 1, .4]), y(N, d=.1, v=.2, flt=["highpass", 2000])),
    "stab": S("強調", "スタブ", "短い和音の一撃（報道風）", y("sawtooth", f=392, d=.25, v=.1, flt=["lowpass", 2000]), y("sawtooth", f=494, d=.25, v=.1, flt=["lowpass", 2000]),
              y("sawtooth", f=587, d=.25, v=.09, flt=["lowpass", 2000]), y("sine", f=98, d=.4, v=.4)),
    "stamp": S("強調", "ハンコ", "押す", y("sine", f=[190, 90], ft=.1, d=.14, v=.7), y(N, flt=["lowpass", 1400], d=.08, v=.4)),
    "reveal": S("強調", "お披露目", "吸い込んで鳴る", y(N, a=.6, d=.05, v=.25, flt=["highpass", [800, 7000], .7, .6]), y("sine", f=1318, at=.6, notes=[0, 7], gap=.08, d=.9, v=.2)),
    "ping": S("強調", "ピン", "高く澄んだ点", y("sine", f=2093, d=.4, v=.25, vib=[6, 15, .05])),
    "thump": S("強調", "トン", "やわらかい一打", y("sine", f=[220, 110], ft=.1, d=.16, v=.5), y("triangle", f=440, d=.05, v=.1)),
    "underline": S("強調", "線を引く", "ペンでさっと引く", y(N, a=.05, d=.15, v=.25, flt=["bandpass", [2000, 4000], 3, .2])),
    "applause": S("強調", "拍手", "拍手が起こる", y(N, flt=["bandpass", 1500, .8], rep=40, gap=.03, rj=.02, vj=.6, a=.003, d=.05, v=.25),
                  y(N, at=.01, flt=["bandpass", 2500, .8], rep=30, gap=.04, rj=.025, vj=.6, a=.003, d=.04, v=.18)),
    # ── 通知
    "notify": S("通知", "通知", "2 音の通知", y("sine", f=1175, notes=[0, 7], gap=.11, d=.45, v=.26), y("sine", f=2350, notes=[0, 7], gap=.11, d=.2, v=.05)),
    "notify-soft": S("通知", "通知（柔らか）", "マリンバ風の通知", y("sine", f=880, notes=[0, 4], gap=.12, d=.32, v=.3), y("sine", f=3520, notes=[0, 4], gap=.12, d=.05, v=.06)),
    "alert": S("通知", "注意喚起", "ピピッ", y("square", f=880, notes=[0, 0], gap=.15, d=.1, v=.1, flt=["lowpass", 2500])),
    "error": S("通知", "エラー", "低いブブッ", y("square", f=[220, 180], ft=.2, d=.22, v=.12, flt=["lowpass", 1200]), y("square", f=[180, 150], at=.14, ft=.2, d=.25, v=.12, flt=["lowpass", 1200])),
    "buzzer": S("通知", "ブザー", "不正解・停止", y("sawtooth", f=110, a=.005, h=.3, d=.05, v=.12, flt=["lowpass", 1500]), y("sawtooth", f=113, a=.005, h=.3, d=.05, v=.1, flt=["lowpass", 1500])),
    "alarm": S("通知", "アラーム", "くり返す警報", y("square", f=988, notes=[0, 5, 0, 5], gap=.12, d=.1, v=.1, flt=["lowpass", 4000])),
    "siren": S("通知", "サイレン", "上がって下がる", y("sawtooth", f=[600, 1100], fe="lin", ft=.5, a=.01, h=.45, d=.05, v=.07, flt=["lowpass", 2500]),
               y("sawtooth", f=[1100, 600], fe="lin", at=.5, ft=.5, a=.01, h=.45, d=.1, v=.07, flt=["lowpass", 2500])),
    "warning": S("通知", "警告", "2 音で下がる", y("triangle", f=660, notes=[0, -4], gap=.18, d=.26, v=.3)),
    "done": S("通知", "完了", "3 音の完了", y("sine", f=1046, notes=[0, 7, 12], gap=.06, d=.42, v=.2)),
    "ok": S("通知", "OK", "オクターブで上がる", y("triangle", f=784, notes=[0, 12], gap=.07, d=.22, v=.3)),
    "question": S("通知", "問い", "問いかける上がり", y("triangle", f=587, notes=[0, 7], gap=.12, d=.25, v=.3)),
    # ── 数値
    "count": S("数値", "カウント", "数え上げの刻み（連続に使う）", y("square", f=1800, d=.012, v=.07, flt=["lowpass", 4500])),
    "counter": S("数値", "数え上げ", "上がりながら刻む", y("sine", f=600, rep=12, gap=.05, rf=1.03, d=.03, v=.14)),
    "scan": S("数値", "スキャン", "走査する", y("sine", f=[400, 2400], ft=.6, a=.5, d=.1, v=.1), y("triangle", f=[800, 4800], ft=.6, a=.5, d=.1, v=.03)),
    "beep": S("数値", "ビープ", "機械の一音", y("sine", f=1000, a=.002, h=.08, d=.02, v=.18)),
    "radar": S("数値", "レーダー", "こだまする", y("sine", f=[1500, 1400], ft=.9, d=.9, v=.22, rep=2, gap=.45, rv=.35)),
    "sonar": S("数値", "ソナー", "深い探索音", y("sine", f=1244, a=.005, d=1.7, v=.28), y("sine", f=1250, a=.005, d=1.7, v=.12)),
    "data": S("数値", "データ", "高速のデータ", y("square", f=880, notes=[0, 12, 5, 17, 7, 19, 10, 22], gap=.03, d=.02, v=.07, flt=["lowpass", 5000])),
    "compute": S("数値", "計算", "電子計算機", y("square", f=1320, notes=[0, 7, 3, 10, 5, 12, -2, 9], gap=.045, d=.03, v=.07, flt=["lowpass", 5000])),
    "process": S("数値", "処理中", "交互の刻み", y("sine", f=1500, notes=[0, 5, 0, 5, 0, 5], gap=.12, d=.04, v=.12)),
    "charge": S("数値", "チャージ", "ためる", y("sawtooth", f=[100, 800], ft=.8, a=.8, d=.05, v=.1, flt=["lowpass", [300, 3000], 1, .8])),
    "powerup": S("数値", "起動", "立ち上がる", y("sine", f=[80, 400], ft=.6, a=.6, d=.3, v=.25), y("triangle", f=523, at=.5, notes=[0, 7, 12], gap=.06, d=.3, v=.18)),
    "powerdown": S("数値", "停止", "落ちる", y("sine", f=[400, 60], ft=.9, a=.01, d=.9, v=.28), y("square", f=[200, 40], ft=.6, d=.6, v=.03, flt=["lowpass", 800])),
    "connect": S("数値", "接続", "つながる", y("sine", f=660, notes=[0, 5, 12], gap=.05, d=.12, v=.24), y(N, d=.01, v=.2, flt=["highpass", 3000])),
    "disconnect": S("数値", "切断", "切れる", y("sine", f=660, notes=[12, 5, 0], gap=.05, d=.12, v=.24)),
    "graph-rise": S("数値", "伸びる", "棒・線が伸びる", y("triangle", f=[300, 900], ft=.5, a=.05, h=.3, d=.2, v=.15), y("sine", f=[600, 1800], ft=.5, a=.05, h=.3, d=.2, v=.05)),
    # ── 自然・もの
    "bubble": S("自然・もの", "泡", "ぷくぷく", y("sine", f=[300, 1200], ft=.05, d=.08, v=.35, rep=3, gap=.07, rf=1.2)),
    "drop": S("自然・もの", "しずく", "水滴", y("sine", f=[1600, 500], ft=.08, d=.16, v=.45)),
    "water": S("自然・もの", "水", "水が跳ねる", y("sine", f=[500, 1100], ft=.04, notes=[0, 5, 2, 8, 4], gap=.06, d=.07, v=.25)),
    "knock": S("自然・もの", "ノック", "扉を 2 回", y("sine", f=[200, 140], ft=.06, d=.08, v=.65, rep=2, gap=.16), y(N, flt=["bandpass", 1000, 4], d=.03, v=.3, rep=2, gap=.16)),
    "wood": S("自然・もの", "木の音", "コツ", y("sine", f=800, d=.07, v=.45), y("sine", f=2000, d=.02, v=.12)),
    "paper": S("自然・もの", "紙", "紙がこすれる", y(N, a=.05, d=.26, v=.3, flt=["bandpass", [3000, 2000], 1, .3])),
    "pencil": S("自然・もの", "書く", "鉛筆で書く", y(N, flt=["bandpass", 4200, 2], rep=5, gap=.06, rj=.015, a=.015, d=.05, v=.18)),
    "clock-tick": S("自然・もの", "チクタク", "時計の 2 拍", y(N, flt=["bandpass", 4000, 10], d=.016, v=.6), y(N, at=.5, flt=["bandpass", 3000, 10], d=.016, v=.6)),
    "heartbeat": S("自然・もの", "心音", "ドクン", y("sine", f=[70, 48], ft=.1, d=.16, v=.8, rep=2, gap=.22, rv=.7)),
    "footstep": S("自然・もの", "足音", "一歩", y(N, flt=["lowpass", 600], d=.09, v=.5), y(N, flt=["bandpass", 1500, 1], d=.03, v=.12)),
    "wind": S("自然・もの", "風", "吹き抜ける", y(N, a=.8, h=.3, d=.8, v=.18, flt=["bandpass", [400, 900], 1.4, 1.5])),
    "snap": S("自然・もの", "指パッチン", "パチン", y(N, flt=["bandpass", 2800, 3], d=.04, v=.7), y("sine", f=2000, d=.012, v=.15)),
    "clink": S("自然・もの", "乾杯", "グラスが触れる", y("sine", f=3136, d=.6, v=.15), y("sine", f=4700, d=.4, v=.08), y("sine", f=3150, at=.08, d=.5, v=.1)),
    "hyoshigi": S("自然・もの", "拍子木", "カン、カン", y("sine", f=1400, d=.06, v=.5, rep=2, gap=.28), y("sine", f=3300, d=.02, v=.15, rep=2, gap=.28)),
    # ── ゲーム
    "coin": S("ゲーム", "コイン", "取った", y("square", f=988, d=.06, v=.1), y("square", f=1318, at=.07, h=.12, d=.3, v=.1)),
    "jump": S("ゲーム", "ジャンプ", "跳ぶ", y("square", f=[300, 900], ft=.15, d=.16, v=.1)),
    "powerup8": S("ゲーム", "パワーアップ", "8bit の駆け上がり", y("square", f=523, notes=[0, 4, 7, 12, 16, 19, 24], gap=.04, d=.05, v=.09)),
    "levelup": S("ゲーム", "レベルアップ", "上がって和音", y("triangle", f=523, notes=[0, 4, 7, 12], gap=.09, d=.1, v=.25), y("triangle", f=1046, at=.38, notes=[0, 4, 7], gap=.004, d=.6, v=.16)),
    "laser": S("ゲーム", "レーザー", "ピュン", y("square", f=[1800, 200], ft=.2, d=.2, v=.08)),
    "zap": S("ゲーム", "電撃", "バチバチ", y("sawtooth", f=[900, 100], ft=.08, d=.1, v=.12, rep=3, gap=.05), y(N, d=.15, v=.1, flt=["highpass", 2000])),
    "explode8": S("ゲーム", "8bit の爆発", "ボン", y(N, nr=.3, d=.7, v=.45, flt=["lowpass", [3000, 150], 1, .6])),
    "oneup": S("ゲーム", "1UP", "ひとつ増えた", y("square", f=1318, notes=[0, 3, 15, 12, 14, 19], gap=.08, d=.07, v=.08)),
    "select8": S("ゲーム", "8bit の選択", "ピコッ", y("square", f=1046, notes=[0, 12], gap=.04, d=.04, v=.09)),
    "win": S("ゲーム", "勝利", "8bit の短い祝い", y("pulse", pw=.25, f=523, notes=[0, 4, 7, 12, 7, 12], gap=.1, d=.12, v=.08)),
    # ── 楽器
    "drumroll": S("楽器", "ドラムロール", "だんだん強く", y(N, flt=["highpass", 1500], rep=22, gap=.04, rv=1.06, a=.002, d=.05, v=.07, rj=.004)),
    "cymbal": S("楽器", "シンバル", "ジャーン", y(N, d=1.6, v=.3, flt=["highpass", 5000, .5]), y(N, d=.9, v=.1, flt=["bandpass", 8000, 2])),
    "gong": S("楽器", "銅鑼", "ゴーン", y("sine", f=110, a=.02, d=3.2, v=.28), y("sine", f=163, a=.02, d=2.5, v=.14), y("sine", f=231, a=.03, d=2, v=.1), y("sine", f=319, d=1.4, v=.06, vib=[3, 8, .2])),
    "taiko-hit": S("楽器", "太鼓", "ドン", y("sine", f=[110, 58], ft=.25, d=.75, v=.9), y(N, d=.14, v=.3, flt=["lowpass", 500])),
    "marimba-hit": S("楽器", "マリンバ", "コロン", y("sine", f=523, d=.45, v=.4), y("sine", f=2092, d=.08, v=.12)),
    "kalimba-hit": S("楽器", "カリンバ", "3 音の粒", y("sine", f=784, notes=[0, 4, 7], gap=.09, d=.7, v=.22), y("sine", f=4665, notes=[0, 4, 7], gap=.09, d=.1, v=.04)),
    "piano-chord": S("楽器", "ピアノの和音", "ジャーン（柔らか）", y("triangle", f=262, d=1.4, v=.15, flt=["lowpass", 2500]), y("triangle", f=330, d=1.4, v=.15, flt=["lowpass", 2500]),
                     y("triangle", f=392, d=1.4, v=.15, flt=["lowpass", 2500]), y("triangle", f=523, d=1.2, v=.1, flt=["lowpass", 2500])),
    "harp-gliss": S("楽器", "ハープのグリッサンド", "夢の場面へ", y("triangle", f=392, notes=[0, 2, 4, 7, 9, 12, 14, 16, 19, 21, 24], gap=.03, d=.8, v=.1)),
    "pizz": S("楽器", "ピチカート", "ポツ", y("triangle", f=392, d=.2, v=.35, flt=["lowpass", 1600])),
    "clap1": S("楽器", "手拍子", "パン", y(N, flt=["bandpass", 1200, 1.3], rep=3, gap=.012, d=.02, v=.3), y(N, at=.03, d=.14, v=.25, flt=["bandpass", 1200, 1.3])),
    "woodblock": S("楽器", "ウッドブロック", "カッ", y("sine", f=1100, d=.05, v=.5), y("sine", f=2600, d=.02, v=.12)),
    "triangle": S("楽器", "トライアングル", "チーン（金属）", y("sine", f=2800, d=1.5, v=.15), y("sine", f=7400, d=.8, v=.05)),
    # ── 追加: 操作
    "click-soft": S("操作", "クリック（柔らか）", "角の無いクリック", y(N, flt=["lowpass", 2500], d=.02, v=.5), y("sine", f=[1200, 900], ft=.02, d=.025, v=.15)),
    "double-click": S("操作", "ダブルクリック", "2 回続けて", y(N, flt=["highpass", 2800], d=.015, v=.5, rep=2, gap=.09), y("square", f=2000, d=.012, v=.08, rep=2, gap=.09)),
    "scroll": S("操作", "スクロール", "ホイールを回す", y(N, flt=["bandpass", 3200, 6], d=.012, v=.5, rep=8, gap=.035, rv=.9, rj=.006)),
    "drag": S("操作", "ドラッグ", "つかんで引きずる", y(N, a=.03, h=.15, d=.08, v=.3, flt=["bandpass", [900, 1400], 2, .25]), y("triangle", f=[180, 220], ft=.25, a=.03, h=.15, d=.08, v=.05)),
    "place": S("操作", "置く", "ことっと置く・はめる", y("sine", f=[420, 180], ft=.06, d=.1, v=.55), y(N, flt=["lowpass", 1200], d=.04, v=.3)),
    "unlock": S("操作", "解錠", "鍵が開く", y(N, flt=["bandpass", 2500, 5], d=.02, v=.5), y(N, at=.07, flt=["bandpass", 1800, 5], d=.03, v=.55), y("sine", f=1320, at=.1, notes=[0, 7], gap=.06, d=.15, v=.2)),
    "lock": S("操作", "施錠", "鍵を掛ける", y(N, flt=["bandpass", 1800, 5], d=.03, v=.55), y(N, at=.06, flt=["bandpass", 3000, 5], d=.015, v=.45), y("sine", f=660, at=.08, d=.12, v=.2)),
    "copy": S("操作", "複製", "同じ音が 2 つ", y("sine", f=1175, notes=[0, 0], gap=.07, d=.06, v=.3), y("sine", f=2350, notes=[0, 0], gap=.07, d=.03, v=.06)),
    "like": S("操作", "いいね", "ハートが付く", y("sine", f=[500, 1200], ft=.08, d=.12, v=.4), y("sine", f=1568, at=.08, notes=[0, 5], gap=.06, d=.25, v=.2)),
    "keypad": S("操作", "プッシュ音", "電話のボタン", y("sine", f=697, a=.003, h=.08, d=.04, v=.25), y("sine", f=1209, a=.003, h=.08, d=.04, v=.25)),
    "trash": S("操作", "ゴミ箱", "丸めて捨てる", y(N, flt=["bandpass", [1800, 900], 1.2, .25], d=.25, v=.4, rep=3, gap=.05, rj=.02, vj=.3), y("sine", f=[300, 120], at=.15, ft=.15, d=.18, v=.35)),
    "zip": S("操作", "ファスナー", "ジーッと閉じる・まとめる", y(N, flt=["bandpass", [1500, 4000], 3, .35], rep=14, gap=.025, d=.015, v=.35)),
    "slider": S("操作", "つまみ", "目盛りを上げる", y("sine", f=800, rep=8, gap=.045, rf=1.06, d=.025, v=.2), y(N, flt=["bandpass", 4000, 8], rep=8, gap=.045, d=.01, v=.3)),
    # ── 追加: 転換
    "whoosh-deep": S("転換", "ゴォッ", "低く太く流れる", y(N, a=.2, d=.4, v=.6, flt=["lowpass", [300, 1200], 1.5, .5]), y("sine", f=[70, 120], ft=.4, a=.2, d=.3, v=.3)),
    "whoosh-metal": S("転換", "シャーン", "金属的に流れる", y(N, a=.1, d=.25, v=.5, flt=["bandpass", [2000, 7000], 4, .3]), y("sawtooth", f=[800, 1600], ft=.3, a=.1, d=.2, v=.03, flt=["bandpass", 3000, 6])),
    "swish": S("転換", "風切り", "刀・棒を振る", y(N, a=.01, d=.14, v=.55, flt=["highpass", [3000, 9000], 1, .1]), y(N, at=.02, d=.08, v=.2, flt=["bandpass", 6000, 3])),
    "pass-by": S("転換", "通り過ぎる", "左から右へ横切る", y(N, a=.25, d=.35, v=.35, pan=-.7, flt=["bandpass", [500, 2200], 1.4, .3]), y(N, at=.18, a=.1, d=.35, v=.35, pan=.7, flt=["bandpass", [2200, 500], 1.4, .4]),
                      y("sawtooth", f=[180, 140], ft=.6, a=.25, d=.35, v=.03, flt=["lowpass", 900])),
    "warp": S("転換", "ワープ", "揺れながら跳ぶ", y("sine", f=[200, 2400], ft=.5, a=.05, h=.3, d=.25, v=.2, vib=[18, 80, .05]), y("sawtooth", f=[100, 1200], ft=.5, a=.05, h=.3, d=.2, v=.03, flt=["lowpass", [600, 6000], 2, .5])),
    "rewind": S("転換", "巻き戻し", "キュルキュルと戻る", y("square", f=[1800, 1200], ft=.05, rep=10, gap=.05, rf=.94, d=.04, v=.06, flt=["lowpass", 4000]), y(N, a=.05, h=.4, d=.1, v=.08, flt=["highpass", 4000])),
    "tape-stop": S("転換", "テープが止まる", "音が落ちて止まる", y("sawtooth", f=[440, 40], ft=.7, a=.005, h=.5, d=.25, v=.1, flt=["lowpass", [3000, 200], 1, .7]), y("sine", f=[220, 20], ft=.7, h=.5, d=.25, v=.2)),
    "scratch": S("転換", "スクラッチ", "レコードをこする", y(N, flt=["bandpass", [800, 3000], 4, .12], d=.14, v=.6), y(N, at=.14, flt=["bandpass", [3000, 700], 4, .14], d=.16, v=.6)),
    "downlifter": S("転換", "下降の風", "1.4 秒かけて落ちていく", y(N, a=.02, d=1.4, v=.45, flt=["highpass", [8000, 200], .7, 1.4]), y("sine", f=[400, 60], ft=1.3, a=.02, d=1.3, v=.12)),
    "sweep-up": S("転換", "長い上昇", "2 秒かけて昇りつめる", y(N, a=1.8, d=.1, v=.35, flt=["bandpass", [300, 9000], 2, 1.9]), y("sawtooth", f=[80, 640], ft=1.9, a=1.8, d=.1, v=.06, flt=["lowpass", [300, 4000], 2, 1.9])),
    "braam": S("転換", "ブォーン", "予告編の重い和音", y("sawtooth", f=65, a=.03, h=1.2, d=1.2, v=.12, sh=3, flt=["lowpass", [300, 1400], 2, .6]), y("sawtooth", f=98, dt=10, a=.03, h=1.2, d=1.2, v=.1, sh=3, flt=["lowpass", [300, 1400], 2, .6]),
                    y("sawtooth", f=131, a=.03, h=1.2, d=1.2, v=.08, sh=3, flt=["lowpass", [300, 1400], 2, .6]), y("sine", f=[80, 40], ft=1, d=1.5, v=.4)),
    "impact-metal": S("転換", "金属の衝撃", "ガーンと響く", y("sine", f=[90, 40], ft=.3, d=.5, v=.7), y("square", f=[440, 410], ft=.4, d=1.2, v=.04, flt=["bandpass", 1500, 6]), y("sine", f=2330, d=1, v=.08, vib=[6, 15, 0]),
                           y(N, d=.2, v=.3, flt=["highpass", 3000])),
    "impact-soft": S("転換", "柔らかい衝撃", "ドスッと受け止める", y("sine", f=[140, 55], ft=.2, d=.35, v=.65), y(N, flt=["lowpass", [1200, 200], 1, .2], d=.2, v=.3)),
    "teleport": S("転換", "転送", "粒になって消える・現れる", y("sine", f=880, notes=[0, 7, 12, 19, 24, 31], gap=.025, d=.12, v=.15, vib=[20, 40, 0]), y(N, a=.1, d=.3, v=.12, flt=["bandpass", [2000, 9000], 3, .3])),
    # ── 追加: 強調
    "glass-ting": S("強調", "グラスの響き", "澄んだ高い一音", y("sine", f=2217, d=1.4, v=.2), y("sine", f=5540, d=.5, v=.06), y("sine", f=2224, d=1.4, v=.1)),
    "choir-ah": S("強調", "天使の声", "アーと広がる和音", y("sawtooth", f=523, a=.25, h=.5, d=.8, v=.06, flt=["bandpass", 800, 4], vib=[5, 10, .3]), y("sawtooth", f=659, a=.3, h=.5, d=.8, v=.05, flt=["bandpass", 1150, 5]),
                      y("sawtooth", f=784, a=.3, h=.5, d=.8, v=.05, flt=["bandpass", 1000, 4]), y("sine", f=1046, a=.3, h=.5, d=.8, v=.08)),
    "bell-tree": S("強調", "ベルツリー", "高い粒が降りてくる", y("sine", f=4186, notes=[0, -2, -3, -5, -7, -9, -10, -12, -14, -15, -17, -19], gap=.045, d=.6, v=.08)),
    "cracker": S("強調", "クラッカー", "パン！と紙吹雪", y(N, flt=["bandpass", 1800, 1], d=.08, v=.8), y("sine", f=[300, 90], ft=.08, d=.1, v=.5), y(N, at=.06, flt=["highpass", 5000], rep=10, gap=.04, rj=.03, vj=.6, d=.03, v=.12)),
    "party-horn": S("強調", "パーティーの笛", "ピロロー", y("sawtooth", f=[520, 700], ft=.12, a=.02, h=.35, d=.1, v=.08, flt=["lowpass", 2500, 3], vib=[14, 30, .1]), y("square", f=[520, 700], ft=.12, a=.02, h=.35, d=.1, v=.03, flt=["lowpass", 1800])),
    "jackpot": S("強調", "大当たり", "コインがあふれる", y("square", f=988, notes=[0, 5, 0, 5, 0, 5, 0, 5, 12, 17], gap=.06, d=.05, v=.07), y("sine", f=1318, at=.6, d=1.2, v=.15),
                     y(N, at=.1, flt=["highpass", 6000], rep=12, gap=.05, rj=.02, vj=.5, d=.03, v=.1)),
    "tada": S("強調", "ジャジャーン", "短く長く、お披露目", y("sawtooth", f=392, d=.12, v=.07, flt=["lowpass", 2600]), y("sawtooth", f=494, d=.12, v=.06, flt=["lowpass", 2600]),
                  y("sawtooth", f=523, at=.16, h=.4, d=.6, v=.08, flt=["lowpass", 3000], vib=[5, 10, .2]), y("sawtooth", f=659, at=.16, h=.4, d=.6, v=.06, flt=["lowpass", 3000]),
                  y("sawtooth", f=784, at=.16, h=.4, d=.6, v=.06, flt=["lowpass", 3000]), y("sine", f=131, at=.16, d=1, v=.3)),
    "drama": S("強調", "衝撃の事実", "ダン、ダン、ダーン", y("sawtooth", f=196, notes=[0, -1], gap=.35, h=.2, d=.35, v=.08, flt=["lowpass", 1400]),
                   y("sawtooth", f=155.6, at=.7, h=.6, d=.8, v=.08, flt=["lowpass", 1400], vib=[5, 15, .3]), y("sine", f=[78, 70], at=.7, d=1.6, v=.3)),
    "heart-pop": S("強調", "ハート", "ぽわん", y("sine", f=[600, 1400], ft=.1, d=.15, v=.4), y("sine", f=2093, at=.09, d=.35, v=.12, vib=[8, 20, 0])),
    "flash": S("強調", "フラッシュ", "光る瞬間", y(N, d=.25, v=.4, flt=["highpass", 4000, .7]), y("sine", f=[3000, 1500], ft=.2, d=.3, v=.1)),
    # ── 追加: 通知
    "doorbell": S("通知", "ピンポーン", "玄関のチャイム", y("sine", f=659, d=1.2, v=.3), y("sine", f=523, at=.45, d=1.6, v=.3), y("sine", f=1977, d=.3, v=.05)),
    "phone-ring": S("通知", "電話", "トゥルルル×2", y("sine", f=1300, rep=16, gap=.05, a=.004, h=.01, d=.04, v=.15), y("sine", f=1600, rep=16, gap=.05, a=.004, h=.01, d=.04, v=.1),
                        y("sine", f=1300, at=1.1, rep=16, gap=.05, a=.004, h=.01, d=.04, v=.15), y("sine", f=1600, at=1.1, rep=16, gap=.05, a=.004, h=.01, d=.04, v=.1)),
    "vibrate": S("通知", "バイブ", "ブブッと震える", y("sawtooth", f=150, a=.01, h=.35, d=.05, v=.12, flt=["lowpass", 400], rep=2, gap=.55), y(N, a=.01, h=.35, d=.05, v=.08, flt=["bandpass", 180, 2], rep=2, gap=.55)),
    "mail": S("通知", "メール", "3 音の着信", y("sine", f=1047, notes=[0, 4, 7], gap=.08, d=.4, v=.22), y("triangle", f=2094, notes=[0, 4, 7], gap=.08, d=.1, v=.04)),
    "reminder": S("通知", "リマインダー", "ポン、ポン、ポン", y("triangle", f=880, notes=[0, 0, 0], gap=.18, d=.15, v=.28), y("sine", f=1760, notes=[0, 0, 0], gap=.18, d=.06, v=.05)),
    "timer-end": S("通知", "タイマー", "ピピピピ×2", y("square", f=2000, rep=4, gap=.14, a=.002, h=.07, d=.01, v=.07, flt=["lowpass", 4000]), y("square", f=2000, at=.8, rep=4, gap=.14, a=.002, h=.07, d=.01, v=.07, flt=["lowpass", 4000])),
    "error-soft": S("通知", "エラー（柔らか）", "下がる 2 音", y("sine", f=[440, 330], ft=.15, d=.2, v=.35), y("sine", f=[330, 262], at=.13, ft=.15, d=.25, v=.3)),
    "denied": S("通知", "拒否", "低い不協和の 2 回", y("square", f=185, a=.005, h=.25, d=.05, v=.1, flt=["lowpass", 1000], rep=2, gap=.35), y("square", f=131, a=.005, h=.25, d=.05, v=.1, flt=["lowpass", 1000], rep=2, gap=.35)),
    "correct": S("通知", "正解", "駆け上がって響く", y("square", f=1047, notes=[0, 4, 7, 12], gap=.05, d=.08, v=.05, flt=["lowpass", 5000]), y("sine", f=2093, at=.2, d=.7, v=.2)),
    "announce": S("通知", "館内放送", "ピンポンパンポーン", y("sine", f=698, notes=[0, 4, 7, 12], gap=.32, d=.9, v=.22), y("triangle", f=1396, notes=[0, 4, 7, 12], gap=.32, d=.2, v=.05)),
    # ── 追加: 数値
    "tally": S("数値", "集計", "音階で数え上げる", y("triangle", f=523, notes=[0, 2, 4, 5, 7, 9, 11, 12], gap=.07, d=.08, v=.25)),
    "cash": S("数値", "レジ", "チーンと引き出し", y("sine", f=2637, at=.12, d=.9, v=.2), y("sine", f=3136, at=.12, d=.6, v=.1), y(N, flt=["bandpass", 2500, 3], d=.04, v=.4, rep=2, gap=.05),
                  y("sine", f=[200, 120], at=.05, ft=.1, d=.12, v=.35)),
    "printer": S("数値", "印刷", "ジジジと刷る", y("square", f=[180, 200], rep=6, gap=.1, a=.01, h=.05, d=.03, v=.05, flt=["bandpass", 900, 3]), y(N, rep=6, gap=.1, a=.01, h=.05, d=.03, v=.15, flt=["bandpass", 3000, 2])),
    "barcode": S("数値", "読み取り", "バーコードのピッ", y("sine", f=2600, a=.002, h=.09, d=.02, v=.2), y("square", f=2600, a=.002, h=.09, d=.02, v=.02)),
    "loading": S("数値", "読み込み", "回る粒", y("sine", f=880, notes=[0, 4, 7, 12, 7, 4, 0, 4, 7, 12], gap=.09, d=.08, v=.15)),
    "upload": S("数値", "アップロード", "上がっていく粒", y("sine", f=440, rep=6, gap=.06, rf=1.19, d=.05, v=.2), y(N, a=.3, d=.1, v=.05, flt=["highpass", [1000, 6000], 1, .4])),
    "download": S("数値", "ダウンロード", "下がっていく粒", y("sine", f=1760, rep=6, gap=.06, rf=.84, d=.05, v=.2), y(N, a=.3, d=.1, v=.05, flt=["highpass", [6000, 1000], 1, .4])),
    "sync": S("数値", "同期", "行って戻って揃う", y("sine", f=660, notes=[0, 7], gap=.08, d=.1, v=.22), y("sine", f=990, at=.25, notes=[0, -7], gap=.08, d=.1, v=.22), y("sine", f=1320, at=.45, d=.3, v=.15)),
    "boot": S("数値", "起動音", "広がる和音", y("sine", f=262, a=.05, d=2.2, v=.12), y("sine", f=392, a=.05, d=2.2, v=.1), y("sine", f=523, a=.05, d=2.2, v=.1), y("sine", f=659, a=.08, d=2, v=.08),
                  y("triangle", f=1047, a=.1, d=1.5, v=.04)),
    "modem": S("数値", "モデム", "ピーガガガ（懐かしい接続）", y("sine", f=[1200, 2200], fe="lin", rep=6, gap=.12, ft=.1, d=.1, v=.1), y(N, at=.8, a=.1, h=.4, d=.1, v=.1, flt=["bandpass", 1800, 1]),
                   y("square", f=1650, at=.8, a=.01, h=.4, d=.05, v=.03)),
    # ── 追加: 自然・もの
    "door-creak": S("自然・もの", "扉のきしみ", "ギィー", y("sawtooth", f=[180, 260], ft=.8, a=.1, h=.5, d=.2, v=.05, flt=["bandpass", [900, 1400], 6, .8], vib=[22, 60, 0]),
                        y("sawtooth", f=[90, 130], ft=.8, a=.1, h=.5, d=.2, v=.04, flt=["bandpass", 600, 5])),
    "door-close": S("自然・もの", "扉を閉める", "バタン", y("sine", f=[120, 60], ft=.12, d=.35, v=.7), y(N, flt=["lowpass", [2000, 300], 1, .2], d=.25, v=.45), y(N, at=.08, flt=["bandpass", 2500, 6], d=.03, v=.3)),
    "steps": S("自然・もの", "歩く", "4 歩", y(N, flt=["lowpass", 700], d=.08, v=.5, rep=4, gap=.32, rj=.02, vj=.2), y(N, flt=["bandpass", 1800, 2], d=.03, v=.12, rep=4, gap=.32)),
    "rain": S("自然・もの", "雨", "ざあっと降る", y(N, a=.3, h=1, d=.5, v=.12, flt=["bandpass", 3500, .8]), y("sine", f=2200, rep=18, gap=.08, rj=.05, vj=.8, d=.02, v=.08)),
    "thunder": S("自然・もの", "雷", "ピシャッ、ゴロゴロ", y(N, a=.01, d=.15, v=.5, flt=["highpass", 1500]), y(N, a=.05, d=2.5, v=.7, flt=["lowpass", [900, 120], 1, 2]), y("sine", f=[50, 35], ft=2, a=.1, d=2, v=.35)),
    "fire": S("自然・もの", "焚き火", "パチパチ燃える", y(N, a=.3, h=.8, d=.5, v=.12, flt=["lowpass", 900]), y(N, rep=16, gap=.09, rj=.06, vj=.8, d=.012, v=.3, flt=["highpass", 2500])),
    "bird": S("自然・もの", "小鳥", "さえずり", y("sine", f=[3200, 4200], ft=.05, notes=[0, 2, 0, 5], gap=.09, d=.06, v=.15, vib=[30, 50, 0]), y("sine", f=[2800, 3600], at=.55, ft=.08, notes=[0, 3], gap=.1, d=.08, v=.12)),
    "splash": S("自然・もの", "水しぶき", "バシャッ", y(N, a=.005, d=.5, v=.5, flt=["bandpass", [2500, 900], .8, .4]), y("sine", f=[700, 1400], ft=.05, rep=4, gap=.07, rj=.03, d=.06, v=.15, rf=1.1)),
    "crumple": S("自然・もの", "紙を丸める", "くしゃくしゃ", y(N, flt=["bandpass", 3200, 1.5], rep=14, gap=.03, rj=.025, vj=.7, d=.03, v=.35), y(N, a=.1, d=.4, v=.08, flt=["bandpass", 2000, .8])),
    "glass-break": S("自然・もの", "ガラスが割れる", "ガシャン", y(N, d=.08, v=.6, flt=["highpass", 2500]), y("sine", f=3700, notes=[0, 5, -3, 9, 2, 12, -1], gap=.035, rj=.02, d=.3, v=.1),
                         y("sine", f=5100, at=.05, notes=[0, -4, 7, 3], gap=.05, d=.25, v=.07)),
    "cork": S("自然・もの", "栓を抜く", "ポンッ", y("sine", f=[500, 300], ft=.03, d=.06, v=.6), y(N, flt=["bandpass", 900, 3], d=.04, v=.4)),
    "cricket": S("自然・もの", "虫の声", "リリッ、リリッ", y("sine", f=4400, rep=3, gap=.05, a=.005, h=.02, d=.01, v=.15), y("sine", f=4400, at=.5, rep=3, gap=.05, a=.005, h=.02, d=.01, v=.15),
                     y("sine", f=4400, at=1, rep=3, gap=.05, a=.005, h=.02, d=.01, v=.15)),
    # ── 追加: ゲーム
    "hit8": S("ゲーム", "ダメージ", "8bit の被弾", y("square", f=[400, 120], ft=.1, d=.12, v=.1), y(N, nr=.4, d=.12, v=.25, flt=["lowpass", 3000])),
    "fall": S("ゲーム", "落下", "ヒューッと落ちる", y("sine", f=[1800, 300], ft=.9, fe="lin", a=.01, h=.8, d=.1, v=.2)),
    "boing": S("ゲーム", "バネ", "ボイーン", y("sine", f=[180, 420], ft=.25, a=.005, d=.45, v=.45, vib=[14, 120, 0]), y("triangle", f=[360, 840], ft=.25, d=.3, v=.08)),
    "slip": S("ゲーム", "すべる", "つるっ", y("sine", f=[900, 300], ft=.12, d=.15, v=.35), y("sine", f=[300, 1400], at=.14, ft=.2, d=.25, v=.3)),
    "dash": S("ゲーム", "ダッシュ", "勢いよく走り出す", y(N, a=.01, d=.2, v=.5, flt=["bandpass", [1500, 5000], 2, .15]), y("square", f=[200, 600], ft=.12, d=.12, v=.06)),
    "item": S("ゲーム", "アイテム", "手に入れた", y("square", f=784, notes=[0, 4, 7, 12, 16], gap=.05, d=.06, v=.07), y("triangle", f=1568, at=.25, d=.35, v=.2)),
    "heal": S("ゲーム", "回復", "きらきら満ちる", y("sine", f=523, notes=[0, 4, 7, 12, 16, 19, 24], gap=.07, d=.5, v=.12), y("triangle", f=1047, a=.2, h=.2, d=.6, v=.06, vib=[6, 15, .1])),
    "gameover": S("ゲーム", "ゲームオーバー", "下がって沈む", y("square", f=494, notes=[0, -1, -2, -3], gap=.3, h=.15, d=.12, v=.07, flt=["lowpass", 2500]), y("triangle", f=[123, 110], at=1.2, ft=.6, d=1, v=.3)),
    "shield": S("ゲーム", "防御", "膜が張る", y("sine", f=[300, 600], ft=.2, a=.01, h=.2, d=.3, v=.25, vib=[25, 60, 0]), y(N, a=.05, d=.4, v=.1, flt=["bandpass", 3000, 4])),
    "pause": S("ゲーム", "ポーズ", "一時停止", y("triangle", f=1568, notes=[0, -12], gap=.08, d=.08, v=.25)),
    "treasure": S("ゲーム", "宝箱", "開けたら響く", y("square", f=523, notes=[0, 4, 7, 11, 12, 16], gap=.1, d=.1, v=.07), y("triangle", f=1047, at=.6, h=.3, d=.6, v=.2, vib=[6, 12, .1])),
    # ── 追加: 楽器
    "timpani-roll": S("楽器", "ティンパニのロール", "ゴロゴロ…ドン", y("sine", f=[98, 92], rep=20, gap=.05, rv=1.05, a=.002, d=.25, v=.12), y("sine", f=[98, 90], at=1.02, d=1.5, v=.6)),
    "cowbell": S("楽器", "カウベル", "コン", y("square", f=587, d=.3, v=.07, flt=["bandpass", 800, 3]), y("square", f=845, d=.3, v=.05, flt=["bandpass", 900, 3])),
    "tambourine": S("楽器", "タンバリン", "シャラン", y(N, flt=["highpass", 7000], d=.2, v=.3), y(N, flt=["bandpass", 9500, 4], rep=3, gap=.02, d=.12, v=.15)),
    "bongo": S("楽器", "ボンゴ", "ポコポン", y("sine", f=[520, 470], ft=.05, d=.14, v=.5), y("sine", f=[380, 340], at=.14, ft=.05, d=.18, v=.5)),
    "steel-hit": S("楽器", "スチールドラム", "南国の 3 音", y("sine", f=784, notes=[0, 4, 7], gap=.1, d=.8, v=.2), y("sine", f=1568, notes=[0, 4, 7], gap=.1, d=.3, v=.07), y("sine", f=2352, notes=[0, 4, 7], gap=.1, d=.1, v=.03)),
    "tubular": S("楽器", "チューブラーベル", "カーンと長く", y("sine", f=392, d=3.5, v=.2), y("sine", f=792, d=2.5, v=.12), y("sine", f=1188, d=1.5, v=.08), y("sine", f=1948, d=.8, v=.05)),
    "glock-up": S("楽器", "鉄琴の駆け上がり", "音階を一気に", y("sine", f=1047, notes=[0, 2, 4, 5, 7, 9, 11, 12, 14, 16, 17, 19, 21, 23, 24], gap=.035, d=.5, v=.1)),
    "rimshot": S("楽器", "ツッコミ", "ドン、ドン、シャーン（オチ）", y("sine", f=[220, 140], ft=.1, d=.18, v=.5), y("sine", f=[160, 100], at=.18, ft=.1, d=.2, v=.55), y(N, at=.38, d=1, v=.3, flt=["highpass", 5000]),
                     y("sine", f=[70, 45], at=.38, ft=.1, d=.25, v=.6)),
    # ── 和
    "suzu": S("和", "鈴", "シャンシャン", y("sine", f=5200, rep=8, gap=.04, rj=.02, vj=.5, d=.35, v=.08), y(N, flt=["bandpass", 7000, 3], rep=8, gap=.04, rj=.02, d=.08, v=.1)),
    "kotsuzumi": S("和", "小鼓", "ポン", y("sine", f=[520, 300], ft=.08, d=.35, v=.45), y(N, flt=["bandpass", 1200, 2], d=.05, v=.3)),
    "shamisen-hit": S("和", "三味線", "ベン", y("sawtooth", f=196, d=.6, v=.12, pe=[1.05, .05], flt=["lowpass", [4000, 800], 3, .3]), y(N, flt=["bandpass", 2500, 2], d=.03, v=.4)),
    "taiko-roll": S("和", "太鼓の連打", "ドドドド…ドン", y("sine", f=[110, 60], ft=.2, rep=10, gap=.1, rv=1.08, d=.3, v=.4), y("sine", f=[110, 55], at=1.02, ft=.3, d=.9, v=.9), y(N, at=1.02, d=.14, v=.3, flt=["lowpass", 500])),
    "shishi-odoshi": S("和", "ししおどし", "カコーン", y("sine", f=[900, 700], ft=.05, d=.2, v=.5), y("sine", f=[1800, 1500], ft=.05, d=.08, v=.15), y("sine", f=[500, 450], at=.25, d=.12, v=.2)),
    "furin": S("和", "風鈴", "チリーン", y("sine", f=3520, d=2, v=.14, vib=[6, 6, 0]), y("sine", f=5600, d=1.2, v=.06), y("sine", f=3530, at=.45, d=1.8, v=.08)),
    "kane": S("和", "寺の鐘", "ゴーンと長く残る", y("sine", f=138, a=.01, d=6, v=.3), y("sine", f=139.5, a=.01, d=6, v=.15), y("sine", f=366, d=3.5, v=.1), y("sine", f=620, d=2, v=.05), y(N, d=.08, v=.15, flt=["lowpass", 800])),
    "hyoshigi-roll": S("和", "拍子木の連打", "チョン、チョン、チョン…", y("sine", f=1400, rep=12, gap=.09, rj=.01, d=.05, v=.4), y("sine", f=3300, rep=12, gap=.09, d=.02, v=.12)),
}
# 効果音の音量の揃え（--sounds のページで合成した山の高さから求めた倍率。効果音を足したら測り直す）
SFX_GAIN = {"click": 0.81, "pop": 0.92, "pop-soft": 1.09, "blip": 2.2, "tick": 2.08, "toggle": 2.2, "select": 1.45, "confirm": 1.47, "back": 1.53, "hover": 3, "key": 2.2, "key-soft": 3, "typewriter": 0.84, "carriage": 1.54, "send": 1.44, "receive": 1.46, "message": 1.47, "delete": 1.37, "nav": 1.68, "switch": 3, "whoosh": 2.16, "whoosh-long": 1.98, "whoosh-short": 1.78, "swoosh-down": 1.85, "swipe": 3, "air": 3, "zoom-in": 1.9, "zoom-out": 1.89, "riser": 1.9, "downer": 2.2, "reverse": 1.87, "shutter": 1.25, "glitch": 1.46, "cut": 0.67, "impact": 0.5, "boom": 0.53, "subdrop": 0.64, "slide": 2.78, "page": 1.7, "curtain": 3, "flip": 1.75, "ding": 1.36, "chime": 1.38, "bell": 1.18, "rin": 1.14, "sparkle": 2.5, "shimmer": 3, "twinkle": 2.62, "magic": 2.55, "bling": 2.06, "success": 1.52, "fanfare": 2.2, "orchestra": 1.6, "stamp": 0.64, "reveal": 1.68, "ping": 2.01, "underline": 3, "applause": 3, "notify": 1.55, "notify-soft": 1.43, "alert": 2.2, "error": 2.2, "buzzer": 1.58, "alarm": 2.2, "siren": 2.2, "warning": 1.76, "done": 1.79, "ok": 1.68, "question": 1.74, "count": 2.2, "counter": 3, "scan": 3, "beep": 2.78, "radar": 2.28, "sonar": 1.26, "data": 2.2, "compute": 2.2, "process": 3, "charge": 2.2, "powerup": 1.19, "powerdown": 1.66, "connect": 1.46, "disconnect": 2.1, "graph-rise": 3, "bubble": 1.46, "drop": 1.11, "water": 2.02, "knock": 0.75, "paper": 2.81, "pencil": 3, "clock-tick": 3, "heartbeat": 0.7, "footstep": 2.94, "wind": 3, "snap": 1.54, "clink": 2.29, "hyoshigi": 0.78, "coin": 2.2, "jump": 2.2, "powerup8": 2.2, "levelup": 1.25, "laser": 2.2, "zap": 2.2, "oneup": 2.2, "select8": 2.2, "win": 2.2, "drumroll": 1.92, "cymbal": 2.02, "taiko-hit": 0.55, "kalimba-hit": 1.48, "piano-chord": 1.17, "harp-gliss": 2.03, "pizz": 1.48, "clap1": 3, "woodblock": 0.87, "triangle": 2.58, "tap": 1.04, "bloop": 1.03, "swoosh-up": 0.71, "stab": 1.06, "thump": 1.03, "wood": 0.98, "explode8": 1.16, "gong": 1.05, "marimba-hit": 0.98, "click-soft": 1.41, "double-click": 0.78, "scroll": 3, "drag": 3, "place": 0.78, "unlock": 2.44, "lock": 2.53, "copy": 1.49, "like": 1.3, "keypad": 1.0, "trash": 1.32, "zip": 3.62, "slider": 1.81, "whoosh-deep": 1.14, "whoosh-metal": 2.2, "swish": 0.68, "pass-by": 2.83, "warp": 2.13, "rewind": 2.2, "tape-stop": 2.2, "scratch": 1.84, "downlifter": 0.67, "sweep-up": 1.62, "braam": 0.76, "impact-metal": 0.48, "impact-soft": 0.78, "teleport": 2.59, "glass-ting": 1.4, "choir-ah": 3.6, "bell-tree": 2.94, "cracker": 0.71, "party-horn": 3.03, "jackpot": 2.2, "tada": 1.36, "drama": 1.62, "heart-pop": 1.25, "flash": 0.93, "doorbell": 1.59, "phone-ring": 2.0, "vibrate": 3.28, "mail": 1.8, "reminder": 1.71, "timer-end": 4.76, "error-soft": 1.43, "denied": 2.08, "correct": 2.2, "announce": 1.85, "tally": 2.06, "cash": 1.25, "printer": 4.13, "barcode": 2.2, "loading": 3, "upload": 2.24, "download": 2.12, "sync": 2.29, "boot": 1.74, "modem": 4.05, "door-creak": 16.41, "door-close": 0.65, "steps": 3, "rain": 3, "thunder": 0.66, "fire": 1.79, "bird": 3, "splash": 1.47, "crumple": 3, "glass-break": 0.73, "cork": 0.86, "cricket": 3, "hit8": 1.67, "fall": 2.5, "boing": 1.07, "slip": 1.46, "dash": 2.2, "item": 2.2, "heal": 2.52, "gameover": 1.69, "shield": 1.78, "pause": 2.07, "treasure": 2.2, "timpani-roll": 0.81, "cowbell": 4.64, "tambourine": 1.24, "bongo": 1.02, "steel-hit": 1.45, "tubular": 1.31, "glock-up": 2.14, "rimshot": 0.53, "suzu": 3.43, "kotsuzumi": 1.11, "shamisen-hit": 2.2, "taiko-roll": 0.56, "shishi-odoshi": 0.88, "furin": 2.54, "kane": 0.88, "hyoshigi-roll": 1.01}
for _k, _g in SFX_GAIN.items():
    SFX[_k]["g"] = _g
SFX_CATS = ["操作", "転換", "強調", "通知", "数値", "自然・もの", "ゲーム", "楽器", "和"]

# ──────────────────────────────────────────────────────────────────────────
# 映像の出来事（効果音を当てるきっかけ）と効果音の組
# ──────────────────────────────────────────────────────────────────────────
# 出来事: 説明, 段階（1=少なめでも鳴る 2=標準 3=多め）
EVENTS = {
    "chapter": ("章の始まり", 1), "tr.fade": ("場面の切り替え（fade）", 2), "tr.slide": ("切り替え（slide）", 1), "tr.push": ("切り替え（push）", 1),
    "tr.wipe": ("切り替え（wipe）", 1), "tr.zoom": ("切り替え（zoom）", 1), "tr.cut": ("切り替え（cut）", 1),
    "title": ("題名が出る", 1), "outro": ("締めの題名", 1), "appear": ("項目・カード・点が出る", 2), "step": ("手順が進む", 2),
    "tick": ("年表の点", 2), "row": ("表の行", 3), "word": ("語が飛び出す（kinetic）", 2), "hit": ("強い言い切り・VS・強調の語", 1),
    "emphasize": ("強調（コードの行・表の行・下線）", 2), "reveal": ("前後の切り替え（beforeafter）", 1), "quote": ("引用が出る", 2),
    "connect": ("線がつながる", 2), "travel": ("受け渡しの印が動く", 2), "arrive": ("受け渡しの印が着く", 2),
    "type": ("入力（打鍵の連続）", 2), "enter": ("コマンドの確定", 2), "count": ("数え上げ（刻みの連続）", 2), "countEnd": ("数え上げの終わり", 1),
    "grow": ("棒・線が伸びる", 2), "sweep": ("円グラフが回る", 2), "message": ("相手のメッセージ", 1), "send": ("自分のメッセージ", 1),
    "toast": ("画面の中の通知", 1), "notify": ("OS 風の通知", 1), "done": ("状態が完了に", 1), "blocked": ("状態が承認待ち・エラーに", 1), "working": ("状態が作業中に", 3),
    "note": ("注記", 2), "arrow": ("矢印", 2), "highlight": ("強調の枠・スポットライト", 2), "badge": ("バッジ", 2), "click": ("カーソルのクリック", 1),
    "nav": ("チャプターを移る操作", 1),
}
# 組: 出来事 → [効果音, 音量, 番号ごとに上げる半音]。None は鳴らさない。standard に無い出来事は standard から
KITS = {
    "standard": ("標準", "はっきり、でも控えめ。迷ったらこれ", {
        "chapter": ["chime", .8], "tr.fade": ["air", .6], "tr.slide": ["whoosh", .7], "tr.push": ["whoosh", .8], "tr.wipe": ["swipe", .8],
        "tr.zoom": ["zoom-in", .7], "tr.cut": ["cut", .7], "title": ["reveal", .8], "outro": ["chime", .7], "appear": ["pop", .55, 1],
        "step": ["select", .6, 2], "tick": ["tick", .7, 1], "row": ["tick", .4], "word": ["tap", .5, 1], "hit": ["impact", .55],
        "emphasize": ["ping", .45], "reveal": ["swoosh-up", .6], "quote": ["page", .5], "connect": ["blip", .4, 1], "travel": ["whoosh-short", .45],
        "arrive": ["pop-soft", .5], "type": ["key", .45], "enter": ["tap", .35], "count": ["count", .5], "countEnd": ["ding", .45],
        "grow": ["graph-rise", .5, 1], "sweep": ["swoosh-up", .5], "message": ["receive", .6], "send": ["send", .6], "toast": ["notify-soft", .7],
        "notify": ["notify", .7], "done": ["done", .6], "blocked": ["warning", .6], "working": ["blip", .3], "note": ["pop-soft", .5],
        "arrow": ["whoosh-short", .4], "highlight": ["sparkle", .45], "badge": ["stamp", .5], "click": ["click", .8], "nav": ["nav", .6]}),
    "soft": ("柔らか", "角の無い音。研修・医療・子ども向け", {
        "chapter": ["notify-soft", .7], "tr.slide": ["slide", .5], "tr.push": ["slide", .6], "tr.wipe": ["page", .5], "tr.zoom": ["air", .7],
        "tr.cut": ["thump", .4], "title": ["kalimba-hit", .7], "outro": ["kalimba-hit", .6], "appear": ["pop-soft", .5, 1], "step": ["marimba-hit", .45, 2],
        "tick": ["wood", .5, 1], "word": ["pop-soft", .45, 1], "hit": ["thump", .6], "emphasize": ["ping", .35], "connect": ["pop-soft", .35, 1],
        "travel": ["air", .6], "arrive": ["drop", .35], "type": ["key-soft", .45], "countEnd": ["ping", .4], "grow": ["air", .6],
        "done": ["notify-soft", .6], "blocked": ["question", .45], "highlight": ["twinkle", .35], "badge": ["pop-soft", .5], "click": ["tap", .5]}),
    "digital": ("デジタル", "電子音。技術・データ・SaaS", {
        "chapter": ["powerup", .5], "tr.fade": ["whoosh-short", .3], "tr.slide": ["whoosh-short", .6], "tr.push": ["scan", .5], "tr.wipe": ["scan", .5],
        "tr.zoom": ["zoom-in", .6], "tr.cut": ["glitch", .5], "title": ["powerup", .6], "outro": ["done", .6], "appear": ["blip", .5, 1],
        "step": ["beep", .45, 2], "tick": ["blip", .45, 1], "row": ["count", .5], "word": ["blip", .4, 1], "hit": ["glitch", .6],
        "emphasize": ["scan", .35], "connect": ["connect", .45], "travel": ["data", .5], "arrive": ["beep", .35], "type": ["key", .45],
        "enter": ["blip", .4], "count": ["count", .5], "countEnd": ["beep", .45], "grow": ["scan", .45], "sweep": ["scan", .45],
        "toast": ["notify", .6], "done": ["ok", .55], "blocked": ["error", .55], "highlight": ["scan", .4], "badge": ["beep", .45], "click": ["click", .8]}),
    "retro": ("レトロ", "8bit のゲーム音。遊び心・レトロ", {
        "chapter": ["levelup", .6], "tr.fade": None, "tr.slide": ["jump", .5], "tr.push": ["jump", .5], "tr.wipe": ["laser", .4], "tr.zoom": ["powerup8", .4],
        "tr.cut": ["select8", .5], "title": ["powerup8", .6], "outro": ["win", .6], "appear": ["select8", .45, 1], "step": ["coin", .5, 2],
        "tick": ["select8", .4, 1], "row": ["select8", .3], "word": ["select8", .4, 1], "hit": ["explode8", .5], "emphasize": ["coin", .4],
        "connect": ["select8", .35, 1], "travel": ["jump", .35], "arrive": ["coin", .4], "type": ["count", .5], "enter": ["select8", .4],
        "countEnd": ["coin", .5], "grow": ["powerup8", .35], "message": ["select8", .5], "send": ["jump", .45], "toast": ["coin", .5],
        "notify": ["oneup", .5], "done": ["oneup", .5], "blocked": ["error", .5], "highlight": ["powerup8", .35], "badge": ["coin", .45], "click": ["select8", .6]}),
    "organic": ("自然", "木・紙・水の音。手作り・生活・教育", {
        "chapter": ["kalimba-hit", .6], "tr.fade": ["paper", .35], "tr.slide": ["slide", .55], "tr.push": ["slide", .6], "tr.wipe": ["page", .6],
        "tr.zoom": ["wind", .5], "tr.cut": ["knock", .4], "title": ["kalimba-hit", .7], "outro": ["clink", .6], "appear": ["wood", .5, 1],
        "step": ["woodblock", .5, 2], "tick": ["pencil", .4], "row": ["wood", .3], "word": ["wood", .4, 1], "hit": ["taiko-hit", .5],
        "emphasize": ["underline", .5], "reveal": ["page", .6], "connect": ["drop", .4, 1], "travel": ["slide", .45], "arrive": ["drop", .4],
        "type": ["typewriter", .45], "enter": ["carriage", .35], "countEnd": ["clink", .45], "grow": ["paper", .45], "sweep": ["paper", .45],
        "message": ["water", .45], "send": ["bubble", .45], "toast": ["notify-soft", .6], "done": ["kalimba-hit", .5], "blocked": ["knock", .5],
        "note": ["paper", .45], "arrow": ["pencil", .4], "highlight": ["underline", .5], "badge": ["stamp", .55], "click": ["snap", .5]}),
    "cinematic": ("映画", "重い転換と大きな一撃。予告・ビジョン・発表", {
        "chapter": ["boom", .45], "tr.fade": ["whoosh-long", .3], "tr.slide": ["whoosh-long", .55], "tr.push": ["whoosh-long", .6], "tr.wipe": ["whoosh-long", .55],
        "tr.zoom": ["riser", .45], "tr.cut": ["impact", .5], "title": ["boom", .6], "outro": ["gong", .5], "appear": ["thump", .4, 1],
        "step": ["taiko-hit", .4], "tick": ["thump", .35], "word": ["thump", .4], "hit": ["impact", .7], "emphasize": ["orchestra", .3],
        "reveal": ["whoosh-long", .6], "connect": ["whoosh-short", .3], "travel": ["whoosh-short", .4], "arrive": ["thump", .35],
        "countEnd": ["impact", .45], "grow": ["riser", .35], "sweep": ["whoosh-long", .4], "highlight": ["shimmer", .45], "badge": ["impact", .35]}),
    "playful": ("楽しい", "泡・星・跳ねる音。子ども・イベント・SNS", {
        "chapter": ["twinkle", .6], "tr.fade": ["bubble", .25], "tr.slide": ["swipe", .5], "tr.push": ["swipe", .6], "tr.wipe": ["swipe", .6],
        "tr.zoom": ["jump", .4], "tr.cut": ["pop", .5], "title": ["magic", .6], "outro": ["success", .6], "appear": ["bubble", .45, 1],
        "step": ["bloop", .5, 2], "tick": ["pop", .45, 1], "word": ["pop", .45, 1], "hit": ["jump", .5], "emphasize": ["twinkle", .4],
        "connect": ["bubble", .35], "travel": ["whoosh-short", .4], "arrive": ["pop", .4], "countEnd": ["coin", .45], "grow": ["jump", .35],
        "message": ["bubble", .5], "send": ["pop", .5], "done": ["success", .5], "blocked": ["bloop", .5], "note": ["pop", .45],
        "highlight": ["sparkle", .5], "badge": ["pop", .5], "click": ["pop", .6]}),
    "wa": ("和", "拍子木・りん・太鼓。和の題材", {
        "chapter": ["rin", .6], "tr.fade": ["wind", .25], "tr.slide": ["slide", .5], "tr.push": ["slide", .55], "tr.wipe": ["paper", .55],
        "tr.zoom": ["wind", .45], "tr.cut": ["hyoshigi", .45], "title": ["taiko-hit", .7], "outro": ["rin", .6], "appear": ["woodblock", .45, 1],
        "step": ["woodblock", .5, 2], "tick": ["wood", .45, 1], "word": ["wood", .4, 1], "hit": ["taiko-hit", .65], "emphasize": ["rin", .3],
        "reveal": ["paper", .55], "connect": ["wood", .35], "travel": ["slide", .4], "arrive": ["woodblock", .35], "type": ["key-soft", .45],
        "enter": ["woodblock", .35], "countEnd": ["rin", .4], "grow": ["wind", .4], "done": ["rin", .45], "blocked": ["hyoshigi", .4],
        "highlight": ["shimmer", .35], "badge": ["stamp", .55], "click": ["wood", .5]}),
    "news": ("報道", "スタブとスワイプ。ニュース・速報・レポート", {
        "chapter": ["stab", .6], "tr.fade": ["swoosh-down", .3], "tr.slide": ["swipe", .6], "tr.push": ["whoosh", .7], "tr.wipe": ["swipe", .7],
        "tr.cut": ["stab", .45], "title": ["orchestra", .5], "outro": ["stab", .5], "appear": ["tick", .6, 1], "step": ["tick", .6, 1],
        "hit": ["stab", .55], "emphasize": ["stab", .35], "countEnd": ["stab", .4], "grow": ["swoosh-up", .45], "toast": ["alert", .5],
        "notify": ["alert", .6], "highlight": ["swipe", .45], "badge": ["stamp", .5]}),
    "minimal": ("最小限", "章・通知・クリックだけ。静かに見せたいとき", {
        "chapter": ["ping", .5], "title": ["ping", .45], "outro": ["ping", .45], "countEnd": ["ping", .35], "toast": ["notify-soft", .6],
        "notify": ["notify-soft", .6], "done": ["ping", .4], "blocked": ["warning", .45], "click": ["click", .7], "nav": ["tap", .5],
        "**": None}),
    "scifi": ("SF", "光線・ワープ・転送・電子の起動音。宇宙・未来・SF", {
        "chapter": ["warp", .5], "tr.fade": ["whoosh-metal", .3], "tr.slide": ["pass-by", .5], "tr.push": ["warp", .45], "tr.wipe": ["whoosh-metal", .5],
        "tr.zoom": ["teleport", .5], "tr.cut": ["laser", .35], "title": ["boot", .6], "outro": ["teleport", .5], "appear": ["blip", .45, 1],
        "step": ["teleport", .35], "tick": ["beep", .35, 1], "word": ["blip", .4, 1], "hit": ["impact-metal", .55], "emphasize": ["shield", .35],
        "reveal": ["warp", .45], "connect": ["sync", .4], "travel": ["upload", .4], "arrive": ["barcode", .35], "type": ["key", .4],
        "enter": ["barcode", .35], "count": ["count", .5], "countEnd": ["shield", .4], "grow": ["sweep-up", .3], "sweep": ["scan", .45],
        "message": ["mail", .5], "send": ["upload", .45], "toast": ["notify", .55], "notify": ["mail", .6], "done": ["boot", .4],
        "blocked": ["denied", .45], "highlight": ["shield", .35], "badge": ["barcode", .4], "click": ["click-soft", .7]}),
    "horror": ("ホラー", "低い一撃・鐘・きしみ・心音。怪談・警告・ミステリー", {
        "chapter": ["kane", .45], "tr.fade": ["downlifter", .25], "tr.slide": ["whoosh-deep", .5], "tr.push": ["whoosh-deep", .55], "tr.wipe": ["door-creak", .4],
        "tr.zoom": ["downlifter", .35], "tr.cut": ["impact-soft", .5], "title": ["braam", .5], "outro": ["kane", .45], "appear": ["heartbeat", .35],
        "step": ["steps", .35], "tick": ["clock-tick", .45], "word": ["thump", .4], "hit": ["braam", .45], "emphasize": ["drama", .3],
        "reveal": ["door-creak", .45], "quote": ["crumple", .35], "connect": ["drop", .35], "travel": ["whoosh-deep", .35], "arrive": ["door-close", .3],
        "type": ["typewriter", .35], "enter": ["carriage", .3], "countEnd": ["tubular", .35], "grow": ["downlifter", .3], "sweep": ["whoosh-deep", .35],
        "message": ["phone-ring", .35], "send": ["whoosh-deep", .35], "toast": ["vibrate", .45], "notify": ["vibrate", .5], "done": ["tubular", .35],
        "blocked": ["denied", .45], "highlight": ["thunder", .3], "badge": ["door-close", .35], "click": ["click-soft", .5]}),
    "kids": ("子ども", "バネ・ハート・鉄琴・クラッカー。子ども・教育・絵本", {
        "chapter": ["glock-up", .45], "tr.fade": ["heart-pop", .25], "tr.slide": ["boing", .4], "tr.push": ["slip", .4], "tr.wipe": ["swipe", .5],
        "tr.zoom": ["boing", .4], "tr.cut": ["cork", .45], "title": ["party-horn", .45], "outro": ["cracker", .45], "appear": ["heart-pop", .4, 1],
        "step": ["marimba-hit", .45, 2], "tick": ["bongo", .4, 1], "word": ["cork", .4, 1], "hit": ["boing", .5], "emphasize": ["glock-up", .3],
        "reveal": ["tada", .4], "connect": ["bubble", .35, 1], "travel": ["slip", .3], "arrive": ["cork", .35], "type": ["key-soft", .45],
        "countEnd": ["correct", .45], "grow": ["boing", .3], "sweep": ["slip", .35], "message": ["heart-pop", .45], "send": ["like", .45],
        "toast": ["notify-soft", .6], "done": ["correct", .45], "blocked": ["error-soft", .4], "note": ["heart-pop", .4], "highlight": ["twinkle", .4],
        "badge": ["like", .45], "click": ["click-soft", .6]}),
    "game": ("ゲーム", "アイテム・回復・宝箱・ダッシュ。RPG・ゲーム風の案内", {
        "chapter": ["treasure", .5], "tr.slide": ["dash", .45], "tr.push": ["dash", .5], "tr.wipe": ["swish", .45], "tr.zoom": ["warp", .4],
        "tr.cut": ["hit8", .4], "title": ["item", .55], "outro": ["levelup", .55], "appear": ["pause", .4, 1], "step": ["item", .35, 1],
        "tick": ["select8", .4, 1], "word": ["select8", .4, 1], "hit": ["hit8", .55], "emphasize": ["heal", .3], "reveal": ["treasure", .45],
        "connect": ["select8", .35, 1], "travel": ["dash", .35], "arrive": ["coin", .4], "type": ["count", .45], "enter": ["pause", .35],
        "countEnd": ["jackpot", .35], "grow": ["heal", .3], "sweep": ["swish", .35], "message": ["pause", .45], "send": ["jump", .4],
        "toast": ["item", .45], "notify": ["oneup", .5], "done": ["levelup", .45], "blocked": ["hit8", .45], "highlight": ["shield", .35],
        "badge": ["coin", .45], "click": ["select8", .55]}),
    "luxury": ("上質", "ガラス・鐘・声の響き。高級・ブランド・式典", {
        "chapter": ["glass-ting", .5], "tr.fade": ["air", .5], "tr.slide": ["whoosh-deep", .35], "tr.push": ["whoosh-deep", .4], "tr.wipe": ["swish", .3],
        "tr.zoom": ["air", .6], "tr.cut": ["impact-soft", .35], "title": ["choir-ah", .4], "outro": ["tubular", .4], "appear": ["glass-ting", .3, 1],
        "step": ["marimba-hit", .35, 2], "tick": ["clink", .3, 1], "word": ["glass-ting", .25, 1], "hit": ["impact-soft", .45], "emphasize": ["bell-tree", .3],
        "reveal": ["harp-gliss", .4], "quote": ["page", .4], "connect": ["glass-ting", .25, 1], "travel": ["air", .5], "arrive": ["clink", .3],
        "type": ["key-soft", .4], "enter": ["glass-ting", .25], "countEnd": ["bell-tree", .35], "grow": ["air", .5], "sweep": ["swish", .3],
        "toast": ["notify-soft", .55], "notify": ["notify-soft", .55], "done": ["glass-ting", .4], "blocked": ["error-soft", .4], "highlight": ["bell-tree", .3],
        "badge": ["clink", .4], "click": ["click-soft", .6]}),
}
DENSITY = {"low": 1, "normal": 2, "high": 3}


# ──────────────────────────────────────────────────────────────────────────
# 台本の audio を確かめて、HTML に埋め込む形にする
# ──────────────────────────────────────────────────────────────────────────
def _data_uri(path):
    mime = mimetypes.guess_type(path)[0] or "audio/mpeg"
    return "data:%s;base64,%s" % (mime, base64.b64encode(open(path, "rb").read()).decode("ascii"))


def _read_code(v, base, where, errs):
    if v.get("src"):
        p = os.path.join(base, v["src"])
        if not os.path.isfile(p):
            errs.append("%s: src が見つかりません: %s" % (where, p))
            return None
        return open(p, encoding="utf-8").read()
    c = v.get("code")
    return "\n".join(c) if isinstance(c, list) else c


def _check_recipe(r, where, errs):
    if not isinstance(r, dict) or not isinstance(r.get("l"), list) or not r["l"]:
        errs.append("%s: 音色は {\"l\": [層, …]} の形にしてください（層の書き方は --list-sounds）" % where)
        return
    for i, lay in enumerate(r["l"]):
        bad = set(lay) - LAYER_KEYS
        if bad:
            errs.append("%s: l[%d] に使えない項目 %s（使える項目: %s）" % (where, i, ", ".join(sorted(bad)), " ".join(sorted(LAYER_KEYS))))
        if lay.get("w", "sine") not in WAVES:
            errs.append("%s: l[%d] の w %r は %s のいずれか" % (where, i, lay.get("w"), "/".join(sorted(WAVES))))


def _check_music(d, where, insts, errs):
    if d.get("file"):
        return
    if d.get("scale", "major") not in SCALES:
        errs.append("%s: scale %r は %s のいずれか" % (where, d.get("scale"), "/".join(SCALES)))
    if d.get("key", "C") not in KEYS:
        errs.append("%s: key %r は %s のいずれか" % (where, d.get("key"), "/".join(KEYS)))
    prog = d.get("prog") or []
    for sym in [x for p in prog for x in (p if isinstance(p, list) else [p])]:
        if not re.match(r"^b?[1-7](m|M|7|9|s4|s2|p)*$", str(sym)):
            errs.append("%s: prog の和音 %r は「度数 1〜7」に b（前）・m M 7 9 s4 s2 p（後）を付けた形" % (where, sym))
    dr = d.get("drum")
    if isinstance(dr, dict):
        for inst, pat in dr.items():
            if inst not in insts:
                errs.append("%s: drum の楽器 %r は楽器の一覧（--list-sounds）か audio.instruments に無い" % (where, inst))
            if not isinstance(pat, str) or not re.match(r"^[xXgrt.\- ]+$", pat):
                errs.append("%s: drum の %s は x X g r t . の並び（1 文字が 16 分の刻み）" % (where, inst))
    elif dr and dr not in DRUMS:
        errs.append("%s: drum %r は %s のいずれか、または {楽器: \"x...x...\"}" % (where, dr, "/".join(DRUMS)))
    if not d.get("code"):
        for i, lay in enumerate(d.get("layers") or []):
            if lay.get("inst") not in insts:
                errs.append("%s: layers[%d] の inst %r は楽器の一覧（--list-sounds）か audio.instruments に無い" % (where, i, lay.get("inst")))
            if lay.get("pat", "hold") not in PATTERNS:
                errs.append("%s: layers[%d] の pat %r は %s のいずれか" % (where, i, lay.get("pat"), "/".join(PATTERNS)))
        if not d.get("layers") and not d.get("drum"):
            errs.append("%s: 曲には layers（楽器 × 型）か drum、または code（src）が必要です" % where)


def _music(v, where, base, insts, errs, table, n):
    """曲の指定 → 埋め込む表のキー（無音は None）。v: 名前 | {preset, …上書き} | {file} | {code|src, bpm, …} | 曲の定義そのもの"""
    if v in (None, False, "", "none"):
        return None
    if isinstance(v, str):
        if v not in MUSIC:
            errs.append("%s: 曲 %r は無い（--list-sounds で一覧。近い名前: %s）" % (where, v, ", ".join(_near(v, MUSIC)) or "なし"))
            return None
        d = {k: x for k, x in MUSIC[v].items() if k not in ("cat", "name", "desc")}
        key = v
    elif isinstance(v, dict):
        fk = "file:%s:%s:%s" % (v.get("file"), v.get("volume"), v.get("loop"))
        if v.get("file") and fk in table.get("_files", {}):   # 同じファイルは 1 回だけ埋め込む（章・場面で同じ曲を何度使っても）
            return table["_files"][fk]
        if v.get("file"):
            p = os.path.join(base, v["file"])
            if not re.match(r"^(data:|https?:)", v["file"]) and not os.path.isfile(p):
                errs.append("%s: 音楽のファイルが見つかりません: %s" % (where, p))
                return None
            d = dict(v)
            d["file"] = v["file"] if re.match(r"^(data:|https?:)", v["file"]) else _data_uri(p)
        else:
            if v.get("preset"):
                if v["preset"] not in MUSIC:
                    errs.append("%s: preset %r は無い（--list-sounds）" % (where, v["preset"]))
                    return None
                d = {k: x for k, x in copy.deepcopy(MUSIC[v["preset"]]).items() if k not in ("cat", "name", "desc")}
                d.update({k: x for k, x in v.items() if k != "preset"})
            else:
                d = dict(v)
            if not v.get("preset"):
                d.setdefault("g", .35)   # 自作の曲は大きさを測っていないので控えめに（g で変えられる）
            if d.get("src") or d.get("code"):
                code = _read_code(d, base, where, errs)
                d.pop("src", None)
                if code:
                    d["code"] = code
        key = "custom%d" % n
        if v.get("file"):
            table.setdefault("_files", {})[fk] = key
    else:
        errs.append("%s: 曲は名前か {preset|file|code|src|layers …} で指定してください" % where)
        return None
    _check_music(d, where, insts, errs)
    table[key] = d
    return key


def _near(name, table):
    return [k for k in table if k.startswith(name[:2]) or name in k][:5]


def prepare(spec, base):
    """spec["audio"] を確かめ、_music（使う曲の定義）・_sfx（効果音の音色）・_kit（出来事 → 効果音）を書き込む。エラーの一覧を返す。"""
    errs = []
    au = spec.get("audio")
    if au is None:
        au = spec["audio"] = {}
    insts = set(INSTRUMENTS) | set((au.get("instruments") or {}).keys())
    for k, r in (au.get("instruments") or {}).items():
        _check_recipe(r, "audio.instruments.%s" % k, errs)
    table, n = {}, [0]

    def mus(v, where):
        n[0] += 1
        return _music(v, where, base, insts, errs, table, n[0])
    au["_musicKey"] = mus(au.get("music"), "audio.music")
    for ci, ch in enumerate(spec.get("chapters") or []):
        if "music" in ch:
            ch["_music"] = mus(ch["music"], "第 %d 章の music" % (ci + 1))
        for si, sc in enumerate(ch.get("scenes") or []):   # 場面の頭で曲を替える（その章の終わりまで続く）
            if "music" in sc:
                sc["_music"] = mus(sc["music"], "第 %d 章の場面 %d の music" % (ci + 1, si + 1))
        if "energy" in ch and ch["energy"] not in (1, 2, 3):
            errs.append("第 %d 章の energy は 1・2・3 のいずれか" % (ci + 1))
    table.pop("_files", None)
    au["_music"] = table
    # 楽器の音: 録音の音（samples.py）に差し替えられる楽器は、使う音域だけ埋め込む（audio.samples: false で合成の音のまま）
    au.pop("_samples", None)
    if au.get("samples", True) is not False and table:
        import samples as _smp
        w = []
        au["_samples"] = _smp.build(table, custom=set((au.get("instruments") or {}).keys()), warn=w)
        for x in w:
            print("warn:", x, file=sys.stderr)
        if au["_samples"]:
            cr = spec.setdefault("_credits", [])
            if _smp.CREDIT not in cr:
                cr.append(_smp.CREDIT)
    # 効果音
    sfx = au.get("sfx", True)
    defs = dict(SFX)
    for k, r in (au.get("sfxDefs") or {}).items():
        where = "audio.sfxDefs.%s" % k
        if r.get("file"):
            p = os.path.join(base, r["file"])
            if not os.path.isfile(p):
                errs.append("%s: ファイルが見つかりません: %s" % (where, p))
                continue
            defs[k] = {"file": _data_uri(p), "v": r.get("v", 1)}
        elif r.get("code") or r.get("src"):
            defs[k] = {"code": _read_code(r, base, where, errs)}
        else:
            _check_recipe(r, where, errs)
            defs[k] = r
    au["_sfx"] = {k: {x: y for x, y in r.items() if x not in ("cat", "name", "desc")} for k, r in defs.items()}
    if sfx is False:
        # 効果音を使わないときは音色の表を埋め込まない（全部で約 40 KB。動画・文書の図ごとに入っていた）
        au["_sfx"] = {}
        au["_sfxcfg"] = None
        return errs
    cfg = {} if sfx is True else dict(sfx)
    # 効果音の組の既定は、動きの性格（台本の motion）に合わせる
    kit = cfg.get("kit", {"tech": "digital", "playful": "playful", "cinematic": "cinematic"}.get(spec.get("motion"), "standard"))
    if kit not in KITS:
        errs.append("audio.sfx.kit %r は %s のいずれか" % (kit, "/".join(KITS)))
        kit = "standard"
    if cfg.get("density", "normal") not in DENSITY:
        errs.append("audio.sfx.density は low / normal / high のいずれか")
    kmap = KITS[kit][2]
    merged = {}
    for ev in EVENTS:
        if ev in kmap:
            merged[ev] = kmap[ev]
        elif "**" in kmap:
            merged[ev] = None
        else:
            merged[ev] = KITS["standard"][2].get(ev)
    for ev, v in (cfg.get("map") or {}).items():
        if ev not in EVENTS:
            errs.append("audio.sfx.map の %r は出来事の一覧（--list-sounds）に無い" % ev)
            continue
        merged[ev] = [v, 1] if isinstance(v, str) else v
    kitout = {}
    for ev, v in merged.items():
        if not v:
            continue
        if v[0] not in defs:
            errs.append("効果音 %r（出来事 %s）は無い（--list-sounds）" % (v[0], ev))
            continue
        kitout[ev] = [v[0], v[1] if len(v) > 1 else 1, v[2] if len(v) > 2 else 0, EVENTS[ev][1]]
    # 場面ごとの sfx
    for ci, ch in enumerate(spec.get("chapters") or []):
        for si, s in enumerate(ch.get("scenes") or []):
            ss = s.get("sfx")
            if ss is None or ss is False:
                continue
            where = "第 %d 章の場面 %d の sfx" % (ci + 1, si + 1)
            adds = ss if isinstance(ss, list) else ss.get("add", [])
            for a in adds:
                if a.get("name") and a["name"] not in defs:
                    errs.append("%s: 効果音 %r は無い" % (where, a["name"]))
                if a.get("event") and a["event"] not in EVENTS:
                    errs.append("%s: 出来事 %r は無い" % (where, a["event"]))
                if not a.get("name") and not a.get("event"):
                    errs.append("%s: 足す音には name（効果音）か event（出来事）が必要です" % where)
            if isinstance(ss, dict):
                for ev, v in (ss.get("map") or {}).items():
                    if ev not in EVENTS:
                        errs.append("%s: map の出来事 %r は無い" % (where, ev))
                    elif v and (v if isinstance(v, str) else v[0]) not in defs:
                        errs.append("%s: map の効果音 %r は無い" % (where, v))
    au["_sfxcfg"] = {"kit": kitout, "density": DENSITY.get(cfg.get("density", "normal"), 2), "volume": cfg.get("volume", 1)}
    return errs


def music_label(v):
    if isinstance(v, str):
        return "%s（%s）" % (v, MUSIC[v]["name"]) if v in MUSIC else v
    if isinstance(v, dict):
        return "ファイル" if v.get("file") else "%s を元に変更" % v["preset"] if v.get("preset") else "自作（code）" if (v.get("code") or v.get("src")) else "自作"
    return "なし"


def print_sounds():
    print("# 曲（audio.music / 章の music）— 名前か {\"preset\": 名前, 上書き…}。全 %d 曲" % len(MUSIC))
    for cat in MUSIC_CATS:
        print("\n  [%s]" % cat)
        for k, d in MUSIC.items():
            if d["cat"] == cat:
                print("  %-12s %-10s %3d BPM %-3s %-10s %s" % (k, d["name"], d["bpm"], d["key"], d["scale"], d["desc"]))
    print("\n# 効果音（sfx の name・sfx.map の値）— 全 %d 種" % len(SFX))
    for cat in SFX_CATS:
        items = ["%s（%s）" % (k, d["name"]) for k, d in SFX.items() if d["cat"] == cat]
        print("\n  [%s] %s" % (cat, "　".join(items)))
    print("\n# 効果音の組（audio.sfx.kit）")
    for k, (n, desc, _) in KITS.items():
        print("  %-10s %-6s %s" % (k, n, desc))
    print("\n# 出来事（audio.sfx.map のキー・sfx の event）— 段階: 1 は density=low でも鳴る、3 は high だけ")
    for k, (desc, lv) in EVENTS.items():
        print("  %-10s %d  %s" % (k, lv, desc))
    print("\n# 自作の曲（layers の inst・pat、drum）")
    print("  楽器: " + " ".join(INSTRUMENTS))
    print("  型:")
    for k, d in PATTERNS.items():
        print("    %-10s %s" % (k, d))
    print("  打楽器の型（drum）: " + " ".join(DRUMS))
    print("  音階（scale）: " + " ".join(SCALES) + "　調（key）: C〜B（# と b も可）")
    print("\n" + AUDIO_DOC)


AUDIO_DOC = """# audio の書き方
"audio": {
  "narration": true, "rate": 1.1, "wait": true, "pronounce": {…},
  "music": "corporate",                      曲の名前（none で無し）
  "music": {"preset": "corporate", "bpm": 92, "key": "E"},   名前を元に一部を変える
  "music": {"file": "bgm.mp3", "volume": .35, "loop": true}, 音声ファイル（埋め込む。volume の既定 .35）
  "music": {"bpm": 96, "key": "D", "scale": "dorian", "prog": [["1","4","5","1"]],
            "layers": [{"inst":"keys","pat":"broken8","oct":4,"v":.7}, {"inst":"bass","pat":"root4","oct":2,"e":2}],
            "drum": "backbeat", "swing": .2, "g": .35},   自作（層は e=この盛り上がりから鳴る。g は音量）
            drum は型の名前か {"kick": "X...x...", "hat": "x.x.xrx."}（x 打つ X 強く g 弱く r 2 連打 t 3 連打）
  "music": {"bpm": 90, "src": "music.js"},   JS で作曲（本体 (bar, M) → [{at 拍, len 拍, n MIDI, inst, v} | {at, drum, v}]）
  "musicVolume": 1, "duck": .5,              音楽の音量・読み上げ中に下げる割合
  "energy": [1, 2, 2, 3, 1],                 章ごとの盛り上がり 1..3（既定: 最初と最後は 1、最後の手前は 3、ほかは 2）
  "sfx": {"kit": "standard", "density": "normal", "volume": 1, "map": {"appear": "bubble", "hit": null}},
  "sfxDefs": {"myhit": {"l": [{"w":"sine","f":[180,60],"d":.4,"v":.8}]}, "logo": {"file": "logo.wav"}, "mine": {"src": "sfx.js"}},
  "instruments": {"myvox": {"l": [{"w":"sawtooth","sus":1,"a":.1,"d":.3,"v":.08,"flt":["bandpass",900,4]}]}}
}
章に "music": "…"（その章だけ別の曲）・"energy": 1..3。
場面に "sfx": false（自動の効果音を止める）・[{"at": 0.5, "name": "ding"}, {"at": 0.2, "event": "appear"}]・
  {"auto": false, "map": {"appear": "bubble"}, "add": [...]}。at は場面の進み 0..1（"ms" なら場面の中の ms）。
custom の中で H.sfx(ms, "名前か出来事", {v, pitch}) — 場面の最初に一度集めるので、条件の外で呼ぶ。
自作の効果音の JS（sfxDefs の src）は本体 (ac, out, when, A)。ac は AudioContext、out に繋ぐ、when に鳴らす。A は audio.js の道具。"""
