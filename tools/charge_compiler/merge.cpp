// Ordered local-to-global merge with streaming JSON and bounded serialization.
#include "json.hpp"
#include <array>
#include <bit>
#include <cstdint>
#include <filesystem>
#include <iostream>
#include <time.h>
using I=long long;
namespace fs=std::filesystem;
static double uptime(){timespec t{};require(clock_gettime(CLOCK_BOOTTIME,&t)==0,"clock");return t.tv_sec+t.tv_nsec*1e-9;}
struct Rows {
    std::ifstream in;Json row;bool have=false,started=false,done=false;
    explicit Rows(const fs::path& p):in(p){require(bool(in),"open array: "+p.string());in>>std::ws;require(in.get()=='[',"array start");next();}
    void next(){
        if(done){have=false;return;}in>>std::ws;
        if(started&&in.peek()==','){in.get();in>>std::ws;require(in.peek()=='[',"array row after separator");}
        else require(in.peek()==']'||(!started&&in.peek()=='['),"array separator");
        if(in.peek()==']'){in.get();in>>std::ws;require(in.peek()==EOF,"array trailing data");done=true;have=false;return;}
        std::string text;int depth=0;bool quoted=false,escaped=false;char c;
        do{require(bool(in.get(c)),"truncated array row");text+=c;
            if(quoted){if(escaped)escaped=false;else if(c=='\\')escaped=true;else if(c=='"')quoted=false;}
            else if(c=='"')quoted=true;else if(c=='['||c=='{')++depth;else if(c==']'||c=='}')--depth;
        }while(depth>0||quoted);
        row=Json::parse(text);require(std::holds_alternative<Json::Array>(row.value),"array row");started=have=true;
        in>>std::ws;require(in.peek()==','||in.peek()==']',"row separator");
    }
};
static void save(const fs::path& p,const Json& j){require(!fs::exists(p),"fresh artifact required");auto tmp=p;tmp+=".tmp";std::ofstream f(tmp);f<<j.dump()<<'\n';f.close();require(bool(f),"write");fs::rename(tmp,p);}
static void equal(const Json& a,const Json& b){
    require(a.value.index()==b.value.index(),"JSON value type differs");
    if(std::holds_alternative<double>(a.value))require(std::bit_cast<uint64_t>(a.num())==std::bit_cast<uint64_t>(b.num()),"numeric bits differ");
    else if(std::holds_alternative<std::string>(a.value))require(a.str()==b.str(),"field identity differs");
    else if(std::holds_alternative<Json::Array>(a.value)){require(a.arr().size()==b.arr().size(),"row width differs");for(size_t i=0;i<a.arr().size();++i)equal(a.at(i),b.at(i));}
    else throw std::runtime_error("unexpected comparison value");
}
int main(int argc,char** argv){try{
    if(argc==5&&std::string(argv[1])=="compare"){
        double deadline=std::stod(argv[4]);Rows a(argv[2]),b(argv[3]);I n=0;
        while(a.have&&b.have){require(uptime()<deadline,"comparison deadline");equal(a.row,b.row);a.next();b.next();++n;}
        require(!a.have&&!b.have,"row count differs");Json result=Json::object();result["identical_rows"]=n;result["numeric_values_bitwise_equal"]=true;std::cout<<result.dump()<<'\n';return 0;
    }
    require(argc==2,"usage: charge_merge CONFIG | compare FILE FILE DEADLINE");auto cfg=Json::read(argv[1]);fs::path out=cfg.at("output").str();
    double deadline=cfg.at("deadline_uptime").num();auto check=[&](){require(uptime()<deadline,"whole-check deadline exhausted");};check();
    auto receipts=Json::read(cfg.at("receipts").str());require(!receipts.arr().empty(),"empty shard set");
    fs::path field_path=out/"fields.json",ledger_path=out/"collapsed_matrix_ledger.json";
    require(!fs::exists(field_path)&&!fs::exists(ledger_path)&&!fs::exists(out/"operators_manifest.json"),"fresh merge artifacts required");
    fs::path tmp_fields=field_path;tmp_fields+=".tmp";std::ofstream fields_file(tmp_fields);require(bool(fields_file),"field output");fields_file<<'[';bool first_field=true;
    using Field=std::array<std::string,3>;std::map<Field,I> fields;
    std::map<std::pair<I,I>,std::array<double,3>> ledger;
    std::map<std::string,I> counts,components;std::map<std::string,double> residuals;Json shards=Json::array();I ledger_rows=0;
    for(size_t i=0;i<receipts.arr().size();++i){
        check();auto& proof=receipts.at(i);fs::path shard=out/("worker_"+std::to_string(i));std::vector<I> mapping;
        fs::path mapping_path=out/("worker_"+std::to_string(i)+"_field_map.json");
        require(!fs::exists(mapping_path),"fresh field map required");fs::path mapping_tmp=mapping_path;mapping_tmp+=".tmp";
        std::ofstream map_file(mapping_tmp);require(bool(map_file),"field map output");map_file<<'[';
        Rows local_fields(shard/"fields.json");
        while(local_fields.have){
            check();auto& r=local_fields.row;require(r.arr().size()==3,"field key width");Field key{r.at(0).str(),r.at(1).str(),r.at(2).str()};
            auto [it,added]=fields.emplace(key,I(fields.size()));if(added){if(!first_field)fields_file<<',';first_field=false;fields_file<<r.dump();require(bool(fields_file),"field write");}
            if(!mapping.empty())map_file<<',';map_file<<it->second;mapping.push_back(it->second);local_fields.next();
        }
        require(!mapping.empty()&&mapping[0]==0,"substrate reference mapping");
        map_file<<"]\n";map_file.close();require(bool(map_file),"field map close");fs::rename(mapping_tmp,mapping_path);
        Json spec=Json::object();spec["operators"]=(shard/"operators.jsonl").string();spec["field_map"]=mapping_path.string();spec["range_spec"]=proof.at("range_spec");shards.push(spec);
        for(auto& [key,v]:proof.at("counts").obj()){I n=v.integer();require(n>=0,"negative count");counts[key]+=n;}
        for(auto& [key,v]:proof.at("components").obj()){I n=v.integer();require(n>=0,"negative component count");components[key]+=n;}
        for(auto& [key,v]:proof.at("arithmetic_residual_absolute_native_cap_units").obj()){double n=v.num();require(n>=0,"negative arithmetic residual");residuals[key]+=n;require(std::isfinite(residuals[key]),"residual overflow");}
        Rows local_ledger(shard/"collapsed_matrix_ledger.json");
        while(local_ledger.have){
            if(++ledger_rows%10000==0)check();auto& r=local_ledger.row;require(r.arr().size()==5,"ledger row width");I a=r.at(0).integer(),b=r.at(1).integer();
            require(a>=0&&b>=0&&a<I(mapping.size())&&b<I(mapping.size()),"local field index outside map");a=mapping[a];b=mapping[b];if(b<a)std::swap(a,b);
            auto& target=ledger[{a,b}];for(int j=0;j<3;++j){target[j]+=r.at(j+2).num();require(std::isfinite(target[j]),"ledger overflow");}local_ledger.next();
        }
    }
    fields_file<<"]\n";fields_file.close();require(bool(fields_file),"fields close");fs::rename(tmp_fields,field_path);
    fs::path tmp_ledger=ledger_path;tmp_ledger+=".tmp";std::ofstream ledger_file(tmp_ledger);require(bool(ledger_file),"ledger output");ledger_file<<'[';bool first=true;
    for(auto& [key,v]:ledger){check();if(!first)ledger_file<<',';first=false;ledger_file<<Json(Json::Array{key.first,key.second,v[0],v[1],v[2]}).dump();require(bool(ledger_file),"ledger write");}
    ledger_file<<"]\n";ledger_file.close();require(bool(ledger_file),"ledger close");fs::rename(tmp_ledger,ledger_path);
    Json result=Json::object(),c=Json::object(),k=Json::object(),r=Json::object();for(auto& [key,n]:counts)c[key]=n;for(auto& [key,n]:components)k[key]=n;for(auto& [key,n]:residuals)r[key]=n;
    result["format"]="ordered_operator_shards_with_local_to_global_field_maps_v1";result["shards"]=shards;result["fields"]=field_path.string();result["counts"]=c;result["components"]=k;result["arithmetic_residual_absolute_native_cap_units"]=r;
    save(out/"operators_manifest.json",result);Json summary=Json::object();summary["global_fields"]=I(fields.size());summary["global_ledger_rows"]=I(ledger.size());summary["consumed_local_ledger_rows"]=ledger_rows;summary["runtime_model_eligible"]=false;summary["release_qualified"]=false;save(out/"merge_summary.json",summary);check();return 0;
}catch(const std::exception& e){std::cerr<<"charge_merge: "<<e.what()<<'\n';return 1;}}
