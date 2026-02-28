import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root

    required property var controller

    signal newAnalysis()

    function riskColor(level) {
        switch (level) {
        case "LOW": return "#27ae60"
        case "MODERATE": return "#f39c12"
        case "HIGH": return "#e67e22"
        case "VERY HIGH": return "#e74c3c"
        default: return "#999"
        }
    }

    function riskBackground(level) {
        switch (level) {
        case "LOW": return "#eafaf1"
        case "MODERATE": return "#fef9e7"
        case "HIGH": return "#fdf2e9"
        case "VERY HIGH": return "#fdedec"
        default: return "#f5f5f5"
        }
    }

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
                        font.pixelSize: 24
                        font.weight: Font.Bold
                        color: "#1a1a2e"
                        Layout.alignment: Qt.AlignHCenter
                    }

                    Label {
                        text: root.controller.username
                        font.pixelSize: 16
                        color: "#666"
                        Layout.alignment: Qt.AlignHCenter
                    }

                    // Suspicion Score Card
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: scoreColumn.implicitHeight + 40
                        radius: 12
                        color: riskBackground(root.controller.riskLevel)
                        border.color: riskColor(root.controller.riskLevel)
                        border.width: 2

                        ColumnLayout {
                            id: scoreColumn
                            anchors.centerIn: parent
                            spacing: 8

                            Label {
                                text: Math.round(root.controller.suspicionScore)
                                font.pixelSize: 56
                                font.weight: Font.Bold
                                color: riskColor(root.controller.riskLevel)
                                Layout.alignment: Qt.AlignHCenter
                            }

                            Label {
                                text: "Suspicion Score"
                                font.pixelSize: 13
                                color: "#666"
                                Layout.alignment: Qt.AlignHCenter
                            }

                            // Risk Level Badge
                            Rectangle {
                                Layout.alignment: Qt.AlignHCenter
                                Layout.preferredWidth: riskLabel.implicitWidth + 24
                                Layout.preferredHeight: riskLabel.implicitHeight + 12
                                radius: 16
                                color: riskColor(root.controller.riskLevel)

                                Label {
                                    id: riskLabel
                                    anchors.centerIn: parent
                                    text: root.controller.riskLevel
                                    font.pixelSize: 13
                                    font.weight: Font.Bold
                                    color: "#fff"
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

                        // ACPL Mean
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 80
                            radius: 8
                            color: "#f8f9fa"
                            border.color: "#e9ecef"

                            ColumnLayout {
                                anchors.centerIn: parent
                                spacing: 4

                                Label {
                                    text: root.controller.acplMean.toFixed(1)
                                    font.pixelSize: 24
                                    font.weight: Font.Bold
                                    color: "#1a1a2e"
                                    Layout.alignment: Qt.AlignHCenter
                                }
                                Label {
                                    text: "ACPL Mean"
                                    font.pixelSize: 11
                                    color: "#888"
                                    Layout.alignment: Qt.AlignHCenter
                                }
                            }
                        }

                        // Games Count
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 80
                            radius: 8
                            color: "#f8f9fa"
                            border.color: "#e9ecef"

                            ColumnLayout {
                                anchors.centerIn: parent
                                spacing: 4

                                Label {
                                    text: root.controller.gamesCount
                                    font.pixelSize: 24
                                    font.weight: Font.Bold
                                    color: "#1a1a2e"
                                    Layout.alignment: Qt.AlignHCenter
                                }
                                Label {
                                    text: "Games Analyzed"
                                    font.pixelSize: 11
                                    color: "#888"
                                    Layout.alignment: Qt.AlignHCenter
                                }
                            }
                        }

                        // Top-1 Match Rate
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 80
                            radius: 8
                            color: "#f8f9fa"
                            border.color: "#e9ecef"

                            ColumnLayout {
                                anchors.centerIn: parent
                                spacing: 4

                                Label {
                                    text: root.controller.top1MatchRate.toFixed(1) + "%"
                                    font.pixelSize: 24
                                    font.weight: Font.Bold
                                    color: "#1a1a2e"
                                    Layout.alignment: Qt.AlignHCenter
                                }
                                Label {
                                    text: "Top-1 Match"
                                    font.pixelSize: 11
                                    color: "#888"
                                    Layout.alignment: Qt.AlignHCenter
                                }
                            }
                        }

                        // Blunder Rate
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 80
                            radius: 8
                            color: "#f8f9fa"
                            border.color: "#e9ecef"

                            ColumnLayout {
                                anchors.centerIn: parent
                                spacing: 4

                                Label {
                                    text: root.controller.blunderRate.toFixed(1) + "%"
                                    font.pixelSize: 24
                                    font.weight: Font.Bold
                                    color: "#1a1a2e"
                                    Layout.alignment: Qt.AlignHCenter
                                }
                                Label {
                                    text: "Blunder Rate"
                                    font.pixelSize: 11
                                    color: "#888"
                                    Layout.alignment: Qt.AlignHCenter
                                }
                            }
                        }
                    }

                    // New Analysis button
                    Item { height: 8 }

                    Button {
                        id: newAnalysisButton
                        text: "New Analysis"
                        Layout.fillWidth: true
                        Layout.preferredHeight: 44
                        font.pixelSize: 15
                        font.weight: Font.Medium

                        contentItem: Label {
                            text: newAnalysisButton.text
                            font: newAnalysisButton.font
                            color: "#4a90d9"
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }

                        background: Rectangle {
                            radius: 8
                            color: newAnalysisButton.hovered ? "#e8f0fe" : "#fff"
                            border.color: "#4a90d9"
                            border.width: 1.5
                        }

                        onClicked: root.newAnalysis()
                    }
                }
            }
        }
    }
}
