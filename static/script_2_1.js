const socket = io();

// Берём переменные из глобального объекта window
const room = window.room;
const session_id = window.session_id;

// Сообщаем серверу о входе
socket.emit("join_room", { room: room, session_id: session_id });

// Обработка событий от сервера
socket.on("update_player_count", data => {
  console.log("Игроков в комнате:", data.count);
});

socket.on("joined", data => {
  console.log(data.message);
});
