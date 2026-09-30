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
    "kick": "バスドラム", "snare": "スネア", "clap": "クラップ", "hat": "ハイハット", "ohat": "オープンハイハット", "ride": "ライド",
    "rim": "リム", "tom": "タム", "taiko": "太鼓", "shaker": "シェイカー", "crash": "クラッシュ", "tick": "時計の刻み",
    "brush": "ブラシ", "timpani": "ティンパニ", "chipnoise": "8bit の雑音", "chipkick": "8bit のキック",
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
}
DRUMS = ["pulse", "soft", "four", "house", "backbeat", "rock", "halftime", "lofi", "breaks", "dnb", "trap", "funk", "bossa", "brush",
         "reggae", "march", "taiko", "matsuri", "cinematic", "tick", "clock", "heart", "shaker", "ostinato", "chip", "waltz", "sixeight"]
SCALES = ["major", "minor", "dorian", "phrygian", "lydian", "mixolydian", "harmonic", "pentamaj", "pentamin", "blues",
          "yo", "in", "ryukyu", "hirajoshi", "whole"]
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
    # ── レトロ・ゲーム
    "chiptune": M("レトロ・ゲーム", "8bit", "8bit の旋律と分散。ゲーム・レトロ", 140, "C", "major", [["1", "6", "4", "5"]],
                  [L("chip", "melody", 5, .5, dens=.6), L("chipsq", "arp16", 4, .3), L("chiptri", "root8", 2, .8)], drum="chip"),
    "arcade": M("レトロ・ゲーム", "アーケード", "短調の速い 8bit。対戦・競争", 150, "A", "minor", [["1", "6", "7", "1"]],
                [L("chip", "melody", 5, .45, dens=.7), L("chipsq", "off", 4, .3), L("chiptri", "oct8", 2, .8)], drum="chip"),
    "puzzle": M("レトロ・ゲーム", "パズル", "マリンバの旋律とピチカート。考える・解く", 110, "F", "major", [["1", "2", "5", "1"]],
                [L("marimba", "melody", 5, .5, dens=.5), L("pizz", "off", 4, .45), L("bass", "fifth", 2, .5)], drum="clock", dv=.6),
    "rpg": M("レトロ・ゲーム", "冒険の旅", "笛とハープと行進。手順・旅の案内", 104, "D", "dorian", [["1", "7", "6", "7"]],
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
}
# 曲の音量の揃え（--sounds のページで合成した盛り上がり 3 の大きさから求めた倍率。ナレーションの後ろで流す大きさ。曲を足したら測り直す）
MUSIC_GAIN = {"calm": 0.289, "deep": 0.34, "drift": 0.409, "dawn": 0.312, "mist": 0.39, "ocean": 0.354, "space": 0.259, "rain": 0.304, "forest": 0.462, "bright": 0.411, "corporate": 0.499, "innovate": 0.38, "trust": 0.497, "growth": 0.509, "clean": 0.55, "keynote": 0.413, "launch": 0.382, "pitch": 0.376, "startup": 0.486, "tech": 0.484, "circuit": 0.459, "data": 0.34, "cyber": 0.455, "synthwave": 0.488, "neon": 0.398, "hacker": 0.317, "ai": 0.413, "quantum": 0.323, "robot": 0.49, "pop": 0.386, "happy": 0.434, "sunny": 0.499, "kids": 0.456, "summer": 0.526, "disco": 0.375, "idol": 0.334, "lofi": 0.413, "study": 0.539, "jazz": 0.406, "bossa": 0.397, "night": 0.433, "cafe": 0.589, "soul": 0.422, "epic": 0.302, "hero": 0.418, "tension": 0.367, "mystery": 0.376, "sad": 0.412, "hope": 0.519, "wonder": 0.824, "trailer": 0.299, "documentary": 0.552, "adventure": 0.507, "memory": 0.54, "suspense": 0.326, "wa": 0.509, "matsuri": 0.251, "kyoto": 1.157, "ryukyu": 0.605, "zen": 0.344, "celtic": 0.331, "orient": 0.703, "desert": 0.336, "island": 0.626, "chiptune": 0.605, "arcade": 0.798, "puzzle": 0.863, "rpg": 0.568, "waltz": 0.471, "baroque": 1.746, "piano": 1.529, "strings": 0.629, "chamber": 1.308, "musicbox": 2.889, "drive": 0.469, "sport": 0.388, "rock": 0.142, "funk": 0.299, "house": 0.38, "countdown": 0.529, "pulse": 0.419, "hype": 0.372, "minimal": 0.877, "clock": 1.988, "glass": 0.673, "steps": 0.613}
for _k, _g in MUSIC_GAIN.items():
    MUSIC[_k]["g"] = _g
MUSIC_CATS = ["落ち着き", "企業・製品", "技術", "ポップ", "ジャズ・ローファイ", "物語・映画", "和・民族", "レトロ・ゲーム", "クラシック風", "エネルギー", "ミニマル"]


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
}
# 効果音の音量の揃え（--sounds のページで合成した山の高さから求めた倍率。効果音を足したら測り直す）
SFX_GAIN = {"click": 0.81, "pop": 0.92, "pop-soft": 1.09, "blip": 2.2, "tick": 2.08, "toggle": 2.2, "select": 1.45, "confirm": 1.47, "back": 1.53, "hover": 3, "key": 2.2, "key-soft": 3, "typewriter": 0.84, "carriage": 1.54, "send": 1.44, "receive": 1.46, "message": 1.47, "delete": 1.37, "nav": 1.68, "switch": 3, "whoosh": 2.16, "whoosh-long": 1.98, "whoosh-short": 1.78, "swoosh-down": 1.85, "swipe": 3, "air": 3, "zoom-in": 1.9, "zoom-out": 1.89, "riser": 1.9, "downer": 2.2, "reverse": 1.87, "shutter": 1.25, "glitch": 1.46, "cut": 0.67, "impact": 0.5, "boom": 0.53, "subdrop": 0.64, "slide": 2.78, "page": 1.7, "curtain": 3, "flip": 1.75, "ding": 1.36, "chime": 1.38, "bell": 1.18, "rin": 1.14, "sparkle": 2.5, "shimmer": 3, "twinkle": 2.62, "magic": 2.55, "bling": 2.06, "success": 1.52, "fanfare": 2.2, "orchestra": 1.6, "stamp": 0.64, "reveal": 1.68, "ping": 2.01, "underline": 3, "applause": 3, "notify": 1.55, "notify-soft": 1.43, "alert": 2.2, "error": 2.2, "buzzer": 1.58, "alarm": 2.2, "siren": 2.2, "warning": 1.76, "done": 1.79, "ok": 1.68, "question": 1.74, "count": 2.2, "counter": 3, "scan": 3, "beep": 2.78, "radar": 2.28, "sonar": 1.26, "data": 2.2, "compute": 2.2, "process": 3, "charge": 2.2, "powerup": 1.19, "powerdown": 1.66, "connect": 1.46, "disconnect": 2.1, "graph-rise": 3, "bubble": 1.46, "drop": 1.11, "water": 2.02, "knock": 0.75, "paper": 2.81, "pencil": 3, "clock-tick": 3, "heartbeat": 0.7, "footstep": 2.94, "wind": 3, "snap": 1.54, "clink": 2.29, "hyoshigi": 0.78, "coin": 2.2, "jump": 2.2, "powerup8": 2.2, "levelup": 1.25, "laser": 2.2, "zap": 2.2, "oneup": 2.2, "select8": 2.2, "win": 2.2, "drumroll": 1.92, "cymbal": 2.02, "taiko-hit": 0.55, "kalimba-hit": 1.48, "piano-chord": 1.17, "harp-gliss": 2.03, "pizz": 1.48, "clap1": 3, "woodblock": 0.87, "triangle": 2.58}
for _k, _g in SFX_GAIN.items():
    SFX[_k]["g"] = _g
SFX_CATS = ["操作", "転換", "強調", "通知", "数値", "自然・もの", "ゲーム", "楽器"]

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
    if d.get("drum") and d["drum"] not in DRUMS:
        errs.append("%s: drum %r は %s のいずれか" % (where, d["drum"], "/".join(DRUMS)))
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
        if "energy" in ch and ch["energy"] not in (1, 2, 3):
            errs.append("第 %d 章の energy は 1・2・3 のいずれか" % (ci + 1))
    au["_music"] = table
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
