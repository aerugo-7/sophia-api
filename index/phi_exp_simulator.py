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
            输出的名字必须与名单中的文字【完全一致】
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
# --- 改进后的精准匹配逻辑 ---
            parts = ai_text.split('[VS]')
            final_philosophers = []
            
            # titans 是我们之前从数据库拿到的 [(name, id), ...] 列表
            for part in parts:
                text_segment = part.strip()
                matched = False
                
                # 直接在这一段的前 30 个字里寻找名单里的原名
                for name, p_id in titans:
                    if name in text_segment[:30]:
                        final_philosophers.append({"name": name, "id": p_id})
                        matched = True
                        break
                
                if not matched:
                    # 如果 AI 还是没听话，保底给一个 0 ID
                    final_philosophers.append({"name": "先贤", "id": 0})

            # 确保返回两个对象
            while len(final_philosophers) < 2:
                final_philosophers.append({"name": "先贤", "id": 0})

            cur.close(); conn.close()
            return {
                "text": ai_text,
                "philosophers": final_philosophers,
                "exp_id": exp[2]
            }
                            
        except Exception as e:
            print(f"Error in Simulation: {e}")
            print(traceback.format_exc())
            return {"text": f"对垒加载失败: {str(e)}", "philosophers": [], "id": 0}
        finally:
            # 稳健的关闭连接逻辑
            if cur: cur.close()
            if conn: conn.close()