import { existsSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { BACKGROUND_NAMES, backgroundName, backgroundSrc } from "./background";

const ROOT = join(import.meta.dirname, "../../..");

describe("backgroundSrc", () => {
  it("datasets/ の全データセットに、背景画像が対応している", () => {
    const ids = readdirSync(join(ROOT, "datasets"))
      .filter((f) => f.endsWith(".yaml") && !f.startsWith("_"))
      .filter((f) => !f.endsWith(".draft.yaml"))
      .map((f) => f.replace(/\.yaml$/, ""));
    expect(ids).toHaveLength(14);
    for (const id of ids) {
      expect(backgroundSrc(id), id).not.toBeNull();
    }
  });

  it("対応する画像ファイルが public/bg/ に実在する", () => {
    for (const name of BACKGROUND_NAMES) {
      expect(existsSync(join(ROOT, "apps/web/public/bg", `${name}.webp`))).toBe(
        true,
      );
    }
  });

  it("データセットごとに期待どおりの画像を返す", () => {
    expect(backgroundName("accident")).toBe("drone");
    expect(backgroundName("flightplan")).toBe("drone");
    expect(backgroundName("akiya_sold")).toBe("home");
    expect(backgroundName("rental_fleet")).toBe("car");
    expect(backgroundName("naiko_route")).toBe("ship");
    expect(backgroundName("rail_bs")).toBe("train");
    expect(backgroundSrc("rail_km")).toBe("/bg/train.webp");
  });

  it("未知のデータセットは null(画像なし)", () => {
    expect(backgroundSrc("unknown")).toBeNull();
    expect(backgroundSrc("")).toBeNull();
    expect(backgroundSrc("example")).toBeNull();
  });
});
