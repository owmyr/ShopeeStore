/**
 * Intelligence domain models for the client-facing TrendScout portal.
 * Defines the public-safe data contract exported from the internal analyzer.
 */

/**
 * Technical production specifications for an audited apparel item.
 * Guides the confeccionista on cut, raw material, and application method.
 */
export interface GarmentProductionSpecs {
  /** Recommended cut/pattern (e.g., Oversized Street Boxy, Regular Fit) */
  cut: string;
  /** Ideal yarn and knit specifications (e.g., 100% Algodão 30.1 Penteado) */
  fabric: string;
  /** Primary printing technology (e.g., DTF Têxtil HD, Silk Screen 4 cores) */
  printTechnique: string;
  /** Estimated gross profit margin range */
  estimatedMargin: string;
  /** Estimated manufacturing cost in BRL */
  costEstimateBrl: number;
  /** Target demographic segment */
  targetAudience: string;
}

/**
 * Unit economics and real net margin simulation for apparel confection.
 * Why: Empowers confeccionistas with clear financial visibility on Shopee fees,
 * blank fabric costs, printing overheads, and multi-unit kit leverage.
 */
export interface UnitEconomics {
  /** Retail listing price in BRL */
  priceBrl: number;
  /** Shopee 20% marketplace commission in BRL */
  shopeeCommissionBrl: number;
  /** Fixed transaction fee charged by Shopee per unit sold */
  shopeeFixedFeeBrl: number;
  /** Standard wholesale blank garment cost (malha 30.1 penteado) */
  blankShirtCostBrl: number;
  /** Industrial printing application cost (DTF/Silk) */
  printCostBrl: number;
  /** Simples Nacional tax (~5%) plus packaging label and polybag */
  packagingTaxBrl: number;
  /** Real net profit after deducting all factory costs and marketplace fees */
  netProfitBrl: number;
  /** Net margin percentage relative to retail price */
  netMarginPct: number;
  /** Health status of single-piece unit sale */
  status: "viable" | "tight" | "risk_single_item";
  /** Contextual recommendation for confeccionistas */
  recommendation: string;
  /** Simulated net profit if sold as a 2-piece combo kit (price * 1.85) */
  kitSimulatedProfitBrl: number;
}

/**
 * Individual breakout product detected by velocity acceleration algorithms.
 */
export interface BreakoutPrint {
  /** Unique audit identifier */
  id: string;
  /** Commercial listing title sanitised of seller internal codes */
  title: string;
  /** Relative or absolute image URI */
  imageUrl: string;
  /** Primary classified aesthetic theme */
  theme: string;
  /** Estimated daily unit velocity */
  dailySales: number;
  /** Total cumulative historical sales recorded by marketplace */
  historicalSales: number;
  /** Retail price in Brazilian Reais */
  priceBrl: number;
  /** Public Shopee item reference code for audit trail */
  shopeeItemCode: string;
  /** Actionable garment and manufacturing specs */
  specs: GarmentProductionSpecs;
  /** Real net margin and unit economics breakdown */
  unitEconomics?: UnitEconomics;
}

/**
 * Niche aggregation metrics and price dispersion percentiles.
 */
export interface NicheSummary {
  /** Normalized slug identifier */
  id: string;
  /** Human-readable Portuguese theme name */
  name: string;
  /** Total active audited listings in this category */
  volume: number;
  /** Aggregated daily unit run rate */
  dailyVelocity: number;
  /** 25th percentile retail price in BRL */
  priceP25: number;
  /** Median retail price (50th percentile) in BRL */
  priceMedian: number;
  /** 75th percentile retail price in BRL */
  priceP75: number;
  /** Strategic categorization tag */
  tag: "Alta Margem" | "Guerra de Preço" | "Volume Explosivo" | "Equilibrado";
  /** Contextual recommendation badge */
  badge: string;
  /** Market share percentage relative to category total */
  sharePercent: number;
}

/**
 * Macro market overview aggregated across all active printed apparel listings.
 */
export interface MacroMarketOverview {
  /** Count of listings verified through the print filter pipeline */
  auditedListings: number;
  /** Total annualized or weekly GMV estimated from unit runs */
  weeklyRevenueBrl: number;
  /** Daily units sold across the monitored cohort */
  dailyUnitVelocity: number;
  /** Baseline median price across all audited products */
  medianPriceBrl: number;
  /** Interquartile 25th percentile baseline */
  priceP25Brl: number;
  /** Interquartile 75th percentile baseline */
  priceP75Brl: number;
}

/**
 * Fabric and modeling metric indicating raw material and pattern adoption.
 */
export interface FabricModelingMetric {
  /** Feature or attribute name */
  feature: string;
  /** Prevalence percentage in top-selling listings */
  percentage: number;
  /** Directional momentum compared to previous period */
  trend: "up" | "stable" | "down";
  /** Strategic commentary for the factory floor */
  description: string;
}

/**
 * What-to-print vs what-to-pause directives with strict mutual exclusion.
 */
export interface StrategicDirectivesPayload {
  /** Niches primed for production expansion */
  whatToPrint: Array<{
    niche: string;
    reason: string;
    recommendedThemes: string[];
    marginRating: "Alta" | "Média";
  }>;
  /** Niches suffering from margin degradation or cut-throat price warfare */
  whatToPause: Array<{
    niche: string;
    reason: string;
    riskFactor: string;
  }>;
}

/**
 * Top-level payload structure delivered to the web application.
 */
export interface ClientReportPayload {
  /** ISO 8601 UTC timestamp of pipeline generation */
  generatedAt: string;
  /** Display edition label */
  edition: string;
  /** Macro marketplace volume and velocity metrics */
  macro: MacroMarketOverview;
  /** Ranked list of niche summaries */
  niches: NicheSummary[];
  /** Highlighted high-acceleration print designs */
  breakouts: BreakoutPrint[];
  /** Textile and modeling attribute share */
  fabricRadar: FabricModelingMetric[];
  /** Tactical directives for confectioners */
  directives: StrategicDirectivesPayload;
}
