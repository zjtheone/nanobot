"""Configuration schema using Pydantic."""

from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field, ConfigDict
from pydantic_settings import BaseSettings


class WhatsAppConfig(BaseModel):
    """WhatsApp channel configuration."""

    enabled: bool = False
    bridge_url: str = "ws://localhost:3001"
    allow_from: list[str] = Field(default_factory=list)  # Allowed phone numbers


class TelegramConfig(BaseModel):
    """Telegram channel configuration."""

    enabled: bool = False
    token: str = ""  # Bot token from @BotFather
    allow_from: list[str] = Field(default_factory=list)  # Allowed user IDs or usernames
    proxy: str | None = (
        None  # HTTP/SOCKS5 proxy URL, e.g. "http://127.0.0.1:7890" or "socks5://127.0.0.1:1080"
    )


class FeishuConfig(BaseModel):
    """Feishu/Lark channel configuration using WebSocket long connection."""

    enabled: bool = False
    app_id: str = ""  # App ID from Feishu Open Platform
    app_secret: str = ""  # App Secret from Feishu Open Platform
    encrypt_key: str = ""  # Encrypt Key for event subscription (optional)
    verification_token: str = ""  # Verification Token for event subscription (optional)
    allow_from: list[str] = Field(default_factory=list)  # Allowed user open_ids


class DingTalkConfig(BaseModel):
    """DingTalk channel configuration using Stream mode."""

    enabled: bool = False
    client_id: str = ""  # AppKey
    client_secret: str = ""  # AppSecret
    allow_from: list[str] = Field(default_factory=list)  # Allowed staff_ids


class DiscordConfig(BaseModel):
    """Discord channel configuration."""

    enabled: bool = False
    token: str = ""  # Bot token from Discord Developer Portal
    allow_from: list[str] = Field(default_factory=list)  # Allowed user IDs
    gateway_url: str = "wss://gateway.discord.gg/?v=10&encoding=json"
    intents: int = 37377  # GUILDS + GUILD_MESSAGES + DIRECT_MESSAGES + MESSAGE_CONTENT


class EmailConfig(BaseModel):
    """Email channel configuration (IMAP inbound + SMTP outbound)."""

    enabled: bool = False
    consent_granted: bool = False  # Explicit owner permission to access mailbox data

    # IMAP (receive)
    imap_host: str = ""
    imap_port: int = 993
    imap_username: str = ""
    imap_password: str = ""
    imap_mailbox: str = "INBOX"
    imap_use_ssl: bool = True

    # SMTP (send)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False
    from_address: str = ""

    # Behavior
    auto_reply_enabled: bool = (
        True  # If false, inbound email is read but no automatic reply is sent
    )
    poll_interval_seconds: int = 30
    mark_seen: bool = True
    max_body_chars: int = 12000
    subject_prefix: str = "Re: "
    allow_from: list[str] = Field(default_factory=list)  # Allowed sender email addresses


class MochatMentionConfig(BaseModel):
    """Mochat mention behavior configuration."""

    require_in_groups: bool = False


class MochatGroupRule(BaseModel):
    """Mochat per-group mention requirement."""

    require_mention: bool = False


class MochatConfig(BaseModel):
    """Mochat channel configuration."""

    enabled: bool = False
    base_url: str = "https://mochat.io"
    socket_url: str = ""
    socket_path: str = "/socket.io"
    socket_disable_msgpack: bool = False
    socket_reconnect_delay_ms: int = 1000
    socket_max_reconnect_delay_ms: int = 10000
    socket_connect_timeout_ms: int = 10000
    refresh_interval_ms: int = 30000
    watch_timeout_ms: int = 25000
    watch_limit: int = 100
    retry_delay_ms: int = 500
    max_retry_attempts: int = 0  # 0 means unlimited retries
    claw_token: str = ""
    agent_user_id: str = ""
    sessions: list[str] = Field(default_factory=list)
    panels: list[str] = Field(default_factory=list)
    allow_from: list[str] = Field(default_factory=list)
    mention: MochatMentionConfig = Field(default_factory=MochatMentionConfig)
    groups: dict[str, MochatGroupRule] = Field(default_factory=dict)
    reply_delay_mode: str = "non-mention"  # off | non-mention
    reply_delay_ms: int = 120000


class SlackDMConfig(BaseModel):
    """Slack DM policy configuration."""

    enabled: bool = True
    policy: str = "open"  # "open" or "allowlist"
    allow_from: list[str] = Field(default_factory=list)  # Allowed Slack user IDs


class SlackConfig(BaseModel):
    """Slack channel configuration."""

    enabled: bool = False
    mode: str = "socket"  # "socket" supported
    webhook_path: str = "/slack/events"
    bot_token: str = ""  # xoxb-...
    app_token: str = ""  # xapp-...
    user_token_read_only: bool = True
    group_policy: str = "mention"  # "mention", "open", "allowlist"
    group_allow_from: list[str] = Field(default_factory=list)  # Allowed channel IDs if allowlist
    dm: SlackDMConfig = Field(default_factory=SlackDMConfig)


class QQConfig(BaseModel):
    """QQ channel configuration using botpy SDK."""

    enabled: bool = False
    app_id: str = ""  # 机器人 ID (AppID) from q.qq.com
    secret: str = ""  # 机器人密钥 (AppSecret) from q.qq.com
    allow_from: list[str] = Field(
        default_factory=list
    )  # Allowed user openids (empty = public access)


class ChannelsConfig(BaseModel):
    """Configuration for chat channels."""

    whatsapp: WhatsAppConfig = Field(default_factory=WhatsAppConfig)
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    discord: DiscordConfig = Field(default_factory=DiscordConfig)
    feishu: FeishuConfig = Field(default_factory=FeishuConfig)
    mochat: MochatConfig = Field(default_factory=MochatConfig)
    dingtalk: DingTalkConfig = Field(default_factory=DingTalkConfig)
    email: EmailConfig = Field(default_factory=EmailConfig)
    slack: SlackConfig = Field(default_factory=SlackConfig)
    qq: QQConfig = Field(default_factory=QQConfig)


class AgentDefaults(BaseModel):
    """Default agent configuration."""

    workspace: str = "~/.nanobot/workspace"
    model: str = "anthropic/claude-opus-4-5"
    max_tokens: int = 8192
    temperature: float = 0.7
    frequency_penalty: float = 0.0
    max_tool_iterations: int = 20
    context_window: int = 200000  # chars (~50K tokens), trim old tool results when exceeded
    auto_verify: bool = True  # Auto-run build/test after code changes
    auto_verify_command: str = ""  # Custom verify command (empty = auto-detect project type)
    sandbox: bool = False  # Enable Docker sandbox for execution
    permission_mode: str = "auto"  # auto | confirm_writes | confirm_all | yolo
    thinking_budget: int = 0  # Extended thinking token budget (0 = disabled)


class AgentsConfig(BaseModel):
    """Agent configuration."""

    defaults: AgentDefaults = Field(default_factory=AgentDefaults)


class ProviderConfig(BaseModel):
    """LLM provider configuration."""

    api_key: str = ""
    api_base: str | None = None
    extra_headers: dict[str, str] | None = None  # Custom headers (e.g. APP-Code for AiHubMix)


class ProvidersConfig(BaseModel):
    """Configuration for LLM providers."""

    custom: ProviderConfig = Field(default_factory=ProviderConfig)
    anthropic: ProviderConfig = Field(default_factory=ProviderConfig)
    openai: ProviderConfig = Field(default_factory=ProviderConfig)
    openrouter: ProviderConfig = Field(default_factory=ProviderConfig)
    deepseek: ProviderConfig = Field(default_factory=ProviderConfig)
    groq: ProviderConfig = Field(default_factory=ProviderConfig)
    zhipu: ProviderConfig = Field(default_factory=ProviderConfig)
    dashscope: ProviderConfig = Field(default_factory=ProviderConfig)  # 阿里云通义千问
    vllm: ProviderConfig = Field(default_factory=ProviderConfig)
    gemini: ProviderConfig = Field(default_factory=ProviderConfig)
    moonshot: ProviderConfig = Field(default_factory=ProviderConfig)
    minimax: ProviderConfig = Field(default_factory=ProviderConfig)
    aihubmix: ProviderConfig = Field(default_factory=ProviderConfig)  # AiHubMix API gateway


class GatewayConfig(BaseModel):
    """Gateway/server configuration."""

    host: str = "0.0.0.0"
    port: int = 18790


class WebSearchConfig(BaseModel):
    """Web search tool configuration."""

    api_key: str = ""  # Brave Search API key
    max_results: int = 5


class WebToolsConfig(BaseModel):
    """Web tools configuration."""

    search: WebSearchConfig = Field(default_factory=WebSearchConfig)


class ExecToolConfig(BaseModel):
    """Shell exec tool configuration."""

    timeout: int = 60
    sandbox_image: str = "python:3.12-slim"


class ToolsConfig(BaseModel):
    """Tools configuration."""

    web: WebToolsConfig = Field(default_factory=WebToolsConfig)
    exec: ExecToolConfig = Field(default_factory=ExecToolConfig)
    restrict_to_workspace: bool = False  # If true, restrict all tool access to workspace directory


class MCPServerConfig(BaseModel):
    """Configuration for a single MCP server."""

    command: str = ""
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    enabled: bool = True


class MemorySearchConfig(BaseModel):
    """Memory search configuration."""

    enabled: bool = True
    max_distance: float = 0.4
    hybrid_weight: float = 0.5
    top_k: int = 10
    use_embedding_fallback: bool = True
    embedding_provider: str = "openai"  # openai, gemini, llama
    openai_api_key: str = ""
    openai_api_base: str = ""
    openai_model: str = "text-embedding-3-small"
    gemini_api_key: str = ""
    gemini_model: str = "models/text-embedding-004"
    llama_model_path: str = ""
    llama_n_gpu_layers: int = -1
    storage_path: str = "memory/vector"
    # File watching configuration
    watch_paths: list[str] = Field(default_factory=lambda: ["memory"])
    watch_interval: float = 5.0
    # Chunking configuration
    chunk_size: int = 20  # lines per chunk
    chunk_overlap: int = 0  # lines overlap between chunks
    chunk_boundary: str = "line"  # "line", "paragraph", "sentence", "markdown_heading", "semantic"
    semantic_boundary_threshold: float = 0.7  # similarity threshold for semantic segmentation
    # Enhanced hybrid search options
    query_parser_enabled: bool = True
    keyword_weight: float = 0.4
    vector_weight: float = 0.6
    rerank_method: str = "none"  # "none", "similarity", "cross_encoder"
    rerank_top_k: int = 20
    cross_encoder_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    score_normalization: bool = True
    score_rescaling: bool = False
    # Embedding provider configuration
    embedding_fallback_chain: list[str] = Field(
        default_factory=lambda: ["openai", "gemini", "sentence_transformer", "local_llama", "none"]
    )
    sentence_transformer_model: str = "all-MiniLM-L6-v2"
    embedding_cache_size: int = 1000
    # Vector search backend configuration
    vector_search_backend: str = "sqlite-vec"  # "sqlite-vec", "sqlite-vss", "none"
    sqlite_vss_extension_path: str = ""
    # Reranker fine-tuning
    reranker_device: str = "cpu"  # "cpu", "cuda", "mps"
    reranker_max_length: int = 512


class MCPConfig(BaseModel):
    """MCP (Model Context Protocol) configuration."""

    servers: dict[str, MCPServerConfig] = Field(default_factory=dict)


class Config(BaseSettings):
    """Root configuration for nanobot."""

    agents: AgentsConfig = Field(default_factory=AgentsConfig)
    channels: ChannelsConfig = Field(default_factory=ChannelsConfig)
    providers: ProvidersConfig = Field(default_factory=ProvidersConfig)
    gateway: GatewayConfig = Field(default_factory=GatewayConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    memory_search: MemorySearchConfig = Field(default_factory=MemorySearchConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)

    @property
    def workspace_path(self) -> Path:
        """Get expanded workspace path."""
        return Path(self.agents.defaults.workspace).expanduser()

    def _match_provider(
        self, model: str | None = None
    ) -> tuple["ProviderConfig | None", str | None]:
        """Match provider config and its registry name. Returns (config, spec_name)."""
        from nanobot.providers.registry import PROVIDERS, find_by_name

        model_lower = (model or self.agents.defaults.model).lower()
        model_prefix = model_lower.split("/", 1)[0] if "/" in model_lower else ""
        normalized_prefix = model_prefix.replace("-", "_")

        # Prefer explicit provider prefix match (e.g., "github-copilot/" -> github_copilot)
        for spec in PROVIDERS:
            if model_prefix and normalized_prefix == spec.name:
                p = getattr(self.providers, spec.name, None)
                # OAuth providers don't need api_key
                if spec.is_oauth:
                    return p or ProviderConfig(), spec.name
                if p and p.api_key:
                    return p, spec.name

        # Match by keyword (order follows PROVIDERS registry)
        for spec in PROVIDERS:
            p = getattr(self.providers, spec.name, None)
            if p and any(
                kw in model_lower or kw.replace("-", "_") in model_lower.replace("-", "_")
                for kw in spec.keywords
            ):
                # OAuth providers don't need api_key
                if spec.is_oauth:
                    return p or ProviderConfig(), spec.name
                if p.api_key:
                    return p, spec.name

        # Fallback: gateways first, then others (follows registry order)
        for spec in PROVIDERS:
            p = getattr(self.providers, spec.name, None)
            if p and p.api_key:
                return p, spec.name
        return None, None

    def get_provider(self, model: str | None = None) -> ProviderConfig | None:
        """Get matched provider config (api_key, api_base, extra_headers). Falls back to first available."""
        p, _ = self._match_provider(model)
        return p

    def get_provider_name(self, model: str | None = None) -> str | None:
        """Get the registry name of the matched provider (e.g. "deepseek", "openrouter")."""
        _, name = self._match_provider(model)
        return name

    def get_api_key(self, model: str | None = None) -> str | None:
        """Get API key for the given model. Falls back to first available key."""
        p = self.get_provider(model)
        return p.api_key if p else None

    def get_api_base(self, model: str | None = None) -> str | None:
        """Get API base URL for the given model. Applies default URLs for known gateways."""
        from nanobot.providers.registry import find_by_name

        p, name = self._match_provider(model)
        if p and p.api_base:
            return p.api_base
        # Only gateways get a default api_base here. Standard providers
        # (like Moonshot) set their base URL via env vars in _setup_env
        # to avoid polluting the global litellm.api_base.
        if name:
            spec = find_by_name(name)
            if spec and spec.is_gateway and spec.default_api_base:
                return spec.default_api_base
        return None

    model_config = ConfigDict(env_prefix="NANOBOT_", env_nested_delimiter="__")


# ============================================================================
# Agent-to-Agent Configuration Models
# ============================================================================

class SubagentConfig(BaseModel):
    """Subagent configuration."""
    model: str | None = None  # Override model for subagents
    temperature: float | None = None  # Override temperature
    max_tokens: int | None = None  # Override max_tokens
    max_spawn_depth: int = 1  # Maximum spawn depth (1=no nesting, 2=orchestrator pattern)
    max_children_per_agent: int = 5  # Max active children per agent session
    max_concurrent: int = 8  # Global concurrency limit
    run_timeout_seconds: int = 0  # Default timeout (0=no timeout)
    archive_after_minutes: int = 60  # Auto-archive after N minutes


class AgentToAgentPolicy(BaseModel):
    """Agent-to-Agent communication policy."""
    enabled: bool = False  # Enable/disable A2A communication
    allow: list[str] = Field(default_factory=list)  # Allowed agent IDs ("*" for all)
    deny: list[str] = Field(default_factory=list)  # Denied agent IDs
    max_ping_pong_turns: int = 5  # Maximum automatic ping-pong turns


class SessionVisibilityPolicy(BaseModel):
    """Session visibility policy for tools."""
    visibility: str = "tree"  # self | tree | agent | all
    
    @property
    def is_self(self) -> bool:
        return self.visibility == "self"
    
    @property
    def is_tree(self) -> bool:
        return self.visibility == "tree"
    
    @property
    def is_agent(self) -> bool:
        return self.visibility == "agent"
    
    @property
    def is_all(self) -> bool:
        return self.visibility == "all"


class AgentConfig(BaseModel):
    """Individual agent configuration."""
    id: str = Field(..., min_length=1, max_length=64, description="Agent identifier")
    name: str | None = Field(None, description="Human-readable agent name")
    workspace: Path | None = Field(None, description="Workspace directory")
    agent_dir: Path | None = Field(None, description="Agent state directory")
    model: str | None = Field(None, description="Default model for this agent")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="Temperature")
    max_tokens: int = Field(4096, ge=1, description="Max tokens")
    
    # Subagent settings
    subagents: SubagentConfig = Field(default_factory=SubagentConfig)
    
    # Tool policies
    sandbox: dict[str, Any] = Field(default_factory=dict)
    tools: dict[str, Any] = Field(default_factory=dict)
    
    def get_workspace_path(self) -> Path:
        """Get resolved workspace path."""
        if self.workspace:
            return self.workspace.expanduser()
        return Path.home() / ".nanobot" / f"workspace-{self.id}"
    
    def get_agent_dir_path(self) -> Path:
        """Get resolved agent directory path."""
        if self.agent_dir:
            return self.agent_dir.expanduser()
        return Path.home() / ".nanobot" / "agents" / self.id / "agent"


class AgentsConfig(BaseModel):
    """Multi-agent configuration."""
    defaults: AgentConfig = Field(default_factory=lambda: AgentConfig(id="default"))
    agent_list: list[AgentConfig] = Field(default_factory=list)
    
    def get_agent(self, agent_id: str) -> AgentConfig:
        """Get agent config by ID, falling back to defaults."""
        for agent in self.agent_list:
            if agent.id == agent_id:
                return agent
        # Return defaults with overridden id
        default = self.defaults.model_copy()
        default.id = agent_id
        return default
    
    def has_agent(self, agent_id: str) -> bool:
        """Check if an agent is configured."""
        return any(a.id == agent_id for a in self.agent_list)
    
    def list_agent_ids(self) -> list:
        """Get list of configured agent IDs."""
        return [a.id for a in self.agent_list]


class ToolsConfig(BaseModel):
    """Tool configuration."""
    agent_to_agent: AgentToAgentPolicy = Field(default_factory=AgentToAgentPolicy)
    sessions: SessionVisibilityPolicy = Field(default_factory=SessionVisibilityPolicy)


# Update Config class to include new fields
# Note: We'll add these as optional fields to maintain backward compatibility
class ConfigExtensions(BaseModel):
    """Extension fields for Config class."""
    agents: AgentsConfig = Field(default_factory=AgentsConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
