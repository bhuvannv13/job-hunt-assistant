"""Skill vocabulary used to compare CVs with job descriptions.

Each canonical skill maps to regular expressions that recognise it in free text. Matching is
case-insensitive and respects word boundaries, so "R" does not match every word containing an r.
"""
from __future__ import annotations

import re

SKILLS: dict[str, list[str]] = {
    # Languages
    "Python": [r"python"],
    "SQL": [r"sql", r"t-sql", r"pl/sql", r"postgres(?:ql)?", r"mysql", r"sql server", r"sqlite"],
    "R": [r"(?<![\w-])R(?![\w-])(?=\s*(?:,|/|and|or|\)|programming|language|studio|\.))", r"[Rr][Ss]tudio", r"tidyverse", r"ggplot2?"],
    "Java": [r"java(?!script)"],
    "JavaScript": [r"javascript", r"node\.?js", r"typescript"],
    "Scala": [r"scala"],
    "Bash": [r"bash", r"shell scripting", r"linux"],
    "MATLAB": [r"matlab"],
    "C++": [r"c\+\+"],
    # Data handling
    "pandas": [r"pandas"],
    "NumPy": [r"numpy"],
    "Excel": [r"excel", r"spreadsheets?", r"vlookup", r"pivot tables?"],
    "ETL": [r"etl", r"elt", r"data pipelines?", r"data ingestion"],
    "APIs": [r"rest(?:ful)? apis?", r"apis?"],
    "Web scraping": [r"web scraping", r"beautiful ?soup", r"scrapy"],
    "Data cleaning": [r"data cleaning", r"data cleansing", r"data wrangling", r"data quality", r"data validation"],
    "Data modelling": [r"data model(?:l)?ing", r"dimensional model(?:l)?ing", r"star schema", r"data warehous(?:e|ing)"],
    "Spark": [r"spark", r"pyspark", r"databricks"],
    "Airflow": [r"airflow", r"orchestration", r"dagster", r"prefect"],
    "dbt": [r"dbt"],
    "Kafka": [r"kafka", r"streaming data", r"event streaming"],
    "Snowflake": [r"snowflake"],
    "BigQuery": [r"bigquery"],
    "NoSQL": [r"mongodb", r"nosql", r"dynamodb", r"cassandra"],
    # Analysis and BI
    "Statistics": [r"statistic(?:s|al)", r"hypothesis testing", r"a/b test(?:s|ing)?", r"regression analysis"],
    "Tableau": [r"tableau"],
    "Power BI": [r"power ?bi", r"dax"],
    "Looker": [r"looker"],
    "Data visualisation": [r"data visuali[sz]ation", r"dashboards?", r"matplotlib", r"seaborn", r"plotly"],
    "Reporting": [r"reporting", r"kpis?", r"metrics"],
    "Survival analysis": [r"survival analysis", r"kaplan[- ]meier", r"cox (?:model|regression)"],
    # Machine learning
    "Machine learning": [r"machine learning", r"\bml\b"],
    "scikit-learn": [r"scikit[- ]learn", r"sklearn"],
    "XGBoost": [r"xgboost", r"lightgbm", r"gradient boost(?:ing|ed)"],
    "Deep learning": [r"deep learning", r"neural networks?"],
    "TensorFlow": [r"tensorflow", r"keras"],
    "PyTorch": [r"pytorch", r"torch"],
    "Computer vision": [r"computer vision", r"image (?:processing|classification|segmentation)", r"object detection"],
    "OpenCV": [r"opencv"],
    "NLP": [r"nlp", r"natural language processing", r"text (?:mining|classification)"],
    "LLMs": [r"llms?", r"large language models?", r"generative ai", r"genai", r"prompt engineering", r"rag\b", r"retrieval[- ]augmented"],
    "Transformers": [r"transformers?", r"hugging ?face", r"bert"],
    "Explainable AI": [r"shap", r"explainab(?:le|ility)", r"interpretab(?:le|ility)"],
    "MLOps": [r"mlops", r"model deployment", r"model monitoring", r"mlflow"],
    "Time series": [r"time[- ]series", r"forecasting"],
    "Clustering": [r"clustering", r"k-means", r"hdbscan", r"unsupervised"],
    # Engineering
    "Git": [r"git(?!hub actions)", r"github", r"gitlab", r"version control"],
    "CI/CD": [r"ci/cd", r"continuous integration", r"github actions", r"gitlab ci", r"jenkins"],
    "Docker": [r"docker", r"containers?", r"containeri[sz](?:ed|ation)"],
    "Kubernetes": [r"kubernetes", r"k8s"],
    "Testing": [r"pytest", r"unit tests?", r"automated testing", r"test automation"],
    "Cloud": [r"aws", r"azure", r"gcp", r"google cloud", r"cloud platforms?"],
    "Streamlit": [r"streamlit", r"gradio"],
    "Agile": [r"agile", r"scrum", r"jira"],
    # Domain and soft skills
    "Healthcare data": [r"healthcare", r"clinical", r"medical", r"genomics?", r"bioinformatics", r"tcga"],
    "Trust and safety": [r"trust (?:and|&) safety", r"content moderation", r"policy enforcement", r"online safety", r"integrity"],
    "Risk and compliance": [r"compliance", r"fraud", r"risk analysis", r"aml\b", r"kyc"],
    "Communication": [r"communication skills", r"stakeholders?", r"presentations?", r"storytelling"],
    "Research": [r"research", r"literature review"],
}

_COMPILED = {
    name: re.compile("|".join(f"(?<![A-Za-z0-9]){p}(?![A-Za-z0-9])" if not p.startswith("(?<!") else p for p in patterns),
                     0 if name == "R" else re.IGNORECASE)
    for name, patterns in SKILLS.items()
}


def find_skills(text: str) -> list[str]:
    """Canonical skills mentioned in text, in vocabulary order."""
    if not text:
        return []
    return [name for name, pattern in _COMPILED.items() if pattern.search(text)]


def skill_pattern(name: str):
    return _COMPILED.get(name)
