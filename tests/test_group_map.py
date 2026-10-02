"""Classical MDS reproduces a configuration that is truly two-dimensional."""

import numpy as np

from api.group_map import classical_mds


def test_recovers_planar_distances_exactly():
    points = np.array([[0, 0], [3, 0], [0, 4], [1, 1], [5, 2]], dtype=float)
    d = np.linalg.norm(points[:, None] - points[None, :], axis=-1)
    coords = classical_mds(d)
    d2 = np.linalg.norm(coords[:, None] - coords[None, :], axis=-1)
    assert np.allclose(d, d2)


def test_empty_and_deterministic():
    assert classical_mds(np.zeros((0, 0))).shape == (0, 2)
    d = np.random.default_rng(0).random((6, 6))
    d = (d + d.T) / 2
    np.fill_diagonal(d, 0)
    assert np.array_equal(classical_mds(d), classical_mds(d))
