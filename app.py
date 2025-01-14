from flask import Flask, request, jsonify, render_template
import logging
import json
import os
import time
import pandas as pd
import atexit
from apscheduler.schedulers.background import BackgroundScheduler

# Importe do ultrabot
from ultrabot import load_states, save_states, send_message_ultramsg, ultraChatBot

app = Flask(__name__)

# Configuração de logging
logging.basicConfig(level=logging.INFO)

# Caminho para o arquivo de status do bot
STATUS_FILE = 'bot_status.json'

# Função para carregar o status do bot
def load_bot_status():
    """Carrega o status do bot de um arquivo JSON. Se não existir, retorna False (desativado)."""
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE, 'r') as f:
                data = json.load(f)
                return data.get("active", False)
        except Exception as e:
            logging.error(f"Erro ao carregar status do bot: {e}")
    return False  # Default: desativado

# Função para salvar o status do bot
def save_bot_status(is_active: bool):
    """Salva o status do bot em um arquivo JSON."""
    try:
        with open(STATUS_FILE, 'w') as f:
            json.dump({"active": is_active}, f)
    except Exception as e:
        logging.error(f"Erro ao salvar status do bot: {e}")

# Inicializa o status do bot ao iniciar
bot_active = load_bot_status()

# Função para verificar conversas inativas
def check_inactive_conversations():
    try:
        states = load_states()
        current_time = time.time()

        for chatID, state_info in list(states.items()):
            last_interaction = state_info.get('last_interaction', current_time)
            state = state_info.get('state', '')
            pause_start_time = state_info.get('pause_start_time', None)

            # Se inativo por mais de 20 min, mas menos de 30 min, enviar aviso
            if 20 * 60 <= current_time - last_interaction < 30 * 60 and state != 'WARNING_SENT':
                send_message_ultramsg(
                    chatID,
                    "Estamos verificando se você ainda está aí! Sua sessão será encerrada em 30 minutos por inatividade. "
                    "Se precisar continuar, por favor, envie uma mensagem."
                )
                states[chatID]['state'] = 'WARNING_SENT'
                save_states(states)

            # Se inativo por mais de 30 min e não está em SESSION_ENDED
            elif current_time - last_interaction >= 30 * 60 and state != 'SESSION_ENDED':
                send_message_ultramsg(
                    chatID,
                    "Sua sessão foi encerrada por inatividade. "
                    "Se precisar de algo, por favor, envie uma nova mensagem para iniciar um novo atendimento."
                )
                states[chatID]['state'] = 'SESSION_ENDED'
                states[chatID]['pause_start_time'] = time.time()
                save_states(states)

            # Remove estados SESSION_ENDED há mais de 24 horas
            if state == 'SESSION_ENDED' and pause_start_time and current_time - pause_start_time > 24 * 60 * 60:
                del states[chatID]

        save_states(states)

    except Exception as e:
        logging.error(f"Erro ao verificar conversas inativas: {e}")

# Configuração do agendador para conversas inativas
scheduler = BackgroundScheduler()
scheduler.add_job(func=check_inactive_conversations, trigger="interval", seconds=60)
scheduler.start()

atexit.register(lambda: scheduler.shutdown())

##############################################################################
# Rotas para Página de Controle
##############################################################################

@app.route('/index.html')
def index():
    """Renderiza o HTML de controle do bot (ativar/desativar e upload Excel)."""
    return render_template('index.html')

@app.route('/status', methods=['GET', 'POST'])
def bot_status():
    """Retorna ou altera o estado do bot."""
    global bot_active
    if request.method == 'POST':
        bot_active = not bot_active
        save_bot_status(bot_active)  # Salva o estado no arquivo
        return jsonify({'active': bot_active})
    elif request.method == 'GET':
        return jsonify({'active': bot_active})

@app.route('/upload', methods=['POST'])
def upload_excel():
    """Recebe upload de arquivo Excel e sobrescreve excel/Produtos_Lacrados.xlsx."""
    if 'arquivo' not in request.files:
        return jsonify({'message': 'Nenhum arquivo enviado.'}), 400
    
    file = request.files['arquivo']
    if file.filename == '':
        return jsonify({'message': 'Nome de arquivo vazio.'}), 400

    # Caminho para salvar na pasta excel/
    save_path = os.path.join('excel', 'Produtos_Lacrados.xlsx')
    
    # Salva (sobrescreve) o arquivo
    file.save(save_path)

    logging.info(f"Planilha atualizada: {save_path}")
    return jsonify({'message': 'Planilha atualizada com sucesso!'}), 200

# Rota que retorna a lista de conversas atuais
@app.route('/conversations', methods=['GET'])
def get_conversations():
    states = load_states()
    conversation_list = []

    for chat_id, st in states.items():
        conversation_list.append({
            'chatID': chat_id,
            'agentMode': st.get('agent_mode', False),  # se não existir, default False
            'state': st.get('state', '')  # Adiciona o estado
        })
    return jsonify(conversation_list), 200

# Rota para alterar se a conversa está ou não em modo atendente
@app.route('/toggle_conversation', methods=['POST'])
def toggle_conversation():
    data = request.json
    chat_id = data.get('chatID')
    agent_mode = data.get('agentMode')  # true ou false

    if not chat_id:
        return jsonify({'error': 'chatID não fornecido'}), 400

    states = load_states()
    if chat_id not in states:
        return jsonify({'error': 'Conversa não encontrada'}), 404

    # Atualiza o estado
    states[chat_id]['agent_mode'] = agent_mode
    save_states(states)
    return jsonify({'success': True}), 200

##############################################################################
# Webhook principal do UltraMsg
##############################################################################

@app.route('/', methods=['POST'])
def webhook():
    global bot_active
    if not bot_active:
        # Se o bot está desativado, devolve 403
        return jsonify({'error': 'Bot está desativado'}), 403

    try:
        json_data = request.get_json()
        logging.info(f"Dados recebidos: {json_data}")

        if not json_data:
            logging.error("Nenhum dado JSON recebido.")
            return jsonify({'error': 'Nenhum dado recebido'}), 400

        if 'event_type' not in json_data or json_data['event_type'] != 'message_received':
            logging.error("Evento inválido ou ausente.")
            return jsonify({'error': 'Evento inválido'}), 400

        if 'data' not in json_data or not json_data['data']:
            logging.error("Faltando 'data' no JSON recebido.")
            return jsonify({'error': 'Faltando data no JSON'}), 400

        result = json_data['data']
        user_message = result.get('body')
        sender = result.get('from')

        # ------ NÃO RESPONDER GRUPO ------
        # Se for grupo (contém '@g.us'), ignorar
        if sender.endswith('@g.us'):
            logging.info(f"Mensagem de grupo recebida ({sender}). Ignorando.")
            return jsonify({'status': 'ignorado', 'reason': 'mensagem de grupo'}), 200
        # ----------------------------------

        if not user_message or not sender:
            logging.error("Faltando 'sender' ou 'body' nos dados recebidos.")
            return jsonify({'error': 'Faltando sender ou body nos dados'}), 400

        # Monta o objeto de mensagem
        message_data = {
            'body': user_message,
            'from': sender
        }

        # Processa a mensagem no bot
        bot = ultraChatBot(message_data)
        response = bot.Processing_incoming_messages()
        return jsonify({'status': 'sucesso', 'response': response}), 200

    except Exception as e:
        logging.error(f"Ocorreu um erro no webhook: {e}")
        return jsonify({'error': 'Erro interno do servidor'}), 500

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
