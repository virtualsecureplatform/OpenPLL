from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT=Path(__file__).with_name('command_log_tee.py')


class NativeOutputRelay(unittest.TestCase):
    def test_binary_output_and_nonzero_exit_are_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            log=Path(temp)/'native.log'
            child=[sys.executable,'-c',"import os;os.write(1,b'a\\x00b');os.write(2,b'error\\n');raise SystemExit(7)"]
            expected=subprocess.run(child,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            actual=subprocess.run([sys.executable,str(SCRIPT),'--output',str(log),'--',*child],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            self.assertEqual(actual.returncode,expected.returncode)
            self.assertEqual(actual.stdout,expected.stdout)
            self.assertEqual(log.read_bytes(),expected.stdout)
            self.assertEqual(actual.stderr,b'')

    def test_signal_and_existing_log_are_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            log=Path(temp)/'native.log'
            child=[sys.executable,'-c','import os,signal;os.kill(os.getpid(),signal.SIGTERM)']
            actual=subprocess.run([sys.executable,str(SCRIPT),'--output',str(log),'--',*child],capture_output=True)
            self.assertEqual(actual.returncode,-15)
            sentinel=Path(temp)/'started'
            child=[sys.executable,'-c',f'from pathlib import Path;Path({str(sentinel)!r}).touch()']
            rejected=subprocess.run([sys.executable,str(SCRIPT),'--output',str(log),'--',*child],capture_output=True)
            self.assertNotEqual(rejected.returncode,0);self.assertFalse(sentinel.exists())


if __name__=='__main__':unittest.main()
