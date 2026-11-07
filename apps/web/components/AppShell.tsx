"use client";

import { useCallback, useEffect, useState, useSyncExternalStore } from "react";
import { Feed } from "./Feed";
import { TastePanel } from "./TastePanel";
import { TasteSheet } from "./TasteSheet";
import { TasteAppContext, type TasteApp } from "./taste-context";
import { TasteStore } from "@/lib/taste-store";
import { ViewTracker, type ViewPayload } from "@/lib/view-tracker";
import type { Taste } from "@/lib/types";
import "./taste.css";

function sendView(payload: ViewPayload, beacon: boolean, onTaste: (t: Taste) => void): void {
  const body = JSON.stringify(payload);
  // ページを離れる最中は sendBeacon(応答は読めない)。使えない・断られたら keepalive の fetch
  if (beacon && typeof navigator !== "undefined" && navigator.sendBeacon) {
    const ok = navigator.sendBeacon("/api/view", new Blob([body], { type: "application/json" }));
    if (ok) return;
  }
  fetch("/api/view", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
    keepalive: true,
  })
    .then((res) => (res.ok ? (res.json() as Promise<{ taste: Taste }>) : null))
    .then((body) => {
      if (body) onTaste(body.taste);
    })
    .catch(() => {
      // 視聴の送信に失敗しても、動画の視聴は続ける
    });
}

/** 画面全体: 左にフィード、右に好みパネル(PC)。スマホでは好みシート */
export function AppShell() {
  const [app] = useState<TasteApp>(() => {
    const store = new TasteStore();
    const tracker = new ViewTracker({
      now: () => performance.now(),
      newViewId: () => crypto.randomUUID(),
      send: (payload, beacon) => {
        store.markViewed(payload.videoId);
        sendView(payload, beacon, (t) => store.applyTaste(t));
      },
    });
    return { store, tracker };
  });
  const { store, tracker } = app;
  const state = useSyncExternalStore(store.subscribe, store.getSnapshot, store.getSnapshot);

  // タブが隠れる・ページを離れるときに視聴を送る。戻ったら数え直す
  useEffect(() => {
    const onVisibility = () => {
      if (document.visibilityState === "hidden") tracker.suspend();
      else tracker.resume();
    };
    const onPageHide = () => tracker.suspend();
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("pagehide", onPageHide);
    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("pagehide", onPageHide);
    };
  }, [tracker]);

  const closeSheet = useCallback(() => store.closeSheet(), [store]);

  return (
    <TasteAppContext.Provider value={app}>
      <div className="app">
        <div className="appFeed">
          <Feed />
        </div>
        <aside className="tasteAside">
          <TastePanel state={state} />
        </aside>
        <TasteSheet open={state.sheetOpen} onClose={closeSheet}>
          <TastePanel state={state} />
        </TasteSheet>
      </div>
    </TasteAppContext.Provider>
  );
}
