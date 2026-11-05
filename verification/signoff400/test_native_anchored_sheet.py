from fractions import Fraction as F
import unittest
from native_anchored_sheet import prepare, reference_mass
from native_axis_stubs import schur_eliminate, complex_solve


class AnchoredSheet(unittest.TestCase):
    def test_exact_native_DC_and_anchor_geometry(self):
        for refinement in (1, 2, 4):
            m = prepare([0, 0, 6, 4], [([2, 1], 'N')], 'latent', refinement)
            self.assertEqual(schur_eliminate(m['conductance'], m['latent_nodes']), {})
            self.assertEqual(sum(m['unit_area_mass'].values()), 24)
            index = m['template']['points'].index((F(2), F(1)))
            self.assertEqual(m['template']['point_nodes'][index], 'N')
            self.assertFalse(m['physical_RC_qualified'])

    def test_multiple_locations_share_native_identity_without_overwrite(self):
        m = prepare([0, 0, 6, 4], [([0, 0], 'N'), ([6, 4], 'N'), ([0, 0], 'N')], 'latent', 2)
        self.assertEqual(m['template']['point_nodes'].count('N'), 2)
        self.assertEqual(schur_eliminate(m['conductance'], m['latent_nodes']), {})
        rows = {}
        for (a, b), value in reference_mass(m).items():
            rows[a] = rows.get(a, F(0))+value
        self.assertTrue(all(value == 0 for value in rows.values()))

    def test_finite_frequency_response_differs_from_constant_tile_clamp(self):
        m = prepare([0, 0, 2, 2], [([1, 1], 'N')], 'latent', 2)
        g, c, inner = m['conductance'], m['unit_area_mass'], m['latent_nodes']
        def y(a, b):
            return float(g.get((a, b), 0))+1j*float(c.get((a, b), 0))
        voltages, residual = complex_solve([[y(a, b) for b in inner] for a in inner], [-y(a, 'N') for a in inner])
        current = y('N', 'N')+sum(y('N', n)*v for n, v in zip(inner, voltages))
        self.assertGreater(current.real, 0)
        self.assertGreater(abs(current-4j), 0.1)
        self.assertLessEqual(residual, 1e-12)

    def test_outside_distinct_ports_collision_split_and_unbounded_mesh_rejected(self):
        bad = [dict(anchors=[([3, 1], 'N')]),
               dict(anchors=[([0, 0], 'N'), ([2, 2], 'M')]),
               dict(anchors=[([0, 0], 'N'), ([0, 0], 'M')]),
               dict(anchors=[([0, 0], 'latent:1')]),
               dict(split=1), dict(refinement=32)]
        for change in bad:
            args = dict(box=[0, 0, 2, 2], anchors=[([1, 1], 'N')], namespace='latent')
            args.update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                prepare(**args)
