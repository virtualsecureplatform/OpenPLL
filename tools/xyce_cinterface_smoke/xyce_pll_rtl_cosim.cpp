// SPDX-License-Identifier: Apache-2.0
// Extracted BBPD + selected RTL controller + calibrated behavioral oscillator.
#include <N_CIR_MixedSignalSimulator.h>
#include "VIntegerPLL_Cosim.h"
#include "calibrated_dco.h"
#include <algorithm>
#include <array>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <stdexcept>
#include <string>
#include <tuple>
#include <vector>

using Points = std::map<std::string,std::vector<std::pair<double,double>>>;
int main(int argc, char** argv) {
 try {
  if (argc < 9) throw std::runtime_error("usage: DECK TRACE SEED PHASE_NS DURATION_NS STEP_PS KI KP");
  const int seed=std::stoi(argv[3]), ki=std::stoi(argv[7]), kp=std::stoi(argv[8]);
  const double phase=std::stod(argv[4]), end=std::stod(argv[5])*1e-9, step=std::stod(argv[6])*1e-12;
  if(seed<0||seed>255||ki<0||ki>255||kp<0||kp>31||!std::isfinite(phase)||phase<0||phase>=40||!std::isfinite(end)||end<=1e-6||!std::isfinite(step)||step<=0||step>50e-12)
    throw std::runtime_error("invalid diagnostic arguments");
  CalibratedDco model;
  CalibratedDcoBank bank;
  DcoOutputDivider output_clock;
  std::string divider_path;
  DcoPhase oscillator_phase;
  bool phase_accum = false;
  bool acquisition=false, bank_loaded=false;
  bool smoke_only=false;
  int ndiv = 4, coarse = 17;
  double vdd = 1.8;
  for (int i=9; i<argc; ++i) {
    const std::string option=argv[i];
    if (option=="--phase-accum") {phase_accum=true; continue;}
    if (option=="--acquisition") {acquisition=true; continue;}
    if (option=="--smoke-only") {smoke_only=true; continue;}
    if (++i>=argc) throw std::runtime_error("missing option value");
    if (option=="--dco-table") model.load(argv[i]);
    else if (option=="--dco-bank") {bank.load(argv[i]);bank_loaded=true;}
    else if (option=="--dco-dividers") divider_path=argv[i];
    else if (option=="--ndiv") ndiv=std::stoi(argv[i]);
    else if (option=="--coarse") coarse=std::stoi(argv[i]);
    else if (option=="--vdd") vdd=std::stod(argv[i]);
    else throw std::runtime_error("unknown option "+option);
  }
  if ((ndiv!=4 && ndiv!=10 && ndiv!=12 && ndiv!=16 && ndiv!=20) ||
      coarse<0 || coarse>47 || !std::isfinite(vdd) || vdd<=0)
    throw std::runtime_error("invalid operating point");
  if(acquisition && (!bank_loaded || !phase_accum))
    throw std::runtime_error("acquisition requires a complete DCO bank and continuous phase");
  if(!divider_path.empty()) bank.load_dividers(divider_path.c_str());
  VerilatedContext context;
  VIntegerPLL_Cosim rtl{&context};
  auto frequency = [&](int code) {return acquisition ?
    bank.frequency(rtl.COARSE_CODE,code)*bank.divider(rtl.COARSE_CODE) : model.frequency(code);};
  rtl.SEED=seed; rtl.KI=ki; rtl.KP=kp;
  rtl.MODE_DIVIDER=ndiv; rtl.COARSE_SEED=coarse;
  rtl.PLLOUT=0; rtl.PLL_ENABLE=0; rtl.BBPD=0;
  rtl.REFCLK=0;rtl.ACQUIRE=acquisition;
  std::ofstream trace(argv[2]), replay(std::string(argv[2])+".replay");
  if(!trace||!replay) throw std::runtime_error("cannot open output");
  trace << "event,time_ns,code,bbpd\n" << std::fixed << std::setprecision(6);
  double now=0; unsigned long evals=0;
  auto evaluate=[&]() {
    int olddiv=rtl.CLKDIV_RETIMED;
    rtl.eval(); ++evals;
    replay << int(rtl.PLLOUT) << ' ' << int(rtl.RESET_N) << ' ' << int(rtl.PLL_ENABLE) << ' ' << int(rtl.BBPD) << ' '
           << int(rtl.CLKDIV_RETIMED) << ' ' << int(rtl.BBPD_RESET_N) << ' ' << int(rtl.TRACKING) << ' ' << int(rtl.DCO_CODE) << ' ' << int(rtl.DLF_CODE) << ' '
           << int(rtl.REFCLK) << ' ' << int(rtl.COARSE_CODE) << '\n';
    if (!olddiv && rtl.CLKDIV_RETIMED) trace << "DIV," << now*1e9 << ',' << int(rtl.DCO_CODE) << ',' << int(rtl.BBPD) << '\n';
  };
  auto drive_clock=[&]() {
    const bool value=output_clock.output(acquisition ? bank.divider(rtl.COARSE_CODE) : 1);
    if(value!=rtl.PLLOUT) {
      rtl.PLLOUT=value;evaluate();
      if(value) trace << "OUT," << now*1e9 << ',' << int(rtl.DCO_CODE) << ',' << int(rtl.BBPD) << '\n';
    }
  };
  // Exercise an explicit reset edge in both Verilator and the independent replay.
  rtl.RESET_N=1; evaluate(); rtl.RESET_N=0; evaluate();
  Xyce::Circuit::MixedSignalSimulator xyce;
  char name[]="xyce_pll_rtl_cosim";
  std::array<char*,3> args{name,argv[1],nullptr};
  if(xyce.initialize(2,args.data()) != Xyce::Circuit::Simulator::SUCCESS) throw std::runtime_error("Xyce initialize failed");
  std::vector<std::string> names; xyce.getDACDeviceNames(names);
  auto find=[&](const std::string& token) {
    for(auto& n:names) if(n.find(token)!=std::string::npos) return n;
    throw std::runtime_error("missing DAC "+token);
  };
  const std::string refdac=find("REF_DRIVER"), divdac=find("DIV_DRIVER"), resetdac=find("RESET_DRIVER");
  std::map<std::string,int> driven;
  auto drive=[&](const std::string& n,int value) {
    if(driven.count(n) && driven[n]==value) return;
    double previous=driven.count(n) ? driven[n]*vdd : value*vdd;
    Points data{{n,{{now,previous},{now+20e-12,value*vdd}}}};
    std::map<std::string,std::vector<std::pair<double,double>>*> pointers;
    for(auto& [key,v]:data) pointers[key]=&v;
    if(!xyce.updateTimeVoltagePairs(pointers)) throw std::runtime_error("DAC update failed");
    driven[n]=value;
  };
  int ref=0; drive(refdac,0); drive(divdac,0); drive(resetdac,0);
  double nextref=(20+phase)*1e-9, nextosc=std::numeric_limits<double>::infinity();
  double resettime=200e-9, enabletime=280e-9;
  unsigned long steps=0, adc_events=0; int stagnant_steps=0; double max_lag=0, tracking_time=-1;
  while(now < end-1e-16) {
    const bool was_running=rtl.RESET_N;
    const double old_frequency=frequency(rtl.DCO_CODE);
    double stop=std::min({end,nextref,nextosc,resettime,enabletime,now+step});
    double dt=0; Points updates;
    if(!xyce.provisionalStep(std::max(stop-now,1e-16),dt,updates)) throw std::runtime_error("provisional step failed");
    xyce.acceptProvisionalStep();
    // getTime() exposes nextTime, which advances again during acceptance.
    // The returned timestep is the interval actually solved (zero for DCOP).
    const double before=now; now+=dt; ++steps;
    if (phase_accum && was_running) oscillator_phase.advance(dt, old_frequency);
    stagnant_steps = now>before ? 0 : stagnant_steps+1;
    if(stagnant_steps>64) throw std::runtime_error("Xyce stopped advancing");
    if(now < before-1e-16 || now > stop+1e-14) { std::cerr << std::setprecision(17) << "before=" << before << " now=" << now << " stop=" << stop << " dt=" << dt << "\n"; throw std::runtime_error("unexpected Xyce time advance"); }
    // Preserve every ADC transition and chronological ordering. Outputs feed back
    // at this accepted endpoint; max_lag records the bounded interface latency.
    std::vector<std::tuple<double,int,int>> events;
    for(auto& [n,points]:updates) {
      int bit=n.find("UP_ADC")!=std::string::npos ? 1 : n.find("DN_ADC")!=std::string::npos ? 0 : -1;
      if(bit<0) continue;
      // Xyce may stamp DC operating-point samples with the initial trial
      // time. They describe the t=0 solution, not a future transition.
      for(auto& [t,v]:points) {
        if(dt==0 && now==0) t=0;
        if(!std::isfinite(t)||!std::isfinite(v)||t>now+1e-14) { std::cerr << std::setprecision(17) << "ADC time=" << t << " now=" << now << " dt=" << dt << " voltage=" << v << "\n"; throw std::runtime_error("invalid or future ADC sample"); }
        events.emplace_back(t,bit,v>=vdd/2);
      }
    }
    std::sort(events.begin(),events.end());
    for(size_t i=0;i<events.size();) {
      double t=std::get<0>(events[i]); int value=rtl.BBPD;
      do {auto [et,bit,state]=events[i++]; value=(value&~(1<<bit))|(state<<bit);} while(i<events.size() && std::get<0>(events[i])==t);
      if(value!=rtl.BBPD) {max_lag=std::max(max_lag,now-t); rtl.BBPD=value; evaluate(); ++adc_events;}
    }
    if(now+1e-16>=resettime) {rtl.RESET_N=1; evaluate(); resettime=INFINITY; nextosc=now+(phase_accum ? oscillator_phase.time_to_edge(frequency(rtl.DCO_CODE)) : std::round(500e3/frequency(rtl.DCO_CODE))*1e-12);}
    if(now+1e-16>=enabletime) {rtl.PLL_ENABLE=1; evaluate(); enabletime=INFINITY;}
    if(now+1e-16>=nextosc) {
      if (phase_accum) oscillator_phase.edge();
      output_clock.edge();drive_clock();
      nextosc=now+std::round(500e3/frequency(rtl.DCO_CODE))*1e-12;
    }
    if(now+1e-16>=nextref) {ref=!ref;rtl.REFCLK=ref;evaluate();drive_clock(); drive(refdac,ref); if(ref && now+10e-12<=end) trace << "REF," << (now+10e-12)*1e9 << ',' << int(rtl.DCO_CODE) << ',' << int(rtl.BBPD) << '\n'; nextref+=20e-9;}
    if (phase_accum && rtl.RESET_N) nextosc=now+oscillator_phase.time_to_edge(frequency(rtl.DCO_CODE));
    drive(divdac,rtl.CLKDIV_RETIMED); drive(resetdac,rtl.BBPD_RESET_N);
    if(rtl.TRACKING && tracking_time<0) tracking_time=now;
    if(steps%1000000==0) std::cerr << "progress_ns=" << now*1e9 << '\n';
  }
  xyce.finalize(); rtl.final();
  if(!smoke_only && (tracking_time<0||adc_events<10)) throw std::runtime_error("missing tracking or analog activity");
  std::cout << std::setprecision(12) << "rtl_cosim=pass final_ns=" << now*1e9 << " tracking_ns=" << tracking_time*1e9 << " adc_events=" << adc_events << " max_adc_lag_ps=" << max_lag*1e12 << " evaluations=" << evals << " steps=" << steps << '\n';
  return 0;
 } catch(const std::exception& e) {std::cerr << "rtl_cosim=fail error=" << e.what() << '\n'; return 1;}
}
