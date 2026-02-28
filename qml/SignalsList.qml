import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import ChessAnalyzerQML

ColumnLayout {
    id: root

    property var signals: []  // string array

    spacing: 6

    Repeater {
        model: root.signals

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Label {
                text: "\u2022"
                font.pixelSize: Theme.fontBody
                color: Theme.riskHigh
            }

            Label {
                text: modelData
                font.pixelSize: Theme.fontSmall
                color: Theme.textSecondary
                wrapMode: Text.Wrap
                Layout.fillWidth: true
            }
        }
    }
}
