LABEL_DEFINITIONS = {
    "episode_labelling": {
        "FACT": dict(
            definition=(
                "Statements that describe objective product behavior, system capabilities, "
                "business rules, constraints, user flows, acceptance criteria, or "
                "implementation details. These statements can be verified through product "
                "specifications, documentation, or the actual system."
            ),
            date_handling_guidance=(
                "Facts may describe either (1) a single event or requirement that became "
                "true at a specific moment, or (2) an ongoing product behavior or rule. "
                "Static facts refer to specific points in time (e.g., when a feature was "
                "released). Dynamic facts refer to continuous states (e.g., a feature that "
                "is currently active or a system process that runs continuously)."
            ),
            date_handling_example=(
                "'The Apply button appears only when the user has a complete profile', "
                "'Version 2.1 introduced profile visibility states', or "
                "'The onboarding flow triggers recalculation on every data change'."
            ),
        ),
        "OPINION": dict(
            definition=(
                "Statements expressing subjective perspectives, stakeholder preferences, "
                "product judgments, qualitative assessments, perceived risks, or non-verifiable "
                "assumptions. This includes UX feedback, stakeholder commentary, or internal "
                "product opinions that cannot be empirically validated."
            ),
            date_handling_guidance=(
                "Opinion statements are always static—they record the moment the opinion was "
                "expressed but do not describe system behavior or future commitments."
            ),
            date_handling_example=(
                "'Recruiters find the current workflow confusing', "
                "'We believe reducing friction will increase profile completion', or "
                "'The new dashboard feels too cluttered'."
            ),
        ),
        "PREDICTION": dict(
            definition=(
                "Forward-looking statements describing planned features, roadmap expectations, "
                "hypothesized product outcomes, experimental hypotheses, projected KPIs, or "
                "anticipated user behavior. These statements describe what might happen but "
                "have not occurred yet and therefore cannot be verified."
            ),
            date_handling_guidance=(
                "Prediction statements are static—they represent the date the forecast or "
                "expectation was made, not when/if it becomes true."
            ),
            date_handling_example=(
                "'We expect the new onboarding flow to improve activation by 20%', "
                "'The system will support multi-tenant accounts in Q4', or "
                "'Introducing job discovery should increase weekly applications'."
            ),
        ),
    },
    "temporal_labelling": {
        "STATIC": dict(
            definition=(
                "Statements describing a product or system event that occurred at a specific "
                "moment in time, or a requirement tied to a discrete point (e.g., a release, "
                "a configuration change, the introduction of a rule). These statements remain "
                "permanently valid as historical facts."
            ),
            date_handling_guidance=(
                "valid_at is the date/time of the event or introduction of the requirement; "
                "invalid_at is None because historical facts never stop being true."
            ),
            date_handling_example=(
                "'Feature flag X was enabled on March 5', "
                "'Version 1.3 added ProfileCompletion logic', or "
                "'The system validated location preferences at submission time'."
            ),
        ),
        "DYNAMIC": dict(
            definition=(
                "Statements describing ongoing product behavior, system states, business rules, "
                "or functional relationships that persist over a period of time. These remain "
                "true until explicitly changed by a new requirement, system update, or "
                "contradictory fact."
            ),
            date_handling_guidance=(
                "valid_at is the date the behavior/state began; invalid_at is the date it ended, "
                "or None if it is still active. Dynamic statements commonly appear in current "
                "system behavior descriptions, user flows, or operational conditions."
            ),
            date_handling_example=(
                "'The system automatically recalculates metrics on every form edit', "
                "'Candidates must complete one PositionDetails record to apply', or "
                "'The recommendation engine runs every 24 hours'."
            ),
        ),
        "ATEMPORAL": dict(
            definition=(
                "Statements that will always hold true regardless of time therefore have no "
                "temporal bounds."
            ),
            date_handling_guidance=(
                "These statements are assumed to be atemporal and have no temporal bounds. Both "
                "their valid_at and invalid_at are None."
            ),
            date_handling_example=(
                "'A stock represents a unit of ownership in a company', 'The earth is round', or "
                "'Europe is a continent'. These statements are true regardless of time."
            ),
        ),
    },
}

