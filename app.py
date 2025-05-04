import streamlit as st
from PIL import Image
import pytesseract
import tweepy
from transformers import pipeline
import re
import os
from dotenv import load_dotenv
from email_validator import validate_email, EmailNotValidError
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import time
from collections import defaultdict
import hashlib
import tempfile
import json

# Configurações iniciais
load_dotenv()

# Configuração do Tesseract OCR
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Configurações
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
MAX_TWEETS = 5
MAX_FOLLOWING = 100
ORGANIZACOES_ESPORTS = ["furia", "loud", "mibr", "g2esports", "fnatic", "navi", "teamliquid"]
JOGOS_ESPORTS = ["lol", "league of legends", "csgo", "valorant", "dota", "fortnite", "rainbow six"]

# Inicializa session_state se não existir
if 'user_data' not in st.session_state:
    st.session_state.user_data = {}

# Twitter API setup - modificado para ser opcional
def get_twitter_client():
    try:
        return tweepy.Client(
            bearer_token=os.getenv('TWITTER_BEARER_TOKEN'),
            consumer_key=os.getenv('TWITTER_API_KEY'),
            consumer_secret=os.getenv('TWITTER_API_SECRET'),
            access_token=os.getenv('TWITTER_ACCESS_TOKEN'),
            access_token_secret=os.getenv('TWITTER_ACCESS_TOKEN_SECRET')
        )
    except Exception as e:
        st.warning(f"Twitter API não configurada corretamente: {str(e)}")
        return None

twitter_client = get_twitter_client()

# Cache para melhorar performance
@st.cache_data(ttl=3600)
def analyze_twitter_profile(username):
    """Analisa o perfil do Twitter e retorna dados estruturados"""
    if not twitter_client:
        st.warning("Twitter API não está configurada corretamente")
        return None
        
    try:
        user = twitter_client.get_user(username=username, user_fields=["public_metrics", "description", "profile_image_url"])
        user_id = user.data.id
        
        # Busca tweets recentes
        tweets = twitter_client.get_users_tweets(
            id=user_id, 
            max_results=MAX_TWEETS, 
            tweet_fields=["created_at", "public_metrics", "entities"]
        )
        
        # Busca contas seguidas
        following = twitter_client.get_users_following(
            id=user_id, 
            max_results=MAX_FOLLOWING, 
            user_fields=["name", "username", "description"]
        )
        
        return {
            "user": user.data,
            "tweets": tweets.data if tweets.data else [],
            "following": following.data if following.data else []
        }
    except tweepy.errors.TweepyException as e:
        st.error(f"Erro ao buscar dados do Twitter: {str(e)}")
        return None

def validate_cpf(cpf: str) -> bool:
    """Valida um CPF brasileiro"""
    cpf = ''.join(filter(str.isdigit, cpf))
    
    if len(cpf) != 11:
        return False
    
    # Verifica dígitos repetidos
    if cpf == cpf[0] * 11:
        return False
    
    # Calcula o primeiro dígito verificador
    soma = 0
    for i in range(9):
        soma += int(cpf[i]) * (10 - i)
    resto = 11 - (soma % 11)
    digito1 = resto if resto < 10 else 0
    
    # Calcula o segundo dígito verificador
    soma = 0
    for i in range(10):
        soma += int(cpf[i]) * (11 - i)
    resto = 11 - (soma % 11)
    digito2 = resto if resto < 10 else 0
    
    return cpf[-2:] == f"{digito1}{digito2}"

def validate_email_address(email: str) -> bool:
    """Valida um endereço de email"""
    try:
        v = validate_email(email)
        return True
    except EmailNotValidError:
        return False

def process_document(uploaded_file):
    """Processa documento de identidade usando OCR"""
    try:
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_file_path = tmp_file.name
        
        # Para PDFs precisaríamos de conversão para imagem
        if uploaded_file.type == "application/pdf":
            st.warning("Suporte a PDF requer bibliotecas adicionais como pdf2image")
            return None
        
        image = Image.open(tmp_file_path)
        texto = pytesseract.image_to_string(image, lang='por')
        
        # Padroniza CPF no texto extraído
        cpfs = re.findall(r'\d{3}\.?\d{3}\.?\d{3}-?\d{2}', texto)
        if cpfs:
            texto += f"\n\nCPF encontrado: {cpfs[0]}"
        
        os.unlink(tmp_file_path)
        return texto
    except Exception as e:
        st.error(f"Erro ao processar documento: {str(e)}")
        return None

def analyze_links(links_list, user_interests=None):
    """Analisa uma lista de links validando relevância para o perfil do usuário"""
    if user_interests is None:
        user_interests = []
    
    resultados = []
    
    # Configuração do navegador
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # Pipeline de classificação
    @st.cache_resource
    def get_validator():
        return pipeline("zero-shot-classification", model="facebook/bart-large-mnli")
    
    validador = get_validator()
    
    with webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options) as driver:
        for link in links_list:
            try:
                driver.get(link)
                time.sleep(2)  # Espera carregar
                html = driver.page_source
                
                soup = BeautifulSoup(html, 'html.parser')
                texto = soup.get_text()[:2000].lower()
                
                # Classificação principal
                candidate_labels = [
                    "e-sports organization", 
                    "competitive gaming", 
                    "personal profile", 
                    "gaming news", 
                    "streaming channel",
                    "game developer",
                    "fan community",
                    "esports tournament"
                ]
                
                resultado = validador(texto, candidate_labels)
                primary_category = resultado["labels"][0]
                confidence = resultado["scores"][0]
                
                # Verificação de relevância
                relevant_terms = []
                relevance_score = 0
                
                # 1. Termos de e-sports genéricos
                for term in JOGOS_ESPORTS + ORGANIZACOES_ESPORTS:
                    if term in texto:
                        relevant_terms.append(term)
                        relevance_score += 1
                
                # 2. Interesses específicos do usuário
                user_terms_found = []
                for interest in user_interests:
                    if isinstance(interest, str) and interest.lower() in texto:
                        user_terms_found.append(interest)
                        relevance_score += 2  # Peso maior para interesses do usuário
                
                # 3. Verificação de perfil pessoal (se for rede social)
                is_personal_profile = False
                social_platforms = ["twitter.com", "instagram.com", "twitch.tv", "youtube.com"]
                if any(plat in link for plat in social_platforms):
                    profile_indicators = ["profile", "perfil", "user", "sobre", "about", "bio"]
                    if any(ind in texto for ind in profile_indicators):
                        is_personal_profile = True
                
                # Determinar relevância geral
                if relevance_score >= 3:
                    relevance = "Alta"
                elif relevance_score >= 1:
                    relevance = "Média"
                else:
                    relevance = "Baixa"
                
                # Se for perfil pessoal mas não tem termos relevantes, considerar baixa relevância
                if is_personal_profile and relevance_score == 0:
                    relevance = "Baixa"
                
                resultados.append({
                    "Link": link,
                    "Categoria": primary_category,
                    "Confiança": f"{confidence*100:.1f}%",
                    "Relevância": relevance,
                    "Termos Encontrados": ", ".join(relevant_terms),
                    "Interesses do Usuário": ", ".join(user_terms_found),
                    "Pontuação": relevance_score
                })
                
            except Exception as e:
                resultados.append({
                    "Link": link,
                    "Categoria": "Erro",
                    "Confiança": "N/A",
                    "Relevância": "N/A",
                    "Termos Encontrados": f"Erro: {str(e)}",
                    "Interesses do Usuário": "N/A",
                    "Pontuação": 0
                })
    
    return resultados

def generate_fan_profile(data):
    """Gera um perfil completo do fã baseado nos dados coletados"""
    profile = {
        "basic_info": {
            "name": data.get("Nome", ""),
            "twitter": data.get("Twitter_Usuario", ""),
            "email": data.get("Email", "")
        },
        "metrics": defaultdict(int),
        "interests": [],
        "recommendations": [],
        "badges": []
    }
    
    # Interesses do formulário
    if "Interesses" in data:
        interests = [i.strip() for i in data["Interesses"].split(",")]
        profile["interests"] = interests
        profile["metrics"]["interests_count"] = len(interests)
    
    # Eventos participados
    if "Eventos_Participados" in data and data["Eventos_Participados"]:
        profile["metrics"]["events_attended"] = len(data["Eventos_Participados"].split(","))
    
    # Compras realizadas
    if "Compras_Realizadas" in data and data["Compras_Realizadas"]:
        profile["metrics"]["purchases"] = len(data["Compras_Realizadas"].split(","))
    
    # Análise de tweets (se disponível)
    if "twitter_data" in data and data["twitter_data"]:
        tweets_esports = [
            t for t in data["twitter_data"].get("tweets", [])
            if any(org in t.text.lower() for org in ORGANIZACOES_ESPORTS) or 
               any(game in t.text.lower() for game in JOGOS_ESPORTS)
        ]
        
        profile["metrics"]["tweets_esports"] = len(tweets_esports)
        profile["metrics"]["engagement"] = sum(
            t.public_metrics["like_count"] + t.public_metrics["retweet_count"] 
            for t in tweets_esports
        )
    
    # Análise de contas seguidas (se disponível)
    if "twitter_data" in data and data["twitter_data"] and data["twitter_data"].get("following"):
        orgs_seguidas = [
            user for user in data["twitter_data"]["following"]
            if user.description and any(org in user.description.lower() for org in ORGANIZACOES_ESPORTS)
        ]
        profile["metrics"]["orgs_followed"] = len(orgs_seguidas)
    
    # Gerar recomendações baseadas em dados disponíveis
    if profile["metrics"].get("orgs_followed", 0) > 3:
        profile["recommendations"].append("Você é um fã dedicado! Considere participar de programas de fã-clube oficial.")
    elif profile["interests"]:
        profile["recommendations"].append(f"Baseado em seus interesses em {', '.join(profile['interests'][:3])}, siga as organizações oficiais para ficar por dentro!")
    
    if profile["metrics"].get("tweets_esports", 0) > 10:
        profile["recommendations"].append("Seu alto engajamento merece recompensas! Procure por programas de embaixadores.")
    
    if profile["metrics"].get("events_attended", 0) > 0:
        profile["recommendations"].append("Participar de eventos mostra seu engajamento! Continue assim!")
    
    # Badges baseadas em vários critérios
    if profile["metrics"].get("interests_count", 0) >= 3:
        profile["badges"].append("Fã Conhecedor")
    
    if profile["metrics"].get("purchases", 0) > 0:
        profile["badges"].append("Apoiador")
    
    if profile["metrics"].get("events_attended", 0) > 0:
        profile["badges"].append("Fã Presente")
    
    return profile

# Interface Streamlit
st.set_page_config(page_title="Know Your Fan", page_icon="🎮", layout="wide")

# Título do app
st.title("Know Your Fan 🎮")
st.subheader("Perfil de fã de e-sports")

# Coleta de dados pessoais
with st.form("formulario_fas"):
    st.header("📝 Dados Pessoais")
    
    col1, col2 = st.columns(2)
    nome = col1.text_input("Nome completo*", 
                          value=st.session_state.user_data.get("Nome", ""), 
                          key="nome_input")
    cpf = col2.text_input("CPF*", 
                         value=st.session_state.user_data.get("CPF", ""), 
                         key="cpf_input", 
                         help="Digite apenas números")
    
    email = st.text_input("Email*", 
                         value=st.session_state.user_data.get("Email", ""), 
                         key="email_input")
    endereco = st.text_input("Endereço", 
                           value=st.session_state.user_data.get("Endereco", ""), 
                           key="endereco_input")
    
    st.subheader("Interesses em E-Sports")
    interesses_salvos = st.session_state.user_data.get("Interesses", "").split(", ") if st.session_state.user_data.get("Interesses") else []
    interesses = st.multiselect("Quais equipes ou jogos você mais acompanha?", 
                              options=ORGANIZACOES_ESPORTS + JOGOS_ESPORTS,
                              default=interesses_salvos,
                              key="interesses_input")
    
    st.subheader("Atividades Recentes")
    eventos = st.text_area("Eventos de e-sports que participou no último ano",
                          value=st.session_state.user_data.get("Eventos_Participados", ""),
                          key="eventos_input")
    compras = st.text_area("Produtos relacionados a e-sports que comprou no último ano",
                          value=st.session_state.user_data.get("Compras_Realizadas", ""),
                          key="compras_input")
    username = st.text_input("Digite seu usuário do Twitter (sem @)", 
                           value=st.session_state.user_data.get("Twitter_Usuario", ""),
                           key="twitter_input")
    
    enviado = st.form_submit_button("Salvar Meus Dados")
    
    if enviado:
        if not nome or not cpf or not email:
            st.error("Por favor, preencha os campos obrigatórios (*)")
        elif not validate_cpf(cpf):
            st.error("CPF inválido. Por favor, verifique o número.")
        elif not validate_email_address(email):
            st.error("Email inválido. Por favor, verifique o endereço.")
        else:
            st.session_state.user_data.update({
                "Data_Registro": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Nome": nome,
                "CPF": cpf,
                "Email": email,
                "Endereco": endereco,
                "Interesses": ", ".join(interesses),
                "Eventos_Participados": eventos,
                "Compras_Realizadas": compras,
                "Twitter_Usuario": username
            })
            
            # Salva em JSON (opcional)
            with open("user_data.json", "w") as f:
                json.dump(st.session_state.user_data, f)
            
            st.success("Dados salvos com sucesso!")
            st.write("Dados salvos:", st.session_state.user_data)  # Para debug

# Validação de Identidade
with st.expander("🆔 Validação de Identidade", expanded=False):
    uploaded_file = st.file_uploader("Documento de identidade (RG, CNH, Passaporte)", 
                                   type=["png", "jpg", "jpeg"])
    
    if uploaded_file and uploaded_file.size > 0:
        if uploaded_file.size > MAX_FILE_SIZE:
            st.error(f"Arquivo muito grande. Tamanho máximo permitido: {MAX_FILE_SIZE/1024/1024}MB")
        else:
            with st.spinner("Processando documento..."):
                texto_extraido = process_document(uploaded_file)
                if texto_extraido:
                    st.text_area("Texto extraído (OCR)", texto_extraido, height=200)
                    
                    # Verifica correspondência de CPF
                    if 'CPF' in st.session_state.user_data:
                        cpfs_doc = re.findall(r'\d{3}\.?\d{3}\.?\d{3}-?\d{2}', texto_extraido)
                        if cpfs_doc and st.session_state.user_data['CPF'] in ''.join(filter(str.isdigit, cpfs_doc[0])):
                            st.success("CPF do documento corresponde ao informado!")
                        else:
                            st.warning("CPF não encontrado ou não corresponde ao informado")

# Análise de Redes Sociais
st.header("📱 Análise de Redes Sociais")

tab_twitter, tab_other = st.tabs(["Twitter", "Outras Plataformas"])

with tab_twitter:
    if st.session_state.user_data.get("Twitter_Usuario"):
        if st.button("Analisar Perfil do Twitter"):
            with st.spinner("Coletando dados do Twitter..."):
                twitter_data = analyze_twitter_profile(st.session_state.user_data["Twitter_Usuario"])
                
                if twitter_data:
                    st.session_state.user_data["twitter_data"] = twitter_data
                    
                    # Mostra métricas básicas
                    metrics = twitter_data["user"].public_metrics
                    st.subheader("📊 Métricas do Perfil")
                    
                    cols = st.columns(4)
                    cols[0].metric("Seguidores", metrics["followers_count"])
                    cols[1].metric("Seguindo", metrics["following_count"])
                    cols[2].metric("Tweets", metrics["tweet_count"])
                    cols[3].metric("Listas", metrics["listed_count"])
                    
                    # Análise de tweets
                    st.subheader("🎮 Tweets sobre E-Sports")
                    if twitter_data["tweets"]:
                        tweets_esports = []
                        for tweet in twitter_data["tweets"]:
                            if any(org in tweet.text.lower() for org in ORGANIZACOES_ESPORTS) or \
                               any(game in tweet.text.lower() for game in JOGOS_ESPORTS):
                                engagement = tweet.public_metrics["like_count"] + tweet.public_metrics["retweet_count"]
                                tweets_esports.append({
                                    "Tweet": tweet.text[:100] + "..." if len(tweet.text) > 100 else tweet.text,
                                    "Data": tweet.created_at.strftime("%Y-%m-%d"),
                                    "Engajamento": engagement
                                })
                        
                        if tweets_esports:
                            df = pd.DataFrame(tweets_esports).sort_values("Engajamento", ascending=False)
                            st.dataframe(df, use_container_width=True)
                            
                            engajamento_total = df["Engajamento"].sum()
                            st.metric("Total de Engajamento em E-Sports", engajamento_total)
                        else:
                            st.info("Nenhum tweet sobre e-sports encontrado nos últimos tweets.")
                    
                    # Análise de contas seguidas
                    st.subheader("🏆 Organizações Seguidas")
                    if twitter_data["following"]:
                        orgs_seguidas = []
                        for user in twitter_data["following"]:
                            desc = user.description.lower() if user.description else ""
                            if any(org in desc or org in user.username.lower() for org in ORGANIZACOES_ESPORTS):
                                orgs_seguidas.append({
                                    "Organização": user.name,
                                    "Username": f"@{user.username}",
                                    "Seguidores": user.public_metrics["followers_count"] if hasattr(user, 'public_metrics') else "N/A"
                                })
                        
                        if orgs_seguidas:
                            df_orgs = pd.DataFrame(orgs_seguidas)
                            st.dataframe(df_orgs, use_container_width=True)
                            
                            top_org = df_orgs.sort_values("Seguidores", ascending=False).iloc[0]
                            st.success(f"Você segue {len(orgs_seguidas)} organizações de e-sports! A maior é {top_org['Organização']} com {top_org['Seguidores']} seguidores.")
                        else:
                            st.info("Nenhuma organização de e-sports encontrada entre as contas seguidas.")
    else:
        st.warning("Por favor, insira um nome de usuário do Twitter e salve os dados primeiro")

with tab_other:
    plataforma = st.selectbox("Selecione a plataforma", ["Twitch", "YouTube", "Instagram", "Steam"])
    username_outro = st.text_input(f"Digite seu usuário no {plataforma}")
    
    if st.button(f"Validar {plataforma}"):
        if not username_outro:
            st.warning("Por favor, insira um nome de usuário")
        else:
            # Simulação de análise para outras plataformas
            with st.spinner(f"Analisando perfil na {plataforma}..."):
                time.sleep(2)  # Simula processamento
                
                # Dados mockados para demonstração
                mock_data = {
                    "Twitch": {"seguidores": "1.2K", "canais_favoritos": 5, "horas_assistidas": "45h"},
                    "YouTube": {"inscritos": "3.4K", "vídeos_assistidos": 120, "canais_inscritos": 28},
                    "Instagram": {"seguidores": "2.1K", "seguindo": 350, "posts_esports": 12},
                    "Steam": {"jogos": 45, "horas_jogadas": "560h", "amigos": 23}
                }
                
                st.success(f"Perfil na {plataforma} encontrado!")
                st.json(mock_data[plataforma])

# Validação de Links
with st.expander("🔗 Validação de Links de E-Sports", expanded=False):
    links = st.text_area("Cole links de perfis ou páginas relacionados a e-sports (um por linha)", height=100)
    
    if st.button("Validar Links"):
        if not links:
            st.warning("Por favor, insira pelo menos um link")
        else:
            links_list = [link.strip() for link in links.split('\n') if link.strip()]
            
            # Obtém interesses do usuário se existirem
            user_interests = []
            if 'Interesses' in st.session_state.user_data:
                user_interests = [i.strip().lower() for i in st.session_state.user_data['Interesses'].split(",")]
            
            with st.spinner("Analisando links..."):
                resultados = analyze_links(links_list, user_interests)
                
                st.subheader("📋 Resultados da Validação")
                
                # Ordena por relevância e pontuação
                df_resultados = pd.DataFrame(resultados).sort_values(
                    ["Relevância", "Pontuação"], 
                    ascending=[False, False]
                )
                
                # Formatação condicional
                def color_relevance(val):
                    if val == "Alta":
                        return 'background-color: #4CAF50; color: white'
                    elif val == "Média":
                        return 'background-color: #FFC107; color: black'
                    elif val == "Baixa":
                        return 'background-color: #F44336; color: white'
                    else:
                        return ''
                
                styled_df = df_resultados.style.applymap(color_relevance, subset=['Relevância'])
                st.dataframe(styled_df, use_container_width=True, hide_index=True)
                
                # Estatísticas
                high_relevance = sum(1 for r in resultados if r["Relevância"] == "Alta")
                medium_relevance = sum(1 for r in resultados if r["Relevância"] == "Média")
                
                col1, col2 = st.columns(2)
                col1.metric("Links Altamente Relevantes", high_relevance)
                col2.metric("Links Medianamente Relevantes", medium_relevance)
                
                # Mostra recomendações baseadas nos melhores links
                if high_relevance > 0:
                    best_links = [r for r in resultados if r["Relevância"] == "Alta"]
                    st.success("🔍 Recomendações baseadas nos links mais relevantes:")
                    
                    for link in best_links[:3]:  # Mostra até 3 recomendações
                        terms = link["Termos Encontrados"] + (" | " + link["Interesses do Usuário"] if link["Interesses do Usuário"] else "")
                        st.write(f"- [{link['Link']}]({link['Link']}) - {terms}")

# Perfil Completo
if st.button("Gerar Perfil Completo", type="primary"):
    if not st.session_state.get('user_data') or not st.session_state.user_data.get("Nome"):
        st.error("Por favor, preencha seus dados pessoais e clique em 'Salvar Meus Dados' primeiro")
    else:
        with st.spinner("Gerando seu perfil de fã..."):
            profile = generate_fan_profile(st.session_state.user_data)
            
            st.header(f"🎮 Perfil de Fã: {profile['basic_info']['name']}")
            
            # Seção de métricas
            st.subheader("📊 Suas Métricas")
            cols = st.columns(4)
            cols[0].metric("Interesses", profile['metrics'].get('interests_count', 0))
            cols[1].metric("Eventos Participados", profile['metrics'].get('events_attended', 0))
            cols[2].metric("Compras Realizadas", profile['metrics'].get('purchases', 0))
            
            # Adiciona métricas do Twitter se disponíveis
            twitter_metrics = []
            if 'tweets_esports' in profile['metrics']:
                twitter_metrics.append(f"Tweets sobre E-Sports: {profile['metrics']['tweets_esports']}")
            if 'engagement' in profile['metrics']:
                twitter_metrics.append(f"Engajamento: {profile['metrics']['engagement']}")
            if 'orgs_followed' in profile['metrics']:
                twitter_metrics.append(f"Organizações Seguidas: {profile['metrics']['orgs_followed']}")
            
            if twitter_metrics:
                cols[3].metric("Twitter", "\n".join(twitter_metrics))
            else:
                cols[3].metric("Twitter", "Não vinculado")
            
            # Seção de interesses
            st.subheader("❤️ Seus Interesses")
            if profile['interests']:
                st.write(", ".join(profile['interests']))
            else:
                st.warning("Nenhum interesse registrado")
            
            # Seção de recomendações
            st.subheader("✨ Recomendações Personalizadas")
            if profile['recommendations']:
                for rec in profile['recommendations']:
                    st.success(rec)
            else:
                st.info("Complete mais informações para receber recomendações personalizadas")
            
            # Badges
            st.subheader("🏅 Conquistas")
            if profile['badges']:
                cols = st.columns(len(profile['badges']))
                for i, badge in enumerate(profile['badges']):
                    cols[i].image(f"https://via.placeholder.com/100/4CAF50/FFFFFF?text={badge.replace(' ', '+')}", 
                                caption=badge, width=100)
            else:
                st.info("Complete mais informações para desbloquear conquistas")