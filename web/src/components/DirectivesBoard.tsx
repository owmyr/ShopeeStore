"use client";

import React from "react";
import type { StrategicDirectivesPayload } from "@/types/intelligence";
import { useVip } from "@/context/VipContext";

/**
 * Props definition for DirectivesBoard component.
 */
interface DirectivesBoardProps {
  /** Mutually exclusive tactical directives */
  directives: StrategicDirectivesPayload;
}

/**
 * Directives Board enforcing the zero-overlap 'O Que Estampar' vs 'O Que Pausar' framework.
 * Empowers manufacturers to allocate cutting tables and print capacity exclusively to profitable niches.
 * Adopts an editorial, architectural graphite aesthetic without blurs or glows.
 * Secondary recommendations are gated gracefully with inline text.
 *
 * @param props DirectivesBoardProps
 * @returns JSX.Element
 */
export function DirectivesBoard({ directives }: DirectivesBoardProps): React.JSX.Element {
  const { isVip, openCheckoutModal } = useVip();

  return (
    <section aria-labelledby="directives-heading" className="w-full space-y-6">
      <div>
        <h2 id="directives-heading" className="text-xl font-bold tracking-tight text-[#F4F3EF] sm:text-2xl">
          Diretrizes de Produção
        </h2>
        <p className="mt-1 text-sm text-[#8E9099]">
          Alocação de maquinário com exclusão mútua.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Column 1: O Que Estampar */}
        <div className="bg-[#1A1B20] border border-[#2E3038] rounded-2xl p-6">
          <div className="pb-4 border-b border-[#2E3038]">
            <h3 className="text-lg font-bold text-[#F4F3EF]">Prioridade de Produção & Corte</h3>
            <span className="text-xs text-[#8E9099]">Alta Demanda • Margens Preservadas</span>
          </div>

          <div className="mt-5 space-y-0">
            {(directives?.whatToPrint || []).map((item, idx) => {
              const isLocked = !isVip && idx > 0;
              return (
                <div key={item.niche} className="py-4 border-b border-[#2E3038] last:border-b-0">
                  <div className="flex items-center justify-between">
                    <h4 className="font-bold text-[#F4F3EF] text-sm sm:text-base">
                      {item.niche}
                    </h4>
                    <span className="text-xs font-medium text-[#8E9099]">Margem {item.marginRating}</span>
                  </div>
                  {isLocked ? (
                    <button
                      type="button"
                      onClick={() => openCheckoutModal("Diretrizes de Produção")}
                      className="mt-2 text-xs font-semibold text-[#8E9099] hover:text-[#F4F3EF] transition-colors"
                    >
                      [ Restrito para Assinantes ]
                    </button>
                  ) : (
                    <>
                      <p className="mt-2 text-xs text-[#8E9099] leading-relaxed">
                        {item.reason}
                      </p>
                      <div className="mt-3 flex flex-wrap gap-1.5">
                        {(item.recommendedThemes || []).map((theme) => (
                          <span
                            key={theme}
                            className="bg-[#22232A] border border-[#2E3038] px-2 py-0.5 text-[11px] text-[#8E9099]"
                          >
                            + {theme}
                          </span>
                        ))}
                      </div>
                    </>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Column 2: O Que Pausar */}
        <div className="bg-[#1A1B20] border border-[#2E3038] rounded-2xl p-6">
          <div className="pb-4 border-b border-[#2E3038]">
            <h3 className="text-lg font-bold text-[#F4F3EF]">Saturação & Pausa de Produção</h3>
            <span className="text-xs text-[#8E9099]">Guerra de Preço • Risco de Estoque</span>
          </div>

          <div className="mt-5 space-y-0">
            {(directives?.whatToPause || []).map((item, idx) => {
              const isLocked = !isVip && idx > 0;
              return (
                <div key={item.niche} className="py-4 border-b border-[#2E3038] last:border-b-0">
                  <div className="flex items-center justify-between">
                    <h4 className="font-bold text-[#F4F3EF] text-sm sm:text-base">
                      {item.niche}
                    </h4>
                    <span className="text-xs font-medium text-[#8E9099]">
                      Risco de Estoque
                    </span>
                  </div>
                  {isLocked ? (
                    <button
                      type="button"
                      onClick={() => openCheckoutModal("Diretrizes de Produção")}
                      className="mt-2 text-xs font-semibold text-[#8E9099] hover:text-[#F4F3EF] transition-colors"
                    >
                      [ Restrito para Assinantes ]
                    </button>
                  ) : (
                    <>
                      <p className="mt-2 text-xs text-[#8E9099] leading-relaxed">
                        {item.reason}
                      </p>
                      <div className="mt-3 text-[11px] text-[#8E9099]">
                        <strong>Fator de Risco: </strong>
                        {item.riskFactor}
                      </div>
                    </>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}
