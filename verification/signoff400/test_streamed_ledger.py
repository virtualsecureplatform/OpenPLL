"""Exact native output equivalence and a memory-bound legacy failure control."""
import json
from pathlib import Path
import resource
import subprocess
import sys
import tempfile
import time
import unittest
from common import ROOT
from compiled_charge import build as old_build, compile_shard as old_compile
from compiled_charge_v2 import build, compile_shard
sys.path.append(str(ROOT/'verification/prototype400'))
sys.path.append(str(ROOT/'verification/timing400'))
from test_parallel_capacitance import fixture
from parallel_C_trace_ranges import metadata,partition


class StreamedLedger(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();root=Path(cls.temp.name)
        cls.old=old_build(root/'old_build');cls.new=build(root/'new_build')

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_all_operator_outputs_match_legacy_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);trace=root/'trace';trace.mkdir();fixture(trace)
            meta=root/'metadata.json';meta.write_text(json.dumps(metadata(trace)))
            deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+60
            span=partition(trace,1,deadline)[0]
            old_compile(self.old,trace,root/'old',deadline,span,meta)
            compile_shard(self.new,trace,root/'new',deadline,span,meta)
            for name in ('operators.jsonl','fields.json','collapsed_matrix_ledger.json','observed_plane_residues.json'):
                self.assertEqual((root/'old'/name).read_bytes(),(root/'new'/name).read_bytes())

    def test_ledger_serializer_fits_where_legacy_tree_exhausts_memory(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'control.cpp';binary=root/'control'
            include=ROOT/'tools/charge_compiler/main_stream_ledger.cpp'
            source.write_text(f'''#define main retained_charge_main
#include "{include}"
#undef main
int main(int argc,char** argv) {{try {{
    std::map<std::pair<I,I>,std::array<double,3>> ledger;
    for(I i=0;i<200000;++i)ledger[{{i,i+1}}]={{double(i),double(i)*.5,0}};
    if(std::string(argv[1])=="legacy") {{
        Json rows=Json::array();for(auto [k,v]:ledger)rows.push(Json::Array{{k.first,k.second,v[0],v[1],v[2]}});
        save(argv[2],rows);
    }} else save_ledger(argv[2],ledger,uptime()+60);
    return 0;
}} catch(const std::exception& e) {{std::cerr<<e.what()<<'\\n';return 1;}} }}
''')
            subprocess.run(['g++','-std=c++20','-O2','-pthread',str(source),'-o',str(binary)],
                           check=True,capture_output=True,timeout=120)
            def bounded():resource.setrlimit(resource.RLIMIT_AS,(64*1024**2,64*1024**2))
            legacy=subprocess.run([binary,'legacy',root/'old.json'],capture_output=True,text=True,preexec_fn=bounded,timeout=60)
            self.assertNotEqual(legacy.returncode,0)
            self.assertIn('bad_alloc',legacy.stderr)
            result=subprocess.run([binary,'stream',root/'new.json'],capture_output=True,text=True,preexec_fn=bounded,timeout=60)
            self.assertEqual(result.returncode,0,result.stderr)
            rows=json.loads((root/'new.json').read_text())
            self.assertEqual(len(rows),200000)
            self.assertEqual(rows[-1],[199999,200000,199999,99999.5,0])


if __name__=='__main__':unittest.main()
