import psycopg2
from openai import OpenAI
import re
import traceback

class ExperimentAgent:
    def __init__(self, db_connection_func):
        self.get_conn = db_connection_func
        self.ds_client = OpenAI(api_key="sk-125beb76c63b469485884a6a63deb157", base_url="https://api.deepseek.com")

    def run_experiment_simulation(self, experiment_name, user_decision):
        conn = None
        cur = None
        try:
            conn = self.get_conn()
            cur = conn.cursor()
            
            # 1. 获取实验 (严格匹配名字)
            cur.execute("SELECT name, description, id FROM thought_experiments WHERE name = %s", (experiment_name,))
            exp = cur.fetchone()
            if not exp:
                return {"text": "未找到实验内容", "philosophers": [], "id": 0}
            
            # 2. 获取巨头名单
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
            必须严格按以下格式输出，不要有任何前言：
            [哲学家A的名字]：[支持论点，并直接回应用户的输入]
            [VS]
            [哲学家B的名字]：[反驳论点，并直接回应用户和哲学家A]
            """
            resp = self.ds_client.chat.completions.create(
                model="deepseek-chat", 
                messages=[{"role": "user", "content": prompt}], 
                temperature=0.7
            )
            ai_text = resp.choices[0].message.content

# --- 找到解析 [VS] 的逻辑，替换为以下代码 ---
            parts = ai_text.split('[VS]')
            final_philosophers = []
            
            for part in parts:
                text_segment = part.strip()
                # 识别第一个冒号（兼容中英文冒号）
                split_char = '：' if '：' in text_segment else ':'
                if split_char in text_segment:
                    # 提取冒号前的名字（去掉 AI 可能加的星号）
                    raw_name = text_segment.split(split_char)[0].strip().replace('*', '')
                    
                    # 去数据库里搜这个人的真实 ID
                    cur.execute("SELECT name, id FROM philosophers WHERE name LIKE %s LIMIT 1", (f"%{raw_name}%",))
                    db_res = cur.fetchone()
                    if db_res:
                        final_philosophers.append({"name": db_res[0], "id": db_res[1]})
                    else:
                        final_philosophers.append({"name": raw_name, "id": 0})
                else:
                    final_philosophers.append({"name": "未知先贤", "id": 0})

            # 确保即使出错也返回两个占位对象
            while len(final_philosophers) < 2:
                final_philosophers.append({"name": "辩论者", "id": 0})

            cur.close(); conn.close()
            return {
                "text": ai_text, # 返回带 [VS] 的原文
                "philosophers": final_philosophers,
                "id": exp[2] # 确保这里叫 id，方便前端调用
            }            
        except Exception as e:
            print(f"Error in Simulation: {e}")
            print(traceback.format_exc())
            return {"text": f"对垒加载失败: {str(e)}", "philosophers": [], "id": 0}
        finally:
            # 稳健的关闭连接逻辑
            if cur: cur.close()
            if conn: conn.close()