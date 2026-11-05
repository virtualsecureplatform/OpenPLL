// Select bounded, fully indexed real operator controls without collapsing sheets.
#include "../charge_compiler/json.hpp"
#include <filesystem>
#include <array>
#include <set>
#include <iostream>
#include <time.h>
using I=long long;namespace fs=std::filesystem;
static double uptime(){timespec t{};require(clock_gettime(CLOCK_BOOTTIME,&t)==0,"clock");return t.tv_sec+t.tv_nsec*1e-9;}
int main(int argc,char** argv){try{
 require(argc==2,"usage: sample_sheet_operators CONFIG");auto cfg=Json::read(argv[1]);double deadline=cfg.at("deadline_uptime").num();auto check=[&](){require(uptime()<deadline,"sample deadline");};check();
 fs::path out=cfg.at("output").str();require(fs::create_directory(out),"fresh sample output");
 auto fields=Json::read(cfg.at("fields").str()),mapping=Json::read(cfg.at("field_map").str());std::vector<I> owners(fields.arr().size(),-1);require(fields.at(0).at(0).str()=="@SUBSTRATE_REFERENCE"&&mapping.at(0).integer()==0,"explicit reference identity");
 struct Component{std::string name,type;std::array<I,4> box;bool rectangle;};std::vector<Component> components;
 I count=0;std::string line;
 for(const auto& part:cfg.at("geometry_partitions").arr()){
  std::ifstream input(part.at("nodes").str());require(bool(input),"geometry open");
  while(std::getline(input,line)){
   if(++count%10000==0)check();auto r=Json::parse(line);require(r.at("candidate_polygons").integer()==1&&r.at("native_area_equal").boolean()&&r.at("native_perimeter_equal").boolean()&&r.at("spatial_material_equal").boolean()&&!r.at("duplicate_component_box").boolean(),"geometry attribution incomplete");
   Component c{r.at("original_conductor").str(),part.at("native_type").str(),{},r.at("rectangle").boolean()};for(int i=0;i<4;++i)c.box[i]=r.at("bbox_gds_dbu").at(i).integer();
   I component=I(components.size());components.push_back(c);
   for(const auto& f:r.at("field_ids").arr()){I id=f.integer();require(id>0&&id<I(owners.size())&&owners[id]==-1,"invalid/duplicate field geometry");require(fields.at(size_t(id)).at(0).str()==c.name,"field/conductor identity mismatch");owners[id]=component;}
  }require(input.eof()&&!input.bad(),"geometry read");
 }
 std::ifstream ri(cfg.at("R_index").str(),std::ios::binary);require(bool(ri),"R index open");
 std::string bytes((std::istreambuf_iterator<char>(ri)),{});require(bytes.size()==16+16*fields.arr().size()&&bytes.substr(0,8)=="RBSIDX01","R index format");
 for(size_t id=1;id<fields.arr().size();++id){size_t slot=16+16*id;bool absent=true;for(int k=0;k<8;k++)absent=absent&&static_cast<unsigned char>(bytes[slot+k])==255;
  if(absent)continue;require(owners[id]<0,"R and floating field overlap");const auto& f=fields.at(id);
  owners[id]=I(components.size());components.push_back(Component{f.at(0).str(),"R:"+f.at(1).str()+"/"+f.at(2).str(),{},false});
 }
 auto context=[&](I global){Json r=Json::object();r["global_field_id"]=global;r["field"]=fields.at(size_t(global));
  if(global==0)r["explicit_reference"]=true;
  else{const auto& c=components.at(size_t(owners[global]));r["original_conductor"]=c.name;r["native_type"]=c.type;r["rectangle"]=c.rectangle;Json b=Json::array();for(I x:c.box)b.push(x);r["bbox_gds_dbu"]=b;}return r;};
 std::ifstream operators(cfg.at("operators").str());require(bool(operators),"operator input");std::ofstream rows(out/"cases.jsonl");require(bool(rows),"cases output");
 I scanned=0,selected=0,max_records=cfg.at("max_records").integer(),per_bucket=cfg.at("per_bucket").integer();require(max_records>0&&per_bucket>0,"positive sample bounds");std::map<std::string,I> buckets,ignored;
 I windows=cfg.obj().count("windows")?cfg.at("windows").integer():1;require(windows>=1&&windows<=32,"window bound");I per_window=(max_records+windows-1)/windows;std::set<I> selected_offsets;
 for(I window=0;window<windows&&scanned<max_records;++window){
  I start=I(fs::file_size(cfg.at("operators").str()))*window/windows;operators.clear();operators.seekg(start?start-1:0);
  if(start){char c;require(bool(operators.get(c)),"window seek");if(c!='\n')std::getline(operators,line);}
  for(I local=0;local<per_window&&scanned<max_records;++local){
   I record_offset=I(operators.tellg());if(!std::getline(operators,line))break;
   if(selected_offsets.count(record_offset)){++scanned;++ignored["duplicate_selected_offset"];continue;}
  if(++scanned%10000==0)check();auto op=Json::parse(line);std::string kind=op.at(0).str();require(kind=="A"||kind=="L"||kind=="F","operator kind");I la=op.at(1).integer(),lb=op.at(2).integer();require(la>=0&&lb>=0&&la<I(mapping.arr().size())&&lb<I(mapping.arr().size()),"local field map bounds");I a=mapping.at(size_t(la)).integer(),b=mapping.at(size_t(lb)).integer();require(a>=0&&b>=0&&a<I(owners.size())&&b<I(owners.size()),"global field bounds");
  if((a&&owners[a]<0)||(b&&owners[b]<0)){++ignored["unregistered_active_or_other_field"];continue;}
  if(fields.at(size_t(a)).at(1).str()=="arithmetic"||fields.at(size_t(b)).at(1).str()=="arithmetic"){++ignored["unlocated_arithmetic_field"];continue;}
  double density=op.at(kind=="A"?5:kind=="L"?6:7).num();if(density==0){++ignored["zero_density"];continue;}
  std::string category=kind+std::string(density>0?"/positive/":"/negative/")+(b==0?"reference":a&&owners[a]==owners[b]?"same_sheet":"two_sheets")+(op.at(3).integer()<0?"/restored":"/native");
  category+="/"+(a?components.at(size_t(owners[a])).type:std::string("reference"))+"-"+(b?components.at(size_t(owners[b])).type:std::string("reference"));
  if(buckets[category]>=per_bucket)continue;++buckets[category];selected_offsets.insert(record_offset);Json r=Json::object();r["sample_row"]=scanned;r["sample_window"]=window;r["operator_byte_offset"]=record_offset;r["category"]=category;r["operator"]=op;r["source"]=context(a);r["target"]=context(b);rows<<r.dump()<<'\n';require(bool(rows),"sample write");++selected;
 }
 }require(!operators.bad(),"operator read");rows.close();require(bool(rows),"sample close");
 Json result=Json::object(),bc=Json::object(),ic=Json::object();for(const auto& [k,v]:buckets)if(v)bc[k]=v;for(const auto& [k,v]:ignored)ic[k]=v;
 result["sample_windows"]=windows;result["scanned_operator_rows"]=scanned;result["selected_cases"]=selected;result["sample_buckets"]=bc;result["ignored_rows"]=ic;result["geometry_conductors"]=I(components.size());result["full_operator_coverage"]=false;result["physical_domain_complete"]=false;result["release_qualified"]=false;check();std::ofstream summary(out/"summary.json");summary<<result.dump()<<'\n';summary.close();require(bool(summary),"summary write");return 0;
}catch(const std::exception& e){std::cerr<<"sample_sheet_operators: "<<e.what()<<'\n';return 1;}}
