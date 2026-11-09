# OpenDopa
#### Progateハッカソン powered by ProjectLINKS
#### 最優秀賞 / Project LINKS賞 受賞
https://topaz.dev/projects/rf23wuwzyssmxsjj

国土交通省 Project LINKS のオープンデータ(CSV)から、縦スクロールのショート動画を作り、視聴といいねから好みを学習して次の動画を選ぶ Web アプリです。

OpenDopa は**非公式のネタアプリ**です。国土交通省とは関係がなく、国土交通省 Project LINKS が公開するオープンデータをもとにしています(詳しくは「免責とクレジット」)。

使い方の流れは、(1)セットアップ、(2)DB・web・recsys の起動、(3)パイプラインで動画データを作って公開、(4)ブラウザで見る(「デモの手順」)です。Azure に載せる手順は「CD(デプロイ)とインフラ変更」「Azure 環境をゼロから作る・消す」にあります。

動作確認の範囲: ローカルの手順(セットアップ、起動、パイプライン、デモ)のコマンドとタスク名は、`mise.toml`・`Makefile`・`opendopa --help` と照らして存在を確かめました。ただし、この README の更新では、DB・web・recsys を起動した通しの実行(クリーンな環境での手順の再実行)はしていません(実機未確認)。Azure 向けの手順(`make deploy`、`make recsys-reload`、`make deploy-pipeline`、`make pipeline-run`、`make deploy-decider`、CD、Terraform)は、`infra/`・`Makefile`・`.github/workflows/` の読み取りと `terraform validate` に基づいており、**実機未確認**です(Azure のサブスクリプションが書き込み禁止だったため)。該当箇所にも「実機未確認」と書いています。

## 構成図

```
[事前バッチ(手元またはCI)]                          [実行時]
 data/raw/*.csv                                      ブラウザ(Next.js の画面)
   │  pipeline/ (Python)                                │ ↑
   ├─ profile / 取り込み・整形                           │ │ 動画: Blob + CDN(シーンJSON, 音声)
   ├─ generate: 判断 → テンプレート → 穴埋め             ▼ │
   ├─ tts(音声: 任意)                              Next.js(BFF)── DBの読み書き ──┐
   ├─ embed(埋め込み)→ 2D座標 → クラスタ                │  内部HTTP                  │
   └─ publish ─┬→ Blob(音声・シーンJSON)                ▼                          ▼
               └→ PostgreSQL ◄───────────────── recsys(Rust: 計算だけ)      PostgreSQL
                      起動時に埋め込みを読む(読み取りのみ)
```

元の図は `docs/design_doc.md` §4 です。DB の読み書きはすべて web が行い、ベクトル計算は recsys(Rust)だけが行います。

## 構成

| ディレクトリ | 役割 | 言語 |
| --- | --- | --- |
| `apps/web` | 画面と BFF(DB の読み書きはすべてここ) | TypeScript(Next.js) |
| `services/recsys` | 好みのベクトルの計算(状態を持たない内部サービス) | Rust |
| `pipeline` | Batch。CSV から動画データを作り、DB に公開する | Python |
| `packages/shared` | pipeline と web の契約(シーンJSONの JSON Schema) | JSON Schema |
| `datasets` | データセット別の列定義 YAML | YAML |
| `docs` | 設計書、データ定義書、決定の記録(ADR) | - |

## セットアップ

### 前提

- macOS
- [Homebrew](https://brew.sh/)
- Docker(DB の起動に使う。Docker Desktop など、`docker compose` が使えるもの)

次のツールは、すべて mise が `mise.toml` のバージョンで入れます。個別にインストールする必要はありません(バージョンは `mise.toml` が正です)。

| 用途 | ツール |
| --- | --- |
| web | Node.js、pnpm |
| recsys | Rust(clippy、rustfmt を含む) |
| pipeline | Python、uv |
| DB | dbmate(マイグレーション。DB 本体は Docker で起動する) |
| 開発補助 | lefthook(git hook)、Terraform(インフラを触るときだけ) |

### 1. mise を入れて有効にする

```bash
brew install mise
```

```bash
echo 'eval "$(mise activate zsh)"' >> ~/.zshrc
```

```bash
source ~/.zshrc
```

### 2. ツールと依存を入れる

リポジトリのディレクトリで実行します。

```bash
mise trust
```

```bash
mise install
```

```bash
mise run setup
```

`mise run setup` は次をまとめて行います。

- `.env.example` をコピーして `.env.local` を作る(すでにあれば何もしない)
- web(pnpm)、pipeline(uv)、recsys(cargo)の依存を入れる
- git hook(lefthook)を登録する

### 3. 確認する

```bash
mise doctor
```

`activated: yes` と `No problems found` が出れば準備完了です。

## 起動

先に DB を起動します(初回はイメージの取得に少し時間がかかります)。

```bash
mise run db-up
```

PostgreSQL 16 + pgvector を Docker で起動し、`db/migrations` のマイグレーションを流します。続けて、web と recsys を起動します。

```bash
mise run dev
```

web と recsys がまとめて起動します。個別に起動するときは `mise run web` / `mise run recsys` を使います。

| サービス | URL | 確認用のエンドポイント |
| --- | --- | --- |
| web | http://localhost:3000 | `GET /api/health`(DB に接続できれば 200、できなければ 503)、`GET /api/health/recsys`(web から recsys に内部 HTTP でつながれば 200) |
| recsys | http://localhost:8080 | `GET /healthz`、`GET /internal/ping` `POST /internal/feed|taste|reload`(ヘッダー `X-Internal-Token` が必要) |
| DB | localhost:5432 | `mise run db-check`(pgvector が入っていることと、recsys のロールが読み取り専用であることを確かめる。要 `mise run db-up`)。`mise run db-psql` でつなげる |
| DB マイグレーション | (使い捨ての DB) | `mise run db-test`(空の DB に適用、2回流す、制約と recsys ロールの権限の確認。要 `mise run db-up`) |

起動できたかは、別のターミナルで次のとおり確認します。

```bash
curl -i http://localhost:3000/api/health
```

`HTTP/1.1 200` と `{"status":"ok","db":"ok"}` が返れば、web と DB がつながっています。続けて `curl -i http://localhost:3000/api/health/recsys` が 200 なら、web から recsys までつながっています。

web の BFF(`apps/web/app/api/`)には、次の API があります。画面から呼ばれるもので、DB の読み書きはすべてここが行い、好みの計算は recsys に任せます。

| API | 内容 |
| --- | --- |
| `GET /api/feed` | 次の動画を返す(好みに合う動画 + 探索)。`?tag=<タグID>`(複数可、AND)で、タグで候補を絞る |
| `GET /api/tags` | タグの一覧(動画がないタグは件数 0) |
| `POST /api/view` / `POST /api/like` | 視聴(視聴率)・いいねを記録し、好みを更新する |
| `GET /api/health` / `GET /api/health/recsys` | 上の表のとおり |

タグの絞り込みは、BFF の API までが入っています。画面(左上の虫眼鏡など)は未実装です(`docs/hashtag_design.md`、`docs/decisions/2026-11-07-bff-tag-filter.md`)。タグは、パイプラインがタグを付けるまで空です(`docs/decisions/2026-11-07-tags-schema-empty-until-assigned.md`)。

終わったら、`mise run dev` を Ctrl+C で止め、`mise run db-down` で DB を止めます。

DB のタスクは次のとおりです。

| コマンド | 内容 |
| --- | --- |
| `mise run db-up` | DB を起動し、マイグレーションを流す |
| `mise run db-down` | DB を止める(データは残る) |
| `mise run db-reset` | データを消して作り直す |
| `mise run db-migrate` | 未適用のマイグレーションを流す |
| `mise run db-new 名前` | マイグレーションのファイルを作る(`db/migrations/`) |
| `mise run db-psql` | psql でつなぐ |
| `mise run db-check` | DB の状態を確かめる(`mise-tasks/db-check`。`mise.toml` ではなくファイルタスク) |
| `mise run db-test` | マイグレーションの検証(使い捨ての DB) |

recsys 用のロール(`db/init/01-roles.sql`)は、ボリュームを最初に作るときにしか作られません。ロールを足す前に作ったボリュームを使っている場合は、`mise run db-reset` で作り直してください。

## パイプライン(動画データを作る)

Batch(Python)で、元データの CSV から動画データを作り、DB に公開します。実行時(ユーザーが見ている最中)には LLM を呼びません。原稿の数字は、元データから機械的に作ります。

```bash
mise exec -- uv run --project pipeline opendopa --help
```

(`cd pipeline && uv run opendopa --help` でも同じです。以降のコマンドはリポジトリのルートで実行します。)

### 1. 元データを置く

`data/raw/<データセットID>/<ファイル名>` に、国土交通省 Project LINKS が公開している CSV を置きます(`data/raw/` は git に入りません)。ID とファイル名は `docs/data.md` §10.0 の表のとおりです(例: `data/raw/accident/02_jikojyouhou.csv`)。置き場所の詳細は `data/README.md` にあります。列の定義は `datasets/<ID>.yaml` です。

### 2. 実行の順番

| コマンド | 内容 | 出力 |
| --- | --- | --- |
| `opendopa profile --dataset <ID>` | 列の型・欠損率・種類数などを調べる(確認用。なくても動く) | `out/<ID>/profile.json` |
| `opendopa generate --dataset <ID>` | 選定 → 判断 → 原稿 → シーン → 品質ゲート | `out/<ID>/scenes.jsonl` ほか |
| `opendopa tts --dataset <ID>` | 音声を作る(`TTS_PROVIDER=none` なら何もしない) | `out/<ID>/media/` |
| `opendopa embed` | 全動画の埋め込み・2D 座標・クラスタ(全データセットをまとめて) | `out/embeddings.npz` ほか |
| `opendopa publish` | DB(と Blob)に公開する(1 トランザクションで入れ替え) | DB |
| `opendopa fetch-raw` | Blob の `raw` コンテナの `<ID>/` 配下を `data/raw/<ID>/` に取り込む(`RAW_SOURCE=blob` のときの前処理。`all` は自動で行う) | `data/raw/<ID>/` |
| `opendopa all` | `datasets/*.yaml` のすべてについて、generate → tts → embed → publish を順に行う | 上のすべて |

- そのほか、`draft-yaml`(列定義 YAML の下書きの材料。新しいデータセットを足すとき)と `decide`(判断モデルの評価)があります。使い方は `pipeline/README.md` を見てください。
- `embed` は `tts` のあとに行います。`tts` が長さ超過の動画を除外するため、`embed` は除外後の動画だけを読みます(`docs/decisions/2026-11-06-all-order-tts-before-embed.md`)。個別に流すときも、この順番です。
- `embed` は常に全体をやり直します。データセットを足したり作り直したりしたら、`embed` と `publish` を流し直します。
- `publish` の前に、`--dry-run` で件数だけ確かめられます(DB にも Blob にも接続しません)。
- ローカルの DB に公開するときは、`--skip-blob` を付けます(ローカルに Blob は立てません。`docs/decisions/2026-11-06-publish-local-blob.md`)。シーンは DB の `videos.scene` に入るので、`--skip-blob` だけで画面は動きます。

最短の例(DB を起動済み、`data/raw/` に CSV を置いた状態):

```bash
mise exec -- uv run --project pipeline opendopa generate --dataset rental_result
mise exec -- uv run --project pipeline opendopa embed
mise exec -- uv run --project pipeline opendopa publish --skip-blob
```

全データセットをまとめて作るときは、次のとおりです。

```bash
mise exec -- uv run --project pipeline opendopa all --skip-blob
```

### 3. 環境変数(切り替え)

ルートの `.env.local` に書きます(`mise run setup` が `.env.example` からコピーします)。

| 変数 | 値 | 意味 |
| --- | --- | --- |
| `EMBED_PROVIDER` | `azure`(既定)/ `local` | 埋め込みモデル。`azure` は Azure OpenAI(`AZURE_OPENAI_*` が要る)。`local` は手元の `multilingual-e5-large` で、Azure なしで試せる。`local` を使うときは、先に `uv sync --project pipeline --extra local` を実行する |
| `TTS_PROVIDER` | `none`(既定)/ `voicevox` | 音声。`none` は音声なし(字幕の秒数は文字数からの見積もり)。`voicevox` は VOICEVOX ENGINE(`VOICEVOX_URL`、既定 `http://localhost:50021`)で読み上げる |
| `RAW_SOURCE` | `local`(既定)/ `blob` | 元 CSV の読み先。`local` は `data/raw/`(`datasets/*.yaml` の `files`)。`blob` は Blob のコンテナ `RAW_BLOB_CONTAINER`(既定 `raw`)の `<ID>/` 配下をすべて読む(Azure のジョブで使う。`STORAGE_CONNECTION_STRING` が要る) |
| `LLM_PROVIDER` | `none`(既定)/ `azure` | クラスタ名を付ける LLM。`none` は機械的な名前。原稿の生成には使わない |
| `DECIDER_PROVIDER` | `rules`(既定)/ `strands_azure` ほか | 型の選択などの「判断」を行うモデル。`rules` は規則のみ(LLM を使わない)。`strands_azure` は Azure 上の自前モデルで、`STRANDS_DECIDER_URL` と `STRANDS_DECIDER_TOKEN` が要る |

ローカルだけで試すなら、`EMBED_PROVIDER=local`、`TTS_PROVIDER=none`、`LLM_PROVIDER=none`、`DECIDER_PROVIDER=rules` の組み合わせです。`EMBED_PROVIDER` を変えたら、ベクトルを混ぜないよう `embed` をやり直し、`publish` で DB を入れ替えます(ローカルと Azure の埋め込みはモデルが違います)。変数の全一覧は `.env.example` にあります。

音声と BGM を画面で鳴らす設定(`MEDIA_BASE_URL`、`TTS_CREDIT`、`BGM_FILE`、`BGM_CREDIT`、`BGM_VOLUME`)は web が実行時に読みます。BGM は任意で、`BGM_FILE` と `BGM_CREDIT` の両方を設定したときだけ、フィード全体で 1 曲をループします(音源は同梱しません。ライセンスを確認したものだけを `MEDIA_BASE_URL` 配下に置きます。`docs/decisions/2026-11-07-bgm-feed-wide-loop.md`)。左下のボタンでミュートできます。

各コマンドの `--provider` で、環境変数を上書きできます(`generate` は判断、`embed` は埋め込み、`tts` は音声)。

### 4. out/ の中身

`out/` は git に入りません。

| パス | 内容 |
| --- | --- |
| `out/<ID>/scenes.jsonl` | 品質ゲートを通った動画のシーン JSON(1 行 1 本。契約は `packages/shared/schema`) |
| `out/<ID>/videos.jsonl` | DB の `videos` 用の行(除外された動画も含む) |
| `out/<ID>/excluded.csv` | 除外した行と理由(列: `row_id`、`video_id`、`stage`、`reason`、`detail`) |
| `out/<ID>/decisions_report.json` | 判断の集計(型の内訳、フォールバックの件数など) |
| `out/<ID>/decisions.cache.jsonl` | 判断のキャッシュ |
| `out/<ID>/profile.json` | `profile` の結果 |
| `out/<ID>/media/<videoId>/<n>.mp3` | `tts` の音声 |
| `out/embeddings.npz`、`out/clusters.json`、`out/centroid.json` | `embed` の結果(全データセット共通) |

新しいデータセットを足すときは、`pipeline/README.md` を見てください。

### publish のあとの recsys の再読み込み

recsys は起動時に索引を読みます。ローカルでは、`publish` が `RECSYS_URL` の `/internal/reload` を呼びます。recsys が動いていなければ警告だけで終わるので、`mise run recsys` を起動し直してください。

Azure の recsys は内部 ingress のみのため、手元 PC や CI の `publish` から `/internal/reload` は届かず、警告(`recsys の reload に失敗しました`)だけで終わる。公開のあとは、`az login` した状態で `make recsys-reload` を実行する。recsys が再起動し、起動時に新しい索引を読み込む。

### Azure でパイプラインを動かす(Container Apps Job)

手元の PC ではなく、Azure の Container Apps Job で `opendopa all` を流せます(実機未確認。`terraform validate` のみ。`docs/decisions/2026-11-07-pipeline-job-raw-blob.md`)。元 CSV は Blob の非公開コンテナ `raw` の `<データセットID>/` 直下に人が置きます。ジョブは `RAW_SOURCE=blob` で、そこをすべて読みます。TTS は `none` です(VOICEVOX にジョブから届かないため。音声つきの動画は手元から公開します)。

1. `infra/terraform.tfvars` に `pipeline_job_enabled = true`(`enable_storage = true` が必要)を足して `make infra-plan && make infra-apply`。判断モデルを Azure のものにするときは `pipeline_decider_provider = "strands_azure"`(`decider_enabled = true` が必要)
2. `make deploy-pipeline`: pipeline のイメージ(`pipeline/Dockerfile`)をビルドして push し、ジョブを更新する
3. `make pipeline-run`: ジョブを起動する。進み具合は `az containerapp job execution list -g <rg> -n <job> -o table`、ログは Log Analytics の `ContainerAppConsoleLogs_CL`
4. ジョブの `publish` は、recsys の内部 URL に reload を POST する

動画 ID は CSV の行順に依存するため、元 CSV を差し替えるときは既存の行の順序を保ちます(増やす行は末尾)。順序が変わると、`publish` が警告を出します。

判断モデル(`DECIDER_PROVIDER=strands_azure`)の API サーバーは、`make deploy-decider` でイメージを push して更新します(`infra` の `decider_enabled = true` と、サーバーの Dockerfile `services/decider/Dockerfile` が要る。後者はこのリポジトリにまだありません。実機未確認。常時 1 レプリカが課金されます)。評価に合格するまでは `rules` が既定です。

## 入っているデータ

デモ用に、14 のデータセットから 1,845 本の動画を作ります(2026-11-07 時点の実データでの生成結果。除外は 32 本。この README の更新では、元データがないため再生成していません)。件数は、データのバージョンや `datasets/*.yaml` の設定で変わります。

| 分類 | データセット ID | 内容 | 本数 |
| --- | --- | --- | --- |
| 事故 | `accident` | 事故等報告 | 188 |
| 空き家 | `akiya_reg` / `akiya_sold` | 空き家バンクの登録 / 成約物件 | 149 / 148 |
| 鉄道 | `rail_traffic1` / `rail_traffic2` / `rail_km` | 輸送人員・運輸成績・営業キロ | 146 / 146 / 147 |
| 鉄道 | `rail_pl` / `rail_income` / `rail_bs` | 営業損益・損益・貸借 | 145 / 146 / 150 |
| 内航 | `naiko_route` / `naiko_ship` | 内航海運の航路 / 船 | 150 / 146 |
| レンタカー | `rental_result` / `rental_fleet` | 貸渡実績 / 配車車両数 | 25 / 59 |
| 計画書 | `flightplan` | 飛行計画(GeoJSON のサンプル 100 件) | 100 |

件数の出どころは、`docs/decisions/` と `docs/adr/` の各データセットの記録です(例: `2026-11-06-rail-datasets-design.md`、`2026-11-06-naiko-datasets.md`、ADR-0051)。列の定義は `docs/data.md` にあります。

## デモの手順

所要時間の目安は 3〜5 分です。見せどころは、**いいねや視聴で、右側の「あなたの好み」が動くところ**です。PC の幅(900px 以上)で行うと、動画と右側のパネルを同時に見せられます。

事前に、「セットアップ」「起動」「パイプライン」を済ませ(DB に動画が入っていること)、`mise run dev` で web と recsys を起動しておきます。

1. http://localhost:3000 を開く。選択画面は出ず、そのまま動画が再生される(「AI生成のフィクション風解説」のラベル、見出し、字幕、大きな数字、流れるコメント)。
2. スクロール(↑↓、`j` / `k`)で次の動画へ進む。
3. 気になる種類の動画は最後まで見る。興味のないものは、すぐ飛ばす。
4. 気に入った動画で、右レールのいいね(`l` キーでも可)を押す。赤く塗られる。
5. 右側の「あなたの好み」を見る。地図の黄色い点(いまの好み)が動き、カテゴリ別の割合(%)が変わり、黄色の帯の要約が変わる。「最近の視聴」に、出た理由と視聴率が並ぶ。スマホ幅では、右レールの「好み」ボタンでシートを開く。
6. 数本見て、好みに近い種類の動画が増えていくことを確かめる(全データセットを一巡するまでの最大 14 本は、新しいデータセットも出る。一巡のあとが、収束を見せやすい。`docs/decisions/2026-11-07-recsys-discovery-and-streak.md`)。
7. 右レールの「元データ」を押し、元の 1 行(データ名、行番号、列名と値)を見せる。「デモ用の仮データではなく、元データの値です。」と出る。
8. ページをリロードする。同じブラウザなら好みが保たれる(匿名 ID の Cookie `od_aid` で識別する)。
9. (任意)コメントの流れ方を見せる。BGM は、設定したときだけ鳴る(左下のボタンでミュート)。音声は、`TTS_PROVIDER=voicevox` で作り、配信できる環境(Azure の Blob と CDN)で再生する(下の注意)。

注意:

- ローカルの web には、音声ファイル(`MEDIA_BASE_URL`)を配信する経路がありません。音声つきのデモは、Blob に公開した環境で行います。ローカルのデモは、`TTS_PROVIDER=none`(字幕とコメントのみ)を前提にします。
- 好みをやり直したいときは、Cookie `od_aid` を消します(シークレットウィンドウでも可)。

## 免責とクレジット

- OpenDopa は**非公式のネタアプリ**です。国土交通省 Project LINKS が公開するオープンデータをもとにしていますが、国土交通省とは関係がありません。画面のフッターにも同じ文言を出しています。動画は「AI生成のフィクション風解説」で、数字は元データから機械的に作っています。元データの値は、各動画の「元データ」で確認できます。
- 個人情報と配慮の方針は、設計書 §15.2 のとおりです(例: 事故データでは、負傷の部位や症状を読みません)。
- **VOICEVOX**(`TTS_PROVIDER=voicevox`)を使うときは、画面のフッターにクレジット(既定は「VOICEVOX:ずんだもん」)を出します。声を変えたら、`TTS_CREDIT` も合わせて変えてください(`docs/decisions/2026-11-06-tts-voice-and-credit.md`)。VOICEVOX 本体と各キャラクターの利用規約・ライセンスは、公開前に必ず確認してください。このリポジトリは VOICEVOX を同梱しません。
- BGM(`BGM_FILE`)を使うときは、`BGM_CREDIT` がフッターに出ます。音源のライセンス・利用規約は、公開前に必ず確認してください。このリポジトリは音源を同梱しません。
- 右側の地図の日本の輪郭は、world-atlas 2.0.2(ISC ライセンス。元データは Natural Earth でパブリックドメイン)から作り、`apps/web/lib/data/japan.json` に同梱しています(作り方は `apps/web/scripts/build-japan.mjs`)。
- 元データの CSV は、このリポジトリに含めません。

## 開発

### テストの実行

```bash
mise run test
```

全言語のテストをまとめて流します。言語ごとに流すときは `mise run test:web` / `test:shared` / `test:pipeline` / `test:recsys` を使います(`mise run lint:*` も同じ並びです)。web は、変更したら `cd apps/web && mise exec -- pnpm typecheck` も通してください。テストは DB を必要としません。

`data/raw/` は git に入りません(`.gitignore` 対象)。実データ(オープンデータの CSV)を `data/raw/<データセットID>/` に置くと、実データを使うテストも走ります。ファイル名は `docs/data.md` の一覧のとおりで、例は `data/raw/accident/02_jikojyouhou.csv` です。worktree では `data/raw` が空なので、メインの `data/raw` へのシンボリックリンクを張ると実データで動かせます。

注意: 実データがあると、`pipeline/tests/test_generate.py::test_generate_accident_real` が main でも失敗します(推定秒数の最小 18.31 が期待の 19 未満)。CI は実データなしで skip するので影響しません。

### Makefile のターゲット(Azure。人が実行する)

| コマンド | 内容 |
| --- | --- |
| `make infra-init` / `infra-plan` / `infra-apply` / `infra-validate` / `infra-fmt` | Terraform(`mise run infra-init` / `infra-plan` / `infra-apply` も同じ。`infra-validate` / `infra-fmt` は make のみ。OpenTofu なら `TF=tofu`) |
| `make deploy` | web・recsys のイメージをビルドして push し、Container Apps を更新する(`mise run deploy` も同じ) |
| `make recsys-reload` | recsys を再起動して、`publish` 後の索引を読み直させる |
| `make deploy-pipeline` / `make pipeline-run` | pipeline のジョブの更新 / 起動 |
| `make deploy-decider` | 判断モデルのサーバーの更新 |

いずれも実機未確認です(課金されるため人が実行します)。

### コマンド

| コマンド | 内容 |
| --- | --- |
| `mise tasks` | タスクの一覧 |
| `mise run lint` | 全言語の lint(CI と同じ内容。`.github/workflows/ci.yml` が同じ内容を実行する) |
| `mise run test` | 全言語のテスト |
| `mise run fmt` | 全言語の整形 |
| `mise run gen-types` | `packages/shared/schema` から TS の型と pydantic のモデルを生成する |

- 環境変数は、ルートの `.env.local` に書きます。mise が自動で読み込み、すべてのアプリに渡します。どんな変数があるかは `.env.example` を見てください
- commit すると、lefthook が変更したファイルを整形します
- シーンJSONの形を変えるときは、`packages/shared/schema/*.json` を直してから `mise run gen-types` を実行します。生成されたファイルは手で編集しません

## CI

PR と `main` への push で、GitHub Actions(`.github/workflows/ci.yml`)が検証を行います。シークレットは使いません。

| ジョブ | 内容 | 走る条件(変更があったとき) |
| --- | --- | --- |
| `web` | `pnpm lint && pnpm test`、`pnpm typecheck` | `apps/web`、`packages/shared`、pnpm の設定 |
| `pipeline` | `ruff format --check`、`ruff check`、`uv run pytest` | `pipeline`、`packages/shared/schema`、`datasets` |
| `recsys` | `cargo fmt --check`、`cargo clippy`、`cargo test` | `services/recsys` |
| `types` | 生成した型が JSON Schema と一致しているか(`mise run gen-types:check`) | `packages/shared`、`pipeline` の依存 |
| `infra` | `terraform fmt -check`、`terraform validate`(`mise run lint:infra`。Azure には接続しない) | `infra` |
| `ci-ok` | 上のジョブの結果をまとめる(常に走る) | 常に |

`mise.toml` と `ci.yml` を変えたときは、すべてのジョブが走ります。ツールのバージョンは `mise.toml` が正で、キャッシュは pnpm のストア、uv、cargo(`target/`)に効いています。

### 必須チェックの設定手順

リポジトリの管理者が一度だけ設定します。

1. GitHub のリポジトリで **Settings → Rules → Rulesets**(または **Settings → Branches → Branch protection rules**)を開く
2. `main` を対象に、新しいルールを作る
3. **Require status checks to pass** を有効にし、チェックに **`CI(必須チェック)`**(ジョブ `ci-ok`)だけを追加する
4. 必要なら **Require a pull request before merging** も有効にして保存する

`web` などのジョブを個別に必須にしないでください。パスフィルタでスキップされたジョブは必須チェックを満たせず、PR が止まるおそれがあります。`ci-ok` は、スキップを成功として扱い、失敗・キャンセルだけを落とします。なお、チェックを追加できるのは、一度 PR で走ったあとです。

## CD(デプロイ)とインフラ変更

Azure への認証は OIDC(フェデレーション資格情報)です。クライアントシークレットなど、Azure の長期の資格情報は GitHub に置きません(ADR-0019)。

| ワークフロー | きっかけ | 内容 |
| --- | --- | --- |
| `.github/workflows/deploy.yml` | `main` の CI が成功したあと(手動実行も可) | web・recsys・マイグレーションのイメージをビルド → Container Registry に push → **マイグレーション Job を流す(失敗したらここで止まる)** → Container Apps を更新 → `/api/health` を確認 |
| `.github/workflows/infra.yml` | 手動実行(`workflow_dispatch`) | `terraform plan`(要約に出る)→ environment `infra-apply` の承認 → `terraform apply`(承認した plan をそのまま適用) |

変数(`AZURE_CLIENT_ID_DEPLOY` / `AZURE_CLIENT_ID_INFRA`)が空のあいだ、これらは何もせず終わります。下の設定を人が行ってから動きます。**以下はすべて Azure の課金とアクセス権に関わるため、人が実行します。**

### 1. Azure 側(最初の1回)

前提: `az login` 済み、Terraform の state 用 Storage(`infra/bootstrap/bootstrap.sh`)と、`mise run infra-apply` による最初のインフラ作成が済んでいること。以下の `<...>` は自分の値に置き換えます。

アプリ登録は 2 つ作ります(権限を分けるため)。

| アプリ登録 | 使う場面 | ロール |
| --- | --- | --- |
| `opendopa-gh-deploy` | `deploy.yml` | Container Registry に `AcrPush`、リソースグループ `rg-opendopa-<env>` に `Container Apps Contributor`(イメージの更新に必要な最小の権限) |
| `opendopa-gh-infra` | `infra.yml` | サブスクリプションに `Contributor` と `Role Based Access Control Administrator`(Terraform が `AcrPull` の割り当てを作るため)、state の Storage Account に `Storage Blob Data Contributor` |

```bash
# 例: deploy 用(infra 用も同じ要領で名前とロールを変える)
APP_ID=$(az ad app create --display-name opendopa-gh-deploy --query appId -o tsv)
az ad sp create --id "$APP_ID"
# フェデレーション資格情報: environment dev の実行だけを信頼する
az ad app federated-credential create --id "$APP_ID" --parameters '{
  "name": "gh-env-dev",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "repo:proto08/opendopa:environment:dev",
  "audiences": ["api://AzureADTokenExchange"]
}'
SP_ID=$(az ad sp show --id "$APP_ID" --query id -o tsv)
az role assignment create --assignee-object-id "$SP_ID" --assignee-principal-type ServicePrincipal \
  --role AcrPush --scope "$(az acr show -n <ACR名> --query id -o tsv)"
az role assignment create --assignee-object-id "$SP_ID" --assignee-principal-type ServicePrincipal \
  --role "Container Apps Contributor" --scope "$(az group show -n rg-opendopa-<env> --query id -o tsv)"
```

`opendopa-gh-infra` のフェデレーション資格情報の subject は 2 つ(`repo:proto08/opendopa:environment:infra-plan` と `repo:proto08/opendopa:environment:infra-apply`)です。

### 2. GitHub 側

**Settings → Environments** で次の 3 つを作ります。

| environment | 用途 | 設定 |
| --- | --- | --- |
| `dev` | deploy | 承認なし(必要なら Deployment branches を `main` に限定する) |
| `infra-plan` | plan | 承認なし |
| `infra-apply` | apply | **Required reviewers** に承認者を入れる。Deployment branches を `main` に限定する |

**Settings → Secrets and variables → Actions → Variables** に次を登録します(値は秘密ではありません)。

| 変数 | 値 |
| --- | --- |
| `AZURE_TENANT_ID` / `AZURE_SUBSCRIPTION_ID` | テナント ID / サブスクリプション ID |
| `AZURE_CLIENT_ID_DEPLOY` / `AZURE_CLIENT_ID_INFRA` | 上の 2 つのアプリ登録のクライアント ID |
| `AZURE_RESOURCE_GROUP` / `ACR_NAME` / `WEB_APP_NAME` / `RECSYS_APP_NAME` / `MIGRATE_JOB_NAME` | `terraform output` の `resource_group_name` / `registry_name` / `web_app_name` / `recsys_app_name` / `migrate_job_name`(`MIGRATE_JOB_NAME` が空のあいだ、マイグレーションの手順は飛ばされる。Job を作る infra の apply 後に設定する) |
| `TF_ENV_NAME` / `TF_NAME_SUFFIX` | `terraform.tfvars` の `env_name` / `name_suffix`(suffix なしなら空) |
| `TFSTATE_RESOURCE_GROUP` / `TFSTATE_STORAGE_ACCOUNT` | `infra/backend.hcl` の `resource_group_name` / `storage_account_name` |

**Secrets** には、アプリの設定値だけを、`infra-plan` と `infra-apply` の両方の environment secrets として登録します(Azure の資格情報ではありません)。

| Secret | 内容 |
| --- | --- |
| `TF_POSTGRES_ADMIN_PASSWORD` | `TF_VAR_postgres_admin_password` と同じ値(16 文字以上) |
| `TF_INTERNAL_TOKEN` | `TF_VAR_internal_token` と同じ値(16 文字以上) |
| `TF_RECSYS_DATABASE_URL` | `TF_VAR_recsys_database_url`(読み取り専用ロールを作る前は空) |
| `TF_PLAN_PASSPHRASE` | plan ファイル(artifact)を暗号化・復号するパスフレーズ。長いランダム文字列を、`infra-plan` と `infra-apply` の両方に**同じ値**で登録する。plan ファイルには DB パスワードなどが入り、このリポジトリは public で artifact を誰でも取得できるため、暗号化して渡す |

### 3. 使い方

- デプロイ: `main` に merge すると、CI が通ったあとに `Deploy` が走ります。手動で再デプロイするときは Actions の `Deploy` から **Run workflow** します。
- マイグレーション: `db/migrations` に足した SQL は、デプロイのときに Container Apps Job(`db/Dockerfile`、`dbmate up`)が未適用の分だけ流します。アプリの更新より前に流れるため、旧バージョンのアプリが動いているあいだに適用されても壊れない変更(列の追加など)にしてください。
- インフラ変更: Actions の `Infra` から **Run workflow** → `plan` の要約を確認 → `infra-apply` の承認 → `apply`。
- 最小構成から始める(無料試用など): 必須は Resource Group、Container Registry、Log Analytics、Postgres、Container Apps で、Azure OpenAI(`enable_openai`)、Blob(`enable_storage`)、Front Door(`enable_cdn`)は `terraform.tfvars` で `false` にできます(既定は `true`。`enable_openai = false` のときは `AZURE_OPENAI_*` が空になります)。変数は `.env.example` の `TF_VAR_*` と `infra/terraform.tfvars.example` を参照してください。

## Azure 環境をゼロから作る・消す

新しい `env_name` で、Azure 環境を最初から作る手順です。**Azure の課金とアクセス権に関わるため、人が実行します**(自動化したワークフローでは行いません)。CI/CD の初期設定(OIDC・GitHub の変数)は前節の「CD(デプロイ)とインフラ変更」のとおりです。

この手順は、既存の設定(`infra/`、`Makefile`、`.github/workflows/`)の読み取りに基づいて書いたもので、実際の Azure 環境での動作確認はまだしていません。実行して食い違いがあれば、この README を直してください。

前提: `az login` 済み(サブスクリプションで Owner か、Contributor と User Access Administrator)、`docker`、`terraform`(または `TF=tofu`)、`dbmate`(`mise install` で入る)。

### 作る

```bash
# 1. state 用の Storage を作る(最初の1回だけ。infra/backend.hcl が書かれる)
TFSTATE_SUFFIX=ab12 ENV_NAME=demo ./infra/bootstrap/bootstrap.sh

# 2. 設定を用意する(terraform.tfvars はコミットしない)
cp infra/terraform.tfvars.example infra/terraform.tfvars   # env_name を新しい名前にする
export TF_VAR_postgres_admin_password='...'                # 16 文字以上
export TF_VAR_internal_token='...'                         # 16 文字以上

# 3. インフラを作る
make infra-init && make infra-plan && make infra-apply

# 4. DB のマイグレーションを流す(リポジトリのルートで実行する。DBMATE_MIGRATIONS_DIR=db/migrations は mise.toml が設定する)
#    Postgres は Azure 内サービスからのみ許可のため、手元から流すときは自分の IP を一時的に許可し、流した後に消す
RG="$(terraform -chdir=infra output -raw resource_group_name)"
PG="$(terraform -chdir=infra output -raw postgres_fqdn | cut -d. -f1)"   # サーバー名はホスト名の先頭
MYIP="$(curl -s https://api.ipify.org)"
az postgres flexible-server firewall-rule create -g "$RG" --server-name "$PG" --name tmp-migrate \
  --start-ip-address "$MYIP" --end-ip-address "$MYIP"
#    recsys 用の読み取り専用ロールは dbmate より先に作る(GRANT のマイグレーションはロールがないと何もしない)。手順は後述の「初回データを入れる」の 1
DATABASE_URL="$(terraform -chdir=infra output -raw database_url)" mise exec -- dbmate up
az postgres flexible-server firewall-rule delete -g "$RG" --server-name "$PG" --name tmp-migrate --yes   # 必ず消す

# 5. イメージをビルドして Container Apps を更新する
make deploy
```

### 確認する

```bash
WEB_URL="$(terraform -chdir=infra output -raw web_url)"

# /api/health が 200(DB 接続を含む。DB に繋がらなければ 503)
curl -fsS -o /dev/null -w '%{http_code}\n' "$WEB_URL/api/health"

# recsys が外部から届かない(内部 ingress のみ)。名前解決できない、または接続できないことを確かめる
RECSYS_FQDN="$(terraform -chdir=infra output -raw recsys_internal_url | sed 's#^https\?://##')"
curl -sS --max-time 10 "https://$RECSYS_FQDN/healthz" || echo "届かない(期待どおり)"
```

`/api/health/recsys` は web から recsys への到達を確認します。recsys に索引を読ませるには、pipeline の `publish` のあとに `make recsys-reload` を実行します(前述)。

### 初回データを入れる

`make deploy` の直後は DB が空で、フィードに動画が出ません。次の順で入れます。**Azure への書き込みなので人が実行します。** `.env.local` には手元用の `DATABASE_URL` が入っていて mise が読み込むため、Azure 向けの値は必ず各コマンドの前で上書きします(`.env.local` は編集しません)。以降は手順 4 の一時ファイアウォール規則(`tmp-migrate`)を作った状態で行い、最後に消します。

```bash
ADMIN_URL="$(terraform -chdir=infra output -raw database_url)"     # 管理者ロール。sslmode=require
RO_PASSWORD='...'                                                   # 読み取り専用ロールのパスワード(英数字のみ推奨。URL に入れるため)

# 1. 読み取り専用ロール opendopa_recsys を作る(最初の1回。dbmate up より先)
psql "$ADMIN_URL" -c "CREATE ROLE opendopa_recsys LOGIN PASSWORD '$RO_PASSWORD'"
#    dbmate up を先に流してしまった場合は、ロールを作ったあとに次の GRANT を psql で流す
#    (db/migrations/*grant_recsys* と同じ内容)
#    GRANT SELECT ON embeddings, clusters, meta TO opendopa_recsys;
#    GRANT SELECT (id, dataset_id, status) ON videos TO opendopa_recsys;

# 2. マイグレーション(手順 4 のとおり)
DATABASE_URL="$ADMIN_URL" mise exec -- dbmate up

# 3. recsys に読み取り専用ロールの URL を渡す(Terraform。ホストは database_url と同じ)
RO_URL="$(echo "$ADMIN_URL" | sed "s#//[^@]*@#//opendopa_recsys:$RO_PASSWORD@#")"
export TF_VAR_recsys_database_url="$RO_URL"      # CI の infra ワークフローを使うなら GitHub の TF_RECSYS_DATABASE_URL に同じ値
make infra-plan && make infra-apply

# 4. 動画・埋め込み・クラスタを DB に、シーン JSON と音声を Blob に入れる(リポジトリのルートで)
export DATABASE_URL="$ADMIN_URL"
export STORAGE_CONNECTION_STRING="$(terraform -chdir=infra output -raw storage_connection_string)"
# 音声の URL の前に付ける値。未設定だと相対パスのまま入り音声が再生されない。.env.local / .env.example の http://localhost:3000/media は Azure では404になるので必ず上書きする
# 音声は Blob の media コンテナにあり、URL は <MEDIA_BASE_URL>/<動画ID>/<n>.mp3 になる。output の値(アカウント直下、CDN があれば Front Door)の末尾に /media を付ける。付け忘れると 400 になり音声が鳴らない
export MEDIA_BASE_URL="$(terraform -chdir=infra output -raw media_base_url)/media"
# 埋め込みを Azure OpenAI で作るなら AZURE_OPENAI_ENDPOINT / AZURE_OPENAI_API_KEY / AZURE_OPENAI_EMBED_DEPLOYMENT も
# terraform output の値で設定する。音声は TTS_PROVIDER=voicevox(手元で VOICEVOX を起動しておく)
# mise 経由(mise exec -- uv run)にしない: mise は .env.local を読み込み、上で export した値を手元用の値で上書きしうるため。素の uv run なら export した値がそのまま使われる
cd pipeline && uv run opendopa all
#    tts と embed を手元で済ませてあるときは all ではなく publish だけ(all は生成からやり直す): uv run opendopa publish
#    件数だけ確かめるなら: uv run opendopa publish --dry-run

# 5. recsys に索引を読み直させる(publish のあと。reload の警告が出るのは正常。az login 済みで)
cd .. && make recsys-reload

# 6. 一時ファイアウォール規則を消す(手順 4 と同じ。必ず消す)
az postgres flexible-server firewall-rule delete -g "$RG" --server-name "$PG" --name tmp-migrate --yes
```

順序の理由: ロール → マイグレーション(GRANT がロールを前提にする)→ `TF_VAR_recsys_database_url`(recsys が読む URL)→ publish(索引の元データ)→ `make recsys-reload`(recsys は起動時にだけ索引を読む)。`publish` は `videos` を `id` で upsert し、`embeddings` と `clusters` を入れ直します(視聴・いいねの履歴は消しません。`docs/decisions/2026-11-07-etl-job-and-video-refresh.md`)。再実行しても同じ結果になります。

確認: `curl "$WEB_URL/api/health/recsys"` が 200、`$WEB_URL` を開いてフィードに動画が出て、音声が再生されること。出ないときは、`az containerapp logs show` で recsys のログ(起動時の索引の読み込み件数)を見ます。

### 消す

```bash
terraform -chdir=infra destroy        # 作った環境を消す。確認の入力が要る
# state 用の Storage(rg-opendopa-tfstate)は別に作ったものなので、不要なら人が az group delete で消す
```

`destroy` はデータ(DB・Blob)も消します。残したいデータがあれば、先に取り出してください。Front Door と Postgres は課金が続くので、使い終わったら消します。

## ドキュメント

- [設計書](docs/design_doc.md)
- [データ定義書](docs/data.md)
- [決定の記録](docs/DECISIONS.md)(2026-11-05 までの分。ADR の索引を兼ねる)
- [ADR](docs/adr/)(Issue 単位の大きな決定)と [小さな決定](docs/decisions/)(1 決定 1 ファイル)。索引は `mise run decisions-index`
- [pipeline の README](pipeline/README.md)(新しいデータセットの足し方)
- [ハッシュタグと絞り込みの設計](docs/hashtag_design.md)(BFF の API まで実装済み)
- [看板(状態ラベル)](docs/kanban.md): Claude Code の `/sleep`・`/start-task`・`/pr-review` が使うラベルの取り決め。`mise run sleep-scan` が、レビュー・実装などの対象を洗い出す(`docs/decisions/2026-11-06-sleep-scan-and-idle.md`)
- [CLAUDE.md](CLAUDE.md): Claude Code 向けの案内
