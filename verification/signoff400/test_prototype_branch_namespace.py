import unittest
from prototype_electrical_branch_eco_v13 import actions_for_plan


class BranchNamespaceTests(unittest.TestCase):
    def plan(self):
        return dict(targets=[dict(capture_cell='prototype_wire_closure008_source_0',
                    capture_master='sky130_fd_sc_hs__clkbuf_8',replacement_master='sky130_fd_sc_hs__clkbuf_16')],
                    branches=[],source_buffers=[dict(driver=dict(cell='old_gate',pin='Y',master='sky130_fd_sc_hs__o21ai_2'),
                    buffer_master='sky130_fd_sc_hs__clkbuf_8')],short_data_targets=[])

    def test_existing_instance_names_are_not_rewritten(self):
        text=actions_for_plan(self.plan(),'prototype_wire_closure009')
        self.assertIn('replace_cell {prototype_wire_closure008_source_0}',text)
        self.assertIn('findInst prototype_wire_closure009_source_0',text)

    def test_successive_candidates_get_distinct_created_instances(self):
        a=actions_for_plan(self.plan(),'prototype_wire_closure009')
        b=actions_for_plan(self.plan(),'prototype_wire_closure010')
        self.assertIn('prototype_wire_closure009_source_0',a)
        self.assertNotIn('prototype_wire_closure009_source_0',b)
        self.assertIn('prototype_wire_closure010_source_0',b)

    def test_unsafe_namespace_rejected(self):
        for namespace in ('','a b','a;exit','a{bad}','1bad'):
            with self.subTest(namespace=namespace), self.assertRaises(ValueError):
                actions_for_plan(self.plan(),namespace)


if __name__=='__main__':unittest.main()
