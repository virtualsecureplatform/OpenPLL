cmake_minimum_required(VERSION 3.16)
project(OpenPLLBoundedReuseProbe LANGUAGES CXX)
find_package(Trilinos REQUIRED)
add_executable(native_KLS_rhs_probe main.cpp)
target_compile_features(native_KLS_rhs_probe PRIVATE cxx_std_17)
target_include_directories(native_KLS_rhs_probe PRIVATE ${Trilinos_INCLUDE_DIRS} ${Trilinos_TPL_INCLUDE_DIRS})
target_link_directories(native_KLS_rhs_probe PRIVATE ${Trilinos_LIBRARY_DIRS} ${Trilinos_TPL_LIBRARY_DIRS})
target_link_libraries(native_KLS_rhs_probe PRIVATE ${Trilinos_LIBRARIES} ${Trilinos_TPL_LIBRARIES})
target_include_directories(native_KLS_rhs_probe PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/../native_wire_preconditioner)

set(KLS_ROOT /tmp/openpll-xyce-kls-20261022-001)
target_include_directories(native_KLS_rhs_probe PRIVATE ${KLS_ROOT}/KLS/include)
target_link_libraries(native_KLS_rhs_probe PRIVATE
 ${KLS_ROOT}/build/KLS/libkls.a ${KLS_ROOT}/build/KLS/libkls_suitesparse.a
 ${KLS_ROOT}/build/KLS/libkls_metis.a ${KLS_ROOT}/build/KLS/libkls_gklib.a
 ${KLS_ROOT}/build/lib/libscotch.a ${KLS_ROOT}/build/lib/libscotcherr.a
 ${KLS_ROOT}/build/KLS/libkls_spral_scaling.a gfortran quadmath gomp)
