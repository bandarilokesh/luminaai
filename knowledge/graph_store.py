import json
import networkx as nx
from typing import Dict, Any, List
from database.db_helper import db
from utils.logger import logger

class GraphStore:
    """
    Manages persistence of the Knowledge Graph to SQLite.
    """
    
    def save_graph(self, graph: nx.DiGraph):
        """Saves a NetworkX graph to the database."""
        conn = db._get_connection()
        try:
            cursor = conn.cursor()
            
            # Map of in-memory node ID to DB node ID
            node_id_map = {}
            
            # 1. Save Nodes
            for node, attr in graph.nodes(data=True):
                paper_id = attr.get("paper_id", "")
                node_type = attr.get("type", "Entity")
                node_name = str(node)
                
                # Remove primary keys from attributes if present
                clean_attr = {k: v for k, v in attr.items() if k not in ["paper_id", "type"]}
                
                # Check if exists
                cursor.execute(
                    "SELECT id FROM knowledge_graph_nodes WHERE node_name = ? AND node_type = ?",
                    (node_name, node_type)
                )
                row = cursor.fetchone()
                if row:
                    db_id = row["id"]
                    # Update
                    cursor.execute(
                        "UPDATE knowledge_graph_nodes SET attributes_json = ?, paper_id = ? WHERE id = ?",
                        (json.dumps(clean_attr), paper_id, db_id)
                    )
                else:
                    # Insert
                    cursor.execute(
                        "INSERT INTO knowledge_graph_nodes (node_name, node_type, paper_id, attributes_json) VALUES (?, ?, ?, ?)",
                        (node_name, node_type, paper_id, json.dumps(clean_attr))
                    )
                    db_id = cursor.lastrowid
                    
                node_id_map[node] = db_id
                
            # 2. Save Edges
            for u, v, attr in graph.edges(data=True):
                u_db = node_id_map.get(u)
                v_db = node_id_map.get(v)
                
                if not u_db or not v_db:
                    continue
                    
                edge_type = attr.get("type", "RELATES_TO")
                clean_attr = {k: val for k, val in attr.items() if k != "type"}
                
                # Check if exists
                cursor.execute(
                    "SELECT id FROM knowledge_graph_edges WHERE source_node_id = ? AND target_node_id = ? AND edge_type = ?",
                    (u_db, v_db, edge_type)
                )
                if not cursor.fetchone():
                    cursor.execute(
                        "INSERT INTO knowledge_graph_edges (source_node_id, target_node_id, edge_type, metadata_json) VALUES (?, ?, ?, ?)",
                        (u_db, v_db, edge_type, json.dumps(clean_attr))
                    )
                    
            conn.commit()
            logger.info(f"Saved graph with {graph.number_of_nodes()} nodes and {graph.number_of_edges()} edges to DB.")
        except Exception as e:
            conn.rollback()
            logger.error(f"Error saving graph to DB: {e}")
        finally:
            conn.close()

    def load_graph(self, paper_ids: List[str] = None) -> nx.DiGraph:
        """Loads the graph from DB. If paper_ids is provided, loads a subgraph."""
        graph = nx.DiGraph()
        conn = db._get_connection()
        try:
            cursor = conn.cursor()
            
            # Load Nodes
            if paper_ids:
                placeholders = ",".join("?" * len(paper_ids))
                cursor.execute(
                    f"SELECT * FROM knowledge_graph_nodes WHERE paper_id IN ({placeholders}) OR paper_id = ''",
                    paper_ids
                )
            else:
                cursor.execute("SELECT * FROM knowledge_graph_nodes")
                
            nodes = cursor.fetchall()
            db_to_name = {}
            for row in nodes:
                db_to_name[row["id"]] = row["node_name"]
                attrs = json.loads(row["attributes_json"])
                attrs["type"] = row["node_type"]
                attrs["paper_id"] = row["paper_id"]
                graph.add_node(row["node_name"], **attrs)
                
            # Load Edges
            # We only load edges where BOTH source and target are in our loaded nodes
            if nodes:
                node_ids = [str(r["id"]) for r in nodes]
                placeholders = ",".join(node_ids)
                cursor.execute(
                    f"SELECT * FROM knowledge_graph_edges WHERE source_node_id IN ({placeholders}) AND target_node_id IN ({placeholders})"
                )
                
                for row in cursor.fetchall():
                    u_name = db_to_name.get(row["source_node_id"])
                    v_name = db_to_name.get(row["target_node_id"])
                    if u_name and v_name:
                        attrs = json.loads(row["metadata_json"])
                        attrs["type"] = row["edge_type"]
                        graph.add_edge(u_name, v_name, **attrs)
                        
            logger.info(f"Loaded graph with {graph.number_of_nodes()} nodes and {graph.number_of_edges()} edges.")
        except Exception as e:
            logger.error(f"Error loading graph from DB: {e}")
        finally:
            conn.close()
            
        return graph

graph_store = GraphStore()
