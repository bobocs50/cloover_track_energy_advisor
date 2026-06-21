import { useState } from "react";
import { ArrowRight, Check, MapPinned } from "lucide-react";
import HeimwendeMark from "@/components/HeimwendeMark";

interface LandingPageProps {
  onStart: () => void;
}

export default function LandingPage({ onStart }: LandingPageProps) {
  const [exiting, setExiting] = useState(false);

  function handleStart() {
    if (exiting) return;
    setExiting(true);
    setTimeout(onStart, 480);
  }

  return (
    <div className={`landing-root${exiting ? " landing-root--exiting" : ""}`}>
      <div className="landing-progress" aria-hidden="true" />
      <nav className="landing-nav">
        <div className="landing-brand">
          <HeimwendeMark />
          <span className="landing-brand-name">Heimwende</span>
        </div>
      </nav>

      <main className="landing-main">
        <section className="landing-hero" aria-labelledby="landing-title">
          <div className="landing-copy">
            <h1 className="landing-headline" id="landing-title">
              Your home energy plan, ready in minutes.
            </h1>
            <p className="landing-sub">
              Solar, heating, subsidies, and financing in one guided flow.
            </p>
            <div className="landing-actions">
              <button className="landing-cta" onClick={handleStart} type="button">
                Start Heimwende
                <ArrowRight size={18} strokeWidth={2.4} aria-hidden="true" />
              </button>
            </div>

            <dl className="landing-metrics" aria-label="Planning highlights">
              <div>
                <dt>4 stages</dt>
                <dd>Solar to mobility</dd>
              </div>
              <div>
                <dt>1 min</dt>
                <dd>First proposal</dd>
              </div>
              <div>
                <dt>1 plan</dt>
                <dd>Clear next step</dd>
              </div>
            </dl>
          </div>

          <div className="landing-media" aria-label="Energy plan preview">
            <div className="landing-image-frame">
              <img
                src="/pic.avif"
                alt="House with solar panels, an electric car, and homeowners outside"
                className="landing-img"
                draggable={false}
              />
              <div className="landing-image-shade" aria-hidden="true" />
            </div>

            <div className="landing-floating-card landing-floating-card--top">
              <div className="landing-card-icon">
                <MapPinned size={18} strokeWidth={2.3} aria-hidden="true" />
              </div>
              <div>
                <span>Roof scan</span>
                <strong>8.6 kWp potential</strong>
              </div>
            </div>

            <div className="landing-caption">
              <Check size={16} strokeWidth={2.4} aria-hidden="true" />
              Subsidy, permit, and payback checks included
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
