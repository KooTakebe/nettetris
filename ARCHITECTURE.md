# Network Tetris — 技術解説ドキュメント

このドキュメントは、**Network Tetris**（ネット対戦テトリス）のプログラム構造と技術的な実装を、プログラミング初心者にも分かるように丁寧に解説したものです。

---

## 📋 目次

1. [プログラムの概要](#プログラムの概要)
2. [全体アーキテクチャ](#全体アーキテクチャ)
3. [使用ライブラリと技術](#使用ライブラリと技術)
4. [主要な処理フロー](#主要な処理フロー)
5. [ネットワーク通信の仕組み](#ネットワーク通信の仕組み)
6. [ゲーム処理の実装](#ゲーム処理の実装)
7. [UI/画面レンダリング](#ui画面レンダリング)
8. [学習ポイント](#学習ポイント)

---

## 🎮 プログラムの概要

**Network Tetris**は、インターネットを通じて 2 人がリアルタイムで対戦するテトリスゲームです。

### 主な特徴

- **P2P（ピア・ツー・ピア）通信**: サーバーを介さず、2つのコンピュータが直接通信
- **リアルタイム同期**: 両者のゲーム画面がリアルタイムで更新される
- **対戦要素**: 1行を消すと相手に 1 行のゴミ（障害物）が自動的に追加
- **スコア計算**: 1行消去=100点
- **操作**: 矢印キーとスペースキーで簡単操作

### ゲーム流れ

```
1. プレイヤーA と B がそれぞれ起動
2. 接続確立（ハンドシェイク）
3. どちらかが「Start」を押す
4. 両者がゲーム開始
5. 操作してテトリスをプレイ
6. 1行消す → 相手に 1 行のゴミが追加される
7. 盤が埋まったら LOSE、相手が埋まったら WIN
```

---

## 🏗️ 全体アーキテクチャ

```
┌──────────────────────────────────────────────┐
│         Network Tetris アプリケーション      │
├──────────────────────────────────────────────┤
│                                              │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐│
│  │   UI層     │ │ ゲーム層   │ │ ネット層   ││
│  │────────────│ │────────────│ │────────────││
│  │・画面描画  │ │・テトリス  │ │・TCP接続   ││
│  │・入力処理  │ │  ロジック  │ │・JSON通信  ││
│  │・ボタン    │ │・スコア    │ │・ハンドシェ││
│  │  イベント  │ │  管理      │ │  イク      ││
│  └────────────┘ └────────────┘ └────────────┘│
│         │               │               │    │
│         └──────┬────────┴───────┬───────┘    │
│                │                │            │
│  ┌────────────────────────────────────────┐  │
│  │           main.py（メイン実行）        │  │
│  │  • UIクラス — 画面・入力管理           │  │
│  │  • TetrisGameクラス — ゲームロジック   │  │
│  │  • Pieceクラス — テトロミノ管理        │  │
│  │  • NetworkManagerクラス — 通信処理     │  │
│  └────────────────────────────────────────┘  │
│                                              │
├──────────────────────────────────────────────┤
│              ライブラリ層                    │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐│
│  │ pygame │ │ socket │ │ json   │ │threading││
│  │ (GUI)  │ │(通信)  │ │(データ)│ │ (並列) ││
│  └────────┘ └────────┘ └────────┘ └────────┘│
└──────────────────────────────────────────────┘
```

### 3 層構成

1. **UI 層（ユーザーインターフェース）**
   - 画面上に文字や図形を描画
   - マウス・キーボード入力を受け取る
   - ボタンクリック処理

2. **ゲーム層（ゲームロジック）**
   - テトリスのルール実装
   - ブロック移動・回転・落下
   - 行消去・スコア計算

3. **ネットワーク層（通信）**
   - 2 つのコンピュータ間の接続管理
   - ゲーム状態（盤面、スコアなど）をJSON形式で送受信
   - エラーハンドリング・再接続

---

## 📚 使用ライブラリと技術

### 1. **pygame** — ゲーム画面描画・イベント処理

**【ライブラリとは】**

ライブラリは、よく使う機能があらかじめ用意されたプログラムの部品です。自分で一から作らず、他人が作った便利な機能を「借りる」というイメージです。

**【pygame とは】**

`pygame` は Python でゲームやグラフィックスプログラムを作るための有名なライブラリです。画面に図形を描いたり、キーボード入力を受け取ったり、音を出したりできます。

**参考URL**  
🔗 [pygame 公式ドキュメント](https://www.pygame.org/)  
🔗 [pygame 入門（日本語）](https://pg-archive.readthedocs.io/)

**【このプログラムで使った関数と役割】**

| 関数名 | 役割 | コード例 |
|--------|------|---------|
| `pygame.init()` | pygame を初期化（準備） | `pygame.init()` |
| `pygame.display.set_mode()` | ゲームウィンドウを作成 | `screen = pygame.display.set_mode((WIDTH, HEIGHT))` |
| `pygame.draw.rect()` | 四角形を画面に描く | `pygame.draw.rect(screen, (255,0,0), (x, y, w, h))` |
| `pygame.font.SysFont()` | 文字を描くためのフォント取得 | `font = pygame.font.SysFont('Arial', 20)` |
| `font.render()` | 文字列を画像に変換 | `text_img = font.render('Hello', True, (255,255,255))` |
| `pygame.event.get()` | キーボード・マウス入力を取得 | `for event in pygame.event.get(): ...` |
| `pygame.time.Clock()` | ゲーム速度（フレームレート）制御 | `clock.tick(60)` — 1秒間に60回更新 |

**【使った流れ】**

```python
# 1. pygame 初期化
pygame.init()

# 2. ウィンドウ作成（幅800×高さ600）
screen = pygame.display.set_mode((800, 600))

# 3. ゲームループ内で毎フレーム:
while True:
    # 背景を黒で塗りつぶし
    screen.fill((0, 0, 0))
    
    # 赤い四角を描く
    pygame.draw.rect(screen, (255, 0, 0), (100, 100, 50, 50))
    
    # 画面を更新して表示
    pygame.display.flip()
    
    # 60 FPS（毎秒60フレーム）制限
    clock.tick(60)
```

---

### 2. **socket** — ネットワーク通信

**【socket とは】**

`socket`（ソケット）は、ネットワークを通じて別のコンピュータと通信するための Python 標準ライブラリです。郵便ポストのようなもので、データを「送る」「受ける」という操作ができます。

**参考URL**  
🔗 [Python socket ドキュメント](https://docs.python.org/ja/3/library/socket.html)

**【このプログラムで使った関数と役割】**

| 関数名 | 役割 |
|--------|------|
| `socket.socket()` | 通信用の「ソケット」を作成 |
| `.bind()` | IP アドレス・ポート番号を割り当てる（サーバー側） |
| `.listen()` | 他のコンピュータからの接続を待つ（サーバー側） |
| `.accept()` | 接続してきたコンピュータを受け入れる（サーバー側） |
| `.connect()` | 他のコンピュータに接続を試みる（クライアント側） |
| `.sendall()` | データを相手に送信 |
| `.recv()` | 相手からデータを受け取る |
| `.close()` | 接続を切る |

**【P2P 通信のイメージ】**

```
プレイヤーA（127.0.0.1:6000）      プレイヤーB（127.0.0.2:6000）
     │                                  │
     ├─ サーバーソケット作成            │
     │  (ポート6000で待ち受け)         │
     │                                  ├─ 接続試行
     │                                  │  connect(127.0.0.1:6000)
     │  ← ← ← ← ← ← ← ← ← ← ← ←  
     │
     ├─ accept() で接続受け入れ ────→ ├─ 接続確立
     │
     ├─ ハンドシェイク（"hello"）
     ├─ ← ← ← ← ← ← ← ← ← ← ← ←
     ├─ → → → → → → → → → → → →
     │  (相互に ID を確認)
     │
     ├─ ゲーム状態（JSON）を送信
     └─ 受信・同期
```

---

### 3. **json** — データフォーマット

**【JSON とは】**

`JSON`（JavaScript Object Notation）は、データを構造化して表現するための形式です。辞書のようにキー（名前）と値を組み合わせます。

**形式例**

```json
{
  "type": "state",
  "board": [[null, null, ...], ...],
  "score": 500,
  "game_over": false
}
```

**【このプログラムで使った関数】**

| 関数名 | 役割 |
|--------|------|
| `json.dumps(obj)` | Python 辞書を JSON 文字列に変換（送信用） |
| `json.loads(string)` | JSON 文字列を Python 辞書に変換（受信用） |

**【使った流れ】**

```python
# データを辞書で作成
message = {
    'type': 'add',
    'lines': 1
}

# JSON 文字列に変換して送信
json_str = json.dumps(message)
# → '{"type": "add", "lines": 1}'

# 受信した JSON 文字列を辞書に変換
received_json = '{"type": "add", "lines": 1}'
data = json.loads(received_json)
print(data['lines'])  # → 1
```

---

### 4. **threading** — 複数の処理を同時実行

**【threading とは】**

通常、プログラムは上から下へ順番に実行されます。しかし、ゲームでは「画面描画」と「ネットワーク受信」を同時にしたいはず。`threading` は複数の処理を並列に実行する機能です。

**【マルチスレッドのイメージ】**

```
単一スレッド：
  1. 描画 ← 完了待ち
  2. 通信 ← 完了待ち
  3. 描画 ← 完了待ち
  ... (遅い！）

マルチスレッド：
  スレッド1（UI）:    描画 → 描画 → 描画 → ...
  スレッド2（通信）: 受信 → 受信 → 受信 → ...
  （同時実行！）
```

**参考URL**  
🔗 [Python threading ドキュメント](https://docs.python.org/ja/3/library/threading.html)

**【このプログラムで使った機能】**

| 機能 | 役割 |
|------|------|
| `threading.Thread()` | 新しいスレッド（並列処理）を作成 |
| `thread.start()` | スレッドを開始 |
| `threading.Lock()` | 複数スレッド間のデータ競合を防ぐ（排他制御） |

**【使った流れ】**

```python
# メインスレッド: ゲーム画面を描画
while True:
    draw_screen()
    
# 別スレッド: ネットワークで受信
def receive_data():
    while True:
        data = socket.recv()
        process(data)

# スレッド開始
thread = threading.Thread(target=receive_data, daemon=True)
thread.start()
```

---

### 5. **queue** — スレッド間のデータ受け渡し


**【queue とは】**

複数のスレッドが同時にデータにアクセスするとバグが起きます。`queue` は「安全に」スレッド間でデータを受け渡しするための機能です。

**【このプログラムでの使い方】**

- **送信キュー**として使っています。
- UI（メインスレッド）から送信したいメッセージ（JSON形式の文字列や辞書）をqueueに入れます。
- バックグラウンドの送信スレッド（send_loop）がqueueから順番にデータを取り出し、ネットワーク経由で相手に送信します。

**【queueに入れているデータの例】**

- ゲーム状態（state）: 盤面やスコアを表す辞書
- ゴミ行追加（add）: {"type": "add", "lines": 1} のような辞書
- ゲーム開始（start）: {"type": "start"}
- ゲーム終了（gameover）: {"type": "gameover", "score": 500}

**【イメージ】**

```
UIスレッド（ユーザー操作）
    ├─ queue.put({"type": "add", "lines": 1})
    │
送信スレッド（send_loop）
    ├─ queue.get() → ソケットで送信
```

**参考URL**  
🔗 [Python queue ドキュメント](https://docs.python.org/ja/3/library/queue.html)

---

## 🔄 主要な処理フロー

### 起動時の流れ

```python
# 1. コマンドライン引数をパース
args = parser.parse_args()
# --local 127.0.0.1 --peer 127.0.0.2 --port 6000

# 2. UI インスタンス作成
ui = UI()
ui.local_ip = args.local
ui.peer_ip = args.peer

# 3. ネットワーク接続初期化
ui.connect_network()
# NetworkManager が起動、サーバーソケット作成 + 接続試行スレッド開始

# 4. ゲームループ開始
ui.run()
# メインループで毎フレーム画面を更新・入力を処理
```

### ゲームループ（毎フレーム実行）

```python
while self.running:
    self.clock.tick(60)  # 60 FPS に制限
    
    # 1. イベント処理（キーボード・マウス）
    for event in pygame.event.get():
        if キー == 左:
            piece.x -= 1
        if キー == スペース:
            hard_drop()
    
    # 2. ゲーム更新（ブロック落下など）
    if started and (現在時刻 - 最終更新 > 落下速度):
        cleared = game.step()
        if cleared > 0:
            network.send_add_message(cleared)
    
    # 3. 画面描画
    screen.fill(BLACK)
    draw_board(local_game)
    draw_board(peer_game)
    draw_scores()
    pygame.display.flip()
```

---

## 🌐 ネットワーク通信の仕組み

### ハンドシェイク（接続確立）

**問題**: 2つのコンピュータが同時に接続しようとしたらどうなる？→ デッドロック

**解決**: **役割分け（active/passive）**

```
Active（積極型）           Passive（受動型）
    │                           │
    ├─ connect() ────────→      ├─ accept()
    │                           │
    ├─ send hello ───────→      ├─ receive hello
    │                           │
    │<──── send hello_ack ──────┤
    ├─ receive hello_ack        │
    │
    └─ ハンドシェイク完了
```

### メッセージ形式（JSON）

| メッセージ型 | 内容 | 例 |
|-------------|------|-----|
| `hello` | 接続確立 | `{"type":"hello","id":"abc123..."}` |
| `hello_ack` | 接続確認 | `{"type":"hello_ack","id":"def456..."}` |
| `start` | ゲーム開始 | `{"type":"start"}` |
| `state` | 盤面・スコア同期 | `{"type":"state","board":[...],"score":100,...}` |
| `add` | ゴミ行追加 | `{"type":"add","lines":1}` |
| `gameover` | ゲーム終了通知 | `{"type":"gameover","score":500}` |

### スレッド構成

```
メインスレッド（UI）          バックグラウンドスレッド
   ├─ accept_loop（受け入れ）
   ├─ try_connect（接続試行）
   ├─ recv_loop（受信）
   ├─ send_loop（送信キュー処理）
   └─ ゲームループ
       ├─ ユーザー入力処理
       ├─ ゲーム更新
       └─ 画面描画
```

---

## 🎯 ゲーム処理の実装

### 1. Piece クラス — ブロック（テトロミノ）

```python
class Piece:
    def __init__(self, shape_idx):
        self.matrix = SHAPES[shape_idx]  # ブロック形状（4×4行列）
        self.color = COLORS[shape_idx]   # 色
        self.x = COLS // 2               # X 座標
        self.y = 0                       # Y 座標
    
    def rotate(self):
        # 90度回転: 行列を転置 + 行を反転
        self.matrix = [list(row) for row in zip(*self.matrix[::-1])]
```

### 2. TetrisGame クラス — ゲームロジック

```python
class TetrisGame:
    def __init__(self):
        self.grid = [[None]*COLS for _ in range(ROWS)]  # 20×15 の盤面
        self.piece = Piece(random.randint(0, 6))        # 現在のピース
        self.score = 0
        self.game_over = False
    
    def step(self):
        # 毎フレーム呼ぶ
        if ブロックが衝突:
            self.lock_piece()  # ブロックを盤に固定
            cleared = self.clear_lines()  # 消えた行数を返す
            self.piece = Piece(random.randint(0, 6))  # 新しいピース生成
        else:
            self.piece.y += 1  # ブロックを下に移動
        return cleared
    
    def lock_piece(self):
        # ブロックを盤に固定
        for r, row in enumerate(self.piece.matrix):
            for c, val in enumerate(row):
                if val:  # ブロック部分なら
                    x = self.piece.x + c
                    y = self.piece.y + r
                    if 0 <= y < ROWS and 0 <= x < COLS:
                        self.grid[y][x] = self.piece.color
    
    def clear_lines(self):
        # 横一列が埋まった行を消す
        new_grid = [row for row in self.grid if any(cell is None for cell in row)]
        cleared = ROWS - len(new_grid)
        for _ in range(cleared):
            new_grid.insert(0, [None]*COLS)  # 上に空行を挿入
        self.grid = new_grid
        self.score += cleared * 100  # 1行=100点
        return cleared
    
    def add_garbage(self, lines):
        # 相手からのゴミ行を追加
        for _ in range(lines):
            hole = random.randint(0, COLS-1)
            new_row = [灰色 if c != hole else None for c in range(COLS)]
            self.grid.pop(0)  # 上の行を削除
            self.grid.append(new_row)  # 下に追加
```

### 3. 衝突判定

```python
def collides(self, piece=None, dx=0, dy=0):
    """ブロックが壁や他のブロックと衝突しているか判定"""
    for r, row in enumerate(piece.matrix):
        for c, val in enumerate(row):
            if val:  # ブロック部分
                x = piece.x + c + dx
                y = piece.y + r + dy
                
                # 盤面外なら衝突
                if x < 0 or x >= COLS or y >= ROWS:
                    return True
                
                # 既に何かある場所なら衝突
                if y >= 0 and self.grid[y][x] is not None:
                    return True
    
    return False
```

---

## 🎨 UI/画面レンダリング

### 画面構成

```
┌─────────────────────────────────────────────────────────┐
│ ネット対戦テトリス           [Connected]  (右上)         │
│                                                           │
│ 自IP: 127.0.0.1  相手IP: 127.0.0.2  速度: 500ms  役割: active
│                                                           │
│ Me: 500                                  Peer: 200      │
│ ┌──────────────────┐      ┌──────────────────┐        │
│ │                  │      │                  │        │
│ │   自分の盤面    │      │   相手の盤面      │        │
│ │  (20行×15列)   │      │  (20行×15列)     │        │
│ │                  │      │                  │        │
│ └──────────────────┘      └──────────────────┘        │
│                                                           │
│ 未接続 — Reconnect をクリック...                        │
│ ┌─────────────┐  ┌─────────────┐                      │
│ │ START (S)   │  │ Reconnect   │  (接続済み時は非表示) │
│ └─────────────┘  └─────────────┘                      │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

### 描画関数

```python
def draw_board(surface, x, y, game):
    """盤面と落下中のブロックを描画"""
    # 背景（暗い灰色）
    pygame.draw.rect(surface, (30, 30, 30), (x, y, COLS*CELL, ROWS*CELL))
    
    # 各セルを描画
    for r in range(ROWS):
        for c in range(COLS):
            cell = game.grid[r][c]
            rect = pygame.Rect(x + c*CELL, y + r*CELL, CELL-1, CELL-1)
            if cell is None:
                pygame.draw.rect(surface, (15, 15, 15), rect)  # 空白
            else:
                pygame.draw.rect(surface, cell, rect)  # ブロック
    
    # 落下中のブロックを描画
    for r, row in enumerate(game.piece.matrix):
        for c, val in enumerate(row):
            if val:
                px = x + (game.piece.x + c) * CELL
                py = y + (game.piece.y + r) * CELL
                pygame.draw.rect(surface, game.piece.color, (px, py, CELL-1, CELL-1))
```

---

## 📖 学習ポイント

このプログラムを通じて学べる技術・概念:

### 1. **ネットワークプログラミング**
- TCP/IP ソケット通信
- サーバー・クライアント構成
- P2P（ピア・ツー・ピア）通信

### 2. **マルチスレッド処理**
- 複数の処理を同時実行
- スレッド安全なデータ受け渡し（キュー）
- デッドロック対策

### 3. **ゲーム開発基礎**
- ゲームループ
- 衝突判定
- スコア管理
- UI/UX 設計

### 4. **データ形式**
- JSON によるデータシリアライズ
- 通信プロトコル設計

### 5. **エラーハンドリング**
- 例外処理（`try-except`）
- 再接続ロジック
- タイムアウト管理

### 6. **ユーザーインターフェース**
- GUI ライブラリの使用
- イベント駆動型プログラミング
- 動的なレイアウト調整

---

## 🚀 今後の拡張案

以下のような機能追加で、さらに高度なポートフォリオになります:

1. **マッチングサーバー**
   - インターネット上でプレイヤーマッチング
   - クラウドサーバーを経由した接続

2. **ゲーム性の向上**
   - Super Rotation System（SRS）— 高度な回転判定
   - ホールド機能（ブロック一時保管）
   - ガイドライン表示

3. **UI/UX 改善**
   - IP 入力フォーム GUI
   - リーダーボード（ランキング）
   - リプレイ機能

4. **パフォーマンス最適化**
   - フレームバッファリング
   - 圧縮通信
   - 帯域幅削減

5. **セキュリティ**
   - 通信暗号化（SSL/TLS）
   - チート防止メカニズム

---

## 📝 参考資料

- 🔗 [pygame Documentation](https://www.pygame.org/docs/)
- 🔗 [Python socket — Network Communication](https://docs.python.org/3/library/socket.html)
- 🔗 [Python threading — Thread-based parallelism](https://docs.python.org/3/library/threading.html)
- 🔗 [JSON — JavaScript Object Notation](https://www.json.org/json-ja.html)
- 🔗 [P2P 通信の基礎](https://en.wikipedia.org/wiki/Peer-to-peer)
- 🔗 [Tetris Guidelines](https://tetris.fandom.com/wiki/Tetris_Guideline)




