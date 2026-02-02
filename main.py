# -*- coding: utf-8 -*-
# 必要なライブラリをインポート（読み込み）
import pygame       # ゲーム画面を描画するライブラリ
import random       # ランダムな数値を生成（テトロミノの形を決める）
import threading    # 複数の処理を同時に実行（画面描画とネット通信を並行）
import socket       # ネットワーク通信（相手とデータ送受信）
import json         # データをJSON形式で送受信
import time         # 時間を計測
import queue        # スレッド間でデータを安全に受け渡し
import uuid         # 一意なIDを生成（接続時の識別用）

# ゲームの設定値（定数）
ROWS, COLS = 20, 15  # 盤面のサイズ（縦20行×横15列）
CELL = 20            # 1マスのサイズ（ピクセル）
# 盤面を描画する位置
BOARD_X = 20         # 左端からの距離
BOARD_Y = 90         # 上端からの距離
BUTTON_MARGIN = 10   # ボタンと盤面の間隔
WIDTH = COLS * CELL * 2 + 180   # ウィンドウの幅（2つの盤面を並べる）
# ウィンドウの高さ（盤面＋ボタンが入る高さ）
HEIGHT = BOARD_Y + ROWS * CELL + 80
FPS = 60             # 1秒間に60フレーム（60回画面を更新）

# デバッグログの表示切り替え（Trueにすると詳細なログが出る）
VERBOSE = False

# 色の定義（RGB形式: 赤Red, 緑Green, 青Blueの3つの値で色を指定）
BLACK = (0,0,0)          # 黒（背景色）
WHITE = (255,255,255)    # 白（文字色）
GREY = (50,50,50)        # 灰色（ゴミ行の色）
# テトロミノ（ブロック）の色リスト
COLORS = [(0,255,255),(0,0,255),(255,165,0),(255,255,0),(0,255,0),(128,0,128),(255,0,0)]

# テトロミノ（ブロック）の形状定義（7種類）
# 1はブロックあり、0はブロックなし
SHAPES = [
    [[1,1,1,1]],        # I字型（棒）
    [[1,1,0],[0,1,1]],  # Z字型
    [[0,1,1],[1,1,0]],  # S字型
    [[1,1,1],[1,0,0]],  # L字型
    [[1,1,1],[0,0,1]],  # J字型（逆L）
    [[1,1,1],[0,1,0]],  # T字型
    [[1,1],[1,1]]       # O字型（四角）
]

# ネットワーク通信用の補助関数

def send_json(sock, obj):
    """辞書データをJSON形式に変換して送信する関数
    
    引数:
        sock: ソケット（通信用のオブジェクト）
        obj: 送信するデータ（辞書形式）
    """
    try:
        # 辞書をJSON文字列に変換し、改行を追加（メッセージの区切り）
        data = json.dumps(obj) + '\n'
        # 文字列をバイト列に変換して送信
        sock.sendall(data.encode())
    except Exception as e:
        # エラーが起きたら表示
        print('send error', e)

class NetworkManager:
    """ネットワーク通信を管理するクラス
    
    役割:
        - 相手との接続確立（サーバー・クライアント両方の役割）
        - メッセージの送受信
        - 接続が切れたら自動で再接続
    """
    def __init__(self, local_ip, peer_ip, port, on_message, peer_port=None, role='auto'):
        """ネットワークマネージャーを初期化
        
        引数:
            local_ip: 自分のIPアドレス（待ち受け用）
            peer_ip: 相手のIPアドレス（接続先）
            port: 自分のポート番号
            on_message: メッセージを受信したときに呼ぶ関数
            peer_port: 相手のポート番号（省略時はportと同じ）
            role: 接続の役割（'auto', 'active', 'passive'）
        """
        self.local_ip = local_ip
        self.peer_ip = peer_ip
        self.port = port
        self.peer_port = peer_port if peer_port is not None else port
        self.on_message = on_message  # 受信時のコールバック関数
        # 接続の役割（auto=自動判定, active=積極的に接続, passive=待つだけ）
        self.role = role
        print('Network role:', self.role)
        # ハンドシェイク（接続確認）の状態
        self.handshake_done = False      # ハンドシェイク完了フラグ
        self.handshake_deadline = 0      # ハンドシェイクのタイムアウト時刻
        self.last_hello_sent = 0         # 最後にhelloメッセージを送った時刻
        self.hello_interval = 1.0        # helloメッセージの送信間隔（秒）
        self.sock = None                 # 現在の通信用ソケット
        self.server = None               # サーバー用ソケット（待ち受け用）
        self.client = None               # クライアント用ソケット（接続用）
        self.running = True              # 実行中フラグ
        # スレッド間でデータ競合を防ぐためのロック
        self.lock = threading.Lock()
        self.recv_thread = None          # 受信スレッド
        # 再接続の設定
        self.reconnect_delay = 1         # 再接続待機時間（秒）
        self.reconnector_started = False # 再接続スレッド開始済みフラグ
        # ハンドシェイク用の一意なID（重複接続防止）
        self.local_id = uuid.uuid4().hex
        self.peer_id = None
        # 送信キュー（メッセージを順番に送るための待ち行列）
        self.send_queue = queue.Queue()
        # 送信用のスレッドを開始（バックグラウンドで動作）
        self.sender_thread = threading.Thread(target=self.send_loop, daemon=True)
        self.sender_thread.start()
        # サーバーソケットを起動（相手からの接続を待つ）
        self.start_server()
        # 接続試行スレッドを開始（相手に接続を試みる）
        if not self.reconnector_started:
            threading.Thread(target=self.try_connect, daemon=True).start()
            self.reconnector_started = True

    def start_server(self):
        """サーバーソケットを作成し、相手からの接続を待ち受ける
        
        処理:
            1. ソケットを作成
            2. IPアドレスとポート番号に紐付け（bind）
            3. 接続待ち受け開始（listen）
            4. 別スレッドで接続受け入れ処理を開始
        """
        # TCP通信用のソケットを作成
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # ポート番号を再利用できるようにする（プログラム再起動時に便利）
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            # IPアドレスとポート番号を割り当て
            self.server.bind((self.local_ip, self.port))
            # 接続待ち受け開始（最大1件）
            self.server.listen(1)
            # 別スレッドで接続受け入れ処理を開始
            threading.Thread(target=self.accept_loop, daemon=True).start()
            print('Server listening on', self.local_ip, self.port)
        except Exception as e:
            print('Server bind error', e)

    def accept_loop(self):
        """相手からの接続を受け入れ続けるループ（別スレッドで動作）
        
        処理:
            1. accept()で接続を待つ
            2. 接続が来たらソケットを取得
            3. 既に接続済みなら新しい接続は閉じる
            4. 未接続なら新しいソケットをセット
        """
        while self.running:
            try:
                if not self.server:
                    # try to restart server socket if missing
                    try:
                        self.start_server()
                    except Exception:
                        pass
                    time.sleep(0.5)
                    continue
                conn, addr = self.server.accept()
                print('Accepted from', addr)
                try:
                    conn.settimeout(None)
                except Exception:
                    pass
                # If already connected, close the extra connection
                with self.lock:
                    if self.sock is not None:
                        try:
                            conn.close()
                        except Exception:
                            pass
                        continue
                # mark as accepted
                self.set_socket(conn, accepted=True)
                # continue loop to allow future reconnections
            except OSError as e:
                # possible server closed; try to recreate server
                print('accept OSError', e)
                try:
                    if self.server:
                        self.server.close()
                except Exception:
                    pass
                self.server = None
                time.sleep(1)
                continue
            except Exception as e:
                # don't break on transient errors; keep listening
                print('accept error', e)
                time.sleep(1)
                continue

    def try_connect(self):
        # persistent connector: keep running and attempt to connect when in active role
        while self.running:
            with self.lock:
                has_sock = (self.sock is not None)
            if has_sock:
                time.sleep(1)
                continue
            if not self.peer_ip:
                time.sleep(1)
                continue
            # role selection to avoid symmetric simultaneous connects
            try:
                # forced role: if 'passive' we never initiate outgoing connects
                if self.role == 'passive':
                    time.sleep(1)
                    continue
                # auto mode uses lexicographic ordering as before (deterministic)
                if self.role == 'auto' and self.local_ip and self.peer_ip and self.local_ip >= self.peer_ip:
                    # passive by lexicographic order: wait for incoming connection
                    time.sleep(1)
                    continue
                # if role == 'active', proceed with connect attempts immediately
            except Exception:
                pass
            s = None
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(3)
                s.connect((self.peer_ip, self.peer_port))
                try:
                    print('try_connect: connected socket fileno', s.fileno(), 'to', self.peer_ip, self.peer_port, flush=True)
                except Exception:
                    print('try_connect: connected to peer', self.peer_ip, self.peer_port, flush=True)
                try:
                    s.settimeout(None)
                except Exception:
                    pass
                # only set socket if none exists
                need_set = False
                with self.lock:
                    if self.sock is None:
                        need_set = True
                if need_set:
                    try:
                        print('try_connect: setting socket outside lock for fileno', s.fileno(), flush=True)
                        self.set_socket(s, accepted=False)
                        print('try_connect: set_socket returned for fileno', s.fileno(), flush=True)
                    except Exception as e:
                        print('try_connect: set_socket raised', e, flush=True)
                        try:
                            s.close()
                        except Exception:
                            pass
                else:
                    try:
                        s.close()
                    except Exception:
                        pass
                # reset backoff on success
                self.reconnect_delay = 1
                print('try_connect: socket set or closed, reconnect_delay reset', flush=True)
            except Exception as e:
                # failed to connect; close socket and retry later with backoff
                try:
                    if s:
                        s.close()
                except Exception:
                    pass
                print('try_connect exception:', e)
                time.sleep(self.reconnect_delay)
                # exponential backoff up to 10s
                self.reconnect_delay = min(10, self.reconnect_delay * 2)
                continue

    def close_socket(self):
        with self.lock:
            try:
                if self.sock:
                    try:
                        self.sock.shutdown(socket.SHUT_RDWR)
                    except Exception:
                        pass
                    try:
                        self.sock.close()
                    except Exception:
                        pass
                    self.sock = None
            except Exception:
                self.sock = None
        # reset peer relationship
        try:
            self.peer_id = None
        except Exception:
            pass
        # reset handshake
        try:
            self.handshake_done = False
        except Exception:
            pass
        # increase reconnect delay slightly
        self.reconnect_delay = min(10, max(1, self.reconnect_delay))
        print('Socket closed')

    def send_json_socket(self, sock, obj):
        try:
            data = json.dumps(obj) + '\n'
            sock.sendall(data.encode())
            try:
                fid = sock.fileno()
            except Exception:
                fid = None
            # suppress state messages unless verbose
            if obj.get('type') != 'state' or VERBOSE:
                print('send_json_socket: sent', obj.get('type'), 'on', fid, flush=True)
        except Exception as e:
            print('send_json_socket failed', e, flush=True)
            try:
                sock.close()
            except Exception:
                pass

    def send_now(self, obj):
        """Attempt to send immediately if handshake completed and socket present. Returns True if sent."""
        with self.lock:
            s = self.sock
            ok = self.handshake_done and s is not None
        if not ok:
            return False
        try:
            self.send_json_socket(s, obj)
            return True
        except Exception as e:
            print('send_now failed', e, flush=True)
            try:
                self.close_socket()
            except Exception:
                pass
            return False

    def set_socket(self, s, accepted=False):
        print('set_socket: entry fileno', getattr(s,'fileno',lambda:None)(), 'accepted', accepted, flush=True)
        # set a new socket safely, closing any previous one
        try:
            s.settimeout(None)
        except Exception:
            pass
        with self.lock:
            # if there is an existing socket, close it first
            if self.sock is not None:
                try:
                    self.sock.shutdown(socket.SHUT_RDWR)
                except Exception:
                    pass
                try:
                    self.sock.close()
                except Exception:
                    pass
                self.sock = None
            self.sock = s
            # reset backoff
            self.reconnect_delay = 1
            # reset handshake state for this socket
            self.handshake_done = False
            self.handshake_deadline = time.time() + 5
            self.last_hello_sent = 0
            # start receiver thread for this socket
            self.recv_thread = threading.Thread(target=self.recv_loop, daemon=True)
            self.recv_thread.start()
            # log socket info
            try:
                peer = s.getpeername()
            except Exception:
                peer = None
            print(f'set_socket: accepted={accepted} fileno={s.fileno()} peer={peer}', flush=True)
            # send immediate hello handshake on this socket (direct send only; avoid enqueueing extra hellos)
            try:
                # use direct socket send to ensure handshake goes via this connection
                self.send_json_socket(s, {'type':'hello','id': self.local_id})
                self.last_hello_sent = time.time()
                self.handshake_deadline = time.time() + 5
                print('Sent hello on sock', s.fileno(), self.local_id[:8], flush=True)
            except Exception as e:
                print('failed to send hello on sock', e, flush=True)
            # start a small helper to retry hello a few times if handshake hasn't completed
            def _hello_retry(sock_ref, start_fileno):
                retries = 0
                delay = self.hello_interval
                while retries < 3 and self.running:
                    time.sleep(delay)
                    with self.lock:
                        if self.handshake_done:
                            return
                        # ensure socket still same
                        if self.sock is not sock_ref:
                            return
                    try:
                        self.send_json_socket(sock_ref, {'type':'hello','id': self.local_id})
                        self.last_hello_sent = time.time()
                        print('hello retry sent on', start_fileno, 'retry', retries+1, flush=True)
                    except Exception as e:
                        print('hello retry failed', e, flush=True)
                        return
                    retries += 1
                    delay *= 2
            try:
                threading.Thread(target=_hello_retry, args=(s, s.fileno()), daemon=True).start()
            except Exception:
                pass

    def recv_loop(self):
        buffer = ''
        while self.running:
            with self.lock:
                s = self.sock
            if not s:
                time.sleep(0.1)
                continue
            try:
                data = s.recv(4096)
                if not data:
                    # remote side closed connection; close and mark None
                    print('Connection closed by peer')
                    try:
                        self.close_socket()
                    except Exception:
                        pass
                    break
                # debug: bytes received
                try:
                    if VERBOSE:
                        print('recv_loop: received', len(data), 'bytes on sock', s.fileno(), flush=True)
                except Exception:
                    if VERBOSE:
                        print('recv_loop: received bytes', flush=True)
                buffer += data.decode(errors='ignore')
                while '\n' in buffer:
                    line, buffer = buffer.split('\n',1)
                    try:
                        msg = json.loads(line)
                        # handshake messages handled here
                        mt = msg.get('type')
                        if mt == 'hello':
                            pid = msg.get('id')
                            if pid:
                                self.peer_id = pid
                                print('Received hello from', pid[:8], 'on sock', s.fileno(), flush=True)
                                # send explicit ack back so the other side can confirm handshake
                                try:
                                    self.send_json_socket(s, {'type':'hello_ack','id': self.local_id})
                                    print('Sent hello_ack on sock', s.fileno(), flush=True)
                                except Exception as e:
                                    print('hello_ack send failed', e, flush=True)
                                # handshake marked done locally
                                self.handshake_done = True
                                self.last_hello_sent = time.time()
                            continue
                        if mt == 'hello_ack':
                            pid = msg.get('id')
                            if pid:
                                self.peer_id = pid
                                print('Received hello_ack from', pid[:8], 'on sock', s.fileno(), flush=True)
                                self.handshake_done = True
                                self.last_hello_sent = time.time()
                            continue
                        if mt == 'close':
                            print('Peer requested close on sock', s.fileno())
                            try:
                                # close this specific socket
                                try:
                                    s.shutdown(socket.SHUT_RDWR)
                                except Exception:
                                    pass
                                try:
                                    s.close()
                                except Exception:
                                    pass
                                # if this was the active socket, clear it
                                with self.lock:
                                    if self.sock is s:
                                        self.sock = None
                            except Exception:
                                pass
                            continue
                        # otherwise forward to application handler
                        try:
                            self.on_message(msg)
                        except Exception as e:
                            print('on_message error', e)
                    except Exception as e:
                        print('json parse error', e)
            except socket.timeout:
                # temporary timeout; continue
                continue
            except OSError as e:
                # socket errors (e.g., operation on non-socket) - close and let connector retry
                print('recv error', e)
                try:
                    self.close_socket()
                except Exception:
                    pass
                break
            except Exception as e:
                print('recv error', e)
                try:
                    self.close_socket()
                except Exception:
                    pass
                break

    def send_loop(self):
        while self.running:
            try:
                obj = self.send_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            # wait until a socket is available
            while self.running:
                with self.lock:
                    s = self.sock
                if not s:
                    # no socket yet; re-enqueue and wait. (Suppress noisy log unless VERBOSE)
                    if VERBOSE:
                        print('send_loop: no socket available, waiting to send', obj.get('type'), flush=True)
                    try:
                        self.send_queue.put_nowait(obj)
                    except Exception:
                        pass
                    time.sleep(0.5)
                    break
                # Wait for handshake to complete before sending non-handshake messages
                if not self.handshake_done and obj.get('type') not in ('hello','close'):
                    # requeue and wait; also send hello periodically
                    try:
                        self.send_queue.put_nowait(obj)
                    except Exception:
                        pass
                    now = time.time()
                    if now - self.last_hello_sent > self.hello_interval:
                        try:
                            self.send_json_socket(s, {'type':'hello','id': self.local_id})
                            self.last_hello_sent = now
                        except Exception as e:
                            print('hello resend failed', e)
                            try:
                                self.close_socket()
                            except Exception:
                                pass
                    time.sleep(0.5)
                    break
                try:
                    if obj.get('type') != 'state' or VERBOSE:
                        print('send_loop: sending', obj.get('type'), flush=True)
                    send_json(s, obj)
                    break
                except Exception as e:
                    if VERBOSE:
                        print('send failed', e, flush=True)
                    try:
                        self.close_socket()
                    except Exception:
                        pass
                    # try again with next available socket
                    time.sleep(0.5)
                    continue
    def send(self, obj):
        # enqueue the object for asynchronous sending
        try:
            self.send_queue.put_nowait(obj)
        except Exception as e:
            print('send enqueue failed', e)

    def stop(self):
        self.running = False
        try:
            if self.server:
                self.server.close()
        except: pass
        try:
            if self.sock:
                self.sock.close()
        except: pass

# テトリスのゲームロジック

class Piece:
    """テトロミノ（落下するブロック）を表すクラス
    
    属性:
        shape_idx: 形状の番号（0～6までの7種類）
        matrix: ブロックの形状（2次元リスト）
        color: ブロックの色
        x, y: 盤面内の位置
    """
    def __init__(self, shape_idx):
        """テトロミノを初期化
        
        引数:
            shape_idx: 形状の番号（0～6）
        """
        self.shape_idx = shape_idx
        # 形状データをコピー（元のデータを変えないため）
        self.matrix = [row[:] for row in SHAPES[shape_idx]]
        # 形状に対応する色を設定
        self.color = COLORS[shape_idx]
        # 初期位置：横は中央、縦は一番上
        self.x = COLS//2 - len(self.matrix[0])//2
        self.y = 0

    def rotate(self):
        """ブロックを90度右回転させる
        
        仕組み:
            1. 行列を転置（行と列を入れ替え）
            2. 各行を反転
            → 結果、90度右回転
        """
        self.matrix = [list(row) for row in zip(*self.matrix[::-1])]

class TetrisGame:
    """テトリスゲームのルールと状態を管理するクラス
    
    属性:
        grid: 盤面（20行×15列の2次元リスト）
        piece: 現在落下中のブロック
        next_piece: 次に出てくるブロック
        score: 現在のスコア
        game_over: ゲームオーバーフラグ
    """
    def __init__(self):
        """テトリスゲームを初期化
        
        処理:
            - 空の盤面を作成
            - 最初のブロックを生成
            - スコアを0に設定
        """
        # 空の盤面を作成（Noneは空白マス）
        self.grid = [[None for _ in range(COLS)] for _ in range(ROWS)]
        # 新しいブロックを生成
        self.piece = self.new_piece()
        self.next_piece = self.new_piece()
        self.score = 0           # スコアは0からスタート
        self.game_over = False   # ゲームオーバーフラグ

    def new_piece(self):
        """ランダムに新しいブロックを生成
        
        戻り値:
            Piece: ランダムな形状のブロック
        """
        return Piece(random.randrange(len(SHAPES)))

    def collides(self, piece=None, dx=0, dy=0):
        """ブロックが壁や他のブロックと衝突するか判定
        
        引数:
            piece: 判定するブロック（省略時は現在のブロック）
            dx: X方向のオフセット（左右移動のテスト用）
            dy: Y方向のオフセット（上下移動のテスト用）
        
        戻り値:
            bool: 衝突する場合True、しない場合False
        """
        if piece is None: piece = self.piece
        # ブロックの各マスをチェック
        for r,row in enumerate(piece.matrix):
            for c,val in enumerate(row):
                if val:  # ブロックがあるマスのみチェック
                    x = piece.x + c + dx
                    y = piece.y + r + dy
                    # 盤面の外に出ていたら衝突
                    if x < 0 or x >= COLS or y >= ROWS:
                        return True
                    # 既に他のブロックがあったら衝突
                    if y>=0 and self.grid[y][x] is not None:
                        return True
        return False

    def lock_piece(self):
        """ブロックを盤面に固定する（落下終了時）
        
        処理:
            1. ブロックの各マスを盤面に書き込む
            2. 横一列が埋まった行を消す
        
        戻り値:
            int: 消した行数
        """
        # ブロックの各マスを盤面に書き込む
        for r,row in enumerate(self.piece.matrix):
            for c,val in enumerate(row):
                if val:
                    x = self.piece.x + c
                    y = self.piece.y + r
                    if 0<=y<ROWS and 0<=x<COLS:
                        self.grid[y][x] = self.piece.color
                    else:
                        # 盤面からはみ出ていたらゲームオーバー
                        self.game_over = True
        # 横一列が埋まった行を消す
        cleared = self.clear_lines()
        return cleared

    def clear_lines(self):
        """横一列が埋まった行を消す
        
        処理:
            1. 空白マスがある行だけを残す
            2. 消えた行数分、上に空白行を追加
            3. スコアを追加（1行=100点）
        
        戻り値:
            int: 消した行数
        """
        # 空白マスがある行だけを残す（全部埋まった行は除外）
        new_grid = [row for row in self.grid if any(cell is None for cell in row)]
        # 消えた行数を計算
        cleared = ROWS - len(new_grid)
        # 上に空白行を追加
        for _ in range(cleared):
            new_grid.insert(0,[None]*COLS)
        self.grid = new_grid
        # スコア追加（1行消すと100点）
        if cleared>0:
            self.score += 100*cleared
            print('clear_lines: cleared', cleared, 'new score', self.score)
        return cleared

    def add_garbage(self, lines):
        """相手からのゴミ行を盤面に追加
        
        引数:
            lines: 追加するゴミ行の数
        
        処理:
            1. 上の行を削除
            2. 下にランダムな穴（1マス）があるゴミ行を追加
        """
        for _ in range(lines):
            # ランダムな位置に穴を作る
            hole = random.randrange(COLS)
            # 穴以外は灰色のブロック
            new_row = [GREY if c!=hole else None for c in range(COLS)]
            # 一番上の行を削除
            self.grid.pop(0)
            # 一番下にゴミ行を追加
            self.grid.append(new_row)

    def step(self):
        """ブロックを1マス下に落下させる（毎フレーム呼ばれる）
        
        処理:
            - 下に移動できれば移動
            - 下に移動できない（衝突）なら固定して新しいブロックを生成
        
        戻り値:
            int: 消した行数（0または1以上）
        """
        if self.game_over: return 0
        # 下に移動できるかチェック
        if not self.collides(dy=1):
            # 移動できるなら1マス下へ
            self.piece.y += 1
            return 0
        else:
            # 移動できないので固定
            cleared = self.lock_piece()
            # 新しいブロックを生成
            self.piece = self.next_piece
            self.next_piece = self.new_piece()
            # 新しいブロックが最初から衝突するならゲームオーバー
            if self.collides():
                self.game_over = True
            return cleared

# Pygameを使ったUI（画面描画）とメイン処理

def draw_board(surface, x_offset, y_offset, game):
    """テトリスの盤面と落下中のブロックを画面に描画
    
    引数:
        surface: 描画先の画面（pygameのsurface）
        x_offset: 描画開始位置のX座標
        y_offset: 描画開始位置のY座標
        game: 描画するTetrisGameオブジェクト
    """
    # 盤面の背景（暗い灰色）を描画
    pygame.draw.rect(surface, (30,30,30), (x_offset,y_offset,COLS*CELL,ROWS*CELL))
    # 盤面の各マスを描画
    for r in range(ROWS):
        for c in range(COLS):
            # マスの場所とサイズを計算
            rect = pygame.Rect(x_offset + c*CELL, y_offset + r*CELL, CELL-1, CELL-1)
            color = game.grid[r][c]
            if color is None:
                # 空白マス（黒っぽい灰色）
                pygame.draw.rect(surface, (15,15,15), rect)
            else:
                # ブロックがあるマス（色付き）
                pygame.draw.rect(surface, color, rect)
    # 落下中のブロックを描画
    if game.piece and not game.game_over:
        for r,row in enumerate(game.piece.matrix):
            for c,val in enumerate(row):
                if val:  # ブロックがある部分だけ描画
                    px = x_offset + (game.piece.x + c)*CELL
                    py = y_offset + (game.piece.y + r)*CELL
                    pygame.draw.rect(surface, game.piece.color, (px,py,CELL-1,CELL-1))


class UI:
    """ゲームの画面とユーザー入力を管理するクラス
    
    役割:
        - pygameを使ってウィンドウを表示
        - キーボード・マウス入力を処理
        - ネットワーク通信を管理
        - 2つの盤面（自分と相手）を同時に表示
    """
    def __init__(self):
        """ゲームUIを初期化
        
        処理:
            - pygameの初期化
            - ウィンドウの作成
            - フォントの選択（日本語対応）
            - ゲーム状態の初期化
        """
        # pygameを初期化（準備）
        pygame.init()
        # ウィンドウを作成
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption('Network Tetris')  # ウィンドウのタイトル
        self.clock = pygame.time.Clock()  # FPS制御用
        
        # 日本語が表示できるフォントを選択
        preferred_fonts = ['Meiryo','Yu Gothic','MS Gothic','MS UI Gothic','Noto Sans CJK JP','Arial Unicode MS','Segoe UI','Noto Sans','Consolas']
        def choose_font(size):
            """日本語が表示できるフォントを選ぶ関数"""
            for n in preferred_fonts:
                try:
                    f = pygame.font.SysFont(n, size)
                    # 日本語が表示できるかテスト
                    if f and f.size('あ')[0] > 0:
                        return f
                except Exception:
                    pass
            # 見つからなければデフォルトフォント
            return pygame.font.Font(None, size)
        
        # 3種類のフォントサイズを用意
        self.small = choose_font(14)  # 小さい文字（説明文用）
        self.font = choose_font(16)   # 普通の文字
        self.large = choose_font(22)  # 大きい文字（タイトル用）

        # ネットワーク設定の初期値
        self.local_ip = '0.0.0.0'     # 自分のIPアドレス
        self.peer_ip = ''             # 相手のIPアドレス
        self.port = 6000              # ポート番号
        self.speed = 500              # ブロック落下速度（ミリ秒）
        # 接続の役割（auto=自動判定, active=積極接続, passive=待機）
        self.role = 'auto'
        self.network = None           # NetworkManagerオブジェクト
        
        # ゲームのタイミング管理
        self.last_tick = 0            # 最後にブロックを落とした時刻
        self.interval = self.speed    # 落下間隔
        self.running = True           # アプリ実行中フラグ
        
        # 2つのゲーム状態（自分と相手）
        self.local_game = TetrisGame()  # 自分のゲーム
        self.peer_game = TetrisGame()   # 相手のゲーム（表示用）
        
        # ゲーム開始・終了の状態
        self.started = False          # ゲーム開始済みフラグ
        self.last_state_send = 0      # 最後に状態を送信した時刻
        self.sent_gameover = False    # ゲームオーバー送信済みフラグ
        self.end_message = None       # 終了メッセージ（'Win', 'Loose', 'Tie'）
        self.end_time = 0             # 終了時刻
        
        # ハンドシェイク状態（現在は使っていない）
        self.handshake_done = False
        self.handshake_deadline = 0
        self.last_hello_sent = 0
        self.hello_interval = 1.0

    def on_network(self, msg):
        """ネットワークからメッセージを受信したときの処理
        
        引数:
            msg: 受信したメッセージ（辞書形式）
        
        メッセージ種類:
            - 'start': ゲーム開始の通知
            - 'add': ゴミ行追加の通知
            - 'gameover': 相手のゲームオーバー通知
            - 'state': 相手の盤面・スコアの同期
        """
        t = msg.get('type')
        # state以外のメッセージは表示（VERBOSEがTrueならstateも表示）
        if t != 'state' or VERBOSE:
            print('on_network received:', t, flush=True)
        
        if t=='start':
            # 相手がゲームを開始した
            self.started = True
        elif t=='add':
            # 相手が行を消したので、自分にゴミ行を追加
            lines = msg.get('lines',1)
            print('on_network: add lines', lines)
            try:
                # 自分の盤面にゴミ行を追加（相手からの攻撃）
                self.local_game.add_garbage(lines)
                print('Added', lines, 'garbage lines to local game', flush=True)
            except Exception as e:
                print('add_garbage failed', e, flush=True)
        elif t=='gameover':
            # 相手がゲームオーバーになった
            peer_score = msg.get('score',0)
            print('on_network: peer gameover score', peer_score)
            self.peer_game.game_over = True
            self.peer_game.score = peer_score
            # 自分もゲームオーバーならスコアで勝敗判定
            if self.local_game.game_over:
                if self.local_game.score > self.peer_game.score:
                    self.finish_game('Win')   # 自分の勝ち
                elif self.local_game.score < self.peer_game.score:
                    self.finish_game('Loose') # 自分の負け
                else:
                    self.finish_game('Tie')   # 引き分け
            else:
                # 自分はまだプレイ中なので自分の勝ち
                self.finish_game('Win')
        elif t=='state':
            # 相手の盤面・スコア・ブロックを更新
            board = msg.get('board')
            score = msg.get('score',0)
            piece = msg.get('piece')
            game_over = msg.get('game_over', False)
            if board:
                # 盤面データを展開（色番号→実際の色）
                g = [[None]*COLS for _ in range(ROWS)]
                for r in range(ROWS):
                    for c in range(COLS):
                        v = board[r][c]
                        if v is not None:
                            g[r][c] = COLORS[v]
                self.peer_game.grid = g
            self.peer_game.score = score
            self.peer_game.game_over = game_over
            # 相手の落下中ブロックを展開
            if piece:
                try:
                    p = Piece(0)
                    p.matrix = piece.get('matrix')
                    p.x = piece.get('x',0)
                    p.y = piece.get('y',0)
                    color_idx = piece.get('color',0)
                    p.color = COLORS[color_idx] if 0<=color_idx<len(COLORS) else COLORS[0]
                    self.peer_game.piece = p
                except Exception:
                    pass

    def pack_board(self, game):
        """盤面データを送信用に圧縮
        
        引数:
            game: TetrisGameオブジェクト
        
        戻り値:
            list: 色番号の2次元リスト（Noneは空白）
        
        処理:
            実際の色（RGB）を色番号（0～6）に変換してデータ量を削減
        """
        packed = []
        for r in range(ROWS):
            row = []
            for c in range(COLS):
                val = game.grid[r][c]
                if val is None:
                    row.append(None)  # 空白マス
                else:
                    # 色を番号に変換
                    idx = COLORS.index(val) if val in COLORS else 0
                    row.append(idx)
            packed.append(row)
        return packed

    def pack_piece(self, game):
        """落下中のブロック情報を送信用に圧縮
        
        引数:
            game: TetrisGameオブジェクト
        
        戻り値:
            dict: ブロックの形状・位置・色番号、またはNone
        """
        if not game or not game.piece:
            return None
        # 色を番号に変換
        try:
            color_idx = COLORS.index(game.piece.color) if game.piece.color in COLORS else 0
        except Exception:
            color_idx = 0
        return {'matrix': game.piece.matrix, 'x': game.piece.x, 'y': game.piece.y, 'color': color_idx}

    def connect_network(self, force=False):
        """ネットワーク接続を開始または再開始
        
        引数:
            force: Trueの場合、既存の接続を強制的に再開始
        """
        if self.network and not force:
            return
        if self.network and force:
            # 既存のネットワークを停止
            try:
                print('connect_network: forcing restart of network', flush=True)
                self.network.stop()
            except Exception:
                pass
            self.network = None
        # 新しいNetworkManagerを作成
        self.network = NetworkManager(self.local_ip, self.peer_ip, self.port, self.on_network, peer_port=getattr(self,'peer_port', None), role=getattr(self,'role','auto'))

    def is_connected(self):
        """接続状態を確認
        
        戻り値:
            bool: ソケットがありハンドシェイク完了していればTrue
        """
        if not self.network:
            return False
        try:
            return (self.network.sock is not None) and getattr(self.network, 'handshake_done', False)
        except Exception:
            return False

    def finish_game(self, result):
        """ゲーム終了処理
        
        引数:
            result: 結果（'Win', 'Loose', 'Tie'）
        
        処理:
            - 終了メッセージを設定
            - ゲームを停止（ネットワークは維持）
            - ウィンドウは開いたままにしてユーザーが結果を見られるようにする
        """
        if self.end_message:
            return  # 既に終了していれば何もしない
        self.end_message = result
        self.started = False
        # ネットワークを停止せず、自動的にアプリを閉じない
        # UIを表示したままにして、プレイヤーが結果を見て手動で閉じられるようにする
        print('finish_game:', result, '— game stopped, awaiting user quit', flush=True)

    def send_state(self):
        """自分のゲーム状態を相手に送信
        
        処理:
            - 盤面・スコア・落下中ブロック・ゲームオーバー状態を送信
            - ゲーム終了後は送信しない
        """
        # ゲーム終了後は状態を送信しない
        if self.end_message:
            return
        if not self.network: return
        # 送信するデータを作成
        obj = {'type':'state',
               'board': self.pack_board(self.local_game),      # 盤面データ
               'score': self.local_game.score,                 # 現在のスコア
               'piece': self.pack_piece(self.local_game),      # 落下中ブロック
               'game_over': self.local_game.game_over}         # ゲームオーバーフラグ
        # 送信キューに追加
        self.network.send(obj)

    def run(self):
        """メインゲームループ（毎フレーム実行）
        
        処理の流れ:
            1. ユーザー入力を処理（キーボード・マウス）
            2. ゲーム状態を更新（ブロック落下・行消去）
            3. 画面を描画（2つの盤面・スコア・ボタン）
            4. 60 FPS（毎秒1て60フレーム）でループ
        """
        while self.running:
            # FPS制限（60 FPS）
            self.clock.tick(FPS)
            # レイアウトの位置を計算（テキストの重なりを防ぐ）
            title_y = 8
            info_y = title_y + self.large.get_linesize() + 6
            score_y = info_y + self.font.get_linesize() + 8
            board_y = max(BOARD_Y, score_y + self.font.get_linesize() + 12)
            # ボタンと説明文の位置を計算（10pxのギャップ）
            base_button_y = board_y + ROWS*CELL + BUTTON_MARGIN
            gap = 10
            helper_y = base_button_y - self.small.get_linesize() - gap
            button_y = base_button_y
            
            # イベント処理（キーボード・マウス入力）
            for event in pygame.event.get():
                if event.type==pygame.QUIT:
                    self.running=False
                elif event.type==pygame.KEYDOWN:
                    # If the game has finished, ignore gameplay keys
                    if self.end_message:
                        continue
                    if event.key==pygame.K_LEFT:
                        if not self.local_game.collides(dx=-1):
                            self.local_game.piece.x -=1
                        self.send_state()
                    elif event.key==pygame.K_RIGHT:
                        if not self.local_game.collides(dx=1):
                            self.local_game.piece.x +=1
                        self.send_state()
                    elif event.key==pygame.K_UP:
                        self.local_game.piece.rotate()
                        if self.local_game.collides():
                            # revert rotation
                            for _ in range(3): self.local_game.piece.rotate()
                        self.send_state()
                    elif event.key==pygame.K_DOWN:
                        # soft drop
                        if not self.local_game.collides(dy=1):
                            self.local_game.piece.y +=1
                        self.send_state()
                    elif event.key==pygame.K_SPACE:
                        # hard drop
                        while not self.local_game.collides(dy=1):
                            self.local_game.piece.y +=1
                        cleared = self.local_game.step()
                        if cleared>0:
                            # send add to opponent
                            if self.network:
                                sent = self.network.send_now({'type':'add','lines':cleared})
                                if not sent:
                                    self.network.send({'type':'add','lines':cleared})
                                self.send_state()
                                print('Sent add lines:', cleared, 'immediate:', sent, flush=True)
                        # check for game over after hard drop
                        if self.local_game.game_over and not self.sent_gameover:
                            if self.network:
                                self.network.send({'type':'gameover','score':self.local_game.score})
                            self.sent_gameover = True
                            self.finish_game('Loose')
                    elif event.key==pygame.K_s:
                        # start shortcut
                        self.started = True
                        if self.network:
                            self.network.send({'type':'start'})
                            self.send_state()
                elif event.type==pygame.MOUSEBUTTONDOWN:
                    mx,my = event.pos
                    # simple input area and buttons
                    # compute button positions
                    # compute button positions based on computed board_y to avoid overlap
                    # add extra offset to avoid overlapping the helper text above
                    button_y = board_y + ROWS*CELL + BUTTON_MARGIN + 18
                    start_x = BOARD_X + 20
                    start_w, start_h = 100, 32
                    connect_x = start_x + start_w + 20
                    connect_w, connect_h = 100, 32
                    # Start button
                    if start_x <= mx <= start_x + start_w and button_y <= my <= button_y + start_h:
                        if not self.end_message:
                            self.started = True
                            if self.network:
                                self.network.send({'type':'start'})
                                self.send_state()
                    # Connect / Reconnect button
                    if connect_x <= mx <= connect_x + connect_w and button_y <= my <= button_y + connect_h:
                        if not self.is_connected():
                            # force a reconnect attempt
                            self.connect_network(force=True)
                        else:
                            print('Connect button clicked but already connected; no action', flush=True)
            # Start screen inputs (quick textual entry using keys) - simplified
            keys = pygame.key.get_pressed()
            # timing
            if self.started:
                now = pygame.time.get_ticks()
                if now - self.last_tick > self.interval:
                    self.last_tick = now
                    cleared = self.local_game.step()
                    if cleared>0 and self.network:
                        sent = self.network.send_now({'type':'add','lines':cleared})
                        if not sent:
                            self.network.send({'type':'add','lines':cleared})
                        self.send_state()
                        print('Sent add lines (step):', cleared, 'immediate:', sent, flush=True)
                    # send periodic state after each step
                    self.send_state()
                    # detect local game over
                    if self.local_game.game_over and not self.sent_gameover:
                        if self.network:
                            self.network.send({'type':'gameover','score':self.local_game.score})
                        self.sent_gameover = True
                        self.finish_game('Loose')
                # periodic state send (in ms)
                if pygame.time.get_ticks() - self.last_state_send > 200:
                    self.last_state_send = pygame.time.get_ticks()
                    self.send_state()

            # Drawing
            self.screen.fill(BLACK)
            # Titles and inputs
            # Dynamic layout to avoid overlapping text
            title_y = 8
            title = self.large.render('ネット対戦テトリス', True, WHITE)
            self.screen.blit(title,(20,title_y))
            info_y = title_y + self.large.get_linesize() + 6
            info = self.font.render(f'自IP: {self.local_ip}  相手IP: {self.peer_ip}  Port: {self.port}  速度(ms): {self.speed}  役割: {self.role}', True, WHITE)
            self.screen.blit(info,(20,info_y))
            # show a small Connected tag at top-right when connected (avoids overlapping main game area)
            if self.is_connected():
                try:
                    tag = self.small.render('Connected', True, (0,200,0))
                    tx = self.screen.get_width() - tag.get_width() - 12
                    ty = title_y
                    self.screen.blit(tag, (tx, ty))
                except Exception:
                    pass

            # Scores (placed below info, above the boards)
            s1 = self.font.render(f'Me: {self.local_game.score}', True, WHITE)
            s2 = self.font.render(f'Peer: {self.peer_game.score}', True, WHITE)
            score_y = info_y + self.font.get_linesize() + 8
            self.screen.blit(s1,(BOARD_X, score_y))
            self.screen.blit(s2,(BOARD_X + COLS*CELL + 60, score_y))

            # Draw local and peer boards positioned below the header area (board_y precomputed)
            # Ensure window height is sufficient when header grows
            required_height = board_y + ROWS*CELL + 80
            try:
                if required_height > self.screen.get_height():
                    # resize window to fit content
                    print('Resizing window height', self.screen.get_height(), '->', required_height, flush=True)
                    self.screen = pygame.display.set_mode((WIDTH, required_height))
            except Exception:
                pass
            draw_board(self.screen, BOARD_X, board_y, self.local_game)
            draw_board(self.screen, BOARD_X + COLS*CELL + 60, board_y, self.peer_game)

# Buttons (placed below boards) - position computed once per frame
            start_x = BOARD_X + 20
            start_w, start_h = 100, 32
            connect_x = start_x + start_w + 20
            connect_w, connect_h = 100, 32
            pygame.draw.rect(self.screen, (0,120,0), (start_x, button_y, start_w, start_h))
            st = self.font.render('START (S)', True, WHITE)
            self.screen.blit(st,(start_x + 8, button_y + 6))

            # Show Connect/Reconnect button only when not connected
            if not self.is_connected():
                pygame.draw.rect(self.screen, (0,0,120), (connect_x, button_y, connect_w, connect_h))
                cb = self.font.render('Reconnect', True, WHITE)
                self.screen.blit(cb,(connect_x + 12, button_y + 6))
            else:
                # connected: no inline tag shown to avoid UI overlap
                pass

            # Draw instructions near buttons (use helper_y with fixed gap)
            if self.is_connected():
                # do not show helper text when connected (we will show a small Connected tag elsewhere)
                ins_text = ''
            else:
                ins_text = '未接続 — Reconnect をクリック（左上情報はコマンドラインで指定）'
            ins = self.small.render(ins_text, True, GREY)
            self.screen.blit(ins,(BOARD_X, helper_y))

            # draw end message overlay if present (on top)
            if self.end_message:
                em = self.large.render(self.end_message, True, (255,215,0))
                ew, eh = em.get_size()
                self.screen.blit(em, ((self.screen.get_width()-ew)//2, (self.screen.get_height()-eh)//2))
                pygame.display.flip()
                # Keep showing the message until the user closes the window; do not exit automatically
            else:
                pygame.display.flip()

        if self.network:
            self.network.stop()
        pygame.quit()

# プログラムのエントリーポイント（起動地点）
if __name__=='__main__':
    # コマンドライン引数を解析
    import argparse
    parser = argparse.ArgumentParser()
    # 各引数を定義
    parser.add_argument('--local', default='0.0.0.0', help='自分のIPアドレス（待ち受け用）')
    parser.add_argument('--peer', default='', help='相手のIPアドレス（接続先）')
    parser.add_argument('--port', type=int, default=6000, help='ポート番号')
    parser.add_argument('--peer-port', type=int, default=None, help='相手のポート番号（異なる場合）')
    parser.add_argument('--speed', type=int, default=500, help='ブロック落下速度（ミリ秒）')
    parser.add_argument('--role', choices=['auto','active','passive'], default='auto', help='接続の役割: auto(自動), active(積極接続), passive(待機のみ)')
    args = parser.parse_args()

    # UIオブジェクトを作成
    ui = UI()
    # コマンドライン引数の値を設定
    ui.local_ip = args.local
    ui.peer_ip = args.peer
    ui.port = args.port
    ui.peer_port = args.peer_port if args.peer_port is not None else args.port
    ui.speed = args.speed
    ui.role = args.role
    ui.interval = ui.speed
    # ネットワーク接続を開始
    ui.connect_network()
    # メインループを開始（ゲーム開始）
    ui.run()
