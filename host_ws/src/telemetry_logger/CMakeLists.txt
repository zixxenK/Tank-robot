cmake_minimum_required(VERSION 3.8)
project(telemetry_logger)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)

ament_python_install_package(${PROJECT_NAME})

install(PROGRAMS
  telemetry_logger/telemetry_recorder.py
  telemetry_logger/bag_parser.py
  telemetry_logger/feature_extractor.py
  DESTINATION lib/${PROJECT_NAME}
)

# This package currently has no launch/ or config/ directories.  Keep the
# executable install self-contained so colcon can build the whole workspace.

if(BUILD_TESTING)
  find_package(ament_cmake_gtest REQUIRED)
  find_package(ament_lint_auto REQUIRED)
  find_package(ament_lint_common REQUIRED)
  find_package(ament_cmake_pep257 REQUIRED)

  # The package uses Google-style Args/Returns sections.  Keep the remaining
  # pep257 checks active while excluding incompatible NumPy-section rules.
  set(AMENT_LINT_AUTO_EXCLUDE ament_cmake_pep257)
  ament_lint_auto_find_test_dependencies()
  ament_pep257(--add-ignore D204 D213 D401 D406 D407 D413)
endif()

ament_package()
