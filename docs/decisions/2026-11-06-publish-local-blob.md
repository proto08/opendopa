# ローカルの publish は --skip-blob で Blob を飛ばす(Azurite は足さない)

- 日付: 2026-11-06
- Issue: #38
- 決定: docker-compose に Azurite は足さない。ローカルでは `--skip-blob` を付ける。`--skip-blob` なしで `STORAGE_CONNECTION_STRING` が空ならエラーにする。DB だけでも画面は動く(シーンは `videos.scene` にある)。
- 理由: ハッカソンの時間内で、ローカルに足すサービスを増やさないため。Blob の書き込みはテストで SDK を差し替えて確かめる。
