// Field Shift Phase L — Mobile-friendly interactive client (zero technical farmer inputs)

const PRESETS = {
  belkheir: {
    fieldId: "FLD_BELKHEIR_PILOT",
    fieldName: "Belkheir / Boumahra Alluvial Parcel",
    coords: [[[7.48, 36.47], [7.486, 36.47], [7.486, 36.474], [7.48, 36.474], [7.48, 36.47]]],
    water: { availability: "limited", source: "rainfed", irrigation_system: "none" },
  },
  tamlouka: {
    fieldId: "FLD_TAMLOUKA_PILOT",
    fieldName: "Tamlouka Semi-Arid Southern Parcel",
    coords: [[[7.137, 36.128], [7.143, 36.128], [7.143, 36.132], [7.137, 36.132], [7.137, 36.128]]],
    water: { availability: "limited", source: "rainfed", irrigation_system: "none" },
  },
  periurban: {
    fieldId: "FLD_PERIURBAN_CHECK",
    fieldName: "Guelma South-East Peri-Urban Boundary Check",
    coords: [[[7.435, 36.443], [7.441, 36.443], [7.441, 36.447], [7.435, 36.447], [7.435, 36.443]]],
    water: { availability: "limited", source: "rainfed", irrigation_system: "none" },
  },
};

let wilayaGeo = null;
let bounds = { minLon: 7.0, maxLon: 7.85, minLat: 36.02, maxLat: 36.68 };
let drawnVertices = [...PRESETS.belkheir.coords[0].slice(0, -1)];

const el = (id) => document.getElementById(id);

function setPolygonTextFromVertices() {
  if (drawnVertices.length < 3) {
    el("polygonJson").value = "";
    return;
  }
  const ring = [...drawnVertices, drawnVertices[0]].map(([x, y]) => [Number(x.toFixed(6)), Number(y.toFixed(6))]);
  el("polygonJson").value = JSON.stringify({ type: "Polygon", coordinates: [ring] });
}

function projectLonLatToCanvas(lon, lat, w, h) {
  const pad = 16;
  const x = pad + ((lon - bounds.minLon) / (bounds.maxLon - bounds.minLon)) * (w - 2 * pad);
  const y = h - pad - ((lat - bounds.minLat) / (bounds.maxLat - bounds.minLat)) * (h - 2 * pad);
  return [x, y];
}

function unprojectCanvasToLonLat(px, py, w, h) {
  const pad = 16;
  const lon = bounds.minLon + ((px - pad) / (w - 2 * pad)) * (bounds.maxLon - bounds.minLon);
  const lat = bounds.minLat + ((h - pad - py) / (h - 2 * pad)) * (bounds.maxLat - bounds.minLat);
  return [lon, lat];
}

function renderMapCanvas() {
  const canvas = el("offlineCanvas");
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);

  // Grid backdrop
  ctx.strokeStyle = "#dce5da";
  ctx.lineWidth = 1;
  for (let i = 1; i < 6; i++) {
    ctx.beginPath(); ctx.moveTo((w / 6) * i, 0); ctx.lineTo((w / 6) * i, h); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(0, (h / 6) * i); ctx.lineTo(w, (h / 6) * i); ctx.stroke();
  }

  // Draw offline Wilaya boundary if fetched
  if (wilayaGeo && wilayaGeo.features) {
    ctx.fillStyle = "rgba(36, 92, 56, 0.08)";
    ctx.strokeStyle = "#5c7a65";
    ctx.lineWidth = 1.5;
    for (const feat of wilayaGeo.features) {
      const geom = feat.geometry;
      const polys = geom.type === "MultiPolygon" ? geom.coordinates : [geom.coordinates];
      for (const poly of polys) {
        const ring = poly[0];
        ctx.beginPath();
        ring.forEach(([lon, lat], idx) => {
          const [px, py] = projectLonLatToCanvas(lon, lat, w, h);
          if (idx === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
        });
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
      }
    }
  }

  // Draw farmer polygon vertices
  if (drawnVertices.length > 0) {
    ctx.fillStyle = "rgba(217, 155, 30, 0.35)";
    ctx.strokeStyle = "#b55d0d";
    ctx.lineWidth = 2;
    ctx.beginPath();
    drawnVertices.forEach(([lon, lat], idx) => {
      const [px, py] = projectLonLatToCanvas(lon, lat, w, h);
      if (idx === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
    });
    if (drawnVertices.length >= 3) ctx.closePath();
    ctx.fill();
    ctx.stroke();

    drawnVertices.forEach(([lon, lat]) => {
      const [px, py] = projectLonLatToCanvas(lon, lat, w, h);
      ctx.fillStyle = "#8e1414";
      ctx.beginPath();
      ctx.arc(px, py, 3.5, 0, Math.PI * 2);
      ctx.fill();
    });
  }

  ctx.fillStyle = "#37474f";
  ctx.font = "11px sans-serif";
  ctx.fillText("Guelma Wilaya Map Canvas (Click to add vertices)", 10, h - 6);
}

function addHistoryRow(season = "Autumn", year = 2024, cropName = "Durum Wheat") {
  const row = document.createElement("div");
  row.className = "history-row";
  row.innerHTML = `
    <select class="hist-season">
      <option value="Autumn" ${season === "Autumn" ? "selected" : ""}>Autumn</option>
      <option value="Winter" ${season === "Winter" ? "selected" : ""}>Winter</option>
      <option value="Spring" ${season === "Spring" ? "selected" : ""}>Spring</option>
      <option value="Summer" ${season === "Summer" ? "selected" : ""}>Summer</option>
    </select>
    <input type="number" class="hist-year" value="${year}" min="2010" max="2035" />
    <input type="text" class="hist-crop" value="${cropName}" placeholder="e.g. Durum Wheat" />
    <button type="button" class="btn btn-secondary btn-sm btn-del">✕</button>
  `;
  row.querySelector(".btn-del").addEventListener("click", () => row.remove());
  el("historyRows").appendChild(row);
}

function buildApiPayload(includeAnalyzeFields = true) {
  let geomObj;
  try {
    geomObj = JSON.parse(el("polygonJson").value);
  } catch {
    throw new Error("Polygon GeoJSON is invalid JSON or incomplete (draw at least 3 points).");
  }

  const payload = {
    field: {
      field_id: el("fieldId").value.trim(),
      field_name: el("fieldName").value.trim() || null,
      geometry: geomObj,
    },
    water: {
      availability: el("waterAvail").value,
      source: el("waterSource").value,
      irrigation_system: el("irrigSys").value,
    },
    planning: {
      start_season: el("startSeason").value,
      start_year: Number(el("startYear").value),
      horizon_seasons: Number(el("horizonSeasons").value),
      planning_mode: el("planningMode").value,
    },
  };

  const hMode = el("historyMode").value;
  if (hMode === "null") {
    payload.crop_history = null;
  } else if (hMode === "empty") {
    payload.crop_history = [];
  } else {
    const items = [];
    el("historyRows").querySelectorAll(".history-row").forEach((r) => {
      const cname = r.querySelector(".hist-crop").value.trim();
      if (cname) {
        items.push({
          season: r.querySelector(".hist-season").value,
          year: Number(r.querySelector(".hist-year").value),
          crop_name_raw: cname,
        });
      }
    });
    payload.crop_history = items;
  }

  const prefs = {};
  const fMode = el("forageMode").value;
  if (fMode === "null") {
    prefs.forage_value_weight = null;
  } else if (fMode === "zero") {
    prefs.forage_value_weight = 0.0;
  } else {
    prefs.forage_value_weight = Number(fMode);
  }

  const eMode = el("equipmentMode").value;
  if (eMode === "null") prefs.equipment_constraints = null;
  else if (eMode === "empty") prefs.equipment_constraints = [];
  else prefs.equipment_constraints = [eMode];

  const tCrop = el("targetCrop").value;
  if (tCrop) prefs.target_crop_ids = [tCrop];
  const exCrop = el("excludedCrop").value;
  if (exCrop) prefs.excluded_crop_ids = [exCrop];

  payload.preferences = prefs;
  if (includeAnalyzeFields) {
    payload.language = "en";
  }
  return payload;
}

function showError(msg) {
  el("errorCard").classList.remove("hidden");
  el("errorCard").innerHTML = `<div class="notice notice-error"><strong>Validation / Request Error:</strong> ${msg}</div>`;
}

function defaultOpenPlanningPeriod(now = new Date()) {
  const m = now.getMonth() + 1;
  const d = now.getDate();
  const y = now.getFullYear();
  if (m === 1 || m === 2 || (m === 3 && d <= 15)) return { season: "Winter", year: y };
  if (m <= 5) return { season: "Spring", year: y };
  if (m <= 8) return { season: "Summer", year: y };
  return { season: "Autumn", year: y };
}

function statusBadgeHtml(feasStatus, isTop, provisional = false) {
  if (provisional) {
    return `<span class="badge badge-unknown">${isTop ? "Exploratory Candidate (Unendorsed)" : "Provisional / Unverified Land Use"}</span>`;
  }
  if (feasStatus === "FEASIBLE_PASS") return `<span class="badge badge-recommended">Recommended</span>`;
  if (feasStatus === "CONDITIONALLY_FEASIBLE_WITH_WARNINGS_OR_UNKNOWNS") {
    return `<span class="badge badge-conditional">${isTop ? "Top Conditional Choice" : "Conditionally Recommended"}</span>`;
  }
  if (feasStatus === "UNVERIFIED_HARD_UNKNOWN") return `<span class="badge badge-unknown">Insufficient Evidence / Unknown</span>`;
  return `<span class="badge badge-infeasible">Infeasible</span>`;
}

function renderAnalysisResult(data) {
  el("welcomeCard").classList.add("hidden");
  el("errorCard").classList.add("hidden");
  el("resultsWrap").classList.remove("hidden");

  const fp = data.field_profile_summary;
  const ex = fp.extracted_summary;
  const sv = fp.spatial_validation;
  const rec = data.recommendation;
  const fplan = rec.field_plans[0];
  const gate = fplan.decision_gate || {};
  const lu = fplan.land_use_assessment || fp.land_use_assessment || {};
  const dq = fplan.data_quality || {};
  const crit = dq.critical_data_adequacy || {};
  const wb = fplan.water_balance_assessment || {};

  el("fieldProfileBox").innerHTML = `
    <div class="kpi-grid">
      <div class="kpi"><div class="label">Commune &amp; Area</div><div class="val">${sv.primary_commune ? sv.primary_commune.name_2 : "Unknown"} (${sv.area_ha} ha)</div></div>
      <div class="kpi"><div class="label">Land-Use Evidence (10m CropFreq)</div><div class="val">${lu.status || "UNKNOWN"} (CF=${ex.crop_frequency_2021_2025.value ?? "null"})</div></div>
      <div class="kpi"><div class="label">Soil Texture (SoilGrids 250m)</div><div class="val">${ex.usda_texture_0_5cm || "Masked/Null"} (Clay: ${ex.clay_0_30cm_pct.value ?? "null"}%, cov=${ex.clay_0_30cm_pct.polygon_coverage_pct ?? "null"}%)</div></div>
      <div class="kpi"><div class="label">SOC / pH (Modeled, Not Lab)</div><div class="val">SOC ${ex.soc_0_30cm_g_kg.value ?? "null"} g/kg | pH ${ex.ph_0_30cm.value ?? "null"}</div></div>
      <div class="kpi"><div class="label">Precip Spread (11–55 km)</div><div class="val">${ex.gpm_annual_precip_mm.value ?? "?"} mm GPM / ${ex.nasa_power_annual_precip_mm.value ?? "?"} mm POWER</div></div>
      <div class="kpi"><div class="label">DEM Terrain</div><div class="val">${ex.dem_elevation_m.value ?? "UNAVAILABLE_NOT_INTEGRATED"}</div></div>
      <div class="kpi"><div class="label">Catalog Completeness</div><div class="val">${((dq.completeness_score || 0) * 100).toFixed(1)}% (Not Confidence)</div></div>
      <div class="kpi"><div class="label">Critical Data Adequacy</div><div class="val">${crit.adequacy_status || "UNKNOWN"}</div></div>
    </div>
    <p class="muted">${fp.provenance_disclosures.soilgrids_vs_laboratory_distinction}</p>
  `;

  const rm = fplan.ranking_methodology || {};
  const weightWarnings = rm.weight_warnings || [];
  const weightWarnHtml = weightWarnings.length
    ? `<br/><strong>Priority Weight Disclosure:</strong> ${weightWarnings.join(" ")}`
    : "";
  const bannerCls = gate.decision_status === "EXPLORATORY_ONLY" || !fplan.suggested_strategy_id ? "notice-error" : "notice-conditional";
  const nearTieHtml = gate.near_tie_detected
    ? `<br/><strong>Near-Tie / Sensitivity Caution (${gate.margin_status}):</strong> Alternatives close in score: ${(gate.plausible_alternatives || []).map((a) => `${a.strategy_id} (Δ=${a.score_gap_from_top})`).join(", ")}`
    : "";
  el("overallBanner").innerHTML = `
    <div class="notice ${bannerCls}">
      <strong>Analysis ID:</strong> <code>${data.analysis_id}</code> | <strong>Decision Gate:</strong> ${gate.decision_status || fplan.recommendation_status} | <strong>Endorsed ID:</strong> ${gate.endorsed_recommendation_id || "NONE (Exploratory/Unendorsed)"}<br/>
      <strong>Water Modeling Scope:</strong> Ordinal crop regime only — FAO-56 Penman-Monteith balance is <code>${wb.fao56_water_balance_status || "UNKNOWN"}</code>.<br/>
      ${rec.overall_summary}${weightWarnHtml}${nearTieHtml}<br/>
      <small><strong>Important:</strong> Ordinal scores reflect multi-criteria agronomic suitability—NOT predicted crop yield (t/ha), farm profit, or scientific probability.</small>
    </div>
  `;

  if (fplan.requested_crop_results && fplan.requested_crop_results.length > 0) {
    el("requestedCropsBox").innerHTML = `
      <div class="notice notice-info">
        <strong>Requested Target Crops Audit:</strong><br/>
        ${fplan.requested_crop_results.map((r) => `• <strong>${r.crop_name || r.crop_id}</strong>: <code>${r.outcome}</code> — ${r.reason}`).join("<br/>")}
      </div>
    `;
  } else {
    el("requestedCropsBox").innerHTML = "";
  }

  el("strategiesList").innerHTML = fplan.strategies.map((s) => {
    const isTop = s.strategy_id === fplan.suggested_strategy_id;
    const isProvisional = Boolean(s.provisional || gate.provisional_only);
    const infeas = (
      s.feasibility_status === "INFEASIBLE_HARD_CONSTRAINT"
      || s.feasibility_status === "UNVERIFIED_HARD_UNKNOWN"
      || s.feasibility_status === "INFEASIBLE_CONSTRAINT"
    );
    const sc = s.scores;
    const stab = s.stability_metrics || {};
    const slotsHtml = s.seasons.map((sl) => `
      <div class="slot-pill"><strong>${sl.order}. ${sl.season} ${sl.year}</strong><br/>${sl.crop_name}</div>
    `).join("");

    return `
      <article class="strategy-card ${isTop && !isProvisional ? "top-choice" : ""} ${infeas ? "infeasible-card" : ""}">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.4rem;">
          <strong>${s.rank ? `#${s.rank} ` : ""}${s.name}</strong>
          <div>${statusBadgeHtml(s.feasibility_status, isTop, isProvisional)} <span class="badge badge-unknown">${s.pareto_status}</span></div>
        </div>
        <p class="muted" style="margin:0.3rem 0;">${s.description}</p>
        <div class="sequence-strip">${slotsHtml}</div>
        <div class="kpi-grid">
          <div class="kpi"><div class="label">Relative Composite Score</div><div class="val">${s.weighted_score !== null ? s.weighted_score : "N/A (Excluded)"}</div></div>
          <div class="kpi"><div class="label">Water Efficiency (Ordinal)</div><div class="val">${sc.water_efficiency.score ?? "UNKNOWN"} (${sc.water_efficiency.status})</div></div>
          <div class="kpi"><div class="label">Soil Improvement</div><div class="val">${sc.soil_improvement.score ?? "UNKNOWN"} (${sc.soil_improvement.status})</div></div>
          <div class="kpi"><div class="label">Stability / Income</div><div class="val">${stab.top_1_retention !== undefined ? `Top-1: ${(stab.top_1_retention * 100).toFixed(0)}% | ` : ""}${sc.income_potential.status}</div></div>
        </div>
        <p style="font-size:0.86rem; margin:0.4rem 0;"><strong>Why:</strong> ${s.explanation.summary}</p>
        <details>
          <summary>Water, Soil, Sequence Constraints, Missing Data &amp; Evidence (${s.explanation.evidence.length})</summary>
          <ul>
            <li><strong>Water:</strong> ${sc.water_efficiency.explanation}</li>
            <li><strong>Soil:</strong> ${sc.soil_improvement.explanation}</li>
            <li><strong>Warnings / Risks:</strong> ${(s.explanation.risks || []).join("; ") || "None listed"}</li>
            <li><strong>Missing Info / Gaps:</strong> ${(s.explanation.information_gaps || []).join("; ") || "None"}</li>
            <li><strong>Local Verification Required:</strong> ${(s.explanation.review_checklist || []).join("; ") || "Confirm with DSA advisor"}</li>
            <li><strong>Sources:</strong> ${(s.explanation.evidence || []).slice(0, 8).map((ev) => `${ev.parameter} (${ev.data_source}: ${ev.quality_status})`).join(" | ")}</li>
          </ul>
        </details>
      </article>
    `;
  }).join("");

  el("qualityFooter").innerHTML = `
    <div class="notice notice-info">
      <strong>Data Quality Warnings:</strong> ${(fplan.data_quality.warnings || []).join(" | ") || "None"}<br/>
      <strong>Missing Information:</strong> ${(fplan.data_quality.missing_data || []).slice(0, 4).join(" | ")}<br/>
      <strong>Disclaimer:</strong> ${rec.disclaimer}
    </div>
  `;
}

async function init() {
  const defPlan = defaultOpenPlanningPeriod(new Date());
  el("startSeason").value = defPlan.season;
  el("startYear").value = String(defPlan.year);
  setPolygonTextFromVertices();
  addHistoryRow("Autumn", defPlan.year - 2, "Durum Wheat");

  el("historyMode").addEventListener("change", () => {
    el("historyListWrap").classList.toggle("hidden", el("historyMode").value !== "provided");
  });

  el("offlineCanvas").addEventListener("click", (ev) => {
    const rect = el("offlineCanvas").getBoundingClientRect();
    const px = ((ev.clientX - rect.left) / rect.width) * el("offlineCanvas").width;
    const py = ((ev.clientY - rect.top) / rect.height) * el("offlineCanvas").height;
    drawnVertices.push(unprojectCanvasToLonLat(px, py, el("offlineCanvas").width, el("offlineCanvas").height));
    setPolygonTextFromVertices();
    renderMapCanvas();
  });

  el("btnUndoVertex").addEventListener("click", () => { drawnVertices.pop(); setPolygonTextFromVertices(); renderMapCanvas(); });
  el("btnClearPoly").addEventListener("click", () => { drawnVertices = []; setPolygonTextFromVertices(); renderMapCanvas(); });

  const applyPreset = (key) => {
    const p = PRESETS[key];
    el("fieldId").value = p.fieldId;
    el("fieldName").value = p.fieldName;
    el("waterAvail").value = p.water.availability;
    el("waterSource").value = p.water.source;
    el("irrigSys").value = p.water.irrigation_system;
    drawnVertices = p.coords[0].slice(0, -1);
    setPolygonTextFromVertices();
    renderMapCanvas();
  };
  el("btnPresetBelkheir").addEventListener("click", () => applyPreset("belkheir"));
  el("btnPresetTamlouka").addEventListener("click", () => applyPreset("tamlouka"));
  el("btnPresetPeriUrban").addEventListener("click", () => applyPreset("periurban"));
  el("btnAddHistory").addEventListener("click", () => addHistoryRow("Autumn", 2023, "Faba Bean"));

  try {
    const [hRes, bRes, cRes] = await Promise.all([
      fetch("/api/v1/health"),
      fetch("/api/v1/reference/guelma-boundary"),
      fetch("/api/v1/reference/crops"),
    ]);
    if (hRes.ok) {
      const h = await hRes.json();
      el("apiHealthBadge").textContent = `Backend: ${h.status.toUpperCase()} (${h.knowledge_base.crops_count} crops | ${h.database.active_backend})`;
      el("apiHealthBadge").className = "badge badge-recommended";
    }
    if (bRes.ok) {
      wilayaGeo = await bRes.json();
      renderMapCanvas();
    }
    if (cRes.ok) {
      const cJson = await cRes.json();
      for (const c of cJson.crops) {
        el("targetCrop").insertAdjacentHTML("beforeend", `<option value="${c.crop_id}">${c.canonical_name}</option>`);
        el("excludedCrop").insertAdjacentHTML("beforeend", `<option value="${c.crop_id}">${c.canonical_name}</option>`);
      }
    }
  } catch {
    el("apiHealthBadge").textContent = "Backend unreachable";
  }
  renderMapCanvas();

  el("btnValidate").addEventListener("click", async () => {
    try {
      const payload = buildApiPayload(false);
      const res = await fetch("/api/v1/fields/validate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const body = await res.json();
      el("validationOutput").classList.remove("hidden");
      if (!res.ok) {
        const errCode = body.error_code ? `[${body.error_code}] ` : "";
        el("validationOutput").innerHTML = `<div class="notice notice-error">${errCode}${body.message || JSON.stringify(body.detail || body)}</div>`;
      } else {
        el("validationOutput").innerHTML = `<div class="notice notice-info"><strong>Polygon Valid:</strong> ${body.area_ha} ha inside <strong>${body.primary_commune ? body.primary_commune.name_2 : "Guelma"}</strong> (${body.wilaya_overlap_pct}% overlap).</div>`;
      }
    } catch (err) {
      showError(err.message);
    }
  });

  el("btnAnalyze").addEventListener("click", async () => {
    try {
      const payload = buildApiPayload(true);
      const res = await fetch("/api/v1/fields/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const body = await res.json();
      if (!res.ok) {
        const errCode = body.error_code ? `[${body.error_code}] ` : "";
        showError(`${errCode}${body.message || (body.detail && body.detail.message) || "Validation failed."}`);
        return;
      }
      renderAnalysisResult(body);
    } catch (err) {
      showError(err.message);
    }
  });
}

document.addEventListener("DOMContentLoaded", init);
