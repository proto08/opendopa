// 「あなたの好み」パネルの状態(設計書 §3.4、§3.6)。
// 好みの計算はサーバー(recsys)が行う。ここは `/api/feed`・`/api/view`・`/api/like` の `taste` を受け取って持つだけ。
import type { FeedMap } from "./feedTypes";
import type { Taste } from "./types";

/** 軌跡に残す点の数 */
export const TRAIL_MAX = 24;

export interface TasteState {
  taste: Taste | null;
  map: FeedMap | null;
  /** 再生中の動画 */
  currentVideoId: string | null;
  /** 見た動画(この画面で見たものと、視聴の記録に出ているもの) */
  viewed: ReadonlySet<string>;
  /** 「いまの好み」の軌跡(古い順。最後が現在地) */
  trail: readonly { x: number; y: number }[];
  /** スマホの好みシートが開いているか */
  sheetOpen: boolean;
}

const INITIAL: TasteState = {
  taste: null,
  map: null,
  currentVideoId: null,
  viewed: new Set(),
  trail: [],
  sheetOpen: false,
};

export class TasteStore {
  private state: TasteState = INITIAL;
  private listeners = new Set<() => void>();

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  getSnapshot = (): TasteState => this.state;

  /** `taste` を受け取る(feed・view・like のレスポンス) */
  applyTaste(taste: Taste): void {
    const last = this.state.trail[this.state.trail.length - 1];
    const moved = !last || last.x !== taste.x || last.y !== taste.y;
    const trail = moved ? [...this.state.trail, { x: taste.x, y: taste.y }].slice(-TRAIL_MAX) : this.state.trail;
    const viewed = new Set(this.state.viewed);
    for (const l of taste.log) viewed.add(l.videoId);
    this.set({ taste, trail, viewed });
  }

  /** 初回の `/api/feed?includeMap=1` の `map` */
  setMap(map: FeedMap): void {
    this.set({ map });
  }

  setCurrent(videoId: string | null): void {
    if (this.state.currentVideoId === videoId) return;
    this.set({ currentVideoId: videoId });
  }

  markViewed(videoId: string): void {
    if (this.state.viewed.has(videoId)) return;
    this.set({ viewed: new Set(this.state.viewed).add(videoId) });
  }

  openSheet(): void {
    if (!this.state.sheetOpen) this.set({ sheetOpen: true });
  }

  closeSheet(): void {
    if (this.state.sheetOpen) this.set({ sheetOpen: false });
  }

  private set(patch: Partial<TasteState>): void {
    this.state = { ...this.state, ...patch };
    this.listeners.forEach((l) => l());
  }
}
