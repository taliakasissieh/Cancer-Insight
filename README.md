# Cancer Insight

**Evidence-first cancer research exploration platform**

Cancer Insight is an educational research platform designed to make cancer research easier to explore, understand, and compare while keeping the original scientific evidence visible.

The application combines cancer-research data with PubMed/NCBI metadata and open-access scientific resources.

## Live Application

Cancer Insight is deployed using Streamlit Community Cloud.

https://cancer-insight.streamlit.app/

## Key Features

- Search cancer research by cancer type
- Explore PubMed-enriched research papers
- Read available PubMed abstracts
- Identify free full-text articles in PubMed Central (PMC)
- Filter papers by access type, treatment, publication type, and year
- Sort and save research papers
- View research analytics and publication trends
- Analyze treatment research coverage
- Compare two cancer treatments side-by-side
- View evidence-linked treatment research summaries
- Explore scientifically relevant cancer images
- View image source, creator, and license information
- Download a formatted PDF research report
- Export research data as CSV

## Research Analytics

Cancer Insight automatically summarizes the retrieved research set, including:

- Number of research papers
- Free full-text availability
- Latest publication year
- Number of journals
- Clinical-trial representation
- Treatment types
- Treatment research coverage
- Publication timeline
- Leading journals

These statistics describe the **retrieved literature** and should not be interpreted as measures of treatment effectiveness.

## Treatment Research

Cancer Insight organizes treatment-related evidence into categories such as:

- Chemotherapy
- Immunotherapy
- Radiation
- Surgery
- Targeted therapy

Treatment pages provide plain-language treatment definitions together with cancer-specific research statements derived from the retrieved literature.

Where possible, supporting PubMed identifiers (PMIDs) and source links are displayed so users can inspect the original evidence.

## Treatment Comparison

The comparison tool allows users to compare two treatment categories using the currently retrieved research set.

The comparison includes research coverage measures and recurring research themes.

A larger number of papers does **not** mean that one treatment is safer, more effective, or more appropriate than another.

## Cancer Images

Cancer Insight retrieves scientifically and medically relevant images from Wikimedia Commons.

The gallery prioritizes content such as:

- MRI and CT imaging
- Pathology
- Histology
- Microscopy
- Tumor specimens
- Segmentation images
- Scientific medical diagrams

Source, creator, and licensing information is displayed when supplied by Wikimedia Commons.

## Data Sources

Cancer Insight uses external research and scientific-information services, including:

- Cancer research API data
- PubMed / NCBI metadata
- PubMed Central (PMC)
- Wikimedia Commons

External services may occasionally be unavailable or respond slowly. The application handles unavailable results without treating them as scientific evidence.

## Project Structure

```text
Cancer-Insight/
├── app.py
├── services.py
├── pdf_report.py
├── requirements.txt
├── .gitignore
└── README.md
```

## Running the Project Locally

Install the required Python packages:

```bash
pip install -r requirements.txt
```

Configure the required API credentials using Streamlit secrets.

Then run:

```bash
streamlit run app.py
```

Do not commit private API keys or `secrets.toml` files to a public repository.

## Limitations

Cancer Insight is designed for research exploration rather than clinical decision-making.

Automated extraction and classification may miss context or classify research imperfectly. Research-paper counts represent the literature returned by the application's data sources and search process.

Users should inspect the cited original publications when interpreting research findings.

## Educational Use Disclaimer

**Cancer Insight is for educational and research use only.**

It does not provide medical diagnosis, individualized treatment recommendations, or professional medical advice.

Medical decisions should be made with qualified healthcare professionals using appropriate clinical information.
