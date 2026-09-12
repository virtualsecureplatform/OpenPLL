cmake_minimum_required(VERSION 3.20)

project(OpenPLLXyceCInterfaceSmoke LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

include(CTest)
if(BUILD_TESTING)
  add_executable(test_calibrated_dco test_calibrated_dco.cpp)
  add_test(NAME calibrated_dco_phase COMMAND test_calibrated_dco)
endif()

set(XYCE_INSTALL_DIR "/home/ubuntu/.local/xyce-mpi" CACHE PATH "Installed Xyce prefix")
set(XYCE_BUILD_DIR "/home/ubuntu/builds/xyce/xyce-mpi" CACHE PATH "Xyce build tree with xycecinterface target")

find_package(Xyce REQUIRED CONFIG PATHS "${XYCE_INSTALL_DIR}/lib/cmake/Xyce")

set(XYCE_EXTRA_LIBRARIES "" CACHE STRING "Additional libraries required by a custom static Xyce build")
if(XYCE_EXTRA_LIBRARIES)
  set_property(TARGET Xyce::XyceLib APPEND PROPERTY
    INTERFACE_LINK_LIBRARIES ${XYCE_EXTRA_LIBRARIES})
endif()

set(XYCE_CINTERFACE_LIB "${XYCE_BUILD_DIR}/utils/XyceCInterface/libxycecinterface.a")
if(NOT EXISTS "${XYCE_CINTERFACE_LIB}")
  message(FATAL_ERROR "Missing ${XYCE_CINTERFACE_LIB}; run cmake --build ${XYCE_BUILD_DIR} --target xycecinterface first")
endif()

set(XYCE_SOURCE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../../../Xyce" CACHE PATH "Xyce source tree for internal mixed-step API headers")

set(XYCE_SOURCE_INCLUDE_DIRS
  "${XYCE_SOURCE_DIR}/src"
  "${XYCE_SOURCE_DIR}/src/CircuitPKG"
  "${XYCE_SOURCE_DIR}/src/AnalysisPKG"
  "${XYCE_SOURCE_DIR}/src/DeviceModelPKG/Core"
  "${XYCE_SOURCE_DIR}/src/DeviceModelPKG/OpenModels"
  "${XYCE_SOURCE_DIR}/src/ErrorHandlingPKG"
  "${XYCE_SOURCE_DIR}/src/IOInterfacePKG"
  "${XYCE_SOURCE_DIR}/src/LinearAlgebraServicesPKG"
  "${XYCE_SOURCE_DIR}/src/LoaderServicesPKG"
  "${XYCE_SOURCE_DIR}/src/NonlinearSolverPKG"
  "${XYCE_SOURCE_DIR}/src/ParallelDistPKG"
  "${XYCE_SOURCE_DIR}/src/TimeIntegrationPKG"
  "${XYCE_SOURCE_DIR}/src/TopoManagerPKG"
  "${XYCE_SOURCE_DIR}/src/UtilityPKG"
)

add_executable(xyce_cinterface_smoke xyce_cinterface_smoke.cpp)
target_include_directories(xyce_cinterface_smoke PRIVATE "${XYCE_INSTALL_DIR}/include")
target_link_libraries(xyce_cinterface_smoke PRIVATE "${XYCE_CINTERFACE_LIB}" Xyce::XyceLib)

add_executable(xyce_bbpd_cinterface_smoke xyce_bbpd_cinterface_smoke.cpp)
target_include_directories(xyce_bbpd_cinterface_smoke PRIVATE "${XYCE_INSTALL_DIR}/include")
target_link_libraries(xyce_bbpd_cinterface_smoke PRIVATE "${XYCE_CINTERFACE_LIB}" Xyce::XyceLib)

add_executable(xyce_pll_mixed_signal_smoke xyce_pll_mixed_signal_smoke.cpp)
target_include_directories(xyce_pll_mixed_signal_smoke PRIVATE "${XYCE_INSTALL_DIR}/include")
target_link_libraries(xyce_pll_mixed_signal_smoke PRIVATE "${XYCE_CINTERFACE_LIB}" Xyce::XyceLib)

add_executable(xyce_pll_analog_dco_mixed_signal_smoke xyce_pll_analog_dco_mixed_signal_smoke.cpp)
target_include_directories(xyce_pll_analog_dco_mixed_signal_smoke PRIVATE "${XYCE_INSTALL_DIR}/include")
target_link_libraries(xyce_pll_analog_dco_mixed_signal_smoke PRIVATE "${XYCE_CINTERFACE_LIB}" Xyce::XyceLib)

add_executable(xyce_pll_postlayout_dco_mixed_signal_smoke xyce_pll_postlayout_dco_mixed_signal_smoke.cpp)
target_include_directories(xyce_pll_postlayout_dco_mixed_signal_smoke PRIVATE "${XYCE_INSTALL_DIR}/include" ${XYCE_SOURCE_INCLUDE_DIRS})
target_link_libraries(xyce_pll_postlayout_dco_mixed_signal_smoke PRIVATE Xyce::XyceLib)

add_executable(xyce_mixed_step_probe xyce_mixed_step_probe.cpp)
target_include_directories(
  xyce_mixed_step_probe
  PRIVATE
    "${XYCE_INSTALL_DIR}/include"
    ${XYCE_SOURCE_INCLUDE_DIRS}
)
target_link_libraries(xyce_mixed_step_probe PRIVATE Xyce::XyceLib)

# Optional production-RTL / extracted-BBPD diagnostic.
option(OPENPLL_RTL_COSIM "Build Verilator/Xyce RTL co-simulation" OFF)
if(OPENPLL_RTL_COSIM)
  find_package(verilator REQUIRED)
  set(PLL_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../..")
  add_executable(xyce_pll_rtl_cosim xyce_pll_rtl_cosim.cpp)
  target_include_directories(xyce_pll_rtl_cosim PRIVATE
    "${XYCE_INSTALL_DIR}/include" ${XYCE_SOURCE_INCLUDE_DIRS})
  target_link_libraries(xyce_pll_rtl_cosim PRIVATE Xyce::XyceLib)
  verilate(xyce_pll_rtl_cosim TOP_MODULE IntegerPLL_Cosim
    PREFIX VIntegerPLL_Cosim VERILATOR_ARGS -Wno-fatal
    SOURCES "${PLL_ROOT}/tb/IntegerPLL_Cosim.v"
    "${PLL_ROOT}/rtl/IntegerPLL_AcquiringCore.v"
    "${PLL_ROOT}/rtl/IntegerPLL_TuningHandoff.v"
    "${PLL_ROOT}/rtl/IntegerPLL_FrequencyAcquisition.v"
    "${PLL_ROOT}/rtl/IntegerPLL_25MHzModeController.v"
    "${PLL_ROOT}/rtl/IntegerPLL_25MHzModeConfig.v"
    "${PLL_ROOT}/rtl/IntegerPLL_DigitalCore.v"
    "${PLL_ROOT}/rtl/IntegerPLL_DLF.v"
    "${PLL_ROOT}/rtl/IntegerPLL_B2TH.v"
    "${PLL_ROOT}/rtl/IntegerPLL_MMD_Retimer.v"
    "${PLL_ROOT}/rtl/IntegerPLL_Divider.v")
endif()
