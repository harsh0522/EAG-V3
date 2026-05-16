Prompt: Build a Lightweight Local-Only Splitwise-Style Chrome Extension

Build a lightweight Splitwise-style expense-sharing app as a Chrome Extension.

The app should run locally on whichever device Chrome is running on, such as Windows, macOS, Linux, tablets, and smartphones where browser extension support is available. The app must be lightweight, fast, responsive, and should not require any external backend, external database, cloud server, or paid service.

## App Name

**FairSplit Local**

## Main Goal

Create a local-only Chrome Extension that works like a simple Splitwise clone.

Users should be able to:

- Create groups
- Add people
- Add expenses
- Split expenses
- See who owes whom
- Settle payments
- View balances
- Lock and unlock the app with a PIN
- Recover access using a security question
- Toggle between dark mode and light mode

## Very Important Requirements

- No external database
- No backend server
- No cloud storage
- No Firebase
- No Supabase
- No MongoDB
- No PostgreSQL
- No paid APIs
- No internet dependency for core features
- All data must be stored locally inside the browser/device
- Use Chrome Extension local storage or IndexedDB
- Keep the app lightweight and fast
- App should run completely offline after installation
- Data will stay only on the same device/browser where the extension is installed

## Platform Requirement

Build this as a Chrome Extension using **Manifest V3**.

The extension should work on:

- Chrome on Windows
- Chrome on macOS
- Chrome on Linux
- Chrome-based browsers if supported
- Tablet browsers if extension support is available
- Smartphone browsers if extension support is available

Important:
Normal Chrome on many smartphones may not support extensions. Still, build the UI responsive so it can run properly wherever extension support exists.

## Authentication and Lock System

Do not use real online authentication.

Create a local login/unlock system only.

The first time the user opens the extension, show a setup screen.

The setup screen should ask for:

- Username
- Password
- PIN
- Security question
- Security answer

Store these securely in local storage or IndexedDB.

Security requirements:

- Do not store password, PIN, or security answer in plain text
- Hash password, PIN, and security answer before storing
- Use browser crypto APIs if possible
- User can unlock the app using PIN
- User can log in using username and password
- User can reset PIN using security question and answer
- Add auto-lock after inactivity
- Add manual lock button

## Local Data Storage

Use local browser storage only.

Preferred storage:

- IndexedDB for app data
- chrome.storage.local for settings if needed

Store locally:

- User profile
- Groups
- Members
- Expenses
- Expense splits
- Settlements
- App settings
- Theme preference
- Activity history

No data should leave the device.

## Core Features

## 1. Dashboard

After unlock/login, show a dashboard with:

- Total balance
- Amount user owes
- Amount user is owed
- List of groups
- Recent expenses
- Recent settlements
- Quick add expense button
- Create group button
- Settle up button

## 2. Groups

Users should be able to:

- Create a group
- Edit group name
- Delete group
- Add group category/icon:
  - Trip
  - Home
  - Friends
  - Office
  - Family
  - Other
- Add members manually by name
- Edit member name
- Remove member only if they have no pending balance
- View group expenses
- View group balances
- View settlement suggestions

There is no need to invite people by email because this is a local-only app.

## 3. Members

Members are local names only.

Example members:

- Harsh
- Rahul
- Amit
- Priya

For every group, show:

- Member name
- Total paid
- Total share
- Net balance
- Whether they owe money or are owed money

## 4. Expenses

User should be able to add expenses with:

- Expense title
- Amount
- Paid by
- Date
- Category
- Notes optional
- Group selection
- Split type

Supported split types:

- Equal split
- Unequal exact amount split
- Percentage split
- Shares split
- Split only among selected members

Example:
If Harsh paid ₹1000 for dinner for 4 people, each person owes ₹250. If Harsh is also included, the other 3 people owe Harsh ₹250 each.

## 5. Expense Details

Each expense should show:

- Expense title
- Total amount
- Paid by
- Split members
- Individual share of each member
- Date
- Category
- Notes
- Edit expense button
- Delete expense button

## 6. Balance Calculation

The app should automatically calculate:

- Who paid
- Who shared the expense
- How much each member owes
- How much each member paid
- Net balance for every member
- Group-wise balance
- Overall balance across all groups

Example:
A paid ₹1000.
B paid ₹500.
Both shared equally.
Total = ₹1500.
Each share = ₹750.
A is owed ₹250.
B owes ₹250.

## 7. Settlement Simplification

Create a debt simplification algorithm.

Example:
A owes B ₹500.
B owes C ₹500.

Simplified result:
A owes C ₹500.

Show suggestions like:

- Harsh should pay Rahul ₹350
- Amit should pay Harsh ₹200

## 8. Settlements

Users should be able to:

- Record a payment
- Select payer
- Select receiver
- Enter amount
- Add date
- Add note optional
- View settlement history
- Delete settlement if entered by mistake

Settlements should affect the final balance calculation.

## 9. Activity History

Store local activity logs for:

- Group created
- Group edited
- Group deleted
- Member added
- Member removed
- Expense added
- Expense edited
- Expense deleted
- Settlement recorded
- Settlement deleted
- Theme changed
- App locked/unlocked

## 10. Search and Filters

Users should be able to:

- Search expenses by name
- Filter expenses by group
- Filter expenses by category
- Filter expenses by member who paid
- Filter expenses by date
- Filter settled/unsettled balances

## 11. Dark Mode and Light Mode

Add a theme toggle.

Requirements:

- Light mode
- Dark mode
- Store selected theme locally
- Apply theme immediately
- Theme should persist after closing and reopening the extension
- UI should look clean in both modes

## 12. Data Backup and Restore

Since there is no external database, add local backup and restore.

User should be able to:

- Export all data as a JSON file
- Import data from a JSON file
- Clear all local data after confirmation

This is important because data is stored only on the device.

## Chrome Extension UI Requirements

Create a clean and lightweight UI.

Extension should include:

- Popup UI
- Options/settings page
- Lock screen
- Dashboard screen
- Groups screen
- Group detail screen
- Add expense screen
- Expense detail screen
- Settle up screen
- Activity screen
- Backup/restore screen
- Settings screen

UI style:

- Mobile-first responsive layout
- Works well in small popup size
- Works well on larger extension/options page
- Clean cards
- Simple buttons
- Clear typography
- INR currency by default
- Green accent color similar to Splitwise
- Dark/light mode support
- Avoid heavy UI libraries if possible

## Technical Requirements

Use:

- Chrome Extension Manifest V3
- HTML, CSS, JavaScript or React
- IndexedDB for local data
- chrome.storage.local for settings
- Browser Crypto API for hashing
- No backend
- No external database
- No mandatory internet access
- No heavy dependencies

Preferred frontend:

- React with Vite, or plain JavaScript if simpler and lighter
- Tailwind CSS optional, but keep bundle size small

## Data Models

Create local data models for:

### LocalUser

Fields:

- id
- username
- passwordHash
- pinHash
- securityQuestion
- securityAnswerHash
- createdAt
- updatedAt

### Group

Fields:

- id
- name
- category
- icon
- createdAt
- updatedAt

### Member

Fields:

- id
- groupId
- name
- createdAt
- updatedAt

### Expense

Fields:

- id
- groupId
- title
- amount
- paidByMemberId
- category
- date
- notes
- splitType
- createdAt
- updatedAt

### ExpenseSplit

Fields:

- id
- expenseId
- memberId
- amount
- percentage optional
- shares optional
- createdAt
- updatedAt

### Settlement

Fields:

- id
- groupId
- payerMemberId
- receiverMemberId
- amount
- date
- notes
- createdAt
- updatedAt

### ActivityLog

Fields:

- id
- type
- message
- groupId optional
- expenseId optional
- settlementId optional
- createdAt

### Settings

Fields:

- theme
- currency
- autoLockMinutes
- lastUnlockedAt

## Balance Calculation Rules

Implement proper money calculation.

Rules:

- Use paise/cents internally instead of floating numbers
- Store ₹100.50 as 10050 paise
- Display values rounded to 2 decimals
- Expense amount should equal total split amount
- Percentage split should total 100%
- Exact split should equal total expense amount
- Shares split should be calculated accurately
- Deleted expenses should not affect balance
- Deleted settlements should not affect balance
- Settlements reduce outstanding balance
- Users with zero balance should show as settled

## Security Rules

Because this is local-only, clearly explain:

- Password/PIN protects app access on the same browser
- It is not a real cloud login
- Data is not synced between devices
- If browser data is cleared, app data may be lost
- User should export backup regularly

Implement:

- PIN unlock
- Password login
- Security question recovery
- Auto-lock
- Manual lock
- Hashed secrets
- Clear all data option with confirmation

## Final Output Required

Generate the complete project with:

- Chrome Extension source code
- Manifest V3 file
- Popup UI
- Options/settings page
- Local storage/IndexedDB layer
- Local authentication system
- PIN unlock logic
- Security question reset logic
- Group management
- Member management
- Expense management
- Split calculation logic
- Settlement simplification logic
- Dark/light mode toggle
- Backup/export JSON
- Restore/import JSON
- Clear data option
- README.md
- Setup instructions
- Build instructions
- Instructions to load extension in Chrome developer mode
- Explanation of local-only limitations

## README Must Include

The README should explain:

- What the app does
- Features
- Tech stack
- How to install dependencies
- How to run locally
- How to build the extension
- How to load the extension in Chrome
- How local storage works
- How backup and restore works
- Why there is no external database
- Mobile browser extension limitation
- Security limitation of local-only login

## Expected Result

Build a complete, lightweight, offline-first, local-only Chrome Extension that works like a basic Splitwise clone.

The user should be able to install it in Chrome, set up username/password/PIN, create groups, add people, add expenses, split bills, see balances, settle payments, toggle dark/light mode, and backup/restore data without using any external database or backend server.
"""