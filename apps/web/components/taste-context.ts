"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useSyncExternalStore,
} from "react";
import type { TasteStore } from "@/lib/taste-store";
import type { ViewTracker } from "@/lib/view-tracker";

export interface TasteApp {
  store: TasteStore;
  tracker: ViewTracker;
}

/** AppShell の外(開発用ページなど)では null。そのときは何もしない */
export const TasteAppContext = createContext<TasteApp | null>(null);

export function useTasteApp(): TasteApp | null {
  return useContext(TasteAppContext);
}

/** スマホの好みシートの開閉(右レールの「好み」ボタンから使う: #50) */
export function useTasteSheet(): {
  open: boolean;
  openSheet: () => void;
  closeSheet: () => void;
} {
  const app = useTasteApp();
  const open = useSyncExternalStore(
    (l) => app?.store.subscribe(l) ?? (() => {}),
    () => app?.store.getSnapshot().sheetOpen ?? false,
    () => false,
  );
  const openSheet = useCallback(() => app?.store.openSheet(), [app]);
  const closeSheet = useCallback(() => app?.store.closeSheet(), [app]);
  return { open, openSheet, closeSheet };
}

/** 動画が再生中の間だけ、視聴時間を数える(離れるときに送る)。AppShell の外では何もしない */
export function useViewTracking(
  videoId: string,
  active: boolean,
  paused: boolean,
): void {
  const app = useTasteApp();
  useEffect(() => {
    if (!app || !active) return;
    app.tracker.show(videoId);
    app.store.setCurrent(videoId);
    return () => app.tracker.hide();
  }, [app, videoId, active]);
  useEffect(() => {
    if (app && active) app.tracker.setPaused(paused);
  }, [app, active, paused, videoId]);
}
