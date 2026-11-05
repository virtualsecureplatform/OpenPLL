import unittest
from run_prototype_aperture_boundary_numerics_v2 import select, fixture_lines, compare, normalize_fixture, KINDS


def mesh():
    rows=[]
    for c in ('tt','ff','ss','sf','fs'):
        for m in ('dfrtp_1','dfrtp_2','dfrtp_4','dfstp_1','dfstp_2'):
            for d in (20,200,2000):
                for k in (20,200,400):
                    lo=-{20:25,200:75,2000:750}[d];hi={20:25,200:75,400:150}[k]
                    rows.append(dict(corner=c,master=m,input_full_ramp_ps=d,clock_full_ramp_ps=k,
                        brackets={kind:dict(latest_sampled_clean_before_ps=lo,earliest_sampled_clean_after_ps=hi) for kind in KINDS},
                        records=[dict(kind=kind,offset_ps=offset,clean_capture_of_new_value=offset<0,
                                      clean_retention_of_pretest_value=offset>0) for kind in KINDS for offset in (lo,hi)]))
    return rows


class BoundaryNumericsTests(unittest.TestCase):
    def test_electrically_equal_numeric_spellings_normalize(self):
        self.assertEqual(normalize_fixture('CLOAD0 Q0 0 250f'),normalize_fixture('CLOAD0 Q0 0.0 250.0f'))
        self.assertEqual(normalize_fixture('PWL(0n 0 20n 1.8)'),normalize_fixture('PWL(0 0.0 2e-8 1.800)'))
        self.assertIn('dfrtp_1',normalize_fixture('Xcell0 Q0 sky130_fd_sc_hs__dfrtp_1'))
    def test_worst_and_fast_boundaries_are_all_selected(self):
        targets=select(mesh())
        self.assertEqual(len(targets),300)
        self.assertEqual(sum(len(t['selection_tags']) for t in targets),300)
        for target in targets:
            if 'worst_setup' in target['selection_tags']:self.assertEqual(target['offset_ps'],-750)
            if 'worst_hold' in target['selection_tags']:self.assertEqual(target['offset_ps'],150)
            if any(tag.startswith('fast_') for tag in target['selection_tags']):
                self.assertEqual((target['data_ramp_ps'],target['clock_ramp_ps']),(20,20))

    def test_partial_or_unclean_reference_rejected(self):
        rows=mesh()
        with self.assertRaises(ValueError):select(rows[:-1])
        for row in rows:
            for record in row['records']:record['clean_capture_of_new_value']=False
        with self.assertRaises(ValueError):select(rows)

    def test_fixture_alpha_rename_preserves_unrelated_names_and_load(self):
        source='''VD12 D12 0 PWL(0 0 20n 1.8)
VCTRL12 CTRL12 0 1.8
Xcell12 CLK D12 Q12 private_12_3 private_120_3 D120 sky130_fd_sc_hs__dfrtp_1
CLOAD12 Q12 0 400f
'''
        lines=fixture_lines(source,12)
        self.assertEqual(lines[0],'VD0 D0 0 PWL(0 0 20n 1.8)')
        self.assertIn('private_0_3 private_120_3 D120',lines[2])
        self.assertEqual(lines[3],'CLOAD0 Q0 0 400f')
        with self.assertRaises(ValueError):fixture_lines(source.replace('CLOAD12','CLOAD13'),12)

    def test_output_delta_checked_against_existing_allowance(self):
        def rows(shift):
            times=(0,1,2,10,12,17.5,18.5,19,19.9,20,20.1+shift,20.2+shift,21.9,22,27,28,30)
            return [(t*1e-9,1.8 if 10<=t<12 or 20<=t<22 else 0,
                     1.8 if t>=20.2+shift else 0,1.8 if t>=20 else 0,1.8 if t>=2 else 0) for t in times]
        case=dict(pretest_expected=0,new_value=1)
        result=compare(rows(0),rows(.001),case,'setup',10)
        self.assertAlmostEqual(result['maximum_output_crossing_delta_ps'],1,places=5)
        with self.assertRaises(ValueError):compare(rows(0),rows(.02),case,'setup',10)
