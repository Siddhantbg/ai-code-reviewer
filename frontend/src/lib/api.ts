// frontend/src/lib/api.ts
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// Types for API responses
export interface CodeIssue {
  id: string
  type: string
  severity: 'critical' | 'high' | 'medium' | 'low'
  title: string
  line_number?: number
  column_number?: number
  description: string
  suggestion?: string
  rule_id?: string
  category?: string
  code_snippet?: string
  explanation?: string
  confidence?: number
}

export interface CodeAnalysisResponse {
  analysis_id: string
  timestamp: string
  language: string
  filename?: string
  processing_time_ms: number
  summary: {
    overall_score: number
    total_issues: number
    critical_issues: number
    high_issues: number
    medium_issues: number
    low_issues: number
    lines_of_code?: number
    complexity_score?: number
    recommendation?: string
  }
  issues: CodeIssue[]
  metrics: {
    lines_of_code: number
    complexity_score: number
    maintainability_index: number
    test_coverage?: number | null
    duplication_percentage: number
    cyclomatic_complexity?: number
    technical_debt_ratio?: number
  }
  suggestions: string[]
}

export interface HealthResponse {
  status: string
  message: string
  version: string
  ai_model_loaded: boolean
  ai_model_path?: string
  websocket?: string
  active_analyses?: number
}

export interface AnalysisRequest {
  code: string
  language: string
  filename?: string
  analysis_type?: 'full' | 'bugs_only' | 'security_only' | 'performance_only' | 'style_only'
  include_suggestions?: boolean
  include_explanations?: boolean
  severity_threshold?: 'critical' | 'high' | 'medium' | 'low'
  config?: any
}

// API Client class
class APIClient {
  private baseURL: string

  constructor(baseURL: string = API_BASE_URL) {
    this.baseURL = baseURL
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseURL}${endpoint}`
    
    const config: RequestInit = {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    }

    try {
      const response = await fetch(url, config)
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(
          errorData.detail || 
          errorData.message || 
          `HTTP ${response.status}: ${response.statusText}`
        )
      }

      const data = await response.json()
      return data
    } catch (error) {
      if (error instanceof TypeError && error.message.includes('fetch')) {
        throw new Error('Network error: Unable to connect to the server. Please check if the backend is running.')
      }
      throw error
    }
  }

  // Health check endpoint
  async healthCheck(): Promise<HealthResponse> {
    return this.request<HealthResponse>('/health')
  }

  // Alternative health check
  async apiHealthCheck(): Promise<HealthResponse> {
    return this.request<HealthResponse>('/api/health')
  }

  // Code analysis endpoint (REST API fallback)
  async analyzeCode(data: AnalysisRequest): Promise<CodeAnalysisResponse> {
    return this.request<CodeAnalysisResponse>('/api/v1/analyze', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  // Get supported languages
  async getSupportedLanguages(): Promise<string[]> {
    try {
      return this.request<string[]>('/api/v1/languages')
    } catch (error) {
      // Fallback to default languages if endpoint doesn't exist
      console.warn('Could not fetch supported languages, using defaults:', error)
      return ['python', 'javascript', 'typescript', 'java', 'cpp', 'c', 'go', 'rust', 'php']
    }
  }

  // Get analysis history (if implemented)
  async getAnalysisHistory(limit: number = 10): Promise<any[]> {
    try {
      return this.request<any[]>(`/api/v1/history?limit=${limit}`)
    } catch (error) {
      console.warn('Analysis history endpoint not available:', error)
      return []
    }
  }

  // Get analysis by ID (if implemented)
  async getAnalysis(analysisId: string): Promise<CodeAnalysisResponse> {
    return this.request<CodeAnalysisResponse>(`/api/v1/analysis/${analysisId}`)
  }

  // Export analysis report
  async exportAnalysis(analysisId: string, format: 'json' | 'pdf' | 'csv' = 'json'): Promise<Blob> {
    const response = await fetch(`${this.baseURL}/api/v1/analysis/${analysisId}/export?format=${format}`, {
      method: 'GET',
      headers: {
        'Accept': format === 'json' ? 'application/json' : 
                 format === 'pdf' ? 'application/pdf' : 'text/csv'
      }
    })

    if (!response.ok) {
      throw new Error(`Export failed: ${response.statusText}`)
    }

    return response.blob()
  }

  // Test connection
  async testConnection(): Promise<boolean> {
    try {
      await this.healthCheck()
      return true
    } catch (error) {
      console.error('Connection test failed:', error)
      return false
    }
  }

  // Get server status
  async getServerStatus(): Promise<{
    online: boolean
    websocket: boolean
    aiModel: boolean
    activeAnalyses: number
  }> {
    try {
      const health = await this.healthCheck()
      return {
        online: health.status === 'healthy',
        websocket: health.websocket === 'enabled',
        aiModel: health.ai_model_loaded || false,
        activeAnalyses: health.active_analyses || 0
      }
    } catch (error) {
      return {
        online: false,
        websocket: false,
        aiModel: false,
        activeAnalyses: 0
      }
    }
  }
}

// Create and export the API client instance
export const apiClient = new APIClient()

// Export the class for custom instances
export default APIClient

// Utility function to check if backend is available
export async function checkBackendAvailability(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE_URL}/health`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
      // Add timeout
      signal: AbortSignal.timeout(5000)
    })
    return response.ok
  } catch (error) {
    console.error('Backend availability check failed:', error)
    return false
  }
}

// Utility function to get API base URL
export function getAPIBaseURL(): string {
  return API_BASE_URL
}

// Error types for better error handling
export class APIError extends Error {
  constructor(
    message: string,
    public status?: number,
    public code?: string
  ) {
    super(message)
    this.name = 'APIError'
  }
}

export class NetworkError extends Error {
  constructor(message: string = 'Network connection failed') {
    super(message)
    this.name = 'NetworkError'
  }
}