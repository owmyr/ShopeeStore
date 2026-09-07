"use client";

import React from "react";
import { motion } from "framer-motion";
import { Lock, Sparkles, ArrowRight } from "lucide-react";
import { useVip } from "@/context/VipContext";

/**
 * TeaserBanner component displayed below the hero section when the visitor is on the free tier.
 * Visually communicates the freemium gating boundaries and establishes clear conversion incentive
 * by highlighting missing high-value assets (locked prints, protected margin niches, technical cards).
 *
 * @returns JSX.Element | null
 */
export function TeaserBanner(): React.JSX.Element | null {
  const { isVip, openCheckoutModal } = useVip();

  // Omit banner entirely for subscribers enjoying unhindered access
  if (isVip) {
    return null;
  }

  return (
    <motion.section
      initial={{ opacity: 0, y: -12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      aria-label="Aviso de amostra gratuita"
      className="relative overflow-hidden rounded-3xl border border-emerald-500/30 bg-gradient-to-r from-emerald-950/50 via-slate-900/90 to-amber-950/40 p-6 sm:p-7 shadow-2xl backdrop-blur-xl"
    >
      {/* Background ambient lighting */}
      <div className="absolute -left-12 -top-12 h-44 w-44 rounded-full bg-emerald-500/15 blur-3xl pointer-events-none" />
      <div className="absolute -right-12 -bottom-12 h-44 w-44 rounded-full bg-amber-500/15 blur-3xl pointer-events-none" />

      <div className="relative z-10 flex flex-col items-center justify-between gap-5 text-center lg:flex-row lg:text-left">
        <div className="flex-1">
          {/* Badge */}
          <div className="inline-flex items-center gap-2 rounded-full border border-amber-400/30 bg-amber-400/10 px-3.5 py-1 text-xs font-bold text-amber-300">
            <Lock className="h-3.5 w-3.5 text-amber-400" />
            <span>MODO AMOSTRA GRATUITA • TOP 3 LIBERADOS</span>
          </div>

          <h2 className="mt-2.5 text-lg sm:text-xl font-extrabold text-white tracking-tight">
            Amostra Gratuita Limitada da Auditoria Shopee BR
          </h2>

          <p className="mt-1.5 max-w-3xl text-xs sm:text-sm text-slate-300 leading-relaxed">
            Você está visualizando a amostra aberta da semana. Faltam 12 estampas em alta aceleração, 7 nichos com margem protegida e as fichas de produção completas.
          </p>
        </div>

        {/* CTA Button */}
        <div className="flex flex-col sm:flex-row items-center gap-3 w-full sm:w-auto flex-shrink-0">
          <button
            type="button"
            onClick={() => openCheckoutModal()}
            className="flex w-full sm:w-auto items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-emerald-400 via-teal-400 to-emerald-500 px-6 py-3.5 text-xs sm:text-sm font-extrabold text-slate-950 shadow-xl shadow-emerald-500/25 transition-all hover:scale-105 active:scale-95"
          >
            <Sparkles className="h-4 w-4" />
            <span>Desbloquear Acesso VIP (R$ 97/mês)</span>
            <ArrowRight className="h-4 w-4" />
          </button>
        </div>
      </div>
    </motion.section>
  );
}
