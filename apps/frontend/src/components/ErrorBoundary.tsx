// App-level error boundary. IntakeScreen has no boundary above it, so any
// transient render throw (a bad payload, an HMR-broken module, a Three.js hiccup)
// would otherwise white-screen the whole flow. This catches it, logs it, and
// shows a recoverable fallback instead.
import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  /** Optional label so logs say which subtree failed. */
  label?: string;
}

interface State {
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Surface the *real* error (the boundary notice in the console only names
    // the component, not the throw) so it's debuggable.
    console.error(`[ErrorBoundary${this.props.label ? ` · ${this.props.label}` : ""}]`, error, info.componentStack);
  }

  private reset = () => this.setState({ error: null });

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;

    return (
      <div
        role="alert"
        className="fixed inset-0 z-[999] flex items-center justify-center bg-[#eef1f5] p-6"
      >
        <div className="max-w-md rounded-2xl border border-[var(--border)] bg-white p-6 text-center shadow-[var(--shadow-md)]">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--text-3)]">
            Something broke
          </p>
          <h2 className="mt-1.5 text-[18px] font-bold text-[var(--text-1)]">
            The live view hit an error
          </h2>
          <p className="mt-2 text-[13px] leading-relaxed text-[var(--text-2)]">
            The pipeline and 3D model recovered safely — nothing was lost. You can retry
            without reloading the page.
          </p>
          {import.meta.env.DEV && (
            <pre className="mt-3 max-h-40 overflow-auto rounded-lg bg-[#f6f7f9] p-3 text-left text-[11px] leading-relaxed text-[#b91c1c]">
              {error.message}
            </pre>
          )}
          <button
            type="button"
            onClick={this.reset}
            className="mt-4 inline-flex h-10 items-center justify-center rounded-xl bg-[var(--accent)] px-5 text-[13px] font-semibold text-white transition-[transform,filter] duration-150 hover:brightness-95 active:scale-[0.97]"
          >
            Try again
          </button>
        </div>
      </div>
    );
  }
}
