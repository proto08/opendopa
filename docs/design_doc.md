# OpenDopa 設計書(AI実装エージェント向け)

版: v1.0 / 作成: 2026-11-01 / 対象: 2026-11-07〜08 のハッカソンで動くものを完成させる

この文書は、読み手(AIの実装エージェント)が、人に質問せずに最後まで作り切れることを目的に書いた**設計書**。CSVの列に関わる部分(列定義YAML、テンプレート、データセット別の定義)は、別文書 `docs/data.md` にある。両方を読むこと。判断に迷ったら、この文書の「既定値」を採用し、`docs/DECISIONS.md` に1行で記録して先に進むこと。Issue 単位で決めた大きな判断は `docs/adr/` にある(`docs/DECISIONS.md` の先頭が索引)。

---

## 0. 読み方と実装の約束

### 0.1 読む順番

1. §1〜§3: 何を作るか(ゴール、決定事項、画面)
2. §4〜§7: 構成、データモデル、API、レコメンド
3. §8〜§9: コンテンツ生成の契約(原稿、シーン)。CSVの列に関わる部分(§8.3〜§8.6、§8.9、§10)は、`docs/data.md`
4. §11〜§13: 埋め込み、インフラ、タスク順序
5. §14〜§16: 受け入れ基準、安全、未決(既定値あり)

### 0.2 実装の約束(破ってはいけないこと)

- **元データにない事実を書かない。** 原稿に出る数字・日付・地名は、すべて元データの値、またはコードで機械的に計算した値(合計、順位、前年比など)であること。
- **原因・責任・被害の推測を書かない。** 元データに書かれていることだけを述べる。
- **単位は、厳密に確認しなくてよい。** 「要確認」とした列も、推定した単位で絶対値を読み上げてよい(§10の「単位」欄を参照)。ただし、推定が大きく外れそうな列(桁が極端に大きい、など)は、順位・前年比・割合を使う。
- **LLMを行ごとに呼ばない。** LLMを使うのは、データ種別ごとに1回(テンプレートの案づくり)と、クラスタ名・要約の生成だけ。実行時(ユーザーが見ている最中)には生成しない。
- **決定モデル(Jev系)には、文章も数字も作らせない。** あらかじめ並べた選択肢から「選ぶ」だけ。値の埋め込みは、すべてエンジンが元データから行う。決定モデルが失敗・低確信度のときは、ルールに戻す(§8.3a)。
- **ベクトル計算はRustで行う。DBの読み書きは、すべて Next.js(TypeScript)が行う。** Rust(recsys)は、状態を持たない計算サービスで、DBに書き込まない。Next.js(TypeScript)は、好みのベクトルの更新、近傍検索、地図上の位置の計算をしない(§7)。
- **個人を特定する情報を原稿に出さない。** 氏名、詳細な住所、負傷の部位など(§15)。
- **外部サービスは差し替え可能にする。** 埋め込み、音声、判断モデルはインターフェースの後ろに置く(§0.4)。
- 動くものを先に作る。まず事故データだけで、取り込みから画面表示までを通す(§13)。

### 0.3 用語

| 用語 | 意味 |
| --- | --- |
| データセット | 1つのCSV(またはGeoJSON)。§10に14個ある |
| 動画(video) | 1本のショート動画。実体は「シーンJSON + 音声ファイル」で、ブラウザが描画する(mp4は作らない) |
| シーン(scene) | 1本の動画の描画データ(§9) |
| 切り口(kind) | 動画の型。例: `event`(1件を紹介)、`stat`(数字の比較)、`geo`(地図) |
| 好みのベクトル `u` | ユーザーごとの、動画ベクトルと同じ次元のベクトル |
| 列定義 | データセットごとの、列の役割と使い方を書いたYAML(§8) |

### 0.4 差し替え点(インターフェース)

| 部品 | 既定の実装 | 代わりの実装 | 環境変数 |
| --- | --- | --- | --- |
| 埋め込み | Azure OpenAI `text-embedding-3-small`(`dimensions=1024`) | ローカルの `multilingual-e5-large`(1024次元) | `EMBED_PROVIDER=azure\|local` |
| 音声(TTS) | `none`(字幕のみ。最初はこれで通す)。採用は `voicevox` | `azure`(Azure AI Speech) | `TTS_PROVIDER=none\|azure\|voicevox` |
| 判断(決定モデル) | `rules`(全体を通すまで)。評価に合格したら `strands_azure`(Azure上で動かす Strands Decider 2B。失敗・低確信度のときは `rules`) | `jev_local`、`jev_api`(TypeSafe Jev)、`azure_openai`(構造化出力) | `DECIDER_PROVIDER=rules\|strands_azure\|jev_local\|jev_api\|azure_openai` |
| LLM(テンプレート案、クラスタ名) | Azure OpenAI のチャットモデル | なし(クラスタ名は機械的な名前にフォールバック) | `LLM_PROVIDER=azure\|none` |

ローカルの埋め込み(`EMBED_PROVIDER=local`)は `intfloat/multilingual-e5-large`(1024次元)に決定。入力の先頭に、動画の本文には `passage: `、検索文には `query: ` を付け、正規化したベクトルを保存する。Azure と次元(1024)が同じなので、DBの列は共通。ただし、モデルが違うため、**ベクトルを混ぜない**(切り替えたら全動画を埋め込み直す)。

`TTS_PROVIDER=none` のときの字幕のタイミングは、1秒あたり6.5文字で見積もる。

---

## 1. プロダクト概要

OpenDopa は、国土交通省 Project LINKS が公開するオープンデータのCSV 1行(または集計)を、ニュース風の縦型ショート動画に変えて見せるWebアプリ。非公式のネタアプリである。

- ユーザーは何も選ばず、縦にスクロールして動画を見るだけ。気に入れば、いいねを押せる。
- 動画から離れるときの**視聴時間**と、**いいね**だけが入力になる。そこから「好みのベクトル」を更新し、近い動画が出やすくなる。
- 画面の右側に、いまの好みが人に読める形で表示される(地図上の現在地、カテゴリ別の割合、一言の要約、視聴の記録)。これがデモの見せ場になる。
- 動画ごとのニコニコ動画風コメントが、画面を右から左へ流れる(事前生成の固定データで、投稿はできない)。

### 1.1 ゴール

1. 14個のデータセットから、ニュース風の動画(シーンJSON + 任意で音声)を事前生成する。
2. 縦スクロールのフィードで連続再生する。1本は15〜30秒。
3. 視聴時間といいねで好みのベクトルが動き、近い動画が出やすくなる。右側の表示で、それが見える。
4. 全部がAzure上で動く。インフラはTerraformのコードで再現できる。

### 1.2 非ゴール

- 閲覧時にその場で動画・原稿を生成すること
- mp4動画の書き出し(Remotion等)。映像はブラウザが描画する
- 生成AIによる写実的な映像
- ユーザーによるカテゴリ・CSVの選択、検索、コメント投稿、ログイン
- 他のユーザーのいいねの表示、いいね数のランキング(好みは本人にだけ見せる)
- 事故の原因分析や、安全対策を促す公式な情報提供
- Databricks(今回は使わない。取り込み・プロファイル・座標計算はローカルのPythonで行う)

---

## 2. 決定事項

| # | 決定 | 内容 |
| --- | --- | --- |
| D1 | 描画方式 | ブラウザで描く。サーバーは「シーンJSON + 音声」を配るだけ |
| D2 | 動画の長さ | 15〜30秒 |
| D3 | 流れるコメント | MVPに含める(事前生成、投稿なし) |
| D4 | 対象データ | 届いた14ファイル全部。残り6種類(計画書型)は、後から列定義を足して追加できる設計にする |
| D5 | 入力 | 閲覧時間といいね。ログインなし、匿名ID(Cookie) |
| D6 | 好みの表示 | 画面の右側(PC)、シート(スマホ)。要件であり、MVPに含める |
| D7 | 画面・BFF | Next.js(TypeScript, App Router)。画面と、BFF(Cookie、入力の検証、**DBの読み書きのすべて**、シーンJSONの整形)。ベクトル計算はしない |
| D8 | ホスティング | Azure Container Apps |
| D9 | IaC | Terraform(`azurerm` プロバイダー) |
| D10 | DB | Azure Database for PostgreSQL(Flexible Server) + pgvector |
| D11 | 配信 | Azure Blob Storage + CDN(Front Door)。音声とシーンJSONの置き場 |
| D12 | 原稿生成 | 列定義 + **完成した台本のテンプレート**(型ごとに数本、YAML) + 共通エンジン(Python)。型の選択は決定モデル、穴埋めはコード。行ごとにLLMを呼ばない |
| D13 | Databricks | 使わない |
| D14 | 判断モデル(Jev系) | **使う**。原稿生成で、どの型(テンプレート群)にするかを選ぶ(choice)ほか、安全チェック(noul)に使う(§8.3a)。ただし、全体を通すまでは `rules` で動かし、評価(§14.2b)に合格したら、Azure上で動かす Strands Decider 2B(`strands_azure`)に切り替える。配備先(GPU付きContainer Apps か Azure ML)とモデルの入手元・ライセンスは実装時に確認し、評価の結果は `docs/DECISIONS.md` に記録する |
| D15 | 音声 | **VOICEVOX**。最初は `none` で通し、あとから `voicevox` に切り替える。声(キャラクター)・速度・読み辞書は実装時に決める |
| D16 | 地図の背景 | 日本の輪郭をアプリに同梱する(Natural Earthを元にした公開データ。npmの`world-atlas`など) |
| D17 | ベクトル計算 | **Rustの別サービス(`services/recsys`)**。**状態を持たない計算サービス**で、Next.js から、イベントの履歴などを受け取り、好みの位置・割合と、次の動画を返す。DBには書き込まない(起動時に、動画の埋め込みを読み取りのみ)。Container Apps の内部サービス(§6.6) |

---

## 3. 画面仕様

以下が、UIの仕様(見た目と操作は、この節を正とする)。


### 3.0 デザイン指定

| 項目 | 指定 |
| --- | --- |
| 世界観 | ニュース番組の「速報」のテロップ。固い報道の見た目に、ニコニコ動画風のコメントを重ねる |
| 色 | 紺 `#0A1F3D`(背景)、紙 `#F4F6FA`(ロゴとテロップの帯)、赤 `#E5322D`(速報タブ、カテゴリ名、進行バー、いいねの塗り)、黄 `#FFD23F`(「AI生成」ラベル、好みの現在地、要約の帯)、シアン `#35D0E8`(大きな数字)、補助の文字 `#9db0c9`、罫線 `#1c3354`、ページの背景 `#030a14` |
| 書体 | 見出しと大きな数字: Dela Gothic One。本文: Noto Sans JP(400/500/700/900)。字幕とコメント: 白の太字(900)に、黒の縁取り(`text-shadow` で4方向に0.2cqw) |
| 寸法 | ステージは9:16。PCでは角丸18px。文字サイズは、ステージ幅に対する比率(CSSの `cqw`)で指定する: 大きな数字21cqw(桁が多いと14〜11.5cqw)、テロップの見出し4.7cqw、字幕3.9cqw、コメント4.6cqw、出典2.8cqw、右レールのボタン11cqw |
| 背景 | 上 `#0c274b` から下 `#07152b` の紺のグラデーション。白3.5%の細い斜め縞(115度)。カテゴリの透かし1文字を、右上に、105cqwの大きさ、カテゴリ色の14%の濃さで |
| 動き | 大きな数字のカウントアップ1.2秒(ease-out)。コメントは6〜8.5秒で右から左へ。一時停止アイコンは0.6秒で拡大して消える。好みの現在地の移動は0.7秒。`prefers-reduced-motion` では、点の移動とアイコンの動きを止める |
| 右パネル | 暗い配色(背景は紺、文字は白)。地図の背景は紺で、罫線は `#1c3354` |

### 3.1 レイアウト

- PC(幅900px以上): 左に動画ステージ(9:16、高さは最大880px)、右に「あなたの好み」パネル(幅380px)。
- スマホ(幅899px以下): ステージが画面いっぱい。右レールの「好み」ボタンで、下からシートが開く。

### 3.2 動画ステージ(縦スクロールのフィード)

- スクロールスナップ(1画面1動画)。ネイティブのスクロールで、↑↓、`j`/`k` キーでも次へ進める。
- 動画が60%以上見えたら、その動画の再生を開始する(IntersectionObserver)。
- 上端に進行バー(15〜30秒)。画面タップで一時停止/再開(中央に一時停止アイコンが一瞬出る)。`Space` でも同じ。
- 1画面の構成(上から):
  1. ロゴ「速報 OpenDopa NEWS」と、黄色のラベル「AI生成のフィクション風解説」(**常に表示、必須**)。
  2. 大きな数字(シアン色)。0から1.2秒でカウントアップする。単位とラベルが下に付く。
  3. 流れるコメント(右から左へ、7レーン、最大でレーンが空いているときだけ出す)。
  4. 下部のテロップ(白い帯に見出し、左に赤のカテゴリ名の縦書き)。
  5. 字幕(1行ずつ、台本の秒数に合わせて切り替える)。
  6. 出典「出典:{データ名} / 行 #{番号}」(**常に表示、必須**)。
- 背景には、カテゴリを表す大きな1文字の透かしを置く(例: 鉄、機、家、車、船)。

### 3.3 右レール(ステージの右端)

| ボタン | 動作 |
| --- | --- |
| いいね | 押すと赤く塗られる。もう一度押すと取り消し。`l` キーでも操作できる |
| 元データ | 元の1行を、下から出るシートで表示する(列名と値の表、データ名、行番号、「デモ用の仮データではなく元データの値」であること) |
| 好み(スマホのみ) | 好みパネルのシートを開く |
| 次へ | 次の動画へスクロールする |

シートが開いている間は、再生を止める。

### 3.4 好みパネル(右側)

上から順に表示する。

1. **地図**: 全動画を2次元に並べた散布図。カテゴリごとに色分け。見た動画は濃く、見ていない動画は薄く。再生中の動画は点線の輪で囲む。「いまの好み」は黄色の大きな点で、動くときに0.7秒のイージングで移動する。軌跡を点線で結ぶ。
2. **カテゴリ別の割合**(クラスタごとの横棒グラフ、%)。
3. **一言の要約**(黄色の帯): 例「あなたは「鉄道の収支」を最後まで見る人です」。
4. **最近の視聴**(最大6件): 見出し、出た理由(「最初の1本」「好みを探し中」「好みに近い」「冒険枠」)、視聴率、いいねの有無。

好みの計算は§7、API経由で更新後の値を受け取る。

### 3.5 コメントの運用ルール

- 事故データで**負傷者あり**の動画は、コメントを出さない(`comments: []`)。
- 事故データのそれ以外の動画は、落ち着いた内容のコメントだけ(「気をつけたい」「無事でよかった」など)。ふざけた言い方(「草」「ｗｗｗ」)は使わない。
- その他のデータは、軽い反応(「ほう」「数字えぐい」)も使ってよい。
- 1本あたり6〜12件、動画内の時刻つき。動画のIDを種にした乱数で決めるので、同じ動画は毎回同じコメントになる。

### 3.6 データの流れ

- 画面は、表示と操作だけを担当する。好みの計算は、サーバー側(Next.js → recsys)が行い、ブラウザは結果を受け取って描く。
- 次の動画は、`GET /api/feed` で取得する(1本先読み)。

---

## 4. システム構成と技術スタック

```
[事前バッチ(手元またはCI)]                          [実行時]
 data/raw/*.csv                                      ブラウザ(Next.js の画面)
   │  pipeline/ (Python)                                │ ↑
   ├─ profile / 取り込み・整形                           │ │ 動画: Blob + CDN(シーンJSON, 音声)
   ├─ scriptgen: 判断 → テンプレート → 穴埋め            ▼ │
   │    └─ 決定モデル(Jev系)が型を選ぶ              Next.js(BFF)── DBの読み書き ──┐
   ├─ embed(埋め込み)→ 2D座標 → クラスタ                │  events などを渡す         │
   ├─ tts(音声: 任意)                                   ▼  内部HTTP                  ▼
   └─ publish ─┬→ Blob(音声・シーンJSON)            recsys(Rust: 計算だけ)   PostgreSQL
               └→ PostgreSQL ◄─────────────── 起動時に埋め込みを読む(読み取りのみ) ┘
```

### 4.1 技術スタック

| 層 | 採用 |
| --- | --- |
| Web | Next.js 15 以降(App Router)、TypeScript、React、Tailwind CSS は使わず素のCSS(モックのCSSを移植) |
| BFF | Next.js Route Handlers(Node.js ランタイム)。Cookie、入力の検証、**DBの読み書きのすべて**(`pg`)、シーンJSONの整形。**ベクトル計算はしない** |
| ベクトル計算 | Rust(`services/recsys`)。axum + tokio。状態を持たず、DBに書き込まない(起動時に、埋め込みを読み取りのみ。sqlx)。Cargo workspace で、計算の核(`recsys-core`。axum・sqlx に依存しない)と、HTTP・DB の読み込み(`recsys-server`)の2つの crate に分ける |
| パイプライン | Python 3.13、`uv` で管理。CLI は Typer。`pandas`、`pydantic`、`pyyaml`、`umap-learn`、`scikit-learn`、`openai`(Azure用) |
| DB | PostgreSQL 16(Flexible Server)、拡張 `vector`(pgvector)。マイグレーションは `db/migrations/*.sql` を dbmate で実行 |
| IaC | Terraform(`azurerm` プロバイダー。バージョンを固定する) |
| CI/CD | GitHub Actions(Terraform と、コンテナのビルド・デプロイ) |
| 監視 | Application Insights |
| パッケージ管理 | pnpm(Web。workspace)、uv(Python)、Cargo(Rust) |
| ツールの管理 | mise(言語とツールのバージョン、環境変数、開発用のタスク)。commit 前のチェックは lefthook |
| lint・テスト | Rust: `cargo fmt`・`cargo clippy`・`cargo test`、Python: ruff・pytest、TS: ESLint・Vitest |

### 4.2 リポジトリ構成

```
opendopa/
├─ mise.toml                   # バージョン、環境変数(.env.local を読む)、タスク(mise run dev / infra-apply / deploy などの入口)
├─ lefthook.yml                # commit 前の軽いチェック
├─ .env.example                # 環境変数の一覧(§12.3)。実際の値は .env.local(git管理外)
├─ CLAUDE.md                   # 実装エージェント向けの案内
├─ .claude/                    # Claude Code の設定(settings.json、hooks)
├─ infra/                      # Terraform(main.tf, variables.tf, outputs.tf, modules/*)
├─ apps/web/                   # Next.js
│   ├─ app/                    # ページ、api/ 以下にRoute Handlers
│   ├─ components/             # Feed, Slide, TastePanel, CsvSheet, Map, Comments ...
│   └─ lib/                    # recsys-client.ts(Rustへの内部HTTP), db.ts, types.ts
├─ services/recsys/            # Rust(ベクトル計算。Cargo workspace。状態を持たない)
│   ├─ recsys-core/            # 計算の核(axum・sqlx に依存しない)
│   └─ recsys-server/          # 内部HTTP(axum)と、起動時のDBの読み込み(sqlx)
├─ pipeline/                   # Python
│   ├─ opendopa_pipeline/      # profile, ingest, scriptgen, embed, project, cluster, tts, publish
│   └─ tests/
├─ datasets/                   # データセット別の列定義YAML(§10)
│   ├─ accident.yaml  ...
├─ packages/shared/            # 共有の型。schema/*.json(JSON Schema)が正で、TS の型と pydantic のモデルはここから生成する
├─ db/migrations/              # DBのマイグレーション(素のSQL。dbmate)
├─ data/raw/                   # 元CSV(git管理外。§10のファイル名で置く)
└─ docs/
    ├─ adr/                    # Issue 単位の決定(ADR)
    ├─ decisions/              # 小さな決定(1決定1ファイル。一覧は mise run decisions-index)
    └─ DECISIONS.md            # 2026-11-05 までの小さな決定と、ADR の索引(以降は decisions/)
```

---

## 5. データモデル(PostgreSQL)

`EMBED_DIM` は 1024(既定)。マイグレーションで `vector(1024)` を作る。

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE datasets (
  id            text PRIMARY KEY,            -- 例: 'accident'
  label         text NOT NULL,               -- 例: '事故等報告'
  source_name   text NOT NULL,               -- 出典に出す名前
  wm_char       text NOT NULL,               -- 背景の透かし1文字
  color         text NOT NULL                -- 地図の点の色(#RRGGBB)
);

CREATE TABLE videos (
  id            text PRIMARY KEY,            -- 例: 'accident-0001'
  dataset_id    text NOT NULL REFERENCES datasets(id),
  kind          text NOT NULL,               -- 'event' | 'stat' | 'geo'
  category_name text NOT NULL,               -- テロップに出すカテゴリ名
  headline      text NOT NULL,
  duration_sec  real NOT NULL,               -- 15〜30
  scene         jsonb NOT NULL,              -- §9 のシーンJSON(音声URLを含む)
  csv_row       jsonb NOT NULL,              -- [[列名, 値], ...] 元データの表示用
  source_ref    text NOT NULL,               -- 例: '行 #12' または 'YEAR=2023 / 事業者名'
  search_text   text NOT NULL,               -- 埋め込みに使った文
  decisions     jsonb,                       -- 判断モデルの記録(§8.3a)。クライアントには配信しない
  status        text NOT NULL DEFAULT 'ok',  -- 'ok' | 'excluded'
  excluded_why  text,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE clusters (
  id        int PRIMARY KEY,
  name      text NOT NULL,
  color     text NOT NULL,
  centroid  vector(1024) NOT NULL,
  cx real NOT NULL, cy real NOT NULL          -- 地図上の重心(0〜1)
);

CREATE TABLE embeddings (
  video_id   text PRIMARY KEY REFERENCES videos(id),
  embedding  vector(1024) NOT NULL,           -- 長さ1に正規化済み
  x real NOT NULL, y real NOT NULL,           -- 地図の座標(0〜1)
  cluster_id int REFERENCES clusters(id),
  model      text NOT NULL
);
CREATE INDEX embeddings_hnsw ON embeddings USING hnsw (embedding vector_cosine_ops);  -- 任意(分析用)。recsys(Rust)は使わない(起動時に全件をメモリへ読む)

CREATE TABLE meta (key text PRIMARY KEY, value jsonb NOT NULL);
-- key='centroid': 全動画の重心ベクトル(好みの初期値)

-- 好みのベクトル u は保存しない。view_events と like_events から、recsys が毎回再生して作る(§7.3)。

CREATE TABLE impressions (               -- 配信した動画(見た動画の除外と、出た理由の記録)
  id         bigserial PRIMARY KEY,
  anon_id    text NOT NULL,
  video_id   text NOT NULL REFERENCES videos(id),
  reason     text NOT NULL,              -- 'first' | 'explore_cold' | 'near' | 'adventure'
  served_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (anon_id, video_id)
);

CREATE TABLE view_events (
  id          bigserial PRIMARY KEY,
  view_id     text NOT NULL UNIQUE,      -- クライアントが作るUUID(重複防止)
  anon_id     text NOT NULL,
  video_id    text NOT NULL REFERENCES videos(id),
  watched_sec real NOT NULL,
  ratio       real NOT NULL,             -- サーバーが計算(0〜1)
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE like_events (
  id          bigserial PRIMARY KEY,
  anon_id     text NOT NULL,
  video_id    text NOT NULL REFERENCES videos(id),
  liked       boolean NOT NULL,          -- true=いいね、false=取り消し
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON view_events (anon_id, created_at);
CREATE INDEX ON like_events (anon_id, created_at);
```

匿名IDは、サーバーが発行して `od_aid` Cookie(httpOnly, SameSite=Lax, 有効期間1年)に入れる。クライアントから受け取らない。

---

## 6. API仕様

すべて JSON。匿名IDは Cookie から取る(なければ発行する)。

この章は、ブラウザから見えるAPI(Next.js の BFF)。**DBの読み書きは、すべて Next.js が行う。ベクトルに関わる計算は、Rust の recsys に任せる**(§6.6)。Next.js は、Cookie と入力の検証を行い、DBから読んだ履歴を recsys に渡し、結果に、シーンJSON・CSV行を付けて返す。

### 6.1 `GET /api/feed?count=1&includeMap=0`

次の動画を返す。`count` は1〜3。初回は `count=2&includeMap=1`(現在の動画と、先読み1本)。

処理:
1. 匿名IDを確認する(Cookie。なければ発行する)。
2. DBから、そのユーザーの `events`(`view_events` と `like_events` を時刻順)、配信済みの動画ID(`impressions`)、直近に配信したデータセットを読む。
3. recsys に `POST /internal/feed` で渡し、選ばれた動画ID・理由・`taste`(位置と割合)をもらう(§6.6。選び方は§7.4)。
4. 選ばれた動画を `impressions` に記録し、動画IDから、シーンJSON・CSV行・出典を `videos` から読む。
5. `taste` に、要約文と視聴の記録を足して返す(§6.4)。地図(`includeMap=1`)は、DBの `embeddings` と `clusters` から作る。

レスポンス:
```jsonc
{
  "items": [
    { "videoId": "accident-0001", "reason": "first", "reasonLabel": "最初の1本",
      "scene": { /* §9 */ }, "csvRow": [["発生区分","事故"], ...], "sourceRef": "行 #1" }
  ],
  "taste": { /* §6.4 */ },
  "map": {                       // includeMap=1 のときだけ
    "points": [ { "videoId":"accident-0001", "datasetId":"accident", "x":0.31, "y":0.62, "clusterId":4 } ],
    "clusters": [ { "id":4, "name":"ドローンの接触事故", "color":"#FF7A59", "cx":0.31, "cy":0.62 } ]
  }
}
```

### 6.2 `POST /api/view`

動画から離れるときに送る(`navigator.sendBeacon` でも送れるよう、JSON本文のみで受ける)。

リクエスト:
```json
{ "viewId": "3b0f...uuid", "videoId": "accident-0001", "watchedSec": 14.3 }
```
処理: Next.js が、`view_events` に保存する(`viewId` が重複なら、保存せずに続ける。`ratio = min(1, watchedSec / duration_sec)` をここで計算)。続いて、そのユーザーの `events` を読み、recsys に `POST /internal/taste` で渡して `taste` をもらう。

レスポンス: `{ "taste": {...}, "logEntry": {"videoId","headline","reasonLabel","ratio","liked"} }`

検証: `videoId` が存在すること、`watchedSec` が0以上で `duration_sec * 10` 以下であること。外れたら400。

### 6.3 `POST /api/like`

リクエスト: `{ "videoId": "accident-0001", "liked": true }`(トグルでなく状態を送る。同じ内容を2回送っても二重に足さない)。

処理: Next.js が、`like_events` に追加する。続いて、そのユーザーの `events` を読み、recsys に `POST /internal/taste` で渡して `taste` をもらう。

### 6.4 `taste` オブジェクト

```jsonc
{
  "x": 0.32, "y": 0.69,                       // 地図上の「いまの好み」(0〜1)。recsys が計算
  "shares": [ { "clusterId": 4, "name": "…", "color": "#…", "pct": 41 } ],  // 合計100
  "summary": "あなたは「…」を最後まで見る人です",
  "eventCount": 7,
  "log": [ { "videoId","headline","reasonLabel","ratio","liked" } ]          // 新しい順、最大6件
}
```

`x`、`y`、`shares` は recsys が計算する。`name`、`color`、`summary`、`eventCount`、`log` は、Next.js が、DB(`clusters`、`view_events`、`like_events`、`videos`)から作る。

### 6.5 共通

- エラーは `{ "error": "message" }` と適切なHTTPステータス。
- `/api/*` はすべて `Cache-Control: no-store`。
- 簡単なレート制限(匿名IDごとに1秒あたり10リクエスト)を入れる。

---

### 6.6 内部API(Next.js → recsys)

recsys は、Container Apps の**内部のみ**(外部に公開しない)のサービスで、**状態を持たず、DBに書き込まない**。ヘッダー `X-Internal-Token`(環境変数 `INTERNAL_TOKEN`)で認証する。リクエストで渡された `events` などだけを使って計算し、結果を返す。

`events` は、そのユーザーの視聴といいねを時刻順に並べた配列。

```jsonc
[ {"type":"view", "videoId":"accident-0001", "ratio":0.72},
  {"type":"like", "videoId":"accident-0001", "liked":true},
  {"type":"like", "videoId":"accident-0001", "liked":false} ]   // 取り消しは、同じ動画の後ろの liked=false(§7.3)
```

| メソッド・パス | 送る | 返す |
| --- | --- | --- |
| `POST /internal/feed` | `{events, seenIds, recentDatasets, count}` | `{picks:[{videoId, reason}], seenReset, taste:{x, y, shares:[{clusterId, pct}]}}` |
| `POST /internal/taste` | `{events}` | `{taste:{x, y, shares:[{clusterId, pct}]}}` |
| `POST /internal/reload` | なし | 動画の索引を、DBから読み直す(公開のあとに呼ぶ) |
| `GET /healthz` | なし | 200(索引の件数を含む) |

- `seenIds`: 配信済みの動画ID。`recentDatasets`: 配信済みのデータセットを新しい順に。
- `seenReset`: 未視聴が尽きたので、`seenIds` を空として扱って選んだ印。`true` なら Next.js が、そのユーザーの `impressions` を削除する(recsys は書き込まない。ADR-0040 A1)。
- `reason` は `first` / `explore_cold` / `near` / `adventure`。表示名(`reasonLabel`)は Next.js が付ける。
- 最初の数本を偏らせる判断の `eventCount` は、`events` のうち `view` の数。
- recsys は、起動時と `reload` のときだけ、DBから、`embeddings`(ベクトル・地図の座標)、`clusters`、`meta`(`key='centroid'`。好みの初期値 `u0`、§7.2)、`videos`(`id`、`dataset_id`、`status`)を**読み取りのみ**で全件読み込む。接続は、読み取り専用のロール(環境変数 `RECSYS_DATABASE_URL`)。
- 動画のシーンJSON・CSV行・地図のデータは、recsys は扱わない(Next.js が、DBから直接読む)。



## 7. レコメンドの仕様

**実装は Rust(`services/recsys`)。Next.js(TypeScript)では計算しない。** recsys は、状態を持たない計算サービスで(§6.6)、渡された `events` から好みのベクトル `u` を毎回作り直し、次の動画と、右パネルの値を返す。`u` は保存しない。更新式、取り消し、選び方は、この章に書いた規則のとおりに実装する。

### 7.1 定数(既定値。`services/recsys/recsys-core/src/config.rs` にまとめる)

| 名前 | 値 | 意味 |
| --- | --- | --- |
| `WATCH_NEUTRAL` | 0.4 | この視聴率が「普通」。これより長ければ好き、短ければ嫌い |
| `ALPHA_POS` | 0.5 | 視聴率100%のときに、好みを動画へ近づける量 |
| `ALPHA_NEG` | 0.3 | 視聴率0%のときに、好みを動画から遠ざける量 |
| `ALPHA_LIKE` | 0.6 | いいねで近づける量 |
| `TOPK` | 20 | 近傍候補の数 |
| `TAU` | 0.05 | 候補から確率で選ぶときの温度(コサイン類似度に対して) |
| `EXPLORE` | 0.18 | 冒険枠の確率 |
| `COLD_START_N` | 3 | 最初のN本は、全データセットから偏らず選ぶ |
| `MAX_STREAK` | 2 | 同じデータセットが連続できる最大数 |
| `TAU_MAP` | 0.05 | 地図上の現在地を出すときの温度 |

この値で確定する。問題が出たら、疑似ユーザーのテスト(§14.2)をもとに、あとから調整する。調整しやすいよう、すべて設定ファイルから読む形にする。

### 7.2 視聴による更新

`u0` は `meta.centroid`(全動画の重心。長さ1に正規化)。ベクトルはすべて長さ1。

```
r  = min(1, watchedSec / duration_sec)
w  = clamp((r - WATCH_NEUTRAL) / (1 - WATCH_NEUTRAL), -1, 1)    # r=1 で +1、r=0 で約 -0.67
a  = (w >= 0) ? ALPHA_POS * w : ALPHA_NEG * w                   # a<0 は遠ざかる
u  = normalize(u + a * (v - u))
```


### 7.3 いいね、取り消し

```
like(true):   u = normalize(u + ALPHA_LIKE * (v - u))
like(false):  いいねを取り消し、そのユーザーの全イベントを時刻順に再生して u を作り直す
```

再生は、`u = u0`(全動画の重心)から始め、渡された `events`(`view` と `like`)を、先頭から順に適用する。同じ動画の `like` は、**最後のイベントが `liked=true` のときだけ**有効にする(後ろの `liked=false` で、取り消される)。件数は数十〜数百なので、毎回、最初から再生してよい。`u` を保存しないので、保存した値と食い違うことがない。

いいねが有効になるのは、その動画の**最後の `like` の位置**で 1 回だけである(例: `like(true)`、`view`、`like(false)`、`like(true)` のときは、最初の `like` の位置では適用せず、最後の位置で適用する)。

### 7.4 次の動画の選び方

```
function pickNext(anon, u, eventCount, lastDatasets):
  unseen = videos where status='ok' and id not in impressions(anon)
  if unseen is empty: seenIds を空として扱って全体から選び直し、seenReset=true を返す(Next.js が impressions を削除する)
  if eventCount < COLD_START_N:
      データセットごとに1本ずつ順に(まだ出ていないデータセットから)ランダムに選ぶ。reason='explore_cold'
  elif random() < EXPLORE:
      類似度が unseen の下位半分から、直前と違うデータセットを優先して一様に選ぶ。reason='adventure'
  else:
      cand = メモリ上の全動画との内積(総当たり)で、u に近い unseen の上位 TOPK(sim = u・v)
      p_i ∝ exp(sim_i / TAU)  で確率的に選ぶ。reason='near'
  同じデータセットが MAX_STREAK 回連続していたら、別のデータセットの候補から選び直す
  最初の1本(impressions が空)は reason='first'。
```

`reasonLabel`: first=「最初の1本」、explore_cold=「好みを探し中」、near=「好みに近い」、adventure=「冒険枠」。

起動時に `embeddings` を全件メモリに読み込む(2,100本×1024次元で約8.6MB)。総当たりの内積で、1回の `pick_next` は約1.6ms、`taste_position` は約1.6ms(手元の実測。1スレッド、releaseビルド)。pgvectorの近傍検索は使わない。動画を公開したあとは、`POST /internal/reload` で読み直す。

### 7.5 好みパネルの値の計算

```
sim_i   = u · v_i                        # 全動画
w_i     = softmax(sim_i / TAU_MAP)
x, y    = Σ w_i * (x_i, y_i)             # 地図上の「いまの好み」
share_k = softmax(u · centroid_k / TAU)  # クラスタごとの割合(合計を100%に丸める)
summary = eventCount == 0 ? 'まだ見ていないので、好みはわかりません'
        : max(share) >= 40% ? 'あなたは「{クラスタ名}」を最後まで見る人です'
        : '好みはまだ決まっていません。いろいろ見ています'
```

動画数は数千までなので、全動画の総当たりでよい。

---

## 8. コンテンツ生成パイプライン(`pipeline/`)

全データセットを、同じエンジンで処理する。データセットごとの違いは `datasets/<id>.yaml` に集める。

### 8.1 コマンド

```
uv run opendopa profile  --dataset <id>        # 列のプロファイルを出す(列ごとの欠損率、種類数、最長の文字数、役割の推定、上位の値)
uv run opendopa generate --dataset <id>        # 選定→原稿→シーン→検証→ out/<id>/scenes.jsonl
uv run opendopa decide   --dataset <id> --eval datasets/<id>.labels.csv   # 判断モデルの評価(人が付けた正解との一致率)
uv run opendopa embed                          # 全動画の埋め込み・2D座標・クラスタ
uv run opendopa tts      --dataset <id>        # 音声(TTS_PROVIDER が none ならスキップ)
uv run opendopa publish                        # Blob とDBへ書き込む
uv run opendopa all                            # 上を順に
```

### 8.2 処理の流れ(`generate`)

1. **読み込み**: 文字コード(UTF-8 BOM付き)を処理し、列名の揺れを直す(YAMLの `rename`)。数値の `0` を欠損として扱う列を指定できる。
2. **クリーニング**: 欠損、外れ値、除外条件(YAMLの `filters`)で行を落とす。落とした行は理由つきで `out/<id>/excluded.csv` に記録。
3. **集計の追加**: YAMLの `stats` で、順位、前年比、合計などを計算して列に足す(§8.5)。
4. **選定**: `select`(§8.4)で、動画にする行を絞る。
5. **判断**: `decisions`(§8.3a)を行ごとに実行し、どの型のテンプレートにするかを決める(決定モデル)。安全チェックもここで行う。結果は `decisions` に記録する。
6. **原稿**: `template_groups`(§8.3)から、選ばれた型の中で、埋められて長さに収まるテンプレートを選び、穴に値を入れる(§8.3.1)。
7. **シーン**: 原稿、大きな数字、地図、コメントをまとめたシーンJSON(§9)にする。
8. **検証(品質ゲート)**: §8.6。通らない行は `excluded`。
9. 出力: `out/<id>/scenes.jsonl`、`out/<id>/decisions_report.json`、除外の記録。

### 8.3〜8.6 CSVから台本を作る仕組み(列定義YAML、テンプレート、判断ポイント、選定、集計、品質ゲート)

CSVの列に関わるこの部分は、別文書 **`docs/data.md`** の §8.3〜§8.6(と §8.9、§10)にある。本書でも、これらの節番号(§8.3、§8.3a、§8.5、§8.6、§8.9、§10.x)は、そのまま使う。この設計書に書くのは、次の**契約**だけ。

- 入力: `data/raw/<dataset_id>/` の元ファイル、`datasets/<dataset_id>.yaml`(列定義YAML)。
- 出力: シーンJSON(§9)を1行1本で並べた `out/<dataset_id>/scenes.jsonl`、除外した行と理由、判断の記録(`decisions_report.json`)。
- 原則: LLMを行ごとに呼ばない。台本は、型ごとのテンプレートに値を入れて作る。どの型にするかは、決定モデルが選ぶだけ。決定モデルが使えなければ、ルールに戻る(§0.2)。
- 品質ゲート: 未置換の穴、数字の不一致、長さ(15〜30秒)、個人情報、禁止表現、重複を機械で検査し、通らない行は理由つきで除外する。

### 8.7 読み上げ用の整形(TTSを使う場合)

字幕は元の表記のまま。TTSに渡す文だけ、`pipeline/tts_dict.yaml` の読み替え(例: `無人航空機 → むじんこうくうき`、事業者名・地名の読み)を適用する。辞書にない語は、そのまま渡す。

### 8.8 音声(TTS)

- 1行(字幕1つ)ずつ別のファイルに合成する(例: `audio/<video_id>/<n>.mp3`)。長さを測って、シーンの `lines[i].audio` に入れる。
- `TTS_PROVIDER=none` のときは音声ファイルを作らない。字幕の秒数は1秒6.5文字で見積もる。
- VOICEVOXを使う場合は、キャラクターごとの利用規約とクレジット表記(「VOICEVOX:キャラ名」)を、フィードの下部かフッターに出す。

---

## 9. シーンJSON(ブラウザが描画するデータ)

`packages/shared/schema/` に JSON Schema を置き、これを正とする。TypeScript の型と pydantic のモデルは、ここから生成する(`mise run gen-types`。生成したファイルは commit する)。パイプラインはこの形で出力し、Webはこの形だけを読む。

```jsonc
{
  "videoId": "accident-0001",
  "datasetId": "accident",
  "kind": "event",                       // 'event' | 'stat' | 'geo'
  "categoryName": "ドローン事故",
  "wmChar": "機",
  "color": "#FF7A59",
  "headline": "山梨県で無人航空機が事故",   // テロップの見出し(短く。40字以内)
  "bigNumber": { "value": 1, "text": "山梨県で1件目", "unit": "", "label": "報告された事故等", "countUp": false },
  "lines": [                              // 字幕と読み上げの単位
    { "text": "2022年12月6日11時20分、山梨県北杜市で、無人航空機の事故が報告されました。",
      "speak": "…",                       // TTS用(辞書適用後)。なければ text を使う
      "audio": { "url": "https://cdn/.../accident-0001/0.mp3", "durationSec": 6.2 },   // なければ null
      "durationSec": 6.2 }                // 音声がなければ文字数/6.5 の見積もり
  ],
  "durationSec": 24.8,                    // lines の合計。15〜30
  "map": null,                            // §9.1。地図がなければ null
  "sparkline": null,                      // [{x,y}...] 12点以内。なければ null
  "chips": [],                            // 特徴の小さなラベル(例: ["夜間","目視外"])
  "comments": [ { "t": 3.2, "text": "気をつけたい", "style": "normal" } ],   // style: 'normal'|'yellow'
  "source": { "datasetName": "無人航空機の事故等報告", "ref": "行 #1" },
  "numbers": [ ]                          // 検証用の記録(配信時は不要。DBには残す)
}
```

### 9.1 地図(`map`)

```jsonc
{ "type": "route",   "from": {"name":"仙崎","lat":34.4,"lon":131.2}, "to": {"name":"七尾","lat":37.0,"lon":137.0} }
{ "type": "polygon", "rings": [[[lon,lat],...]], "markers": [{"name":"出発","lat":..,"lon":..}] }
{ "type": "points",  "points": [{"name":"沖縄県","lat":..,"lon":..,"size":0.8}] }
```

描画: 日本の輪郭(同梱データ)を薄く描き、その上に弧(航路)、塗りつぶし(範囲)、点を重ねるSVG。範囲は対象の外接矩形に合わせて自動でズームする。

### 9.2 描画の規則(Webの責務)

- 字幕は `lines[i]` を順に出す(各 `durationSec`)。全行が終わったらループして、数字は固定、進行バーは0に戻す。
- コメントは `comments[i].t`(動画内の秒)に出す。ループ時も同じ時刻に出る。
- 大きな数字は `countUp` が true で `value` が数のとき、0から1.2秒で `value` までカウントアップ(桁区切り表示)。
- 数字の桁数が多いときは、フォントサイズを小さくして、はみ出さないようにする(モックの `fontSize` の分岐を参照)。
- 一時停止のときは、字幕、コメント、カウント、音声を止める。

---

## 10. データセット別の定義

データセット(14ファイル)ごとの、**列の使い方、クリーニング、動画の切り口、注意点**は、別文書 **`docs/data.md`** に書く。この設計書は、データの中身に依存しない。新しいデータセットは、`docs/data.md` に節を足し、`datasets/<id>.yaml` を作る。

### 10.0 一覧

| ID | ファイル | 行数 | 1行の単位 | grain | 切り口(kind) |
| --- | --- | --- | --- | --- | --- |
| `accident` | `02_jikojyouhou.csv` | 194 | 事故1件 | row | event |
| `flightplan` | `01_hikoukeikaku.geojson` | 100(サンプル) | 飛行計画1件 | row | geo |
| `akiya_reg` | `01_tourokubukken.csv` | 32,173 | 登録物件1件 | row | event |
| `akiya_sold` | `02_seiyakubukken.csv` | 16,978 | 成約物件1件 | row | event |
| `rental_result` | `01_yousiki1_kashiwatashijissekihoukokusho.csv` | 1,050 | 事業者×年度(匿名) | group | stat |
| `rental_fleet` | `02_yousiki2_haisyasyaryousuu.csv` | 2,564 | 営業所 | group | stat |
| `naiko_route` | `02_naikousenpakuyusoutoukeichousa.csv` | 47,510 | 航路×年 | row | geo |
| `naiko_ship` | `01_naikoukaiungyou_jigyougaikyouhoukoku.csv` | 2,710 | 船1隻 | row | event |
| `rail_traffic1` | `01_tetsudou_unyuseiseki1.csv` | 4,022 | 事業者×年度 | row | stat |
| `rail_traffic2` | `02_tetsudou_unyuseiseki2.csv` | 3,988 | 事業者×年度 | row | stat |
| `rail_km` | `03_tetsudou_eigyoukiro.csv` | 4,215 | 事業者×年度 | row | stat |
| `rail_pl` | `04_tetsudou_eigyousoneki.csv` | 2,773 | 事業者×年度(鉄道事業) | row | stat |
| `rail_income` | `05_tetsudou_sonekikeisansyo.csv` | 2,523 | 会社×年度 | row | stat |
| `rail_bs` | `06_tetsudou_taisyakutaisyouhyou.csv` | 2,525 | 事業者×年度 | row | stat |

全データセットの合計は動画の上限150×14=約2,100本。

---

## 11. 埋め込み・地図・クラスタ(`embed` コマンド)

実行時のベクトル計算は Rust(§7)。オフラインの処理(埋め込み、UMAP、KMeans)は、ライブラリの都合で Python(パイプライン)のままにする(決定)。

### 11.1 検索用の文(`search_text`)

原稿そのものでなく、データごとの `embed_text` テンプレートで作る(同じカテゴリの原稿が似すぎて、ベクトルが塊にならないようにする)。含める要素:
- データセットのラベル、切り口
- 地域(都道府県)、種別、区分
- 概要の最初の1文(あれば)
- 数値の区分を言葉にしたもの(例: 「大規模」「小規模」「黒字」「赤字」「前年より増加」)

### 11.2 手順

1. 全動画の `search_text` を埋め込み、長さ1に正規化する。1024次元。Azureなら `dimensions=1024` を指定。
2. 全体の重心を `meta.centroid` に保存する(長さ1に正規化)。
3. UMAP(`n_neighbors=15, min_dist=0.1, metric='cosine', random_state=42`)で2次元にし、各軸を0.05〜0.95に収める。
4. KMeans(`k=12`(決定。`embed` の引数で変えられる)、`random_state=42`)で、元のベクトルをクラスタに分ける。`clusters.centroid` は各クラスタの重心(正規化)、`cx, cy` は所属動画の座標の平均。
5. クラスタ名: 各クラスタから、重心に近い動画8本の見出しとデータ名をLLMに渡し、「12文字以内の日本語の名詞句」を1つ作らせる(`LLM_PROVIDER=none` のときは「{主なデータ名}の{最頻の地域・種別}」と機械的に付ける)。
6. クラスタの色は、所属動画で最多のデータセットの色を使う。

動画の本数を増やしたら、`embed` を全体でやり直す(座標とクラスタが変わるため、本番では一括で入れ替える)。

---

## 12. インフラ(Azure)とIaC

### 12.1 リソース

| リソース | 用途 |
| --- | --- |
| リソースグループ | すべてをまとめる(名前に環境名を含める) |
| Log Analytics + Application Insights | ログと監視 |
| Container Registry | Webコンテナの置き場 |
| Container Apps Environment + Container App | Next.js(`web`)。最小レプリカ1、スケールアウトは最大3 |
| Container App(recsys) | Rust の `recsys`。**内部のみ**(外部に公開しない)。最小レプリカ1(起動時に全動画をメモリへ読み込む) |
| PostgreSQL Flexible Server | DB。拡張 `vector` を許可する(`azure.extensions` に `VECTOR`) |
| Storage Account(Blob) | 公開コンテナ `media`(音声)と `scenes`(シーンJSON) |
| Front Door(または Azure CDN) | `media`/`scenes` の配信 |
| Azure OpenAI | 埋め込み、チャットのデプロイ(§0.4)。利用可能なモデル名・地域は、実装時に確認 |
| 判断モデルの配備先(GPU付きContainer Apps、またはAzure ML) | `DECIDER_PROVIDER=strands_azure` のとき。Strands Decider 2B を動かす。**内部のみ** |
| Azure AI Speech | `TTS_PROVIDER=azure` のとき(VOICEVOX採用のため、既定では不要) |
| Key Vault(任意) | 接続文字列とキー |

地域は、日本の東(Japan East)に決定。モデル名は実装時に確認し、`infra/main.parameters.json` で指定する。サービスが使えない地域は、次の候補を選んでよい(記録する)。

### 12.2 Terraform の構成

- 構成は `infra/` に置く。ルートは `main.tf`、`variables.tf`、`outputs.tf`、`providers.tf`、`versions.tf`。リソースはモジュールに分ける(`modules/postgres`, `containerapp`, `storage`, `cdn`, `openai`, `speech`, `monitoring`, `registry`)。
- プロバイダーは `hashicorp/azurerm`。実装時に最新の安定版を選び、`versions.tf` で固定する(この文書ではバージョンを固定しない)。
- **状態(state)** は、Azure Storage のBlobに置く(`backend "azurerm"`)。バックエンド用のStorage Accountは、最初の1回だけ手動(またはブートストラップ用の小さなスクリプト)で作る。
- 環境は変数 `env_name`(例: `dev`)で分け、リソース名に含める。`terraform.tfvars` はコミットしない(`terraform.tfvars.example` を置く)。
- 主なリソースの対応(実装時に、各リソースの引数をプロバイダーのドキュメントで確認する):

| 用途 | Terraform のリソース |
| --- | --- |
| リソースグループ | `azurerm_resource_group` |
| ログ、監視 | `azurerm_log_analytics_workspace`, `azurerm_application_insights` |
| コンテナレジストリ | `azurerm_container_registry` |
| Container Apps の環境とアプリ | `azurerm_container_app_environment`, `azurerm_container_app` |
| recsys のアプリ | `azurerm_container_app`(ingress は `external_enabled = false`) |
| PostgreSQL | `azurerm_postgresql_flexible_server`, `azurerm_postgresql_flexible_server_database`, `azurerm_postgresql_flexible_server_configuration`(`azure.extensions` に `VECTOR` を許可) |
| Blob と配信 | `azurerm_storage_account`, `azurerm_storage_container`, `azurerm_cdn_frontdoor_profile` ほか |
| Azure OpenAI | `azurerm_cognitive_account`(kind: `OpenAI`)、`azurerm_cognitive_deployment`(埋め込みとチャット) |
| Azure AI Speech | `azurerm_cognitive_account`(kind: `SpeechServices`) |
| 秘密の値(任意) | `azurerm_key_vault`, `azurerm_key_vault_secret` |

- `CREATE EXTENSION vector;` は、Terraform ではなく、アプリのDBマイグレーション(`db/migrations/`、dbmate)で実行する。
- アプリのデプロイは、Terraformとは分ける。`docker build` で作ったイメージをレジストリに送り、`azurerm_container_app` のイメージのタグ(変数 `web_image_tag`)を更新して `terraform apply`、またはCIで `az containerapp update` を使う。どちらを使うかは、`docs/DECISIONS.md` に記録する。
- 入口は mise のタスク: `mise run infra-init`, `mise run infra-plan`, `mise run infra-apply`, `mise run deploy`(ビルドからデプロイまで)。
- `terraform output` で、URL、DB接続先、Storageの名前などを取り出せるようにする(秘密の値は `sensitive = true`)。

### 12.3 環境変数

| 名前 | 用途 |
| --- | --- |
| `DATABASE_URL` | PostgreSQL接続文字列 |
| `MEDIA_BASE_URL` | CDNのベースURL |
| `RECSYS_URL`, `INTERNAL_TOKEN` | Next.js から recsys への内部HTTP(URLと共有トークン)。recsys 側にも `INTERNAL_TOKEN` |
| `RECSYS_DATABASE_URL` | recsys が、起動時に埋め込みを読むための、**読み取り専用**のDB接続(Next.js の `DATABASE_URL` とは別のロール) |
| `EMBED_PROVIDER`, `EMBED_DIM` | §0.4 |
| `TTS_PROVIDER`, `LLM_PROVIDER`, `DECIDER_PROVIDER` |
| `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_EMBED_DEPLOYMENT`, `AZURE_OPENAI_CHAT_DEPLOYMENT` | Azure OpenAI |
| `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION` | Azure AI Speech |
| `STORAGE_CONNECTION_STRING` | Blob への書き込み(パイプラインの `publish`) |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | 監視 |

秘密の値は、リポジトリに入れない(`.env.local` は `.gitignore`)。Container Apps にはシークレットとして渡す。

### 12.4 CI/CD

GitHub Actions: `main` へのpushで、`pnpm lint && pnpm test`(Web)、`uv run pytest`(パイプライン)、`cargo fmt --check`・`cargo clippy`・`cargo test`(recsys)、生成した型の差分の検査、イメージのビルドとデプロイ。インフラの変更は、手動実行のワークフロー(`terraform plan` の結果を確認してから `terraform apply`)。Azureへの認証は、OIDC(フェデレーション資格情報)を使い、長期のシークレットをCIに置かない。

---

## 13. 実装タスクと順序

**最優先は、「事故データだけで、取り込みから画面表示までを通す」縦の一本(M0〜M5)**。ここができてから、データを増やす(M6)。

| # | タスク | 受け入れ条件 |
| --- | --- | --- |
| M0 | リポジトリの雛形、Terraform、空のNext.jsをContainer Appsにデプロイ | `mise run infra-apply` と `mise run deploy` でURLが開く。DBに接続できる(`/api/health` が200) |
| M1 | パイプラインの核(`profile`, `generate`)を `accident` で動かす | 試作と同じ傾向(191行前後を生成、No.20は除外、数字の不一致0)。すべての行が推定15〜30秒に収まる(収まらない行は理由つきで除外) |
| M1b | 判断モデルの土台(`Decider` のインターフェース、`rules` の実装、YAMLの `decisions`、キャッシュ、記録)を、事故データに入れる | `rules` で動き、`decisions` が記録される。判断モデルを足してもコードが変わらない |
| M2 | DBのマイグレーション、`embed`、`publish`(ローカル) | `videos` と `embeddings` に191本前後が入る。`clusters` が作られる |
| M3 | Webのフィード(モックのUIを移植)。まずはDB直読みのダミーAPIで | モックと同じ見た目と操作。字幕、カウントアップ、コメント、一時停止、キーボード操作 |
| M4a | `services/recsys`(Rust): 計算(更新式、取り消しの再生、近傍検索、割合の計算)と、内部HTTP(§6.6)。DBは起動時に読み取るだけ | `cargo test` が通る。内部APIが仕様どおり。2,100本×1024次元で、`pick_next` が数ms以内 |
| M4b | Next.js のBFF(`/api/feed` `/api/view` `/api/like`): DBの読み書き、recsys の呼び出し、シーンJSONの整形 | 仕様どおりのJSON。疑似ユーザーのテスト(§14.2)が通る |
| M5 | 好みパネル(地図、割合、要約、視聴の記録)とAPIの連携、元データのシート | モックと同じ見た目。操作で黄色い点が動く |
| M6 | 残り13データセットの列定義YAML(§10)を、1つずつ追加 | 各データで `generate` が品質ゲートを通る本数が出る。数字の不一致0 |
| M6b | `strands_azure` を足し(モデルをAzureに配備)、事故50行で評価する(§14.2b) | 一致率80%以上なら `DECIDER_PROVIDER=strands_azure` を既定にする。未満なら `rules` のまま、結果を記録 |
| M7 | 地図の部品(航路、範囲、点)。日本の輪郭の同梱 | `naiko_route`, `flightplan`, `rental_result` の動画に地図が出る |
| M8 | 音声(`TTS_PROVIDER`)。まず `none` のまま完成させ、余裕があれば追加 | 音声ありのときは字幕と音声が同期する |
| M9 | 仕上げ: 監視、デモの流れ、READMEとデモ手順 | §14.3 の受け入れ基準を満たす |

各タスクは、完了時に `docs/DECISIONS.md` に判断を記録し、変更をコミットする。

### 13.1 週末の進め方(目安)

- 土曜の午前: M0〜M2。昼までに、事故データの動画がDBに入る。
- 土曜の午後〜夜: M3〜M5。夜に、事故データだけで、フィードと好みパネルが動く。
- 日曜の午前: M6〜M7(データを増やす。品質ゲートを通る分だけでよい)。
- 日曜の午後: M8(任意)、M9。
- 時間がなければ、M6は、`accident`、`akiya_reg`、`rental_result`、`rail_pl`、`naiko_route` の5つから先にやる(切り口の種類が揃うため)。

---

## 14. テストと受け入れ基準

### 14.1 テスト

- パイプライン: 事故の試作との照合テスト、品質ゲートの単体テスト、YAMLの式のテスト、数字の表記(`fmt`)のテスト。
- recsys(Rust): `cargo test`(更新式、いいねと取り消しの再生、候補の選択、連続制限、割合の合計100、`events` だけで結果が決まること)。Web(BFF): DBの読み書きと、recsys のモックを使った契約テスト。
- API: 仕様どおりのJSONが返ること、`viewId` の重複を無視すること、不正な値が400になること。

### 14.2 疑似ユーザー(レコメンドの検証)

`services/recsys` の `cargo test`(疑似ユーザー)で、次を行う。
- ユーザーA: 「鉄道」のデータセットの動画だけ、最後まで見る(視聴率1.0)。他はすぐ飛ばす(0.05)。
- ユーザーB: 「空き家」に、いいねを押す。他は普通(0.5)。
- 各ユーザー100本ぶん動かし、**何本目から、好みのデータセットの動画が配信の過半数を超えるか**を測る。
- 合格の目安: 20本以内に過半数を超えること。冒険枠(約18%)は、好み以外の動画が混ざることを確認する。
- 係数(§7.1)は、この結果で調整する。

### 14.2b 判断モデルの評価

- `datasets/accident.labels.csv`: 人(あなた)が事故50行に、`template`(物件の損壊 / 人の負傷 / 制御不能・墜落・落下 / その他)の正解を付ける。`rules` で下書きを作って、人が直すと速い。
- `uv run opendopa decide --dataset accident --eval datasets/accident.labels.csv` で、`rules` と `strands_azure`(と、あれば `jev_api`)の一致率、フォールバックの割合、1問あたりの時間を出す。
- 合格: `strands_azure` の一致率が80%以上、かつフォールバックが30%以下。合格しなければ `rules` を既定のままにする。
- 結果は `docs/DECISIONS.md` に記録する。


### 14.3 受け入れ基準(完成の定義)

1. ブラウザでURLを開くと、選択画面なしで動画が再生される。縦スクロールで次へ進める。
2. すべての動画に「AI生成のフィクション風解説」と出典が出る。「元データ」でCSV行が見られる。
3. 流れるコメントが出る(負傷者ありの事故では出ない)。
4. 動画を見る時間と、いいねで、右側の黄色い点と割合が動く。リロードしても(Cookieが残る限り)好みが保たれる。
5. 少なくとも5データセット以上で、動画が出る。事故を含む。
6. 生成された全原稿の、数字の不一致が0件(品質ゲートの結果が証拠)。
7. 疑似ユーザーのテスト(§14.2)が合格する。
8. `mise run infra-apply` と `mise run deploy` で、ゼロから環境が再現できる。
9. README に、セットアップ、パイプラインの実行方法、デモの手順が書かれている。

---

## 15. 安全と表示

### 15.1 必須の表示

- 動画ごと: 「AI生成のフィクション風解説」、出典(データ名と行番号または集計の条件)、「元データ」ボタン。
- フッター(全画面共通の小さな文字): 「OpenDopaは非公式のアプリです。国土交通省 Project LINKS が公開するオープンデータをもとにしています。」
- VOICEVOX使用時は、クレジット表記(§8.8)。

### 15.2 個人情報と配慮

- 氏名、番地、電話番号、メールアドレスらしい文字列は、原稿に出さない(品質ゲート)。
- 事故データ: 負傷の部位や症状は読まない。「負傷者の報告があります」にとどめる。
- 事故データのコメントは落ち着いた内容にし、負傷者ありではコメントを出さない。
- 事業者・会社の名前: 公開データに載っている法人名は使ってよい(鉄道事業者など)。個人事業者や、匿名化されたID(レンタカー、内航の船)は、特定しない表現にする。

### 15.3 データの扱い

- 元データを書き換えない。クリーニングは、読み込んだコピー上で行う。
- 除外した行と理由は、必ず記録する(`out/<id>/excluded.csv`)。

---

## 16. 未決事項(既定値で進め、あとから差し替える)

現在、未決事項はない。新しく出たら、既定値で進めて、ここに書く。決まったら、本文に反映して、ここから消す。

---