pragma Singleton
import QtQuick

QtObject {
    // ── Backgrounds ──
    readonly property color background:     "#262522"
    readonly property color surface:        "#312e2b"
    readonly property color card:           "#3a3733"
    readonly property color cardHover:      "#454140"

    // ── Text ──
    readonly property color textPrimary:    "#e8e6e3"
    readonly property color textSecondary:  "#9e9b98"
    readonly property color textDisabled:   "#5a5754"
    readonly property color textOnAccent:   "#ffffff"

    // ── Accent ──
    readonly property color accent:         "#81b64c"
    readonly property color accentHover:    "#6ea23e"
    readonly property color accentSubtle:   "#2d3a22"

    // ── Buttons ──
    readonly property color buttonDanger:       "#e74c3c"
    readonly property color buttonDangerHover:  "#c0392b"

    // ── Input ──
    readonly property color inputBackground:    "#3a3733"
    readonly property color inputBorder:        "#4a4744"
    readonly property color inputFocusBorder:   "#81b64c"
    readonly property color inputDisabled:      "#312e2b"

    // ── Progress ──
    readonly property color progressTrack:  "#4a4744"
    readonly property color progressFill:   "#81b64c"

    // ── Risk levels ──
    readonly property color riskLow:            "#81b64c"
    readonly property color riskModerate:       "#f39c12"
    readonly property color riskHigh:           "#e67e22"
    readonly property color riskVeryHigh:       "#e74c3c"
    readonly property color riskUnknown:        "#9e9b98"

    readonly property color riskLowBg:          "#2d3a22"
    readonly property color riskModerateBg:     "#3d3520"
    readonly property color riskHighBg:         "#3d2e20"
    readonly property color riskVeryHighBg:     "#3d2020"
    readonly property color riskUnknownBg:      "#3a3733"

    // ── Error ──
    readonly property color errorText:       "#e74c3c"
    readonly property color errorBackground: "#3d2020"
    readonly property color errorBorder:     "#6b2a2a"

    // ── Radii ──
    readonly property int radius:       8
    readonly property int radiusLarge:  12
    readonly property int radiusPill:   16

    // ── Font sizes ──
    readonly property int fontTitle:     28
    readonly property int fontHeading:   24
    readonly property int fontBody:      15
    readonly property int fontLabel:     13
    readonly property int fontSmall:     12
    readonly property int fontCaption:   11

    // ── Helpers ──
    function riskColor(level: string) : color {
        switch (level) {
        case "LOW":       return riskLow
        case "MODERATE":  return riskModerate
        case "HIGH":      return riskHigh
        case "VERY HIGH": return riskVeryHigh
        default:          return riskUnknown
        }
    }

    function riskBgColor(level: string) : color {
        switch (level) {
        case "LOW":       return riskLowBg
        case "MODERATE":  return riskModerateBg
        case "HIGH":      return riskHighBg
        case "VERY HIGH": return riskVeryHighBg
        default:          return riskUnknownBg
        }
    }
}
