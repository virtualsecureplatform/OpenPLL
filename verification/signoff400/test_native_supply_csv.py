import csv,tempfile,unittest
from pathlib import Path
from assess_native_supply_csv import analyze

class SupplyCSV(unittest.TestCase):
    sources=dict(VPWR='V1',VPB='V2',VGND='V3',VNB='V4')
    header=['TIME','V(VPWR)','V(VPB)','V(VGND)','V(VNB)','I(V1)','I(V2)','I(V3)','I(V4)']
    def rows(self):return [[t,1.8,1.8,0.,0.,-.0018*f,-.00018*f,.0018*f,.00018*f]for t,f in((0.,0.),(10e-9,1.))]
    def write(self,d,rows,header=None):
        p=Path(d)/'supply.csv'
        with p.open('w')as h:
            w=csv.writer(h);w.writerow(self.header if header is None else header);w.writerows(rows)
        return p
    def test_clipped_window_on_ramping_current(self):
        with tempfile.TemporaryDirectory()as d:
            r=analyze(self.write(d,self.rows()),self.sources,2,8,10)
        self.assertAlmostEqual(r['mean_supply_power_W'],.003564/2,places=14)
        self.assertAlmostEqual(r['energy_J']/(.003564/2*6e-9),1,places=14)
        self.assertFalse(r['power_limit_applied'])
    def test_nonfinite_wrong_rail_and_incomplete_horizon_rejected(self):
        for kind in('nonfinite','voltage','end','order'):
            rows=self.rows()
            if kind=='nonfinite':rows[1][5]=float('nan')
            elif kind=='voltage':rows[1][2]=0
            elif kind=='end':rows[1][0]=9e-9
            else:rows.insert(1,rows[0][:])
            with self.subTest(kind=kind),tempfile.TemporaryDirectory()as d,self.assertRaises(ValueError):analyze(self.write(d,rows),self.sources,2,8,10)
    def test_aliased_source_mapping_rejected(self):
        with tempfile.TemporaryDirectory()as d,self.assertRaises(ValueError):analyze(self.write(d,self.rows()),dict(self.sources,VPB='V1'),2,8,10)

if __name__=='__main__':unittest.main()
