cmake_minimum_required(VERSION 3.20)

project(OpenPLLXyceCInterfaceSmoke LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

set(XYCE_INSTALL_DIR "/home/ubuntu/.local/xyce-mpi" CACHE PATH "Installed Xyce prefix")
set(XYCE_BUILD_DIR "/home/ubuntu/builds/xyce/xyce-mpi" CACHE PATH "Xyce build tree with xycecinterface target")

find_package(Xyce REQUIRED CONFIG PATHS "${XYCE_INSTALL_DIR}/lib/cmake/Xyce")

set(XYCE_CINTERFACE_LIB "${XYCE_BUILD_DIR}/utils/XyceCInterface/libxycecinterface.a")
if(NOT EXISTS "${XYCE_CINTERFACE_LIB}")
  message(FATAL_ERROR "Missing ${XYCE_CINTERFACE_LIB}; run cmake --build ${XYCE_BUILD_DIR} --target xycecinterface first")
endif()

set(XYCE_SOURCE_INCLUDE_DIRS
  "/home/ubuntu/sources/Xyce/src"
  "/home/ubuntu/sources/Xyce/src/CircuitPKG"
  "/home/ubuntu/sources/Xyce/src/AnalysisPKG"
  "/home/ubuntu/sources/Xyce/src/DeviceModelPKG/Core"
  "/home/ubuntu/sources/Xyce/src/DeviceModelPKG/OpenModels"
  "/home/ubuntu/sources/Xyce/src/ErrorHandlingPKG"
  "/home/ubuntu/sources/Xyce/src/IOInterfacePKG"
  "/home/ubuntu/sources/Xyce/src/LinearAlgebraServicesPKG"
  "/home/ubuntu/sources/Xyce/src/LoaderServicesPKG"
  "/home/ubuntu/sources/Xyce/src/NonlinearSolverPKG"
  "/home/ubuntu/sources/Xyce/src/ParallelDistPKG"
  "/home/ubuntu/sources/Xyce/src/TimeIntegrationPKG"
  "/home/ubuntu/sources/Xyce/src/TopoManagerPKG"
  "/home/ubuntu/sources/Xyce/src/UtilityPKG"
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
