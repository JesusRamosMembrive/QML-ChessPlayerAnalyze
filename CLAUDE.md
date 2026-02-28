# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ChessAnalyzerQML is a Qt 6 QML desktop application for chess analysis. Currently at version 0.1 (starter scaffold).

## Build Commands

```bash
# Configure (from project root)
cmake -B build -G Ninja

# Build
cmake --build build

# Run
./build/Desktop_Qt_6_10_1_MSVC2022_64bit-Debug/appChessAnalyzerQML.exe
```

**Requirements:** Qt 6.8+, CMake 3.16+, MSVC 2022 64-bit, Ninja build generator.

## Architecture

- **Build system:** CMake with Qt6 Quick module. QML files are registered via `qt_add_qml_module` under URI `ChessAnalyzerQML`.
- **Entry point:** `main.cpp` creates `QGuiApplication` + `QQmlApplicationEngine`, loads `Main.qml` from the QML module.
- **UI layer:** `Main.qml` is the root QML component using Qt Quick Controls `ApplicationWindow`.
- **C++ ↔ QML boundary:** New C++ backend classes should be registered with the QML engine (via `QML_ELEMENT` macro or `qmlRegisterType`) and added to the `qt_add_qml_module` sources in `CMakeLists.txt`.

## Conventions

- C++17 standard (`CMAKE_CXX_STANDARD_REQUIRED ON` in CMakeLists.txt).
- Windows target (`WIN32_EXECUTABLE` set). macOS bundle support is also configured.
- IDE: Qt Creator project (`.qtcreator/` config present). Conan is available for dependency management.
