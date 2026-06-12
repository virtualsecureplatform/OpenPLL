#include <N_CIR_XyceCInterface.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <cctype>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <limits>
#include <string>
#include <utility>
#include <vector>

namespace {

constexpr double kVdd = 1.8;
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
  constexpr int max_points = 8192;

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

std::vector<std::pair<double, double>> code_points(double now_s, int code) {
  const double volt = kVdd * static_cast<double>(std::clamp(code, 0, 255)) / 255.0;
  return {{now_s, volt}, {now_s + 1.0e-12, volt}};
}

std::vector<double> rising_edges_in_window(std::vector<StatePoint> points,
                                           double start_s, double end_s) {
  std::vector<double> edges;
  if (points.empty() || end_s <= start_s) {
    return edges;
  }
  std::sort(points.begin(), points.end(),
            [](const StatePoint &lhs, const StatePoint &rhs) {
              return lhs.time_s < rhs.time_s;
            });

  int state = points.front().state;
  for (const StatePoint &point : points) {
    if (point.time_s <= start_s) {
      state = point.state;
      continue;
    }
    if (point.time_s > end_s) {
      break;
    }
    if (state == 0 && point.state == 1) {
      edges.push_back(point.time_s);
    }
    state = point.state;
  }
  return edges;
}

double frequency_mhz_from_edges(const std::vector<double> &edges) {
  if (edges.size() < 2) {
    return 0.0;
  }
  const double span_s = edges.back() - edges.front();
  if (span_s <= 0.0) {
    return 0.0;
  }
  return (static_cast<double>(edges.size() - 1) / span_s) / 1.0e6;
}

[[noreturn]] void usage(const char *name) {
  std::cerr
      << "usage: " << name
      << " DECK [--init-code N] [--target-code N] [--cycles N]\n"
      << "       [--ki N] [--kp N] [--frac N] [--ref-mhz F]\n"
      << "       [--expect increase|decrease] [--min-motion N] [--tol-code N]\n"
      << "       [--target-mhz F] [--freq-tol-mhz F] [--measure-cycles N]\n"
      << "       [--measure-settle-ns NS] [--min-pllout-rises N]\n"
      << "       [--start-ns NS] [--prop-rail-guard]\n";
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
  int init_code = 0;
  int target_code = 32;
  int cycles = 4;
  int ki = 128;
  int kp = 8;
  int frac = 2;
  int boost_shift = 0;
  int boost_after = 1;
  int ndiv = 2;
  double ref_mhz = 63.443725;
  std::string expect = "increase";
  int min_motion = 20;
  int tol_code = 8;
  int measure_cycles = 2;
  int min_pllout_rises = 3;
  double target_mhz = 0.0;
  double freq_tol_mhz = 2.0;
  double measure_settle_ns = 1.0;
  double start_ns = 20.0;
  bool prop_rail_guard = false;
};

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
    } else if (opt == "--ndiv") {
      args.ndiv = parse_int_arg(argc, argv, index);
    } else if (opt == "--ref-mhz") {
      args.ref_mhz = parse_double_arg(argc, argv, index);
    } else if (opt == "--expect") {
      if (index + 1 >= argc) {
        usage(argv[0]);
      }
      args.expect = argv[++index];
    } else if (opt == "--min-motion") {
      args.min_motion = parse_int_arg(argc, argv, index);
    } else if (opt == "--tol-code") {
      args.tol_code = parse_int_arg(argc, argv, index);
    } else if (opt == "--measure-cycles") {
      args.measure_cycles = parse_int_arg(argc, argv, index);
    } else if (opt == "--min-pllout-rises") {
      args.min_pllout_rises = parse_int_arg(argc, argv, index);
    } else if (opt == "--target-mhz") {
      args.target_mhz = parse_double_arg(argc, argv, index);
    } else if (opt == "--freq-tol-mhz") {
      args.freq_tol_mhz = parse_double_arg(argc, argv, index);
    } else if (opt == "--measure-settle-ns") {
      args.measure_settle_ns = parse_double_arg(argc, argv, index);
    } else if (opt == "--start-ns") {
      args.start_ns = parse_double_arg(argc, argv, index);
    } else if (opt == "--prop-rail-guard") {
      args.prop_rail_guard = true;
    } else {
      usage(argv[0]);
    }
  }

  if (args.init_code < 0 || args.init_code > 255 || args.target_code < 0 ||
      args.target_code > 255 || args.cycles <= 0 || args.ki < 0 ||
      args.kp < 0 || args.frac < 0 || args.frac > 20 ||
      args.boost_shift < 0 || args.boost_shift > 20 ||
      args.boost_after < 1 || args.ndiv <= 0 || args.ref_mhz <= 0.0 ||
      args.measure_cycles < 0 || args.min_pllout_rises < 2 ||
      args.target_mhz < 0.0 || args.freq_tol_mhz <= 0.0 ||
      args.measure_settle_ns < 0.0 || args.start_ns < 0.0 ||
      (args.expect != "increase" && args.expect != "decrease")) {
    usage(argv[0]);
  }
  if (args.target_mhz == 0.0) {
    args.target_mhz = args.ref_mhz * static_cast<double>(args.ndiv);
  }
  return args;
}

struct DlfModel {
  explicit DlfModel(const Args &args)
      : cfg(args),
        acc(static_cast<int64_t>(args.init_code << 2) << args.frac),
        code10(args.init_code << 2),
        dco_code(args.init_code) {}

  void update(int decision) {
    const int64_t max_code10 = 1023;
    const int64_t max_acc = max_code10 << cfg.frac;
    const int64_t high_rail_code10 = 255 << 2;
    const int64_t low_visible_next_code10 = 1 << 2;
    const int64_t kp_acc = static_cast<int64_t>(cfg.kp) << cfg.frac;
    const int64_t integ_code = std::clamp<int64_t>(acc >> cfg.frac, 0, max_code10);

    bool inc = decision > 0;
    bool dec = decision < 0;
    bool prop_low_guard = false;
    bool prop_high_guard = false;
    if (cfg.prop_rail_guard) {
      prop_low_guard = (acc - kp_acc) < (low_visible_next_code10 << cfg.frac);
      prop_high_guard = (acc + kp_acc) >= (high_rail_code10 << cfg.frac);
    }

    const bool inc_eff =
        (inc && !prop_high_guard && integ_code < high_rail_code10) ||
        (((integ_code == 0) || prop_low_guard) && dec);
    const bool dec_eff =
        (dec && !prop_low_guard && integ_code != 0) ||
        (((integ_code >= high_rail_code10) || prop_high_guard) && inc);

    int dir = 0;
    if (inc_eff) {
      dir = 1;
    } else if (dec_eff) {
      dir = -1;
    }

    if (dir == 0) {
      code10 = static_cast<int>(integ_code);
      dco_code = std::clamp(code10 >> 2, 0, 255);
      last_dir = 0;
      same_dir_count = 0;
      return;
    }

    if (dir == last_dir) {
      ++same_dir_count;
    } else {
      last_dir = dir;
      same_dir_count = 1;
    }

    int64_t ki_eff = cfg.ki;
    if (cfg.boost_shift > 0 && same_dir_count >= cfg.boost_after) {
      ki_eff <<= cfg.boost_shift;
    }

    acc = std::clamp<int64_t>(acc + static_cast<int64_t>(dir) * ki_eff, 0, max_acc);
    const int64_t prop_acc =
        std::clamp<int64_t>(acc + static_cast<int64_t>(dir) * kp_acc, 0, max_acc);
    code10 = static_cast<int>(prop_acc >> cfg.frac);
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
    std::cerr << "xyce_pll_analog_dco_mixed_signal_smoke=fail error=\"xyce_open returned null\"\n";
    return EXIT_FAILURE;
  }

  std::vector<char> program_name =
      mutable_string("xyce_pll_analog_dco_mixed_signal_smoke");
  std::vector<char> deck_name = mutable_string(args.deck);
  std::array<char *, 3> xyce_argv = {program_name.data(), deck_name.data(),
                                     nullptr};
  if (xyce_initialize(&xyce, 2, xyce_argv.data()) != 1) {
    std::cerr << "xyce_pll_analog_dco_mixed_signal_smoke=fail error=\"xyce_initialize failed\"\n";
    xyce_close(&xyce);
    return EXIT_FAILURE;
  }

  const std::vector<std::string> dac_names = get_device_names(&xyce, "YDAC");
  const std::string code_dac = find_device(dac_names, "CODE");
  if (code_dac.empty()) {
    std::cerr << "xyce_pll_analog_dco_mixed_signal_smoke=fail error=\"missing CODE YDAC\"\n";
    xyce_close(&xyce);
    return EXIT_FAILURE;
  }

  DlfModel dlf(args);
  double actual_time = 0.0;
  if (!update_dac(&xyce, code_dac, code_points(0.0, dlf.dco_code))) {
    std::cerr << "xyce_pll_analog_dco_mixed_signal_smoke=fail error=\"failed to seed DCO code DAC\"\n";
    xyce_close(&xyce);
    return EXIT_FAILURE;
  }
  if (xyce_simulateUntil(&xyce, args.start_ns * 1.0e-9, &actual_time) != 1) {
    std::cerr << "xyce_pll_analog_dco_mixed_signal_smoke=fail error=\"initial simulateUntil failed\"\n";
    xyce_close(&xyce);
    return EXIT_FAILURE;
  }

  const double tref = 1.0 / (args.ref_mhz * 1.0e6);
  const double start_s = args.start_ns * 1.0e-9;
  const int start_code = dlf.dco_code;
  int min_abs_error = std::abs(start_code - args.target_code);
  int expected_decisions = 0;

  std::cout << std::fixed << std::setprecision(3);
  std::cout << "cycle,start_ns,end_ns,up_ps,dn_ps,decision,dco_code,code10\n";

  for (int cycle = 0; cycle < args.cycles; ++cycle) {
    const double window_start = start_s + static_cast<double>(cycle) * tref;
    const double window_end = start_s + static_cast<double>(cycle + 1) * tref;

    if (window_start > actual_time &&
        xyce_simulateUntil(&xyce, window_start, &actual_time) != 1) {
      std::cerr << "xyce_pll_analog_dco_mixed_signal_smoke=fail error=\"simulateUntil window start failed\"\n";
      xyce_close(&xyce);
      return EXIT_FAILURE;
    }
    if (!update_dac(&xyce, code_dac, code_points(actual_time, dlf.dco_code))) {
      std::cerr << "xyce_pll_analog_dco_mixed_signal_smoke=fail error=\"failed to update DCO code DAC\"\n";
      xyce_close(&xyce);
      return EXIT_FAILURE;
    }
    if (xyce_simulateUntil(&xyce, window_end, &actual_time) != 1) {
      std::cerr << "xyce_pll_analog_dco_mixed_signal_smoke=fail error=\"simulateUntil failed\"\n";
      xyce_close(&xyce);
      return EXIT_FAILURE;
    }

    const std::vector<StatePoint> up = get_adc_points(&xyce, "UP_ADC");
    const std::vector<StatePoint> dn = get_adc_points(&xyce, "DN_ADC");
    if (up.empty() || dn.empty()) {
      std::cerr << "xyce_pll_analog_dco_mixed_signal_smoke=fail error=\"missing UP/DN ADC states\"\n";
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

    std::cout << cycle << ',' << window_start * 1.0e9 << ','
              << window_end * 1.0e9 << ',' << up_time * 1.0e12 << ','
              << dn_time * 1.0e12 << ',' << decision_name(decision) << ','
              << dlf.dco_code << ',' << dlf.code10 << '\n';
  }

  double measured_mhz = 0.0;
  int pllout_rises = 0;
  double measure_start_s = actual_time;
  double measure_end_s = actual_time;
  if (args.measure_cycles > 0) {
    if (!update_dac(&xyce, code_dac, code_points(actual_time, dlf.dco_code))) {
      std::cerr << "xyce_pll_analog_dco_mixed_signal_smoke=fail error=\"failed to update final DCO code DAC\"\n";
      xyce_close(&xyce);
      return EXIT_FAILURE;
    }
    measure_start_s = actual_time + args.measure_settle_ns * 1.0e-9;
    measure_end_s = actual_time + static_cast<double>(args.measure_cycles) * tref;
    if (measure_end_s <= measure_start_s) {
      std::cerr << "xyce_pll_analog_dco_mixed_signal_smoke=fail error=\"invalid measurement window\"\n";
      xyce_close(&xyce);
      return EXIT_FAILURE;
    }
    if (xyce_simulateUntil(&xyce, measure_end_s, &actual_time) != 1) {
      std::cerr << "xyce_pll_analog_dco_mixed_signal_smoke=fail error=\"measurement simulateUntil failed\"\n";
      xyce_close(&xyce);
      return EXIT_FAILURE;
    }

    const std::vector<StatePoint> pllout = get_adc_points(&xyce, "PLLOUT_ADC");
    if (pllout.empty()) {
      std::cerr << "xyce_pll_analog_dco_mixed_signal_smoke=fail error=\"missing PLLOUT ADC states\"\n";
      xyce_close(&xyce);
      return EXIT_FAILURE;
    }
    const std::vector<double> rises =
        rising_edges_in_window(pllout, measure_start_s, measure_end_s);
    pllout_rises = static_cast<int>(rises.size());
    measured_mhz = frequency_mhz_from_edges(rises);
    std::cout << "measure,start_ns,end_ns,pllout_rises,measured_mhz,target_mhz,freq_abs_error_mhz\n";
    std::cout << "measure," << measure_start_s * 1.0e9 << ','
              << measure_end_s * 1.0e9 << ',' << pllout_rises << ','
              << measured_mhz << ',' << args.target_mhz << ','
              << std::abs(measured_mhz - args.target_mhz) << '\n';
  }

  xyce_close(&xyce);

  const int final_code = dlf.dco_code;
  const bool moved =
      (expected_dir > 0) ? (final_code >= start_code + args.min_motion)
                         : (final_code <= start_code - args.min_motion);
  const bool improved =
      min_abs_error < std::abs(start_code - args.target_code);
  const bool close_enough = std::abs(final_code - args.target_code) <= args.tol_code;
  const bool has_expected_decision = expected_decisions > 0;
  const bool freq_checked = args.measure_cycles > 0;
  const bool has_frequency = !freq_checked || pllout_rises >= args.min_pllout_rises;
  const bool freq_close =
      !freq_checked || std::abs(measured_mhz - args.target_mhz) <= args.freq_tol_mhz;
  const bool pass =
      moved && improved && close_enough && has_expected_decision &&
      has_frequency && freq_close;

  std::cout << "xyce_pll_analog_dco_mixed_signal_smoke="
            << (pass ? "pass" : "fail") << " expect=" << args.expect
            << " start_code=" << start_code << " final_code=" << final_code
            << " target_code=" << args.target_code
            << " min_abs_error=" << min_abs_error
            << " final_abs_error=" << std::abs(final_code - args.target_code)
            << " tol_code=" << args.tol_code
            << " expected_decisions=" << expected_decisions
            << " measured_mhz=" << measured_mhz
            << " target_mhz=" << args.target_mhz
            << " freq_abs_error_mhz="
            << std::abs(measured_mhz - args.target_mhz)
            << " freq_tol_mhz=" << args.freq_tol_mhz
            << " pllout_rises=" << pllout_rises << '\n';

  return pass ? EXIT_SUCCESS : EXIT_FAILURE;
}
