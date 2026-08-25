cmake_minimum_required(VERSION 3.8)
project(terrain_adaptation)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)

ament_python_install_package(${PROJECT_NAME})

install(PROGRAMS
  scripts/terrain_classifier.py
  scripts/adaptive_controller.py
  DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY
  launch
  DESTINATION share/${PROJECT_NAME}
)

if(BUILD_TESTING)
  find_package(ament_cmake_gtest REQUIRED)
  find_package(ament_lint_auto REQUIRED)
  find_package(ament_lint_common REQUIRED)
  find_package(ament_cmake_pep257 REQUIRED)

  # The package uses Google-style Args/Returns sections.  Keep the remaining
  # pep257 checks active while excluding incompatible NumPy-section rules.
  set(AMENT_LINT_AUTO_EXCLUDE ament_cmake_pep257)
  ament_lint_auto_find_test_dependencies()
  ament_pep257(--add-ignore D204 D406 D407 D413)
endif()

ament_package()
