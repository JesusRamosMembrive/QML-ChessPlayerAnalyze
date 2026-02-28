import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ChessAnalyzerQML

Item {
    id: root

    required property var controller

    signal newAnalysis()

    ScrollView {
        anchors.fill: parent
        contentWidth: availableWidth

        ColumnLayout {
            width: parent.width
            spacing: 0

            Item {
                Layout.fillWidth: true
                Layout.preferredHeight: mainContent.implicitHeight + 60

                ColumnLayout {
                    id: mainContent
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.top: parent.top
                    anchors.topMargin: 30
                    width: Math.min(parent.width - 60, 440)
                    spacing: 20

                    // Header
                    Label {
                        text: "Analysis Results"
                        font.pixelSize: Theme.fontHeading
                        font.weight: Font.Bold
                        color: Theme.textPrimary
                        Layout.alignment: Qt.AlignHCenter
                    }

                    Label {
                        text: root.controller.username
                        font.pixelSize: 16
                        color: Theme.textSecondary
                        Layout.alignment: Qt.AlignHCenter
                    }

                    // Suspicion Score Card
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: scoreColumn.implicitHeight + 40
                        radius: Theme.radiusLarge
                        color: Theme.riskBgColor(root.controller.riskLevel)
                        border.color: Theme.riskColor(root.controller.riskLevel)
                        border.width: 2

                        ColumnLayout {
                            id: scoreColumn
                            anchors.centerIn: parent
                            spacing: 8

                            Label {
                                text: Math.round(root.controller.suspicionScore)
                                font.pixelSize: 56
                                font.weight: Font.Bold
                                color: Theme.riskColor(root.controller.riskLevel)
                                Layout.alignment: Qt.AlignHCenter
                            }

                            Label {
                                text: "Suspicion Score"
                                font.pixelSize: Theme.fontLabel
                                color: Theme.textSecondary
                                Layout.alignment: Qt.AlignHCenter
                            }

                            // Risk Level Badge
                            Rectangle {
                                Layout.alignment: Qt.AlignHCenter
                                Layout.preferredWidth: riskLabel.implicitWidth + 24
                                Layout.preferredHeight: riskLabel.implicitHeight + 12
                                radius: Theme.radiusPill
                                color: Theme.riskColor(root.controller.riskLevel)

                                Label {
                                    id: riskLabel
                                    anchors.centerIn: parent
                                    text: root.controller.riskLevel
                                    font.pixelSize: Theme.fontLabel
                                    font.weight: Font.Bold
                                    color: Theme.textOnAccent
                                }
                            }
                        }
                    }

                    // Metrics Grid
                    GridLayout {
                        Layout.fillWidth: true
                        columns: 2
                        columnSpacing: 12
                        rowSpacing: 12

                        MetricCard {
                            value: root.controller.acplMean.toFixed(1)
                            label: "ACPL Mean"
                            Layout.fillWidth: true
                        }

                        MetricCard {
                            value: root.controller.gamesCount
                            label: "Games Analyzed"
                            Layout.fillWidth: true
                        }

                        MetricCard {
                            value: root.controller.top1MatchRate.toFixed(1) + "%"
                            label: "Top-1 Match"
                            Layout.fillWidth: true
                        }

                        MetricCard {
                            value: root.controller.blunderRate.toFixed(1) + "%"
                            label: "Blunder Rate"
                            Layout.fillWidth: true
                        }
                    }

                    Item { height: 8 }

                    // New Analysis button
                    Button {
                        id: newAnalysisButton
                        text: "New Analysis"
                        Layout.fillWidth: true
                        Layout.preferredHeight: 44
                        font.pixelSize: Theme.fontBody
                        font.weight: Font.Medium

                        contentItem: Label {
                            text: newAnalysisButton.text
                            font: newAnalysisButton.font
                            color: Theme.accent
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }

                        background: Rectangle {
                            radius: Theme.radius
                            color: newAnalysisButton.hovered ? Theme.accentSubtle : Theme.surface
                            border.color: Theme.accent
                            border.width: 1.5
                        }

                        onClicked: root.newAnalysis()
                    }
                }
            }
        }
    }
}
