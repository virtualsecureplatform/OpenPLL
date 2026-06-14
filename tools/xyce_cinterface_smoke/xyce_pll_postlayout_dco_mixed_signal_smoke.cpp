#include <N_CIR_MixedSignalSimulator.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <cctype>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <map>
#include <string>
#include <utility>
#include <vector>

namespace {

constexpr double kVdd = 1.8;
constexpr double kEdge = 20.0e-12;
constexpr double kPulseWidth = 2.0e-9;
constexpr double kDecisionThreshold = 40.0e-12;
constexpr double kInitialDacSeedTime = 20.0e-12;

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

using XyceSimulator = Xyce::Circuit::MixedSignalSimulator;

std::map<std::string, std::vector<std::pair<double, double>> *>
pointer_map(std::map<std::string, std::vector<std::pair<double, double>>> &data) {
  std::map<std::string, std::vector<std::pair<double, double>> *> out;
  for (auto &[name, points] : data) {
    out[name] = &points;
  }
  return out;
}

std::vector<std::string> get_dac_names(XyceSimulator &xyce) {
  std::vector<std::string> names;
  xyce.getDACDeviceNames(names);
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

bool update_dac(XyceSimulator &xyce, const std::string &name,
                const std::vector<std::pair<double, double>> &points) {
  std::map<std::string, std::vector<std::pair<double, double>>> storage;
  storage[name] = points;
  std::map<std::string, std::vector<std::pair<double, double>> *> updates =
      pointer_map(storage);
  return xyce.updateTimeVoltagePairs(updates);
}

bool update_dacs(
    XyceSimulator &xyce,
    std::map<std::string, std::vector<std::pair<double, double>>> &storage) {
  std::map<std::string, std::vector<std::pair<double, double>> *> updates =
      pointer_map(storage);
  return xyce.updateTimeVoltagePairs(updates);
}

std::map<std::string, std::vector<StatePoint>> get_all_adc_points(
    XyceSimulator &xyce) {
  std::map<std::string, std::vector<std::pair<double, int>>> raw;
  if (!xyce.getTimeStatePairs(raw)) {
    return {};
  }

  std::map<std::string, std::vector<StatePoint>> out;
  for (auto &[name, points] : raw) {
    std::vector<StatePoint> states;
    states.reserve(points.size());
    for (const auto &[time, state] : points) {
      states.push_back({time, state});
    }
    std::sort(states.begin(), states.end(),
              [](const StatePoint &lhs, const StatePoint &rhs) {
                return lhs.time_s < rhs.time_s;
              });
    out[name] = std::move(states);
  }
  return out;
}

std::vector<StatePoint> find_adc_points(
    const std::map<std::string, std::vector<StatePoint>> &points,
    const std::string &token) {
  const std::string token_upper = upper(token);
  for (const auto &[name, states] : points) {
    if (upper(name).find(token_upper) != std::string::npos) {
      return states;
    }
  }
  return {};
}

std::vector<StatePoint> get_adc_points(XyceSimulator &xyce,
                                       const std::string &token) {
  const std::map<std::string, std::vector<StatePoint>> points =
      get_all_adc_points(xyce);
  if (points.empty()) {
    return {};
  }
  return find_adc_points(points, token);
}

using AdcHistory = std::map<std::string, std::vector<StatePoint>>;

int logic_state(double voltage) {
  return (voltage >= (kVdd * 0.5)) ? 1 : 0;
}

void append_adc_updates(
    AdcHistory &history,
    const std::map<std::string, std::vector<std::pair<double, double>>>
        &updates) {
  for (const auto &[name, points] : updates) {
    std::vector<StatePoint> &states = history[name];
    states.reserve(states.size() + points.size());
    for (const auto &[time_s, voltage] : points) {
      states.push_back({time_s, logic_state(voltage)});
    }
  }
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

std::vector<std::pair<double, double>> code_points(double now_s, int code) {
  const double volt =
      kVdd * static_cast<double>(std::clamp(code, 0, 255)) / 255.0;
  return {{now_s, volt}, {now_s + 1.0e-12, volt}};
}

double therm_voltage(int index, int code) {
  return (index < std::clamp(code, 0, 255)) ? 0.0 : kVdd;
}

std::vector<std::string> find_therm_dacs(const std::vector<std::string> &names) {
  std::vector<std::string> therm(255);
  for (int index = 0; index < 255; ++index) {
    const std::string token = "THERM_DRIVER_" +
                              (index < 10 ? std::string("00") :
                               index < 100 ? std::string("0") : std::string()) +
                              std::to_string(index);
    therm[static_cast<size_t>(index)] = find_device(names, token);
    if (therm[static_cast<size_t>(index)].empty()) {
      return {};
    }
  }
  return therm;
}

bool update_code(XyceSimulator &xyce, const std::string &code_dac,
                 const std::vector<std::string> &therm_dacs, double now_s,
                 int code) {
  std::map<std::string, std::vector<std::pair<double, double>>> storage;
  storage[code_dac] = code_points(now_s, code);
  for (int index = 0; index < 255; ++index) {
    const double volt = therm_voltage(index, code);
    storage[therm_dacs[static_cast<size_t>(index)]] = {
        {now_s, volt}, {now_s + 1.0e-12, volt}};
  }
  return update_dacs(xyce, storage);
}

std::vector<std::pair<double, double>> low_points(double now_s) {
  return {{now_s, 0.0}, {now_s + 1.0e-12, 0.0}};
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

[[noreturn]] void usage(const char *name) {
  std::cerr
      << "usage: " << name
      << " DECK [--init-code N] [--target-code N] [--cycles N]\n"
      << "       [--ki N] [--kp N] [--frac N] [--ndiv N]\n"
      << "       [--ref-mhz F] [--expect increase|decrease]\n"
      << "       [--min-motion N] [--tol-code N] [--target-mhz F]\n"
      << "       [--freq-tol-mhz F] [--measure-cycles N]\n"
      << "       [--measure-settle-ns NS] [--min-pllout-rises N]\n"
      << "       [--start-ns NS] [--cosim-step-ns NS]\n"
      << "       [--divider-latency-ps PS] [--prop-rail-guard]\n"
      << "       [--initial-divider-count N] [--no-warmup-divider]\n"
      << "       [--debug-nodes]\n";
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
  int target_code = 190;
  int cycles = 24;
  int ki = 128;
  int kp = 8;
  int frac = 2;
  int ndiv = 8;
  double ref_mhz = 25.0;
  std::string expect = "increase";
  int min_motion = 20;
  int tol_code = 10;
  int measure_cycles = 2;
  int min_pllout_rises = 5;
  double target_mhz = 200.0;
  double freq_tol_mhz = 3.0;
  double measure_settle_ns = 1.0;
  double start_ns = 20.0;
  double cosim_step_ns = 0.25;
  double divider_latency_ps = 50.0;
  int initial_divider_count = 0;
  bool prop_rail_guard = false;
  bool warmup_divider = true;
  bool debug_nodes = false;
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
    } else if (opt == "--cosim-step-ns") {
      args.cosim_step_ns = parse_double_arg(argc, argv, index);
    } else if (opt == "--divider-latency-ps") {
      args.divider_latency_ps = parse_double_arg(argc, argv, index);
    } else if (opt == "--initial-divider-count") {
      args.initial_divider_count = parse_int_arg(argc, argv, index);
    } else if (opt == "--prop-rail-guard") {
      args.prop_rail_guard = true;
    } else if (opt == "--no-warmup-divider") {
      args.warmup_divider = false;
    } else if (opt == "--debug-nodes") {
      args.debug_nodes = true;
    } else {
      usage(argv[0]);
    }
  }
  if (args.init_code < 0 || args.init_code > 255 || args.target_code < 0 ||
      args.target_code > 255 || args.cycles <= 0 || args.ki < 0 ||
      args.kp < 0 || args.frac < 0 || args.frac > 20 || args.ndiv <= 0 ||
      args.ref_mhz <= 0.0 || args.measure_cycles < 0 ||
      args.min_pllout_rises < 2 || args.target_mhz <= 0.0 ||
      args.freq_tol_mhz <= 0.0 || args.measure_settle_ns < 0.0 ||
      args.start_ns < 0.0 || args.cosim_step_ns <= 0.0 ||
      args.divider_latency_ps < 0.0 || args.initial_divider_count < 0 ||
      args.initial_divider_count >= args.ndiv ||
      (args.expect != "increase" && args.expect != "decrease")) {
    usage(argv[0]);
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
    const int64_t integ_code =
        std::clamp<int64_t>(acc >> cfg.frac, 0, max_code10);

    const bool inc = decision > 0;
    const bool dec = decision < 0;
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
      return;
    }

    acc = std::clamp<int64_t>(acc + static_cast<int64_t>(dir) * cfg.ki, 0,
                              max_acc);
    const int64_t prop_acc = std::clamp<int64_t>(
        acc + static_cast<int64_t>(dir) * kp_acc, 0, max_acc);
    code10 = static_cast<int>(prop_acc >> cfg.frac);
    dco_code = std::clamp(code10 >> 2, 0, 255);
  }

  const Args &cfg;
  int64_t acc;
  int code10;
  int dco_code;
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

struct DividerState {
  int count = 0;
  double last_edge_s = -1.0;
};

bool step_to(XyceSimulator &xyce, double end_s, double max_step_s,
             AdcHistory *adc_history = nullptr) {
  constexpr double kTimeEps = 1.0e-15;
  int stagnant_steps = 0;
  while (xyce.getTime() + kTimeEps < end_s) {
    const double before = xyce.getTime();
    double time_step = 0.0;
    std::map<std::string, std::vector<std::pair<double, double>>> tv_pairs;
    const double requested_step = std::min(max_step_s, end_s - before);
    if (!xyce.provisionalStep(requested_step, time_step, tv_pairs)) {
      return false;
    }
    xyce.acceptProvisionalStep();
    if (adc_history != nullptr) {
      append_adc_updates(*adc_history, tv_pairs);
    }
    const double after = xyce.getTime();
    if (after <= before + 1.0e-18) {
      ++stagnant_steps;
      if (stagnant_steps > 64) {
        return false;
      }
    } else {
      stagnant_steps = 0;
    }
  }
  return true;
}

bool advance_with_divider(XyceSimulator &xyce, const Args &args,
                          const std::string &div_dac, DividerState &divider,
                          AdcHistory &adc_history, double end_s) {
  const double step_s = args.cosim_step_ns * 1.0e-9;
  const double latency_s = args.divider_latency_ps * 1.0e-12;
  constexpr double kTimeEps = 1.0e-15;
  int stagnant_steps = 0;
  while (xyce.getTime() + kTimeEps < end_s) {
    const double before = xyce.getTime();
    const double next_s = std::min(before + step_s, end_s);
    double time_step = 0.0;
    std::map<std::string, std::vector<std::pair<double, double>>> tv_pairs;
    if (!xyce.provisionalStep(std::max(next_s - before, 1.0e-15), time_step,
                              tv_pairs)) {
      return false;
    }
    xyce.acceptProvisionalStep();
    append_adc_updates(adc_history, tv_pairs);
    const double actual_time = xyce.getTime();
    if (actual_time <= before + 1.0e-18) {
      ++stagnant_steps;
      if (stagnant_steps > 64) {
        return false;
      }
    } else {
      stagnant_steps = 0;
    }

    const std::vector<StatePoint> pllout =
        find_adc_points(adc_history, "PLLOUT_ADC");
    const std::vector<double> edges =
        rising_edges_in_window(pllout, divider.last_edge_s + 1.0e-15,
                               actual_time + 1.0e-15);
    for (double edge_s : edges) {
      if (edge_s <= divider.last_edge_s + 1.0e-15) {
        continue;
      }
      divider.last_edge_s = edge_s;
      ++divider.count;
      if (divider.count >= args.ndiv) {
        divider.count = 0;
        const double rise_s = actual_time + latency_s;
        if (!update_dac(xyce, div_dac, pulse_points(actual_time, rise_s))) {
          return false;
        }
      }
    }
  }
  return true;
}

bool get_node_voltage(XyceSimulator &xyce, const std::string &node,
                      double &value) {
  return xyce.getCircuitValue("V(" + node + ")", value);
}

void dump_debug_nodes(XyceSimulator &xyce, const std::string &label) {
  const std::array<const char *, 13> nodes = {
      "CODE",          "DCO_THERM[0]",   "DCO_THERM[183]",
      "DCO_THERM[184]", "DCO_THERM[191]", "DCO_THERM[192]",
      "DCO_THERM[254]", "RESET_N",        "CLKDIVR",
      "PLLOUT",        "REF",            "BBPD[0]",
      "BBPD[1]"};
  std::cerr << "debug_nodes,label=" << label << ",time_ns="
            << std::fixed << std::setprecision(6) << xyce.getTime() * 1.0e9
            << '\n';
  for (const char *node : nodes) {
    double value = 0.0;
    const bool ok = get_node_voltage(xyce, node, value);
    std::cerr << "debug_node," << label << ',' << node << ','
              << (ok ? "ok" : "missing") << ',';
    if (ok) {
      std::cerr << std::setprecision(9) << value;
    }
    std::cerr << '\n';
  }
}

void dump_adc_summary(const AdcHistory &adc_history,
                      const std::string &label) {
  std::cerr << "debug_adc,label=" << label << ",maps=" << adc_history.size()
            << '\n';
  for (const auto &[name, points] : adc_history) {
    std::cerr << "debug_adc_map," << label << ',' << name
              << ",points=" << points.size();
    if (!points.empty()) {
      std::cerr << ",last_time_ns=" << std::fixed << std::setprecision(6)
                << points.back().time_s * 1.0e9
                << ",last_state=" << points.back().state;
    }
    std::cerr << '\n';
  }
}

}  // namespace

int main(int argc, char **argv) {
  const Args args = parse_args(argc, argv);
  const int expected_dir = (args.expect == "increase") ? 1 : -1;

  XyceSimulator xyce;
  std::vector<char> program_name =
      mutable_string("xyce_pll_postlayout_dco_mixed_signal_smoke");
  std::vector<char> deck_name = mutable_string(args.deck);
  std::array<char *, 3> xyce_argv = {program_name.data(), deck_name.data(),
                                     nullptr};
  if (xyce.initialize(2, xyce_argv.data()) !=
      Xyce::Circuit::Simulator::SUCCESS) {
    std::cerr << "xyce_pll_postlayout_dco_mixed_signal_smoke=fail error=\"xyce_initialize failed\"\n";
    return EXIT_FAILURE;
  }

  const std::vector<std::string> dac_names = get_dac_names(xyce);
  const std::string code_dac = find_device(dac_names, "CODE");
  const std::string div_dac = find_device(dac_names, "DIV");
  const std::vector<std::string> therm_dacs = find_therm_dacs(dac_names);
  if (code_dac.empty() || div_dac.empty() || therm_dacs.empty()) {
    std::cerr << "xyce_pll_postlayout_dco_mixed_signal_smoke=fail error=\"missing CODE/DIV/THERM YDAC\"\n";
    xyce.finalize();
    return EXIT_FAILURE;
  }

  DlfModel dlf(args);
  if (!update_code(xyce, code_dac, therm_dacs, 0.0, dlf.dco_code) ||
      !update_dac(xyce, div_dac, low_points(0.0))) {
    std::cerr << "xyce_pll_postlayout_dco_mixed_signal_smoke=fail error=\"failed to seed initial DACs\"\n";
    xyce.finalize();
    return EXIT_FAILURE;
  }

  AdcHistory adc_history;
  double dcop_step = 0.0;
  std::map<std::string, std::vector<std::pair<double, double>>> dcop_pairs;
  if (!xyce.provisionalStep(kInitialDacSeedTime, dcop_step, dcop_pairs)) {
    std::cerr << "xyce_pll_postlayout_dco_mixed_signal_smoke=fail error=\"initial DCOP provisionalStep failed\"\n";
    xyce.finalize();
    return EXIT_FAILURE;
  }
  xyce.acceptProvisionalStep();
  append_adc_updates(adc_history, dcop_pairs);
  if (!step_to(xyce, kInitialDacSeedTime, kInitialDacSeedTime, &adc_history)) {
    std::cerr << "xyce_pll_postlayout_dco_mixed_signal_smoke=fail error=\"initial DAC-seed transient step failed\"\n";
    xyce.finalize();
    return EXIT_FAILURE;
  }
  if (args.debug_nodes) {
    dump_debug_nodes(xyce, "after_dcop");
    dump_adc_summary(adc_history, "after_dcop");
  }
  const double seed_time_s = xyce.getTime();
  if (!update_code(xyce, code_dac, therm_dacs, seed_time_s, dlf.dco_code) ||
      !update_dac(xyce, div_dac, low_points(seed_time_s))) {
    std::cerr << "xyce_pll_postlayout_dco_mixed_signal_smoke=fail error=\"failed to seed DACs\"\n";
    xyce.finalize();
    return EXIT_FAILURE;
  }
  if (args.debug_nodes) {
    dump_debug_nodes(xyce, "after_seed_update");
  }

  DividerState divider;
  divider.count = args.initial_divider_count;
  if (args.warmup_divider) {
    if (!advance_with_divider(xyce, args, div_dac, divider,
                              adc_history, args.start_ns * 1.0e-9)) {
      std::cerr << "xyce_pll_postlayout_dco_mixed_signal_smoke=fail error=\"warmup simulateUntil/divider update failed\"\n";
      xyce.finalize();
      return EXIT_FAILURE;
    }
  } else if (!step_to(xyce, args.start_ns * 1.0e-9,
                      args.cosim_step_ns * 1.0e-9, &adc_history)) {
    std::cerr << "xyce_pll_postlayout_dco_mixed_signal_smoke=fail error=\"initial simulateUntil failed\"\n";
    xyce.finalize();
    return EXIT_FAILURE;
  } else {
    divider.last_edge_s = xyce.getTime();
  }
  if (args.debug_nodes) {
    dump_debug_nodes(xyce, "after_start");
    dump_adc_summary(adc_history, "after_start");
  }

  const double tref = 1.0 / (args.ref_mhz * 1.0e6);
  const double start_s = xyce.getTime();
  const int start_code = dlf.dco_code;
  int min_abs_error = std::abs(start_code - args.target_code);
  int expected_decisions = 0;

  std::cout << std::fixed << std::setprecision(3);
  std::cout << "cycle,start_ns,end_ns,up_ps,dn_ps,decision,dco_code,code10\n"
            << std::flush;

  for (int cycle = 0; cycle < args.cycles; ++cycle) {
    const double window_start = start_s + static_cast<double>(cycle) * tref;
    const double window_end = start_s + static_cast<double>(cycle + 1) * tref;

    if (!update_code(xyce, code_dac, therm_dacs,
                     std::max(window_start, xyce.getTime()),
                     dlf.dco_code)) {
      std::cerr << "xyce_pll_postlayout_dco_mixed_signal_smoke=fail error=\"failed to update DCO code DAC\"\n";
      xyce.finalize();
      return EXIT_FAILURE;
    }
    if (!advance_with_divider(xyce, args, div_dac, divider, adc_history,
                              window_end)) {
      std::cerr << "xyce_pll_postlayout_dco_mixed_signal_smoke=fail error=\"simulateUntil/divider update failed\"\n";
      xyce.finalize();
      return EXIT_FAILURE;
    }

    const std::vector<StatePoint> up = find_adc_points(adc_history, "UP_ADC");
    const std::vector<StatePoint> dn = find_adc_points(adc_history, "DN_ADC");
    if (up.empty() || dn.empty()) {
      std::cerr << "xyce_pll_postlayout_dco_mixed_signal_smoke=fail error=\"missing UP/DN ADC states\"\n";
      xyce.finalize();
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
              << dlf.dco_code << ',' << dlf.code10 << '\n'
              << std::flush;
  }

  double measured_mhz = 0.0;
  int pllout_rises = 0;
  if (args.measure_cycles > 0) {
    const double loop_end_s = start_s + static_cast<double>(args.cycles) * tref;
    double measure_base_s = loop_end_s;
    if (dlf.dco_code != start_code) {
      if (!update_code(xyce, code_dac, therm_dacs,
                       std::max(loop_end_s, xyce.getTime()), dlf.dco_code)) {
        std::cerr << "xyce_pll_postlayout_dco_mixed_signal_smoke=fail error=\"failed to update final DCO code DAC\"\n";
        xyce.finalize();
        return EXIT_FAILURE;
      }
      measure_base_s = xyce.getTime();
    }
    const double measure_start_s =
        measure_base_s + args.measure_settle_ns * 1.0e-9;
    const double measure_end_s =
        measure_base_s + static_cast<double>(args.measure_cycles) * tref;
    if (measure_end_s <= measure_start_s) {
      std::cerr << "xyce_pll_postlayout_dco_mixed_signal_smoke=fail error=\"measurement window ends before settle time\"\n";
      xyce.finalize();
      return EXIT_FAILURE;
    }
    if (!step_to(xyce, measure_end_s, args.cosim_step_ns * 1.0e-9,
                 &adc_history)) {
      std::cerr << "xyce_pll_postlayout_dco_mixed_signal_smoke=fail error=\"measurement simulateUntil failed\"\n";
      xyce.finalize();
      return EXIT_FAILURE;
    }
    const std::vector<StatePoint> pllout =
        find_adc_points(adc_history, "PLLOUT_ADC");
    const std::vector<double> rises =
        rising_edges_in_window(pllout, measure_start_s, measure_end_s);
    pllout_rises = static_cast<int>(rises.size());
    measured_mhz = frequency_mhz_from_edges(rises);
    std::cout << "measure,start_ns,end_ns,pllout_rises,measured_mhz,target_mhz,freq_abs_error_mhz\n";
    std::cout << "measure," << measure_start_s * 1.0e9 << ','
              << measure_end_s * 1.0e9 << ',' << pllout_rises << ','
              << measured_mhz << ',' << args.target_mhz << ','
              << std::abs(measured_mhz - args.target_mhz) << '\n'
              << std::flush;
  }

  xyce.finalize();

  const int final_code = dlf.dco_code;
  const bool moved =
      (expected_dir > 0) ? (final_code >= start_code + args.min_motion)
                         : (final_code <= start_code - args.min_motion);
  const bool initially_close =
      std::abs(start_code - args.target_code) <= args.tol_code;
  const bool improved =
      initially_close || min_abs_error < std::abs(start_code - args.target_code);
  const bool close_enough =
      std::abs(final_code - args.target_code) <= args.tol_code;
  const bool has_expected_decision = expected_decisions > 0;
  const bool has_frequency =
      args.measure_cycles == 0 || pllout_rises >= args.min_pllout_rises;
  const bool freq_close =
      args.measure_cycles == 0 ||
      std::abs(measured_mhz - args.target_mhz) <= args.freq_tol_mhz;
  const bool pass = moved && improved && close_enough &&
                    has_expected_decision && has_frequency && freq_close;

  std::cout << "xyce_pll_postlayout_dco_mixed_signal_smoke="
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
