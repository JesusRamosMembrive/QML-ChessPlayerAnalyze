pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import ChessAnalyzerQML

ApplicationWindow {
    id: window
    width: 520
    height: 680
    minimumWidth: 400
    minimumHeight: 550
    visible: true
    title: "Chess Player Analyzer"
    color: "#f5f6fa"
    Material.theme: Material.Dark
    Material.accent: Material.Teal
    Material.primary: Material.BlueGrey

    AnalysisController {
        id: analysisController
    }

    StackView {
        id: stackView
        anchors.fill: parent
        initialItem: searchViewComponent
    }

    Component {
        id: searchViewComponent

        SearchView {
            controller: analysisController

            onAnalysisComplete: {
                stackView.push(resultViewComponent)
            }
        }
    }

    Component {
        id: resultViewComponent

        ResultView {
            controller: analysisController

            onNewAnalysis: {
                stackView.pop()
            }
        }
    }
}
