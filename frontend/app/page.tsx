import Link from "next/link";

const PREVIEW_BARS: { day: string; value: number }[] = [
  { day: "M", value: 55 },
  { day: "T", value: 78 },
  { day: "W", value: 40 },
  { day: "T", value: 92 },
  { day: "F", value: 70 },
  { day: "S", value: 28 },
  { day: "S", value: 18 },
];

const FEATURES: { title: string; body: string }[] = [
  {
    title: "Plan your week",
    body: "Keep calendars, categories, and schedule items in one focused workspace.",
  },
  {
    title: "Catch conflicts",
    body: "Calia warns you when a time overlaps and lets you find replacement options.",
  },
  {
    title: "Understand your schedule balance",
    body: "See where your time is going with weekly load, categories, and Daily Rhythm.",
  },
];

export default function LandingPage() {
  return (
    <div className="landing">
      <section className="landing-hero">
        <div className="landing-hero-copy">
          <p className="landing-eyebrow">Calia</p>
          <h1 className="landing-title">A calmer way to plan your week.</h1>
          <p className="landing-subtitle">
            Organize events, catch scheduling conflicts, and understand how
            balanced your schedule feels before the week gets away from you.
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

        <div className="landing-preview" aria-hidden="true">
          <div className="preview-card">
            <div className="preview-card-header">
              <span className="preview-card-eyebrow">This week</span>
              <span className="preview-card-meta">Mon — Sun</span>
            </div>

            <div className="preview-card-section">
              <p className="preview-section-label">Daily load</p>
              <div className="preview-bars">
                {PREVIEW_BARS.map((bar, i) => (
                  <div className="preview-bar" key={i}>
                    <span className="preview-bar-day">{bar.day}</span>
                    <span className="preview-bar-track">
                      <span
                        className="preview-bar-fill"
                        style={{ width: `${bar.value}%` }}
                      />
                    </span>
                  </div>
                ))}
              </div>
            </div>

            <div className="preview-card-section">
              <p className="preview-section-label">Today</p>
              <ul className="preview-events">
                <li className="preview-event">
                  <span className="preview-event-time">9:00</span>
                  <span className="preview-event-title">Team standup</span>
                </li>
                <li className="preview-event">
                  <span className="preview-event-time">11:30</span>
                  <span className="preview-event-title">Design review</span>
                </li>
                <li className="preview-event preview-event-conflict">
                  <span className="preview-event-time">14:00</span>
                  <span className="preview-event-title">
                    Project deep work
                  </span>
                  <span className="preview-event-warn">Overlaps</span>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      <section className="landing-features" aria-label="What Calia helps with">
        {FEATURES.map((f) => (
          <article className="landing-feature" key={f.title}>
            <h3>{f.title}</h3>
            <p>{f.body}</p>
          </article>
        ))}
      </section>
    </div>
  );
}
