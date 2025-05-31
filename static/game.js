const socket = io();

const roomCode = window.roomCode;
const isCreator = window.isCreator;
const sessionId = window.sessionId;

socket.emit('join_room', { room: roomCode, session_id: sessionId });

socket.on('joined', (data) => {
  console.log(data.message);
  document.getElementById('status').innerText = data.message;
});

socket.on('update_player_count', (data) => {
  console.log(`Игроков в комнате: ${data.count}`);
  document.getElementById('playerCount').textContent = data.count;
});

socket.on('mode_chosen', (data) => {
  if (data.room === roomCode) {
    if (data.mode === '2.1') {
      window.location.href = `/game_mode_2_1?room=${roomCode}`;
    } else if (data.mode === '2.2') {
      window.location.href = `/game_mode_2_2?room=${roomCode}`;
    }
  }
});

socket.on('error', (data) => {
  alert(data.message);
  window.location.href = '/';
});

function chooseMode(mode) {
  if (isCreator) {
    socket.emit('choose_mode', { room: roomCode, mode: mode });
    // Переход для создателя
    if (mode === '2.1') {
      window.location.href = '/game_mode_2_1?room=' + roomCode;
    } else if (mode === '2.2') {
      window.location.href = '/game_mode_2_2?room=' + roomCode;
    }
  } else {
    alert("Только создатель комнаты может выбрать режим.");
  }
}

document.querySelectorAll("button[data-mode]").forEach(btn => {
  btn.addEventListener("click", () => {
    const mode = btn.getAttribute("data-mode");
    chooseMode(mode);
  });
});


