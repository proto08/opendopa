"use client";

import type { Scene } from "@opendopa/shared";
import { useCallback, useEffect, useMemo, useSyncExternalStore } from "react";
import { LineAudio } from "./lineAudio";
import { type PlayerSnapshot, ScenePlayer } from "./scenePlayer";

export type UseScenePlayer = PlayerSnapshot & { toggle: () => void };

/**
 * 1 本の動画の再生状態(字幕の行・進行率・カウント・一時停止・ループ)と、行の音声。
 * 時計とループの計算は `ScenePlayer`(DOM に依存しない)に任せる。
 */
export function useScenePlayer(
  scene: Pick<Scene, "videoId" | "lines">,
  /** false の間は止めて最初に戻す(フィードで画面から外れている動画) */
  active = true,
  /** true の間は再生を止める(シートが開いているとき)。false に戻すと続きから再開する */
  hold = false,
): UseScenePlayer {
  const player = useMemo(
    // 動画が変わったら作り直す。lines の中身は videoId に対して不変とみなす
    () => new ScenePlayer(scene.lines),
    [scene.videoId],
  );

  useEffect(() => {
    if (active) player.start();
    else player.reset();
    return () => player.stop();
  }, [player, active]);

  useEffect(() => {
    if (!active || !hold) return;
    player.hold();
    return () => player.release();
  }, [player, active, hold]);

  const toggle = useCallback(() => player.toggle(), [player]);
  const snap = useSyncExternalStore(
    player.subscribe,
    player.getSnapshot,
    player.getSnapshot,
  );

  const audioUrl = active
    ? (scene.lines[snap.lineIndex]?.audio?.url ?? null)
    : null;
  const lineAudio = useMemo(() => new LineAudio(), []);
  // 行が変わる・ループする・一時停止/再開するたびに、音声を字幕に合わせる
  useEffect(() => {
    lineAudio.sync(audioUrl, `${snap.lineIndex}:${snap.loops}`, snap.paused);
  }, [lineAudio, audioUrl, snap.lineIndex, snap.loops, snap.paused]);
  useEffect(() => () => lineAudio.stop(), [lineAudio]);

  return { ...snap, toggle };
}
