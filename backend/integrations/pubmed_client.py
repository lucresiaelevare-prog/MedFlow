"""PubMed — base científica confiável (NCBI E-utilities).

Uso no MedFlow: buscar artigos científicos por termo (útil para o Tutor
sugerir referências a estudantes de medicina).

- Sem chave funciona (3 req/s). Com chave: 10 req/s.
- Como obter a chave: https://www.ncbi.nlm.nih.gov/account/settings/ →
  "API Key Management" (gratuito, precisa da conta NCBI).

Env vars:
  PUBMED_API_KEY  (opcional, sobe o rate limit)
  PUBMED_TOOL     (nome da app — default: "medflow")
  PUBMED_EMAIL    (recomendado — contato do usuário responsável)

Docs: https://www.ncbi.nlm.nih.gov/books/NBK25501/
"""
from __future__ import annotations

import os
from typing import Optional

import httpx

_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def _params(extra: dict) -> dict:
    p = dict(extra)
    p.setdefault("tool", os.environ.get("PUBMED_TOOL", "medflow"))
    email = os.environ.get("PUBMED_EMAIL")
    if email:
        p["email"] = email
    key = os.environ.get("PUBMED_API_KEY")
    if key:
        p["api_key"] = key
    return p


async def search(term: str, retmax: int = 10, sort: str = "relevance") -> list[str]:
    """Busca PMIDs em PubMed. Retorna lista de IDs."""
    url = f"{_BASE}/esearch.fcgi"
    params = _params({
        "db": "pubmed",
        "term": term,
        "retmode": "json",
        "retmax": retmax,
        "sort": sort,
    })
    async with httpx.AsyncClient(timeout=20.0) as http:
        r = await http.get(url, params=params)
        r.raise_for_status()
        data = r.json()
    return (data.get("esearchresult") or {}).get("idlist") or []


async def summary(pmids: list[str]) -> list[dict]:
    """Retorna metadados (título, autores, revista, ano, doi) para PMIDs."""
    if not pmids:
        return []
    url = f"{_BASE}/esummary.fcgi"
    params = _params({
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "json",
    })
    async with httpx.AsyncClient(timeout=20.0) as http:
        r = await http.get(url, params=params)
        r.raise_for_status()
        data = r.json()
    result = data.get("result") or {}
    items = []
    for pmid in pmids:
        art = result.get(pmid)
        if not art:
            continue
        authors = ", ".join(a.get("name", "") for a in (art.get("authors") or [])[:5])
        items.append({
            "pmid": pmid,
            "title": art.get("title"),
            "journal": art.get("fulljournalname") or art.get("source"),
            "pubdate": art.get("pubdate"),
            "authors": authors,
            "doi": next((x.get("value") for x in (art.get("articleids") or [])
                         if x.get("idtype") == "doi"), None),
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        })
    return items


async def search_and_summarize(term: str, retmax: int = 10) -> list[dict]:
    from integrations import evidence_cache
    cached = await evidence_cache.get("pubmed", term, retmax)
    if cached is not None:
        return cached
    ids = await search(term, retmax=retmax)
    items = await summary(ids)
    await evidence_cache.put("pubmed", term, retmax, items)
    return items
