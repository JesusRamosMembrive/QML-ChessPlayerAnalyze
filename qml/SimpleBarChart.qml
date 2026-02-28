import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import ChessAnalyzerQML

Rectangle {
    id: root

    property string title: ""
    property string subtitle: ""
    property var model: []       // [{label, value, color}]
    property real maxValue: 0    // 0 = auto-detect

    color: Theme.card
    radius: Theme.radius
    implicitHeight: col.implicitHeight + 32

    ColumnLayout {
        id: col
        anchors.fill: parent
        anchors.margins: 16
        spacing: 8

        Label {
            text: root.title
            font.pixelSize: Theme.fontLabel
            font.weight: Font.DemiBold
            color: Theme.textPrimary
            visible: text.length > 0
        }

        // Bars area
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 120

            Row {
                anchors.fill: parent
                spacing: 8

                Repeater {
                    model: root.model

                    Item {
                        width: (parent.width - (root.model.length - 1) * 8) / Math.max(root.model.length, 1)
                        height: parent.height

                        property real barMax: {
                            if (root.maxValue > 0) return root.maxValue;
                            var m = 0;
                            for (var i = 0; i < root.model.length; i++)
                                m = Math.max(m, root.model[i].value || 0);
                            return m > 0 ? m : 1;
                        }

                        // Value label on top
                        Label {
                            id: valLabel
                            anchors.horizontalCenter: parent.horizontalCenter
                            anchors.bottom: bar.top
                            anchors.bottomMargin: 4
                            text: modelData.value !== undefined ? Number(modelData.value).toFixed(1) : ""
                            font.pixelSize: Theme.fontSmall
                            font.weight: Font.Bold
                            color: Theme.textPrimary
                        }

                        // Bar
                        Rectangle {
                            id: bar
                            anchors.bottom: labelText.top
                            anchors.bottomMargin: 4
                            anchors.horizontalCenter: parent.horizontalCenter
                            width: Math.min(parent.width * 0.7, 40)
                            height: Math.max(4, (parent.height - valLabel.height - labelText.height - 16) * Math.min((modelData.value || 0) / barMax, 1))
                            radius: 4
                            color: modelData.color || Theme.accent
                        }

                        // Label below
                        Label {
                            id: labelText
                            anchors.bottom: parent.bottom
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: modelData.label || ""
                            font.pixelSize: Theme.fontCaption
                            color: Theme.textSecondary
                            horizontalAlignment: Text.AlignHCenter
                            width: parent.width
                            elide: Text.ElideRight
                        }
                    }
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
