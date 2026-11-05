import copy
import unittest

from check_parallel_dco import PAIRS,TOP,V5_PAIRS,validate


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
        for top in ('IntegerPLL_DCO_EINVP_COARSE_V3',
                    'IntegerPLL_DCO_EINVP_COARSE_V4'):
            with self.subTest(top=top):
                data,report=self.fixture()
                data['modules'][top]=data['modules'].pop(TOP)
                cells=data['modules'][top]['cells']
                for left,right,_,_ in PAIRS:
                    for suffix in ['2','3']:cells[right+suffix]=copy.deepcopy(cells[left])
                if top.endswith('_V4'):
                    data['modules'][top]['ports']={'DCO_THERM':{'bits':list(range(1000,1255))}}
                    data['modules'][top]['netnames']={'osc_node':{'bits':[2]},
                                                    'mirror_ret[0]':{'bits':[3]}}
                    for index in range(255):
                        cells[f'gen_dco_load[{index}].tune_load']={
                            'type':'sky130_fd_sc_hd__einvp_1',
                            'connections':{'A':[2 if index%2==0 else 3],
                                           'TE':[1000+index],'Z':[2000+index]},
                            'port_directions':{'A':'input','TE':'input','Z':'output'}}
                result=validate(data,report.replace(TOP,top),top)
                self.assertTrue(result['passed'])
                if top.endswith('_V4'):
                    self.assertEqual(result['independent_fine_loads'],255)
                    cells['gen_dco_load[1].tune_load']['connections']['A']=[2]
                    with self.assertRaisesRegex(ValueError,'fine load 1'):
                        validate(data,report.replace(TOP,top),top)

    def test_rejects_aliased_v4_fine_load(self):
        data,report=self.fixture()
        top='IntegerPLL_DCO_EINVP_COARSE_V4'
        data['modules'][top]=data['modules'].pop(TOP)
        cells=data['modules'][top]['cells']
        for left,right,_,_ in PAIRS:
            for suffix in ['2','3']:cells[right+suffix]=copy.deepcopy(cells[left])
        data['modules'][top]['ports']={'DCO_THERM':{'bits':list(range(1000,1255))}}
        data['modules'][top]['netnames']={'osc_node':{'bits':[2]},
                                        'mirror_ret[0]':{'bits':[3]}}
        for index in range(255):
            cells[f'gen_dco_load[{index}].tune_load']={
                'type':'sky130_fd_sc_hd__einvp_1',
                'connections':{'A':[2 if index%2==0 else 3],
                               'TE':[1000+index//2],'Z':[2000+index]},
                'port_directions':{'A':'input','TE':'input','Z':'output'}}
        with self.assertRaisesRegex(ValueError,'fine load'):
            validate(data,report.replace(TOP,top),top)

    def test_v5_coarse_path_driver_validation(self):
        data,report=self.fixture()
        top='IntegerPLL_DCO_EINVP_COARSE_V5'
        data['modules'][top]=data['modules'].pop(TOP)
        module=data['modules'][top]
        cells=module['cells']
        for left,right,_,_ in PAIRS:
            for suffix in ('2','3'):
                cells[right+suffix]=copy.deepcopy(cells[left])
        for bit,(left,right,kind,net) in enumerate(V5_PAIRS,20):
            first='A_N' if 'nand2b' in kind else 'A'
            cell=dict(type=kind,parameters={},connections={first:[2],'B':[3],'Y':[bit]},
                      port_directions={first:'input','B':'input','Y':'output'})
            cells[left]=cell
            for index in range(3):
                cells[f'gen_coarse1_parallel[{index}].{right}']=copy.deepcopy(cell)
            report+=f'Warning: multiple conflicting drivers for {TOP}.\\{net}:\n'
        report=report.replace(TOP,top).replace('3 problems.','7 problems.')
        module['ports']={'DCO_THERM':{'bits':list(range(1000,1255))}}
        module['netnames']={'osc_node':{'bits':[2]},'mirror_ret[0]':{'bits':[3]}}
        for index in range(255):
            cells[f'gen_dco_load[{index}].tune_load']={
                'type':'sky130_fd_sc_hd__einvp_1',
                'connections':{'A':[2 if index%2==0 else 3],
                               'TE':[1000+index],'Z':[2000+index]},
                'port_directions':{'A':'input','TE':'input','Z':'output'}}
        self.assertEqual(validate(data,report,top)['expected_synthesis_check_count'],7)
        cells['gen_coarse1_parallel[1].mirror_return']['connections']['B']=[99]
        with self.assertRaisesRegex(ValueError,'identical connections'):
            validate(data,report,top)

    def test_v6_supplemental_load_pattern(self):
        data,report=self.fixture()
        top='IntegerPLL_DCO_EINVP_COARSE_V6'
        data['modules'][top]=data['modules'].pop(TOP)
        module=data['modules'][top]
        cells=module['cells']
        for left,right,_,_ in PAIRS:
            for suffix in ('2','3'):
                cells[right+suffix]=copy.deepcopy(cells[left])
        for bit,(left,right,kind,net) in enumerate(V5_PAIRS,20):
            first='A_N' if 'nand2b' in kind else 'A'
            cell=dict(type=kind,parameters={},connections={first:[2],'B':[3],'Y':[bit]},
                      port_directions={first:'input','B':'input','Y':'output'})
            cells[left]=cell
            for index in range(3):
                cells[f'gen_coarse1_parallel[{index}].{right}']=copy.deepcopy(cell)
            report+=f'Warning: multiple conflicting drivers for {TOP}.\\{net}:\n'
        report=report.replace(TOP,top).replace('3 problems.','7 problems.')
        module['ports']={'DCO_THERM':{'bits':list(range(1000,1255))}}
        module['netnames']={'osc_node':{'bits':[2]},
                            'mirror_ret[0]':{'bits':[3]}}
        for index in range(255):
            prefix=f'gen_dco_load[{index}]'
            base=dict(type='sky130_fd_sc_hd__einvp_1',
                      connections={'A':[2 if index%2==0 else 3],
                                   'TE':[1000+index],'Z':[2000+index]},
                      port_directions={'A':'input','TE':'input','Z':'output'})
            cells[f'{prefix}.tune_load']=base
            if index%4<2:
                extra=copy.deepcopy(base)
                extra['connections']['Z']=[3000+index]
                cells[f'{prefix}.gen_supplemental_load.tune_load_extra']=extra
        self.assertEqual(validate(data,report,top)['supplemental_fine_loads'],128)
        cells['gen_dco_load[1].gen_supplemental_load.tune_load_extra']['connections']['TE']=[999]
        with self.assertRaisesRegex(ValueError,'supplemental fine load'):
            validate(data,report,top)

    def test_keeper_requires_complementary_control(self):
        data,report=self.fixture()
        top='IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_KEEPER'
        module=data['modules'][top]=data['modules'].pop(TOP)
        cells=module['cells']
        for left,right,_,_ in PAIRS:
            for index in (2,3):
                cells[f'{right}{index}']=copy.deepcopy(cells[left])
        turn=PAIRS[1][0]
        for index in range(4,10):
            cells[f'mirror_turn_parallel{index}']=copy.deepcopy(cells[turn])
        for bit,(left,right,kind,net) in enumerate(V5_PAIRS,20):
            first='A_N' if 'nand2b' in kind else 'A'
            cell=dict(type=kind,parameters={},
                      connections={first:[2],'B':[3],'Y':[bit]},
                      port_directions={first:'input','B':'input','Y':'output'})
            cells[left]=cell
            for index in range(3):
                cells[f'gen_coarse1_parallel[{index}].{right}']=copy.deepcopy(cell)
            report+=f'Warning: multiple conflicting drivers for {TOP}.\\{net}:\n'
        module['ports']={'DCO_THERM':{'bits':list(range(1000,1255))}}
        module['netnames']={'osc_node':{'bits':[2]},'mirror_ret[0]':{'bits':[3]},
                            'tie_hi':{'bits':[4]}}
        for index in range(255):
            branch='gen_mirror_input_load' if index%2==0 else 'gen_feedback_load'
            prefix=f'gen_dco_load[{index}].{branch}.'
            module['netnames'][f'load_dummy[{index}]']={'bits':[2000+index]}
            cells[prefix+'tune_load']={
                'type':'sky130_fd_sc_hd__einvp_1',
                'connections':{'A':[2 if index%2==0 else 3],
                               'TE':[1000+index],'Z':[2000+index]},
                'port_directions':{'A':'input','TE':'input','Z':'output'}}
            cells[prefix+'idle_keeper']={
                'type':'sky130_fd_sc_hd__einvn_0',
                'connections':{'A':[4],'TE_B':[1000+index],'Z':[2000+index]},
                'port_directions':{'A':'input','TE_B':'input','Z':'output'}}
            report+=f'Warning: multiple conflicting drivers for {TOP}.\\load_dummy[{index}]:\n'
        report=report.replace(TOP,top).replace('3 problems.','262 problems.')
        self.assertEqual(validate(data,report,top)['expected_synthesis_check_count'],262)
        cells['gen_dco_load[17].gen_feedback_load.idle_keeper']['connections']['TE_B']=[999]
        with self.assertRaisesRegex(ValueError,'keeper at fine load 17'):
            validate(data,report,top)

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
