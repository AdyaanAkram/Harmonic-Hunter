from __future__ import annotations

import os
from datetime import datetime
from typing import Optional, Literal

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.colors import black, HexColor
from reportlab.lib.utils import ImageReader

try:
    from zoneinfo import ZoneInfo  # py3.9+
except Exception:
    ZoneInfo = None  # type: ignore

ReportKind = Literal["executive", "full"]

COLORS = {
    "safe": HexColor("#2E7D32"),
    "monitor": HexColor("#F9A825"),
    "action": HexColor("#EF6C00"),
    "critical": HexColor("#C62828"),
    "panel": HexColor("#0F1218"),
    "panel2": HexColor("#141925"),
    "muted": HexColor("#B6C0CF"),
    "text": HexColor("#F2F5FA"),
    "line": HexColor("#2A2F3A"),
}


def _risk_color(band: str):
    b = (band or "").lower()
    if "safe" in b:
        return COLORS["safe"]
    if "monitor" in b:
        return COLORS["monitor"]
    if "action" in b:
        return COLORS["action"]
    return COLORS["critical"]


def _now_local_str() -> str:
    """
    Timezone-aware timestamp.
    If running in Streamlit Cloud (UTC), you can set HH_TZ=America/Chicago (or your TZ)
    to display local time.
    """
    tzname = os.getenv("HH_TZ") or os.getenv("TZ")
    if tzname and ZoneInfo is not None:
        try:
            dt = datetime.now(ZoneInfo(tzname))
            return dt.strftime("Generated: %Y-%m-%d %H:%M %Z")
        except Exception:
            pass

    # Fallback: system-local (often UTC on cloud, but at least consistent + labeled)
    dt = datetime.now().astimezone()
    return dt.strftime("Generated: %Y-%m-%d %H:%M %Z")


def _wrap_width(
    c: canvas.Canvas,
    x: float,
    y: float,
    text: str,
    max_width: float,
    lh: float = 13,
) -> float:
    """
    Wrap by actual rendered width (NOT character count).
    Returns new y after drawing.
    """
    if not text:
        return y

    words = text.split()
    line = ""
    for w in words:
        candidate = (line + " " + w).strip()
        if c.stringWidth(candidate, c._fontname, c._fontsize) <= max_width:
            line = candidate
        else:
            if line:
                c.drawString(x, y, line)
                y -= lh
            line = w

    if line:
        c.drawString(x, y, line)
        y -= lh

    return y


def _safe_img_paths(paths: list[str]) -> list[str]:
    return [p for p in (paths or []) if p and os.path.exists(p)]


def _pretty_chart_title(path: str) -> str:
    name = os.path.basename(path).replace(".png", "").replace("_", " ")
    if name.startswith("timeseries phase "):
        ph = name.split("timeseries phase ", 1)[1].strip().upper()
        return f"Phase {ph} — Current vs Time"
    if name.startswith("spectrum phase "):
        ph = name.split("spectrum phase ", 1)[1].strip().upper()
        return f"Phase {ph} — Harmonic Spectrum"
    if name == "risk delta":
        return "Baseline vs Current Risk"
    return name.title()


def build_pdf_report(
    out_pdf: str,
    facility_name: str,
    report_mode: str,
    risk_score: int,
    risk_band: str,
    baseline_score: Optional[int],
    risk_delta: Optional[int],
    change_summary: Optional[str],
    executive_verdict: str,
    why_lines: list[str],
    key_observations: list[str],
    recommendations: list[str],
    summary_lines: list[str],
    images: list[str],
    delta_chart_path: Optional[str] = None,
    report_kind: ReportKind = "full",
):
    os.makedirs(os.path.dirname(out_pdf), exist_ok=True)

    c = canvas.Canvas(out_pdf, pagesize=letter)
    W, H = letter
    m = 48

    # ===== Page 1 header band (dark) =====
    c.setFillColor(COLORS["panel"])
    c.rect(0, H - 118, W, 118, fill=1, stroke=0)
    c.setFillColor(black)

    c.setFont("Helvetica-Bold", 22)
    c.setFillColor(COLORS["text"])
    c.drawString(m, H - 52, "Harmonic Hunter")

    c.setFont("Helvetica", 12)
    c.setFillColor(COLORS["muted"])
    c.drawString(m, H - 70, "Power Quality Risk Report")

    # ✅ Header info stacked (no overlap)
    c.setFont("Helvetica", 10.2)
    c.setFillColor(COLORS["muted"])
    c.drawString(m, H - 90, f"Facility: {facility_name}")
    c.drawString(m, H - 104, f"Mode: {report_mode}")
    c.drawString(m, H - 118 + 10, _now_local_str())  # near bottom of band
    c.setFillColor(black)

    # ===== Risk card (dark) =====
    panel_y = H - 340
    panel_h = 195
    c.setFillColor(COLORS["panel2"])
    c.roundRect(m, panel_y, W - 2 * m, panel_h, 14, fill=1, stroke=0)
    c.setFillColor(black)

    # Layout constants
    chart_w = 220
    chart_h = 95
    chart_x = W - m - chart_w
    chart_y = panel_y + 20
    chart_gap = 18

    # Text should not flow under chart area
    safe_text_right = chart_x - chart_gap
    safe_text_width = max(80, safe_text_right - (m + 18))

    # Score
    c.setFont("Helvetica-Bold", 44)
    c.setFillColor(COLORS["text"])
    c.drawString(m + 18, panel_y + panel_h - 84, f"{risk_score}")

    c.setFont("Helvetica", 12)
    c.setFillColor(COLORS["muted"])
    c.drawString(m + 96, panel_y + panel_h - 60, "/100")

    # Risk band
    c.setFont("Helvetica-Bold", 18)
    c.setFillColor(_risk_color(risk_band))
    c.drawString(m + 170, panel_y + panel_h - 62, risk_band)

    # Baseline line + change summary (wrapped to avoid chart overlap)
    if baseline_score is not None and risk_delta is not None:
        c.setFont("Helvetica", 10.6)
        c.setFillColor(COLORS["muted"])
        sign = "+" if risk_delta > 0 else ""
        base_line = f"Baseline: {baseline_score}/100   Δ {sign}{risk_delta}"
        c.drawString(m + 170, panel_y + panel_h - 86, base_line)

        if change_summary:
            # ✅ Wrap within safe area (won’t go under chart)
            c.setFont("Helvetica", 10.6)
            c.setFillColor(COLORS["muted"])
            _wrap_width(
                c,
                m + 170,
                panel_y + panel_h - 102,
                change_summary,
                max_width=max(80, safe_text_right - (m + 170)),
                lh=12,
            )

    # Delta chart thumbnail
    if delta_chart_path and os.path.exists(delta_chart_path):
        try:
            img = ImageReader(delta_chart_path)
            c.drawImage(
                img,
                chart_x,
                chart_y,
                width=chart_w,
                height=chart_h,
                preserveAspectRatio=True,
                mask="auto",
            )
        except Exception:
            pass

    # Executive verdict (wrapped to avoid chart overlap)
    vx = m + 18
    vy = panel_y + panel_h - 126
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(COLORS["text"])
    c.drawString(vx, vy, "Executive verdict")

    c.setFont("Helvetica", 11)
    c.setFillColor(COLORS["muted"])
    _wrap_width(
        c,
        vx,
        vy - 16,
        executive_verdict,
        max_width=safe_text_width,
        lh=13,
    )
    c.setFillColor(black)

    # ===== BELOW CARD (white background, black text) =====
    y = panel_y - 26

    # Key observations
    c.setFont("Helvetica-Bold", 12.5)
    c.setFillColor(black)
    c.drawString(m, y, "Key observations")
    y -= 16

    c.setFont("Helvetica", 11)
    c.setFillColor(black)
    for obs in (key_observations or [])[:4]:
        y = _wrap_width(c, m + 8, y, f"• {obs}", max_width=W - 2 * m - 8, lh=13)

    y -= 6
    c.setStrokeColor(COLORS["line"])
    c.line(m, y, W - m, y)
    c.setStrokeColor(black)
    y -= 18

    # ✅ Stack sections vertically to prevent overlap
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(black)
    c.drawString(m, y, "Why you’re seeing this result")
    y -= 16

    c.setFont("Helvetica", 10.8)
    c.setFillColor(black)
    for line in (why_lines or [])[:4]:
        y = _wrap_width(c, m + 8, y, f"• {line}", max_width=W - 2 * m - 8, lh=12)

    y -= 10
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(black)
    c.drawString(m, y, "Recommended next steps")
    y -= 16

    c.setFont("Helvetica", 10.8)
    c.setFillColor(black)
    for rec in (recommendations or [])[:7]:
        y = _wrap_width(c, m + 8, y, f"• {rec}", max_width=W - 2 * m - 8, lh=12)

    # Footer disclaimer
    c.setFont("Helvetica-Oblique", 8.8)
    c.setFillColor(HexColor("#333333"))
    c.drawString(
        m,
        26,
        "Advisory analysis based on exported PDU/UPS monitoring data. Not a substitute for on-site inspection or licensed engineering assessment.",
    )
    c.setFillColor(black)

    c.showPage()

    # ===== Charts (white background, BLACK text) =====
    chart_paths = _safe_img_paths(images or [])
    if report_kind == "executive":
        chart_paths = chart_paths[:3]

    if chart_paths:
        idx = 0
        while idx < len(chart_paths):
            c.setFont("Helvetica-Bold", 14)
            c.setFillColor(black)
            c.drawString(m, H - 52, "Charts")

            y = H - 80
            slot_h = 250
            gap = 18

            for _ in range(2):
                if idx >= len(chart_paths):
                    break
                p = chart_paths[idx]
                idx += 1

                c.setFont("Helvetica-Bold", 11)
                c.setFillColor(black)
                c.drawString(m, y, _pretty_chart_title(p))
                y -= 10

                try:
                    img = ImageReader(p)
                    c.drawImage(
                        img,
                        m,
                        y - slot_h,
                        width=W - 2 * m,
                        height=slot_h,
                        preserveAspectRatio=True,
                        mask="auto",
                    )
                except Exception:
                    c.setFont("Helvetica", 10)
                    c.setFillColor(black)
                    c.drawString(m, y - 14, f"(Failed to render image: {p})")

                y -= (slot_h + gap)

            c.showPage()

    # ===== Technical findings (full only, BLACK text) =====
    if report_kind == "full":
        y = H - m
        c.setFont("Helvetica-Bold", 14)
        c.setFillColor(black)
        c.drawString(m, y, "Detailed Technical Findings")
        y -= 18
        c.setFont("Helvetica", 10)
        c.setFillColor(black)

        maxw = W - 2 * m
        for line in (summary_lines or []):
            if y < 78:
                c.showPage()
                y = H - m
                c.setFont("Helvetica-Bold", 14)
                c.setFillColor(black)
                c.drawString(m, y, "Detailed Technical Findings (continued)")
                y -= 18
                c.setFont("Helvetica", 10)
                c.setFillColor(black)

            y = _wrap_width(c, m, y, f"• {line}", max_width=maxw, lh=12)

    c.save()
