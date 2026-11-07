"use client";

import type { Scene } from "@opendopa/shared";
import {
  type CSSProperties,
  type ReactNode,
  useCallback,
  useEffect,
} from "react";
import { takeUnlockGesture } from "@/lib/audioChannel";
import { useScenePlayer } from "@/lib/useScenePlayer";
import { AiLabel } from "./AiLabel";
import { BigNumber } from "./BigNumber";
import { Captions } from "./Captions";
import { Comments } from "./Comments";
import { MuteBadge } from "./MuteBadge";
import { PauseIcon } from "./PauseIcon";
import { ProgressBar } from "./ProgressBar";
import { SceneMap } from "./SceneMap";
import { SourceLine } from "./SourceLine";
import { Telop } from "./Telop";
import { useViewTracking } from "./taste-context";
import "./stage.css";

/** 9:16 の動画ステージ。1 本のシーンを再生する(タップと Space で一時停止/再開) */
export function Stage({
  scene,
  active = true,
  hold = false,
  children,
}: {
  scene: Scene;
  active?: boolean;
  /** true の間は再生を止める(シートが開いているとき) */
  hold?: boolean;
  /** 重ねて置くもの(右レールなど) */
  children?: ReactNode;
}) {
  const player = useScenePlayer(scene, active, hold);
  const { toggle: toggleRaw } = player;
  // 音声を鳴らすための最初の操作は、一時停止の操作として扱わない
  const toggle = useCallback(() => {
    if (!takeUnlockGesture()) toggleRaw();
  }, [toggleRaw]);
  useViewTracking(scene.videoId, active, player.paused);

  useEffect(() => {
    if (!active) return; // フィードでは、見えている動画だけが Space に反応する
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.code !== "Space" || e.repeat) return;
      const target = e.target;
      // 入力欄やボタンの Space は、その本来の動作を優先する
      if (
        target instanceof HTMLElement &&
        target !== document.body &&
        !target.classList.contains("stage") &&
        target.closest("input, textarea, select, button, a, [contenteditable]")
      ) {
        return;
      }
      e.preventDefault(); // ページのスクロールを止める
      toggle();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [toggle, active]);

  return (
    <div
      className="stage"
      style={{ "--cat": scene.color } as CSSProperties}
      role="button"
      tabIndex={0}
      aria-pressed={player.paused}
      aria-label={`${scene.headline}(タップで一時停止/再開)`}
      onClick={toggle}
    >
      <div className="watermark" aria-hidden="true">
        {scene.wmChar}
      </div>
      <ProgressBar progress={player.progress} />
      <div className="logo">
        <span className="logoTab">速報</span>
        <span className="logoName">OpenDopa NEWS</span>
      </div>
      <BigNumber data={scene.bigNumber} countProgress={player.countProgress} />
      <SceneMap map={scene.map} />
      <Telop categoryName={scene.categoryName} headline={scene.headline} />
      <Captions lines={scene.lines} lineIndex={player.lineIndex} />
      <SourceLine source={scene.source} />
      <AiLabel />
      <Comments
        comments={scene.comments}
        totalSec={player.totalSec}
        playedSec={player.playedSec}
      />
      {active && <MuteBadge />}
      <PauseIcon paused={player.paused} toggles={player.toggles} />
      {children}
    </div>
  );
}
