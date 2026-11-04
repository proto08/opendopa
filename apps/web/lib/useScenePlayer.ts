"use client";

import type { Scene } from "@opendopa/shared";
import { useCallback, useEffect, useMemo, useRef, useSyncExternalStore } from "react";
import { ScenePlayer, type PlayerSnapshot } from "./scenePlayer";

export type UseScenePlayer = PlayerSnapshot & { toggle: () => void };

/**
 * 1 本の動画の再生状態(字幕の行・進行率・カウント・一時停止・ループ)と、行の音声。
 * 時計とループの計算は `ScenePlayer`(DOM に依存しない)に任せる。
 */
export function useScenePlayer(scene: Pick<Scene, "videoId" | "lines">): UseScenePlayer {
  const player = useMemo(
    // 動画が変わったら作り直す。lines の中身は videoId に対して不変とみなす
    () => new ScenePlayer(scene.lines),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [scene.videoId],
  );

  useEffect(() => {
    player.start();
    return () => player.stop();
  }, [player]);

  const toggle = useCallback(() => player.toggle(), [player]);
  const snap = useSyncExternalStore(player.subscribe, player.getSnapshot, player.getSnapshot);

  const audioUrl = scene.lines[snap.lineIndex]?.audio?.url ?? null;
  const audioRef = useRef<HTMLAudioElement | null>(null);
  // 行が変わる、またはループするたびに、その行の音声を頭から鳴らす
  useEffect(() => {
    if (!audioUrl) return;
    const audio = new Audio(audioUrl);
    audioRef.current = audio;
    audio.play().catch(() => {
      // 自動再生がブラウザに止められたときは、無音で字幕だけ進める
    });
    return () => {
      audio.pause();
      audioRef.current = null;
    };
    // 行・周回の変化だけで鳴らし直す(一時停止の切り替えでは鳴らし直さない)
  }, [audioUrl, snap.lineIndex, snap.loops]);

  // 一時停止で音声を止め、再開で続きから鳴らす
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    if (snap.paused) audio.pause();
    else audio.play().catch(() => {});
  }, [snap.paused]);

  return { ...snap, toggle };
}
