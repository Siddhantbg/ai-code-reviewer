# Complete Analysis Workflow Test Scenarios

This document provides comprehensive test scenarios to verify the complete analysis workflow from start to finish, ensuring WebSocket connection stability, successful analysis completion, proper result display, and optimal resource usage.

## 🚀 Setup Instructions

### Prerequisites
1. Backend dependencies installed
2. Frontend dependencies installed  
3. Port 8000 available for backend
4. Port 3000 available for frontend

### Starting the System
```bash
# Terminal 1 - Backend
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2 - Frontend  
cd frontend
npm run dev

# Terminal 3 - Optional: Resource monitoring
top -p $(pgrep -f "uvicorn\|node")
```

## 📋 Test Scenarios

### Test Scenario 1: Basic Analysis Workflow ✅
**Objective**: Verify end-to-end analysis works correctly

**Steps**:
1. Open http://localhost:3000
2. Verify connection status shows "Connected" in header
3. Paste simple test code:
```python
def hello_world():
    return "Hello, World!"

def add_numbers(a, b):
    return a + b
```
4. Click "Analyze Code" or press Ctrl+Enter
5. Observe progress updates in real-time
6. Wait for analysis completion

**Expected Results**:
- ✅ Connection indicator shows "Connected"
- ✅ Analysis starts immediately
- ✅ Progress bar updates smoothly
- ✅ Analysis completes within 30 seconds
- ✅ Results display properly with score and suggestions
- ✅ No disconnection warnings appear
- ✅ WebSocket events flow continuously

---

### Test Scenario 2: Complex Code Analysis 🧪
**Objective**: Test analysis with security vulnerabilities and complex code

**Steps**:
1. Paste complex test code with vulnerabilities:
```python
import os
import sqlite3

def vulnerable_login(username, password):
    # SQL Injection vulnerability
    conn = sqlite3.connect('users.db')
    query = "SELECT * FROM users WHERE username = '" + username + "' AND password = '" + password + "'"
    result = conn.execute(query).fetchone()
    
    # Command injection vulnerability  
    os.system("echo 'Login attempt: " + username + "'")
    
    # Division by zero risk
    score = 100 / 0
    
    return result

def risky_file_access(filename):
    # Path traversal vulnerability
    with open("/uploads/" + filename, 'r') as f:
        return f.read()

class DataProcessor:
    def __init__(self):
        # Hardcoded secret
        self.api_key = "sk-1234567890abcdef"
        
    def process_data(self, data):
        # Potential XSS if this were web code
        return "<div>" + data + "</div>"
```

2. Start analysis and monitor resource usage
3. Wait for completion

**Expected Results**:
- ✅ Analysis detects multiple security vulnerabilities
- ✅ Critical issues are flagged (SQL injection, command injection)
- ✅ Overall score is low (1-3 out of 10)
- ✅ Specific suggestions provided for each vulnerability
- ✅ Analysis completes despite complex code
- ✅ Resource usage remains reasonable

---

### Test Scenario 3: Connection Stability During Long Analysis 🔗
**Objective**: Verify WebSocket connection remains stable during extended analysis

**Steps**:
1. Paste very large or complex code (1000+ lines)
2. Start analysis
3. Monitor connection status during analysis
4. Check browser developer tools Network tab
5. Watch for any disconnection/reconnection events
6. Wait for completion

**Expected Results**:
- ✅ Connection status remains "Connected" throughout
- ✅ No disconnection warnings appear
- ✅ Progress updates continue flowing
- ✅ Analysis completes successfully
- ✅ Results are displayed properly
- ✅ No WebSocket errors in browser console

---

### Test Scenario 4: Connection Recovery Testing 🔄
**Objective**: Test connection recovery during analysis

**Steps**:
1. Start a medium-complexity analysis
2. After 10-15 seconds, simulate connection issues:
   - Option A: Temporarily stop backend server (Ctrl+C)
   - Option B: Disconnect network briefly
   - Option C: Close browser tab and reopen
3. Restart backend/reconnect network after 5-10 seconds  
4. Observe connection recovery
5. Check if analysis results are still delivered

**Expected Results**:
- ✅ Connection monitor shows disconnection warning
- ✅ Auto-reconnection attempts visible (up to 3 tries)
- ✅ "Reconnect" button appears and works
- ✅ After reconnection, analysis status is checked
- ✅ Analysis result is delivered when backend reconnects
- ✅ User gets clear feedback about connection issues

---

### Test Scenario 5: Resource Optimization Verification 📊
**Objective**: Verify CPU and memory optimizations are working

**Steps**:
1. Monitor system resources before starting:
```bash
# In separate terminal
htop
# or
top -p $(pgrep -f "uvicorn")
```

2. Run multiple analyses simultaneously:
   - Open 2-3 browser tabs
   - Start analysis in each tab
   - Use different code samples

3. Monitor resource usage during analyses
4. Check for memory leaks after completion

**Expected Results**:
- ✅ CPU usage stays below 200% total
- ✅ Memory usage increases by less than 500MB during analysis
- ✅ Only 1 concurrent AI operation runs (others queued)
- ✅ Memory is cleaned up after analysis completion
- ✅ CPU throttling delays are visible in logs
- ✅ System remains responsive

---

### Test Scenario 6: Result Display and Interaction 🎨
**Objective**: Verify analysis results display correctly and are interactive

**Steps**:
1. Complete analysis with code that has various issue types
2. Examine results display:
   - Overall score
   - Issue breakdown by severity
   - Individual issue details
   - Code suggestions
   - Metrics display

3. Test interactive features:
   - Expand/collapse issue details
   - Copy code suggestions
   - Export results (if available)
   - Analysis history

**Expected Results**:
- ✅ Overall score prominently displayed
- ✅ Issues categorized by type and severity
- ✅ Detailed descriptions for each issue
- ✅ Actionable suggestions provided
- ✅ Code metrics accurately calculated
- ✅ Interactive elements work smoothly
- ✅ Results are well-formatted and readable

---

### Test Scenario 7: Error Handling and Edge Cases ⚠️
**Objective**: Test system behavior with invalid inputs and error conditions

**Steps**:
1. Test with empty code input
2. Test with extremely large code files (>10MB)
3. Test with invalid/corrupted code
4. Test unsupported language selection
5. Test rapid successive analysis requests
6. Test analysis cancellation

**Expected Results**:
- ✅ Appropriate error messages for invalid inputs
- ✅ System gracefully handles large files
- ✅ Syntax errors are handled properly  
- ✅ Rate limiting works correctly
- ✅ Analysis cancellation works immediately
- ✅ No system crashes or hangs
- ✅ User receives clear feedback for all scenarios

---

## 🔧 Troubleshooting Guide

### Common Issues and Solutions

**Issue**: WebSocket connection fails
- Check backend is running on port 8000
- Verify no firewall blocking connections
- Check browser console for CORS errors

**Issue**: Analysis never completes
- Check backend logs for errors
- Verify AI model is properly loaded
- Check for resource exhaustion

**Issue**: High CPU/Memory usage
- Verify optimization settings are applied
- Check for concurrent analysis limits
- Monitor for memory leaks

**Issue**: Results not displaying
- Check browser console for JavaScript errors
- Verify WebSocket events are received
- Check for result parsing errors

## ✅ Success Criteria

A successful test run should demonstrate:

1. **Connection Stability**: WebSocket maintains connection throughout analysis
2. **Analysis Completion**: All analyses complete successfully within reasonable time
3. **Resource Efficiency**: CPU < 200%, Memory spike < 500MB
4. **Error Recovery**: Connection issues are detected and recovered automatically
5. **Result Accuracy**: Analysis finds expected issues and provides useful suggestions
6. **User Experience**: Clear feedback, smooth interactions, no confusing errors

## 📊 Performance Benchmarks

**Target Performance Metrics**:
- Simple analysis (< 100 lines): Complete in < 15 seconds
- Complex analysis (< 1000 lines): Complete in < 60 seconds  
- CPU usage peak: < 200% during analysis
- Memory increase: < 500MB during analysis
- Connection stability: > 99% uptime during analysis
- Recovery time: < 10 seconds after connection loss

## 🎯 Final Validation

After completing all test scenarios, the system should demonstrate:

✅ **Stable WebSocket connections** throughout the entire analysis flow
✅ **Successful analysis completion** for all code types and sizes  
✅ **Proper result display** with accurate issue detection and suggestions
✅ **Optimized resource usage** within defined limits
✅ **Robust error handling** for edge cases and connection issues
✅ **Smooth user experience** with clear feedback and responsive interactions

**If all scenarios pass, the complete analysis workflow is verified and ready for production use!** 🎉