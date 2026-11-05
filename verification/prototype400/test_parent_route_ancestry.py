"""A targeted route must retain its original parent power ancestry."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from common import sha
import test_parent_macro_views as fixtures
from parent_macro_views_v3 import parent_views


class TargetedRouteAncestry(unittest.TestCase):
    def test_targeted_route_ancestor_requires_matching_database_and_receipt(self):
        for corrupt in (False,True):
            with self.subTest(corrupt=corrupt),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);frame,power,route,source=fixtures.ParentMacroViews().prepare(root)
                (route/'route.odb').write_text('source route')
                targeted=root/'targeted';targeted.mkdir()
                data=dict(router_drc_violations=0,exact_macro_bindings_preserved=True,
                    input_sha256={str(route/n):sha(route/n) for n in ('assessment.json','route.odb')},artifacts={})
                if corrupt:data['input_sha256'].pop(str(route/'assessment.json'))
                (targeted/'assessment.json').write_text(json.dumps(data))
                with patch('parent_macro_views_v3.source_pins',return_value={str(source):sha(source)}):
                    if corrupt:
                        with self.assertRaises(ValueError):parent_views(targeted,power,frame)
                    else:self.assertEqual(len(parent_views(targeted,power,frame)['sources']),3)


if __name__=='__main__':unittest.main()
