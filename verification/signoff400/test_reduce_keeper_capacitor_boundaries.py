import unittest
from fractions import Fraction as F
from reduce_keeper_capacitor_boundaries import transform,root_info,decimal_exact
from audit_keeper_native_R_contraction import number
class CapacitorReduction(unittest.TestCase):
    def fixture(self):
        text='.subckt root a b v out\nX0 out v __openpll_device\nC0 out a 1f\nC1 out b 3f\nC2 a v 2f\nC3 out v 1f\n.ends\n.subckt __openpll_device d s\nM0 d s s s transistor\n.ends\n'
        bindings=dict(externally_driven_ports={'A':'a','B':'b','VPWR':'v'},observation_only_ports={'PLLOUT':'out'},all_physical_nodes={'A':'a','B':'b','VPWR':'v','PLLOUT':'out'},default_sources_added=False)
        return text,bindings
    def charge(self,text,node,voltages):
        value=F(0)
        for _,f in root_info(text)[3]:
            if f[0][0].upper()!='C':continue
            a,b=f[1:3];c=number(f[3])
            if a==node:value+=c*(voltages[a]-voltages[b])
            if b==node:value+=c*(voltages[b]-voltages[a])
        return value
    def test_retained_node_charge_exact_for_independent_voltages(self):
        text,b=self.fixture();reduced,bindings,plan=transform(text,b)
        self.assertEqual(plan['transformed_driven_ports'],2);self.assertEqual(plan['transformed_explicit_C_cards'],2);self.assertEqual(bindings['observation_only_ports'],b['observation_only_ports']);self.assertFalse(plan['native_simulation_allowed'])
        for va,vb,vi in [(F(7,5),-F(3,10),F(4,5)),(F(0),F(9,5),F(1)),(F(3),F(3),-F(1))]:
            v=dict(a=va,b=vb,v=F(9,5),out=vi)
            for g in plan['groups']:
                v[g['aggregate_native_port']]=sum((F(w)*v[b['externally_driven_ports'][key]] for key,w in g['boundary_weights_exact'].items()),F(0))
            self.assertEqual(self.charge(text,'out',v),self.charge(reduced,'out',v))
        self.assertIn('X0 out v __openpll_device\n',reduced);self.assertIn('M0 d s s s transistor\n',reduced)
    def test_device_connected_boundary_not_eliminated(self):
        text,b=self.fixture();text=text.replace('X0 out v','X0 out b v');_,new,plan=transform(text,b)
        self.assertIn('B',new['externally_driven_ports']);self.assertEqual(plan['eliminated_boundary_ports'],1)
    def test_exact_decimal_and_unsafe_model_rejection(self):
        for value in [F(1,10**15),F(17,2**20*5**23),-F(3,100)]:self.assertEqual(number(decimal_exact(value)),value)
        with self.assertRaisesRegex(ValueError,'finite decimal'):decimal_exact(F(1,3))
        text,b=self.fixture()
        with self.assertRaisesRegex(ValueError,'positive'):transform(text.replace('C0 out a 1f','C0 out a -1f'),b)
        with self.assertRaisesRegex(ValueError,'unsupported'):transform(text.replace('X0 out v __openpll_device','B0 out 0 V={a}'),b)
if __name__=='__main__':unittest.main()
