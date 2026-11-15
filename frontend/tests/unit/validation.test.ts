import { describe, expect, it, vi } from "vitest";
import { createApiClient } from "@/lib/api/client";
import { FIXTURE_OUTPUT_9_3 } from "@/lib/api/fixtures";
import { AnalysisResultSchema, serializeFieldWriteRequest } from "@/lib/schemas";
import {
  balanceRemainingWeights,
  classifyUsdaSoilTexture,
  validateDisjointCrops,
  validateSeasonMonthConsistency,
  validateWeightsSum,
} from "@/lib/validation";

describe("INPUT-01: Priority weights strict sum to 100", () => {
  it("rejects weights not summing to 100 and accepts valid weights", () => {
    const invalid = validateWeightsSum({
      water_saving: 30,
      soil_improvement: 20,
      income: 20,
      risk_reduction: 15,
      forage_value: 5,
    });
    expect(invalid.valid).toBe(false);
    expect(invalid.sum).toBe(90);
    expect(invalid.remaining).toBe(10);

    const valid = validateWeightsSum({
      water_saving: 25,
      soil_improvement: 20,
      income: 30,
      risk_reduction: 15,
      forage_value: 10,
    });
    expect(valid.valid).toBe(true);
    expect(valid.sum).toBe(100);
    expect(valid.remaining).toBe(0);
  });

  it("balances remaining weights onto anchor key to hit 100", () => {
    const balanced = balanceRemainingWeights(
      {
        water_saving: 35,
        soil_improvement: 20,
        income: 20,
        risk_reduction: 10,
        forage_value: 5,
      },
      "income"
    );
    expect(validateWeightsSum(balanced).valid).toBe(true);
    expect(balanced.income).toBe(30);
  });
});

describe("INPUT-02: Target and excluded crops must be disjoint", () => {
  it("rejects overlapping crop IDs and accepts disjoint sets", () => {
    const invalid = validateDisjointCrops(["durum_wheat", "chickpea"], ["chickpea", "barley"]);
    expect(invalid.valid).toBe(false);
    expect(invalid.overlappingIds).toEqual(["chickpea"]);

    const valid = validateDisjointCrops(["durum_wheat", "lentil"], ["chickpea", "barley"]);
    expect(valid.valid).toBe(true);
    expect(valid.overlappingIds).toEqual([]);
  });
});

describe("INPUT-03: Northern Hemisphere season <-> planting month consistency", () => {
  it("rejects winter + month 8 and accepts spring + month 3", () => {
    const badWinter = validateSeasonMonthConsistency("winter", 8, 36.47);
    expect(badWinter.valid).toBe(false);

    const goodSpring = validateSeasonMonthConsistency("spring", 3, 36.47);
    expect(goodSpring.valid).toBe(true);

    const nullMonth = validateSeasonMonthConsistency("autumn", null, 36.47);
    expect(nullMonth.valid).toBe(true);
  });
});

describe("ADR-5: FieldWriteRequest sanitization", () => {
  it("strips soil.source and crop_history[].catalog_version and keeps elevation_m null", () => {
    const payload = serializeFieldWriteRequest({
      field_id: "F1",
      field_name: "Parcelle Test",
      is_unverified_demo_parcel: true,
      location: { latitude: 36.4692, longitude: 7.4285, boundary: null },
      area_hectares: 4.2,
      elevation_m: null,
      soil: {
        soil_type: "clay",
        source: "farmer",
        soil_ph: 7.6,
        organic_matter_percent: 1.8,
        soil_test_date: "2025-11-10",
      },
      water: {
        availability: "moderate",
        source: "well",
        source_other: null,
        irrigation_system: "drip",
      },
      crop_history: [
        {
          season: "winter",
          year: 2025,
          planting_month: 12,
          crop_id: "durum_wheat",
          crop_name_raw: null,
          catalog_version: "cropcat_v2.4",
          yield_tons_per_hectare: 2.8,
          notes: "Baseline",
        },
      ],
    });

    expect(payload.elevation_m).toBeNull();
    expect("source" in payload.soil).toBe(false);
    expect("catalog_version" in payload.crop_history[0]).toBe(false);
    expect(payload.soil.soil_ph).toBe(7.6);
  });
});

describe("ADR-5: USDA Soil Texture classifier", () => {
  it("follows exact precedence across clay, silt, sand, and loamy boundaries in g/kg and %", () => {
    expect(classifyUsdaSoilTexture({ clay: 400, silt: 500, sand: 100, unit: "g_per_kg" })).toBe(
      "clay"
    );
    expect(classifyUsdaSoilTexture({ clay: 399, silt: 500, sand: 101, unit: "g_per_kg" })).toBe(
      "silty"
    );
    expect(classifyUsdaSoilTexture({ clay: 150, silt: 150, sand: 700, unit: "g_per_kg" })).toBe(
      "sandy"
    );
    expect(classifyUsdaSoilTexture({ clay: 250, silt: 350, sand: 400, unit: "g_per_kg" })).toBe(
      "loamy"
    );
    expect(classifyUsdaSoilTexture({ clay: 42, silt: 38, sand: 20, unit: "percent" })).toBe(
      "clay"
    );
  });
});

describe("Tolerant Reader: AnalysisResultSchema v5.x", () => {
  it("validates §9.3 fixture and forward 5.1 schema with unknown keys, and rejects 6.0", () => {
    const ok93 = AnalysisResultSchema.safeParse(FIXTURE_OUTPUT_9_3);
    expect(ok93.success).toBe(true);

    const forward51 = {
      ...FIXTURE_OUTPUT_9_3,
      schema_version: "5.1",
      future_advisory_note: "optional metadata from 5.1",
    };
    const ok51 = AnalysisResultSchema.safeParse(forward51);
    expect(ok51.success).toBe(true);

    const breaking60 = {
      ...FIXTURE_OUTPUT_9_3,
      schema_version: "6.0",
    };
    const bad60 = AnalysisResultSchema.safeParse(breaking60);
    expect(bad60.success).toBe(false);
  });
});

describe("Single-flight auth refresh mutex", () => {
  it("triggers exactly one POST /auth/refresh across 3 concurrent 401 responses", async () => {
    let accessToken = "expired-access";
    let refreshToken = "valid-refresh";
    let refreshCount = 0;

    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/auth/refresh")) {
        refreshCount += 1;
        await new Promise((r) => setTimeout(r, 20));
        return new Response(
          JSON.stringify({
            access_token: "fresh-access",
            refresh_token: "fresh-refresh",
            token_type: "bearer",
            expires_in: 3600,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }

      const authHeader = new Headers(init?.headers).get("Authorization");
      if (authHeader !== "Bearer fresh-access") {
        return new Response(
          JSON.stringify({ error: { code: "UNAUTHORIZED", message: "Expired" } }),
          { status: 401, headers: { "Content-Type": "application/json" } }
        );
      }
      return new Response(JSON.stringify({ ok: true, path: url }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });

    const client = createApiClient({
      baseUrl: "http://localhost:8000/api/v1",
      fixtureMode: false,
      fetchImpl: fetchMock as unknown as typeof fetch,
      tokenAdapter: {
        getAccessToken: () => accessToken,
        getRefreshToken: () => refreshToken,
        getGuestToken: () => null,
        onTokensRotated: (next) => {
          accessToken = next.accessToken;
          refreshToken = next.refreshToken;
        },
        onAuthInvalidated: () => {
          accessToken = "";
          refreshToken = "";
        },
      },
    });

    const results = await Promise.all([
      client.request<{ ok: boolean }>("/farms"),
      client.request<{ ok: boolean }>("/crops"),
      client.request<{ ok: boolean }>("/auth/me"),
    ]);

    expect(refreshCount).toBe(1);
    expect(accessToken).toBe("fresh-access");
    expect(refreshToken).toBe("fresh-refresh");
    expect(results.every((r) => r.ok)).toBe(true);
  });
});
