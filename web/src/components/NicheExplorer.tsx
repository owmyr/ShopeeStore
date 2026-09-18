"use client";

import React, { useState, useMemo } from "react";
import type { NicheSummary } from "@/types/intelligence";
import { useVip } from "@/context/VipContext";

type FilterCategory = "all" | "high_margin" | "price_war";

interface NicheExplorerProps {
  niches: NicheSummary[];
}

/**
 * Visualizer and analyzer for top apparel niches.
 * Clean solid panels and text pill buttons.
 *
 * @param props NicheExplorerProps
 * @returns JSX.Element
 */
export function NicheExplorer({ niches }: NicheExplorerProps): React.JSX.Element {
  const [activeFilter, setActiveFilter] = useState<FilterCategory>("all");
  const { isVip, openCheckoutModal } = useVip();

  const formatCurrency = (val: number): string => {
    return new Intl.NumberFormat("pt-BR", {
      style: "currency",
      currency: "BRL",
    }).format(val);
  };

  const filteredNiches = useMemo(() => {
    const list = niches || [];
    if (activeFilter === "high_margin") {
      return list.filter((n) => n.tag === "Alta Margem");
    }
    if (activeFilter === "price_war") {
      return list.filter((n) => n.tag === "Guerra de Preço");
    }
    return list;
  }, [niches, activeFilter]);

  const getTagStyle = (tag: NicheSummary["tag"]) => {
    if (tag === "Alta Margem") return "text-[#10B981]";
    if (tag === "Guerra de Preço") return "text-[#E27D44]";
    return "text-[#8E9099]";
  };

  return (
    <section aria-labelledby="niche-explorer-heading" className="w-full space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 id="niche-explorer-heading" className="text-xl font-bold tracking-tight text-[#F4F3EF] sm:text-2xl">
            Termômetro de Nichos & Dispersão de Preços
          </h2>
          <p className="mt-1 text-sm text-[#8E9099]">
            Análise comparativa de liquidez e saturação.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setActiveFilter("all")}
            className={`px-3 py-1.5 text-xs font-semibold border ${
              activeFilter === "all" ? "bg-[#22232A] border-[#3A3D47] text-white" : "border-transparent text-[#8E9099]"
            }`}
          >
            Todos ({niches.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveFilter("high_margin")}
            className={`px-3 py-1.5 text-xs font-semibold border ${
              activeFilter === "high_margin" ? "bg-[#22232A] border-[#3A3D47] text-white" : "border-transparent text-[#8E9099]"
            }`}
          >
            Alta Margem
          </button>
          <button
            type="button"
            onClick={() => setActiveFilter("price_war")}
            className={`px-3 py-1.5 text-xs font-semibold border ${
              activeFilter === "price_war" ? "bg-[#22232A] border-[#3A3D47] text-white" : "border-transparent text-[#8E9099]"
            }`}
          >
            Guerra de Preço
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {filteredNiches.map((niche, idx) => {
          const originalIndex = (niches || []).findIndex((n) => n.id === niche.id);
          const isLocked = !isVip && (originalIndex >= 3 || (originalIndex === -1 && idx >= 3));

          return (
            <div key={niche.id} className="bg-[#1A1B20] border border-[#2E3038] rounded-2xl p-5 flex flex-col justify-between">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="font-bold text-[#F4F3EF] sm:text-lg">{niche.name}</h3>
                  <div className="mt-0.5 text-xs text-[#8E9099]" suppressHydrationWarning>
                    {niche.volume} modelos • {new Intl.NumberFormat("pt-BR").format(niche.dailyVelocity)} pçs/dia
                  </div>
                </div>
                <span className={`text-xs font-semibold uppercase ${getTagStyle(niche.tag)}`}>
                  {niche.tag}
                </span>
              </div>

              <div className="mt-4 pt-4 border-t border-[#2E3038]">
                {isLocked ? (
                  <button
                    type="button"
                    onClick={() => openCheckoutModal("Margens e Dispersão de Preços")}
                    className="text-xs font-semibold text-[#8E9099] hover:text-[#F4F3EF] transition-colors"
                  >
                    [ Restrito para Assinantes ]
                  </button>
                ) : (
                  <>
                    <div className="flex items-center justify-between text-xs text-[#8E9099] mb-2">
                      <span>Dispersão (BRL)</span>
                      <span className="font-mono text-[#F4F3EF]" suppressHydrationWarning>Med: {formatCurrency(niche.priceMedian)}</span>
                    </div>
                    <div className="flex justify-between text-[11px] font-mono text-[#8E9099]" suppressHydrationWarning>
                      <span>P25: {formatCurrency(niche.priceP25)}</span>
                      <span className="text-[#F4F3EF]">P50: {formatCurrency(niche.priceMedian)}</span>
                      <span>P75: {formatCurrency(niche.priceP75)}</span>
                    </div>
                  </>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
