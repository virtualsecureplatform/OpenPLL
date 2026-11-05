from copy import deepcopy
import unittest
from audit_prototype_final_campaign_coverage import corrected_summary


class CampaignCoverageTests(unittest.TestCase):
    def records(self,kind):
        axes={'expanded':[(200,200),(200,400),(2000,200),(2000,400)],
              'fast':[(20,20),(20,200),(20,400),(200,20),(2000,20)],
              'pulse':[(None,20),(None,400)]}[kind]
        rows=[]
        for corner in ('tt','ff','ss','sf','fs'):
            for master,load in [('dfrtp_1',250),('dfrtp_2',400),('dfrtp_4',600),('dfstp_1',125),('dfstp_2',400)]:
                for data,clock in axes:
                    rows.append(dict(corner=corner,master=master,load_fF=load,data_ramp_ps=data,
                                     clock_ramp_ps=clock,native_cases=8 if kind=='pulse' else 30))
        return rows

    def test_actual_counts_replace_copied_single_master_summary(self):
        for kind,points,cases in [('expanded',100,3000),('fast',125,3750),('pulse',50,400)]:
            result=corrected_summary(kind,self.records(kind))
            self.assertEqual(result['complete_native_operating_points'],points)
            self.assertEqual(result['native_cases'],cases)
            self.assertEqual(len(result['masters']),5)

    def test_equal_case_count_cannot_hide_missing_corner_or_duplicate(self):
        rows=self.records('expanded');rows[-1]=deepcopy(rows[0])
        with self.assertRaisesRegex(ValueError,'duplicate'):corrected_summary('expanded',rows)
        with self.assertRaisesRegex(ValueError,'incomplete'):corrected_summary('expanded',self.records('expanded')[:-1])

    def test_wrong_native_load_rejected(self):
        rows=self.records('pulse');rows[0]['load_fF']=100
        with self.assertRaisesRegex(ValueError,'load mismatch'):corrected_summary('pulse',rows)


if __name__=='__main__':unittest.main()
