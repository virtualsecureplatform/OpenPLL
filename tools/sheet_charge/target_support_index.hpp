#pragma once
#include "../charge_compiler/json.hpp"
#include <algorithm>
#include <array>
#include <cstdint>
#include <map>
#include <set>
namespace target_support {
using I=long long;using Box=std::array<I,4>;
inline Box box(const Json&row){require(row.arr().size()==4,"target box width");Box b;for(int k=0;k<4;k++)b[k]=row.at(k).integer();require(b[0]<=b[2]&&b[1]<=b[3],"target ordered box");return b;}
inline bool overlap(Box a,Box b){return std::max(a[0],b[0])<=std::min(a[2],b[2])&&std::max(a[1],b[1])<=std::min(a[3],b[3]);}
class Index{
 struct Tree{
  struct Node{Box box;size_t begin,end;int left=-1,right=-1;};
  std::vector<Box>boxes;std::vector<Node>nodes;
  int build(size_t lo,size_t hi){
   require(lo<hi,"nonempty target support tree");Box b=boxes[lo];for(size_t k=lo+1;k<hi;k++)for(int d=0;d<2;d++){b[d]=std::min(b[d],boxes[k][d]);b[d+2]=std::max(b[d+2],boxes[k][d+2]);}
   int n=nodes.size();nodes.push_back({b,lo,hi});if(hi-lo>8){int axis=(__int128(b[2])-b[0]>=__int128(b[3])-b[1])?0:1;size_t mid=(lo+hi)/2;
    std::nth_element(boxes.begin()+lo,boxes.begin()+mid,boxes.begin()+hi,[&](Box a,Box c){return __int128(a[axis])+a[axis+2]<__int128(c[axis])+c[axis+2];});
    int left=build(lo,mid),right=build(mid,hi);nodes[n].left=left;nodes[n].right=right;
   }return n;
  }
  bool query(int n,Box support)const{const auto&node=nodes[n];if(!overlap(node.box,support))return false;
   if(node.left<0){for(size_t k=node.begin;k<node.end;k++)if(overlap(boxes[k],support))return true;return false;}
   return query(node.left,support)||query(node.right,support);
  }
 };
 std::map<I,Tree>fields;
public:
 explicit Index(const std::string&path){
  std::ifstream input(path);require(bool(input),"target support input");std::map<I,std::set<Box>>unique;std::string raw;uint64_t count=0;
  while(std::getline(input,raw)){
   auto row=Json::parse(raw);auto f=row.at("global_field").integer();require(f>0,"positive target support field");auto b=box(row.at("box"));
   const auto&points=row.at("points").arr();require(points.size()==3&&!row.at("affected_names").arr().empty(),"target triangular support");
   Box actual{points[0].at(0).integer(),points[0].at(1).integer(),points[0].at(0).integer(),points[0].at(1).integer()};
   for(const auto&p:points){require(p.arr().size()==2,"support point width");for(int d=0;d<2;d++){actual[d]=std::min(actual[d],p.at(d).integer());actual[d+2]=std::max(actual[d+2],p.at(d).integer());}}
   require(actual==b,"support box must exactly enclose its triangle");unique[f].insert(b);require(++count<=10000000,"bounded target support count");
  }require(input.eof()&&!input.bad()&&count>0,"complete nonempty target support file");
  for(const auto&[field,boxes]:unique){auto&t=fields[field];t.boxes.assign(boxes.begin(),boxes.end());t.build(0,t.boxes.size());}
 }
 bool contains(I field,Box b)const{auto f=fields.find(field);return f!=fields.end()&&f->second.query(0,b);}
};
}
