cmake_minimum_required(VERSION 3.20)
project(fap_cpp_native VERSION 1.0.1 LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

option(FAP_NATIVE_BUILD_TESTS "Build FAP native tests" ON)
option(FAP_NATIVE_BUILD_CLI "Build FAP native CLI" ON)
option(FAP_NATIVE_BUILD_BENCHMARKS "Build FAP native microbenchmarks" OFF)

add_library(fap_native_core STATIC
    src/native_core.cpp
    src/c_api.cpp
)
target_include_directories(fap_native_core PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)
target_compile_features(fap_native_core PUBLIC cxx_std_20)

if(MSVC)
  target_compile_options(fap_native_core PRIVATE /W4 /permissive-)
else()
  target_compile_options(fap_native_core PRIVATE -Wall -Wextra -Wpedantic)
endif()

if(FAP_NATIVE_BUILD_CLI)
  add_executable(fap_native_cli src/main.cpp)
  target_link_libraries(fap_native_cli PRIVATE fap_native_core)
endif()

if(FAP_NATIVE_BUILD_BENCHMARKS)
  add_executable(fap_native_benchmark bench/benchmark_native.cpp)
  target_link_libraries(fap_native_benchmark PRIVATE fap_native_core)
endif()

if(FAP_NATIVE_BUILD_TESTS)
  enable_testing()
  add_executable(fap_native_tests tests/test_native_core.cpp)
  target_link_libraries(fap_native_tests PRIVATE fap_native_core)
  add_test(NAME fap_native_tests COMMAND fap_native_tests)
endif()
