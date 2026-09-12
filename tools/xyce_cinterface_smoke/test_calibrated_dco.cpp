// SPDX-License-Identifier: Apache-2.0
#include "calibrated_dco.h"
#ifdef NDEBUG
#undef NDEBUG
#endif
#include <cassert>
#include <cmath>
#include <iostream>
#include <filesystem>
#include <unistd.h>
int main() {
  CalibratedDco dco;
  assert(std::abs(dco.frequency(235)-100.000534931)<1e-10);
  assert(dco.frequency(234)<dco.frequency(235));
  DcoPhase phase;
  phase.advance(2e-9,100);
  assert(std::abs(phase.time_to_edge(200)-1.5e-9)<1e-20);
  phase.advance(1.5e-9,200); phase.edge();
  assert(std::abs(phase.time_to_edge(200)-2.5e-9)<1e-20);
  DcoPhase unrounded;
  double elapsed=0, f=dco.frequency(235);
  for(int i=0;i<20000;++i) {
    const double dt=unrounded.time_to_edge(f);
    elapsed+=dt; unrounded.advance(dt,f); unrounded.edge();
  }
  assert(std::abs(10000/elapsed/1e6-f)<1e-7);
  assert(std::abs(elapsed-100e-6)>5e-10); // Must not round to exactly 100 MHz.
  const auto table = std::filesystem::temp_directory_path() /
      ("openpll-dco-test-"+std::to_string(getpid())+".txt");
  { std::ofstream file(table); file << "0 90\n255 110\n"; }
  dco.load(table.c_str());
  assert(std::abs(dco.frequency(128)-(90+20.0*128/255))<1e-10);
  { std::ofstream file(table); file << "0 90\n255 110\n17"; }
  bool rejected=false;
  try { dco.load(table.c_str()); } catch(const std::runtime_error&) { rejected=true; }
  assert(rejected);
  CalibratedDcoBank bank;
  rejected=false;
  try { bank.frequency(0,128); } catch(const std::runtime_error&) { rejected=true; }
  assert(rejected);
  { std::ofstream file(table);
    for(int band_index=0;band_index<48;++band_index)
      file<<band_index<<" 0 "<<100+band_index<<'\n'<<band_index<<" 255 "<<110+band_index<<'\n';
  }
  bank.load(table.c_str());
  assert(std::abs(bank.frequency(47,128)-(147+10.0*128/255))<1e-10);
  // Changing band changes slope without discarding oscillator phase.
  DcoPhase switched;
  switched.advance(2e-9,bank.frequency(0,0));
  assert(std::abs(switched.time_to_edge(bank.frequency(47,0))-.3/(147e6))<1e-20);
  { std::ofstream file(table);file<<"0 0 100\n0 255 110\n"; }
  rejected=false;
  try { bank.load(table.c_str()); } catch(const std::runtime_error&) { rejected=true; }
  assert(rejected);
  assert(std::abs(bank.frequency(47,0)-147)<1e-10);
  { std::ofstream file(table);
    for(int band_index=0;band_index<48;++band_index)
      file<<band_index<<' '<<(1u<<(band_index/12))<<'\n';
  }
  bank.load_dividers(table.c_str());
  assert(bank.divider(0)==1 && bank.divider(12)==2 && bank.divider(24)==4 && bank.divider(47)==8);
  { std::ofstream file(table);file<<"0 3\n"; }
  rejected=false;
  try {bank.load_dividers(table.c_str());} catch(const std::runtime_error&) {rejected=true;}
  assert(rejected && bank.divider(47)==8);
  DcoOutputDivider divided_clock;
  std::array<unsigned,4> rises{};
  std::array<bool,4> previous{};
  for(int edge=0;edge<128;++edge) {
    divided_clock.edge();
    for(unsigned i=0;i<4;++i) {
      const bool level=divided_clock.output(1u<<i);
      if(level && !previous[i]) ++rises[i];
      previous[i]=level;
    }
  }
  assert((rises==std::array<unsigned,4>{64,32,16,8}));
  DcoOutputDivider mux_change;
  mux_change.edge();mux_change.edge();
  assert(!mux_change.output(1) && mux_change.output(8));
  // A mux change exposes the retained divider state, not a reset phase.
  mux_change.edge();assert(mux_change.output(1) && mux_change.output(8));
  std::filesystem::remove(table);
  std::cout << "calibrated_dco=pass\n";
}
