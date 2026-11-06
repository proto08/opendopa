// 行ごとの音声の再生(設計書 §8.8)。React にも DOM にも依存しない(Audio は差し替えられる)。

export type AudioLike = {
  play(): Promise<void> | void;
  pause(): void;
};

export type CreateAudio = (url: string) => AudioLike;

const defaultCreate: CreateAudio = (url) => new Audio(url);

/**
 * いま表示中の行の音声を 1 つだけ鳴らす。
 * `sync` に「鳴らす URL(なければ null)」「行・周回が変わったら変わる鍵」「一時停止中か」を渡す。
 * - 鍵か URL が変わると、前の音声を止めて、新しい音声を頭から鳴らす(行が進む・ループ)
 * - 一時停止で止め、再開で続きから鳴らす(鳴らし直さない)
 * - URL が null(音声なし・画面から外れた)なら止める
 */
export class LineAudio {
  private audio: AudioLike | null = null;
  private current: { url: string; key: string } | null = null;

  constructor(private readonly create: CreateAudio = defaultCreate) {}

  sync(url: string | null, key: string, paused: boolean): void {
    if (url === null) {
      this.stop();
      return;
    }
    if (
      this.audio === null ||
      this.current?.url !== url ||
      this.current.key !== key
    ) {
      this.stop();
      this.audio = this.create(url);
      this.current = { url, key };
    }
    if (paused) this.audio.pause();
    else this.play(this.audio);
  }

  stop(): void {
    this.audio?.pause();
    this.audio = null;
    this.current = null;
  }

  private play(audio: AudioLike): void {
    try {
      // 自動再生がブラウザに止められたときは、無音で字幕だけ進める
      Promise.resolve(audio.play()).catch(() => {});
    } catch {
      // 同期で投げる実装でも、字幕は止めない
    }
  }
}
