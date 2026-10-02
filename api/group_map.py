"""
group_map.py

2D positions for the group map, from classical multidimensional scaling
(Torgerson, 1952) of the weighted Gower distances. Used for display only.
"""

from __future__ import annotations

import numpy as np


def classical_mds(distance: np.ndarray, dimensions: int = 2) -> np.ndarray:
    """n x dimensions coordinates whose Euclidean distances approximate `distance`."""
    n = len(distance)
    if n == 0:
        return np.zeros((0, dimensions))
    centring = np.eye(n) - np.ones((n, n)) / n
    b = -0.5 * centring @ (distance ** 2) @ centring
    values, vectors = np.linalg.eigh(b)
    order = np.argsort(values)[::-1][:dimensions]
    scale = np.sqrt(np.clip(values[order], 0, None))
    coords = vectors[:, order] * scale
    # Fix the sign of each axis so the picture is the same on every run.
    signs = np.sign(coords[np.argmax(np.abs(coords), axis=0), range(coords.shape[1])])
    signs[signs == 0] = 1
    return coords * signs
