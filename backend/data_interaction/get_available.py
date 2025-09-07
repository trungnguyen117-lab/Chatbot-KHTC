def get_root_with_subitem(self, label=None):
        """
        Lấy các node cấp 0 (root) và danh sách subItems (node con trực tiếp).
        Trả về null nếu không tìm thấy trường dữ liệu.
        """
        with self.driver.session() as session:
            if label:
                query = f"""
                MATCH (root:{label})
                WHERE NOT ( ()-[:*]->(root) )
                OPTIONAL MATCH (root)-[:HAS_SUBITEM]->(child)
                RETURN root, collect(child.title) as subItems
                """
            else:
                query = """
                MATCH (root)
                WHERE NOT ( ()-[:*]->(root) )
                OPTIONAL MATCH (root)-[:HAS_SUBITEM]->(child)
                RETURN root, collect(child.title) as subItems
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