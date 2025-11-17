PREDICATE_DEFINITIONS = {
    "IS_A": (
        "Denotes a class-or-type relationship between two entities. "
        "Used when an entity represents a category, role, or conceptual type "
        "(e.g., 'ProfilePage IS_A UI Page', 'Designer IS_A Role')."
    ),

    "HAS_ATTRIBUTE": (
        "Indicates that an entity possesses a property, attribute, or field. "
        "Used for profile fields, configuration values, or feature flags "
        "(e.g., 'User HAS_ATTRIBUTE locationPreferences')."
    ),

    "HAS_ROLE": (
        "Associates a user or entity with a defined role, permission level, or identity. "
        "Useful for role-based access or team composition "
        "(e.g., 'User HAS_ROLE Admin')."
    ),

    "HOLDS_ROLE": (
        "Connects a person or team member to their position in an organisation or product team "
        "(e.g., 'Olga HOLDS_ROLE Designer', 'Victor HOLDS_ROLE Recruiter')."
    ),

    "PART_OF": (
        "Indicates hierarchical inclusion, module membership, or organisational belonging "
        "(e.g., 'Position PART_OF UserProfile', 'NotificationsService PART_OF Backend')."
    ),

    "SUPPORTS": (
        "Indicates that a system, feature, or service provides or enables a capability "
        "(e.g., 'Dashboard SUPPORTS filtering', 'API SUPPORTS pagination')."
    ),

    "PERFORMS_ACTION": (
        "Describes an action executed by a system, component, or service "
        "(e.g., 'MatchingEngine PERFORMS_ACTION scoring')."
    ),

    "TRIGGERS": (
        "Represents an event-driven causal action where one action initiates another "
        "(e.g., 'FormSubmit TRIGGERS recalculation')."
    ),

    "DISPLAYS": (
        "Indicates that a UI surface or component renders or shows information "
        "(e.g., 'ProfilePage DISPLAYS completionBanner')."
    ),

    "RECOMMENDS": (
        "Used when the system suggests items, options, projects, or content to a user "
        "(e.g., 'MatchingEngine RECOMMENDS jobs')."
    ),

    "REQUIRES": (
        "Expresses a prerequisite or condition needed for an action or feature to work "
        "(e.g., 'ApplyButton REQUIRES completeProfile')."
    ),

    "VALIDATES": (
        "Indicates a system performing checks against rules or constraints "
        "(e.g., 'ApplicationForm VALIDATES candidateLocation')."
    ),

    "VISIBLE_TO": (
        "Indicates visibility or access of information to a specific role or viewer type "
        "(e.g., 'SalaryRange VISIBLE_TO Recruiter')."
    ),

    "HIDDEN_FROM": (
        "Indicates that information is explicitly restricted from certain viewer types "
        "(e.g., 'InternalNotes HIDDEN_FROM Candidate')."
    ),

    "INTEGRATES_WITH": (
        "Expresses a system or module dependency or external integration "
        "(e.g., 'Backend INTEGRATES_WITH Stripe')."
    ),

    "DEPENDS_ON": (
        "Captures functional or architectural dependency "
        "(e.g., 'FileUpload DEPENDS_ON S3Storage')."
    ),

    "READS_FROM": (
        "Indicates a data-flow relationship where a system reads from a source "
        "(e.g., 'FeedService READS_FROM EventsTopic')."
    ),

    "WRITES_TO": (
        "Indicates that a system or process outputs data to a destination "
        "(e.g., 'AuditService WRITES_TO LogsTable')."
    ),

    "EMITS_EVENT": (
        "Represents a system publishing or broadcasting an event "
        "(e.g., 'UserSignup EMITS_EVENT ProfileCreated')."
    ),

    "CONSUMES_EVENT": (
        "Represents a system reacting to or processing an event "
        "(e.g., 'NotificationService CONSUMES_EVENT ProfileCreated')."
    ),

    "PERSISTS": (
        "Denotes that a system stores or saves data in a persistent medium "
        "(e.g., 'Backend PERSISTS userProfileData')."
    ),

    "TARGETS": (
        "Indicates that a feature, message, experiment, or product is directed at a specific user group "
        "(e.g., 'OnboardingFlow TARGETS newUsers')."
    ),

    "RESULTS_IN": (
        "Captures a causal outcome relationship between events or actions "
        "(e.g., 'ProfileCompletion RESULTS_IN unlockingJobApplications')."
    )
}
