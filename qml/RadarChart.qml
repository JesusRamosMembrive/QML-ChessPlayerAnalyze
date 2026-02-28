import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import ChessAnalyzerQML

Rectangle {
    id: root

    property string title: ""
    property var model: []       // [{label, value, maxValue, color}]
    property real axisMax: 100

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

        // Radar Canvas
        Canvas {
            id: canvas
            Layout.fillWidth: true
            Layout.preferredHeight: 180

            onPaint: {
                var ctx = getContext("2d");
                ctx.reset();

                var n = root.model.length;
                if (n < 3) return;

                var cx = width / 2;
                var cy = height / 2;
                var r = Math.min(cx, cy) - 30;

                // Draw grid rings (3 levels)
                for (var ring = 1; ring <= 3; ring++) {
                    var rr = r * (ring / 3);
                    ctx.beginPath();
                    ctx.strokeStyle = Theme.progressTrack;
                    ctx.lineWidth = 0.5;
                    for (var i = 0; i <= n; i++) {
                        var angle = (i % n) * (2 * Math.PI / n) - Math.PI / 2;
                        var px = cx + rr * Math.cos(angle);
                        var py = cy + rr * Math.sin(angle);
                        if (i === 0) ctx.moveTo(px, py);
                        else ctx.lineTo(px, py);
                    }
                    ctx.closePath();
                    ctx.stroke();
                }

                // Draw axis lines
                ctx.strokeStyle = Theme.progressTrack;
                ctx.lineWidth = 0.5;
                for (var a = 0; a < n; a++) {
                    var angle2 = a * (2 * Math.PI / n) - Math.PI / 2;
                    ctx.beginPath();
                    ctx.moveTo(cx, cy);
                    ctx.lineTo(cx + r * Math.cos(angle2), cy + r * Math.sin(angle2));
                    ctx.stroke();
                }

                // Draw data polygon
                ctx.beginPath();
                ctx.strokeStyle = Theme.accent;
                ctx.lineWidth = 2;
                ctx.fillStyle = Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.2);

                for (var d = 0; d <= n; d++) {
                    var idx = d % n;
                    var val = Math.min(root.model[idx].value || 0, root.axisMax);
                    var ratio = val / root.axisMax;
                    var angle3 = idx * (2 * Math.PI / n) - Math.PI / 2;
                    var dx = cx + r * ratio * Math.cos(angle3);
                    var dy = cy + r * ratio * Math.sin(angle3);
                    if (d === 0) ctx.moveTo(dx, dy);
                    else ctx.lineTo(dx, dy);
                }
                ctx.closePath();
                ctx.fill();
                ctx.stroke();

                // Draw data points
                for (var p = 0; p < n; p++) {
                    var val2 = Math.min(root.model[p].value || 0, root.axisMax);
                    var ratio2 = val2 / root.axisMax;
                    var angle4 = p * (2 * Math.PI / n) - Math.PI / 2;
                    var ppx = cx + r * ratio2 * Math.cos(angle4);
                    var ppy = cy + r * ratio2 * Math.sin(angle4);

                    ctx.beginPath();
                    ctx.arc(ppx, ppy, 3, 0, 2 * Math.PI);
                    ctx.fillStyle = Theme.accent;
                    ctx.fill();
                }

                // Draw labels
                ctx.fillStyle = Theme.textSecondary;
                ctx.font = "11px sans-serif";
                ctx.textAlign = "center";
                for (var l = 0; l < n; l++) {
                    var angle5 = l * (2 * Math.PI / n) - Math.PI / 2;
                    var lx = cx + (r + 18) * Math.cos(angle5);
                    var ly = cy + (r + 18) * Math.sin(angle5);

                    // Adjust alignment based on position
                    if (Math.abs(Math.cos(angle5)) > 0.3) {
                        ctx.textAlign = Math.cos(angle5) > 0 ? "left" : "right";
                    } else {
                        ctx.textAlign = "center";
                    }

                    var labelText = (root.model[l].label || "") + " (" + Number(root.model[l].value || 0).toFixed(0) + ")";
                    ctx.fillText(labelText, lx, ly + 4);
                }
            }

            Connections {
                target: root
                function onModelChanged() { canvas.requestPaint(); }
            }
        }
    }
}
