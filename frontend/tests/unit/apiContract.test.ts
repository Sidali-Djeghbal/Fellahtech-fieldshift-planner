import { describe, expect, it, vi } from "vitest";
import { apiClient, createApiClient, resolveApiBaseRoot } from "@/lib/api/client";
import { patchField } from "@/lib/api/endpoints";
import { ApiClientError } from "@/lib/api/errors";
import { fixtureState, handleFixtureRequest } from "@/lib/api/fixtures";
import {
  serializeFieldPatchRequest,
  serializeFieldWriteRequest,
  type FieldDetailPublic,
  type FieldWriteDraft,
} from "@/lib/schemas";

const VALID_FIELD_RESPONSE: FieldDetailPublic = {
  farm_id: "farm_1",
  field_id: "F-1",
  field_name: "Parcelle Seybouse",
  is_unverified_demo_parcel: false,
  location: {
    latitude: 36.4621,
    longitude: 7.4264,
    boundary: null,
  },
  area_hectares: 12.5,
  elevation_m: 210,
  soil: {
    soil_type: "loamy",
    source: "farmer",
    soil_ph: 7.4,
    organic_matter_percent: 1.8,
    soil_test_date: "2026-04-01",
  },
  water: {
    availability: "moderate",
    source: "well",
    source_other: null,
    irrigation_system: "drip",
  },
  warnings: [],
  crop_history: [
    {
      season: "autumn",
      year: 2025,
      planting_month: 11,
      crop_id: "durum_wheat",
      crop_name_raw: "Durum Wheat",
      yield_tons_per_hectare: 3.1,
      notes: null,
    },
  ],
};

describe("Live API contract & payload sanitization", () => {
  it("normalizes NEXT_PUBLIC_API_BASE_URL without duplicating /api/v1", () => {
    expect(resolveApiBaseRoot(undefined)).toBe("/api/v1");
    expect(resolveApiBaseRoot("")).toBe("/api/v1");
    expect(resolveApiBaseRoot("http://localhost:8000")).toBe("http://localhost:8000/api/v1");
    expect(resolveApiBaseRoot("http://localhost:8000/")).toBe("http://localhost:8000/api/v1");
    expect(resolveApiBaseRoot("http://localhost:8000/api/v1")).toBe("http://localhost:8000/api/v1");
    expect(resolveApiBaseRoot("https://api.fieldshift.dz/api/v1/")).toBe(
      "https://api.fieldshift.dz/api/v1"
    );
  });

  it("maps live network failures to SERVICE_UNAVAILABLE ApiClientError", async () => {
    const client = createApiClient({
      baseUrl: "http://127.0.0.1:8000/api/v1",
      fixtureMode: false,
      fetchImpl: (async () => {
        throw new TypeError("Failed to fetch");
      }) as typeof fetch,
      tokenAdapter: {
        getAccessToken: () => null,
        getRefreshToken: () => null,
        getGuestToken: () => "guest_tok",
        onTokensRotated: () => {},
        onAuthInvalidated: () => {},
      },
    });

    await expect(client.request("/farms")).rejects.toMatchObject({
      name: "ApiClientError",
      status: 503,
      code: "SERVICE_UNAVAILABLE",
    });
  });

  it("refreshes expired bearer tokens on 401 and parses OpenAPI ErrorEnvelope", async () => {
    let accessToken = "expired_access";
    const calls: string[] = [];

    const mockFetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      calls.push(`${init?.method ?? "GET"} ${url}`);

      if (url.endsWith("/auth/refresh")) {
        return new Response(
          JSON.stringify({
            access_token: "fresh_access",
            refresh_token: "fresh_refresh",
            token_type: "bearer",
            expires_in: 900,
          }),
          { status: 200, headers: { "content-type": "application/json" } }
        );
      }

      const authHeader = (init?.headers as Record<string, string>)?.Authorization;
      if (authHeader === "Bearer expired_access") {
        return new Response(
          JSON.stringify({
            error: {
              code: "UNAUTHORIZED",
              message: "Token expired",
              details: [],
              request_id: "req_1",
            },
          }),
          { status: 401, headers: { "content-type": "application/json" } }
        );
      }

      return new Response(JSON.stringify({ items: [] }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }) as typeof fetch;

    const client = createApiClient({
      baseUrl: "http://127.0.0.1:8000/api/v1",
      fixtureMode: false,
      fetchImpl: mockFetch,
      tokenAdapter: {
        getAccessToken: () => accessToken,
        getRefreshToken: () => "refresh_tok",
        getGuestToken: () => null,
        onTokensRotated: (tokens) => {
          accessToken = tokens.accessToken;
        },
        onAuthInvalidated: () => {},
      },
    });

    const data = await client.request<{ items: unknown[] }>("/farms");
    expect(data).toEqual({ items: [] });
    expect(accessToken).toBe("fresh_access");
    expect(calls).toHaveLength(3);
  });

  it("enforces FieldPatchRequest additionalProperties:false and strips forbidden keys in patchField", async () => {
    const spy = vi.spyOn(apiClient, "request").mockResolvedValueOnce(VALID_FIELD_RESPONSE);

    const dirtyPatch = {
      field_id: "F-1",
      is_unverified_demo_parcel: false,
      field_name: "  Parcelle Updated  ",
      elevation_m: "",
      soil: {
        soil_type: "loamy",
        source: "farmer",
        soil_ph: "",
        organic_matter_percent: "1.9",
        soil_test_date: "",
      },
      crop_history: [
        {
          season: "autumn",
          year: 2025,
          planting_month: "" as unknown as number,
          crop_id: "durum_wheat",
          crop_name_raw: "",
          catalog_version: "2026.11",
          yield_tons_per_hectare: "" as unknown as number,
          notes: "  ",
        },
      ],
    } as Partial<FieldWriteDraft>;

    await patchField("farm_1", "F-1", dirtyPatch);

    expect(spy).toHaveBeenCalledTimes(1);
    const [, options] = spy.mock.calls[0];
    const body = options?.body as Record<string, unknown>;
    expect(body).not.toHaveProperty("field_id");
    expect(body).not.toHaveProperty("is_unverified_demo_parcel");
    expect(body.field_name).toBe("Parcelle Updated");
    expect(body.elevation_m).toBeNull();
    expect(body.soil).toEqual({
      soil_type: "loamy",
      soil_ph: null,
      organic_matter_percent: 1.9,
      soil_test_date: null,
    });
    expect(body.crop_history).toEqual([
      {
        season: "autumn",
        year: 2025,
        planting_month: null,
        crop_id: "durum_wheat",
        crop_name_raw: null,
        yield_tons_per_hectare: null,
        notes: null,
      },
    ]);

    spy.mockRestore();
  });

  it("serializeFieldWriteRequest converts blank numeric/string fields to null cleanly", () => {
    const draft: FieldWriteDraft = {
      field_id: "F-9",
      field_name: "Heliopolis Plot",
      is_unverified_demo_parcel: false,
      location: { latitude: 36.5, longitude: 7.41, boundary: null },
      area_hectares: 6.2,
      elevation_m: "",
      soil: {
        soil_type: "unknown",
        source: "unknown",
        soil_ph: "7.5",
        organic_matter_percent: "1.2",
        soil_test_date: "2026-01-10",
      },
      water: {
        availability: "limited",
        source: "rainwater",
        source_other: "ignored",
        irrigation_system: "rainfed",
      },
      crop_history: [
        {
          season: "autumn",
          year: 2024,
          planting_month: "" as unknown as number,
          crop_id: "barley",
          crop_name_raw: "",
          catalog_version: "2026.11",
          yield_tons_per_hectare: "" as unknown as number,
          notes: "",
        },
      ],
    };

    const req = serializeFieldWriteRequest(draft);
    expect(req.elevation_m).toBeNull();
    expect(req.soil).toEqual({
      soil_type: "unknown",
      soil_ph: null,
      organic_matter_percent: null,
      soil_test_date: null,
    });
    expect(req.water.source_other).toBeNull();
    expect(req.crop_history[0].planting_month).toBeNull();
    expect(req.crop_history[0].yield_tons_per_hectare).toBeNull();

    expect(() => serializeFieldPatchRequest({ field_name: "   " })).toThrow();
    expect(() =>
      new ApiClientError({
        status: 503,
        code: "SERVICE_UNAVAILABLE",
        message: "Offline",
        details: [],
        requestId: null,
      })
    ).not.toThrow();
  });

  it("rehydrates fixture guest session on page reload until explicitly revoked", async () => {
    fixtureState.reset();
    const guestHdr = { "X-Guest-Token": "gst_9b44f7c10a8e2130d5c89e4b" };

    // Simulates browser reload where client still has guest token in localStorage
    const farmsRes = await handleFixtureRequest("/farms", { method: "GET", headers: guestHdr });
    expect(farmsRes.status).toBe(200);
    expect((farmsRes.data as { items: unknown[] }).items.length).toBeGreaterThan(0);

    // Explicit guest deletion revokes session even with matching header
    await handleFixtureRequest("/demo/session", { method: "DELETE", headers: guestHdr });
    await expect(
      handleFixtureRequest("/farms", { method: "GET", headers: guestHdr })
    ).rejects.toMatchObject({ code: "UNAUTHORIZED", status: 401 });
  });
});

