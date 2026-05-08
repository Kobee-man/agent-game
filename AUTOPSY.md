# 尸检报告 - 海龟汤项目 v1

**解剖时间**: 2026-05-08
**尸体**: D:\my_fastapi (完整项目)
**死因**: 史山累积导致的不可维护

---

## 一、致命伤（必须火化）

### 1. api/turtle_soup.py — 978行的弗兰肯斯坦
- **问题**: 11个endpoint、3套prompt模板、JSON解析器、游戏状态管理全塞一个文件
- **症状**: 改任何一个功能都要通读全文，新功能无处安放
- **毒害**: prompt模板硬编码在路由文件中，无法单独测试或复用

### 2. 循环依赖 — config.py ↔ db_models.py
- `config.py` 定义 `Base`，`db_models.py` 导入 `Base`
- `config.py` 的 `create_db_and_tables()` 在函数体内反向导入 `db_models.py` 的 model
- **症状**: 改一处 import 顺序可能导致启动崩溃，靠"导入时序巧合"存活

### 3. JSON解析 — 两套重复实现
- `api/turtle_soup.py`: `parse_llm_json()` + `_extract_brace_block()` + `_fix_json_issues()`
- `core/turtle_soup_judge.py`: `_parse_response()` + 正则提取
- **毒害**: 修了一个另一个还是坏的

### 4. 线程池 — 杀鸡用牛刀
- `core/thread_pool.py` (37行) 单例模式，只为 WebSocket 广播时异步写数据库
- FastAPI 原生 `BackgroundTasks` 完全可以替代
- **毒害**: 多了一个全局状态、一个生命周期管理的坑

### 5. 硬编码密钥 — 安全隐患
- `config.py`: `SECRET_KEY = "your-secret-key-here"`
- `config.py`: `mysql+pymysql://root:123456@localhost`
- `CORS`: `allow_origins=["*"]`
- `.env` 已提交到 git（API key 暴露）

### 6. TurtleSoupJudge — 孤立的冗余模块
- `core/turtle_soup_judge.py` (326行) 设计精良但**几乎没被使用**
- 只有 `/semantic-judge` 一个端点调用它
- 主流程 (`/ask-question`, `/judge-question`) 自己构建 prompt 自己调 LLM
- 自带的缓存、否定检测、对立词检测全部浪费

---

## 二、慢性病（可活但需治疗）

### 7. N+1 查询 — chat.py
- 每条消息都单独查询发送者信息
- 50条历史消息 = 50次 User 查询
- **治疗**: JOIN 查询一次性加载

### 8. 死代码 — PrivateChat 模型
- `PrivateChatSession` 和 `PrivateChatMessage` 定义了但从无任何 API 使用
- **治疗**: 删除

### 9. 未使用的依赖
- `requirements.txt` 中 `sqlmodel` 和 `Pillow` 从未被 import
- `requests` 也不在任何代码中出现（用的是 `httpx`）
- **治疗**: 从 requirements.txt 移除

### 10. /invite 端点 — 假装工作
- 不发送任何实际邀请，只返回 "已发送"
- 纯占位符代码
- **治疗**: 删除或标记为 TODO

### 11. game_history — 内存列表
- `game_history: list = []` 模块级变量
- 游戏结束后追加，重启丢失
- 不持久化到数据库
- **治疗**: 要么删除，要么真正持久化

### 12. UID 生成 — 过度设计
- `generate_10digit_numeric_uid()` 循环检查数据库唯一性
- UUID4 已经足够
- **治疗**: 用 uuid4().hex[:12] 代替

---

## 三、死因总结

| 文件 | 行数 | 存活率 | 诊断 |
|------|------|--------|------|
| main.py | 77 | 60% | 结构OK，需去掉 thread_pool |
| core/config.py | 49 | 40% | 循环依赖需重构，硬编码需修复 |
| core/security.py | 53 | 90% | 接近健康 |
| core/llm_service.py | 205 | 85% | 需微调，结构合理 |
| core/redis_service.py | 97 | 80% | 需增加错误处理 |
| core/turtle_soup_judge.py | 326 | 30% | 90%功能被重复实现，需合并 |
| core/thread_pool.py | 37 | 0% | 废弃，用 BackgroundTasks 替代 |
| core/utils.py | 22 | 0% | 废弃，用 uuid 替代 |
| api/__init__.py | 11 | 50% | 需简化 |
| api/auth.py | 89 | 85% | 接近健康 |
| api/user.py | 96 | 80% | 硬编码URL需修复 |
| api/chat.py | 330 | 50% | N+1查询、线程池依赖需清理 |
| api/turtle_soup.py | 978 | 15% | 需彻底拆解 |
| models/db_models.py | 52 | 60% | 需删除死模型，修复循环依赖 |

---

## 四、抢救方案

**v2 核心原则**:
1. 单一职责 — 每个文件做一件事
2. 拆解 turtle_soup.py — prompts / json_parser / endpoints 三层分离
3. 消除循环依赖 — Base 独立为 base.py
4. 统一 LLM 调用逻辑 — 合并 turtle_soup_judge 到 service 层
5. 删掉所有死代码和未使用依赖
6. secrets 全部走环境变量
7. SQLite 默认可用，无需额外安装 MySQL
