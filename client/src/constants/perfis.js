// Fonte única de verdade para "é um perfil de professor, de qualquer tipo"
// no frontend. Espelha Usuario.PERFIS_PROFESSOR no backend (api/models/base.py).
// Ao criar um novo tipo de professor, atualizar aqui e lá.
export const PERFIS_PROFESSOR = [
  'professor',
  'professor_infantil',
  'professor_fundamental',
  'professor_especialista',
];

export const PERFIL_LABELS_DOCENTE = {
  professor_especialista: 'Prof. especialista',
  professor_infantil: 'Prof. educação infantil',
  professor_fundamental: 'Prof. ensino fundamental',
  professor: 'Regente',
};

export const perfilLabelDocente = (perfil) => PERFIL_LABELS_DOCENTE[perfil] || 'Regente';