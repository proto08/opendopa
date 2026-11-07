import type { Tag } from "@opendopa/shared";
import { VideoTags } from "./VideoTags";

/** 下部のテロップ。白い帯に見出し、左に赤のカテゴリ名(縦書き)。帯の上に動画のタグ */
export function Telop({
  categoryName,
  headline,
  tags = [],
  selectedTags = [],
  onTag,
}: {
  categoryName: string;
  headline: string;
  tags?: Tag[];
  selectedTags?: readonly string[];
  onTag?: (id: string) => void;
}) {
  return (
    <div className="telopWrap">
      <VideoTags tags={tags} selected={selectedTags} onTag={onTag} />
      <div className="telop">
        <div className="telopCategory">{categoryName}</div>
        <h2 className="telopHeadline">{headline}</h2>
      </div>
    </div>
  );
}
