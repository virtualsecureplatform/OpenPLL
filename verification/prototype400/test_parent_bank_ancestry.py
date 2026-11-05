import json
from pathlib import Path
import tempfile
import unittest
from common import sha
from parent_bank_ancestry import existing_extra_banks


def stage(root,name,parent=None,site=None):
    out=root/name;out.mkdir();odb=out/'route.odb';odb.write_text(name)
    inputs={} if parent is None else {str(parent/n):sha(parent/n) for n in ('assessment.json','route.odb')}
    proof=dict(input_sha256=inputs,artifacts={str(odb):sha(odb)})
    if site is not None:
        plan=out/'extra.json';plan.write_text(json.dumps([dict(x_nm=site,y_nm=3330)]))
        proof.update(extra_placement_plan=str(plan));proof['artifacts'][str(plan)]=sha(plan)
    (out/'assessment.json').write_text(json.dumps(proof))
    return out


class BankAncestry(unittest.TestCase):
    def test_all_prior_stage_plans_are_reserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);base=stage(root,'base');first=stage(root,'first',base,480);last=stage(root,'last',first,960)
            plans,receipts,rows=existing_extra_banks(last/'assessment.json')
            self.assertEqual(set(plans),{first/'extra.json',last/'extra.json'})
            self.assertEqual(receipts,[last/'assessment.json',first/'assessment.json',base/'assessment.json'])
            self.assertEqual({row['x_nm'] for row in rows},{480,960})

    def test_changed_ancestor_plan_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);base=stage(root,'base',site=480);last=stage(root,'last',base,960)
            (base/'extra.json').write_text('[]')
            with self.assertRaises(ValueError):existing_extra_banks(last/'assessment.json')

    def test_unpinned_source_receipt_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);base=stage(root,'base');last=stage(root,'last',base,960)
            path=last/'assessment.json';proof=json.loads(path.read_text());del proof['input_sha256'][str(base/'assessment.json')];path.write_text(json.dumps(proof))
            with self.assertRaises(ValueError):existing_extra_banks(path)

    def test_duplicate_sites_in_separate_stages_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);base=stage(root,'base',site=480);last=stage(root,'last',base,480)
            with self.assertRaises(ValueError):existing_extra_banks(last/'assessment.json')

    def test_ambiguous_source_routes_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);base=stage(root,'base');other=stage(root,'other');last=stage(root,'last',base,960)
            path=last/'assessment.json';proof=json.loads(path.read_text());proof['input_sha256'][str(other/'route.odb')]=sha(other/'route.odb');path.write_text(json.dumps(proof))
            with self.assertRaises(ValueError):existing_extra_banks(path)


if __name__=='__main__':unittest.main()
