import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "OpenDopa",
  description: "オープンデータから作るショート動画",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="ja">
      <body>{children}</body>
    </html>
  );
}
