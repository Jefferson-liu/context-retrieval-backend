# TrackRec Profile User Stories

## US001: Automatic Profile Metrics Calculation

**As a** sales professional creating or editing my TrackRec profile  
**I want** my performance metrics to automatically recalculate whenever I change any data  
**So that** I see real-time updates and don't need to manually trigger calculations  

### Scenarios

**Scenario 1: Real-time calculation during profile editing**
- **Given** I am editing my profile on the ProfilePage
- **When** I update any sales metrics, work experience, or achievement data
- **Then** all dependent metrics (business mix, source, segment, TRG) recalculate automatically
- **And** the right-hand panel charts update immediately without page refresh

**Scenario 2: Incomplete data handling**
- **Given** I have some positions with missing sales metrics
- **When** the system calculates my overall performance metrics
- **Then** missing fields are treated as excluded from calculations (not as zero values)
- **And** my years of experience includes all positions with title + company + dates

### Acceptance Criteria
- [ ] Remove existing manual "recalculate" button entirely from ProfilePage
- [ ] Business mix, source, product type, segment, and TRG charts populate after entering sales metrics for at least one position
- [ ] Calculations trigger on any profile data change (experience, metrics, preferences)
- [ ] System counts years from all positions with title + company + dates, even without complete sales metrics
- [ ] Mobile users experience same real-time calculation functionality
- [ ] No loading spinners or delays - calculations appear instantaneous to user

### Business Value
- **Candidate Attraction**: Eliminates friction that prevents profile completion
- **Platform Quality**: Real-time feedback encourages accurate, complete profiles
- **B2B Selling Point**: Demonstrates sophisticated platform capabilities to future clients

### Implementation Notes
- **Frontend Repository**: 
  - Remove manual recalculate button from ProfilePage component
  - Add React hooks to trigger calculations on form state changes
  - Update chart components to re-render on data updates
  - Ensure mobile responsive charts update properly
- **Backend Repository**: 
  - Create calculation service that processes profile data changes
  - Handle incomplete position data by excluding (not zeroing) missing metrics
  - Return structured data for business mix, source, segment, TRG visualizations
- **Integration**: Frontend triggers backend calculation API on any profile change
- **Testing**: Verify calculations work across incomplete profiles, mobile devices, and various data combinations

---

## US002: Profile Data Auto-Population from External Sources

**As a** sales professional creating my TrackRec profile  
**I want** the ProfileCreation module to automatically populate from my resume and LinkedIn data  
**So that** I spend less time on manual data entry and have a complete profile faster  

### Profile Module Components Referenced:
- **UserAccounts**: fullName, about, locationPreferences, resumeParsedData
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
- **When** the LinkedIn API extraction completes
- **Then** UserAccounts.fullName and UserAccounts.about populate from LinkedIn profile data
- **And** Position records auto-create with role, company, startMonth/Year, endMonth/Year from LinkedIn experience
- **And** Keywords.nextDesiredTitles suggests based on current Position.role and previous Position.role values

**Scenario 3: Location and preferences extraction**
- **Given** my resume contains location information OR LinkedIn profile has location data
- **When** the DataEnrichment module processes the location data
- **Then** UserAccounts.locationPreferences populates with extracted city/state information
- **And** UserAccounts.oteExpectation pre-fills if salary information is detected in resume

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
**I want** clear guidance on what to complete and when verification becomes available  
**So that** I understand the steps to build a credible, complete profile  

### Scenarios

**Scenario 1: Completion targeting and guidance**
- **Given** I have multiple work experiences in various completion states
- **When** I view my ProfilePage
- **Then** the system highlights my most recent job that is less than 90% complete with purple highlighting
- **And** completion banner disappears when I have 3 or more complete experiences with metrics

**Scenario 2: Verification availability**
- **Given** I want to get my experience verified
- **When** I have a position with job title + company + dates + sales metrics filled
- **Then** "Get verified" button appears for that specific experience
- **But** verification remains disabled until I have complete experience data

**Scenario 3: Position-specific verification requests**
- **Given** I have multiple positions and want to request verification
- **When** I click to send a verification request
- **Then** I can select which specific positions to include in the request
- **And** exclude roles the verifier cannot comment on (different teams, companies)

### Acceptance Criteria
- [ ] Purple highlighter appears on most recent job <90% complete to guide user attention
- [ ] "Get verified" button only appears when position has: job title + company + dates + sales metrics
- [ ] Profile completion prompts disappear when user has 3+ complete experiences with metrics
- [ ] Verification requests allow selection of specific positions to include
- [ ] Users can exit "Add Metrics" edit mode without making changes (cancel/back option)
- [ ] Verification status shows who request was sent to, when sent, and current status
- [ ] Required fields marked with "*" so users understand expectations

### Business Value
- **Profile Quality**: Guided completion creates higher-quality, more credible profiles
- **Verification System**: Position-specific verification builds trust with recruiters
- **User Experience**: Clear guidance reduces abandonment during profile creation

### Implementation Notes
- **Frontend Repository**:
  - Add completion percentage calculation for each position
  - Create purple highlighting component for incomplete positions
  - Build position selection interface for verification requests
  - Add cancel/back functionality to "Add Metrics" mode
  - Mark required fields with asterisk indicators
- **Backend Repository**:
  - Calculate completion percentage based on required fields per position
  - Store verification request details (recipient, timestamp, status)
  - Handle position-specific verification rather than company-level
- **Verification Module**: Track sent vs received verification requests separately
- **Mobile Optimization**: Ensure completion guidance works on mobile profile editing

---

## US004: Profile Data Persistence and Mobile Optimization

**As a** sales professional using TrackRec on any device  
**I want** my profile changes to save reliably and display properly on mobile  
**So that** I don't lose work and can manage my profile from anywhere  

### Scenarios

**Scenario 1: Reliable data saving**
- **Given** I am entering significant profile information over multiple sessions
- **When** I input or modify profile data on any section
- **Then** the system automatically saves changes without manual save action
- **And** I receive confirmation that data persisted successfully

**Scenario 2: Mobile profile management**
- **Given** I am using TrackRec on a mobile device
- **When** I access my ProfilePage
- **Then** the layout displays correctly with readable text and functional interactions
- **And** all profile editing features work the same as desktop version

**Scenario 3: Work experience management**
- **Given** I want to manage my work experiences
- **When** I view each experience on my profile
- **Then** each experience shows a delete or "X" button with confirmation dialog
- **And** I can add, edit, or remove experiences without accessing separate "add metric" flows

### Acceptance Criteria
- [ ] Profile information persists correctly after data entry sessions across all sections
- [ ] System includes logging to track save success/failure for debugging
- [ ] ProfilePage renders properly on mobile screens with responsive layout
- [ ] Text remains readable and interactions functional on mobile devices
- [ ] Each work experience displays delete/"X" button with confirmation before removal
- [ ] Delete button positioned away from verification images to prevent accidental clicks
- [ ] All profile sections (experience, metrics, preferences) save reliably
- [ ] Users receive visual feedback when saves complete successfully

### Business Value
- **User Retention**: Reliable saving prevents user frustration and abandonment
- **Mobile Accessibility**: Mobile optimization captures mobile-first sales professionals
- **Platform Reliability**: Consistent functionality builds trust for B2B sales

### Implementation Notes
- **Frontend Repository**:
  - Implement auto-save functionality with visual confirmation
  - Fix mobile responsive layout issues on ProfilePage
  - Add delete buttons to work experience components with proper positioning
  - Create confirmation dialogs for destructive actions
- **Backend Repository**:
  - Add comprehensive logging for all save operations
  - Implement save validation and error handling
  - Create API endpoints that confirm successful data persistence
- **Testing Requirements**:
  - Comprehensive testing across all profile sections
  - Mobile device testing on various screen sizes
  - Save functionality validation under different network conditions
- **Error Handling**: Clear error messages when saves fail, with retry options