# SYSTEM DESGIN

**FieldShift Planner — System Design Index (`v3.2`, Local-Dataset Edition)**  
**Architecture Baseline:** `v3.2` (100% Local PostgreSQL `Schema: dataset` · Zero External Environmental APIs)  
**Scope Summary:** `34` Backend API Routes + `3` External ML Sub-Contract Routes · `13` `public` Tables + isolated `Schema: dataset` (`ml_reader`) · `39` `.env` Variables · `ADR-0`..`ADR-9`

## Documents & Machine-Readable Contracts

- [System Architecture Blueprint](SYSTEM%20DESGIN/System%20Architecture%20Blueprint.md) — End-to-end architecture, KPIs (`TBD` SLA gates), W1–W4 workflows, Guest Demo (`DEMO_PARCEL_UNVERIFIED`) & Guelma PostGIS boundary, Compose (`migrate` job), security/data-minimization, and `OQ-1..11` / `OQ-D1..D8` Open Questions.
- [Architecture Decision Records (ADR)](SYSTEM%20DESGIN/Architecture%20Decision%20Records%20(ADR).md) — `ADR-0` (`Superseded`), `ADR-1`..`ADR-6` (`Accepted`), and `ADR-7`..`ADR-9` (`Proposed`).
- [FieldShift Planner — ENDPOINTS API & Database Specification](SYSTEM%20DESGIN/System%20Architecture%20Blueprint/FieldShift%20Planner%20—%20ENDPOINTS%20api%20&%20Database%20Specification.md) — Authoritative `13`-table `public` ERD + DDL (`A.1–A.4`), `Schema: dataset` & `ml_reader` isolation (`A.5`), `34 + 3` routes & `19` error codes (`B.1–B.10`), and `39` `.env` variables (`C`).
- [Visual Input / Output Specification](SYSTEM%20DESGIN/System%20Architecture%20Blueprint/Visual%20Input%20%20Output%20Specification.md) — Flow walkthrough, input/output DB mapping, verified Draft 2020-12 fixtures (`9.1–9.4`), cancel/`SEM-07`/degraded replay/mutation checks.
- [OpenAPI 3.1.0 Specification](SYSTEM%20DESGIN/System%20Architecture%20Blueprint/openapi.yaml) — Machine-readable `/api/v1` REST API contract referencing `./schema-v5.0.json#/$defs/...`.
- [ML Wire JSON Schema (Draft 2020-12)](SYSTEM%20DESGIN/System%20Architecture%20Blueprint/schema-v5.0.json) — Machine-readable contract for `FarmAnalysisInput`, `AnalysisResult` (`additionalProperties: true`), and `CropCatalog`.
