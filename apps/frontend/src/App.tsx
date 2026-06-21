import { useState } from "react";
import LandingPage from "@/features/landing/LandingPage";
import IntakeScreen from "@/features/intake/IntakeScreen";
import ErrorBoundary from "@/components/ErrorBoundary";

export default function App() {
  const [showLanding, setShowLanding] = useState(true);

  return (
    <ErrorBoundary label="IntakeScreen">
      <IntakeScreen />
      {showLanding && <LandingPage onStart={() => setShowLanding(false)} />}
    </ErrorBoundary>
  );
}
