/**
 * Capitaliza cada palavra de uma string, normalizando espaços/caixa antes.
 * Usado para exibir campos como `tipo_especialista` (ex: "psicopedagogo"
 * vindo do banco) de forma legível ("Psicopedagogo"), sem alterar o dado
 * salvo — só a apresentação.
 *
 * @param {string|null|undefined} texto
 * @returns {string}
 */
export function capitalizarPalavras(texto) {
  if (!texto) return '';
  return texto
    .trim()
    .toLowerCase()
    .split(' ')
    .filter(Boolean)
    .map((palavra) => palavra.charAt(0).toUpperCase() + palavra.slice(1))
    .join(' ');
}