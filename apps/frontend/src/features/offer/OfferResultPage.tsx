import {
  ArrowLeft,
  BatteryCharging,
  ChevronRight,
  Database,
  Download,
  FileText,
  Flame,
  Globe2,
  PlugZap,
  ShieldCheck,
  Sun,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { Recommendation, ScenarioResult, Tier } from "@/lib/types";

function eur(n: number, opts?: { sign?: boolean; compact?: boolean }) {
  const abs = Math.abs(n);
  const formatted = abs.toLocaleString("de-DE", {
    maximumFractionDigits: 0,
    notation: opts?.compact ? "compact" : "standard",
  });
  if (opts?.sign) return `${n >= 0 ? "+" : "-"}€${formatted}`;
  return `${n < 0 ? "-" : ""}€${formatted}`;
}

function clean(value: string) {
  return value.replace(/\*\*/g, "").replace(/[\u2013\u2014]/g, "-").replace(/\n+/g, " ").trim();
}

function bundleLabel(value: string) {
  return value.replace(/[☀️🔋♨️🚗]/gu, "").trim();
}

function financeTermMonths(rec: Recommendation) {
  const assumption = rec.assumptions.find((a) => a.field === "financing_term_months");
  const parsed = assumption?.value.match(/\d+/)?.[0];
  return parsed ? Number(parsed) : 180;
}

function monthsToYears(months: number) {
  const years = months / 12;
  return Number.isInteger(years) ? `${years} years` : `${years.toFixed(1)} years`;
}

function tierScenario(rec: Recommendation, tier: Tier) {
  return (
    rec.alternatives.find((alt) => alt.scenario_id === tier.scenario_id) ??
    rec.alternatives.find((alt) => alt.scenario_id === rec.best.scenario_id) ??
    rec.best
  );
}

function tierIcon(id: Tier["id"]) {
  if (id === "low") return Sun;
  if (id === "middle") return Flame;
  return BatteryCharging;
}

function bucketRows(scenario: ScenarioResult) {
  return [
    { label: "Electricity", value: scenario.breakdown.electricity_eur_month, icon: Sun },
    { label: "Heating", value: scenario.breakdown.heating_eur_month, icon: Flame },
    { label: "Mobility", value: scenario.breakdown.mobility_eur_month, icon: PlugZap },
  ];
}

export default function OfferResultPage({
  rec,
  onBack,
}: {
  rec: Recommendation;
  onBack: () => void;
}) {
  const best = rec.best;
  const financeMonths = financeTermMonths(rec);

  return (
    <main className="min-h-[100dvh] bg-[#f3f5f8] text-[#111827]">
      <header className="sticky top-0 z-20 border-b border-[#e5e7eb] bg-white/92 backdrop-blur-xl">
        <div className="mx-auto flex h-14 max-w-[960px] items-center px-4">
          <button
            type="button"
            onClick={onBack}
            className="inline-flex h-9 items-center gap-2 rounded-lg px-2 text-[13px] font-bold text-[#667085] transition-[background-color,transform,color] duration-150 hover:bg-[#f3f5f8] hover:text-[#111827] active:scale-[0.98]"
          >
            <ArrowLeft size={15} strokeWidth={2.2} />
            Back to model
          </button>
        </div>
      </header>

      <div className="mx-auto max-w-[960px] space-y-4 px-4 py-5 sm:py-7">
        <section className="rounded-lg border border-[#d8dee8] bg-white shadow-[0_14px_32px_rgb(20_31_48/0.06)]">
          <div className="grid gap-0 md:grid-cols-[1fr_280px]">
            <div className="border-l-[3px] border-[#2f6fed] p-6">
              <div className="flex flex-wrap items-center gap-3">
                <h1 className="text-[30px] font-black tracking-[-0.035em] text-[#111827]">
                  {bundleLabel(best.label)}
                </h1>
                <span className="rounded-full bg-[#2f6fed] px-3 py-1 text-[12px] font-black text-white">
                  {eur(best.monthly_saving_eur, { sign: true })}/mo
                </span>
              </div>
              <p className="mt-2 text-[16px] font-bold text-[#667085]">
                Best financed outcome for this home.
              </p>
              <p className="mt-5 max-w-[640px] text-[15px] font-semibold leading-7 text-[#4b5563]">
                {clean(rec.explanation_md)}
              </p>
            </div>

            <div className="border-t border-[#e5e7eb] p-5 md:border-l md:border-t-0">
              <div className="rounded-lg bg-[#09264a] p-4 text-white">
                <p className="border-b border-white/18 pb-2 text-[16px] font-black">
                  Offer summary
                </p>
                <SummaryRow label="Monthly net" value={`${eur(best.monthly_saving_eur, { sign: true })}/mo`} />
                <SummaryRow label="Installment" value={`${eur(best.installment_eur_month)}/mo`} />
                <SummaryRow label="After payoff" value={`${eur(best.saving_after_payoff_eur)}/mo`} />
                <SummaryRow label="Term" value={monthsToYears(financeMonths)} />
              </div>
            </div>
          </div>
        </section>

        <Section title="Data checked">
          <div className="grid gap-3 md:grid-cols-2">
            <Evidence icon={Database} label="Database" value={`${eur(rec.current_monthly_spend_eur)}/mo baseline spend`} />
            <Evidence icon={Globe2} label="Internet" value={best.confidence.biggest_driver} />
            <Evidence icon={FileText} label="Subsidy PDF" value={best.capex.subsidy_note} />
            <Evidence icon={ShieldCheck} label="Confidence" value={`${eur(best.confidence.low_eur)} to ${eur(best.confidence.high_eur)}/mo`} />
          </div>
        </Section>

        <Section title="Choose an offer">
          <div className="grid gap-3 lg:grid-cols-3">
            {rec.tiers.map((tier) => (
              <TierCard
                key={tier.id}
                tier={tier}
                scenario={tierScenario(rec, tier)}
                financeMonths={financeMonths}
              />
            ))}
          </div>
        </Section>

        <Section title="AI recommendation letter">
          <div className="rounded-lg border border-[#e5e7eb] bg-[#f8fafc] p-5">
            <div className="grid gap-2 border-b border-[#e5e7eb] pb-4 text-[13px] sm:grid-cols-[82px_1fr]">
              <p className="font-black text-[#8a95a3]">From</p>
              <p className="font-bold text-[#111827]">Heimwende AI Advisor</p>
              <p className="font-black text-[#8a95a3]">Subject</p>
              <p className="font-bold text-[#111827]">{bundleLabel(best.label)}</p>
            </div>
            <div className="mt-5 space-y-4 text-[15px] font-semibold leading-7 text-[#4b5563]">
              <p>{clean(rec.explanation_md)}</p>
              <p>{clean(rec.upsell.reason_md)}</p>
              <p>{clean(rec.proposal_copy_md)}</p>
            </div>
          </div>
        </Section>

        <section className="rounded-lg border border-[#d8dee8] bg-[#0b1220] p-5 text-white">
          <div className="grid gap-4 md:grid-cols-[1fr_auto_auto] md:items-center">
            <div>
              <p className="text-[17px] font-black">Ready to continue</p>
              <p className="mt-1 text-[13px] font-semibold text-white/62">
                Use the recommended package or export the customer packet.
              </p>
            </div>
            <button
              type="button"
              className="inline-flex h-11 items-center justify-center gap-2 rounded-lg bg-[#d9f99d] px-5 text-[13px] font-black text-[#18200d] transition-[background-color,transform] duration-150 hover:bg-[#c8ef84] active:scale-[0.98]"
            >
              Continue offer
              <ChevronRight size={16} strokeWidth={2.3} />
            </button>
            <button
              type="button"
              onClick={() => window.print()}
              className="inline-flex h-11 items-center justify-center gap-2 rounded-lg border border-white/14 bg-white/8 px-5 text-[13px] font-black text-white transition-[background-color,transform] duration-150 hover:bg-white/12 active:scale-[0.98]"
            >
              <Download size={16} strokeWidth={2.2} />
              Download PDF
            </button>
          </div>
        </section>
      </div>
    </main>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-[#e5e7eb] bg-white shadow-[0_10px_28px_rgb(20_31_48/0.04)]">
      <div className="border-b border-[#e5e7eb] px-5 py-3.5">
        <h2 className="text-[15px] font-black text-[#111827]">{title}</h2>
      </div>
      <div className="p-5">{children}</div>
    </section>
  );
}

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between border-b border-white/10 py-2.5 last:border-b-0">
      <p className="text-[12px] font-bold text-white/58">{label}</p>
      <p className="font-mono text-[13px] font-black text-white">{value}</p>
    </div>
  );
}

function Evidence({ icon: Icon, label, value }: { icon: LucideIcon; label: string; value: string }) {
  return (
    <div className="flex gap-3 rounded-lg border border-[#e5e7eb] bg-white p-4">
      <div className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-[#eef3fd] text-[#2f6fed]">
        <Icon size={17} strokeWidth={2.2} />
      </div>
      <div>
        <p className="text-[13px] font-black text-[#111827]">{label}</p>
        <p className="mt-1 text-[13px] font-semibold leading-5 text-[#667085]">{clean(value)}</p>
      </div>
    </div>
  );
}

function TierCard({
  tier,
  scenario,
  financeMonths,
}: {
  tier: Tier;
  scenario: ScenarioResult;
  financeMonths: number;
}) {
  const Icon = tierIcon(tier.id);
  const recommended = tier.id === "high";

  return (
    <article
      className={`rounded-lg border p-4 ${
        recommended ? "border-[#2f6fed] bg-[#f7faff]" : "border-[#e5e7eb] bg-white"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="grid h-9 w-9 place-items-center rounded-lg bg-[#eef3fd] text-[#2f6fed]">
            <Icon size={18} strokeWidth={2.2} />
          </div>
          <div>
            <p className="text-[12px] font-black text-[#667085]">{tier.name}</p>
            <h3 className="mt-0.5 text-[16px] font-black leading-tight text-[#111827]">
              {bundleLabel(tier.label)}
            </h3>
          </div>
        </div>
        {recommended && (
          <span className="rounded-full bg-[#2f6fed] px-2.5 py-1 text-[11px] font-black text-white">
            Best
          </span>
        )}
      </div>

      <div className="mt-4 rounded-lg bg-[#f8fafc] p-3">
        <p
          className={`font-mono text-[28px] font-black tracking-[-0.04em] ${
            tier.monthly_saving_eur >= 0 ? "text-[#08744a]" : "text-[#a15c07]"
          }`}
        >
          {eur(tier.monthly_saving_eur, { sign: true })}/mo
        </p>
        <p className="mt-1 text-[12px] font-bold text-[#667085]">
          after {eur(tier.installment_eur_month)}/mo financing
        </p>
      </div>

      <div className="mt-4 grid grid-cols-3 gap-2">
        {bucketRows(scenario).map((bucket) => {
          const BucketIcon = bucket.icon;
          return (
            <div key={bucket.label} className="rounded-lg border border-[#e5e7eb] bg-white p-2.5">
              <BucketIcon size={14} strokeWidth={2.2} className="text-[#2f6fed]" />
              <p className="mt-2 text-[11px] font-bold text-[#8a95a3]">{bucket.label}</p>
              <p className="font-mono text-[12px] font-black text-[#111827]">{eur(bucket.value)}</p>
            </div>
          );
        })}
      </div>

      <p className="mt-4 text-[13px] font-semibold leading-6 text-[#667085]">
        {clean(tier.rationale_md)}
      </p>

      <div className="mt-4 flex items-center justify-between border-t border-[#e5e7eb] pt-3">
        <p className="text-[12px] font-bold text-[#8a95a3]">{monthsToYears(financeMonths)}</p>
        <p className="font-mono text-[12px] font-black text-[#111827]">
          {eur(tier.saving_after_payoff_eur)}/mo after payoff
        </p>
      </div>
    </article>
  );
}
