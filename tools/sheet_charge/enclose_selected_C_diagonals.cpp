// Analytic enclosures of complete selected source contributions, before sparse rounding.
#include "registered_fringe_interval.hpp"
#include "runtime_geometry_v2.hpp"
#include "bounded_jsonl_range.hpp"
#include <filesystem>
using Interval=fringe_interval::Interval;
static Q scaled_integer(const std::string&n,int exponent){Q q(mpz_class(n),mpz_class(1));if(exponent>=0)mpq_mul_2exp(q.get_mpq_t(),q.get_mpq_t(),exponent);else mpq_div_2exp(q.get_mpq_t(),q.get_mpq_t(),-exponent);return q;}
static bool zero_measure(const Json&op){
 auto kind=op.at(0).str();auto&a=op.at(4);double density=op.at(kind=="A"?5:kind=="L"?6:7).num();if(density==0)return true;
 if(kind=="A")return a.at(0).integer()==a.at(2).integer()||a.at(1).integer()==a.at(3).integer();
 if(kind=="L")return a.at(0).integer()==a.at(2).integer()&&a.at(1).integer()==a.at(3).integer();
 require(kind=="F","selected kernel kind");if(op.at(8).num()==0)return true;auto&b=op.at(5);int direction=op.at(6).integer(),normal=(direction==1||direction==4)?0:1,sign=(direction==1||direction==8)?-1:1;
 I origin=a.at(normal).integer(),lo=b.at(normal).integer(),hi=b.at(normal+2).integer();if(sign>0)lo=std::max(lo,origin);else hi=std::min(hi,origin);
 return lo==hi||b.at(1-normal).integer()==b.at(3-normal).integer();
}
int main(int argc,char**argv){try{
 require(argc==2,"usage CONFIG");auto cfg=Json::read(argv[1]);double deadline=cfg.at("deadline_uptime").num();
 I bits=cfg.at("precision_bits").integer(),threads=cfg.at("threads").integer();require(bits>=128&&bits<=1024&&threads>0&&threads<=16,"bounded diagonal enclosure resources");
 fringe_interval::precision=bits;RuntimeGeometry geometry(cfg.at("geometry"));require(geometry.node_count()==uint64_t(cfg.at("expected_voltage_nodes").integer()),"original voltage namespace count");
 auto targets=Json::read(cfg.at("targets").str());std::map<uint64_t,I>voltage_target;std::map<I,Q>stored;
 int exponent=targets.at("energy_binary_quantum_exponent").integer();
 for(const auto&r:targets.at("negative_nodes").arr()){
  I row=r.at("row").integer();require(row>0&&stored.emplace(row,scaled_integer(r.at("energy_integer").str(),exponent)).second,"unique diagonal targets");
  for(const auto&n:r.at("original_voltage_nodes").arr()){
   I node=n.at("node").integer();require(node>0&&geometry.name(node)==n.at("name").str()&&voltage_target.emplace(node,row).second,"exact target voltage identity");
  }
 }
 const auto&tasks=cfg.at("tasks").arr();require(!tasks.empty()&&tasks.size()<=16384,"bounded selected tasks");
 std::map<std::string,std::shared_ptr<const std::vector<I>>>maps;std::vector<std::shared_ptr<const std::vector<I>>>mapping;
 std::set<I>task_ids;
 for(const auto&t:tasks){require(task_ids.insert(t.at("task").integer()).second,"unique original task IDs");auto path=t.at("field_map").str();
  if(!maps.contains(path)){auto json=Json::read(path);auto values=std::make_shared<std::vector<I>>();for(const auto&id:json.arr())values->push_back(id.integer());require(!values->empty()&&values->at(0)==0,"selected map explicit reference");maps.emplace(path,values);}mapping.push_back(maps.at(path));
 }
 std::vector<std::map<I,Interval>>sums(tasks.size());std::vector<uint64_t>counts(tasks.size());std::vector<std::exception_ptr>errors(tasks.size());std::atomic<bool>cancelled{false};
 #pragma omp parallel for num_threads(threads) schedule(dynamic,1)
 for(I task=0;task<I(tasks.size());task++){if(cancelled.load())continue;try{
  fringe_interval::precision=bits;const auto&t=tasks[task];const auto&map=*mapping[task];
  std::ifstream input(t.at("selected_operators").str()),offsets(t.at("selected_offsets").str(),std::ios::binary),original(t.at("operators").str(),std::ios::binary);
  require(bool(input)&&bool(offsets)&&bool(original),"selected diagonal source streams");std::string raw;uint64_t prior=0;
  while(std::getline(input,raw)){
   if(counts[task]++%1000==0)require(uptime()<deadline,"selected diagonal integration deadline");char bytes[8];offsets.read(bytes,8);require(bool(offsets),"complete selected source offsets");
   uint64_t offset=0;for(int k=0;k<8;k++)offset|=uint64_t(static_cast<unsigned char>(bytes[k]))<<(8*k);
   require(offset>=uint64_t(t.at("begin_byte").integer())&&offset<uint64_t(t.at("end_byte").integer())&&(counts[task]==1||offset>prior),"owned increasing selected source offsets");prior=offset;
   original.clear();original.seekg(offset);std::string physical;require(bool(std::getline(original,physical))&&!original.eof()&&physical==raw,"selected record equals original source bytes");
   auto op=Json::parse(raw);I a=op.at(1).integer(),b=op.at(2).integer();require(a>=0&&b>=0&&a<I(map.size())&&b<I(map.size()),"selected local field bounds");a=map[a];b=map[b];require(geometry.physical(a)&&geometry.physical(b),"selected physical fields");
   if(zero_measure(op))continue;
   std::array<I,4>support;for(int d=0;d<4;d++)support[d]=op.at(4).at(d).integer();P shift{Q(long(support[0])),Q(long(support[1]))};LocalRuntimeNodes nodes;
   auto source=geometry.resolve(a,support,shift,nodes);auto kind=op.at(0).str();auto target_support=support;
   if(kind!="A")for(int d=0;d<4;d++)target_support[d]=op.at(5).at(d).integer();auto target=geometry.resolve(b,target_support,shift,nodes);auto rect=box(op.at(4),shift);
   auto add=[&](int i,int j,const Interval&value){
    auto x=voltage_target.find(nodes.global.at(i)),y=voltage_target.find(nodes.global.at(j));
    if(x==voltage_target.end()||y==voltage_target.end()||x->second!=y->second)return;
    Interval factor(Q(i==j?1:2));auto&sum=sums[task][x->second];sum=sum+factor*value;
   };
   if(kind=="A"||kind=="L"){
    auto exact=kind=="A"?area(source,target,rect,Q(op.at(5).num())):line(source,target,edge(rect),edge(box(op.at(5),shift)),Q(op.at(6).num()));
    for(const auto&[ij,v]:exact){auto r=exact.find({ij.second,ij.first});require(r!=exact.end()&&r->second==v,"selected exact local symmetry");if(ij.first<=ij.second)add(ij.first,ij.second,Interval(v));}
   }else{
    require(kind=="F","selected supported kernel");auto matrix=fringe_certified(source,target,edge(rect),box(op.at(5),shift),op.at(6).integer(),Q(op.at(7).num()),Q(op.at(8).num()));
    for(const auto&[ij,v]:matrix)add(ij.first,ij.second,v);
   }
  }
  char extra;require(input.eof()&&!input.bad()&&!offsets.get(extra)&&offsets.eof(),"complete selected source records and offsets");
  require(counts[task]==uint64_t(t.at("selected_count").integer()),"selected task exact count");
 }catch(...){errors[task]=std::current_exception();cancelled=true;}}
 for(const auto&e:errors)if(e)std::rethrow_exception(e);uint64_t total=0;for(auto n:counts)total+=n;require(total==uint64_t(cfg.at("expected_selected_operators").integer()),"all selected operators integrated");
 std::map<I,Interval>sum;for(const auto&part:sums)for(const auto&[row,value]:part)sum[row]=sum[row]+value;
 Json rows=Json::array();I negative=0,positive=0,zero=0,uncertain=0;
 for(const auto&[row,old]:stored){const auto&value=sum[row];Json r=Json::object();r["row"]=row;r["interval"]=fringe_interval::json(value);r["stored_conservative_diagonal_exact"]=old.get_str();
  std::string sign;if(mpfr_sgn(value.hi)<0){sign="strictly_negative";negative++;}else if(mpfr_sgn(value.lo)>0){sign="strictly_positive";positive++;}else if(mpfr_zero_p(value.lo)&&mpfr_zero_p(value.hi)){sign="exact_zero";zero++;}else{sign="encloses_zero";uncertain++;}
  r["sign"]=sign;r["stored_coefficient_below_interval"]=mpfr_cmp_q(value.lo,old.get_mpq_t())>0;r["stored_coefficient_above_interval"]=mpfr_cmp_q(value.hi,old.get_mpq_t())<0;rows.push(r);
 }
 Json report=Json::object();report["selected_operators_integrated"]=I(total);report["target_diagonal_rows"]=I(stored.size());report["rows"]=rows;
 report["strictly_negative_enclosures"]=negative;report["strictly_positive_enclosures"]=positive;report["exact_zero_enclosures"]=zero;report["enclosures_containing_zero"]=uncertain;
 report["physical_RC_qualified"]=false;report["full_matrix_passivity_verified"]=false;report["release_qualified"]=false;
 std::ofstream out(cfg.at("report").str());out<<report.dump()<<'\n';out.close();require(bool(out),"selected diagonal report close");return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
