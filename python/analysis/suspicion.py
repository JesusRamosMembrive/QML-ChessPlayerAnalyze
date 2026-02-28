"""
Suspicion scoring and cheating detection.

Composite scoring system that combines multiple signals to detect
potentially suspicious play patterns.
"""

from typing import Optional

def calculate_precision_bursts(
    move_evals: list[dict], threshold: int = 10, min_streak: int = 3
) -> dict:
    """
    Detect precision bursts - streaks of consecutive high-quality moves.

    A precision burst is defined as a sequence of consecutive moves where
    each move has cp_loss below the threshold. This can indicate:
    - Strong tactical vision
    - Deep calculation ability
    - Potentially suspicious patterns (if too frequent)

    Args:
        move_evals: List of move evaluations from analyze_game()
        threshold: Maximum cp_loss to be considered "precise" (default: 10)
        min_streak: Minimum consecutive moves to count as burst (default: 3)

    Returns:
        Dict with:
        - burst_count: Number of precision bursts detected
        - longest_burst: Length of longest precision streak
        - total_precise_moves: Total moves meeting threshold
        - precision_rate: Percentage of moves meeting threshold
    """
    if not move_evals:
        return {
            "burst_count": 0,
            "longest_burst": 0,
            "total_precise_moves": 0,
            "precision_rate": 0.0,
        }

    bursts = []
    current_streak = 0
    total_precise = 0

    # FIXED: Handle None cp_loss values
    for move in move_evals:
        cp_loss = move.get("cp_loss")
        if cp_loss is not None and cp_loss <= threshold:
            current_streak += 1
            total_precise += 1
        else:
            if current_streak >= min_streak:
                bursts.append(current_streak)
            current_streak = 0

    # Check final streak
    if current_streak >= min_streak:
        bursts.append(current_streak)

    # Calculate precision_rate only from valid moves
    valid_moves = [m for m in move_evals if m.get("cp_loss") is not None]
    precision_rate = total_precise / len(valid_moves) if valid_moves else 0.0

    return {
        "burst_count": len(bursts),
        "longest_burst": max(bursts) if bursts else 0,
        "total_precise_moves": total_precise,
        "precision_rate": precision_rate,
    }


def calculate_suspicion_score(
    anomaly_score_mean: Optional[float] = None,
    opening_to_middle_transition: Optional[float] = None,
    collapse_rate: Optional[float] = None,
    phase_consistency_middle: Optional[float] = None,
    robust_acpl: Optional[float] = None,
    match_rate_mean: Optional[float] = None,
    # Phase 1A: New signals using already-calculated metrics
    blunder_rate: Optional[float] = None,
    top2_match_rate: Optional[float] = None,
    pressure_degradation: Optional[float] = None,
    tilt_rate: Optional[float] = None,
    # Phase 1B: Advanced temporal detection signals
    opening_to_middle_improvement: Optional[float] = None,
    variance_drop: Optional[float] = None,
    post_pause_improvement: Optional[float] = None,
    # Difficulty & Advanced Detection signals (Signals 14-21)
    cwmr_delta: Optional[float] = None,
    cpa: Optional[float] = None,
    sensitivity: Optional[float] = None,
    ubma: Optional[float] = None,
    difficulty_variance_ratio: Optional[float] = None,
    critical_accuracy_boost: Optional[float] = None,
    oscillation_score: Optional[float] = None,
    mismatch_rate: Optional[float] = None,
    effort_ratio: Optional[float] = None,
) -> dict:
    """
    Calculate composite suspicion score combining multiple signals.

    Score ranges (adjusted for 0-300 scale):
    0-80:    LOW (normal player)
    80-130:  MODERATE (monitor)
    130-180: HIGH (investigate)
    180-300: VERY HIGH (likely cheating)

    Args:
        anomaly_score_mean: Time-complexity anomaly score (0-100)
        opening_to_middle_transition: ACPL increase from opening to middlegame
        collapse_rate: Percentage of games with collapse (0-1)
        phase_consistency_middle: Middlegame consistency score (0-100)
        robust_acpl: Median-based ACPL
        match_rate_mean: Average match rate (0-1)
        blunder_rate: Average blunder rate (0-1) - Phase 1A
        top2_match_rate: Average top-2 match rate (0-1) - Phase 1A
        pressure_degradation: ACPL change under pressure (cp) - Phase 1A
        tilt_rate: Tilt detection rate (0-1) - Phase 1A
        opening_to_middle_improvement: ACPL drop from opening to middle (cp) - Phase 1B
        variance_drop: Std dev drop from opening to middle (cp) - Phase 1B
        post_pause_improvement: ACPL improvement after long pauses (cp) - Phase 1B
        cwmr_delta: CWMR delta (raw_match_rate - cwmr) - Signal 14
        cpa: Critical Position Accuracy (0-1) - Signal 15
        sensitivity: Difficulty Sensitivity (easy_acc - hard_acc) - Signal 16
        ubma: Unique Best Move Accuracy (0-1) - Signal 17
        difficulty_variance_ratio: Variance ratio (easy/hard) - Signal 18
        critical_accuracy_boost: Critical moment accuracy boost - Signal 19
        oscillation_score: Oscillation pattern score (0-100) - Signal 20
        mismatch_rate: Effort-quality mismatch rate (0-1) - Signal 21
        effort_ratio: Effort ratio for human penalty

    Returns:
        Dict with:
        - suspicion_score: Combined score (0-300, capped)
        - confidence: Confidence level (low/medium/high)
        - signals: List of contributing factors
    """
    score = 0
    signals = []
    data_points = 0

    # Signal 1: Time-Complexity Consistency (40 points max)
    # ENGINE DETECTION: Low anomaly = consistent time usage (engine-like)
    # Humans have high anomaly (inconsistent) - think long on easy positions, fast on hard ones
    if anomaly_score_mean is not None:
        data_points += 1
        if anomaly_score_mean < 20:
            score += 40
            signals.append(
                f"Extremely consistent time usage ({anomaly_score_mean:.0f}/100) - engine-like"
            )
        elif anomaly_score_mean < 30:
            score += 30
            signals.append(f"Very consistent time usage ({anomaly_score_mean:.0f}/100)")
        elif anomaly_score_mean < 40:
            score += 20
            signals.append(f"Consistent time usage ({anomaly_score_mean:.0f}/100)")
        elif anomaly_score_mean < 50:
            score += 10
            signals.append(f"Somewhat consistent time usage ({anomaly_score_mean:.0f}/100)")

    # Signal 2: Phase Stability (30 points max)
    # ENGINE DETECTION: Maintains or improves from opening to middlegame (engine-like)
    # Humans typically deteriorate as game gets complex (positive transition)
    if opening_to_middle_transition is not None:
        data_points += 1
        if opening_to_middle_transition < 0:
            score += 30
            signals.append(
                f"Improves opening→middle ({opening_to_middle_transition:.1f} cp) - engine-like"
            )
        elif opening_to_middle_transition < 10:
            score += 20
            signals.append(
                f"Maintains level opening→middle ({opening_to_middle_transition:.1f} cp)"
            )
        elif opening_to_middle_transition < 20:
            score += 10
            signals.append(
                f"Minimal deterioration opening→middle ({opening_to_middle_transition:.1f} cp)"
            )

    # Signal 3: Resilience (20 points max)
    # ENGINE DETECTION: Never collapses (engine-like stability)
    # Humans frequently have collapse games (sudden deterioration)
    if collapse_rate is not None:
        data_points += 1
        if collapse_rate < 0.05:
            score += 20
            signals.append(f"Never collapses ({collapse_rate*100:.0f}%) - engine-like resilience")
        elif collapse_rate < 0.10:
            score += 15
            signals.append(f"Almost never collapses ({collapse_rate*100:.0f}%)")
        elif collapse_rate < 0.20:
            score += 10
            signals.append(f"Rarely collapses ({collapse_rate*100:.0f}%)")

    # Signal 4: Middlegame Consistency (10 points max)
    # ENGINE DETECTION: Very high consistency (engine-like stability)
    # Humans have variable consistency across games
    if phase_consistency_middle is not None:
        data_points += 1
        if phase_consistency_middle > 80:
            score += 10
            signals.append(
                f"Extremely high middlegame consistency ({phase_consistency_middle:.1f}/100) - engine-like"
            )
        elif phase_consistency_middle > 70:
            score += 5
            signals.append(f"Very high middlegame consistency ({phase_consistency_middle:.1f}/100)")

    # Signal 5: Unnatural Accuracy - Low ACPL (40 points max)
    # ENGINE DETECTION: Humans make mistakes, engines don't
    # CRITICAL: This is the strongest signal for engine usage
    # ADJUSTED 2025-11-15: Thresholds calibrated to avoid false positives on mediocre players
    if robust_acpl is not None:
        data_points += 1
        if robust_acpl < 12:
            score += 40
            signals.append(f"Extremely low Robust ACPL ({robust_acpl:.1f}) - engine-like accuracy")
        elif robust_acpl < 15:
            score += 30
            signals.append(f"Very low Robust ACPL ({robust_acpl:.1f}) - suspiciously accurate")
        elif robust_acpl < 20:
            score += 15
            signals.append(f"Low Robust ACPL ({robust_acpl:.1f}) - unusually accurate")
        elif robust_acpl < 25:
            score += 5
            signals.append(f"Good ACPL ({robust_acpl:.1f}) - above average accuracy")

    # Signal 6: Unnatural Consistency - High Match Rate (20 points max)
    # ENGINE DETECTION: Humans vary, engines are consistent
    if match_rate_mean is not None:
        data_points += 1
        if match_rate_mean > 0.55:
            score += 20
            signals.append(
                f"Extremely high match rate ({match_rate_mean*100:.1f}%) - engine-like consistency"
            )
        elif match_rate_mean > 0.50:
            score += 15
            signals.append(
                f"Very high match rate ({match_rate_mean*100:.1f}%) - suspiciously consistent"
            )
        elif match_rate_mean > 0.45:
            score += 10
            signals.append(f"High match rate ({match_rate_mean*100:.1f}%) - unusually consistent")

    # ========== PHASE 1A: NEW SIGNALS (Quick Wins) ==========

    # Signal 7: Low Blunder Rate (15 points max)
    # ENGINE DETECTION: Engines rarely blunder (>100cp loss)
    if blunder_rate is not None:
        data_points += 1
        if blunder_rate < 0.05:  # < 5% blunders
            score += 15
            signals.append(
                f"Very low blunder rate ({blunder_rate*100:.1f}%) - engine-like precision"
            )
        elif blunder_rate < 0.10:  # < 10% blunders
            score += 10
            signals.append(f"Low blunder rate ({blunder_rate*100:.1f}%) - suspiciously accurate")
        elif blunder_rate < 0.15:  # < 15% blunders
            score += 5
            signals.append(f"Below average blunder rate ({blunder_rate*100:.1f}%)")

    # Signal 8: High Top-2 Match Rate (10 points max)
    # ENGINE DETECTION: Chess.com uses Top-2 for precision metric
    if top2_match_rate is not None:
        data_points += 1
        if top2_match_rate > 0.90:  # > 90% top-2
            score += 10
            signals.append(f"Extremely high Top-2 match rate ({top2_match_rate*100:.1f}%)")
        elif top2_match_rate > 0.85:  # > 85% top-2
            score += 7
            signals.append(f"Very high Top-2 match rate ({top2_match_rate*100:.1f}%)")
        elif top2_match_rate > 0.80:  # > 80% top-2
            score += 4
            signals.append(f"High Top-2 match rate ({top2_match_rate*100:.1f}%)")

    # Signal 9: Pressure Degradation (15 points max)
    # ENGINE DETECTION: Humans get worse under pressure (positive degradation)
    #                   Engine users get BETTER under pressure (negative degradation)
    if pressure_degradation is not None:
        data_points += 1
        if pressure_degradation < -5.0:  # Improves significantly
            score += 15
            signals.append(
                f"Improves significantly under pressure ({pressure_degradation:+.1f} cp) - highly suspicious"
            )
        elif pressure_degradation < -2.0:  # Improves moderately
            score += 10
            signals.append(f"Improves under pressure ({pressure_degradation:+.1f} cp) - suspicious")
        elif pressure_degradation < 2.0:  # No degradation (should degrade)
            score += 5
            signals.append(f"Minimal degradation under pressure ({pressure_degradation:+.1f} cp)")

    # Signal 10: Low Tilt Rate (10 points max)
    # ENGINE DETECTION: Engines never tilt, humans frequently do after mistakes
    if tilt_rate is not None:
        data_points += 1
        if tilt_rate < 0.05:  # < 5% tilt
            score += 10
            signals.append(f"Never tilts ({tilt_rate*100:.1f}%) - engine-like consistency")
        elif tilt_rate < 0.10:  # < 10% tilt
            score += 6
            signals.append(f"Rarely tilts ({tilt_rate*100:.1f}%) - unusual consistency")
        elif tilt_rate < 0.15:  # < 15% tilt
            score += 3
            signals.append(f"Low tilt rate ({tilt_rate*100:.1f}%)")

    # ========== PHASE 1B: ADVANCED TEMPORAL DETECTION ==========

    # Signal 11: Sudden Middlegame Improvement (15 points max)
    # ENGINE DETECTION: Opening weak → Middlegame strong = "turns on engine"
    # Note: This is OPPOSITE of Signal 2 (opening_to_middle_transition)
    # Signal 2 detects deterioration (opening good → middle bad)
    # Signal 11 detects improvement (opening bad → middle good)
    if opening_to_middle_improvement is not None:
        data_points += 1
        if opening_to_middle_improvement > 30:  # >30cp improvement
            score += 15
            signals.append(
                f"Dramatic middlegame improvement ({opening_to_middle_improvement:+.1f} cp) - 'turns on engine'"
            )
        elif opening_to_middle_improvement > 20:  # >20cp improvement
            score += 10
            signals.append(
                f"Significant middlegame improvement ({opening_to_middle_improvement:+.1f} cp) - suspicious"
            )
        elif opening_to_middle_improvement > 15:  # >15cp improvement
            score += 5
            signals.append(f"Middlegame improvement ({opening_to_middle_improvement:+.1f} cp)")

    # Signal 12: Consistency Increase (15 points max)
    # ENGINE DETECTION: Variance drops from opening to middlegame = "becomes mechanical"
    # Humans maintain similar variance, engines are consistently precise
    if variance_drop is not None:
        data_points += 1
        if variance_drop > 30:  # >30cp std dev drop
            score += 15
            signals.append(
                f"Dramatic consistency increase ({variance_drop:+.1f} cp std dev drop) - becomes mechanical"
            )
        elif variance_drop > 20:  # >20cp std dev drop
            score += 10
            signals.append(
                f"Significant consistency increase ({variance_drop:+.1f} cp std dev drop) - suspicious"
            )
        elif variance_drop > 15:  # >15cp std dev drop
            score += 5
            signals.append(f"Consistency increase ({variance_drop:+.1f} cp std dev drop)")

    # Signal 13: Post-Pause Improvement (20 points max) - HIGHEST VALUE
    # ENGINE DETECTION: Long pause → perfect move = "consultation"
    # This is the STRONGEST Phase 1B signal
    if post_pause_improvement is not None:
        data_points += 1
        if post_pause_improvement > 20:  # >20cp improvement after pauses
            score += 20
            signals.append(
                f"Dramatic post-pause improvement ({post_pause_improvement:+.1f} cp) - likely consultation"
            )
        elif post_pause_improvement > 15:  # >15cp improvement after pauses
            score += 15
            signals.append(
                f"Significant post-pause improvement ({post_pause_improvement:+.1f} cp) - very suspicious"
            )
        elif post_pause_improvement > 10:  # >10cp improvement after pauses
            score += 10
            signals.append(
                f"Post-pause improvement ({post_pause_improvement:+.1f} cp) - suspicious"
            )
        elif post_pause_improvement > 5:  # >5cp improvement after pauses
            score += 5
            signals.append(f"Moderate post-pause improvement ({post_pause_improvement:+.1f} cp)")

    # ========== DIFFICULTY & ADVANCED DETECTION (Signals 14-21) ==========

    # Signal 14: CWMR Delta (25 points max)
    # ENGINE DETECTION: Engine accuracy is independent of position difficulty
    # cwmr_delta < 0.03 means accuracy doesn't drop in hard positions
    if cwmr_delta is not None:
        data_points += 1
        if cwmr_delta < 0.03:
            score += 25
            signals.append(
                f"CWMR Delta extremely low ({cwmr_delta:.3f}) - accuracy independent of difficulty"
            )
        elif cwmr_delta < 0.06:
            score += 18
            signals.append(f"CWMR Delta very low ({cwmr_delta:.3f}) - suspiciously consistent")
        elif cwmr_delta < 0.10:
            score += 10
            signals.append(f"CWMR Delta low ({cwmr_delta:.3f}) - unusually consistent")

    # Signal 15: Critical Position Accuracy (20 points max)
    # ENGINE DETECTION: Humans score 15-35% in critical positions, engines > 45%
    if cpa is not None:
        data_points += 1
        if cpa > 0.55:
            score += 20
            signals.append(
                f"Extremely high CPA ({cpa*100:.1f}%) - engine-like critical accuracy"
            )
        elif cpa > 0.45:
            score += 15
            signals.append(f"Very high CPA ({cpa*100:.1f}%) - suspiciously accurate in critical positions")
        elif cpa > 0.35:
            score += 8
            signals.append(f"High CPA ({cpa*100:.1f}%) - above expected human range")

    # Signal 16: Difficulty Sensitivity (20 points max)
    # ENGINE DETECTION: Humans drop 0.10-0.40 in hard positions, engines < 0.05
    if sensitivity is not None:
        data_points += 1
        if sensitivity < 0.05:
            score += 20
            signals.append(
                f"Flat difficulty sensitivity ({sensitivity:.3f}) - no accuracy drop in hard positions"
            )
        elif sensitivity < 0.08:
            score += 14
            signals.append(f"Very low sensitivity ({sensitivity:.3f}) - minimal difficulty impact")
        elif sensitivity < 0.12:
            score += 7
            signals.append(f"Low sensitivity ({sensitivity:.3f}) - unusually resilient")

    # Signal 17: UBMA - Unique Best Move Accuracy (15 points max)
    # ENGINE DETECTION: Humans score 30-55%, engines > 75%
    if ubma is not None:
        data_points += 1
        if ubma > 0.80:
            score += 15
            signals.append(
                f"Extremely high UBMA ({ubma*100:.1f}%) - finds unique best moves consistently"
            )
        elif ubma > 0.70:
            score += 10
            signals.append(f"Very high UBMA ({ubma*100:.1f}%) - suspiciously precise")
        elif ubma > 0.55:
            score += 5
            signals.append(f"High UBMA ({ubma*100:.1f}%) - above expected range")

    # Signal 18: Variance Ratio (15 points max)
    # TOGGLE DETECTION: Perfect in hard, normal in easy → ratio > 2.0
    if difficulty_variance_ratio is not None:
        data_points += 1
        if difficulty_variance_ratio > 3.0:
            score += 15
            signals.append(
                f"Extreme variance ratio ({difficulty_variance_ratio:.2f}) - perfect in hard, sloppy in easy"
            )
        elif difficulty_variance_ratio > 2.0:
            score += 10
            signals.append(f"High variance ratio ({difficulty_variance_ratio:.2f}) - suspicious pattern")
        elif difficulty_variance_ratio > 1.5:
            score += 5
            signals.append(f"Elevated variance ratio ({difficulty_variance_ratio:.2f})")

    # Signal 19: Critical Moment Accuracy Boost (20 points max)
    # TOGGLE DETECTION: boost > 0.15 means "turns on engine" in critical moments
    if critical_accuracy_boost is not None:
        data_points += 1
        if critical_accuracy_boost > 0.25:
            score += 20
            signals.append(
                f"Large critical moment boost ({critical_accuracy_boost:+.3f}) - engine activated in key moments"
            )
        elif critical_accuracy_boost > 0.15:
            score += 14
            signals.append(
                f"Significant critical moment boost ({critical_accuracy_boost:+.3f}) - suspicious activation"
            )
        elif critical_accuracy_boost > 0.08:
            score += 7
            signals.append(f"Moderate critical moment boost ({critical_accuracy_boost:+.3f})")

    # Signal 20: Oscillation Pattern (15 points max)
    # TOGGLE DETECTION: Alternating mediocre-perfect windows correlated with difficulty
    if oscillation_score is not None:
        data_points += 1
        if oscillation_score > 40:
            score += 15
            signals.append(
                f"Strong oscillation pattern ({oscillation_score:.1f}/100) - alternating quality by difficulty"
            )
        elif oscillation_score > 25:
            score += 10
            signals.append(f"Moderate oscillation ({oscillation_score:.1f}/100) - suspicious pattern")
        elif oscillation_score > 15:
            score += 5
            signals.append(f"Mild oscillation ({oscillation_score:.1f}/100)")

    # Signal 21: Effort-Quality Mismatch (15 points max)
    # TOGGLE DETECTION: Fast perfect moves in hard positions
    if mismatch_rate is not None:
        data_points += 1
        if mismatch_rate > 0.35:
            score += 15
            signals.append(
                f"High effort mismatch ({mismatch_rate*100:.1f}%) - fast perfect moves in hard positions"
            )
        elif mismatch_rate > 0.25:
            score += 10
            signals.append(f"Elevated effort mismatch ({mismatch_rate*100:.1f}%) - suspicious speed")
        elif mismatch_rate > 0.15:
            score += 5
            signals.append(f"Moderate effort mismatch ({mismatch_rate*100:.1f}%)")

    # ========== PENALTY SIGNALS (Human-Like Patterns) ==========
    # ADDED 2025-11-15: Subtract points when strong human weaknesses are present
    # This prevents weak players from getting high suspicion scores

    # Penalty 1: High Collapse Rate (>30%)
    # HUMAN PATTERN: Weak players frequently collapse (sudden deterioration)
    # Engines maintain consistency and rarely collapse
    if collapse_rate is not None and collapse_rate > 0.30:
        penalty = min(30, int((collapse_rate - 0.30) * 100))
        score -= penalty
        signals.append(
            f"⬇ Frequent collapses ({collapse_rate*100:.0f}%) - human pattern → -{penalty}"
        )

    # Penalty 2: Pressure Degradation (>+10cp worse)
    # HUMAN PATTERN: Weak players get significantly worse under pressure
    # Engines maintain or improve performance under pressure
    if pressure_degradation is not None and pressure_degradation > 10.0:
        penalty = min(20, int(pressure_degradation / 2))
        score -= penalty
        signals.append(
            f"⬇ Degrades under pressure ({pressure_degradation:+.1f}cp) - human pattern → -{penalty}"
        )

    # Penalty 3: High Blunder Rate (>15%)
    # HUMAN PATTERN: Weak players make frequent blunders (>100cp mistakes)
    # Engines rarely make such large errors
    if blunder_rate is not None and blunder_rate > 0.15:
        penalty = min(15, int((blunder_rate - 0.15) * 100))
        score -= penalty
        signals.append(
            f"⬇ High blunder rate ({blunder_rate*100:.1f}%) - human pattern → -{penalty}"
        )

    # Penalty 4: High Difficulty Sensitivity (>0.25)
    # HUMAN PATTERN: Big accuracy drop in hard positions = normal human behavior
    if sensitivity is not None and sensitivity > 0.25:
        penalty = min(15, int((sensitivity - 0.25) * 100))
        score -= penalty
        signals.append(
            f"⬇ High difficulty sensitivity ({sensitivity:.3f}) - human pattern → -{penalty}"
        )

    # Penalty 5: High Effort Ratio (>1.5)
    # HUMAN PATTERN: Thinking much longer on correct hard moves = genuine effort
    if effort_ratio is not None and effort_ratio > 1.5:
        penalty = min(10, int((effort_ratio - 1.5) * 20))
        score -= penalty
        signals.append(
            f"⬇ High effort ratio ({effort_ratio:.2f}) - human thinking pattern → -{penalty}"
        )

    # Ensure score doesn't go negative
    score = max(0, score)

    # Additional context signals (informative only)
    context = []

    # Determine confidence based on data points
    if data_points >= 4:
        confidence = "high"
    elif data_points >= 2:
        confidence = "medium"
    else:
        confidence = "low"

    # Cap score at 300 (21 total signals + difficulty metrics)
    score = min(300, score)

    # Determine risk level (adjusted thresholds for 0-300 scale)
    if score >= 180:
        risk_level = "VERY HIGH"
    elif score >= 130:
        risk_level = "HIGH"
    elif score >= 80:
        risk_level = "MODERATE"
    else:
        risk_level = "LOW"

    return {
        "suspicion_score": round(score, 1),
        "risk_level": risk_level,
        "confidence": confidence,
        "signals": signals,
        "context": context,
        "data_points": data_points,
    }
