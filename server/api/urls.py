from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views.auth import LoginView, me, alterar_senha, recuperar_senha, confirmar_senha
from .views.health import health
from .views.instituicao import (
    listar_instituicoes,
    criar_instituicao,
    detalhe_instituicao,
    atualizar_instituicao,
)
from .views.escola import (
    listar_escolas,
    criar_escola,
    detalhe_escola,
    atualizar_escola,
)
from .views.especialista import (
    listar_especialistas,
    criar_especialista,
    detalhe_especialista,
    atualizar_especialista,
)

urlpatterns = [
    path('health/', health, name='health'),

    # Autenticação (JWT)
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/alterar-senha/', alterar_senha, name='alterar_senha'),
    path('auth/recuperar-senha/', recuperar_senha, name='recuperar_senha'),
    path('auth/confirmar-senha/', confirmar_senha, name='confirmar_senha'),
    path('me/', me, name='me'),

    # Instituições
    path('instituicoes/', listar_instituicoes, name='listar_instituicoes'),
    path('instituicoes/criar/', criar_instituicao, name='criar_instituicao'),
    path('instituicoes/<uuid:instituicao_id>/', detalhe_instituicao, name='detalhe_instituicao'),
    path('instituicoes/<uuid:instituicao_id>/atualizar/', atualizar_instituicao, name='atualizar_instituicao'),

    # Escolas
    path('escolas/', listar_escolas, name='listar_escolas'),
    path('escolas/criar/', criar_escola, name='criar_escola'),
    path('escolas/<uuid:escola_id>/', detalhe_escola, name='detalhe_escola'),
    path('escolas/<uuid:escola_id>/atualizar/', atualizar_escola, name='atualizar_escola'),

    # Especialistas
    path('especialistas/', listar_especialistas, name='listar_especialistas'),
    path('especialistas/criar/', criar_especialista, name='criar_especialista'),
    path('especialistas/<uuid:especialista_id>/', detalhe_especialista, name='detalhe_especialista'),
    path('especialistas/<uuid:especialista_id>/atualizar/', atualizar_especialista, name='atualizar_especialista'),
]