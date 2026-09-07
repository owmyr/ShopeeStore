"use client";

import React, { useEffect } from "react";
import Image from "next/image";
import { motion, AnimatePresence } from "framer-motion";
import { X, Scissors, Layers, Printer, Percent, DollarSign, Users, ShieldCheck } from "lucide-react";
import type { BreakoutPrint } from "@/types/intelligence";

/**
 * Props definition for the PrintAuditModal dialog.
 */
interface PrintAuditModalProps {
  /** Selected breakout print item or null when dismissed */
  print: BreakoutPrint | null;
  /** Dismissal callback */
  onClose: () => void;
}

/**
 * Technical production audit modal for confeccionistas and lojistas.
 * Displays garment cut, fabric knit weight, printing technique, and margin estimation.
 *
 * @param props PrintAuditModalProps
 * @returns JSX.Element | null
 */
export function PrintAuditModal({ print, onClose }: PrintAuditModalProps): React.JSX.Element | null {
  // Dismiss on Escape key press to maintain keyboard accessibility standards
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
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
    return new Intl.NumberFormat("pt-BR", {
      style: "currency",
      currency: "BRL",
    }).format(val);
  };

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 overflow-y-auto">
        {/* Blurred Backdrop */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
          className="fixed inset-0 bg-black/80 backdrop-blur-md"
          aria-hidden="true"
        />

        {/* Modal Window */}
        <motion.div
          role="dialog"
          aria-modal="true"
          aria-labelledby="modal-headline"
          initial={{ opacity: 0, scale: 0.94, y: 16 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.94, y: 16 }}
          transition={{ duration: 0.25, ease: "easeOut" }}
          className="relative w-full max-w-2xl overflow-hidden rounded-3xl border border-white/[0.12] bg-slate-900/95 p-6 sm:p-8 shadow-2xl backdrop-blur-2xl"
        >
          {/* Close button */}
          <button
            type="button"
            onClick={onClose}
            aria-label="Fechar auditoria"
            className="absolute right-4 top-4 rounded-xl border border-white/[0.08] bg-white/[0.04] p-2 text-slate-400 transition-colors hover:bg-white/[0.1] hover:text-white"
          >
            <X className="h-5 w-5" />
          </button>

          {/* Header section with print image and title */}
          <div className="flex flex-col gap-5 sm:flex-row sm:items-center">
            <div className="relative h-28 w-28 flex-shrink-0 overflow-hidden rounded-2xl border border-white/[0.1] bg-slate-800">
              <Image
                src={print.imageUrl}
                alt={print.title}
                fill
                sizes="112px"
                className="object-cover"
                unoptimized
              />
            </div>

            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className="rounded-md border border-indigo-500/30 bg-indigo-500/10 px-2 py-0.5 text-[11px] font-semibold text-indigo-300">
                  {print.theme}
                </span>
                <span className="font-mono text-xs text-slate-400">{print.shopeeItemCode}</span>
              </div>
              <h3 id="modal-headline" className="mt-1 text-lg font-bold text-white sm:text-xl">
                {print.title}
              </h3>
              <div className="mt-2 flex items-center gap-4 text-xs text-slate-300">
                <div>
                  <span className="text-slate-400">Preço Shopee: </span>
                  <span className="font-bold text-emerald-400 font-mono">
                    {formatCurrency(print.priceBrl)}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400">Ritmo: </span>
                  <span className="font-bold text-amber-400 font-mono">
                    +{print.dailySales} pçs/dia
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Garment Technical Specifications Grid */}
          <div className="mt-6 border-t border-white/[0.08] pt-5">
            <div className="flex items-center gap-2 mb-4">
              <ShieldCheck className="h-4 w-4 text-emerald-400" />
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-300">
                Ficha Técnica Recomendada para Produção
              </h4>
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 text-xs">
              {/* Corte */}
              <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3.5">
                <div className="flex items-center gap-2 text-indigo-400 font-semibold mb-1">
                  <Scissors className="h-3.5 w-3.5" />
                  <span>Modelagem & Corte</span>
                </div>
                <p className="text-slate-200 font-medium">{print.specs?.cut ?? "Oversized Boxy"}</p>
              </div>

              {/* Malha */}
              <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3.5">
                <div className="flex items-center gap-2 text-emerald-400 font-semibold mb-1">
                  <Layers className="h-3.5 w-3.5" />
                  <span>Malha & Gramatura</span>
                </div>
                <p className="text-slate-200 font-medium">{print.specs?.fabric ?? "100% Algodão 30.1 Penteado"}</p>
              </div>

              {/* Técnica de Estamparia */}
              <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3.5">
                <div className="flex items-center gap-2 text-amber-400 font-semibold mb-1">
                  <Printer className="h-3.5 w-3.5" />
                  <span>Tecnologia de Impressão</span>
                </div>
                <p className="text-slate-200 font-medium">{print.specs?.printTechnique ?? "DTF Têxtil HD"}</p>
              </div>

              {/* Margem Estimada */}
              <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3.5">
                <div className="flex items-center gap-2 text-teal-400 font-semibold mb-1">
                  <Percent className="h-3.5 w-3.5" />
                  <span>Margem Bruta Estimada</span>
                </div>
                <p className="text-emerald-300 font-bold">{print.specs?.estimatedMargin ?? "65% - 70%"}</p>
              </div>

              {/* Custo Fabril Estimado */}
              <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3.5">
                <div className="flex items-center gap-2 text-cyan-400 font-semibold mb-1">
                  <DollarSign className="h-3.5 w-3.5" />
                  <span>Custo Fabril Médio (Estampada)</span>
                </div>
                <p className="text-slate-200 font-bold font-mono">
                  {formatCurrency(print.specs?.costEstimateBrl ?? 14.5)} / peça
                </p>
              </div>

              {/* Público-Alvo */}
              <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3.5">
                <div className="flex items-center gap-2 text-pink-400 font-semibold mb-1">
                  <Users className="h-3.5 w-3.5" />
                  <span>Público & Posicionamento</span>
                </div>
                <p className="text-slate-200 font-medium">{print.specs?.targetAudience ?? "Jovem / Urbano"}</p>
              </div>
            </div>
          </div>

          {/* Action Footer */}
          <div className="mt-6 flex flex-col sm:flex-row items-center justify-between gap-3 border-t border-white/[0.08] pt-4">
            <p className="text-[11px] text-slate-400">
              *Estimativas industriais calculadas para tiragens a partir de 50 peças.
            </p>
            <button
              type="button"
              onClick={onClose}
              className="w-full sm:w-auto rounded-xl bg-slate-800 hover:bg-slate-700 px-5 py-2 text-xs font-semibold text-white transition-colors"
            >
              Concluir Inspeção
            </button>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
