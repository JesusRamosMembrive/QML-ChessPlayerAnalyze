import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ChessAnalyzerQML

Rectangle {
    id: root

    required property var controller
    property bool showProgress: controller.isAnalyzing

    signal startAnalysisClicked()
    signal dismissed()

    radius: Theme.radiusLarge
    color: Theme.surface
    border.color: Theme.inputBorder
    border.width: 1
    implicitHeight: content.implicitHeight + 32

    ColumnLayout {
        id: content
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12

        // Player info row
        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            // Avatar placeholder
            Rectangle {
                width: 40
                height: 40
                radius: 20
                color: Theme.accent

                Label {
                    anchors.centerIn: parent
                    text: root.controller.username.charAt(0).toUpperCase()
                    font.pixelSize: 18
                    font.weight: Font.Bold
                    color: Theme.textOnAccent
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2

                Label {
                    text: root.controller.username
                    font.pixelSize: Theme.fontBody
                    font.weight: Font.Bold
                    color: Theme.textPrimary
                }

                RowLayout {
                    spacing: 8
                    Label {
                        text: root.controller.gamesAvailable + " games available"
                        font.pixelSize: Theme.fontSmall
                        color: Theme.textSecondary
                    }
                    Label {
                        text: root.controller.monthsAvailable + " months"
                        font.pixelSize: Theme.fontSmall
                        color: Theme.textDisabled
                    }
                }
            }

            // Analyzing badge
            Rectangle {
                visible: root.showProgress
                Layout.preferredWidth: analyzingLabel.implicitWidth + 16
                Layout.preferredHeight: analyzingLabel.implicitHeight + 8
                radius: Theme.radiusPill
                color: Theme.accentSubtle
                border.color: Theme.accent
                border.width: 1

                Label {
                    id: analyzingLabel
                    anchors.centerIn: parent
                    text: "Analyzing"
                    font.pixelSize: Theme.fontCaption
                    font.weight: Font.Medium
                    color: Theme.accent
                }
            }

            // Start Analysis button (shown when not analyzing)
            Button {
                id: startBtn
                visible: !root.showProgress
                text: "Start Analysis"
                font.pixelSize: Theme.fontSmall
                font.weight: Font.Medium

                contentItem: Label {
                    text: startBtn.text
                    font: startBtn.font
                    color: Theme.textOnAccent
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }

                background: Rectangle {
                    radius: Theme.radius
                    color: startBtn.hovered ? Theme.accentHover : Theme.accent
                    implicitWidth: 120
                    implicitHeight: 32
                }

                onClicked: root.startAnalysisClicked()
            }

            // Dismiss button
            Button {
                visible: !root.showProgress
                flat: true
                implicitWidth: 28
                implicitHeight: 28

                contentItem: Label {
                    text: "\u00D7"
                    font.pixelSize: 18
                    color: Theme.textDisabled
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }

                background: Rectangle {
                    radius: 14
                    color: parent.hovered ? Theme.card : "transparent"
                }

                onClicked: root.dismissed()
            }
        }

        // Progress section (visible during analysis)
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 6
            visible: root.showProgress

            RowLayout {
                Layout.fillWidth: true
                Label {
                    text: "Progress"
                    font.pixelSize: Theme.fontSmall
                    color: Theme.textSecondary
                }
                Item { Layout.fillWidth: true }
                Label {
                    text: {
                        let pct = Math.round(root.controller.progress * 100)
                        return pct + "%"
                    }
                    font.pixelSize: Theme.fontSmall
                    color: Theme.textSecondary
                }
            }

            ProgressBar {
                id: progressBar
                clip: true
                from: 0
                to: 1
                value: root.controller.progress
                Layout.fillWidth: true
                indeterminate: root.controller.progress === 0

                background: Rectangle {
                    implicitHeight: 6
                    radius: 3
                    color: Theme.progressTrack
                }

                contentItem: Item {
                    implicitHeight: 6

                    Rectangle {
                        width: progressBar.visualPosition * parent.width
                        height: parent.height
                        radius: 3
                        color: Theme.progressFill
                        visible: !progressBar.indeterminate
                    }

                    Rectangle {
                        id: indeterminateBar
                        width: parent.width * 0.3
                        height: parent.height
                        radius: 3
                        color: Theme.progressFill
                        visible: progressBar.indeterminate

                        SequentialAnimation on x {
                            running: progressBar.indeterminate && root.showProgress
                            loops: Animation.Infinite
                            NumberAnimation {
                                from: -indeterminateBar.width
                                to: progressBar.width
                                duration: 1200
                                easing.type: Easing.InOutQuad
                            }
                        }
                    }
                }
            }

            Label {
                text: root.controller.progressText
                font.pixelSize: Theme.fontCaption
                color: Theme.textDisabled
            }
        }
    }
}
