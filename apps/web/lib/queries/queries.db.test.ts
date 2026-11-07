// SQL の確認。pgvector 入りの PostgreSQL を TEST_DATABASE_URL で渡したときだけ動く(なければスキップ)。
// テストごとに一時スキーマを作り、マイグレーションの 02 を流して、終わったら消す。
import { readFileSync } from "node:fs";
import { Pool } from "pg";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import {
  insertLike,
  insertView,
  loadDuration,
  loadVideoLogInfo,
} from "./actions";
import { loadClusters } from "./clusters";
import { loadEvents } from "./events";
import { loadImpressions, recordImpressions } from "./impressions";
import { countViews, loadViewLog } from "./log";
import { loadMapPoints } from "./map";
import { loadKnownTagIds, loadTags, loadVideoIdsWithAllTags } from "./tags";
import { loadVideos } from "./videos";

const url = process.env.TEST_DATABASE_URL;
const schema = `t47_${process.pid}`;

describe.skipIf(!url)("queries(DB)", () => {
  let pool: Pool;
  const q = (sql: string, params?: unknown[]) => pool.query(sql, params);

  beforeAll(async () => {
    const boot = new Pool({ connectionString: url, max: 1 });
    await boot.query(`CREATE EXTENSION IF NOT EXISTS vector`);
    await boot.query(`CREATE SCHEMA ${schema}`);
    await boot.end();
    pool = new Pool({
      connectionString: url,
      options: `-c search_path=${schema},public`,
    });
    const file = new URL(
      "../../../../db/migrations/20261104000002_create_core_tables.sql",
      import.meta.url,
    );
    const up = readFileSync(file, "utf8").split("-- migrate:down")[0];
    await q(up);
    const tagsFile = new URL(
      "../../../../db/migrations/20261107000001_create_tags.sql",
      import.meta.url,
    );
    await q(readFileSync(tagsFile, "utf8").split("-- migrate:down")[0]);

    await q(
      `INSERT INTO datasets VALUES ('d1','D1','s','あ','#111111'),('d2','D2','s','い','#222222')`,
    );
    const scene = JSON.stringify({ videoId: "x" });
    const decisions = JSON.stringify({ secret: true });
    for (const [id, ds, status] of [
      ["a", "d1", "ok"],
      ["b", "d2", "ok"],
      ["c", "d2", "excluded"],
    ]) {
      await q(
        `INSERT INTO videos (id,dataset_id,kind,category_name,headline,duration_sec,scene,csv_row,source_ref,search_text,decisions,status)
         VALUES ($1,$2,'event','c',$3,20,$4,'[["k","v"]]','行 #1','t',$5,$6)`,
        [id, ds, `h-${id}`, scene, decisions, status],
      );
    }
    await q(`INSERT INTO clusters VALUES (1,'クラスタ','#FF0000',$1,0.1,0.2)`, [
      vec(),
    ]);
    for (const [id, x] of [
      ["a", 0.1],
      ["b", 0.2],
      ["c", 0.3],
    ] as const) {
      await q(`INSERT INTO embeddings VALUES ($1,$2,$3,0.5,1,'m')`, [
        id,
        vec(),
        x,
      ]);
    }
  });

  afterAll(async () => {
    if (!pool) return;
    await pool.end();
    const drop = new Pool({ connectionString: url, max: 1 });
    await drop.query(`DROP SCHEMA ${schema} CASCADE`);
    await drop.end();
  });

  function vec(): string {
    return `[${Array.from({ length: 1024 }, (_, i) => (i === 0 ? 1 : 0)).join(",")}]`;
  }

  it("events: 視聴といいねを時刻順に。同時刻は id 順", async () => {
    await q(`INSERT INTO view_events (view_id,anon_id,video_id,watched_sec,ratio,created_at) VALUES
      ('v1','u','a',10,0.5,'2026-01-01T00:00:01Z'),('v2','u','b',20,1,'2026-01-01T00:00:03Z'),
      ('vx','other','a',1,0.1,'2026-01-01T00:00:00Z')`);
    await q(`INSERT INTO like_events (anon_id,video_id,liked,created_at) VALUES
      ('u','a',true,'2026-01-01T00:00:02Z'),('u','a',false,'2026-01-01T00:00:04Z'),
      ('u','b',true,'2026-01-01T00:00:04Z')`);
    expect(await loadEvents(pool, "u")).toEqual([
      { type: "view", videoId: "a", ratio: 0.5 },
      { type: "like", videoId: "a", liked: true },
      { type: "view", videoId: "b", ratio: 1 },
      { type: "like", videoId: "a", liked: false },
      { type: "like", videoId: "b", liked: true },
    ]);
  });

  it("tags: 件数は ok の動画だけ。AND で絞り、未知の ID を見分ける", async () => {
    await q(
      `INSERT INTO tags (id,kind,label,yomi,sort) VALUES
         ('dataset:x','dataset','X','えっくす',1),
         ('region:hokkaido','region','北海道','ほっかいどう',2),
         ('region:empty','region','空','から',3)`,
    );
    // a(ok): x + 北海道、b(ok): x、c(excluded): x + 北海道
    for (const [v, t] of [
      ["a", "dataset:x"],
      ["a", "region:hokkaido"],
      ["b", "dataset:x"],
      ["c", "dataset:x"],
      ["c", "region:hokkaido"],
    ])
      await q(`INSERT INTO video_tags VALUES ($1,$2)`, [v, t]);

    expect((await loadTags(pool)).map((t) => [t.id, t.count])).toEqual([
      ["dataset:x", 2],
      ["region:hokkaido", 1],
      ["region:empty", 0],
    ]);
    expect((await loadVideoIdsWithAllTags(pool, ["dataset:x"])).sort()).toEqual(
      ["a", "b"],
    );
    expect(
      await loadVideoIdsWithAllTags(pool, ["dataset:x", "region:hokkaido"]),
    ).toEqual(["a"]);
    expect(
      await loadVideoIdsWithAllTags(pool, ["dataset:x", "region:empty"]),
    ).toEqual([]);
    expect([...(await loadKnownTagIds(pool, ["dataset:x", "nope"]))]).toEqual([
      "dataset:x",
    ]);
  });

  it("impressions: scopeIds つきの reset は、範囲の外の配信済みを残す", async () => {
    await recordImpressions(
      pool,
      "s",
      [{ videoId: "a", reason: "near" }],
      false,
    );
    await recordImpressions(
      pool,
      "s",
      [{ videoId: "b", reason: "near" }],
      true,
      ["b"],
    );
    expect((await loadImpressions(pool, "s")).seenIds.sort()).toEqual([
      "a",
      "b",
    ]);
  });

  it("impressions: 記録は重複しても落ちず、reset で消してから入れる", async () => {
    await recordImpressions(
      pool,
      "i",
      [{ videoId: "a", reason: "first" }],
      false,
    );
    await recordImpressions(
      pool,
      "i",
      [
        { videoId: "a", reason: "near" },
        { videoId: "b", reason: "near" },
      ],
      false,
    );
    let imp = await loadImpressions(pool, "i");
    expect(imp.seenIds.sort()).toEqual(["a", "b"]);
    expect(imp.recentDatasets[0]).toBe("d2");
    const { rows } = await q(
      `SELECT reason FROM impressions WHERE anon_id='i' AND video_id='a'`,
    );
    expect(rows[0].reason).toBe("first");

    await recordImpressions(
      pool,
      "i",
      [{ videoId: "b", reason: "adventure" }],
      true,
    );
    imp = await loadImpressions(pool, "i");
    expect(imp.seenIds).toEqual(["b"]);
    expect((await loadImpressions(pool, "none")).seenIds).toEqual([]);
  });

  it("videos: ok の動画だけ。decisions は読まない", async () => {
    const m = await loadVideos(pool, ["a", "c", "zzz"]);
    expect([...m.keys()]).toEqual(["a"]);
    expect(m.get("a")).toEqual({
      id: "a",
      headline: "h-a",
      scene: { videoId: "x" },
      csvRow: [["k", "v"]],
      sourceRef: "行 #1",
    });
    expect(JSON.stringify(m.get("a"))).not.toContain("secret");
  });

  it("map と clusters", async () => {
    expect(await loadClusters(pool)).toEqual([
      { id: 1, name: "クラスタ", color: "#FF0000", cx: 0.1, cy: 0.2 },
    ]);
    const pts = await loadMapPoints(pool);
    expect(pts.map((p) => p.videoId)).toEqual(["a", "b"]);
    expect(pts[0]).toMatchObject({ datasetId: "d1", clusterId: 1 });
  });

  it("log: 新しい視聴から。reason は impressions、liked は最新のいいね", async () => {
    await recordImpressions(
      pool,
      "u",
      [
        { videoId: "a", reason: "first" },
        { videoId: "b", reason: "near" },
      ],
      false,
    );
    const log = await loadViewLog(pool, "u", 6);
    expect(log).toEqual([
      { videoId: "b", headline: "h-b", reason: "near", ratio: 1, liked: true },
      {
        videoId: "a",
        headline: "h-a",
        reason: "first",
        ratio: 0.5,
        liked: false,
      },
    ]);
    expect(await loadViewLog(pool, "u", 1)).toHaveLength(1);
    expect(await countViews(pool, "u")).toBe(2);
    expect(await countViews(pool, "nobody")).toBe(0);
  });

  it("actions: 視聴の保存は view_id の重複を無視し、duration は ok の動画だけ", async () => {
    expect(await loadDuration(pool, "a")).toBe(20);
    expect(await loadDuration(pool, "c")).toBeNull();
    expect(await loadDuration(pool, "zzz")).toBeNull();
    const v = {
      viewId: "act-v1",
      anonId: "act",
      videoId: "a",
      watchedSec: 30,
      ratio: 1,
    };
    expect(await insertView(pool, v)).toBe(true);
    expect(await insertView(pool, v)).toBe(false);
    expect(
      (await q(`SELECT 1 FROM view_events WHERE anon_id='act'`)).rows,
    ).toHaveLength(1);
  });

  it("actions: いいねは最新の状態と同じなら追加しない", async () => {
    const l = (liked: boolean) =>
      insertLike(pool, { anonId: "lk", videoId: "a", liked });
    expect(await l(false)).toBe(false); // 履歴なしで取り消し
    expect(await l(true)).toBe(true);
    expect(await l(true)).toBe(false);
    expect(await l(false)).toBe(true);
    expect(await l(false)).toBe(false);
    const { rows } = await q(
      `SELECT liked FROM like_events WHERE anon_id='lk' ORDER BY id`,
    );
    expect(rows.map((r) => r.liked)).toEqual([true, false]);
    expect(await loadEvents(pool, "lk")).toEqual([
      { type: "like", videoId: "a", liked: true },
      { type: "like", videoId: "a", liked: false },
    ]);
    // 同時に送っても 1 件だけ
    await Promise.all(
      [1, 2, 3].map(() =>
        insertLike(pool, { anonId: "lk2", videoId: "a", liked: true }),
      ),
    );
    expect(
      (await q(`SELECT 1 FROM like_events WHERE anon_id='lk2'`)).rows,
    ).toHaveLength(1);
  });

  it("actions: ロック待ちの後発も、先行のコミットを見て二重に足さない", async () => {
    // 先行がロックを持ったまま止まっている間に後発を走らせる
    const first = await pool.connect();
    await first.query("BEGIN");
    await first.query(
      "SELECT pg_advisory_xact_lock(hashtextextended($1 || ':' || $2, 0))",
      ["lk3", "a"],
    );
    const second = insertLike(pool, {
      anonId: "lk3",
      videoId: "a",
      liked: true,
    });
    await new Promise((r) => setTimeout(r, 200)); // 後発がロック待ちに入る時間
    await first.query(
      "INSERT INTO like_events (anon_id, video_id, liked) VALUES ('lk3','a',true)",
    );
    await first.query("COMMIT");
    first.release();
    expect(await second).toBe(false);
    expect(
      (await q(`SELECT 1 FROM like_events WHERE anon_id='lk3'`)).rows,
    ).toHaveLength(1);
  });

  it("actions: loadVideoLogInfo", async () => {
    await recordImpressions(
      pool,
      "inf",
      [{ videoId: "a", reason: "near" }],
      false,
    );
    await insertLike(pool, { anonId: "inf", videoId: "a", liked: true });
    expect(await loadVideoLogInfo(pool, "inf", "a")).toEqual({
      headline: "h-a",
      reason: "near",
      liked: true,
    });
    expect(await loadVideoLogInfo(pool, "nobody", "b")).toEqual({
      headline: "h-b",
      reason: null,
      liked: false,
    });
    expect(await loadVideoLogInfo(pool, "inf", "zzz")).toBeNull();
  });
});
