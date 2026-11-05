/** 上端の進行バー。`progress` は 0〜1(ループで 0 に戻る) */
export function ProgressBar({ progress }: { progress: number }) {
  return (
    <div
      className="progress"
      role="progressbar"
      aria-label="再生位置"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(progress * 100)}
    >
      <div className="progressFill" style={{ transform: `scaleX(${progress})` }} />
    </div>
  );
}
