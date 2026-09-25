"""Sinais do app `api`."""

import logging

from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver

from api.models import Relatorio
from api.storage import delete_from_storage

logger = logging.getLogger(__name__)

# Campos que alteram o PDF renderizado. Mudou qualquer um → o cache é descartado.
_CAMPOS_QUE_AFETAM_PDF = ('conteudo', 'template_id')


@receiver(pre_save, sender=Relatorio)
def invalidar_pdf_ao_editar_conteudo(sender, instance: Relatorio, update_fields=None, **kwargs):
    """Descarta o PDF cacheado quando o conteúdo ou o template do relatório mudam.

    Mecanismo ÚNICO de invalidação: vale para qualquer caminho que salve um
    Relatorio (views, serializers, admin, shell), sem depender de cada view
    lembrar de chamar algo. O PDF é regenerado sob demanda no próximo download.
    """
    if not instance.pk:
        return

    # Saves parciais que não tocam conteúdo/template (cache do próprio PDF,
    # "revisar", etc.) não precisam nem do SELECT abaixo.
    if update_fields is not None and not ({'conteudo', 'template', 'template_id'} & set(update_fields)):
        return

    # _base_manager ignora o TenantManager: esta é uma checagem de integridade,
    # não uma leitura de negócio. Com escopo 'nenhum' ou fora de request
    # (worker), o manager padrão devolveria vazio e o PDF velho sobreviveria.
    anterior = (
        Relatorio._base_manager
        .filter(pk=instance.pk)
        .values('conteudo', 'template_id', 'pdf_storage_key')
        .first()
    )
    if anterior is None:
        return

    if all(anterior[c] == getattr(instance, c) for c in _CAMPOS_QUE_AFETAM_PDF):
        return

    chave_antiga = anterior['pdf_storage_key']
    if chave_antiga:
        delete_from_storage(chave_antiga)  # S3 ou fallback local; nunca levanta

    instance.pdf_url = None
    instance.pdf_storage_key = None
    # Se o save vier com update_fields sem os campos do PDF, as duas linhas
    # acima não seriam gravadas e o banco apontaria para um objeto já apagado.
    Relatorio._base_manager.filter(pk=instance.pk).update(pdf_url=None, pdf_storage_key=None)

    logger.info(
        "PDF cacheado descartado após edição do relatório.",
        extra={"relatorio_id": str(instance.pk), "storage_key": chave_antiga},
    )


@receiver(post_delete, sender=Relatorio)
def apagar_pdf_ao_excluir_relatorio(sender, instance: Relatorio, **kwargs):
    """Remove do storage o PDF cacheado de um relatório excluído.

    Mesmo princípio do `pre_save` acima: qualquer caminho que apague um
    Relatorio (view, admin, shell, cascade do aluno) limpa o PDF — sem depender
    de cada view lembrar. Roda depois do DELETE; `delete_from_storage` é
    best-effort e nunca levanta, então não derruba a exclusão.
    """
    chave = instance.pdf_storage_key
    if chave:
        delete_from_storage(chave)
        logger.info(
            "PDF removido junto com o relatório.",
            extra={"relatorio_id": str(instance.pk), "storage_key": chave},
        )