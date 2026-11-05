# 台本の段階の除外理由と型の選び方

- 日付: 2026-11-05
- Issue: #33
- 決定: 台本の段階の除外理由は `no_template` / `too_long` / `no_big_number`(`primary` も `fallback` も作れない)/ `decision:<id>`(noul の確率が `exclude_if_probability_above` を超えた)。型は、決定モデルの選択が埋められない型ならば、埋められる最初の型にする。組み立てたシーンがスキーマに合わないときは除外ではなく `SceneError`
