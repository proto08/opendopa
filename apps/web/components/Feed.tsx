"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { buildSlots } from "@/lib/ads";
import {
  clampIndex,
  isEditableTarget,
  keyAction,
  observeActiveSlide,
} from "@/lib/feedNav";
import type { FeedItem, FeedResponse } from "@/lib/feedTypes";
import { createLikeSync } from "@/lib/likeSync";
import {
  feedUrl,
  filteredCount,
  readTagsFromSearch,
  sameTags,
  type TagInfo,
  toggleTag,
  withTagsInSearch,
} from "@/lib/tagFilter";
import { AdSlide } from "./AdSlide";
import { CsvSheet } from "./CsvSheet";
import { PoolEmpty } from "./PoolEmpty";
import { SearchButton } from "./SearchButton";
import { Slide } from "./Slide";
import { TagSearchSheet } from "./TagSearchSheet";
import { useTasteApp, useTasteSheet } from "./taste-context";
import "./feed.css";
import "./tags.css";

/** 最初の取得だけ地図(`includeMap=1`)も受け取る。`tags` があれば、すべてを持つ動画だけ(AND) */
async function fetchFeed(
  count: number,
  includeMap: boolean,
  tags: readonly string[],
): Promise<FeedResponse> {
  const res = await fetch(feedUrl(count, includeMap, tags), {
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`/api/feed が ${res.status} を返しました`);
  return (await res.json()) as FeedResponse;
}

async function fetchTags(): Promise<TagInfo[]> {
  const res = await fetch("/api/tags", { cache: "no-store" });
  if (!res.ok) throw new Error(`/api/tags が ${res.status} を返しました`);
  return ((await res.json()) as { tags: TagInfo[] }).tags;
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
  // タグの絞り込み(状態は URL の ?tag= にも持つ)と検索シート
  const [tags, setTags] = useState<string[]>([]);
  const [catalog, setCatalog] = useState<TagInfo[] | null>(null);
  const [catalogFailed, setCatalogFailed] = useState(false);
  const [searchAt, setSearchAt] = useState<number | null>(null);
  const [poolEmpty, setPoolEmpty] = useState(false);
  const searchOpen = searchAt !== null;
  // 元データのシート、スマホの好みシート(#49)、検索シートのどれかが開いている間は、再生を止める
  const sheetOpen = csvOpen || tasteSheet.open || searchOpen;
  const likeSync = useMemo(
    () =>
      createLikeSync(postLike, (videoId, confirmed) =>
        setLiked((prev) => ({ ...prev, [videoId]: confirmed })),
      ),
    [],
  );
  // 動画の列に広告を差し込んだ表示用の並び。active・anchor・lastActive は、この並びでの番号
  const slots = useMemo(() => buildSlots(items), [items]);
  // 候補が尽きたら、最後の動画のあとに案内の 1 画面を足す
  const slideCount = slots.length + (poolEmpty ? 1 : 0);
  const rootRef = useRef<HTMLDivElement>(null);
  // 絞り込みを変えて取り直したあと、虫眼鏡へフォーカスを戻すかどうか
  const refocusSearch = useRef(false);
  const loadingMore = useRef(false);
  const lastActive = useRef(0);
  const tagsRef = useRef<string[]>([]);
  // 絞り込みを変えるたびに増やす。古い取得の結果は捨てる
  const generation = useRef(0);

  // 取得して items に足す。setState はコールバックの中だけで呼ぶ
  const load = useCallback(
    (count: number, initial: boolean, includeMap = initial) => {
      if (loadingMore.current) return;
      loadingMore.current = true;
      const mine = generation.current;
      fetchFeed(count, includeMap, tagsRef.current)
        .then((body) => {
          if (mine !== generation.current) return;
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
          if (body.reason === "pool_empty") setPoolEmpty(true);
          setItems((prev) => [...prev, ...body.items]);
          setStatus("ready");
        })
        .catch(() => {
          if (mine !== generation.current) return;
          // 先読みの失敗は黙って次の機会に回す。最初の取得の失敗だけ画面に出す
          if (initial) setStatus("error");
        })
        .finally(() => {
          if (mine === generation.current) loadingMore.current = false;
        });
    },
    [app, likeSync],
  );

  // 最初は、URL のタグを読んで、現在の動画と先読みの 2 本
  useEffect(() => {
    const initialTags = readTagsFromSearch(window.location.search);
    tagsRef.current = initialTags;
    setTags(initialTags);
    load(2, true);
  }, [load]);

  // タグの件数の表(虫眼鏡の本数と検索シートの候補)
  useEffect(() => {
    fetchTags()
      .then(setCatalog)
      .catch(() => setCatalogFailed(true));
  }, []);

  // 絞り込みを変える: キューと先読みを捨て、URL を直し、条件つきで取り直して先頭へ戻る
  const applyTags = useCallback(
    (next: string[]) => {
      generation.current += 1;
      loadingMore.current = false;
      tagsRef.current = next;
      lastActive.current = 0;
      setTags(next);
      setItems([]);
      setPoolEmpty(false);
      setActive(null);
      setAnchor(0);
      setStatus("loading");
      window.history.replaceState(
        null,
        "",
        `${window.location.pathname}${withTagsInSearch(window.location.search, next)}${window.location.hash}`,
      );
      load(2, true, false);
    },
    [load],
  );

  const openSearch = useCallback(() => {
    tasteSheet.closeSheet(); // スマホの好みシートと同時には開かない
    setSearchAt(lastActive.current);
  }, [tasteSheet]);

  const closeSearch = useCallback(
    (next: string[]) => {
      const at = searchAt;
      setSearchAt(null);
      if (!sameTags(next, tagsRef.current)) {
        refocusSearch.current = true;
        applyTags(next);
        return;
      }
      // 閉じたら虫眼鏡へフォーカスを戻す
      requestAnimationFrame(() =>
        rootRef.current
          ?.querySelector<HTMLElement>(`[data-index="${at}"] .searchButton`)
          ?.focus(),
      );
    },
    [searchAt, applyTags],
  );

  // 取り直しのあとも、閉じたら虫眼鏡へフォーカスを戻す(先頭の画面の虫眼鏡)
  useEffect(() => {
    if (status !== "ready" || !refocusSearch.current) return;
    refocusSearch.current = false;
    rootRef.current
      ?.querySelector<HTMLElement>('[data-index="0"] .searchButton')
      ?.focus();
  }, [status]);

  // 検索シートが開いている間に好みシートが開いたら、検索シートを閉じる
  useEffect(() => {
    if (tasteSheet.open) setSearchAt(null);
  }, [tasteSheet.open]);

  const onTag = useCallback(
    (id: string) => applyTags(toggleTag(tagsRef.current, id)),
    [applyTags],
  );

  // 常に「いまの次の 1 本」まで持っておく
  useEffect(() => {
    if (status !== "ready" || active === null) return;
    // 広告をはさんでも、次の動画が 1 本は手元にあるようにする
    const videosAfter = slots.filter(
      (s, i) => i > active && s.kind === "video",
    ).length;
    if (videosAfter < 1) load(1, false);
  }, [active, slots, status, load]);

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
  }, [slideCount]);

  const scrollBy = useCallback(
    (delta: number) => {
      const root = rootRef.current;
      if (!root) return;
      const to = clampIndex(lastActive.current, delta, slideCount);
      root
        .querySelector(`[data-index="${to}"]`)
        ?.scrollIntoView({ behavior: "smooth" });
    },
    [slideCount],
  );

  const toggleLike = useCallback(() => {
    const slot = slots[lastActive.current];
    if (slot?.kind !== "video") return; // 広告にはいいねしない
    const id = slot.item.videoId;
    const next = !(liked[id] ?? false);
    setLiked((prev) => ({ ...prev, [id]: next }));
    likeSync.request(id, next);
  }, [slots, liked, likeSync]);

  // ↑ ↓ j k で前後へ(端で止まる)、l でいいね。シートが開いている間と入力欄では効かせない
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey || isEditableTarget(e.target))
        return;
      const action = keyAction(e.key, sheetOpen);
      if (action.type === "like") {
        if (e.repeat) return;
        e.preventDefault();
        toggleLike();
      } else if (action.type === "move") {
        e.preventDefault(); // 矢印キーの素のスクロールと二重にならないように
        scrollBy(action.delta);
      }
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
        {tags.length > 0 ? (
          <button type="button" onClick={() => applyTags([])}>
            タグを外して読み込む
          </button>
        ) : null}
      </div>
    );
  }

  const shownSlot = slots[active ?? anchor];
  const shown = shownSlot?.kind === "video" ? shownSlot.item : undefined;

  // 虫眼鏡と、開いていれば検索シート(見えている動画のステージの上)
  const overlay = (index: number) => (
    <>
      <SearchButton
        filtering={tags.length > 0}
        count={filteredCount(tags, catalog)}
        onOpen={openSearch}
      />
      {searchAt === index ? (
        <TagSearchSheet
          catalog={catalog}
          failed={catalogFailed}
          selected={tags}
          onClose={closeSearch}
        />
      ) : null}
    </>
  );

  return (
    <div className="feed" ref={rootRef} tabIndex={-1} data-locked={searchOpen}>
      {slots.map((slot, i) =>
        slot.kind === "ad" ? (
          <AdSlide key={i} ad={slot.ad} index={i} onNext={() => scrollBy(1)} />
        ) : (
          <Slide
            key={i}
            item={slot.item}
            index={i}
            active={active === i}
            mounted={Math.abs(i - anchor) <= 1}
            hold={sheetOpen}
            liked={liked[slot.item.videoId] ?? false}
            onLike={toggleLike}
            onCsv={() => setCsvOpen(true)}
            onTaste={tasteSheet.openSheet}
            onNext={() => scrollBy(1)}
            selectedTags={tags}
            onTag={onTag}
            overlay={overlay(i)}
          />
        ),
      )}
      {poolEmpty ? (
        <section className="slide" data-index={slots.length} aria-label="動画なし">
          <div className="stage" style={{ cursor: "default" }}>
            <PoolEmpty onClear={() => applyTags([])} />
            {overlay(slots.length)}
          </div>
        </section>
      ) : null}
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
