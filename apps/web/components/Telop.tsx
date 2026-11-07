/** 下部のテロップ。白い帯に見出し、左に赤のカテゴリ名(縦書き) */
export function Telop({
  categoryName,
  headline,
}: {
  categoryName: string;
  headline: string;
}) {
  return (
    <div className="telop">
      <div className="telopCategory">{categoryName}</div>
      <h2 className="telopHeadline">{headline}</h2>
    </div>
  );
}
