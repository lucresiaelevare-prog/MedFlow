# MedFlow — PRD

## Problema
App para estudantes de medicina (copiloto acadêmico com IA). Restauração de codebase existente a partir de zip e preparação para deploy.

## Stack
- Backend: FastAPI (thin orchestrator em server.py + routers em routes/ e módulo mip/)
- Frontend: React (CRA/craco), Tailwind, shadcn/ui
- DB: MongoDB
- Auth: Google OAuth gerenciado pela Emergent (estudantes) + admin email/senha (bcrypt)
- IA: EMERGENT_LLM_KEY + integrações OpenAI/Groq/HuggingFace; evidências via PubMed/OpenAlex

## Status (2026-08-17)
- Código extraído do zip para /app e configurado.
- backend/.env e frontend/.env criados com chaves fornecidas pelo usuário.
- Dependências instaladas (base image já continha os pacotes principais).
- Serviços rodando (supervisor): backend 8001, frontend 3000.
- Admins seedados: admin/eder/carine @medflow.local.
- Verificação de prontidão de deploy: PASS (corrigido .gitignore que bloqueava .env).

## Deploy — próximos passos do usuário
- Clicar em "Deploy" na UI da Emergent.
- Adicionar os secrets/env do backend no painel de deploy (Segredos): ADMIN_*, EMERGENT_LLM_KEY, OPENAI_API_KEY, GROQ_API_KEY, HUGGINGFACE_API_KEY, PUBMED_*, AI_* limits, MIP_PHASE2_ESTIMATED_GENERATION_USD.

## Backlog
- Configurar integrações opcionais adicionais (Resend/email, Sentry, Web Push/VAPID) se desejado.
