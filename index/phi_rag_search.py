import psycopg2
import os
import requests
import json

# --- 1. 配置信息 (公网版优化) ---
API_KEY = "sk-hvbcfazpdzwzvckmlvmcjivqfyqwzfhpcdjtbsqgzhoqnurt"

# 数据库连接：优先读取环境变量（云端部署用），如果没有则用你提供的连接字符串
# 请将下方的字符串替换为你从 Neon 复制的最新完整连接字符串
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://neondb_owner:npg_jKDUwR6ldfY1@ep-wild-mode-aouqz0r7-pooler.c-2.ap-southeast-1.aws.neon.tech/neondb?sslmode=require")

def get_embedding(text):
    """调用 SiliconFlow 将文本转为 1024 维向量"""
    url = "https://api.siliconflow.cn/v1/embeddings"
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    payload = {"model": "BAAI/bge-m3", "input": text, "encoding_format": "float"}
    try:
        resp = requests.post(url, json=payload, headers=headers)
        return resp.json()["data"][0]["embedding"]
    except Exception as e:
        print(f"向量化失败: {e}")
        return None

def search_philosophy_pure(user_input, top_k=3):
    """
    云端极速搜索版：
    利用 PostgreSQL 的 pgvector 扩展在数据库内部进行余弦相似度计算
    """
    # 1. 获取输入文本的向量
    query_vec = get_embedding(user_input)
    if not query_vec:
        return []

    # 2. 连接云端数据库
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        # 3. 执行向量检索 SQL (核心优化)
        # <=> 是 pgvector 专用的余弦距离操作符
        # 1 - (embedding_vector <=> query_vec) = 相似度
        query_sql = """
            SELECT 
                cb.original_text, 
                b.author, 
                b.book_title,
                1 - (cb.embedding_vector <=> %s::vector) AS similarity
            FROM content_blocks cb
            JOIN books b ON cb.book_id = b.id
            WHERE cb.embedding_vector IS NOT NULL
            ORDER BY cb.embedding_vector <=> %s::vector
            LIMIT %s
        """
        
        # 传入两次向量：一次用于排序，一次用于计算相似度（如果需要）
        cur.execute(query_sql, (query_vec, query_vec, top_k))
        rows = cur.fetchall()
        
        results = []
        for text, author, title, score in rows:
            results.append({
                "text": text,
                "author": author,
                "title": title,
                "score": float(score) # 相似度分数
            })
            
        cur.close()
        conn.close()
        
        # 打印调试信息
        print(f"\n[云端检索成功] 关键词: {user_input}")
        return results

    except Exception as e:
        print(f"数据库查询异常: {e}")
        return []

if __name__ == "__main__":
    # 本地测试代码
    test_thought = "我有时候真的很好奇死亡后的世界，因为现在的世界实在太无聊了。"
    res = search_philosophy_pure(test_thought)
    for r in res:
        print(f"[{r['score']:.4f}] {r['author']}: {r['text'][:50]}...")