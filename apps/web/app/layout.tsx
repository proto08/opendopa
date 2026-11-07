import type { Metadata } from "next";
import { Dela_Gothic_One, Noto_Sans_JP } from "next/font/google";
import { connection } from "next/server";
import { Suspense } from "react";
import { Footer } from "@/components/Footer";
import { ttsCredit } from "@/lib/credit";
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

// TTS_PROVIDER などの環境変数を、ビルド時でなく実行時に読む。
// connection() は <Suspense> の中でしか使えない(外だとプリレンダーできず build が失敗する)ため、ここだけ切り出す
async function CreditFooter() {
  await connection();
  return <Footer credit={ttsCredit()} />;
}

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="ja" className={`${dela.variable} ${notoSansJp.variable}`}>
      <body>
        {children}
        <Suspense fallback={<Footer />}>
          <CreditFooter />
        </Suspense>
      </body>
    </html>
  );
}
