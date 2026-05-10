import sys
import os
import uvicorn
import psycopg2
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import traceback

# --- 1. 路径修复：确保能找到 index 目录下的模块 ---
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, 'index'))

from phi_rag_search import search_philosophy_pure
from phi_graph_path import get_thought_path
from phi_exp_simulator import ExperimentAgent
from phi_logic_engine import LogicEngine

app = FastAPI()

# --- 2. 数据库连接配置 (公网云端版) ---
# 默认指向本地，Railway 部署时会自动被环境变量 DATABASE_URL 覆盖
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://neondb_owner:npg_jKDUwR6ldfY1@ep-wild-mode-aouqz0r7-pooler.c-2.ap-southeast-1.aws.neon.tech/neondb?sslmode=require")

def get_db_conn():
    return psycopg2.connect(DATABASE_URL)

# --- 3. 跨域安全配置 (必须开启，否则 GitHub 网页无法访问) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    query: Optional[str] = ""
    action: str
    params: dict = {}

@app.post("/sophia/api")
async def sophia_api(req: QueryRequest):
    try:
        # 1. 语义检索 (基于云端 pgvector 插件)
        if req.action == "search":
            results = search_philosophy_pure(req.query)
            print(f"[DEBUG] RAG 检索完成")
            return {"data": results if results else []}

        # 2. 图谱推理路径
        elif req.action == "path":
            start = req.params.get("start")
            end = req.params.get("end")
            path_result = get_thought_path(start, end)
            return {"path": path_result}

        # 3. 实验对垒模拟器
        elif req.action == "experiment":
            ea = ExperimentAgent(get_db_conn)  # 注入连接函数
            exp_name = req.params.get("name")
            # 返回包含 text, philosophers(含ID), exp_id 的字典
            return ea.run_experiment_simulation(exp_name, req.query)

        # 4. 逻辑演变推演
        elif req.action == "evolve":
            le = LogicEngine(get_db_conn)      # 注入连接函数
            return {"evolution": le.run_evolution_analysis(req.query)}

        # 5. 首页：随机小故事
        elif req.action == "random_story":
            conn = get_db_conn(); cur = conn.cursor()
            cur.execute("SELECT content, author FROM philosophy_stories WHERE content IS NOT NULL ORDER BY RANDOM() LIMIT 1")
            row = cur.fetchone()
            cur.close(); conn.close()
            if row:
                return {"story": row[0], "author": row[1] if row[1] else "佚名"}
            return {"story": "无论世界如何荒诞，我们仍需推石上山。", "author": "加缪"}

        # 6. 获取列表碎片 (金句、杂谈)
        elif req.action == "get_content":
            limit = req.params.get("limit", 3)
            c_type = req.params.get("type", "金句")
            conn = get_db_conn(); cur = conn.cursor()
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

        # 7. 获取随机背景图路径
        elif req.action == "get_decoration":
            conn = get_db_conn(); cur = conn.cursor()
            cur.execute("SELECT image_path FROM atmosphere_decorations WHERE image_path IS NOT NULL ORDER BY RANDOM() LIMIT 1")
            row = cur.fetchone()
            cur.close(); conn.close()
            return {"image_path": row[0] if row else "static/pic/bg.png"}

        # 8. 获取画廊全量数据 (用于 gallery 页面，全部带 ID)
        elif req.action == "get_gallery_all":
            target = req.params.get("target")
            conn = get_db_conn(); cur = conn.cursor()
            results = []
            if target == "philosopher":
                cur.execute("SELECT id, name, era, description FROM philosophers")
            elif target == "experiment":
                # 关键修复：去掉 LIMIT 1，去掉 fetchone，只写查询语句
                cur.execute("SELECT id, name, description FROM thought_experiments WHERE description IS NOT NULL")                
            elif target == "era":
                cur.execute("SELECT id, name, era_summary FROM era_backgrounds")
            elif target == "school":
                cur.execute("SELECT id, name, description FROM philosophy_schools")
            
            for r in cur.fetchall():
                results.append({
                    "id": r[0], 
                    "name": r[1], 
                    "era": r[2] if target=="philosopher" else "", 
                    "description": r[3] if target=="philosopher" else r[2]
                })
            cur.close(); conn.close()
            return {"data": results}

        # 9. 随机获取单条实体信息 (重点修复：gossip 分支现在返回头像 ID)
        elif req.action == "get_random":
            target = req.params.get("target")
            conn = get_db_conn(); cur = conn.cursor()
            result = {}
            
            if target == "philosopher":
                cur.execute("SELECT name, era, description, id FROM philosophers WHERE description IS NOT NULL ORDER BY RANDOM() LIMIT 1")
                r = cur.fetchone()
                if r: result = {"name": r[0], "era": r[1], "description": r[2], "id": r[3]}
                
            elif target == "topic":
                cur.execute("SELECT topic_name, description FROM core_topics WHERE description IS NOT NULL ORDER BY RANDOM() LIMIT 1")
                r = cur.fetchone()
                if r: result = {"topic_name": r[0], "description": r[1]}
                
            elif target == "era":
                cur.execute("SELECT name, era_summary, id FROM era_backgrounds WHERE era_summary IS NOT NULL ORDER BY RANDOM() LIMIT 1")
                r = cur.fetchone()
                if r: result = {"name": r[0], "era_summary": r[1], "id": r[2]}
                
            elif target == "school":
                cur.execute("SELECT name, description, id FROM philosophy_schools WHERE description IS NOT NULL ORDER BY RANDOM() LIMIT 1")
                r = cur.fetchone()
                if r: result = {"name": r[0], "description": r[1], "id": r[2]}
                
            elif target == "experiment":
                cur.execute("SELECT name, description, id FROM thought_experiments WHERE description IS NOT NULL ORDER BY RANDOM() LIMIT 1")
                r = cur.fetchone()
                if r: result = {"name": r[0], "description": r[1], "id": r[2]}
                
            elif target == "gossip":
                # 【核心修复】：通过 JOIN 关联 philosophers 表，获取 source 和 target 的 ID 供前端加载头像
                cur.execute("""
                    SELECT 
                        r.source_entity, 
                        p1.id as source_id,
                        r.target_entity, 
                        p2.id as target_id,
                        r.relation_type, 
                        r.description 
                    FROM relationships r
                    JOIN philosophers p1 ON r.source_entity = p1.name
                    JOIN philosophers p2 ON r.target_entity = p2.name
                    WHERE r.description IS NOT NULL AND r.description != ''
                    ORDER BY RANDOM() LIMIT 1
                """)
                r = cur.fetchone()
                if r: result = {
                    "source": r[0], "source_id": r[1],
                    "target": r[2], "target_id": r[3],
                    "relation": r[4], "description": r[5]
                }
                
            cur.close(); conn.close()
            return result

        else:
            raise HTTPException(status_code=400, detail="Unknown action")

    except Exception as e:
        print(traceback.format_exc()) # 控制台打印详细错误
        return {"error": str(e)}

if __name__ == "__main__":
    # 适配公网部署端口
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)