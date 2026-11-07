// 行ごとの音声の再生(設計書 §8.8)。React にも DOM にも依存しない(要素は差し替えられる)。
import {
  type AudioElementLike,
  audioBlocked,
  markUnlockGesture,
  sharedAudioElement,
} from "./audioChannel";

/** 音声の位置と行の経過秒がこれ以上ずれていたら、音声の位置を合わせる(秒) */
const SEEK_TOLERANCE_SEC = 0.25;

/** 最初の操作とみなすイベント */
const GESTURE_EVENTS = ["pointerdown", "keydown"] as const;

type GestureTarget = Pick<Window, "addEventListener" | "removeEventListener">;

export type LineAudioOptions = {
  /** 鳴らす要素。省略するとアプリ全体で共有する 1 本を使う */
  element?: AudioElementLike;
  /** いまの行の頭からの経過秒(途中から鳴らすときの位置) */
  getOffsetSec?: () => number;
  /** 行の音声が最後まで鳴った(字幕を次の行へ進める合図) */
  onEnded?: () => void;
  /** 最初の操作を待つ先。省略すると window */
  gestureTarget?: GestureTarget;
};

/** 要素ごとの、いま音声を鳴らす権利を持つ LineAudio */
const owners = new WeakMap<AudioElementLike, LineAudio>();

/**
 * いま表示中の行の音声を、共有の 1 本の要素で鳴らす。
 * `sync` に「鳴らす URL(なければ null)」「行・周回が変わったら変わる鍵」「一時停止中か」を渡す。
 * - 鍵か URL が変わると、`src` を差し替えて頭から鳴らす(行が進む・ループ)
 * - 一時停止で止め、再開で続きから鳴らす。字幕の位置とずれていれば、字幕に合わせてから鳴らす
 * - 自動再生が止められたら、最初の操作(pointerdown / keydown)で鳴らし直す
 * - 画面から外れた動画の `stop` が、いま鳴っている別の動画の音声を止めないよう、要素の持ち主だけが止められる
 */
export class LineAudio {
  private current: { url: string; key: string } | null = null;
  private paused = true;
  private armed = false;
  private resolved: AudioElementLike | null = null;

  constructor(private readonly options: LineAudioOptions = {}) {}

  private get element(): AudioElementLike {
    this.resolved ??= this.options.element ?? sharedAudioElement();
    return this.resolved;
  }

  private get target(): GestureTarget {
    return this.options.gestureTarget ?? window;
  }

  private get owned(): boolean {
    return this.current !== null && owners.get(this.element) === this;
  }

  /** この音声が、いま鳴っている最中か(字幕を音声の終わりまで待たせる判断に使う) */
  isPlaying(): boolean {
    return this.owned && !this.element.paused && !this.element.ended;
  }

  sync(url: string | null, key: string, paused: boolean): void {
    if (url === null) {
      this.stop();
      return;
    }
    const el = this.element;
    this.paused = paused;
    if (!this.owned || this.current?.url !== url || this.current.key !== key) {
      const sameUrl = this.owned && this.current?.url === url;
      this.current = { url, key };
      owners.set(el, this);
      el.onended = () => this.options.onEnded?.();
      if (sameUrl) el.currentTime = 0;
      else el.src = url;
    }
    if (paused) el.pause();
    else this.play();
  }

  stop(): void {
    this.disarm();
    if (this.owned) {
      const el = this.element;
      el.pause();
      el.onended = null;
      owners.delete(el);
      audioBlocked.set(false);
    }
    this.current = null;
  }

  private play(): void {
    const el = this.element;
    const offset = this.options.getOffsetSec?.() ?? 0;
    if (Math.abs(el.currentTime - offset) > SEEK_TOLERANCE_SEC) {
      el.currentTime = offset;
    }
    const onBlocked = (error: unknown) => {
      // 行が変わって読み込みが中断されたとき(AbortError)は、止められたのではない
      if (error instanceof Error && error.name === "AbortError") return;
      if (!this.owned || this.paused) return;
      audioBlocked.set(true);
      this.arm();
    };
    try {
      Promise.resolve(el.play()).then(() => {
        if (this.owned) audioBlocked.set(false);
      }, onBlocked);
    } catch (error) {
      onBlocked(error);
    }
  }

  private readonly onGesture = (): void => {
    this.disarm();
    if (!this.owned || this.paused) return;
    markUnlockGesture();
    this.play();
  };

  private arm(): void {
    if (this.armed) return;
    this.armed = true;
    for (const type of GESTURE_EVENTS) {
      this.target.addEventListener(type, this.onGesture, true);
    }
  }

  private disarm(): void {
    if (!this.armed) return;
    this.armed = false;
    for (const type of GESTURE_EVENTS) {
      this.target.removeEventListener(type, this.onGesture, true);
    }
  }
}
