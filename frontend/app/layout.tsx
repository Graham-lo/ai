import "./globals.css";
import { Fraunces, Space_Grotesk } from "next/font/google";

const display = Fraunces({
  subsets: ["latin"],
  variable: "--font-display",
});

const body = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-body",
});

export const metadata = {
  title: "交易体检引擎",
  description: "交易诊断与复盘引擎",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${display.variable} ${body.variable}`}>
      <body className="bg-haze text-ink font-body">
        <div className="min-h-screen bg-grain">
          <header className="px-6 py-5">
            <div className="mx-auto flex max-w-6xl items-center justify-between">
              <div className="text-xl font-display">交易体检引擎</div>
              <nav className="flex gap-4 text-sm text-slate">
                <a href="/accounts" className="hover:text-ink">账户</a>
                <a href="/reports" className="hover:text-ink">报告</a>
                <a href="/transactions" className="hover:text-ink">交易日志</a>
                <a href="/sync" className="hover:text-ink">同步</a>
              </nav>
            </div>
          </header>
          {children}
        </div>
      </body>
    </html>
  );
}
