# Host tier: pure cores built with the system compiler, no ESP-IDF.
#   cmake -S tests/host -B build/host -G Ninja && cmake --build build/host \
#     && ctest --test-dir build/host --output-on-failure
cmake_minimum_required(VERSION 3.22)
project(gplug_mini_host C)

set(CMAKE_C_STANDARD 11)
add_compile_options(-Wall -Wextra -Werror)
enable_testing()

# Proves the tier itself builds and runs. Product tests are added by /build,
# one executable per component, each linked against that component's pure core.
add_executable(test_tier test_tier.c)
add_test(NAME tier_runs COMMAND test_tier)
