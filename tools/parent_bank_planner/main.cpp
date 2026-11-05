// Exact row-interval implementation of the retained exhaustive bank placement.
#include "../charge_compiler/json.hpp"
#include <algorithm>
#include <array>
#include <iostream>
#include <cstdlib>
#include <set>
#include <tuple>
using I=long long;
using Box=std::array<I,4>;
static I floor_div(I a,I b){I q=a/b,r=a%b;return q-(r<0);}
static I ceil_div(I a,I b){return -floor_div(-a,b);}
int main(int argc,char** argv){try{
    require(argc==2,"usage: parent_bank_planner CONFIG");Json cfg=Json::read(argv[1]);
    constexpr I X0=10080,Y0=13320,SX=480,SY=3330,W=4320,H=3330,R=100000;
    std::vector<Box> occupied;
    for(auto& row:cfg.at("macro_boxes").arr()){
        require(row.arr().size()==4,"macro box shape");Box b;
        for(int i=0;i<4;++i)b[i]=row.at(i).integer();
        require(0<=b[0]&&b[0]<b[2]&&b[2]<=1000000&&0<=b[1]&&b[1]<b[3]&&b[3]<=850000,"macro box bounds");
        occupied.push_back({b[0]-3000,b[1]-3000,b[2]+3000,b[3]+3000});
    }
    Json out=Json::array();std::set<std::string> seen;
    for(auto& target:cfg.at("targets").arr()){
        std::string name=target.at("net").str();require(seen.insert(name).second,"duplicate net");
        require(target.at("point").arr().size()==2,"port point shape");
        I cx=target.at("point").at(0).integer(),cy=target.at("point").at(1).integer();
        require(0<=cx&&cx<=1000000&&0<=cy&&cy<=850000,"port point bounds");
        I rlo=std::max<I>(0,floor_div(cy-R-Y0,SY)),rhi=std::min<I>(248,floor_div(cy+R-Y0,SY));
        I clo=std::max<I>(0,floor_div(cx-R-X0,SX)),chi=std::min<I>(2033,floor_div(cx+R-X0,SX));
        bool found=false;std::tuple<I,I,I> best;
        for(I row=rlo;row<=rhi;++row){
            if(row%2)continue;
            I y=Y0+row*SY;
            std::vector<std::pair<I,I>> banned;
            for(auto& b:occupied){
                if(y>=b[3]||y+H<=b[1])continue;
                I lo=std::max(clo,floor_div(b[0]-W-X0,SX)+1);
                I hi=std::min(chi,ceil_div(b[2]-X0,SX)-1);
                if(lo<=hi)banned.emplace_back(lo,hi);
            }
            std::sort(banned.begin(),banned.end());
            auto gap=[&](I lo,I hi){
                if(lo>hi)return;
                I near=floor_div(cx-W/2-X0,SX);
                for(I candidate:{near,near+1}){
                    I col=std::clamp(candidate,lo,hi),x=X0+col*SX;
                    auto score=std::make_tuple(std::llabs(x+W/2-cx)+std::llabs(y+H/2-cy),x,y);
                    if(!found||score<best){best=score;found=true;}
                }
            };
            I next=clo;
            for(auto [lo,hi]:banned){if(lo>next)gap(next,lo-1);next=std::max(next,hi+1);}
            gap(next,chi);
        }
        require(found,"no legal protection-bank site for "+name);
        auto [distance,x,y]=best;occupied.push_back({x-1920,y,x+W+1920,y+H});
        Json result=Json::object();result["net"]=name;result["x_nm"]=x;result["y_nm"]=y;
        result["orient"]="R0";result["diodes"]=4;result["distance_nm"]=distance;out.push(result);
    }
    std::cout<<out.dump()<<'\n';require(bool(std::cout),"plan output failure");return 0;
}catch(const std::exception& e){std::cerr<<"parent_bank_planner: "<<e.what()<<'\n';return 1;}}
