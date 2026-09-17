import sys
import os
import datetime
import requests
from google import genai

# Parametros de entrada
analista = sys.argv[1]
movidesk_token = os.getenv("MOVIDESK_TOKEN")
gemini_api_key = os.getenv("GEMINI_API_KEY")

# Validação das variáveis de ambiente
if not movidesk_token:
    raise ValueError("A variavel de ambiente MOVIDESK_TOKEN nao esta configurada.")
if not gemini_api_key:
    raise ValueError("A variavel de ambiente GEMINI_API_KEY nao esta configurada.")

# Data limite (30 dias atras no formato ISO UTC do Movidesk)
data_limite = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=30)).strftime("%Y-%m-%dT00:00:00.00Z")

print(f"Buscando tickets no Movidesk para o analista '{analista}' desde {data_limite}...")

# 1. Consulta a API de Tickets do Movidesk
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

# Caso nao existam tickets no periodo
if not tickets:
    relatorio_vazio = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6;">
        <h2>Relatorio de Atendimento - {analista}</h2>
        <p>Nenhum ticket foi encontrado nos ultimos 30 dias para este analista.</p>
    </body>
    </html>
    """
    with open("relatorio.html", "w", encoding="utf-8") as f:
        f.write(relatorio_vazio)
    print("Nenhum ticket encontrado. Arquivo 'relatorio.html' gerado com aviso.")
    sys.exit(0)

# 2. Formatar os dados dos tickets para o prompt
resumo_tickets = []
for t in tickets:
    acoes_texto = []
    if "actions" in t and t["actions"]:
        # Pega as 3 ultimas acoes para contextualizar o atendimento sem inflar o prompt
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

# 3. Inicializar o cliente Gemini e gerar a analise
print("Gerando analise com o Gemini...")
client = genai.Client(api_key=gemini_api_key)

prompt = f"""
Voce e um especialista em Gestao de Qualidade e Atendimento ao Cliente.
Analise os ultimos 30 dias de chamados do analista '{analista}' extraidos do Movidesk.

Dados dos Tickets:
{resumo_tickets}

Gere um relatorio formatado em HTML limpo e bem estruturado (retorne APENAS o codigo HTML puro, sem marcadores de bloco markdown como ```html).

O relatorio deve conter:
1. <h2>Resumo dos Maiores Problemas</h2>: Identifique os temas, servicos ou categorias de falhas mais recorrentes.
2. <h2>Pontos Fortes e O que esta Bom</h2>: Destaque aspectos positivos do atendimento do analista.
3. <h2>Oportunidades de Melhoria</h2>: Aponte o que pode ser aprimorado na comunicacao, tempo de resposta ou resolucao.
4. <h2>Plano de Acao Recomendado</h2>: Três acoes praticas e objetivas para o analista evoluir.
"""

gemini_response = client.models.generate_content(
    model="gemini-3.6-flash",
    contents=prompt
)

# Limpeza preventiva caso a IA insira blocos de codigo Markdown
conteudo_html = gemini_response.text.strip()
if conteudo_html.startswith("```html"):
    conteudo_html = conteudo_html.replace("```html", "", 1)
if conteudo_html.startswith("```"):
    conteudo_html = conteudo_html.replace("```", "", 1)
if conteudo_html.endswith("```"):
    conteudo_html = conteudo_html[:-3]

# 4. Salvar o relatorio final
with open("relatorio.html", "w", encoding="utf-8") as f:
    f.write(conteudo_html.strip())

print("Relatorio gerado com sucesso em 'relatorio.html'.")
