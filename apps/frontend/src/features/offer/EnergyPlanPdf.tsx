import { Document, Page, Text, View, StyleSheet } from "@react-pdf/renderer";
import type { Recommendation, ScenarioResult, Tier, Assumption } from "@/lib/types";

// ── Data helpers ──────────────────────────────────────────────────────────────

function eur(n: number, opts?: { sign?: boolean }): string {
  const abs = Math.abs(n);
  const formatted = abs.toLocaleString("de-DE", { maximumFractionDigits: 0 });
  if (opts?.sign) return `${n >= 0 ? "+" : "-"}€${formatted}`;
  return `${n < 0 ? "-" : ""}€${formatted}`;
}

function prose(text: string): string {
  return text
    .replace(/\*+/g, "")
    .replace(/_/g, "")
    .replace(/`/g, "")
    .replace(/[\u{FE0F}\u{200D}]/gu, "")
    .replace(/\p{Extended_Pictographic}/gu, "")
    .replace(/[–—]/g, "-")
    .replace(/\s+/g, " ")
    .trim();
}

function letterParagraphs(rec: Recommendation): string[] {
  return `${rec.proposal_copy_md}\n\n${rec.upsell.reason_md}`
    .split(/\n{2,}/)
    .map((p) => prose(p.replace(/\s*\n\s*/g, " ").trim()))
    .filter(Boolean);
}

const ASSUMPTION_LABELS: Record<string, string> = {
  specific_yield_kwh_per_kwp: "Roof solar yield",
  retail_price_eur_kwh: "Grid electricity price",
  grid_fee_eur_kwh: "Local grid fee",
  kfw_subsidy_rate: "KfW 458 subsidy",
  financing_term_months: "Financing term",
  mastr_neighbour_count: "Neighbouring PV systems",
  climate_zone: "Climate zone",
};

const DRIVER_LABELS: Record<string, string> = {
  irradiance: "Local solar irradiance",
  "local irradiance": "Local solar irradiance",
  dynamic_spread: "Dynamic tariff spread",
  "dynamic tariff spread": "Dynamic tariff spread",
  hp_subsidy: "Heat-pump subsidy rate",
  "kfw subsidy rate": "KfW subsidy rate",
  autarky: "Self-consumption ratio",
};

function assumptionLabel(field: string): string {
  return (
    ASSUMPTION_LABELS[field] ??
    field
      .replace(/[_-]+/g, " ")
      .replace(/\b\w/g, (c) => c.toUpperCase())
  );
}

function driverLabel(raw: string): string {
  return (
    DRIVER_LABELS[raw.trim().toLowerCase()] ??
    raw.replace(/[_-]+/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
  );
}

function financeTermMonths(rec: Recommendation): number {
  const a = rec.assumptions.find((x) => x.field === "financing_term_months");
  const m = a?.value.match(/\d+/)?.[0];
  return m ? Number(m) : 180;
}

function monthsToYears(months: number): string {
  const y = months / 12;
  return Number.isInteger(y) ? `${y} yr` : `${y.toFixed(1)} yr`;
}

function tierScenario(rec: Recommendation, tier: Tier): ScenarioResult {
  return (
    rec.alternatives.find((a) => a.scenario_id === tier.scenario_id) ??
    rec.alternatives.find((a) => a.scenario_id === rec.best.scenario_id) ??
    rec.best
  );
}

function bundleLabel(s: string): string {
  return s.replace(/[☀️🔋♨️🚗]/gu, "").trim();
}

// ── Evidence type (passed in from the parent) ─────────────────────────────────

export interface PdfEvidence {
  roof?: string;
  permits?: { value: string; ok: boolean };
  subsidyValue: string;
  subsidySource: string;
  biggestDriver: string;
  confidenceLow: number;
  confidenceHigh: number;
  confidenceBand: number;
}

// ── Color palette ─────────────────────────────────────────────────────────────

const ACCENT = "#2f6fed";
const ACCENT_SOFT = "#eef3fd";
const SLATE = "#0f172a";
const MUTED = "#64748b";
const LIGHT = "#94a3b8";
const GREEN = "#047857";
const BORDER = "#e7eaf0";
const SURFACE = "#f6f8fc";
const SURFACE2 = "#fafbfe";
const WHITE = "#ffffff";

const TIER_ACCENT: Record<string, string> = {
  low: "#f59e0b",
  middle: "#ef4444",
  high: ACCENT,
};

// ── Styles ────────────────────────────────────────────────────────────────────

const s = StyleSheet.create({
  page: {
    backgroundColor: WHITE,
    paddingTop: 44,
    paddingBottom: 58,
    paddingHorizontal: 44,
    fontFamily: "Helvetica",
    fontSize: 10,
    color: SLATE,
  },

  // Page header
  pageHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: 20,
    paddingBottom: 14,
    borderBottomWidth: 1,
    borderBottomColor: BORDER,
    borderBottomStyle: "solid",
  },
  brandName: {
    fontFamily: "Helvetica-Bold",
    fontSize: 13,
    color: SLATE,
  },
  brandSub: {
    fontSize: 8,
    color: LIGHT,
    marginTop: 2,
  },
  headerDate: {
    fontSize: 9,
    color: MUTED,
    textAlign: "right",
  },

  // Page footer (absolute)
  pageFooter: {
    position: "absolute",
    bottom: 22,
    left: 44,
    right: 44,
    flexDirection: "row",
    justifyContent: "space-between",
    paddingTop: 7,
    borderTopWidth: 1,
    borderTopColor: BORDER,
    borderTopStyle: "solid",
  },
  footerText: {
    fontSize: 7,
    color: LIGHT,
  },

  // Hero
  heroTitle: {
    fontFamily: "Helvetica-Bold",
    fontSize: 19,
    color: SLATE,
    marginBottom: 3,
  },
  heroSub: {
    fontSize: 9.5,
    color: MUTED,
    marginBottom: 16,
  },

  // Section label
  sectionKicker: {
    fontFamily: "Helvetica-Bold",
    fontSize: 7.5,
    color: LIGHT,
    letterSpacing: 1.2,
    textTransform: "uppercase",
    marginBottom: 8,
    marginTop: 14,
  },

  // Tier cards
  tiersRow: {
    flexDirection: "row",
  },
  tierCard: {
    flex: 1,
    borderWidth: 1,
    borderColor: BORDER,
    borderStyle: "solid",
    borderRadius: 7,
    padding: 11,
    marginRight: 8,
    backgroundColor: WHITE,
    flexDirection: "column",
  },
  tierCardLast: {
    marginRight: 0,
  },
  tierCardRec: {
    borderColor: ACCENT,
    borderWidth: 1.5,
  },
  tierDotRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 2,
  },
  tierDot: {
    width: 5,
    height: 5,
    borderRadius: 3,
    marginRight: 4,
  },
  tierName: {
    fontFamily: "Helvetica-Bold",
    fontSize: 7,
    color: LIGHT,
    letterSpacing: 0.8,
    textTransform: "uppercase",
  },
  tierLabelText: {
    fontFamily: "Helvetica-Bold",
    fontSize: 9.5,
    color: SLATE,
    marginTop: 2,
    marginBottom: 6,
  },
  recBadge: {
    fontFamily: "Helvetica-Bold",
    fontSize: 6.5,
    color: WHITE,
    backgroundColor: ACCENT,
    borderRadius: 10,
    paddingHorizontal: 5,
    paddingVertical: 2,
    letterSpacing: 0.4,
    alignSelf: "flex-start",
    marginBottom: 6,
  },
  savingRow: {
    flexDirection: "row",
    alignItems: "flex-end",
    marginBottom: 2,
  },
  savingAmount: {
    fontFamily: "Helvetica-Bold",
    fontSize: 23,
    color: GREEN,
  },
  savingUnit: {
    fontSize: 9,
    color: MUTED,
    marginLeft: 2,
    marginBottom: 2,
  },
  savingMeta: {
    fontSize: 7.5,
    color: MUTED,
    marginBottom: 8,
  },
  bucketsRow: {
    flexDirection: "row",
    marginBottom: 8,
  },
  bucket: {
    flex: 1,
    backgroundColor: SURFACE,
    borderRadius: 4,
    padding: 5,
    marginRight: 3,
  },
  bucketLast: {
    marginRight: 0,
  },
  bucketLabel: {
    fontSize: 6.5,
    color: LIGHT,
    textTransform: "uppercase",
    letterSpacing: 0.5,
    marginBottom: 2,
  },
  bucketValue: {
    fontFamily: "Helvetica-Bold",
    fontSize: 8.5,
    color: SLATE,
  },
  rationaleFlex: {
    flex: 1,
  },
  rationaleText: {
    fontSize: 7.5,
    color: MUTED,
    lineHeight: 1.4,
  },
  tierFooter: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: 8,
    paddingTop: 7,
    borderTopWidth: 1,
    borderTopColor: BORDER,
    borderTopStyle: "solid",
  },
  tierFooterLabel: {
    fontSize: 7,
    color: LIGHT,
  },
  tierFooterValue: {
    fontFamily: "Helvetica-Bold",
    fontSize: 7.5,
    color: SLATE,
  },

  // Evidence grid
  evidenceGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
  },
  evidenceCard: {
    width: "49%",
    borderWidth: 1,
    borderColor: BORDER,
    borderStyle: "solid",
    borderRadius: 6,
    padding: 8,
    flexDirection: "row",
    marginBottom: 6,
    backgroundColor: WHITE,
  },
  evidenceCardOdd: {
    marginRight: "2%",
  },
  evidenceIconBox: {
    width: 20,
    height: 20,
    borderRadius: 5,
    backgroundColor: ACCENT_SOFT,
    alignItems: "center",
    justifyContent: "center",
    marginRight: 7,
    flexShrink: 0,
  },
  evidenceIconChar: {
    fontSize: 9,
    color: ACCENT,
    fontFamily: "Helvetica-Bold",
  },
  evidenceContent: {
    flex: 1,
  },
  evidenceLabel: {
    fontFamily: "Helvetica-Bold",
    fontSize: 8,
    color: SLATE,
    marginBottom: 2,
  },
  evidenceValue: {
    fontSize: 8,
    color: MUTED,
  },
  evidenceNote: {
    fontSize: 7,
    color: LIGHT,
    marginTop: 1,
  },
  evidenceOk: {
    color: GREEN,
    fontFamily: "Helvetica-Bold",
    fontSize: 8,
  },

  // Assumptions table
  assumptionBox: {
    borderWidth: 1,
    borderColor: BORDER,
    borderStyle: "solid",
    borderRadius: 6,
    overflow: "hidden",
  },
  assumptionHeaderRow: {
    flexDirection: "row",
    backgroundColor: SURFACE,
    paddingVertical: 5,
    paddingHorizontal: 10,
    borderBottomWidth: 1,
    borderBottomColor: BORDER,
    borderBottomStyle: "solid",
  },
  assumptionHeaderText: {
    fontFamily: "Helvetica-Bold",
    fontSize: 7,
    color: LIGHT,
    letterSpacing: 0.8,
    textTransform: "uppercase",
  },
  assumptionRow: {
    flexDirection: "row",
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderBottomWidth: 1,
    borderBottomColor: BORDER,
    borderBottomStyle: "solid",
    alignItems: "flex-start",
  },
  assumptionRowLast: {
    borderBottomWidth: 0,
  },
  colField: { flex: 2.5 },
  colValue: { flex: 1.5 },
  colSource: { flex: 3, paddingLeft: 10 },
  assumptionField: {
    fontFamily: "Helvetica-Bold",
    fontSize: 8,
    color: SLATE,
  },
  assumptionValue: {
    fontFamily: "Helvetica-Bold",
    fontSize: 8,
    color: SLATE,
    textAlign: "right",
  },
  assumptionSource: {
    fontSize: 7,
    color: LIGHT,
  },

  // Letter page
  letterPage: {
    backgroundColor: WHITE,
    paddingTop: 44,
    paddingBottom: 58,
    paddingHorizontal: 44,
    fontFamily: "Times-Roman",
    fontSize: 10,
    color: SLATE,
  },
  letterBox: {
    borderWidth: 1,
    borderColor: BORDER,
    borderStyle: "solid",
    borderRadius: 8,
    marginTop: 10,
  },
  letterHeadRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    backgroundColor: SURFACE2,
    paddingHorizontal: 18,
    paddingVertical: 11,
    borderBottomWidth: 1,
    borderBottomColor: BORDER,
    borderBottomStyle: "solid",
  },
  letterHeadBrand: {
    fontFamily: "Helvetica-Bold",
    fontSize: 12,
    color: SLATE,
  },
  letterHeadSubText: {
    fontFamily: "Helvetica",
    fontSize: 8,
    color: LIGHT,
    marginTop: 2,
  },
  letterHeadDate: {
    fontFamily: "Helvetica",
    fontSize: 8,
    color: LIGHT,
    textAlign: "right",
  },
  letterBody: {
    paddingHorizontal: 18,
    paddingTop: 16,
    paddingBottom: 18,
  },
  letterSalutation: {
    fontFamily: "Times-Roman",
    fontSize: 11,
    color: MUTED,
    marginBottom: 10,
  },
  letterPara: {
    fontFamily: "Times-Roman",
    fontSize: 10.5,
    color: "#334155",
    lineHeight: 1.7,
    marginBottom: 8,
  },
  letterSignoffWarm: {
    fontFamily: "Times-Roman",
    fontSize: 11,
    color: MUTED,
    marginTop: 12,
    marginBottom: 3,
  },
  letterSignature: {
    fontFamily: "Times-Italic",
    fontSize: 20,
    color: SLATE,
    marginBottom: 2,
  },
  letterAdvisor: {
    fontFamily: "Helvetica",
    fontSize: 9,
    color: SLATE,
    marginBottom: 2,
  },
  letterFootnote: {
    fontFamily: "Helvetica",
    fontSize: 8,
    color: LIGHT,
  },
});

// ── Sub-components ────────────────────────────────────────────────────────────

function PdfPageHeader({ date }: { date: string }) {
  return (
    <View style={s.pageHeader}>
      <View>
        <Text style={s.brandName}>Heimwende × Cloover</Text>
        <Text style={s.brandSub}>Home Energy Advisory</Text>
      </View>
      <Text style={s.headerDate}>Berlin · {date}</Text>
    </View>
  );
}

function PdfPageFooter({ page }: { page: string }) {
  return (
    <View style={s.pageFooter} fixed>
      <Text style={s.footerText}>Heimwende Energy Plan · Confidential</Text>
      <Text style={s.footerText}>{page}</Text>
    </View>
  );
}

function TierCardPdf({
  tier,
  scenario,
  financeMonths,
  isLast,
}: {
  tier: Tier;
  scenario: ScenarioResult;
  financeMonths: number;
  isLast: boolean;
}) {
  const isRec = tier.id === "high";
  const accent = TIER_ACCENT[tier.id] ?? ACCENT;
  const netSign = tier.monthly_saving_eur >= 0 ? "+" : "";

  return (
    <View style={[s.tierCard, ...(isLast ? [s.tierCardLast] : []), ...(isRec ? [s.tierCardRec] : [])]}>
      {isRec && <Text style={s.recBadge}>Recommended</Text>}
      <View style={s.tierDotRow}>
        <View style={[s.tierDot, { backgroundColor: accent }]} />
        <Text style={s.tierName}>{tier.name}</Text>
      </View>
      <Text style={s.tierLabelText}>{bundleLabel(tier.label)}</Text>

      {/* Main saving figure */}
      <View style={s.savingRow}>
        <Text style={s.savingAmount}>{eur(tier.saving_after_payoff_eur)}</Text>
        <Text style={s.savingUnit}>/mo</Text>
      </View>
      <Text style={s.savingMeta}>
        after payoff · from now{" "}
        {`${netSign}${eur(tier.monthly_saving_eur)}/mo`}
      </Text>

      {/* Energy buckets */}
      <View style={s.bucketsRow}>
        {[
          { label: "Electricity", value: scenario.breakdown.electricity_eur_month },
          { label: "Heating", value: scenario.breakdown.heating_eur_month },
          { label: "Mobility", value: scenario.breakdown.mobility_eur_month },
        ].map((b, i) => (
          <View key={b.label} style={[s.bucket, ...(i === 2 ? [s.bucketLast] : [])]}>
            <Text style={s.bucketLabel}>{b.label}</Text>
            <Text style={s.bucketValue}>{eur(b.value)}</Text>
          </View>
        ))}
      </View>

      {/* Rationale */}
      <View style={s.rationaleFlex}>
        <Text style={s.rationaleText}>{prose(tier.rationale_md)}</Text>
      </View>

      {/* Footer row */}
      <View style={s.tierFooter}>
        <Text style={s.tierFooterLabel}>after {monthsToYears(financeMonths)}</Text>
        <Text style={s.tierFooterValue}>{eur(tier.installment_eur_month, { sign: true })}/mo financing</Text>
      </View>
    </View>
  );
}

function EvidenceGridPdf({
  rec,
  evidence,
}: {
  rec: Recommendation;
  evidence: PdfEvidence;
}) {
  const items: { icon: string; label: string; value: string; note?: string; ok?: boolean }[] = [
    {
      icon: "$",
      label: "Baseline spend",
      value: `${eur(rec.current_monthly_spend_eur)}/mo today`,
    },
    ...(evidence.roof
      ? [{ icon: "R", label: "Roof analysis", value: evidence.roof, note: "Google Solar" }]
      : []),
    ...(evidence.permits
      ? [
          {
            icon: "✓",
            label: "Permit checks",
            value: evidence.permits.value,
            note: "Live German building rules",
            ok: evidence.permits.ok,
          },
        ]
      : []),
    {
      icon: "€",
      label: "Subsidies applied",
      value: evidence.subsidyValue,
      note: evidence.subsidySource,
    },
    {
      icon: "~",
      label: "Biggest driver",
      value: driverLabel(evidence.biggestDriver),
      note: "Largest swing in the confidence band",
    },
    {
      icon: "±",
      label: "Confidence range",
      value: `${eur(evidence.confidenceLow)} to ${eur(evidence.confidenceHigh)}/mo`,
      note: `± ${eur(evidence.confidenceBand)}/mo`,
    },
  ];

  return (
    <View style={s.evidenceGrid}>
      {items.map((item, i) => (
        <View key={item.label} style={[s.evidenceCard, ...(i % 2 === 0 ? [s.evidenceCardOdd] : [])]}>
          <View style={s.evidenceIconBox}>
            <Text style={s.evidenceIconChar}>{item.icon}</Text>
          </View>
          <View style={s.evidenceContent}>
            <Text style={s.evidenceLabel}>{item.label}</Text>
            <Text style={item.ok ? s.evidenceOk : s.evidenceValue}>{item.value}</Text>
            {item.note && <Text style={s.evidenceNote}>{item.note}</Text>}
          </View>
        </View>
      ))}
    </View>
  );
}

function AssumptionTablePdf({ assumptions }: { assumptions: Assumption[] }) {
  return (
    <View style={s.assumptionBox}>
      <View style={s.assumptionHeaderRow}>
        <View style={s.colField}>
          <Text style={s.assumptionHeaderText}>Assumption</Text>
        </View>
        <View style={s.colValue}>
          <Text style={[s.assumptionHeaderText, { textAlign: "right" }]}>Value</Text>
        </View>
        <View style={s.colSource}>
          <Text style={s.assumptionHeaderText}>Source</Text>
        </View>
      </View>
      {assumptions.map((a, i) => (
        <View
          key={a.field}
          style={[s.assumptionRow, ...(i === assumptions.length - 1 ? [s.assumptionRowLast] : [])]}
        >
          <View style={s.colField}>
            <Text style={s.assumptionField}>{assumptionLabel(a.field)}</Text>
          </View>
          <View style={s.colValue}>
            <Text style={s.assumptionValue}>{a.value}</Text>
          </View>
          <View style={s.colSource}>
            <Text style={s.assumptionSource}>{a.source}</Text>
          </View>
        </View>
      ))}
    </View>
  );
}

// ── Main document ─────────────────────────────────────────────────────────────

export function EnergyPlanPdf({
  rec,
  evidence,
}: {
  rec: Recommendation;
  evidence: PdfEvidence;
}) {
  const financeMonths = financeTermMonths(rec);
  const date = new Date().toLocaleDateString("en-GB", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
  const paras = letterParagraphs(rec);

  return (
    <Document
      title="Heimwende Energy Plan"
      author="Heimwende × Cloover"
      subject="Home energy upgrade recommendation"
    >
      {/* ── Page 1: Packages ─────────────────────────────── */}
      <Page size="A4" style={s.page}>
        <PdfPageHeader date={date} />

        <Text style={s.heroTitle}>Your Heimwende Energy Plan</Text>
        <Text style={s.heroSub}>
          Current spend {eur(rec.current_monthly_spend_eur)}/mo · upgrade roadmap prepared {date}
        </Text>

        <Text style={s.sectionKicker}>Choose your package</Text>
        <View style={s.tiersRow}>
          {rec.tiers.map((tier, i) => (
            <TierCardPdf
              key={tier.id}
              tier={tier}
              scenario={tierScenario(rec, tier)}
              financeMonths={financeMonths}
              isLast={i === rec.tiers.length - 1}
            />
          ))}
        </View>

        <PdfPageFooter page="1 / 3" />
      </Page>

      {/* ── Page 2: Evidence + Assumptions ───────────────── */}
      <Page size="A4" style={s.page}>
        <PdfPageHeader date={date} />

        <Text style={s.sectionKicker}>What we checked</Text>
        <EvidenceGridPdf rec={rec} evidence={evidence} />

        {rec.assumptions.length > 0 && (
          <>
            <Text style={s.sectionKicker}>Data &amp; assumptions</Text>
            <AssumptionTablePdf assumptions={rec.assumptions} />
          </>
        )}

        <PdfPageFooter page="2 / 3" />
      </Page>

      {/* ── Page 3: Advisor letter ────────────────────────── */}
      <Page size="A4" style={s.letterPage}>
        <PdfPageHeader date={date} />

        <Text style={[s.sectionKicker, { fontFamily: "Helvetica-Bold" }]}>
          Personal advisor recommendation letter
        </Text>

        <View style={s.letterBox}>
          <View style={s.letterHeadRow}>
            <View>
              <Text style={s.letterHeadBrand}>Heimwende × Cloover</Text>
              <Text style={s.letterHeadSubText}>Home Energy Advisory</Text>
            </View>
            <Text style={s.letterHeadDate}>Berlin · {date}</Text>
          </View>
          <View style={s.letterBody}>
            <Text style={s.letterSalutation}>Dear homeowner,</Text>
            {paras.map((p, i) => (
              <Text key={i} style={s.letterPara}>
                {p}
              </Text>
            ))}
            <Text style={s.letterSignoffWarm}>Warm regards,</Text>
            <Text style={s.letterSignature}>Heimwende</Text>
            <Text style={s.letterAdvisor}>Your Heimwende Advisor</Text>
            <Text style={s.letterFootnote}>Every figure is computed, not AI-invented.</Text>
          </View>
        </View>

        <PdfPageFooter page="3 / 3" />
      </Page>
    </Document>
  );
}
