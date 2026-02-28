import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ChessAnalyzerQML

Popup {
    id: root

    required property string username
    required property int gamesAvailable

    signal startRequested(int games, int depth, int workers)

    anchors.centerIn: parent
    width: Math.min(parent.width - 40, 400)
    modal: true
    dim: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    padding: 0

    Overlay.modal: Rectangle {
        color: "#80000000"
    }

    background: Rectangle {
        radius: Theme.radiusLarge
        color: Theme.surface
        border.color: Theme.inputBorder
        border.width: 1
    }

    contentItem: ColumnLayout {
        spacing: 0

        // Header
        ColumnLayout {
            Layout.fillWidth: true
            Layout.margins: 20
            Layout.bottomMargin: 0
            spacing: 4

            Label {
                text: "Analysis Options"
                font.pixelSize: Theme.fontHeading
                font.weight: Font.Bold
                color: Theme.textPrimary
            }

            Label {
                text: root.username + " \u2022 " + root.gamesAvailable + " games available"
                font.pixelSize: Theme.fontSmall
                color: Theme.textSecondary
            }
        }

        // Separator
        Rectangle {
            Layout.fillWidth: true
            Layout.topMargin: 16
            Layout.bottomMargin: 4
            height: 1
            color: Theme.inputBorder
        }

        // Options
        ColumnLayout {
            Layout.fillWidth: true
            Layout.margins: 20
            spacing: 18

            // Games to analyze
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 6

                RowLayout {
                    Layout.fillWidth: true
                    Label {
                        text: "Games to analyze"
                        font.pixelSize: Theme.fontLabel
                        font.weight: Font.Medium
                        color: Theme.textSecondary
                    }
                    Item { Layout.fillWidth: true }
                    Label {
                        text: gamesSlider.value
                        font.pixelSize: Theme.fontLabel
                        font.weight: Font.Bold
                        color: Theme.textPrimary
                    }
                }

                Slider {
                    id: gamesSlider
                    Layout.fillWidth: true
                    from: 10
                    to: Math.min(200, root.gamesAvailable)
                    stepSize: 10
                    value: Math.min(50, root.gamesAvailable)

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
                    Label { text: Math.min(200, root.gamesAvailable).toString(); font.pixelSize: Theme.fontCaption; color: Theme.textDisabled }
                }
            }

            // Engine depth
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 6

                RowLayout {
                    Layout.fillWidth: true
                    Label {
                        text: "Engine depth"
                        font.pixelSize: Theme.fontLabel
                        font.weight: Font.Medium
                        color: Theme.textSecondary
                    }
                    Item { Layout.fillWidth: true }
                    Label {
                        text: depthSlider.value
                        font.pixelSize: Theme.fontLabel
                        font.weight: Font.Bold
                        color: Theme.textPrimary
                    }
                }

                Slider {
                    id: depthSlider
                    Layout.fillWidth: true
                    from: 8
                    to: 22
                    stepSize: 2
                    value: 12

                    background: Rectangle {
                        x: depthSlider.leftPadding
                        y: depthSlider.topPadding + depthSlider.availableHeight / 2 - height / 2
                        width: depthSlider.availableWidth
                        height: 4
                        radius: 2
                        color: Theme.progressTrack

                        Rectangle {
                            width: depthSlider.visualPosition * parent.width
                            height: parent.height
                            radius: 2
                            color: Theme.accent
                        }
                    }

                    handle: Rectangle {
                        x: depthSlider.leftPadding + depthSlider.visualPosition * (depthSlider.availableWidth - width)
                        y: depthSlider.topPadding + depthSlider.availableHeight / 2 - height / 2
                        width: 18
                        height: 18
                        radius: 9
                        color: depthSlider.pressed ? Theme.accentHover : Theme.accent
                        border.color: Theme.accentHover
                        border.width: 1
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    Label { text: "8 (fast)";  font.pixelSize: Theme.fontCaption; color: Theme.textDisabled }
                    Item { Layout.fillWidth: true }
                    Label { text: "22 (deep)"; font.pixelSize: Theme.fontCaption; color: Theme.textDisabled }
                }
            }

            // Workers
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 6

                RowLayout {
                    Layout.fillWidth: true
                    Label {
                        text: "Parallel workers"
                        font.pixelSize: Theme.fontLabel
                        font.weight: Font.Medium
                        color: Theme.textSecondary
                    }
                    Item { Layout.fillWidth: true }
                    Label {
                        text: workersSlider.value
                        font.pixelSize: Theme.fontLabel
                        font.weight: Font.Bold
                        color: Theme.textPrimary
                    }
                }

                Slider {
                    id: workersSlider
                    Layout.fillWidth: true
                    from: 1
                    to: 8
                    stepSize: 1
                    value: 4

                    background: Rectangle {
                        x: workersSlider.leftPadding
                        y: workersSlider.topPadding + workersSlider.availableHeight / 2 - height / 2
                        width: workersSlider.availableWidth
                        height: 4
                        radius: 2
                        color: Theme.progressTrack

                        Rectangle {
                            width: workersSlider.visualPosition * parent.width
                            height: parent.height
                            radius: 2
                            color: Theme.accent
                        }
                    }

                    handle: Rectangle {
                        x: workersSlider.leftPadding + workersSlider.visualPosition * (workersSlider.availableWidth - width)
                        y: workersSlider.topPadding + workersSlider.availableHeight / 2 - height / 2
                        width: 18
                        height: 18
                        radius: 9
                        color: workersSlider.pressed ? Theme.accentHover : Theme.accent
                        border.color: Theme.accentHover
                        border.width: 1
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    Label { text: "1"; font.pixelSize: Theme.fontCaption; color: Theme.textDisabled }
                    Item { Layout.fillWidth: true }
                    Label { text: "8"; font.pixelSize: Theme.fontCaption; color: Theme.textDisabled }
                }
            }

            // Summary
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: summaryColumn.implicitHeight + 16
                radius: Theme.radius
                color: Theme.accentSubtle
                border.color: Theme.accent
                border.width: 1

                ColumnLayout {
                    id: summaryColumn
                    anchors.fill: parent
                    anchors.margins: 8
                    spacing: 2

                    Label {
                        text: "Will analyze " + gamesSlider.value + " games at depth " + depthSlider.value
                        font.pixelSize: Theme.fontSmall
                        color: Theme.accent
                    }
                    Label {
                        text: "Using " + workersSlider.value + " parallel worker" + (workersSlider.value > 1 ? "s" : "")
                        font.pixelSize: Theme.fontCaption
                        color: Theme.textSecondary
                    }
                }
            }
        }

        // Separator
        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: Theme.inputBorder
        }

        // Buttons
        RowLayout {
            Layout.fillWidth: true
            Layout.margins: 16
            spacing: 12

            Button {
                id: cancelBtn
                text: "Cancel"
                Layout.fillWidth: true
                Layout.preferredHeight: 40
                font.pixelSize: Theme.fontBody
                font.weight: Font.Medium

                contentItem: Label {
                    text: cancelBtn.text
                    font: cancelBtn.font
                    color: Theme.textSecondary
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }

                background: Rectangle {
                    radius: Theme.radius
                    color: cancelBtn.hovered ? Theme.card : "transparent"
                    border.color: Theme.inputBorder
                    border.width: 1
                }

                onClicked: root.close()
            }

            Button {
                id: startBtn
                text: "Start Analysis"
                Layout.fillWidth: true
                Layout.preferredHeight: 40
                font.pixelSize: Theme.fontBody
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
                }

                onClicked: {
                    root.startRequested(gamesSlider.value, depthSlider.value, workersSlider.value)
                    root.close()
                }
            }
        }
    }
}
