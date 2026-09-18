"""
prompt_resolver.py
Resolve prompts do banco de dados com fallback para arquivos .txt.

Prioridade:
  1. Personalizado mais recente da instituição
  2. Global mais recente do banco
  3. Arquivo .txt em /prompts/
  4. String vazia
"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def resolver_prompt(titulo_categoria: str, cliente_id: str = None, fallback_arquivo: str = None) -> str:
    """
    Retorna o prompt resolvido para uma categoria.

    Prioridade:
      1. Personalizado mais recente da instituição (se cliente_id fornecido)
      2. Global mais recente do banco (instituicao=None)
      3. Arquivo .txt em /prompts/ (fallback_arquivo)
      4. String vazia

    "Mais recente" é determinado por -id (maior id primeiro), garantindo
    comportamento previsível mesmo se existir mais de um registro para a
    mesma categoria/instituição (cenário de dados legados/duplicados).

    Args:
        titulo_categoria: Título exato da PromptCategoria no banco.
        cliente_id:       instituicao_id do usuário (str ou None). Nome mantido
                          por compatibilidade com quem já chama esta função.
        fallback_arquivo: Nome do arquivo .txt usado antes do banco existir.
    """
    try:
        from api.models import PromptCategoria, PromptTemplate

        categoria = PromptCategoria.objects.filter(titulo=titulo_categoria, ativo=True).first()
        if categoria:
            # 1. Personalizado mais recente da instituição
            if cliente_id:
                tpl = (
                    PromptTemplate.objects.filter(
                        categoria=categoria,
                        instituicao_id=cliente_id,
                    )
                    .order_by('-id')
                    .first()
                )
                if tpl and tpl.personalizado.strip():
                    logger.debug(
                        "[prompt_resolver] Usando personalizado instituicao=%s categoria=%s (id=%s)",
                        cliente_id, titulo_categoria, tpl.id,
                    )
                    return tpl.personalizado.strip()

            # 2. Global mais recente do banco
            tpl_global = (
                PromptTemplate.objects.filter(
                    categoria=categoria,
                    instituicao__isnull=True,
                )
                .order_by('-id')
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