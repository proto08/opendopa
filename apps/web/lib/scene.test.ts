import type { Scene } from "@opendopa/shared";
import example from "@opendopa/shared/fixtures/accident-0001.json";
import { expect, it } from "vitest";

// pipeline と同じサンプルが、生成した TS の型に合うことを確かめる(型が合わなければ typecheck が落ちる)
it("シーンJSONのサンプルが Scene 型に合う", () => {
  const scene: Scene = example as Scene;
  expect(scene.videoId).toBe("accident-0001");
  expect(scene.lines.length).toBeGreaterThan(0);
});
