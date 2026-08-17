# Testes MedFlow — Guia de execução

## Suite ativa (produto atual)

```bash
cd /app/backend
REACT_APP_BACKEND_URL=<url> python -m pytest tests/
```

**Resultado esperado**: 195/195 verde.

Cobre: `core`, `api`, `decision_engine`, `efficacy`, `auth`, `study_plan`,
`tutor`, `pomodoro`, `insights`, `experience`, `learning_memory`, `mental_health`,
`support`, `admin`, `push`, `iea`, `checkin`.

## Suite legada (preservada para histórico)

```bash
python -m pytest tests/ -m legacy
```

49 testes cobrindo módulos podados no iter14 (missions, community, badges,
planner/agenda_blocks, health, habits/log, leisure/suggestions, sleep/plan,
study/strategies) + 1 teste de contrato drifted (`observation` → `noticed`)
+ 12 testes com race conditions sob `xdist -n 2`.

Kept in-place; não apagar. Se um módulo for restaurado, remover as entradas
correspondentes de `tests/legacy_tests.txt`.

## Como funciona

- `tests/legacy_tests.txt` — manifesto de node ids legados, com comentários
  explicando o motivo por seção
- `tests/conftest.py` — lê o manifesto e aplica `@pytest.mark.legacy`
  dinamicamente no `pytest_collection_modifyitems`
- `pytest.ini` — `addopts = -n 2 --dist loadscope -m "not legacy"` exclui
  legacy por padrão

## Padrões (não repetir)

❌ Apagar testes de módulos podados → perda de histórico  
❌ Forçar 244/244 verde incluindo módulos removidos → métrica falsa  
✅ 195/195 ativo + 49/49 legado catalogado = observabilidade honesta
