import networkx as nx
from typing import List, Dict, Any
from database.db_helper import db
from knowledge.graph_store import graph_store
from utils.logger import logger

class GraphManager:
    """
    Constructs and manages the Knowledge Graph.
    """
    
    def build_graph_for_papers(self, paper_ids: List[str]):
        """
        Builds a local knowledge graph from the structured knowledge of the given papers.
        """
        graph = nx.DiGraph()
        
        conn = db._get_connection()
        try:
            cursor = conn.cursor()
            
            # Fetch all structured knowledge for these papers
            placeholders = ",".join("?" * len(paper_ids))
            cursor.execute(
                f"SELECT * FROM structured_knowledge WHERE paper_id IN ({placeholders})",
                paper_ids
            )
            rows = cursor.fetchall()
            
            # Add Paper nodes first
            for pid in paper_ids:
                paper_meta = db.get_paper(pid)
                if paper_meta:
                    graph.add_node(
                        pid, 
                        type="Paper", 
                        title=paper_meta["title"], 
                        authors=paper_meta["authors"],
                        paper_id=pid
                    )
            
            for row in rows:
                entity_type = row["entity_type"]
                entity_name = row["entity_name"]
                entity_val = row["entity_value"]
                paper_id = row["paper_id"]
                
                if not entity_name:
                    continue
                    
                # Add Entity Node
                graph.add_node(
                    entity_name,
                    type=entity_type.capitalize(),
                    value=entity_val,
                    paper_id=paper_id
                )
                
                # Link Paper -> Entity
                graph.add_edge(paper_id, entity_name, type="PROPOSES" if entity_type == "methods" else "USES")
                
            # Compute cross-document links (e.g. same dataset used by multiple papers)
            # This is a naive exact-match entity resolution. In production, we'd use fuzzy matching or LLM.
            datasets = [n for n, attr in graph.nodes(data=True) if attr.get("type") == "Datasets"]
            methods = [n for n, attr in graph.nodes(data=True) if attr.get("type") == "Methods"]
            
            # (We rely on exact string match of entity_name for implicit sharing)
            
            # Save the updated graph
            graph_store.save_graph(graph)
            logger.info(f"Built and saved graph for {len(paper_ids)} papers.")
            
        except Exception as e:
            logger.error(f"Error building graph: {e}")
        finally:
            conn.close()

graph_manager = GraphManager()
