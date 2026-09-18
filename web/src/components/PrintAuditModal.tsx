"use client";

import React, { useEffect } from "react";
import Image from "next/image";
import { X } from "lucide-react";
import type { BreakoutPrint } from "@/types/intelligence";

interface PrintAuditModalProps {
  print: BreakoutPrint | null;
  onClose: () => void;
}

/**
 * Technical production audit modal.
 * Uses a solid architectural graphite panel, removing blurs and neon glows.
 *
 * @param props PrintAuditModalProps
 * @returns JSX.Element | null
 */
export function PrintAuditModal({ print, onClose }: PrintAuditModalProps): React.JSX.Element | null {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    if (print) {
      window.addEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "hidden";
    }
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "unset";
    };
  }, [print, onClose]);

  if (!print) return null;

  const formatCurrency = (val: number): string => {
    return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(val);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 overflow-y-auto">
      <div className="fixed inset-0 bg-[#121316]/90" onClick={onClose} aria-hidden="true" />
      <div
        role="dialog"
        aria-modal="true"
        className="relative w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-2xl bg-[#1A1B20] border border-[#2E3038] p-6 sm:p-8 shadow-2xl text-[#F4F3EF]"
      >
        <button
          type="button"
          onClick={onClose}
          aria-label="Fechar auditoria"
          className="absolute right-6 top-6 text-[#8E9099] hover:text-[#F4F3EF]"
        >
          <X className="h-5 w-5" />
        </button>

        <div className="flex flex-col gap-5 sm:flex-row sm:items-start">
          <div className="relative h-32 w-32 flex-shrink-0 overflow-hidden bg-[#22232A]">
            <Image
              src={print.imageUrl}
              alt={print.title}
              fill
              sizes="128px"
              className="object-cover"
              unoptimized
              suppressHydrationWarning
            />
          </div>
          <div className="flex-1">
            <span className="text-[11px] font-semibold text-[#8E9099] uppercase">
              {print.theme} • {print.shopeeItemCode}
            </span>
            <h3 className="mt-1 text-lg font-bold text-[#F4F3EF]">{print.title}</h3>
            <div className="mt-3 flex items-center gap-4 text-xs text-[#8E9099]">
              <div>Preço: <span className="font-mono text-[#F4F3EF]">{formatCurrency(print.priceBrl)}</span></div>
              <div>Ritmo: <span className="font-mono text-[#F4F3EF]">+{print.dailySales} pçs/dia</span></div>
            </div>
          </div>
        </div>

        <div className="mt-8 border-t border-[#2E3038] pt-6">
          <h4 className="text-xs font-bold uppercase tracking-wider text-[#8E9099] mb-4">
            Ficha Técnica
          </h4>
          <div className="grid grid-cols-1 gap-x-4 gap-y-3 sm:grid-cols-2 text-xs">
            <div className="border-b border-[#2E3038] pb-2">
              <span className="block text-[#8E9099] mb-1">Modelagem</span>
              <span className="text-[#F4F3EF] font-medium">{print.specs?.cut ?? "Oversized Boxy"}</span>
            </div>
            <div className="border-b border-[#2E3038] pb-2">
              <span className="block text-[#8E9099] mb-1">Malha</span>
              <span className="text-[#F4F3EF] font-medium">{print.specs?.fabric ?? "100% Algodão"}</span>
            </div>
            <div className="border-b border-[#2E3038] pb-2">
              <span className="block text-[#8E9099] mb-1">Técnica</span>
              <span className="text-[#F4F3EF] font-medium">{print.specs?.printTechnique ?? "DTF Têxtil"}</span>
            </div>
            <div className="border-b border-[#2E3038] pb-2">
              <span className="block text-[#8E9099] mb-1">Custo Fabril</span>
              <span className="text-[#F4F3EF] font-medium font-mono">{formatCurrency(print.specs?.costEstimateBrl ?? 14.5)}</span>
            </div>
          </div>
        </div>

        {print.unitEconomics && (
          <div className="mt-8 border-t border-[#2E3038] pt-6">
            <h4 className="text-xs font-bold uppercase tracking-wider text-[#8E9099] mb-4">
              Viabilidade e Margem
            </h4>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
              <div>
                <span className="block text-[#8E9099] mb-1">Venda</span>
                <span className="font-mono text-[#F4F3EF]">{formatCurrency(print.unitEconomics.priceBrl)}</span>
              </div>
              <div>
                <span className="block text-[#8E9099] mb-1">Taxas</span>
                <span className="font-mono text-[#8E9099]">{formatCurrency(print.unitEconomics.shopeeCommissionBrl + print.unitEconomics.shopeeFixedFeeBrl)}</span>
              </div>
              <div>
                <span className="block text-[#8E9099] mb-1">Custo</span>
                <span className="font-mono text-[#8E9099]">{formatCurrency(print.unitEconomics.blankShirtCostBrl + print.unitEconomics.printCostBrl)}</span>
              </div>
              <div>
                <span className="block text-[#8E9099] mb-1">Líquido</span>
                <span className="font-mono text-[#F4F3EF] font-bold">{formatCurrency(print.unitEconomics.netProfitBrl)}</span>
              </div>
            </div>
          </div>
        )}

        <div className="mt-8 flex justify-end gap-4 pt-6 border-t border-[#2E3038]">
          <button onClick={onClose} className="px-5 py-2 text-xs font-semibold text-[#121316] bg-[#F4F3EF] hover:bg-white transition-colors">
            Fechar
          </button>
        </div>
      </div>
    </div>
  );
}
