import type { Metadata, Viewport } from "next";
import { Plus_Jakarta_Sans } from "next/font/google";
import "./globals.css";
import { VipProvider } from "@/context/VipContext";

const plusJakartaSans = Plus_Jakarta_Sans({
  subsets: ["latin"],
  variable: "--font-plus-jakarta-sans",
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_PORTAL_URL || "https://trendscout-shopee.vercel.app",
  ),
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
  other: {
    "darkreader-lock": "",
    "color-scheme": "dark",
  },
};

export const viewport: Viewport = {
  themeColor: "#121316",
  colorScheme: "dark",
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
};

/**
 * Root layout component providing theme tokens, font loading, global styles,
 * and freemium/VIP context provisioning.
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
    <html
      lang="pt-BR"
      className={`${plusJakartaSans.variable} dark`}
      suppressHydrationWarning
    >
      <head>
        <meta name="darkreader-lock" content="" />
        <meta name="color-scheme" content="dark" />
      </head>
      <body
        className="min-h-screen bg-[#121316] text-[#F4F3EF] antialiased selection:bg-[#E27D44] selection:text-white"
        suppressHydrationWarning
      >
        <VipProvider>{children}</VipProvider>
      </body>
    </html>
  );
}
