import json
import urllib.request
import urllib.parse
import os
import time
import argparse
import sys

# Configurações de arquivos
CONFIG_FILE = 'config.json'
CACHE_FILE = 'cache.json'

# Descobre a pasta raiz onde este script está salvo
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def mostrar_parametros():
    """Imprime na tela o manual de parâmetros disponíveis para o usuário."""
    print("""
======================================================================
             PARÂMETROS DISPONÍVEIS PARA O --format
======================================================================
Utilize estes parâmetros entre chaves. Exemplo: --format "{temp}°C"

☀️ CLIMA ATUAL (GERAL)
  {temp}           - Temperatura atual em ºC
  {date}           - Data da consulta, em fuso horário do local
  {time}           - Hora da consulta, em fuso horário do local
  {description}    - Descrição da condição de tempo atual
  {currently}      - Retorna se está de dia ou de noite
  {city_name}      - Nome da cidade
  {city}           - Nome da cidade seguido por uma vírgula
  {woeid}          - Identificador da cidade
  {timezone}       - Fuso horário da cidade
  {condition_code} - Código da condição de tempo atual
  {condition_slug} - Slug da condição de tempo atual

🌧️ UMIDADE, VENTO E CHUVA
  {humidity}       - Umidade atual em percentual
  {cloudiness}     - Nebulosidade em percentual, de 0 a 100
  {rain}           - Volume de chuva em mm na última hora
  {wind_speedy}    - Velocidade do vento em km/h
  {wind_direction} - Direção do vento em graus
  {wind_cardinal}  - Direção do vento em ponto cardeal

🌙 SOL E LUA
  {sunrise}        - Nascer do Sol em horário local da cidade
  {sunset}         - Pôr do Sol em horário local da cidade
  {moon_phase}     - Fase da Lua (Slug em inglês)
  {moon_pt}        - Fase da Lua traduzida (Ex: Lua Crescente) *CUSTOM
  {next_moon_pt}   - Próxima fase da Lua traduzida             *CUSTOM

📅 PREVISÃO DO TEMPO (Quando usar o argumento -d)
  {date}             - Data da previsão dd/mm
  {weekday}          - Dia da semana abreviado
  {max}              - Temperatura máxima em ºC
  {min}              - Temperatura mínima em ºC
  {description}      - Descrição da previsão
  {condition}        - Slug da condição de tempo
  {humidity}         - Umidade prevista em percentual
  {cloudiness}       - Nebulosidade em percentual
  {rain}             - Volume de chuva esperado
  {rain_probability} - Probabilidade de chuva em percentual
  {wind_speedy}      - Velocidade do vento em km/h
  {sunrise}          - Nascer do Sol
  {sunset}           - Pôr do Sol
  {moon_phase}       - Fase da Lua

📂 IMAGENS LOCAIS (Variáveis geradas pelo script)
  {icon_path}      - Caminho da imagem do clima atual/previsto *CUSTOM
  {moon_path}      - Caminho da imagem da lua atual            *CUSTOM
  {next_moon_path} - Caminho da imagem da próxima lua          *CUSTOM
======================================================================
""")

def carregar_configuracao():
    """Lê o arquivo config.json e retorna os dados."""
    caminho_config = os.path.join(BASE_DIR, CONFIG_FILE)
    try:
        with open(caminho_config, 'r') as arquivo:
            return json.load(arquivo)
    except FileNotFoundError:
        print("Erro: Arquivo config.json não encontrado na pasta do script.")
        sys.exit(1)

def montar_url_api(config):
    """
    Toma a decisão de qual URL usar com base no que foi preenchido no config.json.
    """
    api_key = config.get('api_key', '').strip()
    woeid = str(config.get('woeid', '')).strip()
    city_name = config.get('city_name', '').strip()

    # Cenário 1: O usuário TEM uma chave de API válida
    if api_key and api_key != "SUA_CHAVE_AQUI":
        if city_name:
            # Formata o nome da cidade (ex: "Sao Paulo" vira "Sao%20Paulo")
            cidade_formatada = urllib.parse.quote(city_name)
            return f"https://api.hgbrasil.com/weather?key={api_key}&city_name={cidade_formatada}"
        elif woeid:
            return f"https://api.hgbrasil.com/weather?key={api_key}&woeid={woeid}"
        else:
            print("Erro de Configuração: Forneça um 'city_name' ou 'woeid' no config.json.")
            sys.exit(1)
            
    # Cenário 2: O usuário NÃO TEM chave (Uso Free Limitado)
    else:
        if woeid:
            return f"https://api.hgbrasil.com/weather?woeid={woeid}"
        else:
            print("Erro de Configuração: Para usar sem chave (API Key), você precisa fornecer o 'woeid'. Para buscar pelo nome da cidade, a chave é obrigatória.")
            sys.exit(1)

def buscar_dados_clima(config):
    """Verifica o cache. Se válido, usa ele. Se não, busca na API."""
    tempo_atual = time.time()
    tempo_cache_segundos = config.get('cache_minutes', 60) * 60
    caminho_cache = os.path.join(BASE_DIR, CACHE_FILE)

    # 1. Tenta usar o cache local
    if os.path.exists(caminho_cache):
        tempo_modificacao = os.path.getmtime(caminho_cache)
        if (tempo_atual - tempo_modificacao) < tempo_cache_segundos:
            with open(caminho_cache, 'r') as arquivo:
                return json.load(arquivo)

    # 2. Se o cache expirou, monta a URL inteligente e busca na API
    url = montar_url_api(config)
    
    try:
        resposta = urllib.request.urlopen(url)
        dados_json = json.loads(resposta.read())
        
        # Verifica se a API retornou um erro válido (ex: WOEID não encontrado)
        if 'results' not in dados_json:
            print(f"Erro na resposta da API: {dados_json}")
            sys.exit(1)
            
        # Atualiza o arquivo de cache apenas se deu tudo certo
        with open(caminho_cache, 'w') as arquivo:
            json.dump(dados_json, arquivo)
            
        return dados_json
    except Exception as e:
        print(f"Erro de conexão ao buscar na API: {e}")
        sys.exit(1)

def traduzir_dados(resultados):
    """Traduz as fases da lua, descobre a próxima fase e cria os caminhos locais."""
    fases_lua = {
        'new': 'Lua Nova', 'waxing_crescent': 'Lua Crescente',
        'first_quarter': 'Quarto Crescente', 'waxing_gibbous': 'Gibosa Crescente',
        'full': 'Lua Cheia', 'waning_gibbous': 'Gibosa Minguante',
        'last_quarter': 'Quarto Minguante', 'waning_crescent': 'Lua Minguante'
    }
    
    # 1. Lista com a ordem cronológica exata das fases da lua
    ordem_lua = [
        'new', 'waxing_crescent', 'first_quarter', 'waxing_gibbous',
        'full', 'waning_gibbous', 'last_quarter', 'waning_crescent'
    ]
    
    moon_slug = resultados.get('moon_phase', '')
    condition_slug = resultados.get('condition_slug', '')
    
    resultados['moon_pt'] = fases_lua.get(moon_slug, moon_slug)
    
    # Próxima Fase da Lua (Lista Circular)
    if moon_slug in ordem_lua:
        # Descobre a posição atual (índice)
        indice_atual = ordem_lua.index(moon_slug)
        
        # Soma +1 para a próxima fase. 
        # O operador % (módulo) faz o índice voltar a 0 se passar do tamanho da lista (8)
        indice_proxima = (indice_atual + 1) % len(ordem_lua)
        next_moon_slug = ordem_lua[indice_proxima]
    else:
        # Caso a API retorne algo inesperado
        next_moon_slug = moon_slug
        
    # Traduz a próxima fase
    resultados['next_moon_pt'] = fases_lua.get(next_moon_slug, next_moon_slug)
    
    # Caminhos para as imagens locais
    resultados['icon_path'] = os.path.join(BASE_DIR, 'conditions_slugs', f"{condition_slug}.svg")
    resultados['moon_path'] = os.path.join(BASE_DIR, 'moon_phases', f"{moon_slug}.png")
    # Caminho para a imagem da próxima lua
    resultados['next_moon_path'] = os.path.join(BASE_DIR, 'moon_phases', f"{next_moon_slug}.png")
    
    return resultados

def main():
    """Função principal com suporte a imagens e formatação dinâmica."""
    parser = argparse.ArgumentParser(description="BRWeather para Conky", add_help=False)
    parser.add_argument('-h', '--help', action='help', help='Mostra esta mensagem de ajuda e sai do programa')
    
    # Argumento para exibir a lista de parâmetros
    parser.add_argument('--params', action='store_true', help='Lista todos os parâmetros disponíveis para uso no --format')

    # Argumento para os dias de previsão
    parser.add_argument('-d', '--day', type=int, default=0, help='Dia da previsão (1 = Amanhã, 2 = Depois de amanhã, etc. 0 = Clima Atual)')

    parser.add_argument('--format', type=str, required=False, help='Molde do texto. Ex: "{temp}°C em {city}"')
    parser.add_argument('--image-icon', action='store_true', help='Gera a tag da imagem do clima atual')
    parser.add_argument('--image-moon', action='store_true', help='Gera a tag da imagem da lua atual')
    
    # Argumento para a imagem da PRÓXIMA lua
    parser.add_argument('--image-next-moon', action='store_true', help='Gera a tag da imagem da próxima fase da lua')
    
    parser.add_argument('-p', type=str, default='', help='Posição da imagem (ex: 10,50)')
    parser.add_argument('-s', type=str, default='', help='Tamanho da imagem (ex: 60x60)')
    
    args = parser.parse_args()

    # Se o usuário pedir o manual, mostramos e saímos do script ANTES de conectar na API
    if args.params:
        mostrar_parametros()
        sys.exit(0)

    config = carregar_configuracao()
    dados_completos = buscar_dados_clima(config)
    resultados = dados_completos.get('results', {})
    
    # Previsão do tempo
    dia_escolhido = args.day
    if dia_escolhido > 0:
        previsoes = resultados.get('forecast', [])
        # O Dia 1 (amanhã) é a posição 0 na lista do Python
        indice = dia_escolhido - 1 
        
        # Verifica se o usuário pediu um dia além do que o plano dele permite
        if indice >= len(previsoes):
            print(f"Erro: O dia {dia_escolhido} não está disponível. Sua CHAVE da API retornou apenas {len(previsoes)} dias de previsão.")
            sys.exit(1)
            
        # Pega os dados específicos daquele dia
        dados_do_dia = previsoes[indice]
        
        # Padroniza a chave da condição do tempo para o nosso tradutor funcionar
        dados_do_dia['condition_slug'] = dados_do_dia.get('condition', '')
        
        # Substitui os 'resultados' gerais pelos dados deste dia específico
        resultados = dados_do_dia

    # Processa traduções, caminhos locais e próxima lua
    resultados = traduzir_dados(resultados)

    # 1. Imagem do Clima
    if args.image_icon:
        pos_str = f" -p {args.p}" if args.p else ""
        size_str = f" -s {args.s}" if args.s else ""
        print(f"${{image {resultados['icon_path']}{pos_str}{size_str}}}")
        return

    # 2. Imagem da Lua
    if args.image_moon:
        pos_str = f" -p {args.p}" if args.p else ""
        size_str = f" -s {args.s}" if args.s else ""
        print(f"${{image {resultados['moon_path']}{pos_str}{size_str}}}")
        return
        
    # 3. Imagem da PRÓXIMA Lua
    if args.image_next_moon:
        pos_str = f" -p {args.p}" if args.p else ""
        size_str = f" -s {args.s}" if args.s else ""
        print(f"${{image {resultados['next_moon_path']}{pos_str}{size_str}}}")
        return

    # 4. Texto Formatado
    if args.format:
        try:
            texto_final = args.format.format(**resultados)
            print(texto_final)
        except KeyError as erro:
            print(f"Erro: A informação {erro} não existe nos dados da API.")
        return

    # Se rodou sem argumentos
    parser.print_help()

if __name__ == "__main__":
    main()