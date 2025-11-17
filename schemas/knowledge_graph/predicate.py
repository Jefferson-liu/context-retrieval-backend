from enum import StrEnum


class Predicate(StrEnum):
    # Generic structural / domain relationships
    IS_A = "IS_A"                      # "ProfilePage IS_A Page"
    PART_OF = "PART_OF"                # "CheckoutFlow PART_OF PurchaseJourney"
    HAS_ATTRIBUTE = "HAS_ATTRIBUTE"    # "User HAS_ATTRIBUTE openToWork"
    OWNS = "OWNS"                      # "Company OWNS Product"

    # Capabilities & behavior
    SUPPORTS = "SUPPORTS"              # "Product SUPPORTS multi-tenant usage"
    PERFORMS_ACTION = "PERFORMS_ACTION"  # "Service PERFORMS_ACTION metricsCalculation"
    TRIGGERS = "TRIGGERS"              # "FormSubmit TRIGGERS emailNotification"
    RESULTS_IN = "RESULTS_IN"          # "ProfileCompletion RESULTS_IN unlockVerification"

    # Requirements / rules / constraints
    REQUIRES = "REQUIRES"              # "ApplyButton REQUIRES completeProfile"
    ALLOWS = "ALLOWS"                  # "Role.ADMIN ALLOWS editUser"
    RESTRICTS = "RESTRICTS"            # "RateLimit RESTRICTS apiUsage"

    # Data & state
    PERSISTS = "PERSISTS"              # "Backend PERSISTS userProfileData"
    CALCULATES = "CALCULATES"          # "System CALCULATES conversionRate"
    VALIDATES = "VALIDATES"            # "Form VALIDATES userInput"
    TRACKS = "TRACKS"                  # "AnalyticsModule TRACKS pageViews"
    DISPLAYS = "DISPLAYS"              # "Dashboard DISPLAYS experimentMetrics"

    # Access, visibility, roles
    VISIBLE_TO = "VISIBLE_TO"          # "SalaryRange VISIBLE_TO Recruiter"
    HIDDEN_FROM = "HIDDEN_FROM"        # "InternalNotes HIDDEN_FROM Candidate"
    HAS_ROLE = "HAS_ROLE"              # "User HAS_ROLE Admin"
    HAS_ACCESS_LEVEL = "HAS_ACCESS_LEVEL"  # "Session HAS_ACCESS_LEVEL readOnly"

    # Integrations & dependencies
    INTEGRATES_WITH = "INTEGRATES_WITH"  # "Product INTEGRATES_WITH Stripe"
    DEPENDS_ON = "DEPENDS_ON"            # "Feature DEPENDS_ON authentication"
    READS_FROM = "READS_FROM"            # "Service READS_FROM eventsTopic"
    WRITES_TO = "WRITES_TO"              # "Service WRITES_TO auditLog"

    # Events & communication
    EMITS_EVENT = "EMITS_EVENT"        # "System EMITS_EVENT userSignedUp"
    CONSUMES_EVENT = "CONSUMES_EVENT"  # "NotificationService CONSUMES_EVENT userSignedUp"
    NOTIFIES = "NOTIFIES"              # "System NOTIFIES user"

    # Targeting & segmentation
    TARGETS = "TARGETS"                # "Feature TARGETS newUsers"
    CONFIGURED_BY = "CONFIGURED_BY"    # "FeatureFlag CONFIGURED_BY adminUser"
