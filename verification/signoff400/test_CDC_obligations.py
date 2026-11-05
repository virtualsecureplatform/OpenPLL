import copy
import json
from pathlib import Path
import unittest
from common import ROOT
from prepare_CDC_obligations import build


class CDCObligationControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base=ROOT/'build/signoff400'
        cls.profile=json.loads((ROOT/'verification/signoff400/requirements_v2.json').read_text())
        cls.mapped=json.loads((base/'startup_corrected_digital_001/mapped.json').read_text())['modules']['IntegerPLL_ProgrammedCore']
        cls.routed=json.loads((base/'startup_timing_routed_CDC_inventory_001/routed.json').read_text())['modules']['IntegerPLL_ProgrammedCore']
        cls.inventory=json.loads((base/'startup_timing_mapped_CDC_inventory_001/inventory.json').read_text())

    def test_actual_scope_bundle_pruning_and_no_implicit_waivers(self):
        result=build(self.profile,self.mapped,self.routed,self.inventory)
        self.assertEqual(sum(c['in_aggregate_one_FIT_scope'] for c in result['synchronizers']),11)
        self.assertEqual(sum(c['role']=='bbpd_decision_noise' for c in result['synchronizers']),2)
        self.assertEqual([len(b['implemented_destination_registers']) for b in result['bundles']],[2,29])
        self.assertEqual(len(result['crossing_candidates']),421)
        self.assertTrue(all(not c['waived'] for c in result['crossing_candidates']))
        self.assertTrue(all(c['declared_event_rate_upper_hz'] is None for c in result['synchronizers']))
        self.assertFalse(result['physical_CDC_qualified'])

    def test_missing_chain_unknown_marked_state_and_cell_polarity_change_rejected(self):
        for fault in ('missing_chain','extra_marked_state','polarity','profile_scope'):
            with self.subTest(fault=fault):
                inv=copy.deepcopy(self.inventory);route=copy.deepcopy(self.routed);profile=copy.deepcopy(self.profile)
                if fault=='missing_chain':inv['directly_connected_marked_two_stage_chains'].pop()
                if fault=='extra_marked_state':
                    state=next(s for s in inv['sequential_state'] if not any(a['async_reg'] for a in s['output_aliases']))
                    state['output_aliases'].append(dict(name='unreviewed',index=0,async_reg=True))
                if fault=='polarity':
                    chain=inv['directly_connected_marked_two_stage_chains'][0];name=chain['first_cell']
                    actual=next(n for n in route['cells'] if n.lstrip('\\')==name)
                    route['cells'][actual]['type']='sky130_fd_sc_hs__dfstp_1'
                if fault=='profile_scope':profile['cdc_reliability']['scope']='bbpd_only'
                with self.assertRaises(ValueError):build(profile,self.mapped,route,inv)


if __name__=='__main__':unittest.main()
