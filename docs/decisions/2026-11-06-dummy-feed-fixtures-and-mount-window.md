# ダミー /api/feed は DB(なければフィクスチャ)から無作為に返し、フィードは前後 1 本だけ Stage を作る

- 日付: 2026-11-06
- Issue: #45
- 決定: ダミー `GET /api/feed` は、`DATABASE_URL` があれば `videos`(`status='ok'`)から `ORDER BY random()` で返し、接続失敗・空・スキーマ不正ならフィクスチャ 4 本から返す(`reason` は常に `explore_cold`)。フィードは、再生中の動画の前後 1 本だけ `Stage` を作り、離れたスライドは高さだけ確保する。60% 未満になった動画は `ScenePlayer.reset()` で一時停止し最初に戻す。
- 理由: 本物の `/api/feed`(#47)は同じ `items[]` の形のまま中身だけ差し替えればよい。見えていない動画の時計・コメント・音声を動かさないために、Stage を作る範囲を絞る。
- 補足(レビュー対応): window の基準は、スクロール途中で再生中が無い(`active === null`)間も「最後に再生中だった番号」(`anchor`)を使う。切り替えの途中で前後の Stage が外れて空白になるのを防ぐ。
- 補足(テスト方針): jsdom に `IntersectionObserver` が無いため、IntersectionObserver をモックしたコンポーネントテストは書かず、60% 判定を担う `observeActiveSlide` を単体でテストする。
