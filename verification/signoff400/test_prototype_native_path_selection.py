import unittest
from prepare_prototype_native_path_selection import select


def fixture():
    def cell(kind,connections):
        return dict(type=kind,connections={k:[v] for k,v in connections.items()},port_directions={k:'output' if k in ('Q','X') else 'input' for k in connections})
    module=dict(cells=dict(src=cell('ff',dict(CLK=7,D=3,Q=5,RESET_B=4)),dst=cell('ff',dict(CLK=2,D=6,Q=8,RESET_B=4)),data=cell('buf',dict(A=5,X=6)),clock=cell('buf',dict(A=1,X=7)),outside=cell('buf',dict(A=5,X=9))),ports={'A':dict(direction='input',bits=[1]),'B':dict(direction='input',bits=[2])})
    states=[dict(cell='src'),dict(cell='dst')]
    report='Startpoint: src\nEndpoint: dst\nPath Type: min\n 0 ^ src/CLK (ff)\n 0 ^ src/Q (ff)\n 0 ^ data/X (buf)\n 0 ^ dst/D (ff)\n data arrival time\n'
    return module,states,report,'src','dst'


class NativePathSelectionTests(unittest.TestCase):
    def test_retains_data_clock_cone_and_outside_receiver_obligation(self):
        r=select(*fixture())
        self.assertEqual(set(r['cells']),{'src','dst','data','clock'})
        self.assertEqual(r['data_path'],['src','data','dst'])
        self.assertEqual(r['clock_cells'],['clock'])
        self.assertEqual({b['bit'] for b in r['clock_boundaries']},{1,2})
        self.assertEqual(r['omitted_receiver_terminals'],[dict(bit=5,instance='outside',pin='A')])

    def test_wrong_report_or_ambiguous_clock_source_rejected(self):
        f=list(fixture());f[-1]='unreported'
        with self.assertRaises(ValueError):select(*f)
        f=list(fixture());f[0]['cells']['second_clock_driver']=dict(f[0]['cells']['clock'])
        with self.assertRaisesRegex(ValueError,'multiple clock drivers'):select(*f)

if __name__=='__main__':unittest.main()
