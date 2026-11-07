import "./footer.css";

/** 全画面共通のフッター(設計書 §15.1)。音声・BGM のクレジット(VOICEVOX は「VOICEVOX:キャラ名」)を `credits` に渡す */
export function Footer({ credits = [] }: { credits?: string[] }) {
  return (
    <footer className="siteFooter">
      <p>
        OpenDopaは非公式のアプリです。国土交通省 Project LINKS
        が公開するオープンデータをもとにしています。
      </p>
      {credits.map((credit) => (
        <p key={credit}>{credit}</p>
      ))}
    </footer>
  );
}
