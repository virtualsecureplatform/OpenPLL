// Bind every snapshot's native wire creation geometry to resolved private nodes.
// This is a topology/geometry audit, not an RC model or snapshot selection.
#include "../charge_compiler/json.hpp"
#include <array>
#include <filesystem>
#include <iomanip>
#include <iostream>
#include <set>
#include <sstream>
#include <tuple>
#include <time.h>
using I=long long;
using Point=std::array<I,2>;
using Box=std::array<I,4>;
static double uptime(){timespec t{};require(clock_gettime(CLOCK_BOOTTIME,&t)==0,"clock");return t.tv_sec+t.tv_nsec*1e-9;}
static I integer(const std::string& s){size_t n;I v=std::stoll(s,&n);require(n==s.size(),"integer");return v;}
static double number(const std::string& s){size_t n;double v=std::stod(s,&n);require(n==s.size()&&std::isfinite(v),"finite number");return v;}
static std::vector<std::string> words(const std::string& line){
    std::istringstream in(line);std::vector<std::string> r;std::string s;
    for(;;){in>>std::ws;if(in.eof())break;require(bool(in>>std::quoted(s)),"quoted record");r.push_back(s);}return r;
}
static void save(const std::filesystem::path& p,const Json& value){auto tmp=p;tmp+=".tmp";std::ofstream f(tmp);f<<value.dump()<<'\n';f.close();require(bool(f),"write");std::filesystem::rename(tmp,p);}
struct JsonRows {
    std::ifstream in;Json row;bool have=false,done=false;bool array;bool started=false;
    JsonRows(const std::string& path,bool a):in(path),array(a){require(bool(in),"open JSON rows");if(array){in>>std::ws;require(in.get()=='[',"array start");}next();}
    void next(){
        if(done){have=false;return;}
        if(!array){std::string line;if(!std::getline(in,line)){require(in.eof(),"JSONL read");done=true;have=false;return;}row=Json::parse(line);have=true;return;}
        in>>std::ws;if(started&&in.peek()==','){in.get();in>>std::ws;require(in.peek()=='{',"array object after separator");}else require(in.peek()==']'||(!started&&in.peek()=='{'),"array separator");
        if(in.peek()==']'){in.get();in>>std::ws;require(in.peek()==EOF,"array trailing data");done=true;have=false;return;}
        require(in.peek()=='{',"array object expected");std::string text;int depth=0;bool quoted=false,escaped=false;char c;
        do{require(bool(in.get(c)),"truncated array object");text+=c;
            if(quoted){if(escaped)escaped=false;else if(c=='\\')escaped=true;else if(c=='"')quoted=false;}
            else if(c=='"')quoted=true;else if(c=='{'||c=='[')++depth;else if(c=='}'||c==']')--depth;
        }while(depth>0||quoted);
        row=Json::parse(text);have=true;started=true;
        in>>std::ws;require(in.peek()==','||in.peek()==']',"array separator");
    }
};
struct Node {std::string name;Point point;};
struct Branch {std::array<std::string,5> raw;I incidents=0;std::set<std::string> owners;};
struct Segment {Point a,b;Box box;double value;std::string type;I status,center,width;};
struct Tile {std::map<Point,std::set<std::string>> points;std::set<std::string> nodes;};
using TileKey=std::pair<std::string,Box>;
int main(int argc,char** argv){try{
    require(argc==2,"usage: native_r_geometry_audit CONFIG");auto cfg=Json::read(argv[1]);
    double deadline=cfg.at("deadline_uptime").num();auto check=[&](){require(uptime()<deadline,"whole-check deadline exhausted");};check();
    std::filesystem::path out=cfg.at("output").str();require(std::filesystem::create_directory(out),"fresh native output");
    std::ifstream native(cfg.at("native").str()),segments(cfg.at("segments").str());require(bool(native)&&bool(segments),"open native streams");
    JsonRows node_rows(cfg.at("nodes").str(),true),tile_rows(cfg.at("tiles").str(),false);
    std::ofstream groups(out/"groups.jsonl"),failures(out/"failures.jsonl");require(bool(groups)&&bool(failures),"open output");
    std::map<std::string,Segment> latest;
    std::map<std::string,Node> nodes;std::map<std::string,Branch> branches;
    std::string id,label,owner,branch;bool active=false;I count=0,rows=0,total_nodes=0,total_tiles=0,total_branches=0,wires=0,contacts=0,splits=0,failed=0,recorded=0;
    std::map<std::string,I> reasons;
    auto fail=[&](const std::string& why,const std::string& pointer){++failed;++reasons[why];if(recorded++<100){Json r=Json::object();r["group"]=id;r["conductor"]=label;r["branch"]=pointer;r["reason"]=why;failures<<r.dump()<<'\n';}};
    auto finish=[&](){
        require(branch.empty(),"unpaired branch");I start_failed=failed;
        std::map<std::string,std::string> private_ids;std::set<std::string> unique;
        while(node_rows.have&&node_rows.row.at("native_group_id").str()==id){
            auto& r=node_rows.row;std::string ptr=r.at("native_pointer").str(),pid=r.at("private_id").str();
            require(r.at("original_conductor").str()==label&&nodes.count(ptr)&&!private_ids.count(ptr)&&unique.insert(pid).second,"indexed node identity");
            auto& n=nodes.at(ptr);auto& p=r.at("point_internal");
            require(n.name==r.at("printed_name").str()&&p.arr().size()==2&&n.point==Point{p.at(0).integer(),p.at(1).integer()},"indexed native node changed");
            require(pid.rfind("_rmesh_"+id+"_",0)==0,"private node group namespace");private_ids[ptr]=pid;node_rows.next();check();
        }
        require(private_ids.size()==nodes.size(),"indexed native node count");
        std::map<TileKey,std::vector<Tile>> tiles;I tile_count=0;
        while(tile_rows.have&&tile_rows.row.at("native_group_id").str()==id){
            auto& r=tile_rows.row;require(r.at("original_conductor").str()==label,"tile conductor");
            Box box;for(int j=0;j<4;++j)box[j]=r.at("box_internal").at(j).integer();
            Tile tile;for(auto& bp:r.at("breakpoints").arr()){
                auto pid=bp.at("private_id").str();require(unique.count(pid),"unbound tile breakpoint");
                Point point{bp.at("point_internal").at(0).integer(),bp.at("point_internal").at(1).integer()};
                tile.points[point].insert(pid);tile.nodes.insert(pid);
            }
            require(I(r.at("breakpoints").arr().size())==r.at("initial_breakpoint_count").integer(),"tile breakpoint count");
            tiles[{r.at("raw_type_id").str(),box}].push_back(std::move(tile));++tile_count;tile_rows.next();check();
        }
        bool marker=false;std::string line;
        while(std::getline(segments,line)){
            auto f=words(line);require(!f.empty(),"empty segment record");if(++rows%10000==0)check();
            if(f[0]=="GROUP"){require(f.size()==3&&f[1]==id&&f[2]==label,"segment group alignment");marker=true;break;}
            require(f[0]=="SEG"&&f.size()==17,"segment record");
            Segment s;for(int j=0;j<2;++j){s.a[j]=integer(f[4+j]);s.b[j]=integer(f[6+j]);}for(int j=0;j<4;++j)s.box[j]=integer(f[8+j]);
            s.value=number(f[12]);s.type=f[13];s.status=integer(f[14]);s.center=integer(f[15]);s.width=integer(f[16]);latest[f[1]]=s;
        }
        require(marker,"missing segment group");
        I group_wires=0;
        for(auto& [ptr,b]:branches){
            check();require(b.incidents==2,"branch requires two incidences");auto& r=b.raw;
            require(nodes.count(r[0])&&nodes.count(r[1]),"branch endpoint missing");require(number(r[2])>0,"nonpositive native branch");
            I status=integer(r[4]);if(!(status&0x600)){++contacts;continue;}++wires;++group_wires;
            if(status&0x800)++splits;
            auto found=latest.find(ptr);if(found==latest.end()){fail("missing_creation_segment",ptr);continue;}auto& s=found->second;
            if(s.value!=number(r[2])||s.type!=r[3]||(s.status&0xe00)!=(status&0xe00)){fail("creation_branch_value_type_or_status_mismatch",ptr);continue;}
            auto it=tiles.find({s.type,s.box});if(it==tiles.end()||it->second.size()!=1){fail("creation_tile_not_unique",ptr);continue;}auto& t=it->second[0];
            auto a=t.points.find(s.a),bpoint=t.points.find(s.b);
            if(a==t.points.end()||bpoint==t.points.end()||a->second.size()!=1||bpoint->second.size()!=1){fail("creation_breakpoints_not_unique",ptr);continue;}
            std::set<std::string> endpoints{private_ids.at(r[0]),private_ids.at(r[1])};
            if(endpoints.size()!=2||endpoints!=std::set<std::string>{*a->second.begin(),*bpoint->second.begin()}){fail("resolved_branch_endpoints_changed",ptr);continue;}
            if((status&0x600)==0x600){fail("two_wire_flow_axes",ptr);continue;}
            int axis=(status&0x200)?0:1;
            if(s.a[axis]>=s.b[axis]||s.a[axis]<s.box[axis]||s.b[axis]>s.box[axis+2]||s.width<=0){fail("invalid_creation_axis_extent",ptr);continue;}
            // Split tiles need their own polygon interpolation; count separately.
            if(!(status&0x800)&&(s.box[3-axis]-s.box[1-axis]!=s.width||s.center<s.box[1-axis]||s.center>s.box[3-axis]))fail("wire_width_or_centerline_mismatch",ptr);
        }
        Json row=Json::object();row["native_group_id"]=id;row["original_conductor"]=label;row["native_nodes"]=I(nodes.size());row["native_tiles"]=tile_count;row["native_branches"]=I(branches.size());row["wire_branches"]=group_wires;row["failures"]=failed-start_failed;groups<<row.dump()<<'\n';
        total_nodes+=I(nodes.size());total_tiles+=tile_count;total_branches+=I(branches.size());nodes.clear();branches.clear();active=false;
    };
    std::string line;
    while(std::getline(native,line)){
        if(++rows%10000==0)check();auto f=words(line);require(!f.empty(),"empty native record");
        if(f[0]=="TYPE"){require(!active&&f.size()==3,"type record");continue;}
        if(f[0]=="BEGIN"){require(!active&&f.size()==3&&integer(f[1])==count+1,"group sequence");id=f[1];label=f[2];++count;active=true;continue;}
        require(active&&f.size()>1&&f[1]==id,"native group alignment");
        if(f[0]=="NODE"){require(branch.empty()&&f.size()==8&&!nodes.count(f[2]),"node record");nodes[f[2]]={f[3],{integer(f[4]),integer(f[5])}};}
        else if(f[0]=="BRANCH"){require(branch.empty()&&f.size()==4&&nodes.count(f[2]),"branch record");owner=f[2];branch=f[3];}
        else if(f[0]=="EDGE"){
            require(f.size()==8&&!branch.empty()&&owner==f[2]&&(owner==f[3]||owner==f[4]),"incident pairing");
            std::array<std::string,5> r{f[3],f[4],f[5],f[6],f[7]};auto [it,added]=branches.emplace(branch,Branch{r,0,{}});require(added||it->second.raw==r,"branch incidence disagreement");require(it->second.owners.insert(owner).second,"duplicate branch owner incidence");++it->second.incidents;branch.clear();owner.clear();
        }else if(f[0]=="END"){require(f.size()==2,"end record");finish();}else throw std::runtime_error("unknown native record");
    }
    require(native.eof()&&!active&&count>0&&!node_rows.have&&!tile_rows.have,"unconsumed native/index rows");
    segments>>std::ws;require(segments.peek()==EOF,"unconsumed segment records");groups.close();failures.close();require(bool(groups)&&bool(failures),"output close");check();
    Json result=Json::object(),why=Json::object();for(auto& [key,n]:reasons)why[key]=n;
    result["native_groups"]=count;result["native_nodes"]=total_nodes;result["native_tiles"]=total_tiles;result["native_branches"]=total_branches;
    result["wire_branches"]=wires;result["contact_branches"]=contacts;result["split_wire_branches"]=splits;result["wire_geometry_failures"]=failed;result["failure_counts"]=why;
    result["all_snapshot_nodes_and_tiles_accounted"]=true;result["all_wire_creation_geometry_matched"]=failed==0;result["snapshot_selection_qualified"]=false;
    result["contact_impedance_qualified"]=false;result["split_interpolation_qualified"]=false;result["physical_domain_complete"]=false;result["runtime_model_eligible"]=false;result["release_qualified"]=false;
    save(out/"summary.json",result);return 0;
}catch(const std::exception& e){std::cerr<<"native_r_geometry_audit: "<<e.what()<<'\n';return 1;}}
