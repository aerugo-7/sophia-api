import sys
import os
import uvicorn
import psycopg2
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

# --- 关键修复：自动将 index 目录添加到 Python 搜索路径 ---
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, 'index'))

# 导入自定义逻辑模块
from phi_rag_search import search_philosophy_pure
from phi_graph_path import get_thought_path
from phi_exp_simulator import ExperimentAgent
from phi_logic_engine import LogicEngine

app = FastAPI()

# --- 跨域安全配置 ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 统一请求模型
class QueryRequest(BaseModel):
    query: Optional[str] = ""
    action: str
    params: dict = {}

# 数据库连接配置 (全局复用)
DB_CONFIG = {
    "database": "philosophy_db",
    "user": "postgres",
    "password": "536827",
    "host": "127.0.0.1",
    "port": "5432"
}

@app.post("/sophia/api")
async def sophia_api(req: QueryRequest):
    try:
        # 1. 语义检索 (RAG)
        if req.action == "search":
            results = search_philosophy_pure(req.query)
            print(f"[DEBUG] RAG检索匹配完成")
            return {"data": results if results else []}

        # 2. 图谱推理路径
        elif req.action == "path":
            start = req.params.get("start")
            end = req.params.get("end")
            path_result = get_thought_path(start, end)
            return {"path": path_result}

        # 3. 实验对垒模拟器
        elif req.action == "experiment":
            ea = ExperimentAgent()
            exp_name = req.params.get("name")
            # 这里返回 ExperimentAgent 计算出的对垒字典
            return ea.run_experiment_simulation(exp_name, req.query)

        # 4. 逻辑演变推演
        elif req.action == "evolve":
            le = LogicEngine()
            return {"evolution": le.run_evolution_analysis(req.query)}

        # 5. 首页：随机小故事
        elif req.action == "random_story":
            conn = psycopg2.connect(**DB_CONFIG)
            cur = conn.cursor()
            cur.execute("SELECT content, author FROM philosophy_stories WHERE content IS NOT NULL ORDER BY RANDOM() LIMIT 1")
            row = cur.fetchone()
            cur.close(); conn.close()
            if row:
                return {"story": row[0], "author": row[1] if row[1] else "佚名"}
            return {"story": "无论世界如何荒诞，我们仍需推石上山。", "author": "加缪"}

        # 6. 获取列表碎片内容 (用于金句、小故事)
        elif req.action == "get_content":
            limit = req.params.get("limit", 3)
            c_type = req.params.get("type", "金句")
            conn = psycopg2.connect(**DB_CONFIG)
            cur = conn.cursor()
            cur.execute("""
                SELECT cb.original_text, b.author, b.book_title 
                FROM content_blocks cb
                JOIN books b ON cb.book_id = b.id
                WHERE cb.content_type = %s AND cb.original_text IS NOT NULL
                ORDER BY RANDOM() LIMIT %s
            """, (c_type, limit))
            rows = cur.fetchall()
            cur.close(); conn.close()
            data = [{"text": r[0], "author": r[1] if r[1] else "佚名", "title": r[2] if r[2] else "未知"} for r in rows]
            return {"data": data}

        # 7. 获取随机装饰图
        elif req.action == "get_decoration":
            conn = psycopg2.connect(**DB_CONFIG)
            cur = conn.cursor()
            cur.execute("SELECT image_path FROM atmosphere_decorations WHERE image_path IS NOT NULL ORDER BY RANDOM() LIMIT 1")
            row = cur.fetchone()
            cur.close(); conn.close()
            return {"image_path": row[0] if row else "static/pic/bg.png"}

        # 8. 获取画廊全量数据 (用于 gallery 页面)
        elif req.action == "get_gallery_all":
            target = req.params.get("target")
            conn = psycopg2.connect(**DB_CONFIG)
            cur = conn.cursor()
            results = []
            if target == "philosopher":
                cur.execute("SELECT id, name, era, description FROM philosophers WHERE avatar_image IS NOT NULL")
            elif target == "experiment":
                cur.execute("SELECT id, name, description FROM thought_experiments WHERE image_data IS NOT NULL")
            elif target == "era":
                cur.execute("SELECT id, name, era_summary FROM era_backgrounds WHERE image_data IS NOT NULL")
            elif target == "school":
                cur.execute("SELECT id, name, description FROM philosophy_schools WHERE icon_data IS NOT NULL")
            
            for r in cur.fetchall():
                results.append({"id": r[0], "name": r[1], "era": r[2] if len(r)>2 else "", "description": r[3] if len(r)>3 else r[2]})
            cur.close(); conn.close()
            return {"data": results}

        # 9. 随机获取单条实体 (关键修复：为 philosopher 和 experiment 增加了 ID)
        elif req.action == "get_random":
            target = req.params.get("target")
            conn = psycopg2.connect(**DB_CONFIG)
            cur = conn.cursor()
            result = {}

            if target == "philosopher":
                cur.execute("SELECT name, era, description, id FROM philosophers WHERE description IS NOT NULL ORDER BY RANDOM() LIMIT 1")
                row = cur.fetchone()
                if row: result = {"name": row[0], "era": row[1], "description": row[2], "id": row[3]}

            elif target == "topic":
                cur.execute("SELECT topic_name, description FROM core_topics WHERE description IS NOT NULL ORDER BY RANDOM() LIMIT 1")
                row = cur.fetchone()
                if row: result = {"topic_name": row[0], "description": row[1]}

            elif target == "era":
                cur.execute("SELECT name, era_summary, id FROM era_backgrounds WHERE era_summary IS NOT NULL ORDER BY RANDOM() LIMIT 1")
                row = cur.fetchone()
                if row: result = {"name": row[0], "era_summary": row[1], "id": row[2]}

            elif target == "school":
                cur.execute("SELECT name, description, id FROM philosophy_schools WHERE description IS NOT NULL ORDER BY RANDOM() LIMIT 1")
                row = cur.fetchone()
                if row: result = {"name": row[0], "description": row[1], "id": row[2]}

            elif target == "gossip":
                cur.execute("""
                    SELECT r.source_entity, r.target_entity, r.relation_type, r.description 
                    FROM relationships r
                    JOIN entities_mapping em1 ON r.source_entity = em1.raw_name
                    JOIN entities_mapping em2 ON r.target_entity = em2.raw_name
                    WHERE em1.entity_type = 'philosopher' AND em2.entity_type = 'philosopher'
                    AND r.description IS NOT NULL AND r.description != ''
                    ORDER BY RANDOM() LIMIT 1
                """)
                row = cur.fetchone()
                if row: result = {"source": row[0], "target": row[1], "relation": row[2], "description": row[3]}

            elif target == "experiment":
                # 修复点：返回 ID 以便前端加载 static/experiments/exp_{id}.png
                cur.execute("SELECT name, description, id FROM thought_experiments WHERE description IS NOT NULL ORDER BY RANDOM() LIMIT 1")
                row = cur.fetchone()
                if row: result = {"name": row[0], "description": row[1], "id": row[2]}

            cur.close(); conn.close()
            return result

        else:
            raise HTTPException(status_code=400, detail="未知的 action 类型")

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return {"error": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)