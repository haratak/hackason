.PHONY: init install test format lint typecheck clean clean-output run example dev-install

# 初期セットアップ（仮想環境作成と依存関係インストール）
init:
	uv venv
	uv pip install -e .

# Python仮想環境のセットアップ（initのエイリアス）
install: init

# 開発環境のセットアップ（開発ツール含む）
dev-install:
	uv venv
	uv pip install -e ".[dev]"

# 基本的なサンプルを実行
run:
	uv run python examples/basic_example.py

# 別名でサンプル実行
example: run

# テストの実行
test:
	uv run pytest

# コードフォーマット
format:
	uv run black src/
	uv run ruff check src/ --fix

# リンターの実行
lint:
	uv run ruff check src/
	uv run black src/ --check

# 型チェック
typecheck:
	uv run mypy src/

# クリーンアップ
clean:
	rm -rf .venv
	rm -rf __pycache__
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf .ruff_cache
	rm -rf src/**/__pycache__
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf src/*.egg-info

# 出力ファイルのクリーンアップ
clean-output:
	rm -rf examples/output/*.html
	rm -rf examples/output/*.pdf
	rm -rf examples/output/*.png

# 環境変数のセットアップヘルプ
env-setup:
	@echo "環境変数の設定:"
	@echo "1. .env ファイルを作成:"
	@echo "   cp .env.example .env"
	@echo "2. GOOGLE_API_KEY を設定してください"

# macOS用のWeasyPrint依存関係インストール（オプション）
install-weasyprint-deps:
	@echo "WeasyPrint の依存関係をインストール (macOS):"
	@echo "brew install cairo pango gdk-pixbuf libffi"

# すべての開発タスク実行
all: format lint typecheck test