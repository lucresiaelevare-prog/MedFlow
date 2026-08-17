"""Context Engine — cronotipo, energia, saturação, fadiga (diferenciais MedFlow).

Este módulo é o cérebro contextual que os concorrentes não têm. Concentra
as heurísticas que traduzem sinais crus (chronotype, energy_peak, sleep,
stress, tentativas recentes) em decisões que ninguém mais consegue tomar.

Sem estado próprio: só lê `user_profiles`, `checkins`, `recommendation_events`
e `student_content_events`. Nada é gravado aqui.

Filosofia:
    Contexto → Recomendação → Ação → Feedback → Aprendizado.
    Toda função aqui existe pra melhorar a PRÓXIMA decisão.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Optional

from core import _now, db

# ─── Hora local (Brasil UTC-3) ─────────────────────────────────
def local_hour() -> int:
    return (_now().hour - 3) % 24


def hour_bucket(h: int) -> str:
    if 5 <= h < 12:
        return "manha"
    if 12 <= h < 18:
        return "tarde"
    if 18 <= h < 23:
        return "noite"
    return "madrugada"


def _peak_from_chronotype(ct: Optional[str]) -> Optional[str]:
    """Fallback: se o aluno não declarou energy_peak, usa cronotipo."""
    if not ct:
        return None
    ct = ct.strip().lower()
    if ct.startswith("matu"):
        return "manha"
    if ct.startswith("vesp"):
        return "tarde"
    if ct.startswith("notu"):
        return "noite"
    return None


def peak_bucket_of(profile: dict) -> Optional[str]:
    """Pico do aluno em bucket (manha/tarde/noite). None se desconhecido."""
    ep = (profile or {}).get("energy_peak")
    if ep:
        ep = ep.strip().lower()
        if ep in ("manha", "tarde", "noite"):
            return ep
    return _peak_from_chronotype((profile or {}).get("chronotype"))


def optimal_window_label(peak: Optional[str]) -> Optional[str]:
    if peak == "manha":
        return "Melhor entre 8h e 11h."
    if peak == "tarde":
        return "Melhor entre 14h e 17h."
    if peak == "noite":
        return "Melhor entre 19h e 21h."
    return None


def _parse_hhmm(v: Optional[str]) -> Optional[int]:
    if not v or ":" not in v:
        return None
    try:
        return int(str(v).split(":")[0])
    except Exception:
        return None


def sleep_debt(profile: dict, last_sleep: Optional[float]) -> float:
    """Débito de sono em horas (0 se acima da meta, sempre >=0)."""
    target = (profile or {}).get("target_sleep_hours") or 7
    if last_sleep is None:
        return 0.0
    try:
        deficit = float(target) - float(last_sleep)
    except Exception:
        return 0.0
    return max(0.0, round(deficit, 2))


# ─── Saturação (P3 do briefing) ───────────────────────────────
async def is_saturated(user_id: str) -> tuple[bool, dict]:
    """Detecta saturação combinada (retorna flag + evidência).

    Regras (basta UMA para saturar):
      A. Último check-in com stress >= 7
      B. Últimos 3 check-ins com mood <= 4
      C. Últimos 3 check-ins com sleep <= 3
      D. >= 3 recommendation_events com outcome='abandoned' nas últimas 48h
    """
    ev: dict = {}

    last_ck = await db.checkins.find_one(
        {"user_id": user_id}, {"_id": 0, "stress": 1, "mood": 1, "sleep": 1},
        sort=[("created_at", -1)],
    )
    if last_ck and (last_ck.get("stress") or 0) >= 7:
        return True, {"rule": "stress_high", "stress": int(last_ck["stress"])}

    # Últimos 3 check-ins — humor / sono
    moods: list[int] = []
    sleeps: list[int] = []
    async for c in db.checkins.find(
        {"user_id": user_id}, {"_id": 0, "mood": 1, "sleep": 1},
    ).sort("created_at", -1).limit(3):
        if c.get("mood") is not None:
            try:
                moods.append(int(c["mood"]))
            except Exception:
                pass
        if c.get("sleep") is not None:
            try:
                sleeps.append(int(c["sleep"]))
            except Exception:
                pass

    if len(moods) >= 3 and max(moods) <= 4:
        return True, {"rule": "mood_low_persistent", "moods": moods}
    if len(sleeps) >= 3 and max(sleeps) <= 3:
        return True, {"rule": "sleep_low_persistent", "sleeps": sleeps}

    # Abandonos consecutivos nas últimas 48h
    since = (_now() - timedelta(hours=48)).isoformat()
    aband = await db.recommendation_events.count_documents({
        "user_id": user_id, "outcome": "abandoned", "abandoned_at": {"$gte": since},
    })
    if aband >= 3:
        return True, {"rule": "abandon_streak", "count": aband, "window_hours": 48}

    return False, ev


# ─── Fadiga em sessão ativa (P4 do briefing) ───────────────────
async def detect_fatigue(user_id: str, window_min: int = 30) -> dict:
    """Sinais de cansaço nos últimos `window_min` minutos.

    Sinais:
      - >= 3 erros nos últimos 5 answered
      - tempo médio de resposta subindo (tail vs head)
      - >= 5 answered sem 1 correto seguido

    Retorna:
      {
        fatigued: bool,
        reason: str | None,
        evidence: {last_answered_count, correct_recent, incorrect_recent, avg_time_recent}
      }
    """
    since = (_now() - timedelta(minutes=window_min)).isoformat()
    events: list[dict] = []
    async for e in db.student_content_events.find(
        {"user_id": user_id, "event_type": "answered", "created_at": {"$gte": since}},
        {"_id": 0, "correct": 1, "time_spent_sec": 1, "created_at": 1},
    ).sort("created_at", 1):
        events.append(e)

    n = len(events)
    if n < 5:
        return {"fatigued": False, "reason": None, "evidence": {"n": n}}

    last5 = events[-5:]
    correct5 = sum(1 for e in last5 if e.get("correct") is True)
    incorrect5 = sum(1 for e in last5 if e.get("correct") is False)

    # (1) muitos erros seguidos
    if incorrect5 >= 3:
        return {
            "fatigued": True,
            "reason": "Percebi sinais de cansaço. Uma pausa pode aumentar seu rendimento.",
            "evidence": {"incorrect_last5": incorrect5, "correct_last5": correct5, "n": n},
        }

    # (2) tempo médio subindo (comparar 1ª metade vs 2ª metade)
    times = [int(e.get("time_spent_sec") or 0) for e in events if e.get("time_spent_sec")]
    if len(times) >= 6:
        half = len(times) // 2
        head_avg = sum(times[:half]) / half
        tail_avg = sum(times[half:]) / (len(times) - half)
        if head_avg > 0 and tail_avg > head_avg * 1.6:
            return {
                "fatigued": True,
                "reason": "Percebi sinais de cansaço. Uma pausa pode aumentar seu rendimento.",
                "evidence": {"head_avg_sec": round(head_avg, 1), "tail_avg_sec": round(tail_avg, 1), "n": n},
            }

    # (3) 5+ answered sem acerto
    if n >= 5 and all(e.get("correct") is not True for e in last5):
        return {
            "fatigued": True,
            "reason": "Nenhum acerto nos últimos 5. Vale respirar 3 min antes de continuar.",
            "evidence": {"streak_no_correct": len(last5), "n": n},
        }

    return {"fatigued": False, "reason": None, "evidence": {"n": n, "correct_last5": correct5}}
