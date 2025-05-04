# Know Your Fan 🎮

**Know Your Fan** é um aplicativo interativo desenvolvido em Python com Streamlit que permite coletar, analisar e validar o perfil de fãs de e-sports usando inteligência artificial. Ele integra dados pessoais, interações em redes sociais e validações de documentos, ajudando organizações a oferecer experiências mais personalizadas para seus torcedores.

---

## 🚀 Funcionalidades

- � Coleta de dados pessoais e comportamentais
- 🖼️ Upload de documentos e extração de texto com OCR
- 🤖 Validação de identidade com IA
- 🌐 Conexão com redes sociais (Twitter, etc.) para análise de interações
- 🔗 Validação de links e perfis com modelos de NLP

---

## 🛠️ Tecnologias utilizadas

- [Python 3.9+](https://www.python.org/)
- [Streamlit](https://streamlit.io/)
- [pytesseract](https://github.com/madmaze/pytesseract)
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract)
- [Transformers (Hugging Face)](https://huggingface.co/)
- [snscrape](https://github.com/JustAnotherArchivist/snscrape)
- [Requests](https://docs.python-requests.org/)

---

## 📦 Instalação

### Pré-requisitos

1. **Instale o Tesseract OCR** (necessário para o pytesseract):

   - **Linux (Ubuntu/Debian)**:
     ```bash
     sudo apt update
     sudo apt install tesseract-ocr
     sudo apt install libtesseract-dev
     ```

   - **MacOS (via Homebrew)**:
     ```bash
     brew install tesseract
     ```

   - **Windows**:
     - Baixe o instalador do [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) e siga as instruções de instalação.
     - Adicione o Tesseract ao seu PATH durante a instalação ou manualmente depois.

2. **Instale as linguagens adicionais (opcional)**:
   - Para suporte a outros idiomas, instale os pacotes correspondentes (ex: `tesseract-ocr-por` para português).


### Configuração do Projeto

1. Clone o repositório:

```bash
git clone https://github.com/hedgebear/know-your-fan.git
cd know-your-fan
```

2. Crie e ative um ambiente virtual (opcional, mas recomendado):

```bash
python -m venv venv
source venv/bin/activate  # ou venv\Scripts\activate no Windows
```
3. Instale as dependências:

```bash
pip install -r requirements.txt
```

4. Execute o aplicativo:

```bash
streamlit run app.py
```

📹 Demonstração
Assista ao vídeo de demonstração do projeto:
🔗 Link para o vídeo (YouTube ou Loom)

✨ Contribuições
Contribuições são bem-vindas! Fique à vontade para abrir issues ou pull requests.

📫 Contato
Desenvolvido por Lucas Fernandes Mosqueira
📧 lucas2002mkx@gmail.com
🔗 linkedin.com/in/lucas-fernandes-mosqueira/