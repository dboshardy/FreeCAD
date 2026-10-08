# SPDX-License-Identifier: LGPL-2.1-or-later
# FORK: standalone build of the hotkey engine tests (no FreeCAD/Qt needed), used by
# the "hotkeys" job in .github/workflows/fork_checks.yml. The same test file is
# also part of Gui_tests_run in the full build (tests/src/Gui/CMakeLists.txt).

cmake_minimum_required(VERSION 3.16)
project(HotkeyEngineTests CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(GTest REQUIRED)
include(GoogleTest)
enable_testing()

add_executable(HotkeyEngineTest HotkeyEngineTest.cpp)
target_include_directories(HotkeyEngineTest PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/../../../../src)
target_link_libraries(HotkeyEngineTest PRIVATE GTest::gtest_main)
gtest_discover_tests(HotkeyEngineTest)
