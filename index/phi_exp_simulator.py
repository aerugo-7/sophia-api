import psycopg2
from openai import OpenAI
import json
import re

class ExperimentAgent:
    def __init__(self):
        self.ds_client = OpenAI(api_key="sk-125beb76c63b469485884a6a63deb157", base_url="https://api.deepseek.com")
        self.db_config = {"database": "philosophy_db", "user": "postgres", "password": "536827", "host": "127.0.0.1", "port": "5432"}

    def get_db_conn(self):
        return psycopg2.connect(**self.db_config)

    def run_experiment_simulation(self, experiment_name, user_decision):
        conn = self.get_db_conn(); cur = conn.cursor()
        
        # 1. 获取思想实验数据
        cur.execute("SELECT name, description, id FROM thought_experiments WHERE name = %s", (experiment_name,))
        exp = cur.fetchone()
        if not exp: return {"text": "未找到实验", "philosophers": []}
        
        # 2. 获取图谱中的“巨头”名单
        cur.execute("SELECT name, id FROM philosophers WHERE avatar_image IS NOT NULL ORDER BY influence_score DESC LIMIT 10")
        titans = cur.fetchall()
        titan_names = [t[0] for t in titans]
        
        # 3. 优化后的 Prompt：强制 AI 以冒号开头分段
        prompt = f"""
        任务：针对思想实验“{exp[0]}”进行对垒辩论。
        内容简述：{exp[1]}
        用户选择："{user_decision}"
        
        执行要求：
        请从名单 {titan_names} 中选出一位支持用户的哲学家 A 和一位持对立观点的哲学家 B。
        
        你必须严格按以下格式输出，不要有任何前言：
        [哲学家A的名字]：[他的支持论点以及解释为什么用户的选择在逻辑上是可行的]
        [VS]
        [哲学家B的名字]：[他的反驳论点以及用严厉且深刻的逻辑反驳用户和 A，并指出用户选择背后的潜在危机]
        """
        
        try:
            resp = self.ds_client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "system", "content": "你是一个哲学对垒模拟器。"}, {"role": "user", "content": prompt}],
                temperature=0.7 
            )
            ai_text = resp.choices[0].message.content

            # --- 核心改进：双重解析逻辑 ---
            # 首先尝试用 [VS] 切分
            parts = ai_text.split('[VS]')
            
            # 如果 AI 没输出 [VS]，我们按换行切分并寻找含有冒号的行
            if len(parts) < 2:
                parts = [p.strip() for p in ai_text.split('\n') if len(p.strip()) > 5]

            final_philosophers = []
            final_texts = []

            for part in parts:
                text_segment = part.strip()
                # 识别第一个冒号（支持中英文冒号）
                match = re.search(r'^(.*?)[：:]', text_segment)
                
                if match:
                    # 提取冒号前的名字
                    raw_name = match.group(1).strip()
                    clean_name = raw_name.replace('*', '').replace('[', '').replace(']', '').replace('哲学家A', '').replace('哲学家B', '').strip()
                    
                    # 查找 ID
                    cur.execute("SELECT name, id FROM philosophers WHERE name LIKE %s LIMIT 1", (f"%{clean_name}%",))
                    db_res = cur.fetchone()
                    
                    if db_res:
                        final_philosophers.append({"name": db_res[0], "id": db_res[1]})
                    else:
                        final_philosophers.append({"name": clean_name, "id": 0})
                    
                    # 提取冒号后的正文内容
                    content = text_segment[match.end():].strip()
                    final_texts.append(content)

            # 补齐逻辑（确保至少有两个）
            while len(final_philosophers) < 2:
                final_philosophers.append({"name": "先贤", "id": 0})
            if len(final_texts) < 2:
                final_texts = [ai_text, ""]

            cur.close(); conn.close()

            # 将 text 重新组合为带分隔符的格式，供前端再次拆分
            reformatted_text = f"{final_texts[0]} [VS] {final_texts[1]}"

            # 确保拿到两个哲学家，不足则补默认值
            philo_a = final_philosophers[0] if len(final_philosophers) > 0 else {"name": "先贤", "id": 0}
            philo_b = final_philosophers[1] if len(final_philosophers) > 1 else {"name": "先贤", "id": 0}

            return {
                "text": reformatted_text,
                "philosophers": [
                    {"name": philo_a["name"], "id": philo_a["id"]},
                    {"name": philo_b["name"], "id": philo_b["id"]}
                ],
                "exp_id": exp[2]
            }            
        except Exception as e:
            return {"text": f"AI 处理出错：{str(e)}", "philosophers": [], "exp_id": 0}