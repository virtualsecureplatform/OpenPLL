from copy import deepcopy
import unittest
from compare_prototype_final_capture_numerics import compare_cases, fixture_signature


class FinalCaptureNumericsTests(unittest.TestCase):
    def case(self):
        return {('data_rise',-250):dict(final_value=1,clean_capture_of_new_value=True,
            clean_retention_of_pretest_value=False,unresolved_or_glitching=False,
            output_crossings=[dict(clock_relative_ps=125,direction=1)])}

    def test_measured_displacement_preserved(self):
        a=self.case();b=deepcopy(a);b['data_rise',-250]['output_crossings'][0]['clock_relative_ps']=127.5
        differences,edges=compare_cases(a,b)
        self.assertEqual(differences,[]);self.assertEqual(edges,[2.5])

    def test_changed_capture_and_extra_crossing_are_not_hidden_by_zip(self):
        a=self.case();b=deepcopy(a)
        b['data_rise',-250]['output_crossings'].append(dict(clock_relative_ps=200,direction=0))
        differences,edges=compare_cases(a,b)
        self.assertEqual(len(differences),1);self.assertEqual(edges,[])
        b=deepcopy(a);b['data_rise',-250]['final_value']=0
        self.assertEqual(len(compare_cases(a,b)[0]),1)

    def test_missing_phase_point_rejected(self):
        with self.assertRaisesRegex(ValueError,'phase grids differ'):compare_cases(self.case(),{})

    def test_numerical_changes_do_not_hide_changed_physical_fixture(self):
        a=('.include "/first/cell.spice"\n.option klu reltol=1e-5 abstol=1e-9 num_threads=1\n'
           '.temp 27\nVDD VDD 0 1.8\nVD D 0 PWL(0 0 20n 1.8)\n'
           'tran 5p 30n 0 5p\nwrdata /first/wave.dat v(clk) v(q)\n')
        b=a.replace('/first/','/second/').replace('1e-5','1e-6').replace('1e-9','1e-10').replace('5p','2.5p')
        self.assertEqual(fixture_signature(a,'/first/cell.spice'),fixture_signature(b,'/second/cell.spice'))
        for changed in (b.replace('VDD VDD 0 1.8','VDD VDD 0 1.9'), b.replace('.temp 27','.temp 125'),
                        b.replace('20n 1.8','21n 1.8')):
            self.assertNotEqual(fixture_signature(a,'/first/cell.spice'),fixture_signature(changed,'/second/cell.spice'))


if __name__=='__main__':unittest.main()
