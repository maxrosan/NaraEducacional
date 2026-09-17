from django.db import models

from .tenancy import get_current_tenant


class TenantQuerySet(models.QuerySet):
    def for_escola(self, escola_id):
        return self.filter(escola_id=escola_id)

    def for_instituicao(self, instituicao_id):
        return self.filter(instituicao_id=instituicao_id)


class TenantManager(models.Manager):
    def get_queryset(self):
        qs = TenantQuerySet(self.model, using=self._db)
        scope = get_current_tenant()
        if scope is None:
            return qs

        nivel, valor = scope
        if nivel == 'escola':
            return qs.filter(escola_id=valor)
        if nivel == 'instituicao':
            return qs.filter(instituicao_id=valor)
        return qs