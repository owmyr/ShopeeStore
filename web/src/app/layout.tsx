import type { Metadata, Viewport } from "next";
import { Plus_Jakarta_Sans } from "next/font/google";
import "./globals.css";

const plusJakartaSans = Plus_Jakarta_Sans({
  subsets: ["latin"],
  variable: "--font-plus-jakarta-sans",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Trend Scout BR • Inteligência de Mercado Shopee para Camisetas",
  description:
    "Portal semanal de inteligência de mercado para confeccionistas e lojistas de camisetas. Estampas breakout, dispersão de preços e diretrizes táticas.",
  openGraph: {
    title: "Trend Scout BR • Inteligência de Mercado Shopee",
    description:
      "Descubra as estampas mais vendidas da semana, faixas de preço de alta margem e o que pausar na produção.",
    type: "website",
    locale: "pt_BR",
  },
  robots: {
    index: true,
    follow: true,
  },
};

export const viewport: Viewport = {
  themeColor: "#030712",
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
};

/**
 * Root layout component providing theme tokens, font loading, and global styles.
 *
 * @param props Root layout children
 * @returns JSX.Element
 */
export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>): React.JSX.Element {
  return (
    <html lang="pt-BR" className={`${plusJakartaSans.variable} dark`}>
      <body className="min-h-screen bg-[#030712] text-slate-100 antialiased selection:bg-emerald-500 selection:text-slate-950">
        {children}
      </body>
    </html>
  );
}
