import { describe, expect, it, vi } from "vitest";
import { createLikeSync } from "./likeSync";

const flush = () => new Promise((r) => setTimeout(r, 0));

describe("createLikeSync", () => {
  it("押した状態を送り、もう一度押すと取り消しを送る", async () => {
    const send = vi.fn().mockResolvedValue(undefined);
    const sync = createLikeSync(send, vi.fn());
    sync.request("v1", true);
    await flush();
    sync.request("v1", false);
    await flush();
    expect(send.mock.calls).toEqual([
      ["v1", true],
      ["v1", false],
    ]);
  });

  it("同じ状態は重ねて送らない(連打しても最後の状態だけ)", async () => {
    const send = vi.fn().mockResolvedValue(undefined);
    const sync = createLikeSync(send, vi.fn());
    sync.request("v1", true);
    sync.request("v1", true);
    sync.request("v1", false);
    sync.request("v1", true);
    await flush();
    await flush();
    expect(send.mock.calls).toEqual([["v1", true]]);
  });

  it("送信中に元の状態へ戻ったら、送信後に取り消しを送る", async () => {
    const send = vi.fn().mockResolvedValue(undefined);
    const sync = createLikeSync(send, vi.fn());
    sync.request("v1", true);
    sync.request("v1", false);
    await flush();
    await flush();
    expect(send.mock.calls).toEqual([
      ["v1", true],
      ["v1", false],
    ]);
  });

  it("taste.log で liked の動画は、いいねの取り消しだけを送る", async () => {
    const send = vi.fn().mockResolvedValue(undefined);
    const sync = createLikeSync(send, vi.fn());
    sync.seed("v1", true);
    sync.request("v1", true);
    await flush();
    expect(send).not.toHaveBeenCalled();
    sync.request("v1", false);
    await flush();
    expect(send.mock.calls).toEqual([["v1", false]]);
  });

  it("失敗したら、サーバー側の状態を通知する", async () => {
    const send = vi.fn().mockRejectedValue(new Error("x"));
    const onFail = vi.fn();
    const sync = createLikeSync(send, onFail);
    sync.request("v1", true);
    await flush();
    expect(onFail).toHaveBeenCalledWith("v1", false);
  });
});
