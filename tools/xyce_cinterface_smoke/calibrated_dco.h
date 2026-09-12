// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <fstream>
#include <stdexcept>
#include <utility>
#include <vector>

class CalibratedDco {
 public:
  std::vector<std::pair<int, double>> points{
      {0, 96.7173843519}, {128, 98.509313411},
      {235, 100.000534931}, {255, 100.280646517}};
  void load(const char* path) {
    std::ifstream file(path);
    if (!file) throw std::runtime_error("cannot open DCO table");
    std::vector<std::pair<int, double>> loaded;
    int code; double mhz;
    while (file >> code) {
      if (!(file >> mhz)) throw std::runtime_error("incomplete DCO calibration point");
      if (code < 0 || code > 255 || !std::isfinite(mhz) || mhz <= 0 ||
          (!loaded.empty() && code <= loaded.back().first))
        throw std::runtime_error("invalid DCO calibration point");
      loaded.emplace_back(code, mhz);
    }
    if (!file.eof() || loaded.size() < 2 || loaded.front().first != 0 || loaded.back().first != 255)
      throw std::runtime_error("DCO table must cover codes 0 through 255");
    points = loaded;
  }
  double frequency(int code) const {
    if (code < 0 || code > 255) throw std::runtime_error("invalid DCO code");
    auto hi = std::upper_bound(points.begin(), points.end(), code,
        [](int c, const auto& point) { return c < point.first; });
    if (hi == points.end()) return points.back().second;
    auto lo = hi - 1;
    return lo->second + (hi->second-lo->second)*(code-lo->first)/(hi->first-lo->first);
  }
};

class CalibratedDcoBank {
  std::array<CalibratedDco,48> bands_;
  std::array<unsigned,48> dividers_;
  bool loaded_=false;
 public:
  CalibratedDcoBank() {dividers_.fill(1);}
  void load(const char* path) {
    std::ifstream file(path);
    if(!file) throw std::runtime_error("cannot open DCO bank");
    std::array<std::vector<std::pair<int,double>>,48> rows;
    int band,code; double mhz;
    while(file>>band) {
      if(!(file>>code>>mhz)) throw std::runtime_error("incomplete DCO bank point");
      if(band<0 || band>=48 || code<0 || code>255 || !std::isfinite(mhz) || mhz<=0 ||
         (!rows[band].empty() && code<=rows[band].back().first))
        throw std::runtime_error("invalid DCO bank point");
      rows[band].emplace_back(code,mhz);
    }
    if(!file.eof()) throw std::runtime_error("malformed DCO bank");
    for(const auto& row:rows)
      if(row.size()<2 || row.front().first!=0 || row.back().first!=255)
        throw std::runtime_error("DCO bank must cover all 48 bands and codes 0..255");
    for(size_t i=0;i<rows.size();++i) bands_[i].points=std::move(rows[i]);
    dividers_.fill(1);
    loaded_=true;
  }
  void load_dividers(const char* path) {
    if(!loaded_) throw std::runtime_error("load DCO curves before dividers");
    std::ifstream file(path);
    if(!file) throw std::runtime_error("cannot open DCO dividers");
    std::array<unsigned,48> values{};
    int band;unsigned divisor;
    while(file>>band) {
      if(!(file>>divisor) || band<0 || band>=48 || values[band]!=0 ||
         (divisor!=1 && divisor!=2 && divisor!=4 && divisor!=8))
        throw std::runtime_error("invalid DCO output divider");
      values[band]=divisor;
    }
    if(!file.eof() || std::find(values.begin(),values.end(),0)!=values.end())
      throw std::runtime_error("DCO dividers must cover all 48 bands");
    dividers_=values;
  }
  unsigned divider(int band) const {
    if(!loaded_ || band<0 || band>=48) throw std::runtime_error("invalid DCO divider band");
    return dividers_[band];
  }
  double frequency(int band,int code) const {
    if(!loaded_) throw std::runtime_error("DCO bank is not loaded");
    if(band<0 || band>=48) throw std::runtime_error("invalid coarse DCO code");
    return bands_[band].frequency(code);
  }
};

// Matches the candidate's positive-edge ripple T flip-flops. The counter and
// raw oscillator phase survive a coarse output-mux change; output phase may jump.
class DcoOutputDivider {
  bool raw_=false;
  unsigned counter_=0;
 public:
  void edge() {raw_=!raw_;if(raw_) counter_=(counter_-1u)&7u;}
  bool output(unsigned divisor) const {
    switch(divisor) {
      case 1:return raw_;
      case 2:return counter_&1u;
      case 4:return counter_&2u;
      case 8:return counter_&4u;
      default:throw std::runtime_error("unsupported DCO output divider");
    }
  }
};

// Continuous phase measured in cycles since the last half-cycle edge. Changing
// frequency changes the derivative, never resets or quantizes accumulated phase.
class DcoPhase {
  double cycles_ = 0;
 public:
  void advance(double seconds, double mhz) { cycles_ += seconds*mhz*1e6; }
  double time_to_edge(double mhz) const { return std::max(0.0, .5-cycles_)/(mhz*1e6); }
  void edge() { cycles_ = std::max(0.0, cycles_-.5); }
};
