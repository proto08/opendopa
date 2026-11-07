"use client";

import { useEffect, useId, useRef, type ReactNode } from "react";
import "./sheet.css";

const FOCUSABLE = 'button, a[href], input, select, textarea, [tabindex]:not([tabindex="-1"])';

/**
 * 下から出るシートの共通部品(元データ・好みで使う)。
 * 開いている間は `Esc` と背景のクリックで閉じ、フォーカスをシートの中に閉じ込める。
 * 閉じたら、開く前にフォーカスのあった要素へ戻す。再生を止めるのは呼び出し側(`hold`)。
 */
export function Sheet({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  const titleId = useId();
  const sheetRef = useRef<HTMLDivElement>(null);
  const onCloseRef = useRef(onClose);
  useEffect(() => {
    onCloseRef.current = onClose;
  });

  useEffect(() => {
    const previous = document.activeElement;
    const sheet = sheetRef.current;
    sheet?.querySelector<HTMLElement>(".sheetClose")?.focus();

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onCloseRef.current();
        return;
      }
      if (e.key !== "Tab" || !sheet) return;
      const items = Array.from(sheet.querySelectorAll<HTMLElement>(FOCUSABLE));
      if (items.length === 0) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      if (previous instanceof HTMLElement) previous.focus();
    };
  }, []);

  return (
    <div className="sheetBackdrop" onClick={onClose}>
      <div
        ref={sheetRef}
        className="sheet"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="sheetHeader">
          <h2 id={titleId} className="sheetTitle">
            {title}
          </h2>
          <button type="button" className="sheetClose" aria-label="閉じる" onClick={onClose}>
            ×
          </button>
        </div>
        <div className="sheetBody">{children}</div>
      </div>
    </div>
  );
}
