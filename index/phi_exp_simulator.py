import os
import psycopg2
from openai import OpenAI
import re
import traceback

class ExperimentAgent:
    def __init__(self, db_connection_func=None):
        """
        db_connection_func: 可选的数据库连接工厂函数，无参，返回 psycopg2 连接对象。
        若未提供，则回退到读取环境变量 DATABASE_URL（本地兼容）。
        """
        if db_connection_func:
            self.get_conn = db_connection_func
        else:
            DATABASE_URL = os.environ.get(
                "DATABASE_URL",
                "postgresql://neondb_owner:npg_jKDUwR6ldfY1@ep-wild-mode-aouqz0r7-pooler.c-2.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"
            )
            self.get_conn = lambda: psycopg2.connect(DATABASE_URL)
        
        self.ds_client = OpenAI(
            api_key="sk-125beb76c63b469485884a6a63deb157",
            base_url="https://api.deepseek.com"
        )

    def _find_philosopher_id(self, cur, name_str):
        """
        根据名字片段在数据库中查找哲学家 ID。
        先尝试精确匹配，再尝试模糊匹配，失败则返回 (name_str, 0)
        """
        if not name_str or len(name_str.strip()) < 1:
            return ("先贤", 0)
        
        # 1. 先精确匹配
        cur.execute("SELECT name, id FROM philosophers WHERE name = %s LIMIT 1", (name_str.strip(),))
        row = cur.fetchone()
        if row:
            return (row[0], row[1])
        
        # 2. 模糊匹配（LIKE %名字%），取第一个
        cur.execute("SELECT name, id FROM philosophers WHERE name LIKE %s LIMIT 1", (f"%{name_str.strip()}%",))
        row = cur.fetchone()
        if row:
            return (row[0], row[1])
        
        # 3. 找不到
        return (name_str.strip() if name_str.strip() else "先贤", 0)

    def run_experiment_simulation(self, experiment_name, user_decision):
        conn = None
        cur = None
        try:
            conn = self.get_conn()
            cur = conn.cursor()
            
            # 1. 获取实验
            cur.execute("SELECT name, description, id FROM thought_experiments WHERE name = %s", (experiment_name,))
            exp = cur.fetchone()
            if not exp:
                return {"text": "未找到实验内容", "philosophers": [], "exp_id": 0}
            
            # 2. 获取巨头名单（用于AI选择，但实际匹配将从AI输出中提取名字再查库）
            cur.execute("SELECT name, id FROM philosophers ORDER BY influence_score DESC LIMIT 15")
            titans = cur.fetchall()
            titan_names = [t[0] for t in titans]
            
            # 3. 构造 Prompt，强调格式
            prompt = f"""
            任务：针对思想实验“{exp[0]}”进行对垒辩论。
            内容简述：{exp[1]}
            用户的决策是："{user_decision}"
            
            执行要求：
            请从名单 {titan_names} 中选出一位支持用户的哲学家 A 和一位持对立观点的哲学家 B。
            输出的名字必须与名单中的文字完全一致。
            
            你必须严格按以下格式输出，不要有任何前言、引号或额外修饰：
            [哲学家A的名字]：[他的支持论点，直接回应用户输入]
            [VS]
            [哲学家B的名字]：[他的反驳论点，直接回应用户和哲学家A]
            
            注意：A的名字和冒号之间不要有其他符号，格式就是“名字：论点”。
            """
            
            resp = self.ds_client.chat.completions.create(
                model="deepseek-chat", 
                messages=[{"role": "user", "content": prompt}], 
                temperature=0.7
            )
            ai_text = resp.choices[0].message.content
            
            # 4. 解析AI输出
            # 用 [VS] 切分成两部分
            parts = ai_text.split('[VS]')
            # 确保至少有两段
            while len(parts) < 2:
                parts.append("")
            
            final_philosophers = []
            final_speeches = []
            
            for i, part in enumerate(parts[:2]):  # 只处理前两段
                text = part.strip()
                # 提取第一个冒号前的名字（支持中英文冒号）
                match = re.search(r'^(.*?)[：:]', text)
                if match:
                    raw_name = match.group(1).strip()
                    # 清洗掉可能的编号、方括号、星号等
                    clean_name = re.sub(r'[\[\]*#\d]', '', raw_name).strip()
                    # 在数据库中查找该名字对应的ID
                    db_name, db_id = self._find_philosopher_id(cur, clean_name)
                    final_philosophers.append({"name": db_name, "id": db_id})
                    # 提取论点内容（冒号之后的部分）
                    speech = text[match.end():].strip()
                    final_speeches.append(speech)
                else:
                    # 没有冒号，整段作为论点，名字用先贤
                    final_philosophers.append({"name": "先贤", "id": 0})
                    final_speeches.append(text)
            
            # 补充缺失的哲学家
            while len(final_philosophers) < 2:
                final_philosophers.append({"name": "先贤", "id": 0})
            while len(final_speeches) < 2:
                final_speeches.append("")
            
            # 重新构建带分隔符的文本，保持前端兼容
            try:
                reformatted_text = f"{final_speeches[0]} [VS] {final_speeches[1]}"
            except:
                reformatted_text = ai_text

            # 5. 返回结果（注意字段名统一用 exp_id）
            return {
                "text": reformatted_text,
                "philosophers": final_philosophers,
                "exp_id": exp[2]
            }
            
        except Exception as e:
            print(f"Error in Simulation: {e}")
            traceback.print_exc()
            return {"text": f"对垒加载失败: {str(e)}", "philosophers": [], "exp_id": 0}
        finally:
            if cur:
                try:
                    cur.close()
                except:
                    pass
            if conn:
                try:
                    conn.close()
                except:
                    pass