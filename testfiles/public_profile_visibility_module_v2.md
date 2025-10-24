# TrackRec Public Profile & Visibility Module Specification

## Module Overview
The Public Profile & Visibility module manages profile access control and content filtering. It implements a four-state visibility system based on user authentication status and role, balancing candidate privacy with platform growth objectives.

---

## Profile Visibility States

### State 1: Public Profile (Unauthenticated Users)
**Purpose**: Drive user registration by showing profile value while protecting sensitive data  
**Access Level**: Basic professional information only  

**Content Visible**:
- UserAccounts.fullName (complete)
- UserAccounts.customCurrentRole (complete)
- Current Position.company name (company name only, no logo)
- Calculated total experience years (from Position records)
- UserAccounts.locationPreferences (primary location)
- UserAccounts.languages (spoken languages)
- UserAccounts.profileImage (if available)
- UserAccounts.about (first 50 characters + "..." if longer)
- Position records (role, company name, dates only - no PositionDetails)
- Generic achievements ("Exceeded quota", "Top performer" - no specific numbers)
- High-level business mix overview ("Enterprise-focused", "Inbound sales" - no percentages)

**Content Hidden/Blurred**:
- Specific PositionDetails (deal sizes, quotas, metrics)
- UserAccounts.oteExpectation, oteMin, oteMax
- PositionDetails.notableClients
- Complete UserAccounts.about text
- Detailed UserAccounts.metrics calculations
- Contact information
- UserAccounts.nextDesiredTitles
- Verification details and verifier information

### State 2: Candidate View (Authenticated Sales Professionals)
**Purpose**: Professional networking level access  
**Access Level**: Complete professional information, no recruiting intelligence  

**Content Visible** (Everything from Public + ):
- Complete UserAccounts.about section
- Full PositionDetails (deal sizes, sales cycles, achievements with numbers)
- Detailed UserAccounts.metrics (business mix charts with percentages)
- PositionDetails.industry, soldToIndustry
- UserAccounts.languages, skills from Keywords
- VerificationRequest status and verifier profile pictures
- Complete Position histories with detailed descriptions

**Content Still Hidden**:
- UserAccounts.oteExpectation, oteMin, oteMax (salary expectations)
- UserAccounts.nextDesiredTitles (job search intentions)
- UserAccounts.openToWork status
- PositionDetails.notableClients (confidential client information)
- Direct contact information

### State 3: Recruiter View (Authenticated Recruiters)
**Purpose**: Complete recruiting intelligence for hiring decisions  
**Access Level**: All professional and recruiting-sensitive information  

**Content Visible** (Everything from Candidate View + ):
- UserAccounts.openToWork status ("Open to work", "Passively looking", "Not interested")
- UserAccounts.oteExpectation, oteMin, oteMax (salary expectations and ranges)
- UserAccounts.nextDesiredTitles (target job titles and seniority levels)
- UserAccounts.locationPreferences (complete - willing to relocate, remote preferences)
- PositionDetails.notableClients (confidential client information)
- Advanced UserAccounts.metrics (deal cycles, sales methodology preferences)

**Content Still Hidden**:
- Direct contact information until contact is established

### State 4: Edit Profile (Profile Owner)
**Purpose**: Complete profile management and editing  
**Access Level**: Full access with edit controls  

**Content Visible**:
- Everything from all other states
- Edit controls on all sections
- Profile completion guidance
- Account management options

---

## Database Entities

### ProfileVisibility
**Purpose**: Track profile view permissions and access logs  
**Primary Key**: `id`

| Field | Type | Validation | Default | Description |
|-------|------|------------|---------|-------------|
| id | String (UUID) | Required, Unique | Auto-generated | Primary identifier |
| profileOwner | UserAccounts.id | Required, Foreign Key | - | Profile being viewed |
| viewer | UserAccounts.id | Optional, Foreign Key | null | Authenticated viewer (null = anonymous) |
| viewerRole | Enum | Required | ANONYMOUS | ANONYMOUS, CANDIDATE, RECRUITER, OWNER |
| viewDate | DateTime | Required | Auto-set | When profile was accessed |
| ipAddress | String | Required | - | Viewer IP for analytics |
| sessionId | String | Required | - | Session tracking |
| visibilityState | Enum | Required | - | PUBLIC, CANDIDATE, RECRUITER, EDIT |

**Business Rules**:
- Anonymous viewers always get PUBLIC state
- Profile owner always gets EDIT state
- Authenticated users get CANDIDATE or RECRUITER based on user type
- Track all profile views for analytics and candidate insights

---

## Content Filtering Logic

### Role-Based Content Filtering

**Step 1: Determine Viewer Role**
- IF viewer is profile owner → OWNER role
- ELSE IF viewer is unauthenticated → ANONYMOUS role  
- ELSE IF viewer has recruiter role → RECRUITER role
- ELSE IF viewer is authenticated candidate → CANDIDATE role

**Step 2: Apply Visibility State**
- OWNER role → EDIT state (full access + edit controls)
- RECRUITER role → RECRUITER state (all data including recruiting intelligence)
- CANDIDATE role → CANDIDATE state (professional info, no recruiting data)
- ANONYMOUS role → PUBLIC state (basic info only)

**Step 3: Filter Profile Content**
- Load complete UserAccounts, Position, PositionDetails records
- Apply content filters based on determined visibility state
- Return filtered profile data appropriate for viewer role

### Content Filtering Rules

**Public Profile Content Filtering**:
- Show UserAccounts basic fields (fullName, customCurrentRole, profileImage, locationPreferences[0])
- Show UserAccounts.about truncated to 50 characters
- Show Position records with only (role, company.name, startYear, endYear)
- Hide all PositionDetails
- Hide all sensitive UserAccounts fields (OTE, nextDesiredTitles, openToWork)

**Candidate View Content Filtering**:
- Show all content from Public Profile
- Add complete UserAccounts.about
- Add all PositionDetails EXCEPT notableClients
- Add complete UserAccounts.metrics
- Add VerificationRequest information
- Continue hiding salary and job search related fields

**Recruiter View Content Filtering**:
- Show all content from Candidate View  
- Add UserAccounts recruiting fields (oteExpectation, oteMin, oteMax, nextDesiredTitles, openToWork)
- Add complete UserAccounts.locationPreferences array
- Add PositionDetails.notableClients
- Continue hiding direct contact information

---

## Profile URL Structure

### Public Profile URLs
- **Custom Username Format**: `trackrec.com/{publicProfileUsername}`
- **Fallback ID Format**: `trackrec.com/profile/{userId}`
- **Username Validation**: UserAccounts.publicProfileUsername must be URL-safe (alphanumeric + hyphens)
- **Uniqueness**: UserAccounts.publicProfileUsername enforced unique at database level

### Profile Access Patterns
- Anonymous users accessing any profile URL → Public Profile state
- Authenticated users accessing others' profiles → Candidate or Recruiter state based on role
- Users accessing their own profile → Edit Profile state
- All profile access logged in ProfileVisibility table

---

## Authentication Integration

### User Role Classification
**Based on UserAccounts.role field**:
- `Role.APPLICANT` → Candidate authentication level
- `Role.RECRUITER_USER` → Recruiter authentication level  
- `Role.RECRUITER_ADMIN` → Recruiter authentication level
- `Role.SUPER_ADMIN` → Administrative access (separate from profile viewing)

### Session-Based Access Control
- Unauthenticated sessions → Public Profile access only
- Authenticated sessions → Role-appropriate profile access
- Profile owner sessions → Edit Profile access to own profile
- Session expiry (7 days inactivity) reverts to Public Profile access

---

## Profile Analytics & Tracking

### ProfileVisibility Analytics
**Track for each profile view**:
- ProfileVisibility.profileOwner (whose profile was viewed)
- ProfileVisibility.viewer (who viewed it, if authenticated)
- ProfileVisibility.viewerRole (access level used)
- ProfileVisibility.viewDate (when accessed)
- ProfileVisibility.visibilityState (what content level was shown)

**Analytics Calculations**:
- Total profile views per candidate
- Breakdown by viewer type (anonymous, candidate, recruiter)
- Authentication conversion rate (anonymous viewers who later authenticate)
- Profile engagement patterns

### View Tracking Business Rules
- Every profile access creates ProfileVisibility record
- Anonymous viewers tracked by session, not individual identity
- Profile owners can see analytics for their own profiles
- Aggregate analytics available for platform insights

---

## Frontend Components

### Profile Display Components
- `PublicProfileLayout` - Main profile container with state-aware content rendering
- `ProfileHeader` - Name, role, company with appropriate detail level per state
- `ExperienceSection` - Work history with content filtering based on viewer role
- `AuthenticationPrompt` - "Sign in to view full profile" for anonymous users
- `ProfileMetrics` - Charts and performance data with visibility-appropriate detail

### Profile Management Components  
- `EditProfileLayout` - Complete profile editing interface (owner only)
- `ProfileCompletionBanner` - Completion guidance and progress indicators
- `VerificationSection` - Verification status and request management
- `PrivacyControls` - Profile visibility and privacy settings

### Authentication Integration Components
- `ProfileAuthGuard` - Route protection and role-based content serving
- `VisibilityStateProvider` - Context provider for current user's access level
- `ConditionalContent` - Component for showing/hiding content based on visibility state

---

## Integration Points

### Profile Module Dependencies
- **UserAccounts**: Core profile data and preferences
- **Position**: Work experience records
- **PositionDetails**: Sales metrics and performance data  
- **VerificationRequest**: Peer verification information
- **Keywords**: Skills and preferences data

### Authentication Module Dependencies
- **User Role Detection**: Determines CANDIDATE vs RECRUITER access levels
- **Session Management**: 7-day inactivity expiry affects profile access
- **OAuth Integration**: LinkedIn/Google authentication for role classification

### Analytics Integration
- **ProfileVisibility**: All profile views tracked for analytics
- **User Behavior**: Profile view patterns inform product decisions
- **Conversion Tracking**: Anonymous to authenticated user conversion rates

This module provides the foundation for role-based profile access while supporting platform growth through progressive content disclosure and user authentication incentives.