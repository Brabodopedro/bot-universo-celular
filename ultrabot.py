import json
import requests
import pandas as pd
import os
import logging
import time
from weasyprint import HTML

STATE_FILE = 'conversation_states.json'

# Ajuste estas variáveis com seus dados UltaMsg
ULTRAMSG_INSTANCE_ID = "instance99723"  # Substitua pelo seu ID da instância UltraMsg
ULTRAMSG_TOKEN = "2str21gem9r5za4u"    # Substitua pelo seu token UltraMsg

def format_number(chatID):
    """Remove o prefixo 'whatsapp:+' do chatID, se existir."""
    if chatID.startswith("whatsapp:+"):
        chatID = chatID.replace("whatsapp:+", "")
    return chatID

def send_message_ultramsg(chatID, text):
    """Envia texto via API da UltraMsg."""
    chatID = format_number(chatID)
    url = f"https://api.ultramsg.com/{ULTRAMSG_INSTANCE_ID}/messages/chat"
    data = {
        "to": chatID,
        "body": text,
        "token": ULTRAMSG_TOKEN
    }

    try:
        response = requests.post(url, data=data)
        logging.info(f"Mensagem enviada para {chatID}: '{text}'")
        logging.info(f"Resposta UltraMsg: {response.status_code}, {response.text}")
        return response
    except Exception as e:
        logging.error(f"Erro ao enviar mensagem via UltraMsg: {e}")
        return None

def load_states():
    """Carrega o dicionário de estados do arquivo JSON."""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            try:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
                else:
                    logging.error("O arquivo de estados não contém um dicionário válido. Reiniciando estados.")
                    return {}
            except json.JSONDecodeError:
                logging.error("Erro ao decodificar o arquivo de estados. Recriando o arquivo.")
                return {}
    else:
        logging.info("Arquivo de estados não encontrado. Criando novo.")
        return {}

def save_states(states):
    """Salva o dicionário de estados no arquivo JSON."""
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(states, f, indent=4)
        logging.info("Estados salvos com sucesso.")
    except Exception as e:
        logging.error(f"Erro ao salvar os estados: {e}")

class ultraChatBot():
    def __init__(self, message_data):
        self.message = message_data
        raw_chat_id = message_data.get('from')
        if raw_chat_id and not raw_chat_id.startswith("whatsapp:+"):
            raw_chat_id = f"whatsapp:+{raw_chat_id}"
        self.chatID = raw_chat_id
        self.states = load_states()

    def send_message(self, chatID, text):
        return send_message_ultramsg(chatID, text)

    def send_greeting(self):
        greeting = "Olá! Bem-vindo à nossa loja de celulares."
        self.send_message(self.chatID, greeting)

    def send_options(self):
        options = (
            "Como podemos te ajudar? Por favor, escolha uma das opções abaixo:\n"
            "1️⃣ - 📱 Comprar um aparelho\n"
            "2️⃣ - 🔧 Assistência Técnica\n"
            "3️⃣ - 👨‍💼 Falar com um atendente\n"
            "4️⃣ - ❌ Sair"
        )
        self.send_message(self.chatID, options)

    def greet_and_ask_options(self):
        """ Inicia o fluxo de conversa, setando o estado para 'ASKED_OPTION'. """
        self.send_greeting()
        self.send_options()
        self.states[self.chatID] = {'state': 'ASKED_OPTION', 'last_interaction': time.time()}
        save_states(self.states)

    # ----------------------------------------------------------------
    #                      COMPRAR APARELHO
    # ----------------------------------------------------------------

    def handle_buy_device(self):
        question = (
            "Qual modelo de celular você está procurando? "
            "Por favor, digite o nome do modelo ou parte dele (exemplo: iPhone 12)."
        )
        self.send_message(self.chatID, question)
        self.states[self.chatID]['state'] = 'ASKED_MODEL_NAME'
        self.states[self.chatID]['last_interaction'] = time.time()
        save_states(self.states)

    def handle_model_search(self, model_name):
        """ Busca o modelo no arquivo Excel 'Produtos_Lacrados.xlsx' e lista as opções. """
        try:
            df = pd.read_excel('Produtos_Lacrados.xlsx')
            df.columns = df.columns.str.strip()  # Remove espaços extras nos nomes das colunas

            # Filtra as colunas necessárias
            df = df[['Produto', 'Preço (R$)', 'Cor', 'Detalhe']]

            # Adiciona uma coluna "Estado" com base na coluna "Detalhe"
            df['Estado'] = df['Detalhe'].apply(lambda x: 'Lacrado' if pd.isna(x) else f"Seminovo ({x})")

            # Filtra os produtos que contêm o termo buscado
            resultados = df[df['Produto'].str.contains(model_name, case=False, na=False)]

            if not resultados.empty:
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
                self.send_message(self.chatID, "Desculpe, não encontramos esse produto em nosso estoque.")
        except Exception as e:
            logging.error(f"Erro ao acessar a planilha: {e}")
            self.send_message(self.chatID, "Desculpe, ocorreu um erro ao buscar os produtos disponíveis.")

    def handle_model_number_choice(self, choice):
        """ Recebe a opção numérica do aparelho, ou N, M, S. """
        choice = choice.strip().upper()
        if choice == 'N':
            self.handle_buy_device()
        elif choice == 'M':
            self.send_options()
            self.states[self.chatID]['state'] = 'ASKED_OPTION'
            self.states[self.chatID]['last_interaction'] = time.time()
            save_states(self.states)
        elif choice == 'S':
            self.send_message(self.chatID, "Obrigado pelo contato. Se precisar de algo, estamos à disposição!")
            self.states[self.chatID]['state'] = 'FINISHED'
            self.states[self.chatID]['pause_start_time'] = time.time()
            save_states(self.states)
        else:
            try:
                choice_num = int(choice)
                produtos = self.states[self.chatID].get('produtos', [])
                if 1 <= choice_num <= len(produtos):
                    produto_escolhido = produtos[choice_num - 1]

                    # SALVA o produto escolhido para depois gerar PDF
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

    # ----------------------------------------------------------------
    #                       FORMA DE PAGAMENTO
    # ----------------------------------------------------------------

    def handle_confirm_purchase(self, choice):
        """Usuário confirma (ou não) a compra do aparelho."""
        choice = choice.strip().upper()
        if choice in ['SIM', '✅', 'SIM']:
            # Em vez de pedir nome/CPF agora, perguntamos a forma de pagamento
            self.send_message(self.chatID, "Escolha a forma de pagamento:\n"
                                           "1️⃣ - Cartão de Crédito (Com a taxa da maquina)\n"
                                           "2️⃣ - PIX/Dinheiro (Com desconto)\n"
                                           "3️⃣ - Dar um aparelho usado como parte do pagamento")
            self.states[self.chatID]['state'] = 'ASKED_PAYMENT_METHOD'
            self.states[self.chatID]['last_interaction'] = time.time()
            save_states(self.states)
        elif choice in ['NÃO', 'NAO', '❌']:
            self.send_message(self.chatID, "Tudo bem! Se precisar de algo mais, estamos à disposição.")
            self.states[self.chatID]['state'] = 'FINISHED'
            self.states[self.chatID]['pause_start_time'] = time.time()
            save_states(self.states)
        else:
            self.send_message(self.chatID, "Desculpe, não entendi. Responda com 'Sim' ou 'Não'.")

    def handle_payment_method(self, user_message):
        """Usuário escolhe 1 - Cartão, 2 - PIX, 3 - Usado."""
        choice = user_message.strip()
        if choice == '1':
            self.states[self.chatID]['payment_method'] = 'CARTAO'
            self.send_message(self.chatID, "Você selecionou Cartão de Crédito. Haverá uma taxa adicional da maquininha.")
            # Agora coletar dados pessoais
            self.send_message(self.chatID, "Por favor, informe seus dados para finalizar:")
            self.send_message(self.chatID, "NOME COMPLETO:")
            self.states[self.chatID]['state'] = 'ASKED_NAME'
            save_states(self.states)

        elif choice == '2':
            self.states[self.chatID]['payment_method'] = 'PIX_DINHEIRO'
            self.send_message(self.chatID, "Você selecionou PIX/Dinheiro. Você terá um desconto especial.")
            self.send_message(self.chatID, "Por favor, informe seus dados para finalizar:")
            self.send_message(self.chatID, "NOME COMPLETO:")
            self.states[self.chatID]['state'] = 'ASKED_NAME'
            save_states(self.states)

        elif choice == '3':
            self.states[self.chatID]['payment_method'] = 'USADO'
            self.send_message(self.chatID, "Perfeito! Precisamos de algumas informações do aparelho que você vai entregar.")
            self.send_message(self.chatID, "Qual o modelo do aparelho usado?")
            self.states[self.chatID]['state'] = 'ASKED_USED_PHONE_MODEL'
            save_states(self.states)
        else:
            self.send_message(self.chatID, "Opção inválida. Selecione 1, 2 ou 3 por favor.")

    # --------------------
    #   APARELHO USADO
    # --------------------

    def handle_used_phone_model(self, user_message):
        self.states[self.chatID]['used_phone_model'] = user_message
        self.send_message(self.chatID, "Qual o armazenamento do aparelho (ex: 64GB, 128GB)?")
        self.states[self.chatID]['state'] = 'ASKED_USED_PHONE_STORAGE'
        save_states(self.states)

    def handle_used_phone_storage(self, user_message):
        self.states[self.chatID]['used_phone_storage'] = user_message
        self.send_message(self.chatID, "Como está a bateria do aparelho? (ex: Boa, Ruim, Saúde X%)")
        self.states[self.chatID]['state'] = 'ASKED_USED_PHONE_BATTERY'
        save_states(self.states)

    def handle_used_phone_battery(self, user_message):
        self.states[self.chatID]['used_phone_battery'] = user_message
        self.send_message(self.chatID, "O Face ID está funcionando? (Sim / Não)")
        self.states[self.chatID]['state'] = 'ASKED_USED_PHONE_FACEID'
        save_states(self.states)

    def handle_used_phone_faceid(self, user_message):
        self.states[self.chatID]['used_phone_faceid'] = user_message
        self.send_message(self.chatID, "Há algum defeito, tela trincada ou algo parecido? Se sim, descreva. Se não, digite 'Não'.")
        self.states[self.chatID]['state'] = 'ASKED_USED_PHONE_DEFECTS'
        save_states(self.states)

    def handle_used_phone_defects(self, user_message):
        self.states[self.chatID]['used_phone_defects'] = user_message
        self.send_message(self.chatID, "Obrigado! Agora, como você deseja pagar a diferença?\n"
                                       "1️⃣ - Cartão de Crédito (Com a taxa da maquina)\n"
                                       "2️⃣ - PIX/Dinheiro")
        self.states[self.chatID]['state'] = 'ASKED_COMPLEMENT_PAYMENT_METHOD'
        save_states(self.states)

    def handle_complement_payment_method(self, user_message):
        choice = user_message.strip()
        if choice == '1':
            self.states[self.chatID]['payment_complement'] = 'CARTAO'
            self.send_message(self.chatID, "Você escolheu pagar o restante no Cartão de Crédito. Haverá uma taxa adicional da maquininha.")
            # Agora coletar dados pessoais
            self.send_message(self.chatID, "Por favor, informe seus dados para finalizar:")
            self.send_message(self.chatID, "NOME COMPLETO:")
            self.states[self.chatID]['state'] = 'ASKED_NAME'
            save_states(self.states)

        elif choice == '2':
            self.states[self.chatID]['payment_complement'] = 'PIX_DINHEIRO'
            self.send_message(self.chatID, "Você escolheu PIX/Dinheiro para o restante. Ok!")
            # Agora coletar dados pessoais
            self.send_message(self.chatID, "Por favor, informe seus dados para finalizar:")
            self.send_message(self.chatID, "NOME COMPLETO:")
            self.states[self.chatID]['state'] = 'ASKED_NAME'
            save_states(self.states)

        else:
            self.send_message(self.chatID, "Opção inválida. Selecione 1 ou 2, por favor.")

    # ----------------------------------------------------------------
    #              COLETA DE DADOS PESSOAIS E GERA RECIBO
    # ----------------------------------------------------------------

    def collect_client_data(self, user_message):
        """ Lida com as perguntas: nome, CPF, telefone, endereço etc., até gerar o recibo. """
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

            # 1) Calcula o valor final (taxas, desconto, etc.)
            self.calculate_final_price()

            # 2) Gera PDF
            self.generate_receipt()

            # 3) Marca o estado como FINALIZADO
            self.states[self.chatID]['state'] = 'FINISHED'

        save_states(self.states)

    def calculate_final_price(self):
        """Calcula o valor final com base na forma de pagamento e apar. usado."""
        client_data = self.states[self.chatID]
        product = client_data.get('produto_escolhido', {})
        preco_base = float(product.get('Preço (R$)', 0))

        payment_method = client_data.get('payment_method')  # 'CARTAO', 'PIX_DINHEIRO', 'USADO'
        payment_complement = client_data.get('payment_complement')  # se 'USADO'
        
        # EXEMPLOS (ajuste conforme planilhas reais)
        taxa_cartao = 0.05      # 5% de taxa
        desconto_pix = 0.10     # 10% de desconto
        used_phone_value = 0.0  # valor de troca do aparelho usado (exemplo)

        if payment_method == 'CARTAO':
            preco_final = preco_base * (1 + taxa_cartao)

        elif payment_method == 'PIX_DINHEIRO':
            preco_final = preco_base * (1 - desconto_pix)

        elif payment_method == 'USADO':
            # Exemplo fixo de valor de troca
            used_phone_value = 400.0
            preco_base -= used_phone_value
            if preco_base < 0:
                preco_base = 0

            # Verifica se ele ainda precisa pagar complemento em CARTAO ou PIX
            if payment_complement == 'CARTAO':
                preco_final = preco_base * (1 + taxa_cartao)
            elif payment_complement == 'PIX_DINHEIRO':
                preco_final = preco_base * (1 - desconto_pix)
            else:
                preco_final = preco_base  # fallback
        else:
            preco_final = preco_base  # fallback

        # Armazena para gerar o PDF
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
                <div><strong>Cliente:</strong> <span>{client_data.get('name')}</span></div>
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
                {"<p><strong>Forma de Pagamento Complementar:</strong> " + payment_complement + "</p>" if payment_method == "USADO" else ""}
                {f"<p><strong>Valor de troca do aparelho usado:</strong> R$ {valor_troca_usado}</p>" if valor_troca_usado else ""}
                <p><strong>Valor Final (após taxas/descontos):</strong> R$ {valor_final}</p>
            </div>

            <div class="footer">
                <p>Obrigado pela sua compra!</p>
                <p>Loja Exemplo</p>
            </div>
        </body>
        </html>
        """

        pdf_file = f"{self.chatID}_receipt.pdf"
        HTML(string=html_content).write_pdf(pdf_file)

        self.send_message(self.chatID, "Aqui está o seu recibo!")
        send_message_ultramsg(self.chatID, f"file://{os.path.abspath(pdf_file)}")

    # ----------------------------------------------------------------
    #              ASSISTÊNCIA TÉCNICA
    # ----------------------------------------------------------------

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
    
    def handle_tech_option_choice(self, choice):
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

    def handle_phone_model(self, model_name):
        service_type = self.states[self.chatID].get('service_type')
        if not service_type:
            self.send_message(self.chatID, "Desculpe, ocorreu um erro. Vamos começar novamente.")
            self.handle_technical_assistance_options()
            return

        try:
            df = pd.read_excel('reparo_iphones.xlsx')
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

    def handle_service_confirmation(self, confirmation):
        confirmation = confirmation.strip().upper()
        if confirmation in ['SIM', '✅']:
            self.send_message(self.chatID, "Obrigado! Seu serviço foi agendado. Nossa equipe entrará em contato para mais detalhes.")
            self.states[self.chatID]['state'] = 'FINISHED'
            self.states[self.chatID]['pause_start_time'] = time.time()
            save_states(self.states)
        elif confirmation in ['NÃO', 'NAO', '❌']:
            self.send_message(self.chatID, "Tudo bem! Se precisar de algo mais, estamos à disposição.")
            self.states[self.chatID]['state'] = 'FINISHED'
            self.states[self.chatID]['pause_start_time'] = time.time()
            save_states(self.states)
        else:
            self.send_message(self.chatID, "Desculpe, não entendi. Por favor, responda com 'Sim' ou 'Não'.")

    def handle_problem_description(self, description):
        self.send_message(self.chatID, "Obrigado por nos informar. Nossa equipe técnica irá analisar e entraremos em contato com o orçamento em breve.")
        self.states[self.chatID]['state'] = 'FINISHED'
        self.states[self.chatID]['pause_start_time'] = time.time()
        save_states(self.states)

    # ----------------------------------------------------------------
    #                      FALAR COM ATENDENTE
    # ----------------------------------------------------------------

    def handle_talk_to_agent(self):
        message = "Um de nossos atendentes entrará em contato com você em breve."
        self.send_message(self.chatID, message)
        self.states[self.chatID]['state'] = 'WAITING_FOR_AGENT'
        self.states[self.chatID]['pause_start_time'] = time.time()
        save_states(self.states)

    # ----------------------------------------------------------------
    #              PROCESSAMENTO PRINCIPAL DE ENTRADA
    # ----------------------------------------------------------------

    def Processing_incoming_messages(self):
        user_message = self.message.get('body', '').strip()
        if not user_message:
            self.send_message(self.chatID, "Desculpe, não entendi sua mensagem.")
            return

        # Se não houver histórico de estado, inicia o fluxo
        if self.chatID not in self.states:
            self.greet_and_ask_options()
            return

        state_info = self.states[self.chatID]
        state = state_info.get('state')

        # 1) Menu Principal
        if state == 'ASKED_OPTION':
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
            else:
                self.send_message(self.chatID, "Opção inválida. Por favor, selecione uma das opções enviadas.")

        # 2) Busca modelo para compra
        elif state == 'ASKED_MODEL_NAME':
            self.handle_model_search(user_message)

        # 3) Escolhendo o número do modelo
        elif state == 'ASKED_MODEL_NUMBER':
            self.handle_model_number_choice(user_message)

        # 4) Confirmando a compra
        elif state == 'CONFIRM_PURCHASE':
            self.handle_confirm_purchase(user_message)

        # 5) Forma de pagamento principal
        elif state == 'ASKED_PAYMENT_METHOD':
            self.handle_payment_method(user_message)

        # 6) Aparelho usado
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

        # 7) Forma de pagamento do complemento (depois do usado)
        elif state == 'ASKED_COMPLEMENT_PAYMENT_METHOD':
            self.handle_complement_payment_method(user_message)

        # 8) Coleta de dados pessoais para finalizar (nome, CPF, ...)
        elif state.startswith('ASKED_'):
            # Lida com 'ASKED_NAME', 'ASKED_CPF', 'ASKED_PHONE', etc.
            self.collect_client_data(user_message)

        # 9) Assistência Técnica
        elif state == 'ASKED_TECH_OPTION':
            self.handle_tech_option_choice(user_message)
        elif state == 'ASKED_PHONE_MODEL':
            self.handle_phone_model(user_message)
        elif state == 'ASKED_SERVICE_CONFIRMATION':
            self.handle_service_confirmation(user_message)
        elif state == 'ASKED_PROBLEM_DESCRIPTION':
            self.handle_problem_description(user_message)

        # 10) Esperando atendente
        elif state == 'WAITING_FOR_AGENT':
            self.send_message(self.chatID, "Por favor, aguarde. Um atendente entrará em contato em breve.")

        # 11) Finalizado
        elif state == 'FINISHED':
            self.send_message(self.chatID, "Olá novamente! Como podemos te ajudar?")
            self.send_options()
            self.states[self.chatID]['state'] = 'ASKED_OPTION'
            self.states[self.chatID]['last_interaction'] = time.time()
            save_states(self.states)

        # 12) Fallback (estado desconhecido)
        else:
            self.send_message(self.chatID, "Desculpe, ocorreu um erro. Vamos começar novamente.")
            self.greet_and_ask_options()
