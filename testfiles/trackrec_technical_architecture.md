# TrackRec Technical Architecture & User Management

## Technical Architecture Overview

### Core Technology Stack

#### **Frontend Framework**
- **Next.js 14.1.0** (App Router) - React-based full-stack framework
- **React 18** with modern hooks and functional components
- **TypeScript** configured but mostly using JavaScript files
- **Repository**: Separate frontend repository

#### **Backend Framework**
- **NestJS** (Node.js) with TypeScript
- **Database**: MySQL with TypeORM as ORM
- **Architecture**: Modular design with feature-based modules
- **Repository**: Separate backend repository

#### **State Management & UI**
- **Redux Toolkit** with RTK Query for API state management
- **React Redux** for component state binding
- **Tailwind CSS** for utility-first styling
- **Material-UI (MUI)** components for complex UI elements

### Database & Data Management

#### **Primary Database**
- **MySQL** as main data store
- **TypeORM** for database operations and migrations
- **Repository Pattern** for data access layer abstraction
- **Schema**: User profiles, positions, companies, applications, verification system

#### **File Storage**
- **AWS S3** for resume uploads and profile images
- **CDN Support** for optimized file delivery
- **Security**: Secure file access controls and permissions

### Authentication & Security

#### **Authentication Methods**
- **LinkedIn OAuth** (Primary Strategy) - Main authentication for sales professionals
- **LinkedIn OAuth** (Secondary Strategy) - Alternative LinkedIn authentication flow
- **Google OAuth** - Recruiter authentication and profile data extraction
- **Passport.js** with JWT tokens for session management

#### **Authorization System**
- **Role-Based Access Control** with guards and decorators
- **Session Management**: 7-day inactivity expiry across all user types
- **Multi-Token System**: Different tokens for different user types (candidates, recruiters, admins)

### External Integrations

#### **AI & Data Processing**
- **OpenAI GPT** for resume parsing and data extraction
- **LinkedIn API** for profile data import and synchronization
- **AI Services**: Candidate matching algorithms and industry classification

#### **Communication & Payments**
- **Mailgun** for transactional emails and notifications
- **Stripe** for subscription management and payment processing
- **Email Templates**: HTML email system for user communications

#### **Location & Analytics**
- **Google Maps API** for address validation and location services
- **Sentry** for error tracking and performance monitoring
- **Winston** for structured application logging
- **Hotjar** for user analytics and behavior tracking

### Development & Deployment

#### **Code Quality & Standards**
- **TypeScript** for type safety and modern JavaScript features
- **ESLint** for code linting and style enforcement
- **Prettier** for consistent code formatting
- **Zod Schemas** for comprehensive input validation

#### **Performance & Scalability**
- **Rate Limiting** (NestJS Throttler) for API abuse prevention
- **Caching Strategy** for frequently accessed data
- **Database Optimization** with indexed queries and efficient relationships
- **Load Balancing** capabilities for horizontal scaling

#### **Monitoring & Error Handling**
- **Sentry Integration** for real-time error monitoring and performance tracking
- **Winston Logger** for structured logging with correlation IDs
- **Health Checks** for system monitoring and uptime tracking

---

## User Types & Roles

### Database Role Definitions

#### **Role.APPLICANT** 
**Purpose**: Sales professionals seeking new opportunities  
**Database Role**: Primary platform user type  
**Capabilities**:
- Create and manage professional profiles
- Upload resumes and import LinkedIn data
- Apply to job postings
- Request peer verification for work experience
- View other candidate profiles (networking level)
- Set preferences for next role (OTE, location, work type)

#### **Role.RECRUITER_USER**
**Purpose**: Team members within recruiter companies  
**Database Role**: Limited recruiter permissions  
**Capabilities**:
- View job postings within their company scope
- Access candidate profiles with recruiting intelligence
- Review applications and candidate pipeline
- Limited permissions within company boundaries
- Cannot create jobs or manage company settings

#### **Role.RECRUITER_ADMIN** 
**Purpose**: Company owners and administrators  
**Database Role**: Full recruiter permissions  
**Capabilities**:
- Create and manage job postings
- Full access to company data and candidate intelligence
- Manage team members and permissions
- Handle payment and subscription management
- Configure matching criteria and job requirements
- Access analytics and performance data

#### **Role.SUPER_ADMIN**
**Purpose**: Platform administrators  
**Database Role**: System-wide access  
**Capabilities**:
- Impersonate any user type for support
- Manage all platform data and configurations
- Access system-wide analytics and performance metrics
- Delete user accounts and manage platform operations
- Configure matching coefficients and system parameters

---

## User Authentication & Session Management

### Authentication Flows

#### **Candidate Authentication (LinkedIn OAuth)**
1. **Primary LinkedIn Strategy**: Main authentication path for sales professionals
2. **Profile Data Import**: Automatic extraction of work experience and professional information
3. **Role Classification**: Automatic assignment to Role.APPLICANT based on profile analysis
4. **Session Creation**: 7-day inactivity timeout with automatic renewal on activity

#### **Recruiter Authentication (LinkedIn/Google OAuth)**
1. **LinkedIn Job Title Analysis**: System analyzes job titles for recruiter identification
2. **Google OAuth Alternative**: Backup authentication method for recruiters
3. **Company Association**: Link recruiters to RecruiterCompany entities
4. **Role Assignment**: RECRUITER_USER or RECRUITER_ADMIN based on company permissions

#### **Admin Authentication**
1. **Elevated Permissions**: Super admin access for platform management
2. **Impersonation Capabilities**: Ability to view platform from any user perspective
3. **System Access**: Full platform configuration and user management capabilities

### Session & Token Management

#### **Multi-Token System**
- **auth_token**: Sales professionals (localStorage)
- **recruiterToken**: Recruiters (localStorage)  
- **adminDashboardToken**: Administrators (localStorage)

#### **Session Security**
- **JWT Token Security**: Secure token generation and validation
- **7-Day Expiry**: Automatic logout after inactivity period
- **Cross-Site Protection**: CSRF prevention and secure session handling
- **Token Refresh**: Automatic renewal on user activity

---

## User Goals & Platform Objectives

### Candidate (Role.APPLICANT) Goals

#### **Primary Objectives**
- **Profile Creation**: Build comprehensive professional profile showcasing sales experience
- **Job Discovery**: Find relevant sales opportunities matching experience and preferences
- **Application Management**: Apply for positions and track application status
- **Career Advancement**: Leverage platform for next career opportunity

#### **Platform Support**
- **Data Enrichment**: AI-powered profile creation from resume/LinkedIn data
- **Profile Intelligence**: Sophisticated metrics calculation and performance visualization
- **Verification System**: Peer validation for work experience credibility
- **Job Matching**: AI-powered recommendation system for relevant opportunities

### Recruiter Goals (RECRUITER_USER/RECRUITER_ADMIN)

#### **Primary Objectives**
- **Candidate Discovery**: Access to high-quality sales professional database
- **Hiring Efficiency**: Streamlined recruitment workflow and candidate evaluation
- **Intelligence Access**: Detailed candidate performance data and recruiting insights
- **Pipeline Management**: Organized candidate pipeline and application tracking

#### **Platform Support**
- **Job Posting System**: Create detailed sales-specific job requirements
- **Matching Algorithm**: AI-powered candidate recommendations with percentage scoring
- **Recruiting Intelligence**: Access to salary expectations, job search status, notable clients
- **Analytics Dashboard**: Hiring performance metrics and candidate engagement data

### Platform-Level Goals

#### **Business Objectives**
- **User Growth**: Attract A-player sales professionals and active recruiters
- **Platform Quality**: High-quality matches between candidates and opportunities  
- **Engagement**: Active user participation in profile completion and applications
- **Validation**: Prove platform effectiveness through internal recruitment success

#### **Technical Objectives**
- **Scalability**: Support growing user base and increasing platform usage
- **Reliability**: High uptime and consistent performance for business-critical operations
- **Security**: Protect sensitive professional and recruiting intelligence data
- **Integration**: Seamless connection with external services and data sources

#### **Product Objectives**
- **Feature Completeness**: Comprehensive recruitment platform capabilities
- **User Experience**: Intuitive interfaces for all user types and workflows
- **Data Intelligence**: Sophisticated analytics and insights for recruitment decisions
- **Market Readiness**: Platform prepared for B2B sales to other organizations

---

## Architecture Constraints & Considerations

### Development Constraints
- **Two-Repository Structure**: Frontend and backend development coordination required
- **Offshore Development Team**: Clear specifications and documentation essential
- **Existing Architecture**: Preserve current structure unless changes are critical
- **Mobile Responsiveness**: Significant recruiter mobile usage requires mobile optimization

### Performance Requirements
- **Real-Time Matching**: Candidate-job matching must be responsive for user experience
- **Large Database Queries**: Efficient handling of growing candidate and job databases
- **File Processing**: Resume parsing and image handling without performance impact
- **Concurrent Users**: Support multiple recruiters and candidates using platform simultaneously

### Security & Privacy Requirements
- **Professional Data Protection**: Secure handling of sensitive career and salary information
- **Recruiting Intelligence**: Protect confidential client and performance data
- **Authentication Security**: Multi-role authentication with appropriate access controls
- **Data Compliance**: Professional data handling meeting privacy and business requirements