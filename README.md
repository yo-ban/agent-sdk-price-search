# price-search

Claude Agent SDK を使って商品の価格調査を CLI から実行するサンプル実装です。

---

## Features

- エージェント本体( `price-search-core` )
  - Claude Agent SDK を使って価格調査を実行し、`web-search` による候補 URL 発見と `playwright-cli` によるページ検証を組み合わせて、構造化 JSON を返します。
- ランチャー(`price-search-launcher`)
  - run ごとに `/tmp/price-search-workspace-*` のような一時 workspace を作り、必要な wrapper・設定・補助ファイルだけをコピーしてからエージェントを起動します。
- フロントエンド( `price-search-web-api` , `frontend` )
  - run の作成・進捗確認・停止・履歴参照を提供し、CLI を直接叩かなくても価格調査を操作できます。

---

## Prerequisites

| 要件 | 備考 |
|------|------|
| Claude Code v2.1.92+ | *常に最新で動くか不明 |
| Python 3.11+ | |
| `uv` | パッケージ管理・実行 |
| Node.js 20+ | frontend の build / dev server 用 |
| `docker` | Playwright runtime 用 |

---

## Setup

```bash
uv sync --group dev
cd frontend
npm install
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
│   ├── web-search-cli/             # discovery 用検索 CLI
│   └── snapshot-inspect-cli/       # Playwright snapshot 要約・検索 CLI
├── frontend/                       # Web UI
├── workspace_assets/               # temp workspace へコピーする wrapper / skill / helper
├── infra/                          # Docker Compose / image 定義
├── config/                         # 設定ファイル
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

`config/price_search.toml` 例:

```toml
# Shared defaults for this repository.
# Keep secrets out of this file. Use env vars or config/price_search.local.toml instead.

# bedrock
[claude]
provider = "bedrock"
primary_model = "arn:aws:bedrock:ap-northeast-1:874712576047:application-inference-profile/ldjo9vpl86ui"
primary_model_capabilities = "max_effort,thinking"
small_model = "arn:aws:bedrock:ap-northeast-1:874712576047:application-inference-profile/h9ylt4gw0g7k"
small_model_capabilities = "effort,max_effort,thinking,adaptive_thinking,interleaved_thinking"

[aws]
region = "ap-northeast-1"
profile = "svc"

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

[discovery]
provider = "brave"

[brave]
endpoint = "https://api.search.brave.com/res/v1/web/search"
country = "JP"
search_lang = "jp"
ui_lang = "ja-JP"
result_filter = ["web"]
extra_snippets = true
```

`config/price_search.local.toml` 例:

```toml
[brave]
api_key = "xxxxxxxxxxxxxxx"
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
| `PRICE_SEARCH_PRIMARY_MODEL_CAPABILITIES` | primary model capability 上書き |
| `PRICE_SEARCH_SMALL_MODEL_CAPABILITIES` | small model capability 上書き |
| `PRICE_SEARCH_AGENT_THINKING_TYPE` | `enabled` / `adaptive` / `disabled` |
| `PRICE_SEARCH_AGENT_THINKING_BUDGET_TOKENS` | thinking budget tokens |
| `PRICE_SEARCH_AGENT_EFFORT` | `low` / `medium` / `high` / `max` |
| `PRICE_SEARCH_MAX_TURNS` | エージェント最大ターン数 |
| `PRICE_SEARCH_MAX_OFFERS` | 収集する価格候補の最大数 |
| `PRICE_SEARCH_MARKET` | 市場コード（例: `JP`） |
| `PRICE_SEARCH_CURRENCY` | 通貨コード（例: `JPY`） |
| `PRICE_SEARCH_AGENT_LOG_DIR` | エージェント行動ログ出力ディレクトリ |
| `PRICE_SEARCH_RESULT_OUTPUT_DIR` | 価格調査結果 JSON 出力ディレクトリ |
| `PRICE_SEARCH_SEARCH_PROVIDER` | discovery provider。default: `brave` |
| `PRICE_SEARCH_SEARXNG_ENGINES` | 使用する検索エンジン |
| `PRICE_SEARCH_SEARXNG_LANGUAGE` | 検索言語 |
| `PRICE_SEARCH_SEARXNG_RESULT_LIMIT` | 検索結果の上限数 |
| `BRAVE_API_KEY` | Brave Web Search API キー |
| `PRICE_SEARCH_BRAVE_ENDPOINT` | Brave Web Search エンドポイント |
| `PRICE_SEARCH_BRAVE_COUNTRY` | Brave `country` パラメータ |
| `PRICE_SEARCH_BRAVE_SEARCH_LANG` | Brave `search_lang` パラメータ |
| `PRICE_SEARCH_BRAVE_UI_LANG` | Brave `ui_lang` パラメータ |
| `PRICE_SEARCH_BRAVE_RESULT_FILTER` | Brave `result_filter`。CSV 形式 |
| `PRICE_SEARCH_BRAVE_EXTRA_SNIPPETS` | Brave `extra_snippets` の有効化 |

---

## Usage

### 1. Convenience Scripts（推奨）

日常的な起動には `tools/` 配下の wrapper を使います。

#### API + Frontend をまとめて起動

```bash
tools/start-web-stack.sh
```

> `start-web-stack.sh` は Web API をバックグラウンドで起動し、ヘルスチェック成功後に Frontend の dev server をフォアグラウンドで起動します。

#### エージェントのみ実行

```bash
tools/run-agent.sh "全自動コーヒーメーカー ABC-1234"
```

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

#### `web-search`（discovery 確認用）

Brave Web Search を直接使って候補 URL を確認します。
Brave Search APIキー確認: https://aws.amazon.com/marketplace/launch?productId=prod-eerurqrrqwhwk&ref_=aws-mp-console-subscription-table-action

```bash
export BRAVE_API_KEY="xxxxx"
uv run web-search "全自動コーヒーメーカー ABC-1234"
uv run web-search "全自動コーヒーメーカー ABC-1234" --include-domain example-shop.jp
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

## Infrastructure

### Browser Runtime（Playwright）

ブラウザ runtime は Docker 上の headed Chrome + Patchright core で動作します。通常の価格調査では `price-search-run` が runtime を確認してから agent を起動します。

| ファイル | 説明 |
|----------|------|
| `infra/docker/playwright/compose.yaml` | Docker Compose |
| `infra/docker/playwright/Dockerfile` | Dockerfile |

**runtime の個別管理:**

```bash
# 起動
docker compose -f infra/docker/playwright/compose.yaml up -d --build

# 停止
docker compose -f infra/docker/playwright/compose.yaml down
```

`PLAYWRIGHT_XVFB_SCREEN=1920x1080x24` と `PLAYWRIGHT_WINDOW_SIZE=1920,1080` が既定です。解像度を変えたい場合は `PLAYWRIGHT_XVFB_SCREEN=2560x1440x24 PLAYWRIGHT_WINDOW_SIZE=2560,1440 docker compose -f infra/docker/playwright/compose.yaml up -d --build` のように両方を揃えて指定します。

**動作方針:**

- browser launch は `headless = false` / `viewport = null` が既定（Patchright 推奨）
- browser window は `--window-size=1920,1080` を既定にしており、screenshot の視認性を確保する
- Docker 内では `chromiumSandbox = false` も明示
- container 名を変えたい場合は `PRICE_SEARCH_PLAYWRIGHT_CONTAINER_NAME` 環境変数を使います

---

## Agent Execution

`price-search-run` は一時 workspace を作成し、`workspace_assets/` から調査に必要な command と補助ファイルをコピーします。ここでは、workspace 内で agent が呼ぶ command と、それを支える補助ファイルを分けて示します。

### Workspace Commands

一時 workspace にコピーされ、agent が直接呼ぶ command です。

- `workspace_assets/bin/playwright-cli`
  - Playwright runtime container を呼び出す wrapper
  - container の自動 bootstrap は行わず、runtime が無い場合は unavailable error を返します
  - 実行中は一時 workspace 内に `.playwright-cli/` ディレクトリを作り、snapshot などの一時成果物を置きます
- `workspace_assets/bin/snapshot-inspect`
  - Playwright snapshot YAML の要約・検索 helper
- `workspace_assets/bin/web-search`
  - web-search wrapper

### Supporting Files

workspace command が内部で参照する補助ファイルです。

- `workspace_assets/playwright/cli.config.json`
  - Playwright CLI 設定
- `workspace_assets/playwright/filter_playwright_cli_output.py`
  - CLI 出力フィルター

### In-Process Tools

`price-search-core` が Claude Agent SDK に直接登録する tool です。

- `ReadImage`
  - 指定されたパスの画像を Claude に画像 input として渡します

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
