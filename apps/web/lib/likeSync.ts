// いいねの送信(設計書 §6.3)。`POST /api/like` には「押した」でなく「いまの状態」を送る。
// 同じ状態を重ねて送らない。送信中に押されたら、終わってから最後の状態だけを送る。

type VideoState = { confirmed: boolean; wanted: boolean; inflight: boolean };

export interface LikeSync {
  /** サーバーが知っている状態を覚える(押されたことがあれば上書きしない) */
  seed(videoId: string, liked: boolean): void;
  /** 利用者が望む状態を伝える。必要なときだけ送る */
  request(videoId: string, liked: boolean): void;
}

export function createLikeSync(
  send: (videoId: string, liked: boolean) => Promise<void>,
  /** 送信に失敗したとき、サーバー側の状態(画面を戻す先)を受け取る */
  onFail: (videoId: string, confirmed: boolean) => void,
): LikeSync {
  const states = new Map<string, VideoState>();
  const get = (id: string): VideoState => {
    let s = states.get(id);
    if (!s) {
      s = { confirmed: false, wanted: false, inflight: false };
      states.set(id, s);
    }
    return s;
  };

  const pump = (videoId: string): void => {
    const s = get(videoId);
    if (s.inflight || s.wanted === s.confirmed) return;
    const sending = s.wanted;
    s.inflight = true;
    send(videoId, sending).then(
      () => {
        s.inflight = false;
        s.confirmed = sending;
        pump(videoId);
      },
      () => {
        s.inflight = false;
        s.wanted = s.confirmed;
        onFail(videoId, s.confirmed);
      },
    );
  };

  return {
    seed(videoId, liked) {
      if (states.has(videoId)) return;
      const s = get(videoId);
      s.confirmed = liked;
      s.wanted = liked;
    },
    request(videoId, liked) {
      get(videoId).wanted = liked;
      pump(videoId);
    },
  };
}
