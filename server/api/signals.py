"""Sinais do app `api`."""

import logging

from django.db.models.signals import pre_save
from django.dispatch import receiver

from api.models import Relatorio
from api.storage import delete_from_s3

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=Relatorio)
def invalidar_pdf_ao_editar_conteudo(sender, instance: Relatorio, **kwargs):
    """Remove PDF cacheado no S3 quando o conteúdo do relatório muda.

    O PDF é regenerado on-demand no próximo download. Evita servir PDF obsoleto
    após edição pelo professor/coordenador.
    """
    if not instance.pk:
        return

    try:
        anterior = Relatorio.objects.only("conteudo", "pdf_storage_key").get(pk=instance.pk)
    except Relatorio.DoesNotExist:
        return

    if anterior.conteudo == instance.conteudo:
        return

    if anterior.pdf_storage_key:
        delete_from_s3(anterior.pdf_storage_key)
        logger.info(
            "PDF cacheado descartado após edição do conteúdo.",
            extra={"relatorio_id": str(instance.pk), "storage_key": anterior.pdf_storage_key},
        )

    instance.pdf_url = None
    instance.pdf_storage_key = None
