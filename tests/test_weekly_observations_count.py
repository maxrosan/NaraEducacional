"""
Script para verificar se weeklyObservationsCount está contando corretamente.

Compara:
1. O que o frontend recebe (todos os registros, sem filtro de data)
2. O que deveria ser (somente registros da semana atual)

Uso: python test_weekly_observations_count.py
Requer: requests, python-dotenv
"""
import os
import sys
import requests
from datetime import date, timedelta
from dotenv import load_dotenv

# Carregar .env do server
env_path = os.path.join(os.path.dirname(__file__), '..', 'server', '.env')
load_dotenv(env_path)

BASE_URL = os.environ.get('API_BASE_URL', 'http://localhost:8001')

def get_monday_and_sunday():
    """Retorna segunda e domingo da semana atual."""
    today = date.today()
    monday = today - timedelta(days=today.weekday())  # weekday(): 0=segunda
    sunday = monday + timedelta(days=6)
    return monday, sunday

def login(session, email, password):
    """Faz login e retorna dados do usuário."""
    # Buscar CSRF token
    csrf_resp = session.get(f'{BASE_URL}/api/auth/csrf/')
    csrf_token = csrf_resp.json().get('csrfToken', '')

    resp = session.post(
        f'{BASE_URL}/api/auth/login/',
        json={'email': email, 'password': password},
        headers={'X-CSRFToken': csrf_token}
    )
    if resp.status_code != 200:
        print(f"Erro no login: {resp.status_code} - {resp.text}")
        sys.exit(1)
    return resp.json()

def main():
    # Pedir credenciais do coordenador/admin
    email = input("Email do coordenador/admin: ").strip()
    password = input("Senha: ").strip()

    session = requests.Session()

    # Login
    print("\n1. Fazendo login...")
    user_data = login(session, email, password)
    instituicao_id = user_data.get('instituicao_id')
    print(f"   Logado como: {user_data.get('nome')} (perfil: {user_data.get('perfil')})")
    print(f"   Instituição: {instituicao_id}")

    if not instituicao_id:
        print("ERRO: Usuário sem instituicao_id.")
        sys.exit(1)

    monday, sunday = get_monday_and_sunday()
    print(f"\n2. Semana atual: {monday} (segunda) a {sunday} (domingo)")

    # Teste A: O que o frontend realmente faz (enviar filtros que o backend ignora)
    print("\n3. Teste A: Query como o frontend faz (data_observacao__gte/lte)...")
    resp_a = session.get(f'{BASE_URL}/api/observacoes/', params={
        'criancas.instituicao_id': instituicao_id,
        'data_observacao__gte': str(monday),
        'data_observacao__lte': str(sunday),
    })
    data_a = resp_a.json()
    count_a = len(data_a) if isinstance(data_a, list) else 0
    print(f"   Resultado: {count_a} registros")

    # Teste B: Query com os nomes de parâmetro corretos (data_inicio/data_fim)
    print("\n4. Teste B: Query com params corretos (data_inicio/data_fim)...")
    resp_b = session.get(f'{BASE_URL}/api/observacoes/', params={
        'criancas.instituicao_id': instituicao_id,
        'data_inicio': str(monday),
        'data_fim': str(sunday),
    })
    data_b = resp_b.json()
    count_b = len(data_b) if isinstance(data_b, list) else 0
    print(f"   Resultado: {count_b} registros")

    # Teste C: Sem filtro de data (tudo da instituição)
    print("\n5. Teste C: Sem filtro de data (tudo da instituição)...")
    resp_c = session.get(f'{BASE_URL}/api/observacoes/', params={
        'criancas.instituicao_id': instituicao_id,
    })
    data_c = resp_c.json()
    count_c = len(data_c) if isinstance(data_c, list) else 0
    print(f"   Resultado: {count_c} registros")

    # Diagnóstico
    print("\n" + "=" * 60)
    print("DIAGNÓSTICO:")
    print("=" * 60)

    if count_a == count_c:
        print(f"\n⚠ CONFIRMADO: Os filtros de data NÃO estão funcionando!")
        print(f"   Teste A (com filtro de data) = {count_a}")
        print(f"   Teste C (sem filtro de data) = {count_c}")
        print(f"   São iguais → O backend ignora data_observacao__gte/lte")
        print(f"\n   O frontend envia: data_observacao__gte, data_observacao__lte")
        print(f"   O backend espera: data_inicio, data_fim")
        print(f"\n   Contagem correta da semana (Teste B): {count_b}")
        print(f"   Contagem inflada (o que aparece no dashboard): {count_a}")
        if count_b > 0:
            print(f"   Diferença: {count_a - count_b} registros a mais ({((count_a/count_b - 1)*100):.0f}% inflado)")
    elif count_a == count_b:
        print(f"\n✓ Os filtros de data estão funcionando corretamente.")
        print(f"   Registros na semana: {count_a}")
        print(f"   Total da instituição: {count_c}")
    else:
        print(f"\n? Resultado inesperado:")
        print(f"   Teste A (frontend): {count_a}")
        print(f"   Teste B (correto):  {count_b}")
        print(f"   Teste C (sem data): {count_c}")

    # Mostrar distribuição por data se o count parecer alto
    if count_b > 0 and isinstance(data_b, list):
        print(f"\n--- Distribuição dos {count_b} registros da semana por data ---")
        datas = {}
        for r in data_b:
            d = r.get('data_observacao', 'sem data')
            datas[d] = datas.get(d, 0) + 1
        for d in sorted(datas.keys()):
            print(f"   {d}: {datas[d]} registros")

if __name__ == '__main__':
    main()
