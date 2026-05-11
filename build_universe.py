import json
import psycopg2
import base64
import os

# --- 配置 ---
BASE_PATH = os.path.dirname(os.path.abspath(__file__))
DB_CONFIG = {"database": "philosophy_db", "user": "postgres", "password": "536827", "host": "127.0.0.1", "port": "5432"}

def generate_unified_universe():
    conn = psycopg2.connect(**DB_CONFIG); cur = conn.cursor()
    
    # 1. 准备地球数据
    cur.execute("SELECT id, name, era, region, tier, lat, lng, description FROM philosophers WHERE lat IS NOT NULL")
    globe_points = [{"id": r[0], "name": r[1], "era": r[2], "region": r[3], "tier": r[4], "lat": r[5], "lng": r[6], "desc": r[7]} for r in cur.fetchall()]

    # 2. 准备星云数据
    cur.execute("SELECT relation_type FROM relationships GROUP BY relation_type ORDER BY COUNT(*) DESC")
    rel_types = [r[0] for r in cur.fetchall()]
    THEME_COLORS = ["#4da6ff", "#ff4d4d", "#facc15", "#a855f7", "#22c55e", "#ec4899"]
    color_map = {t: THEME_COLORS[i % len(THEME_COLORS)] for i, t in enumerate(rel_types)}
    legend_data = [{"label": k, "color": v} for k, v in color_map.items()]

    cur.execute("""
        SELECT em.raw_name, em.influence_score, em.nebula_brief, p.id,
               CASE WHEN em.influence_score > 0.02 THEN '核心巨头' ELSE '思想节点' END as tier,
               p.era
        FROM entities_mapping em
        LEFT JOIN philosophers p ON em.raw_name = p.name
        WHERE em.influence_score IS NOT NULL
    """)
    nebula_nodes = []
    for r in cur.fetchall():
        nebula_nodes.append({
            "id": r[0], "label": r[0], "size": r[1] * 150 + 3,
            "brief": r[2], "db_id": r[3], "tier": r[4], "era": r[5],
            "font": {"size": 0, "color": "white", "strokeWidth": 2, "strokeColor": "black"}
        })

    cur.execute("""
        SELECT source_entity, target_entity, relation_type FROM relationships 
        WHERE source_entity IN (SELECT raw_name FROM entities_mapping WHERE influence_score IS NOT NULL)
        AND target_entity IN (SELECT raw_name FROM entities_mapping WHERE influence_score IS NOT NULL)
    """)
    nebula_edges = []
    for src, tgt, rel in cur.fetchall():
        clr = color_map.get(rel, "#444")
        nebula_edges.append({
            "from": src, "to": tgt, "label": rel,
            "color": {"color": clr, "opacity": 0.3}, "origColor": clr,
            "font": {"size": 0, "color": "white"}
        })

    # --- 3. 生成 HTML ---
    html_template = f"""
    <!DOCTYPE html>
    <html lang="zh">
    <head>
        <meta charset="UTF-8">
        <title>SOPHIA - THE UNIVERSE</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
        <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
        <link href="https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap" rel="stylesheet">
        <style>
            * {{ box-sizing: border-box; }}
            body, html {{ width: 100%; height: 100%; background-color: #000; color: #d1d5db; margin: 0; overflow: hidden; font-family: 'Microsoft YaHei', serif; }}
            .pixel-font {{ font-family: 'Press Start 2P', cursive !important; image-rendering: pixelated; text-transform: uppercase; }}
            .noise-overlay {{ position: fixed; top: 0; left: 0; width: 100%; height: 100%; background-image: url("https://media.giphy.com/media/oEI9uWUicfG5m/giphy.gif"); opacity: 0.03; pointer-events: none; z-index: 999; }}
            .crt-overlay {{ position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.2) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.03), rgba(0, 255, 0, 0.01), rgba(0, 0, 255, 0.03)); background-size: 100% 4px, 4px 100%; pointer-events: none; z-index: 1000; }}
            .page-bg {{ position: fixed; top: 0; left: 0; width: 100%; height: 100%; background-repeat: no-repeat; background-position: center center; background-size: cover; filter: blur(4px) brightness(0.2); z-index: 0; transition: opacity 0.2s ease-in-out; }}

            .unified-panel {{
                position: fixed; top: 80px; width: 380px; max-height: 80vh;
                background: rgba(15, 15, 20, 0.95); backdrop-filter: blur(12px);
                border: 2px solid #ffffff; box-shadow: 12px 12px 0px #0000ff;
                z-index: 2000; padding: 30px; transition: 0.5s cubic-bezier(0.2, 0.8, 0.2, 1);
                overflow-y: auto;
            }}
            #unified-sidebar {{ left: -420px; }}
            #unified-sidebar.open {{ left: 20px; }}
            
            /* 关键修改：将检索框移至右下角 */
            #pathfinder-panel {{ 
                right: 20px; 
                bottom: 100px; 
                top: auto; 
                display: none; 
            }}

            .refresh-btn-sync {{
                position: fixed; top: 1rem; left: 1rem; z-index: 1001;
                background-color: #111827; color: #eab308; border: 2px solid #eab308;
                padding: 0.5rem 0.75rem; font-size: 0.75rem; cursor: pointer;
                box-shadow: 4px 4px 0px 0px #000; transition: 0.2s;
            }}
            .refresh-btn-sync:hover {{ background-color: #eab308; color: #000; }}

            nav {{ background: rgba(0,0,0,0.8); border-bottom: 2px solid #3b82f6; position: fixed; top: 0; width: 100%; z-index: 50; }}
            nav a {{ color: #aaa; text-decoration: none; padding: 10px 15px; font-size: 10px; transition: 0.3s; font-family: 'Press Start 2P' !important; }}
            nav a:hover, nav a.active {{ color: #facc15; text-shadow: 2px 2px 0px #000; }}

            .view-layer {{ position: absolute; top: 60px; left: 0; width: 100%; height: calc(100% - 60px); opacity: 0; pointer-events: none; transition: opacity 0.5s; }}
            .view-layer.active {{ opacity: 1; pointer-events: auto; }}

            #loader {{ position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); color: #ca8a04; font-family: monospace; z-index: 2000; display: none; text-align: center; }}
            
            /* 关键修改：图例位置固定在右上角 */
            #legend {{ 
                position: fixed; 
                top: 80px; 
                right: 20px; 
                background: rgba(0,0,0,0.6); 
                padding: 15px; 
                border: 1px solid #333; 
                z-index: 500; 
                display: none; 
            }}

            .mode-switcher {{ position: fixed; bottom: 30px; left: 50%; transform: translateX(-50%); display: flex; background: rgba(0,0,0,0.8); border: 2px solid #3b82f6; padding: 5px; z-index: 1500; }}
            .mode-btn {{ padding: 10px 20px; font-size: 10px; cursor: pointer; color: #4b5563; }}
            .mode-btn.active {{ color: #facc15; background: rgba(250, 204, 21, 0.1); border: 1px solid #facc15; }}
            
            .md-content strong {{ color: #facc15; }}
        </style>
    </head>
    <body>
        <div id="dynamic-bg" class="page-bg"></div>
        <div class="noise-overlay"></div><div class="crt-overlay"></div>

        <button class="refresh-btn-sync pixel-font" onclick="refreshBackground()">REFRESH BACKGROUND</button>

        <nav class="flex justify-center py-4">
            <a href="index.html">HOME</a>
            <a href="knowledge_base.html">KNOWLEDGE</a>
            <a href="gallery.html">GALLERY</a>
            <a href="universe.html" class="active">UNIVERSE</a>
            <a href="agent_lab.html">LAB</a>
        </nav>

        <div id="unified-sidebar" class="unified-panel">
            <div class="text-right text-red-500 cursor-pointer pixel-font text-[10px] mb-4" onclick="closeSidebar()">[ CLOSE ]</div>
            <div id="side-avatar-frame" class="w-32 h-32 border-2 border-white shadow-[6px_6px_0_0_#0000ff] mx-auto mb-6 overflow-hidden bg-black">
                <img id="side-img" src="" class="w-full h-full object-cover">
            </div>
            <h2 id="side-name" class="text-2xl font-bold text-white mb-2 text-center"></h2>
            <div id="side-tier-display" class="pixel-font text-[8px] text-center text-yellow-500 mb-6"></div>
            <div id="side-desc" class="md-content text-gray-300 text-xs leading-relaxed text-justify"></div>
        </div>

        <div id="pathfinder-panel" class="unified-panel">
            <h3 class="pixel-font text-yellow-500 text-[10px] mb-4 text-center">PATHFINDER</h3>
            <div class="space-y-4">
                <div>
                    <label class="text-[8px] text-blue-400 block mb-1">START NODE</label>
                    <input id="path-start" type="text" list="node-names" class="w-full bg-black border border-gray-700 p-2 text-xs text-white outline-none focus:border-yellow-500" placeholder="起点...">
                </div>
                <div>
                    <label class="text-[8px] text-blue-400 block mb-1">TARGET NODE</label>
                    <input id="path-end" type="text" list="node-names" class="w-full bg-black border border-gray-700 p-2 text-xs text-white outline-none focus:border-yellow-500" placeholder="终点...">
                </div>
                <button onclick="tracePath()" class="w-full bg-blue-900 hover:bg-yellow-600 text-white p-2 text-[10px] pixel-font transition-colors">TRACE LOGIC</button>
            </div>
            <div id="path-result-container" class="mt-6 border-t border-gray-800 pt-4 hidden">
                <div id="path-display" class="text-xs text-gray-300 italic leading-loose"></div>
            </div>
            <datalist id="node-names"></datalist>
        </div>

        <div id="loader">
            <div class="mb-2 tracking-[0.3em] text-[10px]">INITIALIZING NEBULA</div>
            <div id="progress" class="text-3xl font-bold">0%</div>
        </div>

        <div id="legend">
            {"".join([f'<div class="flex items-center mb-1 text-[10px] text-gray-400"><div class="w-2 h-2 rounded-full mr-2" style="background:{l["color"]}"></div>{l["label"]}</div>' for l in legend_data[:6]])}
        </div>

        <div id="view-globe" class="view-layer active">
            <div id="globe-div" style="width:100%; height:100%;"></div>
        </div>
        <div id="view-nebula" class="view-layer">
            <div id="nebula-div" style="width:100%; height:100%;"></div>
        </div>

        <div class="mode-switcher pixel-font">
            <div id="btn-globe" class="mode-btn active" onclick="switchMode('globe')">GEOSPATIAL</div>
            <div id="btn-nebula" class="mode-btn" onclick="switchMode('nebula')">LOGICAL</div>
        </div>

        <script>
            const API_BASE = "https://sophia-api-production-e49c.up.railway.app/sophia/api";
            const globeRaw = {json.dumps(globe_points)};
            const nebulaNodesRaw = {json.dumps(nebula_nodes)};
            const nebulaEdgesRaw = {json.dumps(nebula_edges)};
            let nebulaNetwork = null;
            let nebulaNodes = null;
            let nebulaEdges = null;

            async function fetchBackground() {{
                try {{
                    const res = await fetch(API_BASE, {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify({{ action: "get_decoration", query: "" }}) }});
                    const data = await res.json();
                    
                    if (data.image_path) {{
                        const bgEl = document.getElementById('dynamic-bg');
                        bgEl.style.opacity = 0;
                        setTimeout(() => {{
                            bgEl.style.backgroundImage = `url('${{data.image_path}}')`;
                            bgEl.style.opacity = 1;
                        }}, 200);
                    }}
                }} catch(e) {{
                    console.error("背景刷新失败:", e);
                }}
            }}

            function refreshBackground() {{ fetchBackground(); }}

            function openSidebar(data) {{
                document.getElementById('side-name').innerText = data.name;
                document.getElementById('side-tier-display').innerText = data.tier || "思想节点";
                const philoId = data.db_id; 
                document.getElementById('side-img').src = philoId ? `static/avatars/avatar_${{philoId}}.png` : 'static/pic/bg.png';
                document.getElementById('side-desc').innerHTML = marked.parse(data.description || data.brief || "");
                document.getElementById('unified-sidebar').classList.add('open');
            }}

            function closeSidebar() {{
                document.getElementById('unified-sidebar').classList.remove('open');
                if (nebulaNetwork && !window.isLocked) {{
                    nebulaNetwork.setOptions({{ physics: true }});
                }}
            }}

            async function tracePath() {{
                const start = document.getElementById('path-start').value;
                const end = document.getElementById('path-end').value;
                if(!start || !end) return;
                const display = document.getElementById('path-display');
                display.innerText = "正在检索路径...";
                document.getElementById('path-result-container').classList.remove('hidden');
                try {{
                    const res = await fetch(API_BASE, {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify({{ action: "path", params: {{ start, end }}, query: "" }}) }});
                    const data = await res.json();
                    display.innerText = data.path || "未发现直接逻辑连接。";
                }} catch(e) {{ display.innerText = "连接失败。"; }}
            }}

            function initGlobe() {{
                const data = [{{
                    type: 'scattergeo', lon: globeRaw.map(p=>p.lng), lat: globeRaw.map(p=>p.lat),
                    text: globeRaw.map(p=>p.name), customdata: globeRaw, mode: 'markers',
                    marker: {{ size: 8, color: globeRaw.map(p=>p.tier === '一代宗师' ? '#FFD700' : '#C0C0C0'), line: {{width:1, color:'white'}} }},
                    hovertemplate: "<b>%{{text}}</b><extra></extra>"
                }}];
                Plotly.newPlot('globe-div', data, {{ geo: {{ projection: {{type: 'orthographic'}}, showland: true, landcolor: '#111', bgcolor: 'rgba(0,0,0,0)', oceancolor: '#050505', showocean: true }}, paper_bgcolor: 'rgba(0,0,0,0)', margin: {{l:0,r:0,t:0,b:0}} }}, {{displayModeBar: false}});
                document.getElementById('globe-div').on('plotly_click', d => {{
                    const p = d.points[0].customdata;
                    openSidebar({{ name: p.name, tier: p.tier, db_id: p.id, description: p.desc }});
                }});
            }}

            function initNebula() {{
                if (nebulaNetwork) return;
                document.getElementById('loader').style.display = 'block';
                nebulaNodes = new vis.DataSet(nebulaNodesRaw);
                nebulaEdges = new vis.DataSet(nebulaEdgesRaw);
                
                const options = {{
                    nodes: {{ shape: 'dot', color: {{ background: '#4da6ff', border: '#1e3a8a' }} }},
                    edges: {{ smooth: {{ type: 'continuous' }}, color: {{ opacity: 0.3 }} }},
                    physics: {{
                        enabled: true,
                        forceAtlas2Based: {{
                            gravitationalConstant: -40,
                            centralGravity: 0.02,
                            springLength: 50,
                            springConstant: 0.05
                        }},
                        maxVelocity: 8,
                        solver: "forceAtlas2Based",
                        timestep: 0.12,
                        stabilization: {{ enabled: true, iterations: 250, updateInterval: 25 }}
                    }},
                    interaction: {{ hover: true, tooltipDelay: 100 }}
                }};

                nebulaNetwork = new vis.Network(document.getElementById('nebula-div'), {{nodes: nebulaNodes, edges: nebulaEdges}}, options);

                nebulaNetwork.on("stabilizationProgress", p => {{
                    document.getElementById('progress').innerText = Math.round((p.iterations/p.total)*100) + "%";
                }});

                nebulaNetwork.on("stabilizationIterationsDone", () => {{
                    document.getElementById('loader').style.display = 'none';
                    nebulaNetwork.fit();
                }});

                nebulaNetwork.on("hoverNode", p => {{
                    if(!window.isLocked) {{
                        nebulaNetwork.setOptions({{ physics: false }});
                        nebulaNodes.update({{ id: p.node, font: {{ size: 16 }} }});
                    }}
                }});
                nebulaNetwork.on("blurNode", p => {{
                    if(!window.isLocked) {{
                        nebulaNetwork.setOptions({{ physics: true }});
                        nebulaNodes.update({{ id: p.node, font: {{ size: 0 }} }});
                    }}
                }});

                nebulaNetwork.on("click", p => {{
                    if (p.nodes.length > 0) {{
                        window.isLocked = true;
                        nebulaNetwork.setOptions({{ physics: false }});
                        const nId = p.nodes[0];
                        const node = nebulaNodes.get(nId);
                        const neighbors = nebulaNetwork.getConnectedNodes(nId);
                        const connectedEdges = nebulaNetwork.getConnectedEdges(nId);

                        openSidebar({{ name: node.id, tier: node.tier, db_id: node.db_id, brief: node.brief }});

                        nebulaNodes.update(nebulaNodes.get().map(n => ({{
                            id: n.id,
                            opacity: (n.id === nId || neighbors.includes(n.id)) ? 1 : 0.05,
                            font: {{ size: n.id === nId ? 35 : (neighbors.includes(n.id) ? 16 : 0) }}
                        }})));

                        nebulaEdges.update(nebulaEdges.get().map(e => ({{
                            id: e.id,
                            color: {{ color: e.origColor, opacity: connectedEdges.includes(e.id) ? 1 : 0.01 }},
                            font: {{ size: connectedEdges.includes(e.id) ? 10 : 0 }}
                        }})));
                        nebulaNetwork.focus(nId, {{ scale: 0.6, animation: {{ duration: 400 }} }});
                    }} else {{
                        window.isLocked = false;
                        closeSidebar();
                        nebulaNodes.update(nebulaNodes.get().map(n => ({{ id: n.id, opacity: 1, font: {{ size: 0 }} }})));
                        nebulaEdges.update(nebulaEdges.get().map(e => ({{ id: e.id, color: {{ color: e.origColor, opacity: 0.3 }}, font: {{ size: 0 }} }})));
                        nebulaNetwork.setOptions({{ physics: true }});
                    }}
                }});
                
                const datalist = document.getElementById('node-names');
                datalist.innerHTML = nebulaNodesRaw.map(n => `<option value="${{n.id}}">`).join('');
            }}

            function switchMode(mode) {{
                document.querySelectorAll('.view-layer').forEach(v => v.classList.remove('active'));
                document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
                document.getElementById(`view-${{mode}}`).classList.add('active');
                document.getElementById(`btn-${{mode}}`).classList.add('active');
                
                if (mode === 'nebula') {{
                    initNebula();
                    document.getElementById('legend').style.display = 'block';
                    document.getElementById('pathfinder-panel').style.display = 'block';
                }} else {{
                    document.getElementById('legend').style.display = 'none';
                    document.getElementById('pathfinder-panel').style.display = 'none';
                    document.getElementById('loader').style.display = 'none';
                }}
                closeSidebar();
            }}

            window.onload = () => {{ fetchBackground(); initGlobe(); }};
        </script>
    </body>
    </html>
    """
    with open(os.path.join(BASE_PATH, "universe.html"), "w", encoding="utf-8") as f:
        f.write(html_template)
    print("✅ 终极修正版 Universe 页面已生成。")

if __name__ == "__main__":
    generate_unified_universe()