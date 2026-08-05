import { Card } from "@/components/ui";

export default function Placeholder({ title }: { title: string }) {
  return (
    <>
      <div className="page-head">
        <div>
          <h1>{title}</h1>
          <p>This section is being rebuilt in the new console.</p>
        </div>
      </div>
      <Card>
        <div className="card-pad">
          <div style={{ padding: "36px 8px", textAlign: "center", color: "var(--ink-3)" }}>
            <p style={{ fontWeight: 600, color: "var(--ink-2)", marginBottom: 6 }}>Coming next</p>
            <p style={{ maxWidth: 460, margin: "0 auto", fontSize: 13.5 }}>
              The <b>{title}</b> workspace will land here — wired to the same live API the current
              console uses. The Overview is the first section built out; the rest follow in passes.
            </p>
          </div>
        </div>
      </Card>
    </>
  );
}
