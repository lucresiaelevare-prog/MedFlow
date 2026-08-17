import {
  BookOpen, Activity, Moon, Sparkles, Users, Utensils, GraduationCap, ClipboardList,
} from 'lucide-react';

export const CATEGORY_META = {
  aula:        { label: 'Aula',         Icon: GraduationCap },
  estudo:      { label: 'Estudo',       Icon: BookOpen },
  movimento:   { label: 'Movimento',    Icon: Activity },
  descanso:    { label: 'Descanso',     Icon: Moon },
  alimentacao: { label: 'Alimentação',  Icon: Utensils },
  bemestar:    { label: 'Bem-estar',    Icon: Sparkles },
  social:      { label: 'Social',       Icon: Users },
  admin:       { label: 'Organização',  Icon: ClipboardList },
};

export const PILLAR_META = {
  estudos:      { label: 'Estudos',      short: 'Estudos',  Icon: BookOpen },
  sono:         { label: 'Sono',         short: 'Sono',     Icon: Moon },
  saude_fisica: { label: 'Saúde Física', short: 'Físico',   Icon: Activity },
  bem_estar:    { label: 'Bem-estar',    short: 'Bem-estar',Icon: Sparkles },
  social:       { label: 'Social',       short: 'Social',   Icon: Users },
};

export const MODE_LABEL = {
  rotina:      'Modo Rotina',
  prova:       'Modo Prova',
  plantao:     'Modo Plantão',
  dependencia: 'Modo Dependência',
  recuperacao: 'Modo Recuperação',
};
