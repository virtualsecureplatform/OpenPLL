"""Protection changes the power database but must retain a proven frame chain."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from common import sha
import test_parent_macro_views as fixtures
from parent_macro_views_v2 import parent_views


class ProtectionAncestry(unittest.TestCase):
    def test_protection_chain_is_accepted_only_for_its_original_frame(self):
        for unrelated in (False,True):
            with self.subTest(unrelated=unrelated),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);frame,power,route,source=fixtures.ParentMacroViews().prepare(root)
                protected=root/'protected';protected.mkdir();(protected/'power.odb').write_text('protected database')
                report=dict(main_rail_database_connectivity_pass=True,
                    input_sha256={str(power/n):sha(power/n) for n in ('assessment.json','power.odb')},
                    artifacts={str(protected/'power.odb'):sha(protected/'power.odb')})
                (protected/'assessment.json').write_text(json.dumps(report))
                path=route/'assessment.json';r=json.loads(path.read_text())
                r['input_sha256']={str(protected/n):sha(protected/n) for n in ('assessment.json','power.odb')}
                path.write_text(json.dumps(r))
                if unrelated:
                    other=root/'other';other.mkdir()
                    for p in frame.iterdir():(other/p.name).write_bytes(p.read_bytes())
                    frame=other
                with patch('parent_macro_views_v2.source_pins',return_value={str(source):sha(source)}):
                    if unrelated:
                        with self.assertRaises(ValueError):parent_views(route,protected,frame)
                    else:
                        self.assertEqual(len(parent_views(route,protected,frame)['sources']),3)


if __name__=='__main__':unittest.main()
