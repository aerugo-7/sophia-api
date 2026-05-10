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
            必须严格按以下格式输出（禁止输出任何前言、后缀或括号说明）：
            哲学家A的名字：[支持论点，并直接回应用户的输入]
            [VS]
            哲学家B的名字：[反驳论点，并直接回应用户和哲学家A]
            """
            resp = self.ds_client.chat.completions.create(
                model="deepseek-chat", 
                messages=[{"role": "user", "content": prompt}], 
                temperature=0.7
            )
            ai_text = resp.choices[0].message.content

# 锁定冒号前的说话者 ---
# --- 终极冒号匹配逻辑 ---
            parts = ai_text.split('[VS]')
            final_philosophers = []
            
            for part in parts:
                text_segment = part.strip()
                # 查找第一个冒号
                if "：" in text_segment or ":" in text_segment:
                    # 提取冒号前的名字并清洗
                    raw_name = re.split('：|:', text_segment)[0].replace('*','').strip()
                    
                    # 匹配 ID（忽略中间点的影响）
                    match_id = 0
                    match_name = raw_name
                    for t_name, t_id in titans:
                        if t_name.replace('·','') in raw_name.replace('·','') or raw_name.replace('·','') in t_name.replace('·',''):
                            match_id = t_id
                            match_name = t_name
                            break
                    final_philosophers.append({"name": match_name, "id": match_id})

            while len(final_philosophers) < 2:
                final_philosophers.append({"name": "先贤", "id": 0})

            return {
                "text": ai_text.replace('[VS]', '\n\n---\n\n'), # 格式化文本
                "philosophers": final_philosophers,
                "id": exp[2]
            }
            
        except Exception as e:
            print(f"Error in Simulation: {e}")
            print(traceback.format_exc())
            return {"text": f"对垒加载失败: {str(e)}", "philosophers": [], "id": 0}
        finally:
            # 稳健的关闭连接逻辑
            if cur: cur.close()
            if conn: conn.close()