"use client";

import React, { useState } from "react";
import Image from "next/image";
import { motion } from "framer-motion";
import { Sparkles, Flame, Eye, Tag } from "lucide-react";
import type { BreakoutPrint } from "@/types/intelligence";
import { PrintAuditModal } from "./PrintAuditModal";

/**
 * Props definition for BreakoutPrints grid.
 */
interface BreakoutPrintsProps {
  /** Array of 12 breakout items */
  prints: BreakoutPrint[];
}

/**
 * Showcase of top 12 accelerating breakout printed t-shirts.
 * Renders high-resolution 1:1 product previews and opens the production audit modal upon interaction.
 *
 * @param props BreakoutPrintsProps
 * @returns JSX.Element
 */
export function BreakoutPrints({ prints }: BreakoutPrintsProps): React.JSX.Element {
  const [selectedPrint, setSelectedPrint] = useState<BreakoutPrint | null>(null);

  const formatCurrency = (val: number): string => {
    return new Intl.NumberFormat("pt-BR", {
      style: "currency",
      currency: "BRL",
    }).format(val);
  };

  return (
    <section aria-labelledby="breakouts-heading" className="w-full space-y-6">
      {/* Section Header */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-emerald-400" aria-hidden="true" />
            <h2 id="breakouts-heading" className="text-xl font-bold tracking-tight text-white sm:text-2xl">
              Estampas Breakout: Top 12 em Aceleração
            </h2>
          </div>
          <p className="mt-1 text-sm text-slate-400">
            Modelos com maior taxa de tração diária no marketplace. Clique em qualquer estampa para inspecionar a ficha fabril.
          </p>
        </div>

        <span className="self-start sm:self-auto rounded-full border border-emerald-500/20 bg-emerald-500/10 px-3 py-1 text-xs font-semibold text-emerald-300">
          12 Modelos Auditados
        </span>
      </div>

      {/* Grid of 12 Cards */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {prints.map((print, index) => (
          <motion.div
            key={print.id}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, delay: index * 0.03 }}
            onClick={() => setSelectedPrint(print)}
            className="group glass-panel glass-panel-hover relative cursor-pointer overflow-hidden rounded-2xl p-3.5 focus:outline-none focus:ring-2 focus:ring-emerald-400"
            tabIndex={0}
            role="button"
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                setSelectedPrint(print);
              }
            }}
            aria-label={`Ver auditoria técnica de ${print.title}`}
          >
            {/* 1:1 Aspect Ratio Image Frame */}
            <div className="relative aspect-square w-full overflow-hidden rounded-xl bg-slate-800">
              <Image
                src={print.imageUrl}
                alt={print.title}
                fill
                sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 25vw"
                className="object-cover transition-transform duration-500 group-hover:scale-105"
                unoptimized
              />

              {/* Floating Velocity Tag */}
              <div className="absolute top-2.5 left-2.5 flex items-center gap-1 rounded-full bg-slate-950/85 backdrop-blur-md px-2.5 py-1 text-[11px] font-bold text-amber-300 border border-amber-500/30">
                <Flame className="h-3 w-3 text-amber-400" />
                <span>+{print.dailySales} pçs/dia</span>
              </div>

              {/* Quick Inspect Hover Overlay */}
              <div className="absolute inset-0 flex items-center justify-center bg-slate-950/60 opacity-0 backdrop-blur-[2px] transition-opacity duration-200 group-hover:opacity-100">
                <span className="flex items-center gap-1.5 rounded-xl bg-emerald-500 px-3.5 py-1.5 text-xs font-bold text-slate-950 shadow-lg">
                  <Eye className="h-3.5 w-3.5" />
                  Inspecionar Ficha
                </span>
              </div>
            </div>

            {/* Content & Metadata */}
            <div className="mt-3 space-y-1.5">
              <div className="flex items-center justify-between text-[11px] text-slate-400">
                <span className="rounded-md bg-white/[0.05] px-1.5 py-0.5 text-indigo-300 font-medium">
                  {print.theme}
                </span>
                <span className="font-mono text-slate-500">{print.shopeeItemCode}</span>
              </div>

              <h3 className="line-clamp-2 text-xs sm:text-sm font-semibold text-white leading-snug group-hover:text-emerald-300 transition-colors">
                {print.title}
              </h3>

              {/* Price & Historical Volume */}
              <div className="flex items-center justify-between pt-1 border-t border-white/[0.06]">
                <div className="flex items-baseline gap-1">
                  <span className="font-mono text-sm sm:text-base font-extrabold text-emerald-400">
                    {formatCurrency(print.priceBrl)}
                  </span>
                </div>
                <div className="text-[11px] text-slate-400">
                  <span className="text-slate-500">Histórico: </span>
                  <span className="font-semibold text-slate-300">
                    {new Intl.NumberFormat("pt-BR").format(print.historicalSales)}
                  </span>
                </div>
              </div>
            </div>
          </motion.div>
        ))}
      </div>

      {/* Technical Inspection Modal */}
      <PrintAuditModal print={selectedPrint} onClose={() => setSelectedPrint(null)} />
    </section>
  );
}
