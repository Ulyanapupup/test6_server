let selectedRole = null;  // роль, которую выбрал этот игрок
let rolesTaken = {};      // роли, которые уже выбраны другими

const socket = io();

// Берём переменные из глобального объекта window
const room = window.room;
const session_id = window.session_id;

// Сообщаем серверу о входе
socket.emit("join_room", { room: window.room, session_id: window.session_id });

// Получаем обновления о занятых ролях от сервера
socket.on("roles_update", data => {
  rolesTaken = data.roles; // объект вида {guesser: 'session_id1', creator: 'session_id2'}
  updateRoleButtons();
  checkStartEnabled();
});

// Подтверждение начала игры
socket.on("game_started", () => {
  console.log("Игра началась!");
  alert("Игра началась!");
});

// Обработка событий от сервера
socket.on("update_player_count", data => {
  console.log("Игроков в комнате:", data.count);
});

socket.on("joined", data => {
  console.log(data.message);
});

// Функция выбора роли
function chooseRole(role) {
  if (rolesTaken[role] && rolesTaken[role] !== window.session_id) {
    alert("Эта роль уже занята!");
    return;
  }
  selectedRole = role;
  socket.emit("choose_role", { room: window.room, session_id: window.session_id, role: role });
  updateRoleButtons();
  checkStartEnabled();
}

// Обновляем кнопки: блокируем занятые роли, выделяем выбранную
function updateRoleButtons() {
  const guesserBtn = document.getElementById("role-guesser");
  const creatorBtn = document.getElementById("role-creator");

  // Блокируем кнопки занятых ролей (если заняты не нами)
  guesserBtn.disabled = rolesTaken.guesser && rolesTaken.guesser !== window.session_id;
  creatorBtn.disabled = rolesTaken.creator && rolesTaken.creator !== window.session_id;

  // Подсветка выбранной роли
  guesserBtn.style.backgroundColor = (selectedRole === "guesser") ? "lightgreen" : "";
  creatorBtn.style.backgroundColor = (selectedRole === "creator") ? "lightgreen" : "";
}

// Кнопка "Играть" активна только если обе роли заняты разными игроками
function checkStartEnabled() {
  const startBtn = document.getElementById("start-game");
  const bothRolesTaken = rolesTaken.guesser && rolesTaken.creator;
  const differentPlayers = bothRolesTaken && (rolesTaken.guesser !== rolesTaken.creator);
  startBtn.disabled = !(bothRolesTaken && differentPlayers);
}

// Кнопка "Играть" — отправляем событие серверу, что готовы стартовать игру
function startGame() {
  if (!selectedRole) {
    alert("Выберите роль!");
    return;
  }
  socket.emit("start_game", { room: window.room });
}
