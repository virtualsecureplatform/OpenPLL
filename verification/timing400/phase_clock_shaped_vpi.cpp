// SPDX-License-Identifier: Apache-2.0
// Sparse exact-code clock bridge. This is not a validated physical DCO model.
#include "phase_clock_shaped.h"
#include <vpi_user.h>
#include <array>
#include <fstream>
#include <map>
#include <memory>
#include <sstream>
#include <string>

namespace {
std::uint64_t ticks() {
  s_vpi_time t{};t.type=vpiSimTime;vpi_get_time(nullptr,&t);
  return (std::uint64_t(t.high)<<32)|t.low;
}

std::string option(const std::string& key) {
  s_vpi_vlog_info info{};vpi_get_vlog_info(&info);
  std::string value;
  for(int i=0;i<info.argc;++i) {
    const std::string arg=info.argv[i];
    if(arg.compare(0,key.size(),key)==0) {
      if(!value.empty()) throw std::runtime_error("DUPLICATE_OPTION");
      value=arg.substr(key.size());
    }
  }
  if(value.empty()) throw std::runtime_error("MISSING_OPTION_"+key);
  return value;
}

class Driver;
std::unique_ptr<Driver> driver;
PLI_INT32 control_callback(p_cb_data);
PLI_INT32 edge_callback(p_cb_data);

class Driver {
  std::array<vpiHandle,4> signals_{}; // PLLOUT, coarse, fine, reset_n
  std::map<std::pair<unsigned,unsigned>,std::uint64_t> table_;
  Phase400ShapedClock phase_;
  std::ofstream trace_;
  vpiHandle edge_=nullptr;
  bool control_pending_=false, active_=false, level_=true;
  unsigned coarse_=0,fine_=0;

  unsigned read(unsigned index) {
    s_vpi_value value{};value.format=vpiVectorVal;
    vpi_get_value(signals_[index],&value);
    if(value.value.vector[0].bval) throw std::runtime_error("CONTROL_XZ");
    return unsigned(value.value.vector[0].aval);
  }
  void cancel() {
    if(edge_) {vpi_remove_cb(edge_);edge_=nullptr;}
  }
  void record(const char* event) {
    trace_<<event<<','<<ticks()<<','<<unsigned(level_)<<','<<coarse_<<','<<fine_<<','<<phase_.frequency()<<'\n';
  }
  void output(bool level,const char* event) {
    level_=level;
    s_vpi_value value{};value.format=vpiIntVal;value.value.integer=level;
    vpi_put_value(signals_[0],&value,nullptr,vpiNoDelay);
    record(event);
  }
  void schedule() {
    const std::uint64_t delta=phase_.delay();
    s_vpi_time time{};time.type=vpiSimTime;time.high=delta>>32;time.low=delta&0xffffffffULL;
    s_cb_data callback{};callback.reason=cbAfterDelay;callback.cb_rtn=edge_callback;callback.time=&time;
    edge_=vpi_register_cb(&callback);
    if(!edge_) throw std::runtime_error("EDGE_CALLBACK_FAILED");
  }
 public:
  explicit Driver(std::array<vpiHandle,4> signals):signals_(signals) {
    if(vpi_get(vpiTimePrecision,nullptr)!=-12)
      throw std::runtime_error("REQUIRES_1PS_PRECISION");
    const auto duty=option("+phase400_duty_ppm=");
    std::size_t consumed=0;
    const auto parsed=std::stoul(duty,&consumed);
    if(consumed!=duty.size() || parsed>=1000000) throw std::runtime_error("INVALID_DUTY_CONFIGURATION");
    phase_.configure_duty(unsigned(parsed));
    std::ifstream file(option("+phase400_table="));
    if(!file) throw std::runtime_error("MODEL_TABLE_OPEN_FAILED");
    std::string line;
    while(std::getline(file,line)) {
      if(line.empty() || line[0]=='#') continue;
      std::istringstream row(line);
      unsigned band,code;std::uint64_t frequency;std::string extra;
      if(!(row>>band>>code>>frequency) || row>>extra || band>=48 || code>255 ||
          !frequency || frequency>=Phase400ShapedClock::half_cycle ||
          !table_.emplace(std::make_pair(band,code),frequency).second)
        throw std::runtime_error("MODEL_TABLE_INVALID");
    }
    if(!file.eof() || table_.empty()) throw std::runtime_error("MODEL_TABLE_INVALID");
    trace_.open(option("+phase400_trace="));
    if(!trace_) throw std::runtime_error("TRACE_OPEN_FAILED");
    trace_<<"event,time_ps,level,coarse,fine,frequency_millihz\n";
    for(unsigned i=1;i<signals_.size();++i) {
      s_vpi_time time{};time.type=vpiSuppressTime;
      s_vpi_value value{};value.format=vpiSuppressVal;
      s_cb_data callback{};callback.reason=cbValueChange;callback.cb_rtn=control_callback;
      callback.obj=signals_[i];callback.time=&time;callback.value=&value;
      if(!vpi_register_cb(&callback)) throw std::runtime_error("CONTROL_CALLBACK_FAILED");
    }
  }
  void request_control() {
    if(control_pending_) return;
    control_pending_=true;
    s_vpi_time time{};time.type=vpiSimTime;
    s_cb_data callback{};callback.reason=cbReadWriteSynch;callback.cb_rtn=control_callback;
    callback.time=&time;callback.user_data=reinterpret_cast<PLI_BYTE8*>(this);
    if(!vpi_register_cb(&callback)) throw std::runtime_error("SYNC_CALLBACK_FAILED");
  }
  void control() {
    control_pending_=false;
    cancel();
    if(!read(3)) {
      phase_.reset(ticks());active_=false;
      // The actual NAND-gated DCO drives PLLOUT high while reset is asserted.
      output(true,"RESET");
      return;
    }
    coarse_=read(1);fine_=read(2);
    const auto found=table_.find({coarse_,fine_});
    if(found==table_.end()) throw std::runtime_error("MODEL_LOOKUP_MISSING");
    if(!active_) {phase_.reset(ticks());active_=true;}
    phase_.tune(ticks(),found->second);
    record("TUNE");schedule();
  }
  void edge() {
    edge_=nullptr;
    if(!active_) return;
    if(!read(3)) {phase_.reset(ticks());active_=false;output(true,"RESET");return;}
    phase_.edge(ticks());output(!level_,"EDGE");schedule();
  }
  void error(const char* reason) {
    cancel();record("ERROR");trace_.flush();
    vpi_printf("PLL400_PHASE_ERROR: %s at %llu ps\n",reason,(unsigned long long)ticks());
    vpip_set_return_value(1);
    vpi_control(vpiFinish,1);
  }
};

void error(const char* reason) {
  if(driver) driver->error(reason);
  else {vpi_printf("PLL400_PHASE_ERROR: %s\n",reason);vpip_set_return_value(1);vpi_control(vpiFinish,1);}
}

PLI_INT32 control_callback(p_cb_data callback) {
  try {
    if(callback->user_data) driver->control();
    else driver->request_control();
  } catch(const std::exception& exception) {error(exception.what());}
  return 0;
}
PLI_INT32 edge_callback(p_cb_data) {
  try {driver->edge();} catch(const std::exception& exception) {error(exception.what());}
  return 0;
}
PLI_INT32 start(PLI_BYTE8*) {
  try {
    if(driver) throw std::runtime_error("ONE_OSCILLATOR_PER_BRIDGE");
    const auto call=vpi_handle(vpiSysTfCall,nullptr);
    auto iterator=vpi_iterate(vpiArgument,call);
    std::array<vpiHandle,4> args{};
    const std::array<int,4> widths{{1,6,8,1}};
    for(unsigned i=0;i<args.size();++i) {
      args[i]=iterator ? vpi_scan(iterator) : nullptr;
      if(!args[i] || vpi_get(vpiSize,args[i])!=widths[i])
        throw std::runtime_error("CLOCK_ARGUMENT_WIDTHS_MUST_BE_1_6_8_1");
    }
    if(vpi_scan(iterator)) throw std::runtime_error("CLOCK_ARGUMENT_COUNT");
    driver.reset(new Driver(args));
    driver->request_control();
  } catch(const std::exception& exception) {error(exception.what());}
  return 0;
}
void register_phase() {
  s_vpi_systf_data task{};task.type=vpiSysTask;
  task.tfname=const_cast<PLI_BYTE8*>("$pll400_phase_clock");task.calltf=start;
  vpi_register_systf(&task);
}
} // namespace

extern "C" {
void (*vlog_startup_routines[])()={register_phase,nullptr};
}
