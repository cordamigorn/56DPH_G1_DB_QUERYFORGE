# QueryForge - Web UI Test Scenarios

**Project:** QueryForge - Automated Data Pipeline Generation System  
**Test Version:** 2.0  
**Last Updated:** December 8, 2025  
**Testing Purpose:** Manual UI testing through web browser

---

## 📋 Table of Contents

1. [Test Environment Setup](#test-environment-setup)
2. [Pre-Test Checklist](#pre-test-checklist)
3. [🌐 WEB UI TEST SCENARIOS](#web-ui-test-scenarios)
4. [📊 Test Results Summary](#test-results-summary)

---

## Test Environment Setup

### Prerequisites

Before starting tests, ensure the following are ready:

```bash
# 1. Check Python version (must be 3.10+)
python --version

# 2. Check virtual environment is activated
which python  # Linux/macOS
where python  # Windows

# 3. Verify all dependencies installed
pip list | grep fastapi
pip list | grep google-generativeai

# 4. Check environment variables
echo $GEMINI_API_KEY  # Linux/macOS
echo %GEMINI_API_KEY%  # Windows
```

### Database Initialization

```bash
# Initialize database
python -m app.core.database

# Verify tables created
sqlite3 queryforge.db ".tables"
# Expected: Pipelines, Pipeline_Steps, Schema_Snapshots, Execution_Logs, Repair_Logs
```

### Test Data Preparation

```bash
# Verify test data files exist
ls -la data/
# Expected files: customers.csv, inventory.json, sales.csv

# Check data/sales.csv content
head -5 data/sales.csv
```

### Database Tables Check

**IMPORTANT:** Before testing, check which tables exist in your database:

```bash
# List all tables
sqlite3 queryforge.db ".tables"

# Expected system tables: Pipelines, Pipeline_Steps, Schema_Snapshots, Execution_Logs, Repair_Logs, Filesystem_Changes

# Check if 'orders' table exists (used in test scenarios)
sqlite3 queryforge.db "SELECT name FROM sqlite_master WHERE type='table' AND name='orders';"
```

**If 'orders' table doesn't exist**, create it before testing:

```bash
sqlite3 queryforge.db "CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY, order_date TEXT, customer TEXT, amount DECIMAL);"
```

Or use an **existing table name** in your tests instead of "orders".

**To see available table columns:**
```bash
sqlite3 queryforge.db "PRAGMA table_info(orders);"
```

---

## Pre-Test Checklist

Mark each item as you complete it:

- [ ] Python 3.10+ installed
- [ ] Virtual environment activated
- [ ] All dependencies installed (`pip install -r requirements.txt`)
- [ ] Gemini API key configured in `.env`
- [ ] Database initialized (queryforge.db exists)
- [ ] Test data files present in `data/` directory
- [ ] Git Bash or WSL available (for Windows users)
- [ ] **Server running:** `uvicorn app.main:app --reload`

---

## 🌐 WEB UI TEST SCENARIOS

> **🎯 START HERE** - These are manual UI test scenarios you can perform through the web browser.

### 🚀 Getting Started

**Before Testing:**
1. Make sure the server is running:
   ```bash
   uvicorn app.main:app --reload
   ```
2. Open your browser and navigate to: `http://localhost:8000/web/`
3. Keep the browser Developer Console open (F12) to monitor requests

---

### UI TEST 1: Homepage Access & Navigation

**Objective:** Verify the web interface loads correctly

**Steps:**
1. Open browser and go to: `http://localhost:8000/web/`
2. Observe the page loading
3. Check for any errors in browser console (F12)
4. Verify page elements are visible

**Expected Results:**
- ✅ Page loads without errors
- ✅ QueryForge logo/title visible
- ✅ Navigation menu present (if implemented)
- ✅ Create Pipeline form visible
- ✅ No JavaScript errors in console
- ✅ Page is responsive (resize browser window)

**Visual Checklist:**
- [ ] Page title displays correctly
- [ ] Form fields are visible and accessible
- [ ] Buttons are clickable
- [ ] Layout looks correct (no broken CSS)

**Pass Criteria:** Homepage loads completely without errors

---

### UI TEST 2: Simple Pipeline Creation (Recommended Pattern)

**Objective:** Create a basic pipeline using the recommended prompt pattern

**Steps:**
1. On the homepage, locate the "Create Pipeline" form
2. Fill in the form fields:
   - **User ID:** `1`
   - **Prompt:** `Load sales.csv into orders table`
     ❗ This uses the recommended pattern: "Load [data_source] into [table_name] table"
3. Click the **"Create Pipeline"** button
4. Wait for the response (may take 2-5 seconds)
5. Observe the result displayed on the page

**Expected Results:**
- ✅ Form accepts input without errors
- ✅ Submit button triggers request
- ✅ Loading indicator appears (if implemented)
- ✅ Pipeline ID returned and displayed
- ✅ Pipeline status shows "generated" or "pending"
- ✅ Draft pipeline steps are displayed
- ✅ Steps show type (bash/sql) and content preview
- ✅ Success message or confirmation appears

**What to Record:**
- Pipeline ID: ____________
- Number of steps generated: ____________
- Response time: ____________ seconds

**Screenshot:** 📷 Take a screenshot of the created pipeline

**Pass Criteria:** Pipeline created successfully with ID and steps displayed

---

### UI TEST 3: View Pipeline Details

**Objective:** Navigate to pipeline detail page and view information

**Steps:**
1. After creating a pipeline, click on the pipeline ID or "View Details" link
2. Observe the pipeline detail page
3. Review all displayed information

**Expected Results:**
- ✅ Detail page loads correctly
- ✅ Pipeline ID displayed prominently
- ✅ Original prompt shown
- ✅ Pipeline status visible (pending/running/success/failed)
- ✅ List of steps displayed with:
  - Step number
  - Step type (bash/sql)
  - Script content (formatted/highlighted)
- ✅ Action buttons available:
  - "Run in Sandbox"
  - "View Logs" (if executed)
  - "Commit to Production" (if successful)

**Visual Elements Checklist:**
- [ ] Pipeline metadata section
- [ ] Steps displayed in order (1, 2, 3...)
- [ ] Code blocks are readable
- [ ] Action buttons are clearly labeled
- [ ] Status badge/indicator visible

**Pass Criteria:** All pipeline information displayed correctly

---

### UI TEST 4: Run Pipeline in Sandbox

**Objective:** Execute a pipeline in the sandbox environment via UI

**Steps:**
1. On the pipeline detail page, locate the **"Run in Sandbox"** button
2. Click the button
3. Wait for execution (may take 5-15 seconds)
4. Observe the execution results

**Expected Results:**
- ✅ Button triggers execution request
- ✅ Loading indicator shows during execution
- ✅ Execution results displayed after completion
- ✅ Each step shows:
  - Exit code (0 = success, non-zero = failure)
  - Standard output (stdout)
  - Error output (stderr) if any
  - Execution time in milliseconds
- ✅ Overall status updated (success/failed)
- ✅ Step-by-step execution log visible

**Execution Log Verification:**
```
For each step, verify:
- [ ] Step number matches
- [ ] Exit code displayed
- [ ] Output is readable
- [ ] Timestamp recorded
- [ ] Success/failure clearly indicated
```

**What to Record:**
- Overall status: ____________ (success/failed)
- Number of steps executed: ____________
- Total execution time: ____________ seconds
- Any errors encountered: ____________

**Pass Criteria:** Pipeline executes and shows detailed results

---

### UI TEST 5: View Execution Logs

**Objective:** Access and review complete execution history

**Steps:**
1. On the pipeline detail page, click **"View Logs"** or **"Execution History"**
2. Review the logs page
3. Examine all log entries

**Expected Results:**
- ✅ Logs page loads successfully
- ✅ Original prompt displayed at top
- ✅ **Execution Logs** section shows:
  - All executed steps in chronological order
  - Timestamp for each execution
  - Success/failure status
  - Complete stdout and stderr
  - Execution time per step
- ✅ **Repair Logs** section visible (may be empty)
- ✅ Logs are formatted and easy to read
- ✅ Color coding for success/error (if implemented)

**Log Detail Checklist:**
- [ ] Can see full command/SQL that was executed
- [ ] Output is complete (not truncated)
- [ ] Timestamps are accurate
- [ ] Can distinguish between different execution attempts

**Pass Criteria:** Complete and readable execution history displayed

---

### UI TEST 6: Pipeline with Error (Testing Repair Flow)

**Objective:** Create a pipeline that will fail and trigger repair mechanism

**Steps:**
1. Go back to homepage (Create Pipeline)
2. Create a pipeline with an intentional error:
   - **User ID:** `1`
   - **Prompt:** `Load non_existent_file.csv into orders table`
     ⚠️ This file doesn't exist, will cause error
3. Click **"Create Pipeline"**
4. Navigate to the pipeline detail page
5. Click **"Run in Sandbox"**
6. Observe the error
7. Look for repair options or automatic repair

**Expected Results:**
- ✅ Pipeline created (LLM may not detect non-existent file)
- ✅ Execution fails with clear error message
- ✅ Error message displayed:
  - "No such file or directory: non_existent_file.csv" or similar
- ✅ Overall status shows "failed"
- ✅ Error is highlighted or marked clearly
- ✅ Repair option available (button/link)

**Error Display Checklist:**
- [ ] Error message is visible and clear
- [ ] Failed step is highlighted
- [ ] stderr output shows actual error
- [ ] Exit code shows failure (non-zero)
- [ ] User understands what went wrong

**Pass Criteria:** Error detected and displayed clearly to user

---

### UI TEST 7: Trigger Pipeline Repair

**Objective:** Use the repair functionality through the UI

**Steps:**
1. From the failed pipeline (TEST 6), locate the **"Repair Pipeline"** button
2. Click the repair button
3. Wait for AI to analyze and fix the error (5-10 seconds)
4. Observe the repair results

**Expected Results:**
- ✅ Repair request triggered
- ✅ Loading/processing indicator shown
- ✅ Repair attempt information displayed:
  - Attempt number (1, 2, or 3)
  - Error analysis/reason
  - AI fix explanation
  - Updated/patched code
- ✅ Option to retry execution with fix
- ✅ Repair logs updated in database

**Repair Result Verification:**
```
- [ ] Repair attempt number shown (max 3)
- [ ] Original error explained
- [ ] Fix reasoning provided by AI
- [ ] New code displayed
- [ ] Can see difference from original
```

**What to Record:**
- Repair attempt number: ____________
- AI fix reasoning: ____________
- Repair successful: Yes / No

**Pass Criteria:** Repair mechanism triggers and shows fix attempt

---

### UI TEST 8: Pipeline List View

**Objective:** View all created pipelines in a list

**Steps:**
1. Navigate to the pipelines list page (may be homepage or separate page)
2. Observe the list of all pipelines
3. Try filtering or sorting (if available)

**Expected Results:**
- ✅ List displays all created pipelines
- ✅ Each pipeline shows:
  - Pipeline ID
  - User ID
  - Prompt text (full or truncated)
  - Status (pending/running/success/failed/repaired)
  - Created date/time
  - Updated date/time
- ✅ Clickable links to pipeline details
- ✅ Pagination (if many pipelines)
- ✅ Status indicators (color/icon)

**List Features Checklist:**
- [ ] Can click on pipeline to view details
- [ ] Status is clear and understandable
- [ ] Timestamps are readable
- [ ] List updates after creating new pipeline
- [ ] Filtering works (if implemented)
- [ ] Sorting works (if implemented)

**Pass Criteria:** Pipeline list displays all pipelines with key information

---

### UI TEST 9: Multi-Step Pipeline Creation

**Objective:** Create a complex pipeline with multiple steps

**Steps:**
1. Create a new pipeline with a complex prompt:
   - **User ID:** `1`
   - **Prompt:** `Load customers.csv, filter rows where email is empty, then import to customers table`
2. Submit and view the generated pipeline
3. Count the number of steps generated
4. Run the pipeline
5. Observe multi-step execution

**Expected Results:**
- ✅ Multiple steps generated (typically 2-3)
- ✅ Steps are in logical order:
  - Step 1: Bash filtering (awk/grep/sed)
  - Step 2: SQL import (COPY/INSERT)
- ✅ Each step displays correctly
- ✅ Execution shows progress through steps
- ✅ Can see intermediate results

**Multi-Step Verification:**
```
Step 1:
- [ ] Type: bash
- [ ] Contains filtering logic
- [ ] References customers.csv
- [ ] Output file specified

Step 2:
- [ ] Type: sql
- [ ] Contains COPY or INSERT
- [ ] References customers table
- [ ] Uses filtered data from Step 1
```

**Pass Criteria:** Multi-step pipeline created and executes sequentially

---

### UI TEST 10: Commit to Production (CAREFUL!)

**Objective:** Test production commit functionality

⚠️ **WARNING:** This will modify your actual database. Only test with non-critical data.

**Pre-requisites:**
- Pipeline must have executed successfully in sandbox
- Overall status = "success"

**Steps:**
1. Navigate to a successfully executed pipeline
2. Locate the **"Commit to Production"** button
3. Read any warning messages
4. Click the commit button
5. Confirm the action (if confirmation dialog appears)
6. Wait for commit to complete
7. Observe the results

**Expected Results:**
- ✅ Warning or confirmation displayed before commit
- ✅ Button only enabled for successful sandbox runs
- ✅ Commit executes successfully
- ✅ Commit status displayed:
  - Success/failure message
  - Number of operations applied
  - Rows affected
  - Timestamp
- ✅ Pipeline status updated to "committed"
- ✅ Cannot commit twice (button disabled after first commit)

**Commit Verification:**
```bash
# Verify data was actually committed to database
sqlite3 queryforge.db "SELECT * FROM orders LIMIT 5;"

# Check commit was logged
sqlite3 queryforge.db "SELECT * FROM Pipelines WHERE id = [pipeline_id];"
```

**Post-Commit Checklist:**
- [ ] Data exists in target table
- [ ] Commit status recorded
- [ ] Commit cannot be repeated
- [ ] Rollback option available (if implemented)

**Pass Criteria:** Commit applies changes to production database successfully

---

### UI TEST 11: Error Handling & User Feedback

**Objective:** Test how the UI handles various error scenarios

**Test Cases:**

**A. Empty Form Submission**
1. Leave user_id or prompt empty
2. Click "Create Pipeline"
3. ✅ Validation error shown
4. ✅ Required fields highlighted
5. ✅ Clear error message displayed

**B. Invalid User ID**
1. Enter non-numeric user_id (e.g., "abc")
2. Submit form
3. ✅ Validation error or type conversion error shown

**C. Network Error Simulation**
1. Stop the server while on the UI
2. Try to create a pipeline
3. ✅ Network error message displayed
4. ✅ Graceful error handling (no page crash)

**D. Long Prompt**
1. Enter a very long prompt (500+ characters)
2. Submit
3. ✅ Form accepts long input
4. ✅ Display handles long text properly

**E. Special Characters in Prompt**
1. Enter prompt with special chars: `Load "sales.csv" into 'orders' & test`
2. Submit
3. ✅ Special characters handled correctly
4. ✅ No SQL injection or script injection

**Pass Criteria:** All error scenarios handled gracefully with clear feedback

---

### UI TEST 12: Browser Compatibility

**Objective:** Test UI works across different browsers

**Browsers to Test:**
- [ ] Google Chrome (latest)
- [ ] Mozilla Firefox (latest)
- [ ] Microsoft Edge (latest)
- [ ] Safari (if on macOS)

**For Each Browser:**
1. Open `http://localhost:8000/web/`
2. Create a pipeline
3. Run the pipeline
4. View logs
5. Check for visual issues

**Expected Results:**
- ✅ UI renders correctly in all browsers
- ✅ Forms work properly
- ✅ JavaScript functions execute
- ✅ AJAX requests succeed
- ✅ No console errors

**Pass Criteria:** UI functions correctly in all major browsers

---

### UI TEST 13: Mobile Responsiveness

**Objective:** Test UI on mobile devices or responsive view

**Steps:**
1. Open Chrome DevTools (F12)
2. Click "Toggle Device Toolbar" (Ctrl+Shift+M)
3. Select mobile device (iPhone, Android)
4. Test all UI functionality

**Expected Results:**
- ✅ Layout adapts to smaller screen
- ✅ Forms are usable on mobile
- ✅ Buttons are tappable (not too small)
- ✅ Text is readable (no tiny fonts)
- ✅ Navigation works on mobile
- ✅ No horizontal scrolling

**Device Sizes to Test:**
- [ ] Mobile (375x667 - iPhone SE)
- [ ] Tablet (768x1024 - iPad)
- [ ] Desktop (1920x1080)

**Pass Criteria:** UI is usable on mobile and tablet screens

---

### UI TEST 14: Complete User Journey

**Objective:** Perform a complete end-to-end user workflow

**Scenario:** New user wants to import sales data

**Steps:**
1. **Start:** User opens QueryForge web interface
2. **Explore:** User looks around the homepage
3. **Create:** User creates pipeline with prompt: `Load sales.csv into orders table`
4. **Review:** User reviews the generated pipeline steps
5. **Test:** User runs the pipeline in sandbox
6. **Verify:** User checks execution logs for success
7. **Deploy:** User commits to production
8. **Confirm:** User verifies data was imported
9. **History:** User views all their pipelines in the list

**Time the Journey:**
- Start time: ____________
- End time: ____________
- Total duration: ____________ minutes

**User Experience Checklist:**
- [ ] User could complete task without help
- [ ] Instructions/labels were clear
- [ ] No confusing error messages
- [ ] Process felt intuitive
- [ ] Feedback was immediate and helpful
- [ ] User felt confident in the results

**Pass Criteria:** Complete workflow possible without documentation

---

### UI TEST 15: Performance & Load Testing

**Objective:** Test UI performance under load

**Steps:**
1. Create 10 pipelines rapidly (one after another)
2. Observe UI responsiveness
3. Check for memory leaks (DevTools Memory tab)
4. View pipeline list with many items

**Expected Results:**
- ✅ UI remains responsive
- ✅ No significant memory increase
- ✅ List pagination works with many items
- ✅ No browser freezing or lag

**Performance Metrics:**
- [ ] Page load time < 2 seconds
- [ ] Form submission < 1 second
- [ ] List rendering < 1 second
- [ ] No memory leaks after 10 operations

**Pass Criteria:** UI performs well with multiple operations

---

## 📝 UI Test Results Summary

**After completing UI tests, fill out this summary:**

| Test # | Test Name | Status | Notes |
|--------|-----------|--------|-------|
| UI-1 | Homepage Access | ☐ Pass / ☐ Fail | |
| UI-2 | Simple Pipeline Creation | ☐ Pass / ☐ Fail | |
| UI-3 | View Pipeline Details | ☐ Pass / ☐ Fail | |
| UI-4 | Run in Sandbox | ☐ Pass / ☐ Fail | |
| UI-5 | View Execution Logs | ☐ Pass / ☐ Fail | |
| UI-6 | Pipeline with Error | ☐ Pass / ☐ Fail | |
| UI-7 | Trigger Repair | ☐ Pass / ☐ Fail | |
| UI-8 | Pipeline List View | ☐ Pass / ☐ Fail | |
| UI-9 | Multi-Step Pipeline | ☐ Pass / ☐ Fail | |
| UI-10 | Commit to Production | ☐ Pass / ☐ Fail | |
| UI-11 | Error Handling | ☐ Pass / ☐ Fail | |
| UI-12 | Browser Compatibility | ☐ Pass / ☐ Fail | |
| UI-13 | Mobile Responsiveness | ☐ Pass / ☐ Fail | |
| UI-14 | Complete User Journey | ☐ Pass / ☐ Fail | |
| UI-15 | Performance Testing | ☐ Pass / ☐ Fail | |

**Overall UI Test Success Rate:** _____ / 15 (____ %)

**Issues Found:**
1. ________________________________________________
2. ________________________________________________
3. ________________________________________________

**Screenshots Folder:** Create a folder to store test screenshots for documentation.

---

## 📊 Test Results Summary

**After completing all UI tests, document your results here:**

### Overall Results

- **Test Date:** _______________
- **Tester Name:** _______________
- **Browser Used:** _______________
- **Total Tests:** 15
- **Tests Passed:** _____ / 15
- **Tests Failed:** _____ / 15
- **Success Rate:** _____ %

### Test Results Table

| Test # | Test Name | Status | Time (sec) | Notes/Issues |
|--------|-----------|--------|------------|---------------|
| UI-1 | Homepage Access | ☐ Pass / ☐ Fail | | |
| UI-2 | Simple Pipeline Creation | ☐ Pass / ☐ Fail | | |
| UI-3 | View Pipeline Details | ☐ Pass / ☐ Fail | | |
| UI-4 | Run in Sandbox | ☐ Pass / ☐ Fail | | |
| UI-5 | View Execution Logs | ☐ Pass / ☐ Fail | | |
| UI-6 | Pipeline with Error | ☐ Pass / ☐ Fail | | |
| UI-7 | Trigger Repair | ☐ Pass / ☐ Fail | | |
| UI-8 | Pipeline List View | ☐ Pass / ☐ Fail | | |
| UI-9 | Multi-Step Pipeline | ☐ Pass / ☐ Fail | | |
| UI-10 | Commit to Production | ☐ Pass / ☐ Fail | | |
| UI-11 | Error Handling | ☐ Pass / ☐ Fail | | |
| UI-12 | Browser Compatibility | ☐ Pass / ☐ Fail | | |
| UI-13 | Mobile Responsiveness | ☐ Pass / ☐ Fail | | |
| UI-14 | Complete User Journey | ☐ Pass / ☐ Fail | | |
| UI-15 | Performance Testing | ☐ Pass / ☐ Fail | | |

### Critical Issues Found

1. Issue: ________________________________________________
   - Severity: ☐ Critical / ☐ High / ☐ Medium / ☐ Low
   - Impact: ________________________________________________
   - Steps to reproduce: ________________________________________________

2. Issue: ________________________________________________
   - Severity: ☐ Critical / ☐ High / ☐ Medium / ☐ Low
   - Impact: ________________________________________________
   - Steps to reproduce: ________________________________________________

3. Issue: ________________________________________________
   - Severity: ☐ Critical / ☐ High / ☐ Medium / ☐ Low
   - Impact: ________________________________________________
   - Steps to reproduce: ________________________________________________

### User Experience Notes

**What worked well:**
- ________________________________________________
- ________________________________________________
- ________________________________________________

**What needs improvement:**
- ________________________________________________
- ________________________________________________
- ________________________________________________

**Suggestions for enhancement:**
- ________________________________________________
- ________________________________________________
- ________________________________________________

### Screenshots

- [ ] Homepage screenshot saved
- [ ] Pipeline creation screenshot saved
- [ ] Execution results screenshot saved
- [ ] Error message screenshot saved
- [ ] Logs view screenshot saved

### Final Verdict

☐ **READY FOR PRODUCTION** - All critical tests passed, minor issues only  
☐ **NEEDS FIXES** - Some important issues need to be addressed  
☐ **NOT READY** - Critical issues found, requires significant work

### Tester Sign-off

**Name:** _______________  
**Date:** _______________  
**Signature:** _______________

---

## 💡 Quick Reference

### Start Server
```bash
uvicorn app.main:app --reload
```

### Access Web UI
```
http://localhost:8000/web/
```

### View API Docs
```
http://localhost:8000/docs
```

### Check Database
```bash
sqlite3 queryforge.db ".tables"
sqlite3 queryforge.db "SELECT * FROM Pipelines LIMIT 5;"
```

### Recommended Test Prompt
```
Load sales.csv into orders table
```

---

**Happy Testing!** 🎉👍

