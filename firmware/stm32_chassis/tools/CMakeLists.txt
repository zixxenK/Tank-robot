cmake_minimum_required(VERSION 3.16)
project(protocol_gateway_tools C)

add_executable(test_parser
  test_parser.c
  ../Core/Src/protocol_gateway.c
  ../Core/Src/protocol_def.c
)

target_include_directories(test_parser PRIVATE
  ../Core/Inc
)

target_compile_options(test_parser PRIVATE
  $<$<C_COMPILER_ID:MSVC>:/W4>
  $<$<NOT:$<C_COMPILER_ID:MSVC>>:-Wall>
  $<$<NOT:$<C_COMPILER_ID:MSVC>>:-Wextra>
)
