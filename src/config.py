"""Application configuration using Pydantic settings."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Slack
    slack_bot_token: str = Field(..., description="Slack Bot OAuth Token")
    slack_app_token: str = Field(..., description="Slack App-Level Token for Socket Mode")
    slack_signing_secret: str = Field(..., description="Slack Signing Secret")

    # Anthropic
    anthropic_api_key: str = Field(..., description="Anthropic API Key")
    claude_model: str = Field(
        default="claude-sonnet-4-5-20250929", description="Claude model to use"
    )

    # OpenAI (for embeddings)
    openai_api_key: str = Field(..., description="OpenAI API Key")
    embedding_model: str = Field(
        default="text-embedding-3-small", description="OpenAI embedding model"
    )

    # Pinecone
    pinecone_api_key: str = Field(..., description="Pinecone API Key")
    pinecone_index_name: str = Field(default="project-brain", description="Pinecone index name")
    pinecone_namespace: str = Field(default="default", description="Pinecone namespace")

    # Redis
    redis_url: str = Field(default="redis://localhost:6379", description="Redis connection URL")
    cache_ttl_seconds: int = Field(default=300, description="Default cache TTL in seconds")

    # Linear
    linear_api_key: str = Field(default="", description="Linear API Key")
    linear_team_id: str = Field(default="", description="Linear Team ID")

    # Notion
    notion_api_key: str = Field(default="", description="Notion Integration Token")
    notion_database_ids: str = Field(default="", description="Comma-separated Notion database IDs")

    # GitHub
    github_token: str = Field(default="", description="GitHub Personal Access Token")
    github_repos: str = Field(default="", description="Comma-separated GitHub repos (owner/repo)")

    # Mixpanel
    mixpanel_api_secret: str = Field(default="", description="Mixpanel API Secret")
    mixpanel_project_id: str = Field(default="", description="Mixpanel Project ID")

    # Datadog
    datadog_api_key: str = Field(default="", description="Datadog API Key")
    datadog_app_key: str = Field(default="", description="Datadog Application Key")
    datadog_site: str = Field(default="datadoghq.com", description="Datadog site")

    # Sync settings
    sync_interval_minutes: int = Field(default=30, description="Background sync interval")
    chunk_size: int = Field(default=1000, description="Document chunk size for embeddings")
    chunk_overlap: int = Field(default=200, description="Overlap between chunks")

    # RAG settings
    retrieval_top_k: int = Field(default=5, description="Number of results to retrieve")
    similarity_threshold: float = Field(default=0.7, description="Minimum similarity score")

    @property
    def notion_database_id_list(self) -> list[str]:
        """Parse comma-separated Notion database IDs."""
        if not self.notion_database_ids:
            return []
        return [db_id.strip() for db_id in self.notion_database_ids.split(",") if db_id.strip()]

    @property
    def github_repo_list(self) -> list[str]:
        """Parse comma-separated GitHub repos."""
        if not self.github_repos:
            return []
        return [repo.strip() for repo in self.github_repos.split(",") if repo.strip()]


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
