// Streaming native charge compiler. Physical units and signed terms are unchanged.
#include "json.hpp"
#include <algorithm>
#include <atomic>
#include <array>
#include <csignal>
#include <ctime>
#include <filesystem>
#include <iomanip>
#include <future>
#include <iostream>
#include <sstream>
#include <unordered_map>

namespace fs=std::filesystem;
using I=long long;
using Box=std::array<I,4>;
using Tokens=std::vector<std::string_view>;
static std::atomic<bool> stopped{false};
static_assert(decltype(stopped)::is_always_lock_free);
static void interrupt(int) { stopped.store(true,std::memory_order_relaxed); }
static double uptime() { timespec t{}; require(clock_gettime(CLOCK_BOOTTIME,&t)==0,"clock failure");return t.tv_sec+t.tv_nsec*1e-9; }
static void check_deadline(double deadline) {require(!stopped.load(std::memory_order_relaxed),"interrupted");require(uptime()<deadline,"whole-check deadline exhausted");}
static Tokens split(const std::string& s) {
    Tokens out; size_t p=0;
    while(p<s.size()) {while(p<s.size()&&std::isspace((unsigned char)s[p]))++p;size_t b=p;while(p<s.size()&&!std::isspace((unsigned char)s[p]))++p;if(p>b)out.emplace_back(s.data()+b,p-b);} return out;
}
static I integer(std::string_view s) { I n=0;auto r=std::from_chars(s.data(),s.data()+s.size(),n);require(r.ec==std::errc{}&&r.ptr==s.data()+s.size(),"invalid trace integer");require(n>=-9007199254740991LL&&n<=9007199254740991LL,"trace integer precision");return n; }
static double number(std::string_view s) {double n;auto r=std::from_chars(s.data(),s.data()+s.size(),n);require(r.ec==std::errc{}&&r.ptr==s.data()+s.size()&&std::isfinite(n),"invalid trace number");return n;}
static void save(const fs::path& p,const Json& j) {
    fs::path tmp=p;tmp+=".tmp";std::ofstream out(tmp);out<<j.dump()<<'\n';out.close();require(bool(out),"write failed: "+p.string());fs::rename(tmp,p);
}
// Stream the ledger without constructing a second complete JSON tree/string.
// Field order, scalar formatting and array bytes match the original writer.
static void save_ledger(const fs::path& path,
        const std::map<std::pair<I,I>,std::array<double,3>>& ledger,double deadline) {
    fs::path tmp=path;tmp+=".tmp";
    std::array<char,1024*1024> buffer{};std::ofstream out;
    out.rdbuf()->pubsetbuf(buffer.data(),buffer.size());out.open(tmp);
    require(bool(out),"ledger output open");out<<'[';bool first=true;I rows=0;
    for(const auto& [key,v]:ledger){
        if(++rows%10000==0)check_deadline(deadline);
        if(!first)out<<',';
        first=false;
        out<<Json(Json::Array{key.first,key.second,v[0],v[1],v[2]}).dump();
        require(bool(out),"ledger row write");
    }
    out<<"]\n";out.close();require(bool(out),"ledger close");
    check_deadline(deadline);fs::rename(tmp,path);
}
struct Range {
    std::array<char,1024*1024> buffer{}; std::ifstream in; I end=0,pos=0; std::string line;
    Range(const fs::path& path,const Json& span) {
        in.rdbuf()->pubsetbuf(buffer.data(),buffer.size());in.open(path,std::ios::binary);require(bool(in),"open failed: "+path.string());
        pos=span.at(0).integer();end=span.at(1).integer();require(0<=pos&&pos<=end&&end<=(I)fs::file_size(path),"invalid range");
        if(pos) {in.seekg(pos-1);char c;in.get(c);require(c=='\n',"split range start");} else in.seekg(pos);
    }
    bool next() {
        if(pos==end) return false;
        require(bool(std::getline(in,line)),"truncated trace range");pos+=I(line.size())+1;require(pos<=end,"split record or missing newline");return true;
    }
    bool record(std::string_view a,std::string_view b={}) {
        while(next()) {auto f=split(line);if(!f.empty()&&(f[0]==a||(!b.empty()&&f[0]==b)))return true;}return false;
    }
};
struct Rect { I rule; bool split;Box box; };
struct Value {I rule;std::array<double,8> v;};
struct Event {I id;std::string kind,component;};
struct Block {
    I id=0;std::string kind;int direction=0;
    std::map<std::string,std::vector<Rect>> rects;
    std::map<std::string,std::vector<Value>> values;
    std::vector<Event> events;
    // Rule collections may legitimately be empty in the native trace.
    // Required scalar/geometry records still use checked lookups below.
    const std::vector<Value>& rules(const std::string& tag) const {
        static const std::vector<Value> empty;
        auto it=values.find(tag);return it==values.end()?empty:it->second;
    }
    const std::array<double,8>& v(const std::string& tag,I rule=0) const {
        const auto& rows=values.at(tag);const Value* found=nullptr;
        for(const auto& r:rows)if(r.rule==rule){require(!found,"duplicate value rule: "+tag);found=&r;}
        require(found,"missing value rule: "+tag);return found->v;
    }
    Box r(const std::string& tag) const {const auto& rows=rects.at(tag);require(rows.size()==1&&!rows[0].split,"unsupported rectangle: "+tag);return rows[0].box;}
};
static double length(Box a) {require(a[0]==a[2]||a[1]==a[3],"non-axis edge");return double(a[2]-a[0])+double(a[3]-a[1]);}
static Box project(Box edge,Box patch) {if(edge[0]==edge[2])return {edge[0],patch[1],edge[2],patch[3]};require(edge[1]==edge[3],"non-axis project");return {patch[0],edge[1],patch[2],edge[1]};}
static Box clip(Box a,Box b,int d) {
    switch(d) {case 1:b[2]=std::min(b[2],a[0]);break;case 2:b[1]=std::max(b[1],a[1]);break;case 4:b[0]=std::max(b[0],a[0]);break;case 8:b[3]=std::min(b[3],a[1]);break;default:throw std::runtime_error("invalid boundary direction");}
    require(b[0]<=b[2]&&b[1]<=b[3],"invalid clipped box");return b;
}
struct Op {
    char kind; Box a,b{}; double density=0,mult=0; int direction=0,other=0;
    double integral() const {
        if(kind=='A')return double(a[2]-a[0])*double(a[3]-a[1])*density;
        if(kind=='L'){require(length(a)==length(b),"unequal edge lengths");return length(a)*density;}
        Box p=clip(a,b,direction);I near=0,far=0;
        switch(direction){case 1:near=a[0]-p[2];far=a[0]-p[0];break;case 2:near=p[1]-a[1];far=p[3]-a[1];break;case 4:near=p[0]-a[0];far=p[2]-a[0];break;case 8:near=a[1]-p[3];far=a[1]-p[1];break;}
        require(0<=near&&near<=far&&mult>=0,"invalid fringe geometry");return density*length(project(a,p))*.6366*(std::atan(mult*far)-std::atan(mult*near));
    }
    static Json box(Box b){Json a=Json::array();for(auto x:b)a.push(x);return a;}
    Json json(I fa,I fb,I event) const {
        Json out=Json::Array{std::string(1,kind),fa,fb,event,box(a)};
        if(kind=='A')out.push(density);
        else if(kind=='L'){out.push(box(b));out.push(density);out.push(direction);out.push(other);}
        else {out.push(box(b));out.push(direction);out.push(density);out.push(mult);}return out;
    }
};
static double sum(const std::vector<double>& values) {
    // Nonoverlapping partial sums, matching the reference's compensated fsum.
    std::vector<double> partials;
    for(double x:values) {size_t i=0;for(double y:partials){if(std::abs(x)<std::abs(y))std::swap(x,y);double hi=x+y,lo=y-(hi-x);if(lo)partials[i++]=lo;x=hi;}partials.resize(i);partials.push_back(x);}
    double hi=0,lo=0;size_t n=partials.size();
    if(n){hi=partials[--n];while(n){double x=hi,y=partials[--n];hi=x+y;lo=y-(hi-x);if(lo)break;}if(n&&((lo<0&&partials[n-1]<0)||(lo>0&&partials[n-1]>0))){double y=lo*2,x=hi+y;if(y==x-hi)hi=x;}}
    require(std::isfinite(hi),"sum overflow");return hi;
}
static void close(double a,double b) {require(std::isfinite(a)&&std::isfinite(b)&&std::abs(a-b)<=1e-8+2e-12*std::max(std::abs(a),std::abs(b)),"native physical integral mismatch");}
static std::vector<Op> ops(const Block& x,bool pair,bool restore=false) {
    std::vector<Op> out;
    if(x.kind=="ROUNDING"){require(!pair,"pair rounding");return out;}
    auto a=x.r("BASE_A");auto line=[&](Box a,Box b,double den,int d,int other=0){out.push_back({'L',a,b,den,0,d,other});};
    if(x.kind=="AREA"){require(!pair,"pair area");out.push_back({'A',a,{},x.v("AREA_DENSITY")[1]});}
    else if(x.kind=="EDGE"){require(!pair,"pair edge");require(x.direction>=0&&x.direction<4,"edge direction");line(a,a,x.v("EDGE_DENSITY")[1],std::array<int,4>{2,1,8,4}[x.direction]);}
    else if(x.kind=="OVERLAP") {
        double d=x.v("OVERLAP_BASE")[pair?2:1]*(pair?1:-1);out.push_back({'A',a,{},d});
        if(auto i=x.rects.find("AREA_SHIELD");i!=x.rects.end())for(const auto& r:i->second){require(r.rule==0&&!r.split,"split shield");out.push_back({'A',r.box,{},-d});}
    } else if(x.kind=="FRINGE_HALO") {
        auto b=x.r("BASE_B");auto base=x.v("FRINGE_BASE");
        if(!pair)line(project(a,b),project(a,b),-x.v("GROUND_PHYSICAL")[4]*base[6],x.direction);
        for(const auto& rv:x.rules("HALO_RULE")) {
            auto remaining=x.v("HALO_RULE_REMAINING",rv.rule);
            if(restore)require(remaining[2]==0,"self fringe omission mismatch");
            if(!restore&&!remaining[2])continue;
            if(pair)out.push_back({'F',a,clip(a,b,x.direction),rv.v[0],base[3],x.direction});
            std::vector<Rect> rr;std::vector<Value> vv;
            if(auto i=x.rects.find("FRINGE_SHIELD");i!=x.rects.end())for(auto r:i->second)if(r.rule==rv.rule)rr.push_back(r);
            if(auto i=x.values.find("FRINGE_SHIELD_GEOMETRY");i!=x.values.end())for(auto v:i->second)if(v.rule==rv.rule)vv.push_back(v);
            require(rr.size()==vv.size(),"fringe shield alignment");
            for(size_t i=0;i<rr.size();++i){require(!rr[i].split,"split fringe shield");auto v=vv[i].v;
                if(pair)out.push_back({'F',a,clip(a,rr[i].box,x.direction),-rv.v[0],v[4],x.direction});
                else {double d=x.v("GROUND_PHYSICAL")[4]*.6366*(std::atan(v[5]*v[3])-std::atan(v[5]*v[2]));line(project(a,rr[i].box),project(a,rr[i].box),d,x.direction);}
            }
        }
    } else if(x.kind=="BLOCKED_FRINGE"){require(!pair,"pair blocked fringe");auto v=x.v("BLOCKED_BASE");line(a,a,-v[4]*(1-v[3]),x.direction);}
    else if(x.kind=="SIDEWALL") {
        require(pair,"ground sidewall");std::vector<double> terms;for(auto r:x.rules("SIDEWALL_RULE"))terms.push_back(r.v[0]/(x.v("SIDEWALL_BASE")[1]+r.v[1]));
        int d=x.direction,opposite=d==1?4:d==2?8:d==4?1:d==8?2:0;require(opposite,"sidewall direction");line(a,x.r("BASE_B"),sum(terms),d,opposite);
    } else throw std::runtime_error("unsupported native kernel: "+x.kind);
    return out;
}
static double total(const std::vector<Op>& pieces){std::vector<double> v;for(auto& p:pieces)v.push_back(p.integral());return sum(v);}
struct Owner {I id=0;std::string a,b;std::array<int,3> source{},target{};bool same=false;};
static Owner owner(const Tokens& f) {
    require(f.size()==11&&f[0]=="OWNER","invalid owner row");Owner o;o.id=integer(f[1]);o.a=f[2];o.b=f[3];
    for(int i=0;i<3;++i){I a=integer(f[4+i]),b=integer(f[7+i]);require(a>=0&&b>=0&&a<=INT32_MAX&&b<=INT32_MAX,"owner plane/type");o.source[i]=int(a);o.target[i]=int(b);}
    I same=integer(f[10]);require(same==0||same==1,"invalid same-conductor flag");o.same=same;require(o.same==(o.a==o.b),"owner conductor mismatch");return o;
}
static void compile(const Json& cfg) {
    fs::path trace=cfg.at("trace").str(),out=cfg.at("output").str();double deadline=cfg.at("deadline_uptime").num();check_deadline(deadline);
    require(fs::create_directory(out),"fresh shard output required");
    Json ids=Json::read((trace/"node_ids.json").string()),meta=Json::read(cfg.at("metadata").str()),spec=cfg.at("range_spec");
    std::map<std::pair<int,int>,int> residues;for(auto& r:meta.at("residues").arr())residues[{int(r.at(0).integer()),int(r.at(1).integer())}]=int(r.at(2).integer());
    Range kernels(trace/"kernels.log",spec.at("kernels")),owners(trace/"owners.log",spec.at("owners")),surfaces(trace/"surfaces.log",spec.at("surfaces")),natives(trace/"contributions.log",spec.at("contributions"));
    std::map<std::array<std::string,3>,I> fields;Json field_rows=Json::array();
    auto intern=[&](std::array<std::string,3> key){auto [it,added]=fields.emplace(key,I(fields.size()));if(added)field_rows.push(Json::Array{key[0],key[1],key[2]});return it->second;};
    intern({"@SUBSTRATE_REFERENCE","reference","reference"});
    auto field=[&](const std::string& ptr,I p,I t){std::string name=ids.at(ptr).str();if(name=="@SUBSTRATE")name="VGND";require(p>=0||t==-1,"unlocated field type");return intern(p>=0?std::array<std::string,3>{name,meta.at("planes").at(std::to_string(p)).str(),meta.at("types").at(std::to_string(t)).str()}:std::array<std::string,3>{name,"arithmetic","unlocated"});};
    std::map<std::string,I> count,reason;std::map<std::string,double> residual;
    std::map<std::pair<I,I>,std::array<double,3>> ledger;
    I event_id=spec.at("event_start").integer(),kernel_id=spec.at("kernel_start").integer()-1;
    count["events"]=0;
    std::array<char,1024*1024> write_buffer{};std::ofstream opfile;opfile.rdbuf()->pubsetbuf(write_buffer.data(),write_buffer.size());opfile.open(out/"operators.jsonl");require(bool(opfile),"operator output open");
    Owner pending;bool have_owner=owners.next();if(have_owner){pending=owner(split(owners.line));require(pending.id>=spec.at("kernel_start").integer()&&pending.id<spec.at("kernel_end").integer(),"owner outside range");}
    auto advance_owner=[&](){I last=pending.id;have_owner=owners.next();if(have_owner){pending=owner(split(owners.line));require(pending.id>last&&pending.id<spec.at("kernel_end").integer(),"owner order");}};
    auto emit=[&](const std::vector<Op>& pieces,I a,I b,I ev,bool restored){for(auto& p:pieces){opfile<<p.json(a,b,ev).dump()<<'\n';++count["operators"];++count[std::string("operator_")+p.kind];if(restored)++count["restored_self_operators"];}require(bool(opfile),"operator write failed");};
    auto progress=[&](){Json j=Json::object(),c=Json::object();for(auto [k,v]:count)c[k]=v;j["state"]="running";j["counts"]=c;j["deadline_uptime"]=deadline;save(out/"status.json",j);};
    auto process=[&](const Block& x) {
        ++count["kernels"];if(count["kernels"]%10000==0){check_deadline(deadline);progress();}
        bool paired=x.kind=="OVERLAP"||x.kind=="FRINGE_HALO"||x.kind=="SIDEWALL";
        require(!have_owner||pending.id>=x.id,"unconsumed owner");bool owned=have_owner&&pending.id==x.id;require(paired==owned,"missing or extraneous owner");
        if(owned){(void)ids.at(pending.a);(void)ids.at(pending.b);++count["owned_pair_kernels"];}
        if(owned&&pending.same){
            auto pieces=ops(x,true,true);double physical=total(pieces);bool nonzero=false;for(auto& p:pieces)nonzero|=p.integral()!=0;
            if(nonzero){
                int pa=pending.source[0],ta=pending.source[2],pb=pending.target[0],tb=pending.target[2];
                int ea=residues.count({pa,ta})?residues.at({pa,ta}):ta,eb=residues.count({pb,tb})?residues.at({pb,tb}):tb;
                count["self_contact_field_normalizations"]+=I(ea!=ta)+I(eb!=tb);
                I a=field(pending.a,pa,ea),b=field(pending.b,pb,eb);require(ids.at(pending.a).str()==ids.at(pending.b).str(),"self field conductor mismatch");
                for(auto& e:x.events)require(e.kind!="P","native pair on omitted self conductor");
                double expected=0;
                if(x.kind=="OVERLAP")expected=x.v("OVERLAP_REMAINING")[0]*x.v("OVERLAP_BASE")[2];
                else {std::vector<double> terms;if(x.kind=="FRINGE_HALO"){auto b=x.v("FRINGE_BASE");for(auto v:x.rules("HALO_RULE"))terms.push_back(v.v[0]*(b[5]-x.v("HALO_RULE_REMAINING",v.rule)[0])*b[0]);}else {auto b=x.v("SIDEWALL_BASE");for(auto v:x.rules("SIDEWALL_RULE"))terms.push_back(v.v[0]*b[0]/(b[1]+v.v[1]));}expected=sum(terms);}
                close(physical,expected);++count["restored_self_pair_kernels"];++count["restored_self_"+x.kind];count["restored_negative_scalar_self_kernels"]+=physical<0;
                ledger[std::minmax(a,b)][1]+=physical;emit(pieces,a,b,-x.id,true);
            }
        }
        if(x.events.empty())++count["native_kernels_without_nonzero_events"];
        else {
            for(auto& [tag,rr]:x.rects)for(auto& r:rr)require(!r.split,"split event rectangle");
            for(auto& event:x.events) {
                ++count["events"];require(natives.record("OPENPLL_G","OPENPLL_P")&&surfaces.record("SURFACE"),"missing aligned event");
                auto n=split(natives.line),s=split(surfaces.line);bool pair=n[0]=="OPENPLL_P";
                // Native records can include the extractor's diagnostic geometry suffix.
                require(n.size()>=(pair?4:3)&&s.size()==9,"invalid event row");
                require(s[0]=="SURFACE"&&integer(s[1])==event.id&&s[2]==event.kind&&event.kind==(pair?"P":"G"),"event/surface alignment");
                if(pair)require(owned&&n[1]==pending.a&&n[2]==pending.b,"native pair ownership");
                I a=field(std::string(n[1]),integer(s[3]),integer(s[5])),b=pair?field(std::string(n[2]),integer(s[6]),integer(s[8])):0;
                double delta=number(n[pair?3:2]);auto pieces=ops(x,pair);double physical=total(pieces),expected=0;
                if(x.kind=="AREA"||x.kind=="EDGE"){auto v=x.v(x.kind=="AREA"?"AREA_DENSITY":"EDGE_DENSITY");expected=v[0]*v[1];}
                else if(x.kind=="OVERLAP")expected=x.v("OVERLAP_REMAINING")[0]*x.v("OVERLAP_BASE")[pair?2:1]*(pair?1:-1);
                else if(x.kind=="FRINGE_HALO")expected=x.v(pair?"PAIR_PHYSICAL":"GROUND_PHYSICAL")[0]*(pair?1:-1);
                else if(x.kind=="BLOCKED_FRINGE")expected=-x.v("BLOCKED_BASE")[5];
                else if(x.kind=="SIDEWALL"){auto b=x.v("SIDEWALL_BASE");std::vector<double> terms;for(auto v:x.rules("SIDEWALL_RULE"))terms.push_back(v.v[0]*b[0]/(b[1]+v.v[1]));expected=sum(terms);}
                close(physical,expected);double error=std::abs(delta-physical);residual[event.component]+=error;++reason[event.component];
                auto& l=ledger[std::minmax(a,b)];l[0]+=delta;l[1]+=physical;l[2]+=error;emit(pieces,a,b,event.id,false);
            }
        }
        if(owned)advance_owner();
    };
    auto checked_process=[&](const Block& x){
        try {process(x);} catch(const std::exception& e) {
            throw std::runtime_error("kernel "+std::to_string(x.id)+" "+x.kind+": "+e.what());
        }
    };
    Block current;
    while(kernels.next()) {
        auto f=split(kernels.line);require(!f.empty(),"empty kernel record");
        if(f[0]=="KERNEL") {
            require(f.size()==4&&integer(f[1])==kernel_id+1,"kernel sequence");if(current.id)checked_process(current);
            current=Block{};current.id=++kernel_id;current.kind=f[2];current.direction=int(integer(f[3]));
        } else if(f[0]=="RECT") {
            require(current.id&&f.size()==10&&integer(f[1])==current.id,"invalid RECT");Box b;for(int i=0;i<4;++i)b[i]=integer(f[6+i]);require(b[0]<=b[2]&&b[1]<=b[3],"invalid rectangle");
            current.rects[std::string(f[2])].push_back({integer(f[3]),integer(f[4])!=0,b});
        } else if(f[0]=="VALUE") {
            require(current.id&&f.size()==12&&integer(f[1])==current.id,"invalid VALUE");Value v;v.rule=integer(f[3]);for(int i=0;i<8;++i)v.v[i]=number(f[4+i]);current.values[std::string(f[2])].push_back(v);
        } else if(f[0]=="EVENT") {
            require(current.id&&f.size()==5&&integer(f[1])==event_id+1&&integer(f[3])==current.id&&f[4]!="MISSING"&&(f[2]=="G"||f[2]=="P"),"invalid EVENT");current.events.push_back({++event_id,std::string(f[2]),std::string(f[4])});
        } else throw std::runtime_error("unexpected range record");
    }
    if(current.id)checked_process(current);
    require(kernel_id==spec.at("kernel_end").integer()-1&&event_id==spec.at("event_end").integer(),"range counts mismatch");
    require(!have_owner&&!natives.record("OPENPLL_G","OPENPLL_P")&&!surfaces.record("SURFACE"),"unconsumed aligned records");
    opfile.close();require(bool(opfile),"operator close failure");check_deadline(deadline);
    save(out/"fields.json",field_rows);
    save_ledger(out/"collapsed_matrix_ledger.json",ledger,deadline);
    Json residue_rows=Json::array();for(auto [key,v]:residues){Json r=Json::object();r["plane"]=key.first;r["raw_type"]=key.second;r["effective_type"]=v;residue_rows.push(r);}save(out/"observed_plane_residues.json",residue_rows);
    Json report=Json::object(),counts=Json::object(),components=Json::object(),res=Json::object();for(auto [k,v]:count)counts[k]=v;for(auto [k,v]:reason)components[k]=v;for(auto [k,v]:residual)res[k]=v;
    report["counts"]=counts;report["components"]=components;report["arithmetic_residual_absolute_native_cap_units"]=res;report["range_spec"]=spec;report["voltage_fields"]=I(fields.size());
    report["local_operator_integrals_match_native_physical_totals"]=true;report["aligned_events_have_owned_voltage_fields"]=true;report["finite_R_same_conductor_pair_energy_restored"]=true;
    report["native_self_conductor_pair_omission_convention_preserved"]=false;report["all_restored_pairs_have_zero_energy_under_ideal_conductor_collapse"]=true;report["native_nonzero_G_P_events_and_ground_convention_preserved"]=true;
    report["owner_contact_fields_normalized_using_exact_observed_native_plane_residues"]=true;report["implicit_ground_return"]="explicit substrate reference, original conductor VGND at zero wire R";
    report["units"]=Json::Object{{"length_m",5e-9},{"capacitance_F",1e-18}};
    report["deadline_uptime"]=deadline;report["field_numbering"]="shard_local_requires_manifest_map";
    for(auto flag:{"full_C_energy_matrix_assembled","global_passivity_qualified","runtime_model_eligible","release_qualified","adopted"})report[flag]=false;
    save(out/"native_summary.json",report);progress();
}
static void metadata(const fs::path& trace,const fs::path& output,double deadline) {
    std::ifstream in(trace/"surfaces.log");require(bool(in),"surface metadata open");std::string line;Json types=Json::object(),planes=Json::object();std::map<std::pair<I,I>,I> residues;I rows=0;bool began=false,ended=false;
    while(std::getline(in,line)) {
        if(++rows%100000==0)check_deadline(deadline);
        auto f=split(line);require(!f.empty()&&!ended,"bad surface stream");
        if(f[0]=="BEGIN"){require(!began,"duplicate surface begin");began=true;}
        else if(f[0]=="TYPE"||f[0]=="PLANE") {require(began&&f.size()>=3,"invalid type/plane metadata");size_t offset=size_t(f[2].data()-line.data());auto text=Json::parse(std::string_view(line).substr(offset));require(std::holds_alternative<std::string>(text.value),"type/plane name");auto& table=f[0]=="TYPE"?types:planes;std::string key(f[1]);require(!table.obj().count(key),"duplicate type/plane");table[key]=text;}
        else if(f[0]=="SURFACE") {require(began&&f.size()==9,"invalid surface metadata row");for(int i:{3,6})if(f[i]!="-1"){auto key=std::pair{integer(f[i]),integer(f[i+1])};I value=integer(f[i+2]);auto [it,added]=residues.emplace(key,value);require(added||it->second==value,"inconsistent native residue");}}
        else {require(f[0]=="END"&&f.size()==2,"unknown surface record");ended=true;}
    }
    require(began&&ended,"incomplete surface metadata");check_deadline(deadline);Json j=Json::object(),r=Json::array();for(auto [key,v]:residues)r.push(Json::Array{key.first,key.second,v});j["types"]=types;j["planes"]=planes;j["residues"]=r;save(output,j);
}
static I align_line(const fs::path& path,I offset) {
    if(!offset)return 0;
    std::ifstream in(path,std::ios::binary);require(bool(in),"index input open");in.seekg(offset-1);char c=0;in.get(c);
    if(c=='\n')return offset;
    std::string line;std::getline(in,line);auto pos=in.tellg();return pos<0?I(fs::file_size(path)):I(pos);
}
struct NativeIndex {I count=0;std::vector<std::pair<I,I>> anchors;};
static NativeIndex index_chunk(const fs::path& path,I start,I end,double deadline) {
    Range range(path,Json::Array{start,end});NativeIndex result;I rows=0;
    while(true) {
        I offset=range.pos;if(!range.next())break;
        if(++rows%100000==0)check_deadline(deadline);
        if(range.line.starts_with("OPENPLL_G ")||range.line.starts_with("OPENPLL_P ")) {
            if(result.count%65536==0)result.anchors.emplace_back(result.count,offset);
            ++result.count;
        }
    }
    check_deadline(deadline);return result;
}
static void native_index(const Json& cfg) {
    fs::path path=cfg.at("path").str();I size=I(fs::file_size(path));double deadline=cfg.at("deadline_uptime").num();
    I workers=cfg.at("workers").integer();require(workers>=1&&workers<=64,"index worker count");check_deadline(deadline);
    {std::ifstream in(path,std::ios::binary);std::string first;std::getline(in,first);require(first.starts_with("OPENPLL_BEGIN"),"missing native begin");
     in.seekg(std::max(I(0),size-64));std::string tail((std::istreambuf_iterator<char>(in)),{});require(tail.ends_with("OPENPLL_END\n"),"missing native end");}
    std::vector<I> boundaries{0};for(I i=1;i<workers;++i)boundaries.push_back(align_line(path,size*i/workers));boundaries.push_back(size);
    std::vector<std::future<NativeIndex>> futures;
    for(I i=0;i<workers;++i)futures.push_back(std::async(std::launch::async,index_chunk,path,boundaries[i],boundaries[i+1],deadline));
    std::vector<NativeIndex> chunks;std::vector<I> bases;I total=0;
    for(auto& f:futures){auto c=f.get();bases.push_back(total);total+=c.count;chunks.push_back(std::move(c));}
    Json offsets=Json::object();
    for(const auto& rank:cfg.at("ranks").arr()) {
        check_deadline(deadline);I target=rank.integer();require(target>=0&&target<=total,"native event rank outside trace");
        if(target==total){offsets[std::to_string(target)]=size;continue;}
        size_t chunk=0;while(chunk<chunks.size()&&!(bases[chunk]<=target&&target<bases[chunk]+chunks[chunk].count))++chunk;
        require(chunk<chunks.size(),"missing index chunk");I local=target-bases[chunk];const auto& anchors=chunks[chunk].anchors;
        auto it=std::upper_bound(anchors.begin(),anchors.end(),std::pair{local,I(INT64_MAX)});require(it!=anchors.begin(),"missing native anchor");--it;
        Range range(path,Json::Array{it->second,boundaries[chunk+1]});I counted=it->first;bool found=false;
        while(true){I offset=range.pos;if(!range.record("OPENPLL_G","OPENPLL_P"))break;
            // record() may skip headers; take the actual current line's start.
            offset=range.pos-I(range.line.size())-1;
            if(counted++==local){offsets[std::to_string(target)]=offset;found=true;break;}}
        require(found,"native rank lookup failed");
    }
    Json report=Json::object();report["offsets"]=offsets;report["events"]=total;report["workers"]=workers;
    report["release_qualified"]=false;check_deadline(deadline);save(cfg.at("output").str(),report);
}
int main(int argc,char** argv) {
    std::signal(SIGTERM,interrupt);std::signal(SIGINT,interrupt);
    try {
        if(argc==3&&std::string(argv[1])=="compile")compile(Json::read(argv[2]));
        else if(argc==3&&std::string(argv[1])=="index")native_index(Json::read(argv[2]));
        else if(argc==5&&std::string(argv[1])=="metadata")metadata(argv[2],argv[3],number(argv[4]));
        else throw std::runtime_error("usage: charge_compiler {compile|index} CONFIG | metadata TRACE OUTPUT DEADLINE_UPTIME");
        return 0;
    } catch(const std::exception& e){std::cerr<<"charge_compiler: "<<e.what()<<'\n';return 1;}
}
