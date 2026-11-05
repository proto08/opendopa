-- migrate:up
-- recsys が status='excluded' の動画を除外できるよう、videos.status の SELECT を足す(Issue #36)。
-- scene・csv_row などの列は読めないままにする。ロールがない環境では何もしない。
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'opendopa_recsys') THEN
    GRANT SELECT (status) ON videos TO opendopa_recsys;
  END IF;
END
$$;

-- migrate:down
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'opendopa_recsys') THEN
    REVOKE SELECT (status) ON videos FROM opendopa_recsys;
  END IF;
END
$$;
