from __future__ import annotations

import html
import re
from typing import Any

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from pdf_report import build_research_report_pdf

from services import (
    CancerInsightError,
    compare_profiles,
    display_treatment,
    enrich_with_pubmed,
    fetch_images,
    fetch_research,
    format_value,
    key_findings_from_papers,
    normalize_treatment,
    research_profile,
    rank_evidence,
    search_pubmed_treatment_evidence,
    synthesize_treatment_overview,
    treatment_research_profile,
)

st.set_page_config(
    page_title="Cancer Insight | Research Platform",
    page_icon="✚",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
:root{--navy:#17364D;--navy2:#12344D;--teal:#168F96;--mist:#EEF4F7;--ink:#17364D;--muted:#6E8796;--card:#FFFFFF;--line:#D6E2E8;}
.stApp{background:var(--mist);color:var(--ink)}
[data-testid="stSidebar"]{background:var(--navy2)}
[data-testid="stSidebar"] *{color:white!important}
.block-container{padding-top:2.1rem;max-width:1280px}
.top-brand{display:flex;align-items:center;gap:.75rem;margin:.15rem 0 .35rem}.top-brand .mark{width:38px;height:38px;border-radius:12px;background:linear-gradient(135deg,#17364D,#168F96);color:white;display:flex;align-items:center;justify-content:center;font-weight:900}.top-brand strong{font-size:1.35rem;color:#17364D}.top-brand span{color:#6E8796;font-size:.84rem}
[data-testid="stSidebar"]{min-width:285px!important;max-width:285px!important;width:285px!important;background:linear-gradient(180deg,#12344D 0%,#102E43 100%)!important}
[data-testid="stSidebar"] .block-container{padding-top:1.6rem!important;padding-left:1.05rem!important;padding-right:1.05rem!important}
.sidebar-brand{padding:.25rem .2rem 1.15rem;border-bottom:1px solid rgba(255,255,255,.13);margin-bottom:1rem}.sidebar-brand .brand-row{display:flex;align-items:center;gap:.72rem}.sidebar-brand .mark{width:42px;height:42px;border-radius:12px;background:linear-gradient(135deg,#168F96,#24B7B0);display:flex;align-items:center;justify-content:center;color:white;font-size:1.45rem;font-weight:900;box-shadow:0 8px 20px rgba(0,0,0,.15)}.sidebar-brand strong{font-size:1.25rem;color:white}.sidebar-brand small{display:block;margin-top:.35rem;color:#B9CAD5;font-size:.82rem;line-height:1.35}
[data-testid="stSidebar"] div[role="radiogroup"]{display:flex!important;flex-direction:column!important;gap:.28rem!important}
[data-testid="stSidebar"] div[role="radiogroup"] label{width:100%!important;background:transparent!important;border:1px solid transparent!important;border-radius:12px!important;padding:.52rem .72rem!important;margin:0!important}
[data-testid="stSidebar"] div[role="radiogroup"] label:hover{background:rgba(255,255,255,.07)!important}
[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked){background:linear-gradient(90deg,#168F96,#1BA8A0)!important;border-color:rgba(255,255,255,.08)!important}
[data-testid="stSidebar"] div[role="radiogroup"] label p{color:#EFF7FA!important;font-size:.94rem!important}
[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) p{color:white!important;font-weight:750!important}
.mini-toolbar{background:white;border:1px solid var(--line);border-radius:18px;padding:.7rem 1rem;margin:.15rem 0 1rem;box-shadow:0 6px 18px rgba(23,54,77,.04)}
h1,h2,h3{color:var(--navy)!important;letter-spacing:-.02em}
.hero{padding:2.4rem 2.6rem;border-radius:28px;background:linear-gradient(120deg,#17364D,#168F96);color:white;margin-bottom:1.4rem;box-shadow:0 18px 45px rgba(23,54,77,.12)}
.hero h1{color:white!important;font-size:3.1rem;margin:.2rem 0 .6rem}.hero p{font-size:1.08rem;max-width:850px;color:#EAF7F8}
.eyebrow{text-transform:uppercase;letter-spacing:.14em;font-size:.76rem;font-weight:800;color:#64CDD0}
.paper-card,.panel{background:white;border:1px solid var(--line);border-radius:20px;padding:1.25rem 1.35rem;margin:.8rem 0;box-shadow:0 8px 25px rgba(23,54,77,.05)}
.paper-card h3{margin:.25rem 0 .45rem;font-size:1.14rem}.muted{color:var(--muted);font-size:.92rem}
.badge{display:inline-block;padding:.28rem .65rem;border-radius:999px;font-size:.78rem;font-weight:700;margin:.1rem .3rem .1rem 0}
.free{background:#E0F5EA;color:#166534}.abstract{background:#E7F0FF;color:#2353A2}.link{background:#E8F6F7;color:#126B70}.record{background:#EDF1F3;color:#506673}
.section-note{background:#E4F2F4;border:1px solid #C7E4E6;padding:1rem 1.15rem;border-radius:16px;margin:.7rem 0 1rem}
.finding{background:white;border-left:4px solid var(--teal);border-radius:12px;padding:.75rem .9rem;margin:.45rem 0}
.source-card{background:#F8FBFC;border:1px solid var(--line);border-radius:15px;padding:1rem;margin:.55rem 0}
.disclaimer{margin-top:2rem;padding:1rem 1.2rem;border-radius:16px;background:#FFF7E6;border:1px solid #EFCB7A;color:#614C18}
div[data-testid="stMetric"]{background:white;border:1px solid var(--line);border-radius:18px;padding:1rem 1.1rem;box-shadow:0 7px 20px rgba(23,54,77,.04)}
.stButton>button,.stLinkButton>a{border-radius:12px!important}
@media(max-width:800px){.hero{padding:1.6rem}.hero h1{font-size:2.2rem}.block-container{padding-left:1rem;padding-right:1rem}}
</style>
""",
    unsafe_allow_html=True,
)


def api_key() -> str:
    try:
        return str(st.secrets.get("CANCER_RESEARCH_API_KEY", "")).strip()
    except Exception:
        return ""


def init_state() -> None:
    defaults = {
        "searched": False,
        "cancer_type": "",
        "papers": pd.DataFrame(),
        "treatments": pd.Series(dtype="int64"),
        "images": [],
        "images_for": "",
        "nav_page": "Search",
        "previous_nav_page": "Search",
        "bookmarks": [],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def scroll_to_top() -> None:
    """Reset the Streamlit viewport after the user changes sections."""
    components.html(
        """
        <script>
        (function(){
          const p = window.parent;
          const reset = () => {
            try {
              const candidates = [
                p.document.querySelector('[data-testid="stAppViewContainer"]'),
                p.document.querySelector('[data-testid="stMain"]'),
                p.document.querySelector('section.main'),
                p.document.querySelector('.main')
              ].filter(Boolean);
              candidates.forEach(el => { el.scrollTop = 0; el.scrollTo && el.scrollTo(0,0); });
              p.document.documentElement.scrollTop = 0;
              p.document.body.scrollTop = 0;
              p.scrollTo(0,0);
            } catch(e) {}
          };
          reset();
          setTimeout(reset, 60);
          setTimeout(reset, 180);
        })();
        </script>
        """,
        height=0,
        width=0,
    )


def navigation() -> str:
    pages = ["Search", "Research Papers", "Research Analytics", "Treatment Research", "Compare Treatments", "Cancer Images", "About"]
    with st.sidebar:
        st.markdown(
            '<div class="sidebar-brand"><div class="brand-row"><div class="mark">✚</div><div><strong>Cancer Insight</strong></div></div><small>Evidence-first cancer research explorer</small></div>',
            unsafe_allow_html=True,
        )
        page = st.radio(
            "Navigation",
            pages,
            label_visibility="collapsed",
            key="nav_page",
        )
        if st.session_state.searched:
            p = research_profile(st.session_state.papers)
            st.markdown(
                f"---\n**{html.escape(st.session_state.cancer_type.title())} cancer**  \n{p['paper_count']} papers · {len(st.session_state.treatments)} treatment types  \n{p['free_full_text_count']} free full-text in PMC"
            )
        st.markdown(
            "<div style='margin-top:1.2rem;padding-top:.8rem;border-top:1px solid rgba(255,255,255,.12);font-size:.76rem;line-height:1.45;color:#B9CAD5'>Educational use only. Not medical advice.</div>",
            unsafe_allow_html=True,
        )
    if page != st.session_state.get("previous_nav_page"):
        st.session_state.previous_nav_page = page
        scroll_to_top()
    return page


def run_search(cancer_type: str) -> None:
    papers, treatments = fetch_research(cancer_type, api_key())
    papers = enrich_with_pubmed(papers)
    st.session_state.papers = papers
    st.session_state.treatments = treatments
    st.session_state.images = fetch_images(cancer_type)
    st.session_state.images_for = cancer_type.strip().lower()
    st.session_state.cancer_type = cancer_type.strip()
    st.session_state.searched = True


def require_results() -> bool:
    if not st.session_state.searched:
        st.info("Search for a cancer type first.")
        return False
    return True


def best_title(row: pd.Series) -> str:
    return format_value(row.get("pubmed_title", "")) or format_value(row.get("title", "Untitled paper"))


def best_abstract(row: pd.Series) -> str:
    return format_value(row.get("pubmed_abstract", "")) or format_value(row.get("abstract", ""))


def best_journal(row: pd.Series) -> str:
    return format_value(row.get("pubmed_journal", "")) or format_value(row.get("journal", ""))


def best_date(row: pd.Series) -> str:
    return format_value(row.get("pubmed_date", "")) or format_value(row.get("publicationDate", ""))


def access_badge(row: pd.Series) -> str:
    status = format_value(row.get("access_status", "PubMed record"))
    css = "record"
    if "free full text" in status.lower(): css = "free"
    elif "abstract" in status.lower(): css = "abstract"
    elif "link" in status.lower(): css = "link"
    return f'<span class="badge {css}">{html.escape(status)}</span>'


def citation_text(row: pd.Series) -> str:
    authors = row.get("pubmed_authors", [])
    if isinstance(authors, list) and authors:
        author_text = ", ".join(authors[:6]) + (" et al." if len(authors) > 6 else "")
    else:
        author_text = ""
    title = best_title(row)
    journal = best_journal(row)
    date = best_date(row)
    pmid = format_value(row.get("pubmedId", ""))
    parts = [x for x in [author_text, title, journal, date, f"PMID: {pmid}" if pmid else ""] if x]
    return ". ".join(parts) + "."


def paper_key(row: pd.Series) -> str:
    pmid = format_value(row.get("pubmedId", "")).strip()
    return pmid or best_title(row)


def toggle_bookmark(key: str) -> None:
    saved = list(st.session_state.get("bookmarks", []))
    if key in saved:
        saved.remove(key)
    else:
        saved.append(key)
    st.session_state.bookmarks = saved


def render_paper(row: pd.Series, number: int | None = None, compact: bool = False) -> None:
    title = best_title(row)
    journal = best_journal(row)
    date = best_date(row)
    pmid = format_value(row.get("pubmedId", ""))
    types = row.get("publication_types", [])
    type_text = ", ".join(types[:3]) if isinstance(types, list) else format_value(types)
    authors = row.get("pubmed_authors", [])
    author_text = ", ".join(authors[:6]) + (" et al." if isinstance(authors, list) and len(authors) > 6 else "") if isinstance(authors, list) else format_value(authors)

    label = f"Paper {number}" if number else "Research paper"
    st.markdown(f'<div class="paper-card"><div class="eyebrow">{label}</div><h3>{html.escape(title)}</h3>{access_badge(row)}</div>', unsafe_allow_html=True)
    bits = []
    if journal: bits.append(journal)
    if date: bits.append(date)
    if pmid: bits.append(f"PMID {pmid}")
    if type_text: bits.append(type_text)
    if bits: st.caption(" · ".join(bits))
    if author_text and not compact: st.caption(author_text)

    treatment_value = row.get("treatmentTypes", "")
    if treatment_value not in [None, ""]:
        st.markdown(f"**Treatment tags:** {format_value(treatment_value)}")

    abstract = best_abstract(row)
    if abstract:
        with st.expander("Read abstract"):
            st.write(abstract)

    pubmed = format_value(row.get("pubmed_url", ""))
    pmc = format_value(row.get("pmc_url", ""))
    publisher = format_value(row.get("publisher_url", ""))
    doi = format_value(row.get("doi", ""))
    c1, c2, c3, c4 = st.columns(4)
    if pubmed: c1.link_button("PubMed", pubmed, use_container_width=True)
    if pmc: c2.link_button("Free full text", pmc, use_container_width=True)
    elif publisher: c2.link_button("Full text", publisher, use_container_width=True)
    if doi: c3.link_button("DOI", f"https://doi.org/{doi}", use_container_width=True)
    key = paper_key(row)
    saved = key in st.session_state.get("bookmarks", [])
    if c4.button("★ Saved" if saved else "☆ Save", key=f"bookmark_{number}_{abs(hash(key))}", use_container_width=True):
        toggle_bookmark(key)
        st.rerun()
    if not compact:
        with st.expander("Citation"):
            st.code(citation_text(row), language=None)



def render_metrics(profile: dict[str, Any], treatment_count: int | None = None) -> None:
    cols = st.columns(6 if treatment_count is not None else 5)
    cols[0].metric("Research papers", profile["paper_count"])
    cols[1].metric("Free full text", profile["free_full_text_count"])
    cols[2].metric("Latest year", profile["latest_year"] or "—")
    cols[3].metric("Journals", len(profile["journals"]))
    cols[4].metric("Clinical trials", profile["clinical_trials"])
    if treatment_count is not None:
        cols[5].metric("Treatment types", treatment_count)


def render_sources(sources: list[dict[str, Any]]) -> None:
    if not sources:
        return
    st.markdown("### Sources used for this overview")
    for i, source in enumerate(sources, 1):
        title = format_value(source.get("pubmed_title", "PubMed source"))
        journal = format_value(source.get("pubmed_journal", ""))
        date = format_value(source.get("pubmed_date", ""))
        pmid = format_value(source.get("pubmedId", ""))
        st.markdown(f'<div class="source-card"><strong>[{i}] {html.escape(title)}</strong><br><span class="muted">{html.escape(" · ".join([x for x in [journal,date,f"PMID {pmid}" if pmid else ""] if x]))}</span></div>', unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        if source.get("pubmed_url"): c1.link_button("Open PubMed", source["pubmed_url"], use_container_width=True)
        if source.get("pmc_url"): c2.link_button("Free full text", source["pmc_url"], use_container_width=True)
        doi = format_value(source.get("doi", ""))
        if doi: c3.link_button("DOI", f"https://doi.org/{doi}", use_container_width=True)


def _citation_suffix(item: dict[str, Any]) -> str:
    sources = item.get("sources", []) or ([item.get("source", {})] if item.get("source") else [])
    pmids = []
    for source in sources:
        pmid = format_value(source.get("pubmedId", ""))
        if pmid and pmid not in pmids:
            pmids.append(pmid)
    if not pmids:
        return ""
    return " " + " ".join(f"**[PMID {pmid}]**" for pmid in pmids[:3])


def render_overview(treatment: str, evidence: pd.DataFrame, compact: bool = False) -> None:
    cancer = st.session_state.cancer_type
    overview = synthesize_treatment_overview(cancer, treatment, evidence)
    st.markdown(f"## {display_treatment(treatment)} — {cancer.title()} cancer")
    st.markdown("### What is this treatment?")
    st.write(overview["definition"])
    st.caption("The treatment definition is written in plain language. Cancer-specific statements are synthesized from PubMed-indexed evidence and linked to the supporting PMID(s); they are not copied from article abstracts.")

    sections = [
        ("How it is used", "use"),
        ("Potential benefits and outcomes studied", "benefits"),
        ("Risks, limitations, and challenges", "limitations"),
        ("Current research directions", "directions"),
    ]
    section_limit = 2 if compact else 3
    for title, key in sections:
        items = overview[key][:section_limit]
        if items:
            st.markdown(f"### {title}")
            for item in items:
                suffix = _citation_suffix(item)
                st.markdown(f'<div class="finding">{html.escape(item["text"])}{suffix}</div>', unsafe_allow_html=True)

    if not any(overview[k] for k in ["use", "benefits", "limitations", "directions"]):
        st.info("PubMed did not return enough suitable evidence for a cancer-specific synthesis. The general treatment description is still shown and the source papers remain available below.")
    if not compact:
        render_sources(overview["sources"])


def combined_research_profile(api_papers: pd.DataFrame, evidence: pd.DataFrame) -> dict[str, Any]:
    frames = [df for df in [api_papers, evidence] if df is not None and not df.empty]
    if not frames:
        return research_profile(pd.DataFrame())
    combined = pd.concat(frames, ignore_index=True, sort=False)
    if "pubmedId" in combined.columns:
        key = combined["pubmedId"].fillna("").astype(str)
        with_id = combined[key.str.strip().ne("")].drop_duplicates(subset=["pubmedId"], keep="first")
        without_id = combined[key.str.strip().eq("")]
        combined = pd.concat([with_id, without_id], ignore_index=True, sort=False)
    return research_profile(combined)

def search_page() -> None:
    st.markdown("""
    <section class="hero"><div class="eyebrow" style="color:#7FE1E4">Evidence-first cancer research platform</div><h1>Cancer Insight</h1><p>Search cancer research, read PubMed abstracts, identify free full-text papers, explore treatment evidence, and compare research coverage without hiding the original sources.</p></section>
    """, unsafe_allow_html=True)
    with st.form("search_form"):
        cancer = st.text_input("Cancer type", value=st.session_state.cancer_type, placeholder="For example: lung")
        submitted = st.form_submit_button("Search research", use_container_width=True)
    if submitted:
        try:
            with st.spinner("Searching and enriching papers with PubMed metadata…"):
                run_search(cancer)
            st.success(f"Found {len(st.session_state.papers)} papers for {cancer.title()}.")
        except CancerInsightError as exc:
            st.error(str(exc))

    if st.session_state.searched:
        p = research_profile(st.session_state.papers)
        st.markdown("## Research Highlights")
        render_metrics(p, len(st.session_state.treatments))
        findings = key_findings_from_papers(st.session_state.papers)
        if findings:
            st.markdown("### Key Findings")
            for finding in findings:
                st.markdown(f'<div class="finding">{html.escape(finding)}</div>', unsafe_allow_html=True)
        if not st.session_state.treatments.empty:
            st.markdown("### Treatment research coverage")
            chart_df = st.session_state.treatments.rename("Papers").to_frame()
            st.bar_chart(chart_df, use_container_width=True)


def research_page() -> None:
    st.title("Research Papers")
    if not require_results(): return
    papers = st.session_state.papers.copy()
    st.caption(f"{st.session_state.cancer_type.title()} · enriched with PubMed metadata when a PMID is available")

    c1, c2, c3 = st.columns([2,1,1])
    query = c1.text_input("Search titles, abstracts, journals, or MeSH terms")
    access = c2.selectbox("Access", ["All", "Free full text in PMC", "Has abstract", "Has full-text link"])
    treatment_options = ["All treatments"] + list(st.session_state.treatments.index)
    treatment = c3.selectbox("Treatment", treatment_options)

    pub_types = sorted({pt for values in papers.get("publication_types", pd.Series(dtype=object)) if isinstance(values, list) for pt in values})
    c4, c5, c6 = st.columns(3)
    selected_type = c4.selectbox("Publication type", ["All types"] + pub_types)
    years = sorted({y for row in papers.itertuples() for y in [__import__('services').extract_year(getattr(row, 'pubmed_date', '')) or __import__('services').extract_year(getattr(row, 'publicationDate', ''))] if y}, reverse=True)
    year = c5.selectbox("Year", ["All years"] + years)
    sort_mode = c6.selectbox("Sort by", ["Original relevance", "Newest first", "Free full text first", "Evidence strength"])
    saved_only = st.checkbox("Show saved papers only", value=False)

    filtered = papers.copy()
    if query.strip():
        q = query.lower().strip()
        filtered = filtered[filtered.apply(lambda row: q in " ".join([best_title(row),best_abstract(row),best_journal(row),format_value(row.get("mesh_terms", ""))]).lower(), axis=1)]
    if access == "Free full text in PMC": filtered = filtered[filtered.get("pmc_id", "").fillna("").astype(str).str.strip().ne("")]
    elif access == "Has abstract": filtered = filtered[filtered.apply(lambda r: bool(best_abstract(r)), axis=1)]
    elif access == "Has full-text link": filtered = filtered[filtered.apply(lambda r: bool(format_value(r.get("pmc_url", "")) or format_value(r.get("publisher_url", ""))), axis=1)]
    if treatment != "All treatments":
        target = normalize_treatment(treatment)
        filtered = filtered[filtered["treatmentTypes"].apply(lambda v: target in [normalize_treatment(x) for x in (v if isinstance(v,list) else str(v).split(','))])]
    if selected_type != "All types": filtered = filtered[filtered["publication_types"].apply(lambda v: selected_type in v if isinstance(v,list) else False)]
    if year != "All years": filtered = filtered[filtered.apply(lambda r: str(year) in best_date(r), axis=1)]
    if saved_only:
        saved = set(st.session_state.get("bookmarks", []))
        filtered = filtered[filtered.apply(lambda r: paper_key(r) in saved, axis=1)]
    if sort_mode == "Newest first":
        filtered = filtered.assign(_sort_year=filtered.apply(lambda r: __import__('services').extract_year(best_date(r)) or 0, axis=1)).sort_values("_sort_year", ascending=False).drop(columns=["_sort_year"])
    elif sort_mode == "Free full text first":
        filtered = filtered.assign(_free=filtered.get("pmc_id", "").fillna("").astype(str).str.strip().ne("")).sort_values("_free", ascending=False).drop(columns=["_free"])
    elif sort_mode == "Evidence strength":
        filtered = rank_evidence(filtered)

    report_pdf = build_research_report_pdf(st.session_state.cancer_type, filtered, st.session_state.treatments)
    export_cols = st.columns([1.4, 1])
    export_cols[0].download_button(
        "Download PDF Research Report",
        data=report_pdf,
        file_name=f"cancer_insight_{st.session_state.cancer_type.strip().lower().replace(' ', '_')}_research_report.pdf",
        mime="application/pdf",
        use_container_width=True,
        type="primary",
    )
    csv_columns = [c for c in [
        "pubmedId", "pubmed_title", "pubmed_journal", "pubmed_date", "pubmed_authors",
        "publication_types", "treatmentTypes", "access_status", "pubmed_url", "pmc_url",
        "publisher_url", "doi", "pubmed_abstract"
    ] if c in filtered.columns]
    export_cols[1].download_button(
        "Export Raw Data (CSV)",
        data=filtered[csv_columns].to_csv(index=False).encode("utf-8-sig"),
        file_name=f"cancer_insight_{st.session_state.cancer_type.strip().lower().replace(' ', '_')}_papers.csv",
        mime="text/csv",
        use_container_width=True,
    )

    st.write(f"Showing **{len(filtered)}** papers")
    for i, (_, row) in enumerate(filtered.iterrows(), 1): render_paper(row, i)


def graph_page() -> None:
    st.title("Research Analytics")
    if not require_results(): return
    profile = research_profile(st.session_state.papers)
    render_metrics(profile, len(st.session_state.treatments))
    st.markdown("### Treatment coverage")
    st.bar_chart(st.session_state.treatments.rename("Papers"), use_container_width=True)
    if not profile["year_counts"].empty:
        st.markdown("### Publication timeline")
        st.line_chart(profile["year_counts"].rename("Papers"), use_container_width=True)
    if profile["top_journals"]:
        st.markdown("### Top journals")
        journal_df = pd.DataFrame(profile["top_journals"], columns=["Journal","Papers"]).set_index("Journal")
        st.bar_chart(journal_df, use_container_width=True)
    st.markdown("### Download report")
    report_pdf = build_research_report_pdf(st.session_state.cancer_type, st.session_state.papers, st.session_state.treatments)
    d1, d2 = st.columns([1.4, 1])
    d1.download_button(
        "Download PDF Research Report",
        data=report_pdf,
        file_name=f"cancer_insight_{st.session_state.cancer_type.strip().lower().replace(' ', '_')}_research_report.pdf",
        mime="application/pdf",
        use_container_width=True,
        type="primary",
    )
    d2.download_button(
        "Export Treatment Counts (CSV)",
        data=st.session_state.treatments.rename("paper_count").to_csv().encode("utf-8-sig"),
        file_name=f"{st.session_state.cancer_type.strip().lower().replace(' ', '_')}_treatment_counts.csv",
        mime="text/csv",
        use_container_width=True,
    )


def treatment_page() -> None:
    st.title("Treatment Research")
    if not require_results(): return
    options = list(st.session_state.treatments.index)
    if not options:
        st.warning("No treatment categories were returned for this search.")
        return
    treatment = st.selectbox("Choose a treatment", options)
    with st.spinner("Retrieving treatment-focused PubMed evidence…"):
        evidence = rank_evidence(search_pubmed_treatment_evidence(st.session_state.cancer_type, treatment, limit=14))
    profile = treatment_research_profile(st.session_state.papers, treatment)
    render_overview(treatment, evidence)
    combined_profile = combined_research_profile(profile["papers"], evidence)
    st.markdown("## Research Highlights")
    render_metrics(combined_profile)
    combined_evidence = pd.concat([profile["papers"], evidence], ignore_index=True, sort=False)
    findings = key_findings_from_papers(combined_evidence, treatment)
    if findings:
        st.markdown("### Key Findings")
        for f in findings: st.markdown(f'<div class="finding">{html.escape(f)}</div>', unsafe_allow_html=True)
    st.markdown("## Papers in your Cancer Insight search")
    if profile["papers"].empty: st.info("No API-tagged papers for this treatment were returned in the current search.")
    else:
        for i, (_, row) in enumerate(profile["papers"].iterrows(), 1): render_paper(row, i, compact=True)
    if not evidence.empty:
        st.markdown("## Additional PubMed evidence")
        for i, (_, row) in enumerate(rank_evidence(evidence).head(8).iterrows(), 1): render_paper(row, i, compact=True)


def compare_page() -> None:
    st.title("Compare Treatments")
    if not require_results(): return
    options = list(st.session_state.treatments.index)
    if len(options) < 2:
        st.warning("At least two treatment types are needed for comparison.")
        return
    c1, c2 = st.columns(2)
    t1 = c1.selectbox("First treatment", options, index=0)
    t2 = c2.selectbox("Second treatment", options, index=1)
    if t1 == t2:
        st.warning("Choose two different treatments.")
        return
    with st.spinner("Building sourced PubMed comparison…"):
        e1 = rank_evidence(search_pubmed_treatment_evidence(st.session_state.cancer_type, t1, 12))
        e2 = rank_evidence(search_pubmed_treatment_evidence(st.session_state.cancer_type, t2, 12))
    api1 = treatment_research_profile(st.session_state.papers, t1)
    api2 = treatment_research_profile(st.session_state.papers, t2)
    p1 = combined_research_profile(api1["papers"], e1); p1["treatment"] = t1
    p2 = combined_research_profile(api2["papers"], e2); p2["treatment"] = t2

    st.markdown('<div class="section-note"><strong>How to read this comparison:</strong> the descriptions explain each treatment, while the numbers compare the retrieved research evidence. More papers or newer studies do not mean one treatment is medically better.</div>', unsafe_allow_html=True)

    left, right = st.columns(2)
    with left: render_overview(t1, e1, compact=True)
    with right: render_overview(t2, e2, compact=True)

    st.markdown("## Research Comparison")
    comparison = pd.DataFrame({
        "Measure": ["Unique evidence papers", "Free full text in PMC", "Latest year", "Journals represented", "Clinical trials", "Reviews", "Meta-analyses"],
        display_treatment(t1): [p1["paper_count"], p1["free_full_text_count"], p1["latest_year"] or "—", len(p1["journals"]), p1["clinical_trials"], p1["reviews"], p1["meta_analyses"]],
        display_treatment(t2): [p2["paper_count"], p2["free_full_text_count"], p2["latest_year"] or "—", len(p2["journals"]), p2["clinical_trials"], p2["reviews"], p2["meta_analyses"]],
    })
    st.dataframe(comparison, hide_index=True, use_container_width=True)

    notes = compare_profiles(p1, p2)
    if notes:
        st.markdown("### Comparison Summary")
        for note in notes:
            st.markdown(f'<div class="finding">{html.escape(note)}</div>', unsafe_allow_html=True)

    left, right = st.columns(2)
    with left:
        st.markdown(f"### {display_treatment(t1)} — key research themes")
        for f in key_findings_from_papers(pd.concat([api1["papers"], e1], ignore_index=True, sort=False), t1):
            st.markdown(f'<div class="finding">{html.escape(f)}</div>', unsafe_allow_html=True)
        st.markdown("#### Strongest supporting PubMed evidence")
        for i, (_, row) in enumerate(e1.head(3).iterrows(), 1): render_paper(row, i, compact=True)
    with right:
        st.markdown(f"### {display_treatment(t2)} — key research themes")
        for f in key_findings_from_papers(pd.concat([api2["papers"], e2], ignore_index=True, sort=False), t2):
            st.markdown(f'<div class="finding">{html.escape(f)}</div>', unsafe_allow_html=True)
        st.markdown("#### Strongest supporting PubMed evidence")
        for i, (_, row) in enumerate(e2.head(3).iterrows(), 1): render_paper(row, i, compact=True)

def images_page() -> None:
    st.title("Cancer Images")
    if not require_results(): return
    st.caption(
        f"Scientific and medically relevant images for {st.session_state.cancer_type.title()} cancer are retrieved from Wikimedia Commons. "
        "The gallery prioritizes MRI/CT, pathology, histology, microscopy, tumor specimens, segmentation, and medical diagrams; documents and unrelated photographs are excluded. Source/license metadata is shown when Commons supplies it."
    )
    image_cache_key = "final-medical-v1:" + st.session_state.cancer_type.strip().lower()
    if st.session_state.get("images_for", "") != image_cache_key:
        with st.spinner("Finding medically relevant scientific images…"):
            st.session_state.images = fetch_images(st.session_state.cancer_type)
            st.session_state.images_for = image_cache_key
    images = st.session_state.images
    if not images:
        st.info("No sufficiently relevant scientific images were returned for this cancer type.")
        return
    cols = st.columns(3)
    for i, img in enumerate(images):
        with cols[i % 3]:
            st.image(img["thumbnail"], use_container_width=True)
            st.markdown(f"**{html.escape(img['title'])}**")
            if img.get("description"):
                cleaned = re.sub(r'<[^>]+>', '', img['description']).strip()
                if cleaned:
                    st.caption(cleaned[:180] + ("…" if len(cleaned) > 180 else ""))
            if img.get("license"):
                st.caption(f"License: {re.sub('<[^>]+>','',img['license'])}")
            if img.get("artist"):
                st.caption(f"Creator: {re.sub('<[^>]+>','',img['artist'])[:120]}")
            st.link_button("Open original source", img["original"], use_container_width=True)


def about_page() -> None:
    st.title("About Cancer Insight")
    st.write("Cancer Insight is an educational cancer-research exploration platform. It combines a cancer-research API with PubMed/NCBI metadata so users can inspect papers, research themes, treatment evidence, and free-full-text availability while keeping the original sources visible.")
    st.subheader("How treatment descriptions work")
    st.write("Cancer Insight gives a plain-language definition of the treatment itself, then displays cancer-specific statements extracted from multiple PubMed-indexed abstracts. Each displayed research statement is linked back to identifiable PubMed sources through PMID references and source cards.")
    st.subheader("Access labels")
    st.markdown("- **Free full text in PMC:** freely readable in PubMed Central; this does not automatically mean unrestricted reuse.\n- **Full-text source link:** a publisher or research-source link is available; access rules may vary.\n- **PubMed abstract:** an abstract is available even if Cancer Insight did not identify a free PMC copy.")
    st.subheader("Limitations")
    st.write("Paper counts and research summaries describe retrieved literature, not treatment effectiveness, safety, or suitability for an individual patient. Automated extraction can miss context, so users should read the cited papers and consult qualified healthcare professionals for personal medical decisions.")


init_state()
page = navigation()
{
    "Search": search_page,
    "Research Papers": research_page,
    "Research Analytics": graph_page,
    "Treatment Research": treatment_page,
    "Compare Treatments": compare_page,
    "Cancer Images": images_page,
    "About": about_page,
}[page]()

st.markdown('<div class="disclaimer"><strong>Educational use only.</strong> Cancer Insight does not provide medical diagnosis, individualized treatment recommendations, or professional medical advice.</div>', unsafe_allow_html=True)
