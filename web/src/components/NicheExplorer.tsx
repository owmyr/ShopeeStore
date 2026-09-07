"use client";

import React, { useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Compass, Flame, AlertTriangle, ShieldCheck, DollarSign } from "lucide-react";
import type { NicheSummary } from "@/types/intelligence";

/**
 * Filter tab definitions for the niche classifier.
 */
type FilterCategory = "all" | "high_margin" | "price_war";

/**
 * Props definition for NicheExplorer.
 */
interface NicheExplorerProps {
  /** Array of top 10 ranked niches */
  niches: NicheSummary[];
}

/**
 * Visualizer and analyzer for top apparel niches.
 * Allows filtering by margin health and displays price dispersion metrics (p25 - p50 - p75).
 *
 * @param props NicheExplorerProps
 * @returns JSX.Element
 */
export function NicheExplorer({ niches }: NicheExplorerProps): React.JSX.Element {
  const [activeFilter, setActiveFilter] = useState<FilterCategory>("all");

  const formatCurrency = (val: number): string => {
    return new Intl.NumberFormat("pt-BR", {
      style: "currency",
      currency: "BRL",
    }).format(val);
  };

  const filteredNiches = useMemo(() => {
    if (activeFilter === "high_margin") {
      return niches.filter((n) => n.tag === "Alta Margem");
    }
    if (activeFilter === "price_war") {
      return niches.filter((n) => n.tag === "Guerra de Preço");
    }
    return niches;
  }, [niches, activeFilter]);

  const getTagBadgeStyle = (tag: NicheSummary["tag"]) => {
    switch (tag) {
      case "Alta Margem":
        return "border-emerald-500/30 bg-emerald-500/10 text-emerald-300";
      case "Guerra de Preço":
        return "border-rose-500/30 bg-rose-500/10 text-rose-300";
      case "Volume Explosivo":
        return "border-amber-500/30 bg-amber-500/10 text-amber-300";
      default:
        return "border-indigo-500/30 bg-indigo-500/10 text-indigo-300";
    }
  };

  return (
    <section aria-labelledby="niche-explorer-heading" className="w-full space-y-6">
      {/* Section Header with Filter Controls */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Compass className="h-5 w-5 text-indigo-400" aria-hidden="true" />
            <h2 id="niche-explorer-heading" className="text-xl font-bold tracking-tight text-white sm:text-2xl">
              Termômetro de Nichos & Dispersão de Preços
            </h2>
          </div>
          <p className="mt-1 text-sm text-slate-400">
            Análise comparativa de liquidez, saturação de vendedores e faixas de preço saudáveis (p25 • p50 • p75).
          </p>
        </div>

        {/* Filter Tabs */}
        <div className="flex items-center gap-1.5 rounded-xl border border-white/[0.08] bg-slate-900/60 p-1.5 backdrop-blur-md">
          <button
            type="button"
            onClick={() => setActiveFilter("all")}
            className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-all ${
              activeFilter === "all"
                ? "bg-indigo-600 text-white shadow-sm"
                : "text-slate-400 hover:text-white"
            }`}
          >
            Todos ({niches.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveFilter("high_margin")}
            className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition-all ${
              activeFilter === "high_margin"
                ? "bg-emerald-600 text-white shadow-sm"
                : "text-slate-400 hover:text-white"
            }`}
          >
            <ShieldCheck className="h-3.5 w-3.5" />
            Alta Margem
          </button>
          <button
            type="button"
            onClick={() => setActiveFilter("price_war")}
            className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition-all ${
              activeFilter === "price_war"
                ? "bg-rose-600 text-white shadow-sm"
                : "text-slate-400 hover:text-white"
            }`}
          >
            <AlertTriangle className="h-3.5 w-3.5" />
            Guerra de Preço
          </button>
        </div>
      </div>

      {/* Niches Grid / Cards */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <AnimatePresence mode="popLayout">
          {filteredNiches.map((niche, idx) => (
            <motion.div
              layout
              initial={{ opacity: 0, scale: 0.96 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.96 }}
              transition={{ duration: 0.25, delay: idx * 0.04 }}
              key={niche.id}
              className="glass-panel glass-panel-hover rounded-2xl p-5"
            >
              {/* Card Header: Rank, Title & Tag */}
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-3">
                  <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-white/[0.06] font-mono text-xs font-bold text-slate-300">
                    #{idx + 1}
                  </span>
                  <div>
                    <h3 className="font-bold text-white sm:text-lg">{niche.name}</h3>
                    <div className="mt-0.5 flex items-center gap-2 text-xs text-slate-400">
                      <span>{niche.volume} modelos no ranking</span>
                      <span>•</span>
                      <span className="flex items-center gap-1 text-amber-400">
                        <Flame className="h-3.5 w-3.5" />
                        {new Intl.NumberFormat("pt-BR").format(niche.dailyVelocity)} pçs/dia
                      </span>
                    </div>
                  </div>
                </div>

                <span
                  className={`rounded-lg border px-2.5 py-1 text-xs font-semibold tracking-wide uppercase ${getTagBadgeStyle(
                    niche.tag
                  )}`}
                >
                  {niche.tag}
                </span>
              </div>

              {/* Opportunity Insight Badge */}
              <div className="mt-3.5 rounded-xl border border-white/[0.05] bg-white/[0.02] px-3 py-2 text-xs text-slate-300">
                <span className="font-semibold text-slate-400">Diagnóstico: </span>
                <span>{niche.badge}</span>
              </div>

              {/* Price Dispersion Meter ($p_{25} - p_{50} - p_{75}$) */}
              <div className="mt-4 pt-3 border-t border-white/[0.06]">
                <div className="flex items-center justify-between text-xs text-slate-400 mb-1.5">
                  <span className="flex items-center gap-1">
                    <DollarSign className="h-3.5 w-3.5 text-slate-400" />
                    Dispersão de Preços (BRL)
                  </span>
                  <span className="font-mono text-[11px] text-emerald-400">
                    Mediana: {formatCurrency(niche.priceMedian)}
                  </span>
                </div>

                {/* Visual Spread Bar */}
                <div className="relative h-2 w-full rounded-full bg-slate-800/80 overflow-hidden">
                  <div
                    className="absolute top-0 h-full rounded-full bg-gradient-to-r from-emerald-500 via-indigo-500 to-amber-500 opacity-85"
                    style={{
                      left: "15%",
                      width: "70%",
                    }}
                  />
                </div>

                {/* Values Footer */}
                <div className="mt-2 flex items-center justify-between text-[11px] font-mono text-slate-400">
                  <div>
                    <span className="text-slate-500">p25 (Entrada): </span>
                    <span className="text-slate-200">{formatCurrency(niche.priceP25)}</span>
                  </div>
                  <div>
                    <span className="text-slate-500">p50 (Ideal): </span>
                    <span className="font-semibold text-emerald-300">
                      {formatCurrency(niche.priceMedian)}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500">p75 (Premium): </span>
                    <span className="text-slate-200">{formatCurrency(niche.priceP75)}</span>
                  </div>
                </div>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </section>
  );
}
