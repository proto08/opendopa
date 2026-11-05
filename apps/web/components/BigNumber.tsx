import type { BigNumber as BigNumberData } from "@opendopa/shared";
import { bigNumberFontSizeCqw, formatBigNumber } from "@/lib/scenePlayer";

/** 大きな数字。単位とラベルが下に付く。`countProgress`(0〜1)で 0 から数え上げる */
export function BigNumber({
  data,
  countProgress,
}: {
  data: BigNumberData;
  countProgress: number;
}) {
  const finalText = formatBigNumber(data.value, false, 1);
  const shown = formatBigNumber(data.value, data.countUp, countProgress);
  return (
    <div className="bigNumber">
      <div
        className="bigNumberValue"
        style={{ fontSize: `${bigNumberFontSizeCqw(finalText)}cqw` }}
      >
        {shown}
      </div>
      {data.unit ? <div className="bigNumberUnit">{data.unit}</div> : null}
      <div className="bigNumberLabel">{data.label}</div>
    </div>
  );
}
