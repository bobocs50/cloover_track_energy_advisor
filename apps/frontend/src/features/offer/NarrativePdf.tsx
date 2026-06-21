import { Document, Page, Text, View, StyleSheet, pdf } from "@react-pdf/renderer";
import type { Recommendation, Tier } from "@/lib/types";
import type { ReportSection } from "@/lib/api";

// ── Helpers ───────────────────────────────────────────────────────────────────

function eur(n: number): string {
  const abs = Math.abs(n);
  const formatted = abs.toLocaleString("de-DE", { maximumFractionDigits: 0 });
  return `${n < 0 ? "-" : ""}€${formatted}`;
}

function monthsToYears(m: number): string {
  const y = m / 12;
  return Number.isInteger(y) ? `${y} yr` : `${y.toFixed(1)} yr`;
}

function bundleLabel(s: string): string {
  return s.replace(/[☀️🔋♨️🚗]/gu, "").trim();
}

// ── Palette ───────────────────────────────────────────────────────────────────

const ACCENT = "#2f6fed";
const SLATE = "#0f172a";
const MUTED = "#64748b";
const LIGHT = "#94a3b8";
const GREEN = "#047857";
const BORDER = "#e7eaf0";
const SURFACE = "#f6f8fc";
const WHITE = "#ffffff";
const ACCENT_SOFT = "#eef3fd";

// ── Styles ────────────────────────────────────────────────────────────────────

const s = StyleSheet.create({
  page: {
    backgroundColor: WHITE,
    paddingTop: 44,
    paddingBottom: 58,
    paddingHorizontal: 48,
    fontFamily: "Helvetica",
    fontSize: 10,
    color: SLATE,
  },

  // Header / footer
  pageHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: 20,
    paddingBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: BORDER,
    borderBottomStyle: "solid",
  },
  brandName: { fontFamily: "Helvetica-Bold", fontSize: 13, color: SLATE },
  brandSub: { fontSize: 8, color: LIGHT, marginTop: 2 },
  headerRight: { textAlign: "right" },
  headerDate: { fontSize: 9, color: MUTED, textAlign: "right" },
  headerAddr: { fontSize: 8, color: LIGHT, marginTop: 2, textAlign: "right" },
  pageFooter: {
    position: "absolute",
    bottom: 22,
    left: 48,
    right: 48,
    flexDirection: "row",
    justifyContent: "space-between",
    paddingTop: 7,
    borderTopWidth: 1,
    borderTopColor: BORDER,
    borderTopStyle: "solid",
  },
  footerText: { fontSize: 7, color: LIGHT },

  // Cover page
  coverBox: {
    borderWidth: 1,
    borderColor: BORDER,
    borderStyle: "solid",
    borderRadius: 10,
    overflow: "hidden",
    marginTop: 6,
    marginBottom: 18,
  },
  coverTop: {
    backgroundColor: ACCENT,
    paddingHorizontal: 24,
    paddingVertical: 20,
  },
  coverTitle: {
    fontFamily: "Helvetica-Bold",
    fontSize: 20,
    color: WHITE,
    marginBottom: 4,
  },
  coverSub: { fontSize: 10, color: "#c7d8fb" },
  coverBody: {
    paddingHorizontal: 24,
    paddingVertical: 18,
    backgroundColor: WHITE,
  },
  coverStatRow: { flexDirection: "row", marginBottom: 4 },
  coverStatBlock: { flex: 1, paddingRight: 10 },
  coverStatLabel: { fontSize: 7.5, color: LIGHT, marginBottom: 3, textTransform: "uppercase", letterSpacing: 0.6 },
  coverStatValue: { fontFamily: "Helvetica-Bold", fontSize: 20, color: GREEN },
  coverStatUnit: { fontSize: 9, color: MUTED, marginTop: 2 },
  coverDivider: { width: 1, backgroundColor: BORDER, marginHorizontal: 8 },
  coverNote: { fontSize: 8, color: LIGHT, marginTop: 10 },

  // Narrative sections
  sectionContainer: { marginBottom: 16 },
  sectionHeading: {
    fontFamily: "Helvetica-Bold",
    fontSize: 11,
    color: SLATE,
    marginBottom: 5,
    paddingBottom: 4,
    borderBottomWidth: 1,
    borderBottomColor: BORDER,
    borderBottomStyle: "solid",
  },
  sectionBody: {
    fontFamily: "Times-Roman",
    fontSize: 10,
    color: "#334155",
    lineHeight: 1.7,
  },

  // Tier comparison table
  tableLabel: {
    fontFamily: "Helvetica-Bold",
    fontSize: 7.5,
    color: LIGHT,
    letterSpacing: 1,
    textTransform: "uppercase",
    marginBottom: 8,
    marginTop: 14,
  },
  tableBox: {
    borderWidth: 1,
    borderColor: BORDER,
    borderStyle: "solid",
    borderRadius: 6,
    overflow: "hidden",
  },
  tableHeaderRow: {
    flexDirection: "row",
    backgroundColor: SURFACE,
    paddingVertical: 5,
    paddingHorizontal: 10,
    borderBottomWidth: 1,
    borderBottomColor: BORDER,
    borderBottomStyle: "solid",
  },
  tableHeaderCell: {
    fontFamily: "Helvetica-Bold",
    fontSize: 7.5,
    color: LIGHT,
    letterSpacing: 0.6,
    textTransform: "uppercase",
  },
  tableRow: {
    flexDirection: "row",
    paddingVertical: 7,
    paddingHorizontal: 10,
    borderBottomWidth: 1,
    borderBottomColor: BORDER,
    borderBottomStyle: "solid",
    alignItems: "center",
  },
  tableRowLast: { borderBottomWidth: 0 },
  tableRowRec: { backgroundColor: ACCENT_SOFT },
  colName: { flex: 2 },
  colNum: { flex: 1.5 },
  cellName: { fontFamily: "Helvetica-Bold", fontSize: 8.5, color: SLATE },
  cellSub: { fontSize: 7, color: LIGHT, marginTop: 1 },
  cellNum: { fontSize: 8.5, color: SLATE, textAlign: "right" },
  cellNumGreen: { fontFamily: "Helvetica-Bold", fontSize: 8.5, color: GREEN, textAlign: "right" },
  recPill: {
    fontFamily: "Helvetica-Bold",
    fontSize: 6,
    color: WHITE,
    backgroundColor: ACCENT,
    borderRadius: 8,
    paddingHorizontal: 5,
    paddingVertical: 2,
    alignSelf: "flex-start",
    marginTop: 2,
    letterSpacing: 0.3,
  },
});

// ── Sub-components ────────────────────────────────────────────────────────────

function PdfHeader({ date, address }: { date: string; address?: string }) {
  return (
    <View style={s.pageHeader}>
      <View>
        <Text style={s.brandName}>Heimwende × Cloover</Text>
        <Text style={s.brandSub}>Home Energy Advisory Report</Text>
      </View>
      <View style={s.headerRight}>
        <Text style={s.headerDate}>Berlin · {date}</Text>
        {address && <Text style={s.headerAddr}>{address}</Text>}
      </View>
    </View>
  );
}

function PdfFooter({ label }: { label: string }) {
  return (
    <View style={s.pageFooter} fixed>
      <Text style={s.footerText}>Heimwende Energy Advisory Report · Confidential</Text>
      <Text style={s.footerText}>{label}</Text>
    </View>
  );
}

function CoverPage({ rec, date, address }: { rec: Recommendation; date: string; address?: string }) {
  const saving = rec.best.monthly_saving_eur;
  const afterPayoff = rec.best.saving_after_payoff_eur;
  const current = rec.current_monthly_spend_eur;
  const breakEven = rec.best.break_even_month;

  return (
    <Page size="A4" style={s.page}>
      <PdfHeader date={date} address={address} />

      <View style={s.coverBox}>
        <View style={s.coverTop}>
          <Text style={s.coverTitle}>Your Heimwende Energy Plan</Text>
          <Text style={s.coverSub}>
            Personalised home-energy upgrade report · prepared {date}
          </Text>
        </View>

        <View style={s.coverBody}>
          <View style={s.coverStatRow}>
            <View style={s.coverStatBlock}>
              <Text style={s.coverStatLabel}>Save from day one</Text>
              <Text style={s.coverStatValue}>{eur(saving)}</Text>
              <Text style={s.coverStatUnit}>per month (net of installment)</Text>
            </View>
            <View style={s.coverDivider} />
            <View style={s.coverStatBlock}>
              <Text style={s.coverStatLabel}>Save after payoff</Text>
              <Text style={s.coverStatValue}>{eur(afterPayoff)}</Text>
              <Text style={s.coverStatUnit}>per month · permanently</Text>
            </View>
            <View style={s.coverDivider} />
            <View style={s.coverStatBlock}>
              <Text style={s.coverStatLabel}>Current spend</Text>
              <Text style={[s.coverStatValue, { color: MUTED }]}>{eur(current)}</Text>
              <Text style={s.coverStatUnit}>per month today</Text>
            </View>
            <View style={s.coverDivider} />
            <View style={[s.coverStatBlock, { paddingRight: 0 }]}>
              <Text style={s.coverStatLabel}>Break-even</Text>
              <Text style={[s.coverStatValue, { color: SLATE, fontSize: 16 }]}>
                {monthsToYears(breakEven)}
              </Text>
              <Text style={s.coverStatUnit}>month {breakEven}</Text>
            </View>
          </View>
          <Text style={s.coverNote}>
            Every figure is computed by the Heimwende savings engine — not AI-invented.
            The LLM prose describes the numbers; the numbers are authoritative.
          </Text>
        </View>
      </View>

      <PdfFooter label="Cover" />
    </Page>
  );
}

function TierTable({ tiers, rec }: { tiers: Recommendation["tiers"]; rec: Recommendation }) {
  const finMonths = (() => {
    const a = rec.assumptions.find((x) => x.field === "financing_term_months");
    const m = a?.value.match(/\d+/)?.[0];
    return m ? Number(m) : 180;
  })();

  return (
    <>
      <Text style={s.tableLabel}>Package comparison</Text>
      <View style={s.tableBox}>
        <View style={s.tableHeaderRow}>
          <View style={s.colName}><Text style={s.tableHeaderCell}>Package</Text></View>
          <View style={s.colNum}><Text style={[s.tableHeaderCell, { textAlign: "right" }]}>Now /mo</Text></View>
          <View style={s.colNum}><Text style={[s.tableHeaderCell, { textAlign: "right" }]}>After payoff</Text></View>
          <View style={s.colNum}><Text style={[s.tableHeaderCell, { textAlign: "right" }]}>Financing</Text></View>
          <View style={s.colNum}><Text style={[s.tableHeaderCell, { textAlign: "right" }]}>Net invest.</Text></View>
        </View>
        {tiers.map((t: Tier, i: number) => {
          const isRec = t.id === "high";
          const isLast = i === tiers.length - 1;
          return (
            <View
              key={t.id}
              style={[s.tableRow, isLast ? s.tableRowLast : {}, isRec ? s.tableRowRec : {}]}
            >
              <View style={s.colName}>
                <Text style={s.cellName}>{bundleLabel(t.label)}</Text>
                {isRec && <Text style={s.recPill}>Recommended</Text>}
                <Text style={s.cellSub}>after {monthsToYears(finMonths)}</Text>
              </View>
              <View style={s.colNum}>
                <Text style={isRec ? s.cellNumGreen : s.cellNum}>{eur(t.monthly_saving_eur)}/mo</Text>
              </View>
              <View style={s.colNum}>
                <Text style={s.cellNum}>{eur(t.saving_after_payoff_eur)}/mo</Text>
              </View>
              <View style={s.colNum}>
                <Text style={s.cellNum}>{eur(t.installment_eur_month)}/mo</Text>
              </View>
              <View style={s.colNum}>
                <Text style={s.cellNum}>{eur(t.capex_after_subsidy_eur)}</Text>
              </View>
            </View>
          );
        })}
      </View>
    </>
  );
}

// ── Main document ─────────────────────────────────────────────────────────────

export function NarrativePdf({
  rec,
  sections,
  address,
}: {
  rec: Recommendation;
  sections: ReportSection[];
  address?: string;
}) {
  const date = new Date().toLocaleDateString("en-GB", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  // Split sections: first 3 on page 2, last 3 + table on page 3.
  // When sections is empty (backend unreachable) skip the narrative pages entirely.
  const firstHalf = sections.slice(0, 3);
  const secondHalf = sections.slice(3);

  return (
    <Document
      title="Heimwende Energy Advisory Report"
      author="Heimwende × Cloover"
      subject="Home energy upgrade recommendation"
    >
      {/* Page 1: Cover */}
      <CoverPage rec={rec} date={date} address={address} />

      {/* Pages 2 & 3: Narrative sections (only when sections were returned) */}
      {sections.length > 0 && (
        <Page size="A4" style={s.page}>
          <PdfHeader date={date} address={address} />
          {firstHalf.map((sec) => (
            <View key={sec.heading} style={s.sectionContainer}>
              <Text style={s.sectionHeading}>{sec.heading}</Text>
              <Text style={s.sectionBody}>{sec.body}</Text>
            </View>
          ))}
          <PdfFooter label="2 / 3" />
        </Page>
      )}

      {/* Page 3 (or 2 in offline mode): Remaining sections + tier table */}
      <Page size="A4" style={s.page}>
        <PdfHeader date={date} address={address} />
        {secondHalf.map((sec) => (
          <View key={sec.heading} style={s.sectionContainer}>
            <Text style={s.sectionHeading}>{sec.heading}</Text>
            <Text style={s.sectionBody}>{sec.body}</Text>
          </View>
        ))}
        <TierTable tiers={rec.tiers} rec={rec} />
        <PdfFooter label={sections.length > 0 ? "3 / 3" : "2 / 2"} />
      </Page>
    </Document>
  );
}

// ── Blob helper (called by OfferResultPage) ───────────────────────────────────

export async function generatePdfBlob(
  rec: Recommendation,
  sections: ReportSection[],
  address?: string,
): Promise<Blob> {
  return pdf(
    <NarrativePdf rec={rec} sections={sections} address={address} />,
  ).toBlob();
}
