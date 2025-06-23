// frontend/src/lib/websocket.ts
import { useEffect, useState, useRef, useCallback } from 'react'
import socketIO from 'socket.io-client'

type Socket = SocketIOClient.Socket

interface UseSocketReturn {
  socket: Socket | null
  connected: boolean
  error: string | null
  connecting: boolean
  reconnectWebSocket: () => void
}

interface AnalysisProgress {
  analysisId: string
  progress: number
  message: string
  stage: string
}

interface AnalysisComplete {
  analysisId: string
  result: any
}

interface AnalysisError {
  analysisId: string
  error: string
}

export function useSocket(url?: string): UseSocketReturn {
  const [connected, setConnected] = useState(false)
  const [connecting, setConnecting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const socketRef = useRef<Socket | null>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const maxReconnectAttempts = 8  // Increased from 3 to 8
  const reconnectAttemptsRef = useRef(0)
  const isManualDisconnect = useRef(false)
  const lastPingTimeRef = useRef<number>(0)
  const heartbeatIntervalRef = useRef<NodeJS.Timeout | null>(null)
  
  // Enhanced reconnection state tracking
  const connectionStateRef = useRef<'disconnected' | 'connecting' | 'connected' | 'reconnecting'>('disconnected')
  const lastConnectionAttemptRef = useRef<number>(0)
  const consecutiveFailuresRef = useRef(0)
  const lastSuccessfulConnectionRef = useRef<number>(0)
  const backoffStrategyRef = useRef<'linear' | 'exponential' | 'adaptive'>('adaptive')
  const connectionHealthRef = useRef<'healthy' | 'degraded' | 'unstable' | 'failed'>('healthy')

  const getSocketUrl = useCallback(() => {
    const baseUrl = url || process.env.NEXT_PUBLIC_WS_URL || 'http://localhost:8000'
    
    if (baseUrl.startsWith('https://')) {
      return baseUrl.replace('https://', 'wss://') 
    } else if (baseUrl.startsWith('http://')) {
      return baseUrl.replace('http://', 'ws://')
    }
    
    return baseUrl
  }, [url])

  // Advanced backoff calculation with jitter and adaptive strategies
  const calculateReconnectDelay = useCallback(() => {
    const attempt = reconnectAttemptsRef.current
    const baseDelay = 1000 // 1 second base delay
    const maxDelay = 60000 // 1 minute maximum delay
    const jitterMax = 0.3 // 30% jitter
    
    let delay: number
    
    switch (backoffStrategyRef.current) {
      case 'linear':
        delay = Math.min(baseDelay * (attempt + 1), maxDelay)
        break
        
      case 'exponential':
        delay = Math.min(baseDelay * Math.pow(2, attempt), maxDelay)
        break
        
      case 'adaptive':
      default:
        const timeSinceLastSuccess = Date.now() - lastSuccessfulConnectionRef.current
        const healthMultiplier = connectionHealthRef.current === 'failed' ? 3 : 
                                connectionHealthRef.current === 'unstable' ? 2 : 
                                connectionHealthRef.current === 'degraded' ? 1.5 : 1
        
        // Use exponential backoff with health-based multiplier
        delay = Math.min(baseDelay * Math.pow(1.8, attempt) * healthMultiplier, maxDelay)
        
        // If connection has been failing for too long, increase delay significantly
        if (timeSinceLastSuccess > 300000) { // 5 minutes
          delay = Math.min(delay * 2, maxDelay)
        }
        break
    }
    
    // Add jitter to prevent thundering herd
    const jitter = delay * jitterMax * Math.random()
    const finalDelay = delay + jitter
    
    console.log(`🔄 Calculated reconnect delay: ${finalDelay.toFixed(0)}ms (attempt ${attempt + 1}, strategy: ${backoffStrategyRef.current}, health: ${connectionHealthRef.current})`)
    
    return finalDelay
  }, [])
  
  // Connection state validation and rate limiting
  const canAttemptConnection = useCallback(() => {
    const now = Date.now()
    const timeSinceLastAttempt = now - lastConnectionAttemptRef.current
    const minTimeBetweenAttempts = 500 // Minimum 500ms between attempts
    
    // Prevent connection storms
    if (timeSinceLastAttempt < minTimeBetweenAttempts) {
      console.warn(`⚠️ Connection rate limited: Only ${timeSinceLastAttempt}ms since last attempt`)
      return false
    }
    
    // Check if we're already in a connecting state
    if (connectionStateRef.current === 'connecting' || connectionStateRef.current === 'reconnecting') {
      console.warn('⚠️ Connection already in progress')
      return false
    }
    
    // Check if we've exceeded maximum attempts
    if (reconnectAttemptsRef.current >= maxReconnectAttempts) {
      console.warn(`⚠️ Maximum reconnection attempts (${maxReconnectAttempts}) exceeded`)
      return false
    }
    
    // Check for manual disconnect
    if (isManualDisconnect.current) {
      console.log('🛑 Manual disconnect active - blocking reconnection')
      return false
    }
    
    return true
  }, [])
  
  // Update connection health based on performance
  const updateConnectionHealth = useCallback(() => {
    const failures = consecutiveFailuresRef.current
    const timeSinceLastSuccess = Date.now() - lastSuccessfulConnectionRef.current
    
    if (failures === 0 && timeSinceLastSuccess < 60000) {
      connectionHealthRef.current = 'healthy'
    } else if (failures <= 2 && timeSinceLastSuccess < 300000) {
      connectionHealthRef.current = 'degraded'
    } else if (failures <= 5 && timeSinceLastSuccess < 600000) {
      connectionHealthRef.current = 'unstable'
    } else {
      connectionHealthRef.current = 'failed'
    }
    
    // Adjust backoff strategy based on health
    if (connectionHealthRef.current === 'failed') {
      backoffStrategyRef.current = 'exponential'
    } else if (connectionHealthRef.current === 'unstable') {
      backoffStrategyRef.current = 'adaptive'
    } else {
      backoffStrategyRef.current = 'linear'
    }
  }, [])

  const connect = useCallback(() => {
    // Validate connection attempt
    if (!canAttemptConnection()) {
      return
    }

    if (socketRef.current?.connected) {
      console.log('🔌 Socket already connected')
      connectionStateRef.current = 'connected'
      return
    }

    // Update connection state and timing
    const now = Date.now()
    lastConnectionAttemptRef.current = now
    connectionStateRef.current = reconnectAttemptsRef.current > 0 ? 'reconnecting' : 'connecting'
    
    setConnecting(true)
    setError(null)
    isManualDisconnect.current = false
    
    // Update connection health before attempt
    updateConnectionHealth()

    const socketUrl = getSocketUrl()
    console.log(`🚀 Attempting to connect to: ${socketUrl} (attempt ${reconnectAttemptsRef.current + 1}/${maxReconnectAttempts}, health: ${connectionHealthRef.current})`)
    
    try {
      socketRef.current = socketIO(socketUrl, {
        transports: ['websocket', 'polling'], // Ensure polling fallback
        upgrade: true,
        timeout: 45000, // INCREASED from 20s to 45s for AI processing initialization
        forceNew: false,
        autoConnect: true,
        reconnection: false, // Using custom reconnection logic
        query: {
          clientType: 'react-frontend',
          timestamp: Date.now(),
          supportsLongAnalysis: true // Indicate support for long analysis operations
        }
      } as any) // Temporary fix for TypeScript compatibility

      const socket = socketRef.current

      socket.on('connect', () => {
        const now = Date.now()
        console.log('✅ WebSocket connected successfully:', socket.id)
        
        // Update connection state and reset counters
        connectionStateRef.current = 'connected'
        setConnected(true)
        setConnecting(false)
        setError(null)
        
        // Reset failure tracking on successful connection
        reconnectAttemptsRef.current = 0
        consecutiveFailuresRef.current = 0
        lastSuccessfulConnectionRef.current = now
        connectionHealthRef.current = 'healthy'
        backoffStrategyRef.current = 'linear'
        
        // Clear any pending reconnection attempts
        if (reconnectTimeoutRef.current) {
          clearTimeout(reconnectTimeoutRef.current)
          reconnectTimeoutRef.current = null
        }
        
        console.log(`📊 Connection stats reset - Health: ${connectionHealthRef.current}, Strategy: ${backoffStrategyRef.current}`)
        
        // Start heartbeat monitoring
        startHeartbeatMonitoring()
      })

      socket.on('disconnect', (reason: string, details?: any) => {
        console.log('🔌 WebSocket disconnected:', reason, details)
        setConnected(false)
        setConnecting(false)
        connectionStateRef.current = 'disconnected'
        
        // Update failure tracking
        consecutiveFailuresRef.current++
        updateConnectionHealth()
        
        // Stop heartbeat monitoring
        stopHeartbeatMonitoring()
        
        if (reason === 'io client disconnect' || isManualDisconnect.current) {
          console.log('🛑 Manual disconnect - not reconnecting')
          return
        }
        
        if (reason === 'transport close' && process.env.NODE_ENV === 'development') {
          console.log('🔧 Development mode - reduced reconnection attempts')
          return
        }
        
        // Check if we can attempt reconnection
        if (!canAttemptConnection()) {
          console.warn('⚠️ Cannot attempt reconnection - validation failed')
          setError('Connection lost. Please refresh the page to reconnect.')
          return
        }
        
        if (reconnectAttemptsRef.current < maxReconnectAttempts) {
          const delay = calculateReconnectDelay()
          console.log(`🔄 Scheduling sophisticated reconnection attempt ${reconnectAttemptsRef.current + 1}/${maxReconnectAttempts} in ${delay.toFixed(0)}ms`)
          console.log(`📊 Connection health: ${connectionHealthRef.current}, Strategy: ${backoffStrategyRef.current}`)
          
          reconnectTimeoutRef.current = setTimeout(() => {
            if (canAttemptConnection()) {
              reconnectAttemptsRef.current++
              connectionStateRef.current = 'reconnecting'
              connect()
            } else {
              console.warn('⚠️ Reconnection attempt blocked by validation')
              setError('Connection lost. Please refresh the page to reconnect.')
            }
          }, delay)
        } else {
          console.error('❌ Maximum reconnection attempts exceeded')
          connectionHealthRef.current = 'failed'
          setError('Connection lost after multiple attempts. Please refresh the page to reconnect.')
        }
      })

      socket.on('connect_error', (err: any) => {
        console.error('❌ WebSocket connection error:', err)
        setConnected(false)
        setConnecting(false)
        connectionStateRef.current = 'disconnected'
        
        // Update failure tracking
        consecutiveFailuresRef.current++
        updateConnectionHealth()
        
        let errorMessage = 'Connection failed'
        
        if (err.message.includes('ECONNREFUSED')) {
          errorMessage = 'Backend server is not running. Please start the server and try again.'
          connectionHealthRef.current = 'failed'
        } else if (err.message.includes('CORS')) {
          errorMessage = 'CORS error: Check backend CORS configuration.'
          connectionHealthRef.current = 'failed'
        } else if (err.message.includes('timeout')) {
          errorMessage = 'Connection timeout: Server might be overloaded.'
        } else {
          errorMessage = `Connection error: ${err.message}`
        }
        
        setError(errorMessage)
        
        // Check if we can attempt reconnection
        if (!canAttemptConnection()) {
          console.warn('⚠️ Cannot attempt reconnection after error - validation failed')
          return
        }
        
        if (reconnectAttemptsRef.current < maxReconnectAttempts) {
          const delay = calculateReconnectDelay()
          console.log(`🔄 Scheduling sophisticated reconnection after error in ${delay.toFixed(0)}ms`)
          console.log(`📊 Error recovery - Health: ${connectionHealthRef.current}, Strategy: ${backoffStrategyRef.current}`)
          
          reconnectTimeoutRef.current = setTimeout(() => {
            if (canAttemptConnection()) {
              reconnectAttemptsRef.current++
              connectionStateRef.current = 'reconnecting'
              connect()
            } else {
              console.warn('⚠️ Error recovery reconnection blocked by validation')
            }
          }, delay)
        } else {
          console.error('❌ Maximum error recovery attempts exceeded')
          connectionHealthRef.current = 'failed'
        }
      })

      socket.on('error', (err: any) => {
        console.error('❌ WebSocket error:', err)
        setError(`Socket error: ${err.message || err}`)
      })

      socket.on('ping', () => {
        console.log('📡 Ping received from server')
        lastPingTimeRef.current = Date.now()
        socket.emit('pong')
      })
      
      socket.on('pong', () => {
        console.log('📡 Pong received from server')
        lastPingTimeRef.current = Date.now()
      })

      socket.on('notification', (data: any) => {
        console.log('📢 Notification:', data)
      })

    } catch (err) {
      console.error('❌ Failed to create WebSocket connection:', err)
      setError('Failed to initialize WebSocket connection')
      setConnecting(false)
    }
  }, [getSocketUrl])
  
  const startHeartbeatMonitoring = useCallback(() => {
    // Clear existing heartbeat monitoring
    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current)
    }
    
    lastPingTimeRef.current = Date.now()
    
    // Check connection health every 30 seconds
    heartbeatIntervalRef.current = setInterval(() => {
      const now = Date.now()
      const timeSinceLastPing = now - lastPingTimeRef.current
      
      // Check if any analysis is currently running to adjust timeout
      // Note: analysisStatus comes from useAnalysisSocket hook, this is just for heartbeat monitoring
      const hasRunningAnalysis = false // Simplified for heartbeat - analysis-aware timeout handled elsewhere
      
      // Use longer timeout during analysis to prevent disconnection during heavy processing
      const pingTimeoutMs = hasRunningAnalysis ? 300000 : 180000 // 5 minutes during analysis, 3 minutes normal
      
      if (timeSinceLastPing > pingTimeoutMs) {
        console.warn('⚠️ Connection appears stale, no ping/pong activity detected')
        console.warn(`📊 Stale connection detected: ${timeSinceLastPing}ms since last ping (threshold: ${pingTimeoutMs}ms)`)
        
        // Update connection health to reflect stale connection
        consecutiveFailuresRef.current++
        updateConnectionHealth()
        
        if (socketRef.current?.connected) {
          console.log('🔄 Forcing reconnection due to stale connection')
          // Force disconnect to trigger reconnection logic
          socketRef.current.disconnect()
        }
      } else {
        const healthyThreshold = hasRunningAnalysis ? 120000 : 70000 // More lenient during analysis
        console.log(`📡 Connection healthy - last ping ${timeSinceLastPing}ms ago (analysis active: ${hasRunningAnalysis})`)
        
        // Reset failure count on healthy ping
        if (timeSinceLastPing < healthyThreshold) {
          if (consecutiveFailuresRef.current > 0) {
            consecutiveFailuresRef.current = Math.max(0, consecutiveFailuresRef.current - 1)
            updateConnectionHealth()
            console.log(`📊 Connection improving - failures reduced to ${consecutiveFailuresRef.current}`)
          }
        }
      }
    }, 30000) // Check every 30 seconds
  }, [connect, updateConnectionHealth])
  
  const stopHeartbeatMonitoring = useCallback(() => {
    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current)
      heartbeatIntervalRef.current = null
    }
  }, [])

  const disconnect = useCallback(() => {
    console.log('🛑 Manually disconnecting WebSocket')
    isManualDisconnect.current = true
    connectionStateRef.current = 'disconnected'
    
    // Stop monitoring
    stopHeartbeatMonitoring()
    
    // Clear any pending reconnection attempts
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
    
    if (socketRef.current) {
      socketRef.current.disconnect()
      socketRef.current = null
    }
    
    // Reset all state
    setConnected(false)
    setConnecting(false)
    setError(null)
    reconnectAttemptsRef.current = 0
    consecutiveFailuresRef.current = 0
    connectionHealthRef.current = 'healthy'
    backoffStrategyRef.current = 'linear'
    
    console.log('📊 Manual disconnect - all state reset')
  }, [stopHeartbeatMonitoring])

  useEffect(() => {
    const connectionDelay = process.env.NODE_ENV === 'development' ? 500 : 0
    
    const timeoutId = setTimeout(() => {
      connect()
    }, connectionDelay)

    return () => {
      clearTimeout(timeoutId)
      isManualDisconnect.current = true
      stopHeartbeatMonitoring()
      disconnect()
    }
  }, [connect, disconnect])

  // Expose reconnection function for manual use
  const reconnectWebSocket = useCallback(() => {
    console.log('🔄 Manual reconnection requested')
    if (socketRef.current?.connected) {
      console.log('🔌 Socket already connected')
      return
    }
    
    // Clear any existing reconnection attempts
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
    
    // Reset manual disconnect flag
    isManualDisconnect.current = false
    
    // Force a new connection attempt
    reconnectAttemptsRef.current = 0
    connect()
  }, [connect])

  return {
    socket: socketRef.current,
    connected,
    error,
    connecting,
    reconnectWebSocket
  }
}

// Analysis-specific hook with progress tracking
export function useAnalysisSocket() {
  const { socket, connected, error, connecting } = useSocket()
  const [analysisStatus, setAnalysisStatus] = useState<{
    [analysisId: string]: {
      status: 'pending' | 'running' | 'completed' | 'error' | 'cancelled'
      progress?: number
      message?: string
      stage?: string
      startTime?: number
      result?: any  // Store completed analysis result
    }
  }>({})
  
  // Track pending completion callbacks
  const completionCallbacksRef = useRef<{
    [analysisId: string]: (result: any) => void
  }>({})
  
  // Track analysis timeouts
  const analysisTimeoutsRef = useRef<{
    [analysisId: string]: NodeJS.Timeout
  }>({})

  useEffect(() => {
    if (!socket) return

    const handleProgress = (data: AnalysisProgress) => {
      console.log('📊 Analysis progress:', data)
      setAnalysisStatus(prev => ({
        ...prev,
        [data.analysisId]: {
          ...prev[data.analysisId],
          status: 'running',
          progress: data.progress,
          message: data.message,
          stage: data.stage
        }
      }))
      
      // Reset analysis timeout on progress update
      if (analysisTimeoutsRef.current[data.analysisId]) {
        clearTimeout(analysisTimeoutsRef.current[data.analysisId])
        // Set a new timeout (15 minutes for long analyses - complex AI processing)
        analysisTimeoutsRef.current[data.analysisId] = setTimeout(() => {
          console.warn(`⏰ Analysis ${data.analysisId} timed out`)
          handleAnalysisTimeout(data.analysisId)
        }, 900000) // INCREASED from 10 minutes to 15 minutes for complex AI processing
      }
    }

    const handleComplete = (data: AnalysisComplete) => {
      console.log('✅ Analysis complete:', data.analysisId)
      
      // Clear timeout
      if (analysisTimeoutsRef.current[data.analysisId]) {
        clearTimeout(analysisTimeoutsRef.current[data.analysisId])
        delete analysisTimeoutsRef.current[data.analysisId]
      }
      
      // Update status with result first
      setAnalysisStatus(prev => ({
        ...prev,
        [data.analysisId]: {
          ...prev[data.analysisId],
          status: 'completed',
          progress: 100,
          message: 'Analysis completed successfully',
          result: data.result
        }
      }))
      
      // Call completion callback with delay to ensure state propagates
      const callback = completionCallbacksRef.current[data.analysisId]
      if (callback) {
        console.log('🔄 Calling analysis completion callback for:', data.analysisId)
        setTimeout(() => {
          callback(data.result)
          delete completionCallbacksRef.current[data.analysisId]
          console.log('🔄 Analysis completion callback executed and cleaned up for:', data.analysisId)
        }, 10) // Small delay for state batching
      }
    }

    const handleError = (data: AnalysisError) => {
      console.error('❌ Analysis error:', data)
      
      // Clear timeout
      if (analysisTimeoutsRef.current[data.analysisId]) {
        clearTimeout(analysisTimeoutsRef.current[data.analysisId])
        delete analysisTimeoutsRef.current[data.analysisId]
      }
      
      setAnalysisStatus(prev => ({
        ...prev,
        [data.analysisId]: {
          ...prev[data.analysisId],
          status: 'error',
          message: data.error
        }
      }))
      
      // Call error callback if exists
      const callback = completionCallbacksRef.current[data.analysisId]
      if (callback) {
        callback(null) // Signal error with null result
        delete completionCallbacksRef.current[data.analysisId]
      }
    }

    const handleCancelled = (data: { analysisId: string }) => {
      console.log('🛑 Analysis cancelled:', data.analysisId)
      
      // Clear timeout
      if (analysisTimeoutsRef.current[data.analysisId]) {
        clearTimeout(analysisTimeoutsRef.current[data.analysisId])
        delete analysisTimeoutsRef.current[data.analysisId]
      }
      
      setAnalysisStatus(prev => ({
        ...prev,
        [data.analysisId]: {
          ...prev[data.analysisId],
          status: 'cancelled',
          message: 'Analysis was cancelled'
        }
      }))
      
      // Clean up callback
      if (completionCallbacksRef.current[data.analysisId]) {
        delete completionCallbacksRef.current[data.analysisId]
      }
    }
    
    const handleReconnect = async () => {
      console.log('🔄 WebSocket reconnected - checking for pending analyses')
      
      // Check if we have any running analyses that might have completed during disconnection
      Object.keys(analysisStatus).forEach(analysisId => {
        const status = analysisStatus[analysisId]
        if (status.status === 'running' || status.status === 'pending') {
          console.log(`🔍 Checking status of analysis ${analysisId} after reconnection`)
          // Emit a status check event
          socket.emit('check_analysis_status', { analysisId })
        }
      })
      
      // Also check for any persisted results that might have completed during disconnection
      try {
        // Import API client dynamically to avoid circular dependencies
        const { api } = await import('./api')
        
        // Get session ID (using socket ID as session identifier)
        const sessionId = socket.id
        if (sessionId) {
          console.log('🔍 Checking for persisted analysis results after reconnection')
          
          const persistedAnalyses = await api.getClientAnalyses(sessionId, 10)
          if (persistedAnalyses.success && persistedAnalyses.analyses) {
            // Check for completed analyses that we don't have in memory
            for (const analysisInfo of persistedAnalyses.analyses) {
              if (analysisInfo.status === 'completed' && analysisInfo.has_result) {
                const currentStatus = analysisStatus[analysisInfo.analysis_id]
                
                // If we don't have this analysis in memory, or it's still running, retrieve the result
                if (!currentStatus || currentStatus.status === 'running' || currentStatus.status === 'pending') {
                  console.log(`📤 Recovering completed analysis: ${analysisInfo.analysis_id}`)
                  
                  try {
                    const resultResponse = await api.getAnalysisResult(analysisInfo.analysis_id, sessionId)
                    if (resultResponse.success && resultResponse.result) {
                      // Trigger the completion callback manually
                      const callback = completionCallbacksRef.current[analysisInfo.analysis_id]
                      if (callback) {
                        console.log('🔄 Calling recovered analysis completion callback')
                        callback(resultResponse.result)
                        delete completionCallbacksRef.current[analysisInfo.analysis_id]
                      } else {
                        // Update status directly if no callback
                        setAnalysisStatus(prev => ({
                          ...prev,
                          [analysisInfo.analysis_id]: {
                            ...prev[analysisInfo.analysis_id],
                            status: 'completed',
                            progress: 100,
                            message: 'Analysis recovered from persistence',
                            result: resultResponse.result
                          }
                        }))
                      }
                    }
                  } catch (error) {
                    console.warn(`⚠️ Failed to recover analysis ${analysisInfo.analysis_id}:`, error)
                  }
                }
              }
            }
          }
        }
      } catch (error) {
        console.warn('⚠️ Failed to check persisted analyses after reconnection:', error)
      }
    }

    // Persistent event listeners
    socket.on('analysis_progress', handleProgress)
    socket.on('analysis_complete', handleComplete)
    socket.on('analysis_error', handleError)
    socket.on('analysis_cancelled', handleCancelled)
    socket.on('connect', handleReconnect)

    return () => {
      socket.off('analysis_progress', handleProgress)
      socket.off('analysis_complete', handleComplete)
      socket.off('analysis_error', handleError)
      socket.off('analysis_cancelled', handleCancelled)
      socket.off('connect', handleReconnect)
      
      // Clear all timeouts
      Object.values(analysisTimeoutsRef.current).forEach(timeout => {
        clearTimeout(timeout)
      })
      analysisTimeoutsRef.current = {}
    }
  }, [socket, analysisStatus])

  // Helper function to handle analysis timeouts
  const handleAnalysisTimeout = useCallback((analysisId: string) => {
    setAnalysisStatus(prev => ({
      ...prev,
      [analysisId]: {
        ...prev[analysisId],
        status: 'error',
        message: 'Analysis timed out - please try again'
      }
    }))
    
    // Clean up callback
    if (completionCallbacksRef.current[analysisId]) {
      completionCallbacksRef.current[analysisId](null)
      delete completionCallbacksRef.current[analysisId]
    }
    
    // Clean up timeout
    if (analysisTimeoutsRef.current[analysisId]) {
      delete analysisTimeoutsRef.current[analysisId]
    }
  }, [])

  const startAnalysis = useCallback((analysisData: any, onComplete?: (result: any) => void) => {
    if (socket && connected) {
      console.log('🚀 Starting analysis:', analysisData.analysisId)
      
      // Store completion callback if provided
      if (onComplete) {
        completionCallbacksRef.current[analysisData.analysisId] = onComplete
      }
      
      // Set initial timeout (5 minutes for initial response - AI model loading can take time)
      analysisTimeoutsRef.current[analysisData.analysisId] = setTimeout(() => {
        console.warn(`⏰ Analysis ${analysisData.analysisId} initial timeout`)
        handleAnalysisTimeout(analysisData.analysisId)
      }, 300000) // INCREASED from 2 minutes to 5 minutes for AI model loading
      
      socket.emit('start_analysis', analysisData)
      setAnalysisStatus(prev => ({
        ...prev,
        [analysisData.analysisId]: {
          status: 'pending',
          progress: 0,
          message: 'Initializing analysis...',
          stage: 'initialization',
          startTime: Date.now()
        }
      }))
      return true
    } else {
      console.warn('⚠️ Cannot start analysis: WebSocket not connected')
      return false
    }
  }, [socket, connected, handleAnalysisTimeout])

  const cancelAnalysis = useCallback((analysisId: string) => {
    console.log('🛑 Cancelling analysis:', analysisId)
    
    // Clear timeout
    if (analysisTimeoutsRef.current[analysisId]) {
      clearTimeout(analysisTimeoutsRef.current[analysisId])
      delete analysisTimeoutsRef.current[analysisId]
    }
    
    // Clean up callback
    if (completionCallbacksRef.current[analysisId]) {
      delete completionCallbacksRef.current[analysisId]
    }
    
    if (socket && connected) {
      socket.emit('cancel_analysis', { analysisId })
      
      setAnalysisStatus(prev => ({
        ...prev,
        [analysisId]: {
          ...prev[analysisId],
          status: 'cancelled',
          message: 'Cancelling analysis...'
        }
      }))
      return true
    } else {
      console.warn('⚠️ Cannot cancel analysis: WebSocket not connected')
      // Still update local status even if not connected
      setAnalysisStatus(prev => ({
        ...prev,
        [analysisId]: {
          ...prev[analysisId],
          status: 'cancelled',
          message: 'Analysis cancelled (offline)'
        }
      }))
      return false
    }
  }, [socket, connected])

  const clearAnalysisStatus = useCallback((analysisId: string) => {
    // Clear timeout if exists
    if (analysisTimeoutsRef.current[analysisId]) {
      clearTimeout(analysisTimeoutsRef.current[analysisId])
      delete analysisTimeoutsRef.current[analysisId]
    }
    
    // Clean up callback
    if (completionCallbacksRef.current[analysisId]) {
      delete completionCallbacksRef.current[analysisId]
    }
    
    setAnalysisStatus(prev => {
      const newStatus = { ...prev }
      delete newStatus[analysisId]
      return newStatus
    })
  }, [])

  const getAnalysisStatus = useCallback((analysisId: string) => {
    return analysisStatus[analysisId] || null
  }, [analysisStatus])
  
  // Get completed analysis result
  const getAnalysisResult = useCallback((analysisId: string) => {
    const status = analysisStatus[analysisId]
    return status?.status === 'completed' ? status.result : null
  }, [analysisStatus])
  
  // Check if an analysis is still running
  const isAnalysisRunning = useCallback((analysisId: string) => {
    const status = analysisStatus[analysisId]
    return status?.status === 'running' || status?.status === 'pending'
  }, [analysisStatus])
  
  // Wait for analysis completion with promise
  const waitForAnalysis = useCallback((analysisId: string, timeoutMs: number = 600000): Promise<any> => {
    return new Promise((resolve, reject) => {
      const status = analysisStatus[analysisId]
      
      // Check if already completed
      if (status?.status === 'completed' && status.result) {
        resolve(status.result)
        return
      }
      
      if (status?.status === 'error') {
        reject(new Error(status.message || 'Analysis failed'))
        return
      }
      
      // Set up completion callback
      const timeoutId = setTimeout(() => {
        delete completionCallbacksRef.current[analysisId]
        reject(new Error('Analysis timeout'))
      }, timeoutMs)
      
      completionCallbacksRef.current[analysisId] = (result) => {
        clearTimeout(timeoutId)
        if (result) {
          resolve(result)
        } else {
          reject(new Error('Analysis failed'))
        }
      }
    })
  }, [analysisStatus])

  return {
    socket,
    connected,
    error,
    connecting,
    analysisStatus,
    startAnalysis,
    cancelAnalysis,
    clearAnalysisStatus,
    getAnalysisStatus,
    getAnalysisResult,
    isAnalysisRunning,
    waitForAnalysis
  }
}