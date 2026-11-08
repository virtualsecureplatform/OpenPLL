// Diagnostic only: preserve the first complete group with unequal kernel fields.
// Input is the fixed-format native JSONL writer; no support qualification is made.
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

std::string field(const std::string& s,const std::string& key) {
    auto p=s.find("\""+key+"\":");
    if(p==std::string::npos) throw std::runtime_error("missing field: "+key);
    p+=key.size()+3;
    auto end=p;
    if(s[p]=='[') end=s.find(']',p)+1;
    else if(s[p]=='\"') end=s.find('\"',p+1)+1;
    else end=s.find_first_of(",}",p);
    if(end<=p || end==std::string::npos) throw std::runtime_error("invalid field");
    return s.substr(p,end-p);
}
int main(int argc,char** argv) {
    try {
        if(argc!=3) throw std::runtime_error("usage: scanner closed-native.jsonl output.jsonl");
        std::ifstream input(argv[1]);
        if(!input) throw std::runtime_error("cannot open input");
        std::string line,begin,group; bool mismatch=false; unsigned long long offset=0,start=0,lines=0;
        const std::vector<std::string> fields={"reference_length","boundary","direction","coupling_multiplier_hex","substrate_multiplier_hex"};
        const std::vector<std::string> identity={"cell","epoch","fringe_id"};
        while(std::getline(input,line)) {
            auto here=offset;offset+=line.size()+1;++lines;
            if(line.rfind("{\"kind\":\"fringe_",0)!=0) continue;
            auto kind=field(line,"kind");
            if(kind=="\"fringe_rule_begin\"") {
                if(!begin.empty()) throw std::runtime_error("nested group");
                begin=line;group=line+'\n';start=here;mismatch=false;
            } else if(kind=="\"fringe_shield_leaf\"" || kind=="\"fringe_rule_end\"") {
                if(begin.empty()) throw std::runtime_error("orphan record");
                for(auto& key:identity) if(field(begin,key)!=field(line,key)) throw std::runtime_error("group identity changed");
                group+=line+'\n';
                if(group.size()>64*1024*1024) throw std::runtime_error("group exceeds memory bound");
                if(kind=="\"fringe_shield_leaf\"") {
                    for(auto& key:fields) if(field(begin,key)!=field(line,key)) {
                        if(!mismatch) std::cerr<<"first mismatch at byte "<<here<<" field "<<key<<'\n';
                        mismatch=true;
                    }
                } else {
                    if(mismatch) {
                        std::ofstream output(argv[2]);output<<group;output.close();
                        if(!output) throw std::runtime_error("output failed");
                        std::cout<<"group_start_byte="<<start<<" scanned_bytes="<<offset<<" scanned_lines="<<lines<<'\n';return 0;
                    }
                    begin.clear();group.clear();
                }
            }
        }
        throw std::runtime_error("no complete mismatching group found");
    } catch(const std::exception& e) {std::cerr<<e.what()<<'\n';return 1;}
}
