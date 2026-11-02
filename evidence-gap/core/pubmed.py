"""PubMed E-utilities 래퍼: 검색(esearch) + 상세 조회(efetch).

API 키 없이 초당 3회까지 호출 가능. NCBI_API_KEY가 있으면 초당 10회.
"""
from __future__ import annotations

import os
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

import requests

BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
TOOL = "evidence-gap"


@dataclass
class Paper:
    pmid: str
    title: str
    abstract: str
    journal: str
    year: str
    pub_types: list[str] = field(default_factory=list)
    mesh: list[str] = field(default_factory=list)

    @property
    def url(self) -> str:
        return f"https://pubmed.ncbi.nlm.nih.gov/{self.pmid}/"


def _params(extra: dict) -> dict:
    p = {"db": "pubmed", "tool": TOOL, **extra}
    if key := os.getenv("NCBI_API_KEY"):
        p["api_key"] = key
    if email := os.getenv("NCBI_EMAIL"):
        p["email"] = email
    return p


def search(query: str, retmax: int = 20, min_year: int | None = None,
           humans_only: bool = True) -> list[str]:
    """검색어로 PMID 목록을 관련도순으로 반환."""
    term = query
    if humans_only:
        term += " AND humans[MeSH Terms]"
    if min_year:
        term += f" AND {min_year}:3000[dp]"
    r = requests.get(f"{BASE}/esearch.fcgi", timeout=20, params=_params({
        "term": term, "retmode": "json", "retmax": retmax, "sort": "relevance",
    }))
    r.raise_for_status()
    return r.json()["esearchresult"]["idlist"]


def fetch(pmids: list[str]) -> list[Paper]:
    if not pmids:
        return []
    time.sleep(0.34)  # rate limit 배려
    r = requests.get(f"{BASE}/efetch.fcgi", timeout=30, params=_params({
        "id": ",".join(pmids), "retmode": "xml",
    }))
    r.raise_for_status()
    return parse_efetch_xml(r.text)


def parse_efetch_xml(xml_text: str) -> list[Paper]:
    root = ET.fromstring(xml_text)
    papers = []
    for art in root.findall(".//PubmedArticle"):
        med = art.find("MedlineCitation")
        a = med.find("Article")
        abstract = " ".join(
            ((t.get("Label") + ": ") if t.get("Label") else "") + "".join(t.itertext())
            for t in a.findall("Abstract/AbstractText")
        )
        year = (a.findtext("Journal/JournalIssue/PubDate/Year")
                or (a.findtext("Journal/JournalIssue/PubDate/MedlineDate") or "")[:4])
        papers.append(Paper(
            pmid=med.findtext("PMID"),
            title="".join(a.find("ArticleTitle").itertext()),
            abstract=abstract,
            journal=a.findtext("Journal/ISOAbbreviation") or a.findtext("Journal/Title") or "",
            year=year,
            pub_types=[p.text for p in a.findall("PublicationTypeList/PublicationType")],
            mesh=[m.findtext("DescriptorName") for m in med.findall("MeshHeadingList/MeshHeading")],
        ))
    return papers


def search_and_fetch(query: str, retmax: int = 20, **kw) -> list[Paper]:
    return fetch(search(query, retmax=retmax, **kw))
