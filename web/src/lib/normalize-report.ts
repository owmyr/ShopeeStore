import type {
  ClientReportPayload,
  MacroMarketOverview,
  NicheSummary,
  BreakoutPrint,
  FabricModelingMetric,
  StrategicDirectivesPayload,
} from "@/types/intelligence";
import { FALLBACK_CLIENT_REPORT } from "./fallback-data";

/**
 * Normalizes raw report JSON from any pipeline version into the strict ClientReportPayload.
 * Ensures complete backward/forward compatibility and prevents client hydration crashes.
 *
 * @param raw Raw JSON object parsed from /data/client_report.json
 * @returns Fully validated and populated ClientReportPayload
 */
export function normalizeClientReport(raw: any): ClientReportPayload {
  if (!raw || typeof raw !== "object") {
    return FALLBACK_CLIENT_REPORT;
  }

  // 1. Meta & Edition
  const edition =
    raw.edition ||
    raw.meta?.period_label ||
    FALLBACK_CLIENT_REPORT.edition;

  const generatedAt =
    raw.generatedAt ||
    raw.meta?.generated_at ||
    FALLBACK_CLIENT_REPORT.generatedAt;

  // 2. Macro Overview
  const rawMacro = raw.macro || raw.market_overview || {};
  const priceBench = rawMacro.price_benchmark || {};

  const macro: MacroMarketOverview = {
    auditedListings:
      rawMacro.auditedListings ??
      rawMacro.printed_products_count ??
      rawMacro.monitored_products_count ??
      FALLBACK_CLIENT_REPORT.macro.auditedListings,
    weeklyRevenueBrl:
      rawMacro.weeklyRevenueBrl ??
      rawMacro.weekly_estimated_revenue_brl ??
      FALLBACK_CLIENT_REPORT.macro.weeklyRevenueBrl,
    dailyUnitVelocity:
      rawMacro.dailyUnitVelocity ??
      rawMacro.daily_volume_velocity ??
      FALLBACK_CLIENT_REPORT.macro.dailyUnitVelocity,
    medianPriceBrl:
      rawMacro.medianPriceBrl ??
      priceBench.p50 ??
      FALLBACK_CLIENT_REPORT.macro.medianPriceBrl,
    priceP25Brl:
      rawMacro.priceP25Brl ??
      priceBench.p25 ??
      FALLBACK_CLIENT_REPORT.macro.priceP25Brl,
    priceP75Brl:
      rawMacro.priceP75Brl ??
      priceBench.p75 ??
      FALLBACK_CLIENT_REPORT.macro.priceP75Brl,
  };

  // 3. Niches
  const rawNiches = Array.isArray(raw.niches) ? raw.niches : [];
  const niches: NicheSummary[] = rawNiches.map((n: any, idx: number) => {
    let tag: NicheSummary["tag"] = "Equilibrado";
    if (n.tag) {
      tag = n.tag;
    } else if (n.status_key === "high_demand_low_comp" || (n.price_p50_brl ?? 0) >= 35) {
      tag = "Alta Margem";
    } else if (n.status_key === "high_comp" || (n.price_p50_brl ?? 0) < 28) {
      tag = "Guerra de Preço";
    }

    return {
      id: String(n.id || n.theme_id || `niche-${idx}`),
      name: String(n.name || n.theme_name || "Nicho"),
      volume: Number(n.volume ?? n.listings_count ?? 15),
      dailyVelocity: Number(n.dailyVelocity ?? n.daily_velocity ?? 0),
      priceP25: Number(n.priceP25 ?? n.price_p25_brl ?? 0),
      priceMedian: Number(n.priceMedian ?? n.price_p50_brl ?? 0),
      priceP75: Number(n.priceP75 ?? n.price_p75_brl ?? 0),
      tag,
      badge: String(n.badge || n.status_label || (tag === "Alta Margem" ? "Alta Margem" : "Mercado Ativo")),
      sharePercent: Number(n.sharePercent ?? n.share_pct ?? 5.0),
    };
  });

  // 4. Breakout Prints (supports both "breakouts" and "breakout_prints")
  const rawBreakouts = Array.isArray(raw.breakouts)
    ? raw.breakouts
    : Array.isArray(raw.breakout_prints)
    ? raw.breakout_prints
    : [];

  const breakouts: BreakoutPrint[] = rawBreakouts.map((b: any, idx: number) => {
    const rawAudit = b.audit || b.specs || {};
    return {
      id: String(b.id || `print-${idx}`),
      title: String(b.title || "Camiseta Estampada"),
      imageUrl: String(b.imageUrl || b.image_url || "/images/prints/placeholder.webp"),
      theme: String(b.theme || b.theme_name || "Geral"),
      dailySales: Number(b.dailySales ?? b.daily_velocity ?? 0),
      historicalSales: Number(b.historicalSales ?? b.sold_count ?? 0),
      priceBrl: Number(b.priceBrl ?? b.price_brl ?? 0),
      shopeeItemCode: String(b.shopeeItemCode || b.id || `item-${idx}`),
      specs: {
        cut: String(rawAudit.cut || "Oversized Boxy"),
        fabric: String(rawAudit.fabric || "100% Algodão 30.1 Penteado"),
        printTechnique: String(rawAudit.printTechnique || rawAudit.print_technique || "DTF Têxtil HD"),
        estimatedMargin: String(rawAudit.estimatedMargin || rawAudit.margin_estimate || "65% - 70%"),
        costEstimateBrl: Number(rawAudit.costEstimateBrl ?? rawAudit.cost_estimate_brl ?? 14.5),
        targetAudience: String(rawAudit.targetAudience || rawAudit.target_audience || "Jovem / Streetwear"),
      },
    };
  });

  // 5. Fabric Radar (supports both "fabricRadar" and "fabric_radar")
  const rawFabric = Array.isArray(raw.fabricRadar)
    ? raw.fabricRadar
    : Array.isArray(raw.fabric_radar)
    ? raw.fabric_radar
    : [];

  const fabricRadar: FabricModelingMetric[] = rawFabric.map((f: any) => {
    let trend: "up" | "stable" | "down" = "stable";
    if (f.trend === "up" || f.trend === "down" || f.trend === "stable") {
      trend = f.trend;
    } else if (typeof f.trend === "string" && f.trend.toLowerCase().includes("alta")) {
      trend = "up";
    }

    return {
      feature: String(f.feature || "Característica Têxtil"),
      percentage: Number(f.percentage ?? f.share_pct ?? 0),
      trend,
      description: String(f.description || f.comment || "Padrão de produção auditado."),
    };
  });

  // 6. Directives (supports both whatToPrint/whatToPause and to_print/to_pause)
  const rawDirectives = raw.directives || {};
  const whatToPrint = Array.isArray(rawDirectives.whatToPrint)
    ? rawDirectives.whatToPrint
    : Array.isArray(rawDirectives.to_print)
    ? rawDirectives.to_print.map((p: any) => ({
        niche: String(p.name || p.theme_id || "Nicho Prioritário"),
        reason: String(p.action || p.reason || "Alta demanda e margem sadia."),
        recommendedThemes: [String(p.name || p.theme_id)],
        marginRating: ((p.p50_brl ?? 0) >= 35 ? "Alta" : "Média") as "Alta" | "Média",
      }))
    : FALLBACK_CLIENT_REPORT.directives.whatToPrint;

  const whatToPause = Array.isArray(rawDirectives.whatToPause)
    ? rawDirectives.whatToPause
    : Array.isArray(rawDirectives.to_pause)
    ? rawDirectives.to_pause.map((p: any) => ({
        niche: String(p.name || p.theme_id || "Nicho Sob Risco"),
        reason: String(p.reason || "Guerra de preços predatória."),
        riskFactor: String(p.mitigation || "Margem comprimida por sellers avulsos."),
      }))
    : FALLBACK_CLIENT_REPORT.directives.whatToPause;

  const directives: StrategicDirectivesPayload = {
    whatToPrint,
    whatToPause,
  };

  return {
    generatedAt,
    edition,
    macro,
    niches: niches.length > 0 ? niches : FALLBACK_CLIENT_REPORT.niches,
    breakouts: breakouts.length > 0 ? breakouts : FALLBACK_CLIENT_REPORT.breakouts,
    fabricRadar: fabricRadar.length > 0 ? fabricRadar : FALLBACK_CLIENT_REPORT.fabricRadar,
    directives,
  };
}
