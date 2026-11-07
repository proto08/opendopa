// 1 本の動画の再生ロジック(設計書 §9.2)。DOM にも React にも依存しない。
import type { Line } from "@opendopa/shared";

/** 大きな数字のカウントアップにかける秒数(§3.0) */
export const COUNT_UP_SEC = 1.2;

/** タブが裏に回るなどで時計が飛んだときに、1 回の更新で進める上限(秒) */
const MAX_STEP_SEC = 0.25;

/** 音声が鳴っている行の終わりで、音声の `ended` を待つ上限(秒)。読み込みが止まっても字幕が固まらないように */
export const AUDIO_WAIT_MAX_SEC = 1.5;

export type PlayerSnapshot = {
  /** ループ内の経過秒(0 以上 totalSec 未満) */
  elapsedSec: number;
  /** 全行の合計秒 */
  totalSec: number;
  /** 表示中の字幕の行 */
  lineIndex: number;
  /** 表示中の行の頭からの経過秒(音声を途中から鳴らす位置) */
  lineElapsedSec: number;
  /** 進行バーの割合(0〜1)。ループで 0 に戻る */
  progress: number;
  /** 再生を始めてからの累計秒。ループしても戻らない(カウントアップは 1 回だけ) */
  playedSec: number;
  /** カウントアップの時間の割合(0〜1)。1 に達したら固定 */
  countProgress: number;
  /** 何周したか。行の音声を頭から鳴らし直す合図 */
  loops: number;
  paused: boolean;
  /** 一時停止/再開を切り替えた回数。アイコンのアニメーションを再生し直す合図 */
  toggles: number;
};

export function totalDuration(durations: readonly number[]): number {
  return durations.reduce((sum, d) => sum + d, 0);
}

/** 累計の再生秒から、その時点の表示状態を求める純粋関数 */
export function computeSnapshot(
  durations: readonly number[],
  playedSec: number,
  state: { paused: boolean; toggles: number },
): PlayerSnapshot {
  const totalSec = totalDuration(durations);
  const loops = totalSec > 0 ? Math.floor(playedSec / totalSec) : 0;
  const elapsedSec = totalSec > 0 ? playedSec - loops * totalSec : 0;
  const lineIndex = lineIndexAt(durations, elapsedSec);
  return {
    elapsedSec,
    totalSec,
    lineIndex,
    lineElapsedSec: elapsedSec - lineStartSec(durations, lineIndex),
    progress: totalSec > 0 ? elapsedSec / totalSec : 0,
    playedSec,
    countProgress: Math.min(playedSec / COUNT_UP_SEC, 1),
    loops,
    ...state,
  };
}

/** ループ内の経過秒に対応する字幕の行(境目は次の行) */
export function lineIndexAt(
  durations: readonly number[],
  elapsedSec: number,
): number {
  let end = 0;
  for (let i = 0; i < durations.length; i++) {
    end += durations[i];
    if (elapsedSec < end) return i;
  }
  return Math.max(durations.length - 1, 0);
}

/** 行の頭の、ループ内の経過秒 */
export function lineStartSec(
  durations: readonly number[],
  lineIndex: number,
): number {
  return totalDuration(durations.slice(0, lineIndex));
}

export const easeOutCubic = (t: number): number => 1 - (1 - t) ** 3;

/** カウントアップ中に表示する数(ease-out)。`value` を超えない */
export function countUpValue(value: number, countProgress: number): number {
  const shown = value * easeOutCubic(Math.min(Math.max(countProgress, 0), 1));
  return countProgress >= 1 ? value : shown;
}

function decimalPlaces(n: number): number {
  const s = String(n);
  if (s.includes("e")) return 0;
  return s.split(".")[1]?.length ?? 0;
}

/** 大きな数字の表示文字列。数で countUp のときだけ 0 から数え、桁区切りを付ける */
export function formatBigNumber(
  value: number | string,
  countUp: boolean,
  countProgress: number,
): string {
  if (typeof value !== "number" || !Number.isFinite(value))
    return String(value);
  const places = decimalPlaces(value);
  const shown = countUp ? countUpValue(value, countProgress) : value;
  return shown.toLocaleString("ja-JP", {
    minimumFractionDigits: places,
    maximumFractionDigits: places,
  });
}

/**
 * 大きな数字の文字サイズ(cqw)。桁数(区切りと小数点を除く)で決める。
 * 4 桁まで 21、5 桁 17、6 桁 14、7 桁 12.5、8 桁以上 11.5(最小)。
 * 桁数は最終的な値で決め、カウント中に大きさが変わらないようにする。
 */
export function bigNumberFontSizeCqw(finalText: string): number {
  const digits = finalText.replace(/[,.\s]/g, "").length;
  if (digits <= 4) return 21;
  if (digits === 5) return 17;
  if (digits === 6) return 14;
  if (digits === 7) return 12.5;
  return 11.5;
}

type Frame = unknown;
export type PlayerDeps = {
  /** 現在時刻(ミリ秒) */
  now: () => number;
  schedule: (cb: () => void) => Frame;
  cancel: (handle: Frame) => void;
};

const defaultDeps: PlayerDeps = {
  now: () => performance.now(),
  schedule: (cb) =>
    typeof requestAnimationFrame === "function"
      ? requestAnimationFrame(cb)
      : setTimeout(cb, 16),
  cancel: (h) =>
    typeof cancelAnimationFrame === "function"
      ? cancelAnimationFrame(h as number)
      : clearTimeout(h as ReturnType<typeof setTimeout>),
};

/** 時計を持つプレイヤー。`useSyncExternalStore` に渡せる形(subscribe / getSnapshot) */
export class ScenePlayer {
  private readonly durations: number[];
  private readonly deps: PlayerDeps;
  private listeners = new Set<() => void>();
  private playedSec = 0;
  private paused = true;
  private toggles = 0;
  /** シートなどで一時的に止めているとき true(利用者の一時停止とは区別する) */
  private held = false;
  private lastMs = 0;
  private frame: Frame | null = null;
  /** 音声が鳴っている行は、その音声の終わりまで次の行へ進めない(true を返している間) */
  private audioGate: (() => boolean) | null = null;
  private waitedLine = "";
  private waitedSec = 0;
  private snapshot: PlayerSnapshot;

  constructor(
    lines: readonly Pick<Line, "durationSec">[],
    deps: Partial<PlayerDeps> = {},
  ) {
    this.durations = lines.map((l) => l.durationSec);
    this.deps = { ...defaultDeps, ...deps };
    this.snapshot = this.compute();
  }

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  getSnapshot = (): PlayerSnapshot => this.snapshot;

  /** 頭から再生を始める */
  start(): void {
    this.cancelFrame();
    this.playedSec = 0;
    this.toggles = 0;
    this.held = false;
    this.paused = false;
    this.lastMs = this.deps.now();
    this.publish();
    this.scheduleTick();
  }

  /** 一時停止して、字幕・進行を最初に戻す(画面から外れたとき) */
  reset(): void {
    this.cancelFrame();
    this.playedSec = 0;
    this.toggles = 0;
    this.held = false;
    this.paused = true;
    this.publish();
  }

  /**
   * シートが開いている間、再生を止める。一時停止アイコンは出さない。
   * すでに利用者が止めているときは何もしない(`release` でも再開しない)。
   */
  hold(): void {
    if (this.paused || this.held) return;
    this.advance();
    this.paused = true;
    this.held = true;
    this.cancelFrame();
    this.publish();
  }

  /** `hold` で止めた再生を続きから再開する。`hold` していなければ何もしない */
  release(): void {
    if (!this.held) return;
    this.held = false;
    this.paused = false;
    this.lastMs = this.deps.now();
    this.publish();
    this.scheduleTick();
  }

  /** 音声が鳴っている間、行の終わりで時計を待たせる判断を渡す(音声を時間の基準にする) */
  setAudioGate(gate: (() => boolean) | null): void {
    this.audioGate = gate;
  }

  /**
   * 音声が行の最後まで鳴ったとき、字幕をその行の終わりまで進める(見積もりより早く終わったとき)。
   * 一時停止中は何もしない。
   */
  finishLine(): void {
    if (this.paused) return;
    this.advance();
    const { end } = this.currentLine();
    this.playedSec = Math.max(this.playedSec, end);
    this.publish();
  }

  /** 時計を止めて破棄する */
  stop(): void {
    this.cancelFrame();
  }

  pause(): void {
    if (this.paused) return;
    this.advance();
    this.paused = true;
    this.toggles++;
    this.cancelFrame();
    this.publish();
  }

  resume(): void {
    if (!this.paused) return;
    this.paused = false;
    this.toggles++;
    this.lastMs = this.deps.now();
    this.publish();
    this.scheduleTick();
  }

  toggle(): void {
    if (this.held) return; // シートが開いている間は、利用者の操作で再開しない
    if (this.paused) this.resume();
    else this.pause();
  }

  private compute(): PlayerSnapshot {
    return computeSnapshot(this.durations, this.playedSec, {
      paused: this.paused,
      toggles: this.toggles,
    });
  }

  private advance(): void {
    const nowMs = this.deps.now();
    const step = Math.min(
      Math.max((nowMs - this.lastMs) / 1000, 0),
      MAX_STEP_SEC,
    );
    this.lastMs = nowMs;
    this.playedSec = this.gate(this.playedSec + step, step);
  }

  /** いまの行と、その行の終わりの累計秒 */
  private currentLine(): { key: string; end: number } {
    const total = totalDuration(this.durations);
    const loops = total > 0 ? Math.floor(this.playedSec / total) : 0;
    const line = lineIndexAt(this.durations, this.playedSec - loops * total);
    return {
      key: `${loops}:${line}`,
      end: loops * total + lineStartSec(this.durations, line + 1),
    };
  }

  /** 音声が鳴っている行の終わりを越えそうなら、行の中に留める(上限あり) */
  private gate(next: number, step: number): number {
    if (this.audioGate === null || totalDuration(this.durations) <= 0)
      return next;
    const { key, end } = this.currentLine();
    if (key !== this.waitedLine) {
      this.waitedLine = key;
      this.waitedSec = 0;
    }
    if (next < end || this.waitedSec >= AUDIO_WAIT_MAX_SEC || !this.audioGate())
      return next;
    this.waitedSec += step;
    return Math.max(this.playedSec, end - 1e-6);
  }

  private publish(): void {
    this.snapshot = this.compute();
    this.listeners.forEach((l) => l());
  }

  private scheduleTick(): void {
    this.frame = this.deps.schedule(() => {
      this.frame = null;
      if (this.paused) return;
      this.advance();
      this.publish();
      this.scheduleTick();
    });
  }

  private cancelFrame(): void {
    if (this.frame !== null) this.deps.cancel(this.frame);
    this.frame = null;
  }
}
