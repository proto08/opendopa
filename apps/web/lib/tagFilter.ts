// タグ絞り込みの純粋な部分(URL、候補の組み立て、強調)。設計: docs/hashtag_design.md §6

import { normalize, searchTags } from "./tagSearch";

/** `GET /api/tags` の 1 件(設計 §5.1) */
export type TagInfo = {
  id: string;
  kind: "dataset" | "region";
  label: string;
  yomi: string;
  count: number;
};

/** 一度に選べるタグの数。BFF が 5 個以上を 400 にする(§5.2) */
export const MAX_TAGS = 4;

/** 空入力のときに出す地域の数(§6.3) */
export const TOP_REGIONS = 8;

/** URL のクエリ(`?tag=a&tag=b`)から、タグ ID を読む。重複は除き、4 個まで */
export function readTagsFromSearch(search: string): string[] {
  const ids = new URLSearchParams(search).getAll("tag").filter((t) => t !== "");
  return [...new Set(ids)].slice(0, MAX_TAGS);
}

/** 他のクエリは残して、`tag` だけを置き換えたクエリ文字列(先頭の `?` つき。空なら空文字) */
export function withTagsInSearch(search: string, tags: string[]): string {
  const params = new URLSearchParams(search);
  params.delete("tag");
  for (const t of tags) params.append("tag", t);
  const s = params.toString();
  return s === "" ? "" : `?${s}`;
}

/** `/api/feed` の URL */
export function feedUrl(
  count: number,
  includeMap: boolean,
  tags: readonly string[],
): string {
  const params = new URLSearchParams({ count: String(count) });
  if (includeMap) params.set("includeMap", "1");
  for (const t of tags) params.append("tag", t);
  return `/api/feed?${params.toString()}`;
}

/** 選んでいれば外し、なければ足す(上限を超えるときは足さない) */
export function toggleTag(tags: readonly string[], id: string): string[] {
  if (tags.includes(id)) return tags.filter((t) => t !== id);
  return tags.length >= MAX_TAGS ? [...tags] : [...tags, id];
}

/** 並びが同じか */
export function sameTags(a: readonly string[], b: readonly string[]): boolean {
  return a.length === b.length && a.every((t, i) => t === b[i]);
}

/**
 * 「絞り込み中 N本」の N。AND の本数は件数の表からは分からないので、選んだタグの件数の最小値(上限)を返す。
 * 件数の表に載っていないタグがあれば null
 */
export function filteredCount(
  selected: readonly string[],
  catalog: readonly TagInfo[] | null,
): number | null {
  if (!catalog || selected.length === 0) return null;
  const counts = selected.map((id) => catalog.find((t) => t.id === id)?.count);
  if (counts.some((c) => c === undefined)) return null;
  return Math.min(...(counts as number[]));
}

export type SheetSection = { title: string | null; tags: TagInfo[] };

/**
 * 検索シートの候補。件数 0 のタグは出さない(選ぶと必ず空になるため)。
 * 空入力は「データの種類」(すべて)と「件数の多い地域」(上位 8 件)。入力があれば一致順の 1 区画
 */
export function sheetSections(
  query: string,
  catalog: readonly TagInfo[],
): SheetSection[] {
  const live = catalog.filter((t) => t.count > 0);
  if (normalize(query) === "") {
    const byCount = (a: TagInfo, b: TagInfo) => b.count - a.count;
    const datasets = live.filter((t) => t.kind === "dataset").sort(byCount);
    const regions = live
      .filter((t) => t.kind === "region")
      .sort(byCount)
      .slice(0, TOP_REGIONS);
    return [
      { title: "データの種類", tags: datasets },
      { title: "件数の多い地域", tags: regions },
    ].filter((s) => s.tags.length > 0);
  }
  const hits = searchTags(query, live).map((m) => m.tag);
  return hits.length > 0 ? [{ title: null, tags: hits }] : [];
}

export type Piece = { text: string; match: boolean };

/** `label` の中の、入力と一致した部分(連続した一致のみ)を分ける。一致しなければ全体を 1 片で返す */
export function highlightPieces(label: string, query: string): Piece[] {
  const q = normalize(query);
  if (q === "") return [{ text: label, match: false }];
  // 正規化後の各文字が、元の何文字目から来たか
  const chars = [...label];
  const normChars: string[] = [];
  const origin: number[] = [];
  chars.forEach((ch, i) => {
    for (const n of normalize(ch)) {
      normChars.push(n);
      origin.push(i);
    }
  });
  const qChars = [...q];
  const start = normChars.findIndex((_, i) =>
    qChars.every((c, k) => normChars[i + k] === c),
  );
  if (start < 0) return [{ text: label, match: false }];
  const from = origin[start];
  const to = origin[start + qChars.length - 1];
  const pieces: Piece[] = [
    { text: chars.slice(0, from).join(""), match: false },
    { text: chars.slice(from, to + 1).join(""), match: true },
    { text: chars.slice(to + 1).join(""), match: false },
  ];
  return pieces.filter((p) => p.text !== "");
}
