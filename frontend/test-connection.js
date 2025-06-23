// Test script to verify connection and analysis state management
// Run with: node test-connection.js

const { createServer } = require('http');
const { Server } = require('socket.io');

// Create a simple test server to simulate backend
const httpServer = createServer();
const io = new Server(httpServer, {
  cors: {
    origin: "http://localhost:3000",
    methods: ["GET", "POST"]
  }
});

let analysisCount = 0;

io.on('connection', (socket) => {
  console.log(`🔌 Client connected: ${socket.id}`);
  
  // Simulate analysis workflow
  socket.on('start_analysis', (data) => {
    analysisCount++;
    console.log(`📊 Analysis ${analysisCount} started:`, data.analysisId);
    
    // Simulate analysis progress
    let progress = 0;
    const progressInterval = setInterval(() => {
      progress += 20;
      
      socket.emit('analysis_progress', {
        analysisId: data.analysisId,
        progress,
        message: `Processing ${data.language} code...`,
        stage: progress < 50 ? 'parsing' : progress < 80 ? 'analyzing' : 'finalizing'
      });
      
      if (progress >= 100) {
        clearInterval(progressInterval);
        
        // Send completion after short delay
        setTimeout(() => {
          socket.emit('analysis_complete', {
            analysisId: data.analysisId,
            result: {
              analysis_id: data.analysisId,
              issues: [
                {
                  id: 'test-1',
                  type: 'bug',
                  severity: 'medium',
                  title: 'Test issue',
                  description: 'This is a test issue',
                  line_number: 1,
                  confidence: 0.8
                }
              ],
              metrics: {
                lines_of_code: data.code.split('\n').length,
                complexity_score: 2.5,
                maintainability_index: 75.0,
                duplication_percentage: 0.0
              },
              summary: {
                total_issues: 1,
                critical_issues: 0,
                high_issues: 0,
                medium_issues: 1,
                low_issues: 0,
                overall_score: 7.5,
                recommendation: 'Good code quality with minor improvements needed'
              },
              suggestions: ['Consider adding unit tests', 'Add code documentation']
            }
          });
          
          console.log(`✅ Analysis ${analysisCount} completed:`, data.analysisId);
        }, 500);
      }
    }, 800);
  });
  
  socket.on('cancel_analysis', (data) => {
    console.log(`🛑 Analysis cancelled:`, data.analysisId);
    socket.emit('analysis_cancelled', data);
  });
  
  socket.on('check_analysis_status', (data) => {
    console.log(`🔍 Status check requested:`, data.analysisId);
    // Simulate status response
    socket.emit('analysis_error', {
      analysisId: data.analysisId,
      error: 'Analysis not found - may have completed during disconnection'
    });
  });
  
  socket.on('disconnect', (reason) => {
    console.log(`🔌 Client disconnected: ${socket.id}, reason: ${reason}`);
  });
});

const PORT = 8000;
httpServer.listen(PORT, () => {
  console.log(`🚀 Test WebSocket server running on port ${PORT}`);
  console.log(`📝 Run this with frontend to test multiple analysis workflows`);
  console.log(`⚠️  Make sure to stop the real backend first`);
  console.log(`🔄 This server simulates:
  - WebSocket connection/disconnection
  - Analysis progress updates
  - Analysis completion
  - Reconnection handling
  - Multiple concurrent analyses`);
});

// Handle graceful shutdown
process.on('SIGINT', () => {
  console.log('\n🛑 Shutting down test server...');
  httpServer.close(() => {
    console.log('✅ Test server closed');
    process.exit(0);
  });
});