from __future__ import annotations

import logging
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.models import RepoSubjectRecord

logger = logging.getLogger(__name__)


class RepoSubjectRepository:
    """Persistence for repository file/symbol/external subjects."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, subject_id: str) -> RepoSubjectRecord | None:
        stmt = (
            select(RepoSubjectRecord)
            .where(RepoSubjectRecord.id == subject_id)
            .order_by(RepoSubjectRecord.created_at.asc(), RepoSubjectRecord.id.asc())
            .limit(2)
        )
        result = await self.session.execute(stmt)
        rows = list(result.scalars().all())
        if len(rows) > 1:
            logger.warning("Duplicate repo subjects detected for id=%s count=%s", subject_id, len(rows))
        return rows[0] if rows else None

    async def get_or_create_file(self, *, repo_address: str, subject_path: str, language: str | None) -> RepoSubjectRecord:
        existing = await self._find_existing_file(repo_address=repo_address, subject_path=subject_path)
        if existing:
            if language and existing.language != language:
                existing.language = language
                await self.session.flush()
            return existing

        record = RepoSubjectRecord(
            id=str(uuid4()),
            repo_address=repo_address,
            subject_path=subject_path,
            subject_type="file",
            language=language,
            is_external=False,
            symbol_name=None,
            symbol_qualname=None,
            external_ref=None,
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def get_or_create_symbol(
        self,
        *,
        repo_address: str,
        subject_path: str,
        language: str | None,
        subject_type: str,
        symbol_name: str,
        symbol_qualname: str,
    ) -> RepoSubjectRecord:
        existing = await self._find_existing_symbol(
            repo_address=repo_address,
            subject_type=subject_type,
            subject_path=subject_path,
            symbol_qualname=symbol_qualname,
        )
        if existing:
            if language and existing.language != language:
                existing.language = language
                await self.session.flush()
            return existing

        record = RepoSubjectRecord(
            id=str(uuid4()),
            repo_address=repo_address,
            subject_path=subject_path,
            subject_type=subject_type,
            language=language,
            symbol_name=symbol_name,
            symbol_qualname=symbol_qualname,
            is_external=False,
            external_ref=None,
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def get_or_create_external(self, *, repo_address: str, external_ref: str) -> RepoSubjectRecord:
        existing = await self._find_existing_external(repo_address=repo_address, external_ref=external_ref)
        if existing:
            return existing

        record = RepoSubjectRecord(
            id=str(uuid4()),
            repo_address=repo_address,
            subject_path=external_ref,
            subject_type="external",
            language=None,
            symbol_name=external_ref,
            symbol_qualname=external_ref,
            is_external=True,
            external_ref=external_ref,
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def find_file_by_path(self, *, repo_address: str, subject_path: str) -> RepoSubjectRecord | None:
        stmt = select(RepoSubjectRecord).where(
            RepoSubjectRecord.repo_address == repo_address,
            RepoSubjectRecord.subject_type == "file",
            RepoSubjectRecord.subject_path == subject_path,
        ).order_by(RepoSubjectRecord.created_at.asc(), RepoSubjectRecord.id.asc()).limit(2)
        result = await self.session.execute(stmt)
        rows = list(result.scalars().all())
        if len(rows) > 1:
            logger.warning(
                "Duplicate file path subjects detected repo_address=%s subject_path=%s count=%s",
                repo_address,
                subject_path,
                len(rows),
            )
        return rows[0] if rows else None

    async def find_symbol_by_qualname(
        self,
        *,
        repo_address: str,
        symbol_qualname: str,
    ) -> RepoSubjectRecord | None:
        stmt = (
            select(RepoSubjectRecord)
            .where(
                RepoSubjectRecord.repo_address == repo_address,
                RepoSubjectRecord.symbol_qualname == symbol_qualname,
                RepoSubjectRecord.subject_type.in_(["class", "func"]),
            )
            .order_by(RepoSubjectRecord.created_at.asc(), RepoSubjectRecord.id.asc())
            .limit(2)
        )
        result = await self.session.execute(stmt)
        rows = list(result.scalars().all())
        if len(rows) > 1:
            logger.warning(
                "Duplicate qualname subjects detected repo_address=%s symbol_qualname=%s count=%s",
                repo_address,
                symbol_qualname,
                len(rows),
            )
        return rows[0] if rows else None

    async def find_symbol_by_name(
        self,
        *,
        repo_address: str,
        symbol_name: str,
    ) -> RepoSubjectRecord | None:
        stmt = (
            select(RepoSubjectRecord)
            .where(
                RepoSubjectRecord.repo_address == repo_address,
                RepoSubjectRecord.symbol_name == symbol_name,
                RepoSubjectRecord.subject_type.in_(["class", "func"]),
            )
            .order_by(RepoSubjectRecord.created_at.asc(), RepoSubjectRecord.id.asc())
            .limit(2)
        )
        result = await self.session.execute(stmt)
        rows = list(result.scalars().all())
        if len(rows) > 1:
            logger.warning(
                "Duplicate symbol-name subjects detected repo_address=%s symbol_name=%s count=%s",
                repo_address,
                symbol_name,
                len(rows),
            )
        return rows[0] if rows else None

    async def _find_existing_file(self, *, repo_address: str, subject_path: str) -> RepoSubjectRecord | None:
        stmt = (
            select(RepoSubjectRecord)
            .where(
                RepoSubjectRecord.repo_address == repo_address,
                RepoSubjectRecord.subject_type == "file",
                RepoSubjectRecord.subject_path == subject_path,
                RepoSubjectRecord.symbol_qualname.is_(None),
                RepoSubjectRecord.external_ref.is_(None),
            )
            .order_by(RepoSubjectRecord.created_at.asc(), RepoSubjectRecord.id.asc())
            .limit(2)
        )
        result = await self.session.execute(stmt)
        rows = list(result.scalars().all())
        if len(rows) > 1:
            logger.warning(
                "Duplicate file subjects detected repo_address=%s subject_path=%s count=%s",
                repo_address,
                subject_path,
                len(rows),
            )
        return rows[0] if rows else None

    async def _find_existing_symbol(
        self,
        *,
        repo_address: str,
        subject_type: str,
        subject_path: str,
        symbol_qualname: str,
    ) -> RepoSubjectRecord | None:
        stmt = (
            select(RepoSubjectRecord)
            .where(
                RepoSubjectRecord.repo_address == repo_address,
                RepoSubjectRecord.subject_type == subject_type,
                RepoSubjectRecord.subject_path == subject_path,
                RepoSubjectRecord.symbol_qualname == symbol_qualname,
                RepoSubjectRecord.external_ref.is_(None),
            )
            .order_by(RepoSubjectRecord.created_at.asc(), RepoSubjectRecord.id.asc())
            .limit(2)
        )
        result = await self.session.execute(stmt)
        rows = list(result.scalars().all())
        if len(rows) > 1:
            logger.warning(
                "Duplicate symbol subjects detected repo_address=%s subject_path=%s symbol_qualname=%s count=%s",
                repo_address,
                subject_path,
                symbol_qualname,
                len(rows),
            )
        return rows[0] if rows else None

    async def _find_existing_external(self, *, repo_address: str, external_ref: str) -> RepoSubjectRecord | None:
        stmt = (
            select(RepoSubjectRecord)
            .where(
                RepoSubjectRecord.repo_address == repo_address,
                RepoSubjectRecord.subject_type == "external",
                RepoSubjectRecord.external_ref == external_ref,
                RepoSubjectRecord.is_external.is_(True),
            )
            .order_by(RepoSubjectRecord.created_at.asc(), RepoSubjectRecord.id.asc())
            .limit(2)
        )
        result = await self.session.execute(stmt)
        rows = list(result.scalars().all())
        if len(rows) > 1:
            logger.warning(
                "Duplicate external subjects detected repo_address=%s external_ref=%s count=%s",
                repo_address,
                external_ref,
                len(rows),
            )
        return rows[0] if rows else None
