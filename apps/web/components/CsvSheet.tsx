import { Sheet } from "./Sheet";

/** 元データのシート: 元の 1 行を、列名と値の表で見せる(設計書 §3.3) */
export function CsvSheet({
  datasetName,
  sourceRef,
  csvRow,
  onClose,
}: {
  datasetName: string;
  sourceRef: string;
  csvRow: [string, string][];
  onClose: () => void;
}) {
  return (
    <Sheet title="元データ" onClose={onClose}>
      <dl className="csvMeta">
        <dt>データ名</dt>
        <dd>{datasetName}</dd>
        <dt>行番号</dt>
        <dd>{sourceRef}</dd>
      </dl>
      <p className="csvNote">デモ用の仮データではなく、元データの値です。</p>
      <table className="csvTable">
        <thead>
          <tr>
            <th scope="col">列名</th>
            <th scope="col">値</th>
          </tr>
        </thead>
        <tbody>
          {csvRow.map(([name, value], i) => (
            <tr key={i}>
              <th scope="row">{name}</th>
              <td>{value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Sheet>
  );
}
