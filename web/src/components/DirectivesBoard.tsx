"use client";

import React from "react";
import { motion } from "framer-motion";
import {
  CheckCircle2,
  XCircle,
  TrendingUp,
  AlertTriangle,
  ShieldAlert,
  Lock,
} from "lucide-react";
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
 * Applies freemium teaser gating to secondary recommendations when the user is not VIP.
 *
 * @param props DirectivesBoardProps
 * @returns JSX.Element
 */
export function DirectivesBoard({ directives }: DirectivesBoardProps): React.JSX.Element {
  const { isVip, openCheckoutModal } = useVip();

  return (
    <section aria-labelledby="directives-heading" className="w-full space-y-6">
      {/* Section Header */}
      <div>
        <div className="flex items-center gap-2">
          <TrendingUp className="h-5 w-5 text-emerald-400" aria-hidden="true" />
          <h2 id="directives-heading" className="text-xl font-bold tracking-tight text-white sm:text-2xl">
            Diretrizes de Produção: O Que Estampar vs O Que Pausar
          </h2>
        </div>
        <p className="mt-1 text-sm text-slate-400">
          Recomendação algorítmica de alocação de maquinário com exclusão mútua (zero sobreposição de riscos).
        </p>
      </div>

      {/* Two Columns Grid */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Column 1: O Que Estampar (Green/Emerald Column) */}
        <div className="glass-panel relative overflow-hidden rounded-3xl p-6 sm:p-7 border-emerald-500/20 bg-gradient-to-b from-emerald-950/20 via-slate-900/60 to-slate-900/60">
          <div className="flex items-center justify-between pb-4 border-b border-emerald-500/20">
            <div className="flex items-center gap-2.5">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                <CheckCircle2 className="h-5 w-5" />
              </div>
              <div>
                <h3 className="text-base sm:text-lg font-bold text-white">
                  O Que Estampar Esta Semana
                </h3>
                <span className="text-xs text-emerald-400 font-medium">
                  Alta Demanda • Margens Preservadas
                </span>
              </div>
            </div>
            <span className="rounded-full bg-emerald-500/20 px-2.5 py-1 text-xs font-bold text-emerald-300">
              PRIORIDADE MÁXIMA
            </span>
          </div>

          <div className="mt-5 space-y-4">
            {(directives?.whatToPrint || []).map((item, idx) => {
              const isLocked = !isVip && idx > 0;

              return (
                <motion.div
                  key={item.niche}
                  initial={{ opacity: 0, x: -12 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.35, delay: idx * 0.08 }}
                  onClick={() => {
                    if (isLocked) {
                      openCheckoutModal("Diretrizes de Produção");
                    }
                  }}
                  role={isLocked ? "button" : undefined}
                  tabIndex={isLocked ? 0 : undefined}
                  onKeyDown={(e) => {
                    if (isLocked && (e.key === "Enter" || e.key === " ")) {
                      e.preventDefault();
                      openCheckoutModal("Diretrizes de Produção");
                    }
                  }}
                  aria-label={
                    isLocked
                      ? "Desbloquear diretriz de produção exclusiva VIP"
                      : undefined
                  }
                  className={`relative overflow-hidden rounded-2xl border p-4 transition-all ${
                    isLocked
                      ? "cursor-pointer border-amber-500/30 bg-slate-900/60 hover:border-amber-400/60"
                      : "border-emerald-500/15 bg-slate-900/50 hover:border-emerald-500/35"
                  }`}
                >
                  {/* Item Content (Blurred when locked) */}
                  <div className={isLocked ? "filter blur-[4px] select-none pointer-events-none opacity-40" : ""}>
                    <div className="flex items-center justify-between">
                      <h4 className="font-bold text-white text-sm sm:text-base">
                        {item.niche}
                      </h4>
                      <span className="rounded-md border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[11px] font-bold text-emerald-300">
                        Margem {item.marginRating}
                      </span>
                    </div>

                    <p className="mt-2 text-xs text-slate-300 leading-relaxed">
                      {item.reason}
                    </p>

                    {/* Sub-themes pills */}
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {(item.recommendedThemes || []).map((theme) => (
                        <span
                          key={theme}
                          className="rounded-md bg-white/[0.05] border border-white/[0.08] px-2 py-0.5 text-[11px] text-slate-300"
                        >
                          + {theme}
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Frosted VIP Lock Overlay */}
                  {isLocked && (
                    <div className="absolute inset-0 flex flex-col items-center justify-center gap-1.5 bg-slate-950/50 backdrop-blur-[2px] p-3 text-center">
                      <div className="inline-flex items-center gap-1.5 rounded-full border border-amber-400/40 bg-amber-400/20 px-3 py-1 text-xs font-bold text-amber-300 shadow-glow">
                        <Lock className="h-3.5 w-3.5 text-amber-400" />
                        <span>🔒 Diretriz Exclusiva VIP</span>
                      </div>
                      <span className="text-[11px] text-slate-300 font-medium">
                        Clique para desbloquear recomendação de corte e estampa
                      </span>
                    </div>
                  )}
                </motion.div>
              );
            })}
          </div>
        </div>

        {/* Column 2: O Que Pausar (Red/Rose Column) */}
        <div className="glass-panel relative overflow-hidden rounded-3xl p-6 sm:p-7 border-rose-500/20 bg-gradient-to-b from-rose-950/20 via-slate-900/60 to-slate-900/60">
          <div className="flex items-center justify-between pb-4 border-b border-rose-500/20">
            <div className="flex items-center gap-2.5">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-rose-500/20 text-rose-400 border border-rose-500/30">
                <XCircle className="h-5 w-5" />
              </div>
              <div>
                <h3 className="text-base sm:text-lg font-bold text-white">
                  O Que Pausar / Desacelerar
                </h3>
                <span className="text-xs text-rose-400 font-medium">
                  Saturação • Guerra Predatória de Preços
                </span>
              </div>
            </div>
            <span className="rounded-full bg-rose-500/20 px-2.5 py-1 text-xs font-bold text-rose-300">
              ALTO RISCO
            </span>
          </div>

          <div className="mt-5 space-y-4">
            {(directives?.whatToPause || []).map((item, idx) => {
              const isLocked = !isVip && idx > 0;

              return (
                <motion.div
                  key={item.niche}
                  initial={{ opacity: 0, x: 12 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.35, delay: idx * 0.08 }}
                  onClick={() => {
                    if (isLocked) {
                      openCheckoutModal("Diretrizes de Produção");
                    }
                  }}
                  role={isLocked ? "button" : undefined}
                  tabIndex={isLocked ? 0 : undefined}
                  onKeyDown={(e) => {
                    if (isLocked && (e.key === "Enter" || e.key === " ")) {
                      e.preventDefault();
                      openCheckoutModal("Diretrizes de Produção");
                    }
                  }}
                  aria-label={
                    isLocked
                      ? "Desbloquear diretriz de risco exclusiva VIP"
                      : undefined
                  }
                  className={`relative overflow-hidden rounded-2xl border p-4 transition-all ${
                    isLocked
                      ? "cursor-pointer border-amber-500/30 bg-slate-900/60 hover:border-amber-400/60"
                      : "border-rose-500/15 bg-slate-900/50 hover:border-rose-500/35"
                  }`}
                >
                  {/* Item Content (Blurred when locked) */}
                  <div className={isLocked ? "filter blur-[4px] select-none pointer-events-none opacity-40" : ""}>
                    <div className="flex items-center justify-between">
                      <h4 className="font-bold text-white text-sm sm:text-base">
                        {item.niche}
                      </h4>
                      <span className="flex items-center gap-1 rounded-md border border-rose-500/30 bg-rose-500/10 px-2 py-0.5 text-[11px] font-bold text-rose-300">
                        <ShieldAlert className="h-3 w-3" />
                        Risco de Estoque
                      </span>
                    </div>

                    <p className="mt-2 text-xs text-slate-300 leading-relaxed">
                      {item.reason}
                    </p>

                    {/* Risk Factor alert */}
                    <div className="mt-3 flex items-start gap-1.5 rounded-lg bg-rose-500/10 border border-rose-500/20 p-2 text-[11px] text-rose-300">
                      <AlertTriangle className="h-3.5 w-3.5 flex-shrink-0 mt-0.5" />
                      <span>
                        <strong>Fator de Risco: </strong>
                        {item.riskFactor}
                      </span>
                    </div>
                  </div>

                  {/* Frosted VIP Lock Overlay */}
                  {isLocked && (
                    <div className="absolute inset-0 flex flex-col items-center justify-center gap-1.5 bg-slate-950/50 backdrop-blur-[2px] p-3 text-center">
                      <div className="inline-flex items-center gap-1.5 rounded-full border border-amber-400/40 bg-amber-400/20 px-3 py-1 text-xs font-bold text-amber-300 shadow-glow">
                        <Lock className="h-3.5 w-3.5 text-amber-400" />
                        <span>🔒 Diretriz Exclusiva VIP</span>
                      </div>
                      <span className="text-[11px] text-slate-300 font-medium">
                        Clique para desbloquear alerta de risco industrial
                      </span>
                    </div>
                  )}
                </motion.div>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}
