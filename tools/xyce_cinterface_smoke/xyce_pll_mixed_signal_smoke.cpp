#include <N_CIR_XyceCInterface.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cctype>
#include <cstdlib>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <limits>
#include <sstream>
#include <string>
#include <utility>
#include <vector>

namespace {

constexpr double kVdd = 1.8;
constexpr double kEdge = 20.0e-12;
constexpr double kPulseWidth = 2.0e-9;
constexpr double kDecisionThreshold = 40.0e-12;

struct StatePoint {
  double time_s;
  int state;
};

std::vector<char> mutable_string(const std::string &value) {
  std::vector<char> data(value.begin(), value.end());
  data.push_back('\0');
  return data;
}

std::string upper(std::string value) {
  for (char &ch : value) {
    ch = static_cast<char>(std::toupper(static_cast<unsigned char>(ch)));
  }
  return value;
}

std::vector<char *> make_name_ptrs(std::vector<std::vector<char>> &buffers) {
  std::vector<char *> ptrs;
  ptrs.reserve(buffers.size());
  for (auto &buffer : buffers) {
    ptrs.push_back(buffer.data());
  }
  return ptrs;
}

std::vector<std::string> get_device_names(void **xyce, const char *kind) {
  int count = 0;
  int max_name = 0;
  std::vector<char> kind_name = mutable_string(kind);
  if (xyce_getNumDevices(xyce, kind_name.data(), &count, &max_name) != 1 ||
      count <= 0) {
    return {};
  }

  std::vector<std::vector<char>> buffers(
      static_cast<size_t>(count),
      std::vector<char>(static_cast<size_t>(max_name + 1), '\0'));
  std::vector<char *> ptrs = make_name_ptrs(buffers);
  if (std::strcmp(kind, "YDAC") == 0) {
    if (xyce_getDACDeviceNames(xyce, &count, ptrs.data()) != 1) {
      return {};
    }
  } else if (xyce_getDeviceNames(xyce, kind_name.data(), &count, ptrs.data()) !=
             1) {
    return {};
  }

  std::vector<std::string> names;
  names.reserve(static_cast<size_t>(count));
  for (int index = 0; index < count; ++index) {
    names.emplace_back(ptrs[static_cast<size_t>(index)]);
  }
  return names;
}

std::string find_device(const std::vector<std::string> &names,
                        const std::string &token) {
  const std::string token_upper = upper(token);
  for (const std::string &name : names) {
    if (upper(name).find(token_upper) != std::string::npos) {
      return name;
    }
  }
  return "";
}

bool update_dac(void **xyce, const std::string &name,
                const std::vector<std::pair<double, double>> &points) {
  std::vector<double> times;
  std::vector<double> volts;
  times.reserve(points.size());
  volts.reserve(points.size());
  for (const auto &[time, volt] : points) {
    times.push_back(time);
    volts.push_back(volt);
  }
  std::vector<char> mutable_name = mutable_string(name);
  return xyce_updateTimeVoltagePairs(xyce, mutable_name.data(),
                                     static_cast<int>(points.size()),
                                     times.data(), volts.data()) == 1;
}

std::vector<StatePoint> get_adc_points(void **xyce, const std::string &token) {
  constexpr int max_adcs = 16;
  constexpr int max_name = 256;
  constexpr int max_points = 4096;

  std::array<std::array<char, max_name>, max_adcs> names{};
  std::array<char *, max_adcs> name_ptrs{};
  for (int index = 0; index < max_adcs; ++index) {
    name_ptrs[static_cast<size_t>(index)] =
        names[static_cast<size_t>(index)].data();
  }

  std::array<int, max_adcs> point_counts{};
  std::array<std::array<double, max_points>, max_adcs> times{};
  std::array<std::array<int, max_points>, max_adcs> states{};
  std::array<double *, max_adcs> time_ptrs{};
  std::array<int *, max_adcs> state_ptrs{};
  for (int index = 0; index < max_adcs; ++index) {
    time_ptrs[static_cast<size_t>(index)] =
        times[static_cast<size_t>(index)].data();
    state_ptrs[static_cast<size_t>(index)] =
        states[static_cast<size_t>(index)].data();
  }

  int adc_count = 0;
  int status = xyce_getTimeStatePairsADCLimitData(
      xyce, max_adcs, max_name, max_points, &adc_count, name_ptrs.data(),
      point_counts.data(), time_ptrs.data(), state_ptrs.data());
  if (status != 1 || adc_count <= 0) {
    return {};
  }

  const std::string token_upper = upper(token);
  for (int adc = 0; adc < adc_count; ++adc) {
    const std::string name = names[static_cast<size_t>(adc)].data();
    if (upper(name).find(token_upper) == std::string::npos) {
      continue;
    }
    std::vector<StatePoint> points;
    for (int point = 0; point < point_counts[static_cast<size_t>(adc)];
         ++point) {
      points.push_back(
          {times[static_cast<size_t>(adc)][static_cast<size_t>(point)],
           states[static_cast<size_t>(adc)][static_cast<size_t>(point)]});
    }
    std::sort(points.begin(), points.end(),
              [](const StatePoint &lhs, const StatePoint &rhs) {
                return lhs.time_s < rhs.time_s;
              });
    return points;
  }
  return {};
}

double high_time_in_window(std::vector<StatePoint> points, double start_s,
                           double end_s) {
  if (points.empty() || end_s <= start_s) {
    return 0.0;
  }
  points.push_back({end_s, points.back().state});
  std::sort(points.begin(), points.end(),
            [](const StatePoint &lhs, const StatePoint &rhs) {
              return lhs.time_s < rhs.time_s;
            });

  int state = 0;
  for (const StatePoint &point : points) {
    if (point.time_s <= start_s) {
      state = point.state;
    } else {
      break;
    }
  }

  double cursor = start_s;
  double high_time = 0.0;
  for (const StatePoint &point : points) {
    if (point.time_s <= start_s) {
      continue;
    }
    const double next = std::min(point.time_s, end_s);
    if (state == 1 && next > cursor) {
      high_time += next - cursor;
    }
    cursor = next;
    state = point.state;
    if (cursor >= end_s) {
      break;
    }
  }
  return high_time;
}

std::vector<std::pair<double, double>> pulse_points(double now_s,
                                                    double rise_s) {
  return {{now_s, 0.0},
          {rise_s, 0.0},
          {rise_s + kEdge, kVdd},
          {rise_s + kPulseWidth, kVdd},
          {rise_s + kPulseWidth + kEdge, 0.0},
          {rise_s + kPulseWidth + 2.0e-9, 0.0}};
}

double wrap_phase(double phase_s, double period_s, double wrap_cycles) {
  if (wrap_cycles <= 0.0) {
    return phase_s;
  }
  const double limit_s = wrap_cycles * period_s;
  while (phase_s > limit_s) {
    phase_s -= period_s;
  }
  while (phase_s < -limit_s) {
    phase_s += period_s;
  }
  return phase_s;
}

[[noreturn]] void usage(const char *name) {
  std::cerr
      << "usage: " << name
      << " DECK [--init-code N] [--target-code N] [--cycles N]\n"
      << "       [--ki N] [--kp N] [--frac N] [--boost-shift N]\n"
      << "       [--boost-after N] [--track-decay-shift N]\n"
      << "       [--ndiv N] [--expect increase|decrease]\n"
      << "       [--phase-ps PS] [--min-motion N] [--tol-code N]\n"
      << "       [--f0-mhz F] [--f64-mhz F] [--f128-mhz F]\n"
      << "       [--f192-mhz F] [--f255-mhz F] [--coarse-code N]\n"
      << "       [--dco-coarse-step-mhz F] [--phase-wrap-cycles F]\n"
      << "       [--ref-mhz F] [--target-mhz F]\n";
  std::exit(EXIT_FAILURE);
}

int parse_int_arg(int argc, char **argv, int &index) {
  if (index + 1 >= argc) {
    usage(argv[0]);
  }
  return std::stoi(argv[++index]);
}

double parse_double_arg(int argc, char **argv, int &index) {
  if (index + 1 >= argc) {
    usage(argv[0]);
  }
  return std::stod(argv[++index]);
}

struct Args {
  std::string deck;
  int init_code = 96;
  int target_code = 128;
  int cycles = 8;
  int ki = 255;
  int kp = 8;
  int frac = 6;
  int boost_shift = 4;
  int boost_after = 1;
  int track_decay_shift = 0;
  int ndiv = 2;
  std::string expect = "increase";
  double phase_ps = std::numeric_limits<double>::quiet_NaN();
  int min_motion = 8;
  int tol_code = 24;
  double f0_mhz = 50.955942;
  double f64_mhz = 55.205750;
  double f128_mhz = 60.174879;
  double f192_mhz = 66.031451;
  double f255_mhz = 72.479371;
  int coarse_code = 0;
  double dco_coarse_step_mhz = 0.0;
  double phase_wrap_cycles = 0.45;
  double ref_mhz = std::numeric_limits<double>::quiet_NaN();
  double target_mhz = std::numeric_limits<double>::quiet_NaN();
};

double dco_freq_hz(int code, const Args &args) {
  struct Point {
    int code;
    double mhz;
  };

  const double coarse_offset_mhz =
      static_cast<double>(args.coarse_code) * args.dco_coarse_step_mhz;
  const Point table[] = {
      {0, args.f0_mhz + coarse_offset_mhz},
      {64, args.f64_mhz + coarse_offset_mhz},
      {128, args.f128_mhz + coarse_offset_mhz},
      {192, args.f192_mhz + coarse_offset_mhz},
      {255, args.f255_mhz + coarse_offset_mhz},
  };

  code = std::clamp(code, 0, 255);
  for (size_t i = 1; i < sizeof(table) / sizeof(table[0]); ++i) {
    if (code <= table[i].code) {
      const Point &lo = table[i - 1];
      const Point &hi = table[i];
      const double t = static_cast<double>(code - lo.code) /
                       static_cast<double>(hi.code - lo.code);
      return (lo.mhz + t * (hi.mhz - lo.mhz)) * 1.0e6;
    }
  }
  return table[sizeof(table) / sizeof(table[0]) - 1].mhz * 1.0e6;
}

Args parse_args(int argc, char **argv) {
  if (argc < 2) {
    usage(argv[0]);
  }

  Args args;
  args.deck = argv[1];
  for (int index = 2; index < argc; ++index) {
    const std::string opt = argv[index];
    if (opt == "--init-code") {
      args.init_code = parse_int_arg(argc, argv, index);
    } else if (opt == "--target-code") {
      args.target_code = parse_int_arg(argc, argv, index);
    } else if (opt == "--cycles") {
      args.cycles = parse_int_arg(argc, argv, index);
    } else if (opt == "--ki") {
      args.ki = parse_int_arg(argc, argv, index);
    } else if (opt == "--kp") {
      args.kp = parse_int_arg(argc, argv, index);
    } else if (opt == "--frac") {
      args.frac = parse_int_arg(argc, argv, index);
    } else if (opt == "--boost-shift") {
      args.boost_shift = parse_int_arg(argc, argv, index);
    } else if (opt == "--boost-after") {
      args.boost_after = parse_int_arg(argc, argv, index);
    } else if (opt == "--track-decay-shift") {
      args.track_decay_shift = parse_int_arg(argc, argv, index);
    } else if (opt == "--ndiv") {
      args.ndiv = parse_int_arg(argc, argv, index);
    } else if (opt == "--expect") {
      if (index + 1 >= argc) {
        usage(argv[0]);
      }
      args.expect = argv[++index];
    } else if (opt == "--phase-ps") {
      args.phase_ps = parse_double_arg(argc, argv, index);
    } else if (opt == "--min-motion") {
      args.min_motion = parse_int_arg(argc, argv, index);
    } else if (opt == "--tol-code") {
      args.tol_code = parse_int_arg(argc, argv, index);
    } else if (opt == "--f0-mhz") {
      args.f0_mhz = parse_double_arg(argc, argv, index);
    } else if (opt == "--f64-mhz") {
      args.f64_mhz = parse_double_arg(argc, argv, index);
    } else if (opt == "--f128-mhz") {
      args.f128_mhz = parse_double_arg(argc, argv, index);
    } else if (opt == "--f192-mhz") {
      args.f192_mhz = parse_double_arg(argc, argv, index);
    } else if (opt == "--f255-mhz") {
      args.f255_mhz = parse_double_arg(argc, argv, index);
    } else if (opt == "--coarse-code") {
      args.coarse_code = parse_int_arg(argc, argv, index);
    } else if (opt == "--dco-coarse-step-mhz") {
      args.dco_coarse_step_mhz = parse_double_arg(argc, argv, index);
    } else if (opt == "--phase-wrap-cycles") {
      args.phase_wrap_cycles = parse_double_arg(argc, argv, index);
    } else if (opt == "--ref-mhz") {
      args.ref_mhz = parse_double_arg(argc, argv, index);
    } else if (opt == "--target-mhz") {
      args.target_mhz = parse_double_arg(argc, argv, index);
    } else {
      usage(argv[0]);
    }
  }

  if (args.init_code < 0 || args.init_code > 255 || args.target_code < 0 ||
      args.target_code > 255 || args.cycles <= 0 || args.ki < 0 ||
      args.kp < 0 || args.frac < 0 || args.frac > 20 ||
      args.boost_shift < 0 || args.boost_shift > 20 ||
      args.track_decay_shift < 0 || args.track_decay_shift > 20 ||
      args.boost_after < 1 || args.ndiv <= 0 ||
      args.coarse_code < 0 || args.coarse_code > 63 ||
      args.dco_coarse_step_mhz < 0.0 ||
      args.phase_wrap_cycles < 0.0 ||
      args.f0_mhz <= 0.0 || args.f64_mhz <= args.f0_mhz ||
      args.f128_mhz <= args.f64_mhz || args.f192_mhz <= args.f128_mhz ||
      args.f255_mhz <= args.f192_mhz ||
      (!std::isnan(args.ref_mhz) && args.ref_mhz <= 0.0) ||
      (!std::isnan(args.target_mhz) && args.target_mhz <= 0.0) ||
      (args.expect != "increase" && args.expect != "decrease")) {
    usage(argv[0]);
  }

  return args;
}

double target_freq_hz(const Args &args) {
  if (!std::isnan(args.target_mhz)) {
    return args.target_mhz * 1.0e6;
  }
  if (!std::isnan(args.ref_mhz)) {
    return args.ref_mhz * 1.0e6 * static_cast<double>(args.ndiv);
  }
  return dco_freq_hz(args.target_code, args);
}

struct DlfModel {
  explicit DlfModel(const Args &args)
      : cfg(args),
        acc(static_cast<int64_t>(args.init_code << 2) << args.frac),
        code10(args.init_code << 2),
        dco_code(args.init_code) {}

  void update(int decision) {
    if (decision == 0) {
      code10 = static_cast<int>(acc >> cfg.frac);
      dco_code = std::clamp(code10 >> 2, 0, 255);
      return;
    }

    const bool reversal = (last_dir != 0) && (decision != last_dir);
    if (decision == last_dir) {
      ++same_dir_count;
    } else {
      last_dir = decision;
      same_dir_count = 1;
    }

    int64_t ki_eff = cfg.ki;
    if (cfg.boost_shift > 0 && same_dir_count >= cfg.boost_after) {
      ki_eff <<= cfg.boost_shift;
    } else if (cfg.track_decay_shift > 0 && reversal) {
      ki_eff >>= cfg.track_decay_shift;
      if (cfg.ki > 0 && ki_eff == 0) {
        ki_eff = 1;
      }
    }

    acc += static_cast<int64_t>(decision) * ki_eff;
    const int64_t max_acc = static_cast<int64_t>(1023) << cfg.frac;
    acc = std::clamp<int64_t>(acc, 0, max_acc);

    const int base10 = static_cast<int>(acc >> cfg.frac);
    code10 = std::clamp(base10 + decision * cfg.kp, 0, 1023);
    dco_code = std::clamp(code10 >> 2, 0, 255);
  }

  const Args &cfg;
  int64_t acc;
  int code10;
  int dco_code;
  int last_dir = 0;
  int same_dir_count = 0;
};

std::string decision_name(int decision) {
  if (decision > 0) {
    return "increase";
  }
  if (decision < 0) {
    return "decrease";
  }
  return "hold";
}

}  // namespace

int main(int argc, char **argv) {
  const Args args = parse_args(argc, argv);
  const int expected_dir = (args.expect == "increase") ? 1 : -1;

  void *xyce = nullptr;
  xyce_open(&xyce);
  if (xyce == nullptr) {
    std::cerr << "xyce_pll_mixed_signal_smoke=fail error=\"xyce_open returned null\"\n";
    return EXIT_FAILURE;
  }

  std::vector<char> program_name = mutable_string("xyce_pll_mixed_signal_smoke");
  std::vector<char> deck_name = mutable_string(args.deck);
  std::array<char *, 3> xyce_argv = {program_name.data(), deck_name.data(),
                                     nullptr};
  if (xyce_initialize(&xyce, 2, xyce_argv.data()) != 1) {
    std::cerr << "xyce_pll_mixed_signal_smoke=fail error=\"xyce_initialize failed\"\n";
    xyce_close(&xyce);
    return EXIT_FAILURE;
  }

  const std::vector<std::string> dac_names = get_device_names(&xyce, "YDAC");
  const std::string ref_dac = find_device(dac_names, "REF");
  const std::string div_dac = find_device(dac_names, "DIV");
  if (ref_dac.empty() || div_dac.empty()) {
    std::cerr << "xyce_pll_mixed_signal_smoke=fail error=\"missing REF/DIV YDAC\"\n";
    xyce_close(&xyce);
    return EXIT_FAILURE;
  }

  const auto seed_low =
      std::vector<std::pair<double, double>>{{0.0, 0.0}, {1.0e-12, 0.0}};
  if (!update_dac(&xyce, ref_dac, seed_low) ||
      !update_dac(&xyce, div_dac, seed_low)) {
    std::cerr << "xyce_pll_mixed_signal_smoke=fail error=\"failed to seed DACs\"\n";
    xyce_close(&xyce);
    return EXIT_FAILURE;
  }

  double actual_time = 0.0;
  if (xyce_simulateUntil(&xyce, 1.0e-12, &actual_time) != 1) {
    std::cerr << "xyce_pll_mixed_signal_smoke=fail error=\"initial simulateUntil failed\"\n";
    xyce_close(&xyce);
    return EXIT_FAILURE;
  }

  DlfModel dlf(args);
  const double target_hz = target_freq_hz(args);
  const double ref_mhz = !std::isnan(args.ref_mhz)
                             ? args.ref_mhz
                             : (target_hz / 1.0e6) / static_cast<double>(args.ndiv);
  const double target_mhz = target_hz / 1.0e6;
  const double tref = static_cast<double>(args.ndiv) / target_hz;
  const double base_time = 20.0e-9;
  double phase = std::isnan(args.phase_ps)
                     ? (expected_dir > 0 ? 0.20e-9 : -0.20e-9)
                     : args.phase_ps * 1.0e-12;
  phase = wrap_phase(phase, tref, args.phase_wrap_cycles);

  const int start_code = dlf.dco_code;
  int min_abs_error = std::abs(start_code - args.target_code);
  int expected_decisions = 0;

  std::cout << std::fixed << std::setprecision(3);
  std::cout << "cycle,ref_ns,div_ns,phase_ps,up_ps,dn_ps,decision,dco_code,"
               "fdco_mhz\n";

  for (int cycle = 0; cycle < args.cycles; ++cycle) {
    const int code_before = dlf.dco_code;
    const double fdco = dco_freq_hz(code_before, args);
    const double ref_rise = base_time + static_cast<double>(cycle) * tref;
    const double div_rise = ref_rise + phase;
    const double window_start =
        std::max(actual_time, std::min(ref_rise, div_rise) - 0.5e-9);
    const double window_end =
        std::max(ref_rise, div_rise) + kPulseWidth + 2.0e-9;

    if (!update_dac(&xyce, ref_dac, pulse_points(actual_time, ref_rise)) ||
        !update_dac(&xyce, div_dac, pulse_points(actual_time, div_rise))) {
      std::cerr << "xyce_pll_mixed_signal_smoke=fail error=\"failed to update DAC waveforms\"\n";
      xyce_close(&xyce);
      return EXIT_FAILURE;
    }

    if (xyce_simulateUntil(&xyce, window_end, &actual_time) != 1) {
      std::cerr << "xyce_pll_mixed_signal_smoke=fail error=\"simulateUntil failed\"\n";
      xyce_close(&xyce);
      return EXIT_FAILURE;
    }

    const std::vector<StatePoint> up = get_adc_points(&xyce, "UP_ADC");
    const std::vector<StatePoint> dn = get_adc_points(&xyce, "DN_ADC");
    if (up.empty() || dn.empty()) {
      std::cerr << "xyce_pll_mixed_signal_smoke=fail error=\"missing UP/DN ADC states\"\n";
      xyce_close(&xyce);
      return EXIT_FAILURE;
    }

    const double up_time = high_time_in_window(up, window_start, window_end);
    const double dn_time = high_time_in_window(dn, window_start, window_end);
    int decision = 0;
    if (up_time > dn_time + kDecisionThreshold) {
      decision = 1;
    } else if (dn_time > up_time + kDecisionThreshold) {
      decision = -1;
    }

    if (decision == expected_dir) {
      ++expected_decisions;
    }
    dlf.update(decision);
    min_abs_error =
        std::min(min_abs_error, std::abs(dlf.dco_code - args.target_code));

    std::cout << cycle << ',' << ref_rise * 1.0e9 << ','
              << div_rise * 1.0e9 << ',' << phase * 1.0e12 << ','
              << up_time * 1.0e12 << ',' << dn_time * 1.0e12 << ','
              << decision_name(decision) << ',' << dlf.dco_code << ','
              << fdco * 1.0e-6 << '\n';

    phase =
        wrap_phase(phase + static_cast<double>(args.ndiv) / fdco - tref, tref,
                   args.phase_wrap_cycles);
  }

  xyce_close(&xyce);

  const int final_code = dlf.dco_code;
  const bool moved =
      (expected_dir > 0) ? (final_code >= start_code + args.min_motion)
                         : (final_code <= start_code - args.min_motion);
  const bool improved =
      min_abs_error < std::abs(start_code - args.target_code);
  const bool has_expected_decision = expected_decisions > 0;
  const bool pass = moved && improved && has_expected_decision;

  std::cout << "xyce_pll_mixed_signal_smoke=" << (pass ? "pass" : "fail")
            << " expect=" << args.expect << " start_code=" << start_code
            << " final_code=" << final_code
            << " target_code=" << args.target_code
            << " ref_mhz=" << ref_mhz
            << " target_mhz=" << target_mhz
            << " min_abs_error=" << min_abs_error
            << " tol_code=" << args.tol_code
            << " expected_decisions=" << expected_decisions << '\n';

  return pass ? EXIT_SUCCESS : EXIT_FAILURE;
}
