// 音声の共有状態(設計書 §8.8)。React にも DOM にも依存しない(`<audio>` は遅延して作る)。

/** `<audio>` 要素のうち、行の音声が使う部分 */
export type AudioElementLike = {
  src: string;
  currentTime: number;
  readonly paused: boolean;
  readonly ended: boolean;
  onended: ((e: Event) => unknown) | null;
  play(): Promise<void> | void;
  pause(): void;
};

let shared: AudioElementLike | null = null;

/**
 * アプリ全体で 1 本の `<audio>` を使い回す。`src` だけ差し替える。
 * 要素ごとに「操作の中での再生」が要る iOS Safari で、次の行・次の動画が無音になるのを避ける。
 */
export function sharedAudioElement(): AudioElementLike {
  shared ??= new Audio();
  return shared;
}

/** 自動再生が止められて、音声が鳴っていない間 true(ミュートの表示に使う) */
let blocked = false;
const listeners = new Set<() => void>();

export const audioBlocked = {
  get: (): boolean => blocked,
  set(value: boolean): void {
    if (blocked === value) return;
    blocked = value;
    listeners.forEach((l) => l());
  },
  subscribe(listener: () => void): () => void {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
};

/** 最初の操作の直後、この時間のうちのクリック・キーは「音を出すための操作」とみなす(ミリ秒) */
const UNLOCK_WINDOW_MS = 600;
let unlockedAt = Number.NEGATIVE_INFINITY;

/** 止められていた音声を、いまの操作で鳴らし始めた */
export function markUnlockGesture(now = performance.now()): void {
  unlockedAt = now;
}

/**
 * 直前の操作が「音を出すための操作」なら true を返し、消費する。
 * 最初のタップで音が鳴り始めると同時に、動画が一時停止してしまうのを防ぐ。
 */
export function takeUnlockGesture(now = performance.now()): boolean {
  const hit = now - unlockedAt <= UNLOCK_WINDOW_MS;
  unlockedAt = Number.NEGATIVE_INFINITY;
  return hit;
}
