from collections import defaultdict
from decimal import Decimal
import json
from pathlib import Path
import random
import subprocess
import tempfile
import time
import unittest
from common import ROOT, save


class CompareNativeCards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.binary = Path(cls.temp.name)/'compare'
        subprocess.run(['g++', '-std=c++20', '-O3', '-fopenmp', '-fno-fast-math', '-ffp-contract=off',
                        str(ROOT/'tools/native_rc_coverage/compare_native_cards.cpp'), '-o', str(cls.binary)],
                       check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def invoke(self, root, left, right, devices=None, threads=1, expired=False):
        for name, text in [('left.spice', left), ('right.spice', right),
                           ('left.ext', 'device mos x y 1\ndevice mos x y 1\n'),
                           ('right.ext', devices if devices is not None else 'device  mos\tx y 1\ndevice mos x y 1\n')]:
            (root/name).write_text(text)
        save(root/'config.json', dict(left_spice=str(root/'left.spice'), right_spice=str(root/'right.spice'),
             left_ext=str(root/'left.ext'), right_ext=str(root/'right.ext'), threads=threads,
             deadline_uptime=time.clock_gettime(time.CLOCK_BOOTTIME)+(-1 if expired else 60)))
        return subprocess.run([self.binary, root/'config.json'], capture_output=True, text=True)

    def test_random_pair_order_orientation_names_and_threads(self):
        rng = random.Random(9821)
        groups = []
        for i in range(1000):
            groups.append([f'C{i}_{j} n{i} ref {rng.choice(["1e30", "-1e30", "1", "-0", ".5p"])}\n' for j in range(10)])
        left = ''.join(''.join(group) for group in groups)
        right = ''.join(''.join(line.replace(f'n{i} ref', f'ref n{i}').replace('C', 'Crenamed', 1)
                         for line in groups[i]) for i in reversed(range(len(groups))))
        def oracle(text):
            matrix = defaultdict(Decimal)
            for line in text.splitlines():
                _, a, b, raw = line.split()
                matrix[tuple(sorted((a, b)))] += Decimal(raw[:-1])*Decimal('1e-12') if raw.endswith('p') else Decimal(raw)*Decimal('1.0')
            return {k: v for k, v in matrix.items() if v}
        self.assertEqual(oracle(left), oracle(right))
        for threads in (1, 4, 16):
            with self.subTest(threads=threads), tempfile.TemporaryDirectory() as temp:
                p = self.invoke(Path(temp), left, right, threads=threads)
                self.assertEqual(p.returncode, 0, p.stderr)
                self.assertEqual(json.loads(p.stdout)['capacitor_records_each'], 10000)

    def test_rounded_cancellation_order_and_device_multiplicity_rejected(self):
        left = 'C0 a b 1e30\nC1 a b -1e30\nC2 a b 1\n'
        right = 'C0 a b 1e30\nC1 a b 1\nC2 a b -1e30\n'
        self.assertNotEqual((Decimal('1e30')-Decimal('1e30'))+1, (Decimal('1e30')+1)-Decimal('1e30'))
        for text, devices in [(right, None), (left, 'device mos x y 1\n')]:
            with tempfile.TemporaryDirectory() as temp:
                self.assertNotEqual(self.invoke(Path(temp), left, text, devices).returncode, 0)

    def test_different_spelling_is_inconclusive_and_malformed_inputs_rejected(self):
        for text in ('C1 a b 1000f\n', 'C1 a b nan\n', 'C1 a b 1e1000000\n',
                     'C1 a b 1p\x1c\n', 'C1 a b\n'):
            with tempfile.TemporaryDirectory() as temp:
                self.assertNotEqual(self.invoke(Path(temp), 'C1 a b 1p\n', text).returncode, 0)
        with tempfile.TemporaryDirectory() as temp:
            self.assertNotEqual(self.invoke(Path(temp), 'C a b 1\n', 'C a b 1\n', expired=True).returncode, 0)
