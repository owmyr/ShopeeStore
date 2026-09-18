"use client";

import React, { useState, useEffect } from "react";
import { X } from "lucide-react";
import { useVip } from "@/context/VipContext";

/**
 * VIP Unlock Modal for subscribers to input their token.
 * Solid architectural design.
 *
 * @returns JSX.Element | null
 */
export function VipUnlockModal(): React.JSX.Element | null {
  const { isUnlockModalOpen, closeUnlockModal, activateVip } = useVip();
  const [tokenInput, setTokenInput] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") closeUnlockModal();
    };
    if (isUnlockModalOpen) {
      window.addEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "hidden";
      setTokenInput("");
      setError(null);
    }
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "unset";
    };
  }, [isUnlockModalOpen, closeUnlockModal]);

  if (!isUnlockModalOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (activateVip(tokenInput)) {
      closeUnlockModal();
    } else {
      setError("Chave inválida.");
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 overflow-y-auto">
      <div className="fixed inset-0 bg-[#121316]/90" onClick={closeUnlockModal} aria-hidden="true" />
      <div
        role="dialog"
        aria-modal="true"
        className="relative w-full max-w-md rounded-2xl bg-[#1A1B20] border border-[#2E3038] p-6 sm:p-8 shadow-2xl"
      >
        <button
          type="button"
          onClick={closeUnlockModal}
          className="absolute right-6 top-6 text-[#8E9099] hover:text-[#F4F3EF]"
        >
          <X className="h-5 w-5" />
        </button>

        <h3 className="text-xl font-bold text-[#F4F3EF]">Acesso VIP</h3>
        <p className="mt-2 text-xs text-[#8E9099]">Insira sua chave de assinante.</p>

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <input
            type="text"
            placeholder="Chave de Acesso"
            value={tokenInput}
            onChange={(e) => {
              setTokenInput(e.target.value);
              setError(null);
            }}
            className="w-full bg-[#121316] border border-[#2E3038] text-[#F4F3EF] focus:border-[#E27D44] px-4 py-2 text-sm outline-none transition-colors"
          />
          {error && <div className="text-xs text-[#E27D44]">{error}</div>}
          <button
            type="submit"
            className="w-full bg-[#F4F3EF] text-[#121316] py-2 text-sm font-bold hover:bg-white transition-colors"
          >
            Desbloquear
          </button>
        </form>
      </div>
    </div>
  );
}
