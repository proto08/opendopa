"use client";

import { Fragment, useEffect, useId, useRef, useState } from "react";
import {
  highlightPieces,
  MAX_TAGS,
  sheetSections,
  type TagInfo,
} from "@/lib/tagFilter";
import "./tags.css";

const KIND_LABEL = { dataset: "種別", region: "地域" } as const;

/**
 * ステージの上に下からせり出す検索シート(高さ 74%)。
 * 選択は、シートの中の下書きで持つ。候補を選ぶと適用して閉じ、`×` で外した分は閉じるときに適用する。
 * 開いたら入力欄にフォーカスし、Esc で閉じる。閉じたあとのフォーカスは呼び出し側が虫眼鏡へ戻す。
 */
export function TagSearchSheet({
  catalog,
  failed,
  selected,
  onClose,
  initialQuery = "",
}: {
  /** null は読み込み中 */
  catalog: readonly TagInfo[] | null;
  failed: boolean;
  selected: readonly string[];
  /** 閉じる。最終的に選んでいるタグの ID を渡す */
  onClose: (tags: string[]) => void;
  /** 入力欄の初期値(テスト用) */
  initialQuery?: string;
}) {
  const [draft, setDraft] = useState<string[]>([...selected]);
  const [query, setQuery] = useState(initialQuery);
  const inputRef = useRef<HTMLInputElement>(null);
  const titleId = useId();
  const draftRef = useRef(draft);
  const onCloseRef = useRef(onClose);
  useEffect(() => {
    draftRef.current = draft;
    onCloseRef.current = onClose;
  });

  useEffect(() => {
    inputRef.current?.focus();
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      e.preventDefault();
      onCloseRef.current(draftRef.current);
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);

  const full = draft.length >= MAX_TAGS;
  const sections = catalog ? sheetSections(query, catalog) : [];
  const label = (id: string) => catalog?.find((t) => t.id === id)?.label ?? id;

  return (
    <div
      className="tagSheet"
      role="dialog"
      aria-labelledby={titleId}
      onClick={(e) => e.stopPropagation()}
    >
      <div className="tagSheetHeader">
        <h2 id={titleId} className="tagSheetTitle">
          タグで探す
        </h2>
        <button
          type="button"
          className="tagSheetClose"
          onClick={() => onClose(draft)}
        >
          閉じる
        </button>
      </div>
      <input
        ref={inputRef}
        type="search"
        className="tagSheetInput"
        placeholder="タグ名(例: 北海、れんたかー)"
        aria-label="タグ名で検索"
        autoComplete="off"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      {draft.length > 0 ? (
        <ul className="tagSheetSelected" aria-label="選択中のタグ">
          {draft.map((id) => (
            <li key={id}>
              <button
                type="button"
                className="tagSheetChip"
                aria-label={`#${label(id)} を外す`}
                onClick={() => setDraft((d) => d.filter((t) => t !== id))}
              >
                #{label(id)} <span aria-hidden="true">×</span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      {full ? (
        <p className="tagSheetNote">選べるタグは {MAX_TAGS} つまでです。</p>
      ) : null}
      <div className="tagSheetList">
        {failed ? (
          <p className="tagSheetNote" role="alert">
            タグを読み込めませんでした。
          </p>
        ) : catalog === null ? (
          <p className="tagSheetNote" role="status">
            読み込み中…
          </p>
        ) : sections.length === 0 ? (
          <p className="tagSheetNote" role="status">
            『{query}
            』に合うタグはありません。都道府県名やデータの種類で探してください。
          </p>
        ) : (
          sections.map((s) => (
            <Fragment key={s.title ?? "hits"}>
              {s.title ? <h3 className="tagSheetSection">{s.title}</h3> : null}
              <ul className="tagSheetRows">
                {s.tags.map((t) => {
                  const picked = draft.includes(t.id);
                  return (
                    <li key={t.id}>
                      <button
                        type="button"
                        className="tagSheetRow"
                        disabled={picked || full}
                        onClick={() => onClose([...draft, t.id])}
                      >
                        <span className="tagSheetKind" data-kind={t.kind}>
                          {KIND_LABEL[t.kind]}
                        </span>
                        <span className="tagSheetName">
                          #
                          {highlightPieces(t.label, query).map((p, i) =>
                            p.match ? (
                              <mark key={i}>{p.text}</mark>
                            ) : (
                              <Fragment key={i}>{p.text}</Fragment>
                            ),
                          )}
                        </span>
                        <span className="tagSheetCount">{t.count}本</span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </Fragment>
          ))
        )}
      </div>
    </div>
  );
}
