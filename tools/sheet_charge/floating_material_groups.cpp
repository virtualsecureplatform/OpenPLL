#include "../charge_compiler/json.hpp"
#include "conductor_map.hpp"
#include <atomic>
#include <memory>
#include <omp.h>
#include <iostream>
#include <time.h>
static double now(){timespec t{};require(clock_gettime(CLOCK_BOOTTIME,&t)==0,"clock");return t.tv_sec+t.tv_nsec*1e-9;}
static void integer(std::ostream& out,uint64_t value,int bytes){for(int k=0;k<bytes;k++)out.put(char(value>>(8*k)));}
int main(int argc,char**argv){try{
 require(argc==2,"usage: floating_material_groups CONFIG");auto cfg=Json::read(argv[1]);ConductorMap fields(cfg.at("field_map").str(),"CNETFLD1");auto groups=std::make_unique<std::atomic<uint8_t>[]>(fields.net_count());for(uint64_t i=0;i<fields.net_count();i++)groups[i]=0;
 auto& parts=cfg.at("parts").arr();require(parts.size()==7,"seven floating material partitions");std::vector<std::exception_ptr> errors(7);std::vector<long long> counts(7);double deadline=cfg.at("deadline_uptime").num();
 #pragma omp parallel for num_threads(7)
 for(int part=0;part<7;part++){try{std::ifstream input(parts[part].at("path").str());require(bool(input),"floating material instance input");std::string raw;
  while(std::getline(input,raw)){require(now()<deadline,"floating material grouping deadline");auto row=Json::parse(raw);require(row.at("native_type").str()==parts[part].at("native_type").str(),"floating material partition identity");uint64_t field=uint64_t(row.at("physical_field_id").integer());uint32_t conductor=fields.at(field);require(conductor>0&&groups[conductor].exchange(uint8_t(part+1))==0,"one material instance per floating conductor");counts[part]++;}
  require(input.eof()&&!input.bad(),"floating material complete read");
 }catch(...){errors[part]=std::current_exception();}}
 for(auto& e:errors)if(e)std::rethrow_exception(e);long long total=0;for(auto n:counts)total+=n;require(total==cfg.at("expected_floating_conductors").integer(),"floating conductor coverage");
 std::ofstream out(cfg.at("output").str(),std::ios::binary);require(bool(out),"material group map output");out.write("CNETDOF1",8);integer(out,fields.net_count(),8);integer(out,8,8);for(uint64_t i=0;i<fields.net_count();i++)integer(out,groups[i].load(),4);out.close();require(bool(out),"material group map close");
 Json result=Json::object(),rows=Json::array();for(int i=0;i<7;i++)rows.push(Json::Array{i+1,parts[i].at("native_type").str(),counts[i]});result["material_groups"]=rows;result["floating_conductors"]=total;result["fixed_conductors"]=static_cast<long long>(fields.net_count())-total;result["physical_RC_qualified"]=false;result["release_qualified"]=false;std::cout<<result.dump()<<'\n';return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 2;}}
