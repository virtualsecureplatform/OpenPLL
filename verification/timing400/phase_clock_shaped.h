// SPDX-License-Identifier: Apache-2.0
// Integer phase integration with a fixed measured-duty sensitivity parameter.
#pragma once
#include <algorithm>
#include <cstdint>
#include <stdexcept>

class Phase400ShapedClock {
 public:
  static constexpr std::uint64_t half_cycle = 500000000000000ULL;
 private:
  std::uint64_t last_=0, frequency_=0, high_=half_cycle;
  __uint128_t phase_=0;
  bool level_=true;
  std::uint64_t threshold() const { return level_ ? high_ : 2*half_cycle-high_; }
  void advance(std::uint64_t now) {
    if(now<last_) throw std::runtime_error("TIME_REVERSED");
    phase_+=__uint128_t(now-last_)*frequency_;last_=now;
  }
 public:
  void configure_duty(unsigned ppm) {
    if(frequency_ || phase_ || !ppm || ppm>=1000000)
      throw std::runtime_error("INVALID_DUTY_CONFIGURATION");
    high_=std::uint64_t(ppm)*1000000000ULL;
  }
  void reset(std::uint64_t now) {
    if(now<last_) throw std::runtime_error("TIME_REVERSED");
    last_=now;phase_=0;frequency_=0;level_=true;
  }
  void tune(std::uint64_t now,std::uint64_t millihertz) {
    if(!millihertz || millihertz>=std::min(high_,2*half_cycle-high_))
      throw std::runtime_error("FREQUENCY_OUTSIDE_EVENT_RESOLUTION");
    advance(now);
    if(phase_>=threshold()) throw std::runtime_error("EDGE_NOT_CONSUMED");
    frequency_=millihertz;
  }
  std::uint64_t delay() const {
    if(!frequency_) throw std::runtime_error("CLOCK_NOT_RUNNING");
    return std::uint64_t((threshold()-phase_+frequency_-1)/frequency_);
  }
  void edge(std::uint64_t now) {
    advance(now);
    if(phase_<threshold()) throw std::runtime_error("EARLY_EDGE");
    phase_-=threshold();level_=!level_;
    if(phase_>=threshold()) throw std::runtime_error("MULTIPLE_EDGES_PER_TICK");
  }
  std::uint64_t frequency() const { return frequency_; }
};
