import unittest
from extend_prototype_plan_programming_input_protection import PORT_WIDTHS,bit_name,select_targets


class ProgrammingInputProtectionTests(unittest.TestCase):
    def design(self):
        module=dict(ports={},cells={});physical=set();bit=2
        for name,width in PORT_WIDTHS.items():
            port=dict(direction='input',bits=list(range(bit,bit+width)))
            module['ports'][name]=port
            physical.update(bit_name(name,port,n) for n in range(width))
            module['cells'][name+'_receiver']=dict(type='sky130_fd_sc_hs__nand2_1',
                connections={'A':[bit]},port_directions={'A':'input'})
            bit+=width
        module['cells']['unrelated_clock']=dict(type='sky130_fd_sc_hs__clkbuf_2',
            connections={'A':[bit]},port_directions={'A':'input'})
        return module,physical

    def test_exact_interface_excludes_unrelated_clock(self):
        module,physical=self.design();targets=select_targets(module,physical)
        self.assertEqual(len(targets),5)
        self.assertNotIn('unrelated_clock',{t[1] for t in targets})

    def test_missing_physical_pin_or_aliased_external_bits_rejected(self):
        module,physical=self.design();physical.remove('KI[0]')
        with self.assertRaises(ValueError):select_targets(module,physical)
        module,physical=self.design();module['ports']['KI']['bits'][0]=module['ports']['KP']['bits'][0]
        with self.assertRaises(ValueError):select_targets(module,physical)

    def test_control_pin_cannot_be_silently_added_to_data_scope(self):
        module,physical=self.design();cell=module['cells']['KI_receiver']
        cell['connections']={'CLK':cell['connections']['A']};cell['port_directions']={'CLK':'input'}
        with self.assertRaises(ValueError):select_targets(module,physical)

    def test_ascending_offset_bus_names_are_explicit(self):
        self.assertEqual(bit_name('BUS',dict(bits=[2,3,4],upto=1,offset=5),0),'BUS[7]')
        self.assertEqual(bit_name('BUS',dict(bits=[2,3,4],upto=1,offset=5),2),'BUS[5]')


if __name__=='__main__':unittest.main()
