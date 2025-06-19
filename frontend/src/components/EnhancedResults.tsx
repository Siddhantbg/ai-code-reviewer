"use client"

import React, { useState, useMemo } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  AlertTriangle,
  CheckCircle,
  XCircle,
  AlertCircle,
  Info,
  Clock,
  BarChart3,
  FileText,
  Lightbulb,
  Download,
  Filter,
  Code,
  Shield,
  Layers,
  ArrowDownToLine
} from 'lucide-react'
import { CodeAnalysisResponse, CodeIssue } from '@/lib/api'
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, 
  PieChart, Pie, Cell, Legend 
} from 'recharts'

interface EnhancedResultsProps {
  analysis: CodeAnalysisResponse
  onExport?: (format: 'json' | 'pdf' | 'csv') => void
}

interface ToolResult {
  toolName: string
  issues: CodeIssue[]
  metrics: {
    issueCount: number
    processingTime: number
    rulesChecked: number
  }
}

const getSeverityIcon = (severity: string) => {
  switch (severity.toLowerCase()) {
    case 'critical':
      return <XCircle className="h-4 w-4 text-red-600" />
    case 'high':
      return <AlertTriangle className="h-4 w-4 text-red-500" />
    case 'medium':
      return <AlertCircle className="h-4 w-4 text-yellow-500" />
    case 'low':
      return <Info className="h-4 w-4 text-blue-500" />
    default:
      return <Info className="h-4 w-4 text-gray-500" />
  }
}

const getSeverityBadgeVariant = (severity: string) => {
  switch (severity.toLowerCase()) {
    case 'critical':
      return 'critical'
    case 'high':
      return 'error'
    case 'medium':
      return 'warning'
    case 'low':
      return 'secondary'
    default:
      return 'outline'
  }
}

const getTypeIcon = (type: string) => {
  switch (type.toLowerCase()) {
    case 'bug':
      return <XCircle className="h-4 w-4 text-red-500" />
    case 'security':
      return <AlertTriangle className="h-4 w-4 text-red-600" />
    case 'performance':
      return <BarChart3 className="h-4 w-4 text-orange-500" />
    case 'style':
      return <FileText className="h-4 w-4 text-blue-500" />
    case 'maintainability':
      return <Lightbulb className="h-4 w-4 text-green-500" />
    default:
      return <Info className="h-4 w-4 text-gray-500" />
  }
}

const getToolIcon = (tool: string) => {
  switch (tool.toLowerCase()) {
    case 'eslint':
      return <Code className="h-4 w-4 text-yellow-500" />
    case 'pylint':
      return <Code className="h-4 w-4 text-blue-500" />
    case 'bandit':
      return <Shield className="h-4 w-4 text-red-500" />
    default:
      return <Layers className="h-4 w-4 text-gray-500" />
  }
}

const getScoreColor = (score: number) => {
  if (score >= 8) return 'text-green-600'
  if (score >= 6) return 'text-yellow-600'
  if (score >= 4) return 'text-orange-600'
  return 'text-red-600'
}

const getScoreBackground = (score: number) => {
  if (score >= 8) return 'bg-green-100'
  if (score >= 6) return 'bg-yellow-100'
  if (score >= 4) return 'bg-orange-100'
  return 'bg-red-100'
}

function IssueCard({ issue }: { issue: CodeIssue }) {
  return (
    <Card className="mb-4">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2">
            {getSeverityIcon(issue.severity)}
            <div>
              <h4 className="font-semibold text-sm">{issue.title}</h4>
              <div className="flex items-center gap-2 mt-1">
                <Badge variant={getSeverityBadgeVariant(issue.severity) as any}>
                  {issue.severity.toUpperCase()}
                </Badge>
                <div className="flex items-center gap-1 text-xs text-muted-foreground">
                  {getTypeIcon(issue.type)}
                  <span>{issue.type.charAt(0).toUpperCase() + issue.type.slice(1)}</span>
                </div>
                {issue.line_number && (
                  <span className="text-xs text-muted-foreground">
                    Line {issue.line_number}
                  </span>
                )}

              </div>
            </div>
          </div>
          <div className="text-xs text-muted-foreground">
            {Math.round(issue.confidence * 100)}% confidence
          </div>
        </div>
      </CardHeader>
      
      <CardContent className="pt-0">
        <p className="text-sm text-gray-700 mb-3">{issue.description}</p>
        
        {issue.code_snippet && (
          <div className="mb-3">
            <h5 className="text-xs font-medium text-gray-600 mb-1">Code:</h5>
            <pre className="bg-gray-100 p-2 rounded text-xs overflow-x-auto">
              <code>{issue.code_snippet}</code>
            </pre>
          </div>
        )}
        
        {issue.suggestion && (
          <div className="mb-3">
            <h5 className="text-xs font-medium text-gray-600 mb-1">Suggestion:</h5>
            <p className="text-sm text-green-700 bg-green-50 p-2 rounded">
              {issue.suggestion}
            </p>
          </div>
        )}
        
        {issue.explanation && (
          <div>
            <h5 className="text-xs font-medium text-gray-600 mb-1">Explanation:</h5>
            <p className="text-sm text-gray-600">{issue.explanation}</p>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function SeverityDistributionChart({ issues }: { issues: CodeIssue[] }) {
  const data = useMemo(() => {
    const counts = {
      critical: 0,
      high: 0,
      medium: 0,
      low: 0,
    }
    
    issues.forEach(issue => {
      const severity = issue.severity.toLowerCase() as keyof typeof counts
      if (counts[severity] !== undefined) {
        counts[severity]++
      }
    })
    
    return [
      { name: 'Critical', value: counts.critical, color: '#b91c1c' },
      { name: 'High', value: counts.high, color: '#ef4444' },
      { name: 'Medium', value: counts.medium, color: '#eab308' },
      { name: 'Low', value: counts.low, color: '#3b82f6' },
    ]
  }, [issues])
  
  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            labelLine={false}
            outerRadius={80}
            fill="#8884d8"
            dataKey="value"
            label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
          >
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.color} />
            ))}
          </Pie>
          <Tooltip formatter={(value) => [`${value} issues`, 'Count']} />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    </div>
  )
}

function IssueTypeChart({ issues }: { issues: CodeIssue[] }) {
  const data = useMemo(() => {
    const typeCounts: Record<string, number> = {}
    
    issues.forEach(issue => {
      const type = issue.type.toLowerCase()
      typeCounts[type] = (typeCounts[type] || 0) + 1
    })
    
    return Object.entries(typeCounts).map(([type, count]) => ({
      name: type.charAt(0).toUpperCase() + type.slice(1),
      count,
    }))
  }, [issues])
  
  const colors = ['#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6']
  
  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="name" />
          <YAxis />
          <Tooltip formatter={(value) => [`${value} issues`, 'Count']} />
          <Bar dataKey="count" fill="#3b82f6">
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={colors[index % colors.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

export default function EnhancedResults({ analysis, onExport }: EnhancedResultsProps) {
  const { summary, metrics, issues, suggestions, processing_time_ms } = analysis
  
  // State for active tab
  const [activeTab, setActiveTab] = useState<string>('all')
  
  // State for severity filter
  const [severityFilter, setSeverityFilter] = useState<string[]>([
    'critical', 'high', 'medium', 'low'
  ])
  
  // Toggle severity filter
  const toggleSeverityFilter = (severity: string) => {
    setSeverityFilter(prev => 
      prev.includes(severity)
        ? prev.filter(s => s !== severity)
        : [...prev, severity]
    )
  }
  
  // Mock tool-specific results
  // In a real app, this would come from the backend
  const toolResults: ToolResult[] = useMemo(() => {
    // Distribute issues randomly across tools since CodeIssue doesn't have tool property
    const eslintIssues = issues.filter((_, index) => index % 3 === 0)
    const pylintIssues = issues.filter((_, index) => index % 3 === 1)
    const banditIssues = issues.filter(issue => issue.type === 'security' || issues.indexOf(issue) % 3 === 2)
    
    return [
      {
        toolName: 'eslint',
        issues: eslintIssues,
        metrics: {
          issueCount: eslintIssues.length,
          processingTime: processing_time_ms * 0.4,
          rulesChecked: 120,
        }
      },
      {
        toolName: 'pylint',
        issues: pylintIssues,
        metrics: {
          issueCount: pylintIssues.length,
          processingTime: processing_time_ms * 0.3,
          rulesChecked: 95,
        }
      },
      {
        toolName: 'bandit',
        issues: banditIssues,
        metrics: {
          issueCount: banditIssues.length,
          processingTime: processing_time_ms * 0.3,
          rulesChecked: 42,
        }
      },
    ]
  }, [issues, processing_time_ms])
  
  // Filter issues based on active tab and severity filter
  const filteredIssues = useMemo(() => {
    let filtered = issues
    
    // Filter by tool
    if (activeTab !== 'all') {
      const activeToolResult = toolResults.find(t => t.toolName === activeTab)
      if (activeToolResult) {
        filtered = filtered.filter(issue => 
          activeToolResult.issues.some(i => i.id === issue.id)
        )
      }
    }
    
    // Filter by severity
    filtered = filtered.filter(issue => severityFilter.includes(issue.severity.toLowerCase()))
    
    return filtered
  }, [issues, activeTab, severityFilter, toolResults])
  
  // Get active tool result
  const activeToolResult = useMemo(() => {
    if (activeTab === 'all') return null
    return toolResults.find(tool => tool.toolName === activeTab) || null
  }, [activeTab, toolResults])
  
  // Handle export
  const handleExport = (format: 'json' | 'pdf' | 'csv') => {
    if (onExport) {
      onExport(format)
    } else {
      // Fallback export functionality
      if (format === 'json') {
        const dataStr = JSON.stringify(analysis, null, 2)
        const dataUri = `data:application/json;charset=utf-8,${encodeURIComponent(dataStr)}`
        const exportFileDefaultName = `code-analysis-${new Date().toISOString()}.json`
        
        const linkElement = document.createElement('a')
        linkElement.setAttribute('href', dataUri)
        linkElement.setAttribute('download', exportFileDefaultName)
        linkElement.click()
      }
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Analysis Results</h2>
          <p className="text-muted-foreground">
            Analysis completed in {processing_time_ms.toFixed(1)}ms
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => handleExport('json')}>
            <ArrowDownToLine className="h-4 w-4 mr-2" />
            JSON
          </Button>
          <Button variant="outline" size="sm" onClick={() => handleExport('csv')}>
            <ArrowDownToLine className="h-4 w-4 mr-2" />
            CSV
          </Button>
          <Button variant="outline" size="sm" onClick={() => handleExport('pdf')}>
            <ArrowDownToLine className="h-4 w-4 mr-2" />
            PDF
          </Button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Overall Score</p>
                <p className={`text-2xl font-bold ${getScoreColor(summary.overall_score)}`}>
                  {summary.overall_score.toFixed(1)}/10
                </p>
              </div>
              <div className={`p-2 rounded-full ${getScoreBackground(summary.overall_score)}`}>
                {summary.overall_score >= 7 ? (
                  <CheckCircle className={`h-6 w-6 ${getScoreColor(summary.overall_score)}`} />
                ) : (
                  <AlertTriangle className={`h-6 w-6 ${getScoreColor(summary.overall_score)}`} />
                )}
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Total Issues</p>
                <p className="text-2xl font-bold">{summary.total_issues}</p>
              </div>
              <div className="p-2 rounded-full bg-blue-100">
                <AlertCircle className="h-6 w-6 text-blue-600" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Lines of Code</p>
                <p className="text-2xl font-bold">{metrics.lines_of_code}</p>
              </div>
              <div className="p-2 rounded-full bg-green-100">
                <FileText className="h-6 w-6 text-green-600" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Processing Time</p>
                <p className="text-2xl font-bold">{(processing_time_ms / 1000).toFixed(2)}s</p>
              </div>
              <div className="p-2 rounded-full bg-purple-100">
                <Clock className="h-6 w-6 text-purple-600" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Tabs and Filters */}
      <div className="flex flex-col md:flex-row gap-4 items-start">
        {/* Tool Tabs */}
        <Card className="w-full md:w-auto">
          <CardContent className="p-4">
            <div className="flex flex-wrap gap-2">
              <Button 
                variant={activeTab === 'all' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setActiveTab('all')}
                className="flex items-center gap-2"
              >
                <Layers className="h-4 w-4" />
                All Tools
              </Button>
              
              {toolResults.map(tool => (
                <Button
                  key={tool.toolName}
                  variant={activeTab === tool.toolName ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setActiveTab(tool.toolName)}
                  className="flex items-center gap-2"
                >
                  {getToolIcon(tool.toolName)}
                  {tool.toolName}
                  <Badge variant="outline" className="ml-1">
                    {Math.round(tool.metrics.issueCount)}
                  </Badge>
                </Button>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Severity Filters */}
        <Card className="w-full md:w-auto">
          <CardContent className="p-4">
            <div className="flex items-center gap-2">
              <Filter className="h-4 w-4 text-gray-500" />
              <span className="text-sm font-medium">Filter by Severity:</span>
              
              <div className="flex gap-2">
                {['critical', 'high', 'medium', 'low'].map(severity => (
                  <Badge
                    key={severity}
                    variant={severityFilter.includes(severity) ? getSeverityBadgeVariant(severity) as any : 'outline'}
                    className="cursor-pointer"
                    onClick={() => toggleSeverityFilter(severity)}
                  >
                    {severity.toUpperCase()}
                  </Badge>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Tool-specific metrics (when a specific tool is selected) */}
      {activeToolResult && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              {getToolIcon(activeToolResult.toolName)}
              {activeToolResult.toolName} Metrics
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <div className="text-sm font-medium text-muted-foreground">Issues Found</div>
                <div className="text-xl font-semibold">{Math.round(activeToolResult.metrics.issueCount)}</div>
              </div>
              <div>
                <div className="text-sm font-medium text-muted-foreground">Processing Time</div>
                <div className="text-xl font-semibold">{(activeToolResult.metrics.processingTime / 1000).toFixed(2)}s</div>
              </div>
              <div>
                <div className="text-sm font-medium text-muted-foreground">Rules Checked</div>
                <div className="text-xl font-semibold">{activeToolResult.metrics.rulesChecked}</div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Charts */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Severity Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            <SeverityDistributionChart issues={filteredIssues} />
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader>
            <CardTitle>Issue Types</CardTitle>
          </CardHeader>
          <CardContent>
            <IssueTypeChart issues={filteredIssues} />
          </CardContent>
        </Card>
      </div>

      {/* Issues List */}
      {filteredIssues.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5" />
              Issues Found ({filteredIssues.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {filteredIssues.map((issue) => (
                <IssueCard key={issue.id} issue={issue} />
              ))}
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-8">
            <div className="text-center">
              <CheckCircle className="h-12 w-12 mx-auto mb-4 text-green-500" />
              <h3 className="text-lg font-medium mb-2">No Issues Found</h3>
              <p className="text-sm text-gray-500">
                No issues were found with the current filter settings.
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Suggestions */}
      {suggestions.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Lightbulb className="h-5 w-5" />
              Improvement Suggestions
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {suggestions.map((suggestion, index) => (
                <li key={index} className="flex items-start gap-2">
                  <div className="w-2 h-2 bg-blue-500 rounded-full mt-2 flex-shrink-0" />
                  <span className="text-sm text-gray-700">{suggestion}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* Analysis Info */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Info className="h-5 w-5" />
            Analysis Information
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
            <div>
              <span className="font-medium">Analysis ID:</span> {analysis.analysis_id}
            </div>
            <div>
              <span className="font-medium">Language:</span> {analysis.language}
            </div>
            <div>
              <span className="font-medium">Timestamp:</span> {new Date(analysis.timestamp).toLocaleString()}
            </div>
            <div>
              <span className="font-medium">Processing Time:</span> {processing_time_ms.toFixed(1)}ms
            </div>
            {analysis.filename && (
              <div>
                <span className="font-medium">Filename:</span> {analysis.filename}
              </div>
            )}
            <div>
              <span className="font-medium">Tools Used:</span> {toolResults.map(t => t.toolName).join(', ')}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}