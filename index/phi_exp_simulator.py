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
            输出的名字必须与名单中的文字【完全一致】，你必须【直接复制】名单中的名字，不要修改任何字符（特别是中间的点“·”）
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

# 锁定冒号前的说话者 ---
            parts = ai_text.split('[VS]')
            final_philosophers = []
            
            for part in parts:
                text_segment = part.strip()
                # 1. 找到第一个冒号（中英文冒号均可）的位置
                # 我们只看前 40 个字符，防止在正文里找冒号
                match = re.search(r'^(.{1,40}?)[:：]', text_segment)
                
                if match:
                    # 2. 提取冒号前的原始文本作为“说话者名字”
                    speaker_name = match.group(1).replace('*', '').strip()
                    
                    # 3. 在 titans 名单中寻找这个说话者
                    found_id = 0
                    found_standard_name = speaker_name
                    
                    for name, p_id in titans:
                        # 兼容逻辑：如果名字完全一致，或者 AI 漏掉了点（模糊包含）
                        # 比如名单是 "约翰·洛克"，AI 吐出 "约翰·洛克" 或 "约翰洛克"
                        clean_target = name.replace('·', '')
                        clean_speaker = speaker_name.replace('·', '')
                        
                        if name == speaker_name or clean_target == clean_speaker:
                            found_id = p_id
                            found_standard_name = name
                            break
                    
                    final_philosophers.append({"name": found_standard_name, "id": found_id})
                else:
                    final_philosophers.append({"name": "未知先贤", "id": 0})

            # 补齐两个位置
            while len(final_philosophers) < 2:
                final_philosophers.append({"name": "辩论者", "id": 0})

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