import copy
import unittest
from fractions import Fraction as F
from native_zero_R_axis import prepare, dc_matrix
from check_native_zero_R_axes import check_model


class ZeroAxisTest(unittest.TestCase):
    def chain(self):
        return dict(state='full_tile_chain_with_zero_R',flow_axis=0,
            native_group_id='7',tile_box_internal=[0,0,10,4],
            segments=[[0,4,'_rmesh_7_a','_rmesh_7_b','0','r0'],
                      [4,10,'_rmesh_7_b','_rmesh_7_c','3','r1']])

    def test_mixed_exact_constraints_and_native_finite_R(self):
        model=prepare(self.chain(),'ZERO')
        self.assertEqual(len(model['constraints']),1)
        self.assertEqual(model['native_edges'][1][2],F(3))
        self.assertEqual(model['conductance']['_rmesh_7_b','_rmesh_7_c'],-F(1,3))
        self.assertFalse(model['epsilon_resistance_added'])
        result=check_model(self.chain(),'ZERO')
        self.assertEqual(result['exact_DC_residual'],'0')

    def test_all_zero_native_chain_retains_every_voltage_identity(self):
        chain=self.chain();chain['segments'][1][4]='0'
        model=prepare(chain,'ZERO')
        self.assertEqual(len(model['native_nodes']),3)
        self.assertEqual(len(model['constraints']),2)
        self.assertFalse(model['conductance'])
        self.assertEqual(check_model(chain,'ZERO')['zero_voltage_constraints'],2)

    def test_mna_is_symmetric_and_has_no_zero_R_inverse(self):
        model=prepare(self.chain(),'ZERO');matrix=dc_matrix(model)
        self.assertTrue(all(matrix.get((b,a),0)==v for (a,b),v in matrix.items()))
        c=model['constraints'][0];i=c['current_unknown']
        self.assertEqual(matrix[c['positive'],i],1)
        self.assertEqual(matrix[c['negative'],i],-1)
        self.assertNotIn((i,i),matrix)

    def test_rotation_preserves_charge_and_exact_dc(self):
        a=self.chain();b=copy.deepcopy(a);b['flow_axis']=1;b['tile_box_internal']=[0,0,4,10]
        self.assertEqual(prepare(a,'Z')['unit_area_mass'],prepare(b,'Z')['unit_area_mass'])
        self.assertTrue(check_model(b,'Z')['unit_density_charge_mass_exact'])

    def test_refuses_negative_R_and_no_zero_branch(self):
        for values in (('-1','3'),('2','3')):
            chain=self.chain()
            for s,r in zip(chain['segments'],values):s[4]=r
            with self.assertRaises(ValueError):prepare(chain,'Z')

    def test_refuses_open_ends_and_discontinuous_private_nodes(self):
        chain=self.chain();chain['tile_box_internal'][2]=11
        with self.assertRaises(ValueError):prepare(chain,'Z')
        chain=self.chain();chain['segments'][1][2]='_rmesh_7_other'
        with self.assertRaises(ValueError):prepare(chain,'Z')

    def test_refuses_cross_snapshot_and_reused_voltage_identity(self):
        chain=self.chain();chain['segments'][1][3]='_rmesh_8_c'
        with self.assertRaises(ValueError):prepare(chain,'Z')
        chain=self.chain();chain['segments'][1][3]='_rmesh_7_a'
        with self.assertRaises(ValueError):prepare(chain,'Z')

    def test_preserves_reference_gauge_without_grounding_native_nodes(self):
        model=prepare(self.chain(),'Z');mass=model['unit_area_mass']
        names=model['native_nodes']+[model['reference']]
        self.assertTrue(all(sum(mass.get((n,k),F(0)) for k in names)==0 for n in names))
        self.assertEqual(sum(mass.get((n,k),F(0)) for n in model['native_nodes'] for k in model['native_nodes']),40)


if __name__=='__main__':unittest.main()
