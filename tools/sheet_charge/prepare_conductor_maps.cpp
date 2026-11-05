// Map every spatial voltage to its native ideal conductor for collapse checks.
#include "../charge_compiler/json.hpp"
#include <cstdint>
#include <iostream>
#include <unordered_map>
#include <filesystem>
#include <charconv>
#include <time.h>
using I=long long;
static double now(){timespec t{};require(clock_gettime(CLOCK_BOOTTIME,&t)==0,"clock");return t.tv_sec+t.tv_nsec*1e-9;}
static void integer(std::ostream& out,uint64_t n,int bytes){for(int k=0;k<bytes;k++)out.put(char(n>>(8*k)));}
static void write_map(const std::filesystem::path& path,const char* magic,const std::vector<uint32_t>& ids,size_t nets){
 std::ofstream out(path,std::ios::binary);require(bool(out),"conductor map output");out.write(magic,8);integer(out,ids.size(),8);integer(out,nets,8);for(auto id:ids){require(id<nets,"conductor ID bounds");integer(out,id,4);}out.close();require(bool(out),"conductor map close");}
static I group_id(const std::string& name){
 for(const std::string prefix:{"_rmesh_axis_end_","_rmesh_sheet_","_zero_R_","_rmesh_"}){
  if(name.starts_with(prefix)){auto end=name.find('_',prefix.size());require(end!=std::string::npos,"group-delimited R voltage");I group=0;auto parsed=std::from_chars(name.data()+prefix.size(),name.data()+end,group);require(parsed.ec==std::errc{}&&parsed.ptr==name.data()+end&&group>0,"native R voltage group");return group;}
 }throw std::runtime_error("unknown native/latent R voltage namespace");
}
int main(int argc,char**argv){try{
 require(argc==2,"usage: prepare_conductor_maps CONFIG");auto cfg=Json::read(argv[1]);double deadline=cfg.at("deadline_uptime").num();
 auto fields=Json::read(cfg.at("fields").str());require(!fields.arr().empty()&&fields.at(0).at(0).str()=="@SUBSTRATE_REFERENCE","explicit reference field");
 std::unordered_map<std::string,uint32_t> nets;nets.reserve(fields.arr().size());std::vector<std::string> names;std::vector<uint32_t> field_net;std::vector<bool> arithmetic;
 for(auto& row:fields.arr()){require(now()<deadline&&row.arr().size()==3,"bounded valid field namespace");auto name=row.at(0).str();auto[it,added]=nets.emplace(name,uint32_t(names.size()));if(added){require(names.size()<UINT32_MAX,"conductor count");names.push_back(name);}field_net.push_back(it->second);arithmetic.push_back(row.at(1).str()=="arithmetic");}
 fields=Json();std::unordered_map<I,uint32_t> groups;std::ifstream catalog(cfg.at("catalog").str());require(bool(catalog),"selected R catalog input");std::string raw;
 while(std::getline(catalog,raw)){require(now()<deadline,"conductor catalog deadline");auto row=Json::parse(raw);auto text=row.at("native_group_id").str();I group=std::stoll(text);auto found=nets.find(row.at("original_conductor").str());require(found!=nets.end(),"R conductor exists in C fields");auto[it,added]=groups.emplace(group,found->second);require(added||it->second==found->second,"one conductor per selected native group");}
 require(catalog.eof()&&!catalog.bad(),"catalog complete read");I count=cfg.at("voltage_nodes").integer();require(count>1&&count<UINT32_MAX,"voltage map bound");std::vector<uint32_t> voltage_net(size_t(count),UINT32_MAX);voltage_net[0]=0;
 std::ifstream native(cfg.at("R_nodes").str());require(bool(native),"R voltage map input");I last=0;
 while(std::getline(native,raw)){require(now()<deadline,"R node map deadline");auto row=Json::parse(raw);I id=row.at(0).integer();require(id==last+1&&id<count,"contiguous R voltage ID");auto found=groups.find(group_id(row.at(1).str()));require(found!=groups.end(),"voltage belongs to selected final R group");voltage_net[id]=found->second;last=id;}
 require(native.eof()&&!native.bad(),"R node map complete read");I nr=last;
 std::ifstream floating(cfg.at("floating_nodes").str());require(bool(floating),"floating voltage ranges input");I last_field=0,nf=0;
 while(std::getline(floating,raw)){require(now()<deadline,"floating map deadline");auto row=Json::parse(raw);I field=row.at(0).integer(),base=row.at(1).integer(),nodes=row.at(2).integer();require(field>last_field&&field<I(field_net.size())&&!arithmetic[field],"physical ordered floating field");require(base==last+1&&nodes>0&&base+nodes<=count,"contiguous floating voltage range");for(I i=0;i<nodes;i++)voltage_net[base+i]=field_net[field];last=base+nodes-1;last_field=field;nf+=nodes;}
 require(floating.eof()&&!floating.bad()&&last==count-1,"complete floating and global voltage coverage");
 std::filesystem::path out=cfg.at("output").str();require(std::filesystem::create_directory(out),"fresh conductor map directory");write_map(out/"field_nets.bin","CNETFLD1",field_net,names.size());write_map(out/"voltage_nets.bin","CNETDOF1",voltage_net,names.size());
 std::ofstream net_names(out/"net_names.jsonl");for(size_t i=0;i<names.size();i++)net_names<<Json(Json::Array{I(i),names[i]}).dump()<<'\n';net_names.close();require(bool(net_names),"conductor names close");
 Json result=Json::object();result["global_fields"]=I(field_net.size());result["voltage_nodes"]=count;result["R_voltage_nodes"]=nr;result["floating_voltage_nodes"]=nf;result["conductor_nets"]=I(names.size());result["selected_native_groups"]=I(groups.size());result["physical_RC_qualified"]=false;result["release_qualified"]=false;std::cout<<result.dump()<<'\n';return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 2;}}
