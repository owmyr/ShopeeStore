"use client";

import React from "react";
import { Sparkles, Activity, LogOut } from "lucide-react";
import { useVip } from "@/context/VipContext";

/**
 * HeaderNav component props definition.
 */
interface HeaderNavProps {
  /** Label indicating the audit run batch and calendar week */
  edition: string;
  /** Optional legacy callback for opening the VIP drawer or modal */
  onOpenVipModal?: () => void;
}

/**
 * Sticky application header adhering to Google Antigravity Premium glass design.
 * Provides live telemetry status, brand recognition, and freemium/VIP authentication controls.
 *
 * @param props HeaderNavProps configuration
 * @returns JSX.Element
 */
export function HeaderNav({ edition }: HeaderNavProps): React.JSX.Element {
  const {
    isVip,
    deactivateVip,
    openUnlockModal,
    openCheckoutModal,
  } = useVip();

  return (
    <header className="sticky top-0 z-40 w-full border-b border-white/[0.08] bg-slate-950/75 backdrop-blur-xl transition-colors">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6 lg:px-8">
        {/* Brand identity */}
        <div className="flex items-center gap-3">
          <div className="relative flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 via-indigo-600 to-emerald-500 shadow-glow">
            <Activity className="h-5 w-5 text-white" aria-hidden="true" />
            <span className="absolute -bottom-1 -right-1 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-emerald-500 ring-2 ring-slate-950">
              <span className="h-1.5 w-1.5 rounded-full bg-white" />
            </span>
          </div>

          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold tracking-tight text-white sm:text-lg">
                TREND<span className="text-emerald-400">SCOUT</span>
              </span>
              <span className="rounded-md border border-emerald-500/30 bg-emerald-500/10 px-1.5 py-0.5 text-[10px] font-semibold tracking-wider text-emerald-300 uppercase">
                PRO
              </span>
            </div>
            <p className="hidden text-xs text-slate-400 sm:block">
              Inteligência de Mercado Shopee BR • Camisetas
            </p>
          </div>
        </div>

        {/* Live sync telemetry badge */}
        <div className="hidden md:flex items-center gap-2.5 rounded-full border border-emerald-500/20 bg-emerald-950/30 px-3.5 py-1.5 text-xs text-emerald-300">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
          </span>
          <span className="font-medium tracking-wide">DADOS SEMANAIS ATUALIZADOS</span>
          <span className="text-emerald-600">•</span>
          <span className="text-slate-300 font-mono text-[11px]">{edition}</span>
        </div>

        {/* Authentication & VIP State actions */}
        <div className="flex items-center gap-2 sm:gap-3">
          {isVip ? (
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-400/40 bg-amber-400/15 px-3 py-1.5 text-xs font-extrabold text-amber-300 shadow-glow">
                <span>⭐</span> CLUBE VIP ATIVO
              </span>
              <button
                type="button"
                onClick={deactivateVip}
                title="Sair do Clube VIP neste navegador"
                className="flex items-center gap-1 rounded-lg border border-white/[0.1] bg-white/[0.04] px-2.5 py-1.5 text-xs font-medium text-slate-400 transition-colors hover:bg-rose-500/10 hover:border-rose-500/30 hover:text-rose-300"
              >
                <LogOut className="h-3 w-3" />
                <span>Sair</span>
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2 sm:gap-3">
              <button
                type="button"
                onClick={openUnlockModal}
                className="rounded-xl border border-white/[0.12] bg-white/[0.04] px-3 py-2 text-xs font-medium text-slate-300 transition-colors hover:bg-white/[0.08] hover:text-white"
              >
                Já sou Assinante
              </button>
              <button
                type="button"
                onClick={() => openCheckoutModal()}
                className="group relative inline-flex items-center gap-2 overflow-hidden rounded-xl bg-gradient-to-r from-emerald-500 to-teal-400 px-3 sm:px-4 py-2 text-xs sm:text-sm font-semibold text-slate-950 shadow-lg shadow-emerald-500/20 transition-all duration-200 hover:scale-[1.02] hover:shadow-emerald-500/35 active:scale-[0.98] focus:outline-none focus:ring-2 focus:ring-emerald-400 focus:ring-offset-2 focus:ring-offset-slate-950"
              >
                <Sparkles className="h-4 w-4 transition-transform group-hover:rotate-12" aria-hidden="true" />
                <span>Assinar Clube VIP (R$ 97/mês)</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
