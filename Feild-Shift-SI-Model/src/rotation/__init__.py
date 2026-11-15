"""Crop Rotation Candidate Generator (Phase H) — deterministic, constraint-aware sequence construction without ranking."""

from src.rotation.candidate_generator import (
    GenerationConfig,
    generate_rotation_candidates,
)

__all__ = [
    "GenerationConfig",
    "generate_rotation_candidates",
]
