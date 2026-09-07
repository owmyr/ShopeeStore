"use client";

import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, KeyRound, ArrowRight, AlertCircle, CheckCircle2 } from "lucide-react";
import { useVip } from "@/context/VipContext";

/**
 * Glassmorphic VIP Unlock Modal designed following the Google Antigravity Premium specification.
 * Provides subscribers with a direct input field to enter their PIN or VIP token,
 * offering instant feedback and seamless routing to the CheckoutModal for non-subscribers.
 *
 * @returns JSX.Element | null
 */
export function VipUnlockModal(): React.JSX.Element | null {
  const {
    isUnlockModalOpen,
    closeUnlockModal,
    activateVip,
    openCheckoutModal,
  } = useVip();

  const [tokenInput, setTokenInput] = useState<string>("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [success, setSuccess] = useState<boolean>(false);

  // Maintain accessibility and close dialog on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        closeUnlockModal();
      }
    };

    if (isUnlockModalOpen) {
      window.addEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "hidden";
      setTokenInput("");
      setErrorMessage(null);
      setSuccess(false);
    }

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "unset";
    };
  }, [isUnlockModalOpen, closeUnlockModal]);

  if (!isUnlockModalOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!tokenInput.trim()) {
      setErrorMessage("Por favor, digite sua chave de assinante.");
      return;
    }

    const activated = activateVip(tokenInput.trim());
    if (activated) {
      setSuccess(true);
      setErrorMessage(null);
      setTimeout(() => {
        closeUnlockModal();
      }, 750);
    } else {
      setErrorMessage(
        "Chave de acesso inválida ou expirada. Verifique se digitou corretamente ou solicite uma nova chave ao suporte.",
      );
    }
  };

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 overflow-y-auto">
        {/* Glassmorphic Dark Backdrop */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={closeUnlockModal}
          className="fixed inset-0 bg-black/80 backdrop-blur-md"
          aria-hidden="true"
        />

        {/* Modal Window */}
        <motion.div
          role="dialog"
          aria-modal="true"
          aria-labelledby="unlock-modal-title"
          initial={{ opacity: 0, scale: 0.94, y: 16 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.94, y: 16 }}
          transition={{ duration: 0.25, ease: "easeOut" }}
          className="relative w-full max-w-md overflow-hidden rounded-3xl border border-white/[0.12] bg-slate-900/95 p-6 sm:p-8 shadow-2xl backdrop-blur-2xl"
        >
          {/* Close button */}
          <button
            type="button"
            onClick={closeUnlockModal}
            aria-label="Fechar validação de chave"
            className="absolute right-4 top-4 rounded-xl border border-white/[0.08] bg-white/[0.04] p-2 text-slate-400 transition-colors hover:bg-white/[0.1] hover:text-white"
          >
            <X className="h-5 w-5" />
          </button>

          {/* Header Icon & Title */}
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-br from-amber-400/20 to-amber-600/10 border border-amber-400/30 text-amber-400 shadow-glow">
              <KeyRound className="h-5 w-5" />
            </div>
            <div>
              <span className="text-[11px] font-bold uppercase tracking-wider text-amber-400">
                Área de Assinantes
              </span>
              <h3 id="unlock-modal-title" className="text-xl font-extrabold text-white tracking-tight">
                Liberar Acesso VIP
              </h3>
            </div>
          </div>

          <p className="mt-3 text-xs sm:text-sm text-slate-300 leading-relaxed">
            Insira sua chave de acesso ou PIN exclusivo de assinante para desbloquear todas as estampas, fichas técnicas e análise de margem.
          </p>

          {/* Unlock Form */}
          <form onSubmit={handleSubmit} className="mt-5 space-y-4">
            <div>
              <label
                htmlFor="vip-token-input"
                className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5"
              >
                Chave de Assinante / PIN
              </label>
              <input
                id="vip-token-input"
                type="text"
                autoComplete="off"
                placeholder="Ex: TS-VIP-2026 ou CLUBE-VIP"
                value={tokenInput}
                onChange={(e) => {
                  setTokenInput(e.target.value);
                  if (errorMessage) setErrorMessage(null);
                }}
                disabled={success}
                className="w-full rounded-xl border border-white/[0.12] bg-slate-950/70 px-4 py-3 font-mono text-sm text-white placeholder-slate-500 transition-all focus:border-amber-400 focus:outline-none focus:ring-2 focus:ring-amber-400/20"
              />
            </div>

            {/* Error Message */}
            {errorMessage && (
              <motion.div
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex items-start gap-2 rounded-xl border border-rose-500/20 bg-rose-500/10 p-3 text-xs text-rose-300"
              >
                <AlertCircle className="h-4 w-4 flex-shrink-0 mt-0.5 text-rose-400" />
                <span>{errorMessage}</span>
              </motion.div>
            )}

            {/* Success Feedback */}
            {success && (
              <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className="flex items-center gap-2 rounded-xl border border-emerald-500/30 bg-emerald-500/15 p-3 text-xs text-emerald-300 font-semibold"
              >
                <CheckCircle2 className="h-4 w-4 flex-shrink-0 text-emerald-400" />
                <span>Chave validada com sucesso! Liberando acesso VIP...</span>
              </motion.div>
            )}

            <button
              type="submit"
              disabled={success}
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-amber-400 via-amber-500 to-amber-600 py-3 text-sm font-extrabold text-slate-950 shadow-lg shadow-amber-500/25 transition-all hover:scale-[1.01] hover:shadow-amber-500/40 active:scale-[0.99] disabled:opacity-50"
            >
              <span>{success ? "Acesso VIP Ativado" : "Validar Chave & Desbloquear"}</span>
              <ArrowRight className="h-4 w-4" />
            </button>
          </form>

          {/* Alternative Link for Non-Subscribers */}
          <div className="mt-5 border-t border-white/[0.08] pt-4 text-center">
            <button
              type="button"
              onClick={() => openCheckoutModal()}
              className="text-xs text-slate-400 transition-colors hover:text-emerald-400 hover:underline"
            >
              Ainda não é assinante? Conheça o Clube VIP (R$ 97/mês)
            </button>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
