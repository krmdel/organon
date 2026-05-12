import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
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
  title: "Organon Dashboard",
  description: "Scientist-facing UI for Organon — literature search, hypothesis, data, figures, drafting.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <head>
        {/* Phase 65 (v2.2) — M4: pre-hydration density script. Reads
            localStorage 'organon.density' synchronously in <head> so the
            cascade is correct before paint, avoiding the flash-of-
            default-density. Three lines, dependency-free, blocks paint
            for ~0.1ms. */}
        <script
          dangerouslySetInnerHTML={{
            __html:
              "try{var d=localStorage.getItem('organon.density');if(d==='compact'||d==='comfortable'||d==='large'){document.documentElement.setAttribute('data-density',d);}}catch(e){}",
          }}
        />
      </head>
      <body className="min-h-full">{children}</body>
    </html>
  );
}
