"use client";

import { useSyncExternalStore } from "react";
import { audioBlocked } from "@/lib/audioChannel";

/**
 * 自動再生が止められて音声が鳴っていないとき、右上に「音声オフ」を出す。
 * 最初のタップ(またはキー)で鳴り始め、表示は消える。
 */
export function MuteBadge() {
  const blocked = useSyncExternalStore(
    audioBlocked.subscribe,
    audioBlocked.get,
    () => false,
  );
  if (!blocked) return null;
  return (
    <div className="muteBadge" role="status">
      <svg
        viewBox="0 0 24 24"
        aria-hidden="true"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M4 9.5v5h3.5L12 18.5v-13L7.5 9.5H4z" fill="currentColor" />
        <path d="M16 9.5l5 5M21 9.5l-5 5" />
      </svg>
      <span>タップで音声オン</span>
    </div>
  );
}
