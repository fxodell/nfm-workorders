# Oilfield CMMS User Guide

## Table of Contents

1. [Getting Started](#getting-started)
2. [Authentication & Login](#authentication--login)
3. [Dashboard](#dashboard)
4. [Work Orders](#work-orders)
5. [Assets & Locations](#assets--locations)
6. [Parts & Inventory](#parts--inventory)
7. [Preventive Maintenance (PM)](#preventive-maintenance-pm)
8. [Shifts & On-Call Scheduling](#shifts--on-call-scheduling)
9. [Reports & Analytics](#reports--analytics)
10. [User Profile & Settings](#user-profile--settings)
11. [Admin Management](#admin-management)
12. [QR Code Scanning](#qr-code-scanning)
13. [Notifications & Real-Time Updates](#notifications--real-time-updates)
14. [Roles & Permissions](#roles--permissions)
15. [Troubleshooting & Tips](#troubleshooting--tips)

---

## Getting Started

### Accessing the Application

- **Web URL**: https://workorders.nfmconsulting.com (Production)
- **Local Development**: http://localhost:5173
- **API Documentation**: http://localhost:8002/docs (Swagger UI)

The application is a Progressive Web App (PWA) that works on both desktop and mobile devices. You can install it to your home screen for app-like access on iOS and Android.

### First Login

1. Open the application in your web browser
2. Enter your email and password on the login page
3. If your account has Multi-Factor Authentication (MFA) enabled, you'll be prompted to enter a 6-digit code from your authenticator app
4. You'll be redirected to the Dashboard on successful login

---

## Authentication & Login

### Login Process

**Step 1: Credentials Entry**
- Enter your registered email address
- Enter your password (minimum 8 characters)
- Optionally check "Remember me" to stay signed in longer

**Step 2: Multi-Factor Authentication (Optional)**

If your administrator has enabled MFA for your account:
- After successful password verification, you'll see a verification prompt
- Open your authenticator app (e.g., Google Authenticator, Microsoft Authenticator, Authy)
- Enter the 6-digit code displayed
- The code changes every 30 seconds, so ensure you're entering the current code

**Account Lockout Protection**
- After 5 failed login attempts within 15 minutes, your account will be temporarily locked
- Wait 15 minutes before attempting to log in again
- Contact your administrator if you're locked out and need immediate access

### Password Requirements

- Minimum 8 characters
- Can include letters, numbers, and special characters

### Account Recovery

If you forget your password:
1. Contact your organization administrator
2. Your administrator can reset your password via Admin Settings
3. Change the temporary password immediately on your next login

---

## Dashboard

### Overview

The Dashboard is your main hub, providing a real-time snapshot of your organization's maintenance operations.

### Quick Statistics Cards

- **Open WOs**: Total number of active work orders across all priorities
- **Escalated**: Number of work orders that have exceeded their SLA deadlines (pulses red)
- **Safety Flags**: Number of safety-critical work orders currently open
- **My Assigned**: Number of work orders assigned to you personally

Click any stat card to filter the work order list by that category.

### On-Shift Indicator

Located in the top-right corner:
- Green indicator + "On Shift": You're currently on a scheduled shift
- Gray indicator + "Off Shift": You're not on a scheduled shift

### Areas Breakdown

Expandable accordion cards for each organizational area:
- **Area Name**: Click to expand/collapse
- **Safety Flag Count**: Number of safety-flagged work orders in this area (red badge with alert icon)
- **Escalated Count**: Number of escalated work orders (red pulsing badge)
- **Priority Breakdown**: Color-coded pills showing count of work orders by priority
  - Red: IMMEDIATE priority
  - Orange: URGENT priority
  - Yellow: SCHEDULED priority
  - Blue: DEFERRED priority
- **Total Count**: Total work orders in the area

When expanded, each area shows:
- **Sites List**: All sites within the area with:
  - Site name and type (Well Site, Plant, Compressor, etc.)
  - Safety flag indicator (red alert icon if present)
  - Escalated indicator (red upward arrow if present)
  - Work order count badge
  - Assigned technician avatars (up to 3 shown, "+N" for more)

### Pull-to-Refresh

On mobile devices, pull down from the top to refresh the dashboard data.

### Floating Action Button

The "+" button in the bottom-right corner takes you directly to **Create New Work Order**.

---

## Work Orders

### Understanding Work Order States

Work orders follow a 10-state lifecycle:

```
NEW → ASSIGNED → ACCEPTED → IN_PROGRESS → RESOLVED → VERIFIED → CLOSED
                                ↕
                        WAITING_ON_OPS
                        WAITING_ON_PARTS
                        (can resume from either)

Any open status → ESCALATED (manual or automatic SLA breach)
CLOSED → (ADMIN can reopen to any open status)
```

#### State Descriptions

| State | Description |
|-------|-------------|
| **NEW** | Initial state when created. Awaiting assignment. |
| **ASSIGNED** | A supervisor has assigned the work order to a technician. |
| **ACCEPTED** | The technician has accepted and committed to the work. |
| **IN_PROGRESS** | The technician is actively working on the issue. |
| **WAITING_ON_OPS** | Paused, waiting for operations team action. |
| **WAITING_ON_PARTS** | Paused, waiting for parts to arrive. |
| **RESOLVED** | Technician has completed the work. |
| **VERIFIED** | A supervisor has verified the work meets quality standards. |
| **CLOSED** | Finalized. ADMIN can reopen if needed. |
| **ESCALATED** | SLA deadline breached, or manually escalated. |
| **CANCELLED** | Work order was cancelled (rare). |

### Work Order Types

- **REACTIVE**: Unplanned maintenance (emergency breakdown, issue reported by operations)
- **PREVENTIVE**: Scheduled maintenance from PM templates
- **INSPECTION**: Routine inspection of equipment or facility
- **CORRECTIVE**: Follow-up repair from an inspection finding

### Priority Levels

Each priority has associated SLA response and resolution times (configurable by Admin):

| Priority | Color | Meaning | Typical SLA |
|----------|-------|---------|------------|
| IMMEDIATE | Red | Drop everything, respond now | 15–30 min response, 2–4 hour resolution |
| URGENT | Orange | Same-day response required | 1–2 hour response, 8 hour resolution |
| SCHEDULED | Yellow | Plan within normal workflow | 4–8 hour response, 2–3 day resolution |
| DEFERRED | Blue | Low priority, no rush | 1 week response, 2 week resolution |

### Creating a Work Order

1. Click the **"+" button** (FAB) or navigate to **Work Orders → New**
2. Fill in the required fields:
   - **Title**: Brief description of the issue (required)
   - **Description**: Detailed problem description (optional but recommended)
   - **Priority**: Select from IMMEDIATE, URGENT, SCHEDULED, or DEFERRED
   - **Type**: Select from REACTIVE, PREVENTIVE, INSPECTION, CORRECTIVE
   - **Site**: Select the site where the work is needed (required)
   - **Asset** (optional): Specific equipment/asset within the site
   - **Assignee** (optional): Assign to a technician immediately
3. **Safety Critical Work**:
   - Check "Safety Flag" if this involves hazardous work
   - Add safety notes describing the hazard (e.g., "H2S environment", "Hot work", "Confined space")
   - Specify required certifications if applicable
4. Click **"Create Work Order"** to submit
   - The system assigns a human-readable number (e.g., "WO-2026-000042")
   - A timeline event is created recording creation details

### Work Order List & Filtering

Access the work order list from the sidebar or by clicking "Open WOs" on the dashboard.

#### Tabs
- **My WOs**: Work orders assigned to you
- **All WOs**: All work orders in your organization (admin) or assigned areas
- **Escalated**: Only escalated work orders (red background)
- **Safety**: Only safety-flagged work orders (red alert icon)

#### Filtering & Search
- **Search Bar**: Search by work order number (e.g., "WO-2026"), title, or description
- **Filter Panel** (funnel icon):
  - **Status**: Filter by any status (NEW, ASSIGNED, ACCEPTED, etc.)
  - **Priority**: Filter by priority level
  - **Type**: Filter by work order type
  - **Safety Flag**: Show only safety-flagged work orders

#### Sorting
- **Newest First**: Most recently created
- **Highest Priority**: IMMEDIATE first, then URGENT, etc.
- **Due Soonest**: Earliest SLA deadline first
- **Recently Updated**: Most recently modified

#### Work Order Card Display
Each card shows:
- **Work Order Number** (e.g., WO-2026-000042) with copy-to-clipboard button
- **Status Badge**: Color-coded status
- **Title**: Brief description
- **Priority Badge**: Color and label
- **Type**: Work order type
- **Site Name**: Where the work is located
- **Updated Timestamp**: How long ago last modified
- **Assignee Avatar**: Initials in a colored circle (if assigned)

### Work Order Detail View

Click on any work order card to open the detailed view with 6 tabs:

#### Tab 1: Details

**Basic Information:**
- Work order number, title, description
- Type, priority (color badge), status
- Safety flag indicator with hazard details
- Site and asset information, area and location

**Key Dates:**
- Created, Updated, Assigned At, Accepted At, Started At, Resolved At, Closed At

**SLA Status:**
- Acknowledgment, First Update, and Resolution deadlines
- SLA Breach indicator (red icon if deadline passed)
- Escalation status and reason

**State Machine Actions** (buttons vary by your role and current status):
- **Assign** — Change the assignee (SUPERVISOR+)
- **Accept** — Accept the assignment (TECHNICIAN+)
- **Start Work** — Begin work (TECHNICIAN+)
- **Wait on Ops** — Pause for operations (TECHNICIAN+)
- **Wait on Parts** — Pause for parts delivery (TECHNICIAN+)
- **Resume** — Resume from waiting state (TECHNICIAN+)
- **Resolve** — Mark work complete (TECHNICIAN+)
- **Verify** — Confirm quality (SUPERVISOR+)
- **Close** — Finalize the work order (SUPERVISOR+)
- **Reopen** — Revert a closed or verified work order (SUPERVISOR+)
- **Escalate** — Flag as SLA breach / urgent (TECHNICIAN+)
- **Acknowledge Escalation** — Acknowledge SLA breach (SUPERVISOR+)

#### Tab 2: Timeline

A chronological record of all events:
- **STATUS_CHANGE**: State transitions
- **MESSAGE**: User posted a message
- **ATTACHMENT**: Photo or file uploaded
- **PARTS_ADDED**: Parts logged as used
- **LABOR_LOGGED**: Time logged
- **ASSIGNMENT_CHANGE**: Assigned to a different technician
- **SLA_BREACH**: SLA deadline passed
- **ESCALATION**: Work order escalated
- **SAFETY_FLAG_SET**: Safety flag toggled

Each event shows timestamp, username, event type with icon, and change details.

#### Tab 3: Messages

A threaded messaging system for team communication:
- Type your message and click **Send** or press Ctrl+Enter
- Messages are ordered chronologically with author name and timestamp
- Real-time updates via WebSocket
- Messages are immutable (audit trail)

#### Tab 4: Parts

Track parts consumed on this work order:

1. Click **+ Add Part**
2. Select or search for the part number
3. Enter quantity used and unit cost (auto-fills from inventory)
4. Click **Add**
5. Stock is automatically decremented in inventory

The parts table shows: part number, description, quantity, unit cost, total cost, and a delete button.

#### Tab 5: Labor

Log technician labor hours:

1. Click **+ Log Labor**
2. Enter minutes spent (e.g., 120 for 2 hours)
3. Add optional notes (e.g., "Troubleshooting pump seals")
4. Click **Log**

The labor table shows: technician name, duration, notes, timestamp, and delete button. Total labor hours and cost are calculated automatically.

#### Tab 6: Attachments (Photos)

Upload photos and documents:

1. Click **+ Add Photo**
2. Select an image file (JPG, PNG, GIF, WebP supported)
3. On mobile, you can take photos directly via camera
4. Files upload to secure storage with pre-signed URLs

Photos taken while offline are queued and upload when connectivity returns.

---

## Assets & Locations

### Organizational Hierarchy

```
Organization (e.g., "Permian Basin Operations")
  └── Area (e.g., "North Field")
      └── Location (e.g., "Section 12 Pad")
          └── Site (e.g., "Well A-1")
              └── Asset (e.g., "Separator SP-001")
```

### Sites

Sites represent physical locations where work occurs.

**Site Types:** WELL_SITE, PRODUCTION_FACILITY, STORAGE, TERMINAL, COMPRESSOR_STATION, TANK_BATTERY, SEPARATOR, PLANT, BUILDING, APARTMENT, LINE, SUITE, OTHER

**Site Details View:**
- Site name and type
- Associated area and location
- All assets within the site
- Open work orders count and priorities
- Assigned technicians
- QR code for scanning

### Assets

Assets are specific equipment or machinery within a site.

**Asset Detail Page:**
- Full asset specifications
- Linked work orders (open and closed)
- Preventive maintenance templates assigned
- Maintenance history

---

## Parts & Inventory

Navigate to **Inventory** from the sidebar.

### Parts List View

- Total inventory value displayed at top
- Low stock count badge
- Search by part number, description, supplier, or storage location
- Toggle **Low Stock Only** to show parts below reorder threshold

**Parts List Columns:** Part Number, Description, Current Stock, Reorder Threshold, Unit Cost, Supplier, Storage Location, Status (green = stocked, red = low stock)

### Adding a New Part

1. Click **+ Add Part**
2. Fill in: Part Number (unique), Description, Unit Cost, Reorder Threshold, Supplier Name, Storage Location
3. Click **Create Part**

### Part Detail View

Click any part to see:
- Part information and specifications
- Current stock level and reorder threshold
- Total inventory value

**Stock Transactions** (historical log):
- **Stock In (IN)**: Received parts (green)
- **Stock Out (OUT)**: Parts consumed on work orders (red)
- **Adjustment (ADJUSTMENT)**: Inventory corrections (blue)

Each transaction shows type, quantity, notes, user, and timestamp.

**Adding a Transaction:**
1. Click **+ Add Transaction**
2. Select type (IN, OUT, ADJUSTMENT)
3. Enter quantity and notes
4. Click **Record**

---

## Preventive Maintenance (PM)

Navigate to **PM** from the sidebar.

### Calendar View

A monthly calendar showing PM schedules:
- **Blue**: PENDING (not yet generated into work orders)
- **Green**: GENERATED (work order created)
- **Gray**: SKIPPED (maintenance was skipped)
- **Red**: OVERDUE (past due without generation)

Navigate months with left/right arrows. Click a date to see that day's schedules.

### PM Templates

Recurring maintenance task definitions.

**Creating a PM Template:**
1. Click **+ New Template**
2. Fill in:
   - **Name**: e.g., "Monthly Pump Inspection"
   - **Description**: What should be done
   - **Site**: Which site this applies to
   - **Asset** (optional): Specific asset
   - **Recurrence Type**:
     - DAILY, WEEKLY, MONTHLY
     - CUSTOM_DAYS (every N days)
     - METER_BASED (every N operating hours)
   - **Assigned Role**: Which role should perform the work
   - **Required Certification**: If applicable
   - **Is Active**: Toggle to enable/disable
3. Click **Create**

**Managing Templates:**
- Toggle Active/Inactive with the green switch
- Edit, Delete, or View Schedules for each template

### PM Schedules

Auto-generated schedule entries:
- A background task runs daily at 06:00 UTC to generate schedules
- PM reminders run at 08:00 UTC to notify assigned technicians

**Schedule Status:**
- **PENDING**: Work order not yet generated
- **GENERATED**: Work order created from this schedule
- **SKIPPED**: Maintenance was skipped (with reason)

**Skipping a Schedule:**
1. Click **Skip**
2. Enter reason (e.g., "Equipment down for repair")
3. Click **Confirm Skip**

---

## Shifts & On-Call Scheduling

### Shift Assignments (Admin Only)

**Creating a Shift:**
1. Navigate to Admin → Shifts
2. Click **+ New Shift**
3. Fill in: Name, Start Time, End Time, Days of Week, Timezone
4. Click **Create**

**Assigning Users to Shifts:**
1. Open shift details
2. Click **+ Add User**
3. Search and select a technician
4. Click **Assign**

### On-Call Schedules (Admin Only)

**Creating On-Call Assignment:**
1. Navigate to Admin → On-Call
2. Click **+ New On-Call Period**
3. Fill in: Date Range, Area, Primary User, Secondary User (optional)
4. Click **Create**

### Personal Shift Status

The dashboard shows your current shift status:
- Green dot + "On Shift": You're on a scheduled shift
- Gray dot + "Off Shift": You're off shift

This is computed automatically from your assigned shifts, current time, and timezone.

---

## Reports & Analytics

Navigate to **Reports** from the sidebar.

### Available Reports

| Report | Description |
|--------|-------------|
| **Overview** | Total work orders, breakdown by status/priority/type |
| **Response Times** | Average/median time from creation to acceptance, by priority and technician |
| **SLA Compliance** | Breach counts by type (ACK, FIRST_UPDATE, RESOLVE), compliance percentage |
| **Parts Spend** | Parts cost by work order, area, and most expensive parts consumed |
| **Labor Cost** | Total hours, cost by technician and area, average per work order |
| **Budget** | Budget vs. actual spend, variance by month and area |
| **PM Completion** | Schedules generated vs. completed, completion rate, overdue count |
| **Technician Performance** | WOs completed, MTTR, labor hours, quality metrics, SLA compliance per tech |
| **Safety Flags** | Safety-flagged WOs by type, technician certifications, completion status |

### Date Range Filters

All reports support date filtering with presets:
- Last 7 Days, Last 30 Days (default), Last 90 Days, Year-to-Date, Custom

### Area Filter

Filter all report data to a specific area.

### Exporting

Most report tables include a **Download CSV** button for use in Excel, Google Sheets, or other tools.

---

## User Profile & Settings

Navigate to **Profile** from the sidebar or top-right user menu.

### Profile Information

- Display name (editable)
- Email address (read-only — contact admin to change)
- Phone number (editable)
- Role (read-only)
- MFA status

### Certification Alerts

If any certifications are:
- **Expired**: Red badge at top of profile
- **Expiring within 30 days**: Yellow badge

View all certifications with name, number, issued date, expiration date, and issuing organization.

### Changing Your Password

1. Expand **Change Password** section
2. Enter current password, new password (8+ characters), confirm new password
3. Click **Change Password**

### Multi-Factor Authentication (MFA)

**Enabling MFA:**
1. Click **Enable MFA**
2. Scan the QR code with your authenticator app (Google Authenticator, Authy, etc.)
3. Enter the 6-digit code from the app
4. Click **Verify & Enable**

**Disabling MFA:**
1. Click **Disable MFA**
2. Confirm by entering your current MFA code

### Push Notifications

1. Toggle **Push Notifications** on
2. Allow browser notification permission when prompted
3. Receive real-time alerts for assignments, status changes, SLA breaches, and PM reminders

### Notification Preferences by Area

For each area you have access to, toggle:
- **Push**: Receive push notifications
- **Email**: Receive email notifications

---

## Admin Management

Only **ADMIN** or **SUPER_ADMIN** roles can access Admin Settings. Navigate to **Admin** from the sidebar.

### Organization Settings

- View/edit organization name
- View organization ID

**SLA Configuration:**

| Priority | Response Time | Resolution Time |
|----------|---------------|-----------------|
| IMMEDIATE | 15 min | 4 hours |
| URGENT | 60 min | 8 hours |
| SCHEDULED | 4 hours | 2 days |
| DEFERRED | 7 days | 14 days |

All values are configurable. Also set the **Labor Rate** (hourly) for cost calculations.

### User Management

- View all users: name, email, role, active status, last login
- Search by name or email, filter by role

**Creating a New User:**
1. Click **+ Add User**
2. Fill in: Name, Email, Role, Initial Password
3. Click **Create**

**Editing a User:**
- Modify name, email, role, active status
- Assign to specific areas (non-admin users only see work in assigned areas)
- Reset password

**Deactivating a User:**
- Toggle **Active** to OFF — user can no longer log in but data is retained

### Audit Log

Complete immutable audit trail:
- Timestamp (UTC), username, action type, entity type, entity ID, changes made
- Filter by date range, entity type, user, or action type
- Export as CSV for compliance reporting

---

## QR Code Scanning

### Using the QR Scanner

1. Click **Scan** in the sidebar or bottom nav
2. Grant camera permission if prompted
3. Point your camera at a QR code

### What Can Be Scanned

QR codes can be printed and attached to:
- **Sites** — navigates to site detail
- **Assets** — navigates to asset detail
- **Parts** — navigates to inventory detail

After scanning, you can view details and create a new work order directly.

### Manual Entry

If the camera isn't working:
1. Go to Scan page
2. Click **Manual Entry**
3. Paste or type the QR URL
4. System recognizes the format and navigates

---

## Notifications & Real-Time Updates

### Real-Time Updates (WebSocket)

While the app is open, you receive instant updates:
- Work order status changes
- New assignments
- SLA escalations
- PM reminders

Updates appear immediately on the Dashboard, Work Order List, and Work Order Detail pages.

### Push Notifications

| Event | Trigger | Timing |
|-------|---------|--------|
| New Assignment | Work order assigned to you | Immediately |
| Status Change | Work order transitions status | Immediately |
| SLA Breach | Response/update/resolve deadline missed | Immediately |
| PM Reminder | PM schedule due within 24 hours | 08:00 daily |
| Shift Start | Your shift is starting | 30 minutes before |

### In-App Notification Drawer

Click the **Bell icon** in the top-right:
- Badge shows unread count
- List of recent notifications
- Click to navigate to the related entity

---

## Roles & Permissions

### Role Hierarchy (least to most privileged)

#### READ_ONLY
- View dashboards, work orders, sites, assets, inventory, reports, PM schedules
- Cannot create or modify anything

#### COST_ANALYST
- All READ_ONLY privileges
- Access to budget reports, labor cost analysis, parts spend analysis

#### TECHNICIAN
- View and accept assigned work orders
- Start/pause work, log labor, consume parts, upload photos, send messages, resolve work

#### OPERATOR
- All TECHNICIAN privileges
- Create reactive work orders, view all work orders, generate work from PM templates

#### SUPERVISOR
- All OPERATOR privileges
- Assign/reassign work orders, verify and close work, reopen work orders, acknowledge SLA breaches, manage shifts and on-call

#### ADMIN
- All SUPERVISOR privileges
- Create/manage users, create/edit PM templates, configure SLA, view audit logs, manage areas/locations/sites, full inventory management

#### SUPER_ADMIN
- All ADMIN privileges
- Cross-organization access, create organizations, system-level settings

### Permission Matrix

| Action | TECH | OPER | SUPV | ADMIN | SUPER |
|--------|:----:|:----:|:----:|:-----:|:-----:|
| Create Work Order | — | Yes | Yes | Yes | Yes |
| Assign Work Order | — | — | Yes | Yes | Yes |
| Accept Work Order | Yes | Yes | Yes | Yes | Yes |
| Log Labor / Parts | Yes | Yes | Yes | Yes | Yes |
| Resolve Work Order | Yes | Yes | Yes | Yes | Yes |
| Verify Work Order | — | — | Yes | Yes | Yes |
| Close Work Order | — | — | Yes | Yes | Yes |
| Manage Users | — | — | — | Yes | Yes |
| Configure SLA | — | — | — | Yes | Yes |
| View Audit Log | — | — | — | Yes | Yes |

### Area Scoping

Non-admin users can be restricted to specific areas — they'll only see work orders, sites, and inventory for their assigned areas. Admins and Super Admins see all areas.

---

## Troubleshooting & Tips

### Login Issues

| Problem | Solution |
|---------|----------|
| "Invalid email or password" | Verify email is correct and lowercase. Contact admin to reset password. |
| "Account is locked" | Wait 15 minutes or contact admin to reset lockout. |
| "Verification session expired" (MFA) | Go back to credentials entry and try again within 10 minutes. |

### Work Order Issues

| Problem | Solution |
|---------|----------|
| Can't transition status | Verify you have the correct role. Check that current status allows the transition. |
| Parts stock not updating | Refresh inventory page. Check transaction history. |
| Timeline events missing | Refresh the page. Verify you have permission to view the work order. |

### Mobile Setup

**iPhone/iPad:**
1. Open Safari → Tap Share → "Add to Home Screen"
2. Name the app and tap Add
3. Enable push notifications in Profile settings

**Android:**
1. Open Chrome → Tap Menu → "Install app"
2. Confirm installation
3. Enable push notifications in Profile settings

### Offline Workflow

**Works offline:**
- View previously loaded work orders, details, messages, timeline
- View cached dashboard and inventory
- Queue messages, status transitions, and photo uploads

**Requires online:**
- All queued changes sync automatically when connectivity returns
- Banner at top shows "X changes pending sync"

### Performance Tips

- Collapse unused areas on the dashboard
- Clear search filters on the work order list
- Refresh with pull-to-refresh on mobile
- Max recommended photo size: ~5MB

---

## Seeded Test Accounts

### Permian Basin Operations

| Role | Email | Password |
|------|-------|----------|
| Admin | admin@apachecorp.com | admin123! |
| Supervisor | supervisor@apachecorp.com | supervisor123! |
| Operator | operator@apachecorp.com | operator123! |
| Technician | tech1@apachecorp.com | tech123! |
| Technician | tech2@apachecorp.com | tech123! |
| Technician | tech3@apachecorp.com | tech123! |
| Read-Only | viewer@apachecorp.com | viewer123! |
| Cost Analyst | analyst@apachecorp.com | analyst123! |
| Super Admin | superadmin@apachecorp.com | super123! |

### Eagle Ford Services

| Role | Email | Password |
|------|-------|----------|
| Admin | admin@eagle-ford-services.com | admin123! |
| Supervisor | supervisor@eagle-ford-services.com | supervisor123! |
| Operator | operator@eagle-ford-services.com | operator123! |
| Technician | tech1@eagle-ford-services.com | tech123! |
| Technician | tech2@eagle-ford-services.com | tech123! |
| Technician | tech3@eagle-ford-services.com | tech123! |
| Read-Only | viewer@eagle-ford-services.com | viewer123! |
| Cost Analyst | analyst@eagle-ford-services.com | analyst123! |
| Super Admin | superadmin@eagle-ford-services.com | super123! |

---

## FAQ

**Q: Can I work offline?**
A: Yes. The app caches data and queues changes. When online, changes sync automatically. Install as PWA for best offline support.

**Q: How are costs calculated?**
A: Labor cost = minutes worked x (org labor rate / 60). Parts cost = sum of (quantity x unit cost).

**Q: Can I undo a status transition?**
A: Only admins/supervisors can reopen a closed work order. Most other transitions are one-directional.

**Q: Why don't I see some work orders?**
A: Non-admin users only see work orders in their assigned areas. Ask your admin to assign you to additional areas.

**Q: How do I change my email?**
A: Email is read-only. Contact your admin to update it.

**Q: What happens if I miss an SLA deadline?**
A: The work order automatically escalates (red background). A supervisor must acknowledge the escalation.

**Q: Can I reassign a work order?**
A: Yes, if you're a Supervisor or above. Open the work order detail and click "Assign."
