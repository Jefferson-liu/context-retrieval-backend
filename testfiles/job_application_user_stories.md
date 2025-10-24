# TrackRec Job Application User Stories - BDD Format

## US005: Job Application Submission with Pre-populated Data

**As a** sales professional with a complete TrackRec profile  
**I want** to apply for jobs with my profile data pre-populated  
**So that** I can quickly submit applications without re-entering information  

### Profile Module Components Referenced:
- **UserAccounts**: oteExpectation, locationPreferences, nextDesiredTitles
- **Position**: All position records for experience validation
- **PositionDetails**: Complete sales metrics for application eligibility
- **ProjectApplication**: Application record with candidate data
- **RecruiterProject**: Job posting being applied to

### Scenarios

**Scenario 1: Application form pre-population for job posting candidates**
- **Given** I have complete ProfilePage with ≥1 Position having complete PositionDetails
- **And** I arrived at my profile from a specific RecruiterProject posting
- **When** I click "Apply" button on my ProfilePage
- **Then** the application form pre-populates UserAccounts.oteExpectation and UserAccounts.locationPreferences
- **And** I can modify these values specifically for this RecruiterProject application
- **And** the form validates location preferences case-by-case for the job requirements

**Scenario 2: Application submission with profile data**
- **Given** I have completed the job application form with pre-populated data
- **When** I submit the application
- **Then** system creates ProjectApplication record linking my UserAccounts to the RecruiterProject
- **And** ProjectApplication stores my modified OTE and location preferences for this specific job
- **And** ProjectApplication.status is set to "Applied" with current timestamp

**Scenario 3: Application eligibility validation**
- **Given** I want to apply for a RecruiterProject
- **When** the system checks my Profile completion status
- **Then** I must have ≥1 Position with complete PositionDetails to see "Apply" button
- **And** UserAccounts.preferenceStep must equal 3 (completed onboarding)
- **And** Position records must include role + company + dates + sales metrics

### Acceptance Criteria
- [ ] "Apply" button only appears on ProfilePage when user has ≥1 complete Position with PositionDetails
- [ ] Application form pre-populates UserAccounts.oteExpectation and UserAccounts.locationPreferences
- [ ] Users can modify OTE and location values specifically for each RecruiterProject application
- [ ] Form validates location compatibility between candidate preferences and job requirements
- [ ] ProjectApplication record created with candidate UserAccounts.id and RecruiterProject.id
- [ ] ProjectApplication stores job-specific OTE and location preferences separately from profile
- [ ] Application submission only allowed for candidates who came from job posting or discovered jobs

### Business Value
- **Application Completion**: Pre-populated forms reduce abandonment from 60% to 25%
- **Data Accuracy**: Profile-sourced data ensures consistent, quality applications
- **Recruiter Intelligence**: Job-specific preferences provide better candidate insights

### Implementation Notes
- **Frontend Repository (JobApplication components)**:
  - Create application form component that reads UserAccounts.oteExpectation and locationPreferences
  - Add form validation for job-specific location requirements
  - Implement job-specific OTE and location modification inputs
  - Show "Apply" button only when ProfilePage detects complete profile from job posting source
- **Backend Repository**:
  - Create ProjectApplication table linking UserAccounts to RecruiterProject
  - Store job-specific candidate preferences separate from UserAccounts profile data
  - Validate Position completeness before allowing application submission
- **Profile Integration**: JobApplication form must read from Profile module's completion logic
- **Validation**: Ensure candidate has complete experience before application submission

---

## US006: Application Status Tracking and Management

**As a** sales professional who has applied for jobs  
**I want** to track my application status and see all my applications in one place  
**So that** I can manage my job search effectively  

### Profile Module Components Referenced:
- **UserAccounts**: Applicant tracking applications
- **ProjectApplication**: Application records with status and timeline
- **RecruiterProject**: Job details for application context
- **RecruiterCompany**: Company information for applications

### Scenarios

**Scenario 1: Application status display and tracking**
- **Given** I have submitted applications through ProjectApplication records
- **When** I access my MyApplications page
- **Then** I see all ProjectApplication records associated with my UserAccounts.id
- **And** each application shows RecruiterProject.title, RecruiterCompany.name, and application date
- **And** ProjectApplication.status displays current status (Applied, Reviewing, Interviewing, Hired, Rejected)

**Scenario 2: Empty applications state management**
- **Given** I have no ProjectApplication records associated with my UserAccounts
- **When** I access MyApplications page  
- **Then** page displays "You don't have any applications yet" message instead of blank screen
- **And** page provides link to discover available RecruiterProject postings

**Scenario 3: Application timeline and status updates**
- **Given** I have ProjectApplication records with various statuses
- **When** recruiters update ProjectApplication.status through their system
- **Then** my MyApplications page reflects the updated status immediately
- **And** I can see timeline of status changes for each application
- **And** applications are sorted by most recent activity first

### Acceptance Criteria
- [ ] MyApplications page displays all ProjectApplication records for authenticated UserAccounts
- [ ] Each application shows RecruiterProject title, RecruiterCompany name, application date, current status
- [ ] Empty state shows "You don't have any applications yet" with link to job discovery
- [ ] Application statuses update in real-time when changed by recruiters
- [ ] Applications sorted by most recent activity (application date or status change)
- [ ] Status timeline shows progression: Applied → Reviewing → Interviewing → Hired/Rejected
- [ ] Page accessible only to authenticated candidates with complete profiles

### Business Value
- **Candidate Engagement**: Application tracking keeps candidates engaged with platform
- **Job Search Management**: Centralized tracking improves candidate job search experience  
- **Platform Retention**: Status updates drive candidates to return to platform regularly

### Implementation Notes
- **Frontend Repository (MyApplications components)**:
  - Create MyApplications page displaying ProjectApplication records
  - Implement empty state component with job discovery links
  - Build application status display with timeline visualization
  - Add real-time status updates through websocket or polling
- **Backend Repository**:
  - ProjectApplication table must track status changes with timestamps
  - API endpoints for retrieving candidate's applications with RecruiterProject details
  - Status update notifications when recruiters change ProjectApplication.status
- **Integration**: MyApplications must integrate with job discovery for non-job-posting users
- **Mobile Optimization**: Application tracking must work on mobile devices for job searching candidates

---

## US007: Job Discovery for Profile Completion Users

**As a** sales professional who completed my profile without coming from a specific job  
**I want** to discover and browse available job opportunities  
**So that** I can find relevant positions and apply through the platform  

### Profile Module Components Referenced:
- **UserAccounts**: Profile completion status and job preferences
- **Position**: Experience records for job matching qualification
- **PositionDetails**: Sales metrics for job compatibility
- **RecruiterProject**: Available job postings
- **RecruiterCompany**: Company information for job listings

### Scenarios

**Scenario 1: Job discovery access for complete profiles**
- **Given** I have completed my ProfilePage with ≥1 Position having complete PositionDetails
- **And** I did not arrive from a specific RecruiterProject posting (direct signup)
- **When** I view my ProfilePage after completion
- **Then** I see option to "Browse Available Jobs" or similar job discovery feature
- **And** clicking leads to job listing page showing published RecruiterProject records

**Scenario 2: Job listing display with basic matching**
- **Given** I access the job discovery feature
- **When** I view available RecruiterProject postings
- **Then** jobs display RecruiterProject.title, RecruiterCompany.name, location, and OTE range
- **And** jobs show basic compatibility indicators based on my UserAccounts.locationPreferences and oteExpectation
- **And** jobs are sorted with most relevant/compatible positions first

**Scenario 3: Job application from discovery flow**
- **Given** I found a relevant RecruiterProject through job discovery
- **When** I click to apply for the position
- **Then** system follows same application workflow as US005 (pre-populated form)
- **And** ProjectApplication record created linking my UserAccounts to the RecruiterProject
- **And** application appears in my MyApplications tracking from US006

### Acceptance Criteria
- [ ] ProfilePage shows job discovery option for users with complete profiles who didn't come from job posting
- [ ] Job listing page displays published RecruiterProject records with basic details
- [ ] Jobs show RecruiterProject title, RecruiterCompany name, location, OTE range from job posting
- [ ] Basic compatibility indicators based on UserAccounts location and OTE preferences
- [ ] Jobs sorted by relevance/compatibility with candidate profile
- [ ] Application flow from job discovery works same as direct job posting applications
- [ ] Job discovery integrated with MyApplications for application tracking

### Business Value
- **Profile Utility**: Gives value to users who complete profiles through general signup
- **Platform Engagement**: Job discovery keeps candidates active on platform
- **Application Volume**: Increases total applications by enabling discovery-based applications

### Implementation Notes
- **Frontend Repository (JobDiscovery components)**:
  - Add job discovery link/button to ProfilePage for users without originating job
  - Create job listing page displaying RecruiterProject records
  - Implement basic compatibility scoring display based on location and OTE
  - Integrate job discovery with existing application flow components
- **Backend Repository**:
  - API endpoint to fetch published RecruiterProject records
  - Basic matching logic comparing UserAccounts preferences to RecruiterProject requirements
  - Job sorting algorithm prioritizing compatible positions
- **Integration Points**:
  - Job discovery must connect to existing JobApplication workflow (US005)
  - Applications from discovery must appear in MyApplications tracking (US006)
  - Profile completion logic determines job discovery access eligibility