/**
 * 画面中央の一時停止/再生アイコン。切り替えのたびに 0.6 秒で拡大して消える。
 * `toggles` が 0 のうちは出さない。`prefers-reduced-motion` では動かさず、一時停止中だけ出す。
 */
export function PauseIcon({
  paused,
  toggles,
}: {
  paused: boolean;
  toggles: number;
}) {
  if (toggles === 0) return null;
  return (
    <div
      className="pauseIcon"
      key={toggles}
      data-paused={paused}
      aria-hidden="true"
    >
      {paused ? (
        <svg viewBox="0 0 24 24" fill="currentColor">
          <rect x="6" y="4" width="4" height="16" rx="1" />
          <rect x="14" y="4" width="4" height="16" rx="1" />
        </svg>
      ) : (
        <svg viewBox="0 0 24 24" fill="currentColor">
          <path d="M7 4.5v15a1 1 0 0 0 1.5.86l12-7.5a1 1 0 0 0 0-1.72l-12-7.5A1 1 0 0 0 7 4.5z" />
        </svg>
      )}
    </div>
  );
}
