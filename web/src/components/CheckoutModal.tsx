"use client";

import React, { useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Sparkles, Check, MessageSquare, ShieldCheck, KeyRound } from "lucide-react";
import { useVip } from "@/context/VipContext";

/**
 * Props definition for CheckoutModal.
 */
interface CheckoutModalProps {
  /** Optional override for open/closed visibility state */
  isOpen?: boolean;
  /** Optional override callback triggered to close modal */
  onClose?: () => void;
}

/**
 * VIP Conversion modal with direct WhatsApp activation link.
 * Targets garment manufacturers with high-value weekly intelligence at R$ 97/month.
 * Adapts messaging to include the target item clicked by the user (e.g. print title or feature).
 *
 * @param props CheckoutModalProps
 * @returns JSX.Element | null
 */
export function CheckoutModal({ isOpen, onClose }: CheckoutModalProps): React.JSX.Element | null {
  const {
    isCheckoutModalOpen,
    closeCheckoutModal,
    openUnlockModal,
    selectedTargetItem,
  } = useVip();

  const isModalOpen = isOpen !== undefined ? isOpen : isCheckoutModalOpen;
  const handleClose = onClose || closeCheckoutModal;

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        handleClose();
      }
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

  const baseMessage = selectedTargetItem
    ? `Olá! Acessei o portal TrendScout e tenho interesse em desbloquear o item "${selectedTargetItem}" no Clube VIP.`
    : "Olá! Acessei o portal TrendScout e quero assinar o Radar Semanal de Estampas";

  const whatsappUrl = `https://wa.me/5511999999999?text=${encodeURIComponent(baseMessage)}`;

  const benefits = [
    "Radar Semanal Antecipado: novas estampas antes de saturarem na Shopee",
    "Fichas Técnicas Prontas: gramatura, corte e técnica recomendada (DTF / Silk)",
    "Filtro de Risco: pare de estampar o que entrou em guerra predatória de preço",
    "Suporte Direto via WhatsApp para tirar dúvidas de posicionamento",
    "Sem fidelidade: cancele quando quiser com 1 clique",
  ];

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 overflow-y-auto">
        {/* Backdrop */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={handleClose}
          className="fixed inset-0 bg-black/80 backdrop-blur-md"
          aria-hidden="true"
        />

        {/* Modal Card */}
        <motion.div
          role="dialog"
          aria-modal="true"
          aria-labelledby="checkout-headline"
          initial={{ opacity: 0, scale: 0.94, y: 16 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.94, y: 16 }}
          transition={{ duration: 0.25, ease: "easeOut" }}
          className="relative w-full max-w-lg overflow-hidden rounded-3xl border border-white/[0.12] bg-slate-900/95 p-6 sm:p-8 shadow-2xl backdrop-blur-2xl"
        >
          {/* Close button */}
          <button
            type="button"
            onClick={handleClose}
            aria-label="Fechar checkout"
            className="absolute right-4 top-4 rounded-xl border border-white/[0.08] bg-white/[0.04] p-2 text-slate-400 transition-colors hover:bg-white/[0.1] hover:text-white"
          >
            <X className="h-5 w-5" />
          </button>

          {/* Badge & Title */}
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/15 border border-emerald-500/30 px-3 py-1 text-xs font-bold text-emerald-400">
              <Sparkles className="h-3.5 w-3.5" />
              CLUBE EXCLUSIVO DE CONFECCIONISTAS
            </span>
          </div>

          <h3 id="checkout-headline" className="mt-3 text-2xl font-extrabold text-white tracking-tight">
            Assine o Radar Semanal de Estampas
          </h3>

          {selectedTargetItem && (
            <div className="mt-2.5 inline-flex items-center gap-1.5 rounded-lg border border-amber-400/30 bg-amber-400/10 px-3 py-1 text-xs font-medium text-amber-300 max-w-full">
              <span className="text-slate-400 flex-shrink-0">Item selecionado:</span>
              <span className="text-white font-semibold truncate">{selectedTargetItem}</span>
            </div>
          )}

          <p className="mt-2 text-xs text-slate-300">
            Tenha acesso completo a todos os modelos auditados, relatórios detalhados e diretrizes antecipadas toda segunda-feira.
          </p>

          {/* Pricing Box */}
          <div className="mt-5 rounded-2xl border border-white/[0.08] bg-white/[0.02] p-5">
            <div className="flex items-baseline justify-between">
              <div>
                <span className="text-xs text-slate-400 font-medium">Plano Mensal Recorrente</span>
                <div className="flex items-baseline gap-1 mt-0.5">
                  <span className="text-3xl font-black text-white font-mono">R$ 97</span>
                  <span className="text-sm font-semibold text-slate-400">/mês</span>
                </div>
              </div>
              <span className="rounded-lg bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-1 text-[11px] font-bold text-emerald-300">
                Paga-se com 3 camisetas
              </span>
            </div>

            {/* Benefits List */}
            <ul className="mt-4 space-y-2.5 text-xs text-slate-200">
              {benefits.map((benefit) => (
                <li key={benefit} className="flex items-start gap-2">
                  <Check className="h-4 w-4 text-emerald-400 flex-shrink-0 mt-0.5" />
                  <span>{benefit}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Conversion CTA */}
          <div className="mt-6 space-y-3">
            <a
              href={whatsappUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex w-full items-center justify-center gap-2.5 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-400 py-3.5 text-sm font-extrabold text-slate-950 shadow-lg shadow-emerald-500/25 transition-all hover:scale-[1.01] hover:shadow-emerald-500/40 active:scale-[0.99]"
            >
              <MessageSquare className="h-4 w-4" />
              <span>Garantir Vaga no WhatsApp VIP</span>
            </a>

            <div className="flex items-center justify-center gap-2 text-[11px] text-slate-400">
              <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" />
              <span>Ativação imediata • Fale direto com o curador</span>
            </div>
          </div>

          {/* Option for existing subscribers */}
          <div className="mt-5 border-t border-white/[0.08] pt-4 text-center">
            <button
              type="button"
              onClick={() => openUnlockModal()}
              className="inline-flex items-center gap-1.5 text-xs text-slate-400 transition-colors hover:text-amber-300 hover:underline"
            >
              <KeyRound className="h-3.5 w-3.5 text-amber-400" />
              <span>Já tem uma chave de acesso? Digite aqui</span>
            </button>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
