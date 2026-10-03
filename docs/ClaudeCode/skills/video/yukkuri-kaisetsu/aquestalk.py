#!/usr/bin/env python3
"""ゆっくりボイス（AquesTalk1。霊夢 = 女性 1（f1）、魔理沙 = 女性 2（f2）が定番）で、せりふの WAV を作る。

  python3 aquestalk.py --check                         # ライブラリと鍵が見つかるか、どの声があるか
  python3 aquestalk.py "ゆっくりしていってね" -o out.wav   # 試しに 1 つ作る（--voice f2・--speed 110）

AquesTalk1 のライブラリは同梱していない（再配布できない）。株式会社アクエストのサイトから自分で入手して置く:

  1. https://www.a-quest.com/download.html の「AquesTalk1 Linux」を、ブラウザでダウンロードする（人の操作の確認があり、自動では取れない）
  2. 展開して、このスキルの aquestalk/ に置く（aquestalk/lib64/f1/libAquesTalk.so の形。場所を変えるなら環境変数 AQUESTALK_DIR）
  3. 開発ライセンスキーを aquestalk/dev_key.txt に書く（か、環境変数 AQUESTALK_DEV_KEY）。
     無いと評価版として動き、ナ行・マ行がすべて「ヌ」になる（評価の目的にだけ使える）。
     個人・非営利の開発ライセンスは、アクエストのオンラインストアで発行手数料 1,980 円。
  4. 動画を収益化するなら、使用ライセンス（商用コンテンツ向け・年 6,380 円）も要る。鍵は aquestalk/usr_key.txt（か AQUESTALK_USR_KEY）

お金をかけない道: Windows のアプリ AquesTalkPlayer（個人・非営利は無償。評価版の制限が無い）を、Wine で動かして WAV を作る。
  1. https://www.a-quest.com/products/aquestalkplayer.html の Win 版を、ブラウザでダウンロードして aquestalk/aquestalkplayer/ に展開する
  2. Wine を用意する（apt の wine か、管理者権限が無ければ展開するだけで動く版を ~/.local/share/yukkuri-wine/ に置く。場所は環境変数 AQUESTALK_WINE でも指定できる）
  開発ライセンスキーがあればライブラリを、無ければ AquesTalkPlayer を使う。どちらも無ければ評価版のライブラリ（「ヌ」になる）。

AquesTalk1 は、かなの音声記号列から声を作る。漢字の文をかなに直すのには、VOICEVOX の読み（/audio_query の kana）を使う
（アクエストの AqKanji2Koe は使わない）。なので VOICEVOX も動いている必要がある。出る音は 8kHz・16 ビット・モノラルの WAV。
"""
import argparse, ctypes, glob, hashlib, json, os, re, shutil, subprocess, sys, tempfile, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.realpath(__file__))
VOICES = ["f1", "f2", "f3", "m1", "m2", "r1", "dvd", "imd1", "jgr"]   # AquesTalk1 の声種の名前（一般に知られているもの。--check は、実際に置いてあるものだけを出す）


def home():
    return os.environ.get("AQUESTALK_DIR") or os.path.join(HERE, "aquestalk")


def lib_path(voice):
    """その声種の libAquesTalk.so。パッケージをそのまま置いても、lib64 の中身だけ置いても見つける。"""
    for base in (home(), os.path.join(home(), "aqtk1_lnx"), *[os.path.join(home(), d) for d in (os.listdir(home()) if os.path.isdir(home()) else [])]):
        for sub in ("lib64", "lib", ""):
            p = os.path.join(base, sub, voice, "libAquesTalk.so")
            if os.path.isfile(p):
                return p
    return None


def key(name):
    v = os.environ.get("AQUESTALK_%s_KEY" % name.upper())
    f = os.path.join(home(), "%s_key.txt" % name)
    return v or (open(f, encoding="utf-8").read().strip() if os.path.isfile(f) else "")


def player_exe():
    """AquesTalkPlayer.exe（aquestalk/ の下のどこかに展開してあるもの）。"""
    hits = glob.glob(os.path.join(home(), "**", "AquesTalkPlayer.exe"), recursive=True) if os.path.isdir(home()) else []
    return hits[0] if hits else None


def wine_bin():
    """Wine の実行ファイル。環境変数 AQUESTALK_WINE、PATH の wine、~/.local/share/yukkuri-wine/ に展開した版 の順に探す。"""
    w = os.environ.get("AQUESTALK_WINE") or shutil.which("wine")
    if w and os.path.isfile(w):
        return w
    hits = sorted(glob.glob(os.path.expanduser("~/.local/share/yukkuri-wine/*/bin/wine")))
    return hits[-1] if hits else None


def backend(voice="f1"):
    """声の作り方: "lib"（鍵つきのライブラリ）・"player"（Wine の AquesTalkPlayer）・"eval"（評価版のライブラリ。ナ行・マ行が「ヌ」）・None。"""
    if lib_path(voice) and key("dev"):
        return "lib"
    if player_exe() and wine_bin():
        return "player"
    return "eval" if lib_path(voice) else None


def to_koe(kana):
    """VOICEVOX の読み（カタカナ。' はアクセント、/ と 、 は区切り、_ は無声化、？ は問い）を、AquesTalk1 の音声記号列（ひらがな）に直す。"""
    s = kana.replace("_", "")
    s = "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)
    s = s.replace("ゔ", "ヴ")
    s = re.sub(r"？(?=.)", "？、", s).replace("、、", "、")
    return s if s.endswith(("。", "？")) else s + "。"


class AquesTalk:
    def __init__(self, vv_url="http://127.0.0.1:50021"):
        self.url, self.libs, self.made, self.warned, self.sid, self.served = vv_url.rstrip("/"), {}, 0, False, None, False

    def available(self, voice="f1"):
        return bool(lib_path(voice))

    def lib(self, voice):
        if voice not in self.libs:
            p = lib_path(voice)
            if not p:
                sys.exit("error: AquesTalk1 の声種 %s のライブラリがありません（%s）。入手と置き方は aquestalk.py の先頭の説明" % (voice, home()))
            L = ctypes.CDLL(p)
            L.AquesTalk_Synthe_Utf8.restype = ctypes.c_void_p
            L.AquesTalk_Synthe_Utf8.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
            L.AquesTalk_FreeWave.argtypes = [ctypes.c_void_p]
            dev, usr = key("dev"), key("usr")
            if dev:
                if L.AquesTalk_SetDevKey(dev.encode("ascii")) != 0:
                    print("warn: AquesTalk の開発ライセンスキーが正しくありません（評価版として動きます）", file=sys.stderr)
            elif not self.warned:
                print("warn: AquesTalk は評価版として動いています（開発ライセンスキーが無い）。ナ行・マ行が「ヌ」になります。評価の目的にだけ使えます", file=sys.stderr)
                self.warned = True
            if usr and L.AquesTalk_SetUsrKey(usr.encode("ascii")) != 0:
                print("warn: AquesTalk の使用ライセンスキーが正しくありません", file=sys.stderr)
            self.libs[voice] = L
        return self.libs[voice]

    def kana(self, text):
        """漢字の文の読み（VOICEVOX に聞く）。"""
        try:
            if self.sid is None:
                sp = json.loads(urllib.request.urlopen(self.url + "/speakers", timeout=10).read())
                self.sid = sp[0]["styles"][0]["id"]
            req = urllib.request.Request(self.url + "/audio_query?" + urllib.parse.urlencode({"text": text, "speaker": self.sid}), data=b"", method="POST")
            return json.loads(urllib.request.urlopen(req, timeout=30).read())["kana"]
        except OSError as e:
            sys.exit("error: 読みを作るのに VOICEVOX が要ります（%s につながりません: %s）" % (self.url, e))

    def preset(self, voice, speed):
        """AquesTalkPlayer のプリセット（声種と話速。抑揚をつけない「棒読み」= ゆっくりの話し方）。無ければプリセットの一覧に足す。"""
        name, f = "kaisetsu_%s_%d" % (voice, speed), os.path.join(os.path.dirname(player_exe()), "AquesTalkPlayer.preset")
        text = open(f, encoding="cp932").read() if os.path.isfile(f) else ""
        if '"%s"' % name not in text:
            open(f, "a", encoding="cp932", newline="").write(('' if text.endswith("\n") or not text else "\r\n") + '"%s","true","AquesTalk1","%s",%d,100,100,100,100,100,"yukkuri-kaisetsu"\r\n' % (name, voice, speed))
        return name

    def player(self, text, voice, speed, path):
        """AquesTalkPlayer を Wine で動かして、text を WAV（path）にする。漢字の読みは AquesTalkPlayer がする。"""
        exe, wine = player_exe(), wine_bin()
        env = dict(os.environ, WINEDEBUG="-all", LC_ALL="ja_JP.UTF-8")
        pre = os.path.expanduser("~/.local/share/yukkuri-wine/prefix")
        if "WINEPREFIX" not in env and os.path.isdir(pre):
            env["WINEPREFIX"] = pre
        srv = os.path.join(os.path.dirname(wine), "wineserver")
        if not self.served and os.path.isfile(srv):   # Wine の土台を 60 秒は動かしたままにする（せりふごとの起動が速くなる）
            subprocess.run([srv, "-p60"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.served = True
        win = lambda p: "Z:" + os.path.abspath(p).replace("/", "\\")
        clean = text.replace("〜", "ー").replace("～", "ー").encode("cp932", "ignore").decode("cp932").strip()
        with tempfile.NamedTemporaryFile("w", suffix=".txt", encoding="cp932", delete=False) as t:
            t.write(clean + "\r\n")
        try:
            r = subprocess.run([wine, exe, "/F", win(t.name), "/P", self.preset(voice, speed), "/W", win(path)], cwd=os.path.dirname(exe), env=env,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90)   # 出力は受け取らない（Wine の土台が動いたままだと、受け口が閉じず待ち続ける）
        finally:
            os.unlink(t.name)
        if not os.path.isfile(path) or os.path.getsize(path) < 100:
            sys.exit("error: AquesTalkPlayer が声を作れませんでした（%s。終了コード %s）%s" % (clean, r.returncode, "。画面（DISPLAY）が無いと動きません" if not os.environ.get("DISPLAY") else ""))

    def synth(self, text, v, outdir):
        """text を v（{voice: f1, aq_speed: 100}）の声で WAV にし、パスを返す（同じ文・同じ声は作り直さない）。"""
        voice, speed = v.get("voice", "f1"), int(max(50, min(300, v.get("aq_speed", 100))))
        if backend(voice) == "player":
            os.makedirs(outdir, exist_ok=True)
            path = os.path.join(outdir, "aq_%s.wav" % hashlib.sha1(json.dumps([voice, text, speed, "player"], ensure_ascii=False).encode("utf-8")).hexdigest()[:16])
            if not os.path.isfile(path):
                self.player(text, voice, speed, path)
                self.made += 1
            return path
        koe = to_koe(self.kana(text))
        os.makedirs(outdir, exist_ok=True)
        path = os.path.join(outdir, "aq_%s.wav" % hashlib.sha1(json.dumps([voice, koe, speed, bool(key("dev"))], ensure_ascii=False).encode("utf-8")).hexdigest()[:16])
        if os.path.isfile(path):
            return path
        L, size = self.lib(voice), ctypes.c_int(0)
        ptr = L.AquesTalk_Synthe_Utf8(koe.encode("utf-8"), speed, ctypes.byref(size))
        if not ptr and size.value == 105:   # 読めない記号があった: アクセントの印を外してもう一度
            ptr = L.AquesTalk_Synthe_Utf8(koe.replace("'", "").encode("utf-8"), speed, ctypes.byref(size))
        if not ptr:
            sys.exit("error: AquesTalk が声を作れませんでした（エラー %d）。音声記号列: %s" % (size.value, koe))
        open(path, "wb").write(ctypes.string_at(ptr, size.value))
        L.AquesTalk_FreeWave(ptr)
        self.made += 1
        return path


def main():
    ap = argparse.ArgumentParser(description="ゆっくりボイス（AquesTalk1）で WAV を作る")
    ap.add_argument("text", nargs="?")
    ap.add_argument("-o", "--out", default="aquestalk_test.wav")
    ap.add_argument("--voice", default="f1")
    ap.add_argument("--speed", type=int, default=100)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--voicevox-url", default="http://127.0.0.1:50021")
    a = ap.parse_args()
    if a.check or not a.text:
        have = [v for v in VOICES if lib_path(v)]
        print("置き場所: %s" % home())
        print("声種: %s" % ("・".join(have) if have else "ライブラリがありません（入手と置き方は、このファイルの先頭の説明）"))
        win = [os.path.join(r, f) for r, _, fs in os.walk(home()) for f in fs if f.lower() == "aquestalk.dll"] if os.path.isdir(home()) else []
        if win and not have:
            print("  Windows 版の DLL が %d 個あります（%s など）。Linux では読み込めません。「AquesTalk1 Linux」（libAquesTalk.so）が要ります" % (len(win), os.path.relpath(win[0], home())))
        print("開発ライセンスキー: %s" % ("あり" if key("dev") else "なし（ライブラリは評価版として動く。ナ行・マ行が「ヌ」になる）"))
        print("AquesTalkPlayer: %s" % (player_exe() or "なし"))
        print("Wine: %s" % (wine_bin() or "なし"))
        print("→ 使う方法: %s" % {"lib": "ライブラリ（鍵つき）", "player": "AquesTalkPlayer を Wine で動かす（個人・非営利は無償。制限なし）", "eval": "評価版のライブラリ（「ヌ」になる）", None: "なし（ブラウザの読み上げで代わる）"}[backend()])
        print("使用ライセンスキー: %s" % ("あり" if key("usr") else "なし（個人・非営利なら不要。収益化するなら要る）"))
        return
    aq = AquesTalk(a.voicevox_url)
    p = aq.synth(a.text, {"voice": a.voice, "aq_speed": a.speed}, os.path.dirname(os.path.abspath(a.out)))
    os.replace(p, a.out)
    print("OK : %s（%s）" % (a.out, "AquesTalkPlayer" if backend(a.voice) == "player" else "音声記号列: " + to_koe(aq.kana(a.text))))


if __name__ == "__main__":
    main()
