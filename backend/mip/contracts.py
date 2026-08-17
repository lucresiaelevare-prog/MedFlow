"""Contratos Pydantic da Fase 1, sem dependência de rotas legadas."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


SafetyAction = Literal[
    "allow",
    "transform_to_educational",
    "require_clarification",
    "block",
]


class SafetyDecision(BaseModel):
    stage: Literal["pre_generation", "post_generation"]
    action: SafetyAction
    reason_codes: list[str] = Field(default_factory=list)
    critical_failure: bool = False


class TraceRequest(BaseModel):
    input_hash: str
    input_length: int = Field(ge=0)
    source: str = "phase1_assess"


class MIPTrace(BaseModel):
    trace_id: str
    phase: Literal["phase1"] = "phase1"
    request: TraceRequest
    safety_pre: SafetyDecision
    safety_post: Optional[SafetyDecision] = None
    shadow_mode: bool = True
    created_at: str


class Phase1AssessInput(BaseModel):
    text: str = Field(min_length=1, max_length=8000)
    generated_text: Optional[str] = Field(default=None, max_length=30000)


class Phase1AssessResponse(BaseModel):
    trace: MIPTrace
    persisted: bool


Phase2EventType = Literal[
    "content_requested",
    "content_viewed",
    "answer_recorded",
    "recommendation_seen",
    "recommendation_outcome",
]

LearningOutcome = Literal["correct", "incorrect", "completed", "skipped", "unknown"]
CurriculumSource = Literal["legacy_faminas_bh", "legacy_fcmmg", "unspecified"]
ContentMode = Literal["review", "flashcard", "question", "summary", "explanation"]


class Phase2ObservationInput(BaseModel):
    """Entrada minimizada: hashes e códigos, nunca conteúdo clínico ou texto do aluno."""

    trace_id: str = Field(pattern=r"^mip_[a-f0-9]{32}$")
    idempotency_key: str = Field(pattern=r"^[A-Za-z0-9_-]{8,80}$")
    event_type: Phase2EventType
    topic_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    curriculum_source: CurriculumSource = "unspecified"
    curriculum_version: str = Field(default="legacy-unvalidated", max_length=64)
    period: Optional[int] = Field(default=None, ge=1, le=12)
    module_id: Optional[str] = Field(default=None, max_length=120)
    content_mode: ContentMode = "review"
    learning_outcome: LearningOutcome = "unknown"
    legacy_recommendation_code: Optional[str] = Field(
        default=None,
        pattern=r"^[a-z0-9_-]{1,64}$",
    )


class CacheObservation(BaseModel):
    cache_key: str
    status: Literal["candidate_created", "candidate_hit", "not_persisted"]
    observation_count: int = Field(ge=0)
    actual_reuse: bool = False
    estimated_generation_avoidable: bool = False


class ShadowRecommendation(BaseModel):
    code: Literal[
        "collect_more_data",
        "keep_current_path",
        "reinforce_before_advancing",
    ]
    confidence: Literal["insufficient", "low", "observational"]
    evidence_count: int = Field(ge=0)
    applies_to_legacy_flow: bool = False


class Phase2Comparison(BaseModel):
    status: Literal["not_compared", "match", "divergent"]
    applies_to_legacy_flow: bool = False


class Phase2ObservationResponse(BaseModel):
    trace_id: str
    event_id: str
    persisted: bool
    idempotent: bool
    cache: CacheObservation
    shadow_recommendation: ShadowRecommendation
    comparison: Phase2Comparison


class Phase2MetricsResponse(BaseModel):
    shadow_mode: bool = True
    events_persisted: int = Field(ge=0)
    failures: int = Field(ge=0)
    cache_lookups: int = Field(ge=0)
    cache_hits: int = Field(ge=0)
    cache_hit_rate: float = Field(ge=0)
    shadow_reuse_candidates: int = Field(ge=0)
    actual_reuses: int = Field(ge=0)
    actual_generations_avoided: int = Field(ge=0)
    estimated_generations_avoidable: int = Field(ge=0)
    estimated_cost_avoidable_usd: float = Field(ge=0)
    latency_ms: dict[str, Optional[float]]
    comparisons: dict[str, int]
    idempotency: dict[str, float | int]
    cost_estimates: dict[str, float | int]
    isolation: dict
    operations: dict[str, float | int | None]
    timeline: list[dict[str, int | str]]
    recent_events: list[dict[str, str | bool]]
    anomalies: list[dict[str, str | int]]