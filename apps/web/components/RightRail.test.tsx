import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { CsvSheet } from "./CsvSheet";
import { RightRail } from "./RightRail";

const noop = () => {};
const rail = (liked: boolean) =>
  renderToStaticMarkup(
    <RightRail liked={liked} onLike={noop} onCsv={noop} onTaste={noop} onNext={noop} />,
  );

describe("RightRail", () => {
  it("いいね・元データ・好み・次への 4 つのボタンが出る", () => {
    const html = rail(false);
    for (const kind of ["like", "csv", "taste", "next"]) {
      expect(html).toContain(`data-kind="${kind}"`);
    }
  });

  it("押したいいねは赤く塗られ(data-liked)、aria-pressed が真になる", () => {
    expect(rail(true)).toContain('data-liked="true"');
    expect(rail(true)).toContain('aria-pressed="true"');
    expect(rail(false)).toContain('aria-pressed="false"');
  });

  it("キー入力を止めない(ボタンにフォーカスがあっても l / j / k が window に届く)", () => {
    // RightRail はフックを使わないので、関数として呼んで根の要素の props を調べる
    const root = RightRail({ liked: false, onLike: noop, onCsv: noop, onTaste: noop, onNext: noop });
    expect(root.props.onKeyDown).toBeUndefined();
    expect(root.props.onKeyUp).toBeUndefined();
    // クリックは止める(ステージの一時停止/再開に伝えない)
    expect(typeof root.props.onClick).toBe("function");
  });
});

describe("CsvSheet", () => {
  it("列名と値の表、データ名、行番号、元データである旨が出る", () => {
    const html = renderToStaticMarkup(
      <CsvSheet
        datasetName="鉄道輸送統計"
        sourceRef="行 #12"
        csvRow={[
          ["事業者", "東都鉄道"],
          ["旅客数", "1,234"],
        ]}
        onClose={noop}
      />,
    );
    expect(html).toContain("鉄道輸送統計");
    expect(html).toContain("行 #12");
    expect(html).toContain("デモ用の仮データではなく、元データの値です");
    expect(html).toContain("<th scope=\"row\">事業者</th><td>東都鉄道</td>");
    expect(html).toContain("<th scope=\"row\">旅客数</th><td>1,234</td>");
    expect(html).toContain('role="dialog"');
  });
});
