"""No API key/network required: check exact TSP on synthetic directed matrices."""
import itertools
import unittest
import numpy as np
from route_optimizer import held_karp, demo_matrices, route_total, MAX_STOPS


class TSPTests(unittest.TestCase):
    def test_demo(self):
        D, T = demo_matrices()
        self.assertEqual(D.shape, (4, 4))
        self.assertEqual(T.shape, (4, 4))
        route, total = held_karp(D)
        self.assertEqual(route[0], 0)
        self.assertEqual(route[-1], 0)
        self.assertEqual(set(route[:-1]), set(range(4)))
        self.assertAlmostEqual(total, route_total(D, route))

    def test_random_directed_against_enumeration(self):
        rng = np.random.default_rng(42)
        for n in range(2, 9):
            with self.subTest(n=n):
                D = rng.integers(1, 100, size=(n, n)).astype(float)
                np.fill_diagonal(D, 0)
                route, total = held_karp(D)
                exact = min(
                    route_total(D, (0,) + order + (0,))
                    for order in itertools.permutations(range(1, n))
                )
                self.assertAlmostEqual(total, exact)
                self.assertEqual(len(route), n + 1)

    def test_bad_matrix(self):
        with self.assertRaises(ValueError):
            held_karp([[0, np.nan], [2, 0]])
        with self.assertRaises(ValueError):
            held_karp([[0, -1], [2, 0]])


if __name__ == "__main__":
    unittest.main()
