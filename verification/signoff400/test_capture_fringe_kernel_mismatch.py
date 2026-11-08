import json,os,subprocess,tempfile,unittest
from pathlib import Path

class NativeKernelScanner(unittest.TestCase):
    def invoke(self,rows):
        binary=os.environ['FRINGE_SCANNER']
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'input.jsonl';output=Path(directory)/'group.jsonl'
            source.write_text(''.join(json.dumps(r,separators=(',',':'))+'\n' for r in rows))
            result=subprocess.run([binary,str(source),str(output)],capture_output=True,text=True,timeout=5)
            return result,output.read_text() if output.exists() else None

    def group(self,identifier=1,changed=False):
        base=dict(cell='fixture',epoch=2,fringe_id=identifier,reference_length=20,
                  boundary=[0,0,20,0],direction=1,coupling_multiplier_hex='0x1p-2',substrate_multiplier_hex='0x1p-3')
        begin=dict(kind='fringe_rule_begin',**base)
        leaf=dict(kind='fringe_shield_leaf',**base)
        if changed:leaf['coupling_multiplier_hex']='0x0p+0'
        return [begin,leaf,dict(kind='fringe_rule_end',**base)]

    def test_preserves_only_first_complete_mismatching_group(self):
        bad=self.group(2,True)
        result,output=self.invoke(self.group()+bad+self.group(3,True))
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual([json.loads(line) for line in output.splitlines()],bad)
        self.assertIn('coupling_multiplier_hex',result.stderr)

    def test_uniform_kernels_are_not_a_counterexample(self):
        result,output=self.invoke(self.group())
        self.assertNotEqual(result.returncode,0);self.assertIsNone(output)

    def test_truncated_mismatch_is_not_retained_as_complete(self):
        result,output=self.invoke(self.group(changed=True)[:-1])
        self.assertNotEqual(result.returncode,0);self.assertIsNone(output)

    def test_changed_group_identity_is_rejected(self):
        rows=self.group(changed=True);rows[1]['fringe_id']=99
        result,output=self.invoke(rows)
        self.assertNotEqual(result.returncode,0);self.assertIsNone(output)

if __name__=='__main__':unittest.main()
