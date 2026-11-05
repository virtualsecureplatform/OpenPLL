"""Exercise duty, accumulated phase, retuning and reset against exact edge times."""
from pathlib import Path
import subprocess
import tempfile
import unittest


class ShapedClockTest(unittest.TestCase):
    def test_integer_phase_and_duty(self):
        source = r'''
#include "phase_clock_shaped.h"
#include "phase_clock.h"
#include <cassert>
int main() {
  Phase400Clock legacy; Phase400ShapedClock symmetric;
  legacy.reset(0);symmetric.reset(0);legacy.tune(0,400123456789ULL);
  symmetric.tune(0,400123456789ULL);
  unsigned long long now=0;
  for(int n=0;n<10000;++n) {
    assert(legacy.delay()==symmetric.delay());now+=legacy.delay();
    legacy.edge(now);symmetric.edge(now);
  }
  Phase400ShapedClock shaped;shaped.configure_duty(540000);
  shaped.reset(0);shaped.tune(0,400000000000ULL);now=0;
  for(unsigned n=0;n<10000;++n) {
    now+=shaped.delay();shaped.edge(now);
    assert(now==(n/2)*2500ULL+(n%2 ? 2500 : 1350));
  }
  shaped.reset(now);const auto start=now;
  shaped.tune(now,400000000000ULL);
  shaped.tune(now+500,500000000000ULL);
  assert(shaped.delay()==680);shaped.edge(start+1180);
  assert(shaped.delay()==920);shaped.edge(start+2100);
  bool rejected=false;
  try {shaped.configure_duty(600000);}catch(const std::runtime_error&) {rejected=true;}
  assert(rejected);
  Phase400ShapedClock invalid;rejected=false;
  try {invalid.configure_duty(0);}catch(const std::runtime_error&) {rejected=true;}
  assert(rejected);
}
'''
        with tempfile.TemporaryDirectory() as work:
            root=Path(__file__).resolve().parents[2]
            cpp=Path(work)/'test.cpp';cpp.write_text(source)
            executable=Path(work)/'test'
            subprocess.run(['g++','-std=c++17','-Wall','-Wextra','-Werror',
                            '-I',str(root/'verification/timing400'),str(cpp),'-o',str(executable)],check=True)
            subprocess.run([executable],check=True)


if __name__ == '__main__':
    unittest.main()
