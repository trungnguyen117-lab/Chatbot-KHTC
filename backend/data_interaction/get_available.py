def get_root_with_subitem(self, label=None):
        with self.driver.session() as session:
            if label:
                query = """
                MATCH (root:Thutuc)
                WHERE NOT EXISTS {
                    MATCH (other)-[r:REQUIRES*]->(root)
                }
                OPTIONAL MATCH (root)-[:REQUIRES]->(child:Thutuc)
                RETURN id(root) AS id,
                    root.title AS title,
                    root.description AS description,
                    root.date AS date,
                    collect(child.title) AS subItems
                """

            results = session.run(query)
            data = []
            for record in results:
                root = record["root"]
                subitems = record["subItems"]
                
                # Xử lý từng trường dữ liệu, trả về null nếu không tồn tại
                try:
                    node_data = {
                        "id": root.get("id", None),
                        "title": root.get("title", None),
                        "description": root.get("description", None), 
                        "date": root.get("date", None),
                        "subItems": [s for s in subitems if s] if subitems else []
                    }
                except Exception as e:
                    print(f"Error processing node: {e}")
                    node_data = {
                        "id": None,
                        "title": None, 
                        "description": None,
                        "date": None,
                        "subItems": []
                    }
                    
                data.append(node_data)
            return data