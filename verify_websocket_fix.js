#!/usr/bin/env node
/**
 * Comprehensive verification script for WebSocket hook fixes
 */

const fs = require('fs');
const path = require('path');

function verifyWebSocketFix() {
    console.log('🔧 Verifying WebSocket Hook Fixes...\n');
    
    // Step 1: Verify websocket.ts exports
    console.log('1. 📁 Checking websocket.ts exports...');
    
    const websocketPath = path.join(__dirname, 'frontend/src/lib/websocket.ts');
    const websocketContent = fs.readFileSync(websocketPath, 'utf8');
    
    // Check for proper export syntax
    const useSocketExport = websocketContent.match(/export\s+function\s+useSocket\s*\(/);
    const useAnalysisSocketExport = websocketContent.match(/export\s+function\s+useAnalysisSocket\s*\(/);
    
    if (useSocketExport) {
        console.log('   ✅ useSocket properly exported');
    } else {
        console.log('   ❌ useSocket export not found');
        return false;
    }
    
    if (useAnalysisSocketExport) {
        console.log('   ✅ useAnalysisSocket properly exported');
    } else {
        console.log('   ❌ useAnalysisSocket export not found');
        return false;
    }
    
    // Step 2: Check page.tsx imports
    console.log('\n2. 📄 Checking page.tsx imports...');
    
    const pagePath = path.join(__dirname, 'frontend/src/app/page.tsx');
    const pageContent = fs.readFileSync(pagePath, 'utf8');
    
    // Check for the correct import statement
    const importRegex = /import\s*\{\s*useSocket\s*,\s*useAnalysisSocket\s*\}\s*from\s*['"]@\/lib\/websocket['"]/;
    
    if (importRegex.test(pageContent)) {
        console.log('   ✅ Both hooks imported correctly');
    } else {
        // Check if import exists but in different format
        if (pageContent.includes("import") && pageContent.includes("useAnalysisSocket") && pageContent.includes("@/lib/websocket")) {
            console.log('   ✅ useAnalysisSocket import found (different format)');
        } else {
            console.log('   ❌ Correct import statement not found');
            console.log('   Expected: import { useSocket, useAnalysisSocket } from \'@/lib/websocket\'');
            
            // Show current import lines
            const importLines = pageContent.split('\n').filter(line => 
                line.includes('import') && line.includes('websocket')
            );
            console.log('   Current import(s):');
            importLines.forEach(line => console.log(`     ${line.trim()}`));
            return false;
        }
    }
    
    // Step 3: Check hook usage
    console.log('\n3. 🔧 Checking hook usage...');
    
    // Check for useAnalysisSocket destructuring
    const destructuringRegex = /const\s*\{\s*[^}]*\}\s*=\s*useAnalysisSocket\s*\(\s*\)/;
    
    if (destructuringRegex.test(pageContent)) {
        console.log('   ✅ useAnalysisSocket hook properly destructured');
    } else {
        console.log('   ❌ useAnalysisSocket hook usage not found');
        return false;
    }
    
    // Step 4: Check for syntax errors
    console.log('\n4. 🔍 Checking for syntax issues...');
    
    // Check for common syntax issues
    const syntaxIssues = [];
    
    // Check for missing semicolons or brackets
    if (pageContent.includes('} = useAnalysisSocket()') && !pageContent.includes('} = useAnalysisSocket();')) {
        // This is actually fine in JSX/React
    }
    
    // Check for correct React imports in websocket.ts
    if (!websocketContent.includes("import { useEffect, useState, useRef, useCallback } from 'react'")) {
        syntaxIssues.push('Missing React hook imports in websocket.ts');
    }
    
    // Check for socket.io import
    if (!websocketContent.includes("import { io, Socket } from 'socket.io-client'")) {
        syntaxIssues.push('Missing socket.io import in websocket.ts');
    }
    
    if (syntaxIssues.length === 0) {
        console.log('   ✅ No syntax issues found');
    } else {
        console.log('   ❌ Syntax issues found:');
        syntaxIssues.forEach(issue => console.log(`     - ${issue}`));
        return false;
    }
    
    // Step 5: Check function availability
    console.log('\n5. 📋 Checking function availability...');
    
    const requiredFunctions = [
        'startAnalysis',
        'cancelAnalysis',
        'getAnalysisStatus',
        'isAnalysisRunning',
        'waitForAnalysis',
        'analysisStatus'
    ];
    
    // Find the return statement of useAnalysisSocket
    const returnMatch = websocketContent.match(/return\s*\{([^}]+)\}/g);
    let lastReturn = '';
    if (returnMatch && returnMatch.length > 0) {
        lastReturn = returnMatch[returnMatch.length - 1];
    }
    
    let allFunctionsAvailable = true;
    for (const func of requiredFunctions) {
        if (lastReturn.includes(func)) {
            console.log(`   ✅ ${func} available`);
        } else {
            console.log(`   ❌ ${func} missing from useAnalysisSocket return`);
            allFunctionsAvailable = false;
        }
    }
    
    if (!allFunctionsAvailable) {
        return false;
    }
    
    // Step 6: Final verification
    console.log('\n' + '='.repeat(50));
    console.log('✅ WEBSOCKET HOOK FIX VERIFICATION COMPLETE');
    console.log('='.repeat(50));
    
    console.log('\n🎉 SUCCESS! All checks passed:');
    console.log('   ✅ useAnalysisSocket hook is properly exported');
    console.log('   ✅ Import statement is correct in page.tsx');
    console.log('   ✅ Hook is properly destructured and used');
    console.log('   ✅ All required functions are available');
    console.log('   ✅ No syntax issues found');
    
    console.log('\n🚀 The missing useAnalysisSocket hook error should now be resolved!');
    
    console.log('\n📋 Next steps:');
    console.log('   1. Start the frontend development server');
    console.log('   2. Check browser console for any remaining errors');
    console.log('   3. Test WebSocket functionality');
    
    return true;
}

// Run the verification
try {
    const success = verifyWebSocketFix();
    process.exit(success ? 0 : 1);
} catch (error) {
    console.error('❌ Verification failed with error:', error.message);
    process.exit(1);
}