# Functional Summary Clustering Vertical Slice

## Goal

Add a new repo-processing vertical slice that creates higher-level **feature** or **business logic summaries** from existing file summaries and group summaries.

The objective is to move from fragmented technical summaries such as:

* user listening data ingestion
* user listening data processing
* user music recommendation algorithm
* user music recommendation UI component

to a single higher-level feature summary such as:

* user music recommendation feature

with all important implementation details captured inside that single feature summary.

This slice should sit **after file summarization and group summarization** in the repo-processing pipeline.

---

## What This Vertical Slice Should Do

This slice should:

1. load all existing summary artifacts for the repo
2. treat file summaries and group summaries as shared inputs
3. build embeddings for those summaries using a richer representation than summary text alone
4. cluster semantically related summaries into candidate feature groupings
5. merge lower-level technical clusters into higher-level business features
6. use Gemini 2.5 Flash to:

   * decide whether nearby clusters belong to the same feature
   * generate final business-logic-oriented feature summaries
7. persist those feature summaries as a first-class repo artifact

---

## Why This Slice Is Needed

File summaries and group summaries are still too close to the implementation layer.

They tell you what individual files or local groups do, but they do not reliably answer:

* what user or business capability is being implemented?
* which backend, UI, data, and orchestration pieces belong to the same feature?
* what is the higher-level functional purpose of this part of the repo?

This vertical slice should bridge that gap.

Its job is not just summarization. Its job is **functional abstraction**.

---

## Core Concept

The system should treat every existing summary artifact as a **summary node** in a common semantic space.

That means:

* file summaries
* group summaries
* possibly later, module summaries or symbol-level summaries

All of these should be embedded and compared together so that the pipeline can discover higher-level feature groupings across layers.

This is important because real features are often split across different parts of the codebase:

* ingestion logic
* processing logic
* algorithmic logic
* backend orchestration
* UI rendering

If those are processed separately, you end up with technical fragments. If they are processed together, you can reconstruct actual product or business features.

---

## High-Level Pipeline

The vertical slice should follow this shape:

```text
repo processing
├── file summaries
├── group summaries
└── functional summary clustering slice
    ├── load summary artifacts
    ├── build embedding representations
    ├── embed all summary nodes
    ├── cluster nodes into candidate feature clusters
    ├── merge related technical clusters into higher-level features
    ├── generate final feature summaries with Gemini 2.5 Flash
    └── persist feature summary artifacts
```

---

## Inputs

This slice should consume all available summary artifacts that already exist from earlier repo processing stages.

At minimum:

* file summaries
* group summaries

Over time, it may also consume:

* module summaries
* dependency group summaries
* architecture slice summaries
* symbol-level rollups

Each summary artifact should also bring along whatever metadata is available, such as:

* title
* summary text
* path
* language
* layer hint
* parent group
* dependency neighbors
* tags or extracted keywords

---

## Important Design Principle: Do Not Cluster Summary Text Alone

The clustering should not operate only on raw summary text.

The embedding representation for each summary node should combine:

* the summary text
* the artifact title
* structural hints like file path
* architectural hints like frontend/backend/data layer
* group ancestry
* tags or extracted domain phrases
* nearby dependency context if available

This matters because two pieces of the same feature may look different at the code level:

* one may talk about ingestion and events
* another may talk about ranking and personalization
* another may talk about rendering recommendations in the UI

If only raw summaries are embedded, these may appear farther apart than they should. Structural and contextual cues help pull them together.

---

## Recommended Clustering Strategy

This should be treated as a **two-stage feature reconstruction process**, not a single clustering pass.

### Stage 1: candidate clustering

Use embeddings to group related summary nodes into **candidate clusters**.

This stage will usually discover local technical neighborhoods such as:

* recommendation ingestion
* recommendation processing
* recommendation UI

That is useful, but it is not yet the final business feature.

### Stage 2: higher-level merge pass

Take those candidate clusters and merge nearby clusters that appear to contribute to the same higher-level feature.

This is the step that turns:

* recommendation ingestion
* recommendation processing
* recommendation ranking
* recommendation UI

into:

* user music recommendation feature

This second step is essential. Without it, the output stays too fragmented.

---

## Recommended First Implementation

For the first version, use a relatively interpretable clustering baseline.

The best first implementation is:

* embed all summary nodes in one space
* run a hierarchical or threshold-based clustering step to produce candidate clusters
* run a second-pass merge step using Gemini 2.5 Flash
* generate one final feature summary per merged cluster

The important thing is not to over-optimize the first clustering pass too early.

The real value comes from the combination of:

* semantic grouping
* structural hints
* LLM-based merge reasoning
* final feature summarization

---

## What the Clustering Stage Should Produce

The clustering stage should output **candidate feature clusters**, not final truth.

Each candidate cluster should represent a tentative grouping of summary artifacts that seem related.

A cluster should know:

* which summary nodes it contains
* what type of nodes those are
* what the rough semantic center of the cluster is
* which members are most representative
* how confident the system is in the grouping

These clusters should then become inputs into the higher-level merge stage.

---

## Higher-Level Merge Stage

This is the most important part of the design.

The merge stage should ask:

* do these two candidate clusters belong to the same end-user or business feature?
* are they just two technical perspectives on one feature?
* should they remain separate?
* is one cluster just infrastructure or shared support code?

This stage should compare nearby clusters using a combination of:

* centroid similarity
* keyword overlap
* path affinity
* dependency overlap
* architectural complementarity
* Gemini 2.5 Flash reasoning

The merge stage should be iterative. It should continue until no more confident merges are found.

---

## Role of Gemini 2.5 Flash

Gemini 2.5 Flash should not replace clustering. It should sit on top of clustering.

It should be used for the parts where semantic reasoning matters most:

### 1. merge decisions

Gemini should determine whether two nearby clusters are really part of the same feature.

### 2. final feature naming

Gemini should produce names that sound like business or product features rather than technical buckets.

### 3. final feature summaries

Gemini should produce the final feature summary that combines all relevant technical evidence into one coherent functional description.

This is a good use of Gemini 2.5 Flash because it keeps the model focused on reasoning and synthesis rather than on doing all the grouping itself.

---

## Prompt Text

### Prompt for merge decisions

You are helping reconstruct business-level software features from repository summaries.

Decide whether these two clusters belong to the same higher-level feature.

Cluster A:
[cluster A payload]

Cluster B:
[cluster B payload]

Return:

* should_merge
* merged_name
* rationale
* confidence from 0 to 1

A merge should happen when both clusters appear to contribute to the same end-user or business feature, even if one is backend or data logic and the other is UI or orchestration logic.

Do not merge clusters just because they are both generic infrastructure or both mention similar technical terms. Focus on whether they jointly implement one coherent feature.

---

### Prompt for final feature summary generation

You are generating a business-logic-oriented feature summary for a software repository.

Given this cluster of file summaries and group summaries, produce a single feature summary.

Cluster:
[cluster payload]

Return:

* name
* summary
* business_purpose
* responsibilities
* representative_node_ids
* confidence from 0 to 1

The output should consolidate technical pieces into one coherent feature description.

Prefer names that describe end-user or business capability, not just implementation layers.

Avoid generic labels like utilities or shared code unless the cluster is clearly infrastructure rather than a product feature.

---

## What the Final Output Should Look Like

Each final output artifact should represent one reconstructed feature.

A feature summary should answer:

* what is the feature called?
* what business or user capability does it provide?
* what are its major responsibilities?
* which summary artifacts support it?
* which artifacts are most representative?
* how confident is the system in this grouping?

This should become a first-class repo artifact, not just a transient intermediate result.

---

## Persistence Requirements

This slice should persist more than just the final summary text.

It should also store:

* final feature name
* final feature summary
* business purpose
* responsibilities
* member summary nodes
* representative summary nodes
* cluster method used
* confidence
* pipeline version
* merge history if possible

That traceability is important because clustering and merge decisions will need debugging later.

---

## Heuristics That Should Exist Early

A few high-level heuristics should be built in from the start.

### Infrastructure should not dominate feature discovery

Clusters dominated by terms like:

* util
* helper
* common
* base
* shared

should not automatically become top-level product features.

They should either be:

* classified as infrastructure
* attached as support context
* or excluded from top-level feature generation unless strongly justified

### Prefer business-capability names

Good outputs sound like:

* user music recommendation feature
* playlist generation and ranking feature
* authentication and session management feature

Bad outputs sound like:

* recommendation cluster 3
* shared frontend logic
* backend helper grouping

### Compare only plausible merge candidates

The merge stage should not compare every cluster with every other cluster.

It should only compare nearby candidate clusters based on semantic and structural similarity.

This keeps the process scalable and reduces bad merges.

### Keep representative evidence

Every final feature should preserve the most representative underlying summary nodes so humans can inspect why that feature exists.

---

## Recommended Implementation Phases

### Phase 1: minimum working version

Build the first end-to-end slice with:

* file summaries and group summaries as input
* shared embedding space
* candidate clustering
* Gemini-based final feature summarization

This gets the core output working.

### Phase 2: merge-based refinement

Add the higher-level merge step so technical subclusters can be fused into real business features.

This is where quality will improve substantially.

### Phase 3: structural improvements

Incorporate stronger non-semantic signals such as:

* dependency relationships
* path affinity
* architectural layer hints
* infrastructure filtering

This will make the system more robust on large real-world repos.

### Phase 4: evaluation and tuning

Add quality checks such as:

* cluster size distribution
* merge counts
* feature count per repo
* proportion of clusters marked infrastructure
* manual spot-check tooling
* gold-set comparison for a few repos

---

## Suggested Vertical Slice Naming

Good names for this slice include:

* `functional_summary`
* `feature_summary_clustering`
* `repo_feature_summaries`
* `functional_feature_reconstruction`

The best name depends on whether you want to emphasize summarization or architecture reconstruction.

If the purpose is mostly business-logic abstraction, `functional_summary` is probably the cleanest.

---

## Final Recommendation

The correct design is to treat this as a **higher-order summarization and feature reconstruction layer** on top of file and group summaries.

The pipeline should:

1. load all summary artifacts
2. embed them in a shared semantic space
3. cluster them into candidate feature groupings
4. merge related technical clusters into business features
5. use Gemini 2.5 Flash to name and summarize the final features
6. persist those feature summaries as first-class repo artifacts

The key idea is that repo processing should not stop at describing files or groups.

It should continue upward until it can describe **what functional capabilities the repository actually implements**.
