"""SSE keep-alive para gerações longas.

Envolve uma coroutine de geração (mantendo 100% da lógica/validação existente)
num stream Server-Sent Events que emite frames continuamente (heartbeat a cada
~1s). Isso mantém a conexão ativa e impede o timeout ~60s do ingress/proxy em
gerações pesadas (43–80s), sem fila, worker ou mudança de arquitetura.

O resultado final (mesmo payload dict do endpoint não-stream) é entregue no
evento `done`; erros viram evento `error` com status/detalhe.
"""
from __future__ import annotations

import asyncio
import json
from typing import Awaitable

from fastapi import HTTPException
from starlette.responses import StreamingResponse

from core import logger


def _frame(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _generator(coro: Awaitable, heartbeat: float):
    task = asyncio.ensure_future(coro)
    # Primeiro byte imediato — abre o stream no ingress sem esperar a geração.
    yield _frame("start", {"ok": True})
    while not task.done():
        yield ": keep-alive\n\n"  # comentário SSE mantém a conexão viva
        await asyncio.sleep(heartbeat)
    try:
        result = task.result()
    except HTTPException as exc:
        yield _frame("error", {"status": exc.status_code, "detail": exc.detail})
        return
    except Exception as exc:  # noqa: BLE001
        logger.exception("SSE geração falhou: %s", exc)
        yield _frame("error", {"status": 500, "detail": "Falha inesperada na geração."})
        return
    yield _frame("done", result if isinstance(result, dict) else {"result": result})


def sse_response(coro: Awaitable, heartbeat: float = 1.0) -> StreamingResponse:
    return StreamingResponse(
        _generator(coro, heartbeat),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # desliga buffering do nginx/ingress
            "Connection": "keep-alive",
        },
    )
