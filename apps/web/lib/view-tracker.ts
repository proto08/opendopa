// 視聴時間の計測と送信(設計書 §3.6、§6.2)。DOM と React に依存しない。
// 動画を表示するたびに新しい viewId を作り、離れるとき(60% を下回る・タブが隠れる・ページを離れる)に
// 一時停止の時間を除いた再生秒を送る。1 つの視聴は 1 回しか送らない。

export interface ViewPayload {
  viewId: string;
  videoId: string;
  watchedSec: number;
}

export interface ViewTrackerDeps {
  /** 現在時刻(ミリ秒) */
  now: () => number;
  newViewId: () => string;
  /** 送る。`beacon` が true のときは、ページを離れる最中でも届く送り方(`sendBeacon`)にする */
  send: (payload: ViewPayload, beacon: boolean) => void;
}

interface OpenView {
  viewId: string;
  videoId: string;
  playedMs: number;
  /** 再生中なら、再生を始めた(または再開した)時刻。一時停止中は null */
  playingSince: number | null;
}

export class ViewTracker {
  private shown: string | null = null;
  private paused = false;
  private open: OpenView | null = null;
  private readonly sent = new Set<string>();

  constructor(private readonly deps: ViewTrackerDeps) {}

  /** 動画が表示された(60% 以上見えた)。前の視聴が残っていれば先に送る */
  show(videoId: string): void {
    this.endView(false);
    this.shown = videoId;
    this.startView();
  }

  /** 動画が表示されなくなった(スクロールで 60% を下回った) */
  hide(): void {
    this.endView(false);
    this.shown = null;
  }

  /** タブが隠れた・ページを離れる。視聴を送って閉じるが、動画は表示中のまま(戻ったら `resume`) */
  suspend(): void {
    this.endView(true);
  }

  /** タブが戻った。表示中の動画があれば、新しい viewId で数え直す */
  resume(): void {
    if (this.shown !== null && this.open === null) this.startView();
  }

  setPaused(paused: boolean): void {
    if (this.paused === paused) return;
    this.paused = paused;
    const v = this.open;
    if (!v) return;
    const now = this.deps.now();
    if (paused) {
      if (v.playingSince !== null) {
        v.playedMs += now - v.playingSince;
        v.playingSince = null;
      }
    } else if (v.playingSince === null) {
      v.playingSince = now;
    }
  }

  private startView(): void {
    if (this.shown === null) return;
    this.open = {
      viewId: this.deps.newViewId(),
      videoId: this.shown,
      playedMs: 0,
      playingSince: this.paused ? null : this.deps.now(),
    };
  }

  private endView(beacon: boolean): void {
    const v = this.open;
    if (!v) return;
    this.open = null;
    if (this.sent.has(v.viewId)) return;
    this.sent.add(v.viewId);
    const playedMs =
      v.playedMs +
      (v.playingSince !== null ? this.deps.now() - v.playingSince : 0);
    const watchedSec = Math.max(0, Math.round(playedMs) / 1000);
    this.deps.send(
      { viewId: v.viewId, videoId: v.videoId, watchedSec },
      beacon,
    );
  }
}
