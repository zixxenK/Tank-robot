cmake_minimum_required(VERSION 3.8)
project(robot_bringup)

find_package(ament_cmake REQUIRED)

install(DIRECTORY launch DESTINATION share/${PROJECT_NAME})
install(DIRECTORY config DESTINATION share/${PROJECT_NAME} OPTIONAL)
install(DIRECTORY urdf   DESTINATION share/${PROJECT_NAME} OPTIONAL)

ament_package()
