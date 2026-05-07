/**
 * main.js — Socket.IO client + UI controller
 * Modules: Auth, UI, Lobby, Game, Toast
 */

// ── State ──────────────────────────────────────────────────────────────
const State = {
  token:       localStorage.getItem('trc_token') || null,
  username:    localStorage.getItem('trc_username') || null,
  roomId:      null,
  myColor:     null,   // 'white' | 'black' | 'spectator'
  currentTurn: null,
  gameActive:  false,
  pendingDraw: false,
};

// ── Socket ─────────────────────────────────────────────────────────────
const socket = io(CONFIG.API_URL, { transports: ['websocket'], autoConnect: true });

// ── Toast ──────────────────────────────────────────────────────────────
const Toast = {
  show(msg, type = 'info', duration = 3500) {
    const el = document.createElement('div');
    el.className = `toast toast-${type}`;
    el.textContent = msg;
    document.getElementById('toast-container').appendChild(el);
    setTimeout(() => el.remove(), duration);
  },
  info(m)    { this.show(m, 'info'); },
  success(m) { this.show(m, 'success'); },
  warn(m)    { this.show(m, 'warn', 4500); },
  error(m)   { this.show(m, 'error', 5000); },
};

// ── UI helper ──────────────────────────────────────────────────────────
const UI = {
  showScreen(id) {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    document.getElementById(`screen-${id}`).classList.add('active');
  },
  showModal(id)  { document.getElementById(`modal-${id}`).classList.add('show'); },
  hideModal(id)  { document.getElementById(`modal-${id}`).classList.remove('show'); },
  showTab(tab) {
    document.getElementById('form-login').style.display    = tab === 'login'    ? '' : 'none';
    document.getElementById('form-register').style.display = tab === 'register' ? '' : 'none';
    document.getElementById('tab-login').classList.toggle('active',    tab === 'login');
    document.getElementById('tab-register').classList.toggle('active', tab === 'register');
  },
  setStatus(msg, cls = '') {
    const bar = document.getElementById('status-bar');
    bar.textContent = msg;
    bar.className   = cls;
  },
  fmtClock(sec) {
    sec = Math.max(0, Math.floor(sec));
    const m = String(Math.floor(sec / 60)).padStart(2, '0');
    const s = String(sec % 60).padStart(2, '0');
    return `${m}:${s}`;
  },
  updateClock(elId, sec) {
    const el = document.getElementById(elId);
    if (!el) return;
    el.textContent = this.fmtClock(sec);
    el.classList.toggle('urgent', sec < 30);
  },
};

// ── Auth ───────────────────────────────────────────────────────────────
const Auth = {
  async login(e) {
    e.preventDefault();
    const username = document.getElementById('login-username').value.trim();
    const password = document.getElementById('login-password').value;
    document.getElementById('login-error').textContent = '';

    const res = await fetch(`${CONFIG.API_URL}/api/login`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    const data = await res.json();
    if (!res.ok) { document.getElementById('login-error').textContent = data.error; return; }

    this._saveSession(data.token, data.username);
    Lobby.show();
  },

  async register(e) {
    e.preventDefault();
    const username = document.getElementById('reg-username').value.trim();
    const password = document.getElementById('reg-password').value;
    document.getElementById('reg-error').textContent = '';

    const res = await fetch(`${CONFIG.API_URL}/api/register`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    const data = await res.json();
    if (!res.ok) { document.getElementById('reg-error').textContent = data.error; return; }

    this._saveSession(data.token, data.username);
    Lobby.show();
  },

  _saveSession(token, username) {
    State.token = token; State.username = username;
    localStorage.setItem('trc_token', token);
    localStorage.setItem('trc_username', username);
    document.getElementById('user-info').textContent = `👤 ${username}`;
    document.getElementById('user-info').style.display = '';
    document.getElementById('btn-logout').style.display = '';
  },

  logout() {
    State.token = State.username = null;
    localStorage.removeItem('trc_token'); localStorage.removeItem('trc_username');
    document.getElementById('user-info').style.display = 'none';
    document.getElementById('btn-logout').style.display = 'none';
    UI.showScreen('auth');
  },
};

document.getElementById('btn-logout').addEventListener('click', () => Auth.logout());

// ── Lobby ──────────────────────────────────────────────────────────────
const Lobby = {
  show() {
    if (!State.token) { UI.showScreen('auth'); return; }
    // Rời phòng hiện tại (nếu có) trước khi về sảnh
    if (State.roomId) {
      socket.emit('leave_room', { room_id: State.roomId, token: State.token });
      State.roomId    = null;
      State.myColor   = null;
      State.gameActive = false;
    }
    UI.hideModal('game-over'); // <--- FIX: Ensure modal is hidden
    UI.showScreen('lobby');
    this.refresh();
  },

  async refresh() {
    const res  = await fetch(`${CONFIG.API_URL}/api/rooms`);
    const list = await res.json();
    const el   = document.getElementById('rooms-list');
    if (!list.length) {
      el.innerHTML = `<div class="empty-state"><div class="icon">♟</div><div>Chưa có phòng nào. Hãy tạo phòng mới!</div></div>`;
      return;
    }
    el.innerHTML = list.map(r => `
      <div class="room-card card">
        <div class="room-card-info">
          <div class="room-card-id">🏠 ${r.room_id}</div>
          <div class="room-card-meta">
            ${Object.values(r.players).map(p => p.username).join(' vs ') || 'Đang chờ...'}
            · ${Math.floor(r.time_control / 60)} phút
          </div>
        </div>
        <button class="btn btn-primary btn-sm" onclick="Lobby.joinRoom('${r.room_id}')">Vào phòng</button>
      </div>
    `).join('');
  },

  async createRoom() {
    const tc  = parseInt(document.getElementById('time-control-select').value);
    const res = await fetch(`${CONFIG.API_URL}/api/rooms`, {
      method: 'POST', headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${State.token}`,
      },
      body: JSON.stringify({ time_control: tc }),
    });
    const data = await res.json();
    if (!res.ok) { Toast.error(data.error); return; }
    Toast.success(`Đã tạo phòng ${data.room_id}`);
    this.joinRoom(data.room_id);
  },

  joinByCode() {
    const code = document.getElementById('room-id-input').value.trim().toUpperCase();
    if (!code) { Toast.warn('Nhập mã phòng trước'); return; }
    this.joinRoom(code);
  },

  joinRoom(roomId) {
    State.roomId = roomId;
    socket.emit('join', { room_id: roomId, token: State.token });
  },
};

// ── Game ───────────────────────────────────────────────────────────────
const Game = {
  _moveHistory: [],
  _plyCount:    0,

  init(snapshot, myColor, roomInfo) {
    State.myColor    = myColor;
    State.gameActive = false;
    this._moveHistory = snapshot.move_history || [];
    this._plyCount    = snapshot.ply || 0;

    UI.showScreen('game');

    BoardManager.init(myColor, uci => this.sendMove(uci));

    if (snapshot.fen && snapshot.fen !== 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1') {
      BoardManager.updatePosition(snapshot.fen);
    }

    // Determine isHost
    let isHost = false;
    if (roomInfo && roomInfo.host_id) {
      const hostP = Object.values(roomInfo.players).find(p => p.user_id === roomInfo.host_id);
      if (hostP && hostP.username === State.username) {
        isHost = true;
      }
    }
    Game._isHost = isHost;

    if (roomInfo && roomInfo.started === false) {
      if (Object.keys(roomInfo.players).length === 2) {
        document.getElementById('ready-overlay').style.display = 'flex';
        document.getElementById('ready-host').style.display = isHost ? 'block' : 'none';
        document.getElementById('ready-guest').style.display = !isHost ? 'block' : 'none';
      } else {
        document.getElementById('ready-overlay').style.display = 'none';
      }
    } else {
      document.getElementById('ready-overlay').style.display = 'none';
    }

    // Tải thông tin người chơi (self/opp cards)
    if (myColor === 'spectator') {
      const wPlayer = roomInfo && roomInfo.players && roomInfo.players['white'];
      const bPlayer = roomInfo && roomInfo.players && roomInfo.players['black'];
      
      if (wPlayer) {
        document.getElementById('self-name').textContent  = wPlayer.username;
        document.getElementById('self-avatar').textContent = wPlayer.username[0].toUpperCase();
        document.getElementById('self-color-badge').textContent = 'Trắng ♔';
      } else {
        document.getElementById('self-name').textContent  = 'Chờ người chơi...';
        document.getElementById('self-avatar').textContent = '?';
        document.getElementById('self-color-badge').textContent = '';
      }
      
      if (bPlayer) {
        document.getElementById('opp-name').textContent   = bPlayer.username;
        document.getElementById('opp-avatar').textContent = bPlayer.username[0].toUpperCase();
        document.getElementById('opp-color-badge').textContent = 'Đen ♚';
      } else {
        document.getElementById('opp-name').textContent   = 'Chờ người chơi...';
        document.getElementById('opp-avatar').textContent = '?';
        document.getElementById('opp-color-badge').textContent = '';
      }
    } else {
      const selfColorStr = myColor === 'white' ? 'Trắng ♔' : 'Đen ♚';
      document.getElementById('self-name').textContent  = State.username;
      document.getElementById('self-avatar').textContent = State.username[0].toUpperCase();
      document.getElementById('self-color-badge').textContent = selfColorStr;

      const oppColor = myColor === 'white' ? 'black' : 'white';
      const opp = roomInfo && roomInfo.players && roomInfo.players[oppColor];
      if (opp) {
        document.getElementById('opp-name').textContent   = opp.username;
        document.getElementById('opp-avatar').textContent = opp.username[0].toUpperCase();
        document.getElementById('opp-color-badge').textContent = oppColor === 'white' ? 'Trắng ♔' : 'Đen ♚';
      } else {
        document.getElementById('opp-name').textContent   = 'Chờ đối thủ...';
        document.getElementById('opp-avatar').textContent = '?';
        document.getElementById('opp-color-badge').textContent = '';
      }
    }

    document.getElementById('info-room').textContent = State.roomId;
    document.getElementById('room-id-display').textContent = `Phòng: ${State.roomId}`;
    document.getElementById('info-ply').textContent  = this._plyCount;

    this._renderRules(snapshot.active_rules || []);
    this._renderMoves(this._moveHistory);

    UI.setStatus('Đang chờ đối thủ vào phòng...', '');

    document.getElementById('btn-resign').disabled = true;
    document.getElementById('btn-draw').disabled   = true;

    // If snapshot has pending choices for us
    if (snapshot.pending_choices && snapshot.pending_for === myColor) {
      this._showRuleModal(snapshot.pending_choices, true);
    }
  },

  sendMove(uci) {
    if (!State.gameActive) return;
    socket.emit('move', { room_id: State.roomId, uci, token: State.token });
  },

  resign() {
    if (!confirm('Bạn có chắc muốn đầu hàng?')) return;
    socket.emit('resign', { room_id: State.roomId, token: State.token });
  },

  offerDraw() {
    socket.emit('offer_draw', { room_id: State.roomId, token: State.token });
    Toast.info('Đã gửi đề nghị hòa');
    document.getElementById('btn-draw').disabled = true;
  },

  acceptDraw() {
    socket.emit('accept_draw', { room_id: State.roomId, token: State.token });
    UI.hideModal('draw-offer');
  },

  declineDraw() {
    UI.hideModal('draw-offer');
    Toast.info('Đã từ chối hòa');
  },

  flipBoard() { BoardManager.flip(); },

  startMatch() {
    const color = document.getElementById('host-color-choice').value;
    socket.emit('start_match', { room_id: State.roomId, color_choice: color, token: State.token });
  },

  rematch() {
    socket.emit('rematch', { room_id: State.roomId, token: State.token });
    UI.hideModal('game-over');
  },

  // ── Internal ────────────────────────────────────────────────────────

  _onGameStart(data) {
    State.gameActive = true;
    State.currentTurn = data.first_turn;
    document.getElementById('info-time').textContent =
      `${Math.floor(data.time_control / 60)} phút`;
    document.getElementById('btn-resign').disabled = false;
    document.getElementById('btn-draw').disabled   = false;
    this._updateTurnUI();
    Toast.success('Ván cờ bắt đầu! ♟');
  },

  _onBoardUpdate(data) {
    BoardManager.updatePosition(data.fen);
    State.currentTurn = data.next_turn;
    this._plyCount = data.ply;
    document.getElementById('info-ply').textContent = data.ply;

    // moveHistory is updated in the socket listener

    this._renderRules(data.active_rules || []);
    this._updateTurnUI();

    if (data.game_over) {
      State.gameActive = false;
      BoardManager.setMyTurn(false);
    }
  },

  _updateTurnUI() {
    const isMyTurn = (State.currentTurn === State.myColor);
    BoardManager.setMyTurn(isMyTurn);

    const selfId = `card-self`;
    const oppId  = `card-opponent`;
    document.getElementById(selfId).classList.toggle('active-turn',  isMyTurn);
    document.getElementById(oppId).classList.toggle('active-turn',  !isMyTurn);

    if (isMyTurn) {
      UI.setStatus('🎯 Lượt của bạn', 'your-turn');
    } else {
      UI.setStatus('⏳ Chờ đối thủ...', 'opp-turn');
    }
  },

  _renderRules(activeRules) {
    const el = document.getElementById('active-rules-list');
    const container = document.getElementById('board-container');
    if (!activeRules.length) {
      el.innerHTML = '<div class="no-rules">Chưa có luật nào</div>';
      container.classList.remove('has-active-rules');
      return;
    }
    container.classList.add('has-active-rules');
    const icons = ['⚡','🔥','❄️','🌀','⚔️','🛡️','🌪️','💀','🔮','🎲'];
    el.innerHTML = activeRules.map((r, i) => {
      const remaining = r.expires_at - this._plyCount;
      const expiring  = remaining <= 3;
      return `
        <div class="rule-badge${expiring ? ' expiring' : ''}">
          <div class="rule-badge-icon">${icons[i % icons.length]}</div>
          <div class="rule-badge-body">
            <div class="rule-badge-name">${r.name}</div>
            <div class="rule-badge-ply">Còn ${remaining} nước · ${r.description}</div>
          </div>
        </div>`;
    }).join('');
  },

  _renderMoves(history) {
    const el = document.getElementById('move-list');
    if (!history.length) { el.innerHTML = ''; return; }
    el.innerHTML = history.map((uci, i) => {
      const isLast = i === history.length - 1;
      return `<span class="move-entry${isLast ? ' last-move' : ''}">${uci}</span>`;
    }).join('');
    el.scrollTop = el.scrollHeight;
  },

  _showRuleModal(choices, isMine) {
    document.getElementById('rule-modal-subtitle').textContent = isMine
      ? 'Bạn vừa đi nước thứ 3 — hãy chọn 1 luật muốn kích hoạt:'
      : 'Đối thủ đang chọn luật...';

    const icons = ['⚡','🔥','❄️','🌀','🎲'];
    const container = document.getElementById('rule-choices-container');

    if (!isMine) {
      container.innerHTML = '<div style="text-align:center;color:var(--text-2);padding:1rem">⏳ Đang chờ đối thủ chọn...</div>';
    } else {
      container.innerHTML = choices.map((r, i) => `
        <div class="rule-choice-card" id="choice-${r.id}" onclick="Game._chooseRule('${r.id}')">
          <div class="rule-icon">${icons[i % icons.length]}</div>
          <div>
            <div class="rule-choice-name">${r.name}</div>
            <div class="rule-choice-desc">${r.description}</div>
          </div>
        </div>`).join('');
    }
    UI.showModal('rule-select');
  },

  _chooseRule(ruleId) {
    socket.emit('choose_rule', { room_id: State.roomId, rule_id: ruleId, token: State.token });
    UI.hideModal('rule-select');
  },

  _showGameOver(data) {
    State.gameActive = false;
    BoardManager.setMyTurn(false);

    const banner = document.getElementById('result-banner');
    const emoji  = document.getElementById('result-emoji');
    const text   = document.getElementById('result-text');
    const reason = document.getElementById('result-reason');

    const reasonMap = {
      normal: 'Kết thúc bình thường',
      resign: 'Đối thủ đầu hàng',
      timeout: 'Hết giờ',
      agreement: 'Đồng thuận hòa',
    };

    if (data.result === 'draw') {
      banner.className = 'result-banner draw';
      emoji.textContent = '🤝'; text.textContent = 'Hòa cờ!';
    } else if (data.result === State.myColor) {
      banner.className = 'result-banner win';
      emoji.textContent = '🏆'; text.textContent = 'Bạn thắng!';
    } else {
      banner.className = 'result-banner lose';
      emoji.textContent = '😔'; text.textContent = 'Bạn thua!';
    }
    reason.textContent = reasonMap[data.reason] || '';
    UI.showModal('game-over');
  },
};

// ── Socket event handlers ──────────────────────────────────────────────

socket.on('connect', () => {
  document.getElementById('conn-dot').className   = 'connected';
  document.getElementById('conn-label').textContent = 'Đã kết nối';
});

socket.on('disconnect', () => {
  document.getElementById('conn-dot').className   = 'disconnected';
  document.getElementById('conn-label').textContent = 'Mất kết nối';
});

socket.on('error', data => Toast.error(data.message || 'Lỗi không xác định'));

socket.on('joined', data => {
  Toast.success(`Đã vào phòng ${data.room_id} — Bạn đi ${data.color === 'white' ? 'Trắng ♔' : 'Đen ♚'}`);
  Game.init(data.snapshot, data.color, data.room_info);
});

socket.on('joined_as_spectator', data => {
  Toast.info('Bạn đang xem với tư cách khán giả');
  Game.init(data.snapshot, 'spectator', data.room_info);
});

socket.on('opponent_joined', data => {
  const oppColor = data.color === 'white' ? 'Trắng ♔' : 'Đen ♚';
  document.getElementById('opp-name').textContent   = data.username;
  document.getElementById('opp-avatar').textContent = data.username[0].toUpperCase();
  document.getElementById('opp-color-badge').textContent = oppColor;
  Toast.info(`${data.username} đã vào phòng`);
});

socket.on('opponent_left', data => {
  Toast.warn(`${data.username} đã rời phòng`);
  document.getElementById('ready-overlay').style.display = 'none';
});

socket.on('room_ready', () => {
  document.getElementById('ready-overlay').style.display = 'flex';
  document.getElementById('ready-host').style.display = Game._isHost ? 'block' : 'none';
  document.getElementById('ready-guest').style.display = !Game._isHost ? 'block' : 'none';
});

socket.on('room_reset', data => {
  let myColor = 'spectator';
  if (data.room_info && data.room_info.players) {
    if (data.room_info.players['white']?.username === State.username) myColor = 'white';
    if (data.room_info.players['black']?.username === State.username) myColor = 'black';
  }
  Game.init(data.snapshot, myColor, data.room_info);
  UI.hideModal('game-over');
});

socket.on('match_started', data => {
  document.getElementById('ready-overlay').style.display = 'none';
  let myColor = 'spectator';
  if (data.room_info && data.room_info.players) {
    if (data.room_info.players['white']?.username === State.username) myColor = 'white';
    if (data.room_info.players['black']?.username === State.username) myColor = 'black';
  }
  Game.init(data.snapshot, myColor, data.room_info);
  Game._onGameStart(data);
});

socket.on('game_start', data => {
  Game._onGameStart(data);
});

socket.on('board_update', data => {
  // Track move history client-side from move_history via snapshot or ply changes
  if (data.ok) {
    if (data.last_move) {
      Game._moveHistory.push(data.last_move);
    }
    Game._onBoardUpdate(data);
    Game._renderMoves(data.move_history || Game._moveHistory);

    if (data.side_effects && data.side_effects.length) {
      data.side_effects.forEach(rid => {
        const ruleNames = { ghost_pawn:'Tốt Ma', pawn_storm:'Bão Tốt', earthquake:'Động Đất',
                            lucky_pawn:'Tốt May Mắn', chaos:'Hỗn Loạn', spy_rook:'Xe Gián Điệp',
                            extra_queen:'Hậu Bổ Sung', frozen_bishop:'Tượng Đóng Băng', magnet:'Nam Châm' };
        const name = ruleNames[rid] || rid;
        Toast.warn(`⚡ Luật "${name}" kích hoạt!`);
      });
    }
  }
});

socket.on('clock_update', clocks => {
  const selfColor = State.myColor;
  const oppColor  = selfColor === 'white' ? 'black' : 'white';
  if (clocks[selfColor] !== undefined) UI.updateClock('self-clock', clocks[selfColor]);
  if (clocks[oppColor]  !== undefined) UI.updateClock('opp-clock',  clocks[oppColor]);
});

socket.on('rule_trigger', data => {
  const isMe = (data.for_player === State.myColor);
  Game._showRuleModal(data.choices, isMe);
  if (isMe) Toast.warn('⚡ Chọn luật mới!');
  else       Toast.info(`⏳ ${data.for_player === 'white' ? 'Trắng' : 'Đen'} đang chọn luật...`);
});

socket.on('rule_activated', data => {
  UI.hideModal('rule-select');
  Game._renderRules(data.active_rules);
  Toast.success(`✅ Luật "${data.rule.name}" được kích hoạt bởi ${data.chosen_by === State.myColor ? 'bạn' : 'đối thủ'}!`);
  
  // Show visual banner
  const banner = document.getElementById('rule-banner');
  document.getElementById('rule-banner-title').textContent = data.rule.name;
  document.getElementById('rule-banner-desc').textContent = data.rule.description;
  banner.classList.add('show');
  setTimeout(() => banner.classList.remove('show'), 3500);
});

socket.on('game_over', data => {
  Game._showGameOver(data);
});

socket.on('draw_offered', () => {
  UI.showModal('draw-offer');
  Toast.warn('Đối thủ đề nghị hòa!');
});

// ── Bootstrap ──────────────────────────────────────────────────────────
(function boot() {
  if (State.token && State.username) {
    document.getElementById('user-info').textContent = `👤 ${State.username}`;
    document.getElementById('user-info').style.display = '';
    document.getElementById('btn-logout').style.display = '';
    Lobby.show();
  } else {
    UI.showScreen('auth');
  }
})();
