from __future__ import annotations

from dataclasses import dataclass
from harmonic_hunter.risk.thresholds import THRESHOLDS


@dataclass
class RiskResult:
    score_0_100: int
    band: str
    findings: list[str]
    top_risks: list[str]


def _band(score: int) -> str:
    if score <= 30:
        return "Safe"
    if score <= 60:
        return "Monitor"
    if score <= 80:
        return "Action Required"
    return "Immediate Risk"


def score_risk_fft(thd: float, triplen: float, fifth_pct: float) -> RiskResult:
    findings: list[str] = []
    top: list[str] = []
    score = 0

    # THD (0-40)
    if thd >= THRESHOLDS["THD_CRITICAL"]:
        score += 40
        msg = f"THD is critical ({thd:.1f}%). Elevated transformer heating and nuisance trips are more likely."
        findings.append(msg)
        top.append("High THD → overheating/nuisance trips")
    elif thd >= THRESHOLDS["THD_WARN"]:
        score += 25
        findings.append(f"THD is elevated ({thd:.1f}%). Monitor; mitigation may be needed if persistent.")
        top.append("Elevated THD trend")
    else:
        score += 10

    # Triplen (0-35)
    if triplen >= THRESHOLDS["TRIPLEN_CRITICAL"]:
        score += 35
        msg = f"Triplen index is critical ({triplen:.1f}%). Neutral overheating/fire risk elevated under non-linear loading."
        findings.append(msg)
        top.append("Triplen harmonics → neutral overheating risk")
    elif triplen >= THRESHOLDS["TRIPLEN_WARN"]:
        score += 20
        findings.append(f"Triplen index is high ({triplen:.1f}%). Neutral loading risk rising.")
        top.append("Triplen harmonics trending high")
    else:
        score += 8

    # 5th harmonic (0-25)
    if fifth_pct >= THRESHOLDS["FIFTH_CRITICAL"]:
        score += 25
        findings.append(f"5th harmonic is critical ({fifth_pct:.1f}% of fundamental). Capacitor/UPS stress risk elevated.")
        top.append("5th harmonic → capacitor/UPS stress")
    elif fifth_pct >= THRESHOLDS["FIFTH_WARN"]:
        score += 15
        findings.append(f"5th harmonic is elevated ({fifth_pct:.1f}% of fundamental).")
        top.append("5th harmonic elevated")
    else:
        score += 5

    score = min(100, score)
    band = _band(score)

    # Keep top 3
    top_risks = top[:3] if top else []
    return RiskResult(score_0_100=score, band=band, findings=findings, top_risks=top_risks)


def score_risk_trend(crest: float, variability: float) -> RiskResult:
    findings: list[str] = []
    top: list[str] = []
    score = 0

    # Crest factor (0-55)
    if crest >= THRESHOLDS["CREST_CRITICAL"]:
        score += 55
        findings.append(
            f"Crest factor is critical ({crest:.2f}). Strong evidence of pulsed non-linear currents and higher RMS heating."
        )
        top.append("High crest factor → pulsed non-linear load risk")
    elif crest >= THRESHOLDS["CREST_WARN"]:
        score += 35
        findings.append(f"Crest factor is elevated ({crest:.2f}). Indicates non-linear load behavior.")
        top.append("Elevated crest factor trend")
    else:
        score += 15

    # Variability (0-45)
    if variability >= THRESHOLDS["VARIABILITY_CRITICAL"]:
        score += 45
        findings.append(
            f"Current variability is critical ({variability:.1f}%). Strong non-linear/pulsed load signature; harmonic risk elevated."
        )
        top.append("High variability → harmonic risk signature")
    elif variability >= THRESHOLDS["VARIABILITY_WARN"]:
        score += 25
        findings.append(f"Current variability is elevated ({variability:.1f}%). Non-linear load behavior likely.")
        top.append("Variability trending high")
    else:
        score += 10

    score = min(100, score)
    band = _band(score)
    top_risks = top[:3] if top else []
    return RiskResult(score_0_100=score, band=band, findings=findings, top_risks=top_risks)
