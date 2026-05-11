# ToDo

## 実装タスク

- [ ] アプリの実装ランタイムを確定する。Python FastAPI を第一候補とし、依存管理方針を決める。
- [ ] Docker Compose 構成を作る。少なくとも api コンテナ、scheduler コンテナ、永続化ボリュームを定義する。
- [ ] アプリ共通基盤を作る。環境変数読み込み、設定管理、ログ出力、ヘルスチェックエンドポイントを実装する。
- [ ] SQLite の初期スキーマを作る。check_ins、message_schedules、app_settings を作成する。
- [ ] 初期データ投入処理を作る。alert_after_hours とサンプルの daily スケジュールを登録できるようにする。
- [ ] message_schedules の CRUD を提供する管理用 API を実装する。将来 GUI から更新できる前提を作る。
- [ ] app_settings の CRUD を提供する管理用 API を実装する。アラート閾値を更新できるようにする。
- [ ] scheduler ワーカーを実装する。1分ごとに JST で現在時刻を判定し、daily の有効スケジュールを処理する。
- [ ] 重複送信防止を実装する。同一 schedule_id と同一日付で check_ins を重複作成しないようにする。
- [ ] LINE メッセージ送信処理を実装する。Flex Message と postback データを組み立てて送信する。
- [ ] POST /webhook を実装する。X-Line-Signature の検証と postback 受信を行う。
- [ ] 返信処理を実装する。対象 check_ins を success に更新し、確認メッセージを返す。
- [ ] 未返信監視処理を実装する。一定間隔で pending を走査し、alert_after_hours 超過を検知する。
- [ ] Slack 通知処理を実装する。異常検知時と死活監視失敗時に通知できるようにする。
- [ ] 安否確認履歴の参照 API を実装する。後から確認できるように一覧取得を用意する。
- [ ] cloudflared を含む公開経路を構成する。Webhook を受けられるようにする。
- [ ] GitHub Actions の死活監視 workflow を作る。ヘルスチェック失敗時に Slack へ通知する。
- [ ] Docker 前提の起動手順と設定手順を README などにまとめる。
- [ ] テストを追加する。スケジュール判定、Webhook 検証、未返信アラート、Slack 通知の主要ケースを確認する。

利用者側の作業は todo_user.md を参照する。
