import sys
import os
import datetime
import requests
from google import genai

# Parametros de entrada
analista = sys.argv[1]
movidesk_token = os.getenv("MOVIDESK_TOKEN")
gemini_api_key = os.getenv("GEMINI_API_KEY")

# Data limite (30 dias atras no formato ISO do Movidesk)
data_limite = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=30)).strftime("%Y-%m-%dT00:00:00.00Z")

print(f"Buscando tickets no Movidesk para o analista '{analista}' desde {data_limite}...")

# 1. Consulta a API de Tickets do Movidesk
# Filtra pelo nome do analista responsável e pela data de criação
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

if not tickets:
    relatorio_vazio = f"""
    <h2>Relatório de Atendimento - {analista}</h2>
    <p>Nenhum ticket encontrado nos últimos 30 dias no nome deste analista.</p>
    """
    with open("relatorio.html", "w", encoding="utf-8") as f:
        f.write(relatorio_vazio)
    sys.exit(0)

# Formatar os dados dos tickets para envio ao Gemini
resumo_tickets = []
for t in tickets:
    # Extrai ultimas acoes/comentarios dos clientes ou agentes
    acoes_texto = []
    if "actions" in t and t["actions"]:
        for act in t["actions"][-3:]: # Pega ate as 3 ultimas acoes para nao sobrecarregar
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

# 2. Enviar prompt para o Gemini
client = genai.Client(api_key=gemini_api_key)

prompt = f"""
Você é um especialista em Gestão de Qualidade e Atendimento ao Cliente.
Analise os últimos 30 dias de chamados do analista '{analista}' no Movidesk.

Dados dos Tickets:
{resumo_tickets}

Gere um relatório formatado em HTML limpo (retorne APENAS a estrutura do corpo do HTML, sem tags markdown do tipo ```html):
1. **Resumo dos Maiores Problemas**: Identifique os temas, serviços ou categorias de falhas mais recorrentes nos atendimentos.
2. **Pontos Fortes e O que está Bom**: Destaque aspectos positivos com base nas interações, resoluções e histórico de comentários.
3. **Oportunidades de Melhoria**: Aponte o que precisa ser aprimorado nos atendimentos, comunicação ou tempo/fluxo de resolução.
4. **Plano de Ação Recomendado**: Sugira 2 a 3 ações práticas para o analista evoluir no próximo mês.
"""

print("Gerando análise com o Gemini...")
gemini_response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=prompt
)

# Salvar o resultado HTML
with open("relatorio.html", "w", encoding="utf-8") as f:
    f.write(gemini_response.text)

print("Relatório gerado com sucesso em 'relatorio.html'.")
