"use client";

import React, { useState, useEffect } from "react";
import { Sparkles, ArrowRight, ShieldCheck, Zap } from "lucide-react";
import type { ClientReportPayload } from "@/types/intelligence";
import { FALLBACK_CLIENT_REPORT } from "@/lib/fallback-data";
import { normalizeClientReport } from "@/lib/normalize-report";
import { useVip } from "@/context/VipContext";
import { HeaderNav } from "@/components/HeaderNav";
import { TeaserBanner } from "@/components/TeaserBanner";
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
 * Coordinates freemium teaser gates and VIP membership modal workflows.
 *
 * @returns JSX.Element
 */
export default function Home(): React.JSX.Element {
  const [data, setData] = useState<ClientReportPayload>(FALLBACK_CLIENT_REPORT);
  const { isVip, openCheckoutModal } = useVip();

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

  return (
    <div className="flex min-h-screen flex-col bg-[#030712] text-slate-100">
      {/* Sticky Header Navigation */}
      <HeaderNav edition={data.edition} />

      <main className="mx-auto flex w-full max-w-7xl flex-1 flex-col gap-12 px-4 py-8 sm:px-6 lg:px-8">
        {/* Hero Section */}
        <section aria-labelledby="hero-title" className="text-center sm:text-left">
          <div className="inline-flex items-center gap-2 rounded-full border border-indigo-500/20 bg-indigo-500/10 px-3.5 py-1 text-xs font-semibold text-indigo-300">
            <Zap className="h-3.5 w-3.5 text-indigo-400" />
            <span>Auditoria Semanal Shopee BR • Categoria Camisetas</span>
          </div>

          <h1
            id="hero-title"
            className="mt-4 text-3xl font-extrabold tracking-tight text-white sm:text-4xl lg:text-5xl"
          >
            Radar de Inteligência para <br className="hidden sm:inline" />
            <span className="bg-gradient-to-r from-emerald-400 via-teal-300 to-indigo-400 bg-clip-text text-transparent">
              Confeccionistas & Lojistas de Camisetas
            </span>
          </h1>

          <p className="mt-3 max-w-3xl text-sm sm:text-base text-slate-400 leading-relaxed">
            Elimine o chute no planejamento de corte e estamparia. Monitoramos mais de 490 produtos líderes na Shopee Brasil
            para revelar onde está a margem real, quais estampas estão acelerando e o que você deve pausar imediatamente.
          </p>
        </section>

        {/* Freemium Teaser Banner below Hero */}
        <TeaserBanner />

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

        {/* 6. Conversion VIP Banner */}
        {!isVip ? (
          <section className="glass-panel relative overflow-hidden rounded-3xl p-8 sm:p-10 border-emerald-500/20 bg-gradient-to-r from-emerald-950/40 via-slate-900/80 to-indigo-950/40">
            <div className="relative z-10 flex flex-col items-center justify-between gap-6 text-center lg:flex-row lg:text-left">
              <div>
                <div className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/20 px-3 py-1 text-xs font-bold text-emerald-300">
                  <Sparkles className="h-3.5 w-3.5" />
                  ACESSO COMPLETO ANTECIPADO
                </div>
                <h2 className="mt-2 text-2xl sm:text-3xl font-bold text-white">
                  Pronto para colocar sua confecção à frente do mercado?
                </h2>
                <p className="mt-1.5 max-w-2xl text-xs sm:text-sm text-slate-300">
                  Receba o relatório completo toda segunda-feira diretamente no seu WhatsApp por apenas R$ 97/mês.
                  Fichas técnicas em alta resolução, listas de fornecedores e consultoria pontual de catálogo.
                </p>
              </div>

              <button
                type="button"
                onClick={() => openCheckoutModal()}
                className="flex items-center gap-2 rounded-2xl bg-gradient-to-r from-emerald-500 to-teal-400 px-6 py-3.5 text-sm font-extrabold text-slate-950 shadow-xl shadow-emerald-500/25 transition-transform hover:scale-105 active:scale-95 flex-shrink-0"
              >
                <span>Quero Acessar o Clube VIP</span>
                <ArrowRight className="h-4 w-4" />
              </button>
            </div>

            <div className="absolute -right-16 -bottom-16 h-64 w-64 rounded-full bg-emerald-500/10 blur-3xl pointer-events-none" />
          </section>
        ) : (
          <section className="glass-panel relative overflow-hidden rounded-3xl p-8 border-amber-500/30 bg-gradient-to-r from-amber-950/30 via-slate-900/80 to-slate-900/80">
            <div className="relative z-10 flex flex-col sm:flex-row items-center justify-between gap-4">
              <div>
                <div className="inline-flex items-center gap-1.5 rounded-full bg-amber-400/20 border border-amber-400/40 px-3 py-1 text-xs font-bold text-amber-300">
                  <span>⭐</span>
                  <span>ASSINATURA VIP ATIVA</span>
                </div>
                <h2 className="mt-2 text-xl sm:text-2xl font-bold text-white">
                  Você possui acesso irrestrito ao Radar Semanal
                </h2>
                <p className="mt-1 text-xs sm:text-sm text-slate-300">
                  Todas as 12 estampas em tração diária, diretrizes completas de maquinário e réguas de preço estão liberadas neste dispositivo.
                </p>
              </div>
            </div>
            <div className="absolute -right-12 -bottom-12 h-44 w-44 rounded-full bg-amber-500/10 blur-3xl pointer-events-none" />
          </section>
        )}
      </main>

      {/* Institutional Footer */}
      <footer className="mt-12 border-t border-white/[0.08] bg-slate-950/80 py-8 text-center text-xs text-slate-500">
        <div className="mx-auto max-w-7xl px-4 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-emerald-400" />
            <span>Trend Scout BR • Inteligência Algorítmica Independente</span>
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
