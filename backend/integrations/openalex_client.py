"""OpenAlex — pesquisa acadêmica e recomendações (sem chave obrigatória).

Uso: buscar trabalhos científicos, autores e conceitos. Complementa PubMed
com literatura fora de MEDLINE (educação, ciências sociais em saúde, etc).

- Sem chave. O "polite pool" (mais rápido/estável) é acessado adicionando
  seu email via header/parâmetro `mailto=`.
- Env var: OPENALEX_EMAIL (recomendado para o polite pool)

Docs: https://docs.openalex.org/
"""
from __future__ import annotations

import os
from typing import Any, Optional

import httpx

_BASE = "https://api.openalex.org"


def _params(extra: dict) -> dict:
    p = dict(extra)
    email = os.environ.get("OPENALEX_EMAIL")
    if email:
        p["mailto"] = email
    return p


async def search_works(query: str, per_page: int = 10, filter_: Optional[str] = None) -> list[dict]:
    from integrations import evidence_cache
    # Cache não considera filter_ (raro de usar). Só cacheia consultas simples.
    if not filter_:
        cached = await evidence_cache.get("openalex", query, per_page)
        if cached is not None:
            return cached
    url = f"{_BASE}/works"
    params = _params({"search": query, "per_page": per_page})
    if filter_:
        params["filter"] = filter_
    async with httpx.AsyncClient(timeout=20.0) as http:
        r = await http.get(url, params=params)
        r.raise_for_status()
        data = r.json()
    items = []
    for w in data.get("results", []) or []:
        items.append({
            "id": w.get("id"),
            "title": w.get("title"),
            "year": w.get("publication_year"),
            "doi": w.get("doi"),
            "type": w.get("type"),
            "cited_by_count": w.get("cited_by_count"),
            "authors": [
                (a.get("author") or {}).get("display_name")
                for a in (w.get("authorships") or [])[:5]
            ],
            "venue": ((w.get("primary_location") or {}).get("source") or {}).get("display_name"),
            "open_access_url": (w.get("open_access") or {}).get("oa_url"),
        })
    if not filter_:
        await evidence_cache.put("openalex", query, per_page, items)
    return items


async def concept_lookup(query: str, per_page: int = 5) -> list[dict]:
    """Descobre 'concepts' (temas) mais próximos de uma consulta livre."""
    url = f"{_BASE}/concepts"
    params = _params({"search": query, "per_page": per_page})
    async with httpx.AsyncClient(timeout=20.0) as http:
        r = await http.get(url, params=params)
        r.raise_for_status()
        data = r.json()
    return [
        {
            "id": c.get("id"),
            "name": c.get("display_name"),
            "level": c.get("level"),
            "works_count": c.get("works_count"),
        }
        for c in data.get("results", []) or []
    ]
