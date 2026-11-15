import {
  AnalysisEnvelopeSchema,
  AnalysisPollEnvelopeSchema,
  AnalysisQueuedResponseSchema,
  BoundaryFeatureSchema,
  CatalogPageSchema,
  FarmAnalysesPageSchema,
  FarmPageSchema,
  FarmPublicSchema,
  FieldDetailPublicSchema,
  FieldPageSchema,
  FieldPublicSchema,
  GuestSessionInfoSchema,
  GuestSessionStartResponseSchema,
  HealthResponseSchema,
  RegisterResponseSchema,
  SelectionPatchResponseSchema,
  TokenPairResponseSchema,
  UserDataExportSchema,
  UserProfileSchema,
  type AnalysisEnvelope,
  type AnalysisPollEnvelope,
  type AnalysisQueuedResponse,
  type AnalysisSubmitRequest,
  type BoundaryFeature,
  type CatalogPage,
  type CropCategory,
  type CropItem,
  type CropRole,
  type DemoLocationSummary,
  type FarmAnalysesPage,
  type FarmPage,
  type FarmPatchRequest,
  type FarmPublic,
  type FarmWriteRequest,
  type FieldDetailPublic,
  type FieldPage,
  type FieldPublic,
  type FieldWriteDraft,
  type GuestSessionInfo,
  type GuestSessionStartResponse,
  type HealthResponse,
  type Language,
  type RegisterResponse,
  type SelectionPatchResponse,
  type SoilType,
  type TokenPairResponse,
  type UserDataExport,
  type UserProfile,
  type WaterAvailability,
  serializeFieldPatchRequest,
  serializeFieldWriteRequest,
} from "@/lib/schemas";
import { apiClient } from "./client";

function buildQuery(params: Record<string, string | number | undefined | null>): string {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") {
      qs.set(k, String(v));
    }
  }
  const s = qs.toString();
  return s ? `?${s}` : "";
}

// ---------------------------------------------------------------------------
// Auth (9 endpoints)
// ---------------------------------------------------------------------------

export async function startGuestSession(demoLocationId = 1): Promise<GuestSessionStartResponse> {
  const data = await apiClient.request<unknown>("/auth/guest", {
    method: "POST",
    body: { demo_location_id: demoLocationId },
    skipAuthRefresh: true,
  });
  return GuestSessionStartResponseSchema.parse(data);
}

export async function registerUser(input: {
  email: string;
  password: string;
  full_name: string;
  preferred_lang?: Language;
}): Promise<RegisterResponse> {
  const data = await apiClient.request<unknown>("/auth/register", {
    method: "POST",
    body: input,
    skipAuthRefresh: true,
  });
  return RegisterResponseSchema.parse(data);
}

export async function loginUser(input: {
  email: string;
  password: string;
}): Promise<TokenPairResponse> {
  const data = await apiClient.request<unknown>("/auth/login", {
    method: "POST",
    body: input,
    skipAuthRefresh: true,
  });
  return TokenPairResponseSchema.parse(data);
}

export async function refreshAuthToken(refresh_token: string): Promise<TokenPairResponse> {
  const data = await apiClient.request<unknown>("/auth/refresh", {
    method: "POST",
    body: { refresh_token },
    skipAuthRefresh: true,
  });
  return TokenPairResponseSchema.parse(data);
}

export async function logoutUser(refresh_token?: string | null): Promise<void> {
  await apiClient.request<void>("/auth/logout", {
    method: "POST",
    body: refresh_token ? { refresh_token } : undefined,
    skipAuthRefresh: true,
  });
}

export async function getMe(): Promise<UserProfile> {
  const data = await apiClient.request<unknown>("/auth/me", { method: "GET" });
  return UserProfileSchema.parse(data);
}

export async function deleteMe(): Promise<void> {
  await apiClient.request<void>("/auth/me", { method: "DELETE" });
}

export async function exportMeData(): Promise<UserDataExport> {
  const data = await apiClient.request<unknown>("/auth/me/export", { method: "GET" });
  return UserDataExportSchema.parse(data);
}

export async function claimGuestSession(): Promise<{ claimed_farms_count: number }> {
  return apiClient.request<{ claimed_farms_count: number }>("/auth/claim-guest", {
    method: "POST",
    sendBothAuthAndGuest: true,
  });
}

// ---------------------------------------------------------------------------
// Demo (4 endpoints)
// ---------------------------------------------------------------------------

export async function listDemoLocations(params?: {
  limit?: number;
  cursor?: string;
}): Promise<{ items: DemoLocationSummary[]; next_cursor: string | null; has_more: boolean }> {
  return apiClient.request(`/demo/locations${buildQuery(params ?? {})}`, {
    method: "GET",
  });
}

export async function getDemoLocationBoundary(id = 1): Promise<BoundaryFeature> {
  const data = await apiClient.request<unknown>(`/demo/locations/${id}/boundary`, {
    method: "GET",
  });
  return BoundaryFeatureSchema.parse(data);
}

export async function getDemoSession(): Promise<GuestSessionInfo> {
  const data = await apiClient.request<unknown>("/demo/session", { method: "GET" });
  return GuestSessionInfoSchema.parse(data);
}

export async function deleteDemoSession(): Promise<void> {
  await apiClient.request<void>("/demo/session", { method: "DELETE" });
}

// ---------------------------------------------------------------------------
// Farms (6 endpoints)
// ---------------------------------------------------------------------------

export async function listFarms(params?: {
  limit?: number;
  cursor?: string;
  country?: string;
  region?: string;
  search?: string;
}): Promise<FarmPage> {
  const data = await apiClient.request<unknown>(`/farms${buildQuery(params ?? {})}`, {
    method: "GET",
  });
  return FarmPageSchema.parse(data);
}

export async function createFarm(payload: FarmWriteRequest): Promise<FarmPublic> {
  const data = await apiClient.request<unknown>("/farms", {
    method: "POST",
    body: payload,
  });
  return FarmPublicSchema.parse(data);
}

export async function getFarm(farmId: string): Promise<FarmPublic> {
  const data = await apiClient.request<unknown>(`/farms/${farmId}`, { method: "GET" });
  return FarmPublicSchema.parse(data);
}

export async function replaceFarm(
  farmId: string,
  payload: FarmWriteRequest
): Promise<FarmPublic> {
  const data = await apiClient.request<unknown>(`/farms/${farmId}`, {
    method: "PUT",
    body: payload,
  });
  return FarmPublicSchema.parse(data);
}

export async function patchFarm(
  farmId: string,
  payload: FarmPatchRequest
): Promise<FarmPublic> {
  const data = await apiClient.request<unknown>(`/farms/${farmId}`, {
    method: "PATCH",
    body: payload,
  });
  return FarmPublicSchema.parse(data);
}

export async function deleteFarm(farmId: string): Promise<void> {
  await apiClient.request<void>(`/farms/${farmId}`, { method: "DELETE" });
}

// ---------------------------------------------------------------------------
// Fields (6 endpoints — enforces ADR-5 serializeFieldWriteRequest)
// ---------------------------------------------------------------------------

export async function listFields(
  farmId: string,
  params?: {
    limit?: number;
    cursor?: string;
    soil_type?: SoilType;
    water_availability?: WaterAvailability;
  }
): Promise<FieldPage> {
  const data = await apiClient.request<unknown>(
    `/farms/${farmId}/fields${buildQuery(params ?? {})}`,
    { method: "GET" }
  );
  return FieldPageSchema.parse(data);
}

export async function createField(
  farmId: string,
  draft: FieldWriteDraft
): Promise<FieldPublic> {
  const payload = serializeFieldWriteRequest(draft);
  const data = await apiClient.request<unknown>(`/farms/${farmId}/fields`, {
    method: "POST",
    body: payload,
  });
  return FieldPublicSchema.parse(data);
}

export async function getField(farmId: string, fieldId: string): Promise<FieldDetailPublic> {
  const data = await apiClient.request<unknown>(
    `/farms/${farmId}/fields/${encodeURIComponent(fieldId)}`,
    { method: "GET" }
  );
  return FieldDetailPublicSchema.parse(data);
}

export async function replaceField(
  farmId: string,
  fieldId: string,
  draft: FieldWriteDraft
): Promise<FieldDetailPublic> {
  const payload = serializeFieldWriteRequest(draft);
  const data = await apiClient.request<unknown>(
    `/farms/${farmId}/fields/${encodeURIComponent(fieldId)}`,
    {
      method: "PUT",
      body: payload,
    }
  );
  return FieldDetailPublicSchema.parse(data);
}

export async function patchField(
  farmId: string,
  fieldId: string,
  patch: Partial<FieldWriteDraft>
): Promise<FieldDetailPublic> {
  // Enforce OpenAPI FieldPatchRequest additionalProperties:false & ADR-5 sanitization
  const sanitized = serializeFieldPatchRequest(patch);
  const data = await apiClient.request<unknown>(
    `/farms/${farmId}/fields/${encodeURIComponent(fieldId)}`,
    {
      method: "PATCH",
      body: sanitized,
    }
  );
  return FieldDetailPublicSchema.parse(data);
}

export async function deleteField(farmId: string, fieldId: string): Promise<void> {
  await apiClient.request<void>(
    `/farms/${farmId}/fields/${encodeURIComponent(fieldId)}`,
    { method: "DELETE" }
  );
}

// ---------------------------------------------------------------------------
// Analysis (6 endpoints — never passes ?wait=true in production UI)
// ---------------------------------------------------------------------------

export async function submitAnalysis(
  payload: AnalysisSubmitRequest,
  idempotencyKey?: string
): Promise<AnalysisQueuedResponse> {
  const key =
    idempotencyKey ??
    (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
      ? crypto.randomUUID()
      : `idem-${Date.now()}`);
  const data = await apiClient.request<unknown>("/analysis", {
    method: "POST",
    body: payload,
    idempotencyKey: key,
  });
  return AnalysisQueuedResponseSchema.parse(data);
}

export async function pollAnalysisRequest(
  requestId: string
): Promise<AnalysisPollEnvelope> {
  const data = await apiClient.request<unknown>(
    `/analysis/requests/${encodeURIComponent(requestId)}`,
    { method: "GET" }
  );
  return AnalysisPollEnvelopeSchema.parse(data);
}

export async function cancelAnalysisRequest(
  requestId: string
): Promise<{ request_id: string; status: "cancelled" }> {
  return apiClient.request(`/analysis/requests/${encodeURIComponent(requestId)}/cancel`, {
    method: "POST",
  });
}

export async function getAnalysisResult(analysisId: string): Promise<AnalysisEnvelope> {
  const data = await apiClient.request<unknown>(
    `/analysis/${encodeURIComponent(analysisId)}`,
    { method: "GET" }
  );
  return AnalysisEnvelopeSchema.parse(data);
}

export async function updateAnalysisSelection(
  analysisId: string,
  payload: {
    field_id: string;
    strategy_id: string;
    selection_status: "selected" | "rejected";
  }
): Promise<SelectionPatchResponse> {
  const data = await apiClient.request<unknown>(
    `/analysis/${encodeURIComponent(analysisId)}/selection`,
    {
      method: "PATCH",
      body: payload,
    }
  );
  return SelectionPatchResponseSchema.parse(data);
}

export async function listFarmAnalyses(
  farmId: string,
  params?: {
    limit?: number;
    cursor?: string;
    status?: "pending" | "running" | "ok" | "partial" | "failed" | "cancelled";
  }
): Promise<FarmAnalysesPage> {
  const data = await apiClient.request<unknown>(
    `/farms/${farmId}/analyses${buildQuery(params ?? {})}`,
    { method: "GET" }
  );
  return FarmAnalysesPageSchema.parse(data);
}

// ---------------------------------------------------------------------------
// Catalog (1 endpoint — cursor auto-pagination) & System Health (1 endpoint)
// ---------------------------------------------------------------------------

export async function getCatalogPage(params?: {
  limit?: number;
  cursor?: string;
  category?: CropCategory;
  role?: CropRole;
  lang?: Language;
  version?: string;
}): Promise<CatalogPage> {
  const data = await apiClient.request<unknown>(
    `/catalog${buildQuery({ limit: 50, ...params })}`,
    { method: "GET" }
  );
  return CatalogPageSchema.parse(data);
}

export async function fetchAllCatalogItems(
  lang?: Language
): Promise<{ catalog_version: string; synced_at: string; items: CropItem[] }> {
  const items: CropItem[] = [];
  let cursor: string | undefined = undefined;
  let catalogVersion = "";
  let syncedAt = "";

  for (let pageCount = 0; pageCount < 20; pageCount++) {
    const page = await getCatalogPage({ limit: 50, cursor, lang });
    catalogVersion = page.catalog_version;
    syncedAt = page.synced_at;
    items.push(...page.items);
    if (!page.has_more || !page.next_cursor) break;
    cursor = page.next_cursor;
  }

  return { catalog_version: catalogVersion, synced_at: syncedAt, items };
}

export async function getHealth(
  check: "live" | "ready" | "dependencies" = "dependencies"
): Promise<HealthResponse> {
  const data = await apiClient.request<unknown>(`/health?check=${check}`, {
    method: "GET",
    skipAuthRefresh: true,
  });
  return HealthResponseSchema.parse(data);
}
