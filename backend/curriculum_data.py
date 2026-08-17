"""Grades curriculares oficiais — FAMINAS-BH e FCMMG.

Fonte: PDF `grades_curriculares_medicina.pdf` (arquivo enviado pelo usuário).
Uso: template para o endpoint `POST /api/academic/import-curriculum` popular
as disciplinas do aluno em bulk sem cadastro manual.

Estrutura:
  CURRICULUM[<university>][<semester>] = [ {name, hours, kind, is_critical} ]

`is_critical` é derivado da regra CRITICAL_TERMS abaixo (matérias com histórico
alto de DP). Pode ser ajustado manualmente depois pelo aluno.
"""
from __future__ import annotations

CRITICAL_TERMS = (
    "anatomia", "anatômicas", "anatômicos",
    "bioquímica",
    "fisiologia", "funcionais",
    "neuroanatomia", "sistema nervoso",
    "histologia", "tecidos",
    "embriologia", "desenvolvimento",
    "patologia",
    "farmacologia",
    "parasita", "parasitologia",
    "imunologia",
    "genética",
)


def is_critical(name: str) -> bool:
    low = (name or "").lower()
    return any(term in low for term in CRITICAL_TERMS)


def _mk(name: str, hours: str = "-", kind: str = "teorica") -> dict:
    return {
        "name": name,
        "hours": hours,
        "kind": kind,  # teorica | pratica
        "is_critical": is_critical(name),
    }


CURRICULUM: dict[str, dict[int, list[dict]]] = {
    "faminas-bh": {
        1: [
            _mk("Atenção Primária à Saúde I", "80"),
            _mk("Bases Anatômicas do Corpo Humano I", "120"),
            _mk("Bases da Biologia Celular e Molecular", "80"),
            _mk("Bases do Desenvolvimento e dos Tecidos do Corpo Humano I", "80"),
            _mk("Bases Funcionais do Corpo Humano I", "120"),
            _mk("Habilidades Médicas I: Comunicação", "40", "pratica"),
            _mk("Integração Curricular I", "20"),
            _mk("Saúde e Espiritualidade", "40"),
            _mk("Ser na Formação Médica: identidade e alteridade", "40"),
        ],
        2: [
            _mk("Atenção Primária à Saúde II", "80"),
            _mk("Bases Anatômicas do Corpo Humano II", "120"),
            _mk("Bases do Desenvolvimento e dos Tecidos do Corpo Humano II", "80"),
            _mk("Bases Funcionais do Corpo Humano II", "120"),
            _mk("Habilidades Médicas II: atendimento pré-hospitalar", "40", "pratica"),
            _mk("Integração Curricular II", "20"),
            _mk("Relação Parasita-Hospedeiro I", "120"),
            _mk("Ser na Formação Médica: personalidade, aprendizagem e sociedade", "40"),
        ],
        3: [
            _mk("Atenção Primária à Saúde III", "80"),
            _mk("Bases Anatômicas e Funcionais do Sistema Nervoso", "120"),
            _mk("Bases Funcionais do Corpo Humano III", "120"),
            _mk("Habilidades Médicas III: introdução à semiologia médica", "160", "pratica"),
            _mk("Integração Curricular III", "20"),
            _mk("Fundamentos da Pesquisa Médica: Bioestatística", "40"),
            _mk("Relação Parasita-Hospedeiro II", "80"),
            _mk("Ser na Formação Médica: saúde e integralidade", "40"),
        ],
    },
    "fcmmg": {
        1: [
            _mk("Anatomia Humana I"),
            _mk("Bioquímica"),
            _mk("Citologia e Histologia Básica"),
            _mk("Neuroanatomia Médica"),
            _mk("Embriologia Humana"),
            _mk("Metodologia Científica"),
            _mk("Genética Aplicada à Medicina"),
            _mk("Integração Curricular I"),
            _mk("Treinamento de Habilidades I", kind="pratica"),
            _mk("Prática Formativa na Comunidade I", kind="pratica"),
            _mk("Língua Inglesa Instrumental em Medicina I"),
            _mk("Gestão Pessoal"),
        ],
        2: [
            _mk("Anatomia Humana II"),
            _mk("Fisiologia Humana I"),
            _mk("Histologia Aplicada à Medicina"),
            _mk("Epidemiologia e Bioestatística"),
            _mk("Ciências Sociais Aplicadas à Saúde"),
            _mk("Práticas em Saúde Coletiva I", kind="pratica"),
            _mk("Língua Inglesa Instrumental em Medicina II"),
            _mk("Integração Curricular II"),
            _mk("Treinamento de Habilidades II", kind="pratica"),
            _mk("Prática Formativa na Comunidade II", kind="pratica"),
        ],
        3: [
            _mk("Patologia Geral"),
            _mk("Fisiologia Humana II"),
            _mk("Parasitologia Aplicada à Medicina"),
            _mk("Imunologia Aplicada à Medicina"),
            _mk("Psicologia Aplicada à Prática Médica"),
            _mk("Práticas em Saúde Coletiva II", kind="pratica"),
            _mk("Saúde da Criança e do Adolescente I"),
            _mk("Integração Curricular III"),
            _mk("Treinamento de Habilidades III", kind="pratica"),
            _mk("Prática Formativa na Comunidade III", kind="pratica"),
            _mk("Língua Portuguesa Instrumental em Medicina I"),
        ],
    },
}


UNIVERSITY_LABELS = {
    "faminas-bh": "FAMINAS-BH",
    "fcmmg": "FCMMG",
}


def list_universities() -> list[dict]:
    return [
        {"slug": slug, "label": label,
         "semesters": sorted(CURRICULUM[slug].keys())}
        for slug, label in UNIVERSITY_LABELS.items()
    ]


def get_semester(university: str, semester: int) -> list[dict]:
    uni = (university or "").lower().strip()
    return list(CURRICULUM.get(uni, {}).get(int(semester), []))
