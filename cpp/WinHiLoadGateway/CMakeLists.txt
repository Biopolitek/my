cmake_minimum_required(VERSION 3.20)
project(WinHiLoadGateway LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_executable(WinHiLoadGateway src/main.cpp)

if(MSVC)
    target_compile_options(WinHiLoadGateway PRIVATE /W4 /permissive- /EHsc)
else()
    target_compile_options(WinHiLoadGateway PRIVATE -Wall -Wextra -Wpedantic)
endif()
