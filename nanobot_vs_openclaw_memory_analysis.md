# 分析报告：Nanobot 与 OpenClaw 的记忆功能差异

经过对 `nanobot` 仓库和 `openclaw` 仓库中记忆（Memory）模块核心代码的深度探查对比，两者的记忆系统虽然在底层存储上都依赖了 `sqlite-vec` 和 FTS5 引擎，但在**分块策略、检索重排、索引性能、以及作用域隔离**等方面有着本质的设计理念差异。

以下是两者的核心差距与特性对比：

### 1. 文档分块策略（Chunking Strategy）
这是两者在数据预处理阶段最大的差异，直接影响检索召回的质量：
*   **Nanobot (语义分块)**：实现了高级的**语义分块（Semantic Chunking）**。在 `_split_semantic` 方法中，Nanobot 会先将文档拆分为句子，利用 Sentence Transformer 计算相邻句子的余弦相似度。当相似度低于预设阈值（如 `0.7`）时，即认定出现“主题切换”，从而在语义边界处切断。这种方式保证了每个 Chunk 在主题上是高度内聚的。
*   **OpenClaw (硬性阈值分块)**：采用的是**基于字节/Token上限的硬切分**（位于 `embedding-input-limits.ts` 的 `splitTextToUtf8ByteLimit`）。它仅仅通过计算字符序列的 UTF-8 字节长度，在达到大模型 Provider 的最大 Token 上限前进行截断，主要目的是防止 API 报错，而非保持语义完整性。

### 2. 检索重排与打分策略（Retrieval & Re-ranking）
在获取初步相似结果后，两者的重排（Rerank）逻辑走向了不同方向：
*   **Nanobot (深度学习交叉编码器)**：集成了一个真实的 **CrossEncoder 重排器**（位于 `reranker.py`）。它可以利用如 `ms-marco-MiniLM` 等交叉编码模型，将 Query 和每一个检索到的 Document 拼接后进行深度相关性打分。这极大地提升了最终排名（Top-K）的绝对准确度。
*   **OpenClaw (MMR 与时间衰减)**：并没有使用交叉编码模型，而是引入了两个非常实用的工程化规则：
    1.  **最大边缘相关性 (MMR - Maximal Marginal Relevance)** (`mmr.ts`)：在相关性和**多样性**之间做折中，惩罚那些与已选出的高分 Chunk 相似度过高的结果，防止喂给 LLM 的上下文中出现大量重复废话。
    2.  **时间衰减 (Temporal Decay)** (`temporal-decay.ts`)：对较老的记忆文件应用指数衰减曲线（可配置半衰期），确保 AI 在搜索时默认更倾向于“最近发生的事情”或“最新的代码”。

### 3. 索引性能与大规模并发（Indexing & Scalability）
*   **Nanobot (同步阻塞式)**：索引过程（`index_all`）是一个简单的 for 循环，它同步遍历所有文件并依次发送给 Embedding Provider。这种设计实现简单，适合轻量级项目或纯本地运行（Local Llama / Sentence Transformer）。但遇到数万个文件的巨型项目时，极易触发 API Rate Limit 或造成主线程长时间阻塞。
*   **OpenClaw (云端 Batch API 深度集成)**：拥有极其健壮的**异步批处理系统**（`batch-openai.ts`, `batch-runner.ts` 等）。对于需要生成大量 Embedding 的场景，OpenClaw 会将请求打包成 `.jsonl` 文件，直接调用各大云厂商的 Batch API（如 OpenAI 官方的 `/v1/batches`）。这不仅绕过了速率限制，还利用了 Batch API 通常享有的 50% 成本折扣，专为处理企业级海量代码库设计。

### 4. 架构、扩展与会话隔离（Architecture & Scoping）
*   **Nanobot**：
    *   具有基于正则和停用词表的 `QueryParser`，用于提取关键词和意图识别。
    *   记忆库是单体全局的（`memory.db`），所有上下文都在一个池子里。
*   **OpenClaw**：
    *   **严格的会话与 Agent 隔离**：通过 `qmd-scope.ts` 和 `session-files.ts`，OpenClaw 可以严格隔离不同 Agent 或不同对话 Session 产生的记忆，避免上下文污染。
    *   **QMD 外部检索引擎**：除了 SQLite，OpenClaw 还设计了与外部高性能检索引擎 `qmd` 交互的接口（`qmd-manager.ts`）。
    *   **大模型 Query 扩展**：除了基础的 FTS 关键词匹配，OpenClaw 支持 `LlmQueryExpander`，可以在纯文本搜索前，先让 LLM 发散联想用户的查询词，提高全文检索（FTS）的命中率。

### 总结
*   **Nanobot** 的记忆系统胜在**局部精度（Micro-accuracy）**：通过“语义分块 + CrossEncoder 重排”，它能非常精准地定位到最符合用户直觉的那一段代码或文档。
*   **OpenClaw** 的记忆系统胜在**宏观调度（Macro-scalability）与多场景兼容**：通过“Batch API + 时间衰减 + MMR 多样性 + Agent 沙盒隔离”，它能稳定地将几十万行的大型项目塞入记忆引擎中，同时保证长轮次对话不跑偏。