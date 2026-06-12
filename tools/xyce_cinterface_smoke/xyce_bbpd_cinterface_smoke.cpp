#include <N_CIR_XyceCInterface.h>

#include <algorithm>
#include <array>
#include <cctype>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <string>
#include <utility>
#include <vector>

namespace {

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
  } else if (xyce_getDeviceNames(xyce, kind_name.data(), &count, ptrs.data()) != 1) {
    return {};
  }

  std::vector<std::string> names;
  names.reserve(static_cast<size_t>(count));
  for (int index = 0; index < count; ++index) {
    names.emplace_back(ptrs[static_cast<size_t>(index)]);
  }
  return names;
}

std::string find_device(const std::vector<std::string> &names, const std::string &token) {
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
                                     static_cast<int>(points.size()), times.data(),
                                     volts.data()) == 1;
}

std::vector<StatePoint> get_adc_points(void **xyce, const std::string &token) {
  constexpr int max_adcs = 8;
  constexpr int max_name = 256;
  constexpr int max_points = 256;

  std::array<std::array<char, max_name>, max_adcs> names{};
  std::array<char *, max_adcs> name_ptrs{};
  for (int index = 0; index < max_adcs; ++index) {
    name_ptrs[static_cast<size_t>(index)] = names[static_cast<size_t>(index)].data();
  }

  std::array<int, max_adcs> point_counts{};
  std::array<std::array<double, max_points>, max_adcs> times{};
  std::array<std::array<int, max_points>, max_adcs> states{};
  std::array<double *, max_adcs> time_ptrs{};
  std::array<int *, max_adcs> state_ptrs{};
  for (int index = 0; index < max_adcs; ++index) {
    time_ptrs[static_cast<size_t>(index)] = times[static_cast<size_t>(index)].data();
    state_ptrs[static_cast<size_t>(index)] = states[static_cast<size_t>(index)].data();
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
    for (int point = 0; point < point_counts[static_cast<size_t>(adc)]; ++point) {
      points.push_back(
          {times[static_cast<size_t>(adc)][static_cast<size_t>(point)],
           states[static_cast<size_t>(adc)][static_cast<size_t>(point)]});
    }
    std::sort(points.begin(), points.end(),
              [](const StatePoint &lhs, const StatePoint &rhs) {
                return lhs.time_s < rhs.time_s;
              });
    std::cout << name << " states:";
    for (const StatePoint &point : points) {
      std::cout << " (" << point.time_s << "s," << point.state << ")";
    }
    std::cout << "\n";
    return points;
  }
  return {};
}

double high_time_in_window(std::vector<StatePoint> points, double start_s, double end_s) {
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

std::vector<std::pair<double, double>> pulse_points(
    const std::vector<std::pair<double, double>> &pulses) {
  constexpr double vdd = 1.8;
  constexpr double edge = 20.0e-12;
  std::vector<std::pair<double, double>> points{{0.0, 0.0}};
  for (const auto &[rise, fall] : pulses) {
    points.push_back({rise, 0.0});
    points.push_back({rise + edge, vdd});
    points.push_back({fall, vdd});
    points.push_back({fall + edge, 0.0});
  }
  return points;
}

}  // namespace

int main(int argc, char **argv) {
  if (argc != 2) {
    std::cerr << "usage: xyce_bbpd_cinterface_smoke <deck.cir>\n";
    return EXIT_FAILURE;
  }

  void *xyce = nullptr;
  xyce_open(&xyce);
  if (xyce == nullptr) {
    std::cerr << "xyce_open returned null\n";
    return EXIT_FAILURE;
  }

  std::vector<char> program_name = mutable_string("xyce_bbpd_cinterface_smoke");
  std::vector<char> deck_name = mutable_string(argv[1]);
  std::array<char *, 2> xyce_argv = {program_name.data(), deck_name.data()};
  if (xyce_initialize(&xyce, static_cast<int>(xyce_argv.size()), xyce_argv.data()) !=
      1) {
    std::cerr << "xyce_initialize failed for " << argv[1] << "\n";
    xyce_close(&xyce);
    return EXIT_FAILURE;
  }

  std::vector<std::string> dac_names = get_device_names(&xyce, "YDAC");
  const std::string ref_dac = find_device(dac_names, "REF");
  const std::string div_dac = find_device(dac_names, "DIV");
  if (ref_dac.empty() || div_dac.empty()) {
    std::cerr << "could not find REF and DIV YDAC devices\n";
    xyce_close(&xyce);
    return EXIT_FAILURE;
  }
  std::cout << "REF YDAC: " << ref_dac << "\n";
  std::cout << "DIV YDAC: " << div_dac << "\n";

  const auto seed_low = std::vector<std::pair<double, double>>{{0.0, 0.0}, {1.0e-12, 0.0}};
  if (!update_dac(&xyce, ref_dac, seed_low) || !update_dac(&xyce, div_dac, seed_low)) {
    std::cerr << "failed to seed REF/DIV DACs low\n";
    xyce_close(&xyce);
    return EXIT_FAILURE;
  }

  double actual_time = 0.0;
  if (xyce_simulateUntil(&xyce, 1.0e-12, &actual_time) != 1) {
    std::cerr << "initial simulateUntil failed\n";
    xyce_close(&xyce);
    return EXIT_FAILURE;
  }

  const auto ref_points = pulse_points({{5.0e-9, 7.0e-9}, {15.2e-9, 17.2e-9}});
  const auto div_points = pulse_points({{5.2e-9, 7.2e-9}, {15.0e-9, 17.0e-9}});
  if (!update_dac(&xyce, ref_dac, ref_points) ||
      !update_dac(&xyce, div_dac, div_points)) {
    std::cerr << "failed to update REF/DIV DAC waveforms\n";
    xyce_close(&xyce);
    return EXIT_FAILURE;
  }

  if (xyce_simulateUntil(&xyce, 23.0e-9, &actual_time) != 1) {
    std::cerr << "simulateUntil failed\n";
    xyce_close(&xyce);
    return EXIT_FAILURE;
  }
  std::cout << "simulated_until_s=" << actual_time << "\n";

  const std::vector<StatePoint> up = get_adc_points(&xyce, "UP_ADC");
  const std::vector<StatePoint> dn = get_adc_points(&xyce, "DN_ADC");
  xyce_close(&xyce);
  if (up.empty() || dn.empty()) {
    std::cerr << "missing UP/DN ADC state points\n";
    return EXIT_FAILURE;
  }

  const double up_ref_leads = high_time_in_window(up, 4.5e-9, 10.0e-9);
  const double dn_ref_leads = high_time_in_window(dn, 4.5e-9, 10.0e-9);
  const double up_div_leads = high_time_in_window(up, 14.5e-9, 20.0e-9);
  const double dn_div_leads = high_time_in_window(dn, 14.5e-9, 20.0e-9);

  std::cout << "ref_leads_up_high_s=" << up_ref_leads << "\n";
  std::cout << "ref_leads_dn_high_s=" << dn_ref_leads << "\n";
  std::cout << "div_leads_up_high_s=" << up_div_leads << "\n";
  std::cout << "div_leads_dn_high_s=" << dn_div_leads << "\n";

  constexpr double min_delta_s = 50.0e-12;
  if (up_ref_leads <= dn_ref_leads + min_delta_s) {
    std::cerr << "REF-leads event did not produce wider UP pulse\n";
    return EXIT_FAILURE;
  }
  if (dn_div_leads <= up_div_leads + min_delta_s) {
    std::cerr << "DIV-leads event did not produce wider DN pulse\n";
    return EXIT_FAILURE;
  }

  std::cout << "xyce_bbpd_cinterface_smoke=pass\n";
  return EXIT_SUCCESS;
}
