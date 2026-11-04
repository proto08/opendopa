"use client";

import type { Scene } from "@opendopa/shared";
import { useState } from "react";
import { Stage } from "@/components/Stage";

type Fixture = { name: string; scene: Scene };

/** 確認用: フィクスチャを切り替え、大きな数字の値とカウントアップを上書きして見られる */
export function StageDev({ fixtures }: { fixtures: Fixture[] }) {
  const [name, setName] = useState(fixtures[0].name);
  const [value, setValue] = useState("");
  const [countUp, setCountUp] = useState(false);
  const [run, setRun] = useState(0);

  const base = fixtures.find((f) => f.name === name)!.scene;
  const scene: Scene = {
    ...base,
    bigNumber: {
      ...base.bigNumber,
      value: value === "" ? base.bigNumber.value : isNaN(Number(value)) ? value : Number(value),
      countUp,
    },
  };

  return (
    <div className="devStage">
      <div className="devControls">
        <label>
          フィクスチャ
          <select value={name} onChange={(e) => setName(e.target.value)}>
            {fixtures.map((f) => (
              <option key={f.name}>{f.name}</option>
            ))}
          </select>
        </label>
        <label>
          数字の上書き
          <input value={value} onChange={(e) => setValue(e.target.value)} placeholder="例: 12345" />
        </label>
        <label>
          <input type="checkbox" checked={countUp} onChange={(e) => setCountUp(e.target.checked)} />
          countUp
        </label>
        <button onClick={() => setRun((n) => n + 1)}>最初から</button>
      </div>
      <Stage key={`${name}-${run}-${value}-${countUp}`} scene={scene} />
    </div>
  );
}
