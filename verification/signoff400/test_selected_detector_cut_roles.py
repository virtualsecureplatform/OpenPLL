import unittest
from classify_selected_detector_cut import classify

class DetectorCutRoleTests(unittest.TestCase):
    def test_terminals_are_grouped_by_physical_cell_without_losing_unknown_roles(self):
        item=dict(physical_hierarchy_identity=[['parent','instance']],leaf_master='buffer')
        other=dict(physical_hierarchy_identity=[['parent','other']],leaf_master='buffer')
        result=classify({'X0':[dict(terminal_index=0,node='a',component='a')],
                         'X1':[dict(terminal_index=2,node='b',component='b')],
                         'X2':[dict(terminal_index=0,node='c',component='c')]},
                        {'X0':item,'X1':item,'X2':other},{'a':{'REF'},'b':{'RESET_N'}})
        self.assertEqual(len(result),2)
        shared=next(v for v in result.values() if len(v['primitives'])==2)
        self.assertEqual(shared['roles'],['REF','RESET_N'])
        self.assertFalse(shared['has_unattributed_terminal'])
        self.assertTrue(next(v for v in result.values() if len(v['primitives'])==1)['has_unattributed_terminal'])

if __name__=='__main__':unittest.main()
