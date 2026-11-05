#include <fstream>
#include <iostream>
#include <sstream>
#include <vector>
#include <string>
#include <cmath>
#include <cstdlib>
#include <algorithm>
int main(int argc,char**argv){
 if(argc!=3)return 2;std::ifstream in(argv[1]);std::ofstream out(argv[2]);std::string l;int n=0;long declared=-1,expected=0;std::vector<std::string> names;std::vector<int> keep;
 while(std::getline(in,l)){if(l.rfind("No. Variables:",0)==0)n=std::stoi(l.substr(14));if(l.rfind("No. Points:",0)==0)declared=std::stol(l.substr(11));if(l=="Variables:")break;}
 if(!in||!out||n<2||declared<2)return 10;
 for(int i=0;i<n;i++){if(!std::getline(in,l))return 3;std::istringstream s(l);int ix;std::string name,typ;s>>ix>>name>>typ;if(ix!=i)return 4;std::transform(name.begin(),name.end(),name.begin(),::tolower);names.push_back(name);if(i==0||name.find("xpll:")==std::string::npos||name=="v(xpll:__parent_r_node_617)")keep.push_back(i);}
 if(!std::getline(in,l)||l!="Values:")return 5;
 for(size_t i=0;i<keep.size();i++)out<<(i?",":"")<<names[keep[i]];out<<"\n";out.precision(17);double prev=-1;
 while(std::getline(in,l)){if(l.empty())continue;char* e;long ix=std::strtol(l.c_str(),&e,10);double t=std::strtod(e,&e);if(ix!=expected++||!std::isfinite(t)||t<=prev)return 6;prev=t;out<<t;size_t k=1;
 for(int i=1;i<n;i++){if(!std::getline(in,l))return 7;char*end;double v=std::strtod(l.c_str(),&end);if(end==l.c_str()||!std::isfinite(v))return 8;if(k<keep.size()&&i==keep[k]){out<<","<<v;k++;}}
 out<<"\n";}
 std::cout<<"All "<<expected<<" samples and "<<n<<" vectors finite; final time "<<prev<<" s; selected "<<keep.size()<<" vectors\n";
 return expected==declared&&std::abs(prev-260e-9)<1e-18?0:9;
}
