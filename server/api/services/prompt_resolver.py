"""
prompt_resolver.py
Resolve prompts do banco de dados com fallback para arquivos .txt.

Prioridade:
  1. Personalizado mais recente da ESCOLA
  2. Global mais recente do banco (sem escola e sem instituição)
  3. Arquivo .txt em /prompts/
  4. String vazia
"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def resolver_prompt(titulo_categoria: str, escola_id=None, fallback_arquivo: str = None) -> str:
    """
    Retorna o prompt resolvido para uma categoria.

    Prioridade:
      1. Personalizado mais recente da escola (se `escola_id` fornecido)
      2. Global mais recente do banco (escola e instituição nulas)
      3. Arquivo .txt em /prompts/ (fallback_arquivo)
      4. String vazia

    A personalização é POR ESCOLA: cada escola pode ter o seu texto; as que
    não personalizaram usam o global. `escola_id` deve ser a escola do
    contexto do prompt (a do aluno, da turma ou do áudio) — não a do usuário,
    que pode nem ter escola (admin, superadmin, suporte).

    "Mais recente" é determinado por `-criado_em` (os ids são UUID, sem
    relação com ordem de criação). Garante comportamento previsível mesmo se
    existir mais de um registro para a mesma categoria/escola.

    Usa `_base_manager` (sem tenant) de propósito: esta função roda DENTRO de
    requisições (análise de produção, relatório, planejamento, áudio). Com o
    `TenantManager`, quem tem escopo de escola não enxergaria o global (sem
    escola) e todo mundo cairia no .txt. O recorte aqui é feito à mão.

    Args:
        titulo_categoria: Título exato da PromptCategoria no banco.
        escola_id:        Escola do contexto (UUID ou str) ou None.
        fallback_arquivo: Nome do arquivo .txt usado antes do banco existir.
    """
    try:
        from api.models import PromptCategoria, PromptTemplate

        categoria = PromptCategoria.objects.filter(titulo=titulo_categoria, ativo=True).first()
        if categoria:
            # 1. Personalizado mais recente da escola
            if escola_id:
                tpl = (
                    PromptTemplate._base_manager.filter(categoria=categoria, escola_id=escola_id)
                    .order_by('-criado_em')
                    .first()
                )
                if tpl and tpl.personalizado.strip():
                    logger.debug(
                        "[prompt_resolver] Usando personalizado escola=%s categoria=%s (id=%s)",
                        escola_id, titulo_categoria, tpl.id,
                    )
                    return tpl.personalizado.strip()

            # 2. Global mais recente do banco
            tpl_global = (
                PromptTemplate._base_manager.filter(
                    categoria=categoria, escola__isnull=True, instituicao__isnull=True,
                )
                .order_by('-criado_em')
                .first()
            )
            if tpl_global and tpl_global.prompt_global.strip():
                logger.debug(
                    "[prompt_resolver] Usando global do banco categoria=%s (id=%s)",
                    titulo_categoria, tpl_global.id,
                )
                return tpl_global.prompt_global.strip()

    except Exception as e:
        logger.warning("[prompt_resolver] Erro ao consultar banco: %s", e)

    # 3. Fallback para arquivo txt
    if fallback_arquivo:
        try:
            conteudo = (_PROMPTS_DIR / fallback_arquivo).read_text(encoding="utf-8")
            logger.debug("[prompt_resolver] Usando arquivo txt fallback=%s", fallback_arquivo)
            return conteudo
        except FileNotFoundError:
            logger.warning("[prompt_resolver] Arquivo não encontrado: %s", fallback_arquivo)

    logger.warning("[prompt_resolver] Nenhum prompt encontrado para categoria=%s", titulo_categoria)
    return ""