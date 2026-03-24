from .data import DataRecord, ChunkRecord
from .repo_knowledge import (
    RepoRunRecord,
    RepoSubjectRecord,
    RepoFileSnapshotRecord,
    RepoFileChunkRecord,
    RepoEdgeRecord,
    RepoParseDiagnosticRecord,
    RepoFileSummaryRunRecord,
    RepoFileSummaryRecord,
    RepoFileSummaryDiagnosticRecord,
    RepoFileSummaryUsageRecord,
    RepoFullSummaryRunRecord,
    RepoFullSummaryRecord,
    RepoFullSummaryDiagnosticRecord,
    RepoEmbeddingRunRecord,
    RepoEmbeddingRecord,
    RepoEmbeddingDiagnosticRecord,
    RepoManagerRunRecord,
    RepoManagerSegmentRecord,
    RepoManagerSegmentMemberRecord,
    RepoManagerSegmentSummaryRecord,
    RepoManagerDiagnosticRecord,
)

# Legacy aliases kept for backwards-compatibility with group_summary_service layer
RepoGroupSummaryRunRecord = RepoManagerRunRecord
RepoGroupSummaryRecord = RepoManagerSegmentSummaryRecord
RepoGroupSummaryDiagnosticRecord = RepoManagerDiagnosticRecord
RepoSummaryGroupRecord = RepoManagerSegmentRecord
RepoSummaryGroupMemberRecord = RepoManagerSegmentMemberRecord

__all__ = [
    "DataRecord",
    "ChunkRecord",
    "RepoRunRecord",
    "RepoSubjectRecord",
    "RepoFileSnapshotRecord",
    "RepoFileChunkRecord",
    "RepoEdgeRecord",
    "RepoParseDiagnosticRecord",
    "RepoFileSummaryRunRecord",
    "RepoFileSummaryRecord",
    "RepoFileSummaryDiagnosticRecord",
    "RepoFileSummaryUsageRecord",
    "RepoFullSummaryRunRecord",
    "RepoFullSummaryRecord",
    "RepoFullSummaryDiagnosticRecord",
    "RepoEmbeddingRunRecord",
    "RepoEmbeddingRecord",
    "RepoEmbeddingDiagnosticRecord",
    "RepoManagerRunRecord",
    "RepoManagerSegmentRecord",
    "RepoManagerSegmentMemberRecord",
    "RepoManagerSegmentSummaryRecord",
    "RepoManagerDiagnosticRecord",
]
