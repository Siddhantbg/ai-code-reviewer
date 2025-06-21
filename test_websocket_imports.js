#!/usr/bin/env node
/**
 * Simple test to verify WebSocket imports are working correctly
 */

const fs = require('fs');
const path = require('path');

function testWebSocketImports() {
    console.log('🧪 Testing WebSocket Hook Imports...\n');
    
    let allTestsPassed = true;
    
    // Test 1: Check websocket.ts exports
    console.log('📁 Checking websocket.ts exports...');
    
    const websocketPath = path.join(__dirname, 'frontend/src/lib/websocket.ts');
    
    if (!fs.existsSync(websocketPath)) {
        console.log('   ❌ websocket.ts file not found');
        allTestsPassed = false;
    } else {
        const websocketContent = fs.readFileSync(websocketPath, 'utf8');
        
        // Check for useSocket export
        if (websocketContent.includes('export function useSocket(')) {
            console.log('   ✅ useSocket hook exported');
        } else {
            console.log('   ❌ useSocket hook not found');
            allTestsPassed = false;
        }
        
        // Check for useAnalysisSocket export
        if (websocketContent.includes('export function useAnalysisSocket(')) {
            console.log('   ✅ useAnalysisSocket hook exported');
        } else {
            console.log('   ❌ useAnalysisSocket hook not found');
            allTestsPassed = false;
        }
        
        // Check for required functions in useAnalysisSocket return
        const requiredFunctions = [
            'startAnalysis',
            'cancelAnalysis', 
            'getAnalysisStatus',
            'isAnalysisRunning',
            'waitForAnalysis',
            'analysisStatus'
        ];
        
        let returnBlockFound = false;
        const returnMatch = websocketContent.match(/return\s*\{[\s\S]*?\}/g);
        if (returnMatch && returnMatch.length > 0) {
            const lastReturn = returnMatch[returnMatch.length - 1];
            returnBlockFound = true;
            
            for (const func of requiredFunctions) {
                if (lastReturn.includes(func)) {
                    console.log(`   ✅ ${func} included in return`);
                } else {
                    console.log(`   ❌ ${func} missing from return`);
                    allTestsPassed = false;
                }
            }
        }
        
        if (!returnBlockFound) {
            console.log('   ❌ Could not find return statement in useAnalysisSocket');
            allTestsPassed = false;
        }
    }
    
    console.log('\n📄 Checking page.tsx imports...');
    
    // Test 2: Check page.tsx imports
    const pagePath = path.join(__dirname, 'frontend/src/app/page.tsx');
    
    if (!fs.existsSync(pagePath)) {
        console.log('   ❌ page.tsx file not found');
        allTestsPassed = false;
    } else {
        const pageContent = fs.readFileSync(pagePath, 'utf8');
        
        // Check for import statement
        if (pageContent.includes("import { useSocket, useAnalysisSocket } from '@/lib/websocket'")) {
            console.log('   ✅ Both hooks imported correctly');
        } else if (pageContent.includes("useAnalysisSocket") && pageContent.includes("from '@/lib/websocket'")) {
            console.log('   ✅ useAnalysisSocket import found');
        } else if (pageContent.includes("useSocket") && !pageContent.includes("useAnalysisSocket")) {
            console.log('   ❌ useAnalysisSocket missing from import');
            allTestsPassed = false;
        } else {
            console.log('   ❌ WebSocket imports not found');
            allTestsPassed = false;
        }
        
        // Check for hook usage
        if (pageContent.includes('} = useAnalysisSocket()')) {
            console.log('   ✅ useAnalysisSocket hook used correctly');
        } else {
            console.log('   ❌ useAnalysisSocket hook usage not found');
            allTestsPassed = false;
        }
        
        // Check for destructured variables
        const destructuredVars = [
            'startAnalysis',
            'cancelAnalysis',
            'getAnalysisStatus', 
            'isAnalysisRunning',
            'analysisStatus'
        ];
        
        for (const varName of destructuredVars) {
            if (pageContent.includes(varName)) {
                console.log(`   ✅ ${varName} variable found`);
            } else {
                console.log(`   ⚠️  ${varName} variable not found (may be unused)`);
            }
        }
    }
    
    console.log('\n🔍 Checking for potential syntax issues...');
    
    // Test 3: Check for common syntax issues
    if (fs.existsSync(pagePath)) {
        const pageContent = fs.readFileSync(pagePath, 'utf8');
        
        // Check for missing imports that are used
        const usedFunctions = ['startAnalysis', 'cancelAnalysis', 'getAnalysisStatus', 'isAnalysisRunning', 'analysisStatus'];
        const importedFunctions = [];
        
        const importMatch = pageContent.match(/import\s*\{([^}]+)\}\s*from\s*['"]@\/lib\/websocket['"]/);
        if (importMatch) {
            const importedItems = importMatch[1].split(',').map(item => item.trim());
            importedFunctions.push(...importedItems);
        }
        
        for (const func of usedFunctions) {
            const isUsed = pageContent.includes(func) && !pageContent.includes(`// ${func}`);
            const isImported = importedFunctions.some(imp => imp.includes(func));
            
            if (isUsed && !isImported) {
                console.log(`   ❌ ${func} is used but not imported`);
                allTestsPassed = false;
            }
        }
        
        console.log('   ✅ No obvious syntax issues found');
    }
    
    // Final assessment
    console.log('\n' + '='.repeat(50));
    console.log('📊 TEST RESULTS');
    console.log('='.repeat(50));
    
    if (allTestsPassed) {
        console.log('🎉 ALL TESTS PASSED!');
        console.log('✅ useAnalysisSocket hook is properly exported');
        console.log('✅ Import statement is correct in page.tsx');
        console.log('✅ Hook usage appears to be correct');
        console.log('\n🚀 The WebSocket hooks should now work without import errors');
    } else {
        console.log('⚠️ SOME TESTS FAILED');
        console.log('🔧 Please review the issues above');
    }
    
    return allTestsPassed;
}

// Run the test
try {
    const success = testWebSocketImports();
    process.exit(success ? 0 : 1);
} catch (error) {
    console.error('❌ Test failed with error:', error.message);
    process.exit(1);
}