# ADR-0013 環境構築(docker-compose と DB マイグレーション)

- Issue: #13
- 日付: 2026-11-04
- 状態: 決定

## A1 ローカルの DB

- 決定: `docker-compose.yml` に `pgvector/pgvector:0.8.1-pg16`(PostgreSQL 16 + pgvector)の1サービス `db` だけを置く。ポートは `127.0.0.1:5432` に公開し、データは名前付きボリュームに置く。web・recsys は Docker に入れず、ホストで動かす。
- 理由: 本番(Flexible Server の PostgreSQL 16)と主バージョンをそろえる。web・recsys をホストで動かすほうが、再ビルドが要らず速い。ローカルの値は `.env.example` の既定値(`opendopa` / `opendopa`)と合わせ、コピーするだけで動くようにする。

## A2 マイグレーションの実行

- 決定: `db/migrations/*.sql` を dbmate で流す。入口は `mise run db-up`(起動 → 健康確認 → `dbmate up`)で、`db-migrate`・`db-reset`・`db-new` なども `mise.toml` に置く。`DBMATE_MIGRATIONS_DIR=db/migrations` と `DBMATE_NO_DUMP_SCHEMA=true` を mise の `[env]` で渡す。ファイル名は dbmate の既定どおり `YYYYMMDDHHMMSS_名前.sql`。
- 理由: ADR-0012 A1 の続き。スキーマの dump は `pg_dump` を要するうえ、`db/migrations` が正なので、作らない。`CREATE EXTENSION vector;` は設計書 §12 のとおり、アプリのマイグレーションで実行する(Terraform には置かない)。

## A3 recsys 用の読み取り専用ロール

- 決定: ロール `opendopa_recsys` の作成は DB の外で行う(ローカルは `db/init/01-roles.sql` を compose の初期化スクリプトとして初回だけ実行)。権限の付与はマイグレーション(`grant_recsys_readonly`)で行い、`embeddings`・`clusters`・`meta` の SELECT と、`videos` の `id`・`dataset_id` 列の SELECT だけを与える(2026-11-06 に `videos.status` 列の SELECT を足した。マイグレーション `grant_recsys_videos_status`、`docs/decisions/2026-11-06-recsys-reads-meta-and-video-status.md`)。ロールがない環境では、付与を何もせずに通す。
- 理由: ロールはクラスター単位でパスワードを持つので、パスワードを含む作成を、全環境で流れるマイグレーションに書かない。付与だけをマイグレーションに置くと、テーブルを足したときに権限の漏れを同じ場所で見直せる。設計書 §6.6 の「起動時に読むのは、`embeddings`、`clusters`、`meta`、`videos`(`id`、`dataset_id`、`status`)」に合わせ、最小の権限にした(当初は `status` がなかった)。`mise run db-check` で、SELECT できて書き込みは拒否されることを確かめる。
- 運用上の前提: ロールがない環境では権限が付かないまま気づけないので、本番(Azure)では「ロール作成 → `dbmate up`」の順を守り、マイグレーションの後に `db-check` 相当(ロールで SELECT できて書き込みが拒否されること)を必ず実行する。ロールの作成と、この順序・確認の手順は、インフラを作る Issue(#17、#18 など)の Terraform・デプロイ手順に書く。ローカルは初回のボリューム作成時に init が先に走るので、`db-up` のたびの確認は要らない。ロール追加前のボリュームは `mise run db-reset` で作り直す(README に記載)。

## A4 web → recsys の内部 HTTP

- 決定: recsys の `/internal/*` は、ヘッダー `X-Internal-Token` が環境変数 `INTERNAL_TOKEN` と一致しなければ 401 にする(定数時間で比較)。`INTERNAL_TOKEN` が空なら recsys は起動しない。`/healthz` は認証なしのままにする。疎通確認用に、認証つきの `GET /internal/ping` を recsys に、それを呼ぶ `GET /api/health/recsys` を web に置く。web 側の呼び出しは `apps/web/lib/recsys-client.ts` にまとめる。`/api/health` 自体は、DB だけで 200/503 を決める(ADR-0012 A10 のまま)。
- 理由: 設計書 §6.6 の認証を、実際の API(M4a)より先に1か所に作っておくと、後から足す API が自動で認証の内側に入る。トークンなしで起動できると、設定漏れのまま公開される恐れがあるので、起動を止める。`/api/health` に recsys を混ぜると、受け入れ条件(DB に接続できれば 200)が recsys の状態に左右されるので、分けた。
