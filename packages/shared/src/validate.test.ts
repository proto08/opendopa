import { readdirSync, readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { validateScene } from "./validate";

const dir = new URL("../fixtures/", import.meta.url);
const load = (name: string) => JSON.parse(readFileSync(new URL(name, dir), "utf-8"));
const fixtures = readdirSync(dir).filter((f) => f.endsWith(".json"));

describe("フィクスチャ", () => {
  it("4つある", () => expect(fixtures).toHaveLength(4));
  it.each(fixtures)("%s は検証を通る", (name) => {
    expect(validateScene(load(name))).toMatchObject({ ok: true });
  });
});

// 検証が失敗すべき入力(pipeline/tests/test_scene_schema.py と同じ表)
const bad: [string, (s: any) => void][] = [
  ["headline 41字", (s) => (s.headline = "あ".repeat(41))],
  ["durationSec 14.9", (s) => (s.durationSec = 14.9)],
  ["durationSec 30.1", (s) => (s.durationSec = 30.1)],
  ["sparkline 13点", (s) => (s.sparkline = Array.from({ length: 13 }, (_, i) => ({ x: i, y: i })))],
  ["comments.style = red", (s) => (s.comments[0].style = "red")],
  ["map.type = line", (s) => (s.map = { type: "line" })],
  ["color = red", (s) => (s.color = "red")],
  ["wmChar 2文字", (s) => (s.wmChar = "機機")],
];

describe("不正なシーン", () => {
  it.each(bad)("%s は検証に失敗する", (_, mutate) => {
    const scene = load("accident-0001.json");
    mutate(scene);
    expect(validateScene(scene)).toMatchObject({ ok: false });
  });

  it("headline 40字ちょうどは通る", () => {
    const scene = load("accident-0001.json");
    scene.headline = "あ".repeat(40);
    expect(validateScene(scene).ok).toBe(true);
  });
});
