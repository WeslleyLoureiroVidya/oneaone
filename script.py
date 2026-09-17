import sys
import os
import datetime
from google import genai

analista = sys.argv[1]
data_limite = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime("%Y-%m-%d")

# 1. Coleta dos tickets (substitua pela API real da sua ferramenta)
dados_tickets_mock = "Substitua pelos dados reais extraídos: notas, comentários e categorias."

# 2. Inicialização do cliente Gemini
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

prompt = f"""
Analise os últimos 30 dias de atendimentos do analista '{analista}':
Dados: {dados_tickets_mock}

Gere um relatório em formato HTML legível (apenas o corpo HTML em código limpo, sem marcações markdown ```html) contendo:
1. Resumo dos maiores problemas relatados pelos clientes.
2. Análise reflexiva do que está bom (pontos fortes baseados em notas e elogios).
3. O que precisa melhorar (oportunidades de evolução baseadas em comentários negativos).
"""

# 3. Geração do relatório com Gemini
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=prompt
)

with open("relatorio.html", "w", encoding="utf-8") as f:
    f.write(response.text)
