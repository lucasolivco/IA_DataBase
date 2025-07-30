Assistente SQL - Consulta em Linguagem Natural para Bancos de Dados

DESCRIÇÃO:
Sistema que permite fazer consultas a bancos de dados SQL usando linguagem natural. Utiliza IA avançada (modelo Microsoft Phi-3) para traduzir perguntas em comandos SQL válidos.

PRINCIPAIS CARACTERÍSTICAS:
- Tradução de perguntas em linguagem natural para SQL
- Execução direta de consultas no banco de dados
- Formatação amigável dos resultados
- Suporte a múltiplas tabelas com cache de schema
- Validação de segurança contra comandos maliciosos
- Interface API RESTful para integração

FLUXO DE FUNCIONAMENTO:
1. Usuário envia pergunta em linguagem natural via API
2. Sistema consulta modelo de IA com schema da tabela
3. IA gera comando SQL correspondente
4. Sistema valida e executa o SQL no banco
5. Resultados são formatados e retornados

TECNOLOGIAS:
- Backend: Flask (Python)
- Banco de Dados: SQL Server (via pyodbc)
- IA: Hugging Face API (modelo microsoft/phi-3-mini-4k-instruct)
- Gerenciamento: dotenv para variáveis de ambiente
- Segurança: Validação rigorosa de comandos SQL

ENDOPOINTS PRINCIPAIS:
POST /perguntar
• Recebe: {"pergunta": "texto", "tabela": "nome_tabela"}
• Retorna: SQL gerado, resultados formatados e dados brutos

GET /schema/<tabela>
• Retorna estrutura completa da tabela

GET /tabelas
• Lista tabelas disponíveis para consulta

PRÉ-REQUISITOS:
1. Conta no Hugging Face com token de API
2. Acesso a banco SQL Server
3. Python 3.8+
4. Variáveis de ambiente configuradas

CONFIGURAÇÃO (arquivo .env):
DB_DRIVER="ODBC Driver 17 for SQL Server"
DB_SERVER="endereco_servidor"
DB_NAME="nome_banco"
DB_USER="usuario"
DB_PASSWORD="senha"
HF_TOKEN="seu_token_hugging_face"

INSTALAÇÃO:
1. Crie ambiente virtual:
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate    # Windows

2. Instale dependências:
pip install flask flask_cors pyodbc requests python-dotenv

3. Configure o arquivo .env

4. Execute o servidor:
python backend.py

EXEMPLOS DE USO:
Pergunta: "Mostre os 5 primeiros atendentes"
SQL Gerado: SELECT TOP 5 * FROM atendentes

Pergunta: "Qual o status da empresa Volseg?"
SQL Gerado: SELECT status FROM empresas WHERE razao_social LIKE '%volseg%'

Pergunta: "Quantos registros ativos?"
SQL Gerado: SELECT COUNT(*) FROM atendentes WHERE ativo = 1

FORMATO DA RESPOSTA:
Total de registros: 2

Registro 1:
id: "123"
nome: "João Silva"
email: "joao@empresa.com"

Registro 2:
id: "456"
nome: "Maria Oliveira"
email: "maria@empresa.com"

SEGURANÇA:
- Bloqueio de comandos perigosos (INSERT, UPDATE, DELETE, DROP)
- Validação de referência à tabela correta
- Filtragem de palavras-chave maliciosas
- Cache de schema com expiração (1 hora)
- Limitador de resultados (100 registros)

PERSONALIZAÇÃO:
1. Para adicionar novas tabelas:
   • Atualize o dicionário TABELAS_DISPONIVEIS
   • Implemente lógica de schema específica

2. Para ajustar o modelo de IA:
   • Altere HF_API_URL para outro modelo
   • Ajuste os parâmetros max_new_tokens e temperature

3. Para modificar a formatação:
   • Edite a função formatar_resposta_natural()

LIMITAÇÕES:
- Suporte apenas para comandos SELECT
- Limitação a tabelas pré-mapeadas
- Dependência da API Hugging Face
- Performance varia com complexidade da pergunta

DICAS PARA PERGUNTAS:
1. Seja específico: "Mostre atendentes ativos"
2. Para códigos: "Qual empresa tem código 123?"
3. Para textos: "Mostre empresas com nome contendo 'tec'"
4. Limite resultados: "Mostre 5 empresas"

DEPENDÊNCIAS (requirements.txt):
flask
flask_cors
pyodbc
requests
python-dotenv
