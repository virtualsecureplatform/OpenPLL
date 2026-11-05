"""Compiled interval search must match independent exhaustive site enumeration."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from common import ROOT


def exhaustive(boxes,targets):
    occupied=[(l-3000,b-3000,r+3000,t+3000) for l,b,r,t in boxes]
    plan=[]
    for target in targets:
        cx,cy=target['point'];choices=[]
        for row in range(max(0,(cy-100000-13320)//3330),min(248,(cy+100000-13320)//3330)+1):
            if row%2:continue
            y=13320+row*3330
            for col in range(max(0,(cx-100000-10080)//480),min(2033,(cx+100000-10080)//480)+1):
                x=10080+col*480
                if any(x<r and x+4320>l and y<t and y+3330>b for l,b,r,t in occupied):continue
                choices.append((abs(x+2160-cx)+abs(y+1665-cy),x,y))
        if not choices:raise ValueError('no legal site')
        distance,x,y=min(choices)
        occupied.append((x-1920,y,x+4320+1920,y+3330))
        plan.append(dict(net=target['net'],x_nm=x,y_nm=y,orient='R0',diodes=4,distance_nm=distance))
    return plan


class ParentBankPlanner(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.binary=Path(cls.temp.name)/'planner'
        subprocess.run(['g++','-std=c++20','-O2',str(ROOT/'tools/parent_bank_planner/main.cpp'),'-o',str(cls.binary)],
                       check=True,capture_output=True,timeout=120)

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def invoke(self,config):
        path=Path(self.temp.name)/'config.json';path.write_text(json.dumps(config))
        return subprocess.run([self.binary,path],capture_output=True,text=True,timeout=60)

    def test_exhaustive_equivalence_for_blocked_rows_ties_and_repeated_targets(self):
        for boxes,points in [([],[(150000,150000),(150000,150000),(151000,150000)]),
            ([[150000,150000,500000,520000],[750000,150000,840000,300000]],[(148000,200000),(502000,300000),(748000,200000)]),
            ([],[(0,0),(1000000,850000),(12240,14985)]),
            ([[10000,10000,20000,20000]],[(23000,13320),(23000,19980)])]:
            with self.subTest(boxes=boxes,points=points):
                targets=[dict(net=str(i),point=list(p)) for i,p in enumerate(points)]
                result=self.invoke(dict(macro_boxes=boxes,targets=targets))
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertEqual(json.loads(result.stdout),exhaustive(boxes,targets))

    def test_infeasible_sites_and_duplicate_targets_fail(self):
        for config in [dict(macro_boxes=[[0,0,1000000,850000]],targets=[dict(net='X',point=[500000,400000])]),
                       dict(macro_boxes=[],targets=[dict(net='X',point=[0,0])]*2)]:
            with self.subTest(config=config):self.assertNotEqual(self.invoke(config).returncode,0)


if __name__=='__main__':unittest.main()
