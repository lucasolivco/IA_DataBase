from flask import Flask, request, jsonify
import pyodbc
from datetime import datetime, timedelta
import threading
from flask_cors import CORS
import requests
import os
import dotenv

# Configurações
app = Flask(__name__)
CORS(app)
dotenv.load_dotenv()  # Carrega variáveis de ambiente do arquivo .env

# Constantes
HF_API_URL = "https://api-inference.huggingface.co/models/microsoft/phi-3-mini-4k-instruct"
HF_TOKEN = os.getenv("HF_TOKEN", "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")  # Usa variável de ambiente ou fallback
headers = {"Authorization": f"Bearer {HF_TOKEN}"}

# Cache de schema
schema_cache = {}
schema_last_updated = {}
cache_lock = threading.Lock()

TABELAS_DISPONIVEIS = {
    "atendentes": {
        "nome": "Atendentes",
        "descricao": "Dados dos colaboradores do setor de atendimento"
    },
    "empresas": {
        "nome": "empresas",
        "descricao": "Registros fiscais e tributários"
    }
}

def get_db_connection():
    """Estabelece conexão com o banco de dados"""
    try:
        return pyodbc.connect(
            f"DRIVER={os.getenv('DB_DRIVER')};"
            f"SERVER={os.getenv('DB_SERVER')};"
            f"DATABASE={os.getenv('DB_NAME')};"
            f"UID={os.getenv('DB_USER')};"
            f"PWD={os.getenv('DB_PASSWORD')};"
        )
    except pyodbc.Error as e:
        raise ConnectionError(f"Falha ao conectar ao banco de dados: {str(e)}")

def get_schema(tabela='atendentes'):
    """Obtém schema com cache"""
    with cache_lock:
        if (tabela not in schema_cache or 
            (datetime.now() - schema_last_updated.get(tabela, datetime.min)) > timedelta(hours=1)):
            conn = None
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
                    FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_NAME = ?
                    ORDER BY ORDINAL_POSITION
                """, tabela)
                schema_cache[tabela] = [
                    {"nome": nome, "tipo": tipo, "nullable": (nullable == 'YES')}
                    for nome, tipo, nullable in cursor.fetchall()
                ]
                schema_last_updated[tabela] = datetime.now()
            except Exception as e:
                raise ValueError(f"Erro ao obter schema: {str(e)}")
            finally:
                if conn:
                    conn.close()
        return {tabela: schema_cache[tabela]}

def query_huggingface(prompt, tabela='atendentes'):
    """Consulta o modelo de IA para gerar apenas o SQL, sem repetir a pergunta."""
    try:
        schema = get_schema(tabela)
        colunas_str = "\n".join([f"- {col['nome']} ({col['tipo']})" for col in schema[tabela]])
        
        # Novo prompt: instrui a retornar SOMENTE o código SQL válido, sem incluir a pergunta
        prompt_otimizado = f"""<|system|>
Você é um especialista em SQL Server. Ao receber uma pergunta, retorne SOMENTE uma consulta SQL válida que responda à pergunta.
Não inclua nenhum texto ou repetição da pergunta.
Sempre use "LIKE" no lugar de "=" se o usuário pedir colunas com valores de string (texto).
<|end|>
<|user|>
Pergunta: {prompt}
Tabela: {tabela}
Colunas disponíveis:
{colunas_str}
<|end|>
<|assistant|>
"""
        
        response = requests.post(
            HF_API_URL,
            headers=headers,
            json={
                "inputs": prompt_otimizado,
                "parameters": {
                    "max_new_tokens": 100,
                    "temperature": 0.1
                }
            },
            timeout=30
        )
        
        if response.status_code != 200:
            raise ConnectionError(f"Erro na API (HTTP {response.status_code}): {response.text}")
        
        resposta = response.json()
        if not isinstance(resposta, list):
            raise ValueError("Resposta inesperada da API")
        
        # Processa a resposta: assume que o texto gerado é apenas o SQL
        sql = resposta[0]['generated_text'].strip()
        # Se houver linhas em branco ou mensagens extras, pega somente a primeira linha que comece com SELECT ou WITH
        for linha in sql.splitlines():
            linha = linha.strip()
            if linha.lower().startswith(('select', 'with')):
                sql = linha
                break
        
        if not sql.lower().startswith(('select', 'with')):
            raise ValueError(f"Resposta não é um SQL válido: {sql}")
            
        return sql
        
    except Exception as e:
        raise RuntimeError(f"Erro ao consultar IA: {str(e)}")

def validar_sql(sql, tabela='atendentes'):
    """Valida a consulta SQL gerada"""
    if not isinstance(sql, str) or not sql.strip():
        raise ValueError("Consulta SQL inválida")
    
    sql_lower = sql.lower()
    
    # Verifica erros
    if any(erro in sql_lower for erro in ["erro", "exception", "error"]):
        raise ValueError(sql)
    
    palavras_proibidas = ["insert", "update", "delete", "drop", "alter", "truncate", "create", "exec"]
    if any(palavra in sql_lower for palavra in palavras_proibidas):
        raise ValueError("Comandos não permitidos detectados")
    
    if (f"from {tabela.lower()}" not in sql_lower and 
        f"join {tabela.lower()}" not in sql_lower and 
        not sql_lower.startswith(('with'))):
        raise ValueError(f"A consulta deve referenciar a tabela {tabela}")
    
    if not sql_lower.lstrip().startswith(('select', 'with')):
        raise ValueError("Apenas consultas SELECT são permitidas")

def executar_sql(sql):
    """Executa a consulta SQL no banco de dados"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(sql)
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    except pyodbc.Error as e:
        raise RuntimeError(f"Erro ao executar SQL: {str(e)}")
    finally:
        if conn:
            conn.close()

def formatar_resposta_natural(pergunta, dados, sql):
    """Formata os resultados em forma de lista, exibindo cada registro como:
    
    nome_da_coluna: "valor"
    """
    if not dados:
        return "Nenhum resultado encontrado."
    
    linhas_formatadas = []
    total = len(dados)
    linhas_formatadas.append(f"Total de registros: {total}")
    linhas_formatadas.append("")
    
    for i, row in enumerate(dados, start=1):
        linhas_formatadas.append(f"Registro {i}:")
        for chave, valor in row.items():
            linhas_formatadas.append(f'{chave}: "{valor}"')
        linhas_formatadas.append("")  # Linha em branco entre registros

    resultado = f"SQL executado:\n{sql}\n\n" + "\n".join(linhas_formatadas)
    return resultado

@app.route('/perguntar', methods=['POST'])
def perguntar():
    try:
        data = request.json
        pergunta = data.get('pergunta', '').strip()
        tabela = data.get('tabela', 'atendentes')
        
        if not pergunta:
            return jsonify({"erro": "Por favor, digite uma pergunta"}), 400
        
        # 1. Gera SQL
        sql = query_huggingface(pergunta, tabela)
        print(f"SQL Gerado: {sql}")
        
        # 2. Valida
        validar_sql(sql, tabela)
        
        # 3. Executa
        dados = executar_sql(sql)
        
        # 4. Formata resposta natural em forma de lista
        resposta = formatar_resposta_natural(pergunta, dados, sql)
        
        return jsonify({
            "pergunta": pergunta,
            "resposta": resposta,
            "sql": sql,
            "total_resultados": len(dados),
            "dados": dados[:100]
        })
        
    except Exception as e:
        return jsonify({
            "erro": str(e),
            "dica": f"Exemplos válidos: 'Quantos registros em {tabela}?', 'Liste 5 itens de {tabela}'"
        }), 500

@app.route('/teste', methods=['GET'])
def teste_conexao():
    """Endpoint para testar conexão com o banco"""
    try:
        schema_atendentes = get_schema('atendentes')
        schema_fiscal = get_schema('empresas')
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT TOP 1 * FROM atendentes")
            exemplo_atendentes = cursor.fetchone()
            cursor.execute("SELECT TOP 1 * FROM empresas")
            exemplo_fiscal = cursor.fetchone()
            return jsonify({
                "status": "Conexão OK",
                "schemas": {
                    "atendentes": schema_atendentes['atendentes'],
                    "empresas": schema_fiscal['empresas']
                }
            })
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route('/schema/<tabela>', methods=['GET'])
def obter_schema(tabela):
    """Endpoint para obter schema de uma tabela"""
    try:
        schema = get_schema(tabela)
        return jsonify({
            "tabela": tabela,
            "colunas": schema[tabela],
            "total_colunas": len(schema[tabela])
        })
    except Exception as e:
        return jsonify({"erro": str(e)}), 404
    
@app.route('/tabelas', methods=['GET'])
def listar_tabelas():
    """Lista todas as tabelas disponíveis para consulta"""
    try:
        return jsonify({
            "tabelas": TABELAS_DISPONIVEIS,
            "suporte": "Utilize o nome da tabela no parâmetro 'tabela' nas requisições POST"
        })
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
