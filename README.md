# Network Tetris (Python)

簡易ネット対戦テトリス（P2P）

特徴
- Python + pygame
- 自分と相手のIP/ポートを指定して接続
- 1行消すと相手側に1行追加（ゴミライン）
- 1行=100点、上部にスコア表示
- 20行 x 15列
- 矢印キーで操作（上: 回転 / 左右: 移動 / 下: ソフトドロップ / Space: ハードドロップ）
- ゲーム開始速度は引数で指定可能
- 片方がSTARTを押すとSTARTメッセージ送信で双方が開始

実行方法

1. 仮想環境を作成して依存をインストール:

   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt

2. それぞれのマシンで実行:

   python main.py --local 0.0.0.0 --peer <相手のIP> --port 6000 --speed 500

- `--local` サーババインドIP
- `--peer` 接続先IP（相手のIP。未指定なら待ち受けのみ）
- `--port` ポート（双方同じにすること）
- `--peer-port` 相手のポート（相手が異なるポートで待ち受けしている場合）
- `--speed` 落下間隔(ms)
- `--role` 接続役割（`auto` | `active` | `passive`）。同一マシンでのループバックテストで役割を固定すると確実に接続できます。

実行例（同一マシンのループバック例、端末を2つ開く）:

- Player A (passive):
  python main.py --local 127.0.0.1 --peer 127.0.0.2 --port 6000 --role passive

- Player B (active):
  python main.py --local 127.0.0.2 --peer 127.0.0.1 --port 6000 --role active

その他の補助機能:
- `VERBOSE` フラグ（`main.py` 内の `VERBOSE = False`）を `True` にすると詳細なネットワークログが出ます（トラブルシュート時に有効化してください）。
- UIの `Connect` ボタンは未接続時に「Reconnect」として表示され、押すと強制的に再接続を試みます。接続中はボタンは非表示になります。

注意・制限 / トラブルシューティング
- シンプル実装のため接続確立処理やエラーハンドリングは最小限です。問題が起きたら `VERBOSE=True` にしてログを確認してください。
- テキスト入力UIはなく、IPや速度はコマンドライン引数で指定します。
- Windowsでの `pygame` インストールに失敗する場合の対処:
  - まず `pip install --upgrade pip setuptools wheel` を実行してから再試行してください。
  - それでも失敗する場合は `pipwin install pygame`（pipwin が使えれば便利）か、Anaconda/Miniconda を用いて `conda install -c conda-forge pygame` を検討してください。
  - Python 3.11〜3.13 での動作を想定しています。環境によっては Microsoft Visual C++ Build Tools が必要になることがあります。
- 同一マシンでテストする場合、2つの異なるループバックアドレス（例: 127.0.0.1 と 127.0.0.2）を使うか、別ポートを使った方が安定します。`--role active/passive` を使うと同時接続の競合を避けられます。
- しばらく接続が安定しない場合は、双方のログ（start→handshake→send/recv の痕跡）を保存して提供してください。
拡張案
- GUIでIPや速度を入力するフォーム追加
- 接続状態の表示
- マッチングサーバを経由した接続
- 当たり判定、回転衝突処理の強化

Enjoy! 🎮