import copy
import unittest

from check_parallel_dco import PAIRS,TOP,validate


class ParallelDriverTest(unittest.TestCase):
    def fixture(self):
        cells={}
        for bit,(left,right,kind,_) in enumerate(PAIRS,10):
            first='A_N' if 'nand2b' in kind else 'A'
            cell=dict(type=kind,parameters={},connections={first:[2],'B':[3],'Y':[bit]},
                      port_directions={first:'input','B':'input','Y':'output'})
            cells[left]=cell;cells[right]=copy.deepcopy(cell)
        report='\n'.join(f'Warning: multiple conflicting drivers for {TOP}.\\{net}:'
                         for *_,net in PAIRS)+'\nFound and reported 3 problems.\n'
        return dict(modules={TOP:dict(cells=cells)}),report

    def test_identical_pairs(self):
        self.assertTrue(validate(*self.fixture())['passed'])

    def test_four_identical_drivers(self):
        data,report=self.fixture()
        top='IntegerPLL_DCO_EINVP_COARSE_V3'
        data['modules'][top]=data['modules'].pop(TOP)
        cells=data['modules'][top]['cells']
        for left,right,_,_ in PAIRS:
            for suffix in ['2','3']:cells[right+suffix]=copy.deepcopy(cells[left])
        self.assertTrue(validate(data,report.replace(TOP,top),top)['passed'])

    def test_different_driver_input(self):
        data,report=self.fixture()
        data['modules'][TOP]['cells']['osc_gate_parallel']['connections']['A']=[99]
        with self.assertRaises(ValueError):validate(data,report)

    def test_unlisted_driver(self):
        data,report=self.fixture()
        data['modules'][TOP]['cells']['extra']=copy.deepcopy(data['modules'][TOP]['cells']['osc_gate'])
        with self.assertRaises(ValueError):validate(data,report)

    def test_additional_warning(self):
        data,report=self.fixture()
        with self.assertRaises(ValueError):validate(data,report+'Warning: undriven net\n')


if __name__=='__main__':unittest.main()
