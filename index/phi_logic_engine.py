import os
import psycopg2
from openai import OpenAI

# 不再自己定义 DATABASE_URL，而是接受一个连接函数或连接对象
class LogicEngine:
    def __init__(self, db_connection_func):
        """
        db_connection_func: 无参函数，返回 psycopg2 连接对象
        """
        self.get_conn = db_connection_func
        self.client = OpenAI(
            api_key="sk-125beb76c63b469485884a6a63deb157",
            base_url="https://api.deepseek.com"
        )

    def run_evolution_analysis(self, concept_word):
        conn = self.get_conn()
        cur = conn.cursor()
        
        # !!! 重要：确保云端已存在 v_logic_evolution 视图
        # 如果没有，需要先创建（或替换成实际存在的表）
        try:
            cur.execute("""
                SELECT era, original_text, logic_chain 
                FROM v_logic_evolution 
                WHERE original_text LIKE %s
                ORDER BY era ASC
            """, (f'%{concept_word}%',))
            
            data = cur.fetchall()
        except Exception as e:
            cur.close()
            conn.close()
            return f"数据库查询失败: {str(e)}"
        
        cur.close()
        conn.close()
        
        if not data:
            return f"未找到与“{concept_word}”相关的演变记录。"
        
        context = "\n".join(
            [f"时期：{row[0]} | 观点：{row[1]} | 逻辑链：{row[2]}" for row in data]
        )
        
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


# 保留原函数签名，但需传入连接函数
def get_logic_engine(get_conn_func):
    return LogicEngine(get_conn_func)