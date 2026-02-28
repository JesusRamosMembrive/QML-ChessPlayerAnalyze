import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ChessAnalyzerQML

Item {
    id: root

    required property var controller

    signal newAnalysis()

    // Convenience alias
    readonly property var rd: controller.resultData

    // Responsive column counts based on content width
    readonly property int gridCols: mainContent.width > 1100 ? 4 : mainContent.width > 700 ? 3 : mainContent.width > 400 ? 2 : 1
    readonly property int gridColsWide: mainContent.width > 1100 ? 5 : mainContent.width > 700 ? 4 : mainContent.width > 500 ? 3 : 2

    // Helper to safely read from resultData
    function val(key, fallback) {
        if (rd && rd[key] !== undefined && rd[key] !== null) return rd[key];
        return fallback !== undefined ? fallback : 0;
    }

    // Profile display names
    function profileLabel(code) {
        var map = {
            "RESILIENT_CLOSER":      "Resilient Closer",
            "RESILIENT_SHAKY":       "Resilient Shaky",
            "FRAGILE_CLOSER":        "Fragile Closer",
            "FRAGILE_CRUMBLER":      "Fragile Crumbler",
            "PRESSURE_FIGHTER":      "Pressure Fighter",
            "PRESSURE_VULNERABLE":   "Pressure Vulnerable",
            "ENGINE_LIKE":           "Engine-Like",
            "NORMAL_HUMAN":          "Normal Human"
        };
        return map[code] || code || "Unknown";
    }

    function profileDescription(code) {
        var map = {
            "RESILIENT_CLOSER":      "Good recovery after mistakes, strong closing game",
            "RESILIENT_SHAKY":       "Good recovery after mistakes, but struggles to close",
            "FRAGILE_CLOSER":        "Struggles to recover from errors, but finishes strong",
            "FRAGILE_CRUMBLER":      "Struggles with both recovery and closing",
            "PRESSURE_FIGHTER":      "Handles time pressure well",
            "PRESSURE_VULNERABLE":   "Performance degrades under time pressure",
            "ENGINE_LIKE":           "Suspiciously consistent — no tilt, perfect recovery",
            "NORMAL_HUMAN":          "Average psychological patterns"
        };
        return map[code] || "";
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
                    width: parent.width - 40
                    spacing: 24

                    // ═══════════════════════════════════════════
                    // SECTION 1: VERDICT
                    // ═══════════════════════════════════════════

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: verdictCol.implicitHeight + 40
                        radius: Theme.radiusLarge
                        color: Theme.riskBgColor(root.controller.riskLevel)
                        border.color: Theme.riskColor(root.controller.riskLevel)
                        border.width: 2

                        ColumnLayout {
                            id: verdictCol
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.margins: 20
                            spacing: 12

                            // Header
                            RowLayout {
                                Layout.fillWidth: true
                                Label {
                                    text: "Suspicion Score"
                                    font.pixelSize: Theme.fontLabel
                                    color: Theme.textSecondary
                                    Layout.fillWidth: true
                                }
                                Label {
                                    text: Math.round(root.controller.suspicionScore) + " / 200"
                                    font.pixelSize: Theme.fontHeading
                                    font.weight: Font.Bold
                                    color: Theme.riskColor(root.controller.riskLevel)
                                }
                            }

                            // Progress bar 0-200
                            Rectangle {
                                Layout.fillWidth: true
                                height: 10
                                radius: 5
                                color: Theme.progressTrack

                                Rectangle {
                                    width: parent.width * Math.min(root.controller.suspicionScore / 200, 1)
                                    height: parent.height
                                    radius: 5
                                    color: Theme.riskColor(root.controller.riskLevel)
                                }
                            }

                            // Risk badge
                            Rectangle {
                                Layout.alignment: Qt.AlignLeft
                                Layout.preferredWidth: riskBadge.implicitWidth + 24
                                Layout.preferredHeight: riskBadge.implicitHeight + 10
                                radius: Theme.radiusPill
                                color: Theme.riskColor(root.controller.riskLevel)

                                Label {
                                    id: riskBadge
                                    anchors.centerIn: parent
                                    text: root.controller.riskLevel
                                    font.pixelSize: Theme.fontLabel
                                    font.weight: Font.Bold
                                    color: Theme.textOnAccent
                                }
                            }

                            // Signals
                            Item {
                                Layout.fillWidth: true
                                Layout.preferredHeight: signalsSection.implicitHeight
                                visible: val("signals", []).length > 0

                                ColumnLayout {
                                    id: signalsSection
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    spacing: 8

                                    Label {
                                        text: "Detected Signals (" + val("signals", []).length + ")"
                                        font.pixelSize: Theme.fontLabel
                                        font.weight: Font.DemiBold
                                        color: Theme.textPrimary
                                    }

                                    SignalsList {
                                        Layout.fillWidth: true
                                        signals: val("signals", [])
                                    }
                                }
                            }

                            // Meta row
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 16

                                Label {
                                    text: root.controller.gamesCount + " games"
                                    font.pixelSize: Theme.fontCaption
                                    color: Theme.textSecondary
                                }

                                Label {
                                    text: {
                                        var f = val("first_game_date", "");
                                        var l = val("last_game_date", "");
                                        if (f && l) return f + " \u2013 " + l;
                                        return "";
                                    }
                                    font.pixelSize: Theme.fontCaption
                                    color: Theme.textSecondary
                                    visible: text.length > 0
                                }

                                Item { Layout.fillWidth: true }

                                Label {
                                    text: "Confidence: " + val("confidence", "low")
                                    font.pixelSize: Theme.fontCaption
                                    color: Theme.textSecondary
                                }
                            }
                        }
                    }

                    // ═══════════════════════════════════════════
                    // SECTION 2: ACCURACY PROFILE
                    // ═══════════════════════════════════════════

                    SectionGroup {
                        title: "Accuracy Profile"

                        // Robust ACPL + Top-1 Match Rate scale bars
                        GridLayout {
                        Layout.fillWidth: true
                        columns: root.gridCols > 1 ? 2 : 1
                        columnSpacing: 12
                        rowSpacing: 12

                        ScaleBar {
                            Layout.fillWidth: true
                            title: "Robust ACPL"
                            value: val("robust_acpl")
                            minValue: 0
                            maxValue: 80
                            subtitle: "Lower = more precise"
                            thresholds: [
                                {value: 15, label: "Engine", color: Theme.riskVeryHigh},
                                {value: 35, label: "GM", color: Theme.riskModerate},
                                {value: 80, label: "Normal", color: Theme.riskLow}
                            ]
                        }

                        ScaleBar {
                            Layout.fillWidth: true
                            title: "Top-1 Match Rate"
                            value: root.controller.top1MatchRate
                            minValue: 0
                            maxValue: 100
                            subtitle: ">55% is suspicious"
                            thresholds: [
                                {value: 35, label: "Normal", color: Theme.riskLow},
                                {value: 55, label: "High", color: Theme.riskModerate},
                                {value: 100, label: "Suspicious", color: Theme.riskVeryHigh}
                            ]
                        }
                    }

                    // Match Rate + Move Quality side by side
                    GridLayout {
                        Layout.fillWidth: true
                        columns: root.gridCols > 1 ? 2 : 1
                        columnSpacing: 12
                        rowSpacing: 12

                        // Match Rate Comparison (top1/2/3)
                        SimpleBarChart {
                            Layout.fillWidth: true
                            title: "Match Rate Comparison"
                            subtitle: "Engine move coincidence by rank"
                            model: [
                                {label: "Top-1", value: root.controller.top1MatchRate, color: "#e74c3c"},
                                {label: "Top-2", value: val("top2_match_rate"), color: "#f39c12"},
                                {label: "Top-3", value: val("top3_match_rate"), color: "#81b64c"}
                            ]
                            maxValue: 100
                        }

                        // Move Quality Distribution (Donut)
                        DonutChart {
                            Layout.fillWidth: true
                            title: "Move Quality Distribution"
                            model: [
                                {label: "Best move", value: val("rank_0_pct"), color: "#81b64c"},
                                {label: "2nd best",  value: val("rank_1_pct"), color: "#5a9e3f"},
                                {label: "3rd best",  value: val("rank_2_pct"), color: "#f39c12"},
                                {label: "Other",     value: val("rank_3plus_pct"), color: "#e74c3c"}
                            ]
                        }
                    }

                    // Blunder Rate + ACPL Distribution
                    GridLayout {
                        Layout.fillWidth: true
                        columns: root.gridCols > 1 ? 2 : 1
                        columnSpacing: 12
                        rowSpacing: 12

                        MetricCard {
                            value: root.controller.blunderRate.toFixed(1) + "%"
                            label: "Blunder Rate"
                            description: "<5% is suspicious"
                            Layout.fillWidth: true
                        }

                        SimpleBarChart {
                            Layout.fillWidth: true
                            title: "ACPL Distribution"
                            subtitle: "Centipawn loss spread"
                            model: [
                                {label: "Min", value: val("acpl_min"), color: Theme.riskLow},
                                {label: "p25", value: val("acpl_p25"), color: Theme.accent},
                                {label: "Med", value: val("acpl_median"), color: Theme.accent},
                                {label: "p75", value: val("acpl_p75"), color: Theme.accent},
                                {label: "Max", value: val("acpl_max"), color: Theme.riskModerate}
                            ]
                        }
                        }
                    }

                    // ═══════════════════════════════════════════
                    // SECTION 3: PHASE ANALYSIS
                    // ═══════════════════════════════════════════

                    SectionGroup {
                        title: "Phase Analysis"

                        // Phase charts side by side
                        GridLayout {
                            Layout.fillWidth: true
                            columns: root.gridCols > 1 ? 2 : 1
                            columnSpacing: 12
                            rowSpacing: 12

                            SimpleBarChart {
                                Layout.fillWidth: true
                                title: "Phase Consistency"
                                subtitle: "Higher middlegame consistency with low overall = more suspicious"
                                model: [
                                    {label: "Opening", value: val("phase_acpl_opening"), color: "#5dade2"},
                                    {label: "Middle",  value: val("phase_acpl_middle"),  color: "#f39c12"},
                                    {label: "Endgame", value: val("phase_acpl_endgame"), color: "#81b64c"}
                                ]
                            }

                            // Phase Consistency Radar
                            RadarChart {
                                Layout.fillWidth: true
                                title: "Phase Consistency Radar"
                                axisMax: 100
                                model: [
                                    {label: "Opening", value: val("phase_acpl_opening")},
                                    {label: "Middlegame", value: val("phase_acpl_middle")},
                                    {label: "Endgame", value: val("phase_acpl_endgame")}
                                ]
                            }
                        }

                        GridLayout {
                            Layout.fillWidth: true
                            columns: root.gridCols
                            columnSpacing: 12
                            rowSpacing: 12

                            MetricCard {
                                value: (val("opening_to_middle_transition") > 0 ? "+" : "") + val("opening_to_middle_transition").toFixed(1) + " cp"
                            label: "Open \u2192 Middle"
                            description: "Quality drop after opening"
                            Layout.fillWidth: true
                        }

                        MetricCard {
                            value: (val("middle_to_endgame_transition") > 0 ? "+" : "") + val("middle_to_endgame_transition").toFixed(1) + " cp"
                            label: "Mid \u2192 Endgame"
                            description: "Quality drop in endgame"
                            Layout.fillWidth: true
                        }

                        MetricCard {
                            value: val("collapse_rate").toFixed(1) + "%"
                            label: "Collapse Rate"
                            description: "Games with phase collapse"
                            Layout.fillWidth: true
                        }
                        }
                    }

                    // ═══════════════════════════════════════════
                    // SECTION 4: BEHAVIORAL PROFILE
                    // ═══════════════════════════════════════════

                    SectionGroup {
                        title: "Behavioral Profile"

                        // Profile badge
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: profileCol.implicitHeight + 24
                            radius: Theme.radius
                            color: Theme.card

                            ColumnLayout {
                                id: profileCol
                                anchors.centerIn: parent
                                width: parent.width - 32
                                spacing: 4

                                Label {
                                    text: profileLabel(val("psychological_profile", "NORMAL_HUMAN"))
                                    font.pixelSize: Theme.fontBody
                                    font.weight: Font.Bold
                                    color: Theme.accent
                                    Layout.alignment: Qt.AlignHCenter
                                }

                                Label {
                                    text: profileDescription(val("psychological_profile", "NORMAL_HUMAN"))
                                    font.pixelSize: Theme.fontCaption
                                    color: Theme.textSecondary
                                    Layout.alignment: Qt.AlignHCenter
                                    horizontalAlignment: Text.AlignHCenter
                                    wrapMode: Text.Wrap
                                    Layout.fillWidth: true
                                }
                            }
                        }

                        GridLayout {
                            Layout.fillWidth: true
                            columns: root.gridCols > 1 ? 2 : 1
                            columnSpacing: 12
                            rowSpacing: 12

                            MetricCard {
                                value: val("tilt_rate").toFixed(2) + "/game"
                                label: "Tilt Rate"
                                description: "Tilt episodes per game"
                                Layout.fillWidth: true
                            }

                            MetricCard {
                                value: val("recovery_rate").toFixed(1) + "%"
                                label: "Recovery Rate"
                                description: "Recovery after errors"
                                Layout.fillWidth: true
                            }

                            MetricCard {
                                value: val("pressure_degradation").toFixed(1) + "%"
                                label: "Pressure Degradation"
                                description: "Degrades under time pressure"
                                Layout.fillWidth: true
                            }

                            MetricCard {
                                value: val("closing_acpl").toFixed(1)
                                label: "Closing ACPL"
                                description: "ACPL in last moves"
                                Layout.fillWidth: true
                            }
                        }
                    }

                    // ═══════════════════════════════════════════
                    // SECTION 5: TEMPORAL ANALYSIS
                    // ═══════════════════════════════════════════

                    SectionGroup {
                        title: "Temporal Analysis"

                        GridLayout {
                            Layout.fillWidth: true
                            columns: root.gridCols > 1 ? 2 : 1
                            columnSpacing: 12
                            rowSpacing: 12

                            ScaleBar {
                                Layout.fillWidth: true
                                title: "Time-Complexity Correlation"
                                value: val("time_complexity_correlation")
                                minValue: -1
                                maxValue: 1
                                subtitle: "Near zero = atypical for humans"
                                thresholds: [
                                    {value: -0.3, label: "Negative", color: Theme.riskModerate},
                                    {value: 0.3, label: "~0", color: Theme.riskVeryHigh},
                                    {value: 1.0, label: "Positive", color: Theme.riskLow}
                                ]
                            }

                            MetricCard {
                                value: val("anomaly_score").toFixed(1) + " / 100"
                                label: "Anomaly Score"
                                description: "Higher = more suspicious time patterns"
                                Layout.fillWidth: true
                            }
                        }

                        // Advanced Suspicion Signals sub-section
                        Label {
                            text: "Advanced Detection Signals"
                            font.pixelSize: Theme.fontLabel
                            font.weight: Font.DemiBold
                            color: Theme.textSecondary
                        }

                        GridLayout {
                            Layout.fillWidth: true
                            columns: root.gridCols
                            columnSpacing: 12
                            rowSpacing: 12

                            MetricCard {
                                value: val("opening_to_middle_improvement").toFixed(1) + " cp"
                                label: "Middlegame Improvement"
                                description: "Sudden quality jump after opening"
                                Layout.fillWidth: true
                            }

                            MetricCard {
                                value: val("variance_drop").toFixed(2)
                                label: "Variance Drop"
                                description: "Becomes mechanical mid-game"
                                Layout.fillWidth: true
                            }

                            MetricCard {
                                value: val("post_pause_improvement").toFixed(1) + " cp"
                                label: "Post-Pause Gain"
                                description: "Quality jump after long pause"
                                Layout.fillWidth: true
                            }
                        }
                    }

                    // ═══════════════════════════════════════════
                    // SECTION 6: PRECISION BURSTS
                    // ═══════════════════════════════════════════

                    SectionGroup {
                        title: "Precision Bursts"

                        GridLayout {
                            Layout.fillWidth: true
                            columns: root.gridCols
                            columnSpacing: 12
                            rowSpacing: 12

                            MetricCard {
                                value: val("precision_burst_mean").toFixed(2)
                                label: "Bursts / Game"
                                description: "Streaks of perfect moves per game"
                                Layout.fillWidth: true
                            }

                            MetricCard {
                                value: val("longest_burst_mean").toFixed(1) + " moves"
                                label: "Longest Burst"
                                description: "Average longest streak"
                                Layout.fillWidth: true
                            }

                            MetricCard {
                                value: val("precision_rate").toFixed(1) + "%"
                                label: "Precision Rate"
                                description: "Best moves in complex positions"
                                Layout.fillWidth: true
                            }
                        }
                    }

                    // ═══════════════════════════════════════════
                    // SECTION 7: HISTORICAL TIMELINES
                    // ═══════════════════════════════════════════

                    SectionGroup {
                        title: "Historical Evolution"
                        visible: val("acpl_timeline", []).length > 1

                        // Historical charts side by side
                        GridLayout {
                            Layout.fillWidth: true
                            columns: root.gridCols > 1 ? 2 : 1
                            columnSpacing: 12
                            rowSpacing: 12

                        // ACPL Evolution
                        LineChart {
                            Layout.fillWidth: true
                            title: "ACPL Evolution"
                            subtitle: "Average centipawn loss over time"
                            series: {
                                var timeline = val("acpl_timeline", []);
                                if (timeline.length < 2) return [];
                                var data = [];
                                for (var i = 0; i < timeline.length; i++)
                                    data.push(timeline[i].acpl || 0);
                                return [{label: "ACPL", color: "#5dade2", data: data}];
                            }
                            xLabels: {
                                var timeline = val("acpl_timeline", []);
                                var labels = [];
                                for (var i = 0; i < timeline.length; i++) {
                                    var d = timeline[i].game_date || "";
                                    // Shorten: "2025-08-15" -> "Aug 15"
                                    if (d.length >= 10) {
                                        var months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
                                        var m = parseInt(d.substring(5, 7)) - 1;
                                        var day = d.substring(8, 10);
                                        labels.push(months[m] + " " + day);
                                    } else {
                                        labels.push(d);
                                    }
                                }
                                return labels;
                            }
                        }

                        // Match Rate Trends
                        LineChart {
                            Layout.fillWidth: true
                            title: "Match Rate Trends"
                            subtitle: "Engine move coincidence over time"
                            visible: val("match_rate_timeline", []).length > 1
                            series: {
                                var timeline = val("match_rate_timeline", []);
                                if (timeline.length < 2) return [];
                                var top1Data = [];
                                var top3Data = [];
                                for (var i = 0; i < timeline.length; i++) {
                                    top1Data.push((timeline[i].top1 || 0) * 100);
                                    top3Data.push((timeline[i].top3 || 0) * 100);
                                }
                                return [
                                    {label: "Top-1 %", color: "#e74c3c", data: top1Data},
                                    {label: "Top-3 %", color: "#81b64c", data: top3Data}
                                ];
                            }
                            xLabels: {
                                var timeline = val("match_rate_timeline", []);
                                var labels = [];
                                for (var i = 0; i < timeline.length; i++) {
                                    var d = timeline[i].game_date || "";
                                    if (d.length >= 10) {
                                        var months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
                                        var m = parseInt(d.substring(5, 7)) - 1;
                                        var day = d.substring(8, 10);
                                        labels.push(months[m] + " " + day);
                                    } else {
                                        labels.push(d);
                                    }
                                }
                                return labels;
                            }
                        }
                        }
                    }

                    // ═══════════════════════════════════════════
                    // SECTION 8: GAME STATISTICS
                    // ═══════════════════════════════════════════

                    SectionGroup {
                        title: "Game Statistics"

                        GridLayout {
                            Layout.fillWidth: true
                            columns: root.gridCols > 1 ? 2 : 1
                            columnSpacing: 12
                            rowSpacing: 12

                            MetricCard {
                                value: root.controller.gamesCount.toString()
                                label: "Games Analyzed"
                                Layout.fillWidth: true
                            }

                            MetricCard {
                                value: val("move_count_mean").toFixed(1)
                                label: "Avg Game Length"
                                description: "Median: " + val("move_count_median").toFixed(1) + " moves"
                                Layout.fillWidth: true
                            }

                            MetricCard {
                                value: root.controller.acplMean.toFixed(1)
                                label: "ACPL Mean"
                                description: "\u03c3 " + val("acpl_std").toFixed(1)
                                Layout.fillWidth: true
                            }

                            MetricCard {
                                value: root.controller.blunderRate.toFixed(1) + "%"
                                label: "Blunder Rate"
                                description: "\u03c3 " + val("blunder_rate_std").toFixed(3)
                                Layout.fillWidth: true
                            }
                        }
                    }

                    // ═══════════════════════════════════════════
                    // SECTION 9: FINAL ASSESSMENT
                    // ═══════════════════════════════════════════

                    SectionGroup {
                        title: "Final Assessment"

                        // Summary cards row
                        GridLayout {
                            Layout.fillWidth: true
                            columns: root.gridColsWide
                            columnSpacing: 12
                            rowSpacing: 12

                            MetricCard {
                                value: val("robust_acpl").toFixed(1)
                                label: "Robust ACPL"
                                description: {
                                    var v = val("robust_acpl");
                                    if (v < 15) return "Engine-like precision";
                                    if (v < 25) return "Unusually precise";
                                    if (v < 35) return "Master/GM level";
                                    if (v < 50) return "Expert level";
                                    return "Normal range";
                                }
                                Layout.fillWidth: true
                            }

                            MetricCard {
                                value: root.controller.top1MatchRate.toFixed(1) + "%"
                                label: "Match Rate"
                                description: {
                                    var v = root.controller.top1MatchRate;
                                    if (v > 55) return "Extremely suspicious";
                                    if (v > 45) return "Suspicious";
                                    if (v > 40) return "GM level";
                                    return "Normal";
                                }
                                Layout.fillWidth: true
                            }

                            MetricCard {
                                value: val("anomaly_score").toFixed(0)
                                label: "Time Anomaly"
                                description: val("anomaly_score") > 40 ? "Suspicious patterns" : "Normal patterns"
                                Layout.fillWidth: true
                            }

                            MetricCard {
                                value: val("collapse_rate").toFixed(0) + "%"
                                label: "Collapse Rate"
                                description: val("collapse_rate") > 50 ? "Selective play" : "Normal"
                                Layout.fillWidth: true
                            }
                        }

                        // Conclusion box
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: conclusionCol.implicitHeight + 32
                            radius: Theme.radius
                            color: Theme.riskBgColor(root.controller.riskLevel)
                            border.color: Theme.riskColor(root.controller.riskLevel)
                            border.width: 1

                            ColumnLayout {
                                id: conclusionCol
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.margins: 16
                                spacing: 8

                                Label {
                                    text: "Analysis Conclusion"
                                    font.pixelSize: Theme.fontLabel
                                    font.weight: Font.DemiBold
                                    color: Theme.textPrimary
                                }

                                Label {
                                    text: {
                                        var rl = root.controller.riskLevel;
                                        if (rl === "VERY HIGH")
                                            return "Analysis indicates VERY HIGH risk of external assistance. Immediate manual investigation and detailed game review recommended.";
                                        if (rl === "HIGH")
                                            return "Analysis indicates HIGH risk. Multiple indicators suggest possible assistance. Manual review of highest-scoring games recommended.";
                                        if (rl === "MODERATE")
                                            return "Analysis indicates MODERATE risk. Some patterns require additional attention. Gather more data if possible before making final decisions.";
                                        return "Analysis indicates LOW risk. Play patterns consistent with natural human behavior for this skill level.";
                                    }
                                    font.pixelSize: Theme.fontSmall
                                    color: Theme.textSecondary
                                    wrapMode: Text.Wrap
                                    Layout.fillWidth: true
                                    lineHeight: 1.4
                                }
                            }
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

                    Item { height: 16 }
                }
            }
        }
    }
}
