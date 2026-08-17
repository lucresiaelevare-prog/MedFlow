export const stateWord = (v) => {
  if (v >= 82) return 'Excelente';
  if (v >= 68) return 'Consistente';
  if (v >= 52) return 'Instável';
  if (v >= 36) return 'Em cuidado';
  return 'Delicado';
};

/**
 * Extract editorial letter parts from mission + IEA context.
 * Returns { primary, followup, rationale[] }.
 */
export const composeLetter = (mission, iea) => {
  if (!mission) return null;
  const primary = (mission.title || '').replace(/\.$/, '');
  const followup = [];
  if (mission.minutes && mission.minutes >= 40) followup.push('Depois faça uma pausa.');
  else if (mission.category === 'estudo' || mission.category === 'aula') followup.push('Depois deixe descansar.');
  if (mission.category === 'descanso') followup.push('O corpo cuida do resto.');

  const rationale = [];
  if (mission.why) rationale.push(mission.why);
  const map = {
    sono:         'Você dormiu pouco.',
    bem_estar:    'Sinais de sobrecarga.',
    estudos:      'Adesão de estudo em queda.',
    saude_fisica: 'Corpo pedindo atenção.',
    social:       'Você tem se isolado.',
  };
  if (iea?.weakest_pillar && map[iea.weakest_pillar]) rationale.push(map[iea.weakest_pillar]);
  return { primary, followup, rationale: [...new Set(rationale)].slice(0, 3) };
};

export const shortDate = (d = new Date()) => {
  const weekday = d.toLocaleDateString('pt-BR', { weekday: 'long' });
  const day = d.getDate();
  const month = d.toLocaleDateString('pt-BR', { month: 'long' });
  return {
    weekday: weekday.charAt(0).toUpperCase() + weekday.slice(1),
    day: String(day).padStart(2, '0'),
    month: month.charAt(0).toUpperCase() + month.slice(1),
  };
};

export const PILLAR_LABELS = {
  estudos:      'Estudos',
  sono:         'Sono',
  saude_fisica: 'Saúde Física',
  bem_estar:    'Bem-estar',
  social:       'Social',
};
