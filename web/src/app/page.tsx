"use client";

import React, { useState, useEffect } from "react";
import { ShieldCheck } from "lucide-react";
import Image from "next/image";
import type { ClientReportPayload } from "@/types/intelligence";
import { FALLBACK_CLIENT_REPORT } from "@/lib/fallback-data";
import { normalizeClientReport } from "@/lib/normalize-report";
import { HeaderNav } from "@/components/HeaderNav";
import { HeroKpiTicker } from "@/components/HeroKpiTicker";
import { NicheExplorer } from "@/components/NicheExplorer";
import { BreakoutPrints } from "@/components/BreakoutPrints";
import { FabricRadar } from "@/components/FabricRadar";
import { DirectivesBoard } from "@/components/DirectivesBoard";
import { CheckoutModal } from "@/components/CheckoutModal";
import { VipUnlockModal } from "@/components/VipUnlockModal";

/**
 * Main Client-Facing Portal Page for TrendScout BR.
 * Integrates all intelligence modules into an ultra-fast, responsive dashboard for confeccionistas.
 *
 * @returns JSX.Element
 */
export default function Home(): React.JSX.Element {
  const [data, setData] = useState<ClientReportPayload>(FALLBACK_CLIENT_REPORT);

  // Hydrate with latest static JSON file if available in public folder
  useEffect(() => {
    async function loadLatestReport() {
      try {
        const res = await fetch("/data/client_report.json");
        if (res.ok) {
          const json = await res.json();
          setData(normalizeClientReport(json));
        }
      } catch {
        // Fallback data already active, graceful degradation
      }
    }
    loadLatestReport();
  }, []);

  const heroPrint = data.breakouts?.[0];

  return (
    <div className="flex min-h-screen flex-col bg-[#121316] text-[#F4F3EF]">
      {/* Sticky Header Navigation */}
      <HeaderNav edition={data.edition} />

      <main className="mx-auto flex w-full max-w-7xl flex-1 flex-col gap-12 px-4 py-12 sm:px-6 lg:px-8">
        {/* Asymmetric Editorial Hero */}
        <section aria-labelledby="hero-title" className="flex flex-col gap-12">
          {/* Header */}
          <div className="flex flex-col gap-4 text-center sm:text-left max-w-4xl">
            <span className="font-mono text-xs text-[#8E9099] tracking-wider uppercase">
              AUDITORIA DE GIRO & MARGEM • SHOPEE BRASIL
            </span>
            <h1
              id="hero-title"
              className="text-3xl font-extrabold tracking-tight text-[#F4F3EF] sm:text-4xl lg:text-5xl leading-tight"
            >
              Inteligência de Produção para Confeccionistas & Lojistas de Camisetas
            </h1>
            <p className="max-w-2xl text-sm sm:text-base text-[#8E9099] leading-relaxed">
              Consolidação pública de 497 produtos líderes na Shopee Brasil. Parâmetros técnicos de corte, gramatura e precificação auditada.
            </p>
          </div>

          {/* Asymmetrical Content Grid */}
          {heroPrint && (
            <div className="flex flex-col lg:flex-row gap-8 lg:gap-12 items-stretch">
              {/* Left Column: Spotlight Image */}
              <div className="w-full lg:w-[55%] flex-shrink-0">
                <div className="relative aspect-[3/4] w-full overflow-hidden bg-[#1A1B20] rounded-lg">
                  <Image
                    src={heroPrint.imageUrl}
                    alt={heroPrint.title}
                    fill
                    sizes="(max-width: 1024px) 100vw, 55vw"
                    className="object-cover"
                    priority
                    unoptimized
                    suppressHydrationWarning
                  />
                  <div className="absolute top-4 left-4 bg-[#121316]/80 backdrop-blur-sm border border-[#2E3038] px-3 py-1.5 text-xs font-mono text-[#F4F3EF]">
                    DESTAQUE #1
                  </div>
                </div>
              </div>

              {/* Right Column: Ficha Técnica Integrada */}
              <div className="w-full lg:w-[45%] flex flex-col justify-center">
                <div className="bg-[#1A1B20] border border-[#2E3038] rounded-lg p-6 sm:p-8">
                  <h2 className="text-sm font-semibold tracking-wide text-[#F4F3EF] uppercase mb-6">
                    Ficha Técnica Integrada
                  </h2>
                  <div className="flex flex-col divide-y divide-[#2E3038] text-sm">
                    <div className="py-4 flex justify-between items-center gap-4">
                      <span className="text-[#8E9099]">Fio & Malha</span>
                      <span className="text-[#F4F3EF] font-medium text-right">Algodão 30.1 Penteado • 180g/m²</span>
                    </div>
                    <div className="py-4 flex justify-between items-center gap-4">
                      <span className="text-[#8E9099]">Método de Estamparia</span>
                      <span className="text-[#F4F3EF] font-medium text-right">DTF Digital Têxtil / Silk</span>
                    </div>
                    <div className="py-4 flex justify-between items-center gap-4">
                      <span className="text-[#8E9099]">Custo Estimado Benchmark</span>
                      <span className="text-[#F4F3EF] font-medium text-right">R$ 13,00 — R$ 15,50</span>
                    </div>
                    <div className="py-4 flex justify-between items-center gap-4">
                      <span className="text-[#8E9099]">Preço Praticado Shopee</span>
                      <span className="text-[#F4F3EF] font-medium font-mono text-right" suppressHydrationWarning>
                        {new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(heroPrint.priceBrl)}
                      </span>
                    </div>
                    <div className="py-4 flex justify-between items-center gap-4">
                      <span className="text-[#8E9099]">Margem Bruta Operacional</span>
                      <span className="font-bold text-emerald-400 text-right">43,7%</span>
                    </div>
                    <div className="py-4 flex justify-between items-center gap-4">
                      <span className="text-[#8E9099]">Ritmo Médio Diário</span>
                      <span className="font-mono text-[#F4F3EF] text-right" suppressHydrationWarning>
                        +{new Intl.NumberFormat("pt-BR").format(heroPrint.dailySales)} pçs/dia
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </section>

        {/* 1. Macro KPIs Ticker */}
        <HeroKpiTicker macro={data.macro} />

        {/* 2. Breakout Prints Showcase (Top 12) */}
        <BreakoutPrints prints={data.breakouts} />

        {/* 3. Directives Board (O Que Estampar vs O Que Pausar) */}
        <DirectivesBoard directives={data.directives} />

        {/* 4. Niche Explorer & Price Dispersion */}
        <NicheExplorer niches={data.niches} />

        {/* 5. Fabric & Modeling Radar */}
        <FabricRadar metrics={data.fabricRadar} />
      </main>

      {/* Institutional Footer */}
      <footer className="mt-12 border-t border-[#2E3038] bg-[#121316] py-8 text-center text-xs text-[#8E9099]">
        <div className="mx-auto max-w-7xl px-4 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-[#F4F3EF]" />
            <span className="text-[#F4F3EF]">Trend Scout BR • Inteligência Algorítmica Independente</span>
          </div>
          <p>
            Análise baseada em dados públicos de mercado auditados. Não vinculado oficialmente à Shopee Inc.
          </p>
        </div>
      </footer>

      {/* VIP Modals */}
      <VipUnlockModal />
      <CheckoutModal />
    </div>
  );
}
