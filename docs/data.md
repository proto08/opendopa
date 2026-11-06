# OpenDopa データ定義書(CSVから台本を作る部分)

版: v1.0 / 作成: 2026-11-01 / 設計書: `docs/design_doc.md`

この文書は、**CSV・GeoJSONの列に関わる部分**をまとめたもの。設計書から切り出した。

- §8.3〜§8.6: 列定義YAMLのスキーマ、テンプレートの規則、判断ポイント(決定モデル)、選定、集計の部品、品質ゲート
- §8.9: テンプレート案を作らせるLLMプロンプトの要点
- §10: データセット別の定義(14ファイルの列の使い方、クリーニング、動画の切り口、注意点)

**文中の「§」は、この文書の節(上記)でなければ、設計書(`docs/design_doc.md`)の節を指す。**

---

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
# grain: group のときだけ。group_by の列で集計して1グループ=1行にする。
# aggregate は 列名: sum|mean|min|max|first|count。集計後の列は group_by と aggregate の列、元の行数 n_rows
# group_by: [PREFECTURE_NAME]
# aggregate: {TOTAL_VEHICLE_COUNT: sum, TOTAL_RENTAL_TIMES: sum, TOTAL_RENTAL_FEES: sum}
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

シーンの組み立て(#33)のための、省略できるキー(実装: `pipeline/opendopa_pipeline/scene.py`, `build.py`):

```yaml
kind: event                        # event | stat | geo。省略は grain: row → event、group → stat
headline: "{pref}で無人航空機が事故"  # 穴を含む文(40字以内)。省略、または穴が空なら、先頭の字幕の最初の文
chips: ["{pref}", "{REMARKS}"]     # 特徴のラベル。穴が空のものは省く
sparkline: trend                   # op: series の stat の名前(12点以内)
map:                               # 地点は 名前(穴を含む文)と 緯度・経度の列。type は route か points
  type: points
  points: [{name: "{place}", lat: LAT, lon: LON}]
hide: [PHONE]                      # videos.jsonl の csv_row に出さない列(個人に関わる列。§15.2)
comments:
  pool_calm: ["気をつけたい"]       # pool_<名前>。なければ既定(calm / light)
  rule: "casualty_sentence == '負傷者の報告があります。' -> none; else calm"   # `式 -> プール; ...; else プール`
select:
  score:                           # 式は 列 / abs(列) / rank_desc(列) / rank_asc(列)。weight は省略で 1
    - {expr: "abs(yoy_ratio)", weight: 1.0}
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
    state: [INCIDENT_SUMMARY, casualty_sentence]   # 判断モデルに渡す列(これだけ)。負傷の内容(CASUALTIES_SUMMARY)は渡さず、定型文にしたものを渡す
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
    - {if: "casualty_sentence == '負傷者の報告があります。' or contains(INCIDENT_SUMMARY, ['負傷'])", then: injury}
    - {if: "contains(INCIDENT_SUMMARY, ['不能', '制御'])", then: loss_of_control}
    - {if: "contains(INCIDENT_SUMMARY, ['車両', '建物', '物件', '衝突', '接触'])", then: object_damage}
    - {else: other}
```

- 選択肢は、`options_from` の型のうち、**その行で、少なくとも1つのテンプレートが埋められるもの**だけにする(決定モデルが、埋められない型を選ぶことはない)。
- 選択肢の `label` は、判断モデルへの質問に出す日本語。`id` はコード用。
- 型の数は、4〜6つに抑える(小さなモデルは、選択肢が多いと精度が落ちる)。
- ルールの `keyword` は粗い。実測(事故194行)では、「接触」が146行に出るため、ほとんどが `object_damage` に入ってしまう(123行)。「プロペラが停止し、屋根に落下した」のような文が、`loss_of_control` に入らない。**ここが、決定モデルで精度を上げたい部分**。

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
    provider: str                  # 'strands_azure' など
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
| `strands_azure` | **採用**。AWSの Strands Decider 2B を、Azure上(GPU付きContainer Apps か Azure ML)で動かし、内部APIとして呼ぶ。評価(§14.2b)に合格したら既定にする。モデルの入手元・ライセンスは実装時に確認する |
| `jev_local` | ローカルで動かす、Jevふうの判断モデル。候補は、Hugging Face の `chaoliangUNSW/Jev-Style-2B-Decision-v3`(約1.9B、Apache-2.0、`jev-style` パッケージでローカルAPIとして起動できる。Apple Siliconは `jev-style[mlx]`)。実装時に、モデルカードの手順とライセンスを確認する(提供元はTypeSafe AIとは別の組織) |
| `jev_api` | TypeSafe Jev(ホスト型のAPI。`TYPESAFE_API_KEY`)。費用・利用条件は要確認 |
| `azure_openai` | Azure OpenAI の構造化出力で、同じ質問に答えさせる(確率は、複数回の試行の割合などで近似してよい) |

**日本語の精度は未検証**。必ず §14.2b の評価を通してから、既定にする。

#### 処理量の見積もり

動画約2,100本 × 1本あたり1〜2問(型の選択と、安全チェック) ≈ 2,000〜4,000問。ローカルの2Bモデルで、1問あたりの時間は、機械によって大きく変わる。`decide` コマンドで実測し、`docs/DECISIONS.md` に記録する(キャッシュがあるので、再実行は速い)。

#### 事故データでの試作の結果(`rules`)

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

#### 各 op の引数と出力(実装: `pipeline/opendopa_pipeline/stats.py`)

`group` / `group_by` は列名(または列名のリスト)。欠損の値・欠損のグループの行は、結果も欠損にする。
`fmt:` を付けると、`<name>_text` の列に表示形(下の `fmt`)の文字列も作る(穴では `{<name>_text}`)。

| op | 引数 | 出力の列 |
| --- | --- | --- |
| `rank_in_group` | `value`、`group`(省略で全体)、`order`(`desc` 既定 / `asc`) | `<name>`(順位。同順位は同じ順位で、次は飛ぶ)、`<name>_n`(順位をつけた行数) |
| `yoy_diff` / `yoy_ratio` | `value`、`group_by`(主体)、`year` | 前年(`year - 1`)の同じ主体の行との差 / 変化率(%。(今年 - 前年) ÷ 前年の絶対値)。前年の行がない・前年が 0(率)なら欠損 |
| `share_of_total` | `value`、`group`(省略で全体) | 0〜100(%)。合計が 0 以下なら欠損 |
| `sum_by` / `mean_by` / `count_by` | `group`、`value`(`count_by` は省略可。省略で行数、あれば欠損でない行数) | 集計値(全部欠損なら `sum_by` / `mean_by` は欠損) |
| `series` | `value`、`group_by`、`order`、`max_points`(最大12) | その行の `order` 以前の `value` を時系列に並べた配列(最大12点) |
| `seq_in_group` | `group`、`order` | 1 始まりの通し番号。`order` は日付の文字列も日付順。同じ値は元の行の順、欠損は最後 |
| `is_first_time` | `value`、`group_by`、`order`、`condition`(`positive` 既定=黒字 / `negative`=赤字) | 真偽。グループの最初の行は偽 |
| `per` | `num`、`den`、`scale`(省略で 1) | `num ÷ den × scale`。分母が 0 なら欠損 |

#### 数字の日本語表記(`fmt`)

- 円・千円: 1万以上は「○万」、1億以上は「○億」、1兆以上は「○兆」(小数は1桁まで、丸めたら「約」を付ける)。例: 2,008,428,041千円 → 「約2兆84億円」ではなく「約2兆円」。**丸めは原稿を作る側の表現として許可するが、元の値から再計算して誤差0.5%以内**であること。
- 日付: `2022年12月6日11時20分`(分が0なら「11時」)。
- パーセント: 小数1桁まで。
- 順位: 「○位」。件数: 「○件」。
- 実装は `pipeline/opendopa_pipeline/fmt.py`。`fmt:` に書ける名前は `yen`(円)、`sen_yen`(千円の列)、`percent`、`rank`、`count`。derived では `op: format` で使う。
- 1桁の丸めで誤差が0.5%を超えるときは、「1億400万円」のように下の単位まで書く(1.04億を「約1億円」とはしない)。

### 8.6 品質ゲート(通らない行は `excluded` にして理由を記録)

| 検査 | 条件 |
| --- | --- |
| 未置換 | 原稿に `{` `}` が残っていない |
| 数字の照合 | 原稿に出る数字のすべてが、`numbers` の記録の表示形、または元の行の値のどれかと一致する(桁区切り、和数字表記は正規化して比較) |
| 欠損 | 必須の列(YAMLの `required`)が空でない |
| 長さ | 推定秒数が15〜30秒に入る(§8.3.1の処理後) |
| 個人情報 | 氏名らしい文字列、番号らしい文字列(電話・メール・番地)が含まれない(§15) |
| 禁止表現 | 「原因は」「責任は」「〜のせい」など、推測を示す言い回しが含まれない |
| 負傷の部位 | 負傷を示す語と同じ文に、部位の語(指・腕・顔・膝など)が含まれない(`casualty_detail`。設計書 §15.2) |
| 重複 | 同じ原稿の動画が重複しない |
| 判断 | フォールバックした判断の割合を記録する。1つのデータセットで30%を超えたら警告(`decisions_report.json`)。`pii`(noul)の確率が上限を超えた行は除外 |

実行結果として、データセットごとに「生成件数、除外件数と理由の内訳、推定秒数の最小・中央・最大」を標準出力とJSONに残す。


### 8.9(補足)テンプレート案を作らせるLLMプロンプトの要点

LLMに渡す: データセットのプロファイル(列名、型、欠損率、種類数、最長文字数、上位の値)、サンプル10行、YAMLスキーマ(§8.3)、禁止事項。指示の要点:
- 値にあることだけを述べる。原因・責任・被害の推測は書かない。
- 穴埋めは、列定義にある列名の `{}` だけを使う。
- ニュース番組風の、落ち着いた語り口。
- 出力はYAMLだけ。
- 型(グループ)ごとに、完成した文章のテンプレートを、標準・短い版・言い回し違いで書く。1行は、読み上げて5〜8秒に収める。
LLMの出力は、列名が列定義に存在するかを機械で検査してから、人が確認する。**LLMが書くのは「ひな型」だけで、数字は必ずエンジンが入れる。**


## 10. データセット別の定義(届いた14ファイル)

ファイル名は、`data/raw/<dataset_id>/` に以下の名前で置く。列名は元のまま(英語)。確認が取れていない単位は「要確認」と書くが、推定した単位で絶対値を読み上げてよい(§0.2)。

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
- **試作**: (テンプレート方式、判断は `rules`)。事故194行のうち、191行を生成(概要が空の1行と、概要だけで30秒に収まらない2行を除外)、数字の不一致0、推定19.5〜30秒。型の内訳は、`object_damage` 123、`loss_of_control` 29、`injury` 29、`other` 10。これと同じ傾向を再現できること(型の割合は、決定モデルで変わる)。
- **列**: `No.`, `OCCURRENCE_DATE`(`2022/12/6 11:20`), `OCCURRENCE_LOCATION`(都道府県+市区町村。海外の1件は長い文)、`OPERATOR`(事業者123/個人58/行政機関11/大学1/学校1)、`MODEL_OR_MANUFACTURER`, `INCIDENT_SUMMARY`(最長165字)、`CASUALTIES_SUMMARY`(なし165。他は負傷の内容)、`AIRCRAFT_DAMAGE_SUMMARY`(全損34、プロペラの破損22、なし17など)、`RECURRENCE_PREVENTION_MEASURES`(最長327字。4件は空)、`REMARKS`(事故/重大インシデントの定型文)。
- **処理**: `REMARKS` の文に「事故に該当」があれば `事故`、なければ `重大インシデント`。都道府県は先頭の `...都道府県` を正規表現で取る(194行中3行は取れない。そのときは大きな数字を「第◯号」にする)。
- **大きな数字**: 「◯◯県で◯件目」(日付順の通し番号)。取れなければ「第◯号」。
- **コメント**: 負傷者あり→なし。それ以外は落ち着いたコメントのみ(§3.5)。
- **個人情報**: 負傷の部位は読まない。「負傷者の報告があります」にとどめる(§15)。型 `injury` は概要の引用を使わず、品質ゲート `casualty_detail` が型を問わず部位の語を検出する(#108)。
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
- 動画: **比率だけ**を語る(「自己資本は総資産の{%}」と、同じ区分内の順位)。絶対額は、推定した単位で読み上げてよい(§0.2)。

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