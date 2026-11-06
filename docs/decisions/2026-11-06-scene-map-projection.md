# 地図は等緯度経度の投影で描き、日本の輪郭は world-atlas(Natural Earth)の 50m から同梱する

- 日付: 2026-11-06
- Issue: #59
- 決定: 投影は等緯度経度(経度に cos(北緯36度) を掛ける)。輪郭は npm の `world-atlas@2.0.2` の `countries-50m.json` から日本(外周のみ・約0.15度未満の島は除く・座標は小数2桁)を `apps/web/lib/data/japan.json`(約15KB)に抜き出して同梱する(`apps/web/scripts/build-japan.mjs` で再生成)。自動ズームは、対象の外接矩形に18%の余白を足し、最小幅1.5度、viewBox(100x68)の縦横比に合わせる。航路の弧は弦の25%だけ画面上側にふくらむ2次ベジェ。
- 理由: 日本の範囲では歪みが小さく、計算が軽く、テストしやすい。ライブラリ(d3-geo など)を足さずに済む。world-atlas は ISC、元の Natural Earth はパブリックドメインのため、表記は必須ではないが、出典はここに残す。
