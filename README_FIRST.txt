CANCER INSIGHT — FINAL FULL VERSION
===================================

1. Open the .streamlit folder.
2. Copy secrets.toml.example and rename the copy to secrets.toml.
3. Put your private Cancer Research API key in secrets.toml:

   CANCER_RESEARCH_API_KEY = "YOUR_PRIVATE_API_KEY"

4. Run START_CANCER_INSIGHT.bat
   OR open a terminal in this folder and run:

   python -m pip install -r requirements.txt
   python -m streamlit run app.py

FINAL VERSION FEATURES
- Left-side navigation with scroll-to-top page changes
- PubMed enrichment and PMID/PMC/DOI source links
- Free-full-text detection
- Evidence-first treatment research and treatment comparisons
- Research analytics, filters, bookmarks, and paper cards
- Primary PDF research-report download + secondary CSV raw-data export
- Strict cancer-image gallery that prioritizes MRI/CT, pathology, histology,
  microscopy, tumor specimens, segmentation, and scientific medical diagrams
- Rejects PDFs, book scans, historical reports, awareness/event photos,
  advertising, vehicles, and unrelated images
- Wikimedia Commons source, creator, and license information

Educational/research use only; not medical advice.
