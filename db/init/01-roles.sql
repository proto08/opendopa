-- ローカル(docker-compose)専用: recsys 用の読み取り専用ロールを作る(ADR-0013 A3)。
-- 本番ではロールを別に作り、権限の付与は db/migrations 側が行う。
-- パスワードは .env.example の RECSYS_DATABASE_URL と合わせている(ローカル専用の値)。
CREATE ROLE opendopa_recsys LOGIN PASSWORD 'opendopa_recsys';
