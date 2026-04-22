from __future__ import annotations

from uuid import uuid4

from sqlalchemy import literal, select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from infrastructure.models import RepoEdgeRecord, RepoSubjectRecord


class RepoEdgeRepository:
    """Persistence and query operations for repository graph edges."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_many(self, edges: list[dict]) -> int:
        if not edges:
            return 0

        rows = [
            {
                "id": str(uuid4()),
                "run_id": edge["run_id"],
                "from_subject_id": edge["from_subject_id"],
                "to_subject_id": edge["to_subject_id"],
                "edge_type": edge["edge_type"],
                "line": edge.get("line"),
                "column": edge.get("column"),
                "evidence": edge.get("evidence"),
                "is_external_target": edge.get("is_external_target", False),
            }
            for edge in edges
        ]
        stmt = (
            postgres_insert(RepoEdgeRecord)
            .values(rows)
            .on_conflict_do_nothing(
                index_elements=[
                    "run_id",
                    "from_subject_id",
                    "to_subject_id",
                    "edge_type",
                    "line",
                    "column",
                ]
            )
            .returning(RepoEdgeRecord.id)
        )
        result = await self.session.execute(stmt)
        return len(result.scalars().all())

    async def list_for_run(
        self,
        *,
        run_id: str,
        limit: int,
        offset: int,
        edge_type: str | None = None,
        from_subject_type: str | None = None,
        to_subject_type: str | None = None,
        language: str | None = None,
    ) -> list[tuple[RepoEdgeRecord, RepoSubjectRecord, RepoSubjectRecord]]:
        from_subject = aliased(RepoSubjectRecord)
        to_subject = aliased(RepoSubjectRecord)

        stmt = (
            select(RepoEdgeRecord, from_subject, to_subject)
            .join(from_subject, RepoEdgeRecord.from_subject_id == from_subject.id)
            .join(to_subject, RepoEdgeRecord.to_subject_id == to_subject.id)
            .where(RepoEdgeRecord.run_id == run_id)
            .order_by(RepoEdgeRecord.edge_type, RepoEdgeRecord.id)
            .offset(offset)
            .limit(limit)
        )

        if edge_type:
            stmt = stmt.where(RepoEdgeRecord.edge_type == edge_type)
        if from_subject_type:
            stmt = stmt.where(from_subject.subject_type == from_subject_type)
        if to_subject_type:
            stmt = stmt.where(to_subject.subject_type == to_subject_type)
        if language:
            stmt = stmt.where(from_subject.language == language)

        result = await self.session.execute(stmt)
        return [(row[0], row[1], row[2]) for row in result.all()]

    async def count_for_run(self, *, run_id: str, symbol_only: bool) -> int:
        from_subject = aliased(RepoSubjectRecord)
        stmt = (
            select(RepoEdgeRecord.id)
            .join(from_subject, RepoEdgeRecord.from_subject_id == from_subject.id)
            .where(RepoEdgeRecord.run_id == run_id)
        )
        if symbol_only:
            stmt = stmt.where(RepoEdgeRecord.edge_type.in_(["defines", "calls", "inherits", "references"]))
        else:
            stmt = stmt.where(RepoEdgeRecord.edge_type.in_(["imports", "exports"]))

        result = await self.session.execute(stmt)
        return len(result.scalars().all())

    async def list_neighbors_for_file(
        self,
        *,
        run_id: str,
        subject_id: str,
        limit_each_direction: int,
    ) -> list[dict]:
        from_subject = aliased(RepoSubjectRecord)
        to_subject = aliased(RepoSubjectRecord)

        outgoing_stmt = (
            select(
                RepoEdgeRecord.edge_type,
                RepoEdgeRecord.line,
                RepoEdgeRecord.column,
                literal("outgoing").label("direction"),
                to_subject.subject_path.label("related_subject_path"),
                to_subject.subject_type.label("related_subject_type"),
            )
            .join(to_subject, RepoEdgeRecord.to_subject_id == to_subject.id)
            .join(from_subject, RepoEdgeRecord.from_subject_id == from_subject.id)
            .where(
                RepoEdgeRecord.run_id == run_id,
                RepoEdgeRecord.from_subject_id == subject_id,
                from_subject.subject_type == "file",
            )
            .order_by(RepoEdgeRecord.edge_type, RepoEdgeRecord.id)
            .limit(limit_each_direction)
        )
        incoming_stmt = (
            select(
                RepoEdgeRecord.edge_type,
                RepoEdgeRecord.line,
                RepoEdgeRecord.column,
                literal("incoming").label("direction"),
                from_subject.subject_path.label("related_subject_path"),
                from_subject.subject_type.label("related_subject_type"),
            )
            .join(from_subject, RepoEdgeRecord.from_subject_id == from_subject.id)
            .join(to_subject, RepoEdgeRecord.to_subject_id == to_subject.id)
            .where(
                RepoEdgeRecord.run_id == run_id,
                RepoEdgeRecord.to_subject_id == subject_id,
                to_subject.subject_type == "file",
            )
            .order_by(RepoEdgeRecord.edge_type, RepoEdgeRecord.id)
            .limit(limit_each_direction)
        )

        outgoing_result = await self.session.execute(outgoing_stmt)
        incoming_result = await self.session.execute(incoming_stmt)
        rows = list(outgoing_result.all()) + list(incoming_result.all())
        payload: list[dict] = []
        for row in rows:
            payload.append(
                {
                    "direction": row.direction,
                    "edge_type": row.edge_type,
                    "line": row.line,
                    "column": row.column,
                    "related_subject_path": row.related_subject_path,
                    "related_subject_type": row.related_subject_type,
                }
            )
        return payload

    async def list_neighbors_for_subject(
        self,
        *,
        run_id: str,
        subject_id: str,
        limit_each_direction: int,
    ) -> list[dict]:
        """Return incoming/outgoing edges for any subject id."""

        from_subject = aliased(RepoSubjectRecord)
        to_subject = aliased(RepoSubjectRecord)

        outgoing_stmt = (
            select(
                RepoEdgeRecord.edge_type,
                RepoEdgeRecord.line,
                RepoEdgeRecord.column,
                literal("outgoing").label("direction"),
                to_subject.subject_path.label("related_subject_path"),
                to_subject.subject_type.label("related_subject_type"),
                to_subject.symbol_name.label("related_symbol_name"),
                to_subject.symbol_qualname.label("related_symbol_qualname"),
            )
            .join(to_subject, RepoEdgeRecord.to_subject_id == to_subject.id)
            .where(
                RepoEdgeRecord.run_id == run_id,
                RepoEdgeRecord.from_subject_id == subject_id,
            )
            .order_by(RepoEdgeRecord.edge_type, RepoEdgeRecord.id)
            .limit(limit_each_direction)
        )
        incoming_stmt = (
            select(
                RepoEdgeRecord.edge_type,
                RepoEdgeRecord.line,
                RepoEdgeRecord.column,
                literal("incoming").label("direction"),
                from_subject.subject_path.label("related_subject_path"),
                from_subject.subject_type.label("related_subject_type"),
                from_subject.symbol_name.label("related_symbol_name"),
                from_subject.symbol_qualname.label("related_symbol_qualname"),
            )
            .join(from_subject, RepoEdgeRecord.from_subject_id == from_subject.id)
            .where(
                RepoEdgeRecord.run_id == run_id,
                RepoEdgeRecord.to_subject_id == subject_id,
            )
            .order_by(RepoEdgeRecord.edge_type, RepoEdgeRecord.id)
            .limit(limit_each_direction)
        )

        outgoing_result = await self.session.execute(outgoing_stmt)
        incoming_result = await self.session.execute(incoming_stmt)
        rows = list(outgoing_result.all()) + list(incoming_result.all())
        payload: list[dict] = []
        for row in rows:
            payload.append(
                {
                    "direction": row.direction,
                    "edge_type": row.edge_type,
                    "line": row.line,
                    "column": row.column,
                    "related_subject_path": row.related_subject_path,
                    "related_subject_type": row.related_subject_type,
                    "related_symbol_name": row.related_symbol_name,
                    "related_symbol_qualname": row.related_symbol_qualname,
                }
            )
        return payload

    async def list_symbol_hints_for_file(
        self,
        *,
        run_id: str,
        file_subject_id: str,
        limit: int,
    ) -> list[dict]:
        """Return lightweight symbol-level hints for one file subject."""
        symbol_subject = aliased(RepoSubjectRecord)
        related_subject = aliased(RepoSubjectRecord)

        defined_stmt = (
            select(
                RepoEdgeRecord.to_subject_id.label("symbol_id"),
                symbol_subject.symbol_name.label("symbol_name"),
                symbol_subject.symbol_qualname.label("symbol_qualname"),
            )
            .join(symbol_subject, RepoEdgeRecord.to_subject_id == symbol_subject.id)
            .where(
                RepoEdgeRecord.run_id == run_id,
                RepoEdgeRecord.from_subject_id == file_subject_id,
                RepoEdgeRecord.edge_type == "defines",
                symbol_subject.subject_type.in_(["class", "func"]),
            )
            .order_by(symbol_subject.symbol_qualname, RepoEdgeRecord.id)
            .limit(limit)
        )
        defined_result = await self.session.execute(defined_stmt)
        defined_rows = list(defined_result.all())
        if not defined_rows:
            return []

        by_symbol: dict[str, dict] = {}
        ordered_symbol_ids: list[str] = []
        for row in defined_rows:
            symbol_id = row.symbol_id
            ordered_symbol_ids.append(symbol_id)
            by_symbol[symbol_id] = {
                "symbol_name": row.symbol_name or "unknown",
                "symbol_qualname": row.symbol_qualname or row.symbol_name or "unknown",
                "relationships": [],
            }

        rel_stmt = (
            select(
                RepoEdgeRecord.from_subject_id.label("symbol_id"),
                RepoEdgeRecord.edge_type.label("edge_type"),
                RepoEdgeRecord.evidence.label("evidence"),
                related_subject.subject_path.label("related_subject_path"),
                related_subject.subject_type.label("related_subject_type"),
            )
            .join(related_subject, RepoEdgeRecord.to_subject_id == related_subject.id)
            .where(
                RepoEdgeRecord.run_id == run_id,
                RepoEdgeRecord.from_subject_id.in_(ordered_symbol_ids),
                RepoEdgeRecord.edge_type.in_(["calls", "inherits", "references"]),
            )
            .order_by(RepoEdgeRecord.edge_type, RepoEdgeRecord.id)
            .limit(max(limit * 6, 12))
        )
        rel_result = await self.session.execute(rel_stmt)
        for row in rel_result.all():
            bucket = by_symbol.get(row.symbol_id)
            if bucket is None:
                continue
            descriptor = f"{row.edge_type} -> {row.related_subject_path} ({row.related_subject_type})"
            if row.evidence:
                descriptor = f"{descriptor} | {row.evidence}"
            relationships: list[str] = bucket["relationships"]
            if descriptor not in relationships:
                relationships.append(descriptor)
                if len(relationships) > 3:
                    del relationships[3:]

        return [by_symbol[sid] for sid in ordered_symbol_ids if sid in by_symbol]

    async def list_file_edges_for_run(self, *, run_id: str) -> list[dict]:
        """Return file-to-file edges for a run, excluding external targets."""
        from_subject = aliased(RepoSubjectRecord)
        to_subject = aliased(RepoSubjectRecord)
        stmt = (
            select(
                RepoEdgeRecord.from_subject_id,
                RepoEdgeRecord.to_subject_id,
                RepoEdgeRecord.edge_type,
            )
            .join(from_subject, RepoEdgeRecord.from_subject_id == from_subject.id)
            .join(to_subject, RepoEdgeRecord.to_subject_id == to_subject.id)
            .where(
                RepoEdgeRecord.run_id == run_id,
                from_subject.subject_type == "file",
                to_subject.subject_type == "file",
                RepoEdgeRecord.is_external_target.is_(False),
            )
            .order_by(RepoEdgeRecord.edge_type, RepoEdgeRecord.id)
        )
        result = await self.session.execute(stmt)
        return [
            {
                "from_subject_id": row.from_subject_id,
                "to_subject_id": row.to_subject_id,
                "edge_type": row.edge_type,
            }
            for row in result.all()
        ]
