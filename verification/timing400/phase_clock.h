// SPDX-License-Identifier: Apache-2.0
// Exact phase integration for a1ps event scheduler; no analog-model claim.
#pragma once
#include <cstdint>
#include <stdexcept>

class Phase400Clock {
 public:
  // A frequency in millihertz integrated for one picosecond contributes
  //1e-15 cycles. Keep this integer residual across all tuning changes/edges.
  static constexpr std::uint64_t half_cycle = 500000000000000ULL;
 private:
  std::uint64_t last_ = 0, frequency_ = 0;
  __uint128_t phase_ = 0;
  void advance(std::uint64_t now) {
    if (now < last_) throw std::runtime_error("TIME_REVERSED");
    phase_ += __uint128_t(now-last_)*frequency_;
    last_ = now;
  }
 public:
  void reset(std::uint64_t now) {
    if (now < last_) throw std::runtime_error("TIME_REVERSED");
    last_=now; phase_=0; frequency_=0;
  }
  void tune(std::uint64_t now, std::uint64_t millihertz) {
    if (!millihertz || millihertz >= half_cycle)
      throw std::runtime_error("FREQUENCY_OUTSIDE_EVENT_RESOLUTION");
    advance(now);
    if (phase_ >= half_cycle) throw std::runtime_error("EDGE_NOT_CONSUMED");
    frequency_=millihertz;
  }
  std::uint64_t delay() const {
    if (!frequency_) throw std::runtime_error("CLOCK_NOT_RUNNING");
    return std::uint64_t((half_cycle-phase_+frequency_-1)/frequency_);
  }
  void edge(std::uint64_t now) {
    advance(now);
    if (phase_ < half_cycle) throw std::runtime_error("EARLY_EDGE");
    phase_ -= half_cycle;
    if (phase_ >= half_cycle) throw std::runtime_error("MULTIPLE_EDGES_PER_TICK");
  }
  std::uint64_t frequency() const { return frequency_; }
};
