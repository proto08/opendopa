"use client";

import { useEffect, type ReactNode } from "react";

/** スマホ(幅 899px 以下)で、下から開く好みのシート。PC では CSS で出さない */
export function TasteSheet({
  open,
  onClose,
  children,
}: {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
}) {
  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="tasteSheetBackdrop" onClick={onClose}>
      <div
        className="tasteSheet"
        role="dialog"
        aria-modal="true"
        aria-label="あなたの好み"
        onClick={(e) => e.stopPropagation()}
      >
        <button type="button" className="tasteSheetClose" onClick={onClose}>
          閉じる
        </button>
        {children}
      </div>
    </div>
  );
}
