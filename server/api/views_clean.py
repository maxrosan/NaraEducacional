from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.http import FileResponse, Http404
import json
import hashlib
import os
import time
import random
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from .models import RegistroEscrita
from .openai_client import get_openai_client

def gerar_nome_arquivo_seguro(nome_aluno, arquivo_original):
    """
    Gera um nome de arquivo seguro usando hash para evitar conflitos
    """
    timestamp = str(int(time.time()))
    random_value = str(random.randint(1000, 9999))
    
    # Limpar nome do aluno (remover caracteres especiais)
    nome_limpo = ''.join(c for c in nome_aluno if c.isalnum() or c in (' ', '-', '_')).strip()
    nome_limpo = nome_limpo.replace(' ', '_').replace('-', '_')
    
    # Criar hash baseado em nome + timestamp + random
    hash_input = f"{nome_limpo}_{timestamp}_{random_value}".encode('utf-8')
    file_hash = hashlib.md5(hash_input).hexdigest()[:12]
    
    # Extrair extensão segura
    extensao = 'jpg'  # default
    if '.' in arquivo_original:
        ext_original = arquivo_original.split('.')[-1].lower()
        # Permitir apenas extensões seguras
        extensoes_permitidas = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp']
        if ext_original in extensoes_permitidas:
            extensao = ext_original
    
    return f"{file_hash}_{nome_limpo}_{timestamp}.{extensao}", file_hash


@api_view(['GET'])
def hello_world(request):
    """
    Simple Hello World API endpoint
    """
    return Response({
        'message': 'Hello World from Nara API!',
        'status': 'success',
        'version': '1.0.0'
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
def health_check(request):
    """
    Health check endpoint
    """
    return Response({
        'status': 'healthy',
        'message': 'API is running properly'
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
def analise_de_escrita(request):
    """
    API endpoint para análise de escrita (apenas metadados - versão simples)
    """
    try:
        nome_aluno = request.data.get('nomeAluno', '')
        serie_aluno = request.data.get('serieAluno', '')
        nome_arquivo = request.data.get('nomeArquivo', '')
        turma_id = request.data.get('turmaId', '')
        
        resultado = {
            'nomeAluno': nome_aluno,
            'serieAluno': serie_aluno,
            'nomeArquivo': nome_arquivo,
            'turmaId': turma_id,
            'analise': {
                'descricao': f"Análise simples da escrita de {nome_aluno}. Arquivo: {nome_arquivo}.",
                'fase_escrita': 'Em análise',
                'data_analise': "2025-07-28"
            }
        }
        
        return Response(resultado, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'error': 'Erro interno no servidor', 'details': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
@api_view(['POST'])
def upload_e_analise_escrita(request):
    """
    API endpoint para upload de arquivo e análise de escrita
    """
    try:
        # Verificar se o arquivo foi enviado
        if 'arquivo' not in request.FILES:
            return Response(
                {'error': 'Nenhum arquivo foi enviado'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        arquivo = request.FILES['arquivo']
        nome_aluno = request.POST.get('nomeAluno', '')
        serie_aluno = request.POST.get('serieAluno', '')
        turma_id = request.POST.get('turmaId', '')
        
        # Validar dados obrigatórios
        if not nome_aluno or not serie_aluno:
            return Response(
                {'error': 'Nome do aluno e série são obrigatórios'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Criar diretório de uploads se não existir
        upload_dir = 'uploads/escrita'
        os.makedirs(upload_dir, exist_ok=True)
        
        # Gerar nome de arquivo seguro com hash
        arquivo_nome, file_hash = gerar_nome_arquivo_seguro(nome_aluno, arquivo.name)
        arquivo_path = os.path.join(upload_dir, arquivo_nome)
        
        with open(arquivo_path, 'wb+') as destination:
            for chunk in arquivo.chunks():
                destination.write(chunk)
        
        # Log do upload realizado
        print(f"[UPLOAD] Arquivo salvo: {arquivo_nome}")
        print(f"[UPLOAD] Hash gerado: {file_hash}")
        print(f"[UPLOAD] Aluno: {nome_aluno}")
        print(f"[UPLOAD] Tamanho: {arquivo.size} bytes")

        # Prompt para análise de escrita com OpenAI
        prompt = f"""
Atue como uma especialista em psicogênese da língua escrita, clonando a sensibilidade e a inteligência de Emilia Ferreiro e Ana Teberosky. Analise com profundidade a escrita infantil de {nome_aluno} a partir dos seguintes pilares: hipótese da criança sobre o sistema de escrita, correspondência sonora, uso de letras e estrutura da palavra.

🔍 Etapas da Análise:

Observe cuidadosamente a imagem da escrita infantil anexada.

Classifique com precisão em uma das fases da psicogênese:
- Pré-silábica
- Silábica sem valor sonoro
- Silábica com valor sonoro
- Silábico-alfabética
- Alfabética

Fundamente sua análise com base nos critérios observacionais de Ferreiro e Teberosky, sem copiar trechos teóricos nem soar como ChatGPT.

🧠 Formato da Resposta:
A resposta deve conter duas partes obrigatórias:

PARTE 1 – ANÁLISE TÉCNICA (máx. 4 linhas)
Use linguagem clara, direta e objetiva. Traga o nome da fase da escrita e os principais indícios observados.

PARTE 2 – PARA FAMÍLIA (mais detalhada)
Fale como se estivesse explicando para a mãe, o pai que não conhece termos técnicos. Use exemplos simples, metáforas acessíveis e um tom afetivo, como numa conversa entre gente que cuida junto.

Evite termos como "hipótese", "fonema", "notação", "grafema". Prefira expressões como "ela está tentando entender que...", "nesse momento, é como se ele pensasse que...".

🎯 Importante:
Evite parecer uma máquina. Sua fala deve tocar o coração de quem lê. Traduza o conhecimento com humanidade, sem perder a precisão.
"""
        
        try:
            # Chamar OpenAI para análise
            print(f"[OPENAI] Enviando prompt para análise da escrita de {nome_aluno}")
            
            openai_client = get_openai_client()

            response = openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=800,
                temperature=0.7
            )
            
            analise_completa = response.choices[0].message.content.strip()
            print(f"[OPENAI] Análise recebida com {len(analise_completa)} caracteres")
            
            # Extrair a fase da escrita da análise
            etapa_detectada = "Análise em processamento"
            
            # Procurar pela fase mencionada na análise
            fases_possiveis = ['Pré-silábica', 'Silábica sem valor sonoro', 'Silábica com valor sonoro', 'Silábico-alfabética', 'Alfabética']
            analise_lower = analise_completa.lower()
            for fase in fases_possiveis:
                if fase.lower() in analise_lower:
                    etapa_detectada = fase
                    break
            
        except RuntimeError as openai_config_error:
            print(f"[OPENAI ERROR] Configuração ausente: {openai_config_error}")
            analise_completa = f"ANÁLISE TÉCNICA:\nA configuração da OpenAI não está disponível. Configure a variável OPENAI_API_KEY e tente novamente."
            etapa_detectada = "Configuração OpenAI ausente"
        except Exception as openai_error:
            print(f"[OPENAI ERROR] Erro na chamada da OpenAI: {openai_error}")
            # Fallback para análise mock em caso de erro
            analise_completa = f"ANÁLISE TÉCNICA:\nA escrita de {nome_aluno} está em processo de análise. Aguarde o processamento completo.\n\nPARA FAMÍLIA:\nEstamos analisando a escrita de {nome_aluno} com muito carinho. Em breve teremos uma análise detalhada sobre o desenvolvimento da escrita."
            etapa_detectada = "Em análise"

🔍 Etapas da Análise:

Observe cuidadosamente a imagem ou transcrição da escrita infantil.

Classifique com precisão em uma das fases da psicogênese:

Pré-silábica

Silábica sem valor sonoro

Silábica com valor sonoro

Silábico-alfabética

Alfabética

Fundamente sua análise com base nos critérios observacionais de Ferreiro e Teberosky, sem copiar trechos teóricos nem soar como ChatGPT.

🧠 Formato da Resposta:
A resposta deve conter duas partes obrigatórias:

Parte 1 – Análise Técnica (máx. 4 linhas)
Use linguagem clara, direta e objetiva. Traga o nome da fase da escrita e os principais indícios observados.

Parte 2 – Explicação Popular e Acolhedora (mais detalhada)
Fale como se estivesse explicando para a mãe, o pai  mas não sabe termos técnicos. Use exemplos simples, metáforas acessíveis e um tom afetivo, como numa conversa entre gente que cuida junto.

Evite termos como “hipótese”, “fonema”, “notação”, “grafema”. Prefira expressões como “ela está tentando entender que...”, “nesse momento, é como se ele pensasse que...”.

"O que essa escrita mostra é que seu filho está numa fase de descoberta linda. Ele ainda não liga som e letra certinho, mas já entendeu que escrever é botar no papel alguma coisa que mora na cabeça dele. Isso é sinal de que ele está no caminho certo. Nosso papel agora é mostrar, com carinho, como o som das palavras pode virar letrinha. Devagarinho, sem pressão."

🎯 Importante:
Evite parecer uma máquina. Sua fala deve tocar o coração de quem lê. Traduza o conhecimento com humanidade, sem perder a precisão.
        """
      
        
        # Selecionar análise baseada no hash do nome (para consistência)
        hash_nome = int(hashlib.md5(nome_aluno.encode()).hexdigest(), 16)
        tipos_analise = list(analises_disponiveis.keys())
        tipo_selecionado = tipos_analise[hash_nome % len(tipos_analise)]
        analise_selecionada = analises_disponiveis[tipo_selecionado]
        
        # Salvar no banco de dados
        try:
            registro = RegistroEscrita.objects.create(
                nome_aluno=nome_aluno,
                turma_id=turma_id,
                serie_aluno=serie_aluno,
                arquivo_nome=arquivo_nome,
                arquivo_hash=file_hash,
                arquivo_path=arquivo_path,
                arquivo_original=arquivo.name,
                tamanho_arquivo=arquivo.size,
                tipo_arquivo=arquivo.content_type or 'image/unknown',
                etapa_ia=analise_selecionada['fase'],
                analise_detalhada=f"ANÁLISE TÉCNICA:\n{analise_selecionada['descricao_tecnica']}\n\nPARA FAMÍLIA:\n{analise_selecionada['descricao_popular']}",
                professora="Sistema",  # Por enquanto, depois vamos integrar com autenticação
                anotacoes_professora=""
            )
            
            print(f"[DATABASE] Registro salvo com ID: {registro.id}")
            
        except Exception as db_error:
            print(f"[DATABASE ERROR] Erro ao salvar no banco: {db_error}")
            # Continua mesmo se houver erro no banco - pelo menos retorna a análise
        
        resultado = {
            'success': True,
            'arquivo_salvo': arquivo_path,
            'arquivo_nome': arquivo_nome,
            'arquivo_hash': file_hash,
            'arquivo_original': arquivo.name,
            'nomeAluno': nome_aluno,
            'serieAluno': serie_aluno,
            'nomeArquivo': arquivo.name,
            'turmaId': turma_id,
            'analise': {
                'descricao': f"ANÁLISE TÉCNICA:\n{analise_selecionada['descricao_tecnica']}\n\nPARA FAMÍLIA:\n{analise_selecionada['descricao_popular']}",
                'fase_escrita': analise_selecionada['fase'],
                'arquivo_processado': True,
                'arquivo_id': file_hash,
                'tamanho_arquivo': arquivo.size,
                'tipo_arquivo': arquivo.content_type,
                'data_analise': "2025-07-28"
            }
        }
        
        return Response(resultado, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'error': 'Erro interno no servidor', 'details': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def upload_e_analise_escrita_mock(request):
    """
    API endpoint para upload de arquivo e análise de escrita
    """
    try:
        # Verificar se o arquivo foi enviado
        if 'arquivo' not in request.FILES:
            return Response(
                {'error': 'Nenhum arquivo foi enviado'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        arquivo = request.FILES['arquivo']
        nome_aluno = request.POST.get('nomeAluno', '')
        serie_aluno = request.POST.get('serieAluno', '')
        turma_id = request.POST.get('turmaId', '')
        
        # Validar dados obrigatórios
        if not nome_aluno or not serie_aluno:
            return Response(
                {'error': 'Nome do aluno e série são obrigatórios'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Criar diretório de uploads se não existir
        upload_dir = 'uploads/escrita'
        os.makedirs(upload_dir, exist_ok=True)
        
        # Gerar nome de arquivo seguro com hash
        arquivo_nome, file_hash = gerar_nome_arquivo_seguro(nome_aluno, arquivo.name)
        arquivo_path = os.path.join(upload_dir, arquivo_nome)
        
        with open(arquivo_path, 'wb+') as destination:
            for chunk in arquivo.chunks():
                destination.write(chunk)
        
        # Log do upload realizado
        print(f"[UPLOAD] Arquivo salvo: {arquivo_nome}")
        print(f"[UPLOAD] Hash gerado: {file_hash}")
        print(f"[UPLOAD] Aluno: {nome_aluno}")
        print(f"[UPLOAD] Tamanho: {arquivo.size} bytes")
        
        # Análises disponíveis baseadas na psicogênese da escrita
        analises_disponiveis = {
            'pre_silabica': {
                'fase': 'Pré-silábica',
                'descricao_tecnica': f"A escrita de {nome_aluno} encontra-se na fase pré-silábica. Utiliza grafismos primitivos sem correspondência sonora, demonstrando compreensão de que a escrita representa algo, mas ainda não estabelece relação entre grafemas e sons.",
                'descricao_popular': f"O que a escrita de {nome_aluno} nos mostra é algo muito bonito: ela já entendeu que escrever é uma forma de guardar pensamentos no papel! Nesse momento, é como se estivesse descobrindo que aqueles risquinhos têm um significado especial. Ainda não consegue ligar certinho o som das palavras com as letrinhas, mas isso é normal e esperado. Nossa tarefa agora é mostrar, com muito carinho e sem pressa, como os sons que falamos podem virar letrinhas no papel."
            },
            'silabica_sem_valor': {
                'fase': 'Silábica sem valor sonoro',
                'descricao_tecnica': f"A escrita de {nome_aluno} indica transição para a fase silábica sem valor sonoro. A criança já compreende que a escrita representa a pauta sonora, utilizando uma letra para cada sílaba, porém sem correspondência sonora convencional.",
                'descricao_popular': f"Que evolução linda na escrita de {nome_aluno}! Agora ela já descobriu algo fundamental: que cada pedacinho que falamos (cada sílaba) precisa de uma letrinha. É como se tivesse entendido que as palavras têm 'partes' e cada parte merece sua marca no papel. Ainda não escolhe as letrinhas certas para cada som, mas isso não é problema - está no caminho certinho!"
            },
            'silabica_com_valor': {
                'fase': 'Silábica com valor sonoro',
                'descricao_tecnica': f"{nome_aluno} demonstra compreensão da relação entre sons e letras, usando principalmente vogais para representar sílabas. Cada letra corresponde a um som silábico, revelando avanço significativo na hipótese da escrita.",
                'descricao_popular': f"Que alegria ver {nome_aluno} descobrindo que as letrinhas têm seus sons! Ele já entendeu que cada pedacinho da palavra (que chamamos de sílaba) precisa de uma letra. É como se ele tivesse descoberto um segredo: as palavras não são só desenhos, elas falam! Ainda está aprendendo todas as letras, mas o caminho está certinho. É uma fase linda de descoberta."
            },
            'silabico_alfabetica': {
                'fase': 'Silábico-alfabética',
                'descricao_tecnica': f"{nome_aluno} transiciona entre a hipótese silábica e alfabética, alternando entre representar sílabas completas e apenas partes delas. Demonstra conflito cognitivo produtivo entre diferentes hipóteses de escrita.",
                'descricao_popular': f"O {nome_aluno} está numa fase de transição muito interessante! É como se estivesse com dois pensamentos ao mesmo tempo: às vezes escreve pensando nos pedacinhos das palavras (sílabas), outras vezes tenta escrever cada letrinha que escuta. Isso é normal e mostra que está evoluindo. É como aprender a andar - primeiro vacila, depois fica firme."
            },
            'alfabetica': {
                'fase': 'Alfabética',
                'descricao_tecnica': f"{nome_aluno} compreende o princípio alfabético, estabelecendo correspondência entre grafemas e fonemas. Sua escrita reflete compreensão da base do sistema alfabético, embora possa apresentar questões ortográficas típicas do processo.",
                'descricao_popular': f"Parabéns! O {nome_aluno} descobriu o grande segredo da escrita: cada letrinha tem seu som e cada som pode virar letrinha. Ele já escreve pensando em todos os sons que escuta nas palavras. Pode ser que ainda troque algumas letras ou esqueça os acentos, mas isso é normal. O mais importante ele já conquistou: sabe que escrever é uma forma de falar no papel."
            }
        }
        
        # Selecionar análise baseada no hash do nome (para consistência)
        hash_nome = int(hashlib.md5(nome_aluno.encode()).hexdigest(), 16)
        tipos_analise = list(analises_disponiveis.keys())
        tipo_selecionado = tipos_analise[hash_nome % len(tipos_analise)]
        analise_selecionada = analises_disponiveis[tipo_selecionado]
        
        # Salvar no banco de dados
        try:
            registro = RegistroEscrita.objects.create(
                nome_aluno=nome_aluno,
                turma_id=turma_id,
                serie_aluno=serie_aluno,
                arquivo_nome=arquivo_nome,
                arquivo_hash=file_hash,
                arquivo_path=arquivo_path,
                arquivo_original=arquivo.name,
                tamanho_arquivo=arquivo.size,
                tipo_arquivo=arquivo.content_type or 'image/unknown',
                etapa_ia=analise_selecionada['fase'],
                analise_detalhada=f"ANÁLISE TÉCNICA:\n{analise_selecionada['descricao_tecnica']}\n\nPARA FAMÍLIA:\n{analise_selecionada['descricao_popular']}",
                professora="Sistema",  # Por enquanto, depois vamos integrar com autenticação
                anotacoes_professora=""
            )
            
            print(f"[DATABASE] Registro salvo com ID: {registro.id}")
            
        except Exception as db_error:
            print(f"[DATABASE ERROR] Erro ao salvar no banco: {db_error}")
            # Continua mesmo se houver erro no banco - pelo menos retorna a análise
        
        resultado = {
            'success': True,
            'arquivo_salvo': arquivo_path,
            'arquivo_nome': arquivo_nome,
            'arquivo_hash': file_hash,
            'arquivo_original': arquivo.name,
            'nomeAluno': nome_aluno,
            'serieAluno': serie_aluno,
            'nomeArquivo': arquivo.name,
            'turmaId': turma_id,
            'analise': {
                'descricao': f"ANÁLISE TÉCNICA:\n{analise_selecionada['descricao_tecnica']}\n\nPARA FAMÍLIA:\n{analise_selecionada['descricao_popular']}",
                'fase_escrita': analise_selecionada['fase'],
                'arquivo_processado': True,
                'arquivo_id': file_hash,
                'tamanho_arquivo': arquivo.size,
                'tipo_arquivo': arquivo.content_type,
                'data_analise': "2025-07-28"
            }
        }
        
        return Response(resultado, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'error': 'Erro interno no servidor', 'details': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def listar_uploads(request):
    """
    API endpoint para listar arquivos enviados (para debug)
    """
    try:
        upload_dir = 'uploads/escrita'
        if not os.path.exists(upload_dir):
            return Response({'arquivos': []}, status=status.HTTP_200_OK)
        
        arquivos = []
        for arquivo in os.listdir(upload_dir):
            arquivo_path = os.path.join(upload_dir, arquivo)
            if os.path.isfile(arquivo_path):
                stat = os.stat(arquivo_path)
                arquivos.append({
                    'nome': arquivo,
                    'tamanho': stat.st_size,
                    'data_criacao': time.ctime(stat.st_ctime),
                    'hash_id': arquivo.split('_')[0] if '_' in arquivo else 'unknown'
                })
        
        return Response({
            'total_arquivos': len(arquivos),
            'arquivos': arquivos
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'error': 'Erro ao listar arquivos', 'details': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def salvar_anotacoes_professora(request):
    """
    API endpoint para salvar as anotações adicionais da professora
    """
    try:
        arquivo_hash = request.data.get('arquivo_hash', '')
        anotacoes = request.data.get('anotacoes', '')
        professora = request.data.get('professora', 'Professora')
        
        if not arquivo_hash:
            return Response(
                {'error': 'Hash do arquivo é obrigatório'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Buscar o registro pelo hash do arquivo
        try:
            registro = RegistroEscrita.objects.get(arquivo_hash=arquivo_hash)
            registro.anotacoes_professora = anotacoes
            registro.professora = professora
            registro.save()
            
            return Response({
                'success': True,
                'message': 'Anotações da professora salvas com sucesso',
                'registro_id': registro.id
            }, status=status.HTTP_200_OK)
            
        except RegistroEscrita.DoesNotExist:
            return Response(
                {'error': 'Registro não encontrado'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
    except Exception as e:
        return Response(
            {'error': 'Erro interno no servidor', 'details': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def listar_registros_escrita(request):
    """
    API endpoint para listar todos os registros de escrita
    """
    try:
        registros = RegistroEscrita.objects.all().order_by('-data_criacao')
        
        dados = []
        for registro in registros:
            dados.append({
                'id': registro.id,
                'nome_aluno': registro.nome_aluno,
                'turma_id': registro.turma_id,
                'serie_aluno': registro.serie_aluno,
                'etapa_ia': registro.etapa_ia,
                'professora': registro.professora,
                'arquivo_nome': registro.arquivo_nome,
                'arquivo_hash': registro.arquivo_hash,
                'data_criacao': registro.data_criacao.strftime('%d/%m/%Y %H:%M'),
                'tem_anotacoes': bool(registro.anotacoes_professora)
            })
        
        return Response({
            'total_registros': len(dados),
            'registros': dados
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'error': 'Erro ao listar registros', 'details': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def registros_por_aluno(request, nome_aluno):
    """
    API endpoint para buscar registros de escrita de um aluno específico
    """
    try:
        registros = RegistroEscrita.objects.filter(
            nome_aluno__icontains=nome_aluno
        ).order_by('-data_criacao')
        
        registros_data = []
        for registro in registros:
            # Criar resumo da análise (primeiras 120 caracteres)
            analise_resumida = registro.analise_detalhada[:120] + '...' if len(registro.analise_detalhada) > 120 else registro.analise_detalhada
            
            registros_data.append({
                'id': registro.id,
                'nome_aluno': registro.nome_aluno,
                'data_criacao': registro.data_criacao.strftime('%d/%m/%Y às %H:%M'),
                'etapa_ia': registro.etapa_ia,
                'analise_resumida': analise_resumida,
                'analise_completa': registro.analise_detalhada,
                'anotacoes_professora': registro.anotacoes_professora or '',
                'professora': registro.professora,
                'arquivo_nome': registro.arquivo_nome,
                'arquivo_hash': registro.arquivo_hash,
                'serie_aluno': registro.serie_aluno,
                'turma_id': registro.turma_id,
                'tamanho_arquivo': registro.tamanho_arquivo,
                'tipo_arquivo': registro.tipo_arquivo
            })
        
        return Response({
            'success': True,
            'registros': registros_data,
            'total': len(registros_data),
            'aluno': nome_aluno
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'error': 'Erro ao buscar registros do aluno', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def servir_arquivo(request, arquivo_hash):
    """
    API endpoint para servir arquivos de escrita de forma segura
    """
    try:
        # Buscar o registro pelo hash
        registro = RegistroEscrita.objects.get(arquivo_hash=arquivo_hash)
        
        # Verificar se o arquivo existe
        if not os.path.exists(registro.arquivo_path):
            raise Http404("Arquivo não encontrado")
        
        # Servir o arquivo
        response = FileResponse(
            open(registro.arquivo_path, 'rb'),
            content_type=registro.tipo_arquivo or 'application/octet-stream'
        )
        
        # Adicionar headers de segurança
        response['Content-Disposition'] = f'inline; filename="{registro.arquivo_nome}"'
        response['X-Content-Type-Options'] = 'nosniff'
        
        return response
        
    except RegistroEscrita.DoesNotExist:
        raise Http404("Registro não encontrado")
    except Exception as e:
        return Response(
            {'error': 'Erro ao servir arquivo', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
