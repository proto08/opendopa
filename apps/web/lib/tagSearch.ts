// タグ名のあいまい検索(純粋関数)。設計: docs/hashtag_design.md §7

export type SearchableTag = {
  label: string;
  yomi: string;
  count: number;
};

export type TagMatch<T extends SearchableTag> = {
  tag: T;
  score: 1 | 2 | 3 | 4;
};

/** NFKC、小文字化、カタカナをひらがなに、空白を除く。 */
export function normalize(text: string): string {
  return text
    .normalize("NFKC")
    .toLowerCase()
    .replace(/[ァ-ヶ]/g, (c) => String.fromCharCode(c.charCodeAt(0) - 0x60))
    .replace(/\s+/gu, "");
}

/** `needle` の文字が、順序を保ったまま `haystack` に含まれるか。 */
function isSubsequence(needle: string, haystack: string): boolean {
  const n = [...needle];
  let i = 0;
  for (const ch of haystack) {
    if (ch === n[i]) i++;
    if (i === n.length) return true;
  }
  return n.length === 0;
}

/** 0 は一致なし。 */
export function scoreTag(query: string, tag: SearchableTag): 0 | 1 | 2 | 3 | 4 {
  const q = normalize(query);
  if (q === "") return 0;
  const label = normalize(tag.label);
  const yomi = normalize(tag.yomi);
  if (label.startsWith(q)) return 4;
  if (label.includes(q) || yomi.startsWith(q)) return 3;
  if (yomi.includes(q)) return 2;
  if ([...q].length >= 2 && (isSubsequence(q, label) || isSubsequence(q, yomi)))
    return 1;
  return 0;
}

/** 一致したタグだけを、点数の高い順、同点は count の多い順に返す。空入力は空配列。 */
export function searchTags<T extends SearchableTag>(
  query: string,
  tags: readonly T[],
): TagMatch<T>[] {
  const out: TagMatch<T>[] = [];
  for (const tag of tags) {
    const score = scoreTag(query, tag);
    if (score > 0) out.push({ tag, score: score as 1 | 2 | 3 | 4 });
  }
  return out.sort((a, b) => b.score - a.score || b.tag.count - a.tag.count);
}
