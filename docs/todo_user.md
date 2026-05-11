# ユーザー作業 ToDo

## 事前準備

- [x] 自宅サーバーの設置場所と常時稼働方針を決める。停電時の扱いも確認する。
- [x] 自宅サーバーに Docker と Docker Compose をインストールする。
- [x] 公開に使う URL 方針を決める。Cloudflare Tunnel の発行 URL を使う。

## LINE Bot 設定

- [x] LINE Developers コンソールで Provider を作成する。
- [x] Provider 配下に Messaging API チャネルを作成する。
- [x] LINE Official Account を作成し、作成した Messaging API チャネルと紐付ける。
- [x] チャネル基本設定から Channel Secret を取得し、安全な場所に保管する。
- [x] Messaging API 設定から Channel Access Token を発行し、安全な場所に保管する。
- [x] Webhook URL に本番公開 URL の /webhook を設定する。
- [x] Webhook の利用を有効化する。
- [x] 応答メッセージを無効化する。Bot 独自実装の返信と競合させない。
- [x] あいさつメッセージを無効化する。不要な自動送信を避ける。
- [x] 対象者の LINE アカウントで Bot を友だち追加し、メッセージ受信ができることを確認する。
- [x] 管理者自身の LINE アカウントでも Bot を友だち追加し、必要ならテスト受信に使えるようにする。

## Slack 設定

- [x] 管理者通知用の Slack チャンネルを作成する。
- [x] Slack Incoming Webhook を作成し、通知先チャンネルを紐付ける。
- [x] 発行された Webhook URL を安全な場所に保管する。
- [ ] 通知文面の受け取り先とメンション方針を決める。必要なら専用チャンネルに集約する。

## Cloudflare Tunnel 設定

- [x] Cloudflare アカウントを用意する。
- [x] Tunnel を作成し、対象サーバーへ接続するための認証情報を取得する。
- [x] Tunnel 作成後に発行される公開 URL を確認し、Webhook 用の URL として控える。
- [x] Tunnel から api コンテナの HTTP ポートへ転送する設定を作る。
- [x] 外部から /healthz へ到達できることを確認する。公開経路の基礎疎通確認として実施する。
- [ ] 外部から /webhook へ到達できることを確認する。

### Cloudflare 作業メモ

#### ここまでに実施した手順

- [x] Cloudflare Zero Trust で Tunnel を作成する。
- [x] Public Hostname に `alive-bot.hacksaw.work` を設定する。
- [x] Service URL に `http://api:8000` を設定する。`cloudflared` を Docker Compose に組み込んでいるため、`localhost` ではなく Compose のサービス名を使う。
- [x] `.env` に `CLOUDFLARE_TUNNEL_TOKEN` を設定する。
- [x] 次のコマンドで `cloudflared` を含む Compose を起動する。

```sh
docker compose up -d --build
```

1. 次のコマンドで公開経路の基礎疎通を確認する。

```sh
curl https://alive-bot.hacksaw.work/healthz
```

- [x] `{"status":"ok"}` を含む応答が返ることを確認する。

#### 以降の手順

- [x] Cloudflare Tunnel token を rotate する。過去にシェルへ直打ちした token は使い続けない。
- [ ] API に `POST /webhook` を実装した状態をデプロイする。
- [ ] 外部から `https://alive-bot.hacksaw.work/webhook` へ到達できることを確認する。
- [x] LINE Developers で Channel Access Token を発行し、安全な場所に保管する。
- [x] LINE Developers の Webhook URL に `https://alive-bot.hacksaw.work/webhook` を設定する。
- [x] Webhook の利用を有効化する。
- [ ] LINE Developers の Webhook 検証を実行し、成功することを確認する。
- [ ] Slack 通知文面、初期の送信時刻、`alert_after_hours`、本番用の環境変数一覧を確定する。
- [ ] 初回疎通確認の 4 項目を順に実施する。

## 本番設定値の確定

- [ ] 初期の送信時刻を決める。例: 09:00、12:00、18:00。
- [ ] alert_after_hours の初期値を決める。例: 3。
- [ ] Slack 通知先チャンネルを確定する。
- [ ] Webhook 公開 URL を確定する。Cloudflare Tunnel の発行 URL に /webhook を付与した値を使う。
- [ ] 本番用の環境変数一覧を埋める。少なくとも LINE の認証情報、Slack Webhook URL、公開 URL、タイムゾーンを整理する。

## 初回疎通確認

- [ ] LINE Developers の Webhook 検証を実行し、成功することを確認する。
- [ ] 手動で安否確認メッセージを送信し、対象者の LINE に届くことを確認する。
- [ ] ボタン押下後に success へ更新され、確認メッセージが返ることを確認する。
- [ ] 未返信状態を意図的に作り、Slack にアラートが届くことを確認する。

## 運用開始前の確認

- [ ] 家族向けの案内文を用意する。ボタンを押すだけでよいことを明確にする。
- [ ] 返信が無い場合の連絡フローを決める。誰が何分後に何をするかを明確にする。
- [ ] 管理者が不在のときの代替連絡先が必要かを判断する。
- [ ] 定期的に確認する運用項目を決める。例: 月1回の疎通確認、トークン期限確認、通知先見直し。
