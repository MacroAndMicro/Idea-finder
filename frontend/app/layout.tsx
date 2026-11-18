import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: { default: "Idea Finder", template: "%s · Idea Finder" },
  description:
    "Evidence-backed software opportunities mined from real developer and business feedback.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-10 focus:rounded focus:bg-accent focus:px-3 focus:py-2 focus:text-accent-foreground"
        >
          Skip to content
        </a>
        <header className="border-b border-border bg-surface">
          <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
            <span className="text-lg font-semibold tracking-tight">Idea Finder</span>
            <nav aria-label="Primary">
              <Link
                href="/"
                aria-current="page"
                className="inline-flex min-h-11 items-center rounded px-3 text-sm font-medium text-accent underline-offset-4 hover:underline"
              >
                Opportunities
              </Link>
            </nav>
          </div>
        </header>
        <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">
          {children}
        </main>
      </body>
    </html>
  );
}
