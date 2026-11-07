"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  clampIndex,
  isEditableTarget,
  isLikeKey,
  keyToDelta,
  observeActiveSlide,
} from "@/lib/feedNav";
import type { FeedItem, FeedResponse } from "@/lib/feedTypes";
import { createLikeSync } from "@/lib/likeSync";
import { CsvSheet } from "./CsvSheet";
import { Slide } from "./Slide";
import { useTasteApp, useTasteSheet } from "./taste-context";
import "./feed.css";

/** 最初の取得だけ地図(`includeMap=1`)も受け取る */
async function fetchFeed(
  count: number,
  includeMap: boolean,
): Promise<FeedResponse> {
  const res = await fetch(
    `/api/feed?count=${count}${includeMap ? "&includeMap=1" : ""}`,
    {
      cache: "no-store",
    },
  );
  if (!res.ok) throw new Error(`/api/feed が ${res.status} を返しました`);
  return (await res.json()) as FeedResponse;
}

async function postLike(videoId: string, liked: boolean): Promise<void> {
  const res = await fetch("/api/like", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ videoId, liked }),
  });
  if (!res.ok) throw new Error(`/api/like が ${res.status} を返しました`);
}

/** 縦スクロールのフィード。1 画面 1 動画で、見えている動画だけ再生する */
export function Feed() {
  const [items, setItems] = useState<FeedItem[]>([]);
  const [status, setStatus] = useState<"loading" | "ready" | "error">(
    "loading",
  );
  const [active, setActive] = useState<number | null>(null);
  // 最後に再生中だった番号。切り替えの途中(active が null)でも Stage の window の基準にする
  const [anchor, setAnchor] = useState(0);
  const app = useTasteApp();
  const tasteSheet = useTasteSheet();
  // いいねの表示状態(動画 ID → 押されているか)。初期値は taste.log の liked
  const [liked, setLiked] = useState<Record<string, boolean>>({});
  const [csvOpen, setCsvOpen] = useState(false);
  // 元データのシートと、スマホの好みシート(#49)のどちらかが開いている間は、再生を止める
  const sheetOpen = csvOpen || tasteSheet.open;
  const likeSync = useMemo(
    () =>
      createLikeSync(postLike, (videoId, confirmed) =>
        setLiked((prev) => ({ ...prev, [videoId]: confirmed })),
      ),
    [],
  );
  const rootRef = useRef<HTMLDivElement>(null);
  const loadingMore = useRef(false);
  const lastActive = useRef(0);

  // 取得して items に足す。setState はコールバックの中だけで呼ぶ
  const load = useCallback(
    (count: number, initial: boolean) => {
      if (loadingMore.current) return;
      loadingMore.current = true;
      fetchFeed(count, initial)
        .then((body) => {
          // 好みと地図は、受け取って描くだけ(計算はサーバー)
          if (body.map) app?.store.setMap(body.map);
          app?.store.applyTaste(body.taste);
          // サーバーが知っているいいねを初期状態にする(この画面で押した分は上書きしない)
          const known = body.taste.log.filter((e) => e.liked);
          known.forEach((e) => likeSync.seed(e.videoId, true));
          setLiked((prev) => {
            const merged = { ...prev };
            for (const e of known)
              if (!(e.videoId in merged)) merged[e.videoId] = true;
            return merged;
          });
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
    },
    [app, likeSync],
  );

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

  const scrollBy = useCallback(
    (delta: number) => {
      const root = rootRef.current;
      if (!root) return;
      const to = clampIndex(lastActive.current, delta, items.length);
      root
        .querySelector(`[data-index="${to}"]`)
        ?.scrollIntoView({ behavior: "smooth" });
    },
    [items.length],
  );

  const toggleLike = useCallback(() => {
    const item = items[lastActive.current];
    if (!item) return;
    const id = item.videoId;
    const next = !(liked[id] ?? false);
    setLiked((prev) => ({ ...prev, [id]: next }));
    likeSync.request(id, next);
  }, [items, liked, likeSync]);

  // ↑ ↓ j k で前後へ(端で止まる)、l でいいね。シートが開いている間と入力欄では効かせない
  useEffect(() => {
    if (sheetOpen) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey || isEditableTarget(e.target))
        return;
      if (isLikeKey(e.key)) {
        if (e.repeat) return;
        e.preventDefault();
        toggleLike();
        return;
      }
      const delta = keyToDelta(e.key);
      if (delta === 0) return;
      e.preventDefault(); // 矢印キーの素のスクロールと二重にならないように
      scrollBy(delta);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [sheetOpen, toggleLike, scrollBy]);

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

  const shown = items[active ?? anchor];

  return (
    <div className="feed" ref={rootRef} tabIndex={-1}>
      {items.map((item, i) => (
        <Slide
          key={i}
          item={item}
          index={i}
          active={active === i}
          mounted={Math.abs(i - anchor) <= 1}
          hold={sheetOpen}
          liked={liked[item.videoId] ?? false}
          onLike={toggleLike}
          onCsv={() => setCsvOpen(true)}
          onTaste={tasteSheet.openSheet}
          onNext={() => scrollBy(1)}
        />
      ))}
      {csvOpen && shown ? (
        <CsvSheet
          datasetName={shown.scene.source.datasetName}
          sourceRef={shown.scene.source.ref}
          csvRow={shown.csvRow}
          onClose={() => setCsvOpen(false)}
        />
      ) : null}
    </div>
  );
}
