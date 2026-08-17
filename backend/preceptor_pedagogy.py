"""Contratos pedagógicos do Preceptor para residência médica."""
from __future__ import annotations


PRECEPTOR_SYSTEM = (
    "Você é o Preceptor IA do MedFlow, professor de Medicina para residência brasileira. "
    "Ensine com profundidade e utilidade clínica. Integre ciência básica, fisiopatologia, "
    "clínica e estratégia de prova. Nunca escreva para leigos, nunca produza texto de "
    "Wikipédia e nunca desperdice espaço com definições óbvias. Adapte os módulos ao "
    "objetivo do aluno: dúvida curta pede resposta direta e profunda; consolidação pede "
    "recuperação ativa; revisão completa pede aula premium. Use português brasileiro."
)


def premium_review_prompt(topic: str, discipline: str, compact: bool) -> str:
    if compact:
        return (
            f"Tema: {topic}\nDisciplina: {discipline}\n\n"
            "O aluno já fez várias revisões longas hoje. Entregue consolidação inteligente: "
            "importância clínica, mecanismo central, 3 pegadinhas, um mnemônico e uma "
            "questão clínica com justificativa. Flashcards: exatamente 8 a 12, cada um "
            "explorando um ASPECTO DISTINTO (definição, mecanismo/fisiologia, valor "
            "normal, correlação clínica, pegadinha de prova) — fronts semanticamente "
            "diferentes, nunca repetindo a mesma ideia com palavras diferentes. Devolva SOMENTE JSON "
            "com topic, discipline, review_type, why_it_matters, detailed_explanation, "
            "high_yield_points, flashcards, practice_questions, common_mistakes, "
            "memory_technique e smart_summary."
        )
    return (
        f"Prepare uma AULA PREMIUM de residência sobre:\nTema: {topic}\n"
        f"Disciplina: {discipline}\n\n"
        "Devolva SOMENTE JSON com topic, discipline, review_type='premium_review', "
        "why_it_matters (até 6 linhas), detailed_explanation.paragraphs (raciocínio "
        "causal e clínica), high_yield_points (porquê, pegadinha e memória), "
        "common_mistakes, mind_map, flashcards (8 a 12 de recuperação ativa, cada um com "
        "um aspecto distinto: definição, mecanismo, valor normal, correlação clínica, "
        "pegadinha de prova — fronts semanticamente diferentes, sem repetir a mesma ideia), "
        "practice_questions (5 vinhetas com opções, answer, explanation e "
        "option_analysis), clinical_case (história, exame, hipótese, pergunta, "
        "discussão e conduta), memory_technique, exam_strategy e smart_summary "
        "(máximo 10 bullets). Não liste fatos soltos: construa mecanismos e use "
        "exemplos clínicos plausíveis. Use aspas duplas, sem markdown ou backticks."
    )


def memorization_prompt(topic: str, discipline: str) -> str:
    return (
        f"Tema: {topic}\nDisciplina: {discipline}\n\n"
        "Monte uma CONSOLIDAÇÃO de 5 a 8 minutos, não uma aula longa. Selecione o que "
        "muda acerto de questão. Devolva SOMENTE JSON com topic, discipline, "
        "review_type='memorization', why_it_matters, detailed_explanation (2 a 3 "
        "parágrafos), high_yield_points, memory_technique, flashcards (8 a 12, cada um "
        "com um aspecto distinto — definição, mecanismo, valor normal, correlação "
        "clínica, pegadinha — sem repetição), "
        "common_mistakes e practice_questions (lista com uma vinheta final, opções, answer, "
        "explanation e option_analysis). Use aspas duplas, sem markdown ou backticks."
    )


def focused_prompt(topic: str, discipline: str, focus: str) -> str:
    objectives = {
        "explanation": "mecanismo, integração fisiopatológica e aplicação clínica",
        "flashcards": "recuperação ativa, mnemônicos e pegadinhas",
        "questions": "questões clínicas, justificativas e alternativas",
        "case": "vinheta realista, hipótese, decisão e conduta",
    }
    objective = objectives.get(focus, objectives["explanation"])
    return (
        f"Tema: {topic}\nDisciplina: {discipline}\nFoco: {objective}\n\n"
        "Crie uma sessão focada, curta e profunda, não uma revisão completa. Devolva "
        "SOMENTE JSON com topic, discipline, review_type='focused', why_it_matters, "
        "detailed_explanation, high_yield_points, flashcards (cada um com um aspecto "
        "distinto, sem repetição), practice_questions, "
        "clinical_case, common_mistakes, memory_technique e smart_summary. Preencha "
        "somente módulos úteis ao foco. Use aspas duplas, sem markdown ou backticks."
    )