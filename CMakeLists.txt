cmake_minimum_required(VERSION 3.16)

project(ChessAnalyzerQML VERSION 0.1 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)

find_package(Qt6 REQUIRED COMPONENTS Quick QuickControls2)

qt_standard_project_setup(REQUIRES 6.8)

qt_add_executable(appChessAnalyzerQML
    main.cpp
    src/AnalysisController.h
    src/AnalysisController.cpp
    src/Settings.h
    src/Settings.cpp
)

set_source_files_properties(qml/Theme.qml PROPERTIES QT_QML_SINGLETON_TYPE TRUE)

qt_add_qml_module(appChessAnalyzerQML
    URI ChessAnalyzerQML
    QML_FILES
        qml/Main.qml
        qml/SearchView.qml
        qml/ResultView.qml
        qml/PlayerCard.qml
        qml/AnalysisOptionsDialog.qml
        qml/MetricCard.qml
        qml/SimpleBarChart.qml
        qml/DonutChart.qml
        qml/ScaleBar.qml
        qml/SignalsList.qml
        qml/LineChart.qml
        qml/RadarChart.qml
        qml/Theme.qml
)

set_target_properties(appChessAnalyzerQML PROPERTIES
    MACOSX_BUNDLE_BUNDLE_VERSION ${PROJECT_VERSION}
    MACOSX_BUNDLE_SHORT_VERSION_STRING ${PROJECT_VERSION_MAJOR}.${PROJECT_VERSION_MINOR}
    MACOSX_BUNDLE TRUE
    WIN32_EXECUTABLE TRUE
)

target_include_directories(appChessAnalyzerQML PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src)

target_link_libraries(appChessAnalyzerQML
    PRIVATE Qt6::Quick Qt6::QuickControls2
)

include(GNUInstallDirs)
install(TARGETS appChessAnalyzerQML
    BUNDLE DESTINATION .
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
)
