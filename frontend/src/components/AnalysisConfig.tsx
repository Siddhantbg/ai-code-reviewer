"use client"

import React, { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Settings, Save, Download, Upload, Check, X, AlertTriangle, Info } from 'lucide-react'

// Define the types for our configuration
export interface Rule {
  id: string
  name: string
  description: string
  category: string
  severity: 'critical' | 'high' | 'medium' | 'low'
  enabled: boolean
  tool: string
}

export interface AnalysisConfig {
  language: string
  rules: Rule[]
  selectedTools: string[]
  severityLevels: {
    critical: boolean
    high: boolean
    medium: boolean
    low: boolean
  }
  preset: string | null
}

interface AnalysisConfigProps {
  language: string
  onConfigChange: (config: AnalysisConfig) => void
  defaultConfig?: AnalysisConfig
}

// Mock data for rule presets
const PRESETS = {
  'python': [
    { name: 'Google Style', description: 'Google Python Style Guide rules' },
    { name: 'PEP 8', description: 'Standard Python style guide' },
    { name: 'Security Focus', description: 'Emphasizes security best practices' },
  ],
  'javascript': [
    { name: 'Airbnb', description: 'Airbnb JavaScript Style Guide' },
    { name: 'Google Style', description: 'Google JavaScript Style Guide' },
    { name: 'Standard', description: 'JavaScript Standard Style' },
  ],
  'typescript': [
    { name: 'Microsoft', description: 'Microsoft TypeScript guidelines' },
    { name: 'Google Style', description: 'Google TypeScript Style Guide' },
    { name: 'Strict', description: 'Strict TypeScript configuration' },
  ],
}

// Mock data for rules by language
const MOCK_RULES: Record<string, Rule[]> = {
  'python': [
    { id: 'py001', name: 'Missing docstring', description: 'Function is missing a docstring', category: 'style', severity: 'low', enabled: true, tool: 'pylint' },
    { id: 'py002', name: 'Unused variable', description: 'Variable is defined but not used', category: 'maintainability', severity: 'medium', enabled: true, tool: 'pylint' },
    { id: 'py003', name: 'Security issue', description: 'Potential security vulnerability', category: 'security', severity: 'high', enabled: true, tool: 'bandit' },
    { id: 'py004', name: 'Code complexity', description: 'Function is too complex', category: 'maintainability', severity: 'medium', enabled: false, tool: 'pylint' },
    { id: 'py005', name: 'SQL Injection', description: 'Possible SQL injection vulnerability', category: 'security', severity: 'critical', enabled: true, tool: 'bandit' },
  ],
  'javascript': [
    { id: 'js001', name: 'Missing semicolon', description: 'Statement is missing a semicolon', category: 'style', severity: 'low', enabled: true, tool: 'eslint' },
    { id: 'js002', name: 'Unused variable', description: 'Variable is defined but not used', category: 'maintainability', severity: 'medium', enabled: true, tool: 'eslint' },
    { id: 'js003', name: 'Eval usage', description: 'Dangerous use of eval()', category: 'security', severity: 'high', enabled: true, tool: 'eslint' },
    { id: 'js004', name: 'Console statement', description: 'Unexpected console statement', category: 'maintainability', severity: 'low', enabled: false, tool: 'eslint' },
    { id: 'js005', name: 'Prototype pollution', description: 'Possible prototype pollution', category: 'security', severity: 'critical', enabled: true, tool: 'eslint' },
  ],
  'typescript': [
    { id: 'ts001', name: 'Any type', description: 'Avoid using the any type', category: 'style', severity: 'medium', enabled: true, tool: 'eslint' },
    { id: 'ts002', name: 'Unused variable', description: 'Variable is defined but not used', category: 'maintainability', severity: 'medium', enabled: true, tool: 'eslint' },
    { id: 'ts003', name: 'Unsafe any', description: 'Unsafe use of any type', category: 'security', severity: 'high', enabled: true, tool: 'eslint' },
    { id: 'ts004', name: 'No explicit return', description: 'Missing return type on function', category: 'style', severity: 'low', enabled: false, tool: 'eslint' },
    { id: 'ts005', name: 'Prototype pollution', description: 'Possible prototype pollution', category: 'security', severity: 'critical', enabled: true, tool: 'eslint' },
  ],
}

// Available tools by language
const TOOLS_BY_LANGUAGE: Record<string, string[]> = {
  'python': ['pylint', 'bandit'],
  'javascript': ['eslint'],
  'typescript': ['eslint'],
}

const getSeverityColor = (severity: string) => {
  switch (severity) {
    case 'critical': return 'bg-red-700 text-white'
    case 'high': return 'bg-red-500 text-white'
    case 'medium': return 'bg-yellow-500 text-white'
    case 'low': return 'bg-blue-500 text-white'
    default: return 'bg-gray-500 text-white'
  }
}

export default function AnalysisConfig({ language, onConfigChange, defaultConfig }: AnalysisConfigProps) {
  // Initialize state with default config or create a new one
  const [config, setConfig] = useState<AnalysisConfig>(() => {
    if (defaultConfig) return defaultConfig
    
    return {
      language,
      rules: MOCK_RULES[language] || [],
      selectedTools: TOOLS_BY_LANGUAGE[language] || [],
      severityLevels: {
        critical: true,
        high: true,
        medium: true,
        low: true,
      },
      preset: null,
    }
  })

  // Update config when language changes
  useEffect(() => {
    if (language !== config.language) {
      setConfig({
        language,
        rules: MOCK_RULES[language] || [],
        selectedTools: TOOLS_BY_LANGUAGE[language] || [],
        severityLevels: config.severityLevels,
        preset: null,
      })
    }
  }, [language, config.language])

  // Notify parent component when config changes
  useEffect(() => {
    onConfigChange(config)
  }, [config, onConfigChange])

  // Toggle a rule's enabled status
  const toggleRule = (ruleId: string) => {
    setConfig(prev => ({
      ...prev,
      rules: prev.rules.map(rule => 
        rule.id === ruleId ? { ...rule, enabled: !rule.enabled } : rule
      )
    }))
  }

  // Toggle a tool's selection
  const toggleTool = (tool: string) => {
    setConfig(prev => {
      const selectedTools = prev.selectedTools.includes(tool)
        ? prev.selectedTools.filter(t => t !== tool)
        : [...prev.selectedTools, tool]
      
      // Update rules to disable those from unselected tools
      const rules = prev.rules.map(rule => ({
        ...rule,
        enabled: rule.enabled && selectedTools.includes(rule.tool)
      }))
      
      return {
        ...prev,
        selectedTools,
        rules,
      }
    })
  }

  // Toggle a severity level
  const toggleSeverity = (severity: keyof typeof config.severityLevels) => {
    setConfig(prev => {
      const severityLevels = {
        ...prev.severityLevels,
        [severity]: !prev.severityLevels[severity]
      }
      
      // Update rules to match severity settings
      const rules = prev.rules.map(rule => ({
        ...rule,
        enabled: rule.enabled && severityLevels[rule.severity]
      }))
      
      return {
        ...prev,
        severityLevels,
        rules,
      }
    })
  }

  // Apply a preset configuration
  const applyPreset = (presetName: string) => {
    // In a real app, we would fetch the preset configuration from the backend
    // For now, we'll just simulate it by enabling all rules
    setConfig(prev => ({
      ...prev,
      preset: presetName,
      rules: prev.rules.map(rule => ({ ...rule, enabled: true })),
      severityLevels: {
        critical: true,
        high: true,
        medium: true,
        low: true,
      },
    }))
  }

  // Export the current configuration
  const exportConfig = () => {
    const configJson = JSON.stringify(config, null, 2)
    const blob = new Blob([configJson], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${language}-analysis-config.json`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  // Import a configuration file
  const importConfig = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    const reader = new FileReader()
    reader.onload = (e) => {
      try {
        const importedConfig = JSON.parse(e.target?.result as string) as AnalysisConfig
        if (importedConfig.language === language) {
          setConfig(importedConfig)
        } else {
          alert(`Configuration is for ${importedConfig.language}, but current language is ${language}`)
        }
      } catch (error) {
        alert('Invalid configuration file')
      }
    }
    reader.readAsText(file)
    
    // Reset the input
    event.target.value = ''
  }

  // Group rules by category
  const rulesByCategory = config.rules.reduce<Record<string, Rule[]>>((acc, rule) => {
    if (!acc[rule.category]) {
      acc[rule.category] = []
    }
    acc[rule.category].push(rule)
    return acc
  }, {})

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Settings className="h-5 w-5" />
          <h2 className="text-xl font-bold">Analysis Configuration</h2>
        </div>
        <div className="flex items-center gap-2">
          <label htmlFor="import-config">
            <Button variant="outline" size="sm" asChild>
              <span>
                <Upload className="h-4 w-4 mr-2" />
                Import
              </span>
            </Button>
          </label>
          <input
            id="import-config"
            type="file"
            accept=".json"
            onChange={importConfig}
            className="hidden"
          />
          <Button variant="outline" size="sm" onClick={exportConfig}>
            <Download className="h-4 w-4 mr-2" />
            Export
          </Button>
        </div>
      </div>

      {/* Presets */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Rule Presets</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {PRESETS[language as keyof typeof PRESETS]?.map((preset) => (
                <div 
                  key={preset.name}
                  className={`p-4 border rounded-lg cursor-pointer transition-colors ${config.preset === preset.name ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-blue-300'}`}
                  onClick={() => applyPreset(preset.name)}
                >
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="font-medium">{preset.name}</h3>
                    {config.preset === preset.name && (
                      <Check className="h-4 w-4 text-blue-500" />
                    )}
                  </div>
                  <p className="text-sm text-gray-600">{preset.description}</p>
                </div>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Tool Selection */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Analysis Tools</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-3">
            {TOOLS_BY_LANGUAGE[language]?.map((tool) => (
              <div 
                key={tool}
                className={`px-4 py-2 border rounded-full cursor-pointer transition-colors ${config.selectedTools.includes(tool) ? 'border-blue-500 bg-blue-50 text-blue-700' : 'border-gray-200 text-gray-700 hover:border-blue-300'}`}
                onClick={() => toggleTool(tool)}
              >
                <div className="flex items-center gap-2">
                  {config.selectedTools.includes(tool) ? (
                    <Check className="h-4 w-4" />
                  ) : (
                    <X className="h-4 w-4" />
                  )}
                  <span className="font-medium">{tool}</span>
                </div>
              </div>
            ))}
          </div>
          <p className="mt-3 text-sm text-gray-500">
            Select which analysis tools to use. Each tool specializes in different types of issues.
          </p>
        </CardContent>
      </Card>

      {/* Severity Levels */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Severity Levels</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-3">
            {Object.entries(config.severityLevels).map(([severity, enabled]) => (
              <div 
                key={severity}
                className={`px-4 py-2 border rounded-full cursor-pointer transition-colors ${enabled ? `border-${severity === 'critical' ? 'red-700' : severity === 'high' ? 'red-500' : severity === 'medium' ? 'yellow-500' : 'blue-500'} ${getSeverityColor(severity)}` : 'border-gray-200 text-gray-700 hover:border-blue-300'}`}
                onClick={() => toggleSeverity(severity as keyof typeof config.severityLevels)}
              >
                <div className="flex items-center gap-2">
                  {enabled ? (
                    <Check className="h-4 w-4" />
                  ) : (
                    <X className="h-4 w-4" />
                  )}
                  <span className="font-medium capitalize">{severity}</span>
                </div>
              </div>
            ))}
          </div>
          <p className="mt-3 text-sm text-gray-500">
            Select which severity levels to include in the analysis.
          </p>
        </CardContent>
      </Card>

      {/* Rules by Category */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Rules Configuration</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-6">
            {Object.entries(rulesByCategory).map(([category, rules]) => (
              <div key={category} className="space-y-3">
                <h3 className="font-medium capitalize">{category}</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {rules.map((rule) => (
                    <div 
                      key={rule.id}
                      className={`p-3 border rounded-lg cursor-pointer transition-colors ${rule.enabled ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-blue-300'}`}
                      onClick={() => toggleRule(rule.id)}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center gap-2">
                          <span className="font-medium">{rule.name}</span>
                          <Badge className={getSeverityColor(rule.severity)}>
                            {rule.severity.toUpperCase()}
                          </Badge>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-gray-500">{rule.tool}</span>
                          {rule.enabled ? (
                            <Check className="h-4 w-4 text-green-500" />
                          ) : (
                            <X className="h-4 w-4 text-gray-400" />
                          )}
                        </div>
                      </div>
                      <p className="text-sm text-gray-600">{rule.description}</p>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Configuration Summary */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Configuration Summary</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <Info className="h-4 w-4 text-blue-500" />
              <span className="text-sm">
                <strong>{config.rules.filter(r => r.enabled).length}</strong> of <strong>{config.rules.length}</strong> rules enabled
              </span>
            </div>
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-yellow-500" />
              <span className="text-sm">
                <strong>{config.selectedTools.length}</strong> analysis tools selected
              </span>
            </div>
            <div className="flex flex-wrap gap-2 mt-3">
              {config.rules
                .filter(rule => rule.enabled)
                .map(rule => (
                  <Badge key={rule.id} variant="outline" className="text-xs">
                    {rule.name}
                  </Badge>
                ))}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}