"use client";

import React from "react";
import { motion } from "framer-motion";
import { Sliders, ArrowUpRight, CheckCircle2 } from "lucide-react";
import type { FabricModelingMetric } from "@/types/intelligence";

/**
 * Props definition for FabricRadar component.
 */
interface FabricRadarProps {
  /** Array of fabric and modeling metrics */
  metrics: FabricModelingMetric[];
}

/**
 * Fabric and Modeling Radar visualizing textile adoption rates among top sellers.
 * Provides actionable manufacturing benchmarks (Algodão 30.1, Oversized, Kits, etc.).
 *
 * @param props FabricRadarProps
 * @returns JSX.Element
 */
export function FabricRadar({ metrics }: FabricRadarProps): React.JSX.Element {
  return (
    <section aria-labelledby="fabric-radar-heading" className="w-full space-y-6">
      {/* Section Header */}
      <div>
        <div className="flex items-center gap-2">
          <Sliders className="h-5 w-5 text-teal-400" aria-hidden="true" />
          <h2 id="fabric-radar-heading" className="text-xl font-bold tracking-tight text-white sm:text-2xl">
            Radar Têxtil: Malhas, Modelagens & Acabamentos
          </h2>
        </div>
        <p className="mt-1 text-sm text-slate-400">
          Proporção observada nos anúncios líderes de vendas. Dados auditados que reduzem devoluções e aumentam o markup.
        </p>
      </div>

      {/* Meters Grid */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {(metrics || []).map((metric, idx) => (
          <motion.div
            key={metric.feature}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, delay: idx * 0.05 }}
            className="glass-panel glass-panel-hover rounded-2xl p-5 flex flex-col justify-between"
          >
            <div>
              {/* Feature Title & Percent */}
              <div className="flex items-start justify-between gap-2">
                <h3 className="font-bold text-white text-base leading-snug">
                  {metric.feature}
                </h3>
                <div className="flex items-center gap-1 rounded-lg bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 text-xs font-mono font-bold text-emerald-400">
                  <ArrowUpRight className="h-3.5 w-3.5" />
                  <span>{metric.percentage}%</span>
                </div>
              </div>

              {/* Progress Bar */}
              <div className="mt-3.5 relative h-2.5 w-full overflow-hidden rounded-full bg-slate-800">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${metric.percentage}%` }}
                  transition={{ duration: 0.8, delay: 0.1 + idx * 0.05, ease: "easeOut" }}
                  className="h-full rounded-full bg-gradient-to-r from-teal-500 via-emerald-400 to-indigo-400"
                />
              </div>

              {/* Description */}
              <p className="mt-3 text-xs text-slate-300 leading-relaxed">
                {metric.description}
              </p>
            </div>

            {/* Industrial recommendation status */}
            <div className="mt-4 flex items-center gap-1.5 border-t border-white/[0.06] pt-3 text-[11px] text-emerald-400 font-medium">
              <CheckCircle2 className="h-3.5 w-3.5" />
              <span>Padrão Recomendado para Confecção</span>
            </div>
          </motion.div>
        ))}
      </div>
    </section>
  );
}
