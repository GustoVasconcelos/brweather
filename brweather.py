import json
import urllib.request
import urllib.parse # Ajuda a formatar espaços no nome da cidade para a URL
import os
import time
import argparse
import sys

# Configurações de arquivos
CONFIG_FILE = 'config.json'
CACHE_FILE = 'cache.json'

# Descobre a pasta raiz onde este script está salvo
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

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
    """Traduz as fases da lua e cria os caminhos para as imagens locais."""
    fases_lua = {
        'new': 'Lua Nova', 'waxing_crescent': 'Lua Crescente',
        'first_quarter': 'Quarto Crescente', 'waxing_gibbous': 'Gibosa Crescente',
        'full': 'Lua Cheia', 'waning_gibbous': 'Gibosa Minguante',
        'last_quarter': 'Quarto Minguante', 'waning_crescent': 'Lua Minguante'
    }
    
    moon_slug = resultados.get('moon_phase', '')
    condition_slug = resultados.get('condition_slug', '')
    
    resultados['moon_pt'] = fases_lua.get(moon_slug, moon_slug)
    
    # Caminhos para as imagens locais
    resultados['icon_path'] = os.path.join(BASE_DIR, 'conditions_slugs', f"{condition_slug}.svg")
    resultados['moon_path'] = os.path.join(BASE_DIR, 'moon_phases', f"{moon_slug}.png")
    
    return resultados

def main():
    """Função principal com suporte a imagens e formatação dinâmica."""
    parser = argparse.ArgumentParser(description="BRWeather para Conky", add_help=False)
    parser.add_argument('-h', '--help', action='help', help='Mostra esta mensagem de ajuda e sai do programa')
    parser.add_argument('--format', type=str, required=False, help='Molde do texto. Ex: "{temp}°C em {city}"')
    parser.add_argument('--image-icon', action='store_true', help='Gera a tag da imagem do clima atual')
    parser.add_argument('--image-moon', action='store_true', help='Gera a tag da imagem da lua atual')
    parser.add_argument('-p', type=str, default='', help='Posição da imagem (ex: 10,50)')
    parser.add_argument('-s', type=str, default='', help='Tamanho da imagem (ex: 60x60)')
    
    args = parser.parse_args()

    config = carregar_configuracao()
    dados_completos = buscar_dados_clima(config)
    resultados = dados_completos.get('results', {})
    
    # Processa traduções e caminhos locais
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

    # 3. Texto Formatado
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