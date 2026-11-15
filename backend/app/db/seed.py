from __future__ import annotations

import json
from typing import Any

from sqlalchemy import Connection, text
from sqlalchemy.ext.asyncio import AsyncConnection

# TODO(OQ-D7): Replace simplified 10-vertex Guelma Wilaya polygon with official surveyed
# administrative GIS boundary once provided by GIS/ML teams.
# TODO(OQ-9): Confirm exact Guelma regional polygon boundaries with project/GIS owners.
GUELMA_LOCATION_ID = 1
GUELMA_CODE = "guelma"
GUELMA_NAME = "Guelma"
GUELMA_COUNTRY = "Algeria"
GUELMA_REGION = "Guelma"
GUELMA_BOUNDARY_GEOJSON: dict[str, Any] = {
    "type": "MultiPolygon",
    "coordinates": [
        [
            [
                [7.12, 36.08],
                [7.38, 36.05],
                [7.68, 36.07],
                [7.90, 36.22],
                [7.88, 36.48],
                [7.72, 36.63],
                [7.42, 36.65],
                [7.14, 36.58],
                [7.00, 36.36],
                [7.12, 36.08],
            ]
        ]
    ],
}

# TODO(OQ-D1): Exact `Schema: dataset` tables/columns/units remain TBD by ML team.
DEFAULT_DATASET_VERSION = "2026.11-guelma-v1"
DEFAULT_DATASET_SOURCE = (
    "Curated Guelma regional agro-climatic and soil baseline dataset (Local-Dataset Edition)."
)
DEFAULT_DATASET_COVERAGE = "Wilaya of Guelma administrative MVP zone."
DEFAULT_DATASET_NOTES = "Initial MVP pinned dataset version; schema dataset tables TBD (OQ-D1)."


def seed_reference_data_sync(conn: Connection) -> None:
    """Idempotently seed Guelma demo zone, active dataset registry row, and breaker singleton.

    Note (`IMPL-009` / `DI-15`): `public.crop_catalog` is deliberately NOT seeded here so
    cold-start behavior preserves `GET /catalog -> 502 ML_UNAVAILABLE` until live/mock ML sync.
    """
    conn.execute(
        text(
            """
            INSERT INTO public.demo_locations (
                id,
                code,
                name,
                country,
                region,
                boundary,
                is_active
            )
            VALUES (
                :id,
                :code,
                :name,
                :country,
                :region,
                ST_SetSRID(ST_GeomFromGeoJSON(:boundary_geojson), 4326),
                true
            )
            ON CONFLICT (code) DO NOTHING
            """
        ),
        {
            "id": GUELMA_LOCATION_ID,
            "code": GUELMA_CODE,
            "name": GUELMA_NAME,
            "country": GUELMA_COUNTRY,
            "region": GUELMA_REGION,
            "boundary_geojson": json.dumps(GUELMA_BOUNDARY_GEOJSON),
        },
    )

    conn.execute(
        text(
            """
            SELECT setval(
                pg_get_serial_sequence('public.demo_locations', 'id'),
                COALESCE((SELECT MAX(id) FROM public.demo_locations), 1),
                true
            )
            """
        )
    )

    conn.execute(
        text(
            """
            INSERT INTO public.dataset_registry (
                dataset_version,
                source_description,
                coverage_notes,
                is_active,
                notes
            )
            SELECT
                :dataset_version,
                :source_description,
                :coverage_notes,
                true,
                :notes
            WHERE NOT EXISTS (
                SELECT 1
                FROM public.dataset_registry
                WHERE dataset_version = :dataset_version OR is_active = true
            )
            """
        ),
        {
            "dataset_version": DEFAULT_DATASET_VERSION,
            "source_description": DEFAULT_DATASET_SOURCE,
            "coverage_notes": DEFAULT_DATASET_COVERAGE,
            "notes": DEFAULT_DATASET_NOTES,
        },
    )

    conn.execute(
        text(
            """
            INSERT INTO public.ml_breaker_state (
                id,
                state,
                consecutive_failures,
                opened_at,
                half_open_probe_at
            )
            VALUES (1, 'closed', 0, NULL, NULL)
            ON CONFLICT (id) DO NOTHING
            """
        )
    )


async def seed_reference_data(conn: AsyncConnection) -> None:
    """Async entrypoint wrapping `seed_reference_data_sync` for app/test helpers."""
    await conn.run_sync(seed_reference_data_sync)


def unseed_reference_data_sync(conn: Connection) -> None:
    """Reverse initial seed rows during Alembic downgrade."""
    conn.execute(text("DELETE FROM public.ml_breaker_state WHERE id = 1"))
    conn.execute(
        text("DELETE FROM public.dataset_registry WHERE dataset_version = :dataset_version"),
        {"dataset_version": DEFAULT_DATASET_VERSION},
    )
    conn.execute(
        text("DELETE FROM public.demo_locations WHERE id = :id AND code = :code"),
        {"id": GUELMA_LOCATION_ID, "code": GUELMA_CODE},
    )
