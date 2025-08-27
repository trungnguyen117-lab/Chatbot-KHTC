import os
import json
import re
from datetime import datetime
from llama_index.core.schema import Document
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core import SimpleDirectoryReader

class CustomTransformation:
    def __call__(self, documents):
        transformed_documents = []
        for doc in documents:
            transformed_content = doc.get_content().lower()
            transformed_content = re.sub(r'\s+', ' ', transformed_content)
            transformed_content = re.sub(r'[^\w\s]', '', transformed_content)
            transformed_documents.append(Document(text=transformed_content, metadata=doc.metadata))
        return transformed_documents

def Sentence_Splitter_docs_into_nodes(all_documents):
    try:
        splitter = SentenceSplitter(
            chunk_size=1500,
            chunk_overlap=200
        )
        nodes = splitter.get_nodes_from_documents(all_documents)
        return nodes
    except Exception as e:
        print(f"Error splitting documents into nodes: {e}")
        return []

def save_nodes(nodes, output_file):
    try:
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        nodes_dict = [node.dict() for node in nodes]
        with open(output_file, 'w', encoding="utf-8") as file:
            json.dump(nodes_dict, file, indent=4, ensure_ascii=False)
        print(f"Saved nodes to {output_file}")
    except Exception as e:
        print(f"Error saving nodes to file: {e}")

# NEW FUNCTIONS for API
def process_single_file(file_path, add_metadata=None):
    """Process a single file and return nodes"""
    try:
        documents = SimpleDirectoryReader(input_files=[file_path]).load_data()
        print(f"Loaded document: {os.path.basename(file_path)}")
        
        if add_metadata and documents:
            for doc in documents:
                if doc.metadata is None:
                    doc.metadata = {}
                doc.metadata.update(add_metadata)
        
        custom_transform = CustomTransformation()
        documents = custom_transform(documents)
        nodes = Sentence_Splitter_docs_into_nodes(documents)
        
        print(f"Created {len(nodes)} nodes from {os.path.basename(file_path)}")
        return nodes
        
    except Exception as e:
        print(f"Error processing file {file_path}: {e}")
        return []

def append_nodes_to_json(new_nodes, json_file_path):
    """Append new nodes to existing JSON file"""
    try:
        existing_nodes = []
        if os.path.exists(json_file_path):
            with open(json_file_path, 'r', encoding='utf-8') as f:
                existing_nodes = json.load(f)
        
        new_nodes_dict = [node.dict() for node in new_nodes]
        start_id = len(existing_nodes)
        
        for i, node in enumerate(new_nodes_dict):
            node['id_'] = f"node_{start_id + i}"
        
        all_nodes = existing_nodes + new_nodes_dict
        
        with open(json_file_path, 'w', encoding='utf-8') as f:
            json.dump(all_nodes, f, indent=4, ensure_ascii=False)
            
        print(f"Appended {len(new_nodes)} nodes to {json_file_path}")
        return len(new_nodes)
        
    except Exception as e:
        print(f"Error appending nodes: {e}")
        return 0

if __name__ == '__main__':
    try:
        documents = SimpleDirectoryReader(input_dir=r"../data").load_data()
        print(f"Loaded {len(documents)} documents")

        if documents:
            custom_transform = CustomTransformation()
            documents = custom_transform(documents)
            nodes = Sentence_Splitter_docs_into_nodes(documents)
            
            print(f"Created {len(nodes)} nodes")
            output_file = r"../data/nodes.json"
            save_nodes(nodes, output_file)
        else:
            print("No documents to process.")

    except Exception as e:
        print(f"Error processing documents: {e}")
