"use client";

import React from "react";
import type { AnalysisEnvelope, FieldPlan, Strategy } from "@/lib/schemas";

// High-contrast light-mode @media print 1-page brief
export function PrintableBrief({
  envelope,
  fieldPlan,
  strategy,
}: {
  envelope: AnalysisEnvelope;
  fieldPlan: FieldPlan;
  strategy?: Strategy;
}) {
  if (!strategy) return null;

  return (
    <article
      data-testid="printable-brief"
      className="print-only-brief rounded-xl border-2 border-[#00291B] bg-white p-6 text-[#111827]"
    >
      <header className="border-b-2 border-[#137135] pb-3">
        <div className="flex items-baseline justify-between">
          <h1 className="text-xl font-extrabold text-[#00291B]">
            FIELD SHIFT — 1-Page Field Rotation Brief
          </h1>
          <span className="text-xs font-bold text-[#137135]">
            {envelope.analysis_id} · {envelope.dataset_version}
          </span>
        </div>
        <p className="mt-1 text-xs text-[#374151]">
          Parcel: <strong>{fieldPlan.field_name}</strong> ({fieldPlan.field_id}) · ML Engine:{" "}
          {envelope.result.ml_engine_version}
        </p>
      </header>

      <section className="mt-4">
        <h2 className="text-sm font-bold text-[#137135]">
          Selected / Recommended Strategy: {strategy.name}
        </h2>
        <p className="mt-1 text-xs text-[#374151]">{strategy.description}</p>
        <div className="mt-2 grid grid-cols-4 gap-2 text-xs">
          <div className="rounded border border-gray-200 bg-gray-50 p-2">
            Priority Fit: <strong className="text-[#00291B]">{strategy.scores.priority_fit}/100</strong>
          </div>
          <div className="rounded border border-gray-200 bg-gray-50 p-2">
            Water Efficiency: <strong className="text-[#00291B]">{strategy.scores.water_efficiency}/100</strong>
          </div>
          <div className="rounded border border-gray-200 bg-gray-50 p-2">
            Nitrogen Gain: <strong className="text-[#00291B]">{strategy.scores.nitrogen_contribution}/100</strong>
          </div>
          <div className="rounded border border-gray-200 bg-gray-50 p-2">
            Bare Field Days: <strong className="text-[#00291B]">{strategy.scores.bare_field_days_per_year} d/yr</strong>
          </div>
        </div>
      </section>

      <section className="mt-4">
        <h3 className="text-xs font-bold uppercase text-[#137135]">Season Sequence</h3>
        <table className="mt-1 w-full border-collapse text-xs">
          <thead>
            <tr className="border-b border-[#00291B] text-start">
              <th className="py-1">#</th>
              <th className="py-1">Season / Year</th>
              <th className="py-1">Crop</th>
              <th className="py-1">Role</th>
            </tr>
          </thead>
          <tbody>
            {strategy.seasons.map((s) => (
              <tr key={s.order} className="border-b border-gray-300">
                <td className="py-1">{s.order}</td>
                <td className="py-1">
                  {s.season} {s.year} (M{s.planting_month ?? "—"})
                </td>
                <td className="py-1 font-bold text-[#00291B]">{s.crop_name}</td>
                <td className="py-1 text-[#374151]">{s.role}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="mt-4 grid grid-cols-2 gap-4 text-xs">
        <div>
          <h3 className="font-bold text-[#137135]">Key Risks & Mitigations</h3>
          <ul className="mt-1 list-disc space-y-1 ps-4 text-[#374151]">
            {strategy.explanation.risks.map((r) => (
              <li key={r.risk_id}>
                <strong>{r.title}</strong> ({r.severity}): {r.mitigation}
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h3 className="font-bold text-[#137135]">Evidence Citations</h3>
          <ul className="mt-1 list-disc space-y-1 ps-4 text-[#374151]">
            {strategy.explanation.evidence.map((ev, i) => (
              <li key={i}>
                [{ev.data_source}] {ev.parameter}: {String(ev.observed_value)} {ev.unit ?? ""}
              </li>
            ))}
          </ul>
        </div>
      </section>

      <footer className="mt-4 border-t border-gray-300 pt-2 text-[10px] text-[#6B7280]">
        <strong>Disclaimer:</strong> {envelope.result.disclaimer}
      </footer>
    </article>
  );
}
