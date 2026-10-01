/* motion-video audio — 音楽と効果音を Web Audio で合成する（音声ファイルが無くても鳴る）。
 * 曲は「時刻 → 音符」の純粋な関数（notes）で決まる。同じ台本・同じ時刻からは同じ音符が出るので、シークしても同じ所が鳴る。
 * 楽器も効果音も「層（l）」の並びで書く。層は 1 つの発振器（か雑音）に、音量の包絡・フィルタ・周波数の動きを付けたもの。
 *   w 波形（sine square sawtooth triangle pulse noise）  f 周波数 Hz（[始め, 終わり] で動く。無ければ音符の高さ × fr）
 *   a 立ち上がり s  h 保つ s（sus:1 なら音符の長さだけ保つ）  d 減衰 s  v 音量  at 遅らせる s
 *   flt [種類, Hz か [始め, 終わり], Q, 動く時間]（fk:1 なら Hz は音符の高さの倍率）  dt ずらし cent  pe [始めの倍率, 戻る時間]
 *   vib [速さ Hz, 深さ cent, 遅れ s]  fm [倍率, 深さ, 減る時間]  sh 歪み  pan -1..1  nr 雑音の速さ  pw pulse の幅
 *   rep 回数 gap 間隔 s  notes 半音の並び（rep の代わり）  rf 回ごとの周波数の倍率  rv 回ごとの音量の倍率  rj 間隔の揺れ s  vj 音量の揺れ */
window.MotionAudio = window.MotionAudio || (function () {
  "use strict";
  var KEYS = { C: 0, "C#": 1, Db: 1, D: 2, "D#": 3, Eb: 3, E: 4, F: 5, "F#": 6, Gb: 6, G: 7, "G#": 8, Ab: 8, A: 9, "A#": 10, Bb: 10, B: 11 };
  var SCALES = {
    major: [0, 2, 4, 5, 7, 9, 11], minor: [0, 2, 3, 5, 7, 8, 10], dorian: [0, 2, 3, 5, 7, 9, 10], phrygian: [0, 1, 3, 5, 7, 8, 10],
    lydian: [0, 2, 4, 6, 7, 9, 11], mixolydian: [0, 2, 4, 5, 7, 9, 10], harmonic: [0, 2, 3, 5, 7, 8, 11],
    pentamaj: [0, 2, 4, 7, 9], pentamin: [0, 3, 5, 7, 10], blues: [0, 3, 5, 6, 7, 10],
    yo: [0, 2, 5, 7, 9], in: [0, 1, 5, 7, 8], ryukyu: [0, 4, 5, 7, 11], hirajoshi: [0, 2, 3, 7, 8], whole: [0, 2, 4, 6, 8, 10],
    hijaz: [0, 1, 4, 5, 7, 8, 10], bhairav: [0, 1, 4, 5, 7, 8, 11], melodic: [0, 2, 3, 5, 7, 9, 11], dim: [0, 2, 3, 5, 6, 8, 9, 11], iwato: [0, 1, 5, 6, 10]
  };
  function hz(m) { return 440 * Math.pow(2, (m - 69) / 12); }
  function rng(seed) { var a = (seed >>> 0) || 1; return function () { a |= 0; a = a + 0x6D2B79F5 | 0; var t = Math.imul(a ^ a >>> 15, 1 | a);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
  function hash() { var h = 2166136261; for (var i = 0; i < arguments.length; i++) { var s = String(arguments[i]);
    for (var j = 0; j < s.length; j++) { h ^= s.charCodeAt(j); h = Math.imul(h, 16777619); } h ^= 124; h = Math.imul(h, 16777619); } return h >>> 0; }

  /* ================= 楽器（音符を鳴らす音色） ================= */
  var INST = {
    pad: { l: [{ w: "sawtooth", dt: -9, sus: 1, a: .7, d: 1.3, v: .05, flt: ["lowpass", 1100, .4] }, { w: "sawtooth", dt: 9, sus: 1, a: .7, d: 1.3, v: .05, flt: ["lowpass", 1100, .4] },
      { w: "triangle", fr: .5, sus: 1, a: .7, d: 1.3, v: .07 }] },
    warm: { l: [{ w: "triangle", dt: -6, sus: 1, a: .45, d: 1.1, v: .11 }, { w: "triangle", dt: 6, sus: 1, a: .45, d: 1.1, v: .11 }, { w: "sine", fr: 2, sus: 1, a: .9, d: 1, v: .025 }] },
    glass: { l: [{ w: "sine", sus: 1, a: .9, d: 1.6, v: .09 }, { w: "sine", fr: 2.002, sus: 1, a: 1.2, d: 1.4, v: .035 }, { w: "sine", fr: 3, sus: 1, a: 1.5, d: 1, v: .012 }] },
    strings: { l: [{ w: "sawtooth", dt: -11, sus: 1, a: .35, d: .7, v: .045, flt: ["lowpass", 2300, .5], vib: [5, 7, .35] }, { w: "sawtooth", dt: 11, sus: 1, a: .4, d: .7, v: .045, flt: ["lowpass", 2300, .5], vib: [5.3, 7, .35] },
      { w: "triangle", sus: 1, a: .35, d: .7, v: .05 }] },
    choir: { l: [{ w: "sawtooth", sus: 1, a: .55, d: .9, v: .06, flt: ["bandpass", 780, 3.5] }, { w: "sawtooth", dt: 8, sus: 1, a: .6, d: .9, v: .05, flt: ["bandpass", 1150, 4] },
      { w: "sine", sus: 1, a: .5, d: .9, v: .06, vib: [4.6, 10, .4] }] },
    organ: { l: [{ w: "sine", sus: 1, a: .012, d: .08, v: .09 }, { w: "sine", fr: 2, sus: 1, a: .012, d: .08, v: .055 }, { w: "sine", fr: 3, sus: 1, a: .012, d: .08, v: .03 }, { w: "sine", fr: 4, sus: 1, a: .012, d: .06, v: .018 }] },
    keys: { l: [{ w: "triangle", a: .004, d: 1.7, v: .2, flt: ["lowpass", [3200, 900], .5, 1] }, { w: "sine", fr: 2, a: .004, d: .6, v: .05 }, { w: "sine", fr: 4, a: .002, d: .12, v: .02 }] },
    epiano: { l: [{ w: "sine", a: .004, d: 1.9, v: .2, fm: [1, 1.1, .5] }, { w: "sine", fr: 4.01, a: .002, d: .25, v: .025 }] },
    pluck: { l: [{ w: "sawtooth", a: .003, d: .5, v: .12, fk: 1, flt: ["lowpass", [8, 1.3], 1, .3] }] },
    harp: { l: [{ w: "triangle", a: .003, d: 1.5, v: .19 }, { w: "sine", fr: 2, a: .003, d: .5, v: .045 }] },
    marimba: { l: [{ w: "sine", a: .002, d: .45, v: .26 }, { w: "sine", fr: 4, a: .001, d: .07, v: .07 }, { w: "sine", fr: 10, a: .001, d: .02, v: .02 }] },
    bell: { l: [{ w: "sine", a: .002, d: 2.2, v: .12 }, { w: "sine", fr: 2.76, a: .002, d: 1.2, v: .05 }, { w: "sine", fr: 5.4, a: .001, d: .6, v: .025 }, { w: "sine", fr: 8.93, a: .001, d: .25, v: .012 }] },
    kalimba: { l: [{ w: "sine", a: .002, d: .85, v: .24 }, { w: "sine", fr: 5.95, a: .001, d: .12, v: .05 }] },
    koto: { l: [{ w: "sawtooth", a: .002, d: 1.2, v: .12, pe: [1.03, .07], fk: 1, flt: ["lowpass", [6, 2], 2, .45] }, { w: "triangle", fr: 2, a: .002, d: .3, v: .035 }] },
    shaku: { l: [{ w: "sine", sus: 1, a: .18, d: .4, v: .19, vib: [5, 18, .35] }, { w: "noise", sus: 1, a: .1, d: .3, v: .05, fk: 1, flt: ["bandpass", 1, 6] }] },
    flute: { l: [{ w: "sine", sus: 1, a: .06, d: .2, v: .19, vib: [5.5, 12, .25] }, { w: "triangle", fr: 2, sus: 1, a: .06, d: .2, v: .02 }] },
    whistle: { l: [{ w: "sine", fr: 2, sus: 1, a: .03, d: .1, v: .1, vib: [6, 20, .1] }] },
    lead: { l: [{ w: "square", sus: 1, a: .01, d: .15, v: .05, flt: ["lowpass", 2600, 1], vib: [5.5, 10, .2] }, { w: "sawtooth", dt: 6, sus: 1, a: .01, d: .15, v: .035, flt: ["lowpass", 2600, 1] }] },
    saw: { l: [{ w: "sawtooth", sus: 1, a: .005, d: .12, v: .07, flt: ["lowpass", [5000, 1800], 1, .3] }] },
    brass: { l: [{ w: "sawtooth", sus: 1, a: .06, d: .18, v: .08, flt: ["lowpass", [500, 2600], 1.2, .12] }, { w: "sawtooth", dt: 7, sus: 1, a: .07, d: .18, v: .055, flt: ["lowpass", [500, 2200], 1, .14] }] },
    chip: { l: [{ w: "pulse", pw: .25, sus: 1, a: .001, d: .04, v: .055 }] },
    chipsq: { l: [{ w: "square", sus: 1, a: .001, d: .04, v: .05 }] },
    chiptri: { l: [{ w: "triangle", sus: 1, a: .001, d: .03, v: .22 }] },
    pizz: { l: [{ w: "triangle", a: .002, d: .25, v: .24, flt: ["lowpass", 1800, .7] }] },
    clav: { l: [{ w: "pulse", pw: .2, a: .002, d: .2, v: .09, fk: 1, flt: ["bandpass", [3, 1.5], 2, .1] }] },
    harpsi: { l: [{ w: "sawtooth", a: .002, d: .6, v: .07, flt: ["highpass", 400, .7] }, { w: "pulse", pw: .1, a: .002, d: .3, v: .035 }] },
    power: { l: [{ w: "sawtooth", sus: 1, a: .005, d: .15, v: .06, sh: 6, flt: ["lowpass", 3200, .7] }, { w: "sawtooth", fr: 1.4983, sus: 1, a: .005, d: .15, v: .045, sh: 6, flt: ["lowpass", 3200, .7] }] },
    bass: { l: [{ w: "sawtooth", sus: 1, a: .005, d: .12, v: .12, flt: ["lowpass", [900, 380], 1.5, .2] }, { w: "sine", sus: 1, a: .005, d: .12, v: .2 }] },
    sub: { l: [{ w: "sine", sus: 1, a: .02, d: .2, v: .3 }] },
    fmbass: { l: [{ w: "sine", sus: 1, a: .003, d: .1, v: .28, fm: [1, 2.5, .15] }] },
    synthbass: { l: [{ w: "square", sus: 1, a: .003, d: .08, v: .07, flt: ["lowpass", [1400, 300], 2, .15] }, { w: "sine", sus: 1, a: .003, d: .08, v: .18 }] },
    acid: { l: [{ w: "sawtooth", sus: 1, a: .003, d: .08, v: .09, flt: ["lowpass", [2600, 250], 12, .18] }] },
    upright: { l: [{ w: "triangle", a: .004, d: .5, v: .3, flt: ["lowpass", 900, .8] }, { w: "sine", a: .004, d: .4, v: .15 }] },
    /* レコードの雑音: 続く「サー」（白い雑音に聞こえる）ではなく、まばらな「プツッ」という短い粒にする */
    crackle: { l: [{ w: "noise", a: .0005, d: .005, v: .07, flt: ["bandpass", 2600, 1.4], rep: 6, gap: .32, rj: .26, vj: .85 }] },
    steel: { l: [{ w: "sine", a: .003, d: .9, v: .2, pe: [1.01, .03] }, { w: "sine", fr: 2, a: .003, d: .35, v: .08 }, { w: "sine", fr: 3.01, a: .002, d: .15, v: .035 }, { w: "triangle", fr: 4, a: .002, d: .06, v: .025 }] },
    sitar: { l: [{ w: "sawtooth", a: .003, d: 1.4, v: .08, pe: [.97, .08], fk: 1, flt: ["bandpass", [4, 2], 3, .5] }, { w: "sawtooth", fr: 1.003, a: .003, d: 1.1, v: .035, flt: ["highpass", 1500, 4] },
      { w: "sine", fr: 2, a: .25, d: 1.4, v: .02 }] },
    shamisen: { l: [{ w: "sawtooth", a: .001, d: .35, v: .12, fk: 1, flt: ["lowpass", [10, 3], 3, .15] }, { w: "noise", a: .001, d: .02, v: .12, flt: ["bandpass", 2500, 2] }, { w: "square", fr: 2, a: .001, d: .06, v: .02 }] },
    uke: { l: [{ w: "triangle", a: .002, d: .6, v: .18, fk: 1, flt: ["lowpass", [6, 2], 1, .2] }, { w: "sawtooth", a: .002, d: .2, v: .03, fk: 1, flt: ["lowpass", [8, 3], 1, .1] }] },
    banjo: { l: [{ w: "sawtooth", a: .001, d: .4, v: .1, fk: 1, flt: ["bandpass", [6, 3], 2, .2] }, { w: "square", fr: 2, a: .001, d: .12, v: .025 }, { w: "noise", a: .001, d: .01, v: .06, flt: ["highpass", 3000] }] },
    accordion: { l: [{ w: "sawtooth", dt: -8, sus: 1, a: .04, d: .12, v: .035, flt: ["lowpass", 2600, .8], vib: [5.5, 4, .2] }, { w: "sawtooth", dt: 8, sus: 1, a: .04, d: .12, v: .035, flt: ["lowpass", 2600, .8] },
      { w: "square", fr: .5, sus: 1, a: .04, d: .12, v: .02, flt: ["lowpass", 1500, .7] }] },
    bandoneon: { l: [{ w: "sawtooth", dt: -5, sus: 1, a: .06, d: .1, v: .04, flt: ["lowpass", 1800, 1.2] }, { w: "sawtooth", dt: 5, sus: 1, a: .06, d: .1, v: .04, flt: ["lowpass", 1800, 1.2] },
      { w: "square", fr: 2, sus: 1, a: .06, d: .1, v: .012, flt: ["lowpass", 2600, .7] }] },
    harmonica: { l: [{ w: "square", sus: 1, a: .05, d: .1, v: .04, fk: 1, flt: ["lowpass", 4, 1.5], vib: [6, 20, .3] }, { w: "sawtooth", dt: 12, sus: 1, a: .05, d: .1, v: .02, flt: ["lowpass", 2500, 1] }] },
    oohs: { l: [{ w: "sawtooth", sus: 1, a: .4, d: .8, v: .06, flt: ["bandpass", 330, 5], vib: [5, 8, .4] }, { w: "sawtooth", dt: -7, sus: 1, a: .45, d: .8, v: .04, flt: ["bandpass", 800, 6] },
      { w: "sine", sus: 1, a: .4, d: .8, v: .06 }] },
    sho: { l: [{ w: "sine", sus: 1, a: 1.2, d: 1.5, v: .07, vib: [4, 4, .8] }, { w: "sine", fr: 1.5, sus: 1, a: 1.2, d: 1.5, v: .05 }, { w: "sine", fr: 2, sus: 1, a: 1.3, d: 1.5, v: .04 },
      { w: "triangle", fr: 2.25, sus: 1, a: 1.4, d: 1.5, v: .025 }, { w: "sine", fr: 3, sus: 1, a: 1.5, d: 1.5, v: .02 }] },
    vibes: { l: [{ w: "sine", a: .003, d: 2, v: .13, dt: -4 }, { w: "sine", a: .003, d: 2, v: .1, dt: 5 }, { w: "sine", fr: 4, a: .002, d: .3, v: .03 }] },
    glock: { l: [{ w: "sine", a: .001, d: .9, v: .16 }, { w: "sine", fr: 3.9, a: .001, d: .25, v: .05 }, { w: "triangle", a: .001, d: .05, v: .05 }] },
    musicbox: { l: [{ w: "sine", a: .001, d: 1, v: .15 }, { w: "sine", fr: 4, a: .001, d: .3, v: .05 }, { w: "sine", fr: 6.1, a: .001, d: .12, v: .02 }] },
    tubular: { l: [{ w: "sine", a: .003, d: 3.5, v: .1 }, { w: "sine", fr: 2.02, a: .003, d: 2.5, v: .06 }, { w: "sine", fr: 3.03, a: .003, d: 1.5, v: .04 }, { w: "sine", fr: 4.97, a: .002, d: .8, v: .025 }] },
    supersaw: { l: [{ w: "sawtooth", dt: -18, sus: 1, a: .01, d: .2, v: .035, flt: ["lowpass", 3500, .7] }, { w: "sawtooth", sus: 1, a: .01, d: .2, v: .035, flt: ["lowpass", 3500, .7] },
      { w: "sawtooth", dt: 18, sus: 1, a: .01, d: .2, v: .035, flt: ["lowpass", 3500, .7] }] },
    slap: { l: [{ w: "sawtooth", a: .002, d: .25, v: .12, fk: 1, flt: ["lowpass", [12, 2], 4, .12] }, { w: "sine", a: .002, d: .3, v: .2 }, { w: "noise", a: .001, d: .015, v: .1, flt: ["bandpass", 2000, 2] }] },
    sub808: { l: [{ w: "sine", sus: 1, a: .003, d: .6, v: .33, pe: [1.5, .05], sh: 1.5 }] },
    /* 打楽器（高さを持たない。f が決まっている） */
    kick: { l: [{ w: "sine", f: [150, 44], ft: .11, a: .002, d: .42, v: .8 }, { w: "noise", a: .001, d: .018, v: .14, flt: ["lowpass", 1500] }] },
    snare: { l: [{ w: "noise", a: .001, d: .17, v: .3, flt: ["highpass", 1400, .7] }, { w: "triangle", f: [210, 160], ft: .05, a: .001, d: .09, v: .28 }] },
    clap: { l: [{ w: "noise", a: .001, d: .02, v: .32, flt: ["bandpass", 1150, 1.3], rep: 3, gap: .011 }, { w: "noise", at: .03, a: .001, d: .16, v: .26, flt: ["bandpass", 1150, 1.3] }] },
    hat: { l: [{ w: "noise", a: .001, d: .04, v: .13, flt: ["highpass", 7500, .7] }] },
    ohat: { l: [{ w: "noise", a: .002, d: .28, v: .09, flt: ["highpass", 6800, .7] }] },
    ride: { l: [{ w: "noise", a: .002, d: .6, v: .05, flt: ["bandpass", 6000, 2] }, { w: "sine", f: 5400, a: .001, d: .35, v: .01 }] },
    rim: { l: [{ w: "square", f: 1750, a: .001, d: .02, v: .07, flt: ["bandpass", 1800, 4] }, { w: "noise", a: .001, d: .012, v: .09, flt: ["highpass", 2000] }] },
    tom: { l: [{ w: "sine", f: [190, 95], ft: .2, a: .002, d: .35, v: .5 }] },
    taiko: { l: [{ w: "sine", f: [105, 58], ft: .25, a: .003, d: .8, v: .8 }, { w: "noise", a: .002, d: .12, v: .2, flt: ["lowpass", 500] }] },
    shaker: { l: [{ w: "noise", a: .012, d: .05, v: .07, flt: ["bandpass", 5500, 1.2] }] },
    crash: { l: [{ w: "noise", a: .002, d: 1.6, v: .12, flt: ["highpass", 4200, .5] }] },
    tick: { l: [{ w: "noise", a: .001, d: .012, v: .2, flt: ["bandpass", 4200, 8] }] },
    brush: { l: [{ w: "noise", a: .03, d: .12, v: .08, flt: ["bandpass", 3500, .8] }] },
    timpani: { l: [{ w: "sine", f: [98, 90], ft: .4, a: .003, d: 1.2, v: .55 }, { w: "noise", a: .001, d: .06, v: .12, flt: ["lowpass", 800] }] },
    chipnoise: { l: [{ w: "noise", nr: .25, a: .001, d: .06, v: .11 }] },
    chipkick: { l: [{ w: "square", f: [220, 40], ft: .08, a: .001, d: .09, v: .1 }] },
    conga: { l: [{ w: "sine", f: [330, 290], ft: .08, a: .001, d: .28, v: .45 }, { w: "noise", a: .001, d: .02, v: .1, flt: ["bandpass", 1500, 2] }] },
    bongo: { l: [{ w: "sine", f: [520, 470], ft: .05, a: .001, d: .14, v: .4 }, { w: "noise", a: .001, d: .012, v: .1, flt: ["bandpass", 2500, 2] }] },
    tabla: { l: [{ w: "sine", f: [420, 400], ft: .1, a: .001, d: .35, v: .3 }, { w: "sine", f: [95, 140], ft: .15, a: .001, d: .3, v: .35 }, { w: "noise", a: .001, d: .01, v: .1, flt: ["highpass", 3000] }] },
    cowbell: { l: [{ w: "square", f: 587, a: .001, d: .25, v: .05, flt: ["bandpass", 800, 3] }, { w: "square", f: 845, a: .001, d: .25, v: .04, flt: ["bandpass", 900, 3] }] },
    tamb: { l: [{ w: "noise", a: .002, d: .12, v: .1, flt: ["highpass", 7000, .7] }, { w: "noise", a: .002, d: .15, v: .06, flt: ["bandpass", 9500, 3] }] },
    kick808: { l: [{ w: "sine", f: [120, 45], ft: .25, a: .002, d: .9, v: .8, sh: 1.2 }] },
    gated: { l: [{ w: "noise", a: .001, h: .12, d: .03, v: .3, flt: ["highpass", 900, .6] }, { w: "triangle", f: [200, 150], ft: .05, a: .001, d: .1, v: .3 }, { w: "noise", a: .001, h: .15, d: .02, v: .1, flt: ["lowpass", 3000] }] },
    kane: { l: [{ w: "square", f: 1900, a: .001, d: .12, v: .04, flt: ["bandpass", 2200, 3] }, { w: "sine", f: 3150, a: .001, d: .18, v: .08 }, { w: "noise", a: .001, d: .03, v: .1, flt: ["highpass", 5000] }] },
    block: { l: [{ w: "sine", f: 1200, a: .001, d: .05, v: .45 }, { w: "sine", f: 2750, a: .001, d: .02, v: .1 }] }
  };

  /* ================= 打楽器の型（1 小節。x=打つ X=強く g=弱く r=刻みの中で 2 連打 t=3 連打。文字の数が 1 小節の刻み） ================= */
  var DRUMS = {
    pulse: { kick: "x...............", hat: "..g...g...g...g." },
    soft: { kick: "x.......x.......", rim: "....g.......g...", shaker: "g.g.g.g.g.g.g.g." },
    four: { kick: "X...x...X...x...", clap: "....x.......x...", hat: "..x...x...x...x." },
    house: { kick: "X...x...X...x...", clap: "....x.......x...", ohat: "..x...x...x...x.", hat: "g.g.g.g.g.g.g.g." },
    backbeat: { kick: "X.....x.x.......", snare: "....X.......X...", hat: "x.g.x.g.x.g.x.g." },
    rock: { kick: "X.x...x.X.x.....", snare: "....X.......X...", hat: "x.x.x.x.x.x.x.x." },
    halftime: { kick: "X.........x.....", snare: "........X.......", hat: "x.g.x.g.x.g.x.g." },
    lofi: { kick: "X......x..x.....", snare: "....x.......x...", hat: "x.g.x.gxx.g.x.g." },
    breaks: { kick: "X.........x.x...", snare: "....X..g.g..X..g", hat: "x.x.x.x.x.x.x.x." },
    dnb: { kick: "X.........X.....", snare: "....X.......X...", hat: "xgxgxgxgxgxgxgxg" },
    trap: { kick: "X......x..x.....", snare: "........X.......", hat: "x.x.x.xxx.x.xxxx" },
    funk: { kick: "X..x..x...x.x...", snare: "....X..g.g..X..g", hat: "xgxgxgxgxgxgxgxg" },
    bossa: { kick: "X..x..x.X..x..x.", rim: "x..x..x...x..x..", shaker: "g.x.g.x.g.x.g.x." },
    brush: { ride: "x...x..xx...x..x", brush: "....x.......x...", kick: "x.......x......." },
    reggae: { kick: "........X.......", rim: "....x.......x...", hat: "x.x.x.x.x.x.x.x." },
    march: { snare: "x.gxx.gxx.gxx.xx", kick: "X.......X......." },
    taiko: { taiko: "X.......x...x...", tom: "......x.......xx", rim: "x...x...x...x..." },
    matsuri: { taiko: "X..x..x.X..x..x.", rim: "x.xxx.xxx.xxx.xx", shaker: "g.g.g.g.g.g.g.g." },
    cinematic: { taiko: "X.......X.......", timpani: "............x.x.", tom: "......x......x.." },
    tick: { tick: "x.x.x.x.x.x.x.x.", kick: "x.......x......." },
    clock: { tick: "x...x...x...x...", rim: "..g...g...g...g." },
    heart: { kick: "X..x............" },
    shaker: { shaker: "xgxgxgxgxgxgxgxg", kick: "X.......x......." },
    ostinato: { tom: "x.x.x.x.x.x.x.x.", kick: "X.......X......." },
    chip: { chipkick: "X.......X.......", chipnoise: "....x.......x...", hat: "x.x.x.x.x.x.x.x." },
    waltz: { kick: "X...........", rim: "....x...x...", hat: "..g...g...g." },
    sixeight: { kick: "X.....x.....", snare: "......X.....", hat: "x.gx.gx.gx.g" },
    boombap: { kick: "X......x.xX.....", snare: "....X.......X...", hat: "x.x.x.x.x.x.x.x." },
    trap2: { kick808: "X......x..x.....", clap: "........X.......", hat: "x.x.xrx.x.x.rttr" },
    futurebass: { kick808: "X.........x.....", clap: "........X.......", hat: "x.x.x.x.x.x.x.rr" },
    reggaeton: { kick: "X...X...X...X...", snare: "...x..x....x..x.", hat: "x.x.x.x.x.x.x.x." },
    samba: { kick: "X..xX..xX..xX..x", tamb: "xgxxxgxxxgxxxgxx", rim: "x..x..x...x..x..", tom: "......x.......x." },
    tango: { kick: "X...x...x...x.x.", rim: "....g.......g..." },
    swing: { ride: "x...x.x.x...x.x.", hat: "....x.......x...", kick: "g.......g......." },
    shuffle: { kick: "X.....x.X.....x.", snare: "....X.......X...", hat: "x.x.x.x.x.x.x.x." },
    polka: { kick: "X.......X.......", snare: "....x.......x...", hat: "..g...g...g...g." },
    techno: { kick: "X...X...X...X...", ohat: "..x...x...x...x.", hat: "gggggggggggggggg", rim: "...g..g....g.g.." },
    garage: { kick: "X.....x...x..x..", snare: "....X.......X...", hat: "..x.gx.x..x.gx.x", shaker: "g.g.g.g.g.g.g.g." },
    eighties: { kick: "X.......X.x.....", gated: "....X.......X...", hat: "x.x.x.x.x.x.x.x." },
    salsa: { cowbell: "x.x.x.x.x.x.x.x.", conga: "..x..xx...x..xx.", rim: "x..x...x..x.x...", kick: "......x.......x." },
    tabla: { tabla: "X..x..x.x.x..x..", kick: "g.......g.x....." },
    ballad: { kick: "X.......x.......", rim: "....x.......x...", hat: "g.g.g.g.g.g.g.g." },
    bon: { taiko: "X...X.x.X...X.x.", kane: "..x...x...x...x.", block: "x.......x......." },
    maqsum: { kick: "X.....x.x.......", bongo: "..x.x.....x.x...", tamb: "gxgxgxgxgxgxgxgx" },
    train: { snare: "gggXgggXgggXgggX", kick: "X...x...X...x..." },
    palmas: { clap: "X..x..x...x.x...", kick: "x.......x......." },
    ska: { kick: "X...x...X...x...", snare: "....X.......X...", hat: "..x...x...x...x." }
  };

  /* ================= 音を鳴らす（楽器も効果音も同じ仕組み） ================= */
  function noiseBuf(ac) {
    if (ac.__mvNoise) return ac.__mvNoise;
    var n = Math.floor(ac.sampleRate * 2), b = ac.createBuffer(1, n, ac.sampleRate), d = b.getChannelData(0), r = rng(12345);
    for (var i = 0; i < n; i++) d[i] = r() * 2 - 1;
    return (ac.__mvNoise = b);
  }
  function pulseWave(ac, pw) {
    var key = "__mvPulse" + pw; if (ac[key]) return ac[key];
    var N = 48, re = new Float32Array(N), im = new Float32Array(N);
    for (var k = 1; k < N; k++) re[k] = 2 / (k * Math.PI) * Math.sin(k * Math.PI * pw);
    return (ac[key] = ac.createPeriodicWave(re, im));
  }
  var CURVES = {};
  function curve(k) { if (CURVES[k]) return CURVES[k]; var n = 1024, c = new Float32Array(n);
    for (var i = 0; i < n; i++) { var x = i * 2 / n - 1; c[i] = Math.tanh(k * x) / Math.tanh(k); } return (CURVES[k] = c); }
  function fc(f) { return Math.max(20, Math.min(19000, f)); }

  function voice(ac, out, L, t0, mul, vol, nf, dur, fast) {
    var a = L.a === undefined ? .004 : L.a, h = L.sus ? Math.max(0, (dur || 0) - a) : (L.h || 0), d = L.d === undefined ? .2 : L.d;
    if (fast) a = Math.min(a, .03);
    var te = t0 + a + h + d, v = Math.max(.00011, vol);
    var g = ac.createGain();
    g.gain.setValueAtTime(.0001, t0); g.gain.linearRampToValueAtTime(v, t0 + a);
    if (h > 0) g.gain.setValueAtTime(v, t0 + a + h);
    if (L.lin) g.gain.linearRampToValueAtTime(0, te); else g.gain.exponentialRampToValueAtTime(.0001, te);
    var head = g, base = L.f !== undefined ? [].concat(L.f) : [(nf || 440) * (L.fr || 1)];
    var f0 = base[0] * mul, f1 = base.length > 1 ? base[1] * mul : 0;
    if (L.flt) {
      var bq = ac.createBiquadFilter(); bq.type = L.flt[0]; var ff = [].concat(L.flt[1] || 1000), k = L.fk ? (nf || 440) * (L.f !== undefined ? 1 : (L.fr || 1)) * mul : 1;
      bq.frequency.setValueAtTime(fc(ff[0] * k), t0);
      if (ff.length > 1) bq.frequency.exponentialRampToValueAtTime(fc(ff[1] * k), t0 + (L.flt[3] || a + h + d));
      bq.Q.value = L.flt[2] === undefined ? 1 : L.flt[2]; bq.connect(head); head = bq;
    }
    if (L.sh) { var ws = ac.createWaveShaper(); ws.curve = curve(L.sh); ws.connect(head); head = ws; }
    if (L.pan && ac.createStereoPanner) { var p = ac.createStereoPanner(); p.pan.value = L.pan; g.connect(p); p.connect(out); } else g.connect(out);
    var src;
    if (L.w === "noise") {
      src = ac.createBufferSource(); src.buffer = noiseBuf(ac); src.loop = true; src.playbackRate.value = (L.nr || 1) * (L.f !== undefined ? 1 : 1);
      src.start(t0, (hash(t0.toFixed(3), L.d) % 1000) / 1000);
    } else {
      src = ac.createOscillator();
      if (L.w === "pulse") src.setPeriodicWave(pulseWave(ac, L.pw || .25)); else src.type = L.w || "sine";
      if (L.pe) { src.frequency.setValueAtTime(fc(f0 * L.pe[0]), t0); src.frequency.exponentialRampToValueAtTime(fc(f0), t0 + L.pe[1]); }
      else src.frequency.setValueAtTime(fc(f0), t0);
      if (f1) { var ft = t0 + (L.ft || a + h + d); if (L.fe === "lin") src.frequency.linearRampToValueAtTime(fc(f1), ft); else src.frequency.exponentialRampToValueAtTime(fc(f1), ft); }
      if (L.dt) src.detune.value = L.dt;
      if (L.vib) { var lfo = ac.createOscillator(), lg = ac.createGain(); lfo.frequency.value = L.vib[0]; lg.gain.setValueAtTime(0, t0);
        lg.gain.linearRampToValueAtTime(L.vib[1], t0 + (L.vib[2] || .01)); lfo.connect(lg); lg.connect(src.detune); lfo.start(t0); lfo.stop(te + .05); }
      if (L.fm) { var mo = ac.createOscillator(), mg = ac.createGain(); mo.frequency.value = f0 * L.fm[0]; mg.gain.setValueAtTime(f0 * L.fm[1], t0);
        mg.gain.exponentialRampToValueAtTime(Math.max(1, f0 * L.fm[1] * .08), t0 + (L.fm[2] || .3)); mo.connect(mg); mg.connect(src.frequency); mo.start(t0); mo.stop(te + .05); }
      src.start(t0);
    }
    src.connect(head); src.stop(te + .05);
    return te;
  }
  /* 音色（層の並び）を when（ac の時刻）に鳴らす。o: {f 音符の高さ Hz, dur 音符の長さ s, v 音量, pitch 半音, rep, gap, seed, fast} */
  function play(ac, out, R, when, o) {
    o = o || {}; if (!R || !R.l) return when;
    var pm = Math.pow(2, (o.pitch || 0) / 12), vol = (o.v === undefined ? 1 : o.v) * (R.g || 1), jr = rng(o.seed || 7), end = when;
    R.l.forEach(function (L) {
      var single = !L.notes && (L.rep || 1) === 1, n = L.notes ? L.notes.length : single && o.rep ? o.rep : (L.rep || 1);
      var gap = single && o.rep ? (o.gap || .06) : (L.gap || .08), rj = L.rj || (single && o.rep ? .006 : 0), vj = L.vj || (single && o.rep ? .35 : 0);
      for (var i = 0; i < n; i++) {
        var t0 = when + (L.at || 0) + i * gap + rj * jr(), mul = pm * (L.notes ? Math.pow(2, L.notes[i] / 12) : Math.pow(L.rf || 1, i));
        var vv = vol * (L.v === undefined ? .5 : L.v) * Math.pow(L.rv || 1, i) * (1 - vj * jr());
        end = Math.max(end, voice(ac, out, L, Math.max(when, t0), mul, vv, o.f, o.dur, o.fast));
      }
    });
    return end;
  }

  /* ================= 和音と音階 ================= */
  function scaleOf(def) { return SCALES[def.scale] || SCALES.major; }
  /* 記号: "1".."7" 音階の度数に 3 度を重ねた和音。後ろに 7（7 の音）・9・s4・s2（掛留）・m / M（短・長に固定）・p（5 度だけ）。
   * 前に b を付けると、長音階の度数を半音下げた長三和音（bVII など、借りてくる和音） */
  function chord(def, sym) {
    var sc = scaleOf(def), n = sc.length, key = KEYS[def.key] || 0, m = /^(b?)([1-7])(.*)$/.exec(String(sym || "1")) || [0, "", "1", ""];
    var deg = +m[2] - 1, ext = m[3] || "";
    var at = function (i) { return key + sc[((i % n) + n) % n] + 12 * Math.floor(i / n); };
    var root = at(deg), tones;
    if (m[1] === "b") { root = key + SCALES.major[deg] - 1; tones = [root, root + 4, root + 7]; }
    else tones = [root, at(deg + 2), at(deg + 4)];
    if (/m(?!aj)/.test(ext.replace(/M/g, ""))) tones = [root, root + 3, root + 7];
    if (/M/.test(ext)) tones = [root, root + 4, root + 7];
    if (/s4/.test(ext)) tones[1] = root + 5;
    if (/s2/.test(ext)) tones[1] = root + 2;
    if (/p/.test(ext)) tones = [root, root + 7, root + 12];
    if (/7/.test(ext) || (def.sevenths && !/p/.test(ext))) tones.push(m[1] === "b" ? root + 10 : at(deg + 6));
    if (/9/.test(ext)) tones.push(m[1] === "b" ? root + 14 : at(deg + 8));
    return { root: root, tones: tones };
  }
  function progOf(def, ci) { var P = def.prog || [["1"]]; if (!Array.isArray(P[0])) P = [P]; var pr = P[ci % P.length];
    if (P.length === 1 && ci > 0 && def.rotate !== false) { var r = (ci * 2) % pr.length; pr = pr.slice(r).concat(pr.slice(0, r)); } return pr; }
  function symAt(def, ci, b) { var pr = progOf(def, ci), cb = def.cb || 1; return pr[Math.floor(b / cb) % pr.length]; }
  /* 和音を oct の C を中心に、近い転回で並べる（和音が変わっても音が跳ばない） */
  function voiced(ch, oct) { var base = 12 * (oct + 1); return ch.tones.map(function (t) { var m = base + (((t % 12) + 12) % 12); if (m > base + 9) m -= 12; return m; }).sort(function (a, b) { return a - b; }); }
  function rootAt(ch, oct, hi) { var base = 12 * (oct + 1), m = base + (((ch.root % 12) + 12) % 12); if (m > base + (hi === undefined ? 7 : hi)) m -= 12; return m; }
  function ladder(ch, oct, span) { var r0 = rootAt(ch, oct), out = [];
    for (var o = 0; o < (span || 2); o++) ch.tones.forEach(function (t) { out.push(r0 + (t - ch.root) + 12 * o); });
    out.sort(function (a, b) { return a - b; }); return out.filter(function (v, i) { return i === 0 || v !== out[i - 1]; }); }

  function rhythm(str, N) { var hits = []; str = String(str); for (var s = 0; s < N; s++) { var c = str[s % str.length]; if (c && c !== "." && c !== "-" && c !== " ") hits.push({ s: s, acc: c === "X" ? 1.15 : c === "g" ? .45 : c === "r" || c === "t" ? .75 : 1, roll: c === "r" ? 2 : c === "t" ? 3 : 0 }); }
    hits.forEach(function (h, i) { var nx = i + 1 < hits.length ? hits[i + 1].s : N; h.len = nx - h.s; }); return hits; }

  /* 旋律: 4 小節ずつの A・B。同じ段の小節は同じ律動と動きで、和音に合わせて高さが変わる（くり返しで覚えやすく） */
  var CELLS16 = [[0, 8], [0, 4, 8], [0, 4, 8, 12], [0, 6, 8, 12], [0, 2, 4, 8, 12], [0, 3, 6, 8, 12, 14], [0, 2, 4, 6, 8, 10, 12, 14]];
  var CELLS12 = [[0, 6], [0, 4, 8], [0, 2, 4, 8], [0, 4, 6, 8, 10]];
  function melody(def, L, ci, b, ch, N) {
    var sc = scaleOf(def), key = KEYS[def.key] || 0, center = 12 * ((L.oct === undefined ? 5 : L.oct) + 1) + key;
    var ph = b % 8, part = ph < 4 ? 0 : 1, sub = ph % 2, last = ph % 4 === 3;
    var R = rng(hash(def.seed || def.bpm, ci % 3, part, sub, L.inst));
    var cells = N === 12 ? CELLS12 : CELLS16, dens = L.dens === undefined ? .5 : L.dens;
    var cell = cells[Math.min(cells.length - 1, Math.floor(dens * (cells.length - 1) + R() * 1.6))].slice();
    if (last) { cell = cell.filter(function (s) { return s < N / 2; }); cell.push(N / 2); }
    var pool = []; for (var m = center - 7; m <= center + 14; m++) { var pc = ((m - key) % 12 + 12) % 12; if (sc.indexOf(pc) >= 0) pool.push(m); }
    var ct = ch.tones.map(function (t) { return ((t % 12) + 12) % 12; });
    var near = function (x, set) { var best = pool[0], bd = 99; pool.forEach(function (p) { if (set && set.indexOf(p % 12) < 0) return; var dd = Math.abs(p - x); if (dd < bd) { bd = dd; best = p; } }); return best; };
    var cur = near(center + Math.floor(R() * 7) - 2, ct), out = [], dir = R() < .5 ? -1 : 1;
    cell.forEach(function (s, i) {
      if (i > 0) {
        if (s % (N === 12 ? 6 : 8) === 0) cur = near(cur + dir * 2, ct);
        else { var idx = pool.indexOf(cur); if (idx < 0) idx = 0; var stp = R() < .7 ? 1 : 2; if (R() < .25) dir = -dir;
          idx = Math.max(0, Math.min(pool.length - 1, idx + dir * stp)); if (idx === 0 || idx === pool.length - 1) dir = -dir; cur = pool[idx]; }
      }
      if (last && i === cell.length - 1) cur = near(cur, [((ch.root % 12) + 12) % 12]);
      var nx = i + 1 < cell.length ? cell[i + 1] : N, len = last && i === cell.length - 1 ? N - s : Math.max(1, (nx - s) * .92);
      out.push({ s: s, len: len, m: cur, v: s % 4 === 0 ? 1 : .8 });
    });
    return out;
  }

  /* 1 小節の音符（ステップ単位）。L は層、ci は章、b は章の中の小節 */
  function layerBar(def, L, ci, b, N, R) {
    var ch = chord(def, symAt(def, ci, b)), nx = chord(def, symAt(def, ci, b + 1)), oct = L.oct === undefined ? 4 : L.oct, out = [];
    var all = function (s, len, v) { voiced(ch, oct).forEach(function (m) { out.push({ s: s, len: len, m: m, v: v || 1 }); }); };
    var p = L.pat || "hold", q = N / 4;
    if (p === "hold") all(0, N);
    else if (p === "half") { all(0, N / 2); all(N / 2, N / 2); }
    else if (p === "beat") { for (var s = 0; s < N; s += q) all(s, q * .9, s === 0 ? 1 : .8); }
    else if (p === "off") { for (var s2 = q / 2; s2 < N; s2 += q) all(s2, q * .45, .85); }
    else if (p === "stab" || p === "strum") { rhythm(L.rhy || "x..x..x.", N).forEach(function (h) { var vs = voiced(ch, oct);
      vs.forEach(function (m, i) { out.push({ s: h.s + (p === "strum" ? i * .12 : 0), len: Math.min(h.len, L.len || h.len) * .9, m: m, v: h.acc }); }); }); }
    else if (/^(arp(?!oct|3)|broken|alberti)/.test(p)) {
      var lad = ladder(ch, oct, L.span || 2), st = /16/.test(p) ? 1 : /4$/.test(p) ? 4 : 2, n = N / st;
      for (var i = 0; i < n; i++) {
        var idx, k = lad.length;
        if (/^arpud/.test(p)) { var per = Math.max(1, 2 * k - 2), j = i % per; idx = j < k ? j : per - j; }
        else if (/^arpdn/.test(p)) idx = k - 1 - (i % k);
        else if (/^arprnd/.test(p)) idx = Math.floor(R() * k);
        else if (/^broken/.test(p)) idx = [0, 2, 3, 2][i % 4];
        else if (/^alberti/.test(p)) idx = [0, 2, 1, 2][i % 4];
        else idx = i % k;
        out.push({ s: i * st, len: st * (L.hold || 1.6), m: lad[Math.min(k - 1, idx)], v: i % (N / st / 4 || 1) === 0 ? 1 : .8 });
      }
    }
    else if (/^root|^pulse16$|^oct8$|^fifth$|^walk$|^syncop$/.test(p)) {
      var r = rootAt(ch, oct), div = { root1: 1, root2: 2, root4: 4, root8: 8, pulse16: 16, oct8: 8, fifth: 4, walk: 4 }[p];
      if (p === "syncop") rhythm(L.rhy || "x..x..x...x.x...", N).forEach(function (h, i) { out.push({ s: h.s, len: h.len * .85, m: i === 3 ? r + 12 : r, v: h.acc }); });
      else for (var i2 = 0; i2 < div; i2++) {
        var ss = i2 * N / div, m2 = r;
        if (p === "oct8" && i2 % 2) m2 = r + 12;
        if (p === "fifth" && i2 % 2) m2 = r + 7;
        if (p === "walk") { var tt = ch.tones.map(function (t) { return r + (t - ch.root); }), nr = rootAt(nx, oct);
          m2 = [r, tt[1], tt[2], nr + (nr > tt[2] ? -1 : 1)][i2 % 4]; }
        out.push({ s: ss, len: (N / div) * (p === "root1" || p === "root2" ? 1 : .85), m: m2, v: i2 === 0 ? 1 : .85 });
      }
    }
    else if (p === "melody") out = melody(def, L, ci, b, ch, N);
    else if (p === "bells") { var lad2 = ladder(ch, oct, 2); for (var s3 = 0; s3 < N; s3 += 2) if (R() < (L.p === undefined ? .25 : L.p)) out.push({ s: s3, len: 4, m: lad2[Math.floor(R() * lad2.length)], v: .6 + .4 * R() }); }
    else if (p === "drone") { var kr = 12 * (oct + 1) + (KEYS[def.key] || 0); if (b % 2 === 0) { out.push({ s: 0, len: N * 2, m: kr, v: 1 }); out.push({ s: 0, len: N * 2, m: kr + 7, v: .7 }); } }
    else if (p === "ostinato") { var sc = scaleOf(def), kb = 12 * (oct + 1) + (KEYS[def.key] || 0), seq = L.seq || [0, 2, 4, 2], st2 = L.step || 2;
      for (var i3 = 0; i3 * st2 < N; i3++) { var dg = seq[i3 % seq.length], mm = kb + sc[((dg % sc.length) + sc.length) % sc.length] + 12 * Math.floor(dg / sc.length);
        out.push({ s: i3 * st2, len: st2 * (L.hold || 1.4), m: mm, v: i3 % 4 === 0 ? 1 : .8 }); } }
    else if (p === "skank") { for (var k1 = 1; k1 < (def.beats || 4); k1 += 2) { all(k1 * q, q * .3, 1); all(k1 * q + q / 2, q * .2, .45); } }
    else if (p === "pump8") { for (var s5 = 0; s5 < N; s5 += q / 2) all(s5, q * .42, s5 % q === 0 ? 1 : .72); }
    else if (p === "tremolo") { for (var s6 = 0; s6 < N; s6++) all(s6, 1, s6 % q === 0 ? .8 : .55); }
    else if (p === "tango") { rhythm(L.rhy || "X...x...x...x.x.", N).forEach(function (h) { var vs3 = voiced(ch, oct); vs3.forEach(function (m) { out.push({ s: h.s, len: Math.min(h.len, 1.4), m: m, v: h.acc }); }); }); }
    else if (p === "stride") { var r3 = rootAt(ch, oct), bt = def.beats || 4;
      for (var k2 = 0; k2 < bt; k2++) { if (k2 === 0) out.push({ s: 0, len: q * .9, m: r3, v: 1 }); else if (k2 === 2 && bt === 4) out.push({ s: 2 * q, len: q * .9, m: r3 - 5, v: .9 });
        else voiced(ch, oct + 1).forEach(function (m) { out.push({ s: k2 * q, len: q * .5, m: m, v: .7 }); }); } }
    else if (p === "gallop" || p === "habanera" || p === "arpoct" || p === "pedal8") {
      var r4 = rootAt(ch, oct);
      if (p === "gallop") rhythm(L.rhy || "x.xxx.xxx.xxx.xx", N).forEach(function (h) { out.push({ s: h.s, len: h.len * .8, m: r4, v: h.acc * (h.s % 4 === 0 ? 1 : .8) }); });
      else if (p === "habanera") for (var s7 = 0; s7 < N; s7 += 8) [[0, 0, 3], [3, 7, 1], [4, 12, 2], [6, 7, 2]].forEach(function (e) { if (s7 + e[0] < N) out.push({ s: s7 + e[0], len: e[2] * .9, m: r4 + e[1], v: e[0] ? .8 : 1 }); });
      else if (p === "arpoct") for (var s8 = 0; s8 < N; s8++) out.push({ s: s8, len: .9, m: r4 + [0, 12, 7, 12][s8 % 4], v: s8 % 4 === 0 ? 1 : .75 });
      else { var kr2 = 12 * (oct + 1) + (KEYS[def.key] || 0); for (var s9 = 0; s9 < N; s9 += 2) out.push({ s: s9, len: 1.6, m: kr2, v: s9 % 4 === 0 ? 1 : .7 }); }
    }
    else if (p === "arp3") { var lad3 = ladder(ch, oct, 2); for (var i4 = 0; i4 < N; i4++) out.push({ s: i4, len: 1.5, m: lad3[Math.min(lad3.length - 1, [0, 1, 2][i4 % 3] + (Math.floor(i4 / 6) % 2))], v: i4 % 3 === 0 ? 1 : .75 }); }
    else if (p === "run") { var sc2 = scaleOf(def), key2 = KEYS[def.key] || 0, pool2 = [], r5 = rootAt(ch, oct);
      for (var mm2 = r5; mm2 <= r5 + 24; mm2++) if (sc2.indexOf(((mm2 - key2) % 12 + 12) % 12) >= 0) pool2.push(mm2);
      if (b % 2 === 1 || (L.every || 0) > 0) for (var i5 = 0; i5 < N / 2; i5++) out.push({ s: N / 2 + i5, len: .9, m: pool2[Math.min(pool2.length - 1, i5)], v: .6 + .4 * i5 / (N / 2) }); }
    else if (p === "tanpura") { var kr3 = 12 * (oct + 1) + (KEYS[def.key] || 0); [[0, kr3 - 5], [q, kr3], [2 * q, kr3], [3 * q, kr3 - 12]].forEach(function (e) { if (e[0] < N) out.push({ s: e[0], len: N, m: e[1], v: e[0] ? .8 : 1 }); }); }
    else if (p === "counter") { var vs2 = voiced(ch, oct), top = vs2[vs2.length - 1]; out.push({ s: 0, len: N / 2, m: top, v: 1 }); out.push({ s: N / 2, len: N / 2, m: vs2[Math.max(0, vs2.length - 2)], v: .85 }); }
    return out;
  }
  function drumBar(def, ci, b, N, energy, R) {
    var pat = typeof def.drum === "object" ? def.drum : DRUMS[def.drum]; if (!pat) return [];
    var out = [], ev = energy >= 3 ? 1.12 : energy <= 1 ? .7 : 1;
    Object.keys(pat).forEach(function (inst) {
      rhythm(pat[inst], N).forEach(function (h) {
        if (energy <= 1 && h.acc < .5) return;
        if (energy <= 1 && (inst === "hat" || inst === "ohat" || inst === "shaker") && h.s % 4 !== 0) return;
        out.push({ s: h.s, inst: inst, v: h.acc * ev * (.88 + .24 * R()) });
        for (var k = 1; k < h.roll; k++) out.push({ s: h.s + k / h.roll, inst: inst, v: h.acc * ev * (.7 + .2 * R()) });
      });
    });
    if (energy >= 2 && b % 4 === 3 && def.fill !== false) {
      var fi = def.fillInst || (pat.snare ? "snare" : pat.taiko ? "tom" : pat.tom ? "tom" : null);
      if (fi) for (var s = N - 4; s < N; s++) if (s % 2 === 0 || energy >= 3) out.push({ s: s, inst: fi, v: .45 + .15 * (s - N + 4) });
    }
    if (energy >= 3 && b % 8 === 0) out.push({ s: 0, inst: "crash", v: .8 });
    if (energy >= 3 && pat.hat && !/x{4}/.test(pat.hat)) for (var s2 = 1; s2 < N; s2 += 2) out.push({ s: s2, inst: "hat", v: .3 });
    return out;
  }

  /* 小節の音符（ms）。章・小節ごとに覚える */
  function barEvents(def, ci, energy, b) {
    var cache = def.__cache || (def.__cache = {}), key = ci + "|" + energy + "|" + b;
    if (cache[key]) return cache[key];
    var beats = def.beats || 4, beat = 60000 / (def.bpm || 90), N = beats * 4, step = beat / 4, bar = beat * beats, out = [];
    var sw = def.swing || 0, t0 = b * bar;
    var at = function (s) { var sw8 = Math.abs(s % 4 - 2) < 1e-6 ? sw * step : 0, sw16 = def.swing16 && Math.abs(s % 2 - 1) < 1e-6 ? def.swing16 * step * .5 : 0; return t0 + s * step + sw8 + sw16; };
    if (def.code) {
      var fn = def.__fn; if (!fn) { try { fn = def.__fn = new Function("bar", "M", Array.isArray(def.code) ? def.code.join("\n") : def.code); } catch (e) { fn = def.__fn = function () { return []; }; console.error("music code:", e); } }
      var M = { bar: b, chapter: ci, energy: energy, beats: beats, bpm: def.bpm || 90, key: def.key || "C", scale: def.scale || "major",
        chord: function (sym, oct) { return voiced(chord(def, sym), oct === undefined ? 4 : oct); }, root: function (sym, oct) { return rootAt(chord(def, sym), oct === undefined ? 2 : oct); },
        prog: symAt(def, ci, b), degree: function (i, oct) { var sc = scaleOf(def); return 12 * ((oct === undefined ? 4 : oct) + 1) + (KEYS[def.key] || 0) + sc[((i % sc.length) + sc.length) % sc.length] + 12 * Math.floor(i / sc.length); },
        rand: rng(hash(def.seed || 1, ci, b)), hz: hz };
      var res = []; try { res = fn(b, M) || []; } catch (e) { if (!def.__err) { def.__err = 1; console.error("music code:", e); } }
      res.forEach(function (n) { out.push({ t: t0 + (n.at || 0) * beat, d: (n.len || (n.drum ? 0 : 1)) * beat, m: n.n, f: n.f, inst: n.drum || n.inst || "keys", v: n.v === undefined ? .8 : n.v, drum: !!n.drum }); });
    } else {
      (def.layers || []).forEach(function (L, li) {
        if ((L.e || 1) > energy || (L.x && energy > L.x)) return;
        if (L.every && b % L.every !== (L.phase || 0)) return;
        var R = rng(hash(def.seed || def.bpm, ci, b, li));
        layerBar(def, L, ci, b, N, R).forEach(function (n) { out.push({ t: at(n.s), d: n.len * step, m: n.m, inst: L.inst, v: (L.v === undefined ? 1 : L.v) * (n.v || 1) * (.92 + .16 * R()) }); });
      });
      if (def.drum && energy >= (def.de || 1)) { var R2 = rng(hash(def.seed || def.bpm, ci, b, "d")); drumBar(def, ci, b, N, energy, R2).forEach(function (n) { out.push({ t: at(n.s), d: 0, inst: n.inst, v: n.v * (def.dv === undefined ? 1 : def.dv), drum: true }); }); }
    }
    out.sort(function (a, b2) { return a.t - b2.t; });
    return (cache[key] = out);
  }
  /* 章の中の時刻 [t0, t1) ms に始まる音符。info: {ci 章, energy 1..3, len 章の長さ ms} */
  function notes(def, info, t0, t1) {
    var beat = 60000 / (def.bpm || 90), bar = beat * (def.beats || 4), out = [], len = info.len || Infinity;
    for (var b = Math.max(0, Math.floor(t0 / bar)); b * bar < t1 && b * bar < len; b++) {
      barEvents(def, info.ci || 0, info.energy || 2, b).forEach(function (n) { if (n.t >= t0 && n.t < t1 && n.t < len) out.push(n.d && n.t + n.d > len ? Object.assign({}, n, { d: len - n.t }) : n); });
    }
    return out;
  }
  /* 音符を鳴らす（INSTX は台本の instruments を足した楽器の表） */
  /* ---- 録音の楽器の音（samples）: 楽器ごとに 4 半音おきの録音を持ち、一番近い音を再生の速さで高さに合わせる ---- */
  var SMP = {}, SMP_ON = true;
  function useSamples(on) { SMP_ON = !!on; }
  function loadSamples(ac, map) {
    Object.keys(map || {}).forEach(function (inst) {
      var e = map[inst], s = SMP[inst] = { k: e.k, g: e.g || 1, buf: {} };
      Object.keys(e.n || {}).forEach(function (m) {
        fetch(e.n[m]).then(function (r) { return r.arrayBuffer(); }).then(function (b) { return ac.decodeAudioData(b); })
          .then(function (ab) { s.buf[m] = ab; }).catch(function (err) { console.warn("sample:", inst, m, err); });
      });
    });
  }
  function sampleNote(ac, out, n, when, durS, vol) {
    var s = SMP[n.inst]; if (!s) return 0;
    var m = n.m !== undefined ? n.m : n.f ? 69 + 12 * Math.log(n.f / 440) / Math.LN2 : 60, best = null, bd = 99;
    Object.keys(s.buf).forEach(function (k) { var d = Math.abs(+k - m); if (d < bd) { bd = d; best = k; } });
    if (best === null || bd > 6) return 0;   /* まだ復号できていない・音域の外は合成の音で */
    var b = s.buf[best], src = ac.createBufferSource(), g = ac.createGain(), v = (n.v === undefined ? 1 : n.v) * (vol === undefined ? 1 : vol) * s.g;
    src.buffer = b; src.playbackRate.value = Math.pow(2, (m - +best) / 12);
    var t0 = Math.max(when, ac.currentTime), dur = Math.max(.05, durS || .3), sus = s.k === "s";
    /* 伸ばす楽器は音符の長さだけ鳴らして離す。減衰する楽器（ピアノ・弦をはじく音）は少し余韻を残して離す */
    var rel = sus ? .22 : .35, end = Math.min(t0 + b.duration / src.playbackRate.value, t0 + (sus ? dur : Math.max(dur, .25) + .25) + rel * 3);
    g.gain.setValueAtTime(0, t0); g.gain.linearRampToValueAtTime(v, t0 + (sus ? .03 : .004));
    g.gain.setTargetAtTime(0, Math.max(t0 + .01, end - rel * 3), rel);
    src.connect(g); g.connect(out); src.start(t0); src.stop(end + .05);
    return end;
  }
  function note(ac, out, n, when, durS, vol, INSTX, fast) {
    /* 録音の音がある楽器はそれで鳴らす（台本で同じ名前の楽器を自作したときは sound.py が録音を入れない） */
    var se = SMP_ON && SMP[n.inst] ? sampleNote(ac, out, n, when, durS, vol) : 0; if (se) return se;
    var R = (INSTX && INSTX[n.inst]) || INST[n.inst]; if (!R) return;
    return play(ac, out, R, when, { f: n.f || hz(n.m === undefined ? 60 : n.m), dur: durS, v: n.v * (vol === undefined ? 1 : vol), fast: fast });
  }
  function isSus(inst, INSTX) { var R = (INSTX && INSTX[inst]) || INST[inst]; return !!(R && R.l && R.l.some(function (L) { return L.sus; })); }
  function barMs(def) { return 60000 / (def.bpm || 90) * (def.beats || 4); }

  /* 復号が済んだ録音の音の数（楽器ごと）。確かめる用 */
  function samplesReady() { var o = {}; Object.keys(SMP).forEach(function (k) { o[k] = Object.keys(SMP[k].buf).length; }); return o; }
  return { loadSamples: loadSamples, sampleNote: sampleNote, samplesReady: samplesReady, useSamples: useSamples, INST: INST, DRUMS: DRUMS, SCALES: SCALES, KEYS: KEYS, hz: hz, rng: rng, hash: hash, play: play, note: note, notes: notes, chord: chord, isSus: isSus, barMs: barMs };
})();
