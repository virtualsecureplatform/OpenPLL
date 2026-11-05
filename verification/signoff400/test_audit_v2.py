import copy
import json
from pathlib import Path
import tempfile
import unittest

from common_v2 import PROFILE, save, sha, source_pins
from audit_v2 import audit, receipt


class AuditControls(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        physical=self.root/'layout.gds';physical.write_bytes(b'test fixture, not real GDS')
        self.candidate=dict(source_sha256=source_pins(),physical_sha256={str(physical):sha(physical)})
        self.manifest=dict(candidate=self.candidate,evidence={})

    def test_missing_evidence_never_qualifies(self):
        result=audit(self.manifest)
        self.assertFalse(result['release_qualified'])
        self.assertTrue(all(not gate['passed'] for gate in result['gates'].values()))

    def test_diagnostic_stale_profile_and_artifact_changes_rejected(self):
        artifact=self.root/'native.txt';artifact.write_text('fixture')
        report=dict(profile_sha256=sha(PROFILE),candidate_source_sha256=self.candidate['source_sha256'],
                    candidate_physical_sha256=self.candidate['physical_sha256'],
                    input_sha256={str(PROFILE):sha(PROFILE)},artifacts={str(artifact):sha(artifact)},
                    dco_model_qualified=True)
        for change in (dict(diagnostic=True),dict(synthetic=True),dict(profile_sha256='0'*64),
                       dict(candidate_physical_sha256={}),dict(artifacts={}),dict(dco_model_qualified=False)):
            path=self.root/'receipt.json';save(path,dict(report,**change))
            with self.assertRaises(ValueError):receipt(path,sha(path),self.candidate,'dco_model_qualified')
        path=self.root/'receipt.json';save(path,report)
        artifact.write_text('changed')
        with self.assertRaises(ValueError):receipt(path,sha(path),self.candidate,'dco_model_qualified')

    def test_single_point_cannot_qualify_temperature_grid(self):
        artifact=self.root/'native.txt';artifact.write_text('fixture')
        path=self.root/'receipt.json'
        report=dict(profile_sha256=sha(PROFILE),candidate_source_sha256=self.candidate['source_sha256'],
                    candidate_physical_sha256=self.candidate['physical_sha256'],
                    input_sha256={str(PROFILE):sha(PROFILE)},artifacts={str(artifact):sha(artifact)},
                    dco_model_qualified=True,corner='tt',temperature_c=27,supply_v=1.8)
        save(path,report)
        self.manifest['evidence']['dco_model']=[dict(path=str(path),sha256=sha(path))]
        result=audit(self.manifest)
        self.assertFalse(result['gates']['dco_model']['passed'])
        self.assertIn('qualified PVT coverage 1/15',result['gates']['dco_model']['failures'])
        self.assertFalse(result['release_qualified'])

    def test_invalid_gain_and_truthy_scenario_flags_are_rejected(self):
        from common_v2 import cases
        artifact=self.root/'native.txt';artifact.write_text('fixture')
        path=self.root/'loop.json'
        report=dict(profile_sha256=sha(PROFILE),candidate_source_sha256=self.candidate['source_sha256'],
                    candidate_physical_sha256=self.candidate['physical_sha256'],
                    input_sha256={str(PROFILE):sha(PROFILE)},artifacts={str(artifact):sha(artifact)},
                    whole_pll_qualification_pass=True,corner='tt',temperature_c=27,supply_v=1.8,ki=4,kp=0,
                    records=[dict(scenario=c['scenario'],phase_offset_ns=c['phase_offset_ns'],passed=True,native_exit=0)
                             for c in cases() if c['corner']=='tt' and c['temperature_c']==27])
        for change,fragment in ((dict(ki=0),'gain pair'),(dict(kp=True),'gain pair'),
                                (dict(records=[dict(r,passed='true') for r in report['records']]),'scenario coverage'),
                                (dict(records=[dict(r,native_exit=False) for r in report['records']]),'scenario coverage')):
            save(path,dict(report,**change))
            self.manifest['evidence']['whole_pll_lock']=[dict(path=str(path),sha256=sha(path))]
            found=audit(self.manifest)['gates']['whole_pll_lock']
            self.assertFalse(found['passed'])
            self.assertTrue(any(fragment in failure for failure in found['failures']))


class CDCControls(AuditControls):
    def setUp(self):
        super().setUp()
        self.characterization = self.root/'characterization.json'
        self.characterization.write_text('{}')
        self.inventory = self.root/'inventory.json'
        save(self.inventory, dict(candidate_source_sha256=self.candidate['source_sha256'],
             candidate_physical_sha256=self.candidate['physical_sha256'],
             complete_structural_inventory_qualified=True,
             crossings=[dict(id='reset', scope='command_and_reset_synchronizers'),
                        dict(id='request', scope='command_and_reset_synchronizers'),
                        dict(id='bbpd', scope='bbpd_decision_noise')]))
        crossing = dict(event_rate_upper_hz=25e6, failure_rate_upper_fit=.5,
                        characterization_artifact=str(self.characterization),
                        event_rate_basis='protocol bound', resolution_time_basis='routed timing')
        self.report = dict(input_sha256={str(self.inventory):sha(self.inventory)},
             artifacts={str(self.characterization):sha(self.characterization)},
             candidate_source_sha256=self.candidate['source_sha256'],
             candidate_physical_sha256=self.candidate['physical_sha256'],
             cdc_reliability=dict(inventory=dict(path=str(self.inventory),sha256=sha(self.inventory)),
                  expected_crossing_ids=['reset','request'],
                  crossings=[dict(crossing,id='reset'),dict(crossing,id='request')]))

    def test_aggregate_boundary_and_bbpd_exclusion(self):
        from audit_v2 import validate_cdc
        validate_cdc(self.report)
        self.report['cdc_reliability']['crossings'][1]['failure_rate_upper_fit']=.50001
        with self.assertRaises(ValueError):validate_cdc(self.report)

    def test_inventing_smaller_expected_inventory_rejected(self):
        from audit_v2 import validate_cdc
        self.report['cdc_reliability']['expected_crossing_ids']=['reset']
        self.report['cdc_reliability']['crossings']=self.report['cdc_reliability']['crossings'][:1]
        with self.assertRaises(ValueError):validate_cdc(self.report)

    def test_unpinned_characterization_and_invalid_rates(self):
        from audit_v2 import validate_cdc
        for field,value in [('failure_rate_upper_fit',float('nan')),
                            ('failure_rate_upper_fit',float('inf')),
                            ('failure_rate_upper_fit',True),('failure_rate_upper_fit',-1),
                            ('event_rate_upper_hz',-1),('event_rate_upper_hz',float('nan')),
                            ('characterization_artifact','unregistered'),('event_rate_basis',''),
                            ('resolution_time_basis','')]:
            bad=copy.deepcopy(self.report)
            bad['cdc_reliability']['crossings'][0][field]=value
            with self.subTest(field=field,value=value),self.assertRaises(ValueError):validate_cdc(bad)

    def test_changed_inventory_rejected(self):
        from audit_v2 import validate_cdc
        self.inventory.write_text('{}')
        with self.assertRaises(ValueError):validate_cdc(self.report)


if __name__=='__main__':unittest.main()
