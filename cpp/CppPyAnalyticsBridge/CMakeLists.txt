cmake_minimum_required(VERSION 3.20)
project(CppPyAnalyticsBridge LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_library(analytics_c SHARED
    cpp/src/analytics_c.cpp
)
target_include_directories(analytics_c PUBLIC cpp/include)
set_target_properties(analytics_c PROPERTIES PREFIX "" OUTPUT_NAME "analytics_c")

if(MSVC)
  target_compile_options(analytics_c PRIVATE /W4 /EHsc)
else()
  target_compile_options(analytics_c PRIVATE -Wall -Wextra -Wpedantic)
endif()
