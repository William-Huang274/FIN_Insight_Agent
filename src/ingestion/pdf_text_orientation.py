"""Preserve character-matrix orientation evidence for PDF parser routing.

A proposed page-view rotation does not rewrite the original or establish text
reading order. Mixed directions remain explicit and require region handling.
"""
from collections import Counter
import math
from typing import Any, Mapping, Sequence


def character_orientation_profile(chars: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    for char in chars:
        if not str(char.get('text') or '').strip():
            continue
        matrix = char.get('matrix')
        try:
            a, b = float(matrix[0]), float(matrix[1])
            if not math.isfinite(a) or not math.isfinite(b) or math.hypot(a, b) < 1e-9:
                raise ValueError('invalid_transform')
            angle = math.degrees(math.atan2(b, a)) % 360
            quarter = (round(angle / 90) * 90) % 360
            delta = abs((angle - quarter + 180) % 360 - 180)
            key = str(quarter) if delta <= 2 else 'non_orthogonal'
        except (TypeError, IndexError, ValueError, KeyError):
            key = 'unknown'
        counts[key] += 1
    total = sum(counts.values())
    orthogonal = {key: count for key, count in counts.items() if key in {'0', '90', '180', '270'}}
    dominant = max(orthogonal, key=orthogonal.get) if orthogonal else None
    share = orthogonal.get(dominant, 0) / total if total else 0.0
    supported = total >= 20 and share >= 0.95
    return {
        'schema_version': 'fin_pdf_character_orientation_v1',
        'nonblank_characters': total,
        'matrix_direction_counts': dict(sorted(counts.items())),
        'dominant_clockwise_view_rotation': int(dominant) if dominant is not None else None,
        'dominant_share': share,
        'suggested_clockwise_view_rotation': int(dominant) if supported else None,
        'status': 'dominant_direction_candidate' if supported else 'insufficient_or_mixed_direction',
        'policy': {'orthogonal_tolerance_degrees': 2, 'minimum_characters': 20,
                   'minimum_dominant_share': 0.95},
        'minority_directions_retained': True,
        'automatic_original_rewrite': False,
    }
