cmake_minimum_required(VERSION 3.18)
project(OpenPLLKLSCertificationComparison LANGUAGES CXX)
find_package(Trilinos REQUIRED)
set(KLS_ROOT /tmp/openpll-kls-certification-20261024-001)
foreach(kind rhs matrix)
 add_executable(compare_${kind} ${kind}.cpp)
 target_compile_features(compare_${kind} PRIVATE cxx_std_17)
 target_include_directories(compare_${kind} PRIVATE ${Trilinos_INCLUDE_DIRS} ${Trilinos_TPL_INCLUDE_DIRS} ${KLS_ROOT}/KLS/include)
 target_link_directories(compare_${kind} PRIVATE ${Trilinos_LIBRARY_DIRS} ${Trilinos_TPL_LIBRARY_DIRS})
 target_link_libraries(compare_${kind} PRIVATE ${Trilinos_LIBRARIES} ${Trilinos_TPL_LIBRARIES}
  ${KLS_ROOT}/build/libkls.a ${KLS_ROOT}/build/libkls_suitesparse.a
  ${KLS_ROOT}/build/libkls_metis.a ${KLS_ROOT}/build/libkls_gklib.a
  ${KLS_ROOT}/build/lib/libscotch.a ${KLS_ROOT}/build/lib/libscotcherr.a
  ${KLS_ROOT}/build/libkls_spral_scaling.a gfortran quadmath gomp)
endforeach()
