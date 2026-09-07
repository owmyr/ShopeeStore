"use client";

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useMemo,
} from "react";

/**
 * Interface defining the VIP and freemium subscription state and actions.
 */
export interface VipContextValue {
  /** Indicates whether the current session has active VIP privileges */
  isVip: boolean;
  /**
   * Attempts to activate VIP status using a subscriber token.
   * Persists token to local storage upon successful validation.
   */
  activateVip: (token: string) => boolean;
  /** Revokes VIP status and clears persistent storage */
  deactivateVip: () => void;
  /** Controls visibility of the VIP unlock PIN entry modal */
  isUnlockModalOpen: boolean;
  /** Opens the unlock modal for existing subscribers */
  openUnlockModal: () => void;
  /** Closes the unlock modal */
  closeUnlockModal: () => void;
  /** Controls visibility of the VIP subscription checkout modal */
  isCheckoutModalOpen: boolean;
  /**
   * Opens the checkout modal, optionally registering a target item
   * (e.g. print title or feature name) to customize conversion context.
   */
  openCheckoutModal: (targetItem?: string) => void;
  /** Closes the checkout modal and resets conversion target */
  closeCheckoutModal: () => void;
  /** Optional contextual item that triggered the checkout prompt */
  selectedTargetItem: string | null;
}

const VipContext = createContext<VipContextValue | undefined>(undefined);

const LOCAL_STORAGE_KEY = "trendscout_vip_token";
const STATIC_VALID_TOKENS = [
  "TS-VIP-2026",
  "CLUBE-VIP",
  "VIP-SETEMBRO",
  "VIP2026",
];

/**
 * Validates subscriber tokens against predefined static keys, wildcard patterns,
 * and environment overrides to ensure flexible coupon and entitlement provisioning.
 *
 * @param token Candidate token entered by user or parsed from URL
 * @returns boolean indicating validity
 */
export function isValidVipToken(token: string): boolean {
  if (!token) return false;
  const clean = token.trim().toUpperCase();

  if (STATIC_VALID_TOKENS.includes(clean)) {
    return true;
  }

  // Matches pattern TS-VIP-* to allow programmatic voucher batching
  if (/^TS-VIP-.*$/i.test(clean)) {
    return true;
  }

  const envKey = process.env.NEXT_PUBLIC_VIP_KEY;
  if (envKey && clean === envKey.trim().toUpperCase()) {
    return true;
  }

  return false;
}

/**
 * Provides freemium gating state, VIP session persistence, and modal controls
 * across the application hierarchy.
 *
 * @param props Component children
 * @returns JSX.Element
 */
export function VipProvider({
  children,
}: {
  children: React.ReactNode;
}): React.JSX.Element {
  const [isVip, setIsVip] = useState<boolean>(false);
  const [isUnlockModalOpen, setIsUnlockModalOpen] = useState<boolean>(false);
  const [isCheckoutModalOpen, setIsCheckoutModalOpen] = useState<boolean>(false);
  const [selectedTargetItem, setSelectedTargetItem] = useState<string | null>(null);

  // Synchronize initial VIP status from URL query parameters or persistent local storage
  useEffect(() => {
    try {
      const searchParams = new URLSearchParams(window.location.search);
      const urlToken = searchParams.get("vip");

      if (urlToken && isValidVipToken(urlToken)) {
        const normalized = urlToken.trim().toUpperCase();
        localStorage.setItem(LOCAL_STORAGE_KEY, normalized);
        setIsVip(true);

        // Sanitize browser history by removing promotional query parameter
        const cleanUrl = window.location.pathname;
        window.history.replaceState({}, document.title, cleanUrl);
        return;
      }

      const storedToken = localStorage.getItem(LOCAL_STORAGE_KEY);
      if (storedToken && isValidVipToken(storedToken)) {
        setIsVip(true);
      }
    } catch {
      // LocalStorage or window may be unavailable or restricted in sandboxed environments
    }
  }, []);

  const activateVip = useCallback((token: string): boolean => {
    if (isValidVipToken(token)) {
      const normalized = token.trim().toUpperCase();
      try {
        localStorage.setItem(LOCAL_STORAGE_KEY, normalized);
      } catch {
        // Handle storage write quotas or private mode restrictions gracefully
      }
      setIsVip(true);
      return true;
    }
    return false;
  }, []);

  const deactivateVip = useCallback((): void => {
    try {
      localStorage.removeItem(LOCAL_STORAGE_KEY);
    } catch {
      // Handle storage access errors
    }
    setIsVip(false);
  }, []);

  const openUnlockModal = useCallback((): void => {
    setIsCheckoutModalOpen(false);
    setIsUnlockModalOpen(true);
  }, []);

  const closeUnlockModal = useCallback((): void => {
    setIsUnlockModalOpen(false);
  }, []);

  const openCheckoutModal = useCallback((targetItem?: string): void => {
    setSelectedTargetItem(targetItem ?? null);
    setIsUnlockModalOpen(false);
    setIsCheckoutModalOpen(true);
  }, []);

  const closeCheckoutModal = useCallback((): void => {
    setIsCheckoutModalOpen(false);
    setSelectedTargetItem(null);
  }, []);

  const contextValue = useMemo<VipContextValue>(
    () => ({
      isVip,
      activateVip,
      deactivateVip,
      isUnlockModalOpen,
      openUnlockModal,
      closeUnlockModal,
      isCheckoutModalOpen,
      openCheckoutModal,
      closeCheckoutModal,
      selectedTargetItem,
    }),
    [
      isVip,
      activateVip,
      deactivateVip,
      isUnlockModalOpen,
      openUnlockModal,
      closeUnlockModal,
      isCheckoutModalOpen,
      openCheckoutModal,
      closeCheckoutModal,
      selectedTargetItem,
    ],
  );

  return (
    <VipContext.Provider value={contextValue}>{children}</VipContext.Provider>
  );
}

/**
 * Hook to consume the VIP context across components.
 * Throws an explicit error if invoked outside of a VipProvider hierarchy.
 *
 * @returns VipContextValue
 */
export function useVip(): VipContextValue {
  const context = useContext(VipContext);
  if (!context) {
    throw new Error("useVip must be used within a VipProvider");
  }
  return context;
}
