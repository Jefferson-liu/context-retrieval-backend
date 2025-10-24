# TrackRec Profile User Stories - BDD Format

## US001: Automatic Profile Metrics Calculation

**As a** sales professional editing my TrackRec profile  
**I want** the ProfilePage module to automatically recalculate metrics when I update any data  
**So that** I see real-time updates without manual intervention  

### Profile Module Components Referenced:
- **Position**: All position records with PositionDetails
- **PositionDetails**: dealSize, salesCycle, channelSplit, segmentSplit, quotaAchievements
- **UserAccounts.metrics**: weightedAverageExistingBusiness, weightedAverageNewBusiness, outboundAverage, inboundAverage

### Scenarios

**Scenario 1: Real-time calculation during position editing**
- **Given** I am on the ProfilePage editing a Position record
- **When** I update any PositionDetails fields (dealSize, salesCycle, channelSplit, segmentSplit)
- **Then** UserAccounts.metrics automatically recalculates based on all Position records
- **And** the ProfilePage charts (business mix, source, segment, TRG) update immediately

**Scenario 2: Incomplete position data handling**
- **Given** I have Position records with some missing PositionDetails fields
- **When** the ProfilePage calculates UserAccounts.metrics
- **Then** missing PositionDetails fields are excluded from calculations (not treated as zero)
- **And** Position records with only title + company + dates still contribute to experience years

**Scenario 3: Manual recalculate button removal**
- **Given** I am viewing my ProfilePage with updated Position data
- **When** any PositionDetails change is saved
- **Then** no manual "recalculate" button appears or is needed
- **And** all dependent metrics update automatically without user action

### Acceptance Criteria
- [ ] Remove existing manual recalculate button from ProfilePage component entirely
- [ ] UserAccounts.metrics recalculate when any PositionDetails fields change
- [ ] ProfilePage right-hand panel charts populate after entering metrics for ≥1 Position
- [ ] Missing PositionDetails fields excluded from UserAccounts.metrics calculation (not zeroed)
- [ ] Position records with title + company + dates count toward experience years regardless of PositionDetails completion
- [ ] Mobile ProfilePage users experience same real-time calculation functionality

### Business Value
- **Candidate Experience**: Eliminates friction causing 30% profile abandonment
- **Data Quality**: Real-time feedback encourages complete PositionDetails entry
- **B2B Differentiation**: Sophisticated metrics calculation impresses potential platform buyers

### Implementation Notes
- **Frontend Repository (ProfilePage components)**:
  - Remove manual recalculate button from ProfilePage layout
  - Add React hooks triggering calculations on PositionDetails form changes
  - Update chart components to re-render when UserAccounts.metrics changes
- **Backend Repository**:
  - Create metrics calculation service processing all Position and PositionDetails records
  - Handle null/undefined PositionDetails fields by exclusion, not zero-value treatment
  - Return structured UserAccounts.metrics for business mix, source, segment, TRG visualizations
- **API Integration**: ProfilePage triggers backend metrics API on any Position/PositionDetails save
- **Validation**: Ensure calculations work across various Position completion states and mobile devices

---

## US002: Profile Data Auto-Population from External Sources

**As a** sales professional creating my TrackRec profile  
**I want** the ProfileCreation module to automatically populate from my resume and LinkedIn data  
**So that** I spend less time on manual data entry and have a complete profile faster  

### Profile Module Components Referenced:
- **UserAccounts**: fullName, about, locationPreferences, resumeParsedData, oteExpectation
- **Position**: role, startMonth/Year, endMonth/Year, company
- **Keywords**: languages, nextDesiredTitles  
- **PositionDetails**: industry, soldToIndustry, notableClients

### Scenarios

**Scenario 1: Resume upload data extraction**
- **Given** I am on the ProfileCreation flow
- **When** I upload a PDF or DOCX resume to the DataEnrichment module
- **Then** the system extracts data and populates UserAccounts.about, Position records, and Keywords.languages
- **And** PositionDetails.industry and PositionDetails.soldToIndustry populate from work history analysis
- **And** UserAccounts.resumeParsedData stores the raw extracted JSON data

**Scenario 2: LinkedIn OAuth data synchronization**
- **Given** I authenticate with LinkedIn OAuth during ProfileCreation
- **When** the LinkedIn API extraction completes successfully
- **Then** UserAccounts.fullName and UserAccounts.about populate from LinkedIn profile data
- **And** Position records auto-create with role, company, startMonth/Year, endMonth/Year from LinkedIn experience
- **And** Keywords.nextDesiredTitles suggests based on current Position.role and previous Position.role values

**Scenario 3: Location and salary preferences extraction**
- **Given** my resume contains location information OR LinkedIn profile has location data
- **When** the DataEnrichment module processes the location data
- **Then** UserAccounts.locationPreferences populates with extracted city/state information
- **And** UserAccounts.oteExpectation pre-fills if salary information is detected in resume text

### Acceptance Criteria
- [ ] DataEnrichment module populates UserAccounts.about from resume/LinkedIn summary text
- [ ] Position records auto-create with extracted role, company, startMonth/Year, endMonth/Year data
- [ ] Keywords.nextDesiredTitles auto-populate based on current and previous Position.role values
- [ ] PositionDetails.industry populates from employer company business sector analysis
- [ ] PositionDetails.soldToIndustry populates from client names mentioned in Position descriptions
- [ ] UserAccounts.locationPreferences populates from resume/LinkedIn location data
- [ ] ProfileCreation form shows visual indicators for imported vs manual data entry fields
- [ ] Users can edit all auto-populated data before saving to respective modules
- [ ] UserAccounts.resumeParsedData stores complete extracted JSON for future reference

### Business Value
- **Candidate Onboarding**: Faster ProfileCreation increases completion rates from 40% to 70%
- **Data Quality**: AI extraction provides more comprehensive Position and PositionDetails records
- **Platform Differentiation**: Advanced DataEnrichment module becomes key B2B selling point

### Implementation Notes
- **DataEnrichment Module**: Create dedicated service handling OpenAI GPT integration for all extraction
- **Frontend Repository (ProfileCreation components)**:
  - Update UserAccounts form fields to display pre-populated data
  - Create Position components that show imported experience records
  - Add visual indicators distinguishing imported vs manual Keywords and PositionDetails
- **Backend Repository**:
  - Build LinkedIn API service populating UserAccounts and Position tables
  - Create resume parsing service writing to UserAccounts.resumeParsedData
  - Implement AI classification service for PositionDetails.industry mapping
- **Database Schema**: Ensure UserAccounts, Position, Keywords, PositionDetails support imported data flags
- **Validation Rules**: All auto-populated data must pass existing ProfileCreation validation before save

---

## US003: Profile Completion Guidance and Verification Workflow

**As a** sales professional with an incomplete TrackRec profile  
**I want** clear guidance on ProfilePage completion and when Verification becomes available  
**So that** I understand the steps to build a credible, complete profile  

### Profile Module Components Referenced:
- **Position**: role, company, startMonth/Year, endMonth/Year (required for verification)
- **PositionDetails**: All fields required for verification eligibility
- **VerificationRequest**: status, approver, positions included
- **UserAccounts**: Completion status and verification eligibility

### Scenarios

**Scenario 1: Completion targeting and visual guidance**
- **Given** I have multiple Position records in various completion states on my ProfilePage
- **When** I view my profile with Position records <90% complete
- **Then** the ProfilePage highlights my most recent incomplete Position with purple highlighting
- **And** completion banner disappears when I have ≥3 Position records with complete PositionDetails

**Scenario 2: Verification eligibility and button appearance**
- **Given** I want to request verification for my work experience
- **When** I have a Position with role + company + dates + complete PositionDetails
- **Then** "Get verified" button appears on the ProfilePage for that specific Position
- **But** verification remains disabled until Position has all required PositionDetails fields

**Scenario 3: Position-specific verification requests**
- **Given** I have multiple Position records and want to request verification
- **When** I click "Get verified" on the ProfilePage
- **Then** I can select which specific Position records to include in the VerificationRequest
- **And** exclude Position records the verifier cannot comment on (different teams, companies)
- **And** VerificationRequest stores selected positions, recipient email, and timestamp

### Acceptance Criteria
- [ ] ProfilePage displays purple highlighting on most recent Position <90% complete
- [ ] "Get verified" button only appears when Position has: role + company + dates + complete PositionDetails
- [ ] Profile completion prompts disappear when UserAccounts has ≥3 complete Position records
- [ ] Verification interface allows selection of specific Position records to include in VerificationRequest
- [ ] ProfilePage "Add Metrics" mode includes cancel/back option returning to normal view
- [ ] VerificationRequest displays who request was sent to, timestamp, and current status
- [ ] ProfileCreation and ProfilePage mark required fields with "*" indicators

### Business Value
- **Profile Quality**: Guided completion creates higher-quality Position and PositionDetails records
- **Verification Trust**: Position-specific VerificationRequest builds credibility with recruiters
- **User Experience**: Clear ProfilePage guidance reduces 25% abandonment during completion

### Implementation Notes
- **Frontend Repository (ProfilePage components)**:
  - Add Position completion percentage calculation based on PositionDetails completeness
  - Create purple highlighting component for incomplete Position records
  - Build Position selection interface for VerificationRequest creation
  - Add cancel/back functionality to "Add Metrics" edit mode
- **Backend Repository**:
  - Calculate Position completion percentage based on required PositionDetails fields
  - Create VerificationRequest table storing recipient, timestamp, status, included positions
  - Implement Position-specific verification logic instead of company-level verification
- **Verification Module**: Track sent vs received VerificationRequest records separately
- **Mobile Optimization**: Ensure ProfilePage completion guidance works on mobile editing flows

---

## US004: Profile Data Persistence and Mobile Optimization

**As a** sales professional using TrackRec on any device  
**I want** my ProfilePage changes to save reliably and display properly on mobile  
**So that** I don't lose work and can manage my profile from anywhere  

### Profile Module Components Referenced:
- **UserAccounts**: All user profile fields requiring reliable persistence
- **Position**: Work experience records with edit/delete operations
- **PositionDetails**: Sales metrics requiring mobile-friendly input
- **System Logging**: Save operation tracking for debugging

### Scenarios

**Scenario 1: Reliable data persistence across sessions**
- **Given** I am entering significant UserAccounts and Position data over multiple sessions
- **When** I input or modify any ProfilePage data (UserAccounts, Position, PositionDetails)
- **Then** the system automatically saves changes to the database without manual save action
- **And** I receive visual confirmation that UserAccounts and Position data persisted successfully
- **And** System logging records save success/failure for debugging

**Scenario 2: Mobile ProfilePage functionality**
- **Given** I am using TrackRec on a mobile device
- **When** I access my ProfilePage with UserAccounts and Position data
- **Then** the layout displays correctly with readable text and functional interactions
- **And** all Position editing, PositionDetails input, and UserAccounts modification work same as desktop

**Scenario 3: Position management with proper controls**
- **Given** I want to manage my Position records on the ProfilePage
- **When** I view each Position with its PositionDetails
- **Then** each Position displays a delete/"X" button with confirmation dialog before removal
- **And** delete button positioning avoids accidental clicks near verification images
- **And** Position deletion removes associated PositionDetails records properly

### Acceptance Criteria
- [ ] UserAccounts, Position, and PositionDetails data persists correctly after entry sessions
- [ ] System logging tracks all save operations for UserAccounts and Position modules
- [ ] ProfilePage renders properly on mobile with responsive layout for all components
- [ ] Mobile users can edit UserAccounts, Position, and PositionDetails same as desktop
- [ ] Each Position record displays delete/"X" button with confirmation before removal
- [ ] Delete buttons positioned away from verification images to prevent accidental Position deletion
- [ ] ProfilePage auto-save provides visual feedback when UserAccounts/Position saves complete
- [ ] All ProfilePage sections (UserAccounts, Position, PositionDetails) save reliably across network conditions

### Business Value
- **User Retention**: Reliable UserAccounts/Position saving prevents 40% frustration-based abandonment
- **Mobile Accessibility**: Mobile ProfilePage optimization captures mobile-first sales professionals (60% of users)
- **Platform Reliability**: Consistent ProfilePage functionality builds trust for B2B platform sales

### Implementation Notes
- **Frontend Repository (ProfilePage components)**:
  - Implement auto-save for UserAccounts, Position, and PositionDetails with visual confirmation
  - Fix mobile responsive layout issues across all ProfilePage components
  - Add delete buttons to Position components with proper spacing from verification elements
  - Create confirmation dialogs for destructive Position/PositionDetails operations
- **Backend Repository**:
  - Add comprehensive logging for all UserAccounts, Position, PositionDetails save operations
  - Implement save validation and error handling for all profile modules
  - Create API endpoints confirming successful UserAccounts/Position data persistence
- **Database Operations**: Ensure Position deletion properly cascades to PositionDetails records
- **Testing Requirements**: 
  - Test ProfilePage saving across all modules under various network conditions
  - Validate mobile ProfilePage functionality on multiple device sizes
  - Verify Position management operations work reliably