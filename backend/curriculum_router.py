"""Roteamento pedagógico por matriz, período, módulo e sistema integrado."""
from __future__ import annotations

from typing import Optional


CURRICULA = {
    "faminas_bh": {
        1: [
            "Atenção Primária à Saúde I",
            "Bases Anatômicas do Corpo Humano I",
            "Bases da Biologia Celular e Molecular",
            "Bases do Desenvolvimento e dos Tecidos do Corpo Humano I",
            "Bases Funcionais do Corpo Humano I",
            "Habilidades Médicas I: Comunicação",
            "Integração Curricular I",
            "Saúde e Espiritualidade",
        ],
        2: [
            "Atenção Primária à Saúde II",
            "Bases Anatômicas do Corpo Humano II",
            "Bases do Desenvolvimento e dos Tecidos do Corpo Humano II",
            "Bases Funcionais do Corpo Humano II",
            "Habilidades Médicas II: atendimento pré-hospitalar",
            "Integração Curricular II",
            "Relação Parasita-Hospedeiro I",
        ],
        3: [
            "Atenção Primária à Saúde III",
            "Bases Anatômicas e Funcionais do Sistema Nervoso",
            "Bases Funcionais do Corpo Humano III",
            "Habilidades Médicas III: introdução à semiologia médica",
            "Integração Curricular III",
            "Fundamentos da Pesquisa Médica: Bioestatística",
            "Relação Parasita-Hospedeiro II",
        ],
    },
    "fcmmg": {
        1: [
            "Anatomia Humana I",
            "Bioquímica",
            "Citologia e Histologia Básica",
            "Neuroanatomia Médica",
            "Embriologia Humana",
            "Metodologia Científica",
            "Genética Aplicada à Medicina",
            "Integração Curricular I",
            "Treinamento de Habilidades I",
            "Prática Formativa na Comunidade I",
        ],
        2: [
            "Anatomia Humana II",
            "Fisiologia Humana I",
            "Histologia Aplicada à Medicina",
            "Epidemiologia e Bioestatística",
            "Ciências Sociais Aplicadas à Saúde",
            "Práticas em Saúde Coletiva I",
            "Integração Curricular II",
        ],
        3: [
            "Patologia Geral",
            "Fisiologia Humana II",
            "Parasitologia Aplicada à Medicina",
            "Imunologia Aplicada à Medicina",
            "Psicologia Aplicada à Prática Médica",
            "Práticas em Saúde Coletiva II",
            "Saúde da Criança e do Adolescente I",
            "Integração Curricular III",
            "Treinamento de Habilidades III",
        ],
    },
}

SPECIALTY_GUIDES = {
    "anatomia": "Ensine organização tridimensional, relações espaciais, vascularização, "
    "inervação, imagem e correlação cirúrgica; nunca anatomia isolada.",
    "fisiologia": "Construa causa → efeito → compensação → descompensação → doença → tratamento.",
    "histologia": "Relacione arquitetura microscópica, função, lesão e reconhecimento em prova.",
    "embriologia": "Organize cronologia, origem embrionária, defeito congênito e pegadinha.",
    "bioquimica": "Explique lógica metabólica: enzima → via → doença → intervenção terapêutica.",
    "genetica": "Conecte gene → mutação → proteína → fenótipo → doença e aconselhamento.",
    "imunologia": "Construa a resposta imune e a decisão clínica; não decore interleucinas isoladas.",
    "microbiologia": "Compare agentes, virulência, quadro, diagnóstico e tratamento diferencial.",
    "parasitologia": "Ensine ciclo → transmissão → quadro → diagnóstico → tratamento.",
    "patologia": "Parta de agressão → adaptação → lesão → necrose → manifestação clínica.",
    "farmacologia": "Integre mecanismo, indicação, contraindicação, efeito adverso e pegadinha.",
    "semiologia": "Ensine hipótese, manobra, achado, interpretação e consequência clínica.",
    "habilidades_medicas": "Priorize comunicação, ética, empatia, segurança e simulação realista.",
    "atencao_primaria": "Use cenários de UBS, prevenção, linha de cuidado e longitudinalidade.",
    "saude_coletiva": "Conecte SUS, políticas, indicadores, território e tomada de decisão.",
    "epidemiologia": "Ensine interpretação e decisão clínica; nunca fórmula sem significado.",
    "bioestatistica": "Ensine pergunta, desenho, medida, viés, interpretação e aplicabilidade.",
    "clinica_medica": "Trabalhe queixa → hipóteses → exames → diagnóstico → conduta.",
    "cirurgia": "Estruture gravidade, tempo, indicação, risco e decisão perioperatória.",
    "pediatria_go_preventiva": "Adapte faixa etária, prevenção, rastreio e conduta baseada em cenário.",
}

KEYWORDS = {
    "anatomia": ["anatom", "nervo", "artéria", "veia", "plexo", "músculo", "ligamento"],
    "fisiologia": ["fisiolog", "feedback", "homeost", "pressão", "débito", "ventila"],
    "histologia": ["histolog", "epitélio", "microsc", "tecido", "lâmina"],
    "embriologia": ["embri", "feto", "congên", "malforma", "neurulação"],
    "bioquimica": ["metab", "enzima", "glicose", "atp", "ciclo de krebs"],
    "genetica": ["gene", "mutação", "cromoss", "herança", "genética"],
    "imunologia": ["imune", "linfócito", "anticorpo", "citocina", "complemento"],
    "microbiologia": ["bactér", "vírus", "fungo", "antibiótico", "cultura"],
    "parasitologia": ["parasita", "helminto", "protozo", "hospedeiro"],
    "patologia": ["necrose", "inflama", "lesão", "neoplas", "apoptose"],
    "farmacologia": ["fármaco", "droga", "receptor", "efeito adverso", "dose"],
    "semiologia": ["sinal", "sintoma", "exame físico", "ausculta", "palpação"],
    "atencao_primaria": ["ubs", "atenção primária", "esf", "família", "território"],
    "epidemiologia": ["incidência", "prevalência", "risco relativo", "sensibilidade"],
    "bioestatistica": ["p valor", "intervalo", "odds ratio", "viés", "amostra"],
    "clinica_medica": ["diagnóstico", "conduta", "dispneia", "dor torácica", "síndrome"],
    "cirurgia": ["cirurgia", "abdome agudo", "trauma", "operatório"],
    "pediatria_go_preventiva": ["pediatria", "gestante", "pré-natal", "criança", "rastreio"],
}

SYSTEM_LINKS = {
    "respiratório": "anatomia torácica → histologia alveolar → fisiologia ventilatória → "
    "embriologia → patologia → farmacologia → clínica",
    "cardiovascular": "anatomia cardíaca → eletrofisiologia → hemodinâmica → patologia → "
    "farmacologia → clínica",
    "nervoso": "neuroanatomia → neurofisiologia → desenvolvimento → patologia → farmacologia → "
    "semiologia neurológica",
    "renal": "anatomia renal → histologia glomerular → fisiologia tubular → patologia → "
    "farmacologia → clínica",
}


def _detect_specialty(topic: str) -> str:
    text = topic.lower()
    if any(term in text for term in ("intervalo de confiança", "p valor", "odds ratio")):
        return "bioestatistica"
    scores = {
        specialty: sum(word in text for word in words)
        for specialty, words in KEYWORDS.items()
    }
    return max(scores, key=scores.get) if any(scores.values()) else "clinica_medica"


def _detect_system(topic: str) -> Optional[str]:
    text = topic.lower()
    for system in SYSTEM_LINKS:
        if system in text:
            return system
    return None


def _module_for_specialty(modules: list[str], specialty: str) -> str:
    lookup = {
        "anatomia": ("anatôm", "anatomia", "neuroanatomia"),
        "fisiologia": ("funcionais", "fisiologia"),
        "histologia": ("tecidos", "histologia", "citologia"),
        "embriologia": ("desenvolvimento", "embriologia"),
        "parasitologia": ("parasita", "parasitologia"),
        "semiologia": ("habilidades médicas", "treinamento de habilidades"),
        "atencao_primaria": ("atenção primária", "prática formativa"),
        "epidemiologia": ("pesquisa", "epidemiologia"),
        "bioestatistica": ("bioestatística", "pesquisa"),
    }
    terms = lookup.get(specialty, ())
    for item in modules:
        if any(term in item.lower() for term in terms):
            return item
    return "Integração Curricular"


def route_curriculum(
    topic: str,
    curriculum: str = "faminas_bh",
    period: Optional[int] = None,
    module: Optional[str] = None,
) -> dict:
    curriculum = curriculum if curriculum in CURRICULA else "faminas_bh"
    specialty = _detect_specialty(topic)
    system = _detect_system(topic)
    modules = CURRICULA[curriculum].get(period or 0, [])
    selected_module = module or _module_for_specialty(modules, specialty)
    integration = SYSTEM_LINKS.get(system, "Conecte ciência básica, clínica e questões relevantes.")
    instruction = (
        f"Contexto curricular: {curriculum.replace('_', ' ').upper()}, período {period or 'não informado'}, "
        f"módulo {selected_module}. Especialização principal: {specialty}. "
        f"Diretriz especializada: {SPECIALTY_GUIDES[specialty]} "
        f"Integração curricular explícita: {integration}"
    )
    return {
        "curriculum": curriculum,
        "period": period,
        "module": selected_module,
        "specialty": specialty,
        "system": system,
        "available_modules": modules,
        "instruction": instruction,
    }