import os
import psycopg2
import networkx as nx

# --- 数据库连接：优先使用环境变量，兼容本地开发 ---
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:536827@127.0.0.1:5432/philosophy_db")

def get_db_conn():
    """统一获取数据库连接"""
    return psycopg2.connect(DATABASE_URL)


class ThoughtPathFinder:
    def __init__(self):
        # 不再需要存储 DB_CONFIG，直接使用统一的连接函数
        pass

    def _get_db_conn(self):
        return get_db_conn()

    def _build_nx_graph(self):
        """简化版：构建无向图，只关注节点的联通性"""
        conn = self._get_db_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT source_entity, target_entity 
            FROM relationships 
            WHERE source_entity IN (SELECT raw_name FROM entities_mapping)
            AND target_entity IN (SELECT raw_name FROM entities_mapping)
        """)
        edges = cur.fetchall()
        
        G = nx.Graph()
        for src, tgt in edges:
            if src == "柏拉图" or tgt == "柏拉图":
                print(f"DEBUG: 发现节点 {src} <-> {tgt}")
            G.add_edge(src, tgt)
        cur.close()
        conn.close()
        return G

    def get_thought_path(self, start_node, end_node):
        """在图谱中寻找思想演变路径，返回路径字符串，失败返回'路径未找到'"""
        conn = self._get_db_conn()
        cur = conn.cursor()
        G = self._build_nx_graph()
        
        try:
            path = nx.shortest_path(G, source=start_node, target=end_node)
            path_str = []
            
            for i in range(len(path) - 1):
                u, v = path[i], path[i+1]
                cur.execute(
                    "SELECT relation_type FROM relationships WHERE (source_entity=%s AND target_entity=%s) OR (source_entity=%s AND target_entity=%s) LIMIT 1",
                    (u, v, v, u)
                )
                rel_info = cur.fetchone()
                rel_type = rel_info[0] if rel_info else "关联"
                path_str.append(f"{u}->{v}({rel_type})")
            
            result = " -> ".join(path_str)
            print(f"DEBUG: 最终计算出的路径是: {result}")
            return result

        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return "路径未找到"
        finally:
            cur.close()
            conn.close()


def get_thought_path(start_node, end_node):
    """保持原有的函数调用方式，返回路径字符串，失败返回'路径未找到'"""
    finder = ThoughtPathFinder()
    return finder.get_thought_path(start_node, end_node)


if __name__ == "__main__":
    result = get_thought_path("柏拉图", "亚里士多德")
    print("最终结果：", result)