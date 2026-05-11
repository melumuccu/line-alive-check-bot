# ユーザー作業 ToDo

## 事前準備

- [ ] 自宅サーバーの設置場所と常時稼働方針を決める。停電時の扱いも確認する。
- [ ] 自宅サーバーに Docker と Docker Compose をインストールする。
- [ ] 公開に使うドメインを決める。Cloudflare 管理下のドメインか、Cloudflare Tunnel の発行 URL を使うかを決める。

## LINE Bot 設定

- [ ] LINE Developers コンソールで Provider を作成する。
- [ ] Provider 配下に Messaging API チャネルを作成する。
- [ ] LINE Official Account を作成し、作成した Messaging API チャネルと紐付ける。
- [ ] チャネル基本設定から Channel Secret を取得し、安全な場所に保管する。
- [ ] Messaging API 設定から Channel Access Token を発行し、安全な場所に保管する。
- [ ] Webhook URL に本番公開 URL の /webhook を設定する。
- [ ] Webhook の利用を有効化する。
- [ ] 応答メッセージを無効化する。Bot 独自実装の返信と競合させない。
- [ ] あいさつメッセージを無効化する。不要な自動送信を避ける。
- [ ] 対象者の LINE アカウントで Bot を友だち追加し、メッセージ受信ができることを確認する。
- [ ] 管理者自身の LINE アカウントでも Bot を友だち追加し、必要ならテスト受信に使えるようにする。

## Slack 設定

- [ ] 管理者通知用の Slack チャンネルを作成する。
- [ ] Slack Incoming Webhook を作成し、通知先チャンネルを紐付ける。
- [ ] 発行された Webhook URL を安全な場所に保管する。
- [ ] 通知文面の受け取り先とメンション方針を決める。必要なら専用チャンネルに集約する。

## Cloudflare Tunnel 設定

- [ ] Cloudflare アカウントを用意する。
- [ ] Tunnel を作成し、対象サーバーへ接続するための認証情報を取得する。
- [ ] 公開ホスト名を決める。例: alive-check.example.com
- [ ] Tunnel から api コンテナの HTTP ポートへ転送する設定を作る。
- [ ] 外部から /health と /webhook へ到達できることを確認する。

## 本番設定値の確定

- [ ] 初期の送信時刻を決める。例: 09:00、12:00、18:00。
- [ ] alert_after_hours の初期値を決める。例: 3。
- [ ] Slack 通知先チャンネルを確定する。
- [ ] ヘルスチェック URL を確定する。例: https://<公開ホスト名>/health
- [ ] 本番用の環境変数一覧を埋める。少なくとも LINE の認証情報、Slack Webhook URL、公開 URL、タイムゾーンを整理する。

## GitHub Actions 設定

- [ ] GitHub リポジトリを用意する。
- [ ] Actions を有効にする。
- [ ] Repository Secrets にヘルスチェック先 URL を登録する。
- [ ] Repository Secrets に Slack 通知用の値を登録する。
- [ ] schedule 実行が有効なことを確認する。

## 初回疎通確認

- [ ] 本番公開 URL に対して /health が 200 を返すことを確認する。
- [ ] LINE Developers の Webhook 検証を実行し、成功することを確認する。
- [ ] 手動で安否確認メッセージを送信し、対象者の LINE に届くことを確認する。
- [ ] ボタン押下後に success へ更新され、確認メッセージが返ることを確認する。
- [ ] 未返信状態を意図的に作り、Slack にアラートが届くことを確認する。
- [ ] GitHub Actions の死活監視を手動実行し、異常時に Slack 通知が届くことを確認する。

## 運用開始前の確認

- [ ] 家族向けの案内文を用意する。ボタンを押すだけでよいことを明確にする。
- [ ] 返信が無い場合の連絡フローを決める。誰が何分後に何をするかを明確にする。
- [ ] 管理者が不在のときの代替連絡先が必要かを判断する。
- [ ] 定期的に確認する運用項目を決める。例: 月1回の疎通確認、トークン期限確認、通知先見直し。
