import copy,unittest
from selected_mixed_signal_build_cache_v2 import check_identity

class BuildCacheIdentity(unittest.TestCase):
    def test_source_and_tool_changes_rejected(self):
        expected={'rtl':'a','detector':'b','vvp':'c'}
        record=dict(state='selected_RTL_VPI_build_complete',build_inputs=expected,image_fingerprint=[1,2,3,4,5])
        check_identity(record,expected,[1,2,3,4,5])
        for key in expected:
            changed=copy.deepcopy(expected);changed[key]='changed'
            with self.subTest(key=key),self.assertRaises(ValueError):check_identity(record,changed,[1,2,3,4,5])
    def test_incomplete_cache_and_changed_image_rejected(self):
        record=dict(state='selected_RTL_VPI_build_complete',build_inputs={},image_fingerprint=[1,2,3,4,5])
        with self.assertRaises(ValueError):check_identity(record,{},[1,2,3,4,6])
        record['state']='building'
        with self.assertRaises(ValueError):check_identity(record,{},[1,2,3,4,5])

if __name__=='__main__':unittest.main()
