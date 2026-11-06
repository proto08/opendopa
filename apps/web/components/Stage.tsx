"use client";

import type { Scene } from "@opendopa/shared";
import { useEffect, type CSSProperties } from "react";
import { useScenePlayer } from "@/lib/useScenePlayer";
import { AiLabel } from "./AiLabel";
import { BigNumber } from "./BigNumber";
import { Captions } from "./Captions";
import { Comments } from "./Comments";
import { PauseIcon } from "./PauseIcon";
import { ProgressBar } from "./ProgressBar";
import { SourceLine } from "./SourceLine";
import { Telop } from "./Telop";
import "./stage.css";

/** 9:16 の動画ステージ。1 本のシーンを再生する(タップと Space で一時停止/再開) */
export function Stage({ scene, active = true }: { scene: Scene; active?: boolean }) {
  const player = useScenePlayer(scene, active);
  const { toggle } = player;

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
      <Telop categoryName={scene.categoryName} headline={scene.headline} />
      <Captions lines={scene.lines} lineIndex={player.lineIndex} />
      <SourceLine source={scene.source} />
      <AiLabel />
      <Comments comments={scene.comments} totalSec={player.totalSec} playedSec={player.playedSec} />
      <PauseIcon paused={player.paused} toggles={player.toggles} />
    </div>
  );
}
