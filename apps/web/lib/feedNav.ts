// フィードの操作まわり(DOM と React に依存しない部分)。

/** キーから、動かす向き(+1 次へ / -1 前へ)を求める。対象外のキーは 0 */
export function keyToDelta(key: string): -1 | 0 | 1 {
  if (key === "ArrowDown" || key === "j") return 1;
  if (key === "ArrowUp" || key === "k") return -1;
  return 0;
}

/** 現在の位置から delta 動かした位置。端で止まる */
export function clampIndex(index: number, delta: number, length: number): number {
  if (length <= 0) return 0;
  return Math.min(Math.max(index + delta, 0), length - 1);
}

/** 動画が見えている割合がこれ以上になったら再生を始める */
export const ACTIVE_RATIO = 0.6;

type EntryLike = { target: Element; isIntersecting: boolean; intersectionRatio: number };
type ObserverCtor = new (
  cb: (entries: EntryLike[]) => void,
  options: { root?: Element | null; threshold: number[] },
) => { observe(el: Element): void; unobserve(el: Element): void; disconnect(): void };

/**
 * 各スライドを監視し、60% 以上見えたら onChange(番号, true)、それを下回ったら onChange(番号, false) を呼ぶ。
 * スライドは `data-index` で番号を持つ。戻り値は監視をやめる関数。
 */
export function observeActiveSlide(
  root: Element,
  slides: readonly Element[],
  onChange: (index: number, visible: boolean) => void,
  Observer: ObserverCtor = IntersectionObserver as unknown as ObserverCtor,
): () => void {
  const observer = new Observer(
    (entries) => {
      for (const e of entries) {
        const i = Number((e.target as HTMLElement).dataset.index);
        if (!Number.isInteger(i)) continue;
        onChange(i, e.isIntersecting && e.intersectionRatio >= ACTIVE_RATIO);
      }
    },
    { root, threshold: [ACTIVE_RATIO] },
  );
  slides.forEach((s) => observer.observe(s));
  return () => observer.disconnect();
}
