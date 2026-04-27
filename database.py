from pymilvus import MilvusClient, DataType
from text import TextProcessor
import os
from typing import List
from util.requester import APIRequester
import asyncio


class MoyuClient(MilvusClient):
    def __init__(self, requester: APIRequester, uri="http://localhost:19530", user="", password="", db_name="", token="", timeout=None, **kwargs):
        super().__init__(uri, user, password, db_name, token, timeout, **kwargs)
        self.requester = requester

    def init_collection(self, collection_name: str = "rag_embeddings"):
        if self.has_collection(collection_name=collection_name):
            return self.get_load_state(collection_name=collection_name)

        schema = self.create_schema(
            auto_id=True,
            enable_dynamic_field=True,
        )

        schema.add_field(field_name="id", datatype=DataType.INT64, is_primary=True)
        schema.add_field(field_name="embedding", datatype=DataType.FLOAT_VECTOR,
                         dim=1536)
        schema.add_field(field_name="type", datatype=DataType.VARCHAR, max_length=16)
        schema.add_field(field_name="path", datatype=DataType.VARCHAR, max_length=1024)
        schema.add_field(field_name="text", datatype=DataType.VARCHAR, max_length=65535)
        schema.add_field(field_name="subject", datatype=DataType.VARCHAR, max_length=64)

        index_params = self.prepare_index_params()

        index_params.add_index(
            field_name="id",
            index_type=""
        )

        index_params.add_index(
            field_name="embedding",
            index_type="",
            metric_type="COSINE"
        )

        self.create_collection(
            collection_name=collection_name,
            schema=schema,
            index_params=index_params
        )

        return self.get_load_state(
            collection_name=collection_name
        )

    def insert(self, data, collection_name="rag_embeddings", timeout=None, partition_name="", **kwargs):
        return super().insert(collection_name, data, timeout, partition_name, **kwargs)

    async def insert_image(self, image_paths: List[str], texts: List[str], collection_name="rag_embeddings", timeout=None,
                     partition_name="", **kwargs):
        assert len(image_paths) == len(texts), "image_paths and texts must have the same length"
        vectors = [(await self.get_fused_embeddings(image_path=image_paths[i], text=texts[i])) for i in range(len(texts))]
        data = [
            {"embedding": vectors[i], "type": "image", "text": texts[i], "path": os.path.abspath(image_paths[i]),
             "subject": "capp"}
            for i in range(len(vectors))
        ]
        return super().insert(collection_name, data, timeout, partition_name, **kwargs)

    def search(self, data, collection_name="rag_embeddings", filter="", limit=10, output_fields=None,
               search_params=None, timeout=None, partition_names=None, anns_field=None, ranker=None, **kwargs):
        return super().search(collection_name, data, filter, limit, output_fields, search_params, timeout,
                              partition_names, anns_field, ranker, **kwargs)

    async def get_text_embeddings(self, text: str):
        return (await self.requester.query_embedding(text, None))['vector']

    async def get_image_embeddings(self, image_path: str):
        return (await self.requester.query_embedding(None, image_path))['vector']

    async def get_fused_embeddings(self, text: str, image_path: str):
        return (await self.requester.query_embedding(text, image_path))['vector']


if __name__ == "__main__":
    async def test():
        client = MoyuClient(f"{os.environ['MILVUS_BASE_URL']}")

        res = client.init_collection()
        print(res)

        # if client.has_collection(collection_name="demo_collection"):
        #     client.drop_collection(collection_name="demo_collection")
        # client.create_collection(
        #     collection_name="demo_collection",
        #     dimension=1536,  # The vectors we will use in this demo has 768 dimensions
        # )

        md_path = r"../data/工艺卡片.md"
        text_processor = TextProcessor()
        with open(md_path, "r+", encoding="utf-8") as f:
            content = f.read()
        chunks = text_processor.split_markdown_for_rag(content, min_words=10, include_subsections=False)

        vectors = []
        for chunk in chunks:
            vector = await client.get_text_embeddings(text=chunk)
            vectors.append(vector)
        # The output vector has 768 dimensions, matching the collection that we just created.
        print("Dim:", 1536)  # Dim: 768 (768,)

        # Each entity has id, vector representation, raw text, and a subject label that we use
        # to demo metadata filtering later.
        data = [
            {"embedding": vectors[i], "type": "text", "text": chunks[i], "path": os.path.abspath(md_path),
             "subject": "capp"}
            for i in range(len(vectors))
        ]

        print("Data has", len(data), "entities, each with fields: ", data[0].keys())
        print("Vector dim:", len(data[0]["embedding"]))

        # insert data
        # res = client.insert(data=data)
        # res = client.insert_image([r"/home/jdy/Documents/AssemblyPlan/backend/data/反推堵盖1.png", r"/home/jdy/Documents/AssemblyPlan/backend/data/反推堵盖2.png"],
        #                            ["这是一张火箭反推堵盖图片，可以参考他进行设计", ""])

        print(res)

        # serach

        query_vectors = client.get_text_embeddings(text="加工内表面螺纹孔")

        # If you don't have the embedding function you can use a fake vector to finish the demo:
        # query_vectors = [ [ random.uniform(-1, 1) for _ in range(768) ] ]

        res = client.search(
            data=[query_vectors],  # query vectors
            limit=2,  # number of returned entities
            output_fields=["text", "subject", "path"],  # specifies fields to be returned
        )

        print(res)

        # search with meta data

        # This will exclude any text in "history" subject despite close to the query vector.
        res = client.search(
            data=[client.get_text_embeddings(text="安装反推火箭堵盖")],
            filter="subject == 'capp'",
            limit=2,
            output_fields=["text", "subject", "path"],
        )

        print(res)

    asyncio.run(test())