import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts

Item {
    id: root

    Material.theme: Material.Dark

    required property var controller

    signal analysisComplete()

    ColumnLayout {
        anchors.centerIn: parent
        width: Math.min(parent.width - 60, 420)
        spacing: 24

        // Title
        Label {
            text: "Chess Player Analyzer"
            font.pixelSize: 28
            font.weight: Font.Bold
            Layout.alignment: Qt.AlignHCenter
            color: "#1a1a2e"
        }

        Label {
            text: "Analyze Chess.com players for suspicious patterns"
            font.pixelSize: 14
            Layout.alignment: Qt.AlignHCenter
            color: "#666666"
        }

        // Spacer
        Item { Layout.preferredHeight: 8 }

        // Username input
        ColumnLayout {
            spacing: 6
            Layout.fillWidth: true

            Label {
                text: "Chess.com Username"
                font.pixelSize: 13
                font.weight: Font.Medium
                color: "#333333"
            }

            TextField {
                id: usernameField
                placeholderText: "e.g. hikaru"
                font.pixelSize: 15
                Layout.fillWidth: true
                enabled: !root.controller.isAnalyzing

                background: Rectangle {
                    radius: 8
                    color: usernameField.enabled ? "#fff" : "#f5f5f5"
                    border.color: usernameField.activeFocus ? "#4a90d9" : "#ddd"
                    border.width: usernameField.activeFocus ? 2 : 1
                }

                leftPadding: 12
                rightPadding: 12
                topPadding: 10
                bottomPadding: 10

                onAccepted: {
                    if (text.trim().length > 0 && !root.controller.isAnalyzing) {
                        analyzeButton.clicked()
                    }
                }
            }
        }

        // Games slider
        ColumnLayout {
            spacing: 6
            Layout.fillWidth: true

            Label {
                text: "Games to analyze: " + gamesSlider.value
                font.pixelSize: 13
                font.weight: Font.Medium
                color: "#333333"
            }

            Slider {
                id: gamesSlider
                from: 10
                to: 200
                stepSize: 10
                value: 50
                Layout.fillWidth: true
                enabled: !root.controller.isAnalyzing
            }

            RowLayout {
                Layout.fillWidth: true
                Label { text: "10"; font.pixelSize: 11; color: "#999999" }
                Item { Layout.fillWidth: true }
                Label { text: "100"; font.pixelSize: 11; color: "#999999" }
                Item { Layout.fillWidth: true }
                Label { text: "200"; font.pixelSize: 11; color: "#999999" }
            }
        }

        // Analyze button
        Button {
            id: analyzeButton
            text: root.controller.isAnalyzing ? "Cancel" : "Analyze"
            Layout.fillWidth: true
            Layout.preferredHeight: 48
            enabled: root.controller.isAnalyzing || usernameField.text.trim().length > 0
            font.pixelSize: 16
            font.weight: Font.Medium

            contentItem: Label {
                text: analyzeButton.text
                font: analyzeButton.font
                color: "#ffffff"
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }

            background: Rectangle {
                radius: 8
                color: {
                    if (!analyzeButton.enabled) return "#cccccc"
                    if (root.controller.isAnalyzing) return analyzeButton.hovered ? "#c0392b" : "#e74c3c"
                    return analyzeButton.hovered ? "#357abd" : "#4a90d9"
                }
            }

            onClicked: {
                if (root.controller.isAnalyzing) {
                    root.controller.cancelAnalysis()
                } else {
                    root.controller.startAnalysis(usernameField.text.trim(), gamesSlider.value)
                }
            }
        }

        // Progress section
        ColumnLayout {
            spacing: 8
            Layout.fillWidth: true
            visible: root.controller.isAnalyzing

            ProgressBar {
                id: progressBar
                from: 0
                to: 1
                value: root.controller.progress
                Layout.fillWidth: true
                indeterminate: root.controller.progress === 0

                background: Rectangle {
                    implicitHeight: 6
                    radius: 3
                    color: "#e0e0e0"
                }

                contentItem: Item {
                    implicitHeight: 6

                    Rectangle {
                        width: progressBar.visualPosition * parent.width
                        height: parent.height
                        radius: 3
                        color: "#4a90d9"
                        visible: !progressBar.indeterminate
                    }

                    // Indeterminate animation
                    Rectangle {
                        id: indeterminateBar
                        width: parent.width * 0.3
                        height: parent.height
                        radius: 3
                        color: "#4a90d9"
                        visible: progressBar.indeterminate

                        SequentialAnimation on x {
                            running: progressBar.indeterminate
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
                font.pixelSize: 12
                color: "#666666"
                Layout.alignment: Qt.AlignHCenter
            }
        }

        // Error message
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: errorLabel.implicitHeight + 20
            radius: 8
            color: "#ffeaea"
            border.color: "#e74c3c"
            border.width: 1
            visible: root.controller.errorMessage.length > 0 && !root.controller.isAnalyzing

            Label {
                id: errorLabel
                text: root.controller.errorMessage
                anchors.fill: parent
                anchors.margins: 10
                wrapMode: Text.WordWrap
                font.pixelSize: 13
                color: "#c0392b"
            }
        }
    }

    // Navigate to results when analysis completes
    Connections {
        target: root.controller
        function onResultReady() {
            root.analysisComplete()
        }
    }
}
