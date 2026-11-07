import "./footer.css";

/** 全画面共通のフッター(設計書 §15.1)。VOICEVOX を使うときは `credit` に「VOICEVOX:キャラ名」を渡す */
export function Footer({ credit }: { credit?: string }) {
  return (
    <footer className="siteFooter">
      <p>
        OpenDopaは非公式のアプリです。国土交通省 Project LINKS
        が公開するオープンデータをもとにしています。
      </p>
      {credit ? <p>{credit}</p> : null}
    </footer>
  );
}
