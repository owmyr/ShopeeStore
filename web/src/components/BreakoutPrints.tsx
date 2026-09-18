"use client";

import React, { useState } from "react";
import Image from "next/image";
import { Lock } from "lucide-react";
import type { BreakoutPrint } from "@/types/intelligence";
import { PrintAuditModal } from "./PrintAuditModal";
import { useVip } from "@/context/VipContext";

/**
 * Props definition for BreakoutPrints grid.
 */
interface BreakoutPrintsProps {
  /** Array of 12 breakout items */
  prints: BreakoutPrint[];
}

/**
 * Showcase of top 12 accelerating breakout printed t-shirts with freemium gating.
 * Designed as a curated 3:4 portrait lookbook grid.
 *
 * @param props BreakoutPrintsProps
 * @returns JSX.Element
 */
export function BreakoutPrints({ prints }: BreakoutPrintsProps): React.JSX.Element {
  const [selectedPrint, setSelectedPrint] = useState<BreakoutPrint | null>(null);
  const { isVip, openCheckoutModal } = useVip();

  const formatCurrency = (val: number): string => {
    return new Intl.NumberFormat("pt-BR", {
      style: "currency",
      currency: "BRL",
    }).format(val);
  };

  const handleCardClick = (print: BreakoutPrint, isLocked: boolean) => {
    if (isLocked) {
      openCheckoutModal(print.title);
    } else {
      setSelectedPrint(print);
    }
  };

  return (
    <section aria-labelledby="breakouts-heading" className="w-full mt-12 space-y-8">
      {/* Section Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between border-b border-[#2E3038] pb-4">
        <div>
          <h2 id="breakouts-heading" className="text-lg font-semibold tracking-wide text-[#F4F3EF] uppercase">
            Estampas Breakout: Top 12 em Aceleração
          </h2>
          <p className="mt-1 text-sm text-[#8E9099]">
            Modelos com maior taxa de tração diária no marketplace. Referência de mercado para inspiração e desenvolvimento de coleção própria autoral.
          </p>
        </div>

        <div className="flex items-center gap-2.5 self-start sm:self-auto">
          {!isVip && (
            <button
              type="button"
              onClick={() => openCheckoutModal("Auditoria Completa dos Anúncios Concorrentes")}
              className="text-xs font-semibold text-[#8E9099] hover:text-[#F4F3EF] transition-colors uppercase tracking-wider"
            >
              Desbloquear Todos
            </button>
          )}
        </div>
      </div>

      {/* Grid of 12 Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
        {(prints || []).map((print, index) => {
          const isLocked = !isVip && index >= 3;
          
          return (
            <div
              key={print.id}
              onClick={() => handleCardClick(print, isLocked)}
              className="group flex flex-col gap-3 cursor-pointer outline-none"
              tabIndex={0}
              role="button"
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  handleCardClick(print, isLocked);
                }
              }}
              aria-label={
                isLocked
                  ? `Desbloquear estampa VIP: ${print.title}`
                  : `Ver auditoria técnica de ${print.title}`
              }
            >
              {/* 3:4 Aspect Ratio Image Frame */}
              <div className={`relative aspect-[3/4] w-full overflow-hidden bg-[#1A1B20] border border-transparent transition-colors ${!isLocked ? 'group-hover:border-[#3A3D47]' : ''}`}>
                <Image
                  src={print.imageUrl}
                  alt={isLocked ? "Acesso Restrito" : print.title}
                  fill
                  sizes="(max-width: 768px) 50vw, (max-width: 1024px) 33vw, 25vw"
                  className="object-cover"
                  unoptimized
                  suppressHydrationWarning
                />

                {/* Overlay for Locked Items */}
                {isLocked && (
                  <div className="absolute inset-0 bg-[#121316]/80 flex flex-col items-center justify-center gap-2">
                    <Lock className="h-5 w-5 text-[#8E9099]" />
                    <span className="text-xs font-semibold uppercase tracking-wider text-[#F4F3EF]">
                      Acesso Restrito
                    </span>
                    <span className="text-[10px] text-[#8E9099] uppercase tracking-wider">
                      Assinantes Pro
                    </span>
                  </div>
                )}
              </div>

              {/* Metadata */}
              {!isLocked && (
                <div className="flex flex-col gap-1">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-semibold text-[#8E9099] uppercase tracking-wider">
                      {print.theme}
                    </span>
                    <span className="text-[10px] text-[#8E9099] border-l border-[#2E3038] pl-2">
                      {print.shopeeItemCode}
                    </span>
                  </div>
                  <h3 className="text-sm text-[#F4F3EF] leading-snug truncate">
                    {print.title}
                  </h3>
                  <div className="flex items-center justify-between mt-1">
                    <span className="font-mono text-sm font-semibold text-[#F4F3EF]" suppressHydrationWarning>
                      {formatCurrency(print.priceBrl)}
                    </span>
                    <span className="font-mono text-xs text-[#8E9099]" suppressHydrationWarning>
                      +{print.dailySales} pçs/dia
                    </span>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Technical Inspection Modal */}
      <PrintAuditModal print={selectedPrint} onClose={() => setSelectedPrint(null)} />
    </section>
  );
}
