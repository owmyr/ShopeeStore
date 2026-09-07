"use client";

import React from "react";
import { motion, type Variants } from "framer-motion";
import { CheckCircle2, TrendingUp, Flame, Tag } from "lucide-react";
import type { MacroMarketOverview } from "@/types/intelligence";

/**
 * Props for HeroKpiTicker component.
 */
interface HeroKpiTickerProps {
  /** Aggregated macro volume and price indices */
  macro: MacroMarketOverview;
}

/**
 * Hero KPI Ticker displaying 4 macro market intelligence metrics.
 * Utilizes staggered Framer Motion entrances and Antigravity glassmorphism tokens.
 *
 * @param props HeroKpiTickerProps containing macro metrics
 * @returns JSX.Element
 */
export function HeroKpiTicker({ macro }: HeroKpiTickerProps): React.JSX.Element {
  // Format monetary currency to Brazilian Reais (R$)
  const formatCurrency = (val: number): string => {
    return new Intl.NumberFormat("pt-BR", {
      style: "currency",
      currency: "BRL",
    }).format(val);
  };

  // Format large monetary representations to abbreviated millions
  const formatMillions = (val: number): string => {
    const millions = val / 1_000_000;
    return `R$ ${millions.toFixed(1).replace(".", ",")}M`;
  };

  // Format unit volume with thousand separators
  const formatNumber = (val: number): string => {
    return new Intl.NumberFormat("pt-BR").format(val);
  };

  const kpis = [
    {
      id: "audited",
      title: "Anúncios Auditados",
      value: formatNumber(macro?.auditedListings ?? 497),
      subtitle: "100% estampas ativas (lisas expurgadas)",
      icon: CheckCircle2,
      accent: "text-emerald-400",
      badge: "Base Auditada",
      glowClass: "glow-emerald",
    },
    {
      id: "revenue",
      title: "Faturamento Monitorado",
      value: formatMillions(macro?.weeklyRevenueBrl ?? 0),
      subtitle: "Movimentação semanal estimada",
      icon: TrendingUp,
      accent: "text-indigo-400",
      badge: "Giro Semanal",
      glowClass: "glow-indigo",
    },
    {
      id: "velocity",
      title: "Giro Médio Diário",
      value: `+${formatNumber(macro?.dailyUnitVelocity ?? 0)}`,
      subtitle: "Peças vendidas por dia no segmento",
      icon: Flame,
      accent: "text-amber-400",
      badge: "Alta Velocidade",
      glowClass: "glow-amber",
    },
    {
      id: "median_price",
      title: "Preço Mediano Base",
      value: formatCurrency(macro?.medianPriceBrl ?? 0),
      subtitle: `Faixa normal: ${formatCurrency(macro?.priceP25Brl ?? 0)} — ${formatCurrency(macro?.priceP75Brl ?? 0)}`,
      icon: Tag,
      accent: "text-teal-400",
      badge: "Percentil 50%",
      glowClass: "glow-emerald",
    },
  ];

  const containerVariants: Variants = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: {
        staggerChildren: 0.08,
      },
    },
  };

  const itemVariants: Variants = {
    hidden: { opacity: 0, y: 16 },
    show: { opacity: 1, y: 0, transition: { duration: 0.45, ease: "easeOut" } },
  };

  return (
    <section aria-label="Indicadores Macro de Mercado" className="w-full">
      <motion.div
        variants={containerVariants}
        initial="hidden"
        animate="show"
        className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4"
      >
        {kpis.map((kpi) => {
          const Icon = kpi.icon;
          return (
            <motion.div
              key={kpi.id}
              variants={itemVariants}
              className="glass-panel glass-panel-hover relative overflow-hidden rounded-2xl p-5"
            >
              {/* Top Row: Icon & Category Badge */}
              <div className="flex items-center justify-between">
                <div
                  className={`flex h-10 w-10 items-center justify-center rounded-xl bg-white/[0.05] border border-white/[0.08] ${kpi.accent}`}
                >
                  <Icon className="h-5 w-5" aria-hidden="true" />
                </div>
                <span className="rounded-full bg-white/[0.04] px-2.5 py-1 text-[11px] font-medium text-slate-400 border border-white/[0.05]">
                  {kpi.badge}
                </span>
              </div>

              {/* Metric Value */}
              <div className="mt-4">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                  {kpi.title}
                </h3>
                <div className="mt-1 flex items-baseline gap-2">
                  <span className="text-2xl font-extrabold tracking-tight text-white sm:text-3xl font-mono">
                    {kpi.value}
                  </span>
                </div>
                <p className="mt-1.5 text-xs text-slate-400 leading-relaxed">
                  {kpi.subtitle}
                </p>
              </div>

              {/* Ambient radial accent line */}
              <div className="absolute -bottom-8 -right-8 h-24 w-24 rounded-full bg-white/[0.02] blur-xl" />
            </motion.div>
          );
        })}
      </motion.div>
    </section>
  );
}
