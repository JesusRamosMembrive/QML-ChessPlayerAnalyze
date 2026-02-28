import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import ChessAnalyzerQML

Rectangle {
    id: root

    required property string value
    required property string label

    height: 80
    radius: Theme.radius
    color: Theme.card

    ColumnLayout {
        anchors.centerIn: parent
        spacing: 4

        Label {
            text: root.value
            font.pixelSize: Theme.fontHeading
            font.weight: Font.Bold
            color: Theme.textPrimary
            Layout.alignment: Qt.AlignHCenter
        }

        Label {
            text: root.label
            font.pixelSize: Theme.fontCaption
            color: Theme.textSecondary
            Layout.alignment: Qt.AlignHCenter
        }
    }
}
