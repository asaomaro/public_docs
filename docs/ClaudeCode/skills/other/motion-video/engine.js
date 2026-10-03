/* motion-video engine — 台本（SPEC）から、時刻だけで決まる映像を Canvas に描き、プレイヤーを動かす。
 * build.py が SPEC（durations 計算済み）・THEME・このファイルを 1 つの HTML に埋め込む。
 * 描画は draw(t) の純粋な関数（t = 動画の先頭からの ms）。シーク・倍速・巻き戻しでも同じ画になる。 */
window.MotionVideo = window.MotionVideo || function (root, SPEC, TH) {
  "use strict";
  var W = 1920, H = 1080;
  /* 要素はこのプレイヤーの中から data-mv で探す（1 ページに複数のプレイヤーを置けるように） */
  var $ = function (id) { return root.querySelector('[data-mv="' + id.replace(/^mv-/, "") + '"]'); };

  /* ================= 時間割 ================= */
  var SCENES = [], CHAPTERS = [], CUES = [], DUR = 0, SCOF = typeof WeakMap === "function" ? new WeakMap() : null;
  SPEC.chapters.forEach(function (ch, ci) {
    CHAPTERS.push({ t: DUR, name: ch.title, desc: ch.desc || "", i: ci });
    ch.scenes.forEach(function (s) {
      var d = s._dur, sc = { s: s, t0: DUR, d: d, ci: ci, cues: [] }, p = s._plan;
      SCENES.push(sc); if (SCOF) SCOF.set(s, sc);
      (s._cues || []).forEach(function (c, j) {
        /* 前もって作ったナレーションの声は s._voices（c[3] が ""）、掛け合いのせりふは s.lines */
        var ln = c[3] === "" && s._voices ? s._voices[c[4]] || null : c[3] !== undefined && s.lines ? s.lines[c[4]] || {} : null;
        /* 1 文の声が字幕 2 つ以上にまたがるとき、2 つ目からは { cont: 文の頭の字幕 } で、声を新しく鳴らさず前の声の続きとする */
        var par = ln && ln.cont !== undefined && c[3] === "" ? CUES[sc.cues[ln.cont]] : null;
        sc.cues.push(CUES.length);
        CUES.push({ a: DUR + c[0], b: DUR + c[1], text: c[2], who: c[3] || null, line: par ? par.line : ln, key: par ? par.key : ln ? SCENES.length + ":" + c[4] : null, par: par,
                    est: p ? (p.L ? (p.L[j] || [0])[0] : (p.e || [])[j] || 0) : 0 }); });
      DUR += d;
    });
  });
  function chapterAt(t) { var i = 0; for (var k = 0; k < CHAPTERS.length; k++) if (t >= CHAPTERS[k].t) i = k; return i; }
  function chLen(i) { return (i < CHAPTERS.length - 1 ? CHAPTERS[i + 1].t : DUR) - CHAPTERS[i].t; }
  function sceneAt(t) { var i = 0; for (var k = 0; k < SCENES.length; k++) if (t >= SCENES[k].t0) i = k; return i; }

  /* ================= 描画の道具 ================= */
  var cv = $("mv-canvas"), ctx = cv.getContext("2d");
  var C = TH.canvas, F = TH.fonts;
  var clamp = function (v, a, b) { a = a === undefined ? 0 : a; b = b === undefined ? 1 : b; return Math.max(a, Math.min(b, v)); };
  var lin = function (x, a, b) { return clamp((x - a) / (b - a)); };
  var eo = function (x) { return 1 - Math.pow(1 - x, 3); };
  var eio = function (x) { return x < .5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; };
  var back = function (x) { var c1 = 1.5, c3 = c1 + 1; return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2); };
  /* 緩急（ease）と現れる順（order）は場面ごとに差し替える（drawScene・collectEvents が設定する） */
  var EASES = { smooth: eo, spring: function (x) { return x >= 1 ? 1 : 1 - Math.cos(x * Math.PI * 2.5) * Math.exp(-6 * x); },
                snappy: function (x) { return 1 - Math.pow(1 - x, 5); },
                bouncy: function (x) { var n = 7.5625, d1 = 2.75; if (x < 1 / d1) return n * x * x; if (x < 2 / d1) return n * (x -= 1.5 / d1) * x + .75; if (x < 2.5 / d1) return n * (x -= 2.25 / d1) * x + .9375; return n * (x -= 2.625 / d1) * x + .984375; },
                elastic: function (x) { return x <= 0 ? 0 : x >= 1 ? 1 : Math.pow(2, -10 * x) * Math.sin((x * 10 - .75) * (2 * Math.PI / 3)) + 1; },
                calm: function (x) { return -(Math.cos(Math.PI * x) - 1) / 2; } };
  var CUR_EASE = eo, CUR_ORDER = "", CUR_CUES = null, CUR_CUEE = null, CUR_SYNC = "auto";
  var linear = function (v) { return v; };
  // H.lin は (x, a, b) の形なので、緩急として渡されたら等速として扱う（そのまま呼ぶと NaN で何も描かれない）
  var P = function (x, a, b, e) { return (e === lin ? linear : e || CUR_EASE)(lin(x, a, b)); };
  var mix = function (a, b, k) { return a + (b - a) * k; };
  function rr(x, y, w, h, r) {
    r = Math.max(0, Math.min(r, w / 2, h / 2));
    ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
  }
  function font(o) { return (o.weight || 400) + " " + (o.size || 30) + "px " + (o.font || F.sans); }
  function txt(s, x, y, o) {
    o = o || {}; ctx.save(); ctx.font = font(o); ctx.fillStyle = o.color || C.ink;
    ctx.textAlign = o.align || "left"; ctx.textBaseline = o.base || "alphabetic";
    if (o.alpha !== undefined) ctx.globalAlpha *= o.alpha;
    if (o.spacing && "letterSpacing" in ctx) ctx.letterSpacing = o.spacing + "px";
    if (o.stroke) { ctx.lineJoin = "round"; ctx.lineWidth = o.strokeWidth || Math.max(4, (o.size || 24) * .22); ctx.strokeStyle = o.stroke; ctx.strokeText(s, x, y); }   /* stroke: 縁取りの色（明るい背景の上の字に） */
    ctx.fillText(s, x, y); ctx.restore();
  }
  function tw(s, o) { ctx.save(); ctx.font = font(o || {}); var w = ctx.measureText(s).width; ctx.restore(); return w; }
  /* 日本語を含む折り返し（行頭禁則の簡易版） */
  var NOSTART = "、。，．・：；？！）」』】〉》ー々ぁぃぅぇぉっゃゅょァィゥェォッャュョ";
  function wrap(s, maxW, o) {
    var out = [], cur = "";
    var tokens = String(s).match(/[A-Za-z0-9_\-./:@#%&+=~`'"(){}\[\]<>$*]+|\s+|./g) || [];
    tokens.forEach(function (tok) {
      var t2 = cur + tok;
      if (tw(t2.replace(/\*\*/g, ""), o) <= maxW || !cur) { cur = t2; return; }
      if (NOSTART.indexOf(tok[0]) >= 0) { cur = t2; return; }
      out.push(cur.replace(/\s+$/, "")); cur = tok.replace(/^\s+/, "");
    });
    if (cur) out.push(cur);
    return out;
  }
  /* **強調** を含む 1 行を描く（強調は accent の色と下線の伸び） */
  function rich(line, x, y, o, emK) {
    var parts = String(line).split("**"), cx = x, total = tw(line.replace(/\*\*/g, ""), o);
    if (o.align === "center") cx = x - total / 2; else if (o.align === "right") cx = x - total;
    parts.forEach(function (p, i) {
      if (!p) return;
      var em = i % 2 === 1, w = tw(p, o);
      txt(p, cx, y, { size: o.size, weight: em ? Math.max(700, o.weight || 400) : o.weight, font: o.font, color: em ? (o.emColor || C.accent) : (o.color || C.ink), alpha: o.alpha });
      if (em && emK !== undefined) {
        ctx.save(); ctx.globalAlpha *= (o.alpha === undefined ? 1 : o.alpha); ctx.fillStyle = o.emColor || C.accent;
        ctx.fillRect(cx, y + o.size * 0.18, w * clamp(emK), Math.max(3, o.size * 0.07)); ctx.restore();
      }
      cx += w;
    });
  }
  /* ---- 線で描くアイコン（icons.py から台本で使う分だけ埋め込まれる）。k は描けた割合、lt で繰り返しの動き ---- */
  var ICO = (function () { var el = root.querySelector("script[data-mv-icons]"); try { return el ? JSON.parse(el.textContent) : {}; } catch (e) { return {}; } })(), ICOC = {};
  function icoPrep(n) {
    var c = ICOC[n]; if (c) return c; var I = ICO[n]; if (!I) return null;
    c = { a: I.a, paths: I.d.map(function (d) { var L = 30; try { var pe = document.createElementNS("http://www.w3.org/2000/svg", "path"); pe.setAttribute("d", d); L = pe.getTotalLength() || 30; } catch (e) {} return { p: new Path2D(d), L: L + 1 }; }) };
    return (ICOC[n] = c);
  }
  function drawIcon(n, x, y, size, o) {
    o = o || {}; var c = icoPrep(n); if (!c) return false;
    var k = o.k === undefined ? 1 : o.k, lt = o.lt || 0, an = o.anim || c.a, col = o.color || C.accent, m = c.paths.length;
    if (k <= 0) return true;
    ctx.save(); ctx.translate(x, y);
    if (k >= 1 && an && an !== "none") {
      if (an === "spin") ctx.rotate(lt * .0012);
      else if (an === "swing") { ctx.translate(0, -size * .42); ctx.rotate(Math.sin(lt / 320) * .22); ctx.translate(0, size * .42); }
      else if (an === "beat") { var bs = 1 + .14 * Math.pow(Math.max(0, Math.sin(lt / 260)), 6); ctx.scale(bs, bs); }
      else if (an === "float") ctx.translate(0, Math.sin(lt / 600) * size * .07);
      else if (an === "blink") ctx.globalAlpha *= .55 + .45 * (.5 + .5 * Math.sin(lt / 350));
      else if (an === "glow") { ctx.shadowColor = col; ctx.shadowBlur = size * .3 * (.5 + .5 * Math.sin(lt / 500)); }
      else if (an === "pulse") { var ps = 1 + .07 * Math.sin(lt / 400); ctx.scale(ps, ps); }
      else if (an === "shake") { var ph = lt % 2400; if (ph < 420) ctx.rotate(Math.sin(ph * .09) * .16 * (1 - ph / 420)); }
      else if (an === "bounce") ctx.translate(0, -Math.abs(Math.sin(lt / 360)) * size * .09);
      else if (an === "flip") ctx.scale(Math.cos(lt / 900), 1);
      else if (an === "twinkle") { var ts = 1 + .13 * Math.sin(lt / 260); ctx.scale(ts, ts); ctx.rotate(Math.sin(lt / 520) * .12); }
    }
    var sc = size / 24; ctx.scale(sc, sc); ctx.translate(-12, -12);
    ctx.strokeStyle = col; ctx.lineWidth = o.width || 2; ctx.lineCap = "round"; ctx.lineJoin = "round";
    c.paths.forEach(function (q, i) { var kk = clamp(k * (1 + .45 * (m - 1)) - i * .45); if (kk <= 0) return;
      ctx.setLineDash(kk < 1 ? [q.L * kk, q.L * 2] : []); ctx.stroke(q.p); });
    ctx.restore(); return true;
  }
  function icon(s, x, y, size, col, k, lt) {
    if (s && ICO[s]) { drawIcon(s, x, y, size * 1.05, { color: col || C.accent, k: k === undefined ? 1 : k, lt: lt || 0 }); return; }
    if (!s) { ctx.save(); ctx.fillStyle = col || C.accent; ctx.beginPath(); ctx.arc(x, y, size * .22, 0, Math.PI * 2); ctx.fill(); ctx.restore(); return; }
    txt(s, x, y + size * .35, { size: size, align: "center", color: col || C.ink, font: '"Apple Color Emoji","Segoe UI Emoji","Noto Color Emoji",' + F.sans });
  }
  function stateMark(x, y, state, t, r) {
    r = r || 9; ctx.save();
    if (state === "working") {
      ctx.strokeStyle = C.edge; ctx.lineWidth = 3; ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.stroke();
      ctx.strokeStyle = C.accent; var a0 = (t / 180) % (Math.PI * 2);
      ctx.beginPath(); ctx.arc(x, y, r, a0, a0 + Math.PI * 1.2); ctx.stroke();
    } else if (state === "done") {
      ctx.fillStyle = C.ok; ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = C.bg0; ctx.lineWidth = 2.6; ctx.lineCap = "round"; ctx.lineJoin = "round";
      ctx.beginPath(); ctx.moveTo(x - r * .45, y); ctx.lineTo(x - r * .1, y + r * .38); ctx.lineTo(x + r * .5, y - r * .38); ctx.stroke();
    } else if (state === "blocked") {
      var pu = .5 + .5 * Math.sin(t / 160);
      ctx.globalAlpha *= .3 + .3 * pu; ctx.fillStyle = C.warn; ctx.beginPath(); ctx.arc(x, y, r + 5, 0, Math.PI * 2); ctx.fill();
      ctx.globalAlpha = 1; ctx.fillStyle = C.warn; ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = C.bg0; ctx.fillRect(x - 1.4, y - r * .55, 2.8, r * .7); ctx.fillRect(x - 1.4, y + r * .3, 2.8, 2.8);
    } else if (state === "idle") {
      ctx.strokeStyle = C.muted; ctx.lineWidth = 2.6; ctx.beginPath(); ctx.arc(x, y, r - 1, 0, Math.PI * 2); ctx.stroke();
    } else { ctx.fillStyle = C.faint; ctx.beginPath(); ctx.arc(x, y, 3.5, 0, Math.PI * 2); ctx.fill(); }
    ctx.restore();
  }
  function panel(x, y, w, h, o) {
    o = o || {}; ctx.save();
    if (o.shadow !== false) { ctx.shadowColor = C.shadow; ctx.shadowBlur = 36; ctx.shadowOffsetY = 14; }
    rr(x, y, w, h, o.r === undefined ? 16 : o.r); ctx.fillStyle = o.fill || C.panel; ctx.fill();
    ctx.shadowColor = "transparent"; ctx.lineWidth = o.lw || 1.5; ctx.strokeStyle = o.stroke || C.edge; ctx.stroke(); ctx.restore();
  }
  function accentAt(i) { return C.accents[i % C.accents.length]; }
  /* 共通の見出し（場面の左上） */
  function heading(s, lt) {
    if (!s.heading) return 0;
    var k = P(lt, 0, 600);
    txt(s.heading, 120, 190 + (1 - k) * 14, { size: 54, weight: 800, font: F.display, color: C.ink, alpha: k });
    ctx.save(); ctx.globalAlpha *= k; ctx.fillStyle = C.accent; ctx.fillRect(120, 214, 90 * P(lt, 200, 900), 6); ctx.restore();
    return 1;
  }
  /* 場面の中の「区切り」を、長さに応じた時刻に割り当てる（最初の in ms で入り、残りに均等） */
  function slots(n, d, lead, tail) {
    var a = lead || 500, b = Math.max(a + 200, d - (tail || 900)), out = [];
    /* 説明に合わせる: 項目の数と字幕の文の数が同じなら（sync: true なら数が違っても）、i 番目の項目を i 番目の文が始まる時に出す。
       余った項目は最後の文の間に均等に。sync: false で場面の長さへの均等な割り付けに戻す */
    var cs = CUR_CUES;
    if (n > 0 && cs && cs.length && CUR_SYNC !== false && (CUR_SYNC === true || cs.length === n)) {
      var lastA = cs[cs.length - 1], lastB = CUR_CUEE[cs.length - 1], extra = n - cs.length;
      for (var j = 0; j < n; j++) out.push(j < cs.length ? cs[j] : lastA + (lastB - lastA) * (j - cs.length + 1) / (extra + 1));
      return out;
    }
    for (var i = 0; i < n; i++) out.push(a + (b - a) * i / Math.max(1, n));
    if (!CUR_ORDER || CUR_ORDER === "normal" || n < 2) return out;
    /* 現れる順を並べ替える: reverse 後ろから・center 中央から・edges 両端から・random ばらばら（種は項目の数）・alternate 1 つおき・zigzag 前後交互 */
    if (CUR_ORDER === "alternate" || CUR_ORDER === "zigzag") { var seq = [], i2;
      if (CUR_ORDER === "alternate") { for (i2 = 0; i2 < n; i2 += 2) seq.push(i2); for (i2 = 1; i2 < n; i2 += 2) seq.push(i2); }
      else for (i2 = 0; seq.length < n; i2++) { seq.push(i2); if (seq.length < n) seq.push(n - 1 - i2); }
      var res2 = []; seq.forEach(function (i, j) { res2[i] = out[j]; }); return res2; }
    var idx = out.map(function (_, i) { return i; }), m = (n - 1) / 2, r = rand(n * 7919 + 13), key = idx.map(function () { return r(); });
    idx.sort(function (p, q) { return CUR_ORDER === "reverse" ? q - p : CUR_ORDER === "center" ? Math.abs(p - m) - Math.abs(q - m) || p - q
      : CUR_ORDER === "edges" ? Math.abs(q - m) - Math.abs(p - m) || p - q : key[p] - key[q]; });
    var res = []; idx.forEach(function (i, j) { res[i] = out[j]; }); return res;
  }
  function useMotion(s) { CUR_EASE = EASES[s.ease || SPEC.ease] || eo; CUR_ORDER = s.order || SPEC.order || "";
    /* その場面の字幕（ナレーションの文・せりふ）の始まりと終わり（場面の中の ms）。声の長さ・retime で動いた後の時刻 */
    var sc = SCOF && SCOF.get(s);
    CUR_CUES = sc && sc.cues.length ? sc.cues.map(function (ci) { return CUES[ci].a - sc.t0; }) : null;
    CUR_CUEE = CUR_CUES ? sc.cues.map(function (ci) { return CUES[ci].b - sc.t0; }) : null;
    CUR_SYNC = s.sync !== undefined ? s.sync : SPEC.sync !== undefined ? SPEC.sync : "auto"; }
  function cueStart(i) { return CUR_CUES && CUR_CUES.length ? CUR_CUES[Math.max(0, Math.min(CUR_CUES.length - 1, i))] : null; }
  function cueEnd(i) { return CUR_CUEE && CUR_CUEE.length ? CUR_CUEE[Math.max(0, Math.min(CUR_CUEE.length - 1, i))] : null; }

  /* ================= 紋章（タイトル・エンドで使う） ================= */
  function emblem(kind, cx, cy, r, rot, alpha, label) {
    if (kind === "none" || r <= 0) return;
    ctx.save(); ctx.globalAlpha *= alpha; ctx.translate(cx, cy);
    if (kind === "wheel") {
      ctx.rotate(rot); var s = r / 23; ctx.scale(s, s);
      for (var i = 0; i < 8; i++) { var a0 = -Math.PI / 2 + i * Math.PI / 4, a1 = a0 + Math.PI / 4;
        ctx.beginPath(); ctx.arc(0, 0, 23, a0, a1); ctx.arc(0, 0, 9, a1, a0, true); ctx.closePath(); ctx.fillStyle = i === 0 ? C.accent2 : C.panel2; ctx.fill(); }
      ctx.strokeStyle = C.accent; ctx.lineCap = "round"; ctx.lineWidth = 3;
      for (var j = 0; j < 4; j++) { var a = j * Math.PI / 4; ctx.beginPath(); ctx.moveTo(Math.cos(a) * -29, Math.sin(a) * -29); ctx.lineTo(Math.cos(a) * 29, Math.sin(a) * 29); ctx.stroke(); }
      ctx.lineWidth = 4; ctx.beginPath(); ctx.arc(0, 0, 23, 0, Math.PI * 2); ctx.stroke();
      ctx.fillStyle = C.bg0; ctx.lineWidth = 2.6; ctx.beginPath(); ctx.arc(0, 0, 9.5, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    } else {
      /* ring: 輪と頭文字 */
      ctx.rotate(rot * .3);
      ctx.strokeStyle = C.accent; ctx.lineWidth = r * .08; ctx.beginPath(); ctx.arc(0, 0, r, -Math.PI * .45, Math.PI * 1.35); ctx.stroke();
      ctx.strokeStyle = C.accent2; ctx.beginPath(); ctx.arc(0, 0, r * .72, Math.PI * .6, Math.PI * 2.3); ctx.stroke();
      ctx.rotate(-rot * .3);
      txt(Array.from(String(label || "•"))[0], 0, r * .26, { size: r * .78, weight: 800, align: "center", font: F.display, color: C.ink });
    }
    ctx.restore();
  }

  /* ================= 場面の部品 ================= */
  var LAYOUT_CACHE = new WeakMap();
  var IMGS = {};
  var R = {};

  R.title = function (s, lt, d, T) {
    sfxEv(250, "title"); if (s.subtitle) sfxEv(2000, "appear", { i: 0 });
    var k = P(lt, 0, 1500, back);
    for (var i = 0; i < 3; i++) { var ph = ((lt / 2600) + i / 3) % 1;
      ctx.save(); ctx.strokeStyle = C.accent2; ctx.globalAlpha *= (1 - ph) * .16 * P(lt, 600, 1600); ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(960, 400, 190 + ph * 260, 0, Math.PI * 2); ctx.stroke(); ctx.restore(); }
    emblem(s.mark || "ring", 960, 400, 160 * k, (1 - P(lt, 0, 2000)) * -2.4 + lt * .00012, clamp(k * 1.4), s.markText || s.title);
    var ta = animOf(s, "title"); textShake(ta, 1200, 16);
    animText(s.title, 960, 722, { size: 116, weight: 800, align: "center", font: F.display }, ta, lt, 1200, 1400);
    if (s.subtitle) txt(s.subtitle, 960, 806, { size: 42, weight: 700, align: "center", color: C.accent, alpha: P(lt, 2000, 2900), spacing: 8 });
    var tg = P(lt, 3200, 4200);
    if (s.tagline) rich(s.tagline, 960, 888 + (1 - tg) * 16, { size: 36, align: "center", color: C.muted, alpha: tg });
  };

  R.bullets = function (s, lt, d, T) {
    heading(s, lt);
    var items = s.items || [], at = slots(items.length, d, 700, Math.min(1600, d * .25));
    var y = s.heading ? 330 : 230, cur = -1;
    at.forEach(function (a, i) { if (lt >= a) cur = i; });
    var lh = 112, maxW = 1540;
    items.forEach(function (it, i) {
      sfxEv(at[i], "appear", { i: i });
      var k = P(lt, at[i], at[i] + 600), text = typeof it === "string" ? it : it.text;
      if (k <= 0) return;
      var lines = wrap(text, maxW - 120, { size: 40, weight: 500 });
      var yy = y, act = i === cur && s.focus !== false;
      ctx.save(); ctx.globalAlpha *= k * (act || cur < 0 ? 1 : .55);
      ctx.translate((1 - k) * -40, 0);
      if (act) { rr(96, yy - 58, 1728, lines.length * 54 + 44, 16); ctx.fillStyle = C.panel; ctx.fill(); ctx.fillStyle = C.accent; ctx.fillRect(96, yy - 58, 6, lines.length * 54 + 44); }
      icon(it.icon, 160, yy - 14, 44, accentAt(i), P(lt, at[i], at[i] + 900), lt);
      lines.forEach(function (ln, j) { rich(ln, 220, yy + j * 54, { size: 40, weight: 500 }, act ? P(lt, at[i] + 300, at[i] + 900) : 1); });
      ctx.restore();
      y += lines.length * 54 + 58;
    });
  };

  function flowLayout(s) {
    var c = LAYOUT_CACHE.get(s); if (c) return c;
    var nodes = s.nodes || [], edges = s.edges || [], ids = nodes.map(function (n) { return n.id; });
    var rank = {}; ids.forEach(function (i) { rank[i] = 0; });
    for (var it = 0; it < ids.length; it++) edges.forEach(function (e) {
      if (rank[e.from] === undefined || rank[e.to] === undefined || e.back) return;
      if (rank[e.to] <= rank[e.from]) rank[e.to] = rank[e.from] + 1; });
    var maxR = 0; ids.forEach(function (i) { maxR = Math.max(maxR, rank[i]); });
    var cols = []; for (var r = 0; r <= maxR; r++) cols.push([]);
    ids.forEach(function (i) { cols[rank[i]].push(i); });
    var pos = {}, span = Math.min(1600, 450 * (maxR + 1)), x0 = 960 - span / 2 + 170, x1 = 960 + span / 2 - 170, y0 = s.heading ? 330 : 240, y1 = 900;
    cols.forEach(function (col, r) {
      var x = maxR ? mix(x0, x1, r / maxR) : 960;
      col.forEach(function (id, k) { pos[id] = { x: x, y: mix(y0, y1, (k + 1) / (col.length + 1)), r: r }; });
    });
    var nw = maxR ? Math.min(330, (x1 - x0) / maxR - 70) : 330;
    c = { pos: pos, rank: rank, maxR: maxR, nw: Math.max(200, nw), nh: 124 };
    LAYOUT_CACHE.set(s, c); return c;
  }
  function qpt(p0, c, p1, u) { var v = 1 - u; return { x: v * v * p0.x + 2 * v * u * c.x + u * u * p1.x, y: v * v * p0.y + 2 * v * u * c.y + u * u * p1.y }; }
  R.flow = function (s, lt, d, T) {
    heading(s, lt);
    var L = flowLayout(s), byId = {}; (s.nodes || []).forEach(function (n) { byId[n.id] = n; });
    var nodeIn = function (id) { return 400 + L.pos[id].r * Math.min(700, d * .08); };
    var edges = s.edges || [], nE = edges.length;
    var buildEnd = 400 + L.maxR * Math.min(700, d * .08) + 900;
    var flowAt = slots(nE, d, buildEnd, 900);
    edges.forEach(function (e, i) {
      var a = L.pos[e.from], b = L.pos[e.to]; if (!a || !b) return;
      var p0, p1, c;
      if (e.back || b.r <= a.r) { p0 = { x: a.x, y: a.y + L.nh / 2 }; p1 = { x: b.x, y: b.y + L.nh / 2 + 4 }; c = { x: (a.x + b.x) / 2, y: Math.max(a.y, b.y) + 220 }; }
      else { p0 = { x: a.x + L.nw / 2, y: a.y }; p1 = { x: b.x - L.nw / 2 - 6, y: b.y }; c = { x: (p0.x + p1.x) / 2, y: (p0.y + p1.y) / 2 - (a.y === b.y ? 0 : 0) }; }
      var st = Math.max(nodeIn(e.from), nodeIn(e.to)) + 300, k = P(lt, st, st + 700, eio);
      sfxEv(st, "connect", { i: i }); if (e.travel !== undefined && e.travel !== false) { sfxEv(flowAt[i], "travel"); sfxEv(flowAt[i] + 1250, "arrive"); }
      if (k <= 0) return;
      ctx.save(); ctx.strokeStyle = e.color || C.accent2; ctx.lineWidth = 4; if (e.dashed) ctx.setLineDash([14, 10]);
      var glow = lt > flowAt[i] && lt < flowAt[i] + 1400 ? Math.sin(lin(lt, flowAt[i], flowAt[i] + 1400) * Math.PI) : 0;
      if (glow > 0) { ctx.shadowColor = C.accent2; ctx.shadowBlur = 24 * glow; }
      ctx.beginPath(); var N = 40;
      for (var j = 0; j <= N * k; j++) { var q = qpt(p0, c, p1, j / N); j ? ctx.lineTo(q.x, q.y) : ctx.moveTo(q.x, q.y); }
      ctx.stroke(); ctx.setLineDash([]); ctx.shadowBlur = 0;
      if (k >= 1) {
        var pe = qpt(p0, c, p1, 1), pb = qpt(p0, c, p1, .96), ang = Math.atan2(pe.y - pb.y, pe.x - pb.x);
        ctx.save(); ctx.fillStyle = e.color || C.accent2; ctx.translate(pe.x, pe.y); ctx.rotate(ang);
        ctx.beginPath(); ctx.moveTo(6, 0); ctx.lineTo(-16, -11); ctx.lineTo(-16, 11); ctx.closePath(); ctx.fill(); ctx.restore();
        if (e.label) { var m = qpt(p0, c, p1, .5), w = tw(e.label, { size: 22, weight: 700 }) + 28;
          rr(m.x - w / 2, m.y - 20, w, 40, 20); ctx.fillStyle = C.bg1; ctx.fill(); ctx.strokeStyle = C.edge; ctx.lineWidth = 1.5; ctx.stroke();
          txt(e.label, m.x, m.y + 8, { size: 22, weight: 700, align: "center", color: C.muted }); }
      }
      ctx.restore();
      if (e.travel !== undefined && e.travel !== false && lt > flowAt[i] && lt < flowAt[i] + 1400) {
        var u = eio(lin(lt, flowAt[i], flowAt[i] + 1400)), pt = qpt(p0, c, p1, u), lab = e.travel === true ? "" : String(e.travel);
        ctx.save(); ctx.shadowColor = C.accent; ctx.shadowBlur = 20; ctx.fillStyle = C.accent;
        if (lab) { var tw2 = tw(lab, { size: 20, weight: 700, font: F.mono }) + 24; rr(pt.x - tw2 / 2, pt.y - 20, tw2, 40, 10); ctx.fill(); ctx.shadowBlur = 0;
          txt(lab, pt.x, pt.y + 7, { size: 20, weight: 700, font: F.mono, align: "center", color: C.onAccent }); }
        else { ctx.beginPath(); ctx.arc(pt.x, pt.y, 11, 0, Math.PI * 2); ctx.fill(); }
        ctx.restore();
      }
    });
    Object.keys(L.pos).forEach(function (id, i) {
      var p = L.pos[id], n = byId[id], k = P(lt, nodeIn(id), nodeIn(id) + 600, back);
      sfxEv(nodeIn(id), "appear", { i: p.r });
      if (k <= 0) return;
      var hot = edges.some(function (e, j) { return e.to === id && lt > flowAt[j] + 1200 && lt < flowAt[j] + 2600; });
      ctx.save(); ctx.translate(p.x, p.y); ctx.scale(k, k);
      panel(-L.nw / 2, -L.nh / 2, L.nw, L.nh, { stroke: hot ? C.accent : C.edge, lw: hot ? 3 : 1.5, fill: n.kind === "start" ? C.accent : C.panel });
      var ink = n.kind === "start" ? C.onAccent : C.ink;
      txt(n.label, 0, n.sub ? -2 : 13, { size: 36, weight: 800, align: "center", color: ink });
      if (n.sub) txt(n.sub, 0, 38, { size: 22, align: "center", color: n.kind === "start" ? ink : C.muted, font: F.mono });
      ctx.restore();
    });
  };

  R.steps = function (s, lt, d, T) {
    heading(s, lt);
    var items = s.items || [], n = items.length, at = slots(n, d, 600, Math.min(1400, d * .2));
    var y = s.heading ? 560 : 500, x0 = 220, x1 = 1700, cur = -1;
    at.forEach(function (a, i) { if (lt >= a) cur = i; });
    ctx.save(); ctx.strokeStyle = C.edge; ctx.lineWidth = 6; ctx.beginPath(); ctx.moveTo(x0, y); ctx.lineTo(x1, y); ctx.stroke();
    var prog = n > 1 ? clamp((cur + P(lt, at[Math.max(0, cur)], at[Math.max(0, cur)] + 700)) / (n - 1)) : 1;
    ctx.strokeStyle = C.accent; ctx.beginPath(); ctx.moveTo(x0, y); ctx.lineTo(mix(x0, x1, Math.min(1, prog)), y); ctx.stroke(); ctx.restore();
    items.forEach(function (it, i) {
      var x = n > 1 ? mix(x0, x1, i / (n - 1)) : 960, k = P(lt, at[i] - 200, at[i] + 400, back), act = i === cur;
      sfxEv(at[i], "step", { i: i });
      ctx.save(); ctx.translate(x, y); ctx.scale(Math.max(.001, k) * (act ? 1.12 : 1), Math.max(.001, k) * (act ? 1.12 : 1));
      ctx.fillStyle = i <= cur ? accentAt(i) : C.panel; ctx.beginPath(); ctx.arc(0, 0, 40, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = accentAt(i); ctx.lineWidth = 3; ctx.stroke();
      txt(String(i + 1), 0, 13, { size: 36, weight: 800, align: "center", color: i <= cur ? C.onAccent : C.ink });
      ctx.restore();
      var tk = P(lt, at[i], at[i] + 500);
      var lab = typeof it === "string" ? it : it.label;
      wrap(lab, 280, { size: 32, weight: 700 }).forEach(function (ln, j) { txt(ln, x, y + 110 + j * 40, { size: 32, weight: 700, align: "center", alpha: tk * (act ? 1 : .7) }); });
      if (it.sub) wrap(it.sub, 280, { size: 24 }).forEach(function (ln, j) { txt(ln, x, y + 190 + j * 32, { size: 24, align: "center", color: C.muted, alpha: tk }); });
    });
  };

  R.terminal = function (s, lt, d, T) {
    heading(s, lt);
    var x = 200, y = s.heading ? 290 : 190, w = 1520, h = s.heading ? 680 : 760;
    var k = P(lt, 0, 700); ctx.save(); ctx.globalAlpha *= k; ctx.translate(0, (1 - k) * 30);
    panel(x, y, w, h, { fill: C.code, r: 18 });
    ctx.save(); rr(x, y, w, h, 18); ctx.clip();
    ctx.fillStyle = C.codeBar; ctx.fillRect(x, y, w, 48);
    [C.warn, C.accent2, C.ok].forEach(function (c, i) { ctx.fillStyle = c; ctx.globalAlpha = .75; ctx.beginPath(); ctx.arc(x + 30 + i * 26, y + 24, 8, 0, Math.PI * 2); ctx.fill(); });
    ctx.globalAlpha = 1;
    txt(s.title || "terminal", x + w / 2, y + 32, { size: 20, font: F.mono, color: C.codeMuted, align: "center" });
    var lines = s.lines || [], prompt = s.prompt || "$", plan = [], at = 800, CH = 34;
    var totalChars = 0; lines.forEach(function (l) { if (l.cmd) totalChars += l.cmd.length; });
    var budget = Math.max(1, d * .75 - 800 - lines.length * 350), rate = Math.min(55, Math.max(14, budget / Math.max(1, totalChars)));
    lines.forEach(function (l) {
      if (l.cmd) { var dd = l.cmd.length * rate; plan.push({ l: l, a: at, b: at + dd }); sfxEv(at, "type", { n: l.cmd.length, dur: dd }); sfxEv(at + dd + 60, "enter"); at += dd + 300; }
      else { plan.push({ l: l, a: at, b: at }); at += 220; }
    });
    var row = 0, lh = 44, maxRows = Math.floor((h - 90) / lh), rows = [];
    plan.forEach(function (p) {
      if (lt < p.a) return;
      if (p.l.cmd) { var n = Math.floor(p.l.cmd.length * lin(lt, p.a, p.b)); rows.push({ cmd: true, text: p.l.cmd.slice(0, n), typing: lt < p.b }); }
      else String(p.l.out).split("\n").forEach(function (o) { rows.push({ cmd: false, text: o }); });
    });
    rows.slice(-maxRows).forEach(function (r, i) {
      var yy = y + 100 + i * lh;
      if (r.cmd) {
        txt(prompt, x + 36, yy, { size: 30, font: F.mono, color: C.accent2 });
        var px = x + 36 + tw(prompt + " ", { size: 30, font: F.mono });
        txt(r.text, px, yy, { size: 30, font: F.mono, color: C.codeInk });
        if (r.typing || (i === Math.min(rows.length, maxRows) - 1 && Math.floor(lt / 500) % 2 === 0)) {
          ctx.fillStyle = C.accent2; ctx.fillRect(px + tw(r.text, { size: 30, font: F.mono }) + 4, yy - 26, 14, 32); }
      } else txt(r.text, x + 36, yy, { size: 28, font: F.mono, color: C.codeMuted });
    });
    ctx.restore(); ctx.restore();
  };

  function parseNum(v) { var m = String(v).match(/-?[\d,]*\.?\d+/); if (!m) return null;
    return { m: m, n: parseFloat(m[0].replace(/,/g, "")), dec: (m[0].split(".")[1] || "").length, comma: m[0].indexOf(",") >= 0 }; }
  function fmtNum(orig, k) {
    var p = parseNum(orig); if (!p) return orig; var v = p.n * k, s2 = v.toFixed(p.dec);
    if (p.comma) { var q = s2.split("."); q[0] = q[0].replace(/\B(?=(\d{3})+(?!\d))/g, ","); s2 = q.join("."); }
    return String(orig).slice(0, p.m.index) + s2 + String(orig).slice(p.m.index + p.m[0].length);
  }
  R.stats = function (s, lt, d, T) {
    heading(s, lt);
    var items = s.items || [], n = items.length, gap = 40, tw0 = Math.min(480, (1680 - gap * (n - 1)) / n);
    var x = 960 - (tw0 * n + gap * (n - 1)) / 2, y = s.heading ? 380 : 320;
    items.forEach(function (it, i) {
      var a = 500 + i * 350, k = P(lt, a, a + 600, back), c = P(lt, a + 200, a + 1800);
      sfxEv(a, "appear", { i: i }); if (parseNum(it.value)) { sfxEv(a + 200, "count", { dur: 1500 }); sfxEv(a + 1750, "countEnd", { i: i }); }
      if (k <= 0) return;
      ctx.save(); ctx.translate(x + i * (tw0 + gap) + tw0 / 2, y + 190); ctx.scale(k, k);
      panel(-tw0 / 2, -190, tw0, 380, {}); ctx.fillStyle = accentAt(i); ctx.fillRect(-tw0 / 2, -190, tw0, 8);
      var val = fmtNum(it.value, c < 1 ? c : 1);
      txt(val, 0, 10, { size: Math.min(110, tw0 / Math.max(3, String(it.value).length) * 1.6), weight: 800, align: "center", color: accentAt(i), font: F.display });
      wrap(it.label || "", tw0 - 60, { size: 30, weight: 700 }).forEach(function (ln, j) { txt(ln, 0, 90 + j * 38, { size: 30, weight: 700, align: "center", color: C.muted }); });
      ctx.restore();
    });
  };

  R.bars = function (s, lt, d, T) {
    heading(s, lt);
    var items = s.items || [], n = items.length, max = s.max || Math.max.apply(null, items.map(function (i) { return +i.value; })) || 1;
    var y0 = s.heading ? 320 : 240, bh = Math.min(76, (900 - y0) / n - 26), lw = 0;
    items.forEach(function (it) { lw = Math.max(lw, tw(it.label, { size: 32, weight: 700 })); });
    var x0 = 140 + lw + 30, bw = 1720 - x0 - 200;
    items.forEach(function (it, i) {
      var y = y0 + i * (bh + 26), a = 500 + i * Math.min(400, d * .06), k = P(lt, a, a + 1100, eio);
      sfxEv(a, "grow", { i: i }); if (s.highlight === i) sfxEv(a + 1100, "emphasize");
      txt(it.label, x0 - 24, y + bh / 2 + 11, { size: 32, weight: 700, align: "right", alpha: P(lt, a - 200, a + 200) });
      var w = bw * (+it.value) / max * k, hl = s.highlight === i;
      ctx.save(); rr(x0, y, Math.max(2, w), bh, 10); ctx.fillStyle = accentAt(i); if (hl) { ctx.shadowColor = accentAt(i); ctx.shadowBlur = 24 * (.5 + .5 * Math.sin(lt / 300)); } ctx.fill(); ctx.restore();
      var disp = it.display || (String(it.value) + (s.unit || ""));
      txt(fmtNum(disp, k), x0 + w + 18, y + bh / 2 + 12, { size: 32, weight: 800, color: C.ink, alpha: k, font: F.display });
    });
  };

  R.compare = function (s, lt, d, T) {
    heading(s, lt);
    var cols = [s.left || {}, s.right || {}], y = s.heading ? 290 : 200, h = 1000 - y - 60, w = 760;
    var pts = cols.map(function (c) { return c.points || []; }), maxN = Math.max(pts[0].length, pts[1].length);
    var at = slots(maxN * 2, d, 1200, 900);
    cols.forEach(function (c, ci) {
      var x = ci === 0 ? 150 : 1010, k = P(lt, 200 + ci * 300, 900 + ci * 300);
      sfxEv(200 + ci * 300, "appear", { i: ci });
      ctx.save(); ctx.globalAlpha *= k; ctx.translate((1 - k) * (ci === 0 ? -80 : 80), 0);
      var col = c.tone === "bad" ? C.warn : c.tone === "good" ? C.ok : accentAt(ci);
      panel(x, y, w, h, { stroke: col, lw: 2.5 });
      ctx.fillStyle = col; ctx.globalAlpha *= .14; rr(x, y, w, 96, 16); ctx.fill(); ctx.globalAlpha /= .14;
      txt(c.title || "", x + w / 2, y + 62, { size: 42, weight: 800, align: "center", color: col });
      pts[ci].forEach(function (p, i) {
        var a = at[i * 2 + ci]; sfxEv(a, "appear", { i: i }); var pk = P(lt, a, a + 500); if (pk <= 0) return;
        var lines = wrap(p, w - 120, { size: 34 });
        lines.forEach(function (ln, j) { rich(ln, x + 90, y + 170 + i * 110 + j * 44, { size: 34, alpha: pk }); });
        ctx.save(); ctx.globalAlpha *= pk; ctx.fillStyle = col;
        if (c.tone === "bad") txt("!", x + 52, y + 172 + i * 110, { size: 34, weight: 800, color: col, align: "center" });
        else if (c.tone === "good") txt("✓", x + 52, y + 172 + i * 110, { size: 32, weight: 800, color: col, align: "center" });
        else { ctx.beginPath(); ctx.arc(x + 52, y + 160 + i * 110, 8, 0, Math.PI * 2); ctx.fill(); }
        ctx.restore();
      });
      ctx.restore();
    });
    var vk = P(lt, 900, 1400, back); if (s.vs !== false) sfxEv(900, "hit");
    if (s.vs !== false && vk > 0) { ctx.save(); ctx.translate(960, y + h / 2); ctx.scale(vk, vk);
      ctx.fillStyle = C.bg1; ctx.beginPath(); ctx.arc(0, 0, 44, 0, Math.PI * 2); ctx.fill(); ctx.strokeStyle = C.edge; ctx.lineWidth = 2; ctx.stroke();
      txt(s.vs || "VS", 0, 12, { size: 30, weight: 800, align: "center", color: C.muted }); ctx.restore(); }
  };

  R.statement = function (s, lt, d, T) {
    var lines = []; (s.lines || [s.text || ""]).forEach(function (l) { wrap(l, 1500, { size: s.size || 76, weight: 800, font: F.display }).forEach(function (w) { lines.push(w); }); });
    var n = lines.length, size = s.size || 76, lh = size * 1.35, y0 = 540 - (n - 1) * lh / 2 + size * .35;
    var at = slots(n, d * .55, 300, 0);
    lines.forEach(function (ln, i) {
      var k = P(lt, at[i], at[i] + 700);
      sfxEv(at[i], i === 0 ? "hit" : "appear", { i: i }); if (/\*\*/.test(ln)) sfxEv(at[i] + 550, "emphasize");
      var sa = animOf(s, "text"); textShake(sa, at[i], 10);
      animText(ln, 960, y0 + i * lh, { size: size, weight: 800, align: "center", font: F.display }, sa, lt, at[i], 700, P(lt, at[i] + 500, at[i] + 1200));
    });
    if (s.note) txt(s.note, 960, y0 + n * lh + 30, { size: 30, align: "center", color: C.muted, alpha: P(lt, d * .5, d * .5 + 800) });
  };

  var KW = /\b(const|let|var|function|return|if|else|for|while|import|from|export|class|new|await|async|def|self|None|True|False|in|of|type|interface|public|private|static|void|int|string|bool|true|false|null|undefined)\b/g;
  function codeLine(src, x, y, size) {
    var parts = [], re = /(\/\/.*$|#.*$|"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|`[^`]*`)/g, last = 0, m;
    while ((m = re.exec(src))) { if (m.index > last) parts.push([src.slice(last, m.index), 0]); parts.push([m[0], /^(\/\/|#)/.test(m[0]) ? 2 : 1]); last = m.index + m[0].length; }
    if (last < src.length) parts.push([src.slice(last), 0]);
    var cx = x;
    parts.forEach(function (p) {
      if (p[1] === 0) {
        var seg = p[0], lastI = 0, mm; KW.lastIndex = 0;
        while ((mm = KW.exec(seg))) { var a = seg.slice(lastI, mm.index); txt(a, cx, y, { size: size, font: F.mono, color: C.codeInk }); cx += tw(a, { size: size, font: F.mono });
          txt(mm[0], cx, y, { size: size, font: F.mono, color: C.accent2, weight: 700 }); cx += tw(mm[0], { size: size, font: F.mono, weight: 700 }); lastI = mm.index + mm[0].length; }
        var rest = seg.slice(lastI); txt(rest, cx, y, { size: size, font: F.mono, color: C.codeInk }); cx += tw(rest, { size: size, font: F.mono });
      } else { var col = p[1] === 2 ? C.codeMuted : C.ok; txt(p[0], cx, y, { size: size, font: F.mono, color: col }); cx += tw(p[0], { size: size, font: F.mono }); }
    });
  }
  R.code = function (s, lt, d, T) {
    heading(s, lt);
    var lines = String(s.code || "").split("\n"), hl = s.highlight || [], y = s.heading ? 280 : 180, size = lines.length > 16 ? 24 : 28, lh = size * 1.6;
    var h = Math.min(1000 - y, lines.length * lh + 80), x = 160, w = 1600;
    var k = P(lt, 0, 600); ctx.save(); ctx.globalAlpha *= k;
    panel(x, y, w, h, { fill: C.code });
    var at = slots(hl.length, d, 900, 600), cur = -1; at.forEach(function (a, i) { if (lt >= a) cur = i; sfxEv(a, "emphasize", { i: i }); });
    lines.forEach(function (ln, i) {
      var yy = y + 60 + i * lh; if (yy > y + h - 10) return;
      var on = cur >= 0 && hl[cur] && i + 1 >= hl[cur].lines[0] && i + 1 <= hl[cur].lines[hl[cur].lines.length - 1];
      if (on) { ctx.save(); ctx.fillStyle = C.accent; ctx.globalAlpha = .16 * P(lt, at[cur], at[cur] + 400); ctx.fillRect(x + 8, yy - size * 1.05, w - 16, lh); ctx.restore(); }
      ctx.save(); ctx.globalAlpha *= cur >= 0 && !on ? .45 : 1;
      txt(String(i + 1), x + 60, yy, { size: size * .8, font: F.mono, color: C.codeMuted, align: "right" });
      codeLine(ln, x + 90, yy, size); ctx.restore();
    });
    if (cur >= 0 && hl[cur].note) {
      var nk = P(lt, at[cur] + 200, at[cur] + 700), nl = wrap(hl[cur].note, 520, { size: 28, weight: 700 }), nh = nl.length * 40 + 36;
      var ny = Math.min(y + 60 + (hl[cur].lines[0] - 1) * lh - size, 1000 - nh);
      ctx.save(); ctx.globalAlpha *= nk; panel(1780 - 560, ny, 560, nh, { stroke: C.accent, lw: 2 });
      nl.forEach(function (l, j) { txt(l, 1780 - 530, ny + 48 + j * 40, { size: 28, weight: 700 }); }); ctx.restore();
    }
    ctx.restore();
  };

  R.window = function (s, lt, d, T) {
    heading(s, lt);
    var x = 150, y = s.heading ? 270 : 170, w = 1620, h = 1000 - y - 30, side = s.sidebar ? 300 : 0;
    var k = P(lt, 0, 700); ctx.save(); ctx.globalAlpha *= k; ctx.translate(0, (1 - k) * 30);
    panel(x, y, w, h, { r: 18 }); ctx.save(); rr(x, y, w, h, 18); ctx.clip();
    ctx.fillStyle = C.bg1; ctx.fillRect(x, y, w, 46);
    for (var i = 0; i < 3; i++) { ctx.fillStyle = C.edge; ctx.beginPath(); ctx.arc(x + 26 + i * 22, y + 23, 6.5, 0, Math.PI * 2); ctx.fill(); }
    txt(s.title || "", x + w / 2, y + 31, { size: 20, color: C.muted, align: "center" });
    if (side) {
      ctx.fillStyle = C.bg1; ctx.fillRect(x, y + 46, side, h - 46);
      var yy = y + 100;
      (s.sidebar || []).forEach(function (it, i) {
        var label = typeof it === "string" ? it : it.label, on = it.active;
        if (on) { rr(x + 12, yy - 28, side - 24, 40, 8); ctx.fillStyle = C.panel2; ctx.fill(); }
        if (it.state) stateMark(x + 36, yy - 8, stateOf(it, lt, d), lt, 8);
        txt(label, x + (it.state ? 58 : 28), yy, { size: 22, weight: on ? 700 : 400, color: on ? C.ink : C.muted });
        yy += 44;
      });
    }
    var panes = s.panes || [], n = panes.length, gx = x + side + 12, gy = y + 58, gw = w - side - 24, gh = h - 70;
    var cols = n <= 1 ? 1 : 2, rows = Math.ceil(n / cols);
    panes.forEach(function (p, i) {
      var a = 300 + i * Math.min(900, d * .1), pk = P(lt, a, a + 600);
      sfxEv(a, "appear", { i: i }); (p.states || []).forEach(function (c0) { if ((c0.at || 0) > 0 && /^(done|blocked|working)$/.test(c0.state)) sfxEv(c0.at * d, c0.state); });
      if (pk <= 0) return;
      var c = i % cols, r = Math.floor(i / cols), pw = (gw - 10 * (cols - 1)) / cols, ph = (gh - 10 * (rows - 1)) / rows;
      if (n === 3 && i === 2) { pw = gw; }
      var px = gx + c * (pw + 10), py = gy + r * (ph + 10);
      ctx.save(); ctx.globalAlpha *= pk;
      rr(px, py, pw, ph, 10); ctx.fillStyle = C.code; ctx.fill(); ctx.strokeStyle = C.edge; ctx.lineWidth = 1.2; ctx.stroke();
      ctx.fillStyle = C.panel2; ctx.fillRect(px + 1, py + 1, pw - 2, 40);
      var st = stateOf(p, lt, d);
      stateMark(px + 24, py + 21, st, lt, 8);
      txt(p.title || "", px + 44, py + 29, { size: 21, weight: 700 });
      if (p.tag) { var tw1 = tw(p.tag, { size: 16, font: F.mono, weight: 600 }) + 18; rr(px + pw - tw1 - 12, py + 9, tw1, 24, 6); ctx.fillStyle = C.panel; ctx.fill();
        txt(p.tag, px + pw - 12 - tw1 / 2, py + 27, { size: 16, font: F.mono, weight: 600, color: C.accent2, align: "center" }); }
      var ls = p.lines || [], shown = ls.length * P(lt, a + 300, a + 300 + Math.max(1500, d * .5), function (q) { return q; });
      var maxL = Math.floor((ph - 60) / 30);
      ls.slice(0, Math.ceil(shown)).slice(-maxL).forEach(function (ln, j, arr) {
        var last = j === arr.length - 1 && shown < ls.length, frac = shown - Math.floor(shown);
        var col = /^[›$>]/.test(ln) ? C.codeInk : /✓/.test(ln) ? C.ok : /[✗?!]/.test(ln) ? C.warn : C.codeMuted;
        txt(last ? ln.slice(0, Math.floor(ln.length * frac)) : ln, px + 18, py + 74 + j * 30, { size: 19, font: F.mono, color: col });
      });
      ctx.restore();
    });
    (s.toasts || []).forEach(function (t0, i) {
      var a = (t0.at || .5) * d, tk = P(lt, a, a + 450, back) * (1 - P(lt, a + (t0.hold || 3200), a + (t0.hold || 3200) + 400));
      sfxEv(a, "toast");
      if (tk <= 0) return;
      var tw0 = 480, th = 96, tx = x + w - tw0 - 24 + (1 - tk) * 80, ty = y + 66 + i * 108;
      ctx.save(); ctx.globalAlpha *= tk; panel(tx, ty, tw0, th, { stroke: t0.kind === "blocked" ? C.warn : C.ok, lw: 2 });
      stateMark(tx + 38, ty + 36, t0.kind || "done", lt, 11);
      txt(t0.title || "", tx + 64, ty + 44, { size: 23, weight: 700 });
      if (t0.sub) txt(t0.sub, tx + 64, ty + 74, { size: 17, font: F.mono, color: C.muted });
      ctx.restore();
    });
    ctx.restore(); ctx.restore();
  };
  function stateOf(p, lt, d) {
    var st = p.state || "none";
    (p.states || []).forEach(function (c) { if (lt >= (c.at || 0) * d) st = c.state; });
    return st;
  }

  R.image = function (s, lt, d, T) {
    heading(s, lt);
    var img = IMGS[s.src]; if (!img || !img.complete || !img.naturalWidth) { txt("（画像）", 960, 560, { size: 30, color: C.muted, align: "center" }); return; }
    var y = s.heading ? 270 : 110, bh = (s.caption ? 880 : 940) - y, bw = 1680, iw = img.naturalWidth, ih = img.naturalHeight;
    var sc = Math.min(bw / iw, bh / ih), dw = iw * sc, dh = ih * sc, dx = 960 - dw / 2, dy = y + (bh - dh) / 2;
    var z = s.kenburns === false ? 1 : mix(1, 1.08, lt / d), k = P(lt, 0, 700);
    ctx.save(); ctx.globalAlpha *= k; rr(dx, dy, dw, dh, 14); ctx.clip();
    var zw = dw * z, zh = dh * z; ctx.drawImage(img, dx - (zw - dw) * (s.pan === "left" ? 1 : .5), dy - (zh - dh) * .5, zw, zh); ctx.restore();
    if (s.caption) txt(s.caption, 960, 960, { size: 30, color: C.muted, align: "center", alpha: P(lt, 600, 1200) });
  };

  R.end = function (s, lt, d, T) {
    if (s.variant === "credits") {   /* 掛け合いの動画の締め: 本編と同じ背景と立ち絵のまま、大きな一言と、小さな字のクレジット（輪の印は出さない。行が多くても画面に収める） */
      var bgi = IMGS[s.bg];
      if (bgi && bgi.complete && bgi.naturalWidth) { var bs = Math.max(W / bgi.naturalWidth, H / bgi.naturalHeight); ctx.drawImage(bgi, 960 - bgi.naturalWidth * bs / 2, 540 - bgi.naturalHeight * bs / 2, bgi.naturalWidth * bs, bgi.naturalHeight * bs); }
      ctx.fillStyle = "rgba(12,14,20,.58)"; ctx.fillRect(0, 0, W, H);
      var fam = TALK.font ? '"' + TALK.font + '",' + F.sans : F.sans, to = { size: 96, weight: 900, font: fam }, tk = P(lt, 150, 750, back);
      ctx.save(); ctx.globalAlpha *= clamp(tk); ctx.translate(960, 120); ctx.scale(.9 + .1 * tk, .9 + .1 * tk); ctx.translate(-960, -120);
      capLine(s.title || "", 960, 152, to, [[30, "#16161d"]], "#ffffff", "#ffe45c"); ctx.restore();
      var rows2 = (s.lines || []).map(function (r) { return typeof r === "string" ? r : r.text; }), PW = 1280, PH = 430, CWd = PW / 2 - 50, sz = 28, out = [], per = 1;
      for (; sz >= 16; sz -= 2) {   /* 2 段に組み、立ち絵の頭の上（y 660 まで）に収まる字の大きさを選ぶ */
        out = []; rows2.forEach(function (r) { wrap(r, CWd, { size: sz, weight: 600, font: fam }).forEach(function (l, i) { out.push((i ? "　" : "") + l); }); });
        per = Math.ceil(out.length / 2); if (per * sz * 1.5 <= PH - 50) break; }
      var lh = sz * 1.5, ph = per * lh + 50, py = 230, ck = P(lt, 500, 1100);
      ctx.save(); ctx.globalAlpha *= ck; rr(960 - PW / 2, py, PW, ph, 22); ctx.fillStyle = "rgba(0,0,0,.52)"; ctx.fill();
      out.forEach(function (l, i) { var col = i < per ? 0 : 1, row = col ? i - per : i;
        txt(l, 960 - PW / 2 + 34 + col * (PW / 2), py + 25 + sz + row * lh - sz * .15, { size: sz, weight: 600, color: "#f1f3f6", font: fam }); });
      ctx.restore();
      return;
    }
    /* 締め（掛け合いでない動画）: 上に大きな題と一文、下に行（コマンド・連絡先）。行が多くても画面に収め、題と重ねない。
       紋章は、台本が mark か markText を書いたときだけ、題の上に小さく出す（書かなければ出さない。前は題の頭の 1 字を輪の中に出していた） */
    var rows = s.lines || [], hasMark = !!(s.mark || s.markText), ty = hasMark ? 330 : 210;
    if (hasMark) emblem(s.mark || "ring", 960, 150, 84 * P(lt, 0, 800, back), lt * .00018, 1, s.markText || s.title);
    animText(s.title || "", 960, ty, { size: 96, weight: 800, align: "center", font: F.display }, animOf(s, "text"), lt, 150, 900);
    if (s.tagline) rich(s.tagline, 960, ty + 74, { size: 34, align: "center", color: C.accent, alpha: P(lt, 600, 1400) });
    var top = ty + (s.tagline ? 150 : 100), room = 900 - top;   /* 字幕（画面の下 1 割）と重ならないよう、下端は 900 まで */
    if (rows.length > 7) {   /* 行が多い（クレジット）: 小さな字の 2 段 */
      var texts = rows.map(function (r) { return typeof r === "string" ? r : r.text + (r.note ? " — " + r.note : ""); }), PW = 1400, sz = 28, out = [], per = 1;
      for (; sz >= 16; sz -= 2) { out = []; texts.forEach(function (r) { wrap(r, PW / 2 - 60, { size: sz, weight: 600 }).forEach(function (l, i2) { out.push((i2 ? "　" : "") + l); }); });
        per = Math.ceil(out.length / 2); if (per * sz * 1.5 <= room - 50) break; }
      var lh = sz * 1.5, ck = P(lt, 500, 1100);
      ctx.save(); ctx.globalAlpha *= ck; panel(960 - PW / 2, top, PW, per * lh + 50, { shadow: false, fill: C.panel });
      out.forEach(function (l, i3) { var col = i3 < per ? 0 : 1, row = col ? i3 - per : i3; txt(l, 960 - PW / 2 + 36 + col * (PW / 2), top + 25 + sz + row * lh - sz * .15, { size: sz, weight: 600, color: C.ink }); });
      ctx.restore();
    } else {
      var step = Math.min(96, room / Math.max(1, rows.length)), k2 = step / 96, fs = Math.max(20, 32 * k2);
      rows.forEach(function (r, i) {
        sfxEv(500 + i * 250, "appear", { i: i });
        var k = P(lt, 500 + i * 250, 1000 + i * 250); if (k <= 0) return;
        var text = typeof r === "string" ? r : r.text, note = r.note, mono = r.mono !== false && /^[$>]/.test(text), y = top + step * .55 + i * step;
        ctx.save(); ctx.globalAlpha *= k;
        var w = Math.min(1700, Math.max(900, tw(text, { size: fs, font: mono ? F.mono : F.sans, weight: 600 }) + (note ? tw(note, { size: fs * .75 }) + 80 : 60)));
        panel(960 - w / 2, y - step * .52, w, step * .77, { shadow: false, fill: C.panel });
        txt(text, 960 - w / 2 + 30, y, { size: fs, font: mono ? F.mono : F.sans, weight: 600, color: mono ? C.accent2 : C.ink });
        if (note) txt(note, 960 + w / 2 - 30, y - 2, { size: fs * .75, color: C.muted, align: "right" });
        ctx.restore();
      });
    }
  };

  /* ---------- 追加の部品 ---------- */
  R.cards = function (s, lt, d) {
    heading(s, lt);
    var items = s.items || [], n = items.length, cols = s.cols || (n <= 3 ? n : n === 4 ? 2 : 3), rows = Math.ceil(n / cols);
    var y0 = s.heading ? 290 : 190, gap = 32, cw = (1680 - gap * (cols - 1)) / cols, chh = Math.min(300, (880 - y0 - gap * (rows - 1)) / rows);
    var at = slots(n, d, 500, Math.max(1200, d * .35));
    items.forEach(function (it, i) {
      var c = i % cols, r = Math.floor(i / cols), x = 120 + c * (cw + gap), y = y0 + r * (chh + gap), k = P(lt, at[i], at[i] + 600, back);
      sfxEv(at[i], "appear", { i: i });
      if (k <= 0) return;
      ctx.save(); ctx.translate(x + cw / 2, y + chh / 2); ctx.scale(k, k); ctx.translate(-cw / 2, -chh / 2);
      panel(0, 0, cw, chh, {}); ctx.fillStyle = accentAt(i); ctx.fillRect(0, 0, cw, 6);
      var ix = 40; if (it.icon) { icon(it.icon, 58, 68, 48, accentAt(i), P(lt, at[i] + 150, at[i] + 1000), lt); ix = 104; }
      txt(it.title || "", ix, 84, { size: 42, weight: 800, color: accentAt(i) });
      wrap(it.text || "", cw - 80, { size: 32 }).slice(0, Math.floor((chh - 130) / 44)).forEach(function (ln, j) { rich(ln, 40, 156 + j * 44, { size: 32, color: C.muted }); });
      ctx.restore();
    });
  };
  R.timeline = function (s, lt, d) {
    heading(s, lt);
    var items = s.items || [], n = items.length, x0 = 170, x1 = 1750, y = s.heading ? 560 : 520;
    var at = slots(n, d, 900, Math.max(900, d * .2)), cur = -1; at.forEach(function (a, i) { if (lt >= a) cur = i; });
    ctx.save(); ctx.strokeStyle = C.edge; ctx.lineWidth = 6; ctx.lineCap = "round";
    ctx.beginPath(); ctx.moveTo(x0, y); ctx.lineTo(mix(x0, x1, P(lt, 0, 900, eio)), y); ctx.stroke(); ctx.restore();
    items.forEach(function (it, i) {
      var x = n > 1 ? mix(x0 + 60, x1 - 60, i / (n - 1)) : 960, k = P(lt, at[i], at[i] + 600, back), up = i % 2 === 0, act = i === cur;
      sfxEv(at[i], it.highlight ? "emphasize" : "tick", { i: i });
      if (k <= 0) return;
      ctx.save(); ctx.fillStyle = it.highlight || act ? C.accent : accentAt(i); ctx.beginPath(); ctx.arc(x, y, (act ? 18 : 13) * k, 0, Math.PI * 2); ctx.fill();
      if (it.highlight) { ctx.globalAlpha = .3 + .3 * Math.sin(lt / 260); ctx.beginPath(); ctx.arc(x, y, 30, 0, Math.PI * 2); ctx.fill(); }
      ctx.restore();
      var ty = up ? y - 70 : y + 90, a2 = P(lt, at[i] + 150, at[i] + 700);
      ctx.save(); ctx.strokeStyle = C.edge; ctx.lineWidth = 2; ctx.globalAlpha *= a2; ctx.beginPath(); ctx.moveTo(x, y + (up ? -20 : 20)); ctx.lineTo(x, up ? ty + 16 : ty - 44); ctx.stroke(); ctx.restore();
      txt(it.date || "", x, up ? ty - 70 : ty, { size: 30, weight: 800, align: "center", color: act ? C.accent : C.ink, alpha: a2, font: F.display });
      wrap(it.label || "", 300, { size: 26, weight: 700 }).slice(0, 2).forEach(function (ln, j) { txt(ln, x, (up ? ty - 30 : ty + 40) + j * 34, { size: 26, weight: 700, align: "center", alpha: a2 * (act || cur < 0 ? 1 : .75) }); });
      if (it.sub) txt(it.sub, x, (up ? ty + 36 : ty + 110), { size: 21, align: "center", color: C.muted, alpha: a2 });
    });
  };
  R.chat = function (s, lt, d) {
    heading(s, lt);
    var msgs = s.messages || [], at = slots(msgs.length, d, 700, 900), y0 = s.heading ? 280 : 170, bottom = 880, bubbles = [];
    msgs.forEach(function (m, i) {
      /* 右: 自分（user・me・side:right）。左: 相手。side を書けばそれに従う */
      var right = m.side ? m.side === "right" : /^(user|me|自分|ユーザー)$/i.test(m.from || "");
      var lines = wrap(m.text || "", 900, { size: 30 }), h = lines.length * 42 + 36 + (m.from ? 30 : 0);
      bubbles.push({ m: m, right: right, lines: lines, h: h, a: at[i] }); sfxEv(at[i], right ? "send" : "message");
    });
    var total = 0, shown = [];
    bubbles.forEach(function (b) { if (lt >= b.a - 700) shown.push(b); });
    shown.forEach(function (b) { total += b.h + 26; });
    var y = Math.min(y0, bottom - total);
    shown.forEach(function (b, i) {
      var typing = lt < b.a, k = typing ? 1 : P(lt, b.a, b.a + 450, back);
      var w = typing ? 130 : Math.max.apply(null, b.lines.map(function (l) { return tw(l.replace(/\*\*/g, ""), { size: 30 }); }).concat([tw(b.m.from || "", { size: 20 })])) + 56;
      var h = typing ? 70 : b.h, x = b.right ? 1780 - w : 140;
      ctx.save(); ctx.translate(x + (b.right ? w : 0), y); ctx.scale(k, k); ctx.translate(-(b.right ? w : 0), 0);
      rr(0, 0, w, h, 26); ctx.fillStyle = b.right ? C.accent : C.panel; ctx.fill();
      if (!b.right) { ctx.strokeStyle = C.edge; ctx.lineWidth = 1.5; ctx.stroke(); }
      var ink = b.right ? C.onAccent : C.ink;
      if (typing) { for (var j = 0; j < 3; j++) { ctx.fillStyle = ink; ctx.globalAlpha = .35 + .65 * Math.max(0, Math.sin(lt / 160 - j * .9)); ctx.beginPath(); ctx.arc(40 + j * 26, 35, 8, 0, Math.PI * 2); ctx.fill(); } }
      else {
        var ty = 50; if (b.m.from) { txt(b.m.from, 28, 38, { size: 20, weight: 700, color: b.right ? ink : C.accent2 }); ty = 80; }
        b.lines.forEach(function (ln, j) { rich(ln, 28, ty + j * 42, { size: 30, color: ink, emColor: b.right ? ink : C.accent }, b.right ? 1 : undefined); });
      }
      ctx.restore();
      y += (typing ? 70 : b.h) + 26;
    });
  };
  function niceMax(v) { if (v <= 0) return 1; var e = Math.pow(10, Math.floor(Math.log10(v))); var ms = [1, 2, 2.5, 5, 10]; for (var i = 0; i < ms.length; i++) if (v <= ms[i] * e) return ms[i] * e; return 10 * e; }
  R.line = function (s, lt, d) {
    heading(s, lt);
    var labels = s.labels || [], series = s.series || [], all = []; series.forEach(function (se) { all = all.concat(se.values); });
    var lo = s.min || 0, hi = niceMax(Math.max.apply(null, all) - lo) + lo, L = 220, Rr = 1700, T0 = s.heading ? 300 : 200, B = 850;
    var X = function (i) { return L + (Rr - L) * i / Math.max(1, labels.length - 1); }, Y = function (v) { return B - (B - T0) * (v - lo) / (hi - lo || 1); };
    var gk = P(lt, 0, 700);
    for (var g = 0; g <= 4; g++) { var gv = lo + (hi - lo) * g / 4, gy = Y(gv);
      ctx.save(); ctx.globalAlpha *= gk; ctx.strokeStyle = C.edge; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(L, gy); ctx.lineTo(Rr, gy); ctx.stroke(); ctx.restore();
      txt(fmtNum(String(Math.round(gv)), 1), L - 20, gy + 8, { size: 22, color: C.muted, align: "right", alpha: gk }); }
    labels.forEach(function (lb, i) { txt(lb, X(i), B + 44, { size: 24, color: C.muted, align: "center", alpha: gk }); });
    series.forEach(function (se, si) {
      var a = 700 + si * 500, k = P(lt, a, a + Math.max(1400, d * .35), function (x) { return x; }), col = accentAt(si), n = se.values.length;
      sfxEv(a, "grow", { i: si }); sfxEv(a + Math.max(1400, d * .35), "countEnd", { i: si });
      var upto = k * (n - 1);
      ctx.save(); ctx.strokeStyle = col; ctx.lineWidth = 6; ctx.lineJoin = "round"; ctx.lineCap = "round"; ctx.beginPath();
      for (var i = 0; i <= Math.floor(upto); i++) { var px = X(i), py = Y(se.values[i]); i ? ctx.lineTo(px, py) : ctx.moveTo(px, py); }
      var fi = Math.floor(upto); if (fi < n - 1) { var f = upto - fi; ctx.lineTo(mix(X(fi), X(fi + 1), f), mix(Y(se.values[fi]), Y(se.values[fi + 1]), f)); }
      ctx.stroke(); ctx.restore();
      for (var j = 0; j <= Math.floor(upto); j++) { ctx.save(); ctx.fillStyle = C.bg1; ctx.strokeStyle = col; ctx.lineWidth = 4; ctx.beginPath(); ctx.arc(X(j), Y(se.values[j]), 9, 0, Math.PI * 2); ctx.fill(); ctx.stroke(); ctx.restore(); }
      if (k >= 1) { var lv = se.values[n - 1]; txt(fmtNum(String(lv) + (s.unit || ""), P(lt, a + Math.max(1400, d * .35), a + Math.max(1400, d * .35) + 900)), X(n - 1) + 22, Y(lv) + 10, { size: 34, weight: 800, color: col, font: F.display }); }
      if (series.length > 1) { txt("● " + (se.name || ""), L + si * 260, T0 - 30, { size: 24, weight: 700, color: col, alpha: gk }); }
    });
  };
  R.donut = function (s, lt, d) {
    heading(s, lt);
    var items = s.items || [], total = items.reduce(function (a, it) { return a + (+it.value); }, 0) || 1;
    var cx = 700, cy = s.heading ? 580 : 540, rad = 250, sw = 90, a = -Math.PI / 2, k = P(lt, 400, 400 + Math.max(1600, d * .35), eio);
    var sweep = k * Math.PI * 2; sfxEv(400, "sweep");
    items.forEach(function (it, i) {
      sfxEv(800 + i * 300, "appear", { i: i });
      var frac = (+it.value) / total, a1 = a + frac * Math.PI * 2, e = Math.min(a1, -Math.PI / 2 + sweep);
      if (e > a) { ctx.save(); ctx.strokeStyle = accentAt(i); ctx.lineWidth = sw; ctx.beginPath(); ctx.arc(cx, cy, rad, a + .012, Math.max(a + .012, e - .012)); ctx.stroke(); ctx.restore(); }
      var lk = P(lt, 800 + i * 300, 1300 + i * 300), ly = cy - (items.length - 1) * 50 + i * 100;
      ctx.save(); ctx.globalAlpha *= lk; ctx.fillStyle = accentAt(i); rr(1080, ly - 22, 30, 30, 6); ctx.fill(); ctx.restore();
      txt(it.label || "", 1130, ly + 2, { size: 32, weight: 700, alpha: lk });
      txt(Math.round(100 * frac) + "%", 1720, ly + 2, { size: 34, weight: 800, color: accentAt(i), align: "right", alpha: lk, font: F.display });
      a = a1;
    });
    var cvv = s.center ? s.center.value : total.toLocaleString("en-US") + (s.unit || ""), cl = s.center ? s.center.label : "合計";
    txt(fmtNum(cvv, k), cx, cy + 16, { size: 64, weight: 800, align: "center", font: F.display });
    txt(cl || "", cx, cy + 62, { size: 26, align: "center", color: C.muted });
  };
  R.table = function (s, lt, d) {
    heading(s, lt);
    var cols = s.columns || [], rows = s.rows || [], n = rows.length, y0 = s.heading ? 290 : 190, rh = Math.min(92, (880 - y0 - 80) / Math.max(1, n));
    var FS = Math.max(24, Math.min(36, rh * .42));
    var cw = cols.map(function (c, i) { var m = tw(String(c), { size: FS, weight: 800 }); rows.forEach(function (r) { m = Math.max(m, tw(String(r[i] == null ? "" : r[i]), { size: FS })); }); return m + 80; });
    var sum = cw.reduce(function (a, b) { return a + b; }, 0), sc = Math.min(1680 / sum, Math.max(1, 1100 / sum)); cw = cw.map(function (w) { return w * sc; });
    var tot = cw.reduce(function (a, b) { return a + b; }, 0), x0 = 960 - tot / 2;
    var hl = s.highlight || [], hat = slots(hl.length, d, 900 + n * 200, 800), cur = -1; hat.forEach(function (a, i) { if (lt >= a) cur = hl[i]; sfxEv(a, "emphasize", { i: i }); });
    var num = cols.map(function (c, i) { return rows.every(function (r) { return /^[-+]?[¥$€]?[\d,.]+\s*[%％a-zA-Z一-龠ぁ-んァ-ヶ]{0,3}$/.test(String(r[i] || "0")); }); });
    var hk = P(lt, 0, 500);
    ctx.save(); ctx.globalAlpha *= hk; rr(x0, y0, tot, FS * 2.3, 12); ctx.fillStyle = C.panel2; ctx.fill(); ctx.restore();
    var x = x0; cols.forEach(function (c, i) { txt(String(c), num[i] ? x + cw[i] - 36 : x + 36, y0 + FS * 1.5, { size: FS, weight: 800, align: num[i] ? "right" : "left", alpha: hk }); x += cw[i]; });
    rows.forEach(function (r, j) {
      var a = 500 + j * Math.min(220, d * .03), k = P(lt, a, a + 450), y = y0 + FS * 2.3 + 8 + j * rh;
      sfxEv(a, "row", { i: j });
      if (k <= 0) return;
      ctx.save(); ctx.globalAlpha *= k; ctx.translate(0, (1 - k) * 12);
      if (cur === j) { rr(x0, y, tot, rh - 6, 10); ctx.fillStyle = C.accent; ctx.globalAlpha *= .18; ctx.fill(); ctx.globalAlpha /= .18; ctx.strokeStyle = C.accent; ctx.lineWidth = 2; ctx.stroke(); }
      else { ctx.strokeStyle = C.edge; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(x0, y + rh - 3); ctx.lineTo(x0 + tot, y + rh - 3); ctx.stroke(); }
      var xx = x0; cols.forEach(function (c, i) { txt(String(r[i] == null ? "" : r[i]), num[i] ? xx + cw[i] - 36 : xx + 36, y + rh / 2 + FS * .35, { size: FS, weight: cur === j ? 800 : 400, align: num[i] ? "right" : "left", color: cur === j ? C.ink : (i === 0 ? C.ink : C.muted) }); xx += cw[i]; });
      ctx.restore();
    });
  };
  R.quote = function (s, lt, d) {
    var lines = wrap(s.text || "", 1400, { size: 54, weight: 700, font: F.display }), n = lines.length, lh = 80, y0 = 540 - (n - 1) * lh / 2 - 20;
    txt("“", 240, y0 - 40, { size: 260, weight: 800, color: C.accent, alpha: P(lt, 0, 800) * .8, font: F.display });
    var at = slots(n, d * .6, 400, 0); sfxEv(0, "quote");
    lines.forEach(function (ln, i) { animText(ln, 360, y0 + i * lh, { size: 54, weight: 700, font: F.display }, animOf(s, "text"), lt, at[i], 700, P(lt, at[i] + 400, at[i] + 1100)); });
    var bk = P(lt, d * .55, d * .55 + 800); if (s.by) sfxEv(d * .55, "appear", { i: 0 });
    ctx.save(); ctx.globalAlpha *= bk; ctx.fillStyle = C.accent; ctx.fillRect(360, y0 + n * lh + 10, 60, 4); ctx.restore();
    if (s.by) txt(s.by, 440, y0 + n * lh + 26, { size: 32, weight: 800, alpha: bk });
    if (s.role) txt(s.role, 440, y0 + n * lh + 70, { size: 24, color: C.muted, alpha: bk });
  };
  R.kinetic = function (s, lt, d) {
    var text = s.text || "", toks = [], re = /\*\*([^*]+)\*\*|([^\s*]+)/g, m;
    while ((m = re.exec(text))) toks.push({ w: m[1] || m[2], em: !!m[1] });
    if (toks.length === 1 && /[^\x00-\x7f]/.test(toks[0].w)) { toks = toks[0].w.split(/(?<=[、。，．！？])/).map(function (w) { return { w: w, em: false }; }); }
    var size = s.size || 92, lines = [[]], lw = 0, gap = size * .32, maxW = 1600;
    toks.forEach(function (t0) { var w = tw(t0.w, { size: t0.em ? size * 1.12 : size, weight: 800, font: F.display }); if (lw + w > maxW && lines[lines.length - 1].length) { lines.push([]); lw = 0; } t0.width = w; lines[lines.length - 1].push(t0); lw += w + gap; });
    var total = toks.length, per = Math.min(420, (d * .6) / Math.max(1, total)), idx = 0, lh = size * 1.35, y0 = 540 - (lines.length - 1) * lh / 2 + size * .35;
    lines.forEach(function (ln, li) {
      var wsum = ln.reduce(function (a, t0) { return a + t0.width; }, 0) + gap * (ln.length - 1), x = 960 - wsum / 2;
      ln.forEach(function (t0) {
        var a = 300 + idx * per, k = P(lt, a, a + 520, back), sz = t0.em ? size * 1.12 : size, wa = s.anim || (MS.text === "rise" ? "pop" : MS.text);
        sfxEv(a, t0.em ? "hit" : "word", { i: idx }); if (t0.em && (wa === "slam" || SPEC.motion === "dynamic")) shakeEv(a + 220, 9, 320);
        if (wa !== "pop") animText(t0.w, x + t0.width / 2, y0 + li * lh, { size: sz, weight: 800, align: "center", font: F.display, color: t0.em ? C.accent : C.ink }, wa, lt, a, 520);
        else if (k > 0) { ctx.save(); ctx.translate(x + t0.width / 2, y0 + li * lh); ctx.scale(k, k);
          txt(t0.w, 0, (1 - Math.min(1, k)) * 30, { size: sz, weight: 800, align: "center", font: F.display, color: t0.em ? C.accent : C.ink });
          if (t0.em) { ctx.fillStyle = C.accent; ctx.fillRect(-t0.width / 2, sz * .2, t0.width * P(lt, a + 300, a + 800), Math.max(4, sz * .07)); }
          ctx.restore(); }
        x += t0.width + gap; idx++;
      });
    });
  };
  R.split = function (s, lt, d) {
    heading(s, lt);
    var y0 = s.heading ? 300 : 200, k = P(lt, 0, 700), L = s.left || {};
    ctx.save(); ctx.globalAlpha *= k; ctx.translate((1 - k) * -40, 0);
    var y = y0;
    if (L.title) { wrap(L.title, 720, { size: 48, weight: 800, font: F.display }).forEach(function (ln) { txt(ln, 120, y + 40, { size: 48, weight: 800, font: F.display }); y += 64; }); y += 20; }
    if (L.text) { wrap(L.text, 720, { size: 30 }).forEach(function (ln) { rich(ln, 120, y + 30, { size: 30, color: C.muted }); y += 44; }); y += 16; }
    var pts = L.points || [], at = slots(pts.length, d, 700, d * .3);
    pts.forEach(function (p, i) { sfxEv(at[i], "appear", { i: i }); var pk = P(lt, at[i], at[i] + 500); if (pk <= 0) return;
      ctx.save(); ctx.globalAlpha *= pk; ctx.fillStyle = accentAt(i); ctx.beginPath(); ctx.arc(136, y + 22, 8, 0, Math.PI * 2); ctx.fill(); ctx.restore();
      wrap(p, 680, { size: 30 }).forEach(function (ln, j) { rich(ln, 164, y + 32 + j * 42, { size: 30, alpha: pk }); }); y += wrap(p, 680, { size: 30 }).length * 42 + 18; });
    ctx.restore();
    if (s.right && R[s.right.type] && s.right.type !== "split") {
      var sub2 = s._rightSpec || (s._rightSpec = Object.assign({}, s.right, { heading: "" }));
      ctx.save(); ctx.globalAlpha *= P(lt, 300, 1000); ctx.translate(820, y0 - 120); ctx.scale(.58, .58);
      EVOFF += 300; try { R[sub2.type](sub2, Math.max(0, lt - 300), d - 300); drawOverlays(sub2, Math.max(0, lt - 300), d - 300); } finally { EVOFF -= 300; } ctx.restore();
    }
  };
  R.beforeafter = function (s, lt, d) {
    heading(s, lt);
    var y0 = s.heading ? 280 : 180, x0 = 140, w = 1640, h = 900 - y0, bf = s.before || {}, af = s.after || {};
    var u = P(lt, d * .35, d * .35 + Math.max(1400, d * .25), eio), sx = x0 + w * u; sfxEv(d * .35, "reveal");
    function side(o, tone, ax) {
      var col = tone === "good" ? C.ok : tone === "bad" ? C.warn : C.accent2;
      panel(x0, y0, w, h, { stroke: col, lw: 2.5, shadow: false });
      txt(o.label || (tone === "good" ? "After" : "Before"), ax, y0 + 64, { size: 30, weight: 800, color: col, align: ax > 960 ? "right" : "left" });
      if (o.title) txt(o.title, 960, y0 + 170, { size: 56, weight: 800, align: "center", font: F.display });
      (o.points || []).forEach(function (p, i) { rich(p, 960, y0 + 260 + i * 62, { size: 34, align: "center", color: C.muted }); });
      if (o.value) txt(o.value, 960, y0 + h - 70, { size: 90, weight: 800, align: "center", color: col, font: F.display });
    }
    ctx.save(); ctx.globalAlpha *= P(lt, 0, 600); side(bf, bf.tone || "bad", x0 + 40); ctx.restore();
    if (u > 0) { ctx.save(); ctx.beginPath(); ctx.rect(x0, y0 - 4, sx - x0, h + 8); ctx.clip(); rr(x0, y0, w, h, 16); ctx.fillStyle = C.bg1; ctx.fill(); side(af, af.tone || "good", x0 + w - 40); ctx.restore();
      if (u < 1) { ctx.fillStyle = C.accent; ctx.fillRect(sx - 3, y0 - 20, 6, h + 40); ctx.beginPath(); ctx.arc(sx, y0 + h / 2, 22, 0, Math.PI * 2); ctx.fill();
        txt("⇆", sx, y0 + h / 2 + 10, { size: 26, weight: 800, align: "center", color: C.onAccent }); } }
  };

  /* ---------- アイコンの格子 ---------- */
  R.icons = function (s, lt, d) {
    heading(s, lt);
    var items = s.items || [], n = items.length, cols = s.cols || Math.min(n, n <= 4 ? n : n <= 6 ? 3 : 4), rows = Math.ceil(n / cols);
    var y0 = s.heading ? 300 : 200, cw = 1600 / cols, ch = Math.min(320, (860 - y0) / rows), at = slots(n, d, 500, Math.max(1200, d * .35));
    items.forEach(function (it, i) {
      sfxEv(at[i], "appear", { i: i });
      var c = i % cols, r = Math.floor(i / cols), cx = 160 + cw * (c + .5), cy = y0 + ch * r + ch * .38, k = P(lt, at[i], at[i] + 500, back);
      if (k <= 0) return;
      ctx.save(); ctx.globalAlpha *= clamp(k * 2); ctx.fillStyle = accentAt(i); ctx.globalAlpha *= .14;
      ctx.beginPath(); ctx.arc(cx, cy, 78 * k, 0, Math.PI * 2); ctx.fill(); ctx.restore();
      if (!drawIcon(it.icon, cx, cy, 84, { color: accentAt(i), k: P(lt, at[i] + 100, at[i] + 1100), lt: lt, width: 1.8 })) icon(it.icon, cx, cy, 80);
      txt(it.label || "", cx, cy + 128, { size: 34, weight: 800, align: "center", alpha: P(lt, at[i] + 300, at[i] + 800) });
      if (it.text) txt(it.text, cx, cy + 172, { size: 24, align: "center", color: C.muted, alpha: P(lt, at[i] + 450, at[i] + 950) });
    });
  };
  /* ---------- 動きの強い部品 ---------- */
  R.impact = function (s, lt, d) {
    var hit = 350; sfxEv(hit, "hit"); shakeEv(hit, s.shake === undefined ? 22 : s.shake, 520);
    var sp = clamp(1 - lin(lt, hit + 250, hit + 1500)); if (sp > 0) { ctx.save(); ctx.globalAlpha *= sp; drawFx(["speedlines"], lt * 2.2, d, "under"); ctx.restore(); }
    burstAt(960, 470, lt - hit, { n: 40, seed: s.seed || 3 });
    animText(s.text || "", 960, 530, { size: s.size || 150, weight: 900, align: "center", font: F.display, color: s.tone === "accent" ? C.accent : C.ink }, s.anim || "slam", lt, hit - 250, 520);
    if (s.sub) animText(s.sub, 960, 650, { size: 42, weight: 700, align: "center", color: C.accent }, "rise", lt, hit + 600, 600);
  };
  R.countdown = function (s, lt, d) {
    var from = s.from || 3, a0 = 300, seg = Math.max(500, Math.min(1000, (d - 1800) / from)), goA = a0 + from * seg, i;
    for (i = 0; i < from; i++) { sfxEv(a0 + i * seg, "tick", { i: i }); shakeEv(a0 + i * seg + 120, 6 + i * 3, 260); }
    if (s.label) { sfxEv(goA, "hit"); shakeEv(goA + 150, 18, 450); }
    var ci = Math.floor((lt - a0) / seg);
    if (lt >= a0 && ci < from) {
      var local = lt - a0 - ci * seg, q = local / seg, n = from - ci, e = lin(local, 0, 260);
      ctx.save(); ctx.lineCap = "round"; ctx.strokeStyle = C.edge; ctx.lineWidth = 14; ctx.beginPath(); ctx.arc(960, 480, 260, 0, Math.PI * 2); ctx.stroke();
      ctx.strokeStyle = accentAt(ci); ctx.beginPath(); ctx.arc(960, 480, 260, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * eo(q)); ctx.stroke();
      var rk = lin(local, 100, 800); if (rk > 0 && rk < 1) { ctx.globalAlpha = (1 - rk) * .6; ctx.lineWidth = 6; ctx.strokeStyle = accentAt(ci); ctx.beginPath(); ctx.arc(960, 480, 260 + rk * 360, 0, Math.PI * 2); ctx.stroke(); }
      ctx.restore();
      var sc = mix(2.3, 1, eo(e)) * (1 - .1 * lin(local, seg * .6, seg));
      ctx.save(); ctx.translate(960, 480); ctx.scale(sc, sc); ctx.globalAlpha *= clamp(e * 3) * (1 - lin(local, seg * .82, seg));
      txt(String(n), 0, 110, { size: 320, weight: 900, align: "center", font: F.display }); ctx.restore();
    }
    if (s.label && lt >= goA - 200) { burstAt(960, 470, lt - goA, { n: 44, seed: 9 });
      animText(s.label, 960, 530, { size: s.size || 150, weight: 900, align: "center", font: F.display, color: C.accent }, "slam", lt, goA - 200, 460);
      if (s.sub) animText(s.sub, 960, 650, { size: 40, weight: 700, align: "center", color: C.muted }, "rise", lt, goA + 500, 600); }
  };
  R.orbit = function (s, lt, d) {
    heading(s, lt);
    var items = s.items || [], n = items.length, cx = 960, cy = s.heading ? 590 : 540, rx = s.rx || 600, ry = s.ry || 250;
    var at = slots(n, d, 900, Math.max(1500, d * .35)), spin = lt * (s.speed === undefined ? 1 : s.speed) * .00009 - Math.PI / 2;
    items.forEach(function (it, i) { sfxEv(at[i], "appear", { i: i }); });
    var ek = P(lt, 200, 1100, eio);
    ctx.save(); ctx.strokeStyle = C.edge; ctx.lineWidth = 2; ctx.setLineDash([8, 12]); ctx.beginPath(); ctx.ellipse(cx, cy, Math.max(1, rx * ek), Math.max(1, ry * ek), 0, 0, Math.PI * 2); ctx.stroke(); ctx.restore();
    var pos = items.map(function (it, i) { var an = spin + i * Math.PI * 2 / Math.max(1, n); return { x: cx + Math.cos(an) * rx, y: cy + Math.sin(an) * ry, z: Math.sin(an) }; });
    var order = items.map(function (_, i) { return i; }).sort(function (a, b) { return pos[a].z - pos[b].z; });
    items.forEach(function (it, i) { var k = P(lt, at[i], at[i] + 600); if (k <= 0) return;
      ctx.save(); ctx.strokeStyle = accentAt(i); ctx.globalAlpha *= .35 * k; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(pos[i].x, pos[i].y); ctx.stroke();
      var u = ((lt - at[i]) / 1600) % 1; ctx.globalAlpha = k; ctx.fillStyle = accentAt(i); ctx.beginPath(); ctx.arc(mix(cx, pos[i].x, u), mix(cy, pos[i].y, u), 6, 0, Math.PI * 2); ctx.fill(); ctx.restore(); });
    var draw1 = function (i) { var it = items[i], k = P(lt, at[i], at[i] + 600, back); if (k <= 0) return;
      var p = pos[i], dep = .78 + .22 * (p.z + 1) / 2, label = typeof it === "string" ? it : it.label, sub = it.sub, w = Math.max(tw(label, { size: 30, weight: 800 }), sub ? tw(sub, { size: 20 }) : 0) + 60, h = sub ? 96 : 70;
      ctx.save(); ctx.translate(p.x, p.y); ctx.scale(k * dep, k * dep); ctx.globalAlpha *= .55 + .45 * dep;
      var ix = it.icon ? 26 : 0; if (ix) w += 52;
      panel(-w / 2, -h / 2, w, h, { r: h / 2, stroke: accentAt(i), lw: 2.5 }); if (it.icon) icon(it.icon, -w / 2 + 40, -2, 32, accentAt(i), P(lt, at[i] + 150, at[i] + 900), lt);
      txt(label, ix, sub ? -4 : 11, { size: 30, weight: 800, align: "center" }); if (sub) txt(sub, ix, 28, { size: 20, align: "center", color: C.muted }); ctx.restore(); };
    order.filter(function (i) { return pos[i].z < 0; }).forEach(draw1);
    var ck = P(lt, 300, 1000, back), c = s.center || {}, cl = typeof c === "string" ? c : c.label || "";
    if (ck > 0) { ctx.save(); ctx.translate(cx, cy); ctx.scale(ck, ck); ctx.fillStyle = C.accent; ctx.beginPath(); ctx.arc(0, 0, 110, 0, Math.PI * 2); ctx.fill();
      ctx.globalAlpha *= .25 + .15 * Math.sin(lt / 400); ctx.beginPath(); ctx.arc(0, 0, 130 + 8 * Math.sin(lt / 400), 0, Math.PI * 2); ctx.fill(); ctx.globalAlpha = 1;
      txt(cl, 0, c.sub ? 4 : 14, { size: 36, weight: 800, align: "center", color: C.onAccent, font: F.display }); if (c.sub) txt(c.sub, 0, 40, { size: 20, align: "center", color: C.onAccent }); ctx.restore(); }
    order.filter(function (i) { return pos[i].z >= 0; }).forEach(draw1);
  };
  R.logo = function (s, lt, d) {
    var cy = 390, R0 = 150, asm = 1400, r = rand(s.seed || 21), N = 28, i;
    sfxEv(0, "title"); sfxEv(asm, "hit"); shakeEv(asm, 10, 420);
    for (i = 0; i < N; i++) {
      var an = i / N * Math.PI * 2, tx = 960 + Math.cos(an) * R0 * .95, ty = cy + Math.sin(an) * R0 * .95, sx = 960 + (r() - .5) * 2800, sy = cy + (r() - .5) * 1700, r0 = (r() - .5) * 10;
      var k = eio(lin(lt, 100 + i * 20, asm)), fade = 1 - lin(lt, asm, asm + 300); if (k <= 0 || fade <= 0) continue;
      ctx.save(); ctx.globalAlpha *= .9 * fade; ctx.translate(mix(sx, tx, k), mix(sy, ty, k)); ctx.rotate(mix(r0, an, k)); ctx.fillStyle = accentAt(i);
      ctx.beginPath(); ctx.moveTo(0, -16); ctx.lineTo(14, 12); ctx.lineTo(-14, 12); ctx.closePath(); ctx.fill(); ctx.restore();
    }
    var ek = P(lt, asm - 120, asm + 500, back); emblem(s.mark || "ring", 960, cy, R0 * ek, lt * .00015, clamp(ek * 1.5), s.markText || s.title);
    burstAt(960, cy, lt - asm, { n: 52, seed: 5, r: 560 });
    var ta = animOf(s, "title"), to = { size: 110, weight: 800, align: "center", font: F.display };
    animText(s.title || "", 960, 720, to, ta, lt, asm + 200, 900);
    var sw = lin(lt, asm + 1400, asm + 2400);
    if (sw > 0 && sw < 1) { var tw0 = tw(s.title || "", to), gx = 960 - tw0 / 2 - 200 + sw * (tw0 + 400), g = ctx.createLinearGradient(gx - 120, 0, gx + 120, 0);
      g.addColorStop(0, "rgba(255,255,255,0)"); g.addColorStop(.5, "rgba(255,255,255,.85)"); g.addColorStop(1, "rgba(255,255,255,0)"); txt(s.title || "", 960, 720, Object.assign({}, to, { color: g })); }
    if (s.subtitle) animText(s.subtitle, 960, 806, { size: 42, weight: 700, align: "center", color: C.accent, spacing: 6 }, "rise", lt, asm + 1100, 700);
  };
  R.marquee = function (s, lt, d) {
    var rows = s.rows || [[s.text || ""]], n = rows.length, gap = s.gap || 170, y0 = 540 - (n - 1) * gap / 2, size = s.size || 120;
    rows.forEach(function (row, i) {
      var str = (Array.isArray(row) ? row : [row]).join("  ·  ") + "  ·  ", o = { size: size, weight: 900, font: F.display }, w = Math.max(200, tw(str, o));
      var dir = i % 2 ? 1 : -1, sp = (s.speed || 1) * (.12 + .035 * i), off = (lt * sp) % w, x = dir < 0 ? -off : off - w, col = i % 2 ? C.accent : C.ink, outline = s.outline !== false && i % 2 === 1;
      ctx.save(); ctx.globalAlpha *= P(lt, i * 150, i * 150 + 600) * (s.caption ? .45 : 1);
      for (var xx = x; xx < W; xx += w) {
        if (outline) { ctx.font = font(o); ctx.lineWidth = 3; ctx.strokeStyle = col; ctx.strokeText(str, xx, y0 + i * gap + size * .35); }
        else txt(str, xx, y0 + i * gap + size * .35, Object.assign({}, o, { color: col }));
      }
      ctx.restore();
    });
    if (s.caption) { sfxEv(600, "appear"); var ck = P(lt, 600, 1200, back), cw = tw(s.caption, { size: 72, weight: 800 }) + 120;
      ctx.save(); ctx.translate(960, 540); ctx.scale(ck, ck); panel(-cw / 2, -80, cw, 160, { fill: C.accent, stroke: C.accent, r: 80 }); txt(s.caption, 0, 25, { size: 72, weight: 800, align: "center", color: C.onAccent }); ctx.restore(); }
  };

  var CUSTOM = new WeakMap();
  R.custom = function (s, lt, d, T) {
    var fn = CUSTOM.get(s);
    if (!fn) { try { fn = new Function("ctx", "lt", "d", "H", "s", Array.isArray(s.code) ? s.code.join("\n") : s.code); } catch (e) { fn = function () {}; console.error("custom scene:", e); } CUSTOM.set(s, fn); }
    heading(s, lt);
    ctx.save(); try { fn(ctx, lt, d, HELP, s); } catch (e) { if (!s._err) { s._err = 1; console.error("custom scene:", e); } } ctx.restore();
  };
  /* ---- custom と重ねの層で使う道具 ---- */
  /* 乱数の種で決まる乱数（時刻だけで決まる描画のため。Math.random は使わない） */
  function rand(seed) { var a = (seed >>> 0) || 1; return function () { a |= 0; a = a + 0x6D2B79F5 | 0; var t2 = Math.imul(a ^ a >>> 15, 1 | a);
    t2 = t2 + Math.imul(t2 ^ t2 >>> 7, 61 | t2) ^ t2; return ((t2 ^ t2 >>> 14) >>> 0) / 4294967296; }; }
  function arrow(p0, c, p1, k, o) {
    o = o || {}; if (k <= 0) return; c = c || { x: (p0.x + p1.x) / 2, y: (p0.y + p1.y) / 2 };
    ctx.save(); ctx.strokeStyle = o.color || C.accent2; ctx.lineWidth = o.width || 4; ctx.lineCap = "round"; if (o.dashed) ctx.setLineDash([14, 10]);
    if (o.glow) { ctx.shadowColor = o.color || C.accent2; ctx.shadowBlur = 24 * o.glow; }
    ctx.beginPath(); var N = 40; for (var j = 0; j <= N * clamp(k); j++) { var q = qpt(p0, c, p1, j / N); j ? ctx.lineTo(q.x, q.y) : ctx.moveTo(q.x, q.y); } ctx.stroke();
    ctx.setLineDash([]); ctx.shadowBlur = 0;
    if (k >= 1 && o.head !== false) { var pe = qpt(p0, c, p1, 1), pb = qpt(p0, c, p1, .96); ctx.translate(pe.x, pe.y); ctx.rotate(Math.atan2(pe.y - pb.y, pe.x - pb.x));
      ctx.fillStyle = o.color || C.accent2; ctx.beginPath(); ctx.moveTo(6, 0); ctx.lineTo(-16, -11); ctx.lineTo(-16, 11); ctx.closePath(); ctx.fill(); }
    ctx.restore();
  }
  function packet(p0, c, p1, u, label, o) {
    o = o || {}; if (u <= 0 || u >= 1) return; c = c || { x: (p0.x + p1.x) / 2, y: (p0.y + p1.y) / 2 };
    var pt = qpt(p0, c, p1, eio(u)), col = o.color || C.accent; ctx.save(); ctx.shadowColor = col; ctx.shadowBlur = 20; ctx.fillStyle = col;
    if (label) { var w = tw(label, { size: 20, weight: 700, font: F.mono }) + 24; rr(pt.x - w / 2, pt.y - 20, w, 40, 10); ctx.fill(); ctx.shadowBlur = 0;
      txt(label, pt.x, pt.y + 7, { size: 20, weight: 700, font: F.mono, align: "center", color: C.onAccent }); }
    else { ctx.beginPath(); ctx.arc(pt.x, pt.y, o.r || 11, 0, Math.PI * 2); ctx.fill(); }
    ctx.restore();
  }
  function node(x, y, w, h, label, sub, o) {
    o = o || {}; panel(x, y, w, h, { stroke: o.stroke || (o.hot ? C.accent : C.edge), lw: o.hot ? 3 : 1.5, fill: o.fill || C.panel });
    var ink = o.ink || C.ink, cx = x + w / 2, cy = y + h / 2;
    if (o.state) { stateMark(x + 28, y + 28, o.state, o.t || 0, 10); }
    txt(label, cx, sub ? cy - 2 : cy + 12, { size: o.size || 34, weight: 800, align: "center", color: ink });
    if (sub) txt(sub, cx, cy + 34, { size: 21, align: "center", color: o.subColor || C.muted, font: F.mono });
  }
  function appWindow(x, y, w, h, title, o) {
    o = o || {}; panel(x, y, w, h, { r: 18 }); ctx.save(); rr(x, y, w, h, 18); ctx.clip();
    ctx.fillStyle = C.bg1; ctx.fillRect(x, y, w, 46);
    for (var i = 0; i < 3; i++) { ctx.fillStyle = C.edge; ctx.beginPath(); ctx.arc(x + 26 + i * 22, y + 23, 6.5, 0, Math.PI * 2); ctx.fill(); }
    txt(title || "", x + w / 2, y + 31, { size: 20, color: C.muted, align: "center" }); ctx.restore();
    return { x: x + 1, y: y + 47, w: w - 2, h: h - 48 };
  }
  function toast(x, y, w, title, sub, kind, k, t0) {
    if (k <= 0) return; ctx.save(); ctx.globalAlpha *= clamp(k); ctx.translate((1 - Math.min(1, k)) * 80, 0);
    panel(x, y, w, 96, { stroke: kind === "blocked" ? C.warn : C.ok, lw: 2 }); stateMark(x + 38, y + 36, kind || "done", t0 || 0, 11);
    txt(title || "", x + 64, y + 44, { size: 23, weight: 700 }); if (sub) txt(sub, x + 64, y + 74, { size: 17, font: F.mono, color: C.muted }); ctx.restore();
  }
  function typed(str, k) { str = String(str); return str.slice(0, Math.round(str.length * clamp(k))); }
  function particles(o, lt) {
    o = o || {}; var r = rand(o.seed || 7), n = o.n || 60, x = o.x || 0, y = o.y || 0, w = o.w || W, h = o.h || H, sp = o.speed || 1;
    ctx.save(); ctx.fillStyle = o.color || C.accent2;
    for (var i = 0; i < n; i++) { var px = r() * w, py = r() * h, vy = (r() * .6 + .2) * sp, ph = r() * Math.PI * 2, sz = (o.size || 3) * (r() * .8 + .4);
      var yy = (py - lt * vy * .03) % h; if (yy < 0) yy += h; ctx.globalAlpha = (o.alpha || .5) * (.5 + .5 * Math.sin(lt / 700 + ph));
      ctx.beginPath(); ctx.arc(x + px + Math.sin(lt / 1500 + ph) * 12, y + yy, sz, 0, Math.PI * 2); ctx.fill(); }
    ctx.restore();
  }
  function cursor(x, y, down, lt) {
    ctx.save(); ctx.translate(x, y);
    if (down) { ctx.strokeStyle = C.accent; ctx.lineWidth = 3; ctx.globalAlpha = .7; ctx.beginPath(); ctx.arc(0, 0, 18 + (lt % 400) / 20, 0, Math.PI * 2); ctx.stroke(); ctx.globalAlpha = 1; }
    ctx.fillStyle = "#ffffff"; ctx.strokeStyle = "#111111"; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(0, 34); ctx.lineTo(9, 26); ctx.lineTo(16, 40); ctx.lineTo(22, 37); ctx.lineTo(15, 24); ctx.lineTo(27, 24); ctx.closePath(); ctx.fill(); ctx.stroke();
    ctx.restore();
  }
  /* 部品を縮小して置く（custom で複数の部品を並べる。spec は s の中に置くと配置の計算が使い回される） */
  function sub(type, spec, lt, d, o) {
    o = o || {}; var sc = o.scale || 1; ctx.save(); if (o.alpha !== undefined) ctx.globalAlpha *= o.alpha;
    ctx.translate(o.x || 0, o.y || 0); ctx.scale(sc, sc);
    if (o.clip) { rr(0, 0, W, H, 24 / sc); ctx.clip(); }
    /* 部品の中の部品は、親の場面の文には合わせない（spec.sync: true のときだけ合わせる） */
    var c0 = CUR_CUES, e0 = CUR_CUEE; if (spec.sync !== true) { CUR_CUES = null; CUR_CUEE = null; }
    EVMUTE++; try { (R[type] || R.statement)(spec, Math.max(0, lt), d); drawOverlays(spec, lt, d); } finally { EVMUTE--; CUR_CUES = c0; CUR_CUEE = e0; } ctx.restore();
  }
  /* カメラ: [{at:0..1, x, y, zoom, rot}] を場面の進みで補間し、(x,y) を画面の中央に zoom 倍・rot 度で映す。文字列なら型（CAMS） */
  var CAMS = {
    "push-in": [{ at: 0, zoom: 1 }, { at: 1, zoom: 1.08 }],
    "pull-out": [{ at: 0, zoom: 1.12 }, { at: 1, zoom: 1 }],
    "pan-left": [{ at: 0, x: 1020, zoom: 1.07 }, { at: 1, x: 900, zoom: 1.07 }],
    "pan-right": [{ at: 0, x: 900, zoom: 1.07 }, { at: 1, x: 1020, zoom: 1.07 }],
    "rise": [{ at: 0, y: 600, zoom: 1.07 }, { at: 1, y: 480, zoom: 1.07 }],
    "punch": [{ at: 0, zoom: 1 }, { at: .14, zoom: 1 }, { at: .22, zoom: 1.13 }, { at: 1, zoom: 1.05 }],
    "tilt": [{ at: 0, zoom: 1.1, rot: -2.5 }, { at: 1, zoom: 1.02, rot: 0 }],
    "drift": [{ at: 0, x: 930, y: 555, zoom: 1.05 }, { at: .5, x: 985, y: 530, zoom: 1.07 }, { at: 1, x: 950, y: 548, zoom: 1.05 }],
    "dolly": [{ at: 0, zoom: 1.25, rot: 1.5 }, { at: .6, zoom: 1.03, rot: 0 }, { at: 1, zoom: 1 }],
    "crash-zoom": [{ at: 0, zoom: 1.45, rot: -1 }, { at: .1, zoom: 1.02, rot: 0 }, { at: 1, zoom: 1.06 }],
    "orbit": [{ at: 0, x: 900, zoom: 1.08, rot: -2 }, { at: .5, x: 960, y: 520, zoom: 1.1, rot: 0 }, { at: 1, x: 1020, zoom: 1.08, rot: 2 }],
    "pan-reveal": [{ at: 0, x: 620, y: 420, zoom: 1.5 }, { at: .55, x: 960, y: 540, zoom: 1 }, { at: 1, zoom: 1 }],
    "rack-focus": [{ at: 0, zoom: 1.06, blur: 9 }, { at: .28, zoom: 1.03, blur: 0 }, { at: 1, zoom: 1.05, blur: 0 }],
    "breathe": [{ at: 0, zoom: 1.02 }, { at: .25, zoom: 1.06 }, { at: .5, zoom: 1.02 }, { at: .75, zoom: 1.06 }, { at: 1, zoom: 1.02 }],
    "sink": [{ at: 0, y: 440, zoom: 1.08 }, { at: 1, y: 620, zoom: 1.08 }],
    "handheld": (function () { var k = []; for (var i = 0; i <= 24; i++) k.push({ at: i / 24, x: 960 + 12 * Math.sin(i * 1.7) + 6 * Math.sin(i * .63), y: 540 + 8 * Math.cos(i * 1.3) + 4 * Math.sin(i * 2.9), zoom: 1.05, rot: .45 * Math.sin(i * .9) }); return k; })()
  };
  function camAt(keys, f) {
    if (typeof keys === "string") keys = CAMS[keys];
    if (!keys || !keys.length) return null;
    var a = keys[0], b = keys[keys.length - 1];
    for (var i = 0; i < keys.length - 1; i++) if (f >= (keys[i].at || 0) && f <= (keys[i + 1].at || 1)) { a = keys[i]; b = keys[i + 1]; break; }
    if (f <= (keys[0].at || 0)) b = a = keys[0];
    var k = a === b ? 0 : eio(lin(f, a.at || 0, b.at || 1));
    return { x: mix(a.x === undefined ? 960 : a.x, b.x === undefined ? 960 : b.x, k), y: mix(a.y === undefined ? 540 : a.y, b.y === undefined ? 540 : b.y, k),
             zoom: mix(a.zoom || 1, b.zoom || 1, k), rot: mix(a.rot || 0, b.rot || 0, k), blur: mix(a.blur || 0, b.blur || 0, k) };
  }
  function applyCam(cam) { if (!cam) return;
    if (cam.blur > .05 && "filter" in ctx) ctx.filter = (ctx.filter && ctx.filter !== "none" ? ctx.filter + " " : "") + "blur(" + cam.blur.toFixed(1) + "px)";
    ctx.translate(960, 540); if (cam.rot) ctx.rotate(cam.rot * Math.PI / 180); ctx.scale(cam.zoom, cam.zoom); ctx.translate(-cam.x, -cam.y); }

  /* ================= 動きの性格（台本の motion）: 切り替え・文字の出方・演出・カメラの既定 ================= */
  var MSTYLES = {
    gentle: { tr: ["fade"], ch: "fade", text: "rise", title: "reveal", fx: [], titleFx: [], endFx: [], cam: {} },
    dynamic: { tr: ["whip", "push", "zoom-through", "slide-up"], ch: "iris", text: "pop", title: "slam", fx: [], titleFx: ["speedlines", "particles"], endFx: ["particles"],
               cam: { statement: "punch", kinetic: "punch", quote: "push-in", title: "push-in" } },
    playful: { tr: ["spin", "squeeze", "iris", "slide-up"], ch: "spin", text: "wave", title: "letters", fx: [], titleFx: ["confetti"], endFx: ["confetti"], cam: { title: "tilt" } },
    cinematic: { tr: ["fade", "zoom-through", "fade"], ch: "flash", text: "blur", title: "stretch", fx: ["vignette"], titleFx: ["bokeh", "rays"], endFx: ["bokeh"],
                 cam: { "*": "drift", title: "dolly", statement: "push-in", quote: "push-in" } },
    tech: { tr: ["glitch", "wipe", "pixel", "blinds"], ch: "glitch", text: "scramble", title: "scramble", fx: ["scanlines"], titleFx: ["grid"], endFx: ["grid"], cam: {} },
    retro: { tr: ["pixel", "dissolve", "stripes", "columns"], ch: "tiles", text: "flicker", title: "bounce", fx: ["film"], titleFx: ["halftone"], endFx: ["halftone"], cam: { title: "handheld" } },
    elegant: { tr: ["focus", "fade", "cover"], ch: "cover", text: "tracking", title: "tracking", fx: ["leaks"], titleFx: ["sparkles"], endFx: ["sparkles"],
               cam: { "*": "breathe", title: "rack-focus", quote: "push-in" } },
    news: { tr: ["bars", "push", "stack", "doors"], ch: "bars", text: "box", title: "skew", fx: [], titleFx: ["pulse"], endFx: ["pulse"],
            cam: { statement: "crash-zoom", impact: "crash-zoom", title: "push-in" } }
  };
  var MS = MSTYLES[SPEC.motion] || MSTYLES.gentle;
  function animOf(s, role) { return s.anim || (role === "title" ? MS.title : MS.text); }
  function camOf(s) { if (s.camera !== undefined) return s.camera; return MS.cam[s.type] || (["custom", "dom", "window", "code", "table", "terminal"].indexOf(s.type) < 0 ? MS.cam["*"] : null) || null; }

  /* ---- 画面の揺れ: 部品と重ねの層が shakeEv で知らせ、起動時に場面ごとに集める（時刻だけで決まる揺れ） ---- */
  function shakeEv(at, amp, dur) { sfxEv(at, "__shake", { amp: amp, dur: dur || 400 }); }
  function shakeOff(sc, lt) {
    var x = 0, y = 0;
    (sc.shakes || []).forEach(function (s) { var u = (lt - s.at) / s.dur; if (u < 0 || u > 1) return; var e = Math.pow(1 - u, 2) * s.amp;
      x += e * Math.sin(lt * .085 + s.at) * Math.cos(lt * .031); y += e * Math.cos(lt * .097 + s.at * .7) * Math.sin(lt * .027 + 1); });
    return x || y ? { x: x, y: y } : null;
  }

  /* ---- 文字の出方（1 行）: rise pop slam stretch blur glitch neon reveal type scramble wave letters split ---- */
  var GLYPHS = "ABCDEFGHJKLMNPQRSTUVWXYZ0123456789#$%&*+=?<>アイウエオカキクケコサシスセソ";
  var CHARPOS = new Map();
  function charLayout(line, x, o) {
    var key = line + "|" + x + "|" + font(o) + "|" + (o.align || ""), c = CHARPOS.get(key); if (c) return c;
    var parts = String(line).split("**"), total = tw(line.replace(/\*\*/g, ""), o), cx = x, out = [];
    if (o.align === "center") cx = x - total / 2; else if (o.align === "right") cx = x - total;
    parts.forEach(function (p, i) {
      if (!p) return; var em = i % 2 === 1, po = { size: o.size, weight: em ? Math.max(700, o.weight || 400) : o.weight, font: o.font }, chars = Array.from(p);
      chars.forEach(function (ch, j) { out.push({ ch: ch, x: cx + tw(chars.slice(0, j).join(""), po), w: tw(ch, po), em: em, o: po }); });
      cx += tw(p, po);
    });
    if (CHARPOS.size > 600) CHARPOS.clear(); CHARPOS.set(key, out); return out;
  }
  function animText(line, x, y, o, anim, lt, a0, dur, emK) {
    dur = dur || 700; anim = anim || "rise";
    if (lt < a0 || !line) return;
    var k = lin(lt, a0, a0 + dur), al = o.alpha === undefined ? 1 : o.alpha, size = o.size || 30;
    var total = tw(String(line).replace(/\*\*/g, ""), o), mid = o.align === "center" ? x : o.align === "right" ? x - total / 2 : x + total / 2, cy = y - size * .35;
    var withA = function (m) { return Object.assign({}, o, { alpha: al * m }); };
    if (TEXTX[anim]) { if (k >= 1) { rich(line, x, y, o, emK); return; } ctx.save(); try { TEXTX[anim](line, x, y, o, k, lt, a0, dur); } finally { ctx.restore(); } return; }
    if (anim === "neon") {
      var fl = [0, 1, .15, 1, .35, 1, 1], on = k >= 1 ? 1 : fl[Math.min(fl.length - 1, Math.floor(k * fl.length))];
      ctx.save(); ctx.shadowColor = o.emColor || C.accent; ctx.shadowBlur = on * (18 + 8 * Math.sin(lt / 300)); rich(line, x, y, withA(on), emK); ctx.restore(); return;
    }
    if (anim === "shadow") { var sn = Math.round(16 * eo(Math.min(1, k))); ctx.save(); for (var si = sn; si > 0; si--) rich(line, x + si * 2, y + si * 2, Object.assign({}, o, { color: C.bg0, emColor: C.bg0, alpha: al * .5 * Math.min(1, k * 2) }));
      ctx.restore(); rich(line, x, y, withA(clamp(k * 2)), emK); return; }
    if (k >= 1) { rich(line, x, y, o, emK); return; }
    ctx.save();
    switch (anim) {
      case "mask": { ctx.beginPath(); ctx.rect(mid - total / 2 - 20, y - size * 1.15, total + 40, size * 1.5); ctx.clip(); rich(line, x, y + (1 - eo(k)) * size * 1.3, o); break; }
      case "marker": { var mk = eio(clamp(k * 1.4)); ctx.save(); ctx.fillStyle = C.accent; ctx.globalAlpha *= .32; ctx.fillRect(mid - total / 2 - 8, y - size * .55, (total + 16) * mk, size * .6); ctx.restore();
        rich(line, x, y, withA(clamp(k * 2 - .2))); break; }
      case "drop": { rich(line, x, y - (1 - EASES.bouncy(k)) * 260, withA(clamp(k * 4))); break; }
      case "zoom": { var zs = mix(4, 1, eo(k)); ctx.translate(mid, cy); ctx.scale(zs, zs); ctx.translate(-mid, -cy); rich(line, x, y, withA(eo(k))); break; }
      case "outline": { ctx.font = font(o); ctx.textAlign = o.align || "left"; ctx.lineWidth = Math.max(1.5, size * .03); ctx.strokeStyle = o.color || C.ink;
        ctx.globalAlpha *= al * clamp(k * 3) * (1 - clamp((k - .6) / .4)); ctx.strokeText(String(line).replace(/\*\*/g, ""), x, y); ctx.globalAlpha = al; rich(line, x, y, withA(clamp((k - .45) / .55))); break; }
      case "roll": case "spin": {
        var cs2 = charLayout(line, x, o), n2 = cs2.length, per2 = Math.min(55, dur * .55 / Math.max(1, n2));
        if (anim === "roll") { ctx.beginPath(); ctx.rect(mid - total / 2 - 20, y - size * 1.15, total + 40, size * 1.5); ctx.clip(); }
        cs2.forEach(function (c, i) { var kk = lin(lt, a0 + i * per2, a0 + i * per2 + Math.max(260, dur * .45)); if (kk <= 0) return;
          var co = { size: size, weight: c.o.weight, font: c.o.font, color: c.em ? (o.emColor || C.accent) : (o.color || C.ink), align: "center" };
          if (anim === "roll") { txt(c.ch, c.x + c.w / 2, y + (1 - eo(kk)) * size * 1.4, Object.assign(co, { alpha: al }));
            if (kk < 1) txt(GLYPHS[Math.floor(rand(i * 131 + 7)() * GLYPHS.length)], c.x + c.w / 2, y - eo(kk) * size * 1.4 + size * 0, Object.assign({}, co, { color: C.accent2, alpha: al * (1 - kk) })); }
          else { ctx.save(); ctx.translate(c.x + c.w / 2, cy); ctx.scale(Math.max(.02, Math.abs(Math.cos((1 - eo(kk)) * Math.PI * 1.5))), 1); txt(c.ch, 0, size * .35, Object.assign(co, { alpha: al * clamp(kk * 3) })); ctx.restore(); } });
        break; }
      case "pop": { var e = back(k); ctx.translate(mid, cy); ctx.scale(Math.max(.01, e), Math.max(.01, e)); ctx.translate(-mid, -cy); rich(line, x, y, withA(clamp(k * 2.5))); break; }
      case "slam": { var e2 = lin(lt, a0, a0 + Math.min(300, dur * .45)), sc = mix(2.6, 1, eo(e2)) * (1 + .05 * Math.sin(clamp(lin(lt, a0 + 300, a0 + dur)) * Math.PI));
        ctx.translate(mid, cy); ctx.scale(sc, sc); ctx.translate(-mid, -cy); rich(line, x, y, withA(clamp(e2 * 3))); break; }
      case "stretch": { var e3 = eo(k); ctx.translate(mid, cy); ctx.scale(mix(2.4, 1, e3), mix(.4, 1, e3)); ctx.translate(-mid, -cy); rich(line, x, y, withA(e3)); break; }
      case "blur": { if ("filter" in ctx) ctx.filter = "blur(" + ((1 - eo(k)) * 16).toFixed(1) + "px)"; rich(line, x + (1 - eo(k)) * 30, y, withA(eo(k))); break; }
      case "glitch": { var j = 1 - k, r = rand(Math.floor(lt / 45) + 1);
        rich(line, x + (r() - .5) * 70 * j, y + (r() - .5) * 12 * j, Object.assign({}, o, { color: C.accent2, emColor: C.accent2, alpha: al * .7 * j }));
        rich(line, x + (r() - .5) * 70 * j, y, Object.assign({}, o, { color: C.accent, emColor: C.accent, alpha: al * .6 * j }));
        rich(line, x + (r() - .5) * 16 * j, y, withA(clamp(k * 3))); break; }
      case "reveal": { ctx.beginPath(); ctx.rect(mid - total / 2 - 10, y - size * 1.1, (total + 20) * eio(k), size * 1.5); ctx.clip(); rich(line, x, y, o);
        ctx.restore(); ctx.save(); ctx.fillStyle = C.accent2; ctx.fillRect(mid - total / 2 - 10 + (total + 20) * eio(k), y - size * .95, 5, size * 1.05); break; }
      case "type": case "scramble": case "wave": case "letters": case "split": {
        var cs = charLayout(line, x, o), n = cs.length, per = Math.min(60, dur * .6 / Math.max(1, n)), lastX = null;
        cs.forEach(function (c, i) {
          var col = c.em ? (o.emColor || C.accent) : (o.color || C.ink), c0 = a0 + i * per, kk = lin(lt, c0, c0 + Math.max(260, dur * .45)), co = { size: size, weight: c.o.weight, font: c.o.font, color: col };
          if (anim === "type") { if (lt >= c0) { txt(c.ch, c.x, y, Object.assign(co, { alpha: al })); lastX = c.x + c.w; } }
          else if (anim === "scramble") {
            if (lt < a0 + i * 14) return; var res = a0 + dur * .2 + (i / n) * dur * .7, fin = lt >= res || /\s/.test(c.ch);
            txt(fin ? c.ch : GLYPHS[Math.floor(rand(i * 977 + Math.floor(lt / 55))() * GLYPHS.length)], c.x + c.w / 2, y, Object.assign(co, { align: "center", color: fin ? col : C.accent2, alpha: al })); }
          else if (anim === "wave") { if (kk <= 0) return; txt(c.ch, c.x, y + (1 - back(kk)) * 44, Object.assign(co, { alpha: al * clamp(kk * 2) })); }
          else if (anim === "letters") { if (kk <= 0) return; var rr1 = rand(i * 31 + 7); ctx.save(); ctx.translate(c.x + c.w / 2, cy); ctx.rotate((1 - eo(kk)) * (rr1() - .5) * 1.6);
            ctx.translate(0, -(1 - back(kk)) * 150); txt(c.ch, 0, size * .35, Object.assign(co, { align: "center", alpha: al * clamp(kk * 3) })); ctx.restore(); }
          else { if (kk <= 0) return; var rr2 = rand(i * 53 + 3), e5 = eo(kk); ctx.save(); ctx.translate(c.x + c.w / 2 + (rr2() - .5) * 1500 * (1 - e5), cy + (rr2() - .5) * 800 * (1 - e5));
            ctx.rotate((rr2() - .5) * 3 * (1 - e5)); txt(c.ch, 0, size * .35, Object.assign(co, { align: "center", alpha: al * clamp(kk * 2) })); ctx.restore(); }
        });
        if (anim === "type" && lastX !== null && Math.floor(lt / 400) % 2 === 0) { ctx.fillStyle = C.accent2; ctx.fillRect(lastX + 4, y - size * .85, Math.max(4, size * .1), size * .95); }
        break; }
      case "rotate": { var ex0 = o.align === "center" ? mid - total / 2 : o.align === "right" ? x - total : x, er = back(k);
        ctx.translate(ex0, y); ctx.rotate((1 - er) * -.5); ctx.translate(-ex0, -y); rich(line, x, y, withA(clamp(k * 2.5))); break; }
      case "box": { var bk1 = eio(clamp(k * 2)), bk2 = eio(clamp(k * 2 - 1)), bx0 = mid - total / 2 - 12, bw = total + 24;
        if (k > .5) { ctx.save(); ctx.beginPath(); ctx.rect(bx0, y - size * 1.1, bw, size * 1.5); ctx.clip(); rich(line, x, y, o); ctx.restore(); }
        ctx.fillStyle = o.emColor || C.accent; ctx.fillRect(bx0 + bw * bk2, y - size * .95, bw * (bk1 - bk2), size * 1.2); break; }
      case "halves": { var eh = eo(k), hy = y - size * .38;
        ctx.save(); ctx.beginPath(); ctx.rect(0, y - size * 1.4, W, size * 1.02); ctx.clip(); rich(line, x - (1 - eh) * 260, y, withA(clamp(k * 2))); ctx.restore();
        ctx.beginPath(); ctx.rect(0, hy, W, size * .9); ctx.clip(); rich(line, x + (1 - eh) * 260, y, withA(clamp(k * 2))); break; }
      case "elastic": { var ee = EASES.elastic(k); ctx.translate(mid, cy); ctx.scale(Math.max(.01, ee), Math.max(.01, 2 - Math.max(.2, ee))); ctx.translate(-mid, -cy); rich(line, x, y, withA(clamp(k * 3))); break; }
      case "skew": { var es = eo(k); ctx.translate(mid, cy); ctx.transform(1, 0, -(1 - es) * .9, 1, 0, 0); ctx.translate(-mid - (1 - es) * 340, -cy); rich(line, x, y, withA(clamp(k * 2))); break; }
      case "words": {
        /* 語ごと（空白で区切る。空白の無い行は 3 文字ずつ）に、下から覗くように */
        var cs4 = charLayout(line, x, o), grp = [], cur4 = null, sp4 = /\s/.test(String(line).replace(/\*\*/g, "").trim());
        cs4.forEach(function (c, i) { var brk = sp4 ? /\s/.test(c.ch) : i % 3 === 0; if (sp4 && /\s/.test(c.ch)) { cur4 = null; return; }
          if (!cur4 || (!sp4 && brk)) { cur4 = []; grp.push(cur4); } cur4.push(c); });
        grp.forEach(function (gq, wi) { var a1 = a0 + wi * dur * .5 / grp.length, kk = lin(lt, a1, a1 + dur * .5); if (kk <= 0) return;
          var gx0 = gq[0].x, gx1 = gq[gq.length - 1].x + gq[gq.length - 1].w;
          ctx.save(); ctx.beginPath(); ctx.rect(gx0 - 4, y - size * 1.15, gx1 - gx0 + 8, size * 1.5); ctx.clip();
          gq.forEach(function (c) { txt(c.ch, c.x, y + (1 - eo(kk)) * size * 1.25, { size: size, weight: c.o.weight, font: c.o.font, color: c.em ? (o.emColor || C.accent) : (o.color || C.ink), alpha: al }); });
          ctx.restore(); });
        break; }
      case "flip": case "bounce": case "flicker": case "swing": case "tracking": {
        var cs3 = charLayout(line, x, o), n3 = cs3.length, per3 = Math.min(55, dur * .55 / Math.max(1, n3));
        cs3.forEach(function (c, i) {
          var col = c.em ? (o.emColor || C.accent) : (o.color || C.ink), c0 = anim === "tracking" ? a0 : a0 + i * per3, kk = lin(lt, c0, c0 + (anim === "tracking" ? dur : Math.max(280, dur * .45)));
          var co = { size: size, weight: c.o.weight, font: c.o.font, color: col, align: "center" }, cxx = c.x + c.w / 2;
          if (anim === "flicker") { var rf = rand(i * 71 + 5), set = a0 + rf() * dur * .8, on = lt >= set || (lt >= a0 + rf() * dur * .5 && Math.floor(lt / 60 + i) % 3 === 0);
            if (on) { ctx.save(); if (lt < set) { ctx.shadowColor = C.accent2; ctx.shadowBlur = 14; } txt(c.ch, cxx, y, Object.assign(co, { alpha: al * (lt >= set ? 1 : .55) })); ctx.restore(); } return; }
          if (kk <= 0) return;
          if (anim === "tracking") { var et = eo(kk); txt(c.ch, mid + (cxx - mid) * (1 + (1 - et) * 1.4), y, Object.assign(co, { alpha: al * et })); return; }
          ctx.save();
          if (anim === "flip") { ctx.translate(cxx, cy); ctx.scale(1, Math.max(.02, Math.abs(Math.cos((1 - eo(kk)) * Math.PI)))); ctx.translate(0, -cy);
            txt(c.ch, 0, y, Object.assign(co, { alpha: al * clamp(kk * 3), color: kk < .5 ? C.accent2 : col })); }
          else if (anim === "bounce") txt(c.ch, cxx, y - (1 - EASES.bouncy(kk)) * size * 2.2, Object.assign(co, { alpha: al * clamp(kk * 4) }));
          else { var ty = y - size * .9; ctx.translate(cxx, ty); ctx.rotate((1 - back(kk)) * -1.3); ctx.translate(-cxx, -ty); txt(c.ch, cxx, y, Object.assign(co, { alpha: al * clamp(kk * 3) })); }
          ctx.restore();
        });
        break; }
      default: { var e6 = eo(k); rich(line, x, y + (1 - e6) * 24, withA(e6)); }
    }
    ctx.restore();
  }
  function textShake(anim, a0, amp) { if (anim === "slam") shakeEv(a0 + 280, amp || 14, 420); }

  /* ---- 破片が弾ける（burst）: t は弾けてからの ms ---- */
  function burstAt(x, y, t, o) {
    o = o || {}; if (t < 0 || t > 1100) return;
    var r = rand(o.seed || 1), n = o.n || 36, u = t / 1000, spread = o.r || 460;
    ctx.save();
    for (var i = 0; i < n; i++) {
      var ang = r() * Math.PI * 2, sp = .45 + r() * .75, sz = 4 + r() * 9, kind = r(), col = o.color || C.accents[i % C.accents.length], rot = r() * 6;
      var d0 = eo(clamp(u * 1.3)) * spread * sp, px = x + Math.cos(ang) * d0, py = y + Math.sin(ang) * d0 + 120 * u * u;
      ctx.globalAlpha = clamp(1 - u) * .95; ctx.fillStyle = col;
      if (kind < .5) { ctx.beginPath(); ctx.arc(px, py, sz * (1 - u * .6) * .6, 0, Math.PI * 2); ctx.fill(); }
      else { ctx.save(); ctx.translate(px, py); ctx.rotate(rot + u * 8); ctx.fillRect(-sz / 2, -sz / 4, sz, sz / 2); ctx.restore(); }
    }
    var rk = clamp(u * 1.6); ctx.globalAlpha = (1 - rk) * .8; ctx.strokeStyle = o.color || C.accent; ctx.lineWidth = 10 * (1 - rk) + 1;
    ctx.beginPath(); ctx.arc(x, y, 30 + rk * spread * .7, 0, Math.PI * 2); ctx.stroke();
    ctx.restore();
  }

  /* ---- 演出の層（fx）: 場面の fx・台本の fx・動きの性格の既定。under は部品の下、ほかは上 ---- */
  var FX_UNDER = { particles: 1, bokeh: 1, rays: 1, speedlines: 1, grid: 1, waves: 1, stars: 1, gradient: 1, aurora: 1, plexus: 1, contour: 1, shapes: 1, blobs: 1,
                   embers: 1, halftone: 1, warp: 1, pulse: 1, bubbles: 1, matrix: 1 };
  function fxOf(s) {
    var own = s.fx !== undefined ? s.fx : s.type === "title" || s.type === "logo" ? MS.titleFx : s.type === "end" ? MS.endFx : [];
    var all = [].concat(SPEC.fx || [], own || [], s.fx === false ? [] : MS.fx), seen = {};
    return all.filter(function (f) { var kk = typeof f === "string" ? f : f && f.kind; if (!kk || seen[kk]) return false; seen[kk] = 1; return true; });
  }
  function drawFx(list, lt, d, layer) {
    (list || []).forEach(function (f) {
      var kind = typeof f === "string" ? f : f.kind, o = typeof f === "string" ? {} : f;
      if (!kind || !!FX_UNDER[kind] !== (layer === "under")) return;
      var col = C[o.color] || o.color || null, r = rand(o.seed || 5), i, n;
      ctx.save(); ctx.globalAlpha *= o.alpha === undefined ? 1 : o.alpha; var GA = ctx.globalAlpha;
      if (FXX[kind]) FXX[kind](o, lt, d, r, col);
      else if (kind === "particles") particles({ seed: o.seed || 11, n: o.n || 70, color: col || C.accent2, size: 3, alpha: .4, speed: 1.4 }, lt);
      else if (kind === "stars") { ctx.fillStyle = col || C.ink; for (i = 0; i < (o.n || 160); i++) { var sx = r() * W, sy = r() * H, ph = r() * 6.28, ss = r() * 1.8 + .6;
          var xx = ((sx - lt * .006 * ss) % W + W) % W, g0 = ctx.globalAlpha; ctx.globalAlpha = g0 * (.15 + .55 * (.5 + .5 * Math.sin(lt / 600 + ph))); ctx.fillRect(xx, sy, ss * 1.6, ss * 1.6); ctx.globalAlpha = g0; } }
      else if (kind === "bokeh") { for (i = 0; i < (o.n || 16); i++) { var bx = r() * W, by = r() * H, br = 50 + r() * 110, ph2 = r() * 6.28, bc = i % 2 ? C.accent : C.accent2;
          var px = bx + Math.sin(lt / 4200 + ph2) * 70, py = by + Math.cos(lt / 5200 + ph2) * 40, gr = ctx.createRadialGradient(px, py, 0, px, py, br);
          gr.addColorStop(0, bc); gr.addColorStop(1, "rgba(0,0,0,0)"); var g1 = ctx.globalAlpha; ctx.globalAlpha = g1 * (.10 + .08 * Math.sin(lt / 1500 + ph2)); ctx.fillStyle = gr; ctx.fillRect(px - br, py - br, br * 2, br * 2); ctx.globalAlpha = g1; } }
      else if (kind === "rays") { var ox = o.x === undefined ? 960 : o.x, oy = o.y === undefined ? -120 : o.y, nr = o.n || 12, rot = lt * .00006, gr2 = ctx.createRadialGradient(ox, oy, 0, ox, oy, 1500);
        gr2.addColorStop(0, col || C.accent); gr2.addColorStop(1, "rgba(0,0,0,0)"); ctx.fillStyle = gr2; ctx.globalAlpha *= .13;
        for (i = 0; i < nr; i++) { var aa = rot + i * Math.PI * 2 / nr; ctx.beginPath(); ctx.moveTo(ox, oy); ctx.arc(ox, oy, 1600, aa, aa + .09); ctx.closePath(); ctx.fill(); } }
      else if (kind === "speedlines") { ctx.strokeStyle = col || C.ink; ctx.globalAlpha *= .2; ctx.lineCap = "round";
        for (i = 0; i < (o.n || 110); i++) { var an = r() * Math.PI * 2, sp = .6 + r() * 1.2, of = r() * 1400, ln = 80 + r() * 260, lw = 1 + r() * 3, dd = (of + lt * sp * 1.1) % 1400 + 140;
          ctx.lineWidth = lw; ctx.beginPath(); ctx.moveTo(960 + Math.cos(an) * dd, 540 + Math.sin(an) * dd); ctx.lineTo(960 + Math.cos(an) * (dd + ln), 540 + Math.sin(an) * (dd + ln)); ctx.stroke(); } }
      else if (kind === "grid") { var hy = o.y || 700, gc = col || C.accent2; ctx.strokeStyle = gc; ctx.lineWidth = 2;
        var hg = ctx.createLinearGradient(0, hy - 120, 0, hy + 20); hg.addColorStop(0, "rgba(0,0,0,0)"); hg.addColorStop(1, gc); var g2 = ctx.globalAlpha; ctx.globalAlpha = g2 * .18; ctx.fillStyle = hg; ctx.fillRect(0, hy - 120, W, 140); ctx.globalAlpha = g2 * .45;
        for (i = -14; i <= 14; i++) { ctx.beginPath(); ctx.moveTo(960 + i * 30, hy); ctx.lineTo(960 + i * 380, H + 40); ctx.stroke(); }
        for (i = 0; i < 16; i++) { var z = (i + (lt / 700) % 1) / 16, yy = hy + (H + 40 - hy) * Math.pow(z, 2.2); ctx.globalAlpha = g2 * .45 * z; ctx.beginPath(); ctx.moveTo(0, yy); ctx.lineTo(W, yy); ctx.stroke(); } }
      else if (kind === "waves") { ctx.strokeStyle = col || C.accent; ctx.lineWidth = 3;
        for (i = 0; i < 3; i++) { ctx.globalAlpha = .22 - i * .05; ctx.beginPath(); for (var wx = 0; wx <= W; wx += 20) { var wy = (o.y || 930) + i * 30 + Math.sin(wx / (180 + i * 40) + lt / (700 - i * 120) + i) * (14 + i * 5); wx ? ctx.lineTo(wx, wy) : ctx.moveTo(wx, wy); } ctx.stroke(); } }
      else if (kind === "scanlines") { ctx.fillStyle = "#000"; ctx.globalAlpha *= .09; for (var sy2 = 0; sy2 < H; sy2 += 4) ctx.fillRect(0, sy2, W, 1.2);
        ctx.globalAlpha = .06; var by2 = (lt * .25) % (H + 240) - 120, sg = ctx.createLinearGradient(0, by2, 0, by2 + 120); sg.addColorStop(0, "rgba(255,255,255,0)"); sg.addColorStop(.5, "#fff"); sg.addColorStop(1, "rgba(255,255,255,0)"); ctx.fillStyle = sg; ctx.fillRect(0, by2, W, 120); }
      else if (kind === "confetti") { for (i = 0; i < (o.n || 90); i++) { var cx0 = r() * W, v = .12 + r() * .22, y0 = r() * (H + 200), rt = (r() - .5) * .012, cw = 10 + r() * 10, ch2 = 5 + r() * 6, ph3 = r() * 6.28;
          var yy2 = (y0 + lt * v) % (H + 200) - 100, xx2 = cx0 + Math.sin(lt / 700 + ph3) * 30; ctx.save(); ctx.translate(xx2, yy2); ctx.rotate(lt * rt + ph3); ctx.scale(1, Math.sin(lt / 300 + ph3));
          ctx.fillStyle = C.accents[i % C.accents.length]; ctx.fillRect(-cw / 2, -ch2 / 2, cw, ch2); ctx.restore(); } }
      else if (kind === "vignette") { var vg = ctx.createRadialGradient(960, 540, 380, 960, 540, 1150); vg.addColorStop(0, "rgba(0,0,0,0)"); vg.addColorStop(1, "rgba(0,0,0," + (o.strength || .55) + ")"); ctx.fillStyle = vg; ctx.fillRect(0, 0, W, H); }
      else if (kind === "sweep") { var per2 = o.period || 3600, p2 = (lt % per2) / per2, sx2 = -700 + p2 * (W + 1400); ctx.transform(1, 0, -.35, 1, 0, 0);
        var swg = ctx.createLinearGradient(sx2, 0, sx2 + 420, 0); swg.addColorStop(0, "rgba(255,255,255,0)"); swg.addColorStop(.5, "rgba(255,255,255,.13)"); swg.addColorStop(1, "rgba(255,255,255,0)"); ctx.fillStyle = swg; ctx.fillRect(sx2, 0, 420 + H * .35, H); }
      else if (kind === "gradient") { [[C.accent, .3, 900, 700], [C.accent2, .25, 1300, 900]].forEach(function (gq, gi) {
          var gx = 960 + Math.sin(lt / (4000 + gi * 1500) + gi * 2) * 700, gy = 540 + Math.cos(lt / (5000 + gi * 900) + gi) * 350, gr3 = ctx.createRadialGradient(gx, gy, 0, gx, gy, gq[2]);
          gr3.addColorStop(0, gq[0]); gr3.addColorStop(1, "rgba(0,0,0,0)"); var ga = ctx.globalAlpha; ctx.globalAlpha = ga * gq[1]; ctx.fillStyle = gr3; ctx.fillRect(0, 0, W, H); ctx.globalAlpha = ga; }); }
      else if (kind === "aurora") { for (i = 0; i < 3; i++) { var ay = (o.y || 330) + i * 110, cA = C.accents[i % C.accents.length], ag = ctx.createLinearGradient(0, ay - 130, 0, ay + 130);
          ag.addColorStop(0, "rgba(0,0,0,0)"); ag.addColorStop(.5, cA); ag.addColorStop(1, "rgba(0,0,0,0)"); var ga2 = ctx.globalAlpha; ctx.globalAlpha = ga2 * (.16 - i * .03); ctx.fillStyle = ag; ctx.beginPath();
          for (var ax = 0; ax <= W; ax += 30) { var yy3 = ay + Math.sin(ax / 260 + lt / (1600 + i * 400) + i) * 70 + Math.sin(ax / 90 - lt / 900) * 16; ax ? ctx.lineTo(ax, yy3 - 120) : ctx.moveTo(ax, yy3 - 120); }
          for (var ax2 = W; ax2 >= 0; ax2 -= 30) ctx.lineTo(ax2, ay + Math.sin(ax2 / 260 + lt / (1600 + i * 400) + i) * 70 + 120); ctx.closePath(); ctx.fill(); ctx.globalAlpha = ga2; } }
      else if (kind === "plexus") { var pts = []; for (i = 0; i < (o.n || 44); i++) { var bx0 = r() * W, by0 = r() * H, ph4 = r() * 6.28; pts.push({ x: bx0 + Math.sin(lt / 2600 + ph4) * 60, y: by0 + Math.cos(lt / 3100 + ph4) * 40 }); }
        ctx.strokeStyle = col || C.accent2; ctx.fillStyle = col || C.accent2; var ga3 = ctx.globalAlpha;
        for (i = 0; i < pts.length; i++) for (var jj = i + 1; jj < pts.length; jj++) { var dd = Math.hypot(pts[i].x - pts[jj].x, pts[i].y - pts[jj].y); if (dd > 240) continue;
          ctx.globalAlpha = ga3 * .28 * (1 - dd / 240); ctx.lineWidth = 1.5; ctx.beginPath(); ctx.moveTo(pts[i].x, pts[i].y); ctx.lineTo(pts[jj].x, pts[jj].y); ctx.stroke(); }
        ctx.globalAlpha = ga3 * .5; pts.forEach(function (q) { ctx.beginPath(); ctx.arc(q.x, q.y, 3.5, 0, Math.PI * 2); ctx.fill(); }); }
      else if (kind === "contour") { var ox2 = o.x || 1400, oy2 = o.y || 380; ctx.strokeStyle = col || C.edge; ctx.lineWidth = 2; ctx.globalAlpha *= .5;
        for (i = 1; i <= 9; i++) { ctx.beginPath(); for (var an2 = 0; an2 <= Math.PI * 2 + .01; an2 += .08) { var rr2 = i * 70 + Math.sin(an2 * 3 + i + lt / 3000) * 18 + Math.sin(an2 * 5 - i * .7 - lt / 4200) * 10;
          var px2 = ox2 + Math.cos(an2) * rr2 * 1.3, py2 = oy2 + Math.sin(an2) * rr2; an2 ? ctx.lineTo(px2, py2) : ctx.moveTo(px2, py2); } ctx.closePath(); ctx.stroke(); } }
      else if (kind === "shapes") { ctx.lineWidth = 3; for (i = 0; i < (o.n || 14); i++) { var sx3 = r() * W, sy3 = r() * H, sk = Math.floor(r() * 4), sz3 = 30 + r() * 50, sp3 = (r() - .5) * .0008, ph5 = r() * 6.28;
          ctx.save(); ctx.translate(sx3 + Math.sin(lt / 3000 + ph5) * 50, ((sy3 - lt * .015 * (1 + r())) % (H + 200) + H + 200) % (H + 200) - 100); ctx.rotate(lt * sp3 + ph5);
          ctx.strokeStyle = C.accents[i % C.accents.length]; ctx.globalAlpha *= .3; ctx.beginPath();
          if (sk === 0) ctx.arc(0, 0, sz3 / 2, 0, Math.PI * 2); else if (sk === 1) ctx.rect(-sz3 / 2, -sz3 / 2, sz3, sz3);
          else if (sk === 2) { ctx.moveTo(0, -sz3 / 2); ctx.lineTo(sz3 / 2, sz3 / 2); ctx.lineTo(-sz3 / 2, sz3 / 2); ctx.closePath(); } else { ctx.moveTo(-sz3 / 2, 0); ctx.lineTo(sz3 / 2, 0); ctx.moveTo(0, -sz3 / 2); ctx.lineTo(0, sz3 / 2); }
          ctx.stroke(); ctx.restore(); } }
      else if (kind === "blobs") { for (i = 0; i < 4; i++) { var bcx = [300, 1600, 1100, 600][i] + Math.sin(lt / 5000 + i) * 120, bcy = [250, 300, 850, 800][i] + Math.cos(lt / 6000 + i * 2) * 90, brr = 260 + i * 30;
          ctx.save(); ctx.fillStyle = C.accents[i % C.accents.length]; ctx.globalAlpha *= .1; ctx.beginPath();
          for (var bj = 0; bj <= 12; bj++) { var ba = bj / 12 * Math.PI * 2, bR = brr * (1 + .12 * Math.sin(ba * 3 + lt / 1300 + i) + .06 * Math.sin(ba * 5 - lt / 900)), bpx = bcx + Math.cos(ba) * bR, bpy = bcy + Math.sin(ba) * bR; bj ? ctx.lineTo(bpx, bpy) : ctx.moveTo(bpx, bpy); }
          ctx.closePath(); ctx.fill(); ctx.restore(); } }
      else if (kind === "rain") { ctx.strokeStyle = col || C.ink; ctx.lineCap = "round"; ctx.globalAlpha *= .22;
        for (i = 0; i < (o.n || 140); i++) { var rx = r() * (W + 300), rs = 1.1 + r() * .9, rl = 30 + r() * 50, ry = (r() * (H + 200) + lt * rs) % (H + 200) - 100, rxx = rx - (ry + 100) * .18;
          ctx.lineWidth = 1 + r() * 1.5; ctx.beginPath(); ctx.moveTo(rxx, ry); ctx.lineTo(rxx - rl * .18, ry + rl); ctx.stroke(); } }
      else if (kind === "snow") { ctx.fillStyle = col || "#ffffff";
        for (i = 0; i < (o.n || 120); i++) { var fx0 = r() * W, fv = .03 + r() * .06, fr = 2 + r() * 4, fph = r() * 6.28, fy = (r() * (H + 60) + lt * fv) % (H + 60) - 30;
          ctx.globalAlpha = GA * (.35 + fr / 12); ctx.beginPath(); ctx.arc(fx0 + Math.sin(lt / 1300 + fph) * 40, fy, fr, 0, Math.PI * 2); ctx.fill(); } }
      else if (kind === "embers") { for (i = 0; i < (o.n || 70); i++) { var ex = r() * W, ev0 = .05 + r() * .09, er0 = 1.5 + r() * 3, eph = r() * 6.28, life = (r() * (H + 100) + lt * ev0) % (H + 100);
          var eyy = H + 50 - life, eaa = Math.sin(Math.PI * life / (H + 100)); ctx.fillStyle = i % 3 ? C.accent2 : C.warn; ctx.globalAlpha = GA * eaa * .75 * (.6 + .4 * Math.sin(lt / 150 + eph));
          ctx.shadowColor = ctx.fillStyle; ctx.shadowBlur = 10; ctx.beginPath(); ctx.arc(ex + Math.sin(lt / 700 + eph) * 30 + life * .08, eyy, er0, 0, Math.PI * 2); ctx.fill(); } }
      else if (kind === "film") { var rf2 = rand(Math.floor(lt / 42) + 3); ctx.fillStyle = "#000"; ctx.globalAlpha *= .05 + .04 * rf2(); ctx.fillRect(0, 0, W, H);
        ctx.globalAlpha = GA * .08; ctx.fillStyle = col || C.ink; for (i = 0; i < 500; i++) ctx.fillRect(rf2() * W, rf2() * H, 1.5 + rf2() * 1.5, 1.5 + rf2() * 1.5);
        ctx.strokeStyle = col || C.ink; for (i = 0; i < 2; i++) if (rf2() < .6) { var sxx = rf2() * W; ctx.globalAlpha = GA * (.12 + rf2() * .1); ctx.lineWidth = 1 + rf2(); ctx.beginPath(); ctx.moveTo(sxx, 0); ctx.lineTo(sxx + (rf2() - .5) * 30, H); ctx.stroke(); }
        if (rf2() < .08) { ctx.globalAlpha = GA * .25; ctx.fillStyle = col || C.ink; ctx.beginPath(); ctx.arc(rf2() * W, rf2() * H, 2 + rf2() * 5, 0, Math.PI * 2); ctx.fill(); } }
      else if (kind === "leaks") { ctx.globalCompositeOperation = "screen"; [[0, C.accent2, 1], [1, C.warn, -1]].forEach(function (lq) {
          var lx = lq[0] ? W + 100 - (Math.sin(lt / 3300) * .5 + .5) * 400 : -100 + (Math.sin(lt / 2700 + 1) * .5 + .5) * 420, ly = lq[0] ? H * .8 : H * .2, lg = ctx.createRadialGradient(lx, ly, 0, lx, ly, 820);
          lg.addColorStop(0, lq[1]); lg.addColorStop(1, "rgba(0,0,0,0)"); var la = ctx.globalAlpha; ctx.globalAlpha = la * (.22 + .1 * Math.sin(lt / 900 + lq[0] * 2)); ctx.fillStyle = lg; ctx.fillRect(0, 0, W, H); ctx.globalAlpha = la; }); }
      else if (kind === "halftone") { var hs = o.size || 34, hc = col || C.accent2, hx0 = o.x === undefined ? 1500 : o.x, hy0 = o.y === undefined ? 260 : o.y; ctx.fillStyle = hc; ctx.globalAlpha *= .22;
        for (var hx = hs / 2; hx < W; hx += hs) for (var hy2 = hs / 2; hy2 < H; hy2 += hs) { var hd = Math.hypot(hx - hx0, hy2 - hy0), hr = hs * .42 * clamp(1 - hd / 1100) * (.75 + .25 * Math.sin(hd / 90 - lt / 500));
          if (hr > .6) { ctx.beginPath(); ctx.arc(hx, hy2, hr, 0, Math.PI * 2); ctx.fill(); } } }
      else if (kind === "warp") { ctx.strokeStyle = col || C.ink; ctx.lineCap = "round";
        for (i = 0; i < (o.n || 160); i++) { var wa = r() * Math.PI * 2, wz = ((r() + lt / (o.period || 2600)) % 1), wd = Math.pow(wz, 3) * 1300 + 10, wl = Math.pow(wz, 3) * 90 + 2;
          ctx.globalAlpha = GA * wz * .6; ctx.lineWidth = .8 + wz * 3; ctx.beginPath(); ctx.moveTo(960 + Math.cos(wa) * wd, 540 + Math.sin(wa) * wd); ctx.lineTo(960 + Math.cos(wa) * (wd + wl), 540 + Math.sin(wa) * (wd + wl)); ctx.stroke(); } }
      else if (kind === "pulse") { var px0 = o.x === undefined ? 960 : o.x, py0 = o.y === undefined ? 540 : o.y; ctx.strokeStyle = col || C.accent; ctx.lineWidth = 2;
        for (i = 0; i < 5; i++) { var pq = ((lt / (o.period || 3200)) + i / 5) % 1; ctx.globalAlpha = GA * (1 - pq) * .3; ctx.beginPath(); ctx.arc(px0, py0, 60 + pq * 1000, 0, Math.PI * 2); ctx.stroke(); }
        var sa = lt / 1600; ctx.globalAlpha = GA * .07; ctx.fillStyle = col || C.accent; ctx.beginPath(); ctx.moveTo(px0, py0); ctx.arc(px0, py0, 1100, sa, sa + .35); ctx.closePath(); ctx.fill(); }
      else if (kind === "spotlight") { var sp0 = (Math.sin(lt / (o.period || 2400)) * .5 + .5), spx = mix(420, 1500, sp0), spy = 480 + Math.sin(lt / 1700) * 90;
        ctx.fillStyle = "rgba(0,0,0," + (o.strength || .5) + ")"; ctx.beginPath(); ctx.rect(0, 0, W, H); ctx.ellipse(spx, spy, 460, 330, 0, 0, Math.PI * 2); ctx.fill("evenodd");
        var sg2 = ctx.createRadialGradient(spx, spy, 280, spx, spy, 480); sg2.addColorStop(0, "rgba(0,0,0,0)"); sg2.addColorStop(1, "rgba(0,0,0," + (o.strength || .5) + ")"); ctx.fillStyle = sg2; ctx.beginPath(); ctx.ellipse(spx, spy, 461, 331, 0, 0, Math.PI * 2); ctx.fill(); }
      else if (kind === "bubbles") { ctx.lineWidth = 2;
        for (i = 0; i < (o.n || 34); i++) { var bbx = r() * W, bbv = .04 + r() * .07, bbr = 8 + r() * 30, bph = r() * 6.28, bby = H + 60 - (r() * (H + 120) + lt * bbv) % (H + 120);
          ctx.strokeStyle = C.accents[i % C.accents.length]; ctx.globalAlpha = GA * .28; ctx.beginPath(); ctx.arc(bbx + Math.sin(lt / 900 + bph) * 24, bby, bbr, 0, Math.PI * 2); ctx.stroke();
          ctx.globalAlpha = GA * .18; ctx.beginPath(); ctx.arc(bbx + Math.sin(lt / 900 + bph) * 24 - bbr * .35, bby - bbr * .35, bbr * .22, 0, Math.PI * 2); ctx.fillStyle = C.ink; ctx.fill(); } }
      else if (kind === "matrix") { var mc = o.size || 26, cols = Math.ceil(W / mc); ctx.font = "700 " + (mc - 4) + "px " + F.mono; ctx.textAlign = "center";
        for (i = 0; i < cols; i++) { var rm = rand(i * 131 + (o.seed || 5)), msp = .08 + rm() * .16, mlen = 8 + Math.floor(rm() * 18), head = (rm() * (H / mc + mlen) + lt * msp / mc * 1.0) % (H / mc + mlen);
          if (rm() < .45) continue;
          for (var mj = 0; mj < mlen; mj++) { var row = Math.floor(head) - mj; if (row < 0 || row * mc > H) continue;
            ctx.fillStyle = mj === 0 ? C.ink : col || C.ok; ctx.globalAlpha = GA * (mj === 0 ? .5 : .28 * (1 - mj / mlen));
            ctx.fillText(GLYPHS[Math.floor(rand(i * 977 + row * 31 + Math.floor(lt / 400 + mj))() * GLYPHS.length)], i * mc + mc / 2, row * mc); } } }
      else if (kind === "sparkles") { for (i = 0; i < (o.n || 26); i++) { var skx = r() * W, sky = r() * H, sper = 1400 + r() * 1800, sph = r() * sper, sq = ((lt + sph) % sper) / sper, sz = (10 + r() * 22) * Math.sin(sq * Math.PI);
          if (sz <= .5) continue; ctx.save(); ctx.translate(skx, sky); ctx.rotate(sq * 1.5); ctx.fillStyle = i % 2 ? C.accent : C.accent2; ctx.globalAlpha *= .7 * Math.sin(sq * Math.PI);
          ctx.beginPath(); ctx.moveTo(0, -sz); ctx.quadraticCurveTo(0, 0, sz, 0); ctx.quadraticCurveTo(0, 0, 0, sz); ctx.quadraticCurveTo(0, 0, -sz, 0); ctx.quadraticCurveTo(0, 0, 0, -sz); ctx.fill(); ctx.restore(); } }
      else if (kind === "noise") { var rn = rand(Math.floor(lt / 50) + 1); ctx.fillStyle = col || C.ink; ctx.globalAlpha *= .07; for (i = 0; i < (o.n || 600); i++) ctx.fillRect(rn() * W, rn() * H, 2, 2); }
      ctx.restore();
    });
  }

  /* ---- 重ねの層（どの場面にも。座標は 1920×1080、at / until は場面の進み 0..1） ---- */
  function drawOverlays(s, lt, d) {
    (s.overlays || []).forEach(function (o) {
      var kind = o.kind || "note", inst = kind === "burst" || kind === "stamp" || kind === "confetti" || kind === "ripple";
      /* atCue / untilCue: n 番目（1 から）の字幕の文が始まる・終わる時（説明に合わせて出す・消す） */
      var a = o.atCue && cueStart(o.atCue - 1) !== null ? cueStart(o.atCue - 1) : (o.at || 0) * d,
          b = o.untilCue && cueEnd(o.untilCue - 1) !== null ? cueEnd(o.untilCue - 1) : o.until !== undefined ? o.until * d : d, k = inst ? (lt >= a ? 1 : 0) * (1 - P(lt, b - 350, b)) : P(lt, a, a + 450) * (1 - P(lt, b - 350, b));
      if (kind === "stamp") shakeEv(a + 240, o.shake === undefined ? 12 : o.shake, 360);
      if (o.sfx !== false) {
        if (kind === "cursor") (o.click || []).forEach(function (ci) { var pts0 = o.path || [[960, 540]]; sfxEv(a + (b - 350 - a) * ci / Math.max(1, pts0.length - 1), "click"); });
        else sfxEv(a, typeof o.sfx === "string" ? o.sfx : { notify: "notify", highlight: "highlight", badge: "badge", arrow: "arrow", burst: "hit", stamp: "badge", confetti: "reveal",
          ripple: "highlight", circle: "emphasize", marker: "emphasize", icon: "appear" }[kind] || "note");
      }
      if (k <= 0) return;
      ctx.save(); ctx.globalAlpha *= k;
      if (kind === "note") {
        var lines = wrap(o.text || "", o.width || 420, { size: 28, weight: 700 }), w = Math.min(o.width || 420, Math.max.apply(null, lines.map(function (l) { return tw(l, { size: 28, weight: 700 }); }))) + 40, h = lines.length * 38 + 30;
        var x = o.x === undefined ? 1400 : o.x, y = o.y === undefined ? 200 : o.y;
        if (o.target) { var tx = o.target[0], ty = o.target[1], ex = tx < x ? x : tx > x + w ? x + w : tx, ey = ty < y ? y : y + h;
          ctx.strokeStyle = C.accent; ctx.lineWidth = 2.5; ctx.setLineDash([6, 6]); ctx.beginPath(); ctx.moveTo(ex, ey); ctx.lineTo(mix(ex, tx, P(lt, a, a + 600)), mix(ey, ty, P(lt, a, a + 600))); ctx.stroke(); ctx.setLineDash([]);
          ctx.fillStyle = C.accent; ctx.beginPath(); ctx.arc(tx, ty, 7 * P(lt, a + 400, a + 700, back), 0, Math.PI * 2); ctx.fill(); }
        panel(x, y, w, h, { stroke: C.accent, lw: 2 });
        lines.forEach(function (l, i) { rich(l, x + 20, y + 44 + i * 38, { size: 28, weight: 700 }); });
      } else if (kind === "arrow") {
        var p0 = { x: o.from[0], y: o.from[1] }, p1 = { x: o.to[0], y: o.to[1] }, cv2 = o.curve ? { x: (p0.x + p1.x) / 2 - (p1.y - p0.y) * o.curve, y: (p0.y + p1.y) / 2 + (p1.x - p0.x) * o.curve } : null;
        arrow(p0, cv2, p1, P(lt, a, a + 700, eio), { color: C.accent, width: 5 });
        if (o.label) { var m = qpt(p0, cv2 || { x: (p0.x + p1.x) / 2, y: (p0.y + p1.y) / 2 }, p1, .5); txt(o.label, m.x, m.y - 16, { size: 26, weight: 700, color: C.accent, align: "center" }); }
      } else if (kind === "highlight") {
        var r = o.rect, pu = .5 + .5 * Math.sin(lt / 260);
        if (o.spotlight) { ctx.save(); ctx.fillStyle = "rgba(0,0,0," + (.55 * k) + ")"; ctx.beginPath(); ctx.rect(0, 0, W, H); rr(r[0] - 12, r[1] - 12, r[2] + 24, r[3] + 24, 16); ctx.fill("evenodd"); ctx.restore(); }
        ctx.strokeStyle = C.accent; ctx.lineWidth = 4 + 2 * pu; rr(r[0] - 12, r[1] - 12, r[2] + 24, r[3] + 24, 16); ctx.stroke();
        if (o.label) txt(o.label, r[0] - 12, r[1] - 26, { size: 26, weight: 700, color: C.accent });
      } else if (kind === "badge") {
        var bw = tw(o.text || "", { size: 24, weight: 800 }) + 32, bk = P(lt, a, a + 500, back);
        ctx.translate(o.x || 0, o.y || 0); ctx.scale(bk, bk); rr(-bw / 2, -22, bw, 44, 22); ctx.fillStyle = o.color === "warn" ? C.warn : C.accent; ctx.fill();
        txt(o.text || "", 0, 9, { size: 24, weight: 800, align: "center", color: C.onAccent });
      } else if (kind === "cursor") {
        var pts = o.path || [[960, 540]], f = lin(lt, a, b - 350), seg = Math.min(pts.length - 2, Math.floor(f * (pts.length - 1))), u = pts.length > 1 ? f * (pts.length - 1) - seg : 0;
        if (pts.length === 1) seg = 0;
        var pA = pts[Math.max(0, seg)], pB = pts[Math.min(pts.length - 1, seg + 1)], e = eio(clamp(u)), cx2 = mix(pA[0], pB[0], e), cy2 = mix(pA[1], pB[1], e);
        var down = (o.click || []).some(function (ci) { var ct = a + (b - 350 - a) * ci / Math.max(1, pts.length - 1); return lt >= ct && lt < ct + 400; });
        cursor(cx2, cy2, down, lt);
      } else if (kind === "icon") { drawIcon(o.name, o.x === undefined ? 960 : o.x, o.y === undefined ? 540 : o.y, o.size || 120, { color: C[o.color] || o.color || C.accent, k: P(lt, a, a + 900), lt: lt, anim: o.anim });
      } else if (kind === "burst") { burstAt(o.x === undefined ? 960 : o.x, o.y === undefined ? 540 : o.y, lt - a, { n: o.n || 36, seed: o.seed || 1, color: C[o.color] || o.color, r: o.r });
      } else if (kind === "ripple") { var rx0 = o.x === undefined ? 960 : o.x, ry0 = o.y === undefined ? 540 : o.y, rR = o.r || 160;
        ctx.strokeStyle = C[o.color] || C.accent; ctx.lineWidth = 3;
        for (var m2 = 0; m2 < 3; m2++) { var q3 = ((lt - a) / 1100 + m2 / 3) % 1; ctx.globalAlpha = k * (1 - q3) * .8; ctx.beginPath(); ctx.arc(rx0, ry0, 16 + q3 * rR, 0, Math.PI * 2); ctx.stroke(); }
      } else if (kind === "confetti") { drawFx([{ kind: "confetti", seed: o.seed || 3, n: o.n || 110 }], lt - a + 3000, d, "over");
      } else if (kind === "stamp") { var se = lin(lt, a, a + 260), ssc = mix(3, 1, eo(se)), scol = o.color === "accent" ? C.accent : o.color === "ok" ? C.ok : C.warn;
        var stw = tw(o.text || "", { size: o.size || 64, weight: 900 }) + 70, sth = (o.size || 64) * 1.6;
        ctx.globalAlpha *= clamp(se * 3) * .95; ctx.translate(o.x === undefined ? 1400 : o.x, o.y === undefined ? 300 : o.y); ctx.rotate((o.rot === undefined ? -12 : o.rot) * Math.PI / 180); ctx.scale(ssc, ssc);
        ctx.strokeStyle = scol; ctx.lineWidth = 7; rr(-stw / 2, -sth / 2, stw, sth, 14); ctx.stroke(); ctx.lineWidth = 2.5; rr(-stw / 2 + 10, -sth / 2 + 10, stw - 20, sth - 20, 8); ctx.stroke();
        txt(o.text || "", 0, (o.size || 64) * .36, { size: o.size || 64, weight: 900, align: "center", color: scol, font: F.display });
      } else if (kind === "circle") { var cr = o.rect, cp = P(lt, a, a + 700, eio), ccx = cr[0] + cr[2] / 2, ccy = cr[1] + cr[3] / 2, crx = cr[2] / 2 + 34, cry = cr[3] / 2 + 26, sd = o.seed || 2;
        ctx.strokeStyle = C[o.color] || C.accent; ctx.lineWidth = 6; ctx.lineCap = "round"; ctx.beginPath();
        for (var th = 0; th <= 2.15 * Math.PI * cp; th += .04) { var wob = 1 + .05 * Math.sin(3 * th + sd) + .03 * th / 6, pxx = ccx + Math.cos(th - 2.2) * crx * wob, pyy = ccy + Math.sin(th - 2.2) * cry * wob; th ? ctx.lineTo(pxx, pyy) : ctx.moveTo(pxx, pyy); }
        ctx.stroke(); if (o.label) txt(o.label, ccx + crx * .6, cr[1] - 40, { size: 28, weight: 800, color: C[o.color] || C.accent, alpha: P(lt, a + 500, a + 900) });
      } else if (kind === "marker") { var mr = o.rect, mp = P(lt, a, a + 600, eio); ctx.fillStyle = C[o.color] || C.accent; ctx.globalAlpha *= .3;
        ctx.beginPath(); ctx.moveTo(mr[0] - 6, mr[1] + 4); ctx.lineTo(mr[0] + mr[2] * mp + 6, mr[1]); ctx.lineTo(mr[0] + mr[2] * mp, mr[1] + mr[3]); ctx.lineTo(mr[0] - 2, mr[1] + mr[3] - 3); ctx.closePath(); ctx.fill();
      } else if (kind === "notify") {
        var nw = 520, nx = W - nw - 48, ny = o.pos === "br" ? H - 330 : 110, nk = P(lt, a, a + 500);   /* 既定は右上（下は字幕と操作部が重なる） */
        ctx.translate(0, (1 - nk) * 30);
        ctx.save(); ctx.shadowColor = "rgba(0,0,0,.35)"; ctx.shadowBlur = 30; rr(nx, ny, nw, 110, 18); ctx.fillStyle = "#eef2f4"; ctx.fill(); ctx.restore();
        emblem("ring", nx + 52, ny + 55, 24, 0, 1, o.app || SPEC.title);
        txt(o.app || (SPEC.brand && SPEC.brand.name) || "", nx + 96, ny + 44, { size: 22, weight: 700, color: "#0f2230" });
        txt(o.text || "", nx + 96, ny + 78, { size: 22, color: "#35505b" });
      }
      ctx.restore();
    });
  }
  /* 部品のファイル（parts-*.js）が足す文字の出方・切り替え・演出の層（X.textAnims・X.transitions・X.fxs に登録する） */
  var TEXTX = {}, TRX = {}, FXX = {};
  var HELP = { C: C, F: F, W: W, H: H, clamp: clamp, lin: lin, linear: linear, eo: eo,
               textAnims: TEXTX, transitions: TRX, fxs: FXX, fxUnder: FX_UNDER, charLayout: charLayout, eases: EASES,
               cue: function (i) { return cueStart(i); }, cueEnd: function (i) { return cueEnd(i); }, cues: function () { return CUR_CUES ? CUR_CUES.slice() : []; }, eio: eio, back: back, P: P, mix: mix, rr: rr, txt: txt, tw: tw, wrap: wrap,
               rich: rich, icon: icon, panel: panel, stateMark: stateMark, emblem: emblem, accentAt: accentAt, slots: slots,
               qpt: qpt, rand: rand, arrow: arrow, packet: packet, node: node, appWindow: appWindow, toast: toast, typed: typed, count: fmtNum,
               particles: particles, cursor: cursor, sub: sub, camAt: camAt, applyCam: applyCam, heading: heading,
               sfx: function (at, what, o) { sfxEv(at, what, o); }, shake: shakeEv, burst: burstAt, fx: drawFx, text: animText, cams: CAMS,
               icon: function (n, x, y, size, o) { return drawIcon(n, x, y, size, o); }, drawIcon: drawIcon, iconAny: icon, cursor: cursor, fmtNum: fmtNum, parseNum: parseNum,
               g: function () { return ctx; }, sfxEv: sfxEv, shakeEv: shakeEv, img: function (src) { return IMGS[src]; }, animText: animText };
  /* 別ファイルの部品（parts-*.js）を登録する: push(function (R, X) { R.xxx = … }) */
  (window.MotionVideoParts || []).forEach(function (fn) { try { fn(R, HELP); } catch (e) { console.error("parts:", e); } });

  /* ================= 背景と 1 コマ ================= */
  function scaleCtx() { ctx.setTransform(cv.width / W, 0, 0, cv.height / H, 0, 0); }
  function backdrop(t) {
    var g = ctx.createLinearGradient(0, 0, 0, H); g.addColorStop(0, C.bg1); g.addColorStop(1, C.bg0);
    ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
    var pat = TH.pattern, drift = (t / 90) % 120;
    ctx.save();
    if (pat === "grid") { ctx.strokeStyle = C.grid; ctx.lineWidth = 1;
      for (var x = -120 + drift; x < W + 120; x += 120) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke(); }
      for (var y = 60; y < H; y += 120) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke(); } }
    else if (pat === "dots") { ctx.fillStyle = C.grid;
      for (var x2 = (drift / 2) % 48; x2 < W; x2 += 48) for (var y2 = 24; y2 < H; y2 += 48) ctx.fillRect(x2, y2, 3, 3); }
    else if (pat === "glow") { var rg = ctx.createRadialGradient(W * .75, H * .2, 50, W * .75, H * .2, 900);
      rg.addColorStop(0, C.grid); rg.addColorStop(1, "rgba(0,0,0,0)"); ctx.fillStyle = rg; ctx.fillRect(0, 0, W, H); }
    ctx.restore();
  }
  function chrome(t) {
    var i = chapterAt(t), lt = t - CHAPTERS[i].t, len = chLen(i);
    var a = P(lt, 200, 700) * (i < CHAPTERS.length - 1 ? 1 - P(lt, len - 500, len) : 1);
    if (SPEC.chrome === false) return;
    var n = CHAPTERS.length;
    txt(String(i + 1).padStart(2, "0") + " / " + String(n).padStart(2, "0"), 64, 72, { size: 22, font: F.mono, color: C.accent, alpha: a, spacing: 2 });
    txt(CHAPTERS[i].name, 64 + tw("00 / 00", { size: 22, font: F.mono }) + 34, 72, { size: 26, weight: 700, alpha: a });
    if (SPEC.brand && SPEC.brand.name) txt(SPEC.brand.name, W - 64, 72, { size: 22, weight: 700, color: C.muted, align: "right", alpha: .8 });
  }
  var FADE = 450;
  /* 前の場面と重ねて描く切り替え（ms）。これ以外（fade・slide・zoom・cut）は場面ごとの透明度で切り替える */
  var SWEEPS = { wipe: 700, push: 700, iris: 800, blinds: 750, split: 750, whip: 460, spin: 820, flash: 520, glitch: 480, pixel: 720,
                 squeeze: 700, "slide-up": 650, "slide-down": 650, "zoom-through": 650,
                 diagonal: 750, diamond: 800, spot: 850, cube: 750, page: 850, liquid: 900, dive: 800, tiles: 900, stripes: 750, clock: 800,
                 doors: 800, shatter: 1100, fan: 850, "spin-zoom": 700, bars: 900, cover: 900, ink: 1000, flip: 800, rings: 900,
                 stack: 750, shrink: 850, flood: 900, focus: 800, dissolve: 850, columns: 800 };
  Object.keys(TRX).forEach(function (k2) { SWEEPS[k2] = TRX[k2].ms || 800; });
  function trOf(k) {
    var s = SCENES[k].s; if (s.transition) return s.transition; if (SPEC.transition) return SPEC.transition;
    if (k > 0 && SCENES[k - 1].ci !== SCENES[k].ci) return MS.ch;
    return MS.tr[k % MS.tr.length];
  }
  function drawScene(k, t, o) {
    o = o || {};
    var sc = SCENES[k], lt = o.lt !== undefined ? o.lt : t - sc.t0, d = sc.d, tr = trOf(k), S = sc.s;
    var last = k === SCENES.length - 1, nextTr = last ? "" : trOf(k + 1), sweepIn = !!SWEEPS[tr], sweepOut = !!SWEEPS[nextTr];
    var inK = k === 0 || sweepIn || tr === "cut" ? 1 : P(lt, 0, FADE), outK = last || sweepOut || nextTr === "cut" ? 1 : 1 - P(lt, d - FADE, d, eio);
    ctx.save(); ctx.globalAlpha = Math.min(inK, outK) * (o.alpha === undefined ? 1 : o.alpha);
    if (o.clipX !== undefined) { ctx.beginPath(); ctx.rect(0, 0, o.clipX, H); ctx.clip(); backdrop(t); }
    if (o.dx || o.dy) ctx.translate(o.dx || 0, o.dy || 0);
    if (o.xf) o.xf();
    if (o.clip) { o.clip(); if (o.bg !== false) backdrop(t); }
    if (o.blur && "filter" in ctx) ctx.filter = "blur(" + o.blur.toFixed(1) + "px)";
    if (tr === "slide") ctx.translate((1 - inK) * 80, 0);
    if (nextTr === "slide") ctx.translate(-(1 - outK) * 80, 0);
    if (tr === "zoom" || nextTr === "zoom") { var z = mix(.96, 1, inK) * mix(1.04, 1, outK); ctx.translate(960, 540); ctx.scale(z, z); ctx.translate(-960, -540); }
    var sh = shakeOff(sc, lt); if (sh) ctx.translate(sh.x, sh.y);
    var fx = fxOf(S), clt = Math.max(0, lt);
    drawFx(fx, clt, d, "under");
    var cam = camAt(camOf(S), clamp(lt / d));
    if (cam) { ctx.save(); applyCam(cam); }
    useMotion(S); (R[S.type] || R.statement)(S, clt, d, t);
    drawOverlays(S, clt, d); useMotion({});
    if (cam) ctx.restore();
    drawFx(fx, clt, d, "over");
    ctx.restore();
  }
  var PIX = null, SNAP = null;
  /* 場面を別の Canvas に描いておく（破片のように何度も貼るとき） */
  function snapshot(t, fn) {
    SNAP = SNAP || document.createElement("canvas"); if (SNAP.width !== cv.width || SNAP.height !== cv.height) { SNAP.width = cv.width; SNAP.height = cv.height; }
    var cv0 = cv, ctx0 = ctx; cv = SNAP; ctx = SNAP.getContext("2d"); ctx.setTransform(SNAP.width / W, 0, 0, SNAP.height / H, 0, 0);
    try { backdrop(t); fn(); } finally { cv = cv0; ctx = ctx0; }
    return SNAP;
  }
  function transition(tr, k, t, lt, SW) {
    var u = eio(lin(lt, 0, SW)), prevD = SCENES[k - 1].d;
    var prev = function (o) { drawScene(k - 1, t, Object.assign({ lt: prevD - 1 }, o || {})); }, next = function (o) { drawScene(k, t, o || {}); };
    var around = function (sc, rot) { return function () { ctx.translate(960, 540); if (rot) ctx.rotate(rot); ctx.scale(sc, sc); ctx.translate(-960, -540); }; };
    var i, r;
    switch (tr) {
      case "push": prev({ dx: -W * u }); next({ dx: W * (1 - u) }); break;
      case "wipe": prev(); next({ clipX: W * u }); ctx.fillStyle = C.accent; ctx.fillRect(W * u - 3, 0, 6, H); break;
      case "slide-up": case "slide-down": { var sg = tr === "slide-up" ? -1 : 1; prev({ dy: sg * H * u }); next({ dy: -sg * H * (1 - u) }); break; }
      case "iris": { prev(); var R0 = Math.hypot(960, 540) * u + .1; next({ clip: function () { ctx.beginPath(); ctx.arc(960, 540, R0, 0, Math.PI * 2); ctx.clip(); } });
        if (u < 1) { ctx.save(); ctx.globalAlpha = 1 - u; ctx.strokeStyle = C.accent; ctx.lineWidth = 8; ctx.beginPath(); ctx.arc(960, 540, R0, 0, Math.PI * 2); ctx.stroke(); ctx.restore(); } break; }
      case "blinds": { prev(); var nb = 9, hh = H / nb;
        next({ clip: function () { ctx.beginPath(); for (var j = 0; j < nb; j++) { var q = eio(clamp(lin(lt, j * SW * .05, SW * .55 + j * SW * .05))); ctx.rect(0, j * hh + hh * (1 - q) / 2, W, hh * q + .5); } ctx.clip(); } }); break; }
      case "split": { next(); var off = H / 2 * u;
        prev({ dy: -off, clip: function () { ctx.beginPath(); ctx.rect(0, 0, W, H / 2); ctx.clip(); } });
        prev({ dy: off, clip: function () { ctx.beginPath(); ctx.rect(0, H / 2, W, H / 2); ctx.clip(); } });
        ctx.fillStyle = C.accent; ctx.fillRect(0, H / 2 - off - 3, W, 5); ctx.fillRect(0, H / 2 + off - 2, W, 5); break; }
      case "whip": { var bl = Math.sin(u * Math.PI) * 10; prev({ dx: -W * u, blur: bl }); next({ dx: W * (1 - u), blur: bl });
        r = rand(7); ctx.save(); ctx.strokeStyle = C.ink; ctx.globalAlpha = Math.sin(u * Math.PI) * .3;
        for (i = 0; i < 34; i++) { var yy = r() * H, ln = 200 + r() * 700, xx = ((r() * W * 2 - u * W * 3) % (W + ln) + W + ln) % (W + ln) - ln; ctx.lineWidth = 1 + r() * 3; ctx.beginPath(); ctx.moveTo(xx, yy); ctx.lineTo(xx + ln, yy); ctx.stroke(); }
        ctx.restore(); break; }
      case "spin": if (u < .5) { var q1 = u * 2; prev({ xf: around(1 - .55 * q1, q1 * .6), alpha: 1 - q1 }); } else { var q2 = (u - .5) * 2; next({ xf: around(1.45 - .45 * q2, -(1 - q2) * .6), alpha: q2 }); } break;
      case "flash": { if (u < .5) prev(); else next(); ctx.save(); ctx.fillStyle = "#ffffff"; ctx.globalAlpha = (1 - Math.abs(u * 2 - 1)) * .95; ctx.fillRect(0, 0, W, H); ctx.restore(); break; }
      case "glitch": { var baseF = u < .5 ? prev : next, otherF = u < .5 ? next : prev; baseF(); r = rand(Math.floor(lt / 40) + 7);
        for (i = 0; i < 7; i++) { (function (y0, h0, dx) { otherF({ dx: dx, clip: function () { ctx.beginPath(); ctx.rect(-dx, y0, W, h0); ctx.clip(); } }); })(r() * H, 20 + r() * 90, (r() - .5) * 180); }
        ctx.save(); for (i = 0; i < 5; i++) { ctx.globalAlpha = .35; ctx.fillStyle = i % 2 ? C.accent : C.accent2; ctx.fillRect(r() * W, r() * H, 80 + r() * 400, 4 + r() * 14); } ctx.restore(); break; }
      case "pixel": { var q = 1 - Math.abs(u * 2 - 1), px = Math.max(1, Math.round(1 + q * 46)), which = u < .5 ? prev : next;
        if (px <= 1) { which(); break; }
        PIX = PIX || document.createElement("canvas"); var pw = Math.ceil(W / px), ph = Math.ceil(H / px); if (PIX.width !== pw || PIX.height !== ph) { PIX.width = pw; PIX.height = ph; }
        var cv0 = cv, ctx0 = ctx; cv = PIX; ctx = PIX.getContext("2d"); ctx.setTransform(1 / px, 0, 0, 1 / px, 0, 0);
        try { backdrop(t); which(); } finally { cv = cv0; ctx = ctx0; }
        ctx.save(); ctx.imageSmoothingEnabled = false; ctx.drawImage(PIX, 0, 0, pw * px, ph * px); ctx.restore(); break; }
      case "squeeze": {
        prev({ xf: function () { ctx.scale(Math.max(.001, 1 - u), 1); } }); next({ xf: function () { ctx.translate(W * (1 - u), 0); ctx.scale(Math.max(.001, u), 1); } });
        ctx.save(); ctx.fillStyle = "#000"; ctx.globalAlpha = .45 * u; ctx.fillRect(0, 0, W * (1 - u), H); ctx.globalAlpha = .45 * (1 - u); ctx.fillRect(W * (1 - u), 0, W * u, H); ctx.restore(); break; }
      case "zoom-through": next({ xf: around(mix(.7, 1, u)), alpha: u }); prev({ xf: around(1 + 2.2 * u), alpha: 1 - u, blur: u * 8 }); break;
      case "diagonal": { prev(); var pd = u * (W + H * .6);
        next({ clip: function () { ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(pd, 0); ctx.lineTo(pd - H * .6, H); ctx.lineTo(0, H); ctx.closePath(); ctx.clip(); } });
        if (u < 1) { ctx.save(); ctx.strokeStyle = C.accent; ctx.lineWidth = 6; ctx.beginPath(); ctx.moveTo(pd, 0); ctx.lineTo(pd - H * .6, H); ctx.stroke(); ctx.restore(); } break; }
      case "diamond": { prev(); var rd = u * (W + H) / 1.4 + .1;
        next({ clip: function () { ctx.beginPath(); ctx.moveTo(960, 540 - rd); ctx.lineTo(960 + rd * 1.6, 540); ctx.lineTo(960, 540 + rd); ctx.lineTo(960 - rd * 1.6, 540); ctx.closePath(); ctx.clip(); } }); break; }
      case "spot": { prev(); var so = SCENES[k].s.origin || [1720, 900], rs = u * Math.hypot(Math.max(so[0], W - so[0]), Math.max(so[1], H - so[1])) + .1;
        next({ clip: function () { ctx.beginPath(); ctx.arc(so[0], so[1], rs, 0, Math.PI * 2); ctx.clip(); } });
        if (u < 1) { ctx.save(); ctx.globalAlpha = 1 - u; ctx.strokeStyle = C.accent2; ctx.lineWidth = 6; ctx.beginPath(); ctx.arc(so[0], so[1], rs, 0, Math.PI * 2); ctx.stroke(); ctx.restore(); } break; }
      case "cube": { prev({ xf: function () { ctx.scale(1, Math.max(.001, 1 - u)); } }); next({ xf: function () { ctx.translate(0, H * (1 - u)); ctx.scale(1, Math.max(.001, u)); } });
        ctx.save(); ctx.fillStyle = "#000"; ctx.globalAlpha = .5 * u; ctx.fillRect(0, 0, W, H * (1 - u)); ctx.globalAlpha = .5 * (1 - u); ctx.fillRect(0, H * (1 - u), W, H * u); ctx.restore(); break; }
      case "page": { next(); var ex = W * (1 - u);
        prev({ clip: function () { ctx.beginPath(); ctx.rect(0, 0, ex, H); ctx.clip(); } });
        if (u > 0 && u < 1) { var cw = 160 * Math.sin(u * Math.PI) + 20, gp = ctx.createLinearGradient(ex - cw, 0, ex + cw * .6, 0);
          gp.addColorStop(0, "rgba(0,0,0,0)"); gp.addColorStop(.55, "rgba(255,255,255,.35)"); gp.addColorStop(.62, "rgba(0,0,0,.35)"); gp.addColorStop(1, "rgba(0,0,0,0)");
          ctx.save(); ctx.fillStyle = gp; ctx.fillRect(ex - cw, 0, cw * 1.6, H); ctx.restore(); } break; }
      case "liquid": { prev(); var bx = u * (W + 240) - 120, amp = 60 * Math.sin(u * Math.PI);
        next({ clip: function () { ctx.beginPath(); ctx.moveTo(0, 0); for (var yy = 0; yy <= H; yy += 20) ctx.lineTo(bx + Math.sin(yy / 90 + lt / 110) * amp + Math.sin(yy / 37 - lt / 70) * amp * .3, yy); ctx.lineTo(0, H); ctx.closePath(); ctx.clip(); } }); break; }
      case "dive": { var fo = SCENES[k - 1].s.focus || [960, 540];
        next({ xf: around(mix(1.3, 1, u)), alpha: u });
        prev({ xf: function () { ctx.translate(fo[0], fo[1]); ctx.scale(1 + 6 * u * u, 1 + 6 * u * u); ctx.translate(-fo[0], -fo[1]); }, alpha: 1 - u * u, blur: u * 6 }); break; }
      case "tiles": { prev(); var tc = 8, trw = 5, tw0 = W / tc, th0 = H / trw;
        next({ clip: function () { ctx.beginPath(); for (var ti = 0; ti < tc; ti++) for (var tj = 0; tj < trw; tj++) { var q = eio(clamp((u * 1.7 - (ti + tj) / (tc + trw) * .7) / .45)); if (q <= 0) continue;
          ctx.rect(ti * tw0 + tw0 * (1 - q) / 2, tj * th0 + th0 * (1 - q) / 2, tw0 * q + .5, th0 * q + .5); } ctx.clip(); } }); break; }
      case "stripes": { prev(); var ns = 10, sw0 = W / ns;
        next({ clip: function () { ctx.beginPath(); for (var si = 0; si < ns; si++) { var q = eio(clamp(u * 1.4 - si * .04)); if (si % 2) ctx.rect(si * sw0, 0, sw0 + .5, H * q); else ctx.rect(si * sw0, H * (1 - q), sw0 + .5, H * q); } ctx.clip(); } }); break; }
      case "clock": { prev(); var a1 = -Math.PI / 2 + u * Math.PI * 2;
        next({ clip: function () { ctx.beginPath(); ctx.moveTo(960, 540); ctx.arc(960, 540, 1400, -Math.PI / 2, a1); ctx.closePath(); ctx.clip(); } });
        if (u < 1) { ctx.save(); ctx.strokeStyle = C.accent; ctx.lineWidth = 6; ctx.beginPath(); ctx.moveTo(960, 540); ctx.lineTo(960 + Math.cos(a1) * 1400, 540 + Math.sin(a1) * 1400); ctx.stroke(); ctx.restore(); } break; }
      case "doors": { next(); var od = W / 2 * u;
        prev({ dx: -od, clip: function () { ctx.beginPath(); ctx.rect(0, 0, W / 2, H); ctx.clip(); } });
        prev({ dx: od, clip: function () { ctx.beginPath(); ctx.rect(W / 2, 0, W / 2, H); ctx.clip(); } });
        ctx.save(); ctx.fillStyle = C.accent; ctx.fillRect(W / 2 - od - 4, 0, 5, H); ctx.fillRect(W / 2 + od - 1, 0, 5, H);
        ctx.globalAlpha = .35 * Math.sin(u * Math.PI); ctx.fillStyle = "#000"; ctx.fillRect(W / 2 - od, 0, od * 2, H); ctx.restore(); break; }
      case "shatter": { next(); var img = snapshot(t, function () { prev(); }), gc = 7, gr = 4, cw2 = W / gc, ch3 = H / gr; r = rand(17);
        var uu = lin(lt, 0, SW);
        for (var gi = 0; gi < gc; gi++) for (var gj = 0; gj < gr; gj++) for (var tri = 0; tri < 2; tri++) {
          var x0 = gi * cw2, y0 = gj * ch3, flipD = (gi + gj) % 2, pts = flipD ? (tri ? [[x0, y0], [x0 + cw2, y0], [x0 + cw2, y0 + ch3]] : [[x0, y0], [x0 + cw2, y0 + ch3], [x0, y0 + ch3]])
            : (tri ? [[x0, y0], [x0 + cw2, y0], [x0, y0 + ch3]] : [[x0 + cw2, y0], [x0 + cw2, y0 + ch3], [x0, y0 + ch3]]);
          var mx = (pts[0][0] + pts[1][0] + pts[2][0]) / 3, my = (pts[0][1] + pts[1][1] + pts[2][1]) / 3, dl = Math.hypot(mx - 960, my - 540) / 1100 * .35 + r() * .08;
          var q = clamp((uu - .12 - dl) / .55), rot2 = (r() - .5) * 2.4, dir = (mx - 960) / 960;
          ctx.save(); ctx.globalAlpha = 1 - q * q;
          ctx.translate(mx + dir * 380 * q, my + 1300 * q * q - 120 * q); ctx.rotate(rot2 * q); ctx.scale(1 - .25 * q, 1 - .25 * q); ctx.translate(-mx, -my);
          ctx.beginPath(); ctx.moveTo(pts[0][0], pts[0][1]); ctx.lineTo(pts[1][0], pts[1][1]); ctx.lineTo(pts[2][0], pts[2][1]); ctx.closePath(); ctx.clip();
          ctx.drawImage(img, 0, 0, W, H); if (uu > .06) { ctx.strokeStyle = "rgba(255,255,255,.55)"; ctx.lineWidth = 2; ctx.stroke(); } ctx.restore(); }
        if (uu < .2) { ctx.save(); ctx.fillStyle = "#fff"; ctx.globalAlpha = (1 - uu / .2) * .5 * clamp(uu / .05); ctx.fillRect(0, 0, W, H); ctx.restore(); }
        break; }
      case "fan": { prev(); var nf = 6;
        next({ clip: function () { ctx.beginPath(); for (var fi = 0; fi < nf; fi++) { var q = eio(clamp(u * 1.5 - fi * .08)), a0 = -Math.PI / 2 + fi * Math.PI * 2 / nf; if (q <= 0) continue;
          ctx.moveTo(960, 540); ctx.arc(960, 540, 1400, a0, a0 + Math.PI * 2 / nf * q + .002); ctx.closePath(); } ctx.clip(); } }); break; }
      case "spin-zoom": if (u < .5) { var q3 = u * 2; prev({ xf: around(1 + 1.6 * q3 * q3, q3 * q3 * 1.4), alpha: 1 - q3 * q3, blur: q3 * 10 }); }
        else { var q4 = (u - .5) * 2; next({ xf: around(mix(.35, 1, eo(q4)), -(1 - eo(q4)) * 1.4), alpha: clamp(q4 * 2), blur: (1 - q4) * 8 }); } break;
      case "bars": { if (u < .5) prev(); else next(); var nbar = 6, bh = H / nbar;
        ctx.save(); for (var bi = 0; bi < nbar; bi++) { var e1 = eio(clamp(u * 2.6 - bi * .1)), e2 = eio(clamp((u - .5) * 2.6 - bi * .1)); if (e1 <= e2) continue;
          ctx.fillStyle = C.accents[bi % C.accents.length]; ctx.fillRect(W * e2, bi * bh, W * (e1 - e2) + 1, bh + 1); } ctx.restore(); break; }
      case "cover": { if (u < .5) prev(); else next(); var c1 = eio(clamp(u * 2)), c2 = eio(clamp(u * 2 - 1));
        ctx.save(); ctx.fillStyle = C.accent; ctx.fillRect(0, H * c2, W, H * (c1 - c2)); ctx.fillStyle = C.accent2; ctx.fillRect(0, H * c1 - 10, W, c1 < 1 ? 10 : 0); ctx.fillRect(0, H * c2, W, c2 > 0 && c2 < 1 ? 10 : 0);
        if (SPEC.brand && SPEC.brand.name && c1 - c2 > .6) txt(SPEC.brand.name, 960, H * (c1 + c2) / 2 + 20, { size: 60, weight: 800, align: "center", font: F.display, color: C.onAccent, alpha: clamp((c1 - c2 - .6) / .3) });
        ctx.restore(); break; }
      case "ink": { prev(); r = rand(29); var blobs = []; for (i = 0; i < 11; i++) blobs.push([r() * W, r() * H, 260 + r() * 420, r() * .35, r() * 6.28]);
        next({ clip: function () { ctx.beginPath(); blobs.forEach(function (b) { var q = eo(clamp((u - b[3]) / .6)); if (q <= 0) return; var rad = b[2] * q;
            for (var bj = 0; bj <= 18; bj++) { var ba = bj / 18 * Math.PI * 2, bR = rad * (1 + .12 * Math.sin(ba * 4 + b[4]) + .07 * Math.sin(ba * 7 - b[4])); bj ? ctx.lineTo(b[0] + Math.cos(ba) * bR, b[1] + Math.sin(ba) * bR) : ctx.moveTo(b[0] + Math.cos(ba) * bR, b[1] + Math.sin(ba) * bR); } ctx.closePath(); });
          var fin = clamp((u - .55) / .45); if (fin > 0) { ctx.moveTo(960 + 1200 * fin, 540); ctx.arc(960, 540, 1200 * fin, 0, Math.PI * 2); } ctx.clip(); } }); break; }
      case "flip": { var fa = u * Math.PI, fc = Math.abs(Math.cos(fa)), fs = 1 - .12 * Math.sin(fa);
        var fxf = function () { ctx.translate(960, 540); ctx.scale(Math.max(.002, fc) * fs, fs); ctx.translate(-960, -540); };
        ctx.save(); ctx.fillStyle = "#000"; ctx.globalAlpha = .35; ctx.fillRect(0, 0, W, H); ctx.restore();
        if (u < .5) prev({ xf: fxf, clip: function () { ctx.beginPath(); ctx.rect(0, 0, W, H); ctx.clip(); } }); else next({ xf: fxf, clip: function () { ctx.beginPath(); ctx.rect(0, 0, W, H); ctx.clip(); } });
        ctx.save(); ctx.globalAlpha = .4 * (1 - fc); ctx.fillStyle = "#000"; ctx.translate(960, 540); ctx.scale(Math.max(.002, fc) * fs, fs); ctx.fillRect(-960, -540, W, H); ctx.restore(); break; }
      case "rings": { prev(); var nr = 8, rw = Math.hypot(960, 540) / nr;
        next({ clip: function () { ctx.beginPath(); for (var ri = 0; ri < nr; ri++) { var q = eio(clamp(u * 1.6 - (ri % 2 ? ri : nr - ri) * .06)); if (q <= 0) continue;
          var mid2 = ri * rw + rw / 2, hw = rw / 2 * q + .5; ctx.moveTo(960 + mid2 + hw, 540); ctx.arc(960, 540, mid2 + hw, 0, Math.PI * 2, false); ctx.moveTo(960 + Math.max(0, mid2 - hw), 540); ctx.arc(960, 540, Math.max(0, mid2 - hw), 0, Math.PI * 2, true); } ctx.clip(); } }); break; }
      case "stack": { prev({ xf: around(1 - .1 * u) }); ctx.save(); ctx.fillStyle = "#000"; ctx.globalAlpha = .5 * u; ctx.fillRect(0, 0, W, H); ctx.restore();
        var sx0 = W * (1 - eo(lin(lt, 0, SW)));
        ctx.save(); ctx.shadowColor = "rgba(0,0,0,.5)"; ctx.shadowBlur = 60; ctx.fillStyle = C.bg0; ctx.fillRect(sx0, 0, W, H); ctx.restore();
        next({ dx: sx0, clip: function () { ctx.beginPath(); ctx.rect(0, 0, W, H); ctx.clip(); } }); break; }
      case "shrink": { next({ xf: around(mix(1.12, 1, u)), alpha: clamp(u * 1.5) }); var ss = mix(1, .28, u);
        ctx.save(); ctx.shadowColor = "rgba(0,0,0,.45)"; ctx.shadowBlur = 50 * u; ctx.globalAlpha = 1 - clamp((u - .7) / .3);
        ctx.translate(mix(960, 330, u * u), mix(540, 230, u * u)); ctx.rotate(-.08 * u); ctx.scale(ss, ss); ctx.translate(-960, -540); ctx.fillStyle = C.bg0; ctx.fillRect(0, 0, W, H); ctx.restore();
        prev({ alpha: 1 - clamp((u - .7) / .3), xf: function () { ctx.translate(mix(960, 330, u * u), mix(540, 230, u * u)); ctx.rotate(-.08 * u); ctx.scale(ss, ss); ctx.translate(-960, -540); },
          clip: function () { ctx.beginPath(); ctx.rect(0, 0, W, H); ctx.clip(); } }); break; }
      case "flood": { prev(); var fy = H + 80 - u * (H + 200), fam = 50 * Math.sin(u * Math.PI);
        next({ clip: function () { ctx.beginPath(); ctx.moveTo(0, H); for (var fx2 = 0; fx2 <= W; fx2 += 24) ctx.lineTo(fx2, fy + Math.sin(fx2 / 150 + lt / 90) * fam + Math.sin(fx2 / 61 - lt / 60) * fam * .35); ctx.lineTo(W, H); ctx.closePath(); ctx.clip(); } });
        if (u < 1) { ctx.save(); ctx.strokeStyle = C.accent2; ctx.lineWidth = 5; ctx.globalAlpha = Math.sin(u * Math.PI); ctx.beginPath();
          for (var fx3 = 0; fx3 <= W; fx3 += 24) { var fyy = fy + Math.sin(fx3 / 150 + lt / 90) * fam + Math.sin(fx3 / 61 - lt / 60) * fam * .35; fx3 ? ctx.lineTo(fx3, fyy) : ctx.moveTo(fx3, fyy); } ctx.stroke(); ctx.restore(); } break; }
      case "focus": prev({ blur: u * 16, alpha: 1 - u, xf: around(1 + .04 * u) }); next({ blur: (1 - u) * 16, alpha: u, xf: around(1.04 - .04 * u) }); break;
      case "dissolve": { prev(); var dc = 32, dr = 18, dw = W / dc, dh = H / dr; r = rand(41); var th0 = []; for (i = 0; i < dc * dr; i++) th0.push(r() * .85);
        next({ clip: function () { ctx.beginPath(); for (var di = 0; di < dc * dr; di++) if (u >= th0[di] || u >= .999) ctx.rect((di % dc) * dw, Math.floor(di / dc) * dh, dw + .5, dh + .5); ctx.clip(); } }); break; }
      case "columns": { prev(); var nc = 12, cw3 = W / nc;
        next({ clip: function () { ctx.beginPath(); for (var ci = 0; ci < nc; ci++) { var q = eio(clamp(lin(lt, ci * SW * .04, SW * .52 + ci * SW * .04))); ctx.rect(ci * cw3 + cw3 * (1 - q) / 2, 0, cw3 * q + .5, H); } ctx.clip(); } }); break; }
      default: if (TRX[tr]) TRX[tr].draw(prev, next, u, lt, SW); else { prev(); next(); }
    }
  }
  function burnCaption(t) {
    var c = CUES.filter(function (c) { return t >= c.a && t < c.b; })[0]; if (!c || c.who) return;
    var lines = wrap(c.text.replace(/\*\*/g, ""), 1500, { size: 40, weight: 700 }), y0 = H - 70 - (lines.length - 1) * 58;
    lines.forEach(function (ln, i) { var w = tw(ln, { size: 40, weight: 700 }) + 44;
      ctx.save(); ctx.fillStyle = "rgba(4,8,12,.8)"; rr(960 - w / 2, y0 + i * 58 - 46, w, 58, 8); ctx.fill(); ctx.restore();
      txt(ln, 960, y0 + i * 58 - 4, { size: 40, weight: 700, align: "center", color: "#f5f8f9" }); });
  }
  var thumbMode = false;
  function drawBody(t) {
    scaleCtx(); backdrop(t);
    var k = sceneAt(t), tr = trOf(k), lt = t - SCENES[k].t0, SW = SWEEPS[tr];
    if (k > 0 && SW && lt < SW) transition(tr, k, t, lt, SW);
    else {
      if (k > 0 && lt < FADE && tr !== "cut" && !SW) drawScene(k - 1, t);
      drawScene(k, t);
    }
  }
  /* ---- 縦の画面（ショート。talk.format: "short"）----
     場面・立ち絵・字幕を、横の画面（1920×1080）のまま 3 枚の層に描き、縦の枠（1080×1920）に組み直す:
     上から 題 → 絵（横の画面の中央 1080×900）→ 字幕 → 立ち絵（左右の端の 600 ずつ）。後ろには、絵をぼかして敷く。 */
  var VW = 1080, VH = 1920, VPASS = "", VLAYER = {};
  function vertOn() { return (SPEC.talk || {}).format === "short"; }
  function vPaint(name, q, fn) {
    var c = VLAYER[name] || (VLAYER[name] = document.createElement("canvas")), w = Math.max(2, Math.round(W * q)), h = Math.max(2, Math.round(H * q));
    if (c.width !== w || c.height !== h) { c.width = w; c.height = h; }
    var cv0 = cv, ctx0 = ctx; cv = c; ctx = c.getContext("2d"); ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.clearRect(0, 0, w, h); scaleCtx(); VPASS = name;
    try { fn(); } finally { VPASS = ""; cv = cv0; ctx = ctx0; }
    return c;
  }
  function drawVert(t) {
    var q = cv.width / VW;
    var sc = vPaint("scene", q, function () { drawBody(t); });
    var ca = vPaint("cast", q, function () { drawCast(t); });
    var cp = vPaint("cap", q, function () { var cur = cueAt(t), capOn = recording ? !recording.clean : captions; if (cur && cur.who && capOn) drawCaption(cur, t); });
    var PX = (W - VW) / 2, PY = 300, PH = 900, CW = 720, CH = 600, CK = .75;   /* 絵: 横の画面の中央を切り出す位置・縦の枠での上の端・高さ。立ち絵: 左右の端から切り出す幅・高さと、縮める割合 */
    ctx.setTransform(q, 0, 0, q, 0, 0);
    ctx.fillStyle = "#14141a"; ctx.fillRect(0, 0, VW, VH);
    if ("filter" in ctx) { ctx.save(); ctx.filter = "blur(" + (26 * q).toFixed(1) + "px) brightness(.45)"; ctx.drawImage(sc, (PX + 240) * q, 0, 600 * q, 1066 * q, -60, -60, VW + 120, VH + 120); ctx.restore(); }
    if (isTalk(SCENES[sceneAt(t)].s)) ctx.drawImage(sc, PX * q, 0, VW * q, PH * q, 0, PY, VW, PH);
    else { var fh = VW * H / W; ctx.drawImage(sc, 0, 0, W * q, H * q, 0, PY + (PH - fh) / 2, VW, fh); }   /* 掛け合いでない場面（題・クレジット）は、切らずに全体を幅に合わせる */
    /* 題（上） */
    var ttl = String(SPEC.title || ""), to = { size: 62, weight: 900, font: TALK.font ? '"' + TALK.font + '",' + F.sans : F.sans }, tl = capWrap(ttl, 980, to).slice(0, 2);
    tl.forEach(function (l2, i) { capLine(l2, VW / 2, 150 + (i - (tl.length - 1) / 2) * 80 + 22, to, [[20, "#16161d"]], "#ffffff", "#ffe45c"); });
    /* 立ち絵（下の左右）→ 字幕（その上） */
    ctx.drawImage(ca, 0, (H - CH) * q, CW * q, CH * q, 0, VH - CH * CK, CW * CK, CH * CK);
    ctx.drawImage(ca, (W - CW) * q, (H - CH) * q, CW * q, CH * q, VW - CW * CK, VH - CH * CK, CW * CK, CH * CK);
    ctx.drawImage(cp, PX * q, (H - 400) * q, VW * q, 400 * q, 0, PY + PH - 60, VW, 400);
  }
  /* 終わりの暗転（台本の endFade: ms）: 最後の endFade の間に、映像を黒へ、音（master）を 0 へ */
  var ENDFADE = +SPEC.endFade || 0, endK = 1;
  function endVeil(t) { if (!ENDFADE || VPASS || t <= DUR - ENDFADE) return; ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalAlpha = clamp(1 - (DUR - t) / ENDFADE); ctx.fillStyle = "#000000"; ctx.fillRect(0, 0, cv.width, cv.height); ctx.restore(); }
  function draw(t) {
    if (vertOn() && !VPASS) { drawVert(t); endVeil(t); if (!thumbMode) syncDom(t); return; }
    drawBody(t);
    drawCast(t);
    chrome(t);
    if (recording && captions && !recording.clean) burnCaption(t);
    endVeil(t);
    if (!thumbMode) syncDom(t);
  }


  /* ================= 掛け合い（登場人物・せりふ・黒板） ================= */
  var CAST = SPEC.cast || {}, CASTIDS = Object.keys(CAST);
  function isTalk(s) { return Array.isArray(s.lines) && s.lines.some(function (l) { return l && l.who; }); }
  var FIRST_TALK = (function () { for (var i = 0; i < SCENES.length; i++) if (isTalk(SCENES[i].s)) return SCENES[i].t0; return -1; })();
  function cueAt(tt) { for (var i = 0; i < CUES.length; i++) if (tt >= CUES[i].a && tt < CUES[i].b) return CUES[i]; return null; }
  function lastCueOf(id, tt) { var r = null; for (var i = 0; i < CUES.length; i++) { if (CUES[i].a > tt) break; if (CUES[i].who === id) r = CUES[i]; } return r; }
  /* 口の開き 0..1: 音声ファイルは音量の並び（50ms ごと）から、読み上げ・無音は文字の拍から。時刻だけで決まる */
  function mouthOf(c, tt) {
    if (!c) return 0; var lt2 = tt - c.a, env = c.line && c.line._env;
    if (env && env.length) { var v = env[Math.min(env.length - 1, Math.floor(lt2 / 50))] || 0; return v > .55 ? 1 : v > .18 ? .5 : 0; }
    var ch = (c.text || "").replace(/\*\*/g, ""), per = Math.max(60, (c.b - c.a) / Math.max(1, ch.length)), i = Math.floor(lt2 / per), cc = ch.charAt(i);
    if (/[、。，．！？!?\s…]/.test(cc)) return 0; return Math.floor(lt2 / 95) % 3 === 0 ? 0 : Math.floor(lt2 / 95) % 3 === 1 ? 1 : .5;
  }
  function blinkOf(id, tt) { var ph = (rand(CASTIDS.indexOf(id) * 97 + 11)() * 3000) | 0, q = (tt + ph) % 3600; return q < 110 || (q > 260 && q < 340 && (CASTIDS.indexOf(id) % 2)); }
  function pickImg(ch, face, open, blink) {
    var im = ch.images || {}, f = im[face] || im.normal || im[Object.keys(im)[0]]; if (!f) return null;
    if (typeof f === "string") return IMGS[f];
    var key = blink && f.blink ? "blink" : open >= 1 && f.open ? "open" : open > 0 && f.half ? "half" : open > 0 && f.open ? "open" : "closed";
    return IMGS[f[key] || f.closed || f.open];
  }
  /* 立ち絵のパーツ（sprite）: 体の絵の上に、表情 → まばたき → 口のパーツを置いて 1 枚にする（パーツは四角の中を置き換える。組み合わせごとに覚えておく） */
  var SPR = {};
  function spriteFrame(id, ch, pose, face, open, blink) {
    var sp = ch.sprite, P = sp.poses[pose || ""] || sp.poses[""], F = P.faces[face] || P.faces.normal || {};
    var mk = open >= 1 && F.open ? "open" : open > 0 && F.half ? "half" : open > 0 && F.open ? "open" : "";
    var parts = [[P.base, 0, 0], F.e, blink && F.blink ? F.blink : null, mk ? F[mk] : null].filter(Boolean), ims = [];
    for (var i = 0; i < parts.length; i++) { var im = IMGS[sp.images[parts[i][0]]]; if (!im || !im.complete || !im.naturalWidth) return null; ims.push(im); }
    var key = parts.map(function (p) { return p[0]; }).join("|"), store = SPR[id] || (SPR[id] = { n: 0, m: {} }), c = store.m[key];
    if (!c) {
      if (store.n > Math.max(12, Math.min(60, Math.floor(3e7 / (sp.w * sp.h))))) { store.m = {}; store.n = 0; }   /* 大きい絵（SVG のパーツ）は、覚えておく枚数を減らす */
      c = document.createElement("canvas"); c.width = sp.w; c.height = sp.h; var g = c.getContext("2d");
      parts.forEach(function (p, j) { if (j) g.clearRect(p[1], p[2], ims[j].naturalWidth, ims[j].naturalHeight); g.drawImage(ims[j], p[1], p[2]); });
      store.m[key] = c; store.n++;
    }
    return c;
  }
  /* ---- 掛け合いの設定（SPEC.talk）----
     caption: "box"（白い箱とキャラ色の縁。既定）・"outline"（箱なし。白い字にキャラ色の太い縁と黒い外縁）／name: false で名札を出さない／size: 字幕の大きさ
     font: 字幕の書体（SPEC.fonts で埋め込んだ名前）／relax: せりふの後、いつもの顔と姿に戻るまでの ms（false で戻らない）
     dim: true で話していない人を薄くする／sfx: 印・大きい字幕に付ける効果音（false で付けない。{印: 効果音} で差し替え） */
  var TALK = SPEC.talk || {};
  /* 埋め込みの書体（SPEC.fonts: [{family, src: data:…, weight}]）。fetch を使わずに読む。textFont は映像の文字ぜんぶに使う書体 */
  (SPEC.fonts || []).forEach(function (f) { try { audioBytes(f.src).then(function (buf) { return new FontFace(f.family, buf, { weight: String(f.weight || "normal") }).load(); })
    .then(function (ff) { document.fonts.add(ff); needsDraw = true; }).catch(function (e) { console.warn("font:", f.family, e); }); } catch (e) { console.warn("font:", e); } });
  if (SPEC.textFont) { F.sans = '"' + SPEC.textFont + '",' + F.sans; F.display = '"' + SPEC.textFont + '",' + F.display; }
  /* 登場人物ごとの演技の並び: 自分のせりふ（途中で変わる acts を含む）と、相手のせりふへの反応（react）を時刻順に。字幕の時刻が直されたら作り直す */
  var ACTS = null, ACTKEY = "";
  function buildActs() {
    var A = {}; CASTIDS.forEach(function (id) { A[id] = []; });
    CUES.forEach(function (c) { if (!c.who || !c.line) return; var ln = c.line, d = c.b - c.a;
      if (A[c.who]) { A[c.who].push({ t: c.a, face: ln.face || "normal", pose: ln.pose || "", motion: ln.motion, mlv: ln.mlv, lv: ln.lv, end: c.b, own: 1 });
        (ln.acts || []).forEach(function (a) { A[c.who].push({ t: c.a + d * clamp(a.at || 0), face: a.face || ln.face || "normal", pose: a.pose === undefined ? ln.pose || "" : a.pose, motion: a.motion, mlv: a.mlv, lv: a.lv, end: c.b, own: 1 }); }); }
      (ln.react || []).forEach(function (r) { if (A[r.who]) A[r.who].push({ t: c.a + d * clamp(r.at === undefined ? .5 : r.at), face: r.face || "normal", pose: r.pose || "", motion: r.motion, mlv: r.mlv, lv: r.lv, emote: r.emote, end: c.b, own: 0 }); });
    });
    CASTIDS.forEach(function (id) { A[id].sort(function (a, b) { return a.t - b.t; }); });
    return A;
  }
  /* その時刻の演技 {t0 始まった時刻, face, pose, motion, mlv, lv, emote, own 自分のせりふか, idle いつもの姿に戻ったか, changed 前と絵が変わったか, pface・ppose 前の絵} */
  function stateOf(id, tt) {
    var key = CUES.length + ":" + DUR; if (key !== ACTKEY) { ACTS = buildActs(); ACTKEY = key; }
    var L = ACTS[id] || [], n = -1, relax = TALK.relax === false ? 0 : TALK.relax || 1500, rest = (CAST[id] || {}).rest || "normal";
    for (var j = 0; j < L.length; j++) { if (L[j].t > tt) break; n = j; }
    if (n < 0) return { face: rest, pose: "", idle: true };
    var a = L[n], p = n > 0 ? L[n - 1] : null, pf = !p ? { face: rest, pose: "" } : relax && a.t > p.end + relax ? { face: rest, pose: "" } : p;
    if (relax && tt > a.end + relax) return { t0: a.end + relax, face: rest, pose: "", idle: true, changed: a.face !== rest || a.pose !== "", pface: a.face, ppose: a.pose };
    return { t0: a.t, face: a.face, pose: a.pose, motion: a.motion, mlv: a.mlv, lv: a.lv, emote: a.emote, own: a.own, changed: pf.face !== a.face || pf.pose !== a.pose, pface: pf.face, ppose: pf.pose };
  }
  /* 声の大きさ 0..1（50ms ごとの音量の並びをならしたもの。声が無ければ一定の拍）。話している間の弾みに使う */
  function voiceLevel(c, tt) {
    var env = c.line && c.line._env; if (!env || !env.length) return Math.abs(Math.sin((tt - c.a) / 180));
    var q = (tt - c.a) / 50, i0 = Math.floor(q), f = q - i0, g = function (k) { return env[Math.max(0, Math.min(env.length - 1, k))] || 0; };
    return clamp((g(i0 - 1) + 2 * mix(g(i0), g(i0 + 1), f) + g(i0 + 2)) / 4 * 1.5);
  }
  /* 立ち絵の動き（時刻だけで決まる）: いつもの呼吸と揺れ、演技（表情・体）が変わったときの弾み、身ぶり。
     身ぶりは演技の motion で選ぶ。無ければ表情から決める。大きさは motion の度合い mlv（無ければ表情の度合い lv。1 控えめ・2 ふつう・3 強め）。
     表情・体の名前の #2 などは同じラベルとして扱う。返すのは、足元を軸にした {x, y, rot, sx, sy, flip}（flip は左右の向き。1 から -1）。
     cast.<名前>.motion: false か SPEC.castMotion: false、OS の「動きを減らす」で止まる。"yukkuri" は、話している間に縦に伸び縮みする（頭だけの立ち絵向け） */
  var CAST_STILL = !!(window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches);
  var FACE_MOTION = { surprised: "jump", smile: "hop", angry: "tremble", sad: "sink", troubled: "fidget", think: "tilt", shy: "sway", smug: "lean", doubt: "back", dizzy: "wobble", love: "bounce" };
  function castMotion(id, i, ch, tt, st, speakingNow, side) {
    var m = { x: 0, y: 0, rot: 0, sx: 1, sy: 1, flip: 1 }, face = st.face, pose = st.pose, kind = st.motion || (st.idle ? "" : FACE_MOTION[String(face).split("#")[0]]);
    if (CAST_STILL || SPEC.castMotion === false || ch.motion === false || ch.motion === "none" || kind === "still") return m;
    var ph = i * 1.7 + 0.6, br = Math.sin(tt / 1150 + ph), dir = side === "right" ? -1 : 1, sin = Math.sin, PI = Math.PI;
    m.sy += .006 * br; m.sx -= .003 * br; m.rot += .004 * sin(tt / 1900 + ph * 2);
    if (st.t0 === undefined) return m;
    var lt = tt - st.t0;
    if (st.changed && lt < 320) { var e = lt / 320, pop = sin(e * PI) * (1 - e) * (st.idle ? .5 : 1); m.sy += .06 * pop; m.sx -= .035 * pop; }
    if (st.idle) return m;
    var lv = st.motion ? st.mlv || 2 : st.lv || 2, A = lv >= 3 ? 1.6 : lv <= 1 ? .55 : 1, s0 = clamp(lt / 450), ease = s0 * s0 * (3 - 2 * s0), own = !!st.motion, k, q;
    if (kind === "jump") { if (lt < 340) m.y -= 28 * A * sin(lt / 340 * PI); if (!own) m.rot -= .012 * dir * ease; }
    else if (kind === "hop") { if (lt < 760) m.y -= 13 * A * Math.abs(sin(lt / 190 * PI / 2)) * (1 - lt / 760); }
    else if (kind === "bounce") { if (speakingNow || lt < 900) m.y -= 12 * A * Math.abs(sin(lt / 170)); }
    else if (kind === "nod") { if (lt < 640) { var nd = Math.abs(sin(lt / 320 * PI)); m.y += 9 * A * nd; m.rot += .012 * A * dir * nd; } }
    else if (kind === "sway") { m.rot += .012 * A * sin(lt / 300); m.y += 3 * ease; }
    else if (kind === "lean") { m.rot += .018 * A * dir * ease; m.x += 7 * A * dir * ease; }
    else if (kind === "back") { m.rot -= .018 * A * dir * ease; m.x -= 7 * A * dir * ease; }
    else if (kind === "sink") { m.y += 10 * A * ease; m.rot += .012 * dir * ease; m.sy -= .012 * A * ease; }
    else if (kind === "tremble") { m.x += 5 * A * sin(lt / 24) * (own ? 1 : clamp(1 - lt / 380)); if (!own) m.rot += .014 * dir * ease; }
    else if (kind === "fidget") { m.x += 2.5 * A * sin(lt / 55) * clamp(1 - lt / 700); m.rot -= .008 * dir * ease; }
    else if (kind === "tilt") { m.rot -= .022 * A * dir * ease; }
    else if (kind === "wobble") { m.rot += .03 * A * sin(lt / 210); m.x += 4 * A * sin(lt / 330); }
    else if (kind === "shakehead") { k = clamp(1 - lt / 800); m.x += 10 * A * sin(lt / 52) * k; m.rot += .012 * A * sin(lt / 52) * k; }                       /* いやいや */
    else if (kind === "stomp") { if (lt < 1000) { k = clamp(1 - lt / 1000); m.y -= 11 * A * Math.abs(sin(lt / 68)) * k; m.x += 4 * A * sin(lt / 43) * k; m.rot += .012 * sin(lt / 60) * k; } }   /* じたばた */
    else if (kind === "spin") { if (lt < 520) { m.flip = Math.cos(lt / 520 * 2 * PI); m.y -= 16 * A * sin(lt / 520 * PI); } }                                 /* くるっと回る */
    else if (kind === "turn") { m.flip = 1 - 2 * eio(clamp(lt / 240)); m.rot -= .01 * dir * ease; }                                                           /* そっぽを向く */
    else if (kind === "zukkoke") { k = lt < 240 ? eo(lt / 240) : lt < 820 ? 1 : lt < 1120 ? 1 - eo((lt - 820) / 300) : 0;                                      /* ずっこける */
      m.rot -= dir * .5 * Math.min(A, 1.25) * k; m.y += 22 * k; if (lt > 240 && lt < 480) m.y -= 8 * sin((lt - 240) / 240 * PI); }
    else if (kind === "bow") { k = sin(clamp(lt / 900) * PI); m.rot += dir * .15 * A * k; m.y += 6 * k; }                                                     /* おじぎ */
    else if (kind === "squash") { k = lt < 150 ? lt / 150 : Math.exp(-(lt - 150) / 170) * Math.cos((lt - 150) / 62); m.sy -= .17 * A * k; m.sx += .12 * A * k; }  /* ぺしゃっ */
    else if (kind === "stretch") { k = sin(clamp(lt / 720) * PI); m.sy += .1 * A * k; m.sx -= .05 * A * k; }                                                  /* のびる */
    else if (kind === "pulse") { q = Math.pow(Math.abs(sin(lt / 240)), 3); m.sx += .035 * A * q; m.sy += .035 * A * q; }                                      /* どきどき */
    else if (kind === "peek") { m.x += 46 * A * dir * ease; m.rot += .012 * dir * ease; m.sx += .04 * ease; m.sy += .04 * ease; }                            /* ずいっと寄る */
    else if (kind === "away") { m.x -= 30 * A * dir * ease; m.rot -= .014 * dir * ease; }                                                                    /* 後ずさり */
    else if (kind === "float") { m.y -= 12 * A * (.5 + .5 * sin(lt / 520 - PI / 2)) * ease; m.rot += .008 * sin(lt / 800); }                                  /* ふわふわ */
    else if (kind === "zoom") { k = (lt < 200 ? back(lt / 200) : 1) * (lt < 1500 ? 1 : clamp(1 - (lt - 1500) / 320)); m.sx += .15 * A * k; m.sy += .15 * A * k; }  /* どーんと大きく */
    else if (kind === "shrink") { m.sx -= .09 * A * ease; m.sy -= .09 * A * ease; }                                                                          /* しゅんと小さく */
    else if (kind === "dance") { m.rot += .03 * A * sin(lt / 190); m.y -= 9 * A * Math.abs(sin(lt / 190)); m.x += 6 * A * sin(lt / 380); }                    /* るんるん */
    var body = String(pose).split("#")[0].split("+");
    if (!own && body.indexOf("raise") >= 0 && lt < 520) m.y -= 10 * sin(lt / 520 * PI);
    if (!own && body.indexOf("point") >= 0 && lt < 300) m.x += 8 * dir * sin(lt / 300 * PI);
    if (ch.motion === "yukkuri" && speakingNow) { q = Math.abs(sin(lt / 170)); m.sy += .05 * q; m.sx -= .03 * q; }
    return m;
  }
  /* 仮のキャラクター（画像が無いとき）: 丸い顔・髪の帯・目・口。色は cast の color */
  function drawDummy(ch, x, by, h, open, blink, face) {
    var col = ch.color || C.accent, r = h * .22, cy = by - h + r + 20;
    ctx.save(); ctx.fillStyle = col; rr(x - r * .95, cy + r * .7, r * 1.9, h - r * 1.7 - 20, r * .6); ctx.fill();
    ctx.fillStyle = "#fde7d6"; ctx.beginPath(); ctx.arc(x, cy, r, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = col; ctx.beginPath(); ctx.arc(x, cy - r * .15, r * 1.04, Math.PI * 1.05, Math.PI * 1.95); ctx.fill();
    ctx.fillStyle = "#2a2230"; var ey = cy + r * .05;
    [-1, 1].forEach(function (sd) { if (blink) { ctx.fillRect(x + sd * r * .38 - r * .14, ey, r * .28, 4); } else { ctx.beginPath(); ctx.ellipse(x + sd * r * .38, ey, r * .1, r * (face === "surprised" ? .2 : .15), 0, 0, Math.PI * 2); ctx.fill(); } });
    ctx.fillStyle = "#9b2d3a"; var mh = r * (.04 + .22 * open), mw = r * (face === "smile" ? .34 : .26);
    ctx.beginPath(); ctx.ellipse(x, cy + r * .5, mw, Math.max(2, mh), 0, 0, Math.PI * 2); ctx.fill();
    if (face === "smile" && open === 0) { ctx.strokeStyle = "#9b2d3a"; ctx.lineWidth = 4; ctx.beginPath(); ctx.arc(x, cy + r * .38, r * .22, .2, Math.PI - .2); ctx.stroke(); }
    if (face === "angry") { ctx.strokeStyle = "#2a2230"; ctx.lineWidth = 5; [-1, 1].forEach(function (sd) { ctx.beginPath(); ctx.moveTo(x + sd * r * .55, ey - r * .32); ctx.lineTo(x + sd * r * .2, ey - r * .2); ctx.stroke(); }); }
    ctx.restore();
  }
  /* 気持ちの印。絵文字の書体に頼らず、線と形で描く（どの環境でも同じに出る）。lt は出てからの ms、sd は顔の外側の向き（左の人 1・右の人 -1） */
  var EMO_ALIAS = { "！": "!", "？": "?", "！？": "!?", "?!": "!?", "汗": "💦", "怒": "💢", "ひらめき": "💡", "キラ": "✨", "きら": "✨", "ハート": "♥", "❤": "♥", "ガーン": "gloom", "がーん": "gloom", "ZZZ": "zzz", "音符": "♪", "無言": "…", "集中": "shock", "ショック": "shock" };
  function drawEmote(em, ex, ey, lt, col, sd) {
    em = EMO_ALIAS[em] || em; var k = P(lt, 0, 350, back), sin = Math.sin, PI = Math.PI, i;
    ctx.save(); ctx.translate(ex, ey); ctx.lineJoin = "round"; ctx.lineCap = "round";
    var edge = function (w) { ctx.strokeStyle = "#ffffff"; ctx.lineWidth = w; ctx.stroke(); };
    if (em === "💦") {   /* 汗: しずくが 2 つ、すべり落ちる */
      for (i = 0; i < 2; i++) { var u = ((lt + i * 420) % 900) / 900, a = clamp(u * 5) * clamp((1 - u) * 3);
        ctx.save(); ctx.globalAlpha *= a * Math.min(1, k); ctx.translate(sd * (8 + i * 34), -30 + u * 46 + i * 18); ctx.rotate(sd * .3); ctx.scale(1 - i * .25, 1 - i * .25);
        ctx.beginPath(); ctx.moveTo(0, -30); ctx.bezierCurveTo(20, 0, 17, 22, 0, 22); ctx.bezierCurveTo(-17, 22, -20, 0, 0, -30); edge(8); ctx.fillStyle = "#58b7f0"; ctx.fill();
        ctx.fillStyle = "rgba(255,255,255,.85)"; ctx.beginPath(); ctx.ellipse(-5, 6, 3.5, 7, .3, 0, PI * 2); ctx.fill(); ctx.restore(); } }
    else if (em === "💢") {   /* 怒り: 4 つのかぎ形が脈打つ */
      var ps = k * (1 + .12 * sin(lt / 110)); ctx.scale(ps, ps); ctx.translate(sd * 14, -6); ctx.beginPath();
      [[1, 1], [-1, 1], [-1, -1], [1, -1]].forEach(function (q) { ctx.moveTo(q[0] * 34, q[1] * 10); ctx.quadraticCurveTo(q[0] * 10, q[1] * 10, q[0] * 10, q[1] * 34); });
      edge(18); ctx.strokeStyle = "#e5323e"; ctx.lineWidth = 9; ctx.stroke(); }
    else if (em === "💡") {   /* ひらめき: 電球と光の線 */
      ctx.scale(k, k); ctx.translate(sd * 10, -18);
      ctx.strokeStyle = "#f5b301"; ctx.lineWidth = 6; var rk = .6 + .4 * sin(lt / 120);
      for (i = 0; i < 7; i++) { var an = -PI + i * PI / 6; ctx.beginPath(); ctx.moveTo(Math.cos(an) * 44, Math.sin(an) * 44 - 6); ctx.lineTo(Math.cos(an) * (54 + 10 * rk), Math.sin(an) * (54 + 10 * rk) - 6); ctx.stroke(); }
      ctx.beginPath(); ctx.arc(0, -6, 30, PI * .78, PI * 2.22); ctx.lineTo(13, 28); ctx.lineTo(-13, 28); ctx.closePath(); edge(8); ctx.fillStyle = "#ffd84a"; ctx.fill();
      ctx.fillStyle = "#8a8f98"; rr(-12, 30, 24, 14, 4); ctx.fill(); }
    else if (em === "✨") {   /* きらきら: 星が 3 つ、順にまたたく */
      [[0, -10, 30, 0], [sd * 46, -44, 18, 300], [sd * -30, -52, 14, 600]].forEach(function (q) { var tk = .55 + .45 * sin((lt + q[3]) / 170), r0 = q[2] * tk * Math.min(1, k);
        ctx.beginPath(); for (var j = 0; j < 8; j++) { var an = j * PI / 4 - PI / 2, rr2 = j % 2 ? r0 * .3 : r0; j ? ctx.lineTo(q[0] + Math.cos(an) * rr2, q[1] + Math.sin(an) * rr2) : ctx.moveTo(q[0] + Math.cos(an) * rr2, q[1] + Math.sin(an) * rr2); }
        ctx.closePath(); edge(6); ctx.fillStyle = "#ffd84a"; ctx.fill(); }); }
    else if (em === "♥") {   /* ハート: ふくらみながら浮く */
      var hb = k * (1 + .1 * sin(lt / 140)); ctx.translate(sd * 12, -10 - 8 * sin(lt / 420)); ctx.scale(hb, hb);
      ctx.beginPath(); ctx.moveTo(0, 26); ctx.bezierCurveTo(-46, -6, -24, -44, 0, -18); ctx.bezierCurveTo(24, -44, 46, -6, 0, 26); edge(9); ctx.fillStyle = "#f0508c"; ctx.fill(); }
    else if (em === "gloom") {   /* ガーン: 頭の上から青い縦線が下りる */
      ctx.strokeStyle = "#5a6fb0"; ctx.lineWidth = 5; for (i = 0; i < 6; i++) { var gl = (38 + (i % 3) * 22) * clamp((lt - i * 50) / 300); ctx.globalAlpha = .75;
        ctx.beginPath(); ctx.moveTo(-sd * 20 + sd * (-50 + i * 18), 20); ctx.lineTo(-sd * 20 + sd * (-50 + i * 18), 20 + gl); ctx.stroke(); } }
    else if (em === "shock") {   /* ショック: 短い線が放射に走る */
      ctx.strokeStyle = col; ctx.lineWidth = 7; var sk = clamp(lt / 200), fd = clamp(1 - (lt - 500) / 400); ctx.globalAlpha *= fd;
      for (i = 0; i < 7; i++) { var an2 = -PI * .95 + i * PI * .9 / 6 + (sd < 0 ? 0 : PI * .05); ctx.beginPath(); ctx.moveTo(Math.cos(an2) * 30, Math.sin(an2) * 30 + 30); ctx.lineTo(Math.cos(an2) * (30 + 46 * sk), Math.sin(an2) * (30 + 46 * sk) + 30); edge(13); ctx.strokeStyle = col; ctx.lineWidth = 7; ctx.stroke(); } }
    else if (em === "zzz") { for (i = 0; i < 3; i++) { var zu = ((lt + i * 500) % 1500) / 1500; txtEdge("z", sd * (i * 22 + zu * 14), 10 - i * 30 - zu * 26, 44 + i * 12, col, clamp(zu * 4) * clamp((1 - zu) * 3)); } }
    else if (em === "…") { for (i = 0; i < 3; i++) { var dk = clamp((lt - i * 220) / 200); ctx.beginPath(); ctx.arc(sd * 4 + (i - 1) * 30, -10, 9 * dk, 0, PI * 2); edge(7); ctx.fillStyle = "#6b7480"; ctx.fill(); } }
    else if (em === "♪") { ctx.translate(sd * 10, -6 * sin(lt / 300)); ctx.rotate(.14 * sin(lt / 260)); ctx.scale(k, k); txtEdge("♪", 0, 0, 96, col, 1); }
    else if (em === "?") { ctx.rotate(.16 * sin(lt / 240) * clamp(1 - lt / 1400)); ctx.scale(k, k); txtEdge("？", 0, 0, 100, col, 1); }
    else if (em === "!" || em === "!?") { var jk = lt < 420 ? 1 + .18 * sin(lt / 420 * PI) : 1; ctx.translate(lt < 260 ? 4 * sin(lt / 22) : 0, 0); ctx.scale(k * jk, k * jk); txtEdge(em === "!" ? "！" : "！？", 0, 0, 100, em === "!?" ? "#e5323e" : col, 1); }
    else { ctx.scale(k, k); txtEdge(em, 0, 0, 84, col, 1); }
    ctx.restore();
  }
  function txtEdge(s, x, y, size, col, alpha) {   /* 白い縁の付いた太い字 */
    ctx.save(); ctx.globalAlpha *= alpha; ctx.font = font({ size: size, weight: 900, font: TALK.font ? '"' + TALK.font + '",' + F.sans : F.sans }); ctx.textAlign = "center"; ctx.lineJoin = "round";
    ctx.lineWidth = size * .16; ctx.strokeStyle = "#ffffff"; ctx.strokeText(s, x, y); ctx.fillStyle = col; ctx.fillText(s, x, y); ctx.restore();
  }
  /* 字幕の 1 行。**強調** は色を変える。layers は外から順に [太さ, 色] */
  function capLine(line, cx, y, o, layers, fill, emFill) {
    var parts = String(line).split("**"), ws = parts.map(function (p2) { return tw(p2, o); }), x = cx - ws.reduce(function (a, b) { return a + b; }, 0) / 2;
    ctx.save(); ctx.font = font(o); ctx.textAlign = "left"; ctx.lineJoin = "round";
    layers.forEach(function (L) { var xx = x; ctx.lineWidth = L[0]; ctx.strokeStyle = L[1]; parts.forEach(function (p2, j) { if (p2) ctx.strokeText(p2, xx, y); xx += ws[j]; }); });
    var xx = x; parts.forEach(function (p2, j) { if (p2) { ctx.fillStyle = j % 2 ? emFill : fill; ctx.fillText(p2, xx, y); } xx += ws[j]; });
    ctx.restore();
  }
  /* 字幕の型（TALK.caption）: outline・box のほかに、手本の動画から取った 4 つ。
     bar: 下に暗い角丸の箱（白い縁）を置きっぱなしにし、話し手の色の字（列挙・資料の型）／band: 下に白く透ける帯、小さめの字（図解の型）／
     strip: 下に黒い帯、黄色い字（怪談・物語の型）／bubble: 話し手のそばに、話し手の色で縁取った白い箱（寸劇の型。立ち絵の無い語り手は、下の中央に暗い箱） */
  var CAPBAR = { bar: 1, band: 1, strip: 1 }, CPOS = {};
  function capTop() { var sz = TALK.size || (TALK.caption === "band" ? 44 : 50); return TALK.caption === "band" ? 1080 - (sz * 2.6 + 70) : 1080 - (sz * 2.6 + 62); }
  function tintCol(col, t) { var m = /^#?([0-9a-f]{6})$/i.exec(col || ""); if (!m) return col; var n = parseInt(m[1], 16);
    return "rgb(" + [n >> 16, n >> 8 & 255, n & 255].map(function (v) { return Math.round(t < 0 ? v * (1 + t) : v + (255 - v) * t); }).join(",") + ")"; }   /* t > 0 で白へ、t < 0 で黒へ寄せる */
  function capBack() {   /* 置きっぱなしの帯・箱（せりふの無い間も出ている） */
    var y = capTop(), m = TALK.caption;
    if (m === "bar") {   /* すりガラス: 箱の後ろ（背景・写真）をぼかして透かし、暗い色を薄く重ねる（背景を箱の上で切らない。字は太い黒縁なので読める） */
      var frost = "filter" in ctx && ctx.getTransform;
      if (frost) { var tm = ctx.getTransform(), cvs = ctx.canvas, pad = 48 * tm.a, sx = Math.max(0, Math.floor(36 * tm.a + tm.e - pad)), sy = Math.max(0, Math.floor(y * tm.d + tm.f - pad)),
          sw = Math.min(cvs.width - sx, Math.ceil(1848 * tm.a + 2 * pad)), sh = Math.min(cvs.height - sy, Math.ceil((1080 - y) * tm.d + 2 * pad));
        if (sw > 0 && sh > 0) { ctx.save(); rr(36, y, 1848, 1080 - y - 14, 18); ctx.clip(); ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.filter = "blur(" + (16 * tm.a).toFixed(1) + "px)"; ctx.drawImage(cvs, sx, sy, sw, sh, sx, sy, sw, sh); ctx.restore(); } }
      rr(36, y, 1848, 1080 - y - 14, 18); ctx.fillStyle = frost ? "rgba(16,16,22,.56)" : "rgba(20,20,26,.88)"; ctx.fill(); ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 4; ctx.stroke(); }
    else if (m === "band") { ctx.fillStyle = "rgba(255,255,255,.74)"; ctx.fillRect(0, y, 1920, 1080 - y); }
    else if (m === "strip") { ctx.fillStyle = "rgba(0,0,0,.9)"; ctx.fillRect(0, y, 1920, 1080 - y); }
  }
  /* 字幕の折り返し: 2 行になるときは、読点・句点・空白の後ろで折る（語の途中で折らない）。切れ目が無ければ、助詞の後ろ、それも無ければ幅で折る */
  function capWrap(text, maxW, o, lim) {   /* lim: 語を 2 行目へ送るときの幅の上限（2 行をそろえるために狭く折るときは、本来の幅） */
    var lines = wrap(text, maxW, o); if (lines.length !== 2) return lines;
    var plain = String(text), best = -1, bestD = 1e9, total = tw(plain.replace(/\*\*/g, ""), o);
    var tryAt = function (re, pen) { var m; re.lastIndex = 0; while ((m = re.exec(plain))) { var i = m.index + m[0].length; if (i < 3 || i > plain.length - 3) continue;
      if ((plain.slice(0, i).match(/\*\*/g) || []).length % 2) continue;   /* 強調（**…**）の中では折らない */
      var a = tw(plain.slice(0, i).replace(/\*\*/g, ""), o), b = total - a; if (a > maxW || b > maxW) continue; var d = Math.abs(a - b) + pen; if (d < bestD) { bestD = d; best = i; } } };
    tryAt(/[、。！？!?…　]+/g, 0);
    if (best < 0 || bestD > total * .5) tryAt(/[^「『（(]+?(?=[「『（(])/g, total * .05);   /* かぎかっこ・かっこの前でも折れる */   /* 半角の空白（英字と仮名の間）では折らない。「React／を」のように助詞が行頭に来るため */
    if (best < 0 || bestD > total * .5) tryAt(/[ぁ-ん](?:は|が|を|に|で|と|も|の|へ|から|まで|より|って|ので|けど|ても|たら|なら)(?=[^ぁ-ん])/g, total * .12);
    if (best < 0) {   /* 幅で折ったとき: 2 行目の頭の句読点・閉じかっこは 1 行目の終わりへ（行頭に「、」を置かない） */
      var m2 = /^[、。，．！？!?」』）)…ー]+/.exec(lines[1]); if (m2) { lines = [lines[0] + m2[0], lines[1].slice(m2[0].length)]; }
      var m3 = /[A-Za-z0-9.\-]+$/.exec(lines[0]);   /* 英字の語の直後で折れて、2 行目が助詞から始まるときは、英字の語ごと 2 行目へ */
      if (m3 && /^[をのがにはでとへもや]/.test(lines[1]) && m3[0].length < lines[0].length - 2 && tw(m3[0] + lines[1], o) <= (lim || maxW)) lines = [lines[0].slice(0, -m3[0].length), m3[0] + lines[1]];
      /* カタカナ語・英単語の途中で折れたとき（「フレームワー／ク」）は、語ごと 2 行目へ */
      [[/[ァ-ヶー]+$/, /^[ァ-ヶー]/], [/[A-Za-z]+$/, /^[A-Za-z]/]].forEach(function (p) { var m4 = p[0].exec(lines[0]);
        if (m4 && p[1].test(lines[1]) && m4[0].length < lines[0].length - 2 && tw(m4[0] + lines[1], o) <= (lim || maxW)) lines = [lines[0].slice(0, -m4[0].length), m4[0] + lines[1]]; });
      return lines; }
    return [plain.slice(0, best).trim(), plain.slice(best).trim()];
  }
  function drawCaption(cur, tt) {
    var vert = vertOn();
    if (!vert && (CAPBAR[TALK.caption] || TALK.caption === "bubble")) return drawCaption2(cur, tt);
    var sp = CAST[cur.who] || {}, col = sp.color || C.accent, ln = cur.line || {}, big = !!ln.big, outline = vert || TALK.caption === "outline", lt = tt - cur.a;
    var size = (vert ? Math.max(TALK.size || 0, 62) : TALK.size || (outline ? 56 : 46)) * (big && !vert ? 1.32 : 1), fam = TALK.font ? '"' + TALK.font + '",' + F.sans : F.sans, o = { size: size, weight: 800, font: fam };
    var maxW = vert ? 960 : outline ? 1180 : 1080, lines = capWrap(cur.text, maxW, o), lh = size * 1.3, ck = P(lt, 0, 200);
    /* 2 行目が数文字だけ残るときは、2 行の長さをそろえる */
    if (lines.length === 2 && lines[1].replace(/\*\*/g, "").length <= 5) { var even = capWrap(cur.text, Math.max(maxW * .5, tw(cur.text.replace(/\*\*/g, ""), o) * .58), o, maxW); if (even.length === 2) lines = even; }
    lines = lines.slice(0, vert ? 3 : 2);
    var named = TALK.name === undefined ? !outline : TALK.name !== false, pk = big ? 1 + (vert ? .08 : .22) * (1 - P(lt, 0, 240, back)) : 1, jx = big && lt < 300 ? 5 * Math.sin(lt / 20) * (1 - lt / 300) : 0;
    ctx.save(); ctx.globalAlpha *= ck;
    if (outline) {
      var base = (vert ? 760 + size + (named ? 60 : 0) : 1040 - (lines.length - 1) * lh); ctx.translate(960 + jx, base); ctx.scale(pk, pk); ctx.translate(-960, -base);
      if (named) { var nm = sp.name || cur.who, nw0 = tw(nm, { size: 26, weight: 800, font: fam }) + 36; rr(960 - nw0 / 2, base - size - 44, nw0, 40, 20); ctx.fillStyle = col; ctx.fill(); ctx.lineWidth = 4; ctx.strokeStyle = "#ffffff"; ctx.stroke();
        txt(nm, 960, base - size - 16, { size: 26, weight: 800, align: "center", color: "#ffffff", font: fam }); }
      lines.forEach(function (l2, i) { capLine(l2, 960, base + i * lh, o, [[size * .34, "#16161d"], [size * .22, col]], "#ffffff", "#ffe45c"); });
    } else {
      var bh = 60 + lines.length * lh * (46 / size) * (size / 46), by0 = 1060 - bh, bx = 400, bw = 1120;
      ctx.translate(960 + jx, by0 + bh / 2); ctx.scale(pk, pk); ctx.translate(-960, -(by0 + bh / 2));
      rr(bx, by0, bw, bh, 18); ctx.fillStyle = "rgba(255,255,255,.92)"; ctx.fill(); ctx.strokeStyle = col; ctx.lineWidth = 6; ctx.stroke();
      if (named) { var nw = tw(sp.name || cur.who, { size: 26, weight: 800, font: fam }) + 40; rr(bx + 24, by0 - 22, nw, 44, 22); ctx.fillStyle = col; ctx.fill();
        txt(sp.name || cur.who, bx + 24 + nw / 2, by0 + 9, { size: 26, weight: 800, align: "center", color: "#ffffff", font: fam }); }
      lines.forEach(function (l2, i) { capLine(l2, 960, by0 + 24 + size + i * lh, o, [[size * .2, col]], "#ffffff", "#fff3a0"); });
    }
    ctx.restore();
  }
  /* 字幕を行に分ける。2 行以上になるとき、句読点の後で 2 行に分けられるなら（どちらの行も幅に収まるなら）、まん中にいちばん近い句読点で折る。
     無ければ capWrap のまま（語の途中で折れることがある: 「すれ違うた／めの場所」）。 */
  function capSplit(text, maxW, o) {
    var L = capWrap(text, maxW, o);
    if (L.length <= 1 || text.indexOf("**") >= 0) return L;
    var best = -1, mid = text.length / 2, w = function (s2) { return tw(s2, o); };
    for (var i = 1; i < text.length - 2; i++) {
      if (!/[、。！？!?…]/.test(text[i]) || /[、。！？!?…」）』]/.test(text[i + 1])) continue;
      var a = text.slice(0, i + 1), b2 = text.slice(i + 1).replace(/^[ \u3000]+/, "");
      if (w(a) <= maxW && w(b2) <= maxW && (best < 0 || Math.abs(i - mid) < Math.abs(best - mid))) best = i;
    }
    if (best < 0) return L;
    var out = [text.slice(0, best + 1), text.slice(best + 1).replace(/^[ \u3000]+/, "")]; out.punct = true; return out;
  }
  /* 帯の字幕を 2 行に収める字の大きさと行: ① 句読点の後で折れる大きさ（8 割まで小さくして探す）→ ② 無ければ、2 行に収まる最初の大きさ */
  function capFit(text, maxW, size, font) {
    var K = [1, .93, .86, .8], o, L, i;
    for (i = 0; i < K.length; i++) { o = { size: size * K[i], weight: 800, font: font }; L = capSplit(text, maxW, o); if (L.length <= 1 || L.punct) return { lines: L, o: o }; }
    for (i = 0; i < K.length; i++) { o = { size: size * K[i], weight: 800, font: font }; L = capSplit(text, maxW, o); if (L.length <= 2) return { lines: L, o: o }; }
    o = { size: size * .74, weight: 800, font: font }; return { lines: capSplit(text, maxW, o), o: o };
  }
  function drawCaption2(cur, tt) {
    var sp = CAST[cur.who] || {}, col = sp.color || C.accent, ln = cur.line || {}, big = !!ln.big, lt = tt - cur.a, m = TALK.caption, fam = TALK.font ? '"' + TALK.font + '",' + F.sans : F.sans;
    var pk = big ? 1 + .18 * (1 - P(lt, 0, 240, back)) : 1, ck = P(lt, 0, 160);
    ctx.save(); ctx.globalAlpha *= ck;
    if (m === "bubble") {
      var pos = CPOS[cur.who], size = (TALK.size || 40) * (big ? 1.25 : 1), o = { size: size, weight: 800, font: fam }, lh = size * 1.34;
      if (!pos || sp.hidden) {   /* 語り手: 下の中央に、暗く透ける箱と黄色い字 */
        var nl = wrap(cur.text, 1240, o).slice(0, 2), nw = Math.max.apply(null, nl.map(function (l) { return tw(l.replace(/\*\*/g, ""), o); })) + 72, nh = nl.length * lh + 34, ny = 1040 - nh;
        rr(960 - nw / 2, ny, nw, nh, 16); ctx.fillStyle = "rgba(24,24,30,.74)"; ctx.fill();
        nl.forEach(function (l2, i) { capLine(l2, 960, ny + 22 + size * .86 + i * lh, o, [[size * .16, "#16161d"]], "#ffe45c", "#ffffff"); });
        ctx.restore(); return; }
      var ls = wrap(cur.text, 600, o).slice(0, 3), bw = Math.max(150, Math.max.apply(null, ls.map(function (l) { return tw(l.replace(/\*\*/g, ""), o); })) + 56), bh = ls.length * lh + 30;
      var cx = clamp(pos.side === "right" ? pos.x - pos.w * .12 - bw / 2 : pos.x + pos.w * .12 + bw / 2, bw / 2 + 24, 1896 - bw / 2), cy = clamp(pos.by - pos.h * .36, bh / 2 + 120, 1040 - bh / 2);
      ctx.translate(cx, cy); ctx.scale(pk * (.9 + .1 * P(lt, 0, 200, back)), pk * (.9 + .1 * P(lt, 0, 200, back))); ctx.translate(-cx, -cy);
      ctx.shadowColor = "rgba(0,0,0,.25)"; ctx.shadowBlur = 12; ctx.shadowOffsetY = 4; rr(cx - bw / 2, cy - bh / 2, bw, bh, 16); ctx.fillStyle = "#ffffff"; ctx.fill(); ctx.shadowColor = "transparent";
      ctx.strokeStyle = col; ctx.lineWidth = 7; ctx.stroke();
      ls.forEach(function (l2, i) { capLine(l2, cx, cy - bh / 2 + 15 + size * .9 + i * lh, o, [], "#20242c", "#d9343f"); });
      ctx.restore(); return; }
    var size2 = (TALK.size || (m === "band" ? 44 : 50)) * (big ? 1.25 : 1), o2 = { size: size2, weight: 800, font: fam }, lh2 = size2 * 1.3, y0 = capTop(), hh = 1080 - y0 - (m === "bar" ? 14 : 0);
    /* 2 行に収める: 収まらなければ字を少しずつ小さくする（前は 3 行目が箱の外に切れていた）。折る所は、できれば句読点の後（capSplit） */
    var capW = Math.min(TALK.capWidth || 1e9, m === "bar" ? 1500 : 1560), lines = [];
    var fit = capFit(cur.text, capW, size2, fam); lines = fit.lines; o2 = fit.o;
    size2 = o2.size; lh2 = size2 * 1.3;
    if (lines.length === 2 && !lines.punct && lines[1].replace(/\*\*/g, "").length <= 5) { var even = capWrap(cur.text, Math.max(700, tw(cur.text.replace(/\*\*/g, ""), o2) * .58), o2, capW); if (even.length === 2) lines = even; }
    lines = lines.slice(0, 2);
    var cy2 = y0 + hh / 2, base = cy2 - (lines.length - 1) * lh2 / 2 + size2 * .36;
    var CXc = TALK.capX || 960;   /* 字幕のまん中（左右の立ち絵の数が違うとき、空いている側へ寄せる。yukkuri-kaisetsu が決める） */
    ctx.translate(CXc, cy2); ctx.scale(pk, pk); ctx.translate(-CXc, -cy2);
    var fill = m === "strip" ? (TALK.capColor === "speaker" ? tintCol(col, .45) : "#ffe45c") : m === "bar" ? tintCol(col, .38) : tintCol(col, -.3), edge = m === "band" ? [[size2 * .2, "#ffffff"]] : [[size2 * .2, "#000000"]];
    lines.forEach(function (l2, i) { capLine(l2, CXc, base + i * lh2, o2, edge, fill, m === "band" ? "#d9343f" : "#ffffff"); });
    if (TALK.name === true) {   /* 置きっぱなしの字幕でも、話し手の名前の札を帯の上の端に出す（3 人以上は、縁の色だけでは誰のせりふか分からない） */
      var nm3 = sp.name || cur.who, no3 = { size: 28, weight: 800, font: fam }, nw3 = tw(nm3, no3) + 40, ny3 = y0 - 24;
      rr(CXc - nw3 / 2, ny3, nw3, 44, 22); ctx.fillStyle = col; ctx.fill(); ctx.lineWidth = 3; ctx.strokeStyle = "#ffffff"; ctx.stroke();
      txt(nm3, CXc, ny3 + 32, { size: 28, weight: 800, align: "center", color: "#ffffff", font: fam }); }
    ctx.restore();
  }
  function drawCast(tt) {
    var k = sceneAt(tt), S = SCENES[k].s, show = isTalk(S) || S.variant === "credits" || (SPEC.castAlways && S.type !== "end" && FIRST_TALK >= 0 && tt >= FIRST_TALK); if (!show || !CASTIDS.length) return;
    var cur = cueAt(tt), onIds = S.cast || CASTIDS, lt0 = FIRST_TALK >= 0 ? tt - FIRST_TALK : 0, sideN = { left: 0, right: 0 }, capOn = recording ? !recording.clean : captions;
    if (CAPBAR[TALK.caption] && capOn && !vertOn() && S.type !== "end") capBack();
    CPOS = {};
    /* 立つ位置は台本の順で決め、描くのは話している人を最後に（同じ側に 2 人立つとき、話し手が手前の人に隠れない） */
    var NTH = {}, spkId = cur && cur.who && speaking !== undefined ? cur.who : null;
    onIds.forEach(function (id, i) { var c0 = CAST[id]; if (!c0 || c0.hidden) return; NTH[id] = sideN[(c0.side || (i % 2 ? "right" : "left")) === "right" ? "right" : "left"]++; });
    onIds.map(function (id, i) { return [id, i]; }).sort(function (a, b) { return (a[0] === spkId) - (b[0] === spkId) || a[1] - b[1]; }).forEach(function (pr) {
      var id = pr[0], i = pr[1];
      var ch = CAST[id]; if (!ch || ch.hidden) return;   /* hidden: 声だけの語り手（立ち絵を出さない） */
      var side = ch.side || (i % 2 ? "right" : "left"), h = ch.height || 520, img0 = pickImg(ch, "normal", 0, false), w = ch.sprite ? h * ch.sprite.w / ch.sprite.h : img0 && img0.naturalWidth ? h * img0.naturalWidth / img0.naturalHeight : h * .62;
      var nth = NTH[id], x = (side === "right" ? 1920 - 40 - w / 2 - nth * w * .75 : 40 + w / 2 + nth * w * .75) + (ch.offsetX || 0), by = (ch.baseY || 1080) + (ch.offsetY || 0) - nth * 30, speakingNow = cur && cur.who === id;
      CPOS[id] = { x: x, by: Math.min(by, 1080), w: w, h: Math.min(h, by), side: side === "right" ? "right" : "left" };
      var st = stateOf(id, tt), face = st.face, pose = st.pose, slt = st.t0 === undefined ? 1e9 : tt - st.t0, fbase = String(face).split("#")[0].split("@")[0];
      var ent = ch.cameo ? P(tt - SCENES[k].t0, 150, 750, back) : P(lt0, i * 200, i * 200 + 700, back), dx = (1 - Math.min(1, ent)) * (side === "right" ? 1 : -1) * (w + 80);
      var bob = speakingNow ? -10 * voiceLevel(cur, tt) : 0, shake = speakingNow && cur.line && cur.line.shake ? Math.sin((tt - cur.a) / 25) * 10 * clamp(1 - (tt - cur.a) / 500) : 0;
      /* 口: 話している間は声に合わせる。反応した瞬間は、声を出さずに口だけ開く（あっ・ふふ） */
      var open = speakingNow ? mouthOf(cur, tt) : !st.own && !st.idle && slt < 320 && /^(surprised|smile|troubled|angry)$/.test(fbase) ? (slt < 200 ? 1 : .5) : 0;
      /* まばたき: いつもの周期に、表情が変わった瞬間の 1 回を足す。驚いた直後は目を見開いたまま */
      var blink = fbase === "surprised" && slt < 900 ? false : blinkOf(id, tt) || (st.changed && slt > 30 && slt < 130);
      var mo = castMotion(id, i, ch, tt, st, speakingNow, side);
      if (ch.motion === "yukkuri") bob = 0;
      var spk = speakingNow ? 1 + .025 * clamp((tt - cur.a) / 180) : 1;   /* 話している人を、足元を軸に少し大きく */
      ctx.save(); ctx.translate(dx + shake + mo.x, bob + mo.y); if (TALK.dim && !speakingNow && cur && cur.who) ctx.globalAlpha *= .82;
      var frame = function (f, p2, op, bl) { return ch.sprite ? spriteFrame(id, ch, p2, f, op, bl) : pickImg(ch, f, op, bl); };
      var put = function (im, al) { if (!(im && (im.getContext || (im.complete && im.naturalWidth)))) return false;
        ctx.save(); ctx.globalAlpha *= al; ctx.translate(x, by); ctx.rotate(mo.rot); ctx.scale(mo.sx * spk * mo.flip * (ch.flip ? -1 : 1), mo.sy * spk); ctx.drawImage(im, -w / 2, -h, w, h); ctx.restore(); return true; };
      if (!put(frame(face, pose, open, blink), 1)) drawDummy(ch, x, by, h, open, blink, fbase);
      else if (st.changed && slt < 110 && st.pface !== undefined) put(frame(st.pface, st.ppose, 0, false), 1 - slt / 110);   /* 前の絵を重ねて消していく（切り替わりをなめらかに） */
      /* 気持ちの印: 話し手のせりふの印と、聞き手の反応の印（1.4 秒） */
      var em = speakingNow && cur.line && cur.line.emote, elt = em ? tt - cur.a : 0;
      if (!em && st.emote && !st.own && slt < 1400) { em = st.emote; elt = slt; }
      if (em) drawEmote(em, clamp(x + (side === "right" ? w * .22 : -w * .22), 70, 1850), Math.max(96, by - h - 10), elt, ch.color || C.accent, side === "right" ? 1 : -1);   /* 印は頭の外側に（中央の絵と字に重ねない） */
      if (TALK.nameTag && ent >= 1) { var nt = ch.name || id, no = capFont(30), nw2 = tw(nt, no) + 32, ny2 = Math.max(70, by - h - 14);   /* 頭の上の名札（寸劇の型） */
        rr(x - nw2 / 2, ny2 - 44, nw2, 44, 8); ctx.fillStyle = TALK.nameTag === true ? "#f08a24" : TALK.nameTag; ctx.fill(); txt(nt, x, ny2 - 12, { size: 30, weight: 800, align: "center", color: "#ffffff", font: no.font }); }
      ctx.restore();
    });
    if (cur && cur.who && capOn && VPASS !== "cast") drawCaption(cur, tt);
  }
  /* 掛け合いの場面: 背景（bg）と中央の黒板（board: 部品の台本・画像・文字列） */
  /* ---- 絵で見せる場面（board: {type: "stage", shots: [{line, items, title, note, credit}]}）----
     白い黒板を置かず、背景の上に絵・写真・矢印・短い言葉を並べる。shots は「何番目のせりふから出すか（line）」で切り替わり、せりふごとに絵を替えられる。
     items: {img: 絵の名前（SPEC.images）, label: 名札, say: 吹き出し, frame: 白い縁（写真）} ／ {text: "1 行目/2 行目", color} ／ {op: "→"・"←"・"＋"・"×"・"＝"・"vs" など}
     絵は順にぽんと現れ、ゆっくり浮く。写真は少しずつ寄る。前の絵は消えていく */
  var STAGE_COL = ["#f08a24", "#e5484d", "#3b82f6", "#2f9e62", "#8b5cf6"];
  function capFont(size, weight) { return { size: size, weight: weight || 800, font: TALK.font ? '"' + TALK.font + '",' + F.sans : F.sans }; }
  function stageArrow(x0, x1, y, k, rev) {
    var a = rev ? x1 : x0, b = rev ? x0 : x1, e = a + (b - a) * clamp(k), dir = b > a ? 1 : -1; if (k <= 0) return;
    var path = function () { ctx.beginPath(); ctx.moveTo(a, y); ctx.lineTo(e - dir * 20, y); ctx.moveTo(e - dir * 34, y - 26); ctx.lineTo(e, y); ctx.lineTo(e - dir * 34, y + 26); };
    ctx.save(); ctx.lineCap = "round"; ctx.lineJoin = "round"; path(); ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 26; ctx.stroke(); path(); ctx.strokeStyle = "#20242c"; ctx.lineWidth = 14; ctx.stroke(); ctx.restore();
  }
  function stageBubble(text, cx, y, maxW, k, tailX) {   /* 吹き出し（白い箱・濃い縁・下向きのしっぽ）。y は箱の下端 */
    var o = capFont(34), lines = wrap(text, maxW - 48, o).slice(0, 3), w = Math.max.apply(null, lines.map(function (l) { return tw(l, o); })) + 52, h = lines.length * 46 + 26;
    ctx.save(); ctx.translate(cx, y); ctx.scale(k, k); ctx.translate(-cx, -y);
    rr(cx - w / 2, y - h, w, h, 20); ctx.fillStyle = "#ffffff"; ctx.fill(); ctx.strokeStyle = "#20242c"; ctx.lineWidth = 5; ctx.stroke();
    var tx = clamp(tailX, cx - w / 2 + 30, cx + w / 2 - 30); ctx.beginPath(); ctx.moveTo(tx - 14, y - 3); ctx.lineTo(tx, y + 22); ctx.lineTo(tx + 14, y - 3); ctx.fillStyle = "#ffffff"; ctx.fill();
    ctx.beginPath(); ctx.moveTo(tx - 14, y); ctx.lineTo(tx, y + 22); ctx.lineTo(tx + 14, y); ctx.strokeStyle = "#20242c"; ctx.lineWidth = 5; ctx.lineJoin = "round"; ctx.stroke();
    lines.forEach(function (l, i) { txt(l, cx, y - h + 50 + i * 46, { size: 34, weight: 800, align: "center", color: "#20242c", font: o.font }); });
    ctx.restore();
  }
  /* items にはほかに: {icon: 線で描くアイコンの名前, label, say}（白い丸の上に、線が描かれてから動き続ける）／{part: 部品の台本, label, say}（白い板の上に部品を縮めて置く）／
     {draw: "…JS…"}（描き下ろし。custom と同じ (ctx, lt, d, H, s) の本体。座標は 1920×1080、lt はこの絵が出てからの ms、s.cue(n) は n 個あとのせりふが始まる ms。並びの外に、ほかの絵より先に描く） */
  var STAGE_DRAW = new WeakMap(), CURSHOT = null;
  function stageDraw(it, slt, d, box) {
    var fn = STAGE_DRAW.get(it);
    if (!fn) { try { fn = new Function("ctx", "lt", "d", "H", "s", Array.isArray(it.draw) ? it.draw.join("\n") : it.draw); } catch (e) { fn = function () {}; console.error("stage draw:", e); } STAGE_DRAW.set(it, fn); }
    var cs = CURSHOT; it.cue = function (n) { if (!cs) return 1e9; var c = (cs.s._cues || []).filter(function (c2) { return c2[4] === cs.line + (n || 0); })[0]; return c ? c[0] - cs.t0 : 1e9; };
    it.box = box;   /* 描く範囲（立ち絵と字幕に隠れない所）。plate: "dark"（既定）・"light"・"board"（黒板）・"none" で、その範囲に板を敷く */
    if (it.plate !== "none") { var pk = P(slt, 0, 320); ctx.save(); ctx.globalAlpha *= pk; ctx.translate(0, (1 - pk) * 16); ctx.shadowColor = "rgba(0,0,0,.35)"; ctx.shadowBlur = 26; ctx.shadowOffsetY = 8;
      if (it.plate === "board") {   /* 黒板: 深い緑の板に木の枠と粉受け。暗い板と同じく、明るい色の字と線で描く（図解の手本の作り。Web の画面のような暗い板に見えない） */
        rr(box.x, box.y, box.w, box.h, 8); ctx.fillStyle = "#8a5a33"; ctx.fill(); ctx.shadowColor = "transparent";
        var g0 = ctx.createLinearGradient(0, box.y, 0, box.y + box.h); g0.addColorStop(0, "#2b5445"); g0.addColorStop(1, "#1f4034");
        ctx.fillStyle = g0; ctx.fillRect(box.x + 16, box.y + 16, box.w - 32, box.h - 40);
        ctx.fillStyle = "#a9713f"; ctx.fillRect(box.x + 8, box.y + box.h - 24, box.w - 16, 16); ctx.fillStyle = "#f4f1e6"; ctx.fillRect(box.x + box.w - 150, box.y + box.h - 30, 46, 8); ctx.fillStyle = "#f2c94c"; ctx.fillRect(box.x + box.w - 92, box.y + box.h - 30, 34, 8);   /* 粉受けとチョーク */
        ctx.restore(); }
      else { rr(box.x, box.y, box.w, box.h, 26); ctx.fillStyle = it.plate === "light" ? "rgba(255,255,255,.96)" : "rgba(18,26,40,.93)"; ctx.fill(); ctx.shadowColor = "transparent"; ctx.strokeStyle = it.plate === "light" ? "#20242c" : "#ffffff"; ctx.lineWidth = 5; ctx.stroke(); ctx.restore(); } }
    var txt0 = HELP.txt; if (it.plate === "none") HELP.txt = function (s2, x, y, o) { return txt0(s2, x, y, Object.assign({ stroke: "#16161d" }, o || {})); };
    ctx.save(); EVMUTE++; try { fn(ctx, slt, d, HELP, it); } catch (e) { if (!it._err) { it._err = String(e && e.message || e); console.error("stage draw:", e); } } finally { EVMUTE--; HELP.txt = txt0; } ctx.restore();
    if (it._err) txt("draw のエラー: " + it._err, box.x + 24, box.y + box.h - 20, { size: 26, weight: 700, color: "#ff5a4d" });   /* 描く途中で止まったら、板の下に出す（--shots で気づける） */
  }
  function drawShot(sh, slt, idx0, d) {
    /* TALK.stage: {plate: "white"（中央の白い板）・"paper"（紙の色の全面）・"dark", photo: "full"（写真 1 枚だけの並びは画面いっぱいに）, align: "ground"（絵を地面に立たせる）} */
    var ST = TALK.stage || {}, capY = CAPBAR[TALK.caption] && !vertOn() ? capTop() : 1080;
    var solo = (sh.items || []).filter(function (it) { return !it.op && !it.draw; });
    if (ST.photo === "full" && solo.length === 1 && solo[0].img && solo[0].frame && (sh.items || []).length === 1) {
      var fim = IMGS["@" + solo[0].img];
      if (fim && fim.complete && fim.naturalWidth) { var fk = P(slt, 0, 260), fs = Math.max(1920 / fim.naturalWidth, 1080 / fim.naturalHeight) * (1 + .04 * clamp(slt / 8000)), fw = fim.naturalWidth * fs, fh = fim.naturalHeight * fs;
        /* 写真は画面の下まで敷く（字幕の箱の上で切らない。箱は、後ろをぼかして透かす）。主題が箱に隠れないよう、箱より上のまん中に寄せる */
        var fy = clamp(capY / 2 - fh / 2, 1080 - fh, 0);
        ctx.save(); ctx.globalAlpha *= fk; ctx.fillStyle = "#000000"; ctx.fillRect(0, 0, 1920, 1080);
        /* 縦長の写真は、画面いっぱいに広げると主題が切れる。ぼかして暗くした同じ写真を敷き、その上に全体が入る大きさで置く（白い縁つき） */
        var sideX = 0;   /* 縦長のとき: 写真の左右の空きの中央までの距離（名札は左、吹き出しは右に置いて、写真に重ねない） */
        if (fim.naturalHeight / fim.naturalWidth > capY / 1920 * 1.45) {
          ctx.save(); ctx.filter = "blur(26px) brightness(.5)"; ctx.drawImage(fim, 960 - fw / 2, 540 - fh / 2, fw, fh); ctx.restore();
          var ch2 = capY - 70, cw2 = fim.naturalWidth * ch2 / fim.naturalHeight, cz = 1 + .03 * clamp(slt / 8000);
          ctx.save(); ctx.translate(960, capY / 2); ctx.scale(cz, cz); ctx.shadowColor = "rgba(0,0,0,.5)"; ctx.shadowBlur = 30; ctx.fillStyle = "#ffffff"; ctx.fillRect(-cw2 / 2 - 8, -ch2 / 2 - 8, cw2 + 16, ch2 + 16);
          ctx.shadowColor = "transparent"; ctx.drawImage(fim, -cw2 / 2, -ch2 / 2, cw2, ch2); ctx.restore();
          sideX = cw2 / 2 + (960 - cw2 / 2) / 2;
        } else ctx.drawImage(fim, 960 - fw / 2, fy, fw, fh);
        if (solo[0].say) {   /* 絵の吹き出し（全画面でも出す）: 上の中央に白い箱 */
          var so = capFont(40, 800), sw = tw(solo[0].say, so) + 56, sk = P(slt, 300, 620, back); var half = sideX ? 2 * (sideX - 480) : 0;
          ctx.save(); ctx.translate(sideX ? 960 + half - sw / 2 + 60 : 960, sideX ? 150 : 96); ctx.scale(sk, sk);
          rr(-sw / 2, -40, sw, 76, 24); ctx.fillStyle = "#ffffff"; ctx.fill(); ctx.lineWidth = 5; ctx.strokeStyle = "#20242c"; ctx.stroke();
          var tx0 = sideX ? -sw / 2 + 40 : 0; ctx.beginPath(); ctx.moveTo(tx0 - 16, 34); ctx.lineTo(tx0 - (sideX ? 26 : 0), 66); ctx.lineTo(tx0 + 16, 34); ctx.closePath(); ctx.fillStyle = "#ffffff"; ctx.fill();
          txt(solo[0].say, 0, 14, { size: 40, weight: 800, align: "center", color: "#20242c", font: so.font }); ctx.restore(); }
        if (solo[0].label && solo[0].big) {   /* 題のように大きく出す名札（動画の題の画面など）。暗い帯の上に、白い太い字 */
          var bo = capFont(132, 900), bl = capWrap(solo[0].label, 1500, bo).slice(0, 2), by0 = Math.min(capY, 1080) * .5 - (bl.length - 1) * 82, bk = P(slt, 120, 520, back);
          ctx.save(); ctx.globalAlpha *= clamp(bk); ctx.fillStyle = "rgba(0,0,0,.42)"; ctx.fillRect(0, by0 - 150, 1920, 210 + (bl.length - 1) * 164);
          bl.forEach(function (l2, i) { capLine(l2, 960, by0 + i * 164, bo, [[34, "#16161d"]], "#ffffff", "#ffe45c"); }); ctx.restore(); }
        else if (solo[0].label) { var fo = capFont(34), flw = tw("【" + solo[0].label + "】", fo) + 28; var fly = vertOn() ? 826 : capY < 1080 ? capY - 76 : 150, flx = sideX ? Math.max(flw / 2 + 20, 960 - sideX) : 960; ctx.fillStyle = "rgba(0,0,0,.72)"; ctx.fillRect(flx - flw / 2, fly, flw, 50); txt("【" + solo[0].label + "】", flx, fly + 36, { size: 34, weight: 800, align: "center", color: "#ffffff", font: fo.font }); }
        if (solo[0].credit) { ctx.font = font(capFont(20, 700)); ctx.textAlign = "right"; ctx.lineJoin = "round"; ctx.lineWidth = 5; ctx.strokeStyle = "rgba(0,0,0,.8)"; ctx.textAlign = "right"; ctx.strokeText(solo[0].credit, vertOn() ? 1484 : 1896, 28); ctx.fillStyle = "#ffffff"; ctx.fillText(solo[0].credit, vertOn() ? 1484 : 1896, 28); }
        ctx.restore();
        if (sh.title) { var ftk = P(slt, 0, 300); ctx.save(); ctx.globalAlpha *= ftk; capLine(sh.title, 960, 130, capFont(62, 900), [[20, "#16161d"]], "#ffffff", "#ffe45c"); ctx.restore(); }
        if (sh.note) { var fnk = P(slt, 400, 750); ctx.save(); ctx.globalAlpha *= fnk; capLine(sh.note, 960, capY - 110, capFont(58, 900), [[19, "#16161d"]], "#ffe45c", "#ffffff"); ctx.restore(); }
        return; } }
    if (ST.plate && (sh.items || []).length) { var pk0 = P(slt, 0, 260); ctx.save(); ctx.globalAlpha *= pk0;
      if (ST.plate === "paper") { }   /* 紙は、場面の背景として R.talk が全面に描く */
      else { ctx.shadowColor = "rgba(0,0,0,.3)"; ctx.shadowBlur = 24; ctx.shadowOffsetY = 8; rr(330, 40, 1260, Math.min(capY, 900) - 70, 10); ctx.fillStyle = ST.plate === "dark" ? "rgba(18,26,40,.93)" : "#ffffff"; ctx.fill(); ctx.shadowColor = "transparent"; ctx.strokeStyle = ST.plate === "dark" ? "#ffffff" : "#20242c"; ctx.lineWidth = 5; ctx.stroke(); }
      ctx.restore(); }
    var top0 = 64 + (sh.title ? 96 : 0), AH0 = 770 - (sh.title ? 96 : 0) - (sh.note ? 92 : 0);
    (sh.items || []).forEach(function (it) { if (it.draw) stageDraw(it, slt, d, vertOn() ? { x: 960 - 500, y: top0, w: 1000, h: AH0 } : { x: 360, y: top0, w: 1200, h: AH0 }); });   /* 縦の画面は、まん中の 1080 だけが映る */
    var items = (sh.items || []).filter(function (it) { return !it.draw; }), cells = items.filter(function (it) { return !it.op; }), nOp = items.length - cells.length;
    var top = 64 + (sh.title ? 96 : 0), AH = 770 - (sh.title ? 96 : 0) - (sh.note ? 92 : 0), CX = 960, gap = 34, opW = 120, AW = TALK.stageWidth || (CASTIDS.length ? 1240 : 1400);   /* 立ち絵があるときは、絵が立ち絵の頭にかからない幅に */
    if (ST.plate === "white" || ST.plate === "dark") { AW = 1160; top += sh.title ? 10 : 36; AH -= sh.title ? 30 : 56; }
    var CY = top + AH / 2;
    var cw = Math.min(cells.length === 1 ? 1120 : cells.length === 2 ? 600 : 460, (AW - nOp * opW - (items.length - 1) * gap) / Math.max(1, cells.length));
    /* 部品（グラフ・図）は字が小さくなるので、ほかの絵より広く取る */
    var nP = cells.filter(function (it) { return it.part; }).length, avail = AW - nOp * opW - (items.length - 1) * gap, pwid = cw;
    if (nP) { var nO = cells.length - nP; pwid = nO ? Math.min(960, (avail - nO * 380) / nP) : Math.min(1240, avail / nP); cw = nO ? Math.min(460, (avail - nP * pwid) / nO) : cw; }
    var total = (cells.length - nP) * cw + nP * pwid + nOp * opW + (items.length - 1) * gap, x = CX - total / 2, sin = Math.sin, ci = 0;
    var anyLabel = items.some(function (it) { return it.label; }), anySay = items.some(function (it) { return it.say; });
    if (sh.title && ST.plate === "white") { var tkw = P(slt, 0, 300); ctx.save(); ctx.globalAlpha *= tkw; txt(sh.title, 366, 112, { size: 50, weight: 900, color: "#d9343f", font: capFont(50).font }); ctx.restore(); }   /* 白い板では、見出しを板の左上に赤い字で */
    else if (sh.title) { var tk = P(slt, 0, 300); ctx.save(); ctx.globalAlpha *= tk; capLine(sh.title, CX, top - 30 - (1 - tk) * 14, capFont(62, 900), [[20, "#16161d"]], "#ffffff", "#ffe45c"); ctx.restore(); }
    items.forEach(function (it, i) {
      var dl = 80 + i * 130, k = P(slt, dl, dl + 340, back), al = clamp((slt - dl) / 160), w = it.op ? opW : it.part ? pwid : cw, cx = x + w / 2; x += w + gap;
      if (al <= 0) return;
      ctx.save(); ctx.globalAlpha *= al;
      if (it.op) { var op = it.op;
        if (op === "→" || op === "->" || op === "⇒") stageArrow(cx - opW / 2 + 6, cx + opW / 2 - 6, CY, clamp((slt - dl) / 300), false);
        else if (op === "←" || op === "<-") stageArrow(cx - opW / 2 + 6, cx + opW / 2 - 6, CY, clamp((slt - dl) / 300), true);
        else { ctx.translate(cx, CY + 34); ctx.scale(k, k); capLine(op, 0, 0, capFont(op.length > 1 ? 72 : 104, 900), [[22, "#ffffff"]], "#20242c", "#20242c"); }
        ctx.restore(); return; }
      var col = it.color || (TALK.nameTag ? (TALK.nameTag === true ? "#f08a24" : TALK.nameTag) : STAGE_COL[(ci + (idx0 || 0)) % STAGE_COL.length]); ci++;
      if (it.text !== undefined) {   /* 短い言葉: / で改行。1 つだけなら大きく */
        var ls = String(it.text).split("/"), longest = Math.max.apply(null, ls.map(function (l) { return l.replace(/\*\*/g, "").trim().length; }));
        var sz = Math.max(40, Math.min(it.size || (cells.length === 1 ? 136 : 84), cw / Math.max(2, longest) * .98, AH / (ls.length * 1.4))), y0 = CY - (ls.length - 1) * sz * .65 + sz * .36;
        ls.forEach(function (l, j) { var lk = P(slt, dl + j * 150, dl + j * 150 + 300, back); ctx.save(); ctx.globalAlpha *= clamp((slt - dl - j * 150) / 160);
          ctx.translate(cx, y0 + j * sz * 1.3); ctx.scale(lk, lk); capLine(l.trim(), 0, 0, capFont(sz, 900), [[sz * .3, "#16161d"]], j ? "#ffffff" : (it.color || "#ffffff"), "#ffe45c"); ctx.restore(); });
        ctx.restore(); return; }
      /* 絵: 上から 吹き出し・名札・絵。名札と吹き出しは絵のすぐ上に置く（下は立ち絵と字幕に隠れるため） */
      var im = IMGS["@" + it.img], offTop = (anySay ? 92 : 0) + (anyLabel ? 70 : 0), hBox = AH - offTop, yTop = top + offTop, iy = yTop + hBox / 2, edge = null;
      if (it.icon) {   /* 線で描くアイコン: 白い丸の上に、線が描かれてから動き続ける */
        var ir = Math.min(cw, hBox) * .4, ifl = 6 * sin(slt / 900 + i * 1.7);
        ctx.save(); ctx.translate(cx, iy + ifl); ctx.scale(k, k);
        ctx.shadowColor = "rgba(0,0,0,.28)"; ctx.shadowBlur = 18; ctx.shadowOffsetY = 8; ctx.beginPath(); ctx.arc(0, 0, ir, 0, Math.PI * 2); ctx.fillStyle = "#ffffff"; ctx.fill(); ctx.shadowColor = "transparent";
        ctx.lineWidth = Math.max(6, ir * .06); ctx.strokeStyle = col; ctx.stroke();
        drawIcon(it.icon, 0, 0, ir * 1.25, { color: it.color || "#20242c", k: clamp((slt - dl - 120) / 800), lt: slt, width: 2 });
        ctx.restore(); edge = iy - ir;
      } else if (it.part) {   /* 部品（グラフ・図）: 16:9 の白い板の上に縮めて置く */
        var pw = Math.min(pwid, hBox * 16 / 9), ph = pw * 9 / 16;
        ctx.save(); ctx.translate(cx, iy); ctx.scale(k, k); ctx.translate(-pw / 2, -ph / 2);
        ctx.shadowColor = "rgba(0,0,0,.3)"; ctx.shadowBlur = 24; ctx.shadowOffsetY = 8; panel(0, 0, pw, ph, { r: 20, fill: C.panel, stroke: col, lw: 6 }); ctx.shadowColor = "transparent";
        rr(0, 0, pw, ph, 20); ctx.clip(); sub(it.part.type || "statement", it.part, slt - dl - 200, d, { scale: pw / 1920 });
        ctx.restore(); edge = iy - ph / 2 - 6;
      } else if (im && im.complete && im.naturalWidth) {
        var sc = Math.min(cw / im.naturalWidth, hBox / im.naturalHeight), dw = im.naturalWidth * sc, dh = im.naturalHeight * sc;
        if (ST.align === "ground" && !it.frame) { var gy = Math.min(capY, 1040) - 30; sc = Math.min(cw / im.naturalWidth, Math.min(600, gy - yTop) / im.naturalHeight); dw = im.naturalWidth * sc; dh = im.naturalHeight * sc; iy = gy - dh / 2; }
        var fl = it.frame || ST.align === "ground" ? 0 : 6 * sin(slt / 900 + i * 1.7), zm = it.frame ? 1 + .03 * clamp(slt / 6000) : 1, tilt = it.frame && cells.length > 1 ? (i % 2 ? .02 : -.02) : 0;
        ctx.save(); ctx.translate(cx, iy + fl); ctx.rotate(tilt); ctx.scale(k * zm, k * zm);
        if (it.frame) { ctx.shadowColor = "rgba(0,0,0,.35)"; ctx.shadowBlur = 30; ctx.shadowOffsetY = 10; ctx.fillStyle = "#ffffff"; ctx.fillRect(-dw / 2 - 12, -dh / 2 - 12, dw + 24, dh + 24); ctx.shadowColor = "transparent"; }
        else { ctx.shadowColor = "rgba(0,0,0,.28)"; ctx.shadowBlur = 18; ctx.shadowOffsetY = 8; }
        ctx.drawImage(im, -dw / 2, -dh / 2, dw, dh); ctx.shadowColor = "transparent";
        if (it.credit) { ctx.font = font(capFont(20, 700)); ctx.textAlign = "right"; ctx.lineJoin = "round"; ctx.lineWidth = 5; ctx.strokeStyle = "rgba(0,0,0,.8)"; ctx.strokeText(it.credit, dw / 2 - 10, dh / 2 - 12); ctx.fillStyle = "#ffffff"; ctx.fillText(it.credit, dw / 2 - 10, dh / 2 - 12); }
        ctx.restore();
        edge = iy - dh / 2 * (it.frame ? 1 : .9) - (it.frame ? 12 : 0);
      }
      if (edge !== null) {
        if (it.label) { var ls2 = Math.max(22, Math.min(38, 38 * (cw + 40 - 44) / Math.max(1, tw(it.label, capFont(38))))), lo = capFont(ls2), lw = tw(it.label, lo) + 44, lh2 = ls2 * 1.58; ctx.save(); ctx.translate(cx, edge - 38); ctx.scale(k, k);   /* 長い名札は字を小さく */
          rr(-lw / 2, -lh2 / 2, lw, lh2, 14); ctx.fillStyle = col; ctx.fill(); ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 5; ctx.stroke(); txt(it.label, 0, ls2 * .37, { size: ls2, weight: 800, align: "center", color: "#ffffff", font: lo.font }); ctx.restore(); }
        if (it.say) stageBubble(it.say, cx, edge - (it.label ? 94 : 26), Math.max(cw, 420), P(slt, dl + 380, dl + 700, back), cx);
      }
      ctx.restore();
    });
    if (sh.note) { var nk = P(slt, 300 + items.length * 130, 650 + items.length * 130); ctx.save(); ctx.globalAlpha *= nk; capLine(sh.note, CX, top + AH + 66 + (1 - nk) * 14, capFont(58, 900), [[19, "#16161d"]], "#ffe45c", "#ffffff"); ctx.restore(); }
  }
  function drawStage(s, b, lt, d) {
    var shots = b.shots || []; if (!shots.length) return;
    var starts = shots.map(function (sh, i) { if (!i && !sh.line) return 0; var c = (s._cues || []).filter(function (c2) { return c2[4] === sh.line; })[0]; return c ? Math.max(0, c[0] - 200) : 0; }), n = 0;
    for (var i = 0; i < shots.length; i++) if (lt >= starts[i]) n = i;
    var slt = lt - starts[n];
    if (n > 0 && slt < 200) { CURSHOT = { s: s, t0: starts[n - 1], line: shots[n - 1].line || 0 }; ctx.save(); ctx.globalAlpha *= 1 - slt / 200; ctx.translate(0, -18 * slt / 200); drawShot(shots[n - 1], starts[n] - starts[n - 1] + slt, n - 1, d); ctx.restore(); }
    CURSHOT = { s: s, t0: starts[n], line: shots[n].line || 0 }; drawShot(shots[n], slt, n, d);
    if (EVC && TALK.sfx !== false) shots.forEach(function (sh, j) { sfxEv(starts[j] + 150, (TALK.sfx || {}).show || "pop", { v: .26, pitch: (j % 4) * 2 }); });
  }
  /* 左上の話題の札（tag）と、右上の項目の札（corner） */
  function stageTags(s, lt) {
    var o = capFont(40), TG = TALK.tags || {};   /* tags: {tag: 左上の札の色, corner: 右上の札の色（書くと白い字になる）} */
    if (s.tag) { var k = P(lt, 100, 480), w = tw(s.tag, o) + 56; ctx.save(); ctx.translate(-(1 - k) * (w + 60), 0); rr(34, 30, w, 70, 12); ctx.fillStyle = TG.tag || "#d9343f"; ctx.fill(); ctx.strokeStyle = TG.tagInk || "#ffffff"; ctx.lineWidth = 5; ctx.stroke();
      txt(s.tag, 34 + w / 2, 80, { size: 40, weight: 800, align: "center", color: TG.tagInk || "#ffffff", font: o.font }); ctx.restore(); }
    if (s.corner) { var o2 = capFont(32), k2 = P(lt, 200, 580), w2 = tw(s.corner, o2) + 48; ctx.save(); ctx.translate((1 - k2) * (w2 + 60), 0); rr(1886 - w2, 34, w2, 58, 10); ctx.fillStyle = TG.corner || "rgba(255,255,255,.94)"; ctx.fill(); ctx.strokeStyle = TG.corner ? "#ffffff" : "#20242c"; ctx.lineWidth = 4; ctx.stroke();
      txt(s.corner, 1886 - w2 / 2, 75, { size: 32, weight: 800, align: "center", color: TG.corner ? "#ffffff" : "#20242c", font: o2.font }); ctx.restore(); }
  }
  var TALK_SFX = { "!": "pop", "?": "question", "!?": "stab", "♪": "bling", "💦": "slip", "💢": "woodblock", "…": "downer", "💡": "correct", "✨": "sparkle", "♥": "heart-pop", gloom: "downer", shock: "stab", big: "hyoshigi", shake: "impact" };
  R.talk = function (s, lt, d) {
    /* 効果音のきっかけ: せりふの印・大きい字幕・揺れ・聞き手の反応の印。続けて鳴らしすぎない（2.4 秒あける。se で名指しした音は必ず鳴らす） */
    if (EVC && TALK.sfx !== false) { var smap = Object.assign({}, TALK_SFX, TALK.sfx || {}), lastT = -9999;
      (s._cues || []).forEach(function (c) { var ln = s.lines[c[4]]; if (!ln || !ln.who) return;
        var name = ln.se || (ln.big ? smap.big : null) || (ln.shake ? smap.shake : null) || smap[EMO_ALIAS[ln.emote] || ln.emote];
        if (name && name !== "none" && (ln.se || c[0] - lastT > 2400)) { sfxEv(c[0] + 60, name, { v: ln.se ? .6 : .42 }); lastT = c[0]; }
        (ln.react || []).forEach(function (r) { var rt = c[0] + (c[1] - c[0]) * (r.at === undefined ? .5 : r.at), rn = r.se || smap[EMO_ALIAS[r.emote] || r.emote];
          if (rn && rn !== "none" && (r.se || rt - lastT > 2400)) { sfxEv(rt + 40, rn, { v: .36 }); lastT = rt; } }); });
      if (s.board && (typeof s.board === "string" || s.board.type === "image")) sfxEv(140, "appear"); }
    var bgi = IMGS[s.bg];
    if (bgi && bgi.complete && bgi.naturalWidth) { var sc = Math.max(W / bgi.naturalWidth, H / bgi.naturalHeight); ctx.drawImage(bgi, 960 - bgi.naturalWidth * sc / 2, 540 - bgi.naturalHeight * sc / 2, bgi.naturalWidth * sc, bgi.naturalHeight * sc); }
    if ((TALK.stage || {}).plate === "paper") { var pg = ctx.createRadialGradient(960, 440, 200, 960, 440, 1300); pg.addColorStop(0, "#d8cba6"); pg.addColorStop(1, "#9c8f6c"); ctx.fillStyle = pg; ctx.fillRect(0, 0, 1920, 1080); }
    var b = s.board; if (!b) { stageTags(s, lt); return; }
    if (b.type === "stage") { drawStage(s, b, lt, d); stageTags(s, lt); return; }
    var bx = 330, byy = 70, bw = 1260, bh = bw * 9 / 16 * .92, k = P(lt, 0, 500);
    ctx.save(); ctx.globalAlpha *= k; ctx.translate(0, (1 - k) * 20);
    panel(bx - 16, byy - 16, bw + 32, bh + 32, { r: 24, fill: s.boardColor || C.panel, stroke: C.accent, lw: 6 });
    ctx.save(); rr(bx, byy, bw, bh, 14); ctx.clip();
    if (typeof b === "string") { var ls = wrap(b, bw - 120, { size: 64, weight: 800, font: F.display }); ls.forEach(function (ln, i) { rich(ln, bx + bw / 2, byy + bh / 2 - (ls.length - 1) * 42 + i * 84 + 22, { size: 64, weight: 800, font: F.display, align: "center" }); }); }
    else if (b.type === "image") { var im = IMGS[b.src]; if (im && im.complete && im.naturalWidth) { var s2 = Math.min(bw / im.naturalWidth, bh / im.naturalHeight); ctx.drawImage(im, bx + (bw - im.naturalWidth * s2) / 2, byy + (bh - im.naturalHeight * s2) / 2, im.naturalWidth * s2, im.naturalHeight * s2); } }
    else sub(b.type || "statement", b, lt, d, { x: bx, y: byy - bh * .02, scale: bw / 1920 });
    ctx.restore(); ctx.restore(); stageTags(s, lt);
  };

  /* ================= HTML・SVG で描く場面（dom） ================= */
  var domLayer = $("mv-dom"), domEls = {}, domScale = 1;
  R.dom = function (s, lt) { heading(s, lt); };
  function syncDom(t) {
    if (!domLayer) return;
    var k = sceneAt(t);
    SCENES.forEach(function (sc, i) {
      if (sc.s.type !== "dom") return;
      var el = domEls[i], lt = t - sc.t0, active = i === k || (i === k - 1 && t - SCENES[k].t0 < FADE);
      if (!active) { if (el) el.style.display = "none"; return; }
      if (!el) {
        el = document.createElement("div"); el.className = "mv-domscene";
        el.innerHTML = (sc.s.css ? "<style>" + sc.s.css + "</style>" : "") + (sc.s.html || "");
        domLayer.appendChild(el); domEls[i] = el;
        try { el.__up = sc.s.update ? new Function("el", "lt", "d", "H", "s", sc.s.update) : null; } catch (e) { console.error("dom scene:", e); }
      }
      var d = sc.d, inK = i === 0 ? 1 : P(lt, 0, FADE), outK = i === SCENES.length - 1 ? 1 : 1 - P(lt, d - FADE, d, eio);
      el.style.display = "block"; el.style.transform = "scale(" + domScale + ")"; el.style.opacity = String(Math.min(inK, outK));
      var cl = Math.max(0, Math.min(lt, d));
      el.style.setProperty("--lt", String(cl)); el.style.setProperty("--p", String(clamp(cl / d)));
      if (el.__up) { try { el.__up(el, cl, d, HELP, sc.s); } catch (e) { if (!sc.s._err) { sc.s._err = 1; console.error("dom scene:", e); } } }
    });
  }


  /* ================= 音声（読み上げ・音楽・効果音） ================= */
  var AUD = SPEC.audio || {}, MA = window.MotionAudio;
  var ac = null, master = null, recording = null, duckG = null, sfxBus = null, VOL = 1;
  var MUS = AUD._music || {}, SFXD = AUD._sfx || {}, SFXCFG = AUD._sfxcfg || null, INSTX = Object.assign({}, (MA && MA.INST) || {}, AUD.instruments || {});
  var SFXBUF = {}, SFXFN = {};
  function ensureAudio() {
    if (ac || !MA) return;
    try { ac = new (window.AudioContext || window.webkitAudioContext)(); master = ac.createGain(); master.gain.value = audioOn ? VOL : 0;
      /* 出口に抑え（音楽・効果音が重なっても割れない） */
      var lim = ac.createDynamicsCompressor(); lim.threshold.value = -6; lim.knee.value = 6; lim.ratio.value = 12; lim.attack.value = .003; lim.release.value = .2;
      master.connect(lim); lim.connect(ac.destination);
      duckG = ac.createGain(); duckG.gain.value = 1; duckG.connect(master);
      sfxBus = ac.createGain(); sfxBus.gain.value = SFXCFG ? (SFXCFG.volume === undefined ? 1 : SFXCFG.volume) : 1; sfxBus.connect(master);
      /* 楽器の録音の音（sound.py の samples）を復号しておく。復号が済むまでの音は合成の音で鳴る */
      if (AUD._samples && MA.loadSamples) MA.loadSamples(ac, AUD._samples);
      /* せりふの音声ファイル（WAV）を復号しておく */
      CUES.forEach(function (c) { if (c.par || !c.line || !c.line.voice || VBUF[c.key]) return; var key = c.key; VBUF[key] = null;
        audioBytes(c.line.voice).then(function (buf) { return ac.decodeAudioData(buf); }).then(function (b) { VBUF[key] = b; }).catch(function (e) { console.warn("voice:", e); }); });
      /* ファイルの効果音は先に復号しておく */
      Object.keys(SFXD).forEach(function (k) { var r = SFXD[k]; if (!r.file) return;
        audioBytes(r.file).then(function (buf) { return ac.decodeAudioData(buf); }).then(function (b) { SFXBUF[k] = b; }).catch(function (e) { console.warn("sfx file:", k, e); }); });
    } catch (e) { ac = null; } }

  /* ---- 音楽: 章ごとに曲の頭から。音符は「章の中の時刻」だけで決まる（MotionAudio.notes）。
   * 音楽の時計 mt は、読み上げを待って映像が止まっている間も進む（音が途切れない）。シーク・再生・速度の変更で映像の時刻に合わせ直す */
  var mclock = { mt: 0, upTo: 0, sec: -1, secStart: 0, bus: null, files: {}, fresh: false };
  var MUSVOL = AUD.musicVolume === undefined ? 1 : AUD.musicVolume;
  var musicOn = true, sfxOn = true;   /* 見る人の設定（設定の「音楽」「効果音」）。起動時に読み込む */
  function musicKeyOf(ci) { var ch = SPEC.chapters[ci]; return ch && ch._music !== undefined ? ch._music : AUD._musicKey; }
  /* 曲の区切り: 章の頭（章の曲か全体の曲）と、曲を書いた場面の頭（その章の終わりまで）。同じ曲が続くなら区切らない（途切れずに流れる）。
     cont: 全体の曲のまま → 映像の先頭からの位置で鳴らす。そのほかは区切りの頭から */
  var MSEG = null;
  function msegs() {
    if (MSEG) return MSEG; MSEG = [];
    SCENES.forEach(function (sc) {
      var ch = SPEC.chapters[sc.ci], first = !MSEG.length || MSEG[MSEG.length - 1].ci !== sc.ci, key, cont;
      if (sc.s._music !== undefined) { key = sc.s._music; cont = false; }
      else if (first) { key = musicKeyOf(sc.ci); cont = ch._music === undefined; }
      else return;
      var last = MSEG[MSEG.length - 1];
      if (last && last.key === key && last.cont === cont) return;   /* 同じ曲が続く: 区切らず、そのまま流す */
      MSEG.push({ t: sc.t0, key: key, cont: cont, ci: sc.ci });
    });
    MSEG.forEach(function (m, i) { m.end = i < MSEG.length - 1 ? MSEG[i + 1].t : DUR; });
    return MSEG;
  }
  function msegAt(tt) { var L = msegs(), i = 0; for (var k = 0; k < L.length; k++) if (tt >= L[k].t) i = k; return i; }
  var XFADE = AUD.musicFade === undefined ? 900 : AUD.musicFade;   /* 曲が替わるときの重ね（ms） */
  function energyOf(ci) {
    var ch = SPEC.chapters[ci], n = CHAPTERS.length;
    if (ch && ch.energy) return ch.energy;
    if (Array.isArray(AUD.energy) && AUD.energy[ci]) return AUD.energy[ci];
    if (ci === 0 || (ci === n - 1 && n > 2)) return 1;
    return ci === n - 2 && n >= 4 ? 3 : 2;
  }
  function musicStop() {
    if (!ac) return;
    if (mclock.bus) { var old = mclock.bus; old.gain.cancelScheduledValues(ac.currentTime); old.gain.setTargetAtTime(0, ac.currentTime, .06);
      setTimeout(function () { try { old.disconnect(); } catch (e) {} }, 600); }
    mclock.bus = null; mclock.sec = -1;
    Object.keys(mclock.files).forEach(function (k) { var f = mclock.files[k]; f.on = false; f.out.gain.cancelScheduledValues(ac.currentTime); f.out.gain.value = 0;
      [f.a, f.b].forEach(function (p) { if (p) try { p.el.pause(); } catch (e) {} }); });
  }
  function musicReset() { musicStop(); mclock.mt = t; }
  /* 曲のファイル: 曲ごとに音量のつまみ（out）を持ち、替わるときは out を XFADE かけて上げ下げする（前の曲が消えていく間に次の曲が入る）。
     ループ用でない曲（loop: false）は、同じ曲を 2 つ持ち、終わりの数秒を次の頭に重ねてつなぐ */
  /* 曲の「音楽としての終わり」: 最後のフェードアウトと無音を除いた所（0.1 秒ごとの音量が、曲の中ほどの音量の 3 割を最後に超えた所）。くり返すときは、ここで次の頭に重ねる */
  var MTRIM = {};
  function musicEnd(buf) {
    var d = buf.getChannelData(0), n = Math.floor(buf.sampleRate / 10), lv = [];
    for (var i = 0; i + n <= d.length; i += n) { var s2 = 0; for (var j = i; j < i + n; j += 16) s2 += d[j] * d[j]; lv.push(Math.sqrt(s2 / (n / 16))); }
    var med = lv.slice().sort(function (a, b) { return a - b; })[Math.floor(lv.length * .5)] || 0, k = lv.length - 1;
    while (k > 0 && lv[k] < med * .3) k--;
    return Math.min(buf.duration, (k + 1) / 10 + .3);
  }
  function trimOf(key, def) {
    if (MTRIM[key] !== undefined || !def.file || def.loop === true) return;
    MTRIM[key] = null;
    try { audioBytes(def.file).then(function (b) { return new OfflineAudioContext(1, 1, 44100).decodeAudioData(b); })
      .then(function (buf) { MTRIM[key] = musicEnd(buf); }).catch(function () {}); } catch (e) {}
  }
  Object.keys(MUS).forEach(function (k) { trimOf(k, MUS[k]); });
  function fileOf(key, def) {
    var f = mclock.files[key]; if (f) return f;
    var mk = function () { var el = new Audio(def.file); el.preservesPitch = true; var g = ac.createGain(); g.gain.value = 0;
      try { ac.createMediaElementSource(el).connect(g); } catch (e) { console.warn("music file:", e); } return { el: el, g: g }; };
    var out = ac.createGain(); out.gain.value = 0; out.connect(duckG);
    var A = mk(), B = def.loop === true ? null : mk(); A.g.connect(out); if (B) B.g.connect(out); else A.el.loop = true;   /* loop: true はループ用に作られた曲（そのまま回す） */
    return (mclock.files[key] = { a: A, b: B, out: out, key: key, vol: (def.volume === undefined ? .35 : def.volume) * MUSVOL, on: false, offAt: 0 });
  }
  function syncEl(p, at, gain) {
    p.el.playbackRate = speed;
    if (p.el.paused) { try { p.el.currentTime = at; } catch (e) {} p.el.play().catch(function () {}); }
    else if (Math.abs(p.el.currentTime - at) > .3) { try { p.el.currentTime = at; } catch (e) {} }
    p.g.gain.setTargetAtTime(gain, ac.currentTime, .04);
  }
  function filePlay(f, pos) {   /* pos: 曲の中の秒 */
    var dur = f.a.el.duration;
    if (!f.b) { if (dur && isFinite(dur)) pos = pos % dur; syncEl(f.a, pos, 1); return; }
    if (MTRIM[f.key]) dur = Math.min(dur || 1e9, MTRIM[f.key]);
    if (!dur || !isFinite(dur)) { syncEl(f.a, pos, 1); return; }
    var X = Math.min(3, dur * .12), L = dur - X, n = Math.floor(pos / L), lp = pos - n * L, cur = n % 2 ? f.b : f.a, prev = n % 2 ? f.a : f.b;
    if (n > 0 && lp < X) { syncEl(cur, lp, lp / X); syncEl(prev, lp + L, 1 - lp / X); }
    else { syncEl(cur, lp, 1); prev.g.gain.setTargetAtTime(0, ac.currentTime, .04); if (!prev.el.paused && lp > X + .5) try { prev.el.pause(); } catch (e) {} }
  }
  function musicTick(dtReal) {
    if (!ac || !audioOn || !playing || !MA || !musicOn) return;
    mclock.mt += dtReal * speed;
    var si = msegAt(t), M = msegs()[si], key = M ? M.key : null, def = key ? MUS[key] : null, off = mclock.mt - t, ci = chapterAt(t);
    if (si !== mclock.sec) {
      mclock.sec = si; mclock.secStart = (M ? M.t : 0) + off; mclock.upTo = mclock.mt; mclock.fresh = true;
      if (!mclock.bus) { mclock.bus = ac.createGain(); mclock.bus.gain.value = MUSVOL * (def && def.g ? def.g : 1); mclock.bus.connect(duckG); }
      else mclock.bus.gain.setTargetAtTime(MUSVOL * (def && def.g ? def.g : 1), ac.currentTime, .3);
      Object.keys(mclock.files).forEach(function (k) { var f = mclock.files[k]; if (k !== key && f.on) { f.on = false; f.offAt = mclock.mt;
        f.out.gain.cancelScheduledValues(ac.currentTime); f.out.gain.setTargetAtTime(0, ac.currentTime, XFADE / 3000); } });
    }
    Object.keys(mclock.files).forEach(function (k) { var f = mclock.files[k];   /* 消え終わった曲を止める */
      if (!f.on && f.offAt && mclock.mt - f.offAt > XFADE * 2) { f.offAt = 0; [f.a, f.b].forEach(function (p) { if (p) try { p.el.pause(); } catch (e) {} }); } });
    if (!def) return;
    if (def.file) {
      var f = fileOf(key, def), pos = (M.cont ? mclock.mt : mclock.mt - mclock.secStart) / 1000;
      if (!f.on) { f.on = true; f.offAt = 0; f.out.gain.cancelScheduledValues(ac.currentTime);
        f.out.gain.setTargetAtTime(f.vol, ac.currentTime, (mclock.fresh && mclock.mt - mclock.secStart < 200 && si > 0 ? XFADE : 120) / 3000); }
      filePlay(f, pos); mclock.fresh = false;
      return;
    }
    var segEnd = (M ? M.end : DUR) + off, to = Math.min(mclock.mt + 300 * speed, segEnd), from = mclock.upTo;
    if (to <= from) return;
    var info = { ci: ci, energy: energyOf(ci), len: segEnd - mclock.secStart }, lf = from - mclock.secStart, t0m = M ? M.t : 0;
    MA.notes(def, info, mclock.fresh ? Math.max(0, lf - 12000) : lf, to - mclock.secStart).forEach(function (n) {
      var st = n.t, en = n.t + (n.d || 0);
      if (st < lf) { if (!mclock.fresh || n.drum || en <= lf + 60 || !MA.isSus(n.inst, INSTX)) return; }   /* 途中から: 伸ばしている音だけ */
      var tv = t0m + st, fade = clamp(tv / 1200 + .15) * clamp((DUR - tv) / 2500);   /* 映像の最初と最後で下げる */
      if (fade <= 0) return;
      var when = ac.currentTime + Math.max(0, mclock.secStart + st - mclock.mt) / speed / 1000;
      MA.note(ac, mclock.bus, n, when, Math.max(.05, (en - Math.max(st, lf)) / speed / 1000), fade, INSTX, st < lf); mclock.count = (mclock.count || 0) + 1;
    });
    mclock.fresh = false; mclock.upTo = to;
  }
  var duckOn = false;
  function syncDuck() { if (!duckG) return; var want = !!speaking && AUD.narration !== false; if (want === duckOn) return; duckOn = want;
    duckG.gain.setTargetAtTime(want ? (AUD.duck === undefined ? .5 : AUD.duck) : 1, ac.currentTime, want ? .08 : .4); }

  /* ---- 効果音: 場面の部品・重ねの層が H.sfx / sfxEv で出来事を知らせる。起動時に場面ごとに一度だけ集めて、時刻の表にする ---- */
  var EVC = null, EVOFF = 0, EVMUTE = 0, SFXQ = [], sfxCount = 0;
  function sfxEv(at, ev, o) { if (EVC && !EVMUTE) EVC.push({ at: at + EVOFF, ev: ev, o: o || {} }); }
  function sfxPlay(name, delay, o, ctx, bus) {
    /* ctx・bus を渡すと、その文脈（書き出しの OfflineAudioContext）に鳴らす（見る人の入り切りは見ない） */
    var A = ctx || ac, B = bus || sfxBus;
    if (!A || (!ctx && (!audioOn || !sfxOn)) || !name) return; var r = SFXD[name]; if (!r) return; sfxCount++;
    o = o || {}; var when = A.currentTime + Math.max(0, delay || 0);
    if (r.lv && r.lv !== 1 && !o.raw) { var LG = A.createGain(); LG.gain.value = r.lv; LG.connect(B); B = LG; }   /* 聞こえる大きさをそろえる倍率（sound.py が sfx_levels.json から書く） */
    if (r.file) { var b = SFXBUF[name]; if (!b) return; var src = A.createBufferSource(), g = A.createGain(); src.buffer = b;
      src.playbackRate.value = Math.pow(2, (o.pitch || 0) / 12); g.gain.value = (o.v === undefined ? 1 : o.v) * (r.v || 1); src.connect(g); g.connect(B); src.start(when); return; }
    if (r.code) { var fn = SFXFN[name]; if (!fn) { try { fn = SFXFN[name] = new Function("ac", "out", "when", "A", "o", r.code); } catch (e) { fn = SFXFN[name] = function () {}; console.error("sfx code:", e); } }
      try { fn(A, B, when, MA, o); } catch (e) { console.error("sfx code:", e); } return; }
    MA.play(A, B, r, when, o);
  }
  /* 場面ごとに最後のコマを小さな Canvas に一度描き、部品が知らせる出来事（効果音のきっかけ・揺れ）を集める */
  function collectEvents(from) {
    var tc = document.createElement("canvas"); tc.width = 8; tc.height = 8;
    var cv0 = cv, ctx0 = ctx; cv = tc; ctx = tc.getContext("2d"); thumbMode = true;
    SCENES.forEach(function (sc, i) {
      if (i < (from || 0)) return;
      EVC = []; EVOFF = 0; EVMUTE = 0;
      try { ctx.setTransform(1, 0, 0, 1, 0, 0); useMotion(sc.s); (R[sc.s.type] || R.statement)(sc.s, Math.max(0, sc.d - 1), sc.d, sc.t0 + sc.d - 1); drawOverlays(sc.s, Math.max(0, sc.d - 1), sc.d); }
      catch (e) { console.warn("event collect:", e); } useMotion({});
      sc.evs = EVC; EVC = null;
      sc.shakes = sc.evs.filter(function (e) { return e.ev === "__shake"; }).map(function (e) { return { at: e.at, amp: e.o.amp, dur: e.o.dur }; })
        .concat((sc.s.shake || []).map(function (s) { return { at: s.ms !== undefined ? s.ms : (s.at || 0) * sc.d, amp: s.amp || 16, dur: s.dur || 450 }; }));
    });
    cv = cv0; ctx = ctx0; thumbMode = false;
  }
  var TR_EV = { iris: "tr.zoom", spin: "tr.zoom", "zoom-through": "tr.zoom", pixel: "tr.wipe", blinds: "tr.wipe", whip: "tr.push", "slide-up": "tr.push",
                "slide-down": "tr.push", squeeze: "tr.push", split: "tr.slide", flash: "tr.cut", glitch: "tr.cut" };
  function buildSfxQueue() {
    SFXQ.length = 0;
    if (!SFXCFG || !MA) return;
    var KIT = SFXCFG.kit || {}, dens = SFXCFG.density || 2, raw = [];
    SCENES.forEach(function (sc, k) {
      var ss = sc.s.sfx, auto = !(ss === false || (ss && !Array.isArray(ss) && ss.auto === false)), smap = ss && !Array.isArray(ss) && ss.map || {};
      var push = function (T, ev, o, name) { raw.push({ T: T, ev: ev, o: o || {}, name: name, map: smap, k: k }); };
      var TRV = SFXCFG.transitionVolume === undefined ? {} : { v: SFXCFG.transitionVolume };   /* 章・場面の切り替えの音だけ、音量を変える（audio.sfx.transitionVolume） */
      if (k > 0 && sc.s.type === "end") {}   /* 締めの画面へは、音を鳴らさずに切り替える */
      else if (k > 0) { if (SCENES[k - 1].ci !== sc.ci) push(sc.t0 + 60, "chapter", TRV); else { var tr = trOf(k), ev = KIT["tr." + tr] || !TR_EV[tr] ? "tr." + tr : TR_EV[tr];
        push(sc.t0 - (tr === "cut" || tr === "flash" || tr === "glitch" ? 0 : 150), ev, TRV); } }
      if (auto) (sc.evs || []).forEach(function (e) { if (e.ev !== "__shake") push(sc.t0 + clamp(e.at, 0, sc.d), e.ev, e.o, SFXD[e.ev] ? e.ev : null); });
      (Array.isArray(ss) ? ss : ss && ss.add || []).forEach(function (a) {
        push(sc.t0 + (a.ms !== undefined ? a.ms : (a.at || 0) * sc.d), a.event, { v: a.v, pitch: a.pitch, force: true }, a.name);
      });
    });
    var last = {};
    raw.forEach(function (r, i) {
      var name = r.name, v = 1, step = 0, lv = 1;
      if (!name) {
        var m = r.map[r.ev] !== undefined ? r.map[r.ev] : KIT[r.ev];
        if (!m) return;
        if (typeof m === "string") m = [m, 1, 0, 1];
        name = m[0]; v = m[1] === undefined ? 1 : m[1]; step = m[2] || 0; lv = m[3] || EVLV[r.ev] || 1;
        if (lv > dens && !r.o.force) return;
      }
      if (!SFXD[name]) return;
      var o = r.o, pitch = (o.pitch || 0) + (o.i !== undefined ? Math.min(12, o.i * step) : 0), q = { T: r.T, name: name, v: v * (o.v === undefined ? 1 : o.v), pitch: pitch, seed: i + 1 };
      if (o.n || o.dur) { var rep = Math.max(1, Math.min(40, o.n || Math.round(o.dur / 70))); q.rep = rep; q.gap = (o.dur || rep * 70) / rep / 1000; }
      if (last[name] !== undefined && Math.abs(last[name] - r.T) < 45) return;   /* 同じ音の重なり（同時に出る項目）は 1 つに */
      last[name] = r.T; SFXQ.push(q);
    });
    SFXQ.sort(function (a, b) { return a.T - b.T; });
  }
  var EVLV = { chapter: 1, hit: 1, click: 1, title: 1, outro: 1, countEnd: 1, message: 1, send: 1, toast: 1, notify: 1, done: 1, blocked: 1, reveal: 1, nav: 1, row: 3, working: 3 };
  function kitPlay(ev, delay) { var m = SFXCFG && SFXCFG.kit[ev]; if (m) sfxPlay(m[0], delay, { v: m[1] }); }
  var synth = "speechSynthesis" in window ? window.speechSynthesis : null, voice = null, LANG = SPEC.lang || "ja";
  function pickVoice() {
    if (!synth) return; var vs = synth.getVoices(), re = new RegExp("^" + LANG, "i");
    voice = vs.filter(function (v) { return re.test(v.lang) && /Kyoko|Nanami|Otoya|Google|Samantha|Aria|Natural/i.test(v.name); })[0] || vs.filter(function (v) { return re.test(v.lang); })[0] || null;
    var note = $("mv-voicenote"); if (note) note.hidden = !(started && audioOn && AUD.narration !== false && vs.length && !voice);
    applyStoredVoiceRate();
  }
  if (synth) { pickVoice(); synth.onvoiceschanged = pickVoice; }
  /* 読み上げ中の字幕。字幕の終わりに来ても読み終わっていなければ、動画をそこで待たせる（audio.wait: false で無効） */
  var speaking = null;
  var VBUF = {}, vsrc = null;
  /* 音声のデータを読む。埋め込み（data: の base64）は fetch を使わずに直す（fetch を止めている場所でも鳴るように） */
  function audioBytes(url) {
    var m = /^data:[^;,]*;base64,/.exec(url || "");
    if (!m) return fetch(url).then(function (x) { return x.arrayBuffer(); });
    return new Promise(function (ok) { var bin = atob(url.slice(m[0].length)), n = bin.length, u = new Uint8Array(n); for (var i = 0; i < n; i++) u[i] = bin.charCodeAt(i); ok(u.buffer); });
  }
  /* 声の速さを変えても、高さは変えない: 波形を短い区間（30ms）に切り、つながりのよい位置を探しながら、間隔を詰めて（広げて）重ね直す（WSOLA）。
     速さごとに 1 度だけ作って覚えておく。r は速さ（2 で倍速）。モノラルにして返す */
  var VSTR = {}, VSTR_SPEED = 0;
  function stretchVoice(key, b, r) {
    if (VSTR_SPEED !== r) { VSTR = {}; VSTR_SPEED = r; }
    if (VSTR[key]) return VSTR[key];
    var sr = b.sampleRate, x = b.getChannelData(0), n = x.length, win = Math.max(64, Math.round(sr * .03) & ~1), hs = win / 2, tol = Math.round(sr * .008), step = sr > 20000 ? 2 : 1;
    var frames = Math.max(1, Math.ceil(n / r / hs)), out = new Float32Array(frames * hs + win), w = new Float32Array(win), i, k, d;
    for (i = 0; i < win; i++) w[i] = .5 - .5 * Math.cos(2 * Math.PI * (i + .5) / win);
    var prev = 0;
    for (k = 0; k < frames; k++) {
      var target = Math.round(k * hs * r), best = 0;
      if (k > 0) {   /* 前の区間の「続き」（prev + hs から）に、いちばん似た位置を target の前後から探す */
        var ref = prev + hs, bestC = -Infinity;
        for (d = -tol; d <= tol; d += step) { var q = target + d; if (q < 0 || q + hs >= n || ref + hs >= n) continue;
          var c = 0; for (i = 0; i < hs; i += step) c += x[q + i] * x[ref + i];
          if (c > bestC) { bestC = c; best = d; } }
      }
      var pos = Math.max(0, Math.min(n - 1, target + best)), o0 = k * hs;
      for (i = 0; i < win && pos + i < n; i++) out[o0 + i] += x[pos + i] * w[i];
      prev = pos;
    }
    var len = Math.max(1, Math.round(n / r)), ob = ac.createBuffer(1, len, sr);
    ob.getChannelData(0).set(out.subarray(0, len));
    return (VSTR[key] = ob);
  }
  function playVoice(cue, off) {
    if (!ac || !audioOn || AUD.narration === false) return false; var b = VBUF[cue.key]; if (!b) return !!(cue.line && cue.line.voice);
    stopVoice(); var s = ac.createBufferSource(), g0 = ac.createGain(), sp = speed || 1, keep = AUD.keepPitch !== false && sp !== 1;
    try { s.buffer = keep ? stretchVoice(cue.key, b, sp) : b; } catch (e) { console.warn("voice stretch:", e); s.buffer = b; keep = false; }
    if (!keep) s.playbackRate.value = sp;   /* audio.keepPitch: false なら、今までどおり速さと一緒に高さも変わる */
    g0.gain.value = cue.line.volume === undefined ? 1 : cue.line.volume;
    s.connect(g0); g0.connect(master); try { s.start(0, Math.max(0, off || 0) / 1000 / (keep ? sp : 1)); } catch (e) { return true; }
    var me = { cue: cue, file: true, started: performance.now(), maxMs: 1e9 }; speaking = me; vsrc = s;
    s.onended = function () { if (speaking === me) speaking = null; if (vsrc === s) vsrc = null; }; return true;
  }
  function stopVoice() { if (vsrc) { try { vsrc.stop(); } catch (e) {} vsrc = null; } }
  function say(text, cue) {
    if (cue && cue.par) return;   /* 前の字幕の声が続いている */
    if (cue && cue.line && cue.line.voice) { playVoice(cue, 0); return; }
    if (!synth || !audioOn || !voice || AUD.narration === false) return;
    try { synth.cancel(); var s = text.replace(/\*\*/g, "");
      /* 長い語から置き換える（「ts5250」より先に「5250」を置き換えない。JS は数字だけのキーを先に並べるため順に頼らない） */
      Object.keys(AUD.pronounce || {}).sort(function (a, b) { return b.length - a.length; }).forEach(function (k) { s = s.split(k).join(AUD.pronounce[k]); });
      /* 日本語と英字・数字の間の空白を詰める（声によっては空白で一呼吸おく。build.py の spoken と同じ） */
      s = s.replace(/[ \u3000]+(?=[^\x00-\x7f])/g, "").replace(/([^\x00-\x7f])[ \u3000]+/g, "$1");
      var u = new SpeechSynthesisUtterance(s), cv0 = cue && cue.who && CAST[cue.who] && CAST[cue.who].voice || {};
      u.voice = voice; u.lang = voice.lang; u.volume = VOL; u.rate = Math.min(2.4, (cv0.rate || AUD.rate || 1.1) * speed); if (cv0.pitch) u.pitch = cv0.pitch;
      var me = { u: u, cue: cue || null, started: performance.now(), maxMs: 4000 + s.length * 420 / u.rate, sp: speed };
      u.onstart = function () { me.t1 = performance.now(); };
      u.onend = u.onerror = function (ev) { if (speaking === me) { speaking = null; root.classList.remove("mv-waiting");
        /* 最後まで話し終えたときだけ（シーク・停止・次の字幕で切られたときは数えない）、実際の長さを 1 倍速に直して学ぶ */
        if (ev && ev.type === "end" && me.t1 && cue && cue.est) learnVoice((performance.now() - me.t1) * me.sp, cue.est); } };
      speaking = me; synth.speak(u); } catch (e) {}
  }
  /* ---- 声の速さに合わせた時間割の直し（ブラウザの読み上げ）----
     build.py は 1 秒 6.2 字の見積もりで場面の長さを決める。実際の声（OS・ブラウザで違う）が遅い・速いと、
     表示の時間と実際の再生がずれる。話し終えた字幕から「実際 ÷ 見積もり」を測り、まだ来ていない場面の長さと
     字幕の時刻を build.py の plan と同じ割り付けで直す。比はこのブラウザに声ごとに覚え、次は最初から使う（audio.adapt: false で無効） */
  var VK = 1, vkA = 0, vkE = 0, uiReady = false;
  function vkKey() { return "vk:" + (voice ? voice.name + "|" + voice.lang : ""); }
  function learnVoice(ms, est) {
    if (AUD.adapt === false || est < 300 || ms < 200) return;
    vkA += ms; vkE += est; if (vkE < 1500) return;
    var k = clamp(vkA / vkE, .5, 3);
    if (Math.abs(k - VK) / VK < .05) return;
    VK = k; store.set(vkKey(), k.toFixed(3)); retime(k);
  }
  function applyStoredVoiceRate() {
    if (!uiReady || AUD.adapt === false || !voice || vkE > 0) return;
    var k = parseFloat(store.get(vkKey(), "")); if (!(k > 0)) return;
    VK = k; vkA = k * 3000; vkE = 3000; retime(k);   /* 覚えた比は 3 秒分の重みで始め、測るたびに今の声に寄せる */
  }
  function planScene(sc, k) {
    var p = sc.s._plan; if (!p) return null;
    var rel = [], d, tt, a0, b0, tot, acc;
    if (p.L) { tt = 400; p.L.forEach(function (l) { var dur = l[1] || Math.max(900, l[0] * k + 250); rel.push([tt, tt + dur]); tt += dur + l[2]; });
      d = Math.max(tt + 500, p.min, p.floor || 0); }
    else { d = p.fix || Math.round(Math.max(p.min, p.sp * k + 1200) / 500) * 500;
      a0 = 500; b0 = Math.max(900, d - 400); tot = p.w.reduce(function (x, y) { return x + y; }, 0) || 1; acc = a0;
      p.w.forEach(function (w) { var span = (b0 - a0) * w / tot; rel.push([acc, acc + span]); acc += span; }); }
    return { d: Math.round(d), rel: rel };
  }
  function retime(k) {
    /* 今の場面とそれより前は動かさない（今の位置 t がそのまま使える） */
    var from = started || t > 0 ? sceneAt(t) + 1 : 0, T = 0, changed = false;
    SCENES.forEach(function (sc, i) {
      var rel = sc.cues.map(function (ci) { return [CUES[ci].a - sc.t0, CUES[ci].b - sc.t0]; });
      if (i >= from) { var r = planScene(sc, k); if (r) { if (r.d !== sc.d) changed = true; sc.d = r.d; if (r.rel.length === rel.length) rel = r.rel; } }
      sc.t0 = T; sc.cues.forEach(function (ci, j) { CUES[ci].a = Math.round(T + rel[j][0]); CUES[ci].b = Math.round(T + rel[j][1]);
        /* 台本の s._cues（場面の中の ms）も直す。custom が s._cues を読んでいても、直した後の時刻になる */
        var c = sc.s._cues && sc.s._cues[j]; if (c) { c[0] = Math.round(rel[j][0]); c[1] = Math.round(rel[j][1]); } });
      sc.s._dur = sc.d;
      T += sc.d;
    });
    if (!changed) return false;
    DUR = T;
    CHAPTERS.forEach(function (c, i) { for (var j = 0; j < SCENES.length; j++) if (SCENES[j].ci === i) { c.t = SCENES[j].t0; break; } });
    try { collectEvents(from); buildSfxQueue(); } catch (e) { console.warn("sfx:", e); }
    refreshTimes();
    return true;
  }
  /* 文書の図（figure.js。SPEC.figure）は声を持たないので、ページ全体の読み上げを止めない */
  function hush() { speaking = null; stopVoice(); root.classList.remove("mv-waiting"); if (SPEC.figure) return; try { if (synth) synth.cancel(); } catch (e) {} }
  function crossed(a, b, x) { return a < x && b >= x; }
  function onAdvance(a, b) {
    if (!audioOn) return;
    CUES.forEach(function (c) { if (crossed(a, b, c.a)) say(c.text, c); });
    if (b - a > 400) return;   /* 大きく飛んだ（シーク相当）ときは鳴らさない */
    SFXQ.forEach(function (q) { if (crossed(a, b, q.T)) sfxPlay(q.name, 0, q); });
  }

  /* ================= プレイヤー ================= */
  var store = { get: function (k, d) { try { var v = localStorage.getItem("mv:" + k); return v === null ? d : v; } catch (e) { return d; } },
                set: function (k, v) { try { localStorage.setItem("mv:" + k, v); } catch (e) {} } };
  var KIOSK = root.getAttribute("data-player") === "kiosk";
  var t = 0, playing = false, started = false, needsDraw = true, lastNow = 0, dragging = false;
  var SLIDES = root.getAttribute("data-player") === "slides", lastSave = 0;
  var POSKEY = "pos:" + location.pathname + ":" + (SPEC.title || "");
  /* 文書の図（SPEC.figure）は、ほかの動画で選んだ倍速に引きずられず、いつも 1 倍速 */
  var speed = SPEC.figure ? 1 : parseFloat(store.get("speed", "1")) || 1;
  var captions = store.get("cc", "1") === "1";
  var audioOn = KIOSK ? false : store.get("audio", AUD.default === "off" ? "0" : "1") === "1";
  var SPEEDS = [0.5, 0.75, 1, 1.25, 1.5, 2];
  var fmt = function (ms) { var s = Math.floor(ms / 1000); return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0"); };

  /* チャプター名が … で省略されているときだけ、ツールチップで全部の名前を出す */
  function chapTip() { var cn = $("mv-chapname"); if (!cn) return;
    if (cn.scrollWidth > cn.clientWidth + 1) cn.title = cn.textContent; else cn.removeAttribute("title"); }
  function resize() { chapTip(); if (recording) return; var r = cv.getBoundingClientRect(), dpr = Math.min(window.devicePixelRatio || 1, 2); domScale = r.width / W;
    var w = Math.max(1, Math.round(r.width * dpr)), h = Math.max(1, Math.round(r.height * dpr));
    if (cv.width !== w || cv.height !== h) { cv.width = w; cv.height = h; } needsDraw = true; }

  function play() {
    if (t >= DUR) t = 0;
    ensureAudio(); if (ac && ac.state === "suspended") ac.resume().catch(function () {});
    musicReset();
    playing = true; started = true; lastNow = performance.now();
    try { document.dispatchEvent(new CustomEvent("mv-exclusive", { detail: root })); } catch (e) {}
    var rb0 = $("mv-resume"); if (rb0) rb0.hidden = true;
    var c = CUES.filter(function (c) { return t >= c.a && t < c.b; })[0];
    if (c && audioOn && c.line && c.line.voice) playVoice(c.par || c, t - (c.par || c).a);
    else if (c && audioOn && (t - c.a) < (c.b - c.a) * .35) say(c.text, c);
    pickVoice(); syncUI(); poke();
  }
  function pause() { playing = false; hush(); musicStop(); cancelRec(); syncUI(); poke(); }
  function stop() { playing = false; hush(); musicStop(); cancelRec(); t = 0; started = false; needsDraw = true; syncUI(); poke(); }
  function toggle() { playing ? pause() : play(); }
  function seek(ms) { t = clamp(ms, 0, DUR); hush(); needsDraw = true; started = true; if (playing) musicReset(); if (t >= DUR) { playing = false; musicStop(); }
    else if (playing) { var cq = CUES.filter(function (c) { return t >= c.a && t < c.b; })[0]; if (cq && cq.line && cq.line.voice) playVoice(cq.par || cq, t - (cq.par || cq).a); } syncUI(); }
  function chapterStep(dir) { var i = chapterAt(t), n = i + dir; if (dir < 0 && t - CHAPTERS[i].t > 2000) n = i;
    n = clamp(n, 0, CHAPTERS.length - 1); seek(CHAPTERS[n].t); ensureAudio(); kitPlay("nav"); }
  function setSpeed(v) { speed = v; var sel = $("mv-speed"); if (sel) sel.value = String(v); store.set("speed", String(v)); if (playing) { hush(); musicReset(); } }
  function setCaptions(on) { captions = on; store.set("cc", on ? "1" : "0"); var b = $("mv-cc"); if (b) b.setAttribute("aria-pressed", String(on)); syncCaption(true); }
  function setAudio(on) { audioOn = on; store.set("audio", on ? "1" : "0"); var b = $("mv-audio");
    if (b) { b.setAttribute("aria-pressed", String(on)); b.setAttribute("aria-label", on ? "音声をオフにする" : "音声をオンにする"); }
    if (ac && master) master.gain.setTargetAtTime(on ? VOL : 0, ac.currentTime, .05);
    if (!on) { hush(); musicStop(); } else if (playing) { ensureAudio(); musicReset(); } pickVoice(); }

  /* シークバー（チャプターごとの区切り） */
  var seekEl = $("mv-seek"), track = $("mv-track");
  CHAPTERS.forEach(function (c, i) { var seg = document.createElement("div"); seg.className = "mv-seg"; seg.style.flex = String(chLen(i)); seg.appendChild(document.createElement("i")); track.appendChild(seg); });
  var segs = [].slice.call(track.children);
  /* 時間割が変わったとき（retime）に、シークバーの区切り・チャプターと文字起こしの時刻を書き直す */
  function refreshTimes() {
    segs.forEach(function (sg, i) { sg.style.flex = String(chLen(i)); });
    [].forEach.call(root.querySelectorAll('[data-mv="chapmenu"] button, [data-mv="chaplist"] button'), function (b) {
      var c = CHAPTERS[+b.dataset.i], el = b.querySelector(".t"); if (c && el) el.textContent = fmt(c.t); });
    var tl = $("mv-tlist"); if (tl) [].forEach.call(tl.querySelectorAll("button"), function (b) {
      var c = CUES[+b.dataset.i], el = b.querySelector(".t"); if (c && el) el.textContent = fmt(c.a); });
    needsDraw = true; syncUI();
  }
  function posToMs(x) { var r = seekEl.getBoundingClientRect(); return clamp((x - r.left) / r.width) * DUR; }
  /* シークバーのプレビュー: 描画は時刻だけで決まるので、その時刻の 1 コマを小さな Canvas に描く */
  var thumbRaf = 0, thumbAt = 0;
  function renderThumb(ms) {
    var tc = $("mv-thumb"); if (!tc || !tc.getClientRects().length) return;
    var cv0 = cv, ctx0 = ctx; cv = tc; ctx = tc.getContext("2d"); thumbMode = true;
    try { draw(ms); } catch (e) {} finally { thumbMode = false; cv = cv0; ctx = ctx0; }
  }
  function showTip(x) { var r = seekEl.getBoundingClientRect(), ms = posToMs(x), tip = $("mv-tip"); tip.hidden = false;
    $("mv-tiplabel").innerHTML = "<b>" + fmt(ms) + "</b>" + esc(CHAPTERS[chapterAt(ms)].name);
    thumbAt = ms; if (!thumbRaf) thumbRaf = requestAnimationFrame(function () { thumbRaf = 0; renderThumb(thumbAt); });
    var half = tip.offsetWidth / 2; tip.style.left = clamp(x - r.left, half, r.width - half) + "px"; }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  seekEl.addEventListener("pointerdown", function (e) { dragging = true; seekEl.classList.add("drag"); seekEl.setPointerCapture(e.pointerId); seek(posToMs(e.clientX)); showTip(e.clientX); });
  seekEl.addEventListener("pointermove", function (e) { showTip(e.clientX); if (dragging) seek(posToMs(e.clientX)); });
  var endDrag = function () { dragging = false; seekEl.classList.remove("drag"); };
  seekEl.addEventListener("pointerup", endDrag); seekEl.addEventListener("pointercancel", endDrag);
  seekEl.addEventListener("pointerleave", function () { if (!dragging) $("mv-tip").hidden = true; });
  seekEl.addEventListener("keydown", function (e) {
    var m = { ArrowLeft: -5000, ArrowDown: -5000, ArrowRight: 5000, ArrowUp: 5000 }[e.key];
    if (m) seek(t + m); else if (e.key === "Home") seek(0); else if (e.key === "End") seek(DUR);
    else if (e.key === "PageUp") chapterStep(-1); else if (e.key === "PageDown") chapterStep(1); else return;
    e.preventDefault(); e.stopPropagation(); });

  /* チャプターの一覧（メニューと、テンプレートによっては横・下の一覧） */
  var menu = $("mv-chapmenu"), list = $("mv-chaplist");
  CHAPTERS.forEach(function (c, i) {
    var num = String(i + 1).padStart(2, "0");
    if (menu) { var b = document.createElement("button"); b.type = "button"; b.dataset.i = i;
      b.innerHTML = '<span class="n">' + num + "</span><span>" + esc(c.name) + '</span><span class="t">' + fmt(c.t) + "</span>";
      b.addEventListener("click", function () { seek(c.t); closeMenu(true); if (!playing) play(); }); menu.appendChild(b); }
    if (list) { var li = document.createElement("li"), b2 = document.createElement("button"); b2.type = "button"; b2.dataset.i = i;
      b2.innerHTML = '<span class="n">' + num + '</span><span class="nm">' + esc(c.name) + (c.desc ? '<span class="d">' + esc(c.desc) + "</span>" : "") + '</span><span class="t">' + fmt(c.t) + "</span>";
      b2.addEventListener("click", function () { seek(c.t); if (!playing) play(); }); li.appendChild(b2); list.appendChild(li); }
  });
  function openMenu() { menu.hidden = false; $("mv-chapbtn").setAttribute("aria-expanded", "true"); (menu.querySelector('[aria-current="true"]') || menu.firstChild).focus(); }
  function closeMenu(refocus) { if (!menu || menu.hidden) return; menu.hidden = true; $("mv-chapbtn").setAttribute("aria-expanded", "false"); if (refocus) $("mv-chapbtn").focus(); }
  if (menu) {
    $("mv-chapbtn").addEventListener("click", function () { menu.hidden ? openMenu() : closeMenu(false); });
    menu.addEventListener("keydown", function (e) { var it = [].slice.call(menu.children), i = it.indexOf(document.activeElement);
      if (e.key === "ArrowDown") { it[(i + 1) % it.length].focus(); e.preventDefault(); }
      else if (e.key === "ArrowUp") { it[(i - 1 + it.length) % it.length].focus(); e.preventDefault(); }
      else if (e.key === "Escape") { closeMenu(true); e.preventDefault(); } e.stopPropagation(); });
  }
  /* minimal の「⋯」メニュー（速度・字幕・音声・チャプターをまとめる） */
  var more = $("mv-more"), morePanel = $("mv-morepanel");
  if (more && morePanel && root.getAttribute("data-player") === "minimal") {
    more.addEventListener("click", function () { var open = morePanel.hidden; morePanel.hidden = !open; more.setAttribute("aria-expanded", String(open)); });
    morePanel.addEventListener("keydown", function (e) { if (e.key === "Escape") { morePanel.hidden = true; more.setAttribute("aria-expanded", "false"); more.focus(); } });
  }
  document.addEventListener("pointerdown", function (e) {
    if (menu && !menu.hidden && !e.target.closest(".mv-menuwrap")) closeMenu(false);
    if (morePanel && root.getAttribute("data-player") === "minimal" && !morePanel.hidden && !e.target.closest(".mv-morewrap")) { morePanel.hidden = true; more.setAttribute("aria-expanded", "false"); }
  });

  /* ボタン */
  function on(id, ev, fn) { var el = $(id); if (el) el.addEventListener(ev, fn); }
  on("mv-play", "click", toggle);
  /* 中央のボタンは再生で隠れるので、キー操作が効くようにプレイヤーへフォーカスを移す */
  function focusPlayer() { try { root.focus({ preventScroll: true }); } catch (e) { root.focus(); } }
  on("mv-big", "click", function (e) { e.stopPropagation(); play(); focusPlayer(); });
  on("mv-stage", "click", function () { if (KIOSK && !started) play(); else toggle(); focusPlayer(); });
  on("mv-stop", "click", stop);
  on("mv-prev", "click", function () { chapterStep(-1); });
  on("mv-next", "click", function () { chapterStep(1); });
  on("mv-speed", "change", function (e) { setSpeed(parseFloat(e.target.value)); });
  on("mv-cc", "click", function () { setCaptions(!captions); });
  on("mv-audio", "click", function () { setAudio(!audioOn); });
  /* 音量（声・音楽・効果音をまとめて。0 にしても「音声」の入・切とは別に覚える） */
  function setVol(v, user) { VOL = Math.round(clamp(v) * 100) / 100; store.set("vol", String(VOL)); var el = $("mv-vol");
    if (el) { el.value = String(Math.round(VOL * 100)); el.setAttribute("aria-valuetext", Math.round(VOL * 100) + "%"); }
    if (user && VOL > 0 && !audioOn) setAudio(true);   /* 切のときに音量を上げたら入にする（読み上げは次の字幕から） */
    if (ac && master) master.gain.setTargetAtTime(audioOn ? VOL : 0, ac.currentTime, .03); }
  on("mv-vol", "input", function (e) { setVol(+e.target.value / 100, true); });
  on("mv-fs", "click", function () { try { if (document.fullscreenElement) document.exitFullscreen().catch(function () {}); else if (root.requestFullscreen) root.requestFullscreen().catch(function () {}); } catch (e) {} });
  document.addEventListener("fullscreenchange", function () { setTimeout(resize, 50); });
  root.addEventListener("keydown", function (e) {
    if (e.target.tagName === "SELECT" || e.target.tagName === "INPUT" || e.altKey || e.ctrlKey || e.metaKey) return;
    var k = e.key, done = true;
    if (k === " " || k === "k" || k === "K") { if (e.target.tagName === "BUTTON" && k === " ") done = false; else toggle(); }
    else if (k === "s" || k === "S") stop();
    else if (k === "ArrowLeft") seek(t - 5000); else if (k === "ArrowRight") seek(t + 5000);
    else if (k === "ArrowUp") setVol(VOL + .1, true); else if (k === "ArrowDown") setVol(VOL - .1, true);
    else if (k === "[") chapterStep(-1); else if (k === "]") chapterStep(1);
    else if (k === "c" || k === "C") setCaptions(!captions); else if (k === "m" || k === "M") setAudio(!audioOn);
    else if (k === "f" || k === "F") $("mv-fs").click();
    else if (/^[0-9]$/.test(k)) seek(DUR * (+k) / 10);
    else if (k === "j" || k === "J") seek(t - 10000);
    else if (k === "l" || k === "L") seek(t + 10000);
    else if (k === "<" || k === ",") setSpeed(SPEEDS[Math.max(0, SPEEDS.indexOf(speed) - 1)] || 1);
    else if (k === ">" || k === ".") setSpeed(SPEEDS[Math.min(SPEEDS.length - 1, SPEEDS.indexOf(speed) + 1)] || 1);
    else done = false;
    if (done) { e.preventDefault(); poke(); }
  });

  /* 操作部の自動で隠れる動き（cinema・minimal・kiosk） */
  var hideTimer = 0;
  function poke() { root.classList.add("mv-awake"); clearTimeout(hideTimer);
    hideTimer = setTimeout(function () {
      var a = document.activeElement, inControls = a && a.closest && a.closest(".mv-controls");
      if (playing && !dragging && !inControls) root.classList.remove("mv-awake");
    }, 2600); }
  root.addEventListener("pointermove", poke); root.addEventListener("focusin", poke);

  var lastCap = null, lastChap = -1;
  function syncCaption(force) {
    var cw = CUES.filter(function (c) { return t >= c.a && t < c.b; })[0]; if (cw && cw.who) { if (lastCap !== "" || force) { lastCap = ""; var el0 = $("mv-captext"); el0.textContent = ""; el0.hidden = true; } return; }
    var c = CUES.filter(function (c) { return t >= c.a && t < c.b; })[0], text = captions && started && c ? c.text.replace(/\*\*/g, "") : "";
    if (text !== lastCap || force) { lastCap = text; var el = $("mv-captext"); el.textContent = text; el.hidden = !text; }
  }
  function syncUI() {
    var pb = $("mv-play"); pb.setAttribute("aria-label", playing ? "一時停止" : "再生");
    pb.querySelector(".i-play").hidden = playing; pb.querySelector(".i-pause").hidden = !playing;
    var big = $("mv-big");
    if (big && SLIDES) {
      var ci0 = chapterAt(t), atStart = t > 0 && t < DUR && Math.abs(t - CHAPTERS[ci0].t) < 50;
      var lab = !started || t === 0 ? "再生" : t >= DUR ? "もう一度" : atStart ? "次へ：" + CHAPTERS[ci0].name : "続きを再生";
      big.hidden = playing; big.setAttribute("aria-label", lab); var bl = big.querySelector(".mv-biglabel"); if (bl) bl.textContent = lab;
    } else if (big) { big.hidden = playing || (started && t > 0 && t < DUR); big.setAttribute("aria-label", t >= DUR ? "もう一度再生" : "再生"); }
    root.classList.toggle("mv-playing", playing);
    $("mv-time").innerHTML = "<b>" + fmt(t) + "</b> / " + fmt(DUR);
    var ci = chapterAt(t);
    if (ci !== lastChap) { lastChap = ci; var cn = $("mv-chapname"); if (cn) { cn.textContent = CHAPTERS[ci].name; chapTip(); }
      [].forEach.call(root.querySelectorAll('[data-mv="chapmenu"] button, [data-mv="chaplist"] button'), function (b) { b.setAttribute("aria-current", String(+b.dataset.i === ci)); });
      var cur = list && list.querySelector('[aria-current="true"]'); if (cur && root.getAttribute("data-player") === "presenter" && cur.scrollIntoView) cur.scrollIntoView({ block: "nearest" }); }
    if (tlist) {
      var cc = -1; CUES.forEach(function (c, i) { if (t >= c.a) cc = i; });
      if (cc !== lastCue) { lastCue = cc; [].forEach.call(tlist.querySelectorAll("button"), function (b) { b.setAttribute("aria-current", String(+b.dataset.i === cc)); });
        var cb = tlist.querySelector('[aria-current="true"]'), box = tlist.parentNode;
        if (cb && box && box.scrollHeight > box.clientHeight) { var r1 = cb.getBoundingClientRect(), r2 = box.getBoundingClientRect(); if (r1.top < r2.top || r1.bottom > r2.bottom) box.scrollTop += r1.top - r2.top - 60; } }
    }
    segs.forEach(function (s, i) { s.firstChild.style.width = (clamp((t - CHAPTERS[i].t) / chLen(i)) * 100) + "%"; });
    $("mv-knob").style.left = (t / DUR * 100) + "%";
    seekEl.setAttribute("aria-valuemax", String(Math.round(DUR / 1000)));
    seekEl.setAttribute("aria-valuenow", String(Math.round(t / 1000)));
    seekEl.setAttribute("aria-valuetext", Math.floor(t / 60000) + " 分 " + (Math.floor(t / 1000) % 60) + " 秒、" + CHAPTERS[ci].name);
    syncCaption(false);
  }
  function frame(now) {
    if (ENDFADE && ac && master) { var ek = playing && t > DUR - ENDFADE ? clamp((DUR - t) / ENDFADE) : 1;   /* 終わりの暗転に合わせて、音も消していく */
      if (Math.abs(ek - endK) > .01) { endK = ek; master.gain.setTargetAtTime((audioOn ? VOL : 0) * ek, ac.currentTime, .03); } }
    if (playing) {
      var nt = Math.min(DUR, t + Math.min(100, now - lastNow) * speed);
      /* 読み上げが字幕の終わりまでに終わらなければ、読み終わるまで字幕の終わりの手前で待つ（終わりの知らせが来ない時の上限つき） */
      if (speaking && speaking.cue && !speaking.file && AUD.wait !== false) {
        if (performance.now() - speaking.started > speaking.maxMs) { speaking = null; root.classList.remove("mv-waiting"); }
        else if (nt > speaking.cue.b - 60) { nt = Math.max(t, speaking.cue.b - 60); root.classList.add("mv-waiting"); }
      }
      /* slides: 章の終わりで止まる（「次へ」で続きを再生） */
      var slideStop = false;
      if (SLIDES && !recording && nt < DUR && chapterAt(nt) > chapterAt(t)) { nt = CHAPTERS[chapterAt(nt)].t; slideStop = true; }
      var prev = t; t = nt; onAdvance(prev, t); musicTick(Math.min(100, now - lastNow)); syncDuck();
      if (now - lastSave > 2000) { lastSave = now; store.set(POSKEY, String(t >= DUR - 3000 ? 0 : Math.round(t))); }
      if (slideStop) { playing = false; hush(); musicStop(); }
      if (t >= DUR) { if (KIOSK && !recording) { t = 0; hush(); musicReset(); } else { playing = false; musicStop(); if (recording) finishRec(); } }
      syncUI(); needsDraw = true;
    }
    lastNow = now;
    if (needsDraw) { draw(started || t > 0 ? t : (SPEC.poster !== undefined ? SPEC.poster : Math.min(4300, DUR))); needsDraw = playing; }
    requestAnimationFrame(frame);
  }

  /* 文字起こし（theater で横に出す。クリックでその位置へ・検索） */
  var tlist = $("mv-tlist"), tsearch = $("mv-tsearch"), lastCue = -2;
  if (tlist) {
    CUES.forEach(function (c, i) {
      var li = document.createElement("li"), b = document.createElement("button"); b.type = "button"; b.dataset.i = i;
      b.innerHTML = '<span class="t">' + fmt(c.a) + "</span><span>" + (c.who && CAST[c.who] ? "<b>" + esc(CAST[c.who].name || c.who) + "：</b>" : "") + esc(c.text.replace(/\*\*/g, "")) + "</span>";
      b.addEventListener("click", function () { seek(c.a); if (!playing) play(); }); li.appendChild(b); tlist.appendChild(li);
    });
    if (tsearch) tsearch.addEventListener("input", function () { var q = tsearch.value.trim().toLowerCase();
      [].forEach.call(tlist.children, function (li) { li.hidden = !!q && li.textContent.toLowerCase().indexOf(q) < 0; }); });
  }
  /* 続きから再生（このブラウザに位置を覚える） */
  var rb = $("mv-resume"), savedPos = parseFloat(store.get(POSKEY, "0")) || 0;
  if (rb && !KIOSK && savedPos > 5000 && savedPos < DUR - 5000) {
    rb.hidden = false; rb.textContent = "▶ 前回の続き（" + fmt(savedPos) + "）から再生";
    rb.addEventListener("click", function (e) { e.stopPropagation(); rb.hidden = true; seek(savedPos); play(); focusPlayer(); });
  }
  /* 設定（字幕の大きさ・小窓・保存） */
  var setBtn = $("mv-setbtn"), setPanel = $("mv-setpanel");
  function closeSet(refocus) { if (!setPanel || setPanel.hidden) return; setPanel.hidden = true; setBtn.setAttribute("aria-expanded", "false"); if (refocus) setBtn.focus(); }
  function setCap(v) { root.setAttribute("data-cap", v); store.set("cap", v);
    [].forEach.call(root.querySelectorAll("button[data-cap]"), function (b) { b.setAttribute("aria-pressed", String(b.getAttribute("data-cap") === v)); }); }
  if (setBtn && setPanel) {
    setBtn.addEventListener("click", function () { var o = setPanel.hidden; setPanel.hidden = !o; setBtn.setAttribute("aria-expanded", String(o)); if (o) { var f = setPanel.querySelector("button"); if (f) f.focus(); } });
    setPanel.addEventListener("keydown", function (e) { if (e.key === "Escape") { closeSet(true); e.preventDefault(); } e.stopPropagation(); });
    [].forEach.call(setPanel.querySelectorAll("button[data-cap]"), function (b) { b.addEventListener("click", function () { setCap(b.getAttribute("data-cap")); }); });
    document.addEventListener("pointerdown", function (e) { if (!setPanel.hidden && !e.target.closest('[data-mv="setpanel"]') && !e.target.closest('[data-mv="setbtn"]')) closeSet(false); });
  }
  setCap(store.get("cap", "m"));
  /* プレイヤーの表示（操作部・一覧・メニュー・設定の色）。映像の中はテーマの色のまま。
     テーマ = 台本の配色のまま / ライト / ダーク / システム（OS の設定に従い、変わればその場で追う） */
  var UI0 = {}, UIV = ["bg", "bg2", "line", "ink", "muted", "accent"];
  UIV.forEach(function (k) { UI0[k] = root.style.getPropertyValue("--c-" + k).trim(); });
  function lum(hex) { var m = /^#?([0-9a-f]{6})$/i.exec(hex || ""); if (!m) return .5; var n = parseInt(m[1], 16);
    return (.2126 * (n >> 16 & 255) + .7152 * (n >> 8 & 255) + .0722 * (n & 255)) / 255; }
  var UI_NATIVE = lum(UI0.bg) < .5 ? "dark" : "light";
  var UIPAL = { light: { bg: "#ffffff", bg2: "#f3f6fa", line: "#d6dde7", ink: "#18212c", muted: "#5b6777" },
                dark: { bg: "#0e141b", bg2: "#151d27", line: "#2a3542", ink: "#e7edf4", muted: "#98a6b4" } };
  var uiMQ = window.matchMedia ? matchMedia("(prefers-color-scheme: dark)") : null, uiPref = "";
  function applyUI() {
    var want = uiPref === "system" ? (uiMQ && uiMQ.matches ? "dark" : "light") : uiPref || UI_NATIVE;
    root.setAttribute("data-uimode", want);
    if (want === UI_NATIVE) { UIV.forEach(function (k) { root.style.setProperty("--c-" + k, UI0[k]); }); return; }
    var P = UIPAL[want]; UIV.forEach(function (k) { if (P[k]) root.style.setProperty("--c-" + k, P[k]); });
    /* テーマの差し色は、逆の明るさの地でも読めるように寄せる */
    root.style.setProperty("--c-accent", "color-mix(in srgb," + UI0.accent + (want === "light" ? " 72%,#000)" : " 62%,#fff)"));
  }
  function setUI(v) { uiPref = v || ""; store.set("ui", uiPref);
    [].forEach.call(root.querySelectorAll("button[data-ui]"), function (b) { b.setAttribute("aria-pressed", String(b.getAttribute("data-ui") === uiPref)); });
    applyUI(); }
  [].forEach.call(root.querySelectorAll("button[data-ui]"), function (b) { b.addEventListener("click", function () { setUI(b.getAttribute("data-ui")); }); });
  if (uiMQ) { var onMQ = function () { if (uiPref === "system") applyUI(); }; if (uiMQ.addEventListener) uiMQ.addEventListener("change", onMQ); else if (uiMQ.addListener) uiMQ.addListener(onMQ); }
  setUI(store.get("ui", ""));
  /* 書体（映像の文字と字幕）。OS に入っている書体だけを選べるようにする。描画は時刻と台本だけで決まるので、選び直してもそのまま描き直せる */
  var F0 = { sans: F.sans, display: F.display };
  var FONTS = [
    ["", "テーマの既定", null],
    ["gothic", "ゴシック", ['"Hiragino Sans"', '"Hiragino Kaku Gothic ProN"', '"Yu Gothic UI"', '"Yu Gothic"', "Meiryo", '"Noto Sans JP"', '"Noto Sans CJK JP"']],
    ["mincho", "明朝", ['"Hiragino Mincho ProN"', '"Yu Mincho"', "YuMincho", '"Noto Serif JP"', '"Noto Serif CJK JP"', '"MS PMincho"']],
    ["maru", "丸ゴシック", ['"Hiragino Maru Gothic ProN"', '"Zen Maru Gothic"', '"M PLUS Rounded 1c"', '"Kosugi Maru"']],
    ["ud", "UD（読みやすさ重視）", ['"BIZ UDPGothic"', '"BIZ UDGothic"', '"UD Digi Kyokasho NK-R"', '"Morisawa BIZ UDPGothic"']],
    ["meiryo", "メイリオ", ["Meiryo"]],
    ["kyokasho", "教科書体", ['"UD Digi Kyokasho NK-R"', '"UD Digi Kyokasho N-R"', '"YuKyokasho"']]
  ];
  /* その書体があるか: 既定の書体と幅が変わるかで見る（document.fonts.check は OS の書体には使えない） */
  function hasFont(name) {
    var c = document.createElement("canvas").getContext("2d"), s = "あいう永ABCabc123", ok = false;
    ["monospace", "serif"].forEach(function (base) { c.font = "40px " + base; var w0 = c.measureText(s).width; c.font = "40px " + name + "," + base; if (c.measureText(s).width !== w0) ok = true; });
    return ok;
  }
  var fontSel = $("mv-font"), FONTOK = {};
  FONTS.forEach(function (f) { var list = f[2] ? f[2].filter(hasFont) : null; if (f[2] && !list.length) return; FONTOK[f[0]] = list;
    if (fontSel) { var op = document.createElement("option"); op.value = f[0]; op.textContent = f[1]; fontSel.appendChild(op); } });
  function setFont(k) {
    if (!(k in FONTOK)) k = "";
    var list = FONTOK[k], stack = list ? list.join(",") + "," + (k === "mincho" ? "serif" : "sans-serif") : null;
    F.sans = stack || F0.sans; F.display = stack || F0.display;
    /* 字幕とプレイヤーの文字（チャプターの一覧・メニュー・設定・文字起こし）も同じ書体に。時刻などの等幅はそのまま */
    ["--mv-capfont", "--mv-uifont"].forEach(function (v) { if (stack) root.style.setProperty(v, stack); else root.style.removeProperty(v); });
    store.set("font", k); if (fontSel) fontSel.value = k; needsDraw = true;
  }
  if (fontSel) fontSel.addEventListener("change", function () { setFont(fontSel.value); });
  setFont(store.get("font", ""));
  function setMus(on) { musicOn = on; store.set("mus", on ? "1" : "0");
    [].forEach.call(root.querySelectorAll("button[data-mus]"), function (b) { b.setAttribute("aria-pressed", String((b.getAttribute("data-mus") === "1") === on)); });
    if (!on) musicStop(); else if (playing) musicReset(); }
  function setSfx(on) { sfxOn = on; store.set("sfx", on ? "1" : "0");
    [].forEach.call(root.querySelectorAll("button[data-sfx]"), function (b) { b.setAttribute("aria-pressed", String((b.getAttribute("data-sfx") === "1") === on)); }); }
  [].forEach.call(root.querySelectorAll("button[data-mus]"), function (b) { b.addEventListener("click", function () { setMus(b.getAttribute("data-mus") === "1"); }); });
  [].forEach.call(root.querySelectorAll("button[data-sfx]"), function (b) { b.addEventListener("click", function () { setSfx(b.getAttribute("data-sfx") === "1"); }); });
  setMus(store.get("mus", "1") === "1"); setSfx(store.get("sfx", "1") === "1");
  var pipBtn = $("mv-pip"), pipVideo = null;
  if (pipBtn) {
    if (!(document.pictureInPictureEnabled && cv.captureStream)) pipBtn.hidden = true;
    pipBtn.addEventListener("click", function () {
      closeSet(false);
      try {
        if (document.pictureInPictureElement) { document.exitPictureInPicture(); return; }
        if (!pipVideo) { pipVideo = document.createElement("video"); pipVideo.muted = true;
          /* 小窓の間はボタンを押された状態にする（小窓の × で閉じたときも戻す） */
          pipVideo.addEventListener("enterpictureinpicture", function () { pipBtn.setAttribute("aria-pressed", "true"); pipBtn.setAttribute("aria-label", "小窓を閉じる"); });
          pipVideo.addEventListener("leavepictureinpicture", function () { pipBtn.setAttribute("aria-pressed", "false"); pipBtn.setAttribute("aria-label", "小窓で再生（ピクチャー・イン・ピクチャー）"); }); }
        pipVideo.srcObject = cv.captureStream(30);
        pipVideo.play().then(function () { return pipVideo.requestPictureInPicture(); }).catch(function (e) { console.warn("pip:", e); });
        if (!playing) play();
      } catch (e) { console.warn("pip:", e); }
    });
  }
  /* @export-begin — 書き出し（WebM で保存・編集用の映像・音のトラック）。配布用（build.py --dist）では、ここから @export-end までを
   * build.py の EXPORT_STUB（finishRec・cancelRec の空の関数）に置き換えて HTML を小さくする */
  /* 動画ファイル（WebM）で保存: 最初から 1 倍速で再生しながら Canvas を録画する（字幕は焼き込み。読み上げの声は録れない）
   * clean（編集用の映像）: 1920×1080・字幕なし・音なし。声を待たず、台本どおりの時間割（build.py --export の字幕・音・プロジェクトと揃う）で録る */
  var recBtn = $("mv-rec"), recBadge = $("mv-recbadge"), recCleanBtn = $("mv-recclean");
  if (!(window.MediaRecorder && cv.captureStream)) { if (recBtn) recBtn.hidden = true; if (recCleanBtn) recCleanBtn.hidden = true; }
  function exportName() { return SPEC._exportName || (SPEC.title || "video").replace(/[\\/:*?"<>|]/g, "_"); }
  function download(blob, name) {
    var a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = name;
    document.body.appendChild(a); a.click(); a.remove(); setTimeout(function () { URL.revokeObjectURL(a.href); }, 60000);
  }
  /* 台本どおりの時間割に戻す（ブラウザの声の速さで直した分を外す）。書き出しの間だけ使い、終わったら restoreTiming で戻す */
  function nominalTiming() { if (VK === 1) return; t = 0; started = false; retime(1); }
  function restoreTiming() { if (VK === 1) return; t = 0; started = false; retime(VK); needsDraw = true; syncUI(); }
  function startRec(clean) {
    closeSet(false);
    try {
      var rec = { cancel: false, speed: speed, clean: !!clean, audio: audioOn };
      if (clean) { hush(); musicStop(); audioOn = false; nominalTiming(); }
      var vr = vertOn(); cv.width = vr ? (clean ? 1080 : 720) : clean ? 1920 : 1280; cv.height = vr ? (clean ? 1920 : 1280) : clean ? 1080 : 720;
      var stream = cv.captureStream(30);
      if (!clean) { ensureAudio();
        if (ac && master && ac.createMediaStreamDestination) { var dest = ac.createMediaStreamDestination(); master.connect(dest); dest.stream.getAudioTracks().forEach(function (tr) { stream.addTrack(tr); }); } }
      var mime = window.MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported("video/webm;codecs=vp9") ? "video/webm;codecs=vp9" : "video/webm";
      var mr = new MediaRecorder(stream, clean ? { mimeType: mime, videoBitsPerSecond: 12000000 } : { mimeType: mime }), chunks = [];
      rec.mr = mr;
      mr.ondataavailable = function (e) { if (e.data && e.data.size) chunks.push(e.data); };
      mr.onstop = function () {
        if (recBadge) recBadge.hidden = true;
        if (!rec.cancel) download(new Blob(chunks, { type: "video/webm" }), exportName() + (clean ? "_video" : "") + ".webm");
      };
      setSpeed(1); t = 0; started = true; hush();
      recording = rec; if (recBadge) { recBadge.textContent = clean ? "● 録画中（編集用）" : "● 録画中"; recBadge.hidden = false; }
      mr.start(1000); play(); focusPlayer();
    } catch (e) { console.warn("rec:", e); recording = null; resize(); }
  }
  function finishRec() { var r = recording; if (!r) return; recording = null; try { r.mr.stop(); } catch (e) {} setSpeed(r.speed);
    if (r.clean) { audioOn = r.audio; restoreTiming(); } resize(); }
  function cancelRec() { if (!recording) return; recording.cancel = true; finishRec(); }
  if (recBtn) recBtn.addEventListener("click", function () { if (recording) cancelRec(); else startRec(false); });
  if (recCleanBtn) recCleanBtn.addEventListener("click", function () { if (recording) cancelRec(); else startRec(true); });

  /* 音のトラックを書き出す（WAV・48kHz・ステレオ）: 声・音楽・効果音と、それを混ぜたものを、台本どおりの時間割で
   * OfflineAudioContext に描き出す（再生を待たずに作れる）。編集ソフト（YMM4・AviUtl など）や YouTube の音声トラック用。
   * 声は前もって作った声（--voicevox・--voices-dir）だけ。ブラウザの読み上げの声は書き出せない */
  var expBtn = $("mv-expaudio"), exporting = false;
  if (expBtn && !(window.OfflineAudioContext && MA)) expBtn.hidden = true;
  var SR = 48000;
  function decodeUrl(url, ctx2) { return audioBytes(url).then(function (b) { return (ctx2 || ac).decodeAudioData(b); })   /* fetch を使わない（埋め込みの data: を読めない環境がある）。ac がまだ無ければ書き出しの文脈で */.catch(function (e) { console.warn("export:", e); return null; }); }
  /* 声・ファイルの効果音・楽器の録音の音の復号を待つ（数が変わらなくなるまで。長くても ms まで） */
  function waitDecoded(ms) {
    return new Promise(function (res) { var t0 = performance.now(), last = "", same = 0;
      (function poll() {
        var pend = Object.keys(VBUF).filter(function (k) { return VBUF[k] === null; }).length
          + Object.keys(SFXD).filter(function (k) { return SFXD[k].file && !SFXBUF[k]; }).length;
        var sig = JSON.stringify(MA.samplesReady ? MA.samplesReady() : {}); same = sig === last ? same + 1 : 0; last = sig;
        if ((!pend && same >= 3) || performance.now() - t0 > ms) res(); else setTimeout(poll, 200);
      })(); });
  }
  function renderStem(fill) {
    var oc = new OfflineAudioContext(2, Math.ceil((DUR + 1500) / 1000 * SR), SR);
    return Promise.resolve(fill(oc, oc.destination)).then(function () { return oc.startRendering(); });
  }
  function hasMusic() { return msegs().some(function (m) { return m.key && MUS[m.key]; }); }
  function voiceCues() { return AUD.narration === false ? [] : CUES.filter(function (c) { return c.key && !c.par && VBUF[c.key]; }); }
  function fillVoice(oc, out) {
    voiceCues().forEach(function (c) { var s = oc.createBufferSource(), g = oc.createGain(); s.buffer = VBUF[c.key];
      g.gain.value = c.line.volume === undefined ? 1 : c.line.volume; s.connect(g); g.connect(out); s.start(c.a / 1000); });
  }
  /* 音楽: musicTick と同じく章ごとに曲の頭から（全体の曲のファイルは映像の先頭からの位置）。映像の最初と最後で下げる */
  function fillMusic(oc, out) {
    var jobs = [], X = XFADE / 1000;
    msegs().forEach(function (M, si) {
      var key = M.key, def = key ? MUS[key] : null; if (!def) return;
      var t0 = M.t, len = M.end - M.t, ci = M.ci, bus = oc.createGain(); bus.connect(out);
      if (def.file) {
        var vol = (def.volume === undefined ? .35 : def.volume) * MUSVOL, a0 = t0 / 1000, a1 = (t0 + len) / 1000;
        bus.gain.setValueAtTime(si > 0 ? 0 : vol, a0); if (si > 0) bus.gain.linearRampToValueAtTime(vol, a0 + X);   /* 前の曲と重ねて入れ替える */
        var last = si === msegs().length - 1; bus.gain.setValueAtTime(vol, a1); if (!last) bus.gain.linearRampToValueAtTime(0, a1 + X);
        jobs.push(decodeUrl(def.file, oc).then(function (b) { if (!b) return;
          var off = (M.cont ? t0 : 0) / 1000, stopAt = last ? a1 : a1 + X;
          if (def.loop === true) { var src = oc.createBufferSource(); src.buffer = b; src.loop = true; src.connect(bus); src.start(a0, off % b.duration); src.stop(stopAt); return; }
          /* ループ用でない曲: 音楽としての終わり（フェードアウトの前）の数秒を、次の頭に重ねて、くり返しをつなぐ */
          var D = musicEnd(b), XX = Math.min(3, D * .12), Lc = D - XX, n0 = Math.floor(off / Lc), t = a0, pos = off - n0 * Lc;
          for (var n = n0; t < stopAt; n++) {
            var s2 = oc.createBufferSource(), g = oc.createGain(); s2.buffer = b; s2.connect(g); g.connect(bus);
            var startAt = t, endAt = Math.min(stopAt, t + (D - pos));
            g.gain.setValueAtTime(n > n0 ? 0 : 1, startAt); if (n > n0) g.gain.linearRampToValueAtTime(1, startAt + XX);
            g.gain.setValueAtTime(1, Math.max(startAt, endAt - XX)); g.gain.linearRampToValueAtTime(endAt < stopAt ? 0 : 1, endAt);
            s2.start(startAt, pos); s2.stop(endAt);
            t = t + (Lc - pos); pos = 0;
          } }));
        return;
      }
      bus.gain.value = MUSVOL * (def.g || 1);
      MA.notes(def, { ci: ci, energy: energyOf(ci), len: len }, 0, len).forEach(function (n) {
        var tv = t0 + n.t, fade = clamp(tv / 1200 + .15) * clamp((DUR - tv) / 2500); if (fade <= 0) return;
        MA.note(oc, bus, n, tv / 1000, Math.max(.05, (n.d || 0) / 1000), fade, INSTX, false);
      });
    });
    return Promise.all(jobs);
  }
  function fillSfx(oc, out) {
    var bus = oc.createGain(); bus.gain.value = SFXCFG && SFXCFG.volume !== undefined ? SFXCFG.volume : 1; bus.connect(out);
    SFXQ.forEach(function (q) { sfxPlay(q.name, q.T / 1000, q, oc, bus); });
  }
  /* 全部: 再生と同じく、声の間は音楽を下げ（audio.duck）、出口に抑えを掛ける */
  function fillMix(st) { return function (oc, out) {
    var lim = oc.createDynamicsCompressor(); lim.threshold.value = -6; lim.knee.value = 6; lim.ratio.value = 12; lim.attack.value = .003; lim.release.value = .2; lim.connect(out);
    var duck = oc.createGain(); duck.gain.value = 1; duck.connect(lim);
    var dv = AUD.duck === undefined ? .5 : AUD.duck;
    voiceCues().forEach(function (c) { duck.gain.setTargetAtTime(dv, c.a / 1000, .08); duck.gain.setTargetAtTime(1, c.a / 1000 + VBUF[c.key].duration, .4); });
    [[st.voice, lim], [st.music, duck], [st.sfx, lim]].forEach(function (p) { if (!p[0]) return; var s = oc.createBufferSource(); s.buffer = p[0]; s.connect(p[1]); s.start(0); });
  }; }
  function wavBlob(buf) {
    var n = buf.length, ch = buf.numberOfChannels, sr = buf.sampleRate, size = n * ch * 2, dv = new DataView(new ArrayBuffer(44 + size)), p = 0, i, c;
    var str = function (x) { for (var k = 0; k < x.length; k++) dv.setUint8(p++, x.charCodeAt(k)); }, u32 = function (v) { dv.setUint32(p, v, true); p += 4; }, u16 = function (v) { dv.setUint16(p, v, true); p += 2; };
    str("RIFF"); u32(36 + size); str("WAVE"); str("fmt "); u32(16); u16(1); u16(ch); u32(sr); u32(sr * ch * 2); u16(ch * 2); u16(16); str("data"); u32(size);
    var data = []; for (c = 0; c < ch; c++) data.push(buf.getChannelData(c));
    for (i = 0; i < n; i++) for (c = 0; c < ch; c++) { var v = Math.max(-1, Math.min(1, data[c][i])); dv.setInt16(p, v < 0 ? v * 32768 : v * 32767, true); p += 2; }
    return new Blob([dv], { type: "audio/wav" });
  }
  function exportAudio() {
    if (exporting || recording) return;
    closeSet(false); ensureAudio(); if (!ac) return;
    exporting = true; if (playing) pause(); nominalTiming();
    if (recBadge) { recBadge.textContent = "● 音を書き出し中…"; recBadge.hidden = false; }
    var st = {}, done = function () { exporting = false; if (recBadge) recBadge.hidden = true; restoreTiming(); };
    waitDecoded(10000)
      .then(function () { return voiceCues().length ? renderStem(fillVoice) : null; }).then(function (b) { st.voice = b; return hasMusic() ? renderStem(fillMusic) : null; })
      .then(function (b) { st.music = b; return SFXCFG && SFXQ.length ? renderStem(fillSfx) : null; }).then(function (b) { st.sfx = b; return renderStem(fillMix(st)); })
      .then(function (b) { st.mix = b;
        var name = exportName();
        [["voice", st.voice], ["music", st.music], ["sfx", st.sfx], ["mix", st.mix]].filter(function (x) { return x[1]; })
          .forEach(function (x, i) { setTimeout(function () { download(wavBlob(x[1]), name + "_" + x[0] + ".wav"); }, i * 700); });
      })
      .catch(function (e) { console.warn("export:", e); }).then(done);
  }
  if (expBtn) expBtn.addEventListener("click", exportAudio);
  /* @export-end */

  /* 起動 */
  var sel = $("mv-speed"); if (sel) sel.value = String(speed);
  var ccb = $("mv-cc"); if (ccb) ccb.setAttribute("aria-pressed", String(captions));
  setVol(parseFloat(store.get("vol", "1")));
  var aub = $("mv-audio"); if (aub) { aub.setAttribute("aria-pressed", String(audioOn)); aub.setAttribute("aria-label", audioOn ? "音声をオフにする" : "音声をオンにする"); }
  var IMG_TYPES = { tour: ["src"], scrollshot: ["src"], swipe: ["before", "after"] };
  var preload = function (src) { if (!src || IMGS[src]) return; var im = new Image(); im.onload = function () { needsDraw = true; }; im.src = src; IMGS[src] = im; };
  Object.keys(CAST).forEach(function (id) { var sp = CAST[id].sprite; if (sp) Object.keys(sp.images || {}).forEach(function (k) { preload(sp.images[k]); }); });
  Object.keys(CAST).forEach(function (id) { var im = CAST[id].images || {}; Object.keys(im).forEach(function (f) { var v = im[f]; if (typeof v === "string") preload(v); else Object.keys(v || {}).forEach(function (s2) { preload(v[s2]); }); }); });
  SCENES.forEach(function (sc) { preload(sc.s.bg); if (sc.s.board && sc.s.board.type === "image") preload(sc.s.board.src); });
  Object.keys(SPEC.images || {}).forEach(function (k) { if (IMGS["@" + k]) return; var im = new Image(); im.onload = function () { needsDraw = true; }; im.src = SPEC.images[k]; IMGS["@" + k] = im; });   /* 絵で見せる場面（stage）の絵。名前で引く */
  SCENES.forEach(function (sc) { if ((sc.s.type === "image" || sc.s.type === "layout") && sc.s.src && !IMGS[sc.s.src]) { var im = new Image(); im.onload = function () { needsDraw = true; }; im.src = sc.s.src; IMGS[sc.s.src] = im; } });
  /* 画面の解説の部品（tour・scrollshot・swipe）の画像 */
  SCENES.forEach(function (sc) { if (IMG_TYPES[sc.s.type]) IMG_TYPES[sc.s.type].forEach(function (k) { if (typeof sc.s[k] === "string") preload(sc.s[k]); }); });
  try { collectEvents(); buildSfxQueue(); } catch (e) { console.warn("sfx:", e); }
  new ResizeObserver(resize).observe(cv); resize(); syncUI(); requestAnimationFrame(frame);
  uiReady = true; applyStoredVoiceRate();
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(function () { needsDraw = true; });
  /* 使う書体・太さを先に読み込む（初めて使う組み合わせを仮の書体で測って、最初の 1 コマだけ幅がずれるのを防ぐ） */
  if (document.fonts && document.fonts.load) { var fl = []; [F.sans, F.display, F.mono].forEach(function (fam) { [400, 600, 700, 800, 900].forEach(function (w) { fl.push(document.fonts.load(w + " 30px " + fam, "あA1")); }); });
    Promise.all(fl).then(function () { CHARPOS.clear(); needsDraw = true; }, function () {}); }
  if (KIOSK && !(window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches)) { started = true; playing = true; lastNow = performance.now(); syncUI(); }
  /* 同じページのほかのプレイヤーを再生したら、こちらは止める（読み上げの声は 1 つしか無いため） */
  document.addEventListener("mv-exclusive", function (e) { if (e.detail !== root && playing && !SPEC.figure) pause(); });
  var api = { renderMusic: function () { return renderStem(fillMusic).then(function (b) { var d = b.getChannelData(0), out = [], n = Math.floor(b.sampleRate / 10);   /* 音楽の音量を 0.1 秒ごとに（確かめる用） */
      for (var i = 0; i + n <= d.length; i += n) { var s2 = 0; for (var j = i; j < i + n; j += 8) s2 += d[j] * d[j]; out.push(Math.round(Math.sqrt(s2 / (n / 8)) * 1000) / 1000); } return out; }); },
    segments: function () { return msegs().map(function (m) { return { t: m.t, end: m.end, key: m.key, cont: m.cont }; }); }, seek: seek, play: play, pause: pause, get t() { return t; }, get speaking() { return !!speaking; }, get DUR() { return DUR; }, CHAPTERS: CHAPTERS,
              get voiceRate() { return VK; }, retime: retime, CUES: CUES, SFX: SFXQ,
              /* 効果音 1 つを音だけ書き出して、大きさを測る（peak: 最大の振れ、rms: いちばん大きい 0.3 秒の実効値）。音量をそろえるための道具（build.py --sfx-levels） */
              sfxLevel: function (name, o) { ensureAudio(); var sr = 44100, oc = new (window.OfflineAudioContext || window.webkitOfflineAudioContext)(1, sr * 3, sr), g = oc.createGain(); g.connect(oc.destination);
                var wait = SFXD[name] && SFXD[name].file ? new Promise(function (ok) { var n = 0; (function w() { if (SFXBUF[name] || n++ > 50) ok(); else setTimeout(w, 100); })(); }) : Promise.resolve();
                return wait.then(function () { sfxPlay(name, .05, Object.assign({ raw: true }, o || {}), oc, g); return oc.startRendering(); }).then(function (buf) {
                  var d = buf.getChannelData(0), pk = 0, win = Math.round(sr * .3), acc = 0, best = 0, i;
                  for (i = 0; i < d.length; i++) { var v = d[i] * d[i]; if (Math.abs(d[i]) > pk) pk = Math.abs(d[i]); acc += v; if (i >= win) acc -= d[i - win] * d[i - win]; if (acc > best) best = acc; }
                  return { peak: pk, rms: Math.sqrt(best / win) }; }); },
              sfxNames: function () { return Object.keys(SFXD); },
              textWidth: function (text, size) { return tw(text, { size: size || 50, weight: 800 }); },
              capFit: function (text, maxW, size) { var f = capFit(text, maxW, size || 50); return { lines: f.lines.slice(), size: f.o.size }; },
              endFade: +SPEC.endFade || 0,
              capWrap: function (text, maxW, size, lim) { return capWrap(text, maxW, { size: size || 56, weight: 800, font: F.sans }, lim); },   /* 字幕の折り返し（確かめる用） */
              get audio() { return { ctx: ac, mt: mclock.mt, section: mclock.sec, notes: mclock.count || 0, sfx: sfxCount, vol: VOL, gain: master ? master.gain.value : null }; } };
  root.__mv = api; window.__MV__ = api;
  return api;
};
/* ページの中のプレイヤーを起動する（台本と配色はプレイヤーの中の JSON から読む。同じ HTML を 2 度読み込んでも 1 度だけ） */
(function () {
  function boot() {
    [].forEach.call(document.querySelectorAll(".mv-player:not([data-mv-ready])"), function (el) {
      var sp = el.querySelector("script[data-mv-spec]"), th = el.querySelector("script[data-mv-theme]");
      if (!sp || !th) return;
      el.setAttribute("data-mv-ready", "");
      try { window.MotionVideo(el, JSON.parse(sp.textContent), JSON.parse(th.textContent)); } catch (e) { console.error("motion-video:", e); }
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot); else boot();
})();
