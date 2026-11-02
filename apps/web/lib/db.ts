import { Pool } from "pg";

// DB の読み書きは、すべて Next.js が行う(設計書 §0.2)。接続は環境変数 DATABASE_URL から取る。
let pool: Pool | undefined;

export function getPool(): Pool {
  if (!pool) {
    const connectionString = process.env.DATABASE_URL;
    if (!connectionString) {
      throw new Error("DATABASE_URL is not set");
    }
    pool = new Pool({ connectionString, connectionTimeoutMillis: 2000 });
  }
  return pool;
}

/** DB に接続して `SELECT 1` が返るかを確かめる。 */
export async function pingDb(): Promise<boolean> {
  try {
    await getPool().query("SELECT 1");
    return true;
  } catch {
    return false;
  }
}
