import json
import requests
import pandas as pd
import os
import logging
import time
import base64
import re
from weasyprint import HTML

##############################################################################
# CONFIGURAÇÕES ULTRAMSG
##############################################################################

STATE_FILE = 'conversation_states.json'

ULTRAMSG_INSTANCE_ID = "instance99723"  # Substitua pelo seu ID da instância UltraMsg
ULTRAMSG_TOKEN = "2str21gem9r5za4u"    # Substitua pelo seu token UltraMsg

# Exemplo de dicionário de taxas do Cartão (1 a 18 parcelas)
CREDIT_RATES = {
    1: 0.0310,
    2: 0.0549,
    3: 0.0680,
    4: 0.0749,
    5: 0.0818,
    6: 0.0885,
    7: 0.0952,
    8: 0.1097,
    9: 0.1163,
    10: 0.1228,
    11: 0.1293,
    12: 0.1356,
    13: 0.1420,
    14: 0.1482,
    15: 0.1544,
    16: 0.1606,
    17: 0.1667,
    18: 0.1727
}

##############################################################################
# FUNÇÕES DE APOIO (ENVIO E MANIPULAÇÃO)
##############################################################################

def format_number(chatID: str) -> str:
    """Remove prefixos como 'whatsapp:+' e '@c.us' para ficar só o número."""
    number = chatID
    if number.startswith("whatsapp:+"):
        number = number.replace("whatsapp:+", "")
    number = number.replace("@c.us", "")
    return number

def send_message_ultramsg(chatID: str, text: str):
    # Supondo que chatID seja só numero ex.: "5511999999999"
    to_number = f"{chatID}@c.us"  # ou se preferir "whatsapp:+{chatID}@c.us"
    url = f"https://api.ultramsg.com/{ULTRAMSG_INSTANCE_ID}/messages/chat"
    data = {
        "to": to_number,
        "body": text,
        "token": ULTRAMSG_TOKEN
    }

    try:
        response = requests.post(url, data=data)
        logging.info(f"Mensagem enviada para {to_number}: '{text}'")
        logging.info(f"Resposta UltraMsg: {response.status_code}, {response.text}")
        return response
    except Exception as e:
        logging.error(f"Erro ao enviar mensagem via UltraMsg: {e}")
        return None

def send_document_ultramsg_base64(chatID: str, pdf_path: str):
    """
    Lê o PDF local em binário, converte para Base64 e envia via endpoint /messages/document
    da UltraMsg, sem precisar de URL pública.
    """
    to_number = format_number(chatID)
    url = f"https://api.ultramsg.com/{ULTRAMSG_INSTANCE_ID}/messages/document"
    
    # Lê o PDF em binário
    try:
        with open(pdf_path, 'rb') as f:
            pdf_bytes = f.read()
    except FileNotFoundError:
        logging.error(f"Arquivo PDF não encontrado: {pdf_path}")
        return None

    # Converte em Base64
    pdf_b64 = base64.b64encode(pdf_bytes).decode('utf-8')

    data = {
        "token": ULTRAMSG_TOKEN,
        "to": to_number,
        "base64Encoded": "true",  
        "document": pdf_b64,
        "filename": os.path.basename(pdf_path)
    }

    try:
        response = requests.post(url, data=data)
        logging.info(f"Enviando PDF (base64) para {to_number} -> {pdf_path}")
        logging.info(f"Resposta UltraMsg: {response.status_code}, {response.text}")
        return response
    except Exception as e:
        logging.error(f"Erro ao enviar PDF via UltraMsg (base64): {e}")
        return None

def load_states() -> dict:
    """Carrega o dicionário de estados do arquivo JSON."""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            try:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
                else:
                    logging.error("O arquivo de estados não contém um dicionário válido.")
                    return {}
            except json.JSONDecodeError:
                logging.error("Erro ao decodificar o arquivo de estados.")
                return {}
    else:
        logging.info("Arquivo de estados não encontrado. Criando novo.")
        return {}

def save_states(states: dict):
    """Salva o dicionário de estados no arquivo JSON."""
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(states, f, indent=4)
        logging.info("Estados salvos com sucesso.")
    except Exception as e:
        logging.error(f"Erro ao salvar os estados: {e}")


##############################################################################
# CLASSE PRINCIPAL DO BOT
##############################################################################

class ultraChatBot():
    def __init__(self, message_data):
        self.message = message_data
        raw_chat_id = message_data.get('from', '')
        # Remove "whatsapp:+" se tiver
        raw_chat_id = raw_chat_id.replace("whatsapp:+", "")
        # Remove "@c.us" se tiver
        raw_chat_id = raw_chat_id.replace("@c.us", "")
        self.chatID = raw_chat_id  # <= FICA SÓ NÚMERO (ex.: 5511999999999)
        
        # Carrega states
        self.states = load_states()

    def send_message(self, chatID: str, text: str):
        return send_message_ultramsg(chatID, text)

    ################################################################
    #                    MENSAGENS BÁSICAS
    ################################################################

    def greet_and_ask_options(self):
        greeting = "Olá! Bem-vindo à nossa loja de celulares."
        self.send_message(self.chatID, greeting)
        options = (
            "Como podemos te ajudar? Por favor, escolha uma das opções abaixo:\n"
            "1️⃣ - 📱 Comprar um aparelho\n"
            "2️⃣ - 🔧 Assistência Técnica\n"
            "3️⃣ - 👨‍💼 Falar com um atendente\n"
            "4️⃣ - ❌ Sair\n"
            "5️⃣ - 💰 Vender um aparelho\n"
        )
        self.send_message(self.chatID, options)

        self.states[self.chatID] = {
            'state': 'ASKED_OPTION',
            'last_interaction': time.time()
        }
        save_states(self.states)
        
    def send_options(self):
        """Envia as opções principais para o usuário."""
        options = (
            "Como podemos te ajudar? Por favor, escolha uma das opções abaixo:\n"
            "1️⃣ - 📱 Comprar um aparelho\n"
            "2️⃣ - 🔧 Assistência Técnica\n"
            "3️⃣ - 👨‍💼 Falar com um atendente\n"
            "4️⃣ - ❌ Sair\n"
            "5️⃣ - 💰 Vender um aparelho\n"
        )
        self.send_message(self.chatID, options)


    ################################################################
    #                LÓGICA DE COMPRA DE APARELHO
    ################################################################

    def handle_buy_device(self):
        question = (
            "Qual modelo de celular você está procurando? "
            "Por favor, digite o nome do modelo ou parte dele (exemplo: iPhone 12)."
        )
        self.send_message(self.chatID, question)

        self.states[self.chatID]['state'] = 'ASKED_MODEL_NAME'
        self.states[self.chatID]['last_interaction'] = time.time()
        save_states(self.states)

    def handle_model_search(self, model_name: str):
        """
        Busca o modelo no arquivo Excel 'Produtos_Lacrados.xlsx' e lista as opções.
        """
        try:
            df = pd.read_excel('excel/Produtos_Lacrados.xlsx')
            df.columns = df.columns.str.strip()

            df = df[['Produto', 'Preço (R$)', 'Cor', 'Detalhe']]
            df['Estado'] = df['Detalhe'].apply(
                lambda x: 'Lacrado' if pd.isna(x) else f"Seminovo ({x})"
            )

            resultados = df[df['Produto'].str.contains(model_name, case=False, na=False)]
            if not resultados.empty:
                # Caso encontre resultados, segue o fluxo normal
                produtos = resultados.to_dict(orient='records')
                self.states[self.chatID]['produtos'] = produtos

                mensagem = "✨📱 LISTA DE APARELHOS DISPONÍVEIS 📱✨\n"
                for i, row in enumerate(produtos, start=1):
                    mensagem += (
                        f"{i}. Produto: {row['Produto']}\n"
                        f"   Cor: {row['Cor']}\n"
                        f"   Estado: {row['Estado']}\n"
                        f"   Preço: {row['Preço (R$)']}\n\n"
                    )

                self.send_message(self.chatID, mensagem)
                self.send_message(
                    self.chatID,
                    "Por favor, digite o número do modelo que você deseja:\n"
                    "ou\n"
                    "N - Escolher outro modelo\n"
                    "M - Menu Principal\n"
                    "S - Sair"
                )
                self.states[self.chatID]['state'] = 'ASKED_MODEL_NUMBER'
                self.states[self.chatID]['last_interaction'] = time.time()
                save_states(self.states)
            else:
                # Não encontrou resultados => oferecer 3 opções:
                self.send_message(self.chatID, "Desculpe, não encontramos esse produto em nosso estoque.")
                self.send_message(
                    self.chatID,
                    "O que você gostaria de fazer agora?\n"
                    "1️⃣ - Listar aparelhos semelhantes disponíveis\n"
                    "2️⃣ - Fazer uma nova consulta\n"
                    "3️⃣ - Voltar ao menu principal\n"
                )
                # Guarda o último modelo pesquisado para utilizar na listagem de similares
                self.states[self.chatID]['last_searched_model'] = model_name
                self.states[self.chatID]['state'] = 'ASKED_NO_RESULTS_ACTION'
                self.states[self.chatID]['last_interaction'] = time.time()
                save_states(self.states)

        except Exception as e:
            logging.error(f"Erro ao acessar a planilha: {e}")
            self.send_message(self.chatID, "Desculpe, ocorreu um erro ao buscar os produtos disponíveis.")



    def handle_model_number_choice(self, choice: str):
        choice = choice.strip().upper()
        if choice == 'N':
            self.handle_buy_device()
        elif choice == 'M':
            # Volta ao menu principal
            self.greet_and_ask_options()
        elif choice == 'S':
            self.send_message(self.chatID, "Obrigado pelo contato. Se precisar de algo, estamos à disposição!")
            self.states[self.chatID]['state'] = 'SESSION_ENDED'
            self.states[self.chatID]['pause_start_time'] = time.time()
            save_states(self.states)
        else:
            try:
                choice_num = int(choice)
                produtos = self.states[self.chatID].get('produtos', [])
                if 1 <= choice_num <= len(produtos):
                    produto_escolhido = produtos[choice_num - 1]
                    self.states[self.chatID]['produto_escolhido'] = produto_escolhido

                    mensagem = (
                        f"Você escolheu o seguinte produto:\n"
                        f"Produto: {produto_escolhido['Produto']}\n"
                        f"Cor: {produto_escolhido['Cor']}\n"
                        f"Estado: {produto_escolhido['Estado']}\n"
                        f"Preço: {produto_escolhido['Preço (R$)']}\n\n"
                        "Você gostaria de prosseguir com a compra?\n"
                        "Digite 'Sim' para confirmar, ou escolha uma opção:\n"
                        "N - Escolher outro modelo\n"
                        "M - Menu Principal\n"
                        "S - Sair"
                    )
                    self.send_message(self.chatID, mensagem)
                    self.states[self.chatID]['state'] = 'CONFIRM_PURCHASE'
                    self.states[self.chatID]['last_interaction'] = time.time()
                    save_states(self.states)
                else:
                    self.send_message(self.chatID, "Opção inválida. Por favor, digite o número do modelo desejado.")
            except ValueError:
                self.send_message(self.chatID, "Entrada inválida. Por favor, digite o número correspondente ao modelo desejado.")

    ################################################################
    #                 PAGAMENTO (CARTÃO / PIX / USADO)
    ################################################################

    def handle_confirm_purchase(self, choice: str):
        choice = choice.strip().upper()
        if choice in ['SIM', '✅']:
            self.send_message(
                self.chatID,
                "Escolha a forma de pagamento:\n"
                "1️⃣ - Cartão de Crédito (Com as taxas da maquina)\n"
                "2️⃣ - PIX/Dinheiro (Com desconto)\n"
                "3️⃣ - Dar um aparelho usado como parte do pagamento"
            )
            self.states[self.chatID]['state'] = 'ASKED_PAYMENT_METHOD'
            self.states[self.chatID]['last_interaction'] = time.time()
            save_states(self.states)
        elif choice in ['NÃO', 'NAO', '❌']:
            self.send_message(self.chatID, "Tudo bem! Se precisar de algo mais, estamos à disposição.")
            self.states[self.chatID]['state'] = 'SESSION_ENDED'
            self.states[self.chatID]['pause_start_time'] = time.time()
            save_states(self.states)
        else:
            self.send_message(self.chatID, "Desculpe, não entendi. Responda com 'Sim' ou 'Não'.")

    def handle_payment_method(self, user_message: str):
        choice = user_message.strip()
        if choice == '1':
            # CARTÃO
            self.states[self.chatID]['payment_method'] = 'CARTAO'

            product = self.states[self.chatID].get('produto_escolhido', {})
            preco_base = float(product.get('Preço (R$)', 0))

            mensagem_parcelas = "O valor do celular parcelado com a taxa da maquininha é:\n"
            for parcelas in range(1, 19):
                taxa = CREDIT_RATES.get(parcelas, 0)
                valor_com_taxa = preco_base * (1 + taxa)
                mensagem_parcelas += (
                    f"{parcelas}x: Valor total: R$ {valor_com_taxa:,.2f}\n"
                )

            mensagem_parcelas += "\nEm quantas vezes você quer fazer?"
            self.send_message(self.chatID, mensagem_parcelas)

            self.states[self.chatID]['state'] = 'ASKED_CREDIT_INSTALLMENTS'
            save_states(self.states)

        elif choice == '2':
            # PIX/DINHEIRO
            self.states[self.chatID]['payment_method'] = 'PIX_DINHEIRO'
            self.send_message(self.chatID, "Você selecionou PIX/Dinheiro. Você terá um desconto especial.")
            self.send_message(self.chatID, "Por favor, informe seus dados para finalizar:")
            self.send_message(self.chatID, "NOME COMPLETO:")
            self.states[self.chatID]['state'] = 'ASKED_NAME'
            save_states(self.states)

        elif choice == '3':
            # DAR APARELHO USADO
            self.states[self.chatID]['payment_method'] = 'USADO'
            self.send_message(self.chatID, "Perfeito! Precisamos de algumas informações do aparelho que você vai entregar.")
            self.send_message(self.chatID, "Qual o modelo do aparelho usado?")
            self.states[self.chatID]['state'] = 'ASKED_USED_PHONE_MODEL'
            save_states(self.states)
        else:
            self.send_message(self.chatID, "Opção inválida. Selecione 1, 2 ou 3 por favor.")

    def handle_credit_installments(self, user_message: str):
        """
        Pergunta: Em quantas vezes o cliente quer pagar?
        """
        try:
            parcelas = int(user_message.strip())
            if 1 <= parcelas <= 18:
                self.states[self.chatID]['installments'] = parcelas
                self.send_message(self.chatID, f"Você escolheu pagar em {parcelas}x.")
                self.send_message(self.chatID, "Por favor, informe seus dados para finalizar:")
                self.send_message(self.chatID, "NOME COMPLETO:")

                self.states[self.chatID]['state'] = 'ASKED_NAME'
                save_states(self.states)
            else:
                self.send_message(self.chatID, "Por favor, digite um número de 1 a 18.")
        except ValueError:
            self.send_message(self.chatID, "Por favor, responda com um número de 1 a 18.")

    ################################################################
    #                 APARELHO USADO (coleta infos)
    ################################################################

    def handle_used_phone_model(self, user_message: str):
        self.states[self.chatID]['used_phone_model'] = user_message
        self.send_message(self.chatID, "Qual o armazenamento do aparelho (ex: 64GB, 128GB)?")
        self.states[self.chatID]['state'] = 'ASKED_USED_PHONE_STORAGE'
        save_states(self.states)

    def handle_used_phone_storage(self, user_message: str):
        self.states[self.chatID]['used_phone_storage'] = user_message
        self.send_message(self.chatID, "Como está a bateria do aparelho? (ex: Boa, Ruim, Saúde X%)")
        self.states[self.chatID]['state'] = 'ASKED_USED_PHONE_BATTERY'
        save_states(self.states)

    def handle_used_phone_battery(self, user_message: str):
        self.states[self.chatID]['used_phone_battery'] = user_message
        self.send_message(self.chatID, "O Face ID está funcionando? (Sim / Não)")
        self.states[self.chatID]['state'] = 'ASKED_USED_PHONE_FACEID'
        save_states(self.states)

    def handle_used_phone_faceid(self, user_message: str):
        self.states[self.chatID]['used_phone_faceid'] = user_message
        self.send_message(self.chatID, "Há algum defeito, tela trincada ou algo parecido? Se sim, descreva. Se não, digite 'Não'.")
        self.states[self.chatID]['state'] = 'ASKED_USED_PHONE_DEFECTS'
        save_states(self.states)

    def handle_used_phone_defects(self, user_message: str):
        self.states[self.chatID]['used_phone_defects'] = user_message
        self.send_message(
            self.chatID,
            "Obrigado! Agora, como você deseja pagar a diferença?\n"
            "1️⃣ - Cartão de Crédito\n"
            "2️⃣ - PIX/Dinheiro"
        )
        self.states[self.chatID]['state'] = 'ASKED_COMPLEMENT_PAYMENT_METHOD'
        save_states(self.states)

    def handle_complement_payment_method(self, user_message: str):
        choice = user_message.strip()
        if choice == '1':
            self.states[self.chatID]['payment_complement'] = 'CARTAO'
            self.send_message(self.chatID, "Você escolheu pagar o restante no Cartão de Crédito.")
            self.send_message(self.chatID, "Por favor, informe seus dados para finalizar:")
            self.send_message(self.chatID, "NOME COMPLETO:")
            self.states[self.chatID]['state'] = 'ASKED_NAME'
            save_states(self.states)

        elif choice == '2':
            self.states[self.chatID]['payment_complement'] = 'PIX_DINHEIRO'
            self.send_message(self.chatID, "Você escolheu PIX/Dinheiro para o restante. Ok!")
            self.send_message(self.chatID, "Por favor, informe seus dados para finalizar:")
            self.send_message(self.chatID, "NOME COMPLETO:")
            self.states[self.chatID]['state'] = 'ASKED_NAME'
            save_states(self.states)
        else:
            self.send_message(self.chatID, "Opção inválida. Selecione 1 ou 2, por favor.")

    ################################################################
    #       COLETA DE DADOS PESSOAIS E GERA RECEITA/PDF
    ################################################################

    def collect_client_data(self, user_message: str):
        current_state = self.states[self.chatID].get('state')

        if current_state == 'ASKED_NAME':
            self.states[self.chatID]['name'] = user_message
            self.send_message(self.chatID, "CPF:")
            self.states[self.chatID]['state'] = 'ASKED_CPF'

        elif current_state == 'ASKED_CPF':
            self.states[self.chatID]['cpf'] = user_message
            self.send_message(self.chatID, "CEL:")
            self.states[self.chatID]['state'] = 'ASKED_PHONE'

        elif current_state == 'ASKED_PHONE':
            self.states[self.chatID]['phone'] = user_message
            self.send_message(self.chatID, "ENDEREÇO DA ENTREGA:")
            self.states[self.chatID]['state'] = 'ASKED_ADDRESS'

        elif current_state == 'ASKED_ADDRESS':
            self.states[self.chatID]['address'] = user_message
            self.send_message(self.chatID, "BAIRRO:")
            self.states[self.chatID]['state'] = 'ASKED_NEIGHBORHOOD'

        elif current_state == 'ASKED_NEIGHBORHOOD':
            self.states[self.chatID]['neighborhood'] = user_message
            self.send_message(self.chatID, "CEP:")
            self.states[self.chatID]['state'] = 'ASKED_ZIP'

        elif current_state == 'ASKED_ZIP':
            self.states[self.chatID]['zip'] = user_message
            self.send_message(self.chatID, "E-MAIL:")
            self.states[self.chatID]['state'] = 'ASKED_EMAIL'

        elif current_state == 'ASKED_EMAIL':
            self.states[self.chatID]['email'] = user_message
            self.send_message(self.chatID, "Obrigado! Estamos gerando o recibo da sua compra...")

            # 1) Calcula valor final
            self.calculate_final_price()
            # 2) Gera PDF
            self.generate_receipt()
            # 3) Finaliza
            self.states[self.chatID]['state'] = 'SESSION_ENDED'
            self.states[self.chatID]['pause_start_time'] = time.time()

        save_states(self.states)

    def calculate_final_price(self):
        client_data = self.states[self.chatID]
        product = client_data.get('produto_escolhido', {})
        preco_base = float(product.get('Preço (R$)', 0))

        payment_method = client_data.get('payment_method', '')
        payment_complement = client_data.get('payment_complement', '')
        installments = client_data.get('installments', 1)

        desconto_pix = 0.10
        used_phone_value = 0.0

        if payment_method == 'CARTAO':
            taxa = CREDIT_RATES.get(installments, 0)
            preco_final = preco_base * (1 + taxa)

        elif payment_method == 'PIX_DINHEIRO':
            preco_final = preco_base * (1 - desconto_pix)

        elif payment_method == 'USADO':
            # Valor fixo do usado (exemplo, R$400)
            used_phone_value = 400.0
            preco_base -= used_phone_value
            if preco_base < 0:
                preco_base = 0

            if payment_complement == 'CARTAO':
                # Se quiser, pergunte de novo quantas parcelas etc.
                taxa = CREDIT_RATES.get(installments, 0)
                preco_final = preco_base * (1 + taxa)
            elif payment_complement == 'PIX_DINHEIRO':
                preco_final = preco_base * (1 - desconto_pix)
            else:
                preco_final = preco_base
        else:
            # fallback
            preco_final = preco_base

        self.states[self.chatID]['valor_troca_usado'] = used_phone_value
        self.states[self.chatID]['valor_final'] = round(preco_final, 2)
        save_states(self.states)

    def generate_receipt(self):
        client_data = self.states[self.chatID]
        product = client_data.get('produto_escolhido', {})
        valor_final = client_data.get('valor_final', 0)
        payment_method = client_data.get('payment_method', '')
        payment_complement = client_data.get('payment_complement', '')
        valor_troca_usado = client_data.get('valor_troca_usado', 0)
        installments = client_data.get('installments', 1)

        nome_cliente = client_data.get('name', 'Cliente')
        # Extrair número de Whats do chatID
        number_str = format_number(self.chatID)  # ex.: '556781687046'

        # Monta o nome do PDF: "NomeDoCliente_whatsnumero.pdf"
        pdf_filename = f"{nome_cliente}_{number_str}.pdf"
        pdf_path = os.path.join("PDF", pdf_filename)

        html_content = f"""
        <!DOCTYPE html>
        <html lang="pt-BR">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Nota/Recibo</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    margin: 20px;
                    padding: 20px;
                    border: 1px solid #ccc;
                    max-width: 600px;
                }}
                h1 {{
                    text-align: center;
                    text-transform: uppercase;
                }}
                .details {{
                    margin-bottom: 20px;
                }}
                .details div {{
                    margin: 5px 0;
                }}
                .footer {{
                    text-align: center;
                    margin-top: 30px;
                }}
            </style>
        </head>
        <body>
            <h1>Recibo de Compra</h1>
            <div class="details">
                <div><strong>Data:</strong> <span>{time.strftime("%d/%m/%Y")}</span></div>
                <div><strong>Cliente:</strong> <span>{nome_cliente}</span></div>
                <div><strong>Endereço:</strong> <span>{client_data.get('address')}, {client_data.get('neighborhood')}, {client_data.get('zip')}</span></div>
                <div><strong>CPF:</strong> <span>{client_data.get('cpf')}</span></div>
                <div><strong>E-mail:</strong> <span>{client_data.get('email')}</span></div>
            </div>

            <h2>Detalhes do Pedido</h2>
            <table border="1" width="100%" cellpadding="5" cellspacing="0">
                <thead>
                    <tr>
                        <th>Item</th>
                        <th>Modelo</th>
                        <th>Quantidade</th>
                        <th>Preço Unitário</th>
                        <th>Total</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>Smartphone</td>
                        <td>{product.get('Produto')}</td>
                        <td>1</td>
                        <td>{product.get('Preço (R$)')}</td>
                        <td>{product.get('Preço (R$)')}</td>
                    </tr>
                </tbody>
            </table>

            <div style="margin-top: 20px;">
                <p><strong>Forma de Pagamento:</strong> {payment_method}</p>
                {"<p><strong>Pagamento Complementar:</strong> " + payment_complement + "</p>" if payment_method == "USADO" else ""}
                {f"<p><strong>Valor de troca do aparelho usado:</strong> R$ {valor_troca_usado}</p>" if valor_troca_usado else ""}
                
                {"<p><strong>Parcelas:</strong> " + str(installments) + "x</p>" if payment_method == "CARTAO" or (payment_method == "USADO" and payment_complement == "CARTAO") else ""}
                
                <p><strong>Valor Final (após taxas/descontos):</strong> R$ {valor_final}</p>
            </div>

            <div class="footer">
                <p>Obrigado pela sua compra!</p>
                <p>Loja Exemplo</p>
            </div>
        </body>
        </html>
        """

        HTML(string=html_content).write_pdf(pdf_path)

        # Envia o PDF como DOCUMENTO
        self.send_message(self.chatID, "Aqui está o seu recibo!")
        send_document_ultramsg_base64(self.chatID, pdf_path)

    ################################################################
    #               LÓGICA DE ASSISTÊNCIA TÉCNICA
    ################################################################

    def handle_technical_assistance_options(self):
        options = (
            "Por favor, selecione o tipo de serviço de assistência técnica que você precisa:\n"
            "1️⃣ - Trocar Tela\n"
            "2️⃣ - Trocar Bateria\n"
            "3️⃣ - Trocar Tampa Traseira\n"
            "4️⃣ - Outro Problema"
        )
        self.send_message(self.chatID, options)
        self.states[self.chatID]['state'] = 'ASKED_TECH_OPTION'
        self.states[self.chatID]['last_interaction'] = time.time()
        save_states(self.states)

    def handle_tech_option_choice(self, choice: str):
        choice = choice.strip()
        if choice in ['1', '2', '3']:
            service_map = {'1': 'Tela', '2': 'Bateria', '3': 'Tampa'}
            self.states[self.chatID]['service_type'] = service_map[choice]
            self.send_message(self.chatID, "Por favor, informe o modelo do seu iPhone (exemplo: iPhone 12).")
            self.states[self.chatID]['state'] = 'ASKED_PHONE_MODEL'
            self.states[self.chatID]['last_interaction'] = time.time()
            save_states(self.states)
        elif choice == '4':
            self.send_message(self.chatID, "Por favor, descreva o problema que está enfrentando.")
            self.states[self.chatID]['state'] = 'ASKED_PROBLEM_DESCRIPTION'
            self.states[self.chatID]['last_interaction'] = time.time()
            save_states(self.states)
        else:
            self.send_message(self.chatID, "Opção inválida. Selecione uma opção válida.")

    def handle_phone_model(self, model_name: str):
        service_type = self.states[self.chatID].get('service_type')
        if not service_type:
            self.send_message(self.chatID, "Desculpe, ocorreu um erro. Vamos começar novamente.")
            self.handle_technical_assistance_options()
            return

        try:
            df = pd.read_excel('excel/reparo_iphones.xlsx')
            df = df[['Modelo', 'Tela', 'Bateria', 'Tampa']]
            df = df.dropna(subset=['Modelo'])

            matched_rows = df[df['Modelo'].str.contains(model_name, case=False, na=False)]
            if matched_rows.empty:
                self.send_message(self.chatID, f"Desculpe, não encontramos o modelo {model_name} em nosso sistema.")
                self.send_message(self.chatID, "Por favor, informe o modelo novamente! ")
                return

            price = matched_rows.iloc[0][service_type]
            if pd.isna(price):
                self.send_message(self.chatID, f"Desculpe, não possuo o serviço de {service_type.lower()} para o modelo {model_name}.")
                self.send_message(self.chatID, "Por favor, informe outro modelo ou peça um orçamento específico.")
                self.handle_technical_assistance_options()
                return

            self.send_message(
                self.chatID,
                f"O valor para trocar a {service_type.lower()} do seu {model_name} é R$ {price:.2f}."
            )
            self.send_message(
                self.chatID,
                "Deseja prosseguir com o serviço?\nResponda com:\nSim ✅\nNão ❌"
            )
            self.states[self.chatID]['state'] = 'ASKED_SERVICE_CONFIRMATION'
            self.states[self.chatID]['last_interaction'] = time.time()
            save_states(self.states)

        except Exception as e:
            logging.error(f"Erro ao acessar a planilha: {e}")
            self.send_message(self.chatID, "Desculpe, ocorreu um erro ao acessar nossas informações.")

    def handle_service_confirmation(self, confirmation: str):
        confirmation = confirmation.strip().upper()
        if confirmation in ['SIM', '✅']:
            self.send_message(
                self.chatID,
                "Obrigado! Seu serviço foi agendado. Nossa equipe entrará em contato para mais detalhes."
            )
            self.states[self.chatID]['state'] = 'SESSION_ENDED'
            self.states[self.chatID]['pause_start_time'] = time.time()
            save_states(self.states)
        elif confirmation in ['NÃO', 'NAO', '❌']:
            self.send_message(self.chatID, "Tudo bem! Se precisar de algo mais, estamos à disposição.")
            self.states[self.chatID]['state'] = 'SESSION_ENDED'
            self.states[self.chatID]['pause_start_time'] = time.time()
            save_states(self.states)
        else:
            self.send_message(self.chatID, "Desculpe, não entendi. Por favor, responda com 'Sim' ou 'Não'.")

    def handle_problem_description(self, description: str):
        self.send_message(self.chatID, "Obrigado por nos informar. Nossa equipe técnica irá analisar e entraremos em contato com o orçamento em breve.")
        self.states[self.chatID]['state'] = 'SESSION_ENDED'
        self.states[self.chatID]['pause_start_time'] = time.time()
        save_states(self.states)
        
    ################################################################
    #                 VENDER UM APARELHO
    ################################################################
    def handle_list_similar_devices(self):
        # Recupera o último modelo que o usuário procurou
        last_model = self.states[self.chatID].get('last_searched_model', '')
        if not last_model:
            # Se não houver modelo anterior, avisa e retorna ao fluxo
            self.send_message(self.chatID, "Não há modelo anterior para comparar. Vamos iniciar novamente a busca.")
            self.handle_buy_device()
            return

        # Tenta capturar algo do tipo "iPhone 14"
        match = re.search(r'iPhone\s*(\d+)', last_model, re.IGNORECASE)
        if match:
            try:
                # Converte a parte numérica para int
                number = int(match.group(1))

                # Define iPhone (n-1) e iPhone (n+1), se fizer sentido
                model_minus = f"iPhone {number - 1}" if number > 1 else None
                model_plus = f"iPhone {number + 1}"

                # Leitura do Excel
                df = pd.read_excel('excel/Produtos_Lacrados.xlsx')
                df.columns = df.columns.str.strip()
                df = df[['Produto', 'Preço (R$)', 'Cor', 'Detalhe']]
                df['Estado'] = df['Detalhe'].apply(
                    lambda x: 'Lacrado' if pd.isna(x) else f"Seminovo ({x})"
                )

                # Aqui vamos juntar resultados dos dois modelos
                similares = pd.DataFrame()
                
                if model_minus:  # se "iPhone 0" não faz sentido, ignoramos
                    results_minus = df[df['Produto'].str.contains(model_minus, case=False, na=False)]
                    similares = pd.concat([similares, results_minus], ignore_index=True)
                
                # iPhone (n+1)
                results_plus = df[df['Produto'].str.contains(model_plus, case=False, na=False)]
                similares = pd.concat([similares, results_plus], ignore_index=True)

                if not similares.empty:
                    produtos = similares.to_dict(orient='records')

                    mensagem = "✨📱 LISTA DE APARELHOS SEMELHANTES DISPONÍVEIS 📱✨\n"
                    for i, row in enumerate(produtos, start=1):
                        mensagem += (
                            f"{i}. Produto: {row['Produto']}\n"
                            f"   Cor: {row['Cor']}\n"
                            f"   Estado: {row['Estado']}\n"
                            f"   Preço: {row['Preço (R$)']}\n\n"
                        )

                    self.send_message(self.chatID, mensagem)
                    self.send_message(
                        self.chatID,
                        "Se algum desses modelos te interessar, por favor digite o número correspondente.\n"
                        "Ou:\n"
                        "N - Fazer outra pesquisa\n"
                        "M - Menu Principal\n"
                        "S - Sair"
                    )
                    # Reaproveitando o estado de 'ASKED_MODEL_NUMBER' para escolher
                    self.states[self.chatID]['produtos'] = produtos
                    self.states[self.chatID]['state'] = 'ASKED_MODEL_NUMBER'
                    self.states[self.chatID]['last_interaction'] = time.time()
                    save_states(self.states)
                else:
                    self.send_message(self.chatID, "Não encontramos modelos semelhantes (iPhone anterior ou posterior).")
                    self.send_message(
                        self.chatID,
                        "Podemos tentar outra pesquisa?\n"
                        "1 - Digitar outro modelo\n"
                        "2 - Menu Principal"
                    )
                    # Pode criar um novo estado ou reaproveitar a lógica de redirect
                    self.states[self.chatID]['state'] = 'ASKED_SIMILAR_NOT_FOUND'
                    self.states[self.chatID]['last_interaction'] = time.time()
                    save_states(self.states)
            except Exception as e:
                logging.error(f"Erro ao listar similares: {e}")
                self.send_message(self.chatID, "Desculpe, ocorreu um erro ao buscar aparelhos semelhantes.")
        else:
            # Se o usuário não digitou algo que bata com 'iPhone (numero)',
            # podemos apenas dizer que não há semelhantes específicos
            self.send_message(self.chatID, "Não foi possível identificar um iPhone para sugerir similares.")
            self.send_message(
                self.chatID,
                "Deseja tentar outra pesquisa?\n"
                "1 - Digitar outro modelo\n"
                "2 - Menu Principal"
            )
            # Pode criar um novo estado, ou chamar handle_buy_device() novamente
            self.states[self.chatID]['state'] = 'ASKED_SIMILAR_NOT_FOUND'
            self.states[self.chatID]['last_interaction'] = time.time()
            save_states(self.states)

        
    ################################################################
    #                 VENDER UM APARELHO
    ################################################################

        
    def handle_sell_device(self):

        self.send_message(self.chatID, "Ótimo! Para avaliarmos seu aparelho, precisamos de algumas informações.")
        self.send_message(self.chatID, "Qual o modelo do seu celular usado? (Exemplo: iPhone 12)")
        
        # Define o próximo estado
        self.states[self.chatID]['state'] = 'ASKED_USED_PHONE_MODEL_SELL'
        self.states[self.chatID]['last_interaction'] = time.time()
        save_states(self.states)
        
    def handle_used_phone_model_sell(self, user_message: str):
        self.states[self.chatID]['used_phone_model'] = user_message
        self.send_message(self.chatID, "Qual o armazenamento do aparelho (ex: 64GB, 128GB)?")
        self.states[self.chatID]['state'] = 'ASKED_USED_PHONE_STORAGE_SELL'
        self.states[self.chatID]['last_interaction'] = time.time()
        save_states(self.states)

    def handle_used_phone_storage_sell(self, user_message: str):
        self.states[self.chatID]['used_phone_storage'] = user_message
        self.send_message(self.chatID, "Como está a bateria do aparelho? (ex: Boa, Ruim, Saúde 85%)")
        self.states[self.chatID]['state'] = 'ASKED_USED_PHONE_BATTERY_SELL'
        self.states[self.chatID]['last_interaction'] = time.time()
        save_states(self.states)

    def handle_used_phone_battery_sell(self, user_message: str):
        self.states[self.chatID]['used_phone_battery'] = user_message
        self.send_message(self.chatID, "O Face ID está funcionando? (Sim / Não)")
        self.states[self.chatID]['state'] = 'ASKED_USED_PHONE_FACEID_SELL'
        self.states[self.chatID]['last_interaction'] = time.time()
        save_states(self.states)

    def handle_used_phone_faceid_sell(self, user_message: str):
        self.states[self.chatID]['used_phone_faceid'] = user_message
        self.send_message(self.chatID, "Há algum defeito, tela trincada ou algo parecido? Se sim, descreva. Se não, digite 'Não'.")
        self.states[self.chatID]['state'] = 'ASKED_USED_PHONE_DEFECTS_SELL'
        self.states[self.chatID]['last_interaction'] = time.time()
        save_states(self.states)
    def handle_used_phone_model_sell(self, user_message: str):
        self.states[self.chatID]['used_phone_model'] = user_message
        self.send_message(self.chatID, "Qual o armazenamento do aparelho (ex: 64GB, 128GB)?")
        self.states[self.chatID]['state'] = 'ASKED_USED_PHONE_STORAGE_SELL'
        self.states[self.chatID]['last_interaction'] = time.time()
        save_states(self.states)

    def handle_used_phone_storage_sell(self, user_message: str):
        self.states[self.chatID]['used_phone_storage'] = user_message
        self.send_message(self.chatID, "Como está a bateria do aparelho? (ex: Boa, Ruim, Saúde 85%)")
        self.states[self.chatID]['state'] = 'ASKED_USED_PHONE_BATTERY_SELL'
        self.states[self.chatID]['last_interaction'] = time.time()
        save_states(self.states)

    def handle_used_phone_battery_sell(self, user_message: str):
        self.states[self.chatID]['used_phone_battery'] = user_message
        self.send_message(self.chatID, "O Face ID está funcionando? (Sim / Não)")
        self.states[self.chatID]['state'] = 'ASKED_USED_PHONE_FACEID_SELL'
        self.states[self.chatID]['last_interaction'] = time.time()
        save_states(self.states)

    def handle_used_phone_faceid_sell(self, user_message: str):
        self.states[self.chatID]['used_phone_faceid'] = user_message
        self.send_message(self.chatID, "Há algum defeito, tela trincada ou algo parecido? Se sim, descreva. Se não, digite 'Não'.")
        self.states[self.chatID]['state'] = 'ASKED_USED_PHONE_DEFECTS_SELL'
        self.states[self.chatID]['last_interaction'] = time.time()
        save_states(self.states)
    
    def handle_used_phone_defects_sell(self, user_message: str):
        self.states[self.chatID]['used_phone_defects'] = user_message
        self.send_message(self.chatID, "Por favor, envie algumas fotos do aparelho para avaliação. "
                                    "Pode mandar uma de cada vez ou várias. Assim que terminar avise.")
        self.states[self.chatID]['state'] = 'ASKED_USED_PHONE_PHOTOS_SELL'
        self.states[self.chatID]['last_interaction'] = time.time()
        save_states(self.states)
        
    def handle_used_phone_photos_sell(self, user_message: str):
        # Exemplo simples: só guardamos a resposta e finalizamos
        # Se quiser lidar com várias fotos, você pode criar um array no self.states e armazenar cada imagem recebida.
        self.states[self.chatID]['used_phone_photos'] = user_message  # ou "Fotos recebidas"
        
        # Agradecemos e avisamos que iremos analisar
        self.send_message(self.chatID, "Obrigado! Recebemos as informações do seu aparelho. "
                                    "Vamos analisar e retornaremos em breve com um valor de proposta.")
        
        # Marcamos a conversa com o status COMPRAR_CEL (conforme solicitado)
        self.states[self.chatID]['state'] = 'VENDER_CEL'
        save_states(self.states)


    ################################################################
    #                 FALAR COM ATENDENTE
    ################################################################

    def handle_talk_to_agent(self):
        # Transfere para atendimento humano
        message = "Um de nossos atendentes entrará em contato com você em breve."
        self.send_message(self.chatID, message)
        self.states[self.chatID]['state'] = 'WAITING_FOR_AGENT'
        self.states[self.chatID]['pause_start_time'] = time.time()
        save_states(self.states)
        
    ################################################################
    #               PROCESSAMENTO PRINCIPAL
    ################################################################

    def Processing_incoming_messages(self):
        user_message = self.message.get('body', '').strip()
        if not user_message:
            self.send_message(self.chatID, "Desculpe, não entendi sua mensagem.")
            return

        # 1) Primeiro, se não existe esse chatID em self.states, inicia a conversa
        if self.chatID not in self.states:
            self.greet_and_ask_options()
            return

        # 2) Verifica se a conversa está em modo atendente
        if self.states[self.chatID].get('agent_mode', False):
            logging.info(f"Conversa {self.chatID} em modo atendente humano. Bot não responderá automaticamente.")
            return

        # 3) Obtém o estado atual
        state_info = self.states[self.chatID]
        state = state_info.get('state', '')

        # 4) Se o estado for SESSION_ENDED, reinicia a conversa
        if state == 'SESSION_ENDED':
            self.send_message(self.chatID, "Olá novamente! Como posso ajudar?")
            self.greet_and_ask_options()
            return

        # 5) Agora segue o fluxo principal de acordo com o estado
        elif state == 'ASKED_OPTION':
            if user_message == '1':
                self.handle_buy_device()
            elif user_message == '2':
                self.handle_technical_assistance_options()
            elif user_message == '3':
                self.handle_talk_to_agent()
            elif user_message == '4':
                self.send_message(self.chatID, "Obrigado pelo contato. Se precisar de algo, estamos à disposição!")
                self.states[self.chatID]['state'] = 'FINISHED'
                self.states[self.chatID]['pause_start_time'] = time.time()
                save_states(self.states)
            elif user_message == '5':
                self.handle_sell_device()  # Método que inicia o fluxo de "Vender um aparelho"
            else:
                self.send_message(self.chatID, "Opção inválida. Por favor, selecione uma das opções enviadas.")
        
        # ===========================================
        #         NOVO ESTADO DE 'SEM RESULTADOS'
        # ===========================================
        elif state == 'ASKED_NO_RESULTS_ACTION':
            if user_message == '1':
                # 1) Listar aparelhos semelhantes
                self.handle_list_similar_devices()
            elif user_message == '2':
                # 2) Fazer nova consulta
                self.handle_buy_device()
            elif user_message == '3':
                # 3) Voltar ao menu principal
                self.greet_and_ask_options()
            else:
                self.send_message(self.chatID, "Por favor, escolha uma das opções: 1, 2 ou 3.")


        # COMPRA
        elif state == 'ASKED_MODEL_NAME':
            self.handle_model_search(user_message)
        elif state == 'ASKED_MODEL_NUMBER':
            self.handle_model_number_choice(user_message)
        elif state == 'CONFIRM_PURCHASE':
            self.handle_confirm_purchase(user_message)

        # PAGAMENTO
        elif state == 'ASKED_PAYMENT_METHOD':
            self.handle_payment_method(user_message)
        elif state == 'ASKED_CREDIT_INSTALLMENTS':
            self.handle_credit_installments(user_message)

        # APARELHO USADO
        elif state == 'ASKED_USED_PHONE_MODEL':
            self.handle_used_phone_model(user_message)
        elif state == 'ASKED_USED_PHONE_STORAGE':
            self.handle_used_phone_storage(user_message)
        elif state == 'ASKED_USED_PHONE_BATTERY':
            self.handle_used_phone_battery(user_message)
        elif state == 'ASKED_USED_PHONE_FACEID':
            self.handle_used_phone_faceid(user_message)
        elif state == 'ASKED_USED_PHONE_DEFECTS':
            self.handle_used_phone_defects(user_message)
        elif state == 'ASKED_COMPLEMENT_PAYMENT_METHOD':
            self.handle_complement_payment_method(user_message)
            
        # VENDER APARELHO (NOVOS ESTADOS):
        elif state == 'ASKED_USED_PHONE_MODEL_SELL':
            self.handle_used_phone_model_sell(user_message)
        elif state == 'ASKED_USED_PHONE_STORAGE_SELL':
            self.handle_used_phone_storage_sell(user_message)
        elif state == 'ASKED_USED_PHONE_BATTERY_SELL':
            self.handle_used_phone_battery_sell(user_message)
        elif state == 'ASKED_USED_PHONE_FACEID_SELL':
            self.handle_used_phone_faceid_sell(user_message)
        elif state == 'ASKED_USED_PHONE_DEFECTS_SELL':
            self.handle_used_phone_defects_sell(user_message)
        elif state == 'ASKED_USED_PHONE_PHOTOS_SELL':
            self.handle_used_phone_photos_sell(user_message)

        # COLETA DE DADOS (NOME, CPF, etc.)
        elif state.startswith('ASKED_'):
            self.collect_client_data(user_message)

        # ASSISTÊNCIA TÉCNICA
        elif state == 'ASKED_TECH_OPTION':
            self.handle_tech_option_choice(user_message)
        elif state == 'ASKED_PHONE_MODEL':
            self.handle_phone_model(user_message)
        elif state == 'ASKED_SERVICE_CONFIRMATION':
            self.handle_service_confirmation(user_message)
        elif state == 'ASKED_PROBLEM_DESCRIPTION':
            self.handle_problem_description(user_message)
        
        #FINALIZAR A COMVERSA
        elif state == 'FINISHED':
            self.send_message(self.chatID, "Olá novamente! Como podemos te ajudar?")
            self.send_options()
            self.states[self.chatID]['state'] = 'ASKED_OPTION'
            self.states[self.chatID]['last_interaction'] = time.time()
            save_states(self.states)

        # FALAR COM ATENDENTE
        elif state == 'WAITING_FOR_AGENT':
            # Não responde nada
            pass
        
        # FALAR COM VENDER DEL
        elif state == 'VENDER_CEL':
            # Não responde nada
            pass

        # Fallback: se cair em um estado desconhecido
        else:
            self.greet_and_ask_options()
