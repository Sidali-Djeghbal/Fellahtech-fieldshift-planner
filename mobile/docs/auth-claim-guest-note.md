# Deferred `/auth/claim-guest` Specification & Technical Note

## 1. OpenAPI v3.2 Contract Specification

In `docs/openapi-v3.2.yaml`, the guest session claim endpoint is defined as:

- **Path**: `POST /api/v1/auth/claim-guest`
- **Security Requirement**:
  ```yaml
  security:
    - BearerAuth: []
      GuestTokenAuth: []
  ```
  Note that unlike standard alternative security schemes (`- BearerAuth: []` OR `- GuestTokenAuth: []`), the OpenAPI specification explicitly declares both schemes within a single object array item. This requires **both** authentication headers to be present simultaneously on the HTTP request:
  - `Authorization: Bearer <access_token>`
  - `X-Guest-Token: <guest_token>`

## 2. Phase 2 Token Isolation Architecture

In Phase 2, `SecureSessionStore` strictly enforces security isolation between registered user sessions and unverified guest sessions:
- Calling `saveBearerTokens()` immediately wipes `guestToken` from persistent storage and memory.
- Calling `saveGuestToken()` immediately wipes `accessToken` and `refreshToken`.
- `AuthInterceptor` attaches `Authorization: Bearer` for registered user endpoints and `X-Guest-Token` for guest endpoints.

This isolation is a deliberate security safeguard: it prevents token confusion, prevents accidental leakage of temporary guest identifiers into authenticated user calls, and ensures single-session predictability across the application.

## 3. Deferred Implementation & Migration Requirements

The `/auth/claim-guest` endpoint is intentionally **deferred** beyond Phase 2 to prevent compromising the strict token isolation boundary before guest conversion workflows are fully designed in subsequent phases.

When `/auth/claim-guest` is implemented in a future phase (e.g. Phase 3 / Phase 4 account migration), the following design requirements must be satisfied:

1. **Transient Token Bridging**:
   - During guest-to-registered conversion, when a guest user chooses to register or log in and claims their prior guest activity, the active `guest_token` must be held in a temporary, scoped transient bridge (e.g., an in-flight operation state or dedicated migration parameter) rather than permanently co-mingled in persistent storage with Bearer tokens.
2. **Explicit Dual-Header Dispatch**:
   - A dedicated migration call must dispatch `POST /api/v1/auth/claim-guest` carrying both headers:
     - `Authorization: Bearer <registered_access_token>`
     - `X-Guest-Token: <transient_guest_token>`
3. **Deterministic Cleanup**:
   - Immediately upon receiving HTTP 200 (or terminal claim failure), the transient `guest_token` must be discarded from memory.
   - The app must then proceed exclusively in `SessionState.Authenticated`.
4. **No Relaxation of Existing Isolation**:
   - Standard operational requests must never send both headers concurrently outside the specific `/auth/claim-guest` flow.

