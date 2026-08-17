"""Curated learning resources library."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends

from core import db, require_user

router = APIRouter(prefix="/api", tags=["resources"])


RESOURCES: list[dict] = [
    {"slug": "sleep-hygiene", "title": "Higiene do sono para estudantes de medicina",
     "type": "artigo", "duration_min": 6, "category": "sono",
     "pillar": "sono",
     "excerpt": "Regularidade de horário, quarto escuro e sem telas antes de deitar: práticas que valem mais para o estudante de medicina do que qualquer estimulante.",
     "url": "https://www.sleepfoundation.org/sleep-hygiene"},
    {"slug": "active-recall", "title": "Active recall: por que releitura não funciona",
     "type": "artigo", "duration_min": 8, "category": "estudo",
     "pillar": "estudos",
     "excerpt": "Testar-se ativamente com flashcards e questões vale mais do que reler: a recuperação ativa fortalece a trilha de memória usada na prova.",
     "url": "https://www.retrievalpractice.org/why-it-works"},
    {"slug": "pomodoro-medstudent", "title": "Pomodoro adaptado para provas curtas",
     "type": "artigo", "duration_min": 5, "category": "estudo",
     "pillar": "estudos",
     "excerpt": "Blocos de 25/5 para matérias densas e 50/10 para revisão de véspera — a pausa real (sem celular) é o que consolida o bloco.",
     "url": "https://todoist.com/productivity-methods/pomodoro-technique"},
    {"slug": "ted-exercicio-cerebro", "title": "TED: os benefícios do exercício para o cérebro que muda",
     "type": "video", "duration_min": 12, "category": "saude_fisica",
     "pillar": "saude_fisica",
     "excerpt": "Wendy Suzuki mostra, com neurociência, como o exercício físico melhora foco, humor e memória — os três pilares da semana de provas."},
    {"slug": "alimentacao-plantao-24h", "title": "Alimentação em plantão de 24h",
     "type": "artigo", "duration_min": 4, "category": "plantao",
     "pillar": "saude_fisica",
     "excerpt": "Hidratar no dia anterior, comer uma refeição sólida antes do plantão e levar snacks de proteína e carboidrato complexo — o que evita o desmaio das 3h.",
     "url": "https://www.medscape.com/viewarticle/residency-101-how-survive-24-hour-call-shift-2025a1000i9l"},
    {"slug": "movimento-microtreino", "title": "Micro-treinos de 7 minutos entre aulas",
     "type": "artigo", "duration_min": 3, "category": "movimento",
     "pillar": "saude_fisica",
     "excerpt": "Sete exercícios com o peso do corpo em sequência — dá para fazer entre duas aulas ou no intervalo do plantão.",
     "url": "https://www.nbcnews.com/better/health/7-minute-workout-exactly-all-you-need-ncna919691"},
    {"slug": "conexao-social-med", "title": "Sozinho na medicina: por que grupos de estudo salvam",
     "type": "artigo", "duration_min": 5, "category": "social",
     "pillar": "social",
     "excerpt": "Conexão social não é distração: Harvard mostra que pertencer a um grupo reduz cortisol e melhora o desempenho — e também a saúde física.",
     "url": "https://hms.harvard.edu/news/social-connection"},
    {"slug": "podcast-cafe-com-med", "title": "Café Com Med: o podcast sobre medicina e residência",
     "type": "podcast", "duration_min": 32, "category": "estudo",
     "pillar": "estudos",
     "excerpt": "Bate-papo em português sobre preparação para residência médica, com episódios curtos que cabem no trajeto até a faculdade.",
     "url": "https://open.spotify.com/show/39K6aniJ8SYwPI4kWbA5Jx"},
    {"slug": "ansiedade-prova", "title": "Organizando o cronograma de estudos de Medicina",
     "type": "artigo", "duration_min": 6, "category": "ansiedade",
     "pillar": "bem_estar",
     "excerpt": "Planejar revisões, questões e pausas de forma realista diminui a ansiedade de véspera — um plano claro pesa menos que a cobrança infinita.",
     "url": "https://sanarmed.com/cronograma-de-estudos-para-calouros-de-medicina-como-comecar/"},
    {"slug": "diario-de-estudos", "title": "Diário de estudos: como registrar o que aprendeu hoje",
     "type": "artigo", "duration_min": 6, "category": "estudo",
     "pillar": "estudos",
     "excerpt": "Três linhas por dia — o que revisei, o que errei e o que falta — são suficientes para transformar a sensação de improviso em acompanhamento real.",
     "url": "https://sanarmed.com/cronograma-de-estudos-para-calouros-de-medicina-como-comecar/"},
]


@router.get("/resources")
async def list_resources(
    user: dict = Depends(require_user),
    pillar: Optional[str] = None,
    category: Optional[str] = None,
) -> dict:
    items = list(RESOURCES)
    # Anexa entradas do CMS
    cms_items = await db.cms_resources.find({}, {"_id": 0}).to_list(200)
    for c in cms_items:
        items.append({
            "slug": c.get("slug") or c.get("id"),
            "title": c.get("title"), "type": c.get("type"),
            "duration_min": c.get("duration_min"),
            "category": c.get("category"), "pillar": c.get("pillar"),
            "excerpt": c.get("excerpt", ""), "url": c.get("url"),
        })
    if pillar:
        items = [r for r in items if r.get("pillar") == pillar]
    if category:
        items = [r for r in items if r.get("category") == category]
    return {"resources": items}
