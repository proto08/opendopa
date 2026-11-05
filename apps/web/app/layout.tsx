import type { Metadata } from "next";
import { Dela_Gothic_One, Noto_Sans_JP } from "next/font/google";
import "./globals.css";

// 見出しと大きな数字(設計書 §3.0)
const dela = Dela_Gothic_One({
  weight: "400",
  display: "swap",
  variable: "--font-dela",
});

// 本文
const notoSansJp = Noto_Sans_JP({
  weight: ["400", "500", "700", "900"],
  display: "swap",
  variable: "--font-noto",
});

export const metadata: Metadata = {
  title: "OpenDopa",
  description: "オープンデータから作るショート動画",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="ja" className={`${dela.variable} ${notoSansJp.variable}`}>
      <body>{children}</body>
    </html>
  );
}
