#include <N_CIR_XyceCInterface.h>

#include <algorithm>
#include <array>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <string>
#include <vector>

namespace {

std::vector<char> mutable_string(const std::string &value) {
  std::vector<char> data(value.begin(), value.end());
  data.push_back('\0');
  return data;
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
  } else {
    if (xyce_getDeviceNames(xyce, kind_name.data(), &count, ptrs.data()) != 1) {
      return {};
    }
  }

  std::vector<std::string> names;
  names.reserve(static_cast<size_t>(count));
  for (int index = 0; index < count; ++index) {
    names.emplace_back(ptrs[static_cast<size_t>(index)]);
  }
  return names;
}

bool adc_states_include_low_and_high(void **xyce) {
  constexpr int max_adcs = 8;
  constexpr int max_name = 256;
  constexpr int max_points = 128;

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
    std::cerr << "failed to retrieve ADC state pairs\n";
    return false;
  }

  bool saw_low = false;
  bool saw_high = false;
  for (int adc = 0; adc < adc_count; ++adc) {
    std::cout << "ADC " << names[static_cast<size_t>(adc)].data() << " states:";
    for (int point = 0; point < point_counts[static_cast<size_t>(adc)]; ++point) {
      const int state =
          states[static_cast<size_t>(adc)][static_cast<size_t>(point)];
      const double time =
          times[static_cast<size_t>(adc)][static_cast<size_t>(point)];
      std::cout << " (" << time << "s," << state << ")";
      saw_low = saw_low || state == 0;
      saw_high = saw_high || state == 1;
    }
    std::cout << "\n";
  }
  return saw_low && saw_high;
}

}  // namespace

int main(int argc, char **argv) {
  if (argc != 2) {
    std::cerr << "usage: xyce_cinterface_smoke <deck.cir>\n";
    return EXIT_FAILURE;
  }

  void *xyce = nullptr;
  xyce_open(&xyce);
  if (xyce == nullptr) {
    std::cerr << "xyce_open returned null\n";
    return EXIT_FAILURE;
  }

  std::vector<char> program_name = mutable_string("xyce_cinterface_smoke");
  std::vector<char> deck_name = mutable_string(argv[1]);
  std::array<char *, 3> xyce_argv = {program_name.data(), deck_name.data(), nullptr};
  if (xyce_initialize(&xyce, 2, xyce_argv.data()) !=
      1) {
    std::cerr << "xyce_initialize failed for " << argv[1] << "\n";
    xyce_close(&xyce);
    return EXIT_FAILURE;
  }

  std::vector<std::string> dac_names = get_device_names(&xyce, "YDAC");
  if (dac_names.empty()) {
    std::cerr << "deck has no YDAC devices\n";
    xyce_close(&xyce);
    return EXIT_FAILURE;
  }
  std::cout << "YDAC device: " << dac_names.front() << "\n";

  double actual_time = 0.0;
  if (xyce_simulateUntil(&xyce, 1.0e-12, &actual_time) != 1) {
    std::cerr << "initial simulateUntil failed\n";
    xyce_close(&xyce);
    return EXIT_FAILURE;
  }

  std::array<double, 7> times = {0.0, 2.0e-9, 3.0e-9, 8.0e-9,
                                 9.0e-9, 14.0e-9, 15.0e-9};
  std::array<double, 7> volts = {0.0, 0.0, 1.8, 1.8, 0.0, 0.0, 1.8};
  std::vector<char> dac_name = mutable_string(dac_names.front());
  if (xyce_updateTimeVoltagePairs(&xyce, dac_name.data(),
                                  static_cast<int>(times.size()), times.data(),
                                  volts.data()) != 1) {
    std::cerr << "xyce_updateTimeVoltagePairs failed\n";
    xyce_close(&xyce);
    return EXIT_FAILURE;
  }

  if (xyce_simulateUntil(&xyce, 16.0e-9, &actual_time) != 1) {
    std::cerr << "second simulateUntil failed\n";
    xyce_close(&xyce);
    return EXIT_FAILURE;
  }
  std::cout << "simulated_until_s=" << actual_time << "\n";

  const bool saw_expected_states = adc_states_include_low_and_high(&xyce);
  xyce_close(&xyce);
  if (!saw_expected_states) {
    std::cerr << "ADC did not report both low and high states\n";
    return EXIT_FAILURE;
  }
  std::cout << "xyce_cinterface_smoke=pass\n";
  return EXIT_SUCCESS;
}
