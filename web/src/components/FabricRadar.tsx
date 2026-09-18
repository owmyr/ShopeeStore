"use client";

import React from "react";
import type { FabricModelingMetric } from "@/types/intelligence";

interface FabricRadarProps {
  metrics: FabricModelingMetric[];
}

/**
 * Fabric and Modeling Radar visualizing textile adoption rates.
 * Clean minimalist specs panel using solid background and hairline rules.
 *
 * @param props FabricRadarProps
 * @returns JSX.Element
 */
export function FabricRadar({ metrics }: FabricRadarProps): React.JSX.Element {
  return (
    <section aria-labelledby="fabric-radar-heading" className="w-full space-y-6">
      <div>
        <h2 id="fabric-radar-heading" className="text-xl font-bold tracking-tight text-[#F4F3EF] sm:text-2xl">
          Radar Têxtil: Malhas & Acabamentos
        </h2>
        <p className="mt-1 text-sm text-[#8E9099]">
          Dados auditados de modelagens predominantes.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {(metrics || []).map((metric, idx) => (
          <div key={metric.feature} className="bg-[#1A1B20] border border-[#2E3038] rounded-2xl p-5 flex flex-col justify-between">
            <div>
              <div className="flex items-start justify-between gap-2">
                <h3 className="font-bold text-[#F4F3EF] text-base leading-snug">
                  {metric.feature}
                </h3>
                <span className="text-xs font-mono font-bold text-[#F4F3EF]">
                  {metric.percentage}%
                </span>
              </div>
              <div className="mt-3.5 relative h-1.5 w-full overflow-hidden bg-[#2E3038]">
                <div
                  className="h-full bg-[#10B981]"
                  style={{ width: `${metric.percentage}%` }}
                />
              </div>
              <p className="mt-3 text-xs text-[#8E9099] leading-relaxed">
                {metric.description}
              </p>
            </div>
            <div className="mt-4 pt-3 border-t border-[#2E3038] text-[11px] text-[#8E9099]">
              Padrão Recomendado para Confecção
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
