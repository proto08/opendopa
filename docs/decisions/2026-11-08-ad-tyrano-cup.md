# 広告の 1 件目をハックツハッカソン ~ティラノカップ~ の告知にする(#147)

- 日付: 2026-11-08
- Issue: #147
- 決定: `apps/web/lib/ads.ts` の `ADS` の 1 件目(サンプルの OpenDopa ハッカソン)を、ユーザーが用意したティラノカップ(2026-12-19〜20、グローバルアリーナ)の告知に差し替える。文面はハードコードで、2 件目(Project LINKS のサンプル)はそのまま。
- 理由: 実際に出したい告知を流し込んで、見た目と挙動をデモで確認するため。仕組み(差し込み位置・推薦の対象外)は [2026-11-07-feed-ads](2026-11-07-feed-ads.md) のまま変えない。
- 画像とテキストの配置: ユーザーが用意した `hack.webp`(1000x563)を `apps/web/public/ads/hack.webp` に置き、`Ad` に任意の `image` を足す。画面の上に画像、下にテキスト(「広告」バッジ・見出し・本文・補足・スキップボタン)を並べ、**文字と画像は重ねない**(最初は背景に敷いたが、読みにくいので分けた)。`public/` は Dockerfile が既にコピーしている。画像が 1 枚で固定なので `next/image` は使わない。
- 申込みリンク: `Ad` に任意の `link`(`href` と `label`)を足し、ティラノカップだけ「申込みはこちら」で https://hackz-community.doorkeeper.jp/events/200137 を指す。新しいタブで開く(`rel="noopener noreferrer"`)ので、フィードの位置や視聴の状態は変わらない。リンクのクリックは `/api/*` に送らない(広告は推薦に混ぜない)。
- 2 件目の広告: サンプルだった Project LINKS を、ユーザーが用意した「58ハッカソン」(2026-11-28〜29、京都工芸繊維大学)の告知に差し替えた。画像は `apps/web/public/ads/58.webp`(1280x727)、リンクは https://58hackathon.connpass.com/event/405339/。広告は ADS の順(ティラノカップ → 58 ハッカソン)で、動画 5 本ごとに回る。
- 3 件目の広告: 国土交通省主催の「LINKS:POWER of DATA x DATA 2026 ハッカソン」(2026-11-28〜29、麻布台ヒルズ 森JPタワー35階(予定))を足した。リンクは https://connpass.com/event/411586/。画像は最初なかったが、あとでユーザーが `links.webp`(中身は PNG)を用意したので `apps/web/public/ads/links.png` に置いて背景(上の画像)に使う。広告は ティラノカップ → 58 ハッカソン → LINKS の順に回る。
- 4 件目の広告: Progate の「Claude Code 入門」コースを足した。画像は `apps/web/public/ads/claude-course.webp`(ユーザーが用意)、リンクは https://progate.com/courses/feature/claude-code、ボタンの文言は日程がないコースなので「コースを見る」にした。広告は ティラノカップ → 58 ハッカソン → LINKS → Claude Code 入門 の順に回る。
- 5 件目の広告: Progate の「Rust」コースを足した。画像は `apps/web/public/ads/progate-rust.webp`(ユーザーが用意)、リンクは https://progate.com/courses/feature/rust、ボタンは「コースを見る」。広告の順は ティラノカップ → 58 ハッカソン → LINKS → Claude Code 入門 → Rust。
- 6 件目の広告: Progate の学割(プロプラン 75% OFF)の告知を足した。画像は `apps/web/public/ads/progate-hello.webp`(ユーザーが用意)、リンクは https://progate.com/blogs/student-discount-release-20261016、ボタンは「詳しく見る」。広告の順は ティラノカップ → 58 ハッカソン → LINKS → Claude Code 入門 → Rust → 学割。
- 7 件目の広告: Topa'z(エンジニアのインプット/アウトプットを可視化するサービス)の紹介を足した。画像は `apps/web/public/ads/topaz.webp`(ユーザーが用意)、リンクは https://topaz.dev/、ボタンは「Topa'z を見る」。広告の順は 学割 のあとに Topa'z。
