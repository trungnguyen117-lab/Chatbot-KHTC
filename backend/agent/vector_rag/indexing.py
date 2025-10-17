import logging
from dotenv import load_dotenv
import os
import json
from fastembed import SparseTextEmbedding, TextEmbedding
from qdrant_client import QdrantClient, models
from qdrant_client.http.models import PointStruct, SparseVector
from tqdm import tqdm
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

load_dotenv()

Qdrant_API_KEY = os.getenv('Qdrant_API_KEY')
Qdrant_URL = os.getenv('Qdrant_URL')
collection_name = os.getenv('COLLECTION_NAME')

class QdrantIndexing:
    """
    A class for indexing documents using Qdrant vector database.
    """

    def __init__(self) -> None:
        """
        Initialize the QdrantIndexing object.
        """
        self.data_path = r"../data/nodes.json" 
        self.embedding_model = HuggingFaceEmbedding(model_name="BAAI/bge-m3")
        self.sparse_embedding_model = SparseTextEmbedding(model_name="Qdrant/bm42-all-minilm-l6-v2-attentions")
        
        # Khởi tạo client cho local hoặc cloud
        if Qdrant_API_KEY:
            # Cloud Qdran
            self.qdrant_client = QdrantClient(
                url=Qdrant_URL,
                api_key=Qdrant_API_KEY)
        else:
            # Local Qdrant
            self.qdrant_client = QdrantClient(
                url=Qdrant_URL or "http://localhost:6333")
        
        self.metadata = []
        self.documents = []
        logging.info("QdrantIndexing object initialized.")

    def load_nodes(self, input_file):
        """
        Load nodes from a JSON file and extract metadata and documents.

        Args:
            input_file (str): The path to the JSON file.
        """
        with open(input_file, 'r', encoding='utf-8', errors='ignore') as file:
            self.nodes = json.load(file)


        for node in self.nodes:
            self.metadata.append(node['metadata'])
            self.documents.append(node['text'])

        logging.info(f"Loaded {len(self.nodes)} nodes from JSON file.")

    def client_collection(self):
        """
        Create a collection in Qdrant vector database.
        """
        if not self.qdrant_client.collection_exists(collection_name=f"{collection_name}"): 
            self.qdrant_client.create_collection(
                collection_name= collection_name,
                vectors_config={
                     'dense': models.VectorParams(
                         size=1024,
                         distance = models.Distance.COSINE,
                     )
                },
                sparse_vectors_config={
                    "sparse": models.SparseVectorParams(
                              index=models.SparseIndexParams(
                                on_disk=True,              
                            ),
                        )
                    }
            )
            logging.info(f"Created collection '{collection_name}' in Qdrant vector database.")

    def create_sparse_vector(self, text):
        """
        Create a sparse vector from the text using SPLADE.
        """
        # Generate the sparse vector using SPLADE model
        embeddings = list(self.sparse_embedding_model.embed([text]))[0]

        # Check if embeddings has indices and values attributes
        if hasattr(embeddings, 'indices') and hasattr(embeddings, 'values'):
            sparse_vector = models.SparseVector(
                indices=embeddings.indices.tolist(),
                values=embeddings.values.tolist()
            )
            return sparse_vector
        else:
            raise ValueError("The embeddings object does not have 'indices' and 'values' attributes.")


    def load_new_documents(self, documents, metadata_list):
        """Load new documents directly without JSON"""
        self.documents = documents
        self.metadata = metadata_list
        logging.info(f"Loaded {len(self.documents)} new documents for indexing.")

    def get_collection_size(self):
        """Get current collection size"""
        try:
            collection_info = self.qdrant_client.get_collection(collection_name)
            return collection_info.points_count
        except:
            return 0

    def documents_insertion_incremental(self):
        """Insert documents with incremental IDs"""
        start_id = self.get_collection_size()
        points = []
        
        for i, (doc, metadata) in enumerate(tqdm(zip(self.documents, self.metadata), total=len(self.documents))):
            dense_embedding = list(self.embedding_model._embed([doc]))[0]
            sparse_vector = self.create_sparse_vector(doc)
            
            point = models.PointStruct(
                id=start_id + i,
                vector={
                    'dense': dense_embedding,
                    'sparse': sparse_vector,
                },
                payload={
                    'text': doc,
                    **metadata
                }
            )
            points.append(point)

        self.qdrant_client.upsert(
            collection_name=collection_name,
            points=points
        )

        logging.info(f"Upserted {len(points)} points with incremental IDs starting from {start_id}.")
        return len(points)

    def documents_insertion(self):
        points = []
        for i, (doc, metadata) in enumerate(tqdm(zip(self.documents, self.metadata), total=len(self.documents))):
            # Generate both dense and sparse embeddings
            dense_embedding = list(self.embedding_model._embed([doc]))[0]
            sparse_vector = self.create_sparse_vector(doc)
            
            # Create PointStruct
            point = models.PointStruct(
                id=i,
                vector={
                    'dense': dense_embedding,
                    'sparse': sparse_vector,
                },
                payload={
                    'text': doc,
                    **metadata  # Include all metadata
                }
            )
            points.append(point)

        # Upsert points
        self.qdrant_client.upsert(
            collection_name=collection_name,
            points=points
        )

        logging.info(f"Upserted {len(points)} points with dense and sparse vectors into Qdrant vector database.")


    
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    indexing = QdrantIndexing()
    indexing.load_nodes(indexing.data_path)
    indexing.client_collection()
    indexing.documents_insertion()
