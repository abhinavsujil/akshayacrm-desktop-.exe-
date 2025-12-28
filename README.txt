================================================================================
                            AKSHAYA ADMIN CRM
                Customer Relationship Management System
================================================================================

A comprehensive desktop application for managing customer service records 
at Akshaya Centers (common service centers in Kerala, India).

Built with: Python 3.10+ | PyQt6 | Supabase (PostgreSQL)

--------------------------------------------------------------------------------
                               OVERVIEW
--------------------------------------------------------------------------------

Akshaya Admin CRM is a full-featured desktop application designed for managing 
customer service records. The system streamlines daily operations by providing 
separate interfaces for Staff and Admin users, with real-time data 
synchronization, bilingual support (English/Malayalam), and comprehensive 
service tracking.

PROBLEM SOLVED:
Traditional paper-based logging at service centers leads to:
  - Lost records and billing disputes
  - No real-time visibility for management
  - Manual service verification bottlenecks
  - Difficulty tracking staff performance

This CRM digitizes the entire workflow, providing instant access to records, 
automated billing calculations, and administrative oversight.

--------------------------------------------------------------------------------
                               FEATURES
--------------------------------------------------------------------------------

STAFF PORTAL:
  * Customer Logging      - Quick entry of customer details with auto-complete
  * Smart Suggestions     - Fuzzy-matching algorithm suggests services as you type
  * Auto-billing          - Base amount + service charge with auto total
  * Document Requirements - View/add required documents for each service
  * Multi-language        - Full Malayalam translation support
  * Recent Work View      - Quick access to recent customer logs
  * Search Records        - Advanced search across all logged records

ADMIN PORTAL:
  * Dashboard Analytics   - Real-time stats: logs, pending, revenue
  * Service Verification  - Approve/reject pending services from staff
  * Staff Management      - Add, edit, deactivate staff accounts
  * Admin Management      - Multi-admin support with role-based access
  * View All Logs         - Comprehensive log viewer with filters
  * Service Suggestions   - Review and approve new services from staff

TECHNICAL FEATURES:
  * Real-time Sync        - Cloud-based PostgreSQL via Supabase REST API
  * Offline Resilience    - Retry logic with exponential backoff
  * Responsive UI         - Adaptive layouts for different screen sizes
  * Session Management    - Secure staff/admin authentication
  * Logging Engine        - AI-powered logging for debugging

--------------------------------------------------------------------------------
                             TECH STACK
--------------------------------------------------------------------------------

  Layer          Technology
  -----------    ----------------------------------
  Frontend       PyQt6 (Python GUI Framework)
  Backend        Supabase (PostgreSQL + REST API)
  Language       Python 3.10+
  Styling        Custom QSS (Qt Style Sheets)
  Build Tool     PyInstaller (Windows .exe)
  i18n           Custom JSON-based translator

--------------------------------------------------------------------------------
                            ARCHITECTURE
--------------------------------------------------------------------------------

+------------------------------------------------------------------+
|                      PRESENTATION LAYER                          |
+-------------------------------+----------------------------------+
|        Staff Panel            |          Admin Panel             |
|  - Customer Entry             |  - Dashboard & Analytics         |
|  - Service Logging            |  - Service Verification          |
|  - Document Viewer            |  - Staff/Admin Management        |
|  - Search & Print             |  - Log Viewer & Export           |
+-------------------------------+----------------------------------+
|                      DATA ACCESS LAYER                           |
|  supabase_utils.py                                               |
|  - RESTful CRUD operations                                       |
|  - Retry logic with backoff                                      |
|  - Data normalization & validation                               |
+------------------------------------------------------------------+
|                       CLOUD BACKEND                              |
|  Supabase (PostgreSQL)                                           |
|  Tables: logs, services, payments, staff, admins,                |
|          service_suggestions, service_documents                  |
+------------------------------------------------------------------+

--------------------------------------------------------------------------------
                          PROJECT STRUCTURE
--------------------------------------------------------------------------------

Akshaya-Software/
|
|-- main.py                    Application entry point with role selection
|-- supabase_utils.py          Database operations & API wrapper (770+ lines)
|-- requirements.txt           Python dependencies
|
|-- gui/                       User Interface Components
|   |-- staff_panel.py         Staff login & navigation
|   |-- staff_dashboard.py     Main staff interface (1200+ lines)
|   |-- search_dialog.py       Advanced search functionality
|   |-- recent_work.py         Recent logs viewer
|   |-- add_required_documents.py
|   |-- view_required_documents.py
|   |
|   +-- admin_panel/           Admin-specific components
|       |-- admin_login.py     Admin authentication
|       |-- admin_dashboard.py Admin main interface
|       |-- verify_services.py Service approval workflow
|       |-- manage_staff.py    Staff CRUD operations
|       |-- manage_admins.py   Admin management
|       +-- view_logs.py       Comprehensive log viewer
|
|-- language/                  Internationalization
|   |-- translator.py          Translation engine
|   |-- english.json           English strings
|   +-- malayalam.json         Malayalam translations
|
|-- core/                      Core utilities
|   |-- firestore_helper.py    Legacy Firebase support
|   +-- logger.py              Logging utilities
|
|-- assets/                    Static assets (icons, images)
|-- services/                  Service configurations
+-- version.txt                Windows version resource

--------------------------------------------------------------------------------
                            INSTALLATION
--------------------------------------------------------------------------------

PREREQUISITES:
  - Python 3.10 or higher
  - pip (Python package manager)

SETUP STEPS:

1. Clone the repository
   git clone https://github.com/yourusername/Akshaya-Software.git
   cd Akshaya-Software

2. Create virtual environment
   python -m venv .venv
   .venv\Scripts\activate       (Windows)
   source .venv/bin/activate    (macOS/Linux)

3. Install dependencies
   pip install -r requirements.txt

4. Run the application
   python main.py

BUILDING EXECUTABLE (Windows):
   pyinstaller --onefile --windowed --name AkshayaAdminCRM main.py
   
   The executable will be created in the dist/ folder.

--------------------------------------------------------------------------------
                          DATABASE SCHEMA
--------------------------------------------------------------------------------

  Table                  Description
  --------------------   --------------------------------------------
  logs                   Customer visit records with timestamps
  services               Services linked to each log entry
  payments               Payment records with base/charge breakdown
  staff                  Staff account information
  admins                 Admin credentials and permissions
  service_suggestions    Pending service approvals
  service_documents      Required documents per service

--------------------------------------------------------------------------------
                          UI/UX HIGHLIGHTS
--------------------------------------------------------------------------------

  * Modern Glassmorphism Design - Clean, professional interface
  * Sidebar Navigation          - Intuitive menu with icons
  * Responsive Cards            - Content adapts to window size
  * Color-coded Status          - Visual indicators for status
  * Dark Sidebar + Light Content - Balanced contrast for extended use

--------------------------------------------------------------------------------
                            KEY METRICS
--------------------------------------------------------------------------------

  Metric                   Value
  -----------------------  ------------------
  Total Lines of Code      5,000+
  GUI Components           15+ custom widgets
  API Endpoints Used       7 Supabase tables
  Languages Supported      2 (English, Malayalam)

--------------------------------------------------------------------------------
                             DEVELOPER
--------------------------------------------------------------------------------

Abhinav S
Full-Stack Developer

  - Designed and developed the complete CRM system
  - Implemented cloud-based real-time data synchronization
  - Built bilingual support with custom translation engine
  - Created intuitive UI/UX for non-technical staff users

--------------------------------------------------------------------------------
                              LICENSE
--------------------------------------------------------------------------------

This project is proprietary software developed for Akshaya Centre operations.
Copyright 2025 Akshaya Centre. All rights reserved.

================================================================================
                    Built with love for Akshaya Kodannur
              Digitizing government services, one entry at a time
================================================================================
