# 阶段一修改记录：LangChain 基础设施层

> **日期**: 2026-05-31
> **分支**: master
> **Commits**: `0a5b37b`, `b5e61b5`

---

## 概述

将项目 LLM 调用从手写 httpx 升级为 LangChain 框架，并搭建 Embedding + PGVector 向量库基础设施。为后续 RAG 和 Agent 化改造奠定基础。

---

## Commit 1: `0a5b37b` — LangChain 基础设施搭建 (T1-T5)

### 新增文件

| 文件 | 行数 | 说明 |
|------|------|------|
| `core/llm_factory.py` | 83 | LangChain LLM 工厂，统一创建 ChatDeepSeek / ChatOllama 实例 |
| `core/embedding.py` | 24 | Embedding 模型管理（占位，T6 完善） |

### 修改文件

| 文件 | 改动 | 说明 |
|------|------|------|
| `requirements.txt` | +16 -1 | 新增 langchain-core/langchain/langchain-deepseek/langchain-ollama/langchain-huggingface/langchain-text-splitters/langchain-postgres/sentence-transformers/pgvector/psycopg[binary]；移除 httpx |
| `core/config.py` | +19 | 新增 13 个配置项：LLM_TEMPERATURE, LLM_MAX_TOKENS, EMBEDDING_MODEL, EMBEDDING_DEVICE, VECTOR_COLLECTION_PREFIX, VECTOR_SEARCH_TOP_K, VECTOR_DISTANCE_THRESHOLD 等 |
| `core/llm_service.py` | 157→58 行 | 重写为 LangChain 兼容层，保留 `llm_service.chat()` 和 `LLMError` 旧接口，内部改用 LangChain messages + invoke |
| `.env.example` | +9 | 新增 Embedding 和向量库配置模板 |

### 依赖变更

```
新增: langchain-core, langchain, langchain-community, langchain-deepseek,
      langchain-ollama, langchain-huggingface, langchain-text-splitters,
      langchain-postgres, sentence-transformers, pgvector, psycopg[binary]
移除: httpx（仅 llm_service.py 使用，改造后不再需要）
保留: psycopg2-binary（SQLAlchemy 仍用 v2）
```

### 兼容性

- `core/agent.py` — 无需改动，通过 `llm_service` 兼容层调用
- `core/ai_player.py` — 无需改动
- `core/prompts.py` — 无需改动
- `core/runtime.py` — 无需改动
- `api/*` — 无需改动

---

## Commit 2: `b5e61b5` — Embedding + PGVector 向量库 (T6-T7)

### 新增文件

| 文件 | 行数 | 说明 |
|------|------|------|
| `core/vector_store.py` | 33 | PGVector 向量库管理，懒缓存模式 |

### 修改文件

| 文件 | 改动 | 说明 |
|------|------|------|
| `core/embedding.py` | 24→67 行 | 重写为双模式：`api`（Silicon Flow 远程）/ `local`（HuggingFace 本地） |
| `core/config.py` | +5 | 新增 EMBEDDING_MODE, SILICONFLOW_API_KEY, SILICONFLOW_API_URL |
| `.env.example` | +5 | 更新 Embedding 配置，说明双模式切换 |

### Embedding 方案

- **默认模式**: `api` — Silicon Flow API（国内服务，BAAI/bge-m3 免费）
- **备用模式**: `local` — HuggingFace 本地模型（需手动下载，设置 EMBEDDING_MODE=local）
- **向量维度**: 1024（bge-m3）
- **距离策略**: COSINE（PGVector 默认）

### 验证结果

| 测试项 | 结果 |
|--------|------|
| Silicon Flow API 调用 | ✅ 1024 维向量 |
| 批量 Embedding (embed_documents) | ✅ 3 条/批 |
| PGVector 写入 | ✅ |
| PGVector 语义检索 | ✅ "推理游戏" 正确返回相关文档 |
| 集合清理 (delete_collection) | ✅ |
| 旧模块兼容 (agent/ai_player/prompts/runtime) | ✅ 全部 import 正常 |
| API 路由加载 | ✅ 6 个 router 全部正常 |

---

## 配置变更汇总

### .env 新增项

```env
# LLM 参数（从 llm_service.py 提取到 config.py）
LLM_TEMPERATURE=0.5
LLM_MAX_TOKENS=1000

# Embedding
EMBEDDING_MODE=api
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DEVICE=cpu
SILICONFLOW_API_KEY=sk-xxx

# 向量库
VECTOR_COLLECTION_PREFIX=htg_
VECTOR_SEARCH_TOP_K=5
VECTOR_DISTANCE_THRESHOLD=0.7
```

### PostgreSQL 新增

- pgvector 扩展已启用 (`CREATE EXTENSION vector`)
- 向量表由 langchain-postgres 自动创建（`htg_xxx` 前缀）

---

## 已知限制

1. **Embedding 依赖网络**: 默认使用 Silicon Flow API，需要网络连接；切换到本地模式需手动下载模型
2. **langchain-community 有 sunset 警告**: 不影响功能，后续可迁移到独立集成包
3. **Embedding/Vector 尚未接入游戏逻辑**: 基础设施就绪，阶段二才会实际使用 RAG
