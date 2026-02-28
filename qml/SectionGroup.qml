import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import ChessAnalyzerQML

Rectangle {
    id: root

    required property string title
    default property alias content: contentColumn.data

    Layout.fillWidth: true
    implicitHeight: innerColumn.implicitHeight + 40
    radius: Theme.radiusLarge
    color: Theme.surface
    border.color: Theme.inputBorder
    border.width: 1

    ColumnLayout {
        id: innerColumn
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: 20
        spacing: 12

        Label {
            text: root.title
            font.pixelSize: Theme.fontHeading
            font.weight: Font.Bold
            color: Theme.textPrimary
        }

        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: Theme.inputBorder
        }

        ColumnLayout {
            id: contentColumn
            Layout.fillWidth: true
            spacing: 12
        }
    }
}
