import { describe, expect, it, vi } from "vitest";
import {
  clampIndex,
  isEditableTarget,
  isLikeKey,
  keyAction,
  keyToDelta,
  observeActiveSlide,
} from "./feedNav";

describe("keyToDelta / clampIndex", () => {
  it("↓ と j は次へ、↑ と k は前へ", () => {
    expect(keyToDelta("ArrowDown")).toBe(1);
    expect(keyToDelta("j")).toBe(1);
    expect(keyToDelta("ArrowUp")).toBe(-1);
    expect(keyToDelta("k")).toBe(-1);
    expect(keyToDelta("a")).toBe(0);
  });

  it("端で止まる", () => {
    expect(clampIndex(0, -1, 3)).toBe(0);
    expect(clampIndex(2, 1, 3)).toBe(2);
    expect(clampIndex(1, 1, 3)).toBe(2);
    expect(clampIndex(0, 1, 0)).toBe(0);
  });
});

describe("observeActiveSlide", () => {
  class MockObserver {
    static last: MockObserver;
    observed: Element[] = [];
    disconnect = vi.fn();
    constructor(
      readonly cb: (entries: never[]) => void,
      readonly options: { threshold: number[] },
    ) {
      MockObserver.last = this;
    }
    observe(el: Element) {
      this.observed.push(el);
    }
    unobserve() {}
  }
  const slide = (index: number) =>
    ({ dataset: { index: String(index) } }) as unknown as Element;
  const fire = (
    target: Element,
    isIntersecting: boolean,
    intersectionRatio: number,
  ) =>
    MockObserver.last.cb([
      { target, isIntersecting, intersectionRatio },
    ] as never[]);

  it("60% 以上で再生開始、外れると止める", () => {
    const onChange = vi.fn();
    const a = slide(0);
    const b = slide(1);
    const stop = observeActiveSlide(
      {} as Element,
      [a, b],
      onChange,
      MockObserver as never,
    );
    expect(MockObserver.last.options.threshold).toEqual([0.6]);
    expect(MockObserver.last.observed).toEqual([a, b]);

    fire(b, true, 0.6);
    expect(onChange).toHaveBeenLastCalledWith(1, true);
    fire(b, false, 0.59);
    expect(onChange).toHaveBeenLastCalledWith(1, false);
    fire(a, true, 0.5); // 閾値未満なら再生しない
    expect(onChange).toHaveBeenLastCalledWith(0, false);

    stop();
    expect(MockObserver.last.disconnect).toHaveBeenCalled();
  });
});

describe("isLikeKey / isEditableTarget", () => {
  it("l だけがいいねのキー", () => {
    expect(isLikeKey("l")).toBe(true);
    expect(isLikeKey("L")).toBe(false);
    expect(isLikeKey("j")).toBe(false);
  });

  it("DOM がない環境や要素でない対象は入力欄とみなさない", () => {
    expect(isEditableTarget(null)).toBe(false);
  });
});

describe("keyAction", () => {
  it("シートが閉じていれば、キーを操作に直す", () => {
    expect(keyAction("j", false)).toEqual({ type: "move", delta: 1 });
    expect(keyAction("ArrowUp", false)).toEqual({ type: "move", delta: -1 });
    expect(keyAction("l", false)).toEqual({ type: "like" });
    expect(keyAction("x", false)).toEqual({ type: "none" });
  });
  it("シート(検索を含む)が開いている間は、↑ ↓ j k l のどれも効かない", () => {
    for (const key of ["ArrowUp", "ArrowDown", "j", "k", "l"])
      expect(keyAction(key, true)).toEqual({ type: "none" });
  });
});
