from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Dict

from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, utility

from .milvus_client import MilvusClientFactory


@dataclass(slots=True)
class MilvusCollectionSpec:
    """Definition for the Milvus collection used to persist embeddings."""

    name: str
    primary_field: str
    vector_field: str
    vector_dimension: int
    metric_type: str
    index_params: Dict[str, Any]


async def ensure_collection(factory: MilvusClientFactory, spec: MilvusCollectionSpec) -> Collection:
    """Create the collection if absent and ensure it is loaded and indexed."""

    alias = await factory.ensure_connection()
    loop = asyncio.get_event_loop()

    def _define_fields() -> Collection:
        if not utility.has_collection(spec.name, using=alias):
            field_schemas = [
                FieldSchema(
                    name=spec.primary_field,
                    dtype=DataType.INT64,
                    is_primary=True,
                    auto_id=False,
                ),
                FieldSchema(name="tenant_id", dtype=DataType.INT64),
                FieldSchema(name="project_id", dtype=DataType.INT64),
                FieldSchema(
                    name=spec.vector_field,
                    dtype=DataType.FLOAT_VECTOR,
                    dim=spec.vector_dimension,
                ),
            ]
            schema = CollectionSchema(
                fields=field_schemas,
                description="Context retrieval chunk embeddings",
                enable_dynamic_field=False,
            )
            collection = Collection(
                name=spec.name,
                schema=schema,
                using=alias,
            )

            if spec.index_params:
                collection.create_index(
                    field_name=spec.vector_field,
                    index_params=spec.index_params,
                )
        else:
            collection = Collection(name=spec.name, using=alias)
            vector_field = next(
                (field for field in collection.schema.fields if field.name == spec.vector_field),
                None,
            )
            if vector_field is None:
                raise ValueError(
                    f"Milvus collection '{spec.name}' is missing vector field '{spec.vector_field}'."
                )
            existing_dim = int(vector_field.params.get("dim", 0))
            if existing_dim != spec.vector_dimension:
                collection.release()
                collection.drop()
                return _define_fields()

            if not collection.has_index():
                collection.create_index(
                    field_name=spec.vector_field,
                    index_params=spec.index_params,
                )

        collection.load()
        return collection

    return await loop.run_in_executor(None, _define_fields)
