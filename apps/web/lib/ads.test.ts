import { describe, expect, it } from "vitest";
import { AD_EVERY, type Ad, buildSlots } from "./ads";
import type { FeedItem } from "./feedTypes";

const items = (n: number) =>
  Array.from({ length: n }, (_, i) => ({ videoId: `v${i}` }) as FeedItem);
const ads: Ad[] = [
  { id: "a", title: "", body: "", note: "", color: "#000" },
  { id: "b", title: "", body: "", note: "", color: "#000" },
];
const kinds = (n: number, every = 3) =>
  buildSlots(items(n), every, ads).map((s) =>
    s.kind === "ad" ? `ad:${s.ad.id}` : (s.item.videoId as string),
  );

describe("buildSlots", () => {
  it("every 本ごとに、次の動画の前へ広告を入れる", () => {
    expect(kinds(7)).toEqual([
      "v0",
      "v1",
      "v2",
      "ad:a",
      "v3",
      "v4",
      "v5",
      "ad:b",
      "v6",
    ]);
  });

  it("次の動画がないときは、末尾に広告を入れない", () => {
    expect(kinds(3)).toEqual(["v0", "v1", "v2"]);
  });

  it("広告は順に回る", () => {
    expect(kinds(10).filter((k) => k.startsWith("ad"))).toEqual([
      "ad:a",
      "ad:b",
      "ad:a",
    ]);
  });

  it("広告が空、または every が 0 以下なら差し込まない", () => {
    expect(buildSlots(items(6), 3, [])).toHaveLength(6);
    expect(buildSlots(items(6), 0, ads)).toHaveLength(6);
  });

  it("動画の順序は変わらない", () => {
    const videos = buildSlots(items(12), AD_EVERY, ads).flatMap((s) =>
      s.kind === "video" ? [s.item.videoId] : [],
    );
    expect(videos).toEqual(items(12).map((i) => i.videoId));
  });
});
