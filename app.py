import eventlet
eventlet.monkey_patch()

import os
import uuid
import random
import string
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_socketio import SocketIO, send, join_room, leave_room, emit

# Импортируем логику игры
from game_logic import mode_1_1
from game_logic.mode_1_2 import Game  # импорт класса Game из mode_1_2

app = Flask(__name__)
app.secret_key = 'some_secret_key'  # для сессий
socketio = SocketIO(app, cors_allowed_origins="*")

games = {}  # хранилище активных игр для режима 1.2: {game_id: Game}

# Добавим поле для хранения выбранных ролей в каждой комнате
# rooms = {
#   'ROOMCODE': {
#       'players': set(session_ids),
#       'creator': session_id,
#       'mode': None,
#       'roles': {session_id: 'угадывающий' / 'отгадывающий'}
#   }
# }

rooms = {}

def generate_session_id():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=16))

@app.before_request
def make_session_permanent():
    if 'session_id' not in session:
        new_id = generate_session_id()
        session['session_id'] = new_id
        print(f'Создан новый session_id: {new_id}')
    else:
        print(f'Существующий session_id: {session["session_id"]}')


# --- Маршруты ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/room_setup')
def room_setup():
    return render_template('room_setup.html')

@app.route('/game/<mode>')
def game_mode(mode):
    if mode == '1.1':
        return render_template('game_mode_1_1.html')
    elif mode == '1.2':
        return render_template('game_mode_1_2.html')
    elif mode in ['2.1', '2.2']:
        return render_template('room_setup.html', mode=mode)
    else:
        return "Неизвестный режим", 404

@app.route('/select_range_1_2')
def select_range_1_2():
    return render_template('range_select_1_2.html')

@app.route('/game_mode_1_2')
def game_mode_1_2():
    range_param = request.args.get('range', '0_100')
    try:
        min_range, max_range = map(int, range_param.split('_'))
    except ValueError:
        min_range, max_range = 0, 100
    return render_template('game_mode_1_2.html', min_range=min_range, max_range=max_range)


# Запуск игры 1.2 — создание новой игры
@app.route('/start_game_1_2', methods=['POST'])
def start_game_1_2():
    data = request.json
    secret = int(data.get('secret'))
    min_range = int(data.get('min_range'))
    max_range = int(data.get('max_range'))

    game_id = str(uuid.uuid4())
    games[game_id] = Game(secret, min_range, max_range)
    first_question = games[game_id].next_question()
    return jsonify({'game_id': game_id, 'question': first_question})

# Обработка ответа в игре 1.2
@app.route('/answer_1_2', methods=['POST'])
def answer_1_2():
    data = request.json
    game_id = data.get('game_id')
    answer = data.get('answer')

    game = games.get(game_id)
    if not game:
        return jsonify({'error': 'Игра не найдена'}), 404

    response = game.process_answer(answer)

    done = getattr(game, 'finished', False)

    return jsonify({'response': response, 'done': done})

# Обработка вопросов для режимов 1.1 и 1.2
@app.route('/ask', methods=['POST'])
def ask():
    question = request.json.get("question", "")
    mode = request.json.get("mode", "1.1")
    if mode == "1.1":
        answer = mode_1_1.process_question(question)
    elif mode == "1.2":
        answer_yes = request.json.get("answer") == "да"
        game_id = request.json.get("game_id")
        game = games.get(game_id)
        if not game:
            return jsonify({"answer": "Игра не найдена"})
        game.filter_numbers(question, answer_yes)
        answer = ", ".join(map(str, game.get_possible_numbers()))
    else:
        answer = "Неподдерживаемый режим"

    return jsonify({"answer": answer})

# Новый роут /game для сетевой игры с комнатой
@app.route('/game')
def game():
    room = request.args.get('room', '').upper()
    print(f"Запрос /game с комнатой: '{room}'")
    if not room:
        print("Комната не указана, редирект на /room_setup")
        return redirect(url_for('room_setup'))

    if 'session_id' not in session:
        new_id = generate_session_id()
        session['session_id'] = new_id
        print(f'Создан новый session_id: {new_id}')

    session_id = session['session_id']
    print(f"Используем session_id: {session_id}")

    if room not in rooms:
        print(f"Создаем новую комнату: {room}")
        rooms[room] = {
            'players': set(),
            'creator': session_id,
            'mode': None
        }

    rooms[room]['players'].add(session_id)
    player_count = len(rooms[room]['players'])
    is_creator = (session_id == rooms[room]['creator'])

    print(f"Комната {room}, игроков: {player_count}, is_creator: {is_creator}")

    return render_template('game.html', room=room, player_count=player_count, is_creator=is_creator)

# WebSocket обработчики

@socketio.on('join_room')
def on_join(data):
    room = data['room']
    session_id = data['session_id']

    if room not in rooms:
        rooms[room] = {
            'players': set(),
            'creator': session_id,
            'mode': None,
            'roles': {}
        }
    players = rooms[room]['players']
    roles = rooms[room]['roles']

    if len(players) >= 2 and session_id not in players:
        emit('error', {'message': 'Комната заполнена, вход запрещен.'}, to=request.sid)
        return

    join_room(room)
    players.add(session_id)

    # 👉 Здесь лог в консоль сервера — видно, сколько игроков после присоединения
    print(f"Игрок {session_id} присоединился к комнате {room}. Всего игроков: {len(players)}")

    # 👉 Обновляем количество игроков всем
    emit('update_player_count', {'count': len(players)}, to=room)

    # 👉 Отправляем текущие роли всем
    emit('roles_update', {'roles': roles}, to=room)

    # 👉 Приветствие — только подключившемуся
    emit('joined', {'message': f'Вы подключились к комнате {room}.'}, to=request.sid)

@socketio.on('choose_role')
def on_choose_role(data):
    room = data['room']
    session_id = data['session_id']
    chosen_role = data['role']  # Ожидаем 'угадывающий' или 'отгадывающий'

    if room not in rooms:
        emit('error', {'message': 'Комната не найдена'})
        return

    roles = rooms[room].setdefault('roles', {})

    # Проверяем, занята ли уже эта роль кем-то другим
    if chosen_role in roles.values():
        emit('role_chosen_response', {'success': False, 'message': f'Роль "{chosen_role}" уже занята.'})
        return

    # Сохраняем роль за игроком
    roles[session_id] = chosen_role

    # Оповещаем всех в комнате об обновлении ролей
    emit('roles_update', {'roles': roles}, room=room)

    emit('role_chosen_response', {'success': True, 'role': chosen_role})
    
@socketio.on('start_game')
def on_start_game(data):
    room = data['room']

    if room not in rooms:
        emit('error', {'message': 'Комната не найдена'})
        return

    roles = rooms[room].get('roles', {})

    # Проверяем, что в комнате 2 игрока и обе роли выбраны и разные
    if len(roles) < 2:
        emit('start_game_response', {'success': False, 'message': 'Ожидается выбор ролей обоими игроками.'})
        return

    chosen_roles = set(roles.values())
    if chosen_roles != {'угадывающий', 'отгадывающий'}:
        emit('start_game_response', {'success': False, 'message': 'Роли должны быть разными.'})
        return

    # Для теста выводим в консоль
    print(f"Игра в комнате {room} началась! Роли: {roles}")

    emit('start_game_response', {'success': True, 'message': 'Игра началась!'}, room=room)

@app.route('/game_mode_2_1')
def game_mode_2_1():
    room = request.args.get('room')
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    return render_template('game_mode_2_1.html', room=room, session_id=session['session_id'])


@app.route('/game_mode_2_2')
def game_mode_2_2():
    room = request.args.get('room')
    return render_template('game_mode_2_2.html', room=room)

@socketio.on('choose_mode')
def handle_choose_mode(data):
    room = data['room']
    mode = data['mode']
    
    # Сохраним выбранный режим, если нужно
    if room in rooms:
        rooms[room]['mode'] = mode

    # Отправим всем в комнате событие, кроме отправителя
    emit('mode_chosen', {'room': room, 'mode': mode}, to=room)


@socketio.on('disconnect')
def on_disconnect():
    session_id = session.get('session_id')
    if not session_id:
        return

    for room, data in list(rooms.items()):
        if session_id in data['players']:
            data['players'].remove(session_id)
            leave_room(room)  # Игрок покидает комнату Socket.IO

            # Обновляем всех игроков в комнате о количестве
            emit('update_player_count', {'count': len(data['players'])}, room=room)

            # Если в комнате никого не осталось — удаляем её из словаря
            if len(data['players']) == 0:
                del rooms[room]
            break

# Простой WebSocket обработчик сообщений (можно убрать/настроить)
@socketio.on('message')
def handle_message(msg):
    send(msg, broadcast=True)


if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
