import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ChessAnalyzerQML

Item {
    id: root

    required property var controller

    signal analysisComplete()

    // States: idle, checking, playerFound, playerNotFound, analyzing
    property string viewState: "idle"

    ColumnLayout {
        anchors.centerIn: parent
        width: Math.min(parent.width - 60, 440)
        spacing: 20

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

        Item { Layout.preferredHeight: 4 }

        // Username input row
        ColumnLayout {
            spacing: 6
            Layout.fillWidth: true

            Label {
                text: "Chess.com Username"
                font.pixelSize: Theme.fontLabel
                font.weight: Font.Medium
                color: Theme.textSecondary
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                TextField {
                    id: usernameField
                    placeholderText: "e.g. hikaru"
                    placeholderTextColor: Theme.textDisabled
                    font.pixelSize: Theme.fontBody
                    color: Theme.textPrimary
                    Layout.fillWidth: true
                    enabled: root.viewState === "idle" || root.viewState === "playerNotFound"

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
                        if (text.trim().length > 0 && root.viewState !== "checking") {
                            doCheck()
                        }
                    }
                }

                Button {
                    id: checkButton
                    text: root.viewState === "checking" ? "Checking..." : "Check"
                    enabled: usernameField.text.trim().length > 0
                             && root.viewState !== "checking"
                             && root.viewState !== "analyzing"
                    font.pixelSize: Theme.fontSmall
                    font.weight: Font.Medium

                    contentItem: Label {
                        text: checkButton.text
                        font: checkButton.font
                        color: checkButton.enabled ? Theme.textOnAccent : Theme.textDisabled
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }

                    background: Rectangle {
                        radius: Theme.radius
                        color: {
                            if (!checkButton.enabled) return Theme.inputDisabled
                            return checkButton.hovered ? Theme.accentHover : Theme.accent
                        }
                        implicitWidth: 100
                        implicitHeight: 40
                    }

                    onClicked: doCheck()
                }
            }
        }

        // Player Card (visible after successful check or during analysis)
        PlayerCard {
            id: playerCard
            Layout.fillWidth: true
            visible: root.viewState === "playerFound" || root.viewState === "analyzing"
            controller: root.controller

            onStartAnalysisClicked: {
                optionsDialog.open()
            }

            onDismissed: {
                root.controller.reset()
                root.viewState = "idle"
            }
        }

        // Player not found message
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: notFoundLabel.implicitHeight + 20
            radius: Theme.radius
            color: Theme.riskModerateBg
            border.color: Theme.riskModerate
            border.width: 1
            visible: root.viewState === "playerNotFound"

            Label {
                id: notFoundLabel
                text: "Player \"" + usernameField.text.trim() + "\" not found on Chess.com"
                anchors.fill: parent
                anchors.margins: 10
                wrapMode: Text.WordWrap
                font.pixelSize: Theme.fontLabel
                color: Theme.riskModerate
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
            visible: root.controller.errorMessage.length > 0
                     && root.viewState !== "analyzing"
                     && root.viewState !== "checking"

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

    // Analysis Options Dialog
    AnalysisOptionsDialog {
        id: optionsDialog
        parent: Overlay.overlay
        username: root.controller.username
        gamesAvailable: root.controller.gamesAvailable

        onStartRequested: function(games, depth, workers) {
            root.viewState = "analyzing"
            root.controller.startAnalysis(root.controller.username, games, depth, workers)
        }
    }

    // Controller signal connections
    Connections {
        target: root.controller

        function onCheckComplete() {
            if (root.controller.playerExists) {
                root.viewState = "playerFound"
            } else {
                root.viewState = "playerNotFound"
            }
        }

        function onResultReady() {
            root.analysisComplete()
        }

        function onErrorOccurred() {
            if (root.viewState === "checking") {
                root.viewState = "idle"
            } else if (root.viewState === "analyzing") {
                root.viewState = "playerFound"
            }
        }

        function onIsAnalyzingChanged() {
            if (!root.controller.isAnalyzing && root.viewState === "analyzing") {
                // Analysis ended (cancelled or error) without result
                if (root.controller.errorMessage.length === 0) {
                    root.viewState = "playerFound"
                }
            }
        }
    }

    function doCheck() {
        root.viewState = "checking"
        root.controller.checkPlayer(usernameField.text.trim())
    }
}
