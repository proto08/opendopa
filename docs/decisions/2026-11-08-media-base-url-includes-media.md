# `MEDIA_BASE_URL` には末尾の `/media` を含める

- 日付: 2026-11-08
- Issue: #175
- 決定: Azure に `publish` するときの `MEDIA_BASE_URL` は、`terraform output media_base_url` の値の末尾に `/media` を付けた値にする(例: `https://<account>.blob.core.windows.net/media`)。README の手順 4 もそうした。
- 理由: `publish` は音声の URL を `<MEDIA_BASE_URL>/<動画ID>/<n>.mp3` と組み立てる。音声ファイルは Blob の `media` コンテナにあるので、実際の URL は `<アカウント直下>/media/<動画ID>/<n>.mp3`。output の値をそのまま使うと `/media` が抜けて 400 になり、音声が鳴らない(2026-11-08 に発生、`/media` を付けて `publish` し直して解消)。ローカルの `http://localhost:3000/media` も、同じく `/media` を含む形で揃っている。CDN(Front Door)でも `/media/*` はそのまま `media` コンテナへ渡るので、同じ扱いになる。
