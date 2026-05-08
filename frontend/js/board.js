/**
 * board.js — chessboard.js wrapper
 * Hỗ trợ: drag-drop (desktop) + tap-to-move (mobile)
 */

const BoardManager = (() => {
  let _board       = null;
  let _chess       = null;
  let _myColor     = 'white';
  let _onMoveCb    = null;
  let _flipped     = false;
  let _isMyTurn    = false;
  let _highlighted = [];

  // Tap-to-move state
  let _selectedSq  = null;   // ô đang chọn (lần tap đầu)
  let _legalDests  = [];     // ô hợp lệ từ ô đang chọn
  let _disableDrag = false;  // cờ tạm tắt drag khi vừa click-to-move

  const PIECE_THEME = 'assets/img/chesspieces/wikipedia/{piece}.png';

  // ── Detect mobile ──────────────────────────────────────────────────
  const isMobile = () => window.innerWidth <= 768 || ('ontouchstart' in window);

  // ── Board size ─────────────────────────────────────────────────────
  function _calcBoardSize() {
    if (isMobile()) {
      // Mobile: chiều rộng màn hình trừ padding
      return Math.min(window.innerWidth - 24, 480);
    }
    // Desktop: 45% màn hình, tối đa 520px
    return Math.min(window.innerWidth * 0.45, 520);
  }

  // ── Highlight helpers ──────────────────────────────────────────────
  function _clearHighlights() {
    _highlighted.forEach(sq =>
      $(`#chessboard .square-${sq}`)
        .removeClass('highlight-from highlight-to highlight-legal highlight-selected')
    );
    _highlighted = [];
  }

  function _mark(sq, cls) {
    $(`#chessboard .square-${sq}`).addClass(cls);
    _highlighted.push(sq);
  }

  function _showLegalDots(moves) {
    moves.forEach(m => _mark(m.to, 'highlight-legal'));
  }

  // ── Drag handlers (desktop) ────────────────────────────────────────
  function _onDragStart(source, piece) {
    if (!_isMyTurn || isMobile() || _disableDrag) return false;
    const isW = piece.startsWith('w');
    if (_myColor === 'white' && !isW) return false;
    if (_myColor === 'black' &&  isW) return false;

    // Nếu đang chọn một ô khác và click vào một ô hợp lệ (để capture), thì không bắt đầu kéo
    // Mà nhường cho sự kiện click xử lý ăn quân
    if (_selectedSq && _legalDests.find(m => m.to === source)) {
        return false;
    }

    _clearHighlights();
    _selectedSq = source;
    _mark(source, 'highlight-from');
    const legal = _chess.moves({ square: source, verbose: true });
    _legalDests = legal;
    _showLegalDots(legal);
    return true;
  }

  function _onDrop(source, target, piece) {
    if (source === target) {
        // User clicked but didn't drag. Giữ nguyên highlight để tap-to-move xử lý cú click tiếp theo.
        return 'snapback';
    }
    
    _clearHighlights();
    _selectedSq = null;
    _legalDests = [];

    const moves    = _chess.moves({ square: source, verbose: true });
    const matched  = moves.find(m => m.from === source && m.to === target);
    if (!matched) return 'snapback';

    let uci = source + target;
    if (matched.flags.includes('p')) uci += 'q';

    const result = _chess.move({ from: source, to: target, promotion: 'q' });
    if (!result) return 'snapback';

    _mark(source, 'highlight-from');
    _mark(target, 'highlight-to');
    if (_onMoveCb) _onMoveCb(uci);
    return undefined;
  }

  function _onSnapEnd() {
    if (_board && _chess) _board.position(_chess.fen(), false);
  }

  // ── Tap-to-move (mobile + desktop click) ──────────────────────────
  function _onSquareClick(square) {
    if (!_isMyTurn) return;

    const piece = _chess.get(square);
    const isMyPiece = piece &&
      ((_myColor === 'white' && piece.color === 'w') ||
       (_myColor === 'black' && piece.color === 'b'));

    // Chưa chọn ô nào → chọn quân của mình
    if (_selectedSq === null) {
      if (!isMyPiece) return;
      _clearHighlights();
      _selectedSq = square;
      _mark(square, 'highlight-selected');
      _legalDests = _chess.moves({ square, verbose: true });
      _showLegalDots(_legalDests);
      return;
    }

    // Đã chọn ô → tap lần 2
    if (square === _selectedSq) {
      // Tap lại ô cũ → bỏ chọn
      _clearHighlights();
      _selectedSq = null;
      _legalDests = [];
      return;
    }

    if (isMyPiece) {
      // Tap quân khác của mình → chuyển chọn
      _clearHighlights();
      _selectedSq = square;
      _mark(square, 'highlight-selected');
      _legalDests = _chess.moves({ square, verbose: true });
      _showLegalDots(_legalDests);
      return;
    }

    // Tap ô đích → thử đi
    const matched = _legalDests.find(m => m.to === square);
    if (!matched) {
      // Ô không hợp lệ → bỏ chọn
      _clearHighlights();
      _selectedSq = null;
      _legalDests = [];
      return;
    }

    // Di chuyển hợp lệ!
    let uci = _selectedSq + square;
    if (matched.flags.includes('p')) uci += 'q';

    const from = _selectedSq;
    _chess.move({ from, to: square, promotion: 'q' });
    _board.position(_chess.fen(), true);

    _clearHighlights();
    _mark(from,   'highlight-from');
    _mark(square, 'highlight-to');
    _selectedSq = null;
    _legalDests = [];

    // Chống dính chuột với chessboard.js khi click-to-move thành công
    _disableDrag = true;
    setTimeout(() => _disableDrag = false, 100);

    if (_onMoveCb) _onMoveCb(uci);
  }

  // ── Init ───────────────────────────────────────────────────────────
  function init(color, onMove) {
    _myColor   = color;
    _onMoveCb  = onMove;
    _chess     = new Chess();
    _flipped   = (color === 'black');
    _selectedSq = null;
    _legalDests = [];

    // Set container width before init
    const size = _calcBoardSize();
    $('#board-container').css('width', size + 'px');

    _board = Chessboard('chessboard', {
      draggable:         !isMobile(),   // drag chỉ trên desktop
      position:          'start',
      orientation:       _flipped ? 'black' : 'white',
      pieceTheme:        PIECE_THEME,
      onDragStart:       _onDragStart,
      onDrop:            _onDrop,
      onSnapEnd:         _onSnapEnd,
      moveSpeed:         'fast',
      snapbackSpeed:     300,
      snapSpeed:         80,
    });

    if (isMobile()) {
      $('#chessboard').addClass('tap-mode');
    }

    // Lắng nghe sự kiện click chung trên toàn board
    $('#chessboard').on('click', function(e) {
      let square = null;
      const target = $(e.target);
      
      if (target.hasClass('square-55d63')) {
        square = target.attr('data-square');
      } else if (target.hasClass('piece-417db')) {
        square = target.attr('data-square');
      } else {
        square = target.closest('.square-55d63').attr('data-square');
      }
      
      if (square) {
        _onSquareClick(square);
      }
    });

    // Responsive resize
    let resizeTimer;
    window.addEventListener('resize', () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => {
        const s = _calcBoardSize();
        $('#board-container').css('width', s + 'px');
        if (_board) _board.resize();
      }, 150);
    });
  }

  function updatePosition(fen) {
    if (!_board) return;
    _chess.load(fen);
    _board.position(fen, true);
    // Reset tap state nếu server update FEN
    _clearHighlights();
    _selectedSq = null;
    _legalDests = [];
  }

  function setMyTurn(val) {
    _isMyTurn = val;
    if (!val) {
      _clearHighlights();
      _selectedSq = null;
      _legalDests = [];
    }
  }

  function flip() {
    if (_board) { _board.flip(); _flipped = !_flipped; }
  }

  function highlightMove(from, to) {
    _clearHighlights();
    _mark(from, 'highlight-from');
    _mark(to,   'highlight-to');
  }

  function getChess() { return _chess; }

  return { init, updatePosition, setMyTurn, flip, highlightMove, getChess };
})();

// ── Highlight styles ───────────────────────────────────────────────────
(function injectStyles() {
  const style = document.createElement('style');
  style.textContent = `
    .highlight-selected { background-color: rgba(124,58,237,0.65) !important; }
    .highlight-from     { background-color: rgba(124,58,237,0.45) !important; }
    .highlight-to       { background-color: rgba(245,158,11,0.55) !important; }
    .highlight-legal    { position: relative; cursor: pointer; }
    .highlight-legal::after {
      content: '';
      position: absolute;
      top: 50%; left: 50%;
      transform: translate(-50%, -50%);
      width: 32%; height: 32%;
      background: rgba(34,197,94,0.7);
      border-radius: 50%;
      pointer-events: none;
      z-index: 5;
    }
    /* Touch-friendly: bigger tap targets on mobile */
    @media (max-width: 768px) {
      .square-55d63 { touch-action: manipulation; cursor: pointer; }
    }
    /* In tap-mode (mobile), pieces pass clicks through to the squares behind them */
    #chessboard.tap-mode .piece-417db {
      pointer-events: none !important;
    }
  `;
  document.head.appendChild(style);
})();
