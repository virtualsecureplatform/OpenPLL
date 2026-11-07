import unittest
from check_selected_einvp_external_keeper import add_inverters


class ExternalKeeperTests(unittest.TestCase):
    def fixture(self):
        text='.subckt selected_einvp_cut a te vp vn\nXflat1 enb te vn vn leaf0\nXkeeper_0_0 z enb q vp leaf0\n.ends selected_einvp_cut\n'
        cells=[dict(local_to_native_nodes={p:[n]for p,n in [('TE','te'),('a_27_47#','enb'),('VGND','vn'),('VNB','vn'),('VPWR','vp'),('VPB','vp')]})]
        group=[];defs={};calls={}
        for i in range(4):
            family='nfet'if i%2==0 else 'pfet';pins=['Y','A','VGND','VNB']if i%2==0 else ['VPWR','A','Y','VPB'];leaf='invleaf%d'%i;name='Xflat%d'%(i+10)
            group.append(dict(instance=name,leaf_master='sky130_fd_sc_hs__inv_2',local_primitive_signature=[family,pins,[['w','37/50'],['l','3/20']]]))
            defs[leaf]=['.subckt '+leaf+' p0 p1 p2 p3\n','Xdevice p0 p1 p2 p3 '+family+' w=.74 l=.15\n','.ends\n'];calls[name]=[name,'y','a','s','b',leaf]
        return text,cells,group,defs,calls

    def test_keeper_uses_external_pin_and_original_internal_node_is_untouched(self):
        text,cells,group,defs,calls=self.fixture();result,added,nodes=add_inverters(text,cells,group,defs,calls)
        self.assertEqual(len(added),4);self.assertEqual(nodes,['__openpll_external_enb_0'])
        self.assertIn('Xflat1 enb te vn vn leaf0',result)
        self.assertIn('Xkeeper_0_0 z __openpll_external_enb_0 q vp leaf0',result)
        self.assertEqual(added[0]['terminals'],['__openpll_external_enb_0','te','vn','vn'])

    def test_changed_inverter_geometry_rejected(self):
        text,cells,group,defs,calls=self.fixture();defs['invleaf0'][1]=defs['invleaf0'][1].replace('w=.74','w=1')
        with self.assertRaisesRegex(ValueError,'exact physical'):add_inverters(text,cells,group,defs,calls)

    def test_incomplete_inverter_rejected(self):
        text,cells,group,defs,calls=self.fixture()
        with self.assertRaisesRegex(ValueError,'four-MOS'):add_inverters(text,cells,group[:3],defs,calls)


if __name__=='__main__':unittest.main()
