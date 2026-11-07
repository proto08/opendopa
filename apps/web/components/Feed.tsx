"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { FeedItem, FeedResponse } from "@/lib/feedTypes";
import { clampIndex, keyToDelta, observeActiveSlide } from "@/lib/feedNav";
import { Slide } from "./Slide";
import { useTasteApp } from "./taste-context";
import "./feed.css";

/** 最初の取得だけ地図(`includeMap=1`)も受け取る */
async function fetchFeed(count: number, includeMap: boolean): Promise<FeedResponse> {
  const res = await fetch(`/api/feed?count=${count}${includeMap ? "&includeMap=1" : ""}`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`/api/feed が ${res.status} を返しました`);
  return (await res.json()) as FeedResponse;
}

/** 縦スクロールのフィード。1 画面 1 動画で、見えている動画だけ再生する */
export function Feed() {
  const [items, setItems] = useState<FeedItem[]>([]);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [active, setActive] = useState<number | null>(null);
  // 最後に再生中だった番号。切り替えの途中(active が null)でも Stage の window の基準にする
  const [anchor, setAnchor] = useState(0);
  const app = useTasteApp();
  const rootRef = useRef<HTMLDivElement>(null);
  const loadingMore = useRef(false);
  const lastActive = useRef(0);

  // 取得して items に足す。setState はコールバックの中だけで呼ぶ
  const load = useCallback((count: number, initial: boolean) => {
    if (loadingMore.current) return;
    loadingMore.current = true;
    fetchFeed(count, initial)
      .then((body) => {
        // 好みと地図は、受け取って描くだけ(計算はサーバー)
        if (body.map) app?.store.setMap(body.map);
        app?.store.applyTaste(body.taste);
        setItems((prev) => [...prev, ...body.items]);
        setStatus("ready");
      })
      .catch(() => {
        // 先読みの失敗は黙って次の機会に回す。最初の取得の失敗だけ画面に出す
        if (initial) setStatus("error");
      })
      .finally(() => {
        loadingMore.current = false;
      });
  }, [app]);

  // 最初は、現在の動画と先読みの 2 本
  useEffect(() => {
    load(2, true);
  }, [load]);

  // 常に「いまの次の 1 本」まで持っておく
  useEffect(() => {
    if (status !== "ready" || active === null) return;
    if (items.length < active + 2) load(1, false);
  }, [active, items.length, status, load]);

  // 60% 以上見えた動画を再生中にする
  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    const slides = Array.from(root.querySelectorAll(".slide"));
    return observeActiveSlide(root, slides, (index, visible) => {
      if (visible) {
        lastActive.current = index;
        setActive(index);
        setAnchor(index);
      } else {
        setActive((cur) => (cur === index ? null : cur));
      }
    });
  }, [items.length]);

  // ↑ ↓ j k で前後へ。端で止まる
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const delta = keyToDelta(e.key);
      if (delta === 0 || e.metaKey || e.ctrlKey || e.altKey) return;
      const target = e.target;
      if (
        target instanceof HTMLElement &&
        target.closest("input, textarea, select, [contenteditable]")
      ) {
        return;
      }
      const root = rootRef.current;
      if (!root) return;
      e.preventDefault(); // 矢印キーの素のスクロールと二重にならないように
      const to = clampIndex(lastActive.current, delta, items.length);
      root.querySelector(`[data-index="${to}"]`)?.scrollIntoView({ behavior: "smooth" });
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [items.length]);

  if (status === "loading") {
    return (
      <div className="feedMessage" role="status">
        読み込み中…
      </div>
    );
  }
  if (status === "error") {
    return (
      <div className="feedMessage" role="alert">
        <p>動画を読み込めませんでした。</p>
        <button
          type="button"
          onClick={() => {
            setStatus("loading");
            load(2, true);
          }}
        >
          もう一度読み込む
        </button>
      </div>
    );
  }

  return (
    <div className="feed" ref={rootRef} tabIndex={-1}>
      {items.map((item, i) => (
        <Slide
          key={i}
          item={item}
          index={i}
          active={active === i}
          mounted={Math.abs(i - anchor) <= 1}
        />
      ))}
    </div>
  );
}
