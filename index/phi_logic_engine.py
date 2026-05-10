import psycopg2
import numpy as np
from openai import OpenAI

class LogicEngine:
    def __init__(self):
        self.conn = psycopg2.connect(database="philosophy_db", user="postgres", password="536827", host="127.0.0.1", port="5432")
        self.client = OpenAI(api_key="sk-125beb76c63b469485884a6a63deb157", base_url="https://api.deepseek.com")

    def run_evolution_analysis(self, concept_word):
        cur = self.conn.cursor()
        
        # 1. 抓取该概念在不同时代的碎片
        cur.execute("""
            SELECT era, original_text, logic_chain 
            FROM v_logic_evolution 
            WHERE original_text LIKE %s
            ORDER BY era ASC
        """, (f'%{concept_word}%',))
        
        data = cur.fetchall()
        cur.close()
        
        # 2. 调用 DeepSeek 进行逻辑差异化推演
        context = "\n".join([f"时期：{row[0]} | 观点：{row[1]} | 逻辑链：{row[2]}" for row in data])
        
        prompt = f"""
        任务：推演哲学概念“{concept_word}”的演变脉络。
        语料库：
        {context}
        
        请分析：
        1. 该概念在不同时代的定义是如何从 A 偏移到 B 的？
        2. 导致这种逻辑偏移的核心因素是什么？
        3. 给出该概念的“逻辑演变轨迹图”描述（用于指导后续可视化）。
        """
        
        resp = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}]
        )
        return resp.choices[0].message.content

if __name__ == "__main__":
    engine = LogicEngine()
    print(engine.run_evolution_analysis("自由"))