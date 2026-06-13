#include <N_CIR_MixedSignalSimulator.h>

#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <map>
#include <array>
#include <string>
#include <utility>
#include <vector>

namespace {

[[noreturn]] void usage(const char *name) {
  std::cerr << "usage: " << name
            << " DECK [--max-step-ns N] [--steps N]\n";
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
  double max_step_ns = 0.25;
  int steps = 12;
};

Args parse_args(int argc, char **argv) {
  if (argc < 2) {
    usage(argv[0]);
  }
  Args args;
  args.deck = argv[1];
  for (int index = 2; index < argc; ++index) {
    const std::string opt = argv[index];
    if (opt == "--max-step-ns") {
      args.max_step_ns = parse_double_arg(argc, argv, index);
    } else if (opt == "--steps") {
      args.steps = parse_int_arg(argc, argv, index);
    } else {
      usage(argv[0]);
    }
  }
  if (args.max_step_ns <= 0.0 || args.steps <= 0) {
    usage(argv[0]);
  }
  return args;
}

std::map<std::string, std::vector<std::pair<double, double>> *>
pointer_map(std::map<std::string, std::vector<std::pair<double, double>>> &data) {
  std::map<std::string, std::vector<std::pair<double, double>> *> out;
  for (auto &[name, points] : data) {
    out[name] = &points;
  }
  return out;
}

std::vector<char> mutable_string(const std::string &value) {
  std::vector<char> data(value.begin(), value.end());
  data.push_back('\0');
  return data;
}

}  // namespace

int main(int argc, char **argv) {
  const Args args = parse_args(argc, argv);

  Xyce::Circuit::MixedSignalSimulator xyce;
  std::vector<char> program_name = mutable_string("xyce_mixed_step_probe");
  std::vector<char> deck_name = mutable_string(args.deck);
  std::array<char *, 3> xyce_argv = {program_name.data(), deck_name.data(),
                                     nullptr};
  if (xyce.initialize(2, xyce_argv.data()) !=
      Xyce::Circuit::Simulator::SUCCESS) {
    std::cerr << "xyce_mixed_step_probe=fail error=\"initialize failed\"\n";
    return EXIT_FAILURE;
  }

  std::vector<std::string> dac_names;
  xyce.getDACDeviceNames(dac_names);

  std::map<std::string, std::vector<std::pair<double, double>>> seed_storage;
  for (const std::string &name : dac_names) {
    seed_storage[name] = {{0.0, 0.0}, {1.0e-12, 0.0}};
  }
  std::map<std::string, std::vector<std::pair<double, double>> *> seed =
      pointer_map(seed_storage);
  if (!seed.empty() && !xyce.updateTimeVoltagePairs(seed)) {
    std::cerr << "xyce_mixed_step_probe=fail error=\"initial DAC update failed\"\n";
    xyce.finalize();
    return EXIT_FAILURE;
  }

  const double max_step_s = args.max_step_ns * 1.0e-9;
  std::cout << std::scientific << std::setprecision(6);
  std::cout << "step,time_before_s,time_step_s,time_after_s,adc_maps\n";

  for (int step = 0; step < args.steps; ++step) {
    const double before = xyce.getTime();
    double time_step = 0.0;
    std::map<std::string, std::vector<std::pair<double, double>>> tv_pairs;
    if (!xyce.provisionalStep(max_step_s, time_step, tv_pairs)) {
      std::cerr << "xyce_mixed_step_probe=fail error=\"provisionalStep failed\" step="
                << step << "\n";
      xyce.finalize();
      return EXIT_FAILURE;
    }
    xyce.acceptProvisionalStep();
    std::map<std::string, std::vector<std::pair<double, int>>> state_pairs;
    xyce.getTimeStatePairs(state_pairs);
    std::cout << step << ',' << before << ',' << time_step << ','
              << xyce.getTime() << ',' << state_pairs.size() << '\n'
              << std::flush;
    if (xyce.simulationComplete()) {
      break;
    }
  }

  xyce.finalize();
  std::cout << "xyce_mixed_step_probe=pass final_time_s=" << xyce.getTime()
            << '\n';
  return EXIT_SUCCESS;
}
