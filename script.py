import sys
import os
import time
import datetime
import requests
from google import genai
from google.genai.errors import ServerError, APIError

# 1. Leitura e validação dos parâmetros de entrada
analista = sys.argv[1]
movidesk_token = os.getenv("MOVIDESK_TOKEN")
gemini_api_key = os.getenv("GEMINI_API_KEY")

if not movidesk_token:
    raise ValueError("A variável de ambiente MOVIDESK_TOKEN não está configurada.")
if not gemini_api_key:
    raise ValueError("A variável de ambiente GEMINI_API_KEY não está configurada.")

# Data limite: últimos 30 dias no formato ISO UTC aceito pelo Movidesk
data_limite = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=30)).strftime("%Y-%m-%dT00:00:00.00Z")

print(f"Buscando tickets no Movidesk para o analista '{analista}' desde {data_limite}...")

# 2. Consulta à API de Tickets do Movidesk
url = "https://api.movidesk.com/public/v1/tickets"
params = {
    "token": movidesk_token,
    "$filter": f"owner/businessName eq '{analista}' and createdDate ge {data_limite}",
    "$expand": "actions",
    "$select": "id,subject,category,serviceFirstLevel,status,createdDate,actions"
}

response = requests.get(url, params=params)

if response.status_code != 200:
    raise Exception(f"Erro ao consultar API do Movidesk ({response.status_code}): {response.text}")

tickets = response.json()
print(f"Total de tickets encontrados: {len(tickets)}")

# Caso não existam tickets no período
if not tickets:
    relatorio_vazio = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6;">
        <h2>Relatório de Atendimento - {analista}</h2>
        <p>Nenhum ticket foi encontrado nos últimos 30 dias para este analista.</p>
    </body>
    </html>
    """
    with open("relatorio.html", "w", encoding="utf-8") as f:
        f.write(relatorio_vazio)
    print("Nenhum ticket encontrado. Arquivo 'relatorio.html' gerado com aviso.")
    sys.exit(0)

# 3. Formatação dos dados dos tickets para o prompt
resumo_tickets = []
for t in tickets:
    acoes_texto = []
    if "actions" in t and t["actions"]:
        # Pega as últimas 3 ações/interações para manter o contexto sem sobrecarregar
        for act in t["actions"][-3:]:
            tipo = act.get("actionType", "")
            desc = act.get("description", "").strip()
            if desc:
                acoes_texto.append(f"[{tipo}]: {desc[:300]}")

    resumo_tickets.append({
        "id": t.get("id"),
        "assunto": t.get("subject"),
        "categoria": t.get("category"),
        "servico": t.get("serviceFirstLevel"),
        "status": t.get("status"),
        "comentarios_recentes": acoes_texto
    })

# 4. Construção do Prompt e chamada ao Gemini com Fallback e Retries
client = genai.Client(api_key=gemini_api_key)

prompt = f"""
Você é um especialista em Gestão de Qualidade e Atendimento ao Cliente.
Analise os últimos 30 dias de chamados do analista '{analista}' extraídos do Movidesk.

Dados dos Tickets:
{resumo_tickets}

Gere um relatório formatado em HTML limpo e bem estruturado (retorne APENAS o código HTML puro, sem marcadores de bloco markdown como ```html).

O relatório deve conter:
1. <h2>Resumo dos Maiores Problemas</h2>: Identifique os temas, serviços ou categorias de falhas mais recorrentes.
2. <h2>Pontos Fortes e O que está Bom</h2>: Destaque aspectos positivos do atendimento do analista.
3. <h2>Oportunidades de Melhoria</h2>: Aponte o que pode ser aprimorado na comunicação, tempo de resposta ou resolução.
4. <h2>Plano de Ação Recomendado</h2>: Três ações práticas e objetivas para o analista evoluir.
"""

# Modelos em ordem de prioridade para contornar indisponibilidades temporárias (503)
modelos = ["gemini-2.5-flash", "gemini-2.5-flash-lite"]
gemini_response = None

print("Gerando análise com o Gemini...")

for model_name in modelos:
    tentativas = 3
    for tentativa in range(1, tentativas + 1):
        try:
            print(f"Tentando gerar relatório com {model_name} (tentativa {tentativa}/{tentativas})...")
            gemini_response = client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            break
        except (ServerError, APIError) as e:
            print(f"Aviso: Erro de API ({e.code}). Aguardando para tentar novamente...")
            if tentativa < tentativas:
                time.sleep(tentativa * 5)
            else:
                print(f"Modelo {model_name} indisponível após {tentativas} tentativas. Testando fallback...")
        except Exception as e:
            print(f"Erro inesperado: {e}")
            break

    if gemini_response:
        break

if not gemini_response:
    raise RuntimeError("Não foi possível gerar a análise: os modelos do Gemini estão indisponíveis no momento.")

# 5. Limpeza de formatação Markdown e salvamento do HTML
conteudo_html = gemini_response.text.strip()
if conteudo_html.startswith("```html"):
    conteudo_html = conteudo_html.replace("```html", "", 1)
if conteudo_html.startswith("```"):
    conteudo_html = conteudo_html.replace("```", "", 1)
if conteudo_html.endswith("```"):
    conteudo_html = conteudo_html[:-3]

with open("relatorio.html", "w", encoding="utf-8") as f:
    f.write(conteudo_html.strip())

print("Relatório gerado com sucesso em 'relatorio.html'.")
