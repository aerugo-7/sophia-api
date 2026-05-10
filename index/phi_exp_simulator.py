import psycopg2
from openai import OpenAI
import re
import traceback

class ExperimentAgent:
    def __init__(self, db_connection_func):
        self.get_conn = db_connection_func
        self.ds_client = OpenAI(api_key="sk-125beb76c63b469485884a6a63deb157", base_url="https://api.deepseek.com")

def run_experiment_simulation(self, experiment_name, user_decision):
        conn = self.get_conn(); cur = conn.cursor()
        cur.execute("SELECT name, description, id FROM thought_experiments WHERE name = %s", (experiment_name,))
        exp = cur.fetchone()
        
        cur.execute("SELECT name, id FROM philosophers ORDER BY influence_score DESC LIMIT 15")
        titans = cur.fetchall()
        titan_names = [t[0] for t in titans]           
            
    # --- 找到 prompt = f"""...""" 部分，替换为： ---
        prompt = f"""
            任务：针对思想实验“{exp[0]}”进行对垒辩论。
            内容简述：{exp[1]}
            用户的决策是："{user_decision}"
            
            执行要求：
            请从名单 {titan_names} 中选出一位支持者的哲学家 A 和一位持对立观点的哲学家 B。
            必须严格按以下格式输出（禁止输出任何前言、后缀或括号说明）：
            哲学家A的名字：[支持论点，并直接回应用户的输入]
            [VS]
            哲学家B的名字：[反驳论点，并直接回应用户和哲学家A]
            """
        try:
            resp = self.ds_client.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": prompt}], temperature=0.7)
            ai_text = resp.choices[0].message.content
            
            # 解析四段式结构
            parts = ai_text.split('[VS]')
            final_philosophers = []
            
            # 针对 A 和 B 的名字去匹配 ID
            for name_idx in [0, 2]:
                if len(parts) > name_idx:
                    raw_name = parts[name_idx].strip().replace('*', '')
                    cur.execute("SELECT name, id FROM philosophers WHERE name LIKE %s LIMIT 1", (f"%{raw_name[:2]}%",))
                    db_res = cur.fetchone()
                    final_philosophers.append({"name": db_res[0] if db_res else raw_name, "id": db_res[1] if db_res else 0})

            cur.close(); conn.close()
            return {
                "raw_parts": [p.strip() for p in parts], # 将切好的四部分传给前端
                "philosophers": final_philosophers,
                "id": exp[2]
            }
        except Exception as e:
            if cur: cur.close(); conn.close()
            return {"text": "对垒失败", "philosophers": []}