from flask import Flask, request, jsonify, render_template
import logging
import json
import os
import time
import pandas as pd
import atexit
from apscheduler.schedulers.background import BackgroundScheduler

# Importe do seu ultrabot
from ultrabot import load_states, save_states, send_message_ultramsg,  ultraChatBot

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
                    "Sua sessão foi encerrada por inatividade. "
                    "Se precisar de algo, por favor, envie uma nova mensagem para iniciar um novo atendimento."
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

##############################################################################
# Rotas para Página de Controle
##############################################################################

@app.route('/index.html')
def index():
    """Renderiza o HTML de controle do bot (ativar/desativar e upload Excel)."""
    return render_template('index.html')

@app.route('/status', methods=['POST'])
def toggle_status():
    """Ativa/Desativa o bot_global. Se desativado, webhook retorna 403."""
    global bot_active
    bot_active = not bot_active
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

    # Aqui você pode fazer backup do antigo, se quiser.
    logging.info(f"Planilha atualizada: {save_path}")
    return jsonify({'message': 'Planilha atualizada com sucesso!'}), 200

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

if __name__ == '__main__':
    # Rode preferencialmente em 0.0.0.0 e port=5000 (ou 80 se quiser root).
    app.run(debug=False, host='0.0.0.0', port=5000)
