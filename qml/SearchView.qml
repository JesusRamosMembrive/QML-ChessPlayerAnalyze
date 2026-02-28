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

    // Show feature cards only when there's nothing else below the input
    property bool showFeatures: root.viewState === "idle"
                                || root.viewState === "playerNotFound"

    ColumnLayout {
        anchors.centerIn: parent
        width: Math.min(parent.width - 60, 500)
        spacing: 0

        // ── Chess icon badge ──
        Rectangle {
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: 72
            Layout.preferredHeight: 72
            radius: 36
            color: Theme.accentSubtle

            Label {
                anchors.centerIn: parent
                text: "\u265E"   // ♞ black chess knight
                font.pixelSize: 38
                color: Theme.accent
            }
        }

        Item { Layout.preferredHeight: 20 }

        // ── Title ──
        Label {
            text: "Chess Player Analyzer"
            font.pixelSize: Theme.fontTitle
            font.weight: Font.Bold
            Layout.alignment: Qt.AlignHCenter
            color: Theme.textPrimary
        }

        Item { Layout.preferredHeight: 8 }

        Label {
            text: "Analyze Chess.com players for suspicious patterns"
            font.pixelSize: 14
            Layout.alignment: Qt.AlignHCenter
            color: Theme.textSecondary
        }

        Item { Layout.preferredHeight: 28 }

        // ── Separator ──
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 1
            color: Theme.inputBorder
            opacity: 0.5
        }

        Item { Layout.preferredHeight: 28 }

        // ── Username input ──
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

        Item { Layout.preferredHeight: 20 }

        // ── Busy indicator while checking ──
        Item {
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: 48
            Layout.preferredHeight: 48
            visible: root.viewState === "checking"

            Rectangle {
                id: spinner
                anchors.centerIn: parent
                width: 40
                height: 40
                radius: 20
                color: "transparent"
                border.width: 4
                border.color: Theme.accentSubtle

                Canvas {
                    id: arc
                    anchors.fill: parent
                    property real angle: 0

                    onPaint: {
                        var ctx = getContext("2d")
                        ctx.reset()
                        ctx.lineWidth = 4
                        ctx.strokeStyle = Theme.accent
                        ctx.lineCap = "round"
                        ctx.beginPath()
                        var cx = width / 2
                        var cy = height / 2
                        var r = (width - 4) / 2
                        var startAngle = angle * Math.PI / 180
                        ctx.arc(cx, cy, r, startAngle, startAngle + Math.PI * 0.75)
                        ctx.stroke()
                    }

                    RotationAnimation on rotation {
                        from: 0
                        to: 360
                        duration: 1000
                        loops: Animation.Infinite
                        running: root.viewState === "checking"
                    }

                    Connections {
                        target: arc
                        function onRotationChanged() { arc.requestPaint() }
                    }
                }
            }
        }

        // ── Player Card ──
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

        // ── Player not found ──
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

        // ── Error message ──
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

        // ── Feature cards (idle decoration) ──
        Item { Layout.preferredHeight: 32; visible: root.showFeatures }

        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            visible: root.showFeatures

            Repeater {
                model: [
                    { icon: "\u2699", title: "Engine Analysis",  desc: "Multi-PV Stockfish depth scan" },
                    { icon: "\u2694", title: "Pattern Detection", desc: "Precision bursts & time anomalies" },
                    { icon: "\u2690", title: "Risk Scoring",     desc: "Composite suspicion signals" }
                ]

                delegate: Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: featureCol.implicitHeight + 28
                    radius: Theme.radius
                    color: Theme.surface
                    border.color: Theme.inputBorder
                    border.width: 1

                    ColumnLayout {
                        id: featureCol
                        anchors.fill: parent
                        anchors.margins: 14
                        spacing: 6

                        Label {
                            text: modelData.icon
                            font.pixelSize: 22
                            color: Theme.accent
                        }

                        Label {
                            text: modelData.title
                            font.pixelSize: Theme.fontLabel
                            font.weight: Font.DemiBold
                            color: Theme.textPrimary
                        }

                        Label {
                            text: modelData.desc
                            font.pixelSize: Theme.fontCaption
                            color: Theme.textSecondary
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }
                    }
                }
            }
        }

        // ── Footer hint ──
        Item { Layout.preferredHeight: 24; visible: root.showFeatures }

        Label {
            text: "Enter a Chess.com username to get started"
            font.pixelSize: Theme.fontCaption
            Layout.alignment: Qt.AlignHCenter
            color: Theme.textDisabled
            visible: root.showFeatures
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
