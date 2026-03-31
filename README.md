# price-search

Claude Agent SDK を使って商品の価格調査を CLI から実行するサンプル実装です。
Claude provider は **AWS Bedrock / Anthropic API / Claude Code サブスクリプション / OpenRouter** の 4 モードを切り替えられます。

---

## Features

- Claude provider 切り替え (`bedrock` / `anthropic` / `subscription` / `openrouter`)
- `searxng-search` による URL discovery + `playwright-cli` による価格ページ検証
- 構造化 JSON 出力による価格候補の正規化
- Hexagonal Architecture に沿った layer separation
- `price_search_launcher` による隔離 workspace 実行

---

## Prerequisites

| 要件 | 備考 |
|------|------|
| Python 3.11+ | |
| `uv` | パッケージ管理・実行 |
| `docker` | SearXNG / Playwright runtime 用 |
| Claude provider 認証 | 下記参照 |

**Provider ごとの認証:**

- `bedrock`: AWS Bedrock で Anthropic Claude モデルへのアクセス権が必要
- `anthropic`: `ANTHROPIC_API_KEY` 環境変数、または `config/price_search.local.toml` の `claude.anthropic_api_key`
- `subscription`: Claude Code にログイン済みのローカル環境（追加設定不要）
- `openrouter`: `OPENROUTER_API_KEY` 環境変数、または `config/price_search.local.toml` の `claude.openrouter_api_key`

`openrouter` では Anthropic-compatible な接続情報を Claude Code 子プロセスにだけ渡します。このアプリケーションの実行では、global shell profile への恒久設定を前提にしません。

---

## Setup

```bash
uv sync --group dev
```

---

## Workspace Layout

uv workspace による Python パッケージ分割と、周辺アセットの配置です。

```
price_search_agent/
├── packages/
│   └── price-search-core/          # 価格調査エージェント本体
├── apps/
│   ├── price-search-launcher/      # 隔離 workspace 実行 + runtime 準備
│   ├── price-search-web-api/       # frontend 向け HTTP API
│   ├── searxng-search-cli/         # discovery 用検索 CLI
│   └── snapshot-inspect-cli/       # Playwright snapshot 要約・検索 CLI
├── frontend/                       # Web UI
├── workspace_assets/               # temp workspace へ複写する wrapper / skill / helper
├── infra/                          # Docker Compose / image 定義
├── config/                         # 共有設定ファイル
└── tools/                          # 日常的な起動用 wrapper スクリプト
```

---

## Configuration

### 設定ファイル

既定では次の順で設定を解決します。

1. `config/price_search.toml` （リポジトリ共有・git 管理）
2. `config/price_search.local.toml` （個人上書き・gitignore 対象）
3. 環境変数（最優先）

shared config には secret を置かず、個人用の `config/price_search.local.toml` または環境変数を使います。

現在の `config/price_search.toml`:

```toml
[claude]
provider = "subscription"
primary_model = "claude-sonnet-4-6"
small_model = "claude-haiku-4-5"

[agent]
thinking_type = "enabled"
thinking_budget_tokens = 4096
effort = "high"
max_turns = 999
max_offers = 3

[market]
code = "JP"
currency = "JPY"

[output]
agent_activity_log_dir = "logs"
result_output_dir = "out"

[searxng]
search_url = "http://127.0.0.1:18888/search"
engines = ["brave", "google", "duckduckgo"]
language = "ja-JP"
result_limit = 8

[workspace]
root = "."
```

個人用の `config/price_search.local.toml` 例:

```toml
[claude]
provider = "openrouter"
openrouter_api_key = "..."

# anthropic を使う場合
# anthropic_api_key = "..."
```

### 環境変数一覧

| 環境変数 | 説明 |
|----------|------|
| `PRICE_SEARCH_CLAUDE_PROVIDER` | `bedrock` / `anthropic` / `subscription` / `openrouter` |
| `PRICE_SEARCH_CONFIG_FILE` | 設定ファイルパス上書き |
| `PRICE_SEARCH_LOCAL_CONFIG_FILE` | ローカル設定ファイルパス上書き |
| `ANTHROPIC_API_KEY` | Anthropic API キー |
| `OPENROUTER_API_KEY` | OpenRouter API キー |
| `PRICE_SEARCH_AWS_REGION` | AWS リージョン（bedrock 用） |
| `PRICE_SEARCH_AWS_PROFILE` | AWS プロファイル（bedrock 用） |
| `PRICE_SEARCH_MODEL` | primary model 上書き |
| `PRICE_SEARCH_SMALL_MODEL` | small model 上書き |
| `PRICE_SEARCH_AGENT_THINKING_TYPE` | `enabled` / `adaptive` / `disabled` |
| `PRICE_SEARCH_AGENT_THINKING_BUDGET_TOKENS` | thinking budget tokens |
| `PRICE_SEARCH_AGENT_EFFORT` | `low` / `medium` / `high` / `max` |
| `PRICE_SEARCH_MAX_TURNS` | エージェント最大ターン数 |
| `PRICE_SEARCH_MAX_OFFERS` | 収集する価格候補の最大数 |
| `PRICE_SEARCH_MARKET` | 市場コード（例: `JP`） |
| `PRICE_SEARCH_CURRENCY` | 通貨コード（例: `JPY`） |
| `PRICE_SEARCH_AGENT_LOG_DIR` | エージェント行動ログ出力ディレクトリ |
| `PRICE_SEARCH_RESULT_OUTPUT_DIR` | 価格調査結果 JSON 出力ディレクトリ |
| `PRICE_SEARCH_SEARXNG_SEARCH_URL` | SearXNG 検索エンドポイント |
| `PRICE_SEARCH_SEARXNG_ENGINES` | 使用する検索エンジン |
| `PRICE_SEARCH_SEARXNG_LANGUAGE` | 検索言語 |
| `PRICE_SEARCH_SEARXNG_RESULT_LIMIT` | 検索結果の上限数 |
| `PRICE_SEARCH_WORKSPACE_ROOT` | 一時 workspace ルートパス |

**Bedrock 利用時の推奨 model ID:**

- `PRICE_SEARCH_MODEL=global.anthropic.claude-sonnet-4-6`
- `PRICE_SEARCH_SMALL_MODEL=global.anthropic.claude-haiku-4-5-20251001-v1:0`

**OpenRouter 利用時の推奨 model ID:**

- `PRICE_SEARCH_MODEL=anthropic/claude-sonnet-4.6`
- `PRICE_SEARCH_SMALL_MODEL=anthropic/claude-haiku-4.5`

---

## Usage

### 1. Convenience Scripts（推奨）

日常的な起動には `tools/` 配下の wrapper を使います。

#### エージェントのみ実行

```bash
tools/run-agent.sh "全自動コーヒーメーカー ABC-1234"
```

#### Web API のみ起動

```bash
tools/start-web-api.sh
tools/start-web-api.sh --host 0.0.0.0 --port 18000
```

#### Frontend のみ起動

```bash
tools/start-frontend.sh
tools/start-frontend.sh --host 0.0.0.0 --port 5174
```

#### API + Frontend をまとめて起動

```bash
tools/start-web-stack.sh
tools/start-web-stack.sh --api-host 0.0.0.0 --api-port 18000 --frontend-host 0.0.0.0 --frontend-port 5174
```

> `start-web-stack.sh` は Web API をバックグラウンドで起動し、ヘルスチェック成功後に Frontend の dev server をフォアグラウンドで起動します。

#### ログビューア

`tools/log-viewer.html` をブラウザで開くと、`logs/` 配下の JSONL 行動ログを確認できます。

---

### 2. Package Entry Points（直接実行）

#### `price-search-run`（通常利用向けランチャー）

runtime の確認と一時 workspace の作成を行い、その上で `price_search` を起動します。`logs/` と `out/` はランチャーを起動したディレクトリへ出力されます。

```bash
uv run price-search-run "全自動コーヒーメーカー ABC-1234"
```

JSON 出力:

```bash
uv run price-search-run "全自動コーヒーメーカー ABC-1234" -- --json
```

出力先を指定:

```bash
uv run price-search-run "全自動コーヒーメーカー ABC-1234" -- --json --output-file out/coffeemachine.json
```

#### `price-search`（エージェント直接実行）

隔離 workspace や runtime 準備を含まない、エージェント本体の直接実行です。

```bash
uv run price-search "全自動コーヒーメーカー ABC-1234"
uv run price-search "全自動コーヒーメーカー ABC-1234" --json
```

#### `price-search-web-api`（HTTP API）

Frontend から価格調査 run を作成・取得・停止・削除するための HTTP API です。

```bash
uv run price-search-web-api --host 127.0.0.1 --port 8000
```

疎通確認:

```bash
curl http://127.0.0.1:8000/api/health
```

#### `searxng-search`（discovery 確認用）

SearXNG を直接叩いて候補 URL を確認します。

```bash
uv run searxng-search "全自動コーヒーメーカー ABC-1234"
uv run searxng-search "全自動コーヒーメーカー ABC-1234" --include-domain example-shop.jp --include-domain yodobashi.com
```

#### `snapshot-inspect`（Playwright snapshot 確認用）

Playwright snapshot YAML を要約・検索する補助 CLI です。raw で読む前に要素候補を絞りたいときに使います。

```bash
uv run snapshot-inspect summary /tmp/example.yaml
uv run snapshot-inspect controls /tmp/example.yaml
uv run snapshot-inspect find /tmp/example.yaml --text "Add to cart"
```

#### `frontend`（Web UI）

`price-search-web-api` と組み合わせて使います。

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

ビルド確認:

```bash
cd frontend
npm run build
```

---

### 3. Provider 別の実行例

#### AWS Bedrock

```bash
export PRICE_SEARCH_CLAUDE_PROVIDER=bedrock
export AWS_PROFILE=your-aws-profile
export AWS_REGION=your-aws-region

uv run price-search-run "全自動コーヒーメーカー ABC-1234"
```

#### Anthropic API

```bash
export PRICE_SEARCH_CLAUDE_PROVIDER=anthropic
export ANTHROPIC_API_KEY=your-api-key

uv run price-search-run "全自動コーヒーメーカー ABC-1234"
```

#### Claude Code Subscription

```bash
export PRICE_SEARCH_CLAUDE_PROVIDER=subscription

uv run price-search-run "全自動コーヒーメーカー ABC-1234"
```

---

## Infrastructure

### Browser Skill（Playwright）

ブラウザ操作は official project skill と Docker wrapper で実行します。通常の価格調査では `price-search-run` が runtime を確認してから agent を起動します。

| ファイル | 説明 |
|----------|------|
| `workspace_assets/bin/playwright-cli` | Docker wrapper |
| `workspace_assets/bin/snapshot-inspect` | snapshot helper |
| `workspace_assets/playwright/cli.config.json` | CLI 設定 |
| `workspace_assets/playwright/filter_playwright_cli_output.py` | 出力フィルター |
| `infra/docker/playwright/compose.yaml` | Docker Compose |
| `infra/docker/playwright/Dockerfile` | Dockerfile |

**runtime の個別管理:**

```bash
# 起動
docker compose -f infra/docker/playwright/compose.yaml up -d --build

# 停止
docker compose -f infra/docker/playwright/compose.yaml down
```

**動作方針:**

- browser launch は `headless = false` / `viewport = null` が既定（Patchright 推奨）
- Docker 内では `chromiumSandbox = false` も明示
- `workspace_assets/bin/playwright-cli` は container の自動 bootstrap を行いません。runtime が無い場合は unavailable エラーを返します
- container 名を変えたい場合は `PRICE_SEARCH_PLAYWRIGHT_CONTAINER_NAME` 環境変数を使います
- token 効率を優先し、`snapshot` より `eval` / `run-code` を優先します。`snapshot` は click や fill に要素 ref が必要な場合に限定し、取得後は `snapshot-inspect summary/find/controls` で候補を絞ってから参照します

---

### Discovery Runtime（SearXNG）

API キー不要の検索 discovery は self-hosted SearXNG + local CLI で実行します。

| ファイル | 説明 |
|----------|------|
| `workspace_assets/bin/searxng-search` | wrapper |
| `apps/searxng-search-cli/` | Python パッケージ本体 |
| `infra/docker/searxng/compose.yaml` | Docker Compose |
| `infra/docker/searxng/settings.yml` | SearXNG 設定 |

**runtime の個別管理:**

```bash
# 起動
docker compose -f infra/docker/searxng/compose.yaml up -d

# 停止
docker compose -f infra/docker/searxng/compose.yaml down
```

**JSON API 疎通確認:**

```bash
curl 'http://127.0.0.1:18888/search?q=playwright&format=json&engines=wikipedia'
```

---

## Observability

### エージェント行動ログ

Agent SDK の行動ログは JSONL 形式で run ごとに保存されます。

- **保存先**: `logs/price_search_agent_activity-<timestamp>-<slug>-<runid>.jsonl`

記録されるイベント:

| イベント | 説明 |
|----------|------|
| `research_started` | 調査開始 |
| `system_message` | システムプロンプト |
| `assistant_message` | アシスタント応答（`tool_use` を含む） |
| `user_message` | ユーザーメッセージ（`tool_result` を含む） |
| `result_message` | 最終結果 |
| `task_*` | stream messages |

最新ログの確認:

```bash
tail -n 20 "$(ls -1t logs/price_search_agent_activity-*.jsonl | head -n 1)"
```

ブラウザで確認:

```bash
open tools/log-viewer.html
```

### 価格調査結果

結果 JSON は既定で `out/` 配下に保存されます。`--output-file` オプションで保存先を指定できます。

---

## Notes

- `PRICE_SEARCH_CLAUDE_PROVIDER=subscription` では provider 強制用の環境変数を SDK 子プロセスに渡さず、Claude Code の既存ログイン状態を使います
- Web 上の価格は変動するため、出力結果は実行時点のスナップショットです
- `price-search-run` は SearXNG と Playwright runtime を確認してから、`price_search` package を一時 workspace で起動します。`.playwright-cli/` は実行中の一時 workspace 内に生成される一時ファイルです

## License

This repository is licensed under MIT-0. See [LICENSE](LICENSE).
