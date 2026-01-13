from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.colors import black, HexColor
from reportlab.lib.utils import ImageReader


COLORS = {
    "safe": HexColor("#2E7D32"),
    "monitor": HexColor("#F9A825"),
    "action": HexColor("#EF6C00"),
    "critical": HexColor("#C62828"),
    "panel": HexColor("#F3F3F3"),
    "muted": HexColor("#555555"),
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


def _wrap(c: canvas.Canvas, x: float, y: float, text: str, max_chars: int = 98, lh: int = 13) -> float:
    """
    Simple word wrap by character count (good enough for your use case).
    Returns the new y after drawing.
    """
    words = (text or "").split()
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


def _section_title(c: canvas.Canvas, x: float, y: float, title: str) -> float:
    c.setFont("Helvetica-Bold", 13)
    c.drawString(x, y, title)
    return y - 16


def build_pdf_report(
    out_pdf: str,
    facility_name: str,
    report_mode: str,
    risk_score: int,
    risk_band: str,
    baseline_score: Optional[int],
    risk_delta: Optional[int],
    executive_verdict: str,
    why_lines: list[str],
    key_observations: list[str],
    recommendations: list[str],
    summary_lines: list[str],
    images: list[str],
    delta_chart_path: Optional[str] = None,
):
    os.makedirs(os.path.dirname(out_pdf), exist_ok=True)

    c = canvas.Canvas(out_pdf, pagesize=letter)
    W, H = letter
    m = 50

    # =========================
    # PAGE 1 — EXEC SUMMARY
    # =========================
    y = H - m

    c.setFont("Helvetica-Bold", 20)
    c.drawString(m, y, "Harmonic Hunter — Power Quality Risk Report")
    y -= 26

    c.setFont("Helvetica", 11)
    c.drawString(m, y, f"Facility: {facility_name}")
    y -= 14
    c.drawString(m, y, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    y -= 14
    c.drawString(m, y, f"Analysis Mode: {report_mode}")
    y -= 18

    # Risk panel
    panel_h = 135
    c.setFillColor(COLORS["panel"])
    c.roundRect(m, y - panel_h, W - 2 * m, panel_h, 10, fill=1, stroke=0)
    c.setFillColor(black)

    # Score
    c.setFont("Helvetica-Bold", 34)
    c.drawString(m + 16, y - 46, f"{risk_score}/100")

    # Band
    c.setFont("Helvetica-Bold", 18)
    c.setFillColor(_risk_color(risk_band))
    c.drawString(m + 185, y - 40, risk_band)
    c.setFillColor(black)

    # Baseline comparison (if provided)
    c.setFont("Helvetica", 10)
    if baseline_score is not None and risk_delta is not None:
        sign = "+" if risk_delta > 0 else ""
        c.setFillColor(COLORS["muted"])
        c.drawString(m + 185, y - 58, f"Baseline: {baseline_score}/100   Δ {sign}{risk_delta}")
        c.setFillColor(black)

    # Executive verdict (wrapped)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(m + 16, y - 78, "Executive verdict")
    c.setFont("Helvetica", 11)
    y_verdict = _wrap(c, m + 16, y - 94, executive_verdict, max_chars=86, lh=13)

    # Key observations (bullets)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(m + 16, y_verdict - 6, "Key observations")
    yy = y_verdict - 20
    c.setFont("Helvetica", 11)
    for obs in (key_observations or [])[:4]:
        yy = _wrap(c, m + 30, yy, f"• {obs}", max_chars=92, lh=13)

    # Optional delta chart thumbnail on page 1 (small, right side)
    if delta_chart_path and os.path.exists(delta_chart_path):
        try:
            img = ImageReader(delta_chart_path)
            # small card bottom-right of panel area
            thumb_w = 210
            thumb_h = 95
            c.drawImage(
                img,
                W - m - thumb_w,
                (y - panel_h) + 10,
                width=thumb_w,
                height=thumb_h,
                preserveAspectRatio=True,
                mask="auto",
            )
        except Exception:
            pass

    # Below panel: Why + Next steps (tight but clean)
    y = (y - panel_h) - 24

    y = _section_title(c, m, y, "Why you’re seeing this result")
    c.setFont("Helvetica", 11)
    for wline in (why_lines or [])[:4]:
        y = _wrap(c, m, y, f"• {wline}", max_chars=105, lh=13)
    y -= 6

    y = _section_title(c, m, y, "Recommended next steps")
    c.setFont("Helvetica", 11)
    for rec in (recommendations or [])[:8]:
        y = _wrap(c, m, y, f"• {rec}", max_chars=105, lh=13)

    # Footer disclaimer
    c.setFont("Helvetica-Oblique", 8.8)
    c.setFillColor(COLORS["muted"])
    c.drawString(
        m,
        28,
        "Advisory analysis based on exported PDU/UPS monitoring data. Not a substitute for on-site inspection or licensed engineering assessment.",
    )
    c.setFillColor(black)

    c.showPage()

    # =========================
    # PAGE(S) 2+ — CHARTS
    # Layout: 2 charts per page, then remaining on next page(s)
    # =========================
    chart_paths = [p for p in (images or []) if p and os.path.exists(p)]

    if chart_paths:
        idx = 0
        while idx < len(chart_paths):
            y = H - m
            c.setFont("Helvetica-Bold", 14)
            c.drawString(m, y, "Charts")
            y -= 18

            # Two slots per page
            slot_h = 240
            gap = 18

            for slot in range(2):
                if idx >= len(chart_paths):
                    break

                p = chart_paths[idx]
                idx += 1

                # Chart title from filename (simple)
                c.setFont("Helvetica-Bold", 11)
                c.drawString(m, y, os.path.basename(p).replace("_", " ").replace(".png", ""))
                y -= 10

                try:
                    img = ImageReader(p)
                    # Fit into a wide, compact rectangle
                    img_w = W - 2 * m
                    img_h = slot_h
                    c.drawImage(
                        img,
                        m,
                        y - img_h,
                        width=img_w,
                        height=img_h,
                        preserveAspectRatio=True,
                        mask="auto",
                    )
                except Exception:
                    c.setFont("Helvetica", 10)
                    c.drawString(m, y - 14, f"(Failed to render image: {p})")

                y -= (slot_h + gap)

            c.showPage()

    # =========================
    # FINAL PAGES — TECHNICAL FINDINGS
    # =========================
    y = H - m
    c.setFont("Helvetica-Bold", 14)
    c.drawString(m, y, "Detailed Technical Findings")
    y -= 18
    c.setFont("Helvetica", 10)

    for line in (summary_lines or []):
        # wrap + page breaks so no cutoff
        if y < 80:
            c.showPage()
            y = H - m
            c.setFont("Helvetica-Bold", 14)
            c.drawString(m, y, "Detailed Technical Findings (continued)")
            y -= 18
            c.setFont("Helvetica", 10)

        y = _wrap(c, m, y, f"• {line}", max_chars=110, lh=12)

    c.save()
