# OpenDopa 実装仕様書(AI実装エージェント向け)

版: v1.0 / 作成: 2026-11-01 / 対象: 2026-11-07〜08 のハッカソンで動くものを完成させる

この文書は、読み手(AIの実装エージェント)が、人に質問せずに最後まで作り切れることを目的に書いている。判断に迷ったら、この文書の「既定値」を採用し、`docs/DECISIONS.md` に1行で記録して先に進むこと。

---

## 0. 読み方と実装の約束

### 0.1 読む順番

1. §1〜§3: 何を作るか(ゴール、決定事項、画面)
2. §4〜§7: 構成、データモデル、API、レコメンド
3. §8〜§10: コンテンツ生成(原稿、シーン、データ別定義)
4. §11〜§13: 埋め込み、インフラ、タスク順序
5. §14〜§16: 受け入れ基準、安全、未決(既定値あり)

### 0.2 実装の約束(破ってはいけないこと)

- **元データにない事実を書かない。** 原稿に出る数字・日付・地名は、すべて元データの値、またはコードで機械的に計算した値(合計、順位、前年比など)であること。
- **原因・責任・被害の推測を書かない。** 元データに書かれていることだけを述べる。
- **単位が確認できていない列の絶対値は読み上げない。** 相対表現(順位、前年比、割合)だけを使う(§10の「単位」欄を参照)。
- **LLMを行ごとに呼ばない。** LLMを使うのは、データ種別ごとに1回(テンプレートの案づくり)と、クラスタ名・要約の生成だけ。実行時(ユーザーが見ている最中)には生成しない。
- **決定モデル(Jev系)には、文章も数字も作らせない。** あらかじめ並べた選択肢から「選ぶ」だけ。値の埋め込みは、すべてエンジンが元データから行う。決定モデルが失敗・低確信度のときは、ルールに戻す(§8.3a)。
- **ベクトル計算はRustで行う。** Next.js(TypeScript)では、好みのベクトルの更新、近傍検索、地図上の位置の計算をしない(§7)。Next.js は、Cookie・検証・整形だけを担当する。
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
| 音声(TTS) | `none`(字幕のみ。最初はこれで通す) | `azure`(Azure AI Speech)、`voicevox` | `TTS_PROVIDER=none\|azure\|voicevox` |
| 判断(決定モデル) | `rules`(全体を通すまで)。評価に合格したら `jev_local`(Jev-Style 2B など。失敗・低確信度のときは `rules`) | `jev_api`(TypeSafe Jev)、`azure_openai`(構造化出力) | `DECIDER_PROVIDER=rules\|jev_local\|jev_api\|azure_openai` |
| LLM(テンプレート案、クラスタ名) | Azure OpenAI のチャットモデル | なし(クラスタ名は機械的な名前にフォールバック) | `LLM_PROVIDER=azure\|none` |

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
| D7 | 画面・BFF | Next.js(TypeScript, App Router)。画面と、BFF(Cookie、入力の検証、シーンJSONの取得・整形)。**ベクトル計算はしない** |
| D8 | ホスティング | Azure Container Apps |
| D9 | IaC | Terraform(`azurerm` プロバイダー) |
| D10 | DB | Azure Database for PostgreSQL(Flexible Server) + pgvector |
| D11 | 配信 | Azure Blob Storage + CDN(Front Door)。音声とシーンJSONの置き場 |
| D12 | 原稿生成 | 列定義 + **完成した台本のテンプレート**(型ごとに数本、YAML) + 共通エンジン(Python)。型の選択は決定モデル、穴埋めはコード。行ごとにLLMを呼ばない |
| D13 | Databricks | 使わない |
| D14 | 判断モデル(Jev系) | **使う**。原稿生成で、どの型(テンプレート群)にするかを選ぶ(choice)ほか、安全チェック(noul)に使う(§8.3a)。ただし、全体を通すまでは `rules` で動かし、評価(§14.2b)に合格したら `jev_local` に切り替える |
| D15 | 音声 | 後で決める(VOICEVOXかAzure AI Speech)。最初は `none` で通す |
| D16 | 地図の背景 | 日本の輪郭をアプリに同梱する(Natural Earthを元にした公開データ。npmの`world-atlas`など) |
| D17 | ベクトル計算 | **Rustの別サービス(`services/recsys`)**で行う。好みのベクトルの更新、近傍検索、右パネルの値の計算。Next.js(TypeScript)では行わない。Container Apps の内部サービスとして置き、Next.js から内部HTTPで呼ぶ(§6.6) |

---

## 3. 画面仕様

**UIの正解は `reference/ui_mock.html`**(単体で開けるHTML。見た目と操作はこれに合わせる)。以下は、モックから読み取れる仕様と、本番で変える点。

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

### 3.6 モックから本番で変える点

| モック | 本番 |
| --- | --- |
| 24本の仮データ、2次元の座標で計算 | 14データセット、埋め込みベクトルで計算(§7、§11) |
| ブラウザ内で好みを計算 | サーバー(API)が計算して返す。ブラウザは表示だけ |
| 次の動画をブラウザが選ぶ | `GET /api/feed` で取得(1本先読み) |

---

## 4. システム構成と技術スタック

```
[事前バッチ(手元またはCI)]                          [実行時]
 data/raw/*.csv                                      ブラウザ(Next.js の画面)
   │  pipeline/ (Python)                                │ ↑
   ├─ profile / 取り込み・整形                           │ │ 動画: Blob + CDN(シーンJSON, 音声)
   ├─ scriptgen: 判断 → テンプレート → 穴埋め            ▼ │
   │    └─ 決定モデル(Jev系)が型を選ぶ              Next.js(BFF: Cookie・検証・整形)
   ├─ embed(埋め込み)→ 2D座標 → クラスタ                │  /api/feed /api/view /api/like
   ├─ tts(音声: 任意)                                   ▼  内部HTTP
   └─ publish ─┬→ Blob(音声・シーンJSON)            recsys(Rust: ベクトル計算)
               └→ PostgreSQL ◄───────────────────── 読み書き(好み・履歴・動画)
```

### 4.1 技術スタック

| 層 | 採用 |
| --- | --- |
| Web | Next.js 15 以降(App Router)、TypeScript、React、Tailwind CSS は使わず素のCSS(モックのCSSを移植) |
| BFF | Next.js Route Handlers(Node.js ランタイム)。Cookie、入力の検証、シーンJSONの取得・整形だけ。**ベクトル計算はしない**。DBは `pg` |
| ベクトル計算 | Rust(`services/recsys`)。axum + tokio + sqlx。計算の核は依存なしのライブラリ(`reference/recsys-rs`、`cargo test` が通る) |
| パイプライン | Python 3.11+、`uv` で管理。`pandas`、`pydantic`、`pyyaml`、`umap-learn`、`scikit-learn`、`openai`(Azure用) |
| DB | PostgreSQL 16(Flexible Server)、拡張 `vector`(pgvector) |
| IaC | Terraform(`azurerm` プロバイダー。バージョンを固定する) |
| CI/CD | GitHub Actions(Terraform と、コンテナのビルド・デプロイ) |
| 監視 | Application Insights |
| パッケージ管理 | pnpm(Web)、uv(Python) |

### 4.2 リポジトリ構成

```
opendopa/
├─ Makefile                    # make infra-plan / infra-apply / deploy などの入口
├─ infra/                      # Terraform(main.tf, variables.tf, outputs.tf, modules/*)
├─ apps/web/                   # Next.js
│   ├─ app/                    # ページ、api/ 以下にRoute Handlers
│   ├─ components/             # Feed, Slide, TastePanel, CsvSheet, Map, Comments ...
│   └─ lib/                    # recsys-client.ts(Rustへの内部HTTP), db.ts, types.ts
├─ services/recsys/            # Rust(ベクトル計算。Cargo。reference/recsys-rs が土台)
├─ pipeline/                   # Python
│   ├─ opendopa_pipeline/      # profile, ingest, scriptgen, embed, project, cluster, tts, publish
│   └─ tests/
├─ datasets/                   # データセット別の列定義YAML(§10)
│   ├─ accident.yaml  ...
├─ packages/shared/            # 共有の型(シーンJSONのスキーマ)
├─ data/raw/                   # 元CSV(git管理外。§10のファイル名で置く)
├─ reference/                  # ui_mock.html, make_scripts_templates.py, profile.py, profiles.json, recsys-rs/
└─ docs/DECISIONS.md           # 決めたことの記録
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

CREATE TABLE user_vectors (
  anon_id    text PRIMARY KEY,
  u          vector(1024) NOT NULL,
  event_count int NOT NULL DEFAULT 0,
  updated_at timestamptz NOT NULL DEFAULT now()
);

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

この章は、ブラウザから見えるAPI(Next.js の BFF)。**ベクトルに関わる処理は、すべて Rust の recsys に任せる**(§6.6)。Next.js は、Cookie と入力の検証を行い、recsys の結果に、シーンJSON・CSV行を付けて返すだけ。

### 6.1 `GET /api/feed?count=1&includeMap=0`

次の動画を返す。`count` は1〜3。初回は `count=2&includeMap=1`(現在の動画と、先読み1本)。

処理:
1. 匿名IDを確認する(Cookie。なければ発行する)。
2. recsys に `POST /internal/feed` で、選んだ動画ID・理由・更新後の `taste` をもらう(§6.6。選び方は§7.4)。
3. 動画IDから、シーンJSON・CSV行・出典を `videos` から読み、`taste` と一緒に返す。

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
処理: recsys に `POST /internal/view` で渡す。recsys が、保存・視聴率の計算(`ratio = min(1, watchedSec / duration_sec)`)・`u` の更新(§7.2)を行う。

レスポンス: `{ "taste": {...}, "logEntry": {"videoId","headline","reasonLabel","ratio","liked"} }`

検証: `videoId` が存在すること、`watchedSec` が0以上で `duration_sec * 10` 以下であること。外れたら400。

### 6.3 `POST /api/like`

リクエスト: `{ "videoId": "accident-0001", "liked": true }`(トグルでなく状態を送る。同じ内容を2回送っても二重に足さない)。

処理: recsys に `POST /internal/like` で渡す。recsys が、`like_events` への追加と、`u` の再計算(§7.3)を行う。

### 6.4 `taste` オブジェクト

```jsonc
{
  "x": 0.32, "y": 0.69,                       // 地図上の「いまの好み」(0〜1)
  "shares": [ { "clusterId": 4, "name": "…", "color": "#…", "pct": 41 } ],  // 合計100
  "summary": "あなたは「…」を最後まで見る人です",
  "eventCount": 7,
  "log": [ { "videoId","headline","reasonLabel","ratio","liked" } ]          // 新しい順、最大6件
}
```

### 6.5 共通

- エラーは `{ "error": "message" }` と適切なHTTPステータス。
- `/api/*` はすべて `Cache-Control: no-store`。
- 簡単なレート制限(匿名IDごとに1秒あたり10リクエスト)を入れる。

---

### 6.6 内部API(Next.js → recsys)

recsys は、Container Apps の**内部のみ**(外部に公開しない)のサービス。ヘッダー `X-Internal-Token`(環境変数 `INTERNAL_TOKEN`)で認証する。Next.js が、ブラウザからのリクエストを検証したうえで呼ぶ。recsys は、`user_vectors`・`impressions`・`view_events`・`like_events` を読み書きし、`embeddings`・`clusters`・`meta` と、`videos` の `duration_sec`・`status` を読む。

| メソッド・パス | 送る | 返す |
| --- | --- | --- |
| `POST /internal/feed` | `{anonId, count, includeMap}` | `{items:[{videoId, reason, reasonLabel}], taste, map?}`(`map` は §6.1 と同じ形) |
| `POST /internal/view` | `{viewId, anonId, videoId, watchedSec}` | `{taste, logEntry}`(`viewId` が重複なら、何もせず現在の `taste` を返す) |
| `POST /internal/like` | `{anonId, videoId, liked}` | `{taste}` |
| `POST /internal/reload` | なし | 動画の索引を、DBから読み直す(公開のあとに呼ぶ) |
| `GET /healthz` | なし | 200(索引の件数を含む) |

`taste` は §6.4 と同じ形。動画のシーンJSON・CSV行は、recsys は扱わない(IDと理由だけ返す)。


## 7. レコメンドの仕様

**実装は Rust(`services/recsys`)。Next.js(TypeScript)では計算しない。** `reference/recsys-rs` が、このアルゴリズムの動くサンプルで、`cargo test` の6件が通る(更新式の表、単位長さの維持、いいねの取り消しで元に戻ること、連続制限、割合の合計100、疑似ユーザーで好みのデータセットが増えること)。これを土台にして、DBと内部HTTP(§6.6)をつなぐ。

### 7.1 定数(既定値。`services/recsys/src/config.rs` にまとめる)

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

すべて、疑似ユーザーのテスト(§14.2)で調整できるよう、設定ファイルから読む形にする。

### 7.2 視聴による更新

`u0` は `meta.centroid`(全動画の重心。長さ1に正規化)。ベクトルはすべて長さ1。

```
r  = min(1, watchedSec / duration_sec)
w  = clamp((r - WATCH_NEUTRAL) / (1 - WATCH_NEUTRAL), -1, 1)    # r=1 で +1、r=0 で約 -0.67
a  = (w >= 0) ? ALPHA_POS * w : ALPHA_NEG * w                   # a<0 は遠ざかる
u  = normalize(u + a * (v - u))
```

(`reference/ui_mock.html` と同じ式。)

### 7.3 いいね、取り消し

```
like(true):   u = normalize(u + ALPHA_LIKE * (v - u))
like(false):  いいねを取り消し、そのユーザーの全イベントを時刻順に再生して u を作り直す
```

再生は、`u = u0` から始め、`view_events` と `like_events`(有効なもの。同じ動画の後ろの `liked=false` で相殺されたいいねは除く)を、`created_at` 順に適用する。件数は数十〜数百なので、毎回再生してよい。常に再生で `u` を作ると、整合性が崩れない(保存した `user_vectors` はキャッシュ扱い)。

### 7.4 次の動画の選び方

```
function pickNext(anon, u, eventCount, lastDatasets):
  unseen = videos where status='ok' and id not in impressions(anon)
  if unseen is empty: impressions をリセットして全体から選び直す
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

起動時に `embeddings` を全件メモリに読み込む(2,100本×1024次元で約8.6MB)。総当たりの内積で、1回の `pick_next` は約1.6ms、`taste_position` は約1.6ms(手元の実測。1スレッド、releaseビルド。`reference/recsys-rs` の `demo`)。pgvectorの近傍検索は使わない。動画を公開したあとは、`POST /internal/reload` で読み直す。

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
uv run opendopa profile  --dataset <id>        # 列のプロファイルを出す(reference/profile.py の整理版)
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

### 8.3 列定義YAMLのスキーマ(テンプレート方式)

方針: 台本は**完成した文章のテンプレート**(穴あき)を、データセットごと・型(グループ)ごとに、人があらかじめ用意しておく。行ごとに、①どの型か(決定モデルが選ぶ)、②その型の中のどのテンプレートか(ルールで決める)を決めて、穴に値を入れる。LLMは行ごとに呼ばない。

```yaml
id: accident                       # データセットID(英数字)
label: 事故等報告                   # 画面に出す名前
source_name: 無人航空機の事故等報告  # 出典に出す名前
wm_char: 機                        # 背景の透かし1文字
color: "#FF7A59"                   # 地図の点の色
files: [data/raw/accident/02_jikojyouhou.csv]
grain: row                         # row=1行1本 / group=グループ集計で1本(§8.5)
rename: {}                         # 列名の置き換え
null_values: ["", "不明"]          # 欠損として扱う値
zero_is_null: []                   # 0を欠損とみなす列
filters: [{col: INCIDENT_SUMMARY, not_null: true}]

derived:                           # 穴に入れる値を作る(すべてコードで計算。LLMは使わない)
  date:   {from: OCCURRENCE_DATE, op: format_datetime, fmt: ymdhm}      # 2022年12月6日11時20分
  place:  {from: OCCURRENCE_LOCATION, op: strip_parenthesis}
  pref:   {from: OCCURRENCE_LOCATION, op: extract_pref}
  kind:   {from: REMARKS, op: classify, rules: [{contains: "事故に該当", value: 事故}, {else: 重大インシデント}]}
  summary_1: {from: INCIDENT_SUMMARY, op: sentence, n: 1}              # 元の文をそのまま使う
  summary_2: {from: INCIDENT_SUMMARY, op: sentence, n: 2}
  casualty_sentence: {from: CASUALTIES_SUMMARY, op: map, map: {"なし": "人的被害は、報告にありません。"}, else: "負傷者の報告があります。"}
  measure_first: {from: RECURRENCE_PREVENTION_MEASURES, op: sentence, n: 1}
stats:                             # 集計(§8.5)
  - {name: pref_seq, op: seq_in_group, group: pref, order: OCCURRENCE_DATE}   # 「その県で◯件目」
select: {cap: 194, order_by: No., diversify_by: null}
big_number:
  primary:  {text: "{pref}で{pref_seq}件目", unit: "", label: "報告された事故等", when: "pref != null"}
  fallback: {text: "第{No.}号", unit: "", label: "報告の番号"}

template_groups:                   # 型ごとの、完成したテンプレート
  - id: object_damage
    label: "物件(車両・建物など)に接触・衝突した"       # 決定モデルに見せる、選択肢の説明
    templates:
      - id: object_damage_std
        lines:
          - "{date}、{place}で、無人航空機が物件に接触・衝突する事故が報告されました。"
          - "{summary_1}"
          - {text: "{summary_2}", optional: true}
          - "{casualty_sentence}"
          - {text: "機体の被害は、{AIRCRAFT_DAMAGE_SUMMARY}と記載されています。", optional: true}
          - {text: "再発防止策として、報告にはこう書かれています。{measure_first}", optional: true}
      - id: object_damage_short
        short: true                # 長さが収まらないときの短い版
        lines:
          - "{date}、{place}で、無人航空機が物件に接触・衝突する事故が報告されました。"
          - "{summary_1}"
          - "{casualty_sentence}"
  - id: injury
    label: "人が負傷した"
    templates: [ ... ]             # 同じ形(導入文は「人の負傷が報告されました」)
  - id: loss_of_control
    label: "制御不能・墜落・落下した"
    templates: [ ... ]
  - id: other
    label: "上のどれでもない"
    templates: [ ... ]             # 導入文は「無人航空機の{kind}が報告されました」

template_select: {decision: template}   # どの型にするかは、決定モデルが選ぶ(§8.3a)

decisions: [ ... ]                 # §8.3a
fallback_rules: { ... }            # §8.3a(決定モデルが使えないときの代わり)
comments:
  pool_calm: ["気をつけたい", "無事でよかった", "安全第一"]
  rule: "casualty_sentence == '負傷者の報告があります。' -> none; else calm"
embed_text: "事故等報告 {pref} {kind} {summary_1}"
```

**式(`when`、`filters`、`fallback_rules` の `if`)** は、安全な小さな式言語だけを許す(列名、`==`、`!=`、`>`、`<`、`and`、`or`、`null`、`contains(列, [語, ...])`)。`eval` は使わない。

#### 8.3.1 テンプレートの規則

- **穴(`{名前}`)** には、列名、または `derived` の名前だけを使える。**列定義にない名前は、読み込み時にエラー**にする。
- **必須の行と任意の行**: 文字列の行は必須。`{text: ..., optional: true}` の行は任意。
  - 必須の行の穴が1つでも空なら、そのテンプレートは、その行の**候補から外す**。
  - 任意の行の穴が空なら、その行だけを省く。
- **各型に、最低限の穴だけで埋まるテンプレート**(短い版 `short: true`)を、必ず1つ以上置く。1つの型に2〜3本(標準・短い版・言い回し違い)、1データセットで4〜6型が目安。
- **長さ(15〜30秒)**: テンプレートは、標準的な値で収まる長さに書く。埋めたあと、推定秒数を測り、次の順に直す。
  1. 30秒を超えたら、任意の行を後ろから省く。
  2. それでも超えたら、同じ型の短い版を使う。
  3. それでも超えたら、その行を `too_long` で除外する(理由を記録)。
  - 15秒に満たなければ、最後の字幕を表示したまま、動画の長さ(`durationSec`)を15秒にする。
- **型の中のテンプレートの選び方**: 埋められて長さに収まるものを、定義の順に試す。言い回しの違いを使いたいときは、同じ条件のテンプレートを複数置き、行のハッシュで選ぶ。
- 数字の表記は §8.5 の `fmt` に従う。値を埋めたあとの文は、必ず元データか計算から来た値だけになる。

### 8.3a 判断ポイント(決定モデル)

**方針**: 決定モデル(Jev系)は、**どの型のテンプレートを使うか**を「選ぶ」だけ。文章や数字は作らない。選ばれた型の中のテンプレートの選択(§8.3.1)と、穴埋めは、すべてエンジンが行う。これにより、LLMを行ごとに呼ぶ場合に比べて、費用と時間が小さく、数字が変わらない。

#### 判断の種類(Jevの3つの形に合わせる)

| kind | 答え | このアプリでの使いどころ |
| --- | --- | --- |
| `choice` | 選択肢から1つ(確率の分布と確信度つき) | **どの型(テンプレート群)にするか**(主な用途) |
| `noul` | はい/いいえの確率 | 個人情報があるか、広告の言い回しか、推測を含むか(安全チェック) |
| `score` | 順序のある基準での点数 | 任意。動画にする行の選別(ニュース性)など |

#### YAMLの書き方

```yaml
decisions:
  - id: template                         # 型を選ぶ(主役)
    kind: choice
    question: "この事故等報告の概要は、次のどの型に一番近いですか。"
    state: [INCIDENT_SUMMARY, CASUALTIES_SUMMARY]   # 判断モデルに渡す列(これだけ)
    options_from: template_groups        # 各型の label を選択肢にする(その行で埋められる型だけ)
    min_confidence: 0.55
    fallback: {rule: keyword, default: other}   # 低確信度・失敗のときの代わり

  - id: pii                              # 安全チェック
    kind: noul
    question: "この文章に、個人を特定できる記述(氏名・番地・電話番号など)がありますか。"
    state: [INCIDENT_SUMMARY]
    exclude_if_probability_above: 0.5    # 超えたら、その行を除外(品質ゲート)
    fallback: {rule: regex_pii}

fallback_rules:                          # 決定モデルが使えないとき(`rules` プロバイダー)の代わり
  keyword:
    - {if: "CASUALTIES_SUMMARY != 'なし' or contains(INCIDENT_SUMMARY, ['負傷'])", then: injury}
    - {if: "contains(INCIDENT_SUMMARY, ['不能', '制御'])", then: loss_of_control}
    - {if: "contains(INCIDENT_SUMMARY, ['車両', '建物', '物件', '衝突', '接触'])", then: object_damage}
    - {else: other}
```

- 選択肢は、`options_from` の型のうち、**その行で、少なくとも1つのテンプレートが埋められるもの**だけにする(決定モデルが、埋められない型を選ぶことはない)。
- 選択肢の `label` は、判断モデルへの質問に出す日本語。`id` はコード用。
- 型の数は、4〜6つに抑える(小さなモデルは、選択肢が多いと精度が落ちる)。
- ルールの `keyword` は粗い。実測(事故194行、`reference/make_scripts_templates.py`)では、「接触」が146行に出るため、ほとんどが `object_damage` に入ってしまう(123行)。「プロペラが停止し、屋根に落下した」のような文が、`loss_of_control` に入らない。**ここが、決定モデルで精度を上げたい部分**。

#### 実行(Decider のインターフェース)

```python
class Decider(Protocol):
    def decide(self, kind, state: dict, question: str,
               options: list[Option] | None = None, rubric: list[str] | None = None) -> Decision: ...

@dataclass
class Decision:
    choice: str | None             # choice のとき
    distribution: dict[str, float] # 各選択肢の確率
    score: float | None            # score のとき(期待値)
    probability: float | None      # noul のとき(はいの確率)
    confidence: float              # 分布の集中の度合い(0〜1)
    provider: str                  # 'jev_local' など
    used_fallback: bool            # フォールバックしたか
```

- **フォールバック**: 確信度が `min_confidence` 未満、またはエラー・タイムアウトのときは、YAMLの `fallback`(`fallback_rules` か既定の選択肢)を使い、`used_fallback=True` で記録する。決定モデルが動かなくても、パイプラインは止まらない。
- **キャッシュ**: `(provider, 質問, state, 選択肢)` のハッシュで結果を `out/<id>/decisions.cache.jsonl` に保存し、再実行で再計算しない。
- **バッチ処理**: 同じ質問は、まとめて推論する。タイムアウトは1問あたり30秒。
- **記録**: 全判断(ID、選択、分布、確信度、provider、フォールバックの有無)を `videos.decisions`(jsonb)に保存する。クライアントには配信しない。データセットごとに、フォールバックの割合を `decisions_report.json` に出す。
- **入力は最小限**: 判断モデルに渡すのは、YAMLの `state` で指定した列だけ。ほかの列(個人に関わるものを含む)は渡さない。

#### プロバイダー

| 名前 | 内容 |
| --- | --- |
| `rules` | ルール(`fallback_rules`、正規表現)。全体を通すまでの既定。判断モデルが使えないときの代わり |
| `jev_local` | ローカルで動かす、Jevふうの判断モデル。候補は、Hugging Face の `chaoliangUNSW/Jev-Style-2B-Decision-v3`(約1.9B、Apache-2.0、`jev-style` パッケージでローカルAPIとして起動できる。Apple Siliconは `jev-style[mlx]`)と、AWSの Strands Decider 2B。実装時に、モデルカードの手順とライセンスを確認する(提供元はTypeSafe AIとは別の組織) |
| `jev_api` | TypeSafe Jev(ホスト型のAPI。`TYPESAFE_API_KEY`)。費用・利用条件は要確認 |
| `azure_openai` | Azure OpenAI の構造化出力で、同じ質問に答えさせる(確率は、複数回の試行の割合などで近似してよい) |

**日本語の精度は未検証**。必ず §14.2b の評価を通してから、既定にする。

#### 処理量の見積もり

動画約2,100本 × 1本あたり1〜2問(型の選択と、安全チェック) ≈ 2,000〜4,000問。ローカルの2Bモデルで、1問あたりの時間は、機械によって大きく変わる。`decide` コマンドで実測し、`docs/DECISIONS.md` に記録する(キャッシュがあるので、再実行は速い)。

#### 事故データでの試作の結果(`rules`、`reference/make_scripts_templates.py`)

事故194行のうち、191行を生成(概要が空の1行と、概要だけで30秒に収まらない2行は除外)。数字の不一致は0。推定秒数は、最小19.5、中央26.0、最大30.0。型の内訳は、`object_damage` 123、`loss_of_control` 29、`injury` 29、`other` 10。標準のテンプレートで収まり、短い版は使われなかった。


### 8.4 選定(`select`)

```yaml
select:
  cap: 150                        # 1データセットの上限(既定150。設定で変えられる)
  filters: [...]                  # 動画にしない行の条件
  score:                          # ニュース性の点数(ルールだけ。LLMは使わない)
    - {expr: "abs(yoy_ratio)", weight: 1.0}
    - {expr: "rank_desc(revenue)", weight: 0.5}
  diversify_by: [prefecture]      # 偏らないよう、この列で順番にばらして選ぶ
  seed: 42
```

点数の高い順に並べ、`diversify_by` の値ごとにラウンドロビンで選んで `cap` 本にする。点数の指定がなければ、ランダム(`seed` 固定)。

### 8.5 集計の部品(`stats`)

| op | 意味 | 出力 |
| --- | --- | --- |
| `rank_in_group` | グループ内の順位(降順/昇順) | 順位、グループの数 |
| `yoy_diff` / `yoy_ratio` | 前年との差、変化率(`group_by` の同じ主体の前年の行) | 差、率 |
| `share_of_total` | グループ内の割合 | 0〜100 |
| `sum_by` / `mean_by` / `count_by` | グループ集計(例: 都道府県別) | 集計値 |
| `series` | 主体ごとの時系列(最大12点) | 小さな折れ線グラフ(スパークライン)用の配列 |
| `seq_in_group` | グループ内の通し番号(日付順) | 「◯件目」 |
| `is_first_time` | 初めて黒字/赤字になった年か | 真偽 |
| `per` | 比(例: 1台あたりの売上 = 売上 ÷ 台数) | 比 |

出力した数値は、「計算に使った元の列、操作、値、表示形」の記録(`numbers` リスト)としてシーンに残す。検証は、この記録を元データから再計算して照合する。

#### 数字の日本語表記(`fmt`)

- 円・千円: 1万以上は「○万」、1億以上は「○億」、1兆以上は「○兆」(小数は1桁まで、丸めたら「約」を付ける)。例: 2,008,428,041千円 → 「約2兆84億円」ではなく「約2兆円」。**丸めは原稿を作る側の表現として許可するが、元の値から再計算して誤差0.5%以内**であること。
- 日付: `2022年12月6日11時20分`(分が0なら「11時」)。
- パーセント: 小数1桁まで。
- 順位: 「○位」。件数: 「○件」。

### 8.6 品質ゲート(通らない行は `excluded` にして理由を記録)

| 検査 | 条件 |
| --- | --- |
| 未置換 | 原稿に `{` `}` が残っていない |
| 数字の照合 | 原稿に出る数字のすべてが、`numbers` の記録の表示形、または元の行の値のどれかと一致する(桁区切り、和数字表記は正規化して比較) |
| 欠損 | 必須の列(YAMLの `required`)が空でない |
| 長さ | 推定秒数が15〜30秒に入る(§8.3.1の処理後) |
| 個人情報 | 氏名らしい文字列、番号らしい文字列(電話・メール・番地)が含まれない(§15) |
| 禁止表現 | 「原因は」「責任は」「〜のせい」など、推測を示す言い回しが含まれない |
| 重複 | 同じ原稿の動画が重複しない |
| 判断 | フォールバックした判断の割合を記録する。1つのデータセットで30%を超えたら警告(`decisions_report.json`)。`pii`(noul)の確率が上限を超えた行は除外 |

実行結果として、データセットごとに「生成件数、除外件数と理由の内訳、推定秒数の最小・中央・最大」を標準出力とJSONに残す。

### 8.7 読み上げ用の整形(TTSを使う場合)

字幕は元の表記のまま。TTSに渡す文だけ、`pipeline/tts_dict.yaml` の読み替え(例: `無人航空機 → むじんこうくうき`、事業者名・地名の読み)を適用する。辞書にない語は、そのまま渡す。

### 8.8 音声(TTS)

- 1行(字幕1つ)ずつ別のファイルに合成する(例: `audio/<video_id>/<n>.mp3`)。長さを測って、シーンの `lines[i].audio` に入れる。
- `TTS_PROVIDER=none` のときは音声ファイルを作らない。字幕の秒数は1秒6.5文字で見積もる。
- VOICEVOXを使う場合は、キャラクターごとの利用規約とクレジット表記(「VOICEVOX:キャラ名」)を、フィードの下部かフッターに出す。

---

## 9. シーンJSON(ブラウザが描画するデータ)

`packages/shared` に TypeScript の型と JSON Schema を置く。パイプラインはこの形で出力し、Webはこの形だけを読む。

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

## 10. データセット別の定義(届いた14ファイル)

ファイル名は、`data/raw/<dataset_id>/` に以下の名前で置く。列名は元のまま(英語)。**列の意味の確認が取れていない単位は「単位:要確認」として、絶対値を読み上げない**(§0.2)。

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

**全データ共通の注意**
- 文字コードはUTF-8(BOM付き)。列名は英語。
- 鉄道の6ファイルは、事業者名の表記がファイルで違う(例: `東日本旅客鉄道` と `ＪＲ東日本`)。**ファイル同士を結合しない**。それぞれを独立のデータセットとして扱う。
- 年度の範囲は、鉄道が2012〜2023。内航の航路は2017〜2023が主(2013〜2016に外れ値が1行ずつある。除外する)。

---

### 10.1 `accident`(事故等報告) — 実装済みの試作あり

- **grain/kind**: 1件=1本 / `event`。
- **試作**: `reference/make_scripts_templates.py`(テンプレート方式、判断は `rules`)。事故194行のうち、191行を生成(概要が空の1行と、概要だけで30秒に収まらない2行を除外)、数字の不一致0、推定19.5〜30秒。型の内訳は、`object_damage` 123、`loss_of_control` 29、`injury` 29、`other` 10。これと同じ傾向を再現できること(型の割合は、決定モデルで変わる)。
- **列**: `No.`, `OCCURRENCE_DATE`(`2022/12/6 11:20`), `OCCURRENCE_LOCATION`(都道府県+市区町村。海外の1件は長い文)、`OPERATOR`(事業者123/個人58/行政機関11/大学1/学校1)、`MODEL_OR_MANUFACTURER`, `INCIDENT_SUMMARY`(最長165字)、`CASUALTIES_SUMMARY`(なし165。他は負傷の内容)、`AIRCRAFT_DAMAGE_SUMMARY`(全損34、プロペラの破損22、なし17など)、`RECURRENCE_PREVENTION_MEASURES`(最長327字。4件は空)、`REMARKS`(事故/重大インシデントの定型文)。
- **処理**: `REMARKS` の文に「事故に該当」があれば `事故`、なければ `重大インシデント`。都道府県は先頭の `...都道府県` を正規表現で取る(194行中3行は取れない。そのときは大きな数字を「第◯号」にする)。
- **大きな数字**: 「◯◯県で◯件目」(日付順の通し番号)。取れなければ「第◯号」。
- **コメント**: 負傷者あり→なし。それ以外は落ち着いたコメントのみ(§3.5)。
- **個人情報**: 負傷の部位は読まない。「負傷者の報告があります」にとどめる(§15)。
- **YAML**: §8.3の例のとおり。
- **判断ポイント**: §8.3a の例のとおり(`template`、`pii`)。評価用の正解は `datasets/accident.labels.csv`(人が50行に付ける: `No.`, `template`)。

### 10.2 `flightplan`(無人航空機飛行計画, GeoJSON)

- **構造**: FeatureCollection(100件のサンプル)。ジオメトリは `Polygon`(飛行範囲)。属性が66個。
- **使う属性**: 飛行目的のフラグ(`FLIGHT_PURPOSE_BUSINESS_AERIAL_PHOTOGRAPHY` など。1なら該当)、飛行方法のフラグ(`FLIGHT_METHOD_NIGHT`=夜間、`FLIGHT_METHOD_BVLOS`=目視外、`FLIGHT_METHOD_WITHIN_30M`=30m以内、`FLIGHT_METHOD_OBJECT_DROPPING`=物件投下 など)、空域のフラグ(`FLIGHT_AIRSPACE_DID`=人口集中地区、`FLIGHT_AIRSPACE_OVER_150M`=150m以上、`FLIGHT_AIRSPACE_AROUND_AIRPORT`=空港周辺)、`FLIGHT_DATETIME_START/END`、`FLIGHT_ALTITUDE`(単位:要確認。メートルと推定)、`FLIGHT_SPEED`(単位:要確認)、`DEPARTURE_LOCATION`, `DESTINATION_LOCATION`(地名)、`DEPARTURE_LATITUDE/LONGITUDE`, `AIRCRAFT_TYPE`(例: 回転翼航空機(マルチローター))。
- **使わない属性**: `FLIGHT_PLAN_ID_NEW`, `MANUFACTURING_NUMBER`, 登録日時などのIDや内部情報(個人特定の可能性があるため)。
- **kind**: `geo`。地図に範囲(`polygon`)を出し、特徴の `chips`(「夜間」「目視外」「人口集中地区」)を付ける。フラグが1つもなければ、「特徴なし」の動画にはしない(除外)。
- **大きな数字**: 飛行高度(単位が確認できるまでは出さず、代わりに「飛行時間◯時間」(開始・終了の差から計算。この単位は時間なので確認不要)を出す)。
- **原稿の例**: 「{出発地名}周辺で、{開始日}に、{目的}の飛行計画が通報されています。特徴は、{chips}です。」

### 10.3 `akiya_reg`(空き家バンク: 登録物件)

- **列(主なもの)**: `PROPERTY_NUMBER_ID`(使わない), `PROPERTY_CATEGORY`(売買居住用21,919/売買土地5,441/賃貸居住用4,191/賃貸土地264/賃貸事業用212/売買事業用146)、`PREFECTURE`, `CITY`, `NEAREST_TRAIN_LINE`, `NEAREST_STATION`, `DISTANCE_TO_NEAREST_STATION_ON_FOOT`(単位:要確認。分と推定)、`AMOUNT/RENT`(円。売買は価格、賃貸は賃料。0や欠損、極端な値あり)、`DATE_OF_CONSTRUCTION`(`1980/3/1`。欠損多)、`CONSTRUCTION`(構造)、`OCCUPATION_AREA`(㎡と推定。**単位:要確認**)、`LAYOUT`(間取り。`R` などの略記あり)、`SIZE_OF_LOT`(敷地面積。㎡と推定。**単位:要確認**)、`STRONG_POINTS`(自由記述。61%が記入、最長133字)。
- **クリーニング**: `AMOUNT/RENT` が0、欠損、または10億円以上は除外。賃貸は月額のため、売買と別の言い回しにする(「月◯万円」)。築年は、`DATE_OF_CONSTRUCTION` の年から計算(築◯年)。
- **選定**: `cap=150`。`PREFECTURE` でばらして選ぶ。`STRONG_POINTS` が記入のある物件を優先(点数に加点)。
- **kind**: `event`(「今日の物件」)。
- **大きな数字**: 価格(`AMOUNT/RENT` を「◯万円」「◯億円」。賃貸は「月◯万円」)。
- **テンプレートの例**: 「今日の物件を紹介します。{PREFECTURE}{CITY}の{PROPERTY_CATEGORY}です。」「価格は{price}です。」「築{age}年、{LAYOUT}」。**面積と敷地の数字は、単位が確認できるまで読み上げない**(順位や比較だけに使う)。
- **`STRONG_POINTS` の扱い**: 不動産会社の屋号、広告の言い回し(例: ハウスメーカー名、「♪」、「！」の連続)が混ざる。使う場合は、①ブランド名らしい固有名詞を含む文は除外 ②記号(♪、♡、★)を取り除く ③最初の1文だけ、40字以内。使えなければ、その文のパーツを出さない。
- **個人情報**: 住所は市区町村までで足りる。番地・電話番号らしい文字列を含む自由記述は除外。
- **型(テンプレート群)の例**: 物件の特徴で、「自然・静か」「駅・生活利便」「広さ・庭」「店舗・事業」「その他」の5つ。決定モデル(choice)が、`STRONG_POINTS` と物件種別から型を選ぶ(確信度が低ければ「その他」)。`stronger_ad`(noul): 「強み」の文に、広告・屋号の言い回しが含まれるか → 確率が0.5を超えたら、その文を使わない。

### 10.4 `akiya_sold`(空き家バンク: 成約物件)

- **列**: `CONTRACT_INFO_DATE`(`2026/3/28`。欠損あり)、`CONTRACT_INFO_AMOUNT/RENT`(成約金額)、`ID`(使わない)、他は `akiya_reg` とほぼ同じ(`AMOUNT/RENT` は売り出し時の価格)。
- **導出**: 値下げ率 = `(AMOUNT/RENT - CONTRACT_INFO_AMOUNT/RENT) / AMOUNT/RENT`。両方が正のときだけ。外れ値(±50%超)は除外。
- **kind**: `event`(「成約しました」)。
- **大きな数字**: 成約価格(「◯万円」)、または「希望価格より◯%」。
- **原稿(例)**: 「成約情報です。{PREFECTURE}{CITY}の{PROPERTY_CATEGORY}が、{price}で成約しました。」「売り出し時の価格は{list_price}でした。」
- その他は `akiya_reg` に準じる。

### 10.5 `rental_result`(レンタカー貸渡実績)

- **構造**: 1行=事業者×年度(匿名。事業者名なし)。`OPERATOR_ID` は匿名のIDなので出さない。
- **列(主なもの)**: `FISCAL_YEAR`(2025が884行、2024が108行、他は少数)、`REPORTING_PERIOD`(和暦の文字列。例: `令和8年1月5日から令和8年3月31日まで`。そのまま使わない)、`ADDRESS`(都道府県名のみ)、`ADDRESS_LATITUDE/LONGITUDE`, `NUMBER_OF_OFFICES`, `TOTAL_VEHICLE_COUNT`(台)、`TOTAL_RENTAL_TIMES`(貸出回数)、`TOTAL_RENTAL_DAYS`(貸出日数)、`TOTAL_DISTANCE`(単位:要確認。キロメートルと推定。欠損多)、`TOTAL_RENTAL_FEES`(円)、車種別(`PASSENGER_CAR_*`、`PASSENGER_CAR_LIGHT_*`、`MICROBUS_*`、`TRUCK_*`、`MOTORCYCLE_*` など)、`PREFECTURE_NAME`, `CITY_WARD_TOWN_NAME`, `ADMINISTRATIVE_AREA_CODE`。
- **フィルタ**: `FISCAL_YEAR == 2025` と `TOTAL_RENTAL_TIMES > 0`。
- **grain**: `group`。都道府県別に集計して1本(`PREFECTURE_NAME` ごとに、`TOTAL_VEHICLE_COUNT`、`TOTAL_RENTAL_TIMES`、`TOTAL_RENTAL_FEES` の合計)。
- **導出**: 1台あたり売上 = 売上 ÷ 台数。平均貸出日数 = 貸出日数 ÷ 貸出回数。
- **kind**: `stat`(順位)。地図に都道府県の点(`points`)を出し、上位を強調。
- **動画の切り口(各都道府県1本)**: 「{都道府県}のレンタカー、貸出は{回数}回」+ 全国順位 + 1台あたり売上の順位。
- **大きな数字**: 貸出回数。ラベル「年間の貸出回数」。

### 10.6 `rental_fleet`(レンタカー配車車両数)

- **構造**: 1行=営業所(運輸支局×所在)。列名が `OFFICE_VEHICLE_ALLOCATION_LIST_*`(営業所単位)と `TOTAL_*`(運輸支局単位の合計)と思われるが、**意味が確認できていない**。
- **使う列**: `OFFICE_VEHICLE_ALLOCATION_LIST_TRANSPORT_BRANCH`(運輸支局名。例: 沖縄)、`OFFICE_VEHICLE_ALLOCATION_LIST_LOCATION`(都道府県名)、`OWNED_VEHICLES_TOTAL`, `TOTAL_SUM`(車両数の合計と推定。**単位:台、ただし意味は要確認**)、`NUMBER_OF_OFFICES_TOTAL`。
- **grain**: `group`(運輸支局ごと)。
- **kind**: `stat`。運輸支局別の車両数ランキングの形に限る(順位と割合だけ。絶対値の読み上げは、意味が確認できるまで控える)。
- **注意**: 意味が曖昧な列を使うので、品質ゲートで「数字の照合」を厳しめにし、迷う場合は動画にしない。

### 10.7 `naiko_route`(内航海運: 船舶輸送統計調査、航路)

- **構造**: 1行=積み港×降ろし港×年(16,062の航路)。2017〜2023年が主。
- **列**: `YEAR`, `LOADING PORT_NAME`, `LOADING PORT_PREFECTURE NAME`, `UNLOADING PORT_NAME`, `UNLOADING PORT_PREFECTURE NAME`(欠損あり)、`SAMPLE SIZE`(標本数。単位は隻/回など**要確認**)、`AVERAGE_GROSS TONNAGE`(平均総トン数)、`AVERAGE_DEAD WEIGHT TONNAGE`, `AVERAGE_LOADING RATIO`(積載率。0〜1)、`AVERAGE_CARGO WEIGHT`(単位:要確認。トンと推定)、`AVERAGE_TRANSPORT DISTANCE`(単位:要確認。キロメートルまたは海里)、`LOADING PORT_LATITUDE/LONGITUDE`(欠損あり。同じ港名の他の行から補完する)、`UNLOADING PORT_LATITUDE/LONGITUDE`、用途別の船の内訳(`PURPOSE_*`)。
- **クリーニング**: `YEAR` が2017〜2023の行だけ。港の緯度経度が補完できない行は除外。
- **選定**: `cap=150`。標本数が多い航路を優先し、`LOADING PORT_PREFECTURE NAME` でばらす。
- **kind**: `geo`(`route`: 港から港への弧)。
- **大きな数字**: 積載率(「◯%」。0〜1を%に変換。単位が確かな比率なので読み上げてよい)。
- **原稿(例)**: 「{積み港}から{降ろし港}へ。{年}年の内航船の航路です。」「平均の積載率は{ratio}%です。」「平均の総トン数は{gross}トンです。」(総トンは単位が明確)。距離と貨物の重さは、単位が確認できるまで読み上げない。

### 10.8 `naiko_ship`(内航海運: 事業概況、船)

- **構造**: 1行=船1隻。事業者の財務は「ランク」区分(`..._RANK`)のみで、数値なし。住所は空欄が多い。**事業者は特定しない**(`Address`, `Business_Management_ID` は使わない)。
- **列**: `Ship_ID`(使わない)、`Usage`(営業船など)、`Ship_Material`(鋼船など)、`Gross_Tonnage`(総トン数)、`Deadweight_Tonnage`(0は欠損)、`Length`(m)、`Horsepower`(0は欠損。単位:要確認)、`Ship_Type_1/2/3`(船種)、`Launch_Year_(20`(建造年代。例: `1980年～1999年`。列名が途中で切れているので、YAMLで `rename: {"Launch_Year_(20": LAUNCH_BAND}`)、`Supervisory_Transport_Bureau`(例: 関東)。
- **選定**: `cap=150`。`Supervisory_Transport_Bureau` と `Ship_Type_1` でばらす。
- **kind**: `event`(「この船」)。
- **大きな数字**: 総トン数(「◯トン」)。
- **原稿(例)**: 「内航海運の船を紹介します。{Ship_Type_1}です。」「総トン数は{Gross_Tonnage}トン、全長は{Length}メートル。」「建造は{LAUNCH_BAND}です。」

### 10.9〜10.14 鉄軌道(6ファイル)の共通方針

- **共通列**: `YEAR`, 事業者名(`CORPORATION_NAME` または `COMPANY_NAME` / `OPERATOR_NAME`)、`JURISDICTION`(管轄の運輸局)、`CATEGORY`(中小/大手/公営/JR。`rail_income` では `COMPANY_SIZE`)。
- **grain**: 事業者×年度(`row`)。**切り口は「事業者の年度ニュース」**: 値の大きさのランキング、前年比、12年の推移(`sparkline`)。
- **選定**: 最新年度(2023)を中心に、変化の大きい事業者と、規模の大きい事業者を点数で選ぶ。`CATEGORY` でばらす(`cap=150`)。
- **列の数が多い**(15〜94列)。使う列は、以下の「見出し指標」の5〜8個に絞る。残りは使わない。
- **ランキングは `CATEGORY` ごと**に行う(中小と大手を同じ順位表に並べない)。

#### 10.9 `rail_traffic1`(運輸成績1: 輸送人員)

- 見出し指標: `TRANSPORTED_NUMBER_TOTAL`(輸送人員。**単位:千人と推定(JR東日本2018年が6,549,424で、約65億人に当たる)。要確認**)、`TRANSPORTED_NUMBER_COMMUTER_PASS_RATIO`(定期の割合。%)、`TRANSPORTED_NUMBER_NON_COMMUTER_PASS`, `TRANSPORTED_TONNAGE_TOTAL`(貨物。**単位:要確認**)。
- 動画: 「{事業者}の{年}年の輸送人員、前年比{率}%」。大きな数字は前年比(%)。絶対値は読み上げない(単位が確定するまで)。

#### 10.10 `rail_traffic2`(運輸成績2)

- 見出し指標: `AVERAGE_PASSAGE_AMOUNT_PASSENGER`(平均通過人員。**単位:要確認**)、`AVERAGE_TRANSPORTED_KILOMETER_PASSENGER`(平均乗車キロ。**要確認**)、`TOTAL_DAY_KILOMETER_PASSENGER`(**要確認**)。
- 動画: 同じ区分内の**順位と前年比だけ**を語る(絶対値は出さない)。

#### 10.11 `rail_km`(営業キロ・車両)

- 見出し指標: `FISCAL_YEAR_TOTAL_OPERATING_KILOMETERS_PASSENGER`(営業キロ。km。**津軽鉄道が20.7でキロメートルと確認できる**)、`FISCAL_YEAR_TOTAL_OPERATING_KILOMETERS_CARGO`, `TOTAL_TRAIN_TOTAL`(列車数。**要確認**)、`TOTAL_CARS_TOTAL`(車両数。**要確認**)。
- 動画: 「{事業者}の営業キロは{km}キロ」「同じ区分で{順位}番目」。営業キロは絶対値を読み上げてよい。

#### 10.12 `rail_pl`(営業損益、鉄道事業)

- 見出し指標: `RAILWAY_OPERATING_REVENUE_TOTAL_TOTAL_THOUSAND_YEN`(営業収益。**千円。JR東日本2018年が約2兆円で確認できる**)、`RAILWAY_OPERATING_PROFIT_LOSS_THOUSAND_YEN`(営業損益。千円)、`OPERATING_RATIO_POST_DEPR_PERCENT`(営業係数。%)、`OPERATING_REVENUE_PER_CAR_KM_YEN`(円)。
- 動画: 「{事業者}の{年}年、鉄道事業の営業損益は{黒字/赤字}{額}」「前年は{黒字/赤字}でした」。初めて黒字/赤字になった年は、強調する(`is_first_time`)。
- 金額は `fmt`(§8.5)で「億円」「兆円」に直して読み上げる。

#### 10.13 `rail_income`(損益計算書、会社単位)

- 見出し指標: `TOTAL_OPERATING_REVENUE_THOUSANDJPY`, `TOTAL_OPERATING_PROFITLOSS_THOUSANDJPY`, `ORDINARY_PROFITLOSS_THOUSANDJPY`, `NET_PROFITLOSS_THOUSANDJPY`(いずれも千円)、鉄道/バス/不動産の事業別(`RAILWAY_*`, `BUS_*`, `REALESTATE_*`)の営業損益。
- 動画: 「{会社}の{年}年、当期純利益は{額}」「鉄道は{黒字/赤字}、不動産は{黒字/赤字}」の形で、事業別の黒字・赤字を語る。

#### 10.14 `rail_bs`(貸借対照表)

- 見出し指標: `TOTAL_ASSETS`, `TOTAL_LIABILITIES`, `TOTAL_EQUITY`(列名に単位がない。**単位:千円と推定。要確認**)、`TOTAL_EQUITY_PERCENT`(%)。
- 動画: **比率だけ**を語る(「自己資本は総資産の{%}」と、同じ区分内の順位)。絶対額は、単位が確認できるまで読み上げない。

---

### 10.15 後から足すデータ(まだ届いていない6種類)

地域公共交通計画、かわまちづくり計画、港湾計画、道路脱炭素化推進計画、離島に関するデータ(離島活性化交付金等事業計画書、離島広域活性化事業、離島振興計画書、離島振興対策実施地域一覧)、PLATEAUの成果報告書等(ユースケース、取組事例)。

**追加の手順**(エンジンの変更なしでできること):
1. `data/raw/<id>/` にCSVを置く。
2. `uv run opendopa profile --dataset <id>` で列の一覧を出す。
3. LLM(`LLM_PROVIDER=azure`)に、プロファイルとサンプル10行を渡して、列定義YAMLの案を作らせる(プロンプトは§8.9)。
4. 人が確認して直し、`datasets/<id>.yaml` に置く。
5. `generate` を実行し、品質ゲートの結果を見る。

計画書型は自由記述が多いと予想される。使い方は、①概要の文をそのまま字幕に使う(元データの文なので、事実が変わらない) ②施策の種類など、分類が要る場合は、`DECIDER_PROVIDER`(最初は`rules`、足りなければJev系の判断モデル。§8.3a)で行う。

### 8.9(補足)テンプレート案を作らせるLLMプロンプトの要点

LLMに渡す: データセットのプロファイル(列名、型、欠損率、種類数、最長文字数、上位の値)、サンプル10行、YAMLスキーマ(§8.3)、禁止事項。指示の要点:
- 値にあることだけを述べる。原因・責任・被害の推測は書かない。
- 穴埋めは、列定義にある列名の `{}` だけを使う。
- ニュース番組風の、落ち着いた語り口。
- 出力はYAMLだけ。
- 型(グループ)ごとに、完成した文章のテンプレートを、標準・短い版・言い回し違いで書く。1行は、読み上げて5〜8秒に収める。
LLMの出力は、列名が列定義に存在するかを機械で検査してから、人が確認する。**LLMが書くのは「ひな型」だけで、数字は必ずエンジンが入れる。**

---

## 11. 埋め込み・地図・クラスタ(`embed` コマンド)

実行時のベクトル計算は Rust(§7)。オフラインの処理(埋め込み、UMAP、KMeans)は、ライブラリの都合で Python(パイプライン)のまま(U11)。

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
4. KMeans(`k=12`、`random_state=42`)で、元のベクトルをクラスタに分ける。`clusters.centroid` は各クラスタの重心(正規化)、`cx, cy` は所属動画の座標の平均。
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
| Azure AI Speech | `TTS_PROVIDER=azure` のとき |
| Key Vault(任意) | 接続文字列とキー |

地域は、日本の東(Japan East)を優先。サービスが使えない地域は、次の候補を選んでよい(記録する)。

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

- `CREATE EXTENSION vector;` は、Terraform ではなく、アプリのDBマイグレーションで実行する。
- アプリのデプロイは、Terraformとは分ける。`docker build` で作ったイメージをレジストリに送り、`azurerm_container_app` のイメージのタグ(変数 `web_image_tag`)を更新して `terraform apply`、またはCIで `az containerapp update` を使う。どちらを使うかは、`docs/DECISIONS.md` に記録する。
- 入口は `Makefile`: `make infra-init`, `make infra-plan`, `make infra-apply`, `make deploy`(ビルドからデプロイまで)。
- `terraform output` で、URL、DB接続先、Storageの名前などを取り出せるようにする(秘密の値は `sensitive = true`)。

### 12.3 環境変数

| 名前 | 用途 |
| --- | --- |
| `DATABASE_URL` | PostgreSQL接続文字列 |
| `MEDIA_BASE_URL` | CDNのベースURL |
| `RECSYS_URL`, `INTERNAL_TOKEN` | Next.js から recsys への内部HTTP(URLと共有トークン) |
| `EMBED_PROVIDER`, `EMBED_DIM` | §0.4 |
| `TTS_PROVIDER`, `LLM_PROVIDER`, `DECIDER_PROVIDER` |
| `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_EMBED_DEPLOYMENT`, `AZURE_OPENAI_CHAT_DEPLOYMENT` | Azure OpenAI |
| `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION` | Azure AI Speech |
| `STORAGE_CONNECTION_STRING` | Blob への書き込み(パイプラインの `publish`) |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | 監視 |

秘密の値は、リポジトリに入れない(`.env.local` は `.gitignore`)。Container Apps にはシークレットとして渡す。

### 12.4 CI/CD

GitHub Actions: `main` へのpushで、`pnpm lint && pnpm test`(Web)、`uv run pytest`(パイプライン)、イメージのビルドとデプロイ。インフラの変更は、手動実行のワークフロー(`terraform plan` の結果を確認してから `terraform apply`)。Azureへの認証は、OIDC(フェデレーション資格情報)を使い、長期のシークレットをCIに置かない。

---

## 13. 実装タスクと順序

**最優先は、「事故データだけで、取り込みから画面表示までを通す」縦の一本(M0〜M5)**。ここができてから、データを増やす(M6)。

| # | タスク | 受け入れ条件 |
| --- | --- | --- |
| M0 | リポジトリの雛形、Terraform、空のNext.jsをContainer Appsにデプロイ | `make infra-apply` と `make deploy` でURLが開く。DBに接続できる(`/api/health` が200) |
| M1 | パイプラインの核(`profile`, `generate`)を `accident` で動かす | 試作と同じ傾向(191行前後を生成、No.20は除外、数字の不一致0)。すべての行が推定15〜30秒に収まる(収まらない行は理由つきで除外) |
| M1b | 判断モデルの土台(`Decider` のインターフェース、`rules` の実装、YAMLの `decisions`、キャッシュ、記録)を、事故データに入れる | `rules` で動き、`decisions` が記録される。判断モデルを足してもコードが変わらない |
| M2 | DBのマイグレーション、`embed`、`publish`(ローカル) | `videos` と `embeddings` に191本前後が入る。`clusters` が作られる |
| M3 | Webのフィード(モックのUIを移植)。まずはDB直読みのダミーAPIで | モックと同じ見た目と操作。字幕、カウントアップ、コメント、一時停止、キーボード操作 |
| M4a | `services/recsys`(Rust): `reference/recsys-rs` を土台に、DBの読み書きと内部HTTP(§6.6)をつなぐ | `cargo test` が通る。内部APIが仕様どおり。2,100本×1024次元で、`pick_next` が数ms以内 |
| M4b | Next.js のBFF(`/api/feed` `/api/view` `/api/like`)と、recsys のクライアント | 仕様どおりのJSON。疑似ユーザーのテスト(§14.2)が通る |
| M5 | 好みパネル(地図、割合、要約、視聴の記録)とAPIの連携、元データのシート | モックと同じ見た目。操作で黄色い点が動く |
| M6 | 残り13データセットの列定義YAML(§10)を、1つずつ追加 | 各データで `generate` が品質ゲートを通る本数が出る。数字の不一致0 |
| M6b | `jev_local` を足し、事故50行で評価する(§14.2b) | 一致率80%以上なら `DECIDER_PROVIDER=jev_local` を既定にする。未満なら `rules` のまま、結果を記録 |
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
- recsys(Rust): `cargo test`(更新式、いいねと取り消しの再生、候補の選択、連続制限、割合の合計100)。Web(BFF): recsys のモックを使った、契約テスト。
- API: 仕様どおりのJSONが返ること、`viewId` の重複を無視すること、不正な値が400になること。

### 14.2 疑似ユーザー(レコメンドの検証)

`services/recsys` の `cargo test`(疑似ユーザー。`reference/recsys-rs` に雛形がある)で、次を行う。
- ユーザーA: 「鉄道」のデータセットの動画だけ、最後まで見る(視聴率1.0)。他はすぐ飛ばす(0.05)。
- ユーザーB: 「空き家」に、いいねを押す。他は普通(0.5)。
- 各ユーザー100本ぶん動かし、**何本目から、好みのデータセットの動画が配信の過半数を超えるか**を測る。
- 合格の目安: 20本以内に過半数を超えること。冒険枠(約18%)は、好み以外の動画が混ざることを確認する。
- 係数(§7.1)は、この結果で調整する。

### 14.2b 判断モデルの評価

- `datasets/accident.labels.csv`: 人(あなた)が事故50行に、`template`(物件の損壊 / 人の負傷 / 制御不能・墜落・落下 / その他)の正解を付ける。`rules` で下書きを作って、人が直すと速い。
- `uv run opendopa decide --dataset accident --eval datasets/accident.labels.csv` で、`rules` と `jev_local`(と、あれば `jev_api`)の一致率、フォールバックの割合、1問あたりの時間を出す。
- 合格: `jev_local` の一致率が80%以上、かつフォールバックが30%以下。合格しなければ `rules` を既定のままにする。
- 結果は `docs/DECISIONS.md` に記録する。


### 14.3 受け入れ基準(完成の定義)

1. ブラウザでURLを開くと、選択画面なしで動画が再生される。縦スクロールで次へ進める。
2. すべての動画に「AI生成のフィクション風解説」と出典が出る。「元データ」でCSV行が見られる。
3. 流れるコメントが出る(負傷者ありの事故では出ない)。
4. 動画を見る時間と、いいねで、右側の黄色い点と割合が動く。リロードしても(Cookieが残る限り)好みが保たれる。
5. 少なくとも5データセット以上で、動画が出る。事故を含む。
6. 生成された全原稿の、数字の不一致が0件(品質ゲートの結果が証拠)。
7. 疑似ユーザーのテスト(§14.2)が合格する。
8. `make infra-apply` と `make deploy` で、ゼロから環境が再現できる。
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

| # | 項目 | 既定値 | 差し替えるときに変えるもの |
| --- | --- | --- | --- |
| U1 | 音声 | `TTS_PROVIDER=none`(字幕のみ) | `TTS_PROVIDER`。VOICEVOXかAzure AI Speech。声と速度、読み辞書 |
| U2 | 判断モデル(Jev系)の採用 | `DECIDER_PROVIDER=rules` で全体を通す。事故50行の評価で一致率80%以上なら `jev_local` を既定にする | `DECIDER_PROVIDER`。評価の結果を `docs/DECISIONS.md` に記録 |
| U3 | 埋め込み | `EMBED_PROVIDER=azure`(使えなければ `local`) | Azure OpenAIの利用可否(サブスクはあるが、OpenAI・Speechは未確認) |
| U4 | 単位の確認 | §10で「要確認」とした列は、絶対値を読み上げない | 仕様書で単位を確認できたら、YAMLの `unit_verified: true` にして解禁 |
| U5 | 残り6種類のデータ | 後から追加(§10.15) | データと仕様書が届いたら、YAMLを足すだけ |
| U6 | レコメンドの係数 | §7.1の値 | 疑似ユーザーのテスト(§14.2)で調整 |
| U7 | 動画の上限 | 1データセット150本 | `select.cap` |
| U8 | クラスタ数 | 12 | `embed` の引数 |
| U9 | 日本の輪郭データ | `world-atlas`(Natural Earth由来)を同梱 | 詳細な行政区画が必要になったら |
| U10 | Azureの地域とモデル名 | Japan East、モデル名は実装時に確認 | `infra/main.parameters.json` |
| U11 | オフラインのベクトル処理(埋め込み、UMAP、KMeans) | Python のまま(実行時の計算だけをRustにする) | Rustにしたい場合は指示する(UMAPのRust実装は成熟度が低いので、先に評価する) |