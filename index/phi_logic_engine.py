import os
import psycopg2
import numpy as np
from openai import OpenAI

# --- 数据库连接：优先使用环境变量，兼容本地开发 ---
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://neondb_owner:npg_jKDUwR6ldfY1@ep-wild-mode-aouqz0r7-pooler.c-2.ap-southeast-1.aws.neon.tech/neondb?sslmode=require")

def get_db_conn():
    """统一获取数据库连接"""
    return psycopg2.connect(DATABASE_URL)


class LogicEngine:
    def __init__(self):
        # 不再存储持久连接，每次运行时通过 get_db_conn() 获取
        self.client = OpenAI(api_key="sk-125beb76c63b469485884a6a63deb157", base_url="https://api.deepseek.com")

    def run_evolution_analysis(self, concept_word):
        conn = get_db_conn()
        cur = conn.cursor()
        
        # 1. 抓取该概念在不同时代的碎片
        cur.execute("""
            SELECT era, original_text, logic_chain 
            FROM v_logic_evolution 
            WHERE original_text LIKE %s
            ORDER BY era ASC
        """, (f'%{concept_word}%',))
        
        data = cur.fetchall()
        cur.close()
        conn.close()
        
        # 2. 调用 DeepSeek 进行逻辑差异化推演
        context = "\n".join([f"时期：{row[0]} | 观点：{row[1]} | 逻辑链：{row[2]}" for row in data])
        
        prompt = f"""
        任务：推演哲学概念“{concept_word}”的演变脉络。
        语料库：
        {context}
        
        请分析：
        1. 该概念在不同时代的定义是如何从 A 偏移到 B 的？
        2. 导致这种逻辑偏移的核心因素是什么？
        3. 给出该概念的“逻辑演变轨迹图”描述。
        """
        
        resp = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}]
        )
        return resp.choices[0].message.content


if __name__ == "__main__":
    engine = LogicEngine()
    print(engine.run_evolution_analysis("自由"))