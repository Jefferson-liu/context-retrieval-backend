# TrackRec Platform Glossary & Index

## Glossary of Terms

### **A**

**Admin Panel**
User interface for Super Admins to manage platform operations, view coefficients, and perform administrative functions. Referenced in requirements for coefficient display issues and user account deletion capabilities.

**Applicant**
Sales professional user (Role.APPLICANT) who creates profiles and applies for jobs. Primary platform user type seeking new opportunities through TrackRec.

**Apply Button**
Interface element appearing on ProfilePage when candidate has complete experience and came from job posting. Enables job application submission with pre-populated data.

**Authentication**
User login and session management system supporting LinkedIn OAuth (primary/secondary), Google OAuth, and role-based access control with 7-day inactivity expiry.

### **B**

**Business Mix**
Sales performance metric showing distribution across different business types (existing vs new business, inbound vs outbound). Calculated from PositionDetails and displayed in ProfilePage charts.

**BDD (Behavior Driven Development)**
User story format using Given/When/Then scenarios to define system behavior in a way both technical and non-technical stakeholders can understand.

### **C**

**Candidate**
Sales professional using TrackRec to build profiles and apply for jobs. Has authenticated access to view other candidate profiles at networking level (no recruiting intelligence).

**Candidate View State**
Profile visibility level for authenticated sales professionals. Shows complete professional information but hides recruiting-sensitive data like salary expectations and job search status.

**Company**
Database entity storing company information for both candidate work experience and recruiter organizations. Includes name, domain, industry, size, and location fields.

**Completion Banner**
UI element on ProfilePage providing guidance on profile completion. Disappears when user has 3+ complete experiences with metrics to avoid unnecessary prompting.

**Custom Profile URL**
Personalized profile URL using UserAccounts.publicProfileUsername in format trackrec.com/{username}. Must be unique and URL-safe (alphanumeric + hyphens).

### **D**

**DataEnrichment Module**
System component handling AI-powered extraction from resumes and LinkedIn profiles. Processes uploaded documents and OAuth data to auto-populate profile fields during creation.

**Deal Cycle**
Sales metric in PositionDetails showing low, average, and high sales cycle lengths. Referenced in requirements for extending maximum limit beyond current 5-month restriction.

### **E**

**Edit Profile State**
Profile visibility level for profile owners viewing their own profiles. Provides full access to all information plus editing controls and completion guidance.

**Experience Calculation**
System logic counting years of experience from Position records. Includes all positions with title + company + dates, even without complete PositionDetails metrics.

### **G**

**Get Verified Button**
Interface element appearing on ProfilePage when position has complete PositionDetails (role + company + dates + sales metrics). Enables verification request submission.

### **I**

**Industries Worked In**
Profile field in PositionDetails showing business sectors of employer companies. Auto-populated during profile creation through AI analysis of work history.

**Industry Sold To**
Profile field in PositionDetails indicating target customer industries. Auto-populated from client names and companies mentioned in work experience descriptions.

### **J**

**Job Application**
User workflow where candidates with complete profiles submit applications to RecruiterProject postings. Creates ProjectApplication records linking candidates to jobs.

**Job Discovery**
Feature allowing candidates who completed profiles without originating from specific jobs to browse and find available RecruiterProject postings for application.

### **K**

**Keywords**
Database entity storing candidate skills, languages, and nextDesiredTitles. Connected to UserAccounts and populated through profile creation and data enrichment processes.

### **L**

**LinkedIn OAuth**
Primary authentication method for TrackRec users. Includes primary and secondary strategies for profile data extraction and role classification during signup.

**Location Preferences**
UserAccounts field storing candidate desired work locations. Can store up to 3 cities/regions. Used for job matching and recruiter intelligence, pre-populated from resume/LinkedIn data.

### **M**

**Metrics Calculation**
Automated process calculating UserAccounts.metrics from Position and PositionDetails data. Triggers automatically when profile data changes, removing need for manual recalculation.

**MyApplications**
Page displaying candidate's ProjectApplication records with status tracking. Shows job details, company information, and application timeline with empty state for no applications.

### **N**

**Notable Clients**
Confidential client information stored in PositionDetails. Only visible to authenticated recruiters in Recruiter View State to protect sensitive business relationships.

**Next Desired Titles**
UserAccounts field storing target job titles for candidate's next role. Pre-populated from current and previous Position.role values during profile creation.

### **O**

**OTE (On-Target Earnings)**
Salary expectation fields in UserAccounts (oteExpectation, oteMin, oteMax). Used for job matching and recruiter intelligence. Pre-populated in job applications but modifiable per application.

**OpenToWork**
UserAccounts boolean field indicating job search status. Only visible to recruiters in Recruiter View State. Values include "Open to work", "Passively looking", "Not interested".

### **P**

**Position**
Database entity representing individual work experiences. Contains role, company, dates, and relationship to UserAccounts. Required fields for verification eligibility and experience calculation.

**PositionDetails**
Database entity storing detailed sales metrics for Position records. Includes dealSize, salesCycle, channelSplit, segmentSplit, quotaAchievements. Required for verification and complete profile status.

**Profile Completion**
System logic determining profile completeness based on UserAccounts data, Position records, and PositionDetails. Drives UI guidance and feature availability like verification and job application.

**ProfilePage**
Main interface for viewing and editing candidate profiles. Supports multiple visibility states and automatic metrics calculation. Contains experience display, completion guidance, and action buttons.

**ProfileVisibility**
Database entity tracking profile views with viewer information, access level used, and timestamps. Supports analytics and understanding of profile engagement patterns.

**Public Profile State**
Lowest profile visibility level for unauthenticated users. Shows basic professional information while hiding sensitive details. Designed to demonstrate value and drive user authentication.

### **Q**

**Quota Achievements**
Array in PositionDetails storing sales performance by period. Includes quota amounts, achieved amounts, and performance percentages. Used for profile credibility and matching.

### **R**

**Recruiter**
User type (RECRUITER_USER or RECRUITER_ADMIN) who posts jobs and views candidates. Has access to Recruiter View State showing complete candidate information including recruiting intelligence.

**Recruiter View State**
Highest profile visibility level for authenticated recruiters. Shows all candidate information including salary expectations, job search status, and notable clients for hiring decisions.

**RecruiterProject**
Database entity representing job postings created by recruiters. Contains job details, requirements, and matching criteria. Linked to candidates through ProjectApplication records.

**Role Classification**
System logic determining user access level based on Role field (APPLICANT, RECRUITER_USER, RECRUITER_ADMIN, SUPER_ADMIN). Drives profile visibility states and feature access.

### **S**

**Sales Metrics**
Performance data stored in PositionDetails including deal sizes, sales cycles, channel splits, and quota achievements. Essential for profile completion and verification eligibility.

**Session Management**
Authentication system maintaining user login state for 7 days of inactivity across all user types. Session expiry reverts users to unauthenticated access level.

**Super Admin**
Highest privilege user role (SUPER_ADMIN) with platform management capabilities including user deletion, coefficient management, and system oversight functions.

### **U**

**UserAccounts**
Core database entity storing candidate profile information including personal details, preferences, metrics, and settings. Central to all profile operations and relationships.

**User Stories**
BDD-format requirements defining system behavior through Given/When/Then scenarios. Reference specific database modules and business rules for implementation clarity.

### **V**

**Verification**
Peer validation system where candidates request colleagues to verify work experience claims. Only available for positions with complete PositionDetails. Creates VerificationRequest records.

**VerificationRequest**
Database entity managing peer verification workflow. Stores positions being verified, approver information, status, and timeline. Supports position-specific rather than company-level verification.

**Visibility States**
Four-level profile access system: Public (unauthenticated), Candidate (authenticated sales professionals), Recruiter (authenticated recruiters), Edit (profile owners). Determines content filtering rules.

---

## Module Index

### **Profile Module**
**Purpose**: Core candidate profile management  
**Entities**: UserAccounts, Position, PositionDetails, Company, VerificationRequest  
**User Stories**: US001, US002, US003, US004  
**Key Features**: Profile creation, data enrichment, metrics calculation, verification system  

### **Public Profile & Visibility Module**  
**Purpose**: Profile access control and content filtering  
**Entities**: ProfileVisibility  
**Key Features**: Four-state visibility system, role-based content filtering, profile analytics  

---

## User Stories Index

### **US001: Automatic Profile Metrics Calculation**
**Module**: Profile  
**Components**: Position, PositionDetails, UserAccounts.metrics  
**Purpose**: Real-time metrics recalculation on profile changes  
**Business Value**: Reduces friction, encourages profile updates  

### **US002: Profile Data Auto-Population from External Sources**
**Module**: Profile + DataEnrichment  
**Components**: UserAccounts, Position, PositionDetails, Keywords  
**Purpose**: AI-powered profile creation from resume/LinkedIn data  
**Business Value**: Faster onboarding, higher completion rates  

### **US003: Profile Completion Guidance and Verification Workflow**
**Module**: Profile + Verification  
**Components**: Position, PositionDetails, VerificationRequest, UserAccounts  
**Purpose**: Guided profile completion and peer verification system  
**Business Value**: Higher profile quality, verification credibility  

### **US004: Profile Data Persistence and Mobile Optimization**
**Module**: Profile  
**Components**: UserAccounts, Position, PositionDetails  
**Purpose**: Reliable data saving and mobile experience  
**Business Value**: Prevents user frustration, mobile accessibility  

### **US005: Job Application Submission with Pre-populated Data**
**Module**: Profile + JobApplication  
**Components**: UserAccounts, Position, PositionDetails, ProjectApplication, RecruiterProject  
**Purpose**: Streamlined job application with profile data  
**Business Value**: Reduces application abandonment, improves data accuracy  

### **US006: Application Status Tracking and Management**
**Module**: Profile + JobApplication  
**Components**: UserAccounts, ProjectApplication, RecruiterProject, RecruiterCompany  
**Purpose**: Centralized application tracking and status management  
**Business Value**: Candidate engagement, job search management  

### **US007: Job Discovery for Profile Completion Users**
**Module**: Profile + JobApplication  
**Components**: UserAccounts, Position, PositionDetails, RecruiterProject, RecruiterCompany  
**Purpose**: Job browsing for users who didn't come from specific postings  
**Business Value**: Profile utility, platform engagement  

---

## Requirements Index

### **Profile Management Requirements**
- REQ-001: Automatic metrics recalculation (US001)
- REQ-009: Include incomplete positions in calculations (US001, US003)
- REQ-013: Right-hand panels populate with data (US001)
- REQ-034: Reliable profile data saving (US004)
- REQ-033: Mobile profile rendering (US004)
- REQ-035: Comprehensive save testing (US004)

### **Profile Creation & Onboarding Requirements**
- REQ-003: Sales professional completion nudges (US002)
- REQ-015: Pre-populate location from resume/job data (US002)
- REQ-016: Pre-populate desired titles from work history (US002)
- REQ-017: Mark required fields with asterisk (US002, US003)
- REQ-036: Auto-populate industries from LLM analysis (US002)
- REQ-045: Pre-populate about section (US002)
- REQ-046: Pre-populate industry sold to from clients (US002)
- REQ-047: Pre-populate industries from employer data (US002)

### **Profile Completion & Verification Requirements**
- REQ-004: Verification only for complete experiences (US003)
- REQ-011: Show verification status history (US003)
- REQ-020: Fix verification email deliverability (US003)
- REQ-022: Verification status dot actions (US003)
- REQ-027: Position-specific verification requests (US003)
- REQ-028: Differentiate sent vs received verifications (US003)
- REQ-041: Add Metrics mode cancel option (US003, US004)
- REQ-042: Hide completion banner with sufficient experiences (US003)

### **Job Application Requirements**
- REQ-010: Pre-populate application form data (US005)
- REQ-014: MyApplications empty state (US006)
- REQ-048: Apply button for job applicants (US005, US007)
- REQ-049: Job discovery for non-job-posting users (US007)

### **Profile Display & Interface Requirements**
- REQ-018: Work experience delete buttons (US004)
- REQ-023: Delete button positioning (US004)
- REQ-024: Display desired location on public profiles
- REQ-025: Multiple desired locations (US002)
- REQ-026: Fix public profile loading (Public Profile Module)
- REQ-030: Show verifier profile pictures
- REQ-031: Show verified images in edit mode (US003)
- REQ-032: Login page CTA visibility
- REQ-039: User account deletion (US004)
- REQ-040: LinkedIn sync for new experiences (US002)

### **Technical & Infrastructure Requirements**
- REQ-002: 7-day session expiry (Authentication)
- REQ-005: Location-based matching accuracy
- REQ-006: Code quality assessment
- REQ-007: Social sharing message
- REQ-021: Job role classification accuracy (US002)
- REQ-037: Data enrichment module (US002)
- REQ-038: Super admin user deletion
- REQ-043: Admin coefficient display
- REQ-044: Location matching algorithm

---

## Database Entity Reference

### **Core Profile Entities**
- **UserAccounts**: id, email, fullName, profileImage, customCurrentRole, locationPreferences, oteExpectation, oteMin, oteMax, nextDesiredTitles, languages, about, openToWork, blocked, isDeleted, resumeParsedData, metrics, preferenceStep, publicProfileUsername
- **Position**: id, role, startMonth, startYear, endMonth, endYear, isCompleted, user, company
- **PositionDetails**: id, position, dealSize, salesCycle, channelSplit, segmentSplit, notableClients, industry, soldToIndustry, personas, quotaAchievements
- **Company**: id, name, domain, industry, size, location
- **Keywords**: languages, nextDesiredTitles (related to UserAccounts)
- **VerificationRequest**: id, positions, approver, status, requestDate, responseDate, verifierUser, requestedBy

### **Visibility & Analytics Entities**
- **ProfileVisibility**: id, profileOwner, viewer, viewerRole, viewDate, ipAddress, sessionId, visibilityState

### **Job Application Entities**
- **ProjectApplication**: id, user, project, ote, available, status, points, percentage, isSuggested
- **RecruiterProject**: id, title, projectTitle, companyName, logo, experience, oteStart, oteEnd, locationType, description, published, company
- **RecruiterCompany**: id, companyName, logo, stripeCustomerId, subscriptionStatus, recruiters, projects

---

## Feature Status Reference

### **Implemented Features** ✅
- Profile editing and display (ProfilePage)
- Basic authentication system
- LinkedIn OAuth integration
- Resume parsing capabilities
- Verification request system
- Public profile URLs
- Experience tracking and display

### **In Development Features** 🔄
- Automatic metrics calculation (REQ-001)
- Profile completion detection logic (REQ-009)
- Mobile profile optimization (REQ-033)
- Data enrichment improvements (REQ-036, REQ-045-047)

### **Planned Features** 📋
- Job application workflow (US005-007)
- Enhanced verification system (REQ-027, REQ-028)
- Profile analytics and tracking
- Advanced matching algorithms
- Recruiter dashboard functionality

### **Bug Fixes Needed** 🐛
- Right-hand panels not populating (REQ-013)
- Public profiles loading issues (REQ-026)
- Verification email deliverability (REQ-020)
- Mobile profile rendering (REQ-033)
- Profile data saving reliability (REQ-034)
- Admin coefficient display (REQ-043)

---

## Integration Points

### **Authentication Integration**
- LinkedIn OAuth (primary/secondary strategies)
- Google OAuth (recruiter authentication)
- Role-based access control
- Session management (7-day expiry)

### **AI/ML Integration**
- Resume parsing (OpenAI GPT)
- Industry classification
- Data extraction from LinkedIn
- Candidate-job matching algorithms

### **External Services**
- Stripe (payment processing for recruiters)
- Mailgun (email delivery)
- AWS S3 (file storage)
- Google Maps (location services)

### **Platform Analytics**
- Profile view tracking
- User behavior analysis
- Conversion rate monitoring
- Performance metrics calculation

This glossary and index provide comprehensive reference for all TrackRec platform terminology, components, and relationships to support navigation, development, and stakeholder communication.