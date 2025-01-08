from flask import Flask, request, jsonify, render_template
import logging
import json
from ultrabot import load_states, save_states, send_message_ultramsg, ultraChatBot
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
import time
import pandas as pd

app = Flask(__name__)

# Variável global para controle do estado do bot
bot_active = False

# Configuração de logging
logging.basicConfig(level=logging.INFO)

# Função para verificar conversas inativas
def check_inactive_conversations():
    try:
        states = load_states()
        current_time = time.time()
        for chatID, state_info in list(states.items()):
            last_interaction = state_info.get('last_interaction', current_time)
            if current_time - last_interaction > 10 * 60 and state_info['state'] != 'SESSION_ENDED':
                send_message_ultramsg(
                    chatID,
                    "Sua sessão foi encerrada por inatividade. Se precisar de algo, por favor, envie uma nova mensagem para iniciar um novo atendimento."
                )
                states[chatID]['state'] = 'SESSION_ENDED'
                states[chatID]['pause_start_time'] = time.time()
        save_states(states)
    except Exception as e:
        logging.error(f"Erro ao verificar conversas inativas: {e}")

# Configuração do agendador para conversas inativas
scheduler = BackgroundScheduler()
scheduler.add_job(func=check_inactive_conversations, trigger="interval", seconds=60)
scheduler.start()

atexit.register(lambda: scheduler.shutdown())

# Rota para servir o arquivo HTML de controle
@app.route('/index.html')
def index():
    return render_template('index.html')

# Endpoint para ativar/desativar o bot
@app.route('/status', methods=['POST'])
def toggle_status():
    global bot_active
    bot_active = not bot_active
    return jsonify({'active': bot_active})

# Webhook principal para processamento de mensagens
@app.route('/', methods=['POST'])
def webhook():
    global bot_active
    if not bot_active:
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

        if not user_message or not sender:
            logging.error("Faltando 'sender' ou 'body' nos dados recebidos.")
            return jsonify({'error': 'Faltando sender ou body nos dados'}), 400

        message_data = {
            'body': user_message,
            'from': sender
        }

        bot = ultraChatBot(message_data)
        response = bot.Processing_incoming_messages()
        return jsonify({'status': 'sucesso', 'response': response}), 200

    except Exception as e:
        logging.error(f"Ocorreu um erro no webhook: {e}")
        return jsonify({'error': 'Erro interno do servidor'}), 500

# Inicialização do servidor Flask
if __name__ == '__main__':
    app.run(debug=True)
from flask import Flask, request, jsonify, render_template
import logging
import json
from ultrabot import load_states, save_states, send_message_ultramsg, ultraChatBot
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
import time
import pandas as pd

app = Flask(__name__)

# Variável global para controle do estado do bot
bot_active = False

# Configuração de logging
logging.basicConfig(level=logging.INFO)

# Função para verificar conversas inativas
def check_inactive_conversations():
    try:
        states = load_states()
        current_time = time.time()
        for chatID, state_info in list(states.items()):
            last_interaction = state_info.get('last_interaction', current_time)
            if current_time - last_interaction > 10 * 60 and state_info['state'] != 'SESSION_ENDED':
                send_message_ultramsg(
                    chatID,
                    "Sua sessão foi encerrada por inatividade. Se precisar de algo, por favor, envie uma nova mensagem para iniciar um novo atendimento."
                )
                states[chatID]['state'] = 'SESSION_ENDED'
                states[chatID]['pause_start_time'] = time.time()
        save_states(states)
    except Exception as e:
        logging.error(f"Erro ao verificar conversas inativas: {e}")

# Configuração do agendador para conversas inativas
scheduler = BackgroundScheduler()
scheduler.add_job(func=check_inactive_conversations, trigger="interval", seconds=60)
scheduler.start()

atexit.register(lambda: scheduler.shutdown())

# Rota para servir o arquivo HTML de controle
@app.route('/index.html')
def index():
    return render_template('index.html')

# Endpoint para ativar/desativar o bot
@app.route('/status', methods=['POST'])
def toggle_status():
    global bot_active
    bot_active = not bot_active
    return jsonify({'active': bot_active})

# Webhook principal para processamento de mensagens
@app.route('/', methods=['POST'])
def webhook():
    global bot_active
    if not bot_active:
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

        if not user_message or not sender:
            logging.error("Faltando 'sender' ou 'body' nos dados recebidos.")
            return jsonify({'error': 'Faltando sender ou body nos dados'}), 400

        message_data = {
            'body': user_message,
            'from': sender
        }

        bot = ultraChatBot(message_data)
        response = bot.Processing_incoming_messages()
        return jsonify({'status': 'sucesso', 'response': response}), 200

    except Exception as e:
        logging.error(f"Ocorreu um erro no webhook: {e}")
        return jsonify({'error': 'Erro interno do servidor'}), 500

# Inicialização do servidor Flask
if __name__ == '__main__':
    app.run(debug=False)
