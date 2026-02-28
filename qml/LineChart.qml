import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import ChessAnalyzerQML

Rectangle {
    id: root

    property string title: ""
    property string subtitle: ""
    property var series: []      // [{label, color, data: [number]}]
    property var xLabels: []     // string array for x-axis

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

        // Chart area
        Canvas {
            id: canvas
            Layout.fillWidth: true
            Layout.preferredHeight: 140

            onPaint: {
                var ctx = getContext("2d");
                ctx.reset();

                if (root.series.length === 0) return;

                var padL = 40, padR = 10, padT = 10, padB = 24;
                var w = width - padL - padR;
                var h = height - padT - padB;

                // Find global min/max across all series
                var gMin = Infinity, gMax = -Infinity;
                for (var s = 0; s < root.series.length; s++) {
                    var d = root.series[s].data;
                    if (!d) continue;
                    for (var i = 0; i < d.length; i++) {
                        if (d[i] < gMin) gMin = d[i];
                        if (d[i] > gMax) gMax = d[i];
                    }
                }
                if (gMin === Infinity) return;
                var range = gMax - gMin;
                if (range < 1) range = 1;
                // Add 10% padding
                gMin -= range * 0.1;
                gMax += range * 0.1;
                range = gMax - gMin;

                // Grid lines
                ctx.strokeStyle = Theme.progressTrack;
                ctx.lineWidth = 0.5;
                for (var g = 0; g <= 4; g++) {
                    var gy = padT + h - (g / 4) * h;
                    ctx.beginPath();
                    ctx.moveTo(padL, gy);
                    ctx.lineTo(padL + w, gy);
                    ctx.stroke();

                    // Y-axis label
                    var yVal = gMin + (g / 4) * range;
                    ctx.fillStyle = Theme.textDisabled;
                    ctx.font = "10px sans-serif";
                    ctx.textAlign = "right";
                    ctx.fillText(yVal.toFixed(0), padL - 6, gy + 4);
                }

                // Draw each series
                for (var si = 0; si < root.series.length; si++) {
                    var ser = root.series[si];
                    var pts = ser.data;
                    if (!pts || pts.length < 2) continue;

                    ctx.strokeStyle = ser.color || Theme.accent;
                    ctx.lineWidth = 2;
                    ctx.beginPath();

                    for (var pi = 0; pi < pts.length; pi++) {
                        var px = padL + (pi / Math.max(pts.length - 1, 1)) * w;
                        var py = padT + h - ((pts[pi] - gMin) / range) * h;
                        if (pi === 0) ctx.moveTo(px, py);
                        else ctx.lineTo(px, py);
                    }
                    ctx.stroke();
                }

                // X-axis labels (show first, middle, last)
                if (root.xLabels.length > 0) {
                    ctx.fillStyle = Theme.textDisabled;
                    ctx.font = "9px sans-serif";
                    ctx.textAlign = "center";
                    var indices = [0, Math.floor(root.xLabels.length / 2), root.xLabels.length - 1];
                    for (var xi = 0; xi < indices.length; xi++) {
                        var idx = indices[xi];
                        if (idx < root.xLabels.length) {
                            var lx = padL + (idx / Math.max(root.xLabels.length - 1, 1)) * w;
                            ctx.fillText(root.xLabels[idx], lx, height - 4);
                        }
                    }
                }
            }

            Connections {
                target: root
                function onSeriesChanged() { canvas.requestPaint(); }
                function onXLabelsChanged() { canvas.requestPaint(); }
            }
        }

        // Legend
        Row {
            spacing: 16
            Layout.alignment: Qt.AlignHCenter
            visible: root.series.length > 1

            Repeater {
                model: root.series

                Row {
                    spacing: 6
                    Rectangle {
                        width: 12; height: 3; radius: 1
                        color: modelData.color || Theme.accent
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    Label {
                        text: modelData.label || ""
                        font.pixelSize: Theme.fontCaption
                        color: Theme.textSecondary
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
