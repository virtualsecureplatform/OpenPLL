// Literal bounded-memory comparison; JSON validity/row counts come from the
// separately pinned reference receipt, not this byte comparator.
#include <array>
#include <cstring>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <time.h>
#include <vector>
static double uptime(){timespec t{};if(clock_gettime(CLOCK_BOOTTIME,&t))throw std::runtime_error("clock");return t.tv_sec+t.tv_nsec*1e-9;}
int main(int argc,char** argv){try{
 if(argc!=4)throw std::runtime_error("usage: compare_bytes FILE FILE DEADLINE");double deadline=std::stod(argv[3]);
 std::ifstream a(argv[1],std::ios::binary),b(argv[2],std::ios::binary);if(!a||!b)throw std::runtime_error("open comparison inputs");
 std::vector<char> left(1<<20),right(left.size());unsigned long long total=0;
 for(;;){if(uptime()>=deadline)throw std::runtime_error("comparison deadline");a.read(left.data(),left.size());b.read(right.data(),right.size());auto na=a.gcount(),nb=b.gcount();
  if(a.bad()||b.bad()||(!a&&!a.eof())||(!b&&!b.eof()))throw std::runtime_error("comparison read");
  if(na!=nb||std::memcmp(left.data(),right.data(),size_t(na)))throw std::runtime_error("bytes differ");total+=static_cast<unsigned long long>(na);
  if(a.eof()||b.eof()){if(!a.eof()||!b.eof())throw std::runtime_error("EOF differs");break;}
 }
 std::cout<<"{\"literal_bytes_identical\":true,\"bytes_compared\":"<<total<<"}\n";return 0;
}catch(const std::exception& e){std::cerr<<"compare_bytes: "<<e.what()<<'\n';return 1;}}
