请增强 Hermes 智能体管理平台的以下功能，在 /home/admin/hermes-platform/agents_api/main.py 的基础上修改：

## 1. 添加 ChromaDB RAG 能力
- 安装 chromadb（如果没装的话 `pip install chromadb`）
- 创建 `/home/admin/hermes-platform/agents_api/rag.py`，包含：
  - `RAGEngine` 类，初始化 ChromaDB 客户端（持久化路径：`/home/admin/hermes-platform/data/chromadb`）
  - `add_document(text, metadata)` 方法：将文本分块（每块500字，重叠50字），用 SentenceTransformer 转为向量存入 Chroma
  - `search(query, top_k=5)` 方法：查询最相关文档块
  - `add_file(file_path)` 方法：支持加载 .txt 和 .md 文件
  - embedding 模型使用 `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`（支持中文，轻量）

## 2. 在 main.py 中添加 RAG API 端点
- `POST /knowledge/upload` - 上传文件到知识库
- `GET /knowledge/files` - 列出已上传的知识文件
- `DELETE /knowledge/files/{file_id}` - 删除知识文件
- `POST /knowledge/search` - 搜索知识库

## 3. 增强 Web 界面
- 在侧边栏添加「知识库管理」面板
- 可以上传文件、查看已上传文件、搜索知识

## 4. 增强集群对话
- 当智能体收到任务时，自动从 RAG 知识库检索相关内容作为上下文
- 在 /cluster/run 的返回中加入知识库命中信息

## 技术约束
- 所有代码用 Python + FastAPI
- 文件保存在 /home/admin/hermes-platform/data/knowledge/
- ChromaDB 持久化在 /home/admin/hermes-platform/data/chromadb/
- 保持原有的 orchestrator 模式不变
- Web 前端保持单页 HTML + JS，不引入额外框架

请仔细查看 /home/admin/hermes-platform/agents_api/main.py 的现有代码后，再进行修改。
修改完成后，用 `pip install chromadb sentence-transformers` 安装依赖。
最后重启服务测试：`pkill -f "python main.py" && sleep 1 && cd /home/admin/hermes-platform/agents_api && nohup python main.py > /tmp/hermes_platform.log 2>&1 &`
