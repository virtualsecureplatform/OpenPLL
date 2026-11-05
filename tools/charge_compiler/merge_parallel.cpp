// Ordered local-to-global merge with streaming JSON and bounded serialization.
#include "json.hpp"
#include <array>
#include <bit>
#include <cstdint>
#include <filesystem>
#include <iostream>
#include <time.h>
#include <parallel/algorithm>
#include <omp.h>
#include <charconv>
#include <unordered_map>
#include <atomic>
#include <exception>
#include <limits>
using I=long long;
namespace fs=std::filesystem;
static double uptime(){timespec t{};require(clock_gettime(CLOCK_BOOTTIME,&t)==0,"clock");return t.tv_sec+t.tv_nsec*1e-9;}
struct Rows {
    std::ifstream in;Json row;bool have=false,started=false,done=false;
    std::vector<char> buffer;size_t pos=0,end=0;std::string text;
    int peek(){if(pos==end){in.read(buffer.data(),std::streamsize(buffer.size()));end=size_t(in.gcount());pos=0;require(!in.bad(),"array read failure");if(!end)return EOF;}return static_cast<unsigned char>(buffer[pos]);}
    int get(){int c=peek();if(c!=EOF)++pos;return c;}
    void ws(){while(peek()==' '||peek()=='\t'||peek()=='\n'||peek()=='\r')get();}
    explicit Rows(const fs::path& p):in(p,std::ios::binary),buffer(1<<20){require(bool(in),"open array: "+p.string());text.reserve(256);ws();require(get()=='[',"array start");next();}
    void next(){
        if(done){have=false;return;}ws();
        if(started&&peek()==','){get();ws();require(peek()=='[',"array row after separator");}
        else require(peek()==']'||(!started&&peek()=='['),"array separator");
        if(peek()==']'){get();ws();require(peek()==EOF,"array trailing data");done=true;have=false;return;}
        text.clear();int depth=0;bool quoted=false,escaped=false;
        do{int n=get();require(n!=EOF,"truncated array row");char c=char(n);text+=c;
            if(quoted){if(escaped)escaped=false;else if(c=='\\')escaped=true;else if(c=='"')quoted=false;}
            else if(c=='"')quoted=true;else if(c=='['||c=='{')++depth;else if(c==']'||c=='}')--depth;
        }while(depth>0||quoted);
        row=Json::parse(text);require(std::holds_alternative<Json::Array>(row.value),"array row");started=have=true;
        ws();require(peek()==','||peek()==']',"row separator");
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
    double phase_start=uptime();
    auto receipts=Json::read(cfg.at("receipts").str());require(!receipts.arr().empty(),"empty shard set");
    fs::path field_path=out/"fields.json",ledger_path=out/"collapsed_matrix_ledger.json";
    require(!fs::exists(field_path)&&!fs::exists(ledger_path)&&!fs::exists(out/"operators_manifest.json"),"fresh merge artifacts required");
    fs::path tmp_fields=field_path;tmp_fields+=".tmp";std::ofstream fields_file(tmp_fields);require(bool(fields_file),"field output");fields_file<<'[';bool first_field=true;
    using Field=std::array<std::string,3>;
    struct FieldHash {size_t operator()(const Field& f)const{size_t h=0;for(const auto& x:f)h^=std::hash<std::string>{}(x)+size_t(0x9e3779b9)+(h<<6)+(h>>2);return h;}};
    std::unordered_map<Field,I,FieldHash> fields;
    struct Entry { I a,b,sequence;std::array<double,3> values; };
    std::vector<Entry> ledger;
    std::vector<std::vector<I>> mappings(receipts.arr().size());
    I threads=cfg.obj().count("threads")?cfg.at("threads").integer():16;
    require(threads>=1&&threads<=32,"sort thread limit");omp_set_dynamic(0);omp_set_num_threads(int(threads));
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
        mappings[i]=std::move(mapping);
    }
    fields_file<<"]\n";fields_file.close();require(bool(fields_file),"fields close");fs::rename(tmp_fields,field_path);
    double field_seconds=uptime()-phase_start;phase_start=uptime();
    std::vector<std::vector<Entry>> parts(receipts.arr().size());
    std::vector<std::exception_ptr> errors(parts.size());std::atomic<bool> cancelled{false};
    #pragma omp parallel for schedule(dynamic,1)
    for(I worker=0;worker<I(parts.size());++worker){
        size_t i=size_t(worker);if(cancelled.load())continue;
        try{
            check();const auto& mapping=mappings[i];auto& part=parts[i];
            Rows rows(out/("worker_"+std::to_string(i))/"collapsed_matrix_ledger.json");
            I local_rows=0;
            while(rows.have){
                if(local_rows++%10000==0){check();if(cancelled.load())break;}
                auto& r=rows.row;require(r.arr().size()==5,"ledger row width");I a=r.at(0).integer(),b=r.at(1).integer();
                require(a>=0&&b>=0&&a<I(mapping.size())&&b<I(mapping.size()),"local field index outside map");a=mapping[a];b=mapping[b];if(b<a)std::swap(a,b);
                Entry entry{a,b,0,{}};for(int j=0;j<3;++j){entry.values[j]=r.at(j+2).num();require(std::isfinite(entry.values[j]),"nonfinite ledger input");}
                part.push_back(entry);rows.next();
            }
        }catch(...){errors[i]=std::current_exception();cancelled.store(true);}
    }
    for(const auto& error:errors)if(error)std::rethrow_exception(error);
    check();size_t total=0;for(const auto& part:parts){require(part.size()<=size_t(std::numeric_limits<I>::max())-total,"row count overflow");total+=part.size();}
    ledger.reserve(total);
    for(auto& part:parts){for(auto& entry:part){entry.sequence=++ledger_rows;ledger.push_back(entry);}std::vector<Entry>().swap(part);}
    std::vector<std::vector<I>>().swap(mappings);
    double ledger_read_seconds=uptime()-phase_start;
    check();
    double input_seconds=field_seconds+ledger_read_seconds;phase_start=uptime();
    __gnu_parallel::sort(ledger.begin(),ledger.end(),[](const Entry& a,const Entry& b){return std::tie(a.a,a.b,a.sequence)<std::tie(b.a,b.b,b.sequence);});
    double sort_seconds=uptime()-phase_start;phase_start=uptime();
    check();I global_rows=0;
    fs::path tmp_ledger=ledger_path;tmp_ledger+=".tmp";std::ofstream ledger_file(tmp_ledger);require(bool(ledger_file),"ledger output");ledger_file<<'[';bool first=true;
    for(size_t at=0;at<ledger.size();){
        check();I a=ledger[at].a,b=ledger[at].b;std::array<double,3> values{};
        do{for(int j=0;j<3;++j){values[j]+=ledger[at].values[j];require(std::isfinite(values[j]),"ledger overflow");}++at;}while(at<ledger.size()&&ledger[at].a==a&&ledger[at].b==b);
        if(!first)ledger_file<<',';first=false;ledger_file<<'[';
        auto integer=[&](I n){char buffer[32];auto result=std::to_chars(buffer,buffer+sizeof(buffer),n);require(result.ec==std::errc{},"integer serialization");ledger_file.write(buffer,result.ptr-buffer);};
        auto number=[&](double n){char buffer[64];auto result=std::to_chars(buffer,buffer+sizeof(buffer),n,std::chars_format::general,17);require(result.ec==std::errc{},"number serialization");ledger_file.write(buffer,result.ptr-buffer);};
        integer(a);ledger_file<<',';integer(b);for(double n:values){ledger_file<<',';number(n);}ledger_file<<']';require(bool(ledger_file),"ledger write");++global_rows;
    }
    ledger_file<<"]\n";ledger_file.close();require(bool(ledger_file),"ledger close");fs::rename(tmp_ledger,ledger_path);
    Json result=Json::object(),c=Json::object(),k=Json::object(),r=Json::object();for(auto& [key,n]:counts)c[key]=n;for(auto& [key,n]:components)k[key]=n;for(auto& [key,n]:residuals)r[key]=n;
    result["format"]="ordered_operator_shards_with_local_to_global_field_maps_v1";result["shards"]=shards;result["fields"]=field_path.string();result["counts"]=c;result["components"]=k;result["arithmetic_residual_absolute_native_cap_units"]=r;
    save(out/"operators_manifest.json",result);Json summary=Json::object();summary["global_fields"]=I(fields.size());summary["global_ledger_rows"]=global_rows;summary["field_seconds"]=field_seconds;summary["ledger_read_seconds"]=ledger_read_seconds;summary["input_seconds"]=input_seconds;summary["sort_seconds"]=sort_seconds;summary["output_seconds"]=uptime()-phase_start;summary["sort_threads"]=threads;summary["ledger_backend"]="parallel_read_sequence_ordered_flat_sort";summary["consumed_local_ledger_rows"]=ledger_rows;summary["runtime_model_eligible"]=false;summary["release_qualified"]=false;save(out/"merge_summary.json",summary);check();return 0;
}catch(const std::exception& e){std::cerr<<"charge_merge: "<<e.what()<<'\n';return 1;}}
