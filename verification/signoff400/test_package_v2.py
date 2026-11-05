"""Receipt linking must not introduce a circular manifest hash dependency."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from common_v2 import PROFILE, cases, save, sha, source_pins, spec
from audit_v2 import audit, FLAGS
from package_v2 import main, ROLES


class PackageControls(unittest.TestCase):
    def test_receipt_survives_campaign_manifest_link_and_detects_changed_artifact(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);artifact=root/'fixture';artifact.write_text('unit-test artifact only')
            candidate=dict(source_sha256=source_pins(),physical_sha256={str(artifact):sha(artifact)})
            manifest=dict(candidate=candidate,evidence={},handoff_artifacts={role:[str(artifact)] for role in ROLES})
            value=spec()
            for gate,flag in FLAGS.items():
                points=[(c,t) for c in value['corners'] for t in value['temperatures_c']] if gate in ('dco_model','interfaces_reset_cdc','whole_pll_lock','digital_timing') else [(None,None)]
                entries=[]
                for corner,temp_c in points:
                    r=dict(profile_sha256=sha(PROFILE),candidate_source_sha256=candidate['source_sha256'],
                           candidate_physical_sha256=candidate['physical_sha256'],
                           input_sha256={str(PROFILE):sha(PROFILE)},artifacts={str(artifact):sha(artifact)},
                           corner=corner,temperature_c=temp_c,supply_v=1.8)
                    r[flag]=True
                    if gate=='interfaces_reset_cdc':
                        inventory=root/'cdc_inventory.json'
                        save(inventory,dict(candidate_source_sha256=candidate['source_sha256'],
                             candidate_physical_sha256=candidate['physical_sha256'],
                             complete_structural_inventory_qualified=True,
                             crossings=[dict(id='test_reset',scope='command_and_reset_synchronizers')]))
                        r['input_sha256'][str(inventory)]=sha(inventory)
                        r['cdc_reliability']=dict(inventory=dict(path=str(inventory),sha256=sha(inventory)),
                             expected_crossing_ids=['test_reset'],crossings=[dict(id='test_reset',
                             event_rate_upper_hz=1,failure_rate_upper_fit=1,
                             characterization_artifact=str(artifact),event_rate_basis='fixture',resolution_time_basis='fixture')])
                    if gate=='whole_pll_lock':
                        r.update(ki=4,kp=0,records=[dict(scenario=c['scenario'],phase_offset_ns=c['phase_offset_ns'],passed=True,native_exit=0)
                                 for c in cases() if c['corner']==corner and c['temperature_c']==temp_c])
                    path=root/f'{gate}_{corner}_{temp_c}.json';save(path,r)
                    entries.append(dict(path=str(path),sha256=sha(path)))
                manifest['evidence'][gate]=entries
            self.assertTrue(audit(manifest,False)['prerequisite_gates_passed'])
            self.assertFalse(audit(manifest)['release_qualified'])
            path=root/'manifest.json';save(path,manifest);out=root/'package'
            with patch.object(sys,'argv',['package.py','--manifest',str(path),'--output',str(out)]):main()
            handoff=out/'assessment.json'
            manifest['handoff_receipt']=dict(path=str(handoff),sha256=sha(handoff));save(path,manifest)
            self.assertTrue(audit(manifest)['release_qualified'])
            (out/'gds/000_fixture').write_text('modified')
            self.assertFalse(audit(manifest)['release_qualified'])


if __name__=='__main__':unittest.main()
