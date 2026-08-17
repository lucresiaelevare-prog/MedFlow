import {
  Bed, CalendarDays, Clock, BookMarked, HeartPulse,
} from 'lucide-react';

/**
 * Constantes de conteúdo da landing.
 * Textos aprovados. NÃO alterar sem revisão.
 */

export const CATEGORY = 'Copiloto de Estudos Inteligente';
export const CREED    = 'Aprenda a estudar com esta nova ferramenta!';

// Passos do raciocínio (Descoberta / PhoneMockup)
export const REASONING = [
  { k: 'time',   Icon: Clock,        label: '07:15',                          tone: 'muted' },
  { k: 'sleep',  Icon: Bed,          label: 'Sono: 5h48',                     tone: 'muted' },
  { k: 'energy', Icon: HeartPulse,   label: 'Energia: baixa',                 tone: 'care'  },
  { k: 'exam',   Icon: CalendarDays, label: 'Prova em 6 dias',                tone: 'brand' },
  { k: 'free',   Icon: Clock,        label: 'Tempo livre: 45 min',            tone: 'muted' },
  { k: 'hist',   Icon: BookMarked,   label: 'Você revisou Fisiologia ontem',  tone: 'muted' },
];

// Fluxo do método
export const FLOW = [
  { k: 'ctx', label: 'Contexto do aluno',    hint: 'Sono, energia, humor, rotina.' },
  { k: 'sig', label: 'Análise dos sinais',   hint: 'Cruza estado atual com histórico.' },
  { k: 'pri', label: 'Priorização',          hint: 'Identifica o que rende mais agora.' },
  { k: 'rec', label: 'Recomendação',         hint: 'Uma ação com duração e razão.' },
  { k: 'nxt', label: 'Próxima ação',         hint: 'Você executa. Sem dúvidas.' },
];

// Sinais analisados
export const SIGNALS = [
  { k: 'ene', label: 'Energia',           hint: 'Estado cognitivo atual',        unit: 'nível' },
  { k: 'son', label: 'Sono',              hint: 'Duração e qualidade',            unit: 'horas' },
  { k: 'dis', label: 'Disciplinas',       hint: 'Prioridades ativas',             unit: 'ativas' },
  { k: 'tem', label: 'Tempo disponível',  hint: 'Janela real do dia',             unit: 'min' },
  { k: 'pro', label: 'Provas',            hint: 'Proximidade e peso',             unit: 'dias' },
  { k: 'his', label: 'Histórico recente', hint: 'O que foi revisado',             unit: 'sessões' },
];

// Parade of Screens — cinco superfícies reais do produto
export const SCREENS = [
  {
    k: 'inicio',
    kicker: 'Início',
    title: 'O passo certo,\nassim que você abre.',
    body: 'Um ritmo diário calibrado por sono, energia e provas. Ao invés de te dar tarefas, o MedFlow te mostra o próximo passo — com contexto e sem excesso.',
    bullets: ['Ritmo de aprovação', 'Missão do dia', 'Sem sobrecarga cognitiva'],
    img: '/brand/screen-dashboard.jpeg',
    alt: 'Tela inicial do MedFlow com ritmo de aprovação',
  },
  {
    k: 'tutor',
    kicker: 'Preceptor IA',
    title: 'Um mentor sempre\ndisponível — nunca genérico.',
    body: 'Traga uma dúvida, um PDF, uma questão. O Preceptor identifica sua intenção e conduz a melhor estratégia: resumo, flashcard, revisão ou simulado.',
    bullets: ['Conversa contextual', 'Memória do que já viu', 'Revisão completa sob demanda'],
    img: '/brand/screen-tutor.jpeg',
    alt: 'Tela do Preceptor IA com recomendação e chat',
  },
  {
    k: 'biblioteca',
    kicker: 'Biblioteca',
    title: 'Curadoria calma.\nNada obrigatório.',
    body: 'Leituras, áudios e vídeos curtos que complementam seus pilares. Você escolhe o que faz sentido para o dia — em vez de correr atrás de todos.',
    bullets: ['Higiene do sono', 'Active recall', 'Rotina de residência'],
    img: '/brand/screen-library.jpeg',
    alt: 'Biblioteca com leituras e escutas curadas',
  },
  {
    k: 'habitos',
    kicker: 'Hábitos',
    title: 'Os cinco pilares\nque sustentam a rotina.',
    body: 'Estudos, sono, saúde física, bem-estar e social. O MedFlow observa o que sustenta seu desempenho — e o que está silenciosamente drenando.',
    bullets: ['Análise dos pilares', 'Aliado × limitador', 'Recuperação semanal'],
    img: '/brand/screen-habitos.jpeg',
    alt: 'Painel de hábitos com performance dos cinco pilares',
  },
  {
    k: 'perfil',
    kicker: 'Perfil',
    title: 'Sua trajetória,\ntraduzida em consistência.',
    body: 'Meta diária, sequência, evolução em 30 dias e conquistas discretas. Um espaço para lembrar o quanto você já andou — sem ranking, sem competição.',
    bullets: ['Meta diária adaptativa', 'Evolução em 30 dias', 'Conquistas por consistência'],
    img: '/brand/screen-profile.jpeg',
    alt: 'Tela de perfil com meta diária e conquistas',
  },
];

// Diferenciais (ferramentas tradicionais × MedFlow)
export const DIFF = [
  { legacy: 'Organizam tarefas',               medflow: 'Guiam o estudo' },
  { legacy: 'Listam conteúdos',                medflow: 'Priorizam ações' },
  { legacy: 'Dependem de planejamento manual', medflow: 'Adaptam-se ao contexto' },
  { legacy: 'Mostram cronogramas',             medflow: 'Consideram a realidade do dia' },
];

// Preceptor IA — capacidades listadas na seção principal
export const PRECEPTOR_CAPS = [
  { k: 'exp',  label: 'Explicações profundas',    hint: 'Da fisiologia ao raciocínio clínico.' },
  { k: 'sum',  label: 'Resumos inteligentes',      hint: 'Direto ao ponto, memorável.' },
  { k: 'map',  label: 'Mapas mentais automáticos', hint: 'Estrutura hierárquica na hora.' },
  { k: 'fl',   label: 'Flashcards prontos',        hint: 'Repetição espaçada sob medida.' },
  { k: 'qs',   label: 'Questões inéditas',         hint: 'Estilo prova, com gabarito comentado.' },
  { k: 'case', label: 'Casos clínicos',            hint: 'Vinheta + decisão + feedback.' },
];

// Experiência do Preceptor — sequência tipo Apple
export const PRECEPTOR_FLOW = [
  { k: 'ask',   step: '01', title: 'Você pergunta',      hint: 'Digite, cole PDF, fotografe, fale. O que for mais rápido.' },
  { k: 'read',  step: '02', title: 'Preceptor interpreta', hint: 'Identifica tema, disciplina e o que faz mais sentido gerar.' },
  { k: 'exp',   step: '03', title: 'Constrói a explicação', hint: 'Do fundamento ao clínico, calibrado ao seu período.' },
  { k: 'sum',   step: '04', title: 'Gera o resumo',        hint: 'Uma linha memorável e bullets essenciais.' },
  { k: 'map',   step: '05', title: 'Desenha o mapa mental', hint: 'Estrutura hierárquica para fixar o modelo.' },
  { k: 'fl',    step: '06', title: 'Produz os flashcards', hint: 'Perguntas curtas para active recall.' },
  { k: 'qs',    step: '07', title: 'Cria questões inéditas', hint: 'Estilo banca, com gabarito comentado.' },
  { k: 'case',  step: '08', title: 'Entrega o caso clínico', hint: 'Você aplica na vinheta antes da prova.' },
];

// Loading states — enquanto o Preceptor gera a Revisão Completa
export const PRECEPTOR_LOADING_STAGES = [
  'Analisando o tema…',
  'Organizando conceitos…',
  'Construindo mapa mental…',
  'Criando flashcards…',
  'Elaborando questões inéditas…',
  'Finalizando a revisão…',
];
