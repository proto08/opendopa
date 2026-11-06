import type { QueryResultRow } from "pg";

/** クエリを投げられるもの(`pg` の `Pool` / `PoolClient` がそのまま当てはまる)。テストでは差し替える。 */
export interface Queryable {
  query<R extends QueryResultRow = QueryResultRow>(
    sql: string,
    params?: unknown[],
  ): Promise<{ rows: R[] }>;
}
