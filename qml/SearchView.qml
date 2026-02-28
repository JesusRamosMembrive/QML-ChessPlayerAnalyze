import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ChessAnalyzerQML

Item {
    id: root

    required property var controller

    signal analysisComplete()

    ColumnLayout {
        anchors.centerIn: parent
        width: Math.min(parent.width - 60, 420)
        spacing: 24

        // Title
        Label {
            text: "Chess Player Analyzer"
            font.pixelSize: Theme.fontTitle
            font.weight: Font.Bold
            Layout.alignment: Qt.AlignHCenter
            color: Theme.textPrimary
        }

        Label {
            text: "Analyze Chess.com players for suspicious patterns"
            font.pixelSize: 14
            Layout.alignment: Qt.AlignHCenter
            color: Theme.textSecondary
        }

        Item { Layout.preferredHeight: 8 }

        // Username input
        ColumnLayout {
            spacing: 6
            Layout.fillWidth: true

            Label {
                text: "Chess.com Username"
                font.pixelSize: Theme.fontLabel
                font.weight: Font.Medium
                color: Theme.textSecondary
            }

            TextField {
                id: usernameField
                placeholderText: "e.g. hikaru"
                placeholderTextColor: Theme.textDisabled
                font.pixelSize: Theme.fontBody
                color: Theme.textPrimary
                Layout.fillWidth: true
                enabled: !root.controller.isAnalyzing

                background: Rectangle {
                    radius: Theme.radius
                    color: usernameField.enabled ? Theme.inputBackground : Theme.inputDisabled
                    border.color: usernameField.activeFocus ? Theme.inputFocusBorder : Theme.inputBorder
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
                font.pixelSize: Theme.fontLabel
                font.weight: Font.Medium
                color: Theme.textSecondary
            }

            Slider {
                id: gamesSlider
                from: 10
                to: 200
                stepSize: 10
                value: 50
                Layout.fillWidth: true
                enabled: !root.controller.isAnalyzing

                background: Rectangle {
                    x: gamesSlider.leftPadding
                    y: gamesSlider.topPadding + gamesSlider.availableHeight / 2 - height / 2
                    width: gamesSlider.availableWidth
                    height: 4
                    radius: 2
                    color: Theme.progressTrack

                    Rectangle {
                        width: gamesSlider.visualPosition * parent.width
                        height: parent.height
                        radius: 2
                        color: Theme.accent
                    }
                }

                handle: Rectangle {
                    x: gamesSlider.leftPadding + gamesSlider.visualPosition * (gamesSlider.availableWidth - width)
                    y: gamesSlider.topPadding + gamesSlider.availableHeight / 2 - height / 2
                    width: 18
                    height: 18
                    radius: 9
                    color: gamesSlider.pressed ? Theme.accentHover : Theme.accent
                    border.color: Theme.accentHover
                    border.width: 1
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Label { text: "10";  font.pixelSize: Theme.fontCaption; color: Theme.textDisabled }
                Item { Layout.fillWidth: true }
                Label { text: "100"; font.pixelSize: Theme.fontCaption; color: Theme.textDisabled }
                Item { Layout.fillWidth: true }
                Label { text: "200"; font.pixelSize: Theme.fontCaption; color: Theme.textDisabled }
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
                color: Theme.textOnAccent
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }

            background: Rectangle {
                radius: Theme.radius
                color: {
                    if (!analyzeButton.enabled) return Theme.textDisabled
                    if (root.controller.isAnalyzing) return analyzeButton.hovered ? Theme.buttonDangerHover : Theme.buttonDanger
                    return analyzeButton.hovered ? Theme.accentHover : Theme.accent
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
                clip:true
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
                font.pixelSize: Theme.fontSmall
                color: Theme.textSecondary
                Layout.alignment: Qt.AlignHCenter
            }
        }

        // Error message
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: errorLabel.implicitHeight + 20
            radius: Theme.radius
            color: Theme.errorBackground
            border.color: Theme.errorBorder
            border.width: 1
            visible: root.controller.errorMessage.length > 0 && !root.controller.isAnalyzing

            Label {
                id: errorLabel
                text: root.controller.errorMessage
                anchors.fill: parent
                anchors.margins: 10
                wrapMode: Text.WordWrap
                font.pixelSize: Theme.fontLabel
                color: Theme.errorText
            }
        }
    }

    Connections {
        target: root.controller
        function onResultReady() {
            root.analysisComplete()
        }
    }
}
