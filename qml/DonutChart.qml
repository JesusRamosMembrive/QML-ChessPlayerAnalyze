import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import ChessAnalyzerQML

Rectangle {
    id: root

    property string title: ""
    property var model: []       // [{label, value, color}]
    property real holeRatio: 0.55

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

        RowLayout {
            Layout.fillWidth: true
            spacing: 16

            // Canvas donut
            Canvas {
                id: canvas
                Layout.preferredWidth: 100
                Layout.preferredHeight: 100

                onPaint: {
                    var ctx = getContext("2d");
                    ctx.reset();
                    var cx = width / 2;
                    var cy = height / 2;
                    var r = Math.min(cx, cy) - 2;
                    var inner = r * root.holeRatio;

                    var total = 0;
                    for (var i = 0; i < root.model.length; i++)
                        total += (root.model[i].value || 0);
                    if (total <= 0) return;

                    var startAngle = -Math.PI / 2;
                    for (var j = 0; j < root.model.length; j++) {
                        var sweep = (root.model[j].value / total) * 2 * Math.PI;
                        ctx.beginPath();
                        ctx.arc(cx, cy, r, startAngle, startAngle + sweep);
                        ctx.arc(cx, cy, inner, startAngle + sweep, startAngle, true);
                        ctx.closePath();
                        ctx.fillStyle = root.model[j].color || Theme.accent;
                        ctx.fill();
                        startAngle += sweep;
                    }
                }

                Connections {
                    target: root
                    function onModelChanged() { canvas.requestPaint(); }
                }
            }

            // Legend
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4

                Repeater {
                    model: root.model

                    RowLayout {
                        spacing: 8
                        Rectangle {
                            width: 10; height: 10; radius: 2
                            color: modelData.color || Theme.accent
                        }
                        Label {
                            text: {
                                var v = modelData.value !== undefined ? Number(modelData.value).toFixed(1) : "0";
                                return (modelData.label || "") + ": " + v + "%";
                            }
                            font.pixelSize: Theme.fontCaption
                            color: Theme.textSecondary
                            Layout.fillWidth: true
                        }
                    }
                }
            }
        }
    }
}
