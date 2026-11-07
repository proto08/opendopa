# ハッシュタグと絞り込みの設計

動画にハッシュタグ(`#レンタカー #北海道`)を付け、ショート画面の左上の虫眼鏡から、タグで絞り込めるようにする追加機能の設計。`docs/design_doc.md` の §0.2「実装の約束」を守る。この文書は設計書への追記ではなく、別ファイルとして置く。実装に入るとき、設計書の該当章(§3、§5、§6、§9)に反映する。

画面の例(動くモック): https://claude.ai/artifact/R2Lwq1vX1V7d9GFvgASb1e(作成者の claude.ai アカウントでのみ閲覧できる)

状態: 設計(未実装)。Issue 番号は未定。

## 1. ゴール

- 動画に、データの種類と地域のタグを付ける。
- 虫眼鏡から、タグで絞り込める。タグ名はあいまい検索できる(「北海」で北海道が出る)。
- 動画のタグをタップして、そのタグで絞り込める。

非ゴール: ユーザーが作るタグ、タグの人気順やトレンド、タグ単位のフォロー、タグのレコメンド。

## 2. 方針

- タグは **元データから機械的に作る**。LLM は使わない(§0.2)。
- 絞り込みで動画を選ぶ処理は **recsys(Rust)に任せる**。Next.js にベクトル計算を書かない(§0.2)。
- あいまい検索は **ブラウザ側の文字列マッチ**で行う。タグは数十〜百件程度なので、DB の拡張(pg_trgm など)やベクトル検索は使わない。

## 3. タグ

### 3.1 種類

| 種類(`kind`) | 例 | 元 |
| --- | --- | --- |
| `dataset`(データの種類) | `#レンタカー` `#事故` `#空き家` `#鉄道` `#内航海運` `#飛行計画` | `datasets/<id>.yaml` に `tag:` を足す。データセットごとに固定 |
| `region`(地域) | `#北海道` `#沖縄県` | 動画1本ごとの都道府県 |

- 複数のデータセットが同じタグを持てる(`rental_result` と `rental_fleet` は `#レンタカー`、`rail_*` の 6 個は `#鉄道`、`akiya_reg` と `akiya_sold` は `#空き家`、`naiko_route` と `naiko_ship` は `#内航海運`)。
- 地方ブロック(`#東北` など)は、初期版では作らない(§11)。

### 3.2 ID と表示名

- ID は `<kind>:<slug>`(例: `dataset:rental`、`region:hokkaido`)。
- 表示名は `#` を付けずに持つ(`label`)。画面で `#` を付ける。
- 検索用に、かなの読み(`yomi`)を持つ(例: 北海道 → ほっかいどう)。

### 3.3 地域の取り方(pipeline)

都道府県の正規化表を `pipeline` に1つ持つ(47 件。名称、slug、読み)。全データセットで共通に使い、都道府県名はこの表で引く。取れない動画は、地域タグを付けない。

| データセット | 地域の元 | 備考 |
| --- | --- | --- |
| `accident` | `OCCURRENCE_LOCATION` の先頭の都道府県 | 194 行中 3 行は取れない(`docs/data.md`) |
| `rental_result` | `PREFECTURE_NAME` | 都道府県別 1 本なので確実 |
| `rental_fleet` | `OFFICE_VEHICLE_ALLOCATION_LIST_LOCATION` | |
| `akiya_reg` / `akiya_sold` | 都道府県の列(要確認) | 列名を `docs/data.md` と CSV で確認する |
| `naiko_route` / `naiko_ship` | 地名の列(要確認) | 緯度経度しかなければ付けない |
| `flightplan` | 要確認 | GeoJSON の属性に地名がなければ付けない |
| `rail_*` | なし | `JURISDICTION`(運輸局)は都道府県にならないので、付けない(§11) |

元データにない地名を作らない。取れなかった動画は、地域タグを持たない。このため、地域タグで絞ると、一部のデータセットは出なくなる。これは仕様とする。

## 4. データモデル

### 4.1 シーンJSON

`packages/shared/schema/scene.schema.json` に `tags` を足し、`mise run gen-types` で型を作り直す。生成物は手で編集しない。

```jsonc
"tags": [
  { "id": "dataset:rental",  "kind": "dataset", "label": "レンタカー" },
  { "id": "region:hokkaido", "kind": "region",  "label": "北海道" }
]
```

`tags` は必須とし、タグがなければ空配列にする。既存の動画は、`pipeline publish` をやり直して置き換える。

### 4.2 DB(マイグレーション1本)

```sql
-- migrate:up
CREATE TABLE tags (
  id     text PRIMARY KEY,          -- 'region:hokkaido' / 'dataset:rental'
  kind   text NOT NULL,             -- 'dataset' | 'region'
  label  text NOT NULL,             -- '北海道'
  yomi   text NOT NULL,             -- 'ほっかいどう'
  sort   int  NOT NULL DEFAULT 0
);
CREATE TABLE video_tags (
  video_id text NOT NULL REFERENCES videos(id),
  tag_id   text NOT NULL REFERENCES tags(id),
  PRIMARY KEY (tag_id, video_id)
);
CREATE INDEX ON video_tags (video_id);
-- migrate:down
DROP TABLE video_tags;
DROP TABLE tags;
```

- `pipeline publish` が、`videos` と同じ置き換えの規則(`docs/decisions/2026-11-06-publish-replace-semantics.md`)で書き込む。
- recsys 用の読み取りロール(`opendopa_recsys`)には、権限を足さない。recsys は DB を読まず、候補をリクエストで受け取る(§5.2)。
- 件数(`count`)は `videos.status = 'ok'` の動画だけを数える。`excluded` の動画は数えない。

## 5. API

### 5.1 `GET /api/tags`

全タグと件数を返す。タグが少ないので、全件を1回で返し、ブラウザがキャッシュする。

```jsonc
{ "tags": [ { "id": "region:hokkaido", "kind": "region", "label": "北海道", "yomi": "ほっかいどう", "count": 42 } ] }
```

`Cache-Control: no-store`(設計書 §6.5)は変えない。ブラウザ側では、画面を開いている間だけ保持する。

### 5.2 `GET /api/feed?tag=…`

既存の feed に `tag` を足す(複数指定できる。例: `tag=dataset:rental&tag=region:hokkaido`)。

1. `tag` が指定されていれば、`video_tags` から **指定したすべてのタグを持つ動画ID**を引く(AND)。
2. recsys の `POST /internal/feed` に、`candidateIds`(省略可)として渡す。
3. recsys は、配信済みの除外と `status` の除外に加えて、`candidateIds` に含まれない動画を候補から外す。選び方(近傍、探索、冒険。設計書 §7.4)は変えない。
4. 候補が尽きたら、`items: []` と `reason: "pool_empty"` を返す。

検証: `tag` は既知の ID だけ(未知の ID は 400)。個数は 4 以下(超えたら 400)。zod で検証する(`docs/decisions/2026-11-06-bff-zod-validation.md`)。

初回取得の `count=2&includeMap=1` は変えない。絞り込みを変えたときは、`includeMap=0` で取り直す。

recsys の変更は、純粋関数側(`recsys-core`)に候補の絞り込みを足し、HTTP 側は受け取るだけにする。`candidateIds` が省略されたときは、今と同じ動きにする。

### 5.3 好みの更新

絞り込み中の視聴・いいねも、通常どおり好みに反映する(§7.2、§7.3 の式は変えない)。絞り込みは探索の幅を狭めるだけとする。

## 6. 画面

元の画面(`apps/web/components/` の `Feed`、`Slide`、`Stage`、`RightRail`)の構成を変えず、足す。

### 6.1 虫眼鏡

- ステージの左上、ロゴ(速報タブ)の下に置く。ロゴが左上を使っているため。位置はステージ幅基準(`cqw`)で、右レールと同じ大きさ(11cqw)。
- 絞り込みがないときは、アイコンだけ。絞り込み中は、黄色にして「絞り込み中 N本」を出す。
- 押すと検索シートが開く。

### 6.2 動画のタグ

- テロップの上、左側に `#レンタカー #北海道` を並べる(右レールと重ならない幅にする)。
- `dataset` はシアン、`region` は白。選択中のタグは黄色。
- タップすると、そのタグで絞り込む。もう一度タップすると外す。

### 6.3 検索シート

- 見えている動画のステージの上に、下からせり出す(ステージの高さの 74%)。シートは画面に1つだけ置く。
- 構成は、見出しと「閉じる」、入力欄、選択中のタグ(`×` で外す)、候補リスト。
- 候補の1行は、`種別` または `地域` のラベル、`#タグ名`(入力と一致した部分を強調)、`N本`。
- 入力が空のときは、「データの種類」(すべて)と「件数の多い地域」(上位 8 件)を出す。
- 入力に合うタグがないときは、「『…』に合うタグはありません。都道府県名やデータの種類で探してください。」を出す。
- 候補を選ぶとシートを閉じ、絞り込みを適用する。すでに選択済みのタグは薄く表示し、選べない。
- 開いている間は、フィードのスクロールと、↑ ↓ j k l のキーを止める(元の `Feed.tsx` の `sheetOpen` と同じ扱い。`hold` で再生も止める)。Esc で閉じる。
- フォーカスは、開いたら入力欄へ、閉じたら虫眼鏡へ戻す。

### 6.4 絞り込みの適用

- 条件が変わったら、フィードのキューと先読みを捨て、条件つきで取り直し、先頭へ戻る。
- 候補がない(`pool_empty`)ときは、ステージの中に「見終わりました。この条件の動画はありません。」と、「タグを全部外す」ボタンを出す。
- 絞り込みの状態は、URL のクエリ(`?tag=region:hokkaido&tag=dataset:rental`)に持つ。リロードや共有で戻せる。
- PC の右パネル(好み)の表示は変えない。スマホの好みシートと、検索シートは同時に開かない。

## 7. あいまい検索(ブラウザ側)

純粋関数として `apps/web/lib/` に置き、テストを書く。

正規化: NFKC、小文字化、カタカナをひらがなに、空白を除く。入力と、各タグの `label` と `yomi` の両方に同じ正規化をかける。

点数(高いものから):

| 点 | 条件 | 例 |
| --- | --- | --- |
| 4 | `label` の前方一致 | `北海` → 北海道 |
| 3 | `label` の部分一致、または `yomi` の前方一致 | `海道` → 北海道、`ほっかい` → 北海道 |
| 2 | `yomi` の部分一致 | `かいどう` → 北海道 |
| 1 | 入力が 2 文字以上で、文字の順序を保った飛び飛び一致(`label` または `yomi`) | `北道` → 北海道 |
| 0 | 一致しない | 出さない |

同点は、`count` の多い順に並べる。

## 8. 実装の分け方(Issue 単位の目安)

| # | 内容 | 主な場所 |
| --- | --- | --- |
| 1 | 都道府県の正規化表、`datasets/*.yaml` の `tag:`、各データセットの地域の取り出し、スキーマと型の生成、マイグレーション、`publish` | `pipeline`、`packages/shared/schema`、`db/migrations` |
| 2 | `candidateIds` の受け取りと絞り込み(純粋関数のテストつき) | `services/recsys` |
| 3 | `GET /api/tags`、`GET /api/feed?tag=` | `apps/web/app/api` |
| 4 | 虫眼鏡、検索シート、動画のタグ、あいまい検索、URL の同期 | `apps/web/components`、`apps/web/lib` |
| 5 | 設計書(§3、§5、§6、§9)への反映と、`docs/decisions/` への記録 | `docs` |

1 を先に行う。2 と 3 は、1 のあとに並行できる。4 は、3 の API が決まれば、ダミーのタグで先に進められる(既存のダミーフィード `app/dev/stage` と同じ考え方)。

## 9. テスト

- pipeline: 都道府県の取り出し(取れる/取れない、海外の長い文)、タグの付与、`publish` の置き換え。
- recsys-core: `candidateIds` なし(今と同じ)、あり(候補だけから選ぶ)、空(`pool_empty`)。
- web(API): `tag` の検証(未知の ID、個数超過)、AND の絞り込み、`pool_empty`。
- web(画面): あいまい検索の純粋関数(§7 の表の例すべて)、シートが開いている間のキーとスクロールの停止、`pool_empty` の表示。
- 型: `cd apps/web && mise exec -- pnpm typecheck`。作業の最後に `mise run lint` と `mise run test`。

## 10. 受け入れ基準

1. 動画に、データの種類のタグが付き、都道府県が取れる動画には地域のタグも付く。
2. 虫眼鏡から、「北海」で北海道が出て、選ぶと北海道のタグを持つ動画だけが流れる。
3. 動画のタグをタップして、同じように絞り込める。
4. 2 つのタグを選ぶと、両方を持つ動画だけが流れる。
5. 候補がなくなると、案内と「タグを全部外す」が出る。
6. 絞り込みを URL で復元できる。
7. 絞り込みをしないときの動きは、今と変わらない。

## 11. 決めたこと(既定値)と未決事項

実装に入るとき、`docs/decisions/` に1決定1ファイルで記録する。

| 論点 | 既定値 | 代案 |
| --- | --- | --- |
| タグ間の条件 | AND | 同じ種類は OR(地域を複数選べる) |
| 地方ブロックのタグ(`#東北` など) | 作らない | 都道府県から表で引いて付ける |
| 運輸局のタグ(鉄道) | 作らない | `#関東運輸局` を `region` に含める |
| 候補を使い切ったとき | 案内とタグを外すボタン | 見た動画の再表示を許す |
| 絞り込み中の好みの更新 | 通常どおり | 絞り込み中は学習しない |
| 虫眼鏡の位置 | ロゴの下 | ロゴを動かして左上の角に置く |

未確認(実装の最初に確認する):

- `akiya_*`、`naiko_*`、`flightplan` に、都道府県を取れる列があるか。
- 絞り込み中に、recsys の「発見」と「連続」の動き(`docs/decisions/2026-11-07-recsys-discovery-and-streak.md`)が、候補の少なさで崩れないか。候補が少ないタグ(数本)での挙動を、疑似ユーザーで確認する。
- 同じ都道府県名でも、表記ゆれ(「東京」「東京都」)が元データにどれだけあるか。正規化表で吸収する。
