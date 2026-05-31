import Link from "next/link";

export default function LandingPage() {
  return (
    <div className="landing">
      <section className="landing-hero">
        <div className="landing-hero-copy">
          <p className="landing-eyebrow">Calia</p>
          <h1 className="landing-title">
            Pre-deployment landing page placeholder
          </h1>
          <p className="landing-subtitle">
            Calia&apos;s public landing page layout has not been finalized yet.
            This temporary page exists so the app has a safe root route while
            the dashboard, schedule, and settings flows continue to be refined.
          </p>
          <div className="landing-cta-row">
            <Link href="/signup" className="landing-cta-primary">
              Create account
            </Link>
            <Link href="/login" className="landing-cta-secondary">
              Log in
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
