from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from common import ROOT
class ByteComparison(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.binary=Path(cls.temp.name)/'compare'
        subprocess.run(['g++','-std=c++20','-O2',str(ROOT/'tools/charge_compiler/compare_bytes.cpp'),'-o',str(cls.binary)],check=True,capture_output=True)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def test_cross_buffer_binary_identity_one_bit_length_and_deadline(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);a=root/'a';b=root/'b';payload=b'x'*(1048576-1)+b'\x00\xff'+b'y'*1048576
            a.write_bytes(payload)
            for fault in ('none','bit','length','deadline'):
                with self.subTest(fault=fault):
                    data=payload if fault in ('none','deadline') else payload[:-1] if fault=='length' else payload[:1048576]+b'\xfe'+payload[1048577:]
                    b.write_bytes(data);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+(30 if fault!='deadline' else -1)
                    p=subprocess.run([str(self.binary),str(a),str(b),str(deadline)],capture_output=True,text=True)
                    self.assertEqual(p.returncode==0,fault=='none',p.stderr)
