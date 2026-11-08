from contextlib import contextmanager
import unittest
from admitted_diagnostic_case import execute_admitted


class AdmissionAccounting(unittest.TestCase):
    def test_long_admission_wait_does_not_consume_active_execution_budget(self):
        now=[0.];claims=[]
        @contextmanager
        def acquire(cpu,memory,deadline):
            claims.append((cpu,memory,deadline));now[0]+=3600
            yield
        def action():now[0]+=3;return 'completed'
        result,elapsed=execute_admitted(action,9000,acquire=acquire,clock=lambda:now[0])
        self.assertEqual((result,elapsed),('completed',3))
        self.assertEqual(claims,[(1,2,9000)])

    def test_admission_timeout_never_starts_simulation(self):
        called=[]
        @contextmanager
        def acquire(*args):
            raise TimeoutError('resources unavailable')
            yield
        with self.assertRaises(TimeoutError):execute_admitted(lambda:called.append(True),9000,acquire=acquire)
        self.assertEqual(called,[])

    def test_execution_failure_releases_claim_and_is_not_a_pass(self):
        released=[]
        @contextmanager
        def acquire(*args):
            try:yield
            finally:released.append(True)
        def action():raise RuntimeError('simulator failed')
        with self.assertRaises(RuntimeError):execute_admitted(action,9000,acquire=acquire)
        self.assertEqual(released,[True])


if __name__=='__main__':unittest.main()
