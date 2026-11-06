# UMAP は 5 本未満のとき SVD で代用し、sentence-transformers は任意の依存にする

- 日付: 2026-11-06
- Issue: #37
- 決定: 動画が 5 本未満なら UMAP の代わりに SVD の上位 2 軸を [0.05, 0.95] に収める。`n_neighbors` は min(15, n-1)。`local` の埋め込みに使う sentence-transformers は `--extra local` の任意依存にし、遅延 import する。
- 理由: UMAP は点が少ないと固有値分解で落ちる。sentence-transformers は torch を引くため、Azure だけ使う環境や CI に入れない。
