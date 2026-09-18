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
    <header className="sticky top-0 z-40 w-full border-b border-[#2E3038] bg-[#121316] transition-colors">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6 lg:px-8">
        {/* Brand identity */}
        <div className="flex items-center gap-3">
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold tracking-wide text-[#F4F3EF] sm:text-lg">
                TRENDSCOUT
              </span>
            </div>
            <p className="hidden text-xs text-[#8E9099] font-mono sm:block">
              // RELATÓRIO SEMANAL {edition} • CAMISETAS SHOPEE BR
            </p>
          </div>
        </div>

        {/* Authentication & VIP State actions */}
        <div className="flex items-center gap-2 sm:gap-4">
          {isVip ? (
            <div className="flex items-center gap-3">
              <span className="text-xs font-medium text-[#8E9099]">
                ⭐ Assinante Pro Ativo
              </span>
              <button
                type="button"
                onClick={deactivateVip}
                title="Sair"
                className="flex items-center gap-1 text-[#8E9099] hover:text-[#F4F3EF] transition-colors"
              >
                <LogOut className="h-4 w-4" />
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-4 text-xs font-medium">
              <button
                type="button"
                onClick={openUnlockModal}
                className="text-[#8E9099] hover:text-[#F4F3EF] transition-colors"
              >
                Acesso Assinante
              </button>
              <button
                type="button"
                onClick={() => openCheckoutModal()}
                className="text-[#E27D44] hover:text-[#F4F3EF] transition-colors"
              >
                Assinar Pro
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
