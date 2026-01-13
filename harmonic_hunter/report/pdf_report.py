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
    "panel": HexColor("#111318"),
    "panel2": HexColor("#171A21"),
    "muted": HexColor("#A7B0BE"),
    "text": HexColor("#E9EEF6"),
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


def _wrap(
    c: canvas.Canvas,
    x: float,
    y: float,
    text: str,
    max_chars: int = 98,
    lh: int = 13,
    bullet: bool = False,
) -> float:
    """
    Simple wrap by character count. Returns new y.
    """
    if not text:
        return y

    prefix = "• " if bullet else ""
    words = text.split()
    line = ""
    first = True

    for w in words:
        candidate = (line + " " + w).strip()
        limit = max_chars if first else max_chars  # keep consistent
        if len(candidate) <= limit:
            line = candidate
        else:
            c.drawString(x, y, (prefix + line) if first else ("  " + line if bullet else line))
            y -= lh
            line = w
            first = False

    if line:
        c.drawString(x, y, (prefix + line) if first else ("  " + line if bullet else line))
        y -= lh

    return y


def _title(c: canvas.Canvas, x: float, y: float, text: str) -> float:
    c.setFont("Helvetica-Bold", 20)
    c.setFillColor(COLORS["text"])
    c.drawString(x, y, text)
    c.setFillColor(black)
    return y - 26


def _section(c: canvas.Canvas, x: float, y: float, text: str) -> float:
    c.setFont("Helvetica-Bold", 12.5)
    c.setFillColor(COLORS["text"])
    c.drawString(x, y, text)
    c.setFillColor(black)
    return y - 16


def _divider(c: canvas.Canvas, x: float, y: float, w: float) -> float:
    c.setStrokeColor(COLORS["line"])
    c.setLineWidth(1)
    c.line(x, y, x + w, y)
    c.setStrokeColor(black)
    return y - 14


def _safe_img_paths(paths: list[str]) -> list[str]:
    out = []
    for p in paths or []:
        if p and os.path.exists(p):
            out.append(p)
    return out


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

    # =========================
    # PAGE 1 — EXEC SUMMARY
    # =========================
    # Dark header band
    c.setFillColor(COLORS["panel"])
    c.rect(0, H - 120, W, 120, fill=1, stroke=0)
    c.setFillColor(black)

    y = H - 52
    c.setFont("Helvetica-Bold", 22)
    c.setFillColor(COLORS["text"])
    c.drawString(m, y, "Harmonic Hunter")
    c.setFont("Helvetica", 12)
    c.setFillColor(COLORS["muted"])
    c.drawString(m, y - 18, "Power Quality Risk Report")
    c.setFillColor(black)

    # Meta row
    c.setFont("Helvetica", 10.5)
    c.setFillColor(COLORS["muted"])
    c.drawString(m, H - 132, f"Facility: {facility_name}")
    c.drawString(m + 240, H - 132, f"Mode: {report_mode}")
    c.drawString(m + 430, H - 132, datetime.now().strftime("Generated: %Y-%m-%d %H:%M"))
    c.setFillColor(black)

    # Risk panel (light card style)
    panel_y = H - 320
    panel_h = 165
    c.setFillColor(COLORS["panel2"])
    c.roundRect(m, panel_y, W - 2 * m, panel_h, 14, fill=1, stroke=0)
    c.setFillColor(black)

    # Score + band
    c.setFont("Helvetica-Bold", 40)
    c.setFillColor(COLORS["text"])
    c.drawString(m + 18, panel_y + panel_h - 70, f"{risk_score}")
    c.setFont("Helvetica", 12)
    c.setFillColor(COLORS["muted"])
    c.drawString(m + 88, panel_y + panel_h - 52, "/100")
    c.setFillColor(black)

    c.setFont("Helvetica-Bold", 18)
    c.setFillColor(_risk_color(risk_band))
    c.drawString(m + 170, panel_y + panel_h - 58, risk_band)
    c.setFillColor(black)

    # Baseline / change summary
    c.setFont("Helvetica", 10.5)
    c.setFillColor(COLORS["muted"])
    if baseline_score is not None and risk_delta is not None:
        sign = "+" if risk_delta > 0 else ""
        c.drawString(m + 170, panel_y + panel_h - 78, f"Baseline: {baseline_score}/100   Δ {sign}{risk_delta}")
        if change_summary:
            c.drawString(m + 170, panel_y + panel_h - 94, change_summary)
    c.setFillColor(black)

    # Optional delta chart thumbnail (right side)
    if delta_chart_path and os.path.exists(delta_chart_path):
        try:
            img = ImageReader(delta_chart_path)
            thumb_w = 205
            thumb_h = 95
            c.drawImage(
                img,
                W - m - thumb_w,
                panel_y + 18,
                width=thumb_w,
                height=thumb_h,
                preserveAspectRatio=True,
                mask="auto",
            )
        except Exception:
            pass

    # Executive verdict
    vx = m + 18
    vy = panel_y + panel_h - 118
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(COLORS["text"])
    c.drawString(vx, vy, "Executive verdict")
    c.setFillColor(black)
    c.setFont("Helvetica", 11)
    c.setFillColor(COLORS["muted"])
    vy = _wrap(c, vx, vy - 16, executive_verdict, max_chars=88, lh=13)
    c.setFillColor(black)

    # Key observations (bullets)
    ky = panel_y - 24
    c.setFont("Helvetica-Bold", 12.5)
    c.setFillColor(COLORS["text"])
    c.drawString(m, ky, "Key observations")
    c.setFillColor(black)
    ky -= 18

    c.setFont("Helvetica", 11)
    c.setFillColor(black)
    for obs in (key_observations or [])[:4]:
        ky = _wrap(c, m + 8, ky, obs, max_chars=104, lh=13, bullet=True)

    # Why + Recommendations (two columns)
    ky -= 6
    c.setStrokeColor(COLORS["line"])
    c.line(m, ky, W - m, ky)
    c.setStrokeColor(black)
    ky -= 16

    col_w = (W - 2 * m - 18) / 2
    left_x = m
    right_x = m + col_w + 18

    # Why
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(COLORS["text"])
    c.drawString(left_x, ky, "Why you’re seeing this result")
    c.setFillColor(black)
    yy = ky - 16
    c.setFont("Helvetica", 10.8)
    for line in (why_lines or [])[:4]:
        yy = _wrap(c, left_x + 8, yy, line, max_chars=58, lh=12, bullet=True)

    # Next steps
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(COLORS["text"])
    c.drawString(right_x, ky, "Recommended next steps")
    c.setFillColor(black)
    ry = ky - 16
    c.setFont("Helvetica", 10.8)
    for rec in (recommendations or [])[:7]:
        ry = _wrap(c, right_x + 8, ry, rec, max_chars=58, lh=12, bullet=True)

    # Footer disclaimer
    c.setFont("Helvetica-Oblique", 8.8)
    c.setFillColor(COLORS["muted"])
    c.drawString(
        m,
        26,
        "Advisory analysis based on exported PDU/UPS monitoring data. Not a substitute for on-site inspection or licensed engineering assessment.",
    )
    c.setFillColor(black)

    c.showPage()

    # =========================
    # PAGE 2+ — CHARTS (2 per page)
    # =========================
    chart_paths = _safe_img_paths(images or [])
    if report_kind == "executive":
        chart_paths = chart_paths[:3]  # keep concise

    if chart_paths:
        idx = 0
        while idx < len(chart_paths):
            # Page header
            c.setFillColor(COLORS["panel2"])
            c.rect(0, H - 56, W, 56, fill=1, stroke=0)
            c.setFillColor(black)

            c.setFont("Helvetica-Bold", 14)
            c.setFillColor(COLORS["text"])
            c.drawString(m, H - 36, "Charts")
            c.setFillColor(black)

            y = H - 80

            # Two charts per page
            slot_h = 250
            gap = 18

            for _slot in range(2):
                if idx >= len(chart_paths):
                    break

                p = chart_paths[idx]
                idx += 1

                # Title
                c.setFont("Helvetica-Bold", 11)
                c.drawString(m, y, os.path.basename(p).replace("_", " ").replace(".png", ""))
                y -= 10

                try:
                    img = ImageReader(p)
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
    # FINAL — TECHNICAL FINDINGS (full only)
    # =========================
    if report_kind == "full":
        y = H - m
        c.setFont("Helvetica-Bold", 14)
        c.drawString(m, y, "Detailed Technical Findings")
        y -= 18
        c.setFont("Helvetica", 10)

        for line in (summary_lines or []):
            if y < 78:
                c.showPage()
                y = H - m
                c.setFont("Helvetica-Bold", 14)
                c.drawString(m, y, "Detailed Technical Findings (continued)")
                y -= 18
                c.setFont("Helvetica", 10)

            y = _wrap(c, m, y, f"• {line}", max_chars=110, lh=12)

    c.save()
