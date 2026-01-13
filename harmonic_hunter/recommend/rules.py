from __future__ import annotations


def recommendations_fft(thd: float, triplen: float, fifth_pct: float) -> list[str]:
    recs: list[str] = []

    if triplen >= 30:
        recs.append(
            "Priority: Evaluate active harmonic filtering focused on triplen mitigation; verify neutral conductor sizing and thermal margins."
        )
    elif triplen >= 20:
        recs.append(
            "Trend triplen harmonics; review neutral loading during peak IT load windows and plan mitigation if persistent."
        )

    if fifth_pct >= 15:
        recs.append(
            "Priority: Evaluate detuned capacitor banks / filtering tuned for 5th harmonic to reduce capacitor and UPS stress."
        )
    elif fifth_pct >= 12:
        recs.append(
            "Inspect capacitor bank health and reactive compensation settings; elevated 5th harmonic can accelerate wear."
        )

    if thd >= 20:
        recs.append(
            "Priority: Perform a power quality audit; implement mitigation to reduce THD and associated transformer heating."
        )
    elif thd >= 15:
        recs.append(
            "Monitor THD and thermal loading; consider mitigation if persistent during peak periods."
        )

    if not recs:
        recs.append("No urgent mitigation required based on thresholds; continue periodic monitoring.")
    return recs


def recommendations_trend(crest: float, variability: float) -> list[str]:
    recs: list[str] = []

    if crest >= 3.0:
        recs.append(
            "Priority: Investigate non-linear load contributions (UPS rectifiers/SMPS/LED drivers). Consider harmonic filtering feasibility study."
        )
    elif crest >= 2.5:
        recs.append(
            "Crest factor elevated; review load mix and UPS operating mode. Consider targeted power quality measurements."
        )

    if variability >= 40:
        recs.append(
            "Priority: Current variability indicates pulsed load behavior; schedule a power quality capture (true waveform) during peak load."
        )
    elif variability >= 25:
        recs.append(
            "Trend current variability over time; investigate spikes and correlate with load changes and breaker events."
        )

    if not recs:
        recs.append("No urgent mitigation required based on trend indicators; continue periodic monitoring.")
    return recs


def dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out
