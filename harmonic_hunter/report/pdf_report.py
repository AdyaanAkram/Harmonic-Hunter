from __future__ import annotations

import os
from datetime import datetime
from typing import Optional, Literal

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.colors import black, HexColor
from reportlab.lib.utils import ImageReader

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

def _wrap(c: canvas.Canvas, x: float, y: float, text: str, max_chars: int = 90, lh: int = 13) -> float:
    if not text:
        return y
    words = text.split()
    line = ""
    for w in words:
        candidate = (line + " " + w).strip()
        if len(candidate) <= max_chars:
            line = candidate
        else:
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
    c.setFillColor(black)

    c.setFont("Helvetica", 10.2)
    c.setFillColor(COLORS["muted"])
    c.drawString(m, H - 92, f"Facility: {facility_name}")
    c.drawString(m + 250, H - 92, f"Mode: {report_mode}")
    c.drawString(m + 430, H - 92, datetime.now().strftime("Generated: %Y-%m-%d %H:%M"))
    c.setFillColor(black)

    # ===== Risk card (dark) =====
    panel_y = H - 340
    panel_h = 195
    c.setFillColor(COLORS["panel2"])
    c.roundRect(m, panel_y, W - 2 * m, panel_h, 14, fill=1, stroke=0)
    c.setFillColor(black)

    c.setFont("Helvetica-Bold", 44)
    c.setFillColor(COLORS["text"])
    c.drawString(m + 18, panel_y + panel_h - 84, f"{risk_score}")
    c.setFont("Helvetica", 12)
    c.setFillColor(COLORS["muted"])
    c.drawString(m + 96, panel_y + panel_h - 60, "/100")
    c.setFillColor(black)

    c.setFont("Helvetica-Bold", 18)
    c.setFillColor(_risk_color(risk_band))
    c.drawString(m + 170, panel_y + panel_h - 62, risk_band)
    c.setFillColor(black)

    # Baseline text inside dark card
    c.setFont("Helvetica", 10.6)
    c.setFillColor(COLORS["muted"])
    if baseline_score is not None and risk_delta is not None:
        sign = "+" if risk_delta > 0 else ""
        c.drawString(m + 170, panel_y + panel_h - 86, f"Baseline: {baseline_score}/100   Δ {sign}{risk_delta}")
        if change_summary:
            c.drawString(m + 170, panel_y + panel_h - 102, change_summary)
    c.setFillColor(black)

    # Delta chart thumbnail
    if delta_chart_path and os.path.exists(delta_chart_path):
        try:
            img = ImageReader(delta_chart_path)
            c.drawImage(
                img,
                W - m - 220,
                panel_y + 20,
                width=220,
                height=95,
                preserveAspectRatio=True,
                mask="auto",
            )
        except Exception:
            pass

    # Verdict inside dark card
    vx = m + 18
    vy = panel_y + panel_h - 126
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(COLORS["text"])
    c.drawString(vx, vy, "Executive verdict")
    c.setFillColor(black)

    c.setFont("Helvetica", 11)
    c.setFillColor(COLORS["muted"])
    _wrap(c, vx, vy - 16, executive_verdict, max_chars=62, lh=13)
    c.setFillColor(black)

    # ===== BELOW CARD: WHITE BACKGROUND => BLACK TEXT (FIX) =====
    y = panel_y - 26

    c.setFont("Helvetica-Bold", 12.5)
    c.setFillColor(black)
    c.drawString(m, y, "Key observations")
    y -= 16

    c.setFont("Helvetica", 11)
    c.setFillColor(black)
    for obs in (key_observations or [])[:4]:
        y = _wrap(c, m + 8, y, f"• {obs}", max_chars=106, lh=13)

    y -= 6
    c.setStrokeColor(COLORS["line"])
    c.line(m, y, W - m, y)
    c.setStrokeColor(black)
    y -= 16

    # Two columns on white background
    col_w = (W - 2 * m - 18) / 2
    left_x = m
    right_x = m + col_w + 18

    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(black)
    c.drawString(left_x, y, "Why you’re seeing this result")
    c.drawString(right_x, y, "Recommended next steps")
    y -= 16

    c.setFont("Helvetica", 10.8)
    c.setFillColor(black)

    yy = y
    for line in (why_lines or [])[:4]:
        yy = _wrap(c, left_x + 8, yy, f"• {line}", max_chars=62, lh=12)

    ry = y
    for rec in (recommendations or [])[:7]:
        ry = _wrap(c, right_x + 8, ry, f"• {rec}", max_chars=62, lh=12)

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

            y = _wrap(c, m, y, f"• {line}", max_chars=110, lh=12)

    c.save()
