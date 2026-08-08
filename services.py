from __future__ import annotations

from collections import Counter
from html import unescape
import math
import re
from typing import Any, Iterable
import xml.etree.ElementTree as ET

import pandas as pd
import requests

RESEARCH_URL = "https://www.curecancerwithai.com/api/v1/research"
PUBMED_EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
PUBMED_ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
COMMONS_URL = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "CancerInsight/4.0 educational-research-project"


class CancerInsightError(RuntimeError):
    """Readable application error intended for display in the UI."""


def format_value(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value)


def _safe_text(element: ET.Element | None) -> str:
    if element is None:
        return ""
    return "".join(element.itertext()).strip()


def normalize_treatment(value: str) -> str:
    value = (value or "").strip().lower().replace("_", " ").replace("-", " ")
    value = re.sub(r"\s+", " ", value)
    aliases = {
        "radiation therapy": "radiation",
        "radiotherapy": "radiation",
        "chemo": "chemotherapy",
        "targeted therapies": "targeted therapy",
        "targeted-therapy": "targeted therapy",
        "hormonal therapy": "hormone therapy",
        "immunotherapies": "immunotherapy",
    }
    return aliases.get(value, value)


def display_treatment(value: str) -> str:
    return normalize_treatment(value).title()


def _iter_treatment_values(value: Any) -> Iterable[str]:
    if isinstance(value, list):
        for item in value:
            yield str(item)
    elif value is not None:
        text = str(value).strip()
        if text:
            for item in re.split(r"[,;|]", text):
                if item.strip():
                    yield item.strip()


def fetch_research(cancer_type: str, api_key: str) -> tuple[pd.DataFrame, pd.Series]:
    cancer_type = cancer_type.strip()
    if not cancer_type:
        raise CancerInsightError("Please enter a cancer type.")
    if not api_key:
        raise CancerInsightError(
            "The research API key has not been configured. Add it to .streamlit/secrets.toml first."
        )

    try:
        response = requests.get(
            RESEARCH_URL,
            headers={"Authorization": f"Bearer {api_key}", "User-Agent": USER_AGENT},
            params={"cancerType": cancer_type},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.Timeout as exc:
        raise CancerInsightError("The research service took too long to respond. Please try again.") from exc
    except requests.RequestException as exc:
        raise CancerInsightError("The research service could not be reached right now.") from exc
    except ValueError as exc:
        raise CancerInsightError("The research service returned an unreadable response.") from exc

    papers = payload.get("data", [])
    if not papers:
        raise CancerInsightError("No research papers were found for that search.")

    papers_df = pd.DataFrame(papers)
    treatment_values: list[str] = []
    if "treatmentTypes" in papers_df.columns:
        for value in papers_df["treatmentTypes"]:
            treatment_values.extend(
                normalize_treatment(item)
                for item in _iter_treatment_values(value)
                if item.strip()
            )
    treatment_counts = pd.Series(treatment_values, dtype="object").value_counts()
    return papers_df, treatment_counts



# --- Cancer-specific research relevance filtering ---------------------------------
CANCER_TEXT_ALIASES: dict[str, list[str]] = {
    "breast": ["breast cancer", "breast carcinoma", "breast neoplasm", "mammary carcinoma", "mammary cancer", "triple-negative breast", "triple negative breast", "tnbc", "her2-positive breast", "her2 positive breast", "ductal carcinoma", "lobular carcinoma", "dcis"],
    "lung": ["lung cancer", "lung carcinoma", "lung neoplasm", "pulmonary carcinoma", "lung adenocarcinoma", "non-small cell lung", "non small cell lung", "nsclc", "small cell lung", "sclc"],
    "brain": ["brain cancer", "brain tumor", "brain tumour", "brain neoplasm", "glioma", "glioblastoma", "astrocytoma", "oligodendroglioma", "ependymoma", "medulloblastoma", "brainstem glioma", "cns tumor", "cns tumour"],
    "prostate": ["prostate cancer", "prostate carcinoma", "prostatic carcinoma", "prostate adenocarcinoma"],
    "colon": ["colon cancer", "colon carcinoma", "colonic carcinoma", "colorectal cancer", "colorectal carcinoma"],
    "colorectal": ["colorectal cancer", "colorectal carcinoma", "colon cancer", "rectal cancer", "rectal carcinoma"],
    "pancreatic": ["pancreatic cancer", "pancreatic carcinoma", "pancreatic adenocarcinoma", "pancreas cancer"],
    "pancreas": ["pancreatic cancer", "pancreatic carcinoma", "pancreatic adenocarcinoma", "pancreas cancer"],
    "liver": ["liver cancer", "liver carcinoma", "hepatic cancer", "hepatocellular carcinoma", "hcc"],
    "kidney": ["kidney cancer", "renal cancer", "renal cell carcinoma", "rcc", "kidney carcinoma"],
    "ovarian": ["ovarian cancer", "ovarian carcinoma", "ovary cancer"],
    "ovary": ["ovarian cancer", "ovarian carcinoma", "ovary cancer"],
    "cervical": ["cervical cancer", "cervical carcinoma", "cervix cancer"],
    "cervix": ["cervical cancer", "cervical carcinoma", "cervix cancer"],
    "thyroid": ["thyroid cancer", "thyroid carcinoma", "papillary thyroid carcinoma", "follicular thyroid carcinoma", "medullary thyroid carcinoma"],
    "bladder": ["bladder cancer", "bladder carcinoma", "urothelial carcinoma"],
    "stomach": ["stomach cancer", "gastric cancer", "gastric carcinoma"],
    "gastric": ["stomach cancer", "gastric cancer", "gastric carcinoma"],
    "esophageal": ["esophageal cancer", "oesophageal cancer", "esophageal carcinoma", "oesophageal carcinoma"],
    "skin": ["skin cancer", "melanoma", "cutaneous carcinoma", "basal cell carcinoma", "cutaneous squamous cell carcinoma"],
    "melanoma": ["melanoma", "malignant melanoma", "skin cancer"],
    "leukemia": ["leukemia", "leukaemia", "acute myeloid leukemia", "acute lymphoblastic leukemia", "chronic myeloid leukemia", "chronic lymphocytic leukemia"],
    "lymphoma": ["lymphoma", "hodgkin lymphoma", "non-hodgkin lymphoma", "non hodgkin lymphoma"],
}

def _cancer_base(cancer_type: str) -> str:
    value = re.sub(r"\s+", " ", (cancer_type or "").strip().lower())
    return re.sub(r"\bcancer\b", "", value).strip()

def cancer_text_aliases(cancer_type: str) -> list[str]:
    base = _cancer_base(cancer_type)
    if not base:
        return []
    aliases = [f"{base} cancer", f"{base} carcinoma", f"{base} neoplasm"]
    aliases.extend(CANCER_TEXT_ALIASES.get(base, []))
    return list(dict.fromkeys(a.strip().lower() for a in aliases if a.strip()))

def _normalized_text(value: Any) -> str:
    if isinstance(value, list):
        value = " ".join(str(x) for x in value)
    text = unescape(str(value or "")).lower()
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()

def cancer_relevance_score(row: pd.Series, cancer_type: str) -> int:
    aliases = cancer_text_aliases(cancer_type)
    base = _cancer_base(cancer_type)
    if not aliases or not base:
        return 0
    title = _normalized_text(row.get("pubmed_title", "")) or _normalized_text(row.get("title", ""))
    abstract = _normalized_text(row.get("pubmed_abstract", "")) or _normalized_text(row.get("abstract", ""))
    mesh = _normalized_text(row.get("mesh_terms", ""))
    cancer_meta = _normalized_text(row.get("cancerTypes", ""))
    score = 0
    title_hits = [a for a in aliases if a in title]
    abstract_hits = [a for a in aliases if a in abstract]
    mesh_hits = [a for a in aliases if a in mesh]
    if title_hits:
        score += 14 + min(len(title_hits) - 1, 2) * 2
    elif re.search(rf"\b{re.escape(base)}\b", title) and any(k in title for k in ["cancer", "carcinoma", "tumor", "tumour", "neoplasm"]):
        score += 10
    if abstract_hits:
        score += 6 + min(len(abstract_hits) - 1, 2)
    if mesh_hits:
        score += 6
    if any(a in cancer_meta for a in aliases) or re.search(rf"\b{re.escape(base)}\b", cancer_meta):
        score += 10
    if re.search(rf"\b{re.escape(base)}\b", mesh) and any(k in mesh for k in ["neoplasm", "neoplasms", "carcinoma", "tumor", "tumour"]):
        score += 5
    other_sites = {"breast", "lung", "brain", "prostate", "colon", "colorectal", "rectal", "pancreatic", "pancreas", "liver", "kidney", "ovarian", "ovary", "cervical", "cervix", "thyroid", "bladder", "gastric", "stomach", "esophageal", "oesophageal", "melanoma", "leukemia", "leukaemia", "lymphoma"}
    if not title_hits:
        for other in other_sites - {base}:
            if re.search(rf"\b{re.escape(other)}\b", title) and any(k in title for k in ["cancer", "carcinoma", "adenocarcinoma", "malignancy", "tumor", "tumour"]):
                score -= 8
                break
    return score

def filter_cancer_relevant_papers(papers_df: pd.DataFrame, cancer_type: str, min_score: int = 10) -> pd.DataFrame:
    if papers_df is None or papers_df.empty:
        return pd.DataFrame() if papers_df is None else papers_df.copy()
    filtered = papers_df.copy()
    filtered["_cancer_relevance"] = filtered.apply(lambda row: cancer_relevance_score(row, cancer_type), axis=1)
    filtered = filtered[filtered["_cancer_relevance"] >= min_score].copy()
    filtered["_relevance_year"] = filtered.apply(lambda row: extract_year(row.get("pubmed_date", "")) or extract_year(row.get("publicationDate", "")) or 0, axis=1)
    filtered = filtered.sort_values(["_cancer_relevance", "_relevance_year"], ascending=[False, False])
    return filtered.drop(columns=["_cancer_relevance", "_relevance_year"], errors="ignore")

def search_pubmed_cancer_papers(cancer_type: str, limit: int = 40) -> pd.DataFrame:
    aliases = cancer_text_aliases(cancer_type)
    base = _cancer_base(cancer_type)
    if not aliases or not base:
        return pd.DataFrame()
    chosen = aliases[:8]
    title_abs = " OR ".join(f'"{a}"[Title/Abstract]' for a in chosen)
    mesh_query = f'"{base} neoplasms"[MeSH Terms]'
    term = f"({title_abs} OR {mesh_query})"
    try:
        response = requests.get(PUBMED_ESEARCH_URL, headers={"User-Agent": USER_AGENT}, params={"db": "pubmed", "term": term, "retmode": "json", "retmax": max(limit, 20), "sort": "pub date", "tool": "CancerInsight"}, timeout=25)
        response.raise_for_status()
        ids = response.json().get("esearchresult", {}).get("idlist", [])
    except (requests.RequestException, ValueError):
        return pd.DataFrame()
    if not ids:
        return pd.DataFrame()
    metadata = fetch_pubmed_metadata(ids)
    rows: list[dict[str, Any]] = []
    for pmid in ids:
        info = metadata.get(pmid)
        if not info:
            continue
        row = {"pubmedId": pmid, **info, "treatmentTypes": [], "cancerTypes": [cancer_type]}
        row["pubmed_url"] = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        pmc_id = str(info.get("pmc_id", "") or "").strip()
        row["pmc_url"] = f"https://pmc.ncbi.nlm.nih.gov/articles/{pmc_id}/" if pmc_id else ""
        row["publisher_url"] = ""
        row["access_status"] = "Free full text in PMC" if pmc_id else ("PubMed abstract" if info.get("pubmed_abstract") else "PubMed record")
        rows.append(row)
    result = pd.DataFrame(rows)
    return filter_cancer_relevant_papers(result, cancer_type, min_score=10)

# --- Treatment inference ---------------------------------------------------------
# The source research API sometimes leaves treatmentTypes empty even when a paper
# clearly studies a treatment.  These rules add conservative, explainable tags
# from PubMed titles/abstracts/MeSH terms while preserving any original API tags.
TREATMENT_INFERENCE_RULES: dict[str, dict[str, list[str]]] = {
    "chemotherapy": {
        "strong": [
            "chemotherapy", "chemotherapeutic", "chemoimmunotherapy", "chemoradiation",
            "docetaxel", "paclitaxel", "carboplatin", "cisplatin", "doxorubicin",
            "cyclophosphamide", "anthracycline", "capecitabine", "gemcitabine",
            "fluorouracil", "5-fluorouracil", "5-fu", "eribulin", "vinorelbine",
        ],
        "support": ["cytotoxic chemotherapy", "platinum-based", "platinum based"],
    },
    "immunotherapy": {
        "strong": [
            "immunotherapy", "immune checkpoint", "checkpoint inhibitor", "pd-1 inhibitor",
            "pd-l1 inhibitor", "pd-1/pd-l1", "pembrolizumab", "nivolumab", "atezolizumab",
            "durvalumab", "ipilimumab", "car-t", "car t-cell", "car t cell",
            "immune checkpoint blockade", "immunostimulant", "immunomodulatory",
        ],
        "support": ["anti-pd-1", "anti-pd-l1", "checkpoint blockade"],
    },
    "targeted therapy": {
        "strong": [
            "targeted therapy", "targeted treatment", "tyrosine kinase inhibitor", "tki",
            "cdk4/6 inhibitor", "cdk 4/6 inhibitor", "parp inhibitor", "alk inhibitor",
            "egfr inhibitor", "braf inhibitor", "mek inhibitor", "her2-targeted",
            "her2 targeted", "trastuzumab", "pertuzumab", "lapatinib", "tucatinib",
            "olaparib", "talazoparib", "palbociclib", "ribociclib", "abemaciclib",
            "antibody-drug conjugate", "antibody drug conjugate",
        ],
        "support": ["molecularly targeted", "targeted agent", "kinase inhibitor"],
    },
    "hormone therapy": {
        "strong": [
            "hormone therapy", "hormonal therapy", "endocrine therapy", "antiestrogen",
            "anti-estrogen", "tamoxifen", "aromatase inhibitor", "letrozole", "anastrozole",
            "exemestane", "fulvestrant", "androgen deprivation", "antiandrogen",
        ],
        "support": ["estrogen receptor blockade", "endocrine treatment"],
    },
    "radiation": {
        "strong": [
            "radiotherapy", "radiation therapy", "radiation treatment", "chemoradiation",
            "irradiation", "stereotactic radiotherapy", "stereotactic body radiation",
            "sbrt", "brachytherapy", "proton therapy",
        ],
        "support": ["radiation dose", "radiation oncology"],
    },
    "surgery": {
        "strong": [
            "surgery", "surgical treatment", "surgical resection", "tumor resection",
            "tumour resection", "mastectomy", "lumpectomy", "breast-conserving surgery",
            "breast conserving surgery", "lobectomy", "pneumonectomy", "colectomy",
            "prostatectomy", "hepatectomy", "pancreatectomy", "lymph node dissection",
        ],
        "support": ["operative treatment", "resection margin", "surgical procedure"],
    },
    "stem cell transplant": {
        "strong": [
            "stem cell transplant", "stem-cell transplant", "stem cell transplantation",
            "hematopoietic stem cell transplantation", "haematopoietic stem cell transplantation",
            "hsct", "bone marrow transplant", "bone marrow transplantation",
        ],
        "support": ["autologous transplant", "allogeneic transplant"],
    },
}

def _contains_treatment_term(text: str, term: str) -> bool:
    text = text or ""
    term = term.lower().strip()
    if not term:
        return False
    # Short abbreviations need word boundaries so e.g. 'tki' does not match inside another word.
    if re.fullmatch(r"[a-z0-9+-]{2,6}", term):
        return re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text) is not None
    return term in text

def infer_treatment_tags(row: pd.Series) -> list[str]:
    """Return conservative treatment tags inferred from a paper plus original API tags.

    Title and MeSH evidence are trusted most. Abstract-only mentions require repeated,
    independent treatment signals so a paper is not tagged merely because it lists a
    therapy in background/context text.
    """
    existing = [normalize_treatment(x) for x in _iter_treatment_values(row.get("treatmentTypes", [])) if str(x).strip()]
    tags: list[str] = list(dict.fromkeys(existing))

    title = _normalized_text(row.get("pubmed_title", "")) or _normalized_text(row.get("title", ""))
    abstract = _normalized_text(row.get("pubmed_abstract", "")) or _normalized_text(row.get("abstract", ""))
    mesh = _normalized_text(row.get("mesh_terms", ""))

    # Photodynamic therapy uses light + photosensitizers; it is not radiation therapy.
    # Prevent the word "radiation" elsewhere in an abstract from turning a PDT paper
    # into a radiation-therapy paper.
    is_photodynamic = any(term in title or term in mesh for term in (
        "photodynamic therapy", "photodynamic treatment", "photodynamic cancer therapy",
        "photodynamic", "photosensitizer", "photosensitiser",
    ))

    for treatment, groups in TREATMENT_INFERENCE_RULES.items():
        if treatment in tags:
            continue
        if treatment == "radiation" and is_photodynamic:
            continue

        title_score = 0
        mesh_score = 0
        abstract_strong_hits = 0
        abstract_support_hits = 0

        for term in groups.get("strong", []):
            if _contains_treatment_term(title, term):
                title_score += 5
            if _contains_treatment_term(mesh, term):
                mesh_score += 4
            if _contains_treatment_term(abstract, term):
                abstract_strong_hits += 1

        for term in groups.get("support", []):
            if _contains_treatment_term(title, term):
                title_score += 4
            if _contains_treatment_term(mesh, term):
                mesh_score += 3
            if _contains_treatment_term(abstract, term):
                abstract_support_hits += 1

        # One clear title/MeSH signal is enough. Abstract-only inference is deliberately
        # stricter: require at least two strong terms, or one strong + two support terms.
        title_or_mesh = (title_score + mesh_score) >= 4
        abstract_only = (abstract_strong_hits >= 2) or (abstract_strong_hits >= 1 and abstract_support_hits >= 2)
        if title_or_mesh or abstract_only:
            tags.append(treatment)

    return tags

def enrich_treatment_tags(papers_df: pd.DataFrame) -> pd.DataFrame:
    if papers_df is None or papers_df.empty:
        return pd.DataFrame() if papers_df is None else papers_df.copy()
    tagged = papers_df.copy()
    tagged["treatmentTypes"] = tagged.apply(infer_treatment_tags, axis=1)
    return tagged

def treatment_counts_from_papers(papers_df: pd.DataFrame) -> pd.Series:
    values: list[str] = []
    if papers_df is not None and not papers_df.empty and "treatmentTypes" in papers_df.columns:
        for value in papers_df["treatmentTypes"]:
            values.extend(normalize_treatment(item) for item in _iter_treatment_values(value) if item.strip())
    return pd.Series(values, dtype="object").value_counts()

def _is_retracted_or_retraction_notice(row: pd.Series) -> bool:
    """True for PubMed retractions/retraction notices that should not enter evidence sets."""
    title = _normalized_text(row.get("pubmed_title", "")) or _normalized_text(row.get("title", ""))
    types = row.get("publication_types", [])
    if isinstance(types, list):
        type_text = " ".join(str(x).lower() for x in types)
    else:
        type_text = _normalized_text(types)
    if "retraction notice" in type_text or "retracted publication" in type_text:
        return True
    if title.startswith("[retracted]") or title.startswith("retracted:") or "[retracted]" in title:
        return True
    return False

def exclude_retracted_papers(papers_df: pd.DataFrame) -> pd.DataFrame:
    if papers_df is None or papers_df.empty:
        return pd.DataFrame() if papers_df is None else papers_df.copy()
    return papers_df[~papers_df.apply(_is_retracted_or_retraction_notice, axis=1)].copy()

def build_relevant_research_set(papers_df: pd.DataFrame, cancer_type: str, target_count: int = 20) -> pd.DataFrame:
    # Retractions are excluded before relevance ranking so they cannot displace valid evidence.
    cleaned = exclude_retracted_papers(papers_df)
    relevant = filter_cancer_relevant_papers(cleaned, cancer_type, min_score=10)
    if len(relevant) < target_count:
        supplemental = search_pubmed_cancer_papers(cancer_type, limit=max(40, target_count * 2))
        supplemental = exclude_retracted_papers(supplemental)
        if not supplemental.empty:
            combined = pd.concat([relevant, supplemental], ignore_index=True, sort=False)
            if "pubmedId" in combined.columns:
                ids = combined["pubmedId"].fillna("").astype(str).str.strip()
                with_id = combined[ids.ne("")].drop_duplicates(subset=["pubmedId"], keep="first")
                without_id = combined[ids.eq("")]
                combined = pd.concat([with_id, without_id], ignore_index=True, sort=False)
            combined = exclude_retracted_papers(combined)
            relevant = filter_cancer_relevant_papers(combined, cancer_type, min_score=10)
    relevant = relevant.head(target_count).reset_index(drop=True)
    return enrich_treatment_tags(relevant)

def _parse_pubmed_date(article: ET.Element) -> str:
    for path in [
        ".//Article/ArticleDate",
        ".//Journal/JournalIssue/PubDate",
        ".//PubmedData/History/PubMedPubDate[@PubStatus='pubmed']",
    ]:
        date_el = article.find(path)
        if date_el is None:
            continue
        year = _safe_text(date_el.find("Year"))
        month = _safe_text(date_el.find("Month"))
        day = _safe_text(date_el.find("Day"))
        medline = _safe_text(date_el.find("MedlineDate"))
        if medline:
            return medline
        parts = [part for part in [year, month, day] if part]
        if parts:
            return " ".join(parts)
    return ""


def _parse_pubmed_article(article: ET.Element) -> tuple[str, dict[str, Any]] | None:
    pmid = _safe_text(article.find(".//MedlineCitation/PMID"))
    if not pmid:
        return None

    article_node = article.find(".//MedlineCitation/Article")
    title = _safe_text(article_node.find("ArticleTitle") if article_node is not None else None)
    journal = _safe_text(article_node.find("Journal/Title") if article_node is not None else None)

    abstract_parts: list[str] = []
    if article_node is not None:
        for part in article_node.findall("Abstract/AbstractText"):
            label = part.attrib.get("Label", "").strip()
            text = _safe_text(part)
            if text:
                abstract_parts.append(f"{label}: {text}" if label else text)
    abstract = "\n\n".join(abstract_parts)

    authors: list[str] = []
    if article_node is not None:
        for author in article_node.findall("AuthorList/Author"):
            collective = _safe_text(author.find("CollectiveName"))
            if collective:
                authors.append(collective)
                continue
            fore = _safe_text(author.find("ForeName"))
            last = _safe_text(author.find("LastName"))
            name = " ".join(part for part in [fore, last] if part)
            if name:
                authors.append(name)

    doi = ""
    pmc = ""
    for article_id in article.findall(".//PubmedData/ArticleIdList/ArticleId"):
        id_type = article_id.attrib.get("IdType", "").lower()
        value = _safe_text(article_id)
        if id_type == "doi":
            doi = value
        elif id_type == "pmc":
            pmc = value

    publication_types = [
        _safe_text(item)
        for item in article.findall(".//MedlineCitation/Article/PublicationTypeList/PublicationType")
        if _safe_text(item)
    ]
    mesh_terms = [
        _safe_text(item.find("DescriptorName"))
        for item in article.findall(".//MedlineCitation/MeshHeadingList/MeshHeading")
        if _safe_text(item.find("DescriptorName"))
    ]

    return pmid, {
        "pubmed_title": unescape(title),
        "pubmed_abstract": unescape(abstract),
        "pubmed_journal": unescape(journal),
        "pubmed_authors": authors,
        "pubmed_date": _parse_pubmed_date(article),
        "doi": doi,
        "pmc_id": pmc,
        "publication_types": publication_types,
        "mesh_terms": mesh_terms,
    }


def fetch_pubmed_metadata(pmids: list[str]) -> dict[str, dict[str, Any]]:
    clean_pmids: list[str] = []
    seen: set[str] = set()
    for value in pmids:
        value = str(value or "").strip()
        if value and value.lower() != "nan" and value not in seen:
            clean_pmids.append(value)
            seen.add(value)
    if not clean_pmids:
        return {}

    metadata: dict[str, dict[str, Any]] = {}
    for start in range(0, len(clean_pmids), 150):
        batch = clean_pmids[start:start + 150]
        try:
            response = requests.get(
                PUBMED_EFETCH_URL,
                headers={"User-Agent": USER_AGENT},
                params={
                    "db": "pubmed",
                    "id": ",".join(batch),
                    "retmode": "xml",
                    "rettype": "abstract",
                    "tool": "CancerInsight",
                },
                timeout=35,
            )
            response.raise_for_status()
            root = ET.fromstring(response.content)
        except (requests.RequestException, ET.ParseError):
            continue
        for article in root.findall(".//PubmedArticle"):
            parsed = _parse_pubmed_article(article)
            if parsed is not None:
                pmid, info = parsed
                metadata[pmid] = info
    return metadata


def enrich_with_pubmed(papers_df: pd.DataFrame) -> pd.DataFrame:
    df = papers_df.copy()
    if "pubmedId" not in df.columns:
        return df

    pmids = [str(value).strip() for value in df["pubmedId"].tolist() if str(value).strip()]
    metadata = fetch_pubmed_metadata(pmids)

    defaults = {
        "pubmed_title": "",
        "pubmed_abstract": "",
        "pubmed_journal": "",
        "pubmed_authors": None,
        "pubmed_date": "",
        "doi": "",
        "pmc_id": "",
        "publication_types": None,
        "mesh_terms": None,
        "pubmed_url": "",
        "pmc_url": "",
        "access_status": "PubMed record",
        "publisher_url": "",
    }
    for column, default in defaults.items():
        if column not in df.columns:
            df[column] = [default for _ in range(len(df))]

    for index, row in df.iterrows():
        pmid = str(row.get("pubmedId", "") or "").strip()
        if pmid.lower() == "nan":
            pmid = ""
        info = metadata.get(pmid, {})
        for key, value in info.items():
            df.at[index, key] = value
        if pmid:
            df.at[index, "pubmed_url"] = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

        pmc_id = str(info.get("pmc_id", "") or "").strip()
        if pmc_id:
            df.at[index, "pmc_url"] = f"https://pmc.ncbi.nlm.nih.gov/articles/{pmc_id}/"
            df.at[index, "access_status"] = "Free full text in PMC"
        else:
            original_url = str(row.get("fullTextUrl", "") or "").strip()
            if original_url and "pubmed.ncbi.nlm.nih.gov" not in original_url and "/pubmed/" not in original_url:
                df.at[index, "publisher_url"] = original_url
                df.at[index, "access_status"] = "Full-text source link"
            elif info.get("pubmed_abstract"):
                df.at[index, "access_status"] = "PubMed abstract"
            else:
                df.at[index, "access_status"] = "PubMed record"
    return df


def papers_for_treatment(papers_df: pd.DataFrame, treatment: str) -> pd.DataFrame:
    target = normalize_treatment(treatment)
    if "treatmentTypes" not in papers_df.columns:
        return papers_df.iloc[0:0].copy()

    def matches(value: Any) -> bool:
        return any(normalize_treatment(item) == target for item in _iter_treatment_values(value))

    return papers_df[papers_df["treatmentTypes"].apply(matches)].copy()


def extract_year(value: Any) -> int | None:
    match = re.search(r"\b(19|20)\d{2}\b", format_value(value))
    return int(match.group(0)) if match else None


def search_pubmed_treatment_evidence(cancer_type: str, treatment: str, limit: int = 12) -> pd.DataFrame:
    cancer = cancer_type.strip()
    treatment_label = normalize_treatment(treatment)
    if not cancer or not treatment_label:
        return pd.DataFrame()

    # We first ask for reviews because they are more suitable for a treatment overview,
    # then broaden to original studies for current evidence.
    base_query = f'("{cancer} cancer"[Title/Abstract]) AND ("{treatment_label}"[Title/Abstract])'
    queries = [
        base_query + " AND (Review[Publication Type] OR Meta-Analysis[Publication Type] OR Systematic Review[Publication Type])",
        base_query,
    ]
    ids: list[str] = []
    for query in queries:
        try:
            response = requests.get(
                PUBMED_ESEARCH_URL,
                headers={"User-Agent": USER_AGENT},
                params={
                    "db": "pubmed",
                    "term": query,
                    "retmode": "json",
                    "retmax": limit,
                    "sort": "relevance",
                    "tool": "CancerInsight",
                },
                timeout=25,
            )
            response.raise_for_status()
            found = response.json().get("esearchresult", {}).get("idlist", [])
        except (requests.RequestException, ValueError):
            found = []
        for pmid in found:
            if pmid not in ids:
                ids.append(pmid)
            if len(ids) >= limit:
                break
        if len(ids) >= min(6, limit):
            break

    if not ids:
        return pd.DataFrame()

    metadata = fetch_pubmed_metadata(ids)
    rows: list[dict[str, Any]] = []
    for pmid in ids:
        info = metadata.get(pmid)
        if not info:
            continue
        row = {"pubmedId": pmid, **info}
        row["pubmed_url"] = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        pmc_id = str(info.get("pmc_id", "") or "").strip()
        row["pmc_url"] = f"https://pmc.ncbi.nlm.nih.gov/articles/{pmc_id}/" if pmc_id else ""
        row["publisher_url"] = ""
        row["access_status"] = "Free full text in PMC" if pmc_id else (
            "PubMed abstract" if info.get("pubmed_abstract") else "PubMed record"
        )
        rows.append(row)
    return pd.DataFrame(rows)


def _sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", (text or "")).strip()
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+", text)
    cleaned: list[str] = []
    for part in parts:
        part = re.sub(
            r"^(BACKGROUND|OBJECTIVE|OBJECTIVES|PURPOSE|METHODS?|RESULTS?|CONCLUSIONS?|IMPORTANCE|DATA SOURCES|STUDY SELECTION)\s*:\s*",
            "",
            part,
            flags=re.I,
        ).strip()
        if len(part.split()) >= 7:
            cleaned.append(part)
    return cleaned


TREATMENT_DEFINITIONS: dict[str, str] = {
    "chemotherapy": "Chemotherapy is a systemic cancer treatment that uses anti-cancer medicines to kill rapidly dividing cancer cells or prevent them from growing and dividing.",
    "radiation": "Radiation therapy uses high-energy radiation to damage the DNA of cancer cells and shrink or control tumors in a defined area of the body.",
    "immunotherapy": "Immunotherapy is a group of cancer treatments that helps the immune system recognize, target, or attack cancer cells more effectively.",
    "targeted therapy": "Targeted therapy uses medicines designed to interfere with specific molecules, pathways, or genetic changes that help cancer cells grow and survive.",
    "surgery": "Cancer surgery removes a tumor and, when appropriate, nearby tissue or lymph nodes. Its role depends on the cancer type, location, stage, and whether the disease can be removed safely.",
    "hormone therapy": "Hormone therapy slows or blocks cancers that depend on hormones or hormone signaling for growth.",
    "stem cell transplant": "Stem cell transplantation restores blood-forming stem cells after intensive treatment and is mainly used for selected blood cancers and related disorders.",
}


TREATMENT_GENERAL_USE: dict[str, list[str]] = {
    "chemotherapy": [
        "It can be used before another treatment to shrink a tumor, after local treatment to reduce the risk of recurrence, or as a main treatment when cancer has spread.",
        "It is also frequently studied in combination with radiation, immunotherapy, targeted therapy, or surgery, depending on the cancer and clinical setting.",
    ],
    "radiation": [
        "It can be used as a main local treatment, before or after surgery, or to control symptoms caused by a tumor.",
        "Radiation is often studied alone or together with systemic treatments such as chemotherapy or immunotherapy.",
    ],
    "immunotherapy": [
        "It may be used alone or with other treatments when the tumor and clinical setting make immune-based treatment appropriate.",
        "Current research frequently examines immune-checkpoint inhibitors, treatment combinations, biomarkers, and use before or after surgery.",
    ],
    "targeted therapy": [
        "It is generally used when a tumor has a molecular feature that can be targeted by a specific drug.",
        "Research commonly evaluates which biomarkers predict benefit, how resistance develops, and how targeted drugs can be combined or sequenced with other treatments.",
    ],
    "surgery": [
        "Surgery is mainly a local treatment and is considered when a tumor can be removed safely and the clinical setting makes an operation appropriate.",
        "Research commonly examines the extent of resection, lymph-node assessment, perioperative treatment, complications, recurrence, and long-term outcomes.",
    ],
    "hormone therapy": [
        "It is used when cancer growth is driven by hormone signaling and may be given alone or with other treatments.",
        "Research often focuses on duration of treatment, resistance, combinations, and biomarkers of response.",
    ],
}


def _evidence_strength(row: pd.Series) -> int:
    types = [str(x).lower() for x in row.get("publication_types", [])] if isinstance(row.get("publication_types", []), list) else []
    title = format_value(row.get("pubmed_title", "")).lower()
    score = 0
    if any("systematic review" in t for t in types): score += 80
    if any("meta-analysis" in t or "meta analysis" in t for t in types): score += 75
    if any("guideline" in t or "practice guideline" in t for t in types): score += 70
    if any("randomized controlled trial" in t for t in types): score += 65
    if any("clinical trial" in t for t in types): score += 55
    if any("review" in t for t in types): score += 45
    if "systematic review" in title: score += 20
    if "meta-analysis" in title or "meta analysis" in title: score += 20
    if format_value(row.get("pubmed_abstract", "")): score += 10
    return score


def rank_evidence(evidence_df: pd.DataFrame) -> pd.DataFrame:
    if evidence_df.empty:
        return evidence_df.copy()
    ranked = evidence_df.copy()
    ranked["_evidence_strength"] = ranked.apply(_evidence_strength, axis=1)
    ranked["_year"] = ranked["pubmed_date"].apply(extract_year) if "pubmed_date" in ranked else None
    ranked = ranked.sort_values(["_evidence_strength", "_year"], ascending=[False, False], na_position="last")
    return ranked.drop(columns=["_evidence_strength", "_year"], errors="ignore")


def _theme_hits(evidence_df: pd.DataFrame, keywords: list[str], max_sources: int = 3) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for _, row in rank_evidence(evidence_df).iterrows():
        text = (format_value(row.get("pubmed_title", "")) + " " + format_value(row.get("pubmed_abstract", ""))).lower()
        if any(keyword in text for keyword in keywords):
            hits.append(row.to_dict())
        if len(hits) >= max_sources:
            break
    return hits


def _statement(text: str, sources: list[dict[str, Any]]) -> dict[str, Any]:
    return {"text": text, "sources": sources, "source": sources[0] if sources else {}}


def synthesize_treatment_overview(cancer_type: str, treatment: str, evidence_df: pd.DataFrame) -> dict[str, Any]:
    """Create treatment-first, plain-language synthesis without reproducing abstract prose."""
    normalized = normalize_treatment(treatment)
    definition = TREATMENT_DEFINITIONS.get(
        normalized,
        f"{display_treatment(treatment)} is a cancer-treatment approach used in selected cancers and clinical situations.",
    )
    ranked = rank_evidence(evidence_df)

    use: list[dict[str, Any]] = []
    benefits: list[dict[str, Any]] = []
    limitations: list[dict[str, Any]] = []
    directions: list[dict[str, Any]] = []

    # Start with treatment-first usage language, then add cancer-specific evidence only when the literature supports it.
    general_use = TREATMENT_GENERAL_USE.get(normalized, [])
    for sentence in general_use[:2]:
        use.append(_statement(sentence, []))

    peri = _theme_hits(ranked, ["neoadjuvant", "preoperative", "perioperative"])
    if peri:
        use.append(_statement(f"For {cancer_type.title()} cancer, the retrieved literature includes use before surgery or around the time of surgery (neoadjuvant/perioperative treatment).", peri))
    adj = _theme_hits(ranked, ["adjuvant", "postoperative"])
    if adj:
        use.append(_statement(f"The evidence also includes treatment given after surgery (adjuvant or postoperative treatment) in selected {cancer_type.title()} cancer settings.", adj))
    combo = _theme_hits(ranked, ["combination", "combined", "chemoimmunotherapy", "chemoradiation", "plus chemotherapy", "plus immunotherapy"])
    if combo:
        use.append(_statement("Combination strategies with other cancer treatments are an important part of the retrieved research.", combo))
    advanced = _theme_hits(ranked, ["advanced", "metastatic", "first-line", "first line"])
    if advanced:
        use.append(_statement(f"Studies in the evidence set also evaluate this treatment in advanced or first-line {cancer_type.title()} cancer settings.", advanced))

    survival = _theme_hits(ranked, ["overall survival", "event-free survival", "progression-free survival", "survival benefit", "improved survival"])
    if survival:
        benefits.append(_statement("Survival and disease-control outcomes are repeatedly evaluated, and some studies report improved outcomes in specific patient groups or treatment combinations.", survival))
    response = _theme_hits(ranked, ["response rate", "pathologic complete response", "pcr", "objective response", "tumor response"])
    if response:
        benefits.append(_statement("Tumor response and pathological response are recurring measures of benefit in the retrieved studies.", response))
    recurrence = _theme_hits(ranked, ["recurrence", "relapse", "disease-free"])
    if recurrence:
        benefits.append(_statement("The literature also examines whether treatment can reduce recurrence or prolong disease-free control after initial therapy.", recurrence))

    adverse = _theme_hits(ranked, ["adverse event", "toxicity", "side effect", "safety", "complication"])
    if adverse:
        limitations.append(_statement("Safety, side effects, and treatment-related complications are important considerations in the evidence base.", adverse))
    hetero = _theme_hits(ranked, ["heterogeneity", "not significantly", "uncertain", "controvers", "lack of", "limited evidence"])
    if hetero:
        limitations.append(_statement("Results are not uniform across all studies or patient groups, and the literature highlights uncertainty or differences in who benefits most.", hetero))
    resistance = _theme_hits(ranked, ["resistance", "refractory", "progressed on", "progression after"])
    if resistance:
        limitations.append(_statement("Treatment resistance or disease progression after therapy remains an active clinical challenge in the retrieved research.", resistance))

    biomarkers = _theme_hits(ranked, ["biomarker", "pd-l1", "egfr", "alk", "mutation", "molecular", "genomic"])
    if biomarkers:
        directions.append(_statement("Current research increasingly studies biomarkers and molecular features to identify which patients are most likely to benefit.", biomarkers))
    combinations = _theme_hits(ranked, ["combination", "combined", "chemoimmunotherapy", "chemoradiation"])
    if combinations:
        directions.append(_statement("Optimizing combinations and treatment sequencing is a major research direction.", combinations))
    trials = _theme_hits(ranked, ["randomized", "clinical trial", "phase ii", "phase iii"])
    if trials:
        directions.append(_statement("Clinical trials continue to test treatment timing, combinations, and outcome improvements.", trials))

    # Keep output concise and avoid duplicate concepts.
    use = use[:4]
    benefits = benefits[:3]
    limitations = limitations[:3]
    directions = directions[:3]

    source_by_pmid: dict[str, dict[str, Any]] = {}
    for group in [use, benefits, limitations, directions]:
        for item in group:
            for source in item.get("sources", []):
                pmid = format_value(source.get("pubmedId", ""))
                if pmid:
                    source_by_pmid[pmid] = source
    if not source_by_pmid:
        for _, row in ranked.head(5).iterrows():
            pmid = format_value(row.get("pubmedId", ""))
            if pmid:
                source_by_pmid[pmid] = row.to_dict()

    return {
        "definition": definition,
        "use": use,
        "benefits": benefits,
        "limitations": limitations,
        "directions": directions,
        "sources": list(source_by_pmid.values())[:8],
        "paper_count": len(ranked),
    }

def research_profile(papers_df: pd.DataFrame, treatment: str | None = None) -> dict[str, Any]:
    subset = papers_for_treatment(papers_df, treatment) if treatment else papers_df.copy()
    if subset.empty:
        return {
            "papers": subset,
            "paper_count": 0,
            "free_full_text_count": 0,
            "latest_year": None,
            "journals": [],
            "top_journals": [],
            "publication_types": [],
            "clinical_trials": 0,
            "reviews": 0,
            "meta_analyses": 0,
            "year_counts": pd.Series(dtype="int64"),
        }

    years: list[int] = []
    journal_values: list[str] = []
    pub_types: list[str] = []
    for _, row in subset.iterrows():
        year = extract_year(row.get("pubmed_date", "")) or extract_year(row.get("publicationDate", ""))
        if year:
            years.append(year)
        journal = format_value(row.get("pubmed_journal", "")) or format_value(row.get("journal", ""))
        if journal:
            journal_values.append(journal)
        types = row.get("publication_types", [])
        if isinstance(types, list):
            pub_types.extend(str(x) for x in types if str(x).strip())

    lower_types = [x.lower() for x in pub_types]
    free_count = int(subset.get("pmc_id", pd.Series(dtype=str)).fillna("").astype(str).str.strip().ne("").sum()) if "pmc_id" in subset else 0
    year_counts = pd.Series(years, dtype="int64").value_counts().sort_index() if years else pd.Series(dtype="int64")

    return {
        "papers": subset,
        "paper_count": len(subset),
        "free_full_text_count": free_count,
        "latest_year": max(years) if years else None,
        "journals": sorted(set(journal_values)),
        "top_journals": Counter(journal_values).most_common(6),
        "publication_types": Counter(pub_types).most_common(8),
        "clinical_trials": sum("clinical trial" in x for x in lower_types),
        "reviews": sum("review" in x for x in lower_types),
        "meta_analyses": sum("meta-analysis" in x or "meta analysis" in x for x in lower_types),
        "year_counts": year_counts,
    }


def treatment_research_profile(papers_df: pd.DataFrame, treatment: str) -> dict[str, Any]:
    profile = research_profile(papers_df, treatment)
    profile["treatment"] = treatment
    return profile


def _paper_text(row: pd.Series) -> str:
    pieces = [
        format_value(row.get("pubmed_title", "")),
        format_value(row.get("pubmed_abstract", "")),
        format_value(row.get("title", "")),
        format_value(row.get("mesh_terms", "")),
    ]
    return " ".join(piece for piece in pieces if piece).lower()


def key_findings_from_papers(papers_df: pd.DataFrame, treatment: str | None = None, max_items: int = 5) -> list[str]:
    if papers_df.empty:
        return []
    corpus = " ".join(_paper_text(row) for _, row in papers_df.iterrows())
    findings: list[tuple[int, str]] = []
    themes = [
        (["survival", "overall survival", "progression-free"], "Survival and disease-control outcomes are prominent research endpoints."),
        (["combination", "combined", "plus chemotherapy", "plus immunotherapy"], "Combination-treatment strategies appear frequently in the retrieved literature."),
        (["biomarker", "pd-l1", "egfr", "alk", "mutation", "molecular"], "Biomarkers and molecular features are recurring themes in treatment selection and research."),
        (["toxicity", "adverse event", "side effect", "safety"], "Safety, toxicity, and treatment-related adverse effects are repeatedly evaluated."),
        (["neoadjuvant", "preoperative", "perioperative"], "Perioperative and pre-surgical treatment strategies are represented in the research."),
        (["adjuvant", "postoperative"], "Post-surgical (adjuvant) treatment is a recurring research topic."),
        (["resistance", "refractory"], "Treatment resistance and strategies to overcome it are active research themes."),
        (["quality of life", "patient-reported"], "Quality-of-life and patient-reported outcomes appear in the evidence base."),
        (["clinical trial", "randomized", "phase ii", "phase iii"], "Clinical-trial evidence is present in the retrieved literature."),
    ]
    for keywords, sentence in themes:
        count = sum(corpus.count(keyword) for keyword in keywords)
        if count:
            findings.append((count, sentence))
    findings.sort(reverse=True, key=lambda x: x[0])
    return [sentence for _, sentence in findings[:max_items]]


def compare_profiles(p1: dict[str, Any], p2: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    if p1["paper_count"] != p2["paper_count"]:
        richer = p1 if p1["paper_count"] > p2["paper_count"] else p2
        notes.append(f"{display_treatment(richer.get('treatment', ''))} has more papers in the current Cancer Insight result set.")
    if (p1["latest_year"] or 0) != (p2["latest_year"] or 0):
        newer = p1 if (p1["latest_year"] or 0) > (p2["latest_year"] or 0) else p2
        notes.append(f"{display_treatment(newer.get('treatment', ''))} has the more recent publication in this result set.")
    if p1["free_full_text_count"] != p2["free_full_text_count"]:
        freer = p1 if p1["free_full_text_count"] > p2["free_full_text_count"] else p2
        notes.append(f"{display_treatment(freer.get('treatment', ''))} has more papers with free full text identified in PubMed Central.")
    if p1["clinical_trials"] or p2["clinical_trials"]:
        notes.append("Clinical-trial counts describe the retrieved literature only; they do not establish which treatment is better.")
    return notes[:4]


def _image_relevance_score(cancer_type: str, title: str, description: str = "", credit: str = "") -> int | None:
    """Return a relevance score for a Commons image, or None when it should be rejected.

    The filter is deliberately conservative: Cancer Insight would rather show 3 strongly
    relevant medical images than 12 photographs/documents that only mention cancer in metadata.
    """
    target = re.sub(r"\s+", " ", cancer_type.strip().lower())
    if not target:
        return None

    def plain(value: str) -> str:
        return re.sub(r"<[^>]+>", " ", unescape(value or " ")).replace("&nbsp;", " ")

    title_l = plain(title).lower()
    description_l = plain(description).lower()
    credit_l = plain(credit).lower()
    combined = " ".join([title_l, description_l, credit_l])

    # Common aliases let medically correct images match even when Commons uses the tumor name
    # rather than the user's exact wording (e.g. glioblastoma instead of "brain cancer").
    alias_map: dict[str, list[str]] = {
        "brain": [
            "brain cancer", "brain tumor", "brain tumour", "brain neoplasm",
            "glioma", "glioblastoma", "astrocytoma", "oligodendroglioma",
            "ependymoma", "medulloblastoma", "brainstem glioma", "cns tumor", "cns tumour",
        ],
        "breast": [
            "breast cancer", "breast carcinoma", "mammary carcinoma", "ductal carcinoma",
            "lobular carcinoma", "invasive breast", "dcis", "mammogram", "mammography",
        ],
        "lung": [
            "lung cancer", "lung carcinoma", "pulmonary carcinoma", "lung adenocarcinoma",
            "non-small cell lung", "non small cell lung", "nsclc", "small cell lung", "sclc",
        ],
        "colon": ["colon cancer", "colon carcinoma", "colonic carcinoma", "colorectal cancer", "colorectal carcinoma"],
        "colorectal": ["colorectal cancer", "colorectal carcinoma", "colon cancer", "rectal cancer", "rectal carcinoma"],
        "prostate": ["prostate cancer", "prostate carcinoma", "prostatic carcinoma", "prostate adenocarcinoma"],
        "pancreatic": ["pancreatic cancer", "pancreatic carcinoma", "pancreatic adenocarcinoma", "pancreas cancer"],
        "pancreas": ["pancreatic cancer", "pancreatic carcinoma", "pancreatic adenocarcinoma", "pancreas cancer"],
        "liver": ["liver cancer", "hepatic cancer", "hepatocellular carcinoma", "hcc", "liver carcinoma"],
        "kidney": ["kidney cancer", "renal cancer", "renal cell carcinoma", "rcc", "kidney carcinoma"],
        "skin": ["skin cancer", "melanoma", "basal cell carcinoma", "squamous cell carcinoma of skin", "cutaneous carcinoma"],
        "melanoma": ["melanoma", "malignant melanoma", "skin cancer"],
        "ovarian": ["ovarian cancer", "ovarian carcinoma", "ovary cancer"],
        "ovary": ["ovarian cancer", "ovarian carcinoma", "ovary cancer"],
        "cervical": ["cervical cancer", "cervical carcinoma", "cervix cancer"],
        "cervix": ["cervical cancer", "cervical carcinoma", "cervix cancer"],
        "leukemia": ["leukemia", "leukaemia", "acute myeloid leukemia", "acute lymphoblastic leukemia", "chronic myeloid leukemia"],
        "lymphoma": ["lymphoma", "hodgkin lymphoma", "non-hodgkin lymphoma", "non hodgkin lymphoma"],
        "thyroid": ["thyroid cancer", "thyroid carcinoma", "papillary thyroid", "follicular thyroid", "medullary thyroid"],
        "bladder": ["bladder cancer", "bladder carcinoma", "urothelial carcinoma"],
        "stomach": ["stomach cancer", "gastric cancer", "gastric carcinoma"],
        "gastric": ["stomach cancer", "gastric cancer", "gastric carcinoma"],
        "esophageal": ["esophageal cancer", "oesophageal cancer", "esophageal carcinoma", "oesophageal carcinoma"],
    }

    # Normalize inputs such as "brain cancer" -> "brain" for alias lookup.
    base = re.sub(r"\bcancer\b", "", target).strip()
    aliases = [f"{target} cancer" if "cancer" not in target else target, f"{base} carcinoma"]
    aliases.extend(alias_map.get(base, []))
    aliases = [a.strip().lower() for a in aliases if a.strip()]

    # Strong disease match: at least one explicit cancer/tumor alias must be present.
    disease_hits = [alias for alias in aliases if alias in combined]
    if not disease_hits:
        return None

    # Medical-image vocabulary: the metadata must indicate that the file visually represents
    # disease, imaging, pathology, tissue, or a scientific cancer diagram—not merely a person,
    # event, report, drug, or institution connected with cancer.
    medical_visual_terms = {
        "histology", "histopathology", "pathology", "micrograph", "microscopy", "microscopic",
        "biopsy", "specimen", "tissue", "cytology", "immunohistochemistry", "immunostain",
        "stain", "h&e", "hematoxylin", "eosin", "tumor", "tumour", "neoplasm", "lesion",
        "carcinoma", "adenocarcinoma", "sarcoma", "glioma", "glioblastoma", "astrocytoma",
        "radiology", "radiograph", "x-ray", "xray", "computed tomography", "ct scan", "mri",
        "magnetic resonance", "pet scan", "pet/ct", "mammogram", "mammography", "ultrasound",
        "gross pathology", "gross specimen", "anatomical", "anatomy", "medical diagram",
        "schematic", "diagram", "illustration", "cancer cell", "tumor cell", "tumour cell",
        "metastasis", "metastatic", "immunofluorescence", "fluorescence", "western blot",
        "survival curve", "kaplan-meier", "kaplan meier", "mechanism of action",
    }
    visual_hits = [term for term in medical_visual_terms if term in combined]
    if not visual_hits:
        return None

    blocked_terms = {
        "bus", "autobus", "coach", "route", "street", "vehicle", "car park", "campaign",
        "awareness", "ribbon", "fundraiser", "fundraising", "charity", "make-a-wish",
        "make a wish", "wish foundation", "poster", "advertisement", "advertising", "logo",
        "mascot", "event", "marathon", "race for", "t-shirt", "shirt", "badge", "stamp",
        "coin", "billboard", "psa", "public service announcement", "military", "marine corps",
        "soldier", "artillery", "army", "state hospital report", "board of directors",
        "yearbook", "book scan", "internet archive book", "internet archive book images",
        "newspaper", "portrait of", "annual report", "proceedings", "archive.org",
        "scanned page", "scanned book", "book page", "title page", "table of contents",
        "presented to the", "reprinted from", "royal college of surgeons",
    }
    if any(term in combined for term in blocked_terms):
        return None

    # Cancer Images is an image gallery, not a document archive. Reject PDFs/DjVu files and
    # obvious book/report scans even when OCR text happens to contain the cancer name.
    lower_title = title_l.strip()
    if re.search(r"\.(pdf|djvu|djv)$", lower_title):
        return None
    document_markers = (
        "identifier:", "find matches", "year:", "authors:", "digitized by",
        "full text", "volume ", "chapter ", "page ", "pages ",
    )
    if sum(marker in combined for marker in document_markers) >= 2:
        return None
    # Historical book scans with a year in the title are rarely useful as a modern medical
    # gallery result. Keep genuine pathology specimens and scans, but reject archive-style pages.
    if re.search(r"\((17|18|19)\d{2}\)", lower_title) and ("book" in combined or "archive" in combined or "pathological histology" in lower_title):
        return None

    # Reject a file that is clearly about another common cancer unless the selected cancer also
    # appears strongly in its title/description. This blocks e.g. breast-cancer figures during a
    # brain-cancer search just because a description happens to mention the brain.
    other_cancers = {
        "breast", "lung", "brain", "prostate", "pancreatic", "pancreas", "liver", "kidney",
        "colon", "colorectal", "rectal", "ovarian", "ovary", "cervical", "cervix", "thyroid",
        "bladder", "gastric", "stomach", "esophageal", "oesophageal", "melanoma", "leukemia",
        "leukaemia", "lymphoma",
    }
    selected_words = set(re.findall(r"[a-z]+", base))
    for other in other_cancers - selected_words:
        if f"{other} cancer" in title_l or f"{other} carcinoma" in title_l:
            if not any(alias in title_l for alias in aliases):
                return None

    score = 0
    # Title specificity carries the most weight.
    title_alias_hits = [a for a in aliases if a in title_l]
    desc_alias_hits = [a for a in aliases if a in description_l]
    score += 14 if title_alias_hits else 0
    score += 7 if desc_alias_hits else 0
    score += min(len(visual_hits), 5) * 3

    high_value = {
        "histology", "histopathology", "pathology", "micrograph", "microscopy", "biopsy",
        "mri", "ct scan", "computed tomography", "mammogram", "mammography", "gross specimen",
        "immunohistochemistry", "medical diagram", "schematic", "glioma", "glioblastoma",
    }
    score += sum(3 for term in high_value if term in combined)

    # Prefer files whose title itself is cancer/tumor-specific. When the disease appears only in
    # a description, require a strong diagnostic/pathology visual signal so incidental keyword
    # mentions do not enter the gallery.
    if not title_alias_hits:
        strong_visual = any(term in combined for term in {
            "histology", "histopathology", "micrograph", "microscopy", "mri", "ct scan",
            "computed tomography", "gross pathology", "gross specimen", "biopsy",
            "immunohistochemistry", "tumor segmentation", "tumour segmentation",
        })
        if not (desc_alias_hits and strong_visual):
            return None
        score -= 3

    # Extra ranking preference: diagnostic imaging and tissue/pathology first, then scientific
    # diagrams. This affects ordering only; every accepted item still passes the relevance gates.
    if any(term in combined for term in {"mri", "ct scan", "computed tomography", "pet scan", "mammogram", "mammography"}):
        score += 8
    if any(term in combined for term in {"histology", "histopathology", "pathology", "micrograph", "microscopy", "gross pathology", "gross specimen"}):
        score += 7
    if any(term in combined for term in {"medical diagram", "schematic", "mechanism of action", "tumor segmentation", "tumour segmentation"}):
        score += 4

    # Require a meaningful threshold. Descriptions that merely mention the disease once should
    # not make it into the gallery.
    if score < 15:
        return None
    return score


def fetch_images(cancer_type: str, limit: int = 12) -> list[dict[str, str]]:
    """Retrieve a conservative gallery of cancer-specific medical images from Commons."""
    target = re.sub(r"\s+", " ", cancer_type.strip().lower())
    if not target:
        return []

    base = re.sub(r"\bcancer\b", "", target).strip()
    query_aliases: dict[str, list[str]] = {
        "brain": ["brain tumor", "glioma", "glioblastoma", "astrocytoma"],
        "breast": ["breast cancer", "breast carcinoma", "mammography"],
        "lung": ["lung cancer", "lung carcinoma", "NSCLC"],
        "colon": ["colon cancer", "colorectal cancer"],
        "colorectal": ["colorectal cancer", "colon cancer", "rectal cancer"],
        "skin": ["skin cancer", "melanoma"],
        "pancreatic": ["pancreatic cancer", "pancreatic adenocarcinoma"],
        "pancreas": ["pancreatic cancer", "pancreatic adenocarcinoma"],
    }
    disease_queries = query_aliases.get(base, [target if "cancer" in target else f"{target} cancer"])
    contexts = ["histology", "pathology", "MRI", "CT", "microscopy", "tumor diagram"]
    queries: list[str] = []
    for disease in disease_queries[:4]:
        for context in contexts:
            queries.append(f'"{disease}" {context}')
    queries.extend([f'"{d}"' for d in disease_queries[:4]])

    candidates: dict[str, dict[str, str]] = {}
    for query in queries:
        try:
            response = requests.get(
                COMMONS_URL,
                headers={"User-Agent": USER_AGENT},
                params={
                    "action": "query",
                    "generator": "search",
                    "gsrsearch": query,
                    "gsrnamespace": 6,
                    "gsrlimit": 20,
                    "prop": "imageinfo",
                    "iiprop": "url|extmetadata",
                    "iiurlwidth": 900,
                    "format": "json",
                },
                timeout=25,
            )
            response.raise_for_status()
            pages = response.json().get("query", {}).get("pages", {})
        except (requests.RequestException, ValueError):
            continue

        for page in pages.values():
            image_info = page.get("imageinfo", [{}])[0]
            thumb = image_info.get("thumburl")
            original = image_info.get("url")
            if not thumb:
                continue
            meta = image_info.get("extmetadata", {}) or {}
            title = str(page.get("title", "Image")).replace("File:", "")
            artist = unescape(str(meta.get("Artist", {}).get("value", "")))
            license_name = unescape(str(meta.get("LicenseShortName", {}).get("value", "")))
            credit = unescape(str(meta.get("Credit", {}).get("value", "")))
            description = unescape(str(meta.get("ImageDescription", {}).get("value", "")))

            score = _image_relevance_score(target, title, description, credit)
            if score is None:
                continue

            key = original or thumb
            item = {
                "title": title,
                "thumbnail": thumb,
                "original": original or thumb,
                "artist": artist,
                "license": license_name,
                "credit": credit,
                "description": description,
                "_score": score + (1 if license_name else 0),
            }
            if key not in candidates or item["_score"] > candidates[key].get("_score", 0):
                candidates[key] = item

    ranked = sorted(candidates.values(), key=lambda item: (-item.get("_score", 0), item.get("title", "")))
    results: list[dict[str, str]] = []
    for item in ranked[:limit]:
        clean = dict(item)
        clean.pop("_score", None)
        results.append(clean)
    return results

