import type {
  ClientReportPayload,
  MacroMarketOverview,
  NicheSummary,
  BreakoutPrint,
  FabricModelingMetric,
  StrategicDirectivesPayload,
  UnitEconomics,
} from "@/types/intelligence";
import { FALLBACK_CLIENT_REPORT } from "./fallback-data";

/**
 * Normalizes or calculates unit economics for a breakout product.
 * Why: Guarantees every product in the portal has real profit simulation metrics
 * regardless of whether the incoming payload was generated with Track 9 or an earlier release.
 *
 * @param rawEcon Raw unit economics object from backend (may be undefined or snake_case)
 * @param priceBrl Retail selling price in BRL
 * @returns Fully typed and calculated UnitEconomics object
 */
export function normalizeUnitEconomics(rawEcon: any, priceBrl: number): UnitEconomics {
  if (rawEcon && typeof rawEcon === "object") {
    const rawPrice = Number(rawEcon.priceBrl ?? rawEcon.price_brl ?? priceBrl ?? 0);
    const shopeeCommissionBrl = Number(
      rawEcon.shopeeCommissionBrl ?? rawEcon.shopee_commission_brl ?? rawPrice * 0.20
    );
    const shopeeFixedFeeBrl = Number(
      rawEcon.shopeeFixedFeeBrl ?? rawEcon.shopee_fixed_fee_brl ?? 4.0
    );
    const blankShirtCostBrl = Number(
      rawEcon.blankShirtCostBrl ?? rawEcon.blank_shirt_cost_brl ?? 14.0
    );
    const printCostBrl = Number(rawEcon.printCostBrl ?? rawEcon.print_cost_brl ?? 7.0);
    const packagingTaxBrl = Number(
      rawEcon.packagingTaxBrl ?? rawEcon.packaging_tax_brl ?? rawPrice * 0.05 + 1.20
    );
    const netProfitBrl = Number(
      rawEcon.netProfitBrl ??
        rawEcon.net_profit_brl ??
        rawPrice -
          (shopeeCommissionBrl +
            shopeeFixedFeeBrl +
            blankShirtCostBrl +
            printCostBrl +
            packagingTaxBrl)
    );
    const netMarginPct = Number(
      rawEcon.netMarginPct ??
        rawEcon.net_margin_pct ??
        (netProfitBrl / Math.max(rawPrice, 1.0)) * 100
    );

    let status: UnitEconomics["status"] = "viable";
    if (
      rawEcon.status === "viable" ||
      rawEcon.status === "tight" ||
      rawEcon.status === "risk_single_item"
    ) {
      status = rawEcon.status;
    } else if (netProfitBrl < 3.0) {
      status = "risk_single_item";
    } else if (netProfitBrl < 7.0) {
      status = "tight";
    }

    let recommendation = String(rawEcon.recommendation || "");
    if (!recommendation) {
      if (status === "risk_single_item") {
        recommendation =
          "Alerta: Venda unitária com margem comprimida. Venda em KITS de 2 ou 3 peças para diluir a taxa fixa de R$ 4,00 da Shopee!";
      } else if (status === "tight") {
        recommendation =
          "Venda unitária viável com controle rígido de insumos. Ideal ofertar kit complementar.";
      } else {
        recommendation = "Margem sadia para venda avulsa e em escala.";
      }
    }

    const kitSimulatedProfitBrl = Number(
      rawEcon.kitSimulatedProfitBrl ?? rawEcon.kit_simulated_profit_brl ?? 0
    );

    return {
      priceBrl: Number(rawPrice.toFixed(2)),
      shopeeCommissionBrl: Number(shopeeCommissionBrl.toFixed(2)),
      shopeeFixedFeeBrl: Number(shopeeFixedFeeBrl.toFixed(2)),
      blankShirtCostBrl: Number(blankShirtCostBrl.toFixed(2)),
      printCostBrl: Number(printCostBrl.toFixed(2)),
      packagingTaxBrl: Number(packagingTaxBrl.toFixed(2)),
      netProfitBrl: Number(netProfitBrl.toFixed(2)),
      netMarginPct: Number(netMarginPct.toFixed(1)),
      status,
      recommendation,
      kitSimulatedProfitBrl: Number(kitSimulatedProfitBrl.toFixed(2)),
    };
  }

  // Fallback calculation directly from priceBrl
  const p = Math.max(0, priceBrl);
  const shopeeCommissionBrl = Number((p * 0.20).toFixed(2));
  const shopeeFixedFeeBrl = 4.0;
  const blankShirtCostBrl = 14.0;
  const printCostBrl = 7.0;
  const packagingTaxBrl = Number((p * 0.05 + 1.20).toFixed(2));
  const totalCostFeesBrl = Number(
    (
      shopeeCommissionBrl +
      shopeeFixedFeeBrl +
      blankShirtCostBrl +
      printCostBrl +
      packagingTaxBrl
    ).toFixed(2)
  );
  const netProfitBrl = Number((p - totalCostFeesBrl).toFixed(2));
  const netMarginPct = Number(((netProfitBrl / Math.max(p, 1.0)) * 100).toFixed(1));

  let status: UnitEconomics["status"] = "viable";
  let recommendation = "Margem sadia para venda avulsa e em escala.";
  if (netProfitBrl < 3.0) {
    status = "risk_single_item";
    recommendation =
      "Alerta: Venda unitária com margem comprimida. Venda em KITS de 2 ou 3 peças para diluir a taxa fixa de R$ 4,00 da Shopee!";
  } else if (netProfitBrl < 7.0) {
    status = "tight";
    recommendation =
      "Venda unitária viável com controle rígido de insumos. Ideal ofertar kit complementar.";
  }

  const kitPriceBrl = Number((p * 1.85).toFixed(2));
  const kitCommissionBrl = Number((kitPriceBrl * 0.20).toFixed(2));
  const kitPackagingTaxBrl = Number((kitPriceBrl * 0.05 + 1.20).toFixed(2));
  const kitTotalCost = Number(
    (kitCommissionBrl + 4.0 + 28.0 + 14.0 + kitPackagingTaxBrl).toFixed(2)
  );
  const kitSimulatedProfitBrl = Number((kitPriceBrl - kitTotalCost).toFixed(2));

  return {
    priceBrl: Number(p.toFixed(2)),
    shopeeCommissionBrl,
    shopeeFixedFeeBrl,
    blankShirtCostBrl,
    printCostBrl,
    packagingTaxBrl,
    netProfitBrl,
    netMarginPct,
    status,
    recommendation,
    kitSimulatedProfitBrl,
  };
}

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
    const priceBrl = Number(b.priceBrl ?? b.price_brl ?? 0);
    const unitEconomics = normalizeUnitEconomics(b.unit_economics || b.unitEconomics, priceBrl);

    return {
      id: String(b.id || `print-${idx}`),
      title: String(b.title || "Camiseta Estampada"),
      imageUrl: String(b.imageUrl || b.image_url || "/images/prints/placeholder.webp"),
      theme: String(b.theme || b.theme_name || "Geral"),
      dailySales: Number(b.dailySales ?? b.daily_velocity ?? 0),
      historicalSales: Number(b.historicalSales ?? b.sold_count ?? 0),
      priceBrl,
      shopeeItemCode: String(b.shopeeItemCode || b.id || `item-${idx}`),
      shopeeUrl: b.shopeeUrl || b.shopee_url || undefined,
      specs: {
        cut: String(rawAudit.corte_modelagem || rawAudit.cut || "Oversized Boxy"),
        fabric: String(rawAudit.malha_sugerida || rawAudit.fabric || "100% Algodão 30.1 Penteado"),
        printTechnique: String(rawAudit.tecnica_estampa || rawAudit.printTechnique || rawAudit.print_technique || "DTF Têxtil HD"),
        estimatedMargin: String(rawAudit.estimativa_margem || rawAudit.estimatedMargin || rawAudit.margin_estimate || "65% - 70%"),
        costEstimateBrl: Number(rawAudit.costEstimateBrl ?? rawAudit.cost_estimate_brl ?? 14.5),
        targetAudience: String(rawAudit.targetAudience || rawAudit.target_audience || "Jovem / Streetwear"),
      },
      unitEconomics,
    };
  });

  // 5. Fabric Radar (supports both "fabricRadar" and "fabric_radar", and both "name" and "feature")
  const rawFabric = Array.isArray(raw.fabricRadar)
    ? raw.fabricRadar
    : Array.isArray(raw.fabric_radar)
    ? raw.fabric_radar
    : [];

  const fabricRadar: FabricModelingMetric[] = rawFabric.map((f: any) => {
    let trend: "up" | "stable" | "down" = "up";
    if (f.trend === "up" || f.trend === "down" || f.trend === "stable") {
      trend = f.trend;
    } else if (typeof f.trend === "string" && f.trend.toLowerCase().includes("alta")) {
      trend = "up";
    }

    return {
      feature: String(f.name || f.feature || f.attribute || "Característica Têxtil"),
      percentage: Number(f.share_pct ?? f.percentage ?? 0),
      trend,
      description: String(f.comment || f.description || f.highlight || "Padrão de produção auditado."),
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
