import psycopg2
import numpy as np
from scipy.spatial.distance import cosine
import requests

# --- 配置信息 ---
API_KEY = "sk-hvbcfazpdzwzvckmlvmcjivqfyqwzfhpcdjtbsqgzhoqnurt"
DB_CONFIG = {
    "database": "philosophy_db", 
    "user": "postgres", 
    "password": "536827", 
    "host": "127.0.0.1", 
    "port": "5432"
}

def get_embedding(text):
    """获取用户输入的向量"""
    url = "https://api.siliconflow.cn/v1/embeddings"
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    payload = {"model": "BAAI/bge-m3", "input": text}
    resp = requests.post(url, json=payload, headers=headers)
    return resp.json()["data"][0]["embedding"]

def search_philosophy_pure(user_input, top_k=3):
    """执行语义搜索并返回 results 列表（已排序），同时打印前 top_k 条"""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    query_sql = """
        SELECT 
            cb.original_text, 
            b.author, 
            b.book_title, 
            cb.embedding_vector 
        FROM content_blocks cb
        JOIN books b ON cb.book_id = b.id
        WHERE cb.embedding_vector IS NOT NULL
    """
    cur.execute(query_sql)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    if not rows:
        print("数据库中尚无已向量化的语料。")
        return []   # 修改：返回空列表而非 None

    query_vec = np.array(get_embedding(user_input))
    results = []
    
    for text, author, title, vec in rows:
        sim = 1 - cosine(query_vec, np.array(vec))
        results.append({
            "text": text,
            "author": author,
            "title": title,
            "score": sim
        })
    
    results.sort(key=lambda x: x["score"], reverse=True)
    
    # 打印前 top_k 条结果
    print(f"\n【搜索词】：{user_input}\n" + "="*50)
    for i, item in enumerate(results[:top_k]):
        print(f"序号：{i+1}")
        print(f"原文：{item['text']}")
        print(f"作者：{item['author']}")
        print(f"出自：《{item['title']}》")
        print("-" * 30)
    
    return results  # 关键修改：返回所有排序后的结果

if __name__ == "__main__":
    my_thought = "我有时候真的很好奇死亡后的世界，因为现在的世界实在太无聊了。"
    result_list = search_philosophy_pure(my_thought)
    # 可选：进一步处理返回的结果
    if result_list:
        print(f"共找到 {len(result_list)} 条匹配内容，最高相似度: {result_list[0]['score']:.4f}")