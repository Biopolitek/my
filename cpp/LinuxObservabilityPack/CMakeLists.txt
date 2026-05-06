cmake_minimum_required(VERSION 3.20)
project(LinuxObservabilityPack LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_executable(LinuxObservabilityPack src/main.cpp)

if(MSVC)
    target_compile_options(LinuxObservabilityPack PRIVATE /W4 /permissive- /EHsc)
else()
    target_compile_options(LinuxObservabilityPack PRIVATE -Wall -Wextra -Wpedantic)
endif()
