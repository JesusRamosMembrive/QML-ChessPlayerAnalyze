import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import ChessAnalyzerQML

Rectangle {
    id: root

    required property string value
    required property string label
    property string description: ""

    height: cardCol.implicitHeight + 24
    radius: Theme.radius
    color: Theme.card

    ColumnLayout {
        id: cardCol
        anchors.centerIn: parent
        width: parent.width - 24
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

        Label {
            text: root.description
            font.pixelSize: Theme.fontCaption
            color: Theme.textDisabled
            visible: text.length > 0
            Layout.alignment: Qt.AlignHCenter
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.Wrap
            Layout.fillWidth: true
        }
    }
}
