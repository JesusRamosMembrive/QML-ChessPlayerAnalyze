import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import ChessAnalyzerQML

Rectangle {
    id: root

    property string title: ""
    property string subtitle: ""
    property real value: 0
    property real minValue: 0
    property real maxValue: 100
    property var thresholds: []  // [{value, label, color}] — zones from left to right

    color: Theme.card
    radius: Theme.radius
    implicitHeight: col.implicitHeight + 32

    ColumnLayout {
        id: col
        anchors.fill: parent
        anchors.margins: 16
        spacing: 8

        // Title row
        RowLayout {
            Layout.fillWidth: true
            Label {
                text: root.title
                font.pixelSize: Theme.fontLabel
                font.weight: Font.DemiBold
                color: Theme.textPrimary
                visible: text.length > 0
                Layout.fillWidth: true
            }
            Label {
                text: Number(root.value).toFixed(1)
                font.pixelSize: Theme.fontHeading
                font.weight: Font.Bold
                color: Theme.textPrimary
            }
        }

        // Scale track
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 24

            // Background track
            Rectangle {
                id: track
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                height: 8
                radius: 4
                color: Theme.progressTrack

                // Colored zones from thresholds
                Repeater {
                    model: root.thresholds

                    Rectangle {
                        property real prevVal: index > 0 ? root.thresholds[index - 1].value : root.minValue
                        property real range: root.maxValue - root.minValue
                        x: range > 0 ? ((prevVal - root.minValue) / range) * track.width : 0
                        width: range > 0 ? (((modelData.value || root.maxValue) - prevVal) / range) * track.width : 0
                        height: track.height
                        radius: 4
                        color: modelData.color || Theme.accent
                        opacity: 0.4
                        anchors.verticalCenter: track.verticalCenter
                    }
                }
            }

            // Marker
            Rectangle {
                id: marker
                property real range: root.maxValue - root.minValue
                property real pos: range > 0 ? Math.max(0, Math.min(1, (root.value - root.minValue) / range)) : 0
                x: pos * (parent.width - width)
                anchors.verticalCenter: parent.verticalCenter
                width: 14
                height: 14
                radius: 7
                color: Theme.textPrimary
                border.color: Theme.background
                border.width: 2
            }
        }

        // Threshold labels
        RowLayout {
            Layout.fillWidth: true

            Repeater {
                model: root.thresholds

                Label {
                    text: modelData.label || ""
                    font.pixelSize: Theme.fontCaption
                    color: Theme.textSecondary
                    Layout.fillWidth: true
                    horizontalAlignment: index === root.thresholds.length - 1 ? Text.AlignRight :
                                        index === 0 ? Text.AlignLeft : Text.AlignHCenter
                }
            }
        }

        Label {
            text: root.subtitle
            font.pixelSize: Theme.fontCaption
            color: Theme.textSecondary
            visible: text.length > 0
            Layout.fillWidth: true
            wrapMode: Text.Wrap
        }
    }
}
