"use client";

import React from "react";
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
 * Redesigned into a clean typographic ledger grid.
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
      subtitle: "100% estampas ativas",
    },
    {
      id: "revenue",
      title: "Faturamento Monitorado",
      value: formatMillions(macro?.weeklyRevenueBrl ?? 0),
      subtitle: "Movimentação semanal estimada",
    },
    {
      id: "velocity",
      title: "Giro Médio Diário",
      value: `+${formatNumber(macro?.dailyUnitVelocity ?? 0)}`,
      subtitle: "Peças vendidas por dia",
    },
    {
      id: "median_price",
      title: "Preço Mediano Base",
      value: formatCurrency(macro?.medianPriceBrl ?? 0),
      subtitle: `Normal: ${formatCurrency(macro?.priceP25Brl ?? 0)} — ${formatCurrency(macro?.priceP75Brl ?? 0)}`,
    },
  ];

  return (
    <section aria-label="Indicadores Macro de Mercado" className="w-full mt-8">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {kpis.map((kpi) => (
          <div
            key={kpi.id}
            className="bg-[#1A1B20] border border-[#2E3038] rounded-2xl p-5 flex flex-col justify-between h-full"
          >
            <h3 className="text-xs font-semibold uppercase tracking-wider text-[#8E9099] mb-4">
              {kpi.title}
            </h3>
            <div>
              <div className="text-2xl font-extrabold tracking-tight text-[#F4F3EF] font-mono mb-1" suppressHydrationWarning>
                {kpi.value}
              </div>
              <p className="text-xs text-[#8E9099] leading-relaxed" suppressHydrationWarning>
                {kpi.subtitle}
              </p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
