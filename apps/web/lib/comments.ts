// 流れるコメントの配置(設計書 §3.0・§9.2)。DOM にも React にも依存しない純粋な関数。
import type { FlowComment } from "@opendopa/shared";

/** レーン数 */
export const LANE_COUNT = 7;
/** 右端から左端まで流れる秒数の範囲 */
export const MIN_DURATION_SEC = 6;
export const MAX_DURATION_SEC = 8.5;

/**
 * 空いている最初のレーンの番号。全レーンが使用中なら null(その回は出さない)。
 * `busyUntil[i]` はレーン i が空く時刻(秒)。`now` 以前なら空いている。
 */
export function assignLane(busyUntil: readonly number[], now: number): number | null {
  const lane = busyUntil.findIndex((until) => until <= now);
  return lane === -1 ? null : lane;
}

/** コメントが流れる秒数(6〜8.5)。文字列と時刻から決めるので、毎回同じ */
export function commentDuration(c: Pick<FlowComment, "t" | "text">): number {
  let h = Math.floor(c.t * 1000);
  for (const ch of c.text) h = (Math.imul(h, 31) + ch.codePointAt(0)!) >>> 0;
  return MIN_DURATION_SEC + ((h % 1000) / 999) * (MAX_DURATION_SEC - MIN_DURATION_SEC);
}

export type ActiveComment = {
  /** ループ周回と添字から作る、安定したキー */
  key: string;
  text: string;
  style: FlowComment["style"];
  lane: number;
  /** 0(右端から出始め)〜1(左端に消える) */
  progress: number;
};

/**
 * 累計の再生秒 `playedSec` に画面にいるコメント。
 * 出す時刻は動画内の `t`(ループしても同じ時刻)。レーンが全部埋まっていたら、その回は出さない。
 * 過去の出し入れを先頭から再現するが、MAX_DURATION_SEC より前のものはもう消えているので、
 * それより後に出るものだけをたどる(周回数が増えても軽い)。
 */
export function activeComments(
  comments: readonly FlowComment[],
  totalSec: number,
  playedSec: number,
): ActiveComment[] {
  if (comments.length === 0 || totalSec <= 0) return [];
  const sorted = comments
    .map((c, i) => ({ c, i }))
    .filter(({ c }) => c.t < totalSec)
    .sort((a, b) => a.c.t - b.c.t || a.i - b.i);

  const from = Math.max(playedSec - MAX_DURATION_SEC, 0);
  const firstLoop = Math.floor(from / totalSec);
  const lastLoop = Math.floor(playedSec / totalSec);
  const busyUntil: number[] = Array(LANE_COUNT).fill(-Infinity);
  const active: ActiveComment[] = [];

  for (let loop = firstLoop; loop <= lastLoop; loop++) {
    for (const { c, i } of sorted) {
      const start = loop * totalSec + c.t;
      if (start < from || start > playedSec) continue;
      const lane = assignLane(busyUntil, start);
      if (lane === null) continue;
      const duration = commentDuration(c);
      busyUntil[lane] = start + duration;
      const progress = (playedSec - start) / duration;
      if (progress < 1) {
        active.push({ key: `${loop}-${i}`, text: c.text, style: c.style, lane, progress });
      }
    }
  }
  return active;
}
