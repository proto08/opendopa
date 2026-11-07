// フィード全体で流す BGM(1 曲をループ)。React にも DOM にも依存しない(要素は差し替えられる)。
// 行ごとの音声(`LineAudio`)とは別の `<audio>` を使う。字幕の切り替えは音声の `ended` が基準なので、
// BGM はループさせて `onended` を使わず、行の音声の進行には関わらない。
import { markUnlockGesture } from "./audioChannel";

export type BgmElementLike = {
  src: string;
  loop: boolean;
  volume: number;
  muted: boolean;
  play(): Promise<void> | void;
  pause(): void;
};

type GestureTarget = Pick<Window, "addEventListener" | "removeEventListener">;

const GESTURE_EVENTS = ["pointerdown", "keydown"] as const;

export class Bgm {
  private wanted = false;
  private armed = false;

  constructor(
    private readonly element: BgmElementLike,
    private readonly target: GestureTarget,
    url: string,
    volume: number,
  ) {
    element.src = url;
    element.loop = true;
    element.volume = volume;
  }

  /** 鳴らす(止められたら、最初の操作で鳴らし直す)。ミュート中は鳴らさない */
  start(): void {
    this.wanted = true;
    this.play();
  }

  stop(): void {
    this.wanted = false;
    this.disarm();
    this.element.pause();
  }

  setMuted(muted: boolean): void {
    this.element.muted = muted;
    if (muted) {
      this.disarm();
      this.element.pause();
    } else if (this.wanted) {
      this.play();
    }
  }

  private play(): void {
    if (this.element.muted) return;
    const onBlocked = (error: unknown) => {
      if (error instanceof Error && error.name === "AbortError") return;
      if (this.wanted && !this.element.muted) this.arm();
    };
    try {
      Promise.resolve(this.element.play()).catch(onBlocked);
    } catch (error) {
      onBlocked(error);
    }
  }

  private readonly onGesture = (): void => {
    this.disarm();
    if (!this.wanted) return;
    // 最初のタップを一時停止の操作として扱わせない(行の音声と同じ扱い)
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
