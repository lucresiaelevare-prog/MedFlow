"""Reschedule engine — reorganização automática da agenda por fadiga/saturação.

Filosofia:
    Hoje o motor DIZ "você está cansado".
    A partir daqui, o motor AGE: "eu reorganizei sua tarde."

Este módulo NÃO expõe rotas — apenas lógica pura. As rotas vivem em
`routes/reschedule.py`. Nada aqui invalida a memória de aprendizagem
(não deleta agenda_blocks recorrentes). Reorganização é sempre uma
sobreposição date-specific + `hidden_dates` para o dia afetado.

Modelo:
    - `agenda_reschedules` — 1 doc por (user_id, date_iso). status pending|accepted|dismissed
    - `agenda_blocks` original com `hidden_dates: ["2026-02-15", ...]` fica invisível nessas datas
    - Novos blocos com `source: "reschedule"` e `date: <today>` compõem a agenda substituta

Fluxo:
    1. `build_proposal(user_id)` — computa ações se saturação/fadiga sinalizarem.
    2. `save_pending(user_id, proposal)` — persiste com status=pending.
    3. `apply(user_id, resch_id)` — materializa: adiciona hidden_dates + insere blocos novos.
    4. `dismiss(user_id, resch_id)` — só marca status.
    5. `undo(user_id, resch_id)` — remove hidden_dates + apaga blocos gerados.
"""
from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Optional

from core import _iso, _now, _today_str, db
from context_engine import detect_fatigue, is_saturated


# ─── Helpers de tempo ─────────────────────────────────────────
def _local_now():
    """Horário local Brasil (UTC-3)."""
    return _now() - timedelta(hours=3)


def _local_hhmm() -> str:
    lt = _local_now()
    return f"{lt.hour:02d}:{lt.minute:02d}"


def _local_dow() -> int:
    return _local_now().weekday()


def _mins(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _hhmm(minutes: int) -> str:
    minutes = max(0, min(24 * 60 - 1, int(minutes)))
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


# ─── Leitura da agenda de hoje ────────────────────────────────
async def _todays_blocks(user_id: str, today_iso: str, dow: int) -> list[dict]:
    """Retorna blocos ativos hoje (recorrentes por dow OU date-specific).

    Blocos com `hidden_dates` contendo `today_iso` são filtrados (foram
    escondidos por uma reordenação anterior — a substituição já existe
    como bloco date-specific).
    """
    cursor = db.agenda_blocks.find(
        {"user_id": user_id,
         "$or": [{"day_of_week": dow}, {"date": today_iso}]},
        {"_id": 0},
    )
    out: list[dict] = []
    async for b in cursor:
        hidden = b.get("hidden_dates") or []
        if today_iso in hidden and b.get("date") != today_iso:
            continue  # recorrente escondida só neste dia
        out.append(b)
    out.sort(key=lambda x: x.get("start_time", "23:59"))
    return out


# ─── Decisão: precisa reorganizar? ────────────────────────────
async def _detect_trigger(user_id: str) -> Optional[dict]:
    """Retorna o motivo forte de reordenação, ou None.

    Ordem de prioridade:
      1. Saturação (stress_high, mood_low_persistent, sleep_low_persistent, abandon_streak)
      2. Fadiga em sessão ativa (últimos 30 min)
    """
    saturated, sat_ev = await is_saturated(user_id)
    if saturated:
        return {"reason": "saturation", "detail": sat_ev}

    fat = await detect_fatigue(user_id, window_min=30)
    if fat.get("fatigued"):
        return {
            "reason": "fatigue",
            "detail": {"rule": "session_fatigue", "reason_text": fat.get("reason"), **(fat.get("evidence") or {})},
        }
    return None


# ─── Construção do plano de ações ─────────────────────────────
COGNITIVE_CATS = {"study", "academic"}
CARE_CAT = "care"


def _copy_for(reason: str) -> dict:
    """Textos de UI por motivo. Sempre honesto, sempre concreto."""
    if reason == "saturation":
        return {
            "headline": "Eu reorganizei sua tarde.",
            "subline": "Detectei sinais de sobrecarga. Preferi consolidar do que acumular.",
        }
    return {
        "headline": "Ajustei o restante do seu dia.",
        "subline": "Percebi cansaço na sua última sessão. Menos carga agora rende mais depois.",
    }


def _pause_block(user_id: str, today_iso: str, start_min: int, minutes: int = 20) -> dict:
    end_min = start_min + minutes
    return {
        "id": f"blk_{uuid.uuid4().hex[:10]}",
        "user_id": user_id,
        "title": "Pausa restauradora",
        "category": CARE_CAT,
        "start_time": _hhmm(start_min),
        "end_time": _hhmm(end_min),
        "day_of_week": None,
        "date": today_iso,
        "note": "Descanso ativo. Sem tela. Água, alongamento, ar.",
        "color": "#14B8A6",
        "done": False,
        "created_at": _iso(_now()),
        "source": "reschedule",
    }


def _shorten_action(block: dict, cap_min: int = 30) -> Optional[dict]:
    """Encurta um bloco cognitivo mantendo start_time. Retorna None se já é curto."""
    start = _mins(block["start_time"])
    end = _mins(block["end_time"])
    if (end - start) <= cap_min:
        return None
    new_end = start + cap_min
    return {
        "type": "shorten",
        "block_id": block["id"],
        "title": block["title"],
        "category": block.get("category"),
        "from_start": block["start_time"],
        "from_end": block["end_time"],
        "to_start": block["start_time"],
        "to_end": _hhmm(new_end),
        "note_added": "Encurtado hoje: prioridade em consolidar, não em avançar.",
    }


def _move_action(block: dict, push_min: int = 90) -> dict:
    start = _mins(block["start_time"])
    end = _mins(block["end_time"])
    dur = end - start
    new_start = min(23 * 60 + 30 - dur, start + push_min)
    return {
        "type": "move",
        "block_id": block["id"],
        "title": block["title"],
        "category": block.get("category"),
        "from_start": block["start_time"],
        "from_end": block["end_time"],
        "to_start": _hhmm(new_start),
        "to_end": _hhmm(new_start + dur),
        "note_added": f"Adiado {push_min // 60}h — janela mais adequada ao seu estado.",
    }


async def build_proposal(user_id: str) -> dict:
    """Se houver saturação ou fadiga, monta ações concretas.

    Retorna sempre {needed: bool, ...}. Idempotente: não persiste nada.
    """
    trigger = await _detect_trigger(user_id)
    if not trigger:
        return {"needed": False, "reason": None}

    today_iso = _today_str()
    dow = _local_dow()
    now_min = _mins(_local_hhmm())

    blocks = await _todays_blocks(user_id, today_iso, dow)

    # Blocos que ainda vão acontecer (não terminaram) e não estão marcados como done
    remaining_cognitive = [
        b for b in blocks
        if b.get("category") in COGNITIVE_CATS
        and not b.get("done")
        and _mins(b.get("end_time", "00:00")) > now_min
    ]

    # ─── Construção das ações ─────────────────────────────────
    actions: list[dict] = []

    # 1. Pausa restauradora agora (só uma) — desde que haja bloco cognitivo restante
    #    e o horário atual esteja entre 6h e 22h (não sugerir pausa de madrugada).
    lt = _local_now()
    if remaining_cognitive and 6 <= lt.hour < 22:
        # Aloca a pausa a partir do minuto atual (arredondado pra 5 min pra frente)
        pause_start = (now_min + 4) // 5 * 5
        pause_minutes = 20 if trigger["reason"] == "saturation" else 15
        pause = _pause_block(user_id, today_iso, pause_start, pause_minutes)
        actions.append({
            "type": "insert",
            "block": pause,
        })

    # 2. Encurtar blocos cognitivos longos (>40min → 30min)
    for b in remaining_cognitive:
        act = _shorten_action(b, cap_min=30)
        if act:
            actions.append(act)

    # 3. Mover blocos cognitivos que começam nas próximas 90 min (para depois)
    for b in remaining_cognitive:
        start_min = _mins(b["start_time"])
        if now_min < start_min <= now_min + 90:
            # Só move se não foi encurtado (evita ação dupla no mesmo bloco)
            if any(a.get("block_id") == b["id"] and a["type"] == "shorten" for a in actions):
                continue
            actions.append(_move_action(b, push_min=90))

    if not actions:
        return {
            "needed": False,
            "reason": trigger["reason"],
            "detail": trigger["detail"],
            "note": "Motivo detectado, mas nenhuma ação útil para o restante de hoje.",
        }

    # ─── Resumo humano das ações ──────────────────────────────
    n_short = sum(1 for a in actions if a["type"] == "shorten")
    n_move = sum(1 for a in actions if a["type"] == "move")
    n_ins = sum(1 for a in actions if a["type"] == "insert")
    summary_parts: list[str] = []
    if n_ins:
        summary_parts.append("adicionei uma pausa restauradora")
    if n_short:
        summary_parts.append(f"encurtei {n_short} bloco{'s' if n_short > 1 else ''}")
    if n_move:
        summary_parts.append(f"adiei {n_move} bloco{'s' if n_move > 1 else ''}")
    summary = "Eu " + " · ".join(summary_parts) + "."

    copy = _copy_for(trigger["reason"])
    return {
        "needed": True,
        "reason": trigger["reason"],
        "detail": trigger["detail"],
        "actions": actions,
        "summary": summary,
        "headline": copy["headline"],
        "subline": copy["subline"],
    }


# ─── Persistência ─────────────────────────────────────────────
async def get_today_reschedule(user_id: str) -> Optional[dict]:
    """Retorna o reschedule ATIVO (pending ou accepted) de hoje, se houver."""
    today_iso = _today_str()
    doc = await db.agenda_reschedules.find_one(
        {"user_id": user_id, "date_iso": today_iso, "status": {"$in": ["pending", "accepted"]}},
        {"_id": 0},
    )
    return doc


async def save_pending(user_id: str, proposal: dict) -> dict:
    """Cria (ou substitui) o reschedule pending de hoje."""
    today_iso = _today_str()
    # Se já existe um pending/accepted, retorna ele (idempotente).
    existing = await get_today_reschedule(user_id)
    if existing:
        return existing

    resch_id = f"resch_{uuid.uuid4().hex[:10]}"
    doc = {
        "id": resch_id,
        "user_id": user_id,
        "date_iso": today_iso,
        "reason": proposal["reason"],
        "reason_detail": proposal.get("detail") or {},
        "status": "pending",
        "actions": proposal["actions"],
        "summary": proposal["summary"],
        "headline": proposal["headline"],
        "subline": proposal["subline"],
        "created_at": _iso(_now()),
        "applied_at": None,
        "dismissed_at": None,
    }
    await db.agenda_reschedules.insert_one(dict(doc))
    return doc


async def apply(user_id: str, resch_id: str) -> dict:
    """Materializa as ações: hidden_dates + blocos date-specific."""
    doc = await db.agenda_reschedules.find_one(
        {"id": resch_id, "user_id": user_id}, {"_id": 0},
    )
    if not doc:
        raise LookupError("Reschedule não encontrado")
    if doc["status"] != "pending":
        return doc  # idempotente

    today_iso = doc["date_iso"]

    for act in doc["actions"]:
        if act["type"] == "insert":
            # Já vem com date=today_iso e source=reschedule
            await db.agenda_blocks.insert_one(dict(act["block"]))
            continue

        # shorten / move: 1) esconde original hoje  2) cria bloco date-specific
        block_id = act["block_id"]
        original = await db.agenda_blocks.find_one({"id": block_id, "user_id": user_id}, {"_id": 0})
        if not original:
            continue

        await db.agenda_blocks.update_one(
            {"id": block_id, "user_id": user_id},
            {"$addToSet": {"hidden_dates": today_iso}},
        )

        new_block = {
            "id": f"blk_{uuid.uuid4().hex[:10]}",
            "user_id": user_id,
            "title": original["title"],
            "category": original.get("category"),
            "start_time": act["to_start"],
            "end_time": act["to_end"],
            "day_of_week": None,
            "date": today_iso,
            "note": ((original.get("note") or "") + "  \n" + (act.get("note_added") or "")).strip(),
            "color": original.get("color"),
            "done": False,
            "created_at": _iso(_now()),
            "source": "reschedule",
            "override_of": block_id,
        }
        await db.agenda_blocks.insert_one(dict(new_block))

    await db.agenda_reschedules.update_one(
        {"id": resch_id},
        {"$set": {"status": "accepted", "applied_at": _iso(_now())}},
    )
    doc["status"] = "accepted"
    doc["applied_at"] = _iso(_now())
    return doc


async def dismiss(user_id: str, resch_id: str) -> dict:
    doc = await db.agenda_reschedules.find_one(
        {"id": resch_id, "user_id": user_id}, {"_id": 0},
    )
    if not doc:
        raise LookupError("Reschedule não encontrado")
    if doc["status"] == "dismissed":
        return doc
    await db.agenda_reschedules.update_one(
        {"id": resch_id},
        {"$set": {"status": "dismissed", "dismissed_at": _iso(_now())}},
    )
    doc["status"] = "dismissed"
    return doc


async def undo(user_id: str, resch_id: str) -> dict:
    """Desfaz um reschedule aplicado. Remove hidden_dates + apaga inserts."""
    doc = await db.agenda_reschedules.find_one(
        {"id": resch_id, "user_id": user_id}, {"_id": 0},
    )
    if not doc:
        raise LookupError("Reschedule não encontrado")
    if doc["status"] != "accepted":
        raise ValueError("Só é possível desfazer um reschedule aplicado")

    today_iso = doc["date_iso"]

    # Remove hidden_dates de todos os originais tocados
    original_ids = {
        a["block_id"] for a in doc["actions"] if a["type"] in ("shorten", "move")
    }
    for oid in original_ids:
        await db.agenda_blocks.update_one(
            {"id": oid, "user_id": user_id},
            {"$pull": {"hidden_dates": today_iso}},
        )

    # Apaga blocos date-specific de hoje que foram gerados por este reschedule
    await db.agenda_blocks.delete_many(
        {"user_id": user_id, "date": today_iso, "source": "reschedule"},
    )

    await db.agenda_reschedules.update_one(
        {"id": resch_id},
        {"$set": {"status": "dismissed", "dismissed_at": _iso(_now()),
                  "undone_at": _iso(_now())}},
    )
    doc["status"] = "dismissed"
    return doc
