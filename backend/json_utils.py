"""Parsing tolerante de JSON vindo de LLM — repara e valida, sem devolver lixo parcial.

Usado pelas gerações pesadas (Devolutiva, Revisão Completa) para tratar JSON
malformado do provider: parse normal → reparo → (o chamador faz 1 retry) → erro.
Nunca retorna estrutura parcialmente corrompida.
"""
from __future__ import annotations

import json
import re
from typing import Optional, Union


def _candidates(text: str):
    t = (text or "").strip()
    if not t:
        return
    yield t
    fenced = re.search(r"```(?:json)?\s*(\{.*\}|\[.*\])\s*```", t, re.DOTALL)
    if fenced:
        yield fenced.group(1)
    start = t.find("{")
    end = t.rfind("}")
    if start != -1 and end != -1 and end > start:
        block = t[start:end + 1]
        yield block
        yield re.sub(r",(\s*[}\]])", r"\1", block)  # remove vírgulas finais
        yield re.sub(  # `texto` -> "texto" (ex.: mapa mental do full-review)
            r"`([^`]*)`",
            lambda mm: json.dumps(mm.group(1), ensure_ascii=False),
            block,
            flags=re.DOTALL,
        )


def _repair_truncated(text: str) -> str:
    """Repara JSON truncado pelo provedor (limite de tokens).

    Fecha aspas abertas, remove a última entrada parcial (depois do último
    delimitador válido) e fecha as chaves/colchetes abertos, devolvendo um
    JSON sintaticamente válido — mesmo que parcial.
    """
    t = text.strip()
    if not t:
        return t
    # 1) Remove a última entrada parcial: corta após o último delimitador
    # que aparece FORA de strings (evita cortar dentro de um valor).
    # Depois, elimina vírgulas e chaves/colchetes residuais do fim
    # (ex.: a última entrada foi aberta com `{` mas nunca concluída).
    trail = {'}', ']', ',', '\n', ' ', '\t', '{', '['}
    cut = False
    i = len(t) - 1
    in_str = False
    while i >= 0:
        ch = t[i]
        if ch == '"' and (i == 0 or t[i - 1] != '\\'):
            in_str = not in_str
        elif not in_str:
            if ch in (',', '{', '[') or t[i:i + 2] in (', ', ',\n'):
                cut = True
                i -= 1
                continue
        if cut:
            break
        i -= 1
    if cut:
        # recua até achar um caractere que não seja separador
        while i >= 0 and t[i] in {' ', '\t', '\n', ',', '}', ']'}:
            i -= 1
        t = t[:i + 1]
    # 2) Fecha aspas abertas na última string incompleta
    if t.count('"') % 2 == 1:
        t = t + '"'
    # 3) Fecha estruturas abertas
    stack: list[str] = []
    i = 0
    in_str = False
    while i < len(t):
        ch = t[i]
        if ch == '"' and (i == 0 or t[i - 1] != '\\'):
            in_str = not in_str
        elif not in_str:
            if ch in '{[':
                stack.append('}' if ch == '{' else ']')
            elif ch in '}]' and stack and stack[-1] == ch:
                stack.pop()
        i += 1
    return t + ''.join(reversed(stack))


def repair_and_parse(text: str) -> Optional[Union[dict, list]]:
    """Retorna dict/list JSON válido ou None. Nunca levanta exceção.

    Ordem: parse direto → candidatos reparados (fence/bloco) → reparo de
    JSON truncado (último recurso; resultado parcial, mas sempre válido).
    """
    for candidate in _candidates(text):
        try:
            parsed = json.loads(candidate)
        except Exception:  # noqa: BLE001
            pass
        else:
            if isinstance(parsed, (dict, list)):
                return parsed
    try:
        parsed = json.loads(_repair_truncated(text))
    except Exception:  # noqa: BLE001
        return None
    if isinstance(parsed, (dict, list)):
        return parsed
    return None
