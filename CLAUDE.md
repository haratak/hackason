## プロジェクトの大前提

### ハッカソンプロジェクトとしての開発
- このプロジェクトは**ハッカソン**として開発しているため、以下の点は考慮しません：
  - 料金設計・課金システム
  - プライバシーポリシーの詳細設計
  - 本番サービス運用に関わる法的要件
  - セキュリティの詳細実装
- **提供する価値や機能の実装に集中**してください

### 技術スタックの統一
- **クラウドサービスは全てGCPに統一**
  - Cloud Run, Cloud Storage, Firestore, Vertex AI など
  - AWS、Azure、その他のクラウドサービスは使用しない
- **LLMモデルもGCP（Vertex AI）で利用可能なものを選定**
  - Gemini Pro, Gemini Pro Vision など
  - OpenAI API、Claude API などの外部APIは使用しない
- **その他のサービスもGCPエコシステム内で完結**
  - 認証: Firebase Authentication（GCP傘下）
  - 監視: Cloud Monitoring
  - ログ: Cloud Logging

## Project Infrastructure

- このプロダクトのプロダクション環境はGCPによって構成する