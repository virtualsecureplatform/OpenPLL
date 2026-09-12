import unittest
from check_strength_dco import TOP,validate


def fixture():
    def cell(kind,inputs,output,bit):
        return dict(type='sky130_fd_sc_hd__'+kind,
                    connections={**{k:[v] for k,v in inputs.items()},output:[bit]},
                    port_directions={**{k:'input' for k in inputs},output:'output'})
    cells={'reset_gate':cell('and2_4',dict(A=4,B=6),'X',5)}
    for stage,base,src,dst in [('osc','osc_gate',3,1),('stage1','stage1_gate',1,2),('stage2','stage2_gate',2,3)]:
        cells[base]=cell('nand2_1' if stage=='osc' else 'inv_1',
                         dict(A=src,B=4) if stage=='osc' else dict(A=src),'Y',dst)
        for i in range(63):cells[f'gen_drive[{i}].{stage}_driver']=cell('einvp_1',dict(A=src,TE=5),'Z',dst)
    m=dict(cells=cells,ports={'RESET_N':dict(direction='input',bits=[4]),
                            'coarse':dict(direction='input',bits=[6])},
           netnames={name:dict(bits=[bit]) for name,bit in [('osc_node',1),('stage1',2),('stage2',3)]})
    report='\n'.join(f'Warning: multiple conflicting drivers for {TOP}.\\{name}:'
                     for name in ['osc_node','stage1','stage2'])+'\nFound and reported 3 problems.'
    return {'modules':{TOP:m}},report


class StrengthDriverTests(unittest.TestCase):
    def test_same_inversions_and_reset_gate_pass(self):
        n,r=fixture();self.assertTrue(validate(n,r)['reset_contention_proof'])

    def test_unqualified_enable_cannot_contend_with_reset(self):
        n,r=fixture();n['modules'][TOP]['cells']['gen_drive[0].osc_driver']['connections']['TE']=[6]
        with self.assertRaises(ValueError):validate(n,r)

    def test_opposite_ring_input_rejected(self):
        n,r=fixture();n['modules'][TOP]['cells']['gen_drive[0].stage1_driver']['connections']['A']=[3]
        with self.assertRaises(ValueError):validate(n,r)

    def test_unexpected_shared_output_rejected(self):
        n,r=fixture();n['modules'][TOP]['cells']['reset_gate']['connections']['X']=[1]
        with self.assertRaises(ValueError):validate(n,r)

    def test_additional_diagnostic_rejected(self):
        n,r=fixture()
        with self.assertRaises(ValueError):validate(n,r+'\nWarning: unrelated problem')


if __name__=='__main__':unittest.main()
