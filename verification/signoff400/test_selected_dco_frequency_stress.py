"""Protect native-data identity and reject mislabeled frequency stress packets."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from common_v3 import ROOT
from selected_dco_frequency_stress_v2 import apply,transform


class FrequencyStressControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base = ROOT/'build/signoff400'
        cls.registry = base/'selected_TT_stress_registry_945/models.json'
        r = json.loads(cls.registry.read_text())
        cls.measured = {(p['coarse'],p['fine']):round(p['frequency_hz']*1000) for p in r['points']}
        cls.dense = {}
        for line in (base/'selected_stress_delivery_baseline_946/dco_table.txt').read_text().splitlines():
            c,f,v = map(int,line.split());cls.dense[c,f] = v
        cls.packets = {n:json.loads((base/'selected_TT_frequency_stress_packets_944'/(n+'.json')).read_text())
                       for n in ('nominal','gain')}

    def test_nominal_is_exact_without_mutating_native_data(self):
        dense,measured = copy.deepcopy(self.dense),copy.deepcopy(self.measured)
        self.assertEqual(transform(dense,measured,self.packets['nominal']),self.dense)
        self.assertEqual(dense,self.dense);self.assertEqual(measured,self.measured)

    def test_gain_preserves_lookup_domain_and_positive_ordering(self):
        result = transform(self.dense,self.measured,self.packets['gain'])
        self.assertEqual(set(result),set(self.dense))
        self.assertNotEqual(result,self.dense)
        values = [result[k] for k in sorted(result)]
        self.assertTrue(all(b>a>0 for a,b in zip(values,values[1:])))

    def test_interpolated_point_cannot_be_a_measured_anchor(self):
        packet = dict(self.packets['gain'],anchor_fine=113)
        with self.assertRaisesRegex(ValueError,'measured anchor'):
            transform(self.dense,self.measured,packet)

    def rejected_packet(self,packet,message):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'stress.json';path.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError,message):
                apply(self.dense,self.measured,self.registry,path)

    def test_TT_observations_cannot_be_relabeled_as_SS(self):
        packet = copy.deepcopy(self.packets['gain'])
        packet['operating_point']['corner'] = 'ss'
        self.rejected_packet(packet,'TT observations cannot stress another process corner')

    def test_changed_observed_gain_is_rejected(self):
        self.rejected_packet(dict(self.packets['gain'],gain_multiplier=.5),'parameters differ')

    def test_nonpositive_frequency_is_rejected(self):
        packet = dict(self.packets['nominal'],offset_ppm_at_anchor=-1000000)
        with self.assertRaisesRegex(ValueError,'positive integer'):
            transform(self.dense,self.measured,packet)


if __name__ == '__main__':
    unittest.main()
