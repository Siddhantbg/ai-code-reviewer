// frontend/src/lib/websocket.ts
import { useEffect, useState, useRef, useCallback } from 'react'
import { io, Socket } from 'socket.io-client'

interface UseSocketReturn {
  socket: Socket | null
  connected: boolean
  error: string | null
  connecting: boolean
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
      socketRef.current = io(socketUrl, {
        transports: ['websocket', 'polling'], // Ensure polling fallback
        upgrade: true,
        timeout: 20000, // Connection timeout increased to 20 seconds
        pingTimeout: 120000, // 120 seconds - match backend
        pingInterval: 60000, // 60 seconds - match backend
        forceNew: false,
        autoConnect: true,
        reconnection: false, // Using custom reconnection logic
        closeOnBeforeunload: false,
        query: {
          clientType: 'react-frontend',
          timestamp: Date.now()
        }
      })

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

      socket.on('disconnect', (reason, details) => {
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

      socket.on('connect_error', (err) => {
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

      socket.on('error', (err) => {
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

      socket.on('notification', (data) => {
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
      const pingTimeoutMs = 120000 // 120 seconds to match backend
      
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
        console.log(`📡 Connection healthy - last ping ${timeSinceLastPing}ms ago`)
        
        // Reset failure count on healthy ping
        if (timeSinceLastPing < 70000) { // Well within healthy range
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

  return {
    socket: socketRef.current,
    connected,
    error,
    connecting
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
    }
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
    }

    const handleComplete = (data: AnalysisComplete) => {
      console.log('✅ Analysis complete:', data.analysisId)
      setAnalysisStatus(prev => ({
        ...prev,
        [data.analysisId]: {
          ...prev[data.analysisId],
          status: 'completed',
          progress: 100,
          message: 'Analysis completed successfully'
        }
      }))
    }

    const handleError = (data: AnalysisError) => {
      console.error('❌ Analysis error:', data)
      setAnalysisStatus(prev => ({
        ...prev,
        [data.analysisId]: {
          ...prev[data.analysisId],
          status: 'error',
          message: data.error
        }
      }))
    }

    const handleCancelled = (data: { analysisId: string }) => {
      console.log('🛑 Analysis cancelled:', data.analysisId)
      setAnalysisStatus(prev => ({
        ...prev,
        [data.analysisId]: {
          ...prev[data.analysisId],
          status: 'cancelled',
          message: 'Analysis was cancelled'
        }
      }))
    }

    socket.on('analysis_progress', handleProgress)
    socket.on('analysis_complete', handleComplete)
    socket.on('analysis_error', handleError)
    socket.on('analysis_cancelled', handleCancelled)

    return () => {
      socket.off('analysis_progress', handleProgress)
      socket.off('analysis_complete', handleComplete)
      socket.off('analysis_error', handleError)
      socket.off('analysis_cancelled', handleCancelled)
    }
  }, [socket])

  const startAnalysis = useCallback((analysisData: any) => {
    if (socket && connected) {
      console.log('🚀 Starting analysis:', analysisData.analysisId)
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
  }, [socket, connected])

  const cancelAnalysis = useCallback((analysisId: string) => {
    if (socket && connected) {
      console.log('🛑 Cancelling analysis:', analysisId)
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
      return false
    }
  }, [socket, connected])

  const clearAnalysisStatus = useCallback((analysisId: string) => {
    setAnalysisStatus(prev => {
      const newStatus = { ...prev }
      delete newStatus[analysisId]
      return newStatus
    })
  }, [])

  const getAnalysisStatus = useCallback((analysisId: string) => {
    return analysisStatus[analysisId] || null
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
    getAnalysisStatus
  }
}