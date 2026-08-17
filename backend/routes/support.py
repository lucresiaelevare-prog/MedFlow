"""Support contacts + mental-health signal detection & alerts.

Owns: SUPPORT_CONTACTS list, high/medium-risk detection, LLM classifier,
alert persistence, and 4 endpoints. Import `persist_mental_health_alert`
+ `detect_high_risk` + `llm_classify_mental_health` + `detect_medium_risk_keywords`
+ `mental_health_message` from the check-in module.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException

from core import EMERGENT_LLM_KEY, _iso, _now, db, require_user
from models import AlertAckInput, SupportContactRequestInput

logger = logging.getLogger("medflow.support")
router = APIRouter(prefix="/api", tags=["support"])


SUPPORT_CONTACTS: list[dict] = [
    {
        "slug": "cvv",
        "name": "CVV — Centro de Valorização da Vida",
        "kind": "prevencao_suicidio",
        "description": "Apoio emocional e prevenção do suicídio. Ligação gratuita, sigilosa, 24h por dia.",
        "phone": "188",
        "phone_display": "188",
        "chat_url": "https://cvv.org.br/chat/",
        "email": "atendimento@cvv.org.br",
        "hours": "24 horas, todos os dias",
        "priority": True,
    },
    {
        "slug": "samu",
        "name": "SAMU — Emergência médica",
        "kind": "emergencia",
        "description": "Em risco imediato à vida (ideação suicida em ato, sobredosagem, crise aguda), acione o SAMU.",
        "phone": "192",
        "phone_display": "192",
        "hours": "24 horas",
        "priority": True,
    },
    {
        "slug": "caps",
        "name": "CAPS — Centro de Atenção Psicossocial",
        "kind": "saude_mental_publica",
        "description": "Rede pública SUS de acolhimento em crises psicológicas e transtornos mentais. Atendimento presencial próximo a você.",
        "url": "https://www.gov.br/saude/pt-br/acesso-a-informacao/acoes-e-programas/caps",
        "hours": "Horário comercial (varia por município)",
    },
    {
        "slug": "abrames",
        "name": "ABRAMES — Apoio ao estudante de medicina",
        "kind": "estudante_medicina",
        "description": "Rede da Associação Brasileira dos Estudantes de Medicina com canais de escuta e materiais sobre burnout, ansiedade e depressão no curso.",
        "url": "https://abrames.org.br/",
        "hours": "Consulte o site da sua atlética/DA",
    },
    {
        "slug": "mapa-saude-mental",
        "name": "Mapa Saúde Mental — grupos gratuitos",
        "kind": "saude_mental_gratuita",
        "description": "Diretório colaborativo com atendimentos gratuitos e sociais em todo o Brasil (psicólogos, clínicas-escola, ONGs).",
        "url": "https://mapasaudemental.com.br/",
        "hours": "24 horas (busca online)",
    },
    {
        "slug": "apoio-universitario",
        "name": "Núcleo de Apoio da sua universidade",
        "kind": "universitario",
        "description": "Sua faculdade provavelmente tem um serviço de apoio psicopedagógico (SAE, DAE, NAE). Procure a coordenação do curso ou o setor de assuntos estudantis.",
        "hours": "Horário acadêmico",
    },
]


# ---------------------------------------------------------------------------
# Mental health signal detection (Onda 3.2)
# ---------------------------------------------------------------------------
HIGH_RISK_PATTERNS: list[str] = [
    r"\bme\s+matar\b",
    r"\bme\s+matando\b",
    r"\bquero\s+morrer\b",
    r"\bn[aã]o\s+quero\s+(mais\s+)?viver\b",
    r"\bn[aã]o\s+quero\s+existir\b",
    r"\bsuic[ií]dio\b",
    r"\bsuicidar\b",
    r"\bme\s+machucar\b",
    r"\bautoles[aã]o\b",
    r"\bacabar\s+com\s+tudo\b",
    r"\bn[aã]o\s+vale\s+a\s+pena\s+viver\b",
    r"\bn[aã]o\s+aguento\s+mais\s+viver\b",
    r"\bsumir\s+do\s+mundo\b",
]
HIGH_RISK_COMPILED = [re.compile(p, re.IGNORECASE) for p in HIGH_RISK_PATTERNS]

MEDIUM_RISK_KEYWORDS: list[str] = [
    "sem esperança", "sem esperanca", "vazio por dentro", "cansado de tudo",
    "exausto emocionalmente", "não sirvo", "nao sirvo", "sou um peso",
    "sozinho de verdade", "ninguém se importa", "ninguem se importa",
    "pânico", "panico constante", "não durmo há", "nao durmo ha",
    "chorando sem motivo", "não consigo mais", "nao consigo mais",
    "surto", "colapso", "burnout", "quero desistir",
]

ALERT_ACTIVE_HOURS = 24


def detect_high_risk(text: str) -> bool:
    if not text or not text.strip():
        return False
    return any(p.search(text) for p in HIGH_RISK_COMPILED)


def detect_medium_risk_keywords(text: str) -> list[str]:
    if not text or not text.strip():
        return []
    low = text.lower()
    return [k for k in MEDIUM_RISK_KEYWORDS if k in low]


async def llm_classify_mental_health(text: str) -> dict:
    """Ask Claude to classify subtler patterns. Returns {level, tags, summary}."""
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    prompt = f"""
Você é um classificador clínico auxiliar do MedFlow. Analise UM texto livre de um estudante brasileiro de medicina no check-in diário. NÃO diagnostique. Apenas classifique.

Texto do estudante:
\"\"\"{text}\"\"\"

Devolva EXCLUSIVAMENTE um JSON válido:
{{"level": "none|low|medium|high", "tags": ["<tag1>", "<tag2>"], "summary": "<frase curta>"}}

Regras:
- "high": sinais explícitos de ideação/plano suicida, autoagressão, ou risco imediato.
- "medium": desesperança persistente, isolamento profundo, ataques de pânico frequentes, exaustão emocional grave, sensação de não conseguir mais.
- "low": estresse acadêmico normal, ansiedade pontual, cansaço sem desesperança.
- "none": texto neutro/positivo/sem sinais.
- tags válidas: ["ideacao_suicida","autoagressao","desesperanca","isolamento","ansiedade","panico","burnout","exaustao","insonia","tristeza","sobrecarga"]
- summary em pt-BR, no máx 15 palavras, sem julgamento.
- Nada de markdown, aspas extras ou comentários.
""".strip()

    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"medflow-mh-{uuid.uuid4().hex[:10]}",
        system_message="Você classifica sinais de saúde mental em textos curtos, sem diagnosticar.",
    ).with_model("anthropic", "claude-sonnet-4-5-20250929")
    try:
        reply = await chat.send_message(UserMessage(text=prompt))
    except Exception as exc:  # noqa: BLE001
        logger.exception("MH classifier failed: %s", exc)
        return {
            "level": "medium",
            "tags": ["sobrecarga"],
            "summary": "Não foi possível concluir a triagem automática.",
        }
    text_reply = reply if isinstance(reply, str) else str(reply)
    m = re.search(r"\{.*\}", text_reply, re.DOTALL)
    if not m:
        return {"level": "none", "tags": [], "summary": ""}
    try:
        data = json.loads(m.group(0))
    except Exception:  # noqa: BLE001
        return {"level": "none", "tags": [], "summary": ""}
    level = str(data.get("level", "none")).lower()
    if level not in {"none", "low", "medium", "high"}:
        level = "none"
    raw_tags = data.get("tags") or []
    tags = [str(t)[:40] for t in raw_tags if isinstance(t, (str, int))][:6]
    return {"level": level, "tags": tags, "summary": str(data.get("summary", ""))[:200]}


def mental_health_message(level: str) -> tuple[str, list[str]]:
    if level == "high":
        return (
            "Percebi que você compartilhou algo muito pesado. Você não precisa passar por isso sozinho agora. "
            "O CVV atende 24h, é gratuito e sigiloso — ligar pra alguém pode ajudar mesmo quando parece que nada vai ajudar.",
            ["cvv", "samu", "caps"],
        )
    if level == "medium":
        return (
            "Notei sinais de que os últimos dias estão pesando. Cuidar disso agora, com apoio, é o mais inteligente que dá pra fazer. "
            "Dá uma olhada nos canais que a gente separou — são gratuitos e nenhum julgamento.",
            ["cvv", "caps", "mapa-saude-mental"],
        )
    return ("", [])


async def persist_mental_health_alert(
    user_id: str, level: str, tags: list[str], summary: str,
    checkin_id: str, source: str, suggested: list[str],
) -> dict:
    active_until = _now() + timedelta(hours=ALERT_ACTIVE_HOURS)
    doc = {
        "id": f"mha_{uuid.uuid4().hex[:10]}",
        "user_id": user_id,
        "level": level,
        "tags": tags,
        "summary": summary,
        "source": source,          # "checkin_free_text" | "checkin_scale"
        "source_ref": checkin_id,
        "suggested_contacts": suggested,
        "active_until": _iso(active_until),
        "acknowledged": False,
        "created_at": _iso(_now()),
    }
    await db.mental_health_alerts.insert_one(dict(doc))
    return doc


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.get("/support-contacts")
async def list_support_contacts(user: dict = Depends(require_user)) -> dict:
    return {"contacts": SUPPORT_CONTACTS}


@router.post("/support-contacts/log")
async def log_support_contact(
    payload: SupportContactRequestInput, user: dict = Depends(require_user)
) -> dict:
    """Log which support contact was surfaced. Anonymous count only — no free text stored."""
    valid = {c["slug"] for c in SUPPORT_CONTACTS}
    if payload.contact_slug not in valid:
        raise HTTPException(status_code=400, detail="contact_slug inválido")
    if payload.method not in {"call", "chat", "link"}:
        raise HTTPException(status_code=400, detail="method inválido")
    doc = {
        "id": f"sc_{uuid.uuid4().hex[:10]}",
        "user_id": user["user_id"],
        "contact_slug": payload.contact_slug,
        "method": payload.method,
        "created_at": _iso(_now()),
    }
    await db.support_contact_logs.insert_one(dict(doc))
    return {"ok": True}


@router.get("/mental-health/alert")
async def get_active_alert(user: dict = Depends(require_user)) -> dict:
    """Return the most recent active (not-yet-expired) alert if any."""
    now_iso = _iso(_now())
    doc = await db.mental_health_alerts.find_one(
        {"user_id": user["user_id"], "active_until": {"$gte": now_iso}},
        {"_id": 0},
        sort=[("created_at", -1)],
    )
    if not doc:
        return {"alert": None}
    message, suggested = mental_health_message(doc["level"])
    return {
        "alert": {
            "id": doc["id"],
            "level": doc["level"],
            "tags": doc.get("tags", []),
            "summary": doc.get("summary", ""),
            "message": message,
            "suggested_contacts": doc.get("suggested_contacts") or suggested,
            "created_at": doc["created_at"],
            "active_until": doc["active_until"],
            "acknowledged": doc.get("acknowledged", False),
        }
    }


@router.post("/mental-health/alert/ack")
async def ack_alert(payload: AlertAckInput, user: dict = Depends(require_user)) -> dict:
    result = await db.mental_health_alerts.update_one(
        {"id": payload.alert_id, "user_id": user["user_id"]},
        {"$set": {"acknowledged": True, "acknowledged_at": _iso(_now())}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="alerta não encontrado")
    return {"ok": True}
