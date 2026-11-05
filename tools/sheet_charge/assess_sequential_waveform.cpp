#include "../charge_compiler/json.hpp"
#include <array>
#include <cstdint>
#include <algorithm>
#include <limits>
#include <iostream>
#include <time.h>
using I=long long;
static double now(){timespec t{};require(clock_gettime(CLOCK_BOOTTIME,&t)==0,"clock");return t.tv_sec+t.tv_nsec*1e-9;}
static std::string_view token(std::string_view&s){size_t begin=s.find_first_not_of(" \t\r");if(begin==s.npos){s={};return{};}s.remove_prefix(begin);auto end=s.find_first_of(" \t\r");auto out=s.substr(0,end);if(end==s.npos)s={};else s.remove_prefix(end);return out;}
static double number(std::string_view t){require(!t.empty(),"waveform number required");double v;auto r=std::from_chars(t.data(),t.data()+t.size(),v);require(r.ec==std::errc{}&&r.ptr==t.data()+t.size()&&std::isfinite(v),"complete finite waveform number");return v;}
struct Cross {std::array<std::vector<double>,2> events;void add(double ta,double tb,double a,double b,double threshold){if(a<threshold&&threshold<=b)events[1].push_back(ta+(tb-ta)*(threshold-a)/(b-a));if(b<threshold&&threshold<=a)events[0].push_back(ta+(tb-ta)*(threshold-a)/(b-a));}};
struct Case {std::array<double,4> initial{},previous{};double minimum=std::numeric_limits<double>::infinity(),maximum=-std::numeric_limits<double>::infinity();Cross clock,reset;std::array<Cross,3> output;};
static void append(Json&r,const char*key,double value){if(!r.obj().contains(key))r[key]=Json::array();r[key].push(value);}
int main(int argc,char**argv){try{
 require(argc==2,"usage CONFIG");auto cfg=Json::read(argv[1]);auto plan=Json::read(cfg.at("plan").str());auto&fixtures=plan.at("fixtures").arr();auto&columns=plan.at("waveform_columns").arr();require(!fixtures.empty()&&columns.size()==4*fixtures.size(),"sequential fixture dimensions");double deadline=cfg.at("deadline_uptime").num();std::vector<Case> cases(fixtures.size());std::ifstream input(cfg.at("waveform").str());require(bool(input),"waveform open");std::string line;require(bool(std::getline(input,line)),"waveform header");std::string_view rest=line;require(token(rest)=="Index"&&token(rest)=="TIME","waveform index/time columns");for(auto&column:columns)require(token(rest)==column.str(),"exact sequential signal column");require(token(rest).empty(),"waveform column count");uint64_t rows=0;bool terminal=false;double previous_time=0,last_time=0;const std::array<double,3> levels{.36,.9,1.44};
 while(std::getline(input,line)){
  if(rows%1000==0)require(now()<deadline,"sequential assessment deadline");
  if(line.find("End of Xyce(TM) Simulation")!=line.npos){require(!terminal,"unique sequential terminal marker");terminal=true;continue;}
  rest=line;auto index=token(rest);if(index.empty())continue;require(!terminal,"data after terminal marker");uint64_t n;auto parsed=std::from_chars(index.data(),index.data()+index.size(),n);require(parsed.ec==std::errc{}&&parsed.ptr==index.data()+index.size()&&n==rows,"contiguous waveform row index");double t=number(token(rest));require(rows?t>previous_time:t==0,"strictly increasing waveform time");
  for(auto&c:cases){std::array<double,4> v;for(auto&value:v)value=number(token(rest));if(!rows)c.initial=v;else{c.clock.add(previous_time,t,c.previous[0],v[0],.9);c.reset.add(previous_time,t,c.previous[2],v[2],.9);for(size_t l=0;l<3;l++)c.output[l].add(previous_time,t,c.previous[3],v[3],levels[l]);}c.minimum=std::min(c.minimum,v[3]);c.maximum=std::max(c.maximum,v[3]);c.previous=v;}
  require(token(rest).empty(),"sequential waveform row width");rows++;previous_time=t;last_time=t;
 }
 require(input.eof()&&terminal&&rows>1&&last_time>=plan.at("stop_ns").num()*1e-9-1e-15,"complete terminal sequential waveform");Json records=Json::array();I passing=0;
 for(size_t i=0;i<cases.size();i++){
  require(now()<deadline,"sequential record deadline");auto&c=cases[i];auto&f=fixtures[i];auto kind=f.at("kind").str();require(kind=="clock_toggle"||kind=="async_assert","known sequential fixture kind");int reset=f.at("reset_value").integer();require(reset==0||reset==1,"binary reset value");auto&targets=f.at("expected_captured_values").arr();require(targets.size()==4,"four expected captures");Json r=Json::object();r["case_index"]=I(i);r["passed"]=false;r["output_min_v"]=c.minimum;r["output_max_v"]=c.maximum;
  try{
   require(std::fabs(c.initial[2])<1e-6&&std::fabs(c.initial[0])<1e-6,"initial reset and clock");require(reset?c.initial[3]>=1.62:c.initial[3]<=.18,"initial reset output");require(c.minimum<.18&&c.maximum>1.62,"output rails");auto&clocks=c.clock.events[1];require(clocks.size()==4,"four rising clock edges");std::array<std::vector<double>,2> transitions;int previous=reset;
   for(size_t k=0;k<4;k++){int target=targets[k].integer();require(target==0||target==1,"binary capture value");if(kind=="async_assert")previous=reset;require(target!=previous,"expected transition");bool rising=target>previous;uint64_t count=0;double selected=0;for(double u:c.output[1].events[rising])if(clocks[k]-1e-9<u&&u<clocks[k]+5e-9){count++;selected=u;}require(count==1,"unique capture output edge");transitions[rising].push_back(selected);previous=target;append(r,rising?"clock_to_q_rise_ns":"clock_to_q_fall_ns",(selected-clocks[k])*1e9);}
   if(kind=="clock_toggle")require(c.output[1].events[0].size()==2&&c.output[1].events[1].size()==2,"two transitions per direction");
   else{bool rising=bool(reset);auto&starts=c.reset.events[0];require(starts.size()==3,"three asynchronous assertions");require(c.output[1].events[rising].size()==3&&c.output[1].events[!rising].size()==4,"asynchronous output edge counts");for(double t:starts){uint64_t count=0;double selected=0;for(double u:c.output[1].events[rising])if(t-1e-9<u&&u<t+5e-9){count++;selected=u;}require(count==1,"unique assertion output edge");transitions[rising].push_back(selected);append(r,"assertion_to_q_ns",(selected-t)*1e9);}}
   for(int rising=0;rising<2;rising++){auto&first=c.output[rising?0:2].events[rising];auto&last=c.output[rising?2:0].events[rising];if(transitions[rising].empty())continue;Json slews=Json::array();for(double center:transitions[rising]){bool found_left=false,found_right=false;double left=-std::numeric_limits<double>::infinity(),right=std::numeric_limits<double>::infinity();for(double t:first)if(center-5e-9<t&&t<=center){found_left=true;left=std::max(left,t);}for(double t:last)if(center<=t&&t<center+5e-9){found_right=true;right=std::min(right,t);}require(found_left&&found_right,"bracketing output thresholds");double slew=(right-left)*1e9;require(slew>0,"positive output slew");slews.push(slew);}r[rising?"output_rise_20_80_ns":"output_fall_80_20_ns"]=slews;}
   r["passed"]=true;passing++;
  }catch(const std::runtime_error&){r["reason"]="DC rail, event/state or threshold correspondence failed";}
  records.push(r);
 }
 Json result=Json::object();result["fixtures"]=I(cases.size());result["passing"]=passing;result["records"]=records;result["waveform_rows"]=I(rows);result["all_native_waveform_events_terminal"]=true;std::ofstream output(cfg.at("report").str());output<<result.dump()<<'\n';require(bool(output),"sequential assessment report close");return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
