"use client";

import React, { useEffect } from "react";
import { X } from "lucide-react";
import { useVip } from "@/context/VipContext";

interface CheckoutModalProps {
  isOpen?: boolean;
  onClose?: () => void;
}

/**
 * VIP Conversion modal with direct WhatsApp activation link.
 * Dignified VIP activation dialog without flashy sales pressure.
 *
 * @param props CheckoutModalProps
 * @returns JSX.Element | null
 */
export function CheckoutModal({ isOpen, onClose }: CheckoutModalProps): React.JSX.Element | null {
  const { isCheckoutModalOpen, closeCheckoutModal, openUnlockModal } = useVip();

  const isModalOpen = isOpen !== undefined ? isOpen : isCheckoutModalOpen;
  const handleClose = onClose || closeCheckoutModal;

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") handleClose();
    };
    if (isModalOpen) {
      window.addEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "hidden";
    }
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "unset";
    };
  }, [isModalOpen, handleClose]);

  if (!isModalOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 overflow-y-auto">
      <div className="fixed inset-0 bg-[#121316]/90" onClick={handleClose} aria-hidden="true" />
      <div
        role="dialog"
        aria-modal="true"
        className="relative w-full max-w-lg rounded-2xl bg-[#1A1B20] border border-[#2E3038] p-6 sm:p-8 shadow-2xl"
      >
        <button
          type="button"
          onClick={handleClose}
          className="absolute right-6 top-6 text-[#8E9099] hover:text-[#F4F3EF]"
        >
          <X className="h-5 w-5" />
        </button>

        <h3 className="text-xl font-bold text-[#F4F3EF]">Assine o Radar Semanal</h3>
        <p className="mt-2 text-xs text-[#8E9099]">
          Acesso completo a diretrizes e fichas técnicas.
        </p>

        <div className="mt-6 border-t border-[#2E3038] pt-6">
          <ul className="space-y-3 text-sm text-[#F4F3EF]">
            <li className="flex gap-2">• Relatório Semanal em PDF/PNG</li>
            <li className="flex gap-2">• Acesso irrestrito a todos os 12 anúncios concorrentes</li>
            <li className="flex gap-2">• Ficha técnica completa e viabilidade de margem</li>
          </ul>
        </div>

        <div className="mt-8 flex flex-col gap-4">
          <a
            href="https://wa.me/5511999999999?text=Ol%C3%A1"
            target="_blank"
            rel="noopener noreferrer"
            className="w-full text-center bg-[#E27D44] text-[#121316] py-3 text-sm font-bold hover:opacity-90 transition-opacity"
          >
            Ativar Acesso via WhatsApp
          </a>
          <button
            type="button"
            onClick={() => {
              handleClose();
              openUnlockModal();
            }}
            className="text-xs text-[#8E9099] hover:text-[#F4F3EF]"
          >
            Já é assinante? Inserir código de acesso
          </button>
        </div>
      </div>
    </div>
  );
}
