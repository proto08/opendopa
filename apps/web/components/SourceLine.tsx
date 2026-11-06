import type { Source } from "@opendopa/shared";

/** 常に表示する出典(設計書 §15.1) */
export function SourceLine({ source }: { source: Source }) {
  return (
    <div className="sourceLine">
      出典:{source.datasetName} / {source.ref}
    </div>
  );
}
