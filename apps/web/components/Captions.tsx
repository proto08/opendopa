import type { Line } from "@opendopa/shared";

/** 字幕。いまの行だけを出す */
export function Captions({ lines, lineIndex }: { lines: Line[]; lineIndex: number }) {
  return (
    <div className="captions" aria-live="off">
      <p className="captionText" key={lineIndex}>
        {lines[lineIndex]?.text}
      </p>
    </div>
  );
}
