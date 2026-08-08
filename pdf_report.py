from __future__ import annotations

import io
import re
import unicodedata
from typing import Any

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    KeepTogether,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from services import format_value, key_findings_from_papers, research_profile

NAVY = colors.HexColor("#17364D")
TEAL = colors.HexColor("#168F96")
MIST = colors.HexColor("#EEF4F7")
LINE = colors.HexColor("#D6E2E8")
MUTED = colors.HexColor("#6E8796")
GREEN_BG = colors.HexColor("#E0F5EA")
GREEN_TEXT = colors.HexColor("#166534")


def _safe(value: Any) -> str:
    """Make arbitrary research metadata safe for ReportLab's built-in fonts."""
    text = format_value(value)
    text = (
        text.replace("–", "-")
        .replace("—", "-")
        .replace("−", "-")
        .replace("‑", "-")
        .replace("’", "'")
        .replace("‘", "'")
        .replace("“", '"')
        .replace("”", '"')
        .replace("…", "...")
        .replace("•", "-")
        .replace("·", "-")
    )
    text = unicodedata.normalize("NFKD", text)
    return text.encode("latin-1", "ignore").decode("latin-1").strip()


def _xml(value: Any) -> str:
    text = _safe(value)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _best(row: pd.Series, primary: str, fallback: str = "") -> str:
    value = _safe(row.get(primary, ""))
    if not value and fallback:
        value = _safe(row.get(fallback, ""))
    return value


def _year_from(value: Any) -> str:
    match = re.search(r"(?:19|20)\d{2}", _safe(value))
    return match.group(0) if match else ""


def _footer(canvas, doc) -> None:
    canvas.saveState()
    width, _ = A4
    canvas.setStrokeColor(LINE)
    canvas.line(18 * mm, 15 * mm, width - 18 * mm, 15 * mm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(18 * mm, 9.5 * mm, "Cancer Insight - Educational research report")
    canvas.drawRightString(width - 18 * mm, 9.5 * mm, f"Page {doc.page}")
    canvas.restoreState()


def _paper_access(row: pd.Series) -> str:
    pmc = _safe(row.get("pmc_id", ""))
    if pmc:
        return "Free full text in PMC"
    if _safe(row.get("pubmed_abstract", "")) or _safe(row.get("abstract", "")):
        return "PubMed abstract"
    if _safe(row.get("publisher_url", "")):
        return "Full-text source link"
    return "Research record"


def build_research_report_pdf(
    cancer_type: str,
    papers: pd.DataFrame,
    treatments: pd.Series,
) -> bytes:
    """Build a user-friendly Cancer Insight PDF report in memory."""
    buffer = io.BytesIO()
    doc = BaseDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=22 * mm,
        title=f"Cancer Insight - {_safe(cancer_type).title()} Cancer Research Report",
        author="Cancer Insight",
        subject="Educational cancer research report",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")
    doc.addPageTemplates([PageTemplate(id="report", frames=frame, onPage=_footer)])

    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "CI_Title", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=24,
        leading=29, textColor=NAVY, spaceAfter=5 * mm, alignment=TA_LEFT,
    )
    subtitle = ParagraphStyle(
        "CI_Subtitle", parent=styles["BodyText"], fontName="Helvetica", fontSize=10.5,
        leading=15, textColor=MUTED, spaceAfter=5 * mm,
    )
    h1 = ParagraphStyle(
        "CI_H1", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=16,
        leading=20, textColor=NAVY, spaceBefore=5 * mm, spaceAfter=3 * mm,
    )
    h2 = ParagraphStyle(
        "CI_H2", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=11.5,
        leading=15, textColor=NAVY, spaceBefore=3 * mm, spaceAfter=1.5 * mm,
    )
    body = ParagraphStyle(
        "CI_Body", parent=styles["BodyText"], fontName="Helvetica", fontSize=9.2,
        leading=13.2, textColor=NAVY, spaceAfter=2 * mm,
    )
    small = ParagraphStyle(
        "CI_Small", parent=body, fontSize=8.1, leading=11.5, textColor=MUTED,
    )
    finding_style = ParagraphStyle(
        "CI_Finding", parent=body, leftIndent=5 * mm, firstLineIndent=-3 * mm,
        borderColor=TEAL, borderWidth=0, borderPadding=0,
    )

    profile = research_profile(papers)
    cancer_label = _safe(cancer_type).title()
    story = [
        Paragraph("Cancer Insight", title),
        Paragraph(f"{_xml(cancer_label)} Cancer Research Report", h1),
        Paragraph(
            "Evidence-first research summary generated from the current Cancer Insight search. "
            "Original PubMed, PubMed Central, DOI, and publisher sources remain visible wherever available.",
            subtitle,
        ),
    ]

    # Summary metrics
    metric_data = [
        ["Research papers", "Free full text", "Latest year", "Journals", "Treatment types"],
        [
            str(profile.get("paper_count", 0)),
            str(profile.get("free_full_text_count", 0)),
            str(profile.get("latest_year") or "-"),
            str(len(profile.get("journals", []))),
            str(len(treatments)),
        ],
    ]
    metrics = Table(metric_data, colWidths=[doc.width / 5.0] * 5, rowHeights=[8 * mm, 10 * mm])
    metrics.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 1), (-1, 1), colors.white),
        ("TEXTCOLOR", (0, 1), (-1, 1), NAVY),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 7.8),
        ("FONTSIZE", (0, 1), (-1, 1), 13),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (0, 0), (-1, -1), 0.7, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE),
    ]))
    story += [metrics, Spacer(1, 4 * mm)]

    findings = key_findings_from_papers(papers)
    if findings:
        story.append(Paragraph("Key Findings", h1))
        for item in findings:
            story.append(Paragraph(f"- {_xml(item)}", finding_style))

    if treatments is not None and not treatments.empty:
        story.append(Paragraph("Treatment Research Coverage", h1))
        treatment_rows = [["Treatment", "Papers"]]
        for name, count in treatments.sort_values(ascending=False).items():
            treatment_rows.append([_safe(name).replace("-", " ").title(), str(int(count))])
        t = Table(treatment_rows, colWidths=[doc.width * 0.76, doc.width * 0.24], repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), TEAL),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, MIST]),
            ("GRID", (0, 0), (-1, -1), 0.45, LINE),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (1, 1), (1, -1), "CENTER"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(t)

    if profile.get("top_journals"):
        story.append(Paragraph("Most Represented Journals", h1))
        journal_rows = [["Journal", "Papers"]] + [[_safe(j), str(c)] for j, c in profile["top_journals"]]
        jt = Table(journal_rows, colWidths=[doc.width * 0.82, doc.width * 0.18], repeatRows=1)
        jt.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.2),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, MIST]),
            ("GRID", (0, 0), (-1, -1), 0.4, LINE),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(jt)

    story.append(Paragraph("Research Papers", h1))
    if papers is None or papers.empty:
        story.append(Paragraph("No papers were returned in this search.", body))
    else:
        for index, (_, row) in enumerate(papers.iterrows(), 1):
            paper_title = _best(row, "pubmed_title", "title") or "Untitled paper"
            journal = _best(row, "pubmed_journal", "journal")
            date = _best(row, "pubmed_date", "publicationDate")
            pmid = _safe(row.get("pubmedId", ""))
            authors = row.get("pubmed_authors", [])
            if isinstance(authors, list):
                author_text = ", ".join(_safe(a) for a in authors[:8] if _safe(a))
                if len(authors) > 8:
                    author_text += " et al."
            else:
                author_text = _safe(authors)
            treatment_tags = _safe(row.get("treatmentTypes", ""))
            pub_types = row.get("publication_types", [])
            pub_type_text = ", ".join(_safe(x) for x in pub_types[:4]) if isinstance(pub_types, list) else _safe(pub_types)
            abstract = _best(row, "pubmed_abstract", "abstract")
            access = _paper_access(row)

            header = Paragraph(f"{index}. {_xml(paper_title)}", h2)
            meta_parts = [x for x in [journal, date, f"PMID {pmid}" if pmid else "", pub_type_text] if x]
            elements = [header]
            if meta_parts:
                elements.append(Paragraph(_xml(" | ".join(meta_parts)), small))
            if author_text:
                elements.append(Paragraph(_xml(author_text), small))
            access_color = GREEN_TEXT if "Free full text" in access else NAVY
            elements.append(Paragraph(f'<font color="#{access_color.hexval()[2:]}"><b>{_xml(access)}</b></font>', small))
            if treatment_tags:
                elements.append(Paragraph(f"<b>Treatment tags:</b> {_xml(treatment_tags)}", body))
            if abstract:
                short_abs = abstract[:1200] + ("..." if len(abstract) > 1200 else "")
                elements.append(Paragraph(f"<b>Abstract:</b> {_xml(short_abs)}", small))

            links = []
            pubmed_url = _safe(row.get("pubmed_url", ""))
            pmc_url = _safe(row.get("pmc_url", ""))
            publisher_url = _safe(row.get("publisher_url", ""))
            doi = _safe(row.get("doi", ""))
            if pubmed_url:
                links.append(f'<link href="{_xml(pubmed_url)}" color="#168F96">PubMed</link>')
            if pmc_url:
                links.append(f'<link href="{_xml(pmc_url)}" color="#168F96">PMC free full text</link>')
            elif publisher_url:
                links.append(f'<link href="{_xml(publisher_url)}" color="#168F96">Full-text source</link>')
            if doi:
                links.append(f'<link href="https://doi.org/{_xml(doi)}" color="#168F96">DOI</link>')
            if links:
                elements.append(Paragraph(" | ".join(links), small))
            elements += [Spacer(1, 2 * mm), HRFlowable(width="100%", thickness=0.6, color=LINE), Spacer(1, 2 * mm)]
            story.append(KeepTogether(elements))

    story.append(Paragraph("Sources and Access", h1))
    story.append(Paragraph(
        "PubMed IDs (PMIDs), PubMed Central links, DOI links, and publisher links shown in this report come from the research metadata returned by Cancer Insight. "
        "A 'Free full text in PMC' label means the article was identified as freely readable in PubMed Central; it does not automatically mean unrestricted copyright reuse.",
        body,
    ))
    story.append(Paragraph("Educational Use Disclaimer", h1))
    story.append(Paragraph(
        "Cancer Insight is an educational research-exploration platform. It does not provide medical diagnosis, individualized treatment recommendations, or professional medical advice. "
        "Research summaries and paper counts describe the retrieved literature and should not be interpreted as proof that one treatment is safer, more effective, or appropriate for a particular person.",
        body,
    ))

    doc.build(story)
    return buffer.getvalue()
