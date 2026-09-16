from django.db import models


class PromptCategoria(models.Model):
    titulo = models.CharField(max_length=200)
    ativo = models.BooleanField(default=True)

    class Meta:
        db_table = 'prompt_categorias'
        managed = True
        verbose_name = 'Categoria de Prompt'
        verbose_name_plural = 'Categorias de Prompt'

    def __str__(self):
        return self.titulo


class PromptTemplate(models.Model):
    # 'global' é palavra reservada do Python -> atributo prompt_global, coluna 'global'
    prompt_global = models.TextField(blank=True, default='', db_column='global')
    personalizado = models.TextField(blank=True, default='')
    categoria = models.ForeignKey(
        PromptCategoria,
        on_delete=models.CASCADE,
        db_column='categoria_id',
        related_name='templates',
    )
    cliente_id = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = 'prompt_templates'
        managed = True
        verbose_name = 'Template de Prompt'
        verbose_name_plural = 'Templates de Prompt'

    def __str__(self):
        return f'{self.categoria.titulo} — {self.cliente_id or "global"}'
