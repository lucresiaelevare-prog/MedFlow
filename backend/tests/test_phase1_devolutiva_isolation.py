"""FASE 1 — P0 Segurança: isolamento cross-user da Devolutiva (exam_feedback).

Teste determinístico (sem LLM, sem banco): prova que o `user_id` participa da
IDENTIDADE do cache. Dois alunos com subject/tópicos/período/nota idênticos
NÃO podem colidir no mesmo fingerprint.
"""
from learning_memory import compute_fingerprint_generic
from routes.tutor import exam_feedback_key_fields, normalize_topics_key


def test_cross_user_fingerprints_differ():
    common = dict(subject="Cardiologia", weak_topics="arritmias, ICC", period_bucket="clinico")
    kf_a = exam_feedback_key_fields(user_id="user_AAAAAAAA", **common)
    kf_b = exam_feedback_key_fields(user_id="user_BBBBBBBB", **common)
    variant = "grade-low"
    fp_a = compute_fingerprint_generic("exam_feedback", kf_a, variant)
    fp_b = compute_fingerprint_generic("exam_feedback", kf_b, variant)
    assert fp_a != fp_b, "CROSS-USER LEAK: fingerprints iguais para usuários diferentes"


def test_same_user_same_need_reuses():
    common = dict(subject="Cardiologia", weak_topics="arritmias, ICC", period_bucket="clinico")
    kf1 = exam_feedback_key_fields(user_id="user_AAAAAAAA", **common)
    kf2 = exam_feedback_key_fields(user_id="user_AAAAAAAA", **common)
    fp1 = compute_fingerprint_generic("exam_feedback", kf1, "grade-low")
    fp2 = compute_fingerprint_generic("exam_feedback", kf2, "grade-low")
    assert fp1 == fp2, "reuso intra-user quebrado (mesmo aluno, mesma necessidade)"


def test_user_id_present_in_key_fields():
    kf = exam_feedback_key_fields(
        user_id="user_XYZ", subject="Anatomia", weak_topics="crânio", period_bucket="basico"
    )
    assert kf.get("user_id") == "user_XYZ"


def test_topics_key_is_order_insensitive_but_content_sensitive():
    assert normalize_topics_key("arritmias, ICC") == normalize_topics_key("ICC, arritmias")
    assert normalize_topics_key("arritmias") != normalize_topics_key("ICC")
