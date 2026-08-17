"""Pydantic input models shared across route modules."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class CheckinInput(BaseModel):
    sleep_hours: float
    energy: int
    mood: int
    stress: int
    upcoming_exam: bool = False
    exam_name: Optional[str] = None
    exam_date: Optional[str] = None
    on_call_today: bool = False
    commitments: Optional[str] = None
    free_text: Optional[str] = None


class FeedbackInput(BaseModel):
    recommendation_id: str
    followed: bool
    helped: Optional[bool] = None
    reason: Optional[str] = None


class MoodLogInput(BaseModel):
    value: int
    note: Optional[str] = None


class ExamModeInput(BaseModel):
    exam_name: str
    exam_date: str


class OnCallInput(BaseModel):
    active: bool


class MindfulnessLogInput(BaseModel):
    session_slug: str
    duration_seconds: int


class SubjectInput(BaseModel):
    name: str
    color: Optional[str] = "#6B8E76"
    is_dependency: bool = False


class ExamInput(BaseModel):
    subject_id: str
    name: str
    exam_date: str  # ISO YYYY-MM-DD
    weight: Optional[float] = 1.0


class ExamGradeInput(BaseModel):
    grade: float  # 0..10
    weak_topics: Optional[str] = None


VALID_MODES = {"rotina", "prova", "plantao", "dependencia", "recuperacao"}


class ModeInput(BaseModel):
    mode: str  # one of VALID_MODES


class ProfileInput(BaseModel):
    study_tool: Optional[str] = None  # anki | quizlet | remnote | caderno | outro
    display_name: Optional[str] = None
    # Persistência estendida — dados pessoais/acadêmicos/preferências
    course: Optional[str] = None  # ex: "Medicina"
    university: Optional[str] = None
    semester: Optional[int] = None  # 1..12
    living_alone: Optional[bool] = None  # mora sozinho / república
    has_dependencies: Optional[bool] = None
    is_neurodivergent: Optional[bool] = None
    neurodivergence_type: Optional[str] = None  # tdah | tea | outro
    chronotype: Optional[str] = None  # matutino | vespertino | noturno
    wake_time: Optional[str] = None  # HH:MM
    sleep_time: Optional[str] = None  # HH:MM
    target_sleep_hours: Optional[float] = None  # 6..10
    energy_peak: Optional[str] = None  # manha | tarde | noite
    focus_technique: Optional[str] = None  # pomodoro | ultradian | flow | livre
    hobbies: Optional[list[str]] = None
    interests: Optional[list[str]] = None
    family_pref: Optional[str] = None  # frequencia: diaria | semanal | quinzenal | mensal
    social_pref: Optional[str] = None  # baixa | media | alta
    physical_activity: Optional[str] = None  # nenhuma | leve | moderada | intensa
    physical_days_per_week: Optional[int] = None  # 0..7
    notify_channel: Optional[str] = None  # push | whatsapp | email
    dark_mode: Optional[bool] = None
    reduce_motion: Optional[bool] = None
    # Lembretes de autocuidado (Onda 5)
    remind_water: Optional[bool] = None
    remind_stretch: Optional[bool] = None
    # Acessibilidade — Otimização para Neurodivergência (Nível 2)
    font_size: Optional[str] = None       # sm | md | lg | xl
    high_contrast: Optional[bool] = None
    simplified_ui: Optional[bool] = None  # esconde elementos decorativos e cards secundários
    dyslexia_font: Optional[bool] = None  # aplica família de fonte mais legível
    # Comunidade
    anonymous_community: Optional[bool] = None


class MissionCompleteInput(BaseModel):
    completed: bool = True


class SupportContactRequestInput(BaseModel):
    contact_slug: str
    method: str  # "call" | "chat" | "link"


class AlertAckInput(BaseModel):
    alert_id: str


# ---------- Agenda / Time-Block ----------
class AgendaBlockInput(BaseModel):
    title: str
    category: str  # academic | study | physical | leisure | social | family | love | sleep | care
    start_time: str  # HH:MM
    end_time: str  # HH:MM
    day_of_week: Optional[int] = None  # 0=Mon..6=Sun (recurring)
    date: Optional[str] = None  # ISO YYYY-MM-DD (one-off)
    note: Optional[str] = None
    color: Optional[str] = None


class AgendaBlockUpdate(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    day_of_week: Optional[int] = None
    date: Optional[str] = None
    note: Optional[str] = None
    color: Optional[str] = None
    done: Optional[bool] = None
