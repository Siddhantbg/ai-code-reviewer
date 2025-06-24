# AI-Powered Code Review Assistant

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-15+-black.svg)](https://nextjs.org)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://docker.com)
[![Docker](https://img.shields.io/badge/gsap-3.13.0-green.svg)](https://gsap.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A web application that uses **DeepSeek AI models** to review code, detect bugs, suggest improvements, and provide security analysis. This tool helps developers identify issues in their code and receive actionable feedback with **superior performance compared to GPT-3.5** due to specialized code training.

![Landing Page](https://github.com/Siddhantbg/ai-code-reviewer/blob/main/assets/ss2.png)
![Code Editor Window](https://github.com/Siddhantbg/ai-code-reviewer/blob/main/assets/ss1.png)
![Analysis Results](https://github.com/Siddhantbg/ai-code-reviewer/blob/main/assets/ss3.png)

## Tech Stack

### Frontend
- **Framework**: Next.js 15.3.3 with React 19 and TypeScript 5
- **UI/Styling**: Tailwind CSS 4, Radix UI components, Lucide React icons
- **Code Editor**: Monaco Editor with syntax highlighting
- **Animations**: GSAP with ScrollTrigger
- **Build Tool**: Turbopack

### Backend
- **Framework**: FastAPI 0.104.1
- **Language**: Python 3.9+
- **AI Model**: DeepSeek Coder 1.3B (GGUF format)
- **Model Runtime**: llama-cpp-python
- **Validation**: Pydantic 2.5.0
- **Server**: Uvicorn (ASGI)

### DevOps & Deployment
- **Containerization**: Docker & Docker Compose
- **Container Registry**: Docker Hub (`siddhant004/ai-code-reviewer:latest`)
- **Deployment**: Railway / Render / DigitalOcean
- **CI/CD**: GitHub Actions
- **Code Quality**: ESLint, Pylint, Black, isort, pre-commit hooks

## Project Structure

```
ai-code-reviewer/
├── frontend/                     # Next.js app with TypeScript
│   ├── src/                     # Source code
│   │   ├── app/                # Next.js app router
│   │   ├── components/         # React components
│   │   │   ├── ui/            # Reusable UI components (Radix)
│   │   │   ├── CodeEditor.tsx # Monaco code editor
│   │   │   ├── AnalysisResults.tsx
│   │   │   ├── EnhancedResults.tsx
│   │   │   ├── AnalysisConfig.tsx
│   │   │   ├── AnalysisProgress.tsx
│   │   │   ├── EpicLoader.tsx
│   │   │   └── CircuitBoardCity.tsx
│   │   ├── lib/               # Utilities and API client
│   │   └── hooks/             # Custom React hooks
│   ├── package.json           # Frontend dependencies
│   └── next.config.js         # Next.js configuration
├── backend/                    # FastAPI app
│   ├── app/                   # Application code
│   │   ├── main.py           # Entry point
│   │   ├── models/           # Pydantic request/response models
│   │   ├── routers/          # API endpoints
│   │   │   └── analysis.py   # Code analysis routes
│   │   ├── services/         # Business logic
│   │   │   ├── analysis.py   # Static analysis service
│   │   │   └── gguf_service.py # AI model service
│   │   └── utils/            # Utility functions
│   ├── models/               # 🚨 AI model files go here
│   │   └── deepseek-coder-1.3b-instruct.Q4_K_M.gguf
│   ├── requirements.txt      # Python dependencies
│   ├── Dockerfile.prod       # Production container
│   └── .env.example         # Environment variables template
├── .github/                  # GitHub Actions workflows
│   └── workflows/
│       └── lint.yml         # Automated linting
├── docker-compose.yml        # Development environment
├── .pre-commit-config.yaml  # Code quality hooks
├── package.json             # Root scripts for development workflow
├── README.md
└── .gitignore
```

## Quick Start

### Prerequisites
- **Docker & Docker Compose** (recommended)
- **Node.js 18+** and **Python 3.9+** (for local development)
- **Git** for cloning the repository

### 🐳 Docker Deployment (Recommended)

**Option 1: Use pre-built Docker image**
```bash
# Pull and run the production image
docker run -p 8000:8000 \
  -e MODEL_PATH="/app/models/deepseek-coder-1.3b-instruct.Q4_K_M.gguf" \
  -e PORT=8000 \
  siddhant004/ai-code-reviewer:latest
```

**Option 2: Docker Compose**
```bash
# Clone the repository
git clone https://github.com/Siddhantbg/ai-code-reviewer.git
cd ai-code-reviewer

# Start with Docker Compose
docker-compose up -d

# Access the application
# Frontend: http://localhost:3000
# Backend: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

### 📦 Local Development Setup

#### 1. Clone and setup the project
```bash
git clone https://github.com/Siddhantbg/ai-code-reviewer.git
cd ai-code-reviewer
```

#### 2. 🚨 **IMPORTANT: Download AI Model**

**This project requires a DeepSeek Coder model to function properly.**

```bash
# Create models directory
mkdir -p backend/models

# Download DeepSeek Coder 1.3B model (800MB)
# Download from: https://huggingface.co/microsoft/DeepSeek-Coder-1.3B-Instruct-GGUF
# Place the .gguf file in backend/models/

# Expected file structure:
# backend/models/deepseek-coder-1.3b-instruct.Q4_K_M.gguf
```

> **⚠️ Note**: This project is specifically configured for DeepSeek models. Using other models requires changes in `backend/app/services/gguf_service.py`.

#### 3. Install dependencies
```bash
# Install all dependencies at once
npm run install:all
```

This will install:
- Root dependencies
- Frontend dependencies  
- Backend dependencies

#### 4. Environment setup
```bash
# Backend environment
cd backend
cp .env.example .env

# Edit .env file with your configuration:
# MODEL_PATH=./models/deepseek-coder-1.3b-instruct.Q4_K_M.gguf
# PORT=8000
```

#### 5. Start development servers
```bash
# Start both frontend and backend
npm run dev
```

Or start them individually:
```bash
# Start only frontend
npm run dev:frontend

# Start only backend  
npm run dev:backend
```

#### 6. Alternative: Docker development
```bash
npm run docker:up
```

### Access the Application

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000  
- **API Documentation**: http://localhost:8000/docs

## Features

### Core Features ✅
- **Interactive code editor** with Monaco Editor
  - Syntax highlighting for multiple languages
  - File upload functionality  
  - Example code templates
  - Drag and drop support
- **Multi-language support**
  - Python, JavaScript, TypeScript, Java, C++, and more
  - Automatic language detection from file extension
- **AI-powered code analysis** using DeepSeek models
  - Detection of bugs, security issues, and style problems
  - Code metrics (complexity, maintainability)
  - Severity-based issue categorization
  - Suggestions and explanations for each issue
- **Modern, responsive UI** with Tailwind CSS
  - Analysis results dashboard
  - Issue breakdown by severity
  - Export functionality for analysis reports
- **RESTful API** with FastAPI
  - Health check endpoint
  - Code analysis endpoint
  - Supported languages endpoint
  - AI model status endpoint

### Advanced Features ⚡
- **Real-time WebSocket** connections for live analysis
- **Analysis progress tracking** with cancellation support
- **Multiple analysis methods**: Quick, Comprehensive, Custom
- **Configurable analysis rules** and severity levels
- **Analysis history** and project management
- **Export reports** in JSON, CSV, PDF formats
- **Keyboard shortcuts** for power users
- **Dark/Light theme** support

## API Documentation

### Core Endpoints

```bash
# Health check
GET /health

# Code analysis with static tools
POST /api/analyze
{
  "code": "print('hello world')",
  "language": "python",
  "analysis_type": "comprehensive"
}

# AI-powered analysis  
POST /api/analyze-with-ai
{
  "code": "def hello():\n    print('world')",
  "language": "python"
}

# Get supported languages
GET /api/languages

# Check AI model status
GET /api/model/status
```

### Example Response
```json
{
  "analysis_id": "analysis-123",
  "language": "python", 
  "summary": {
    "overall_score": 8.5,
    "total_issues": 2,
    "critical_issues": 0,
    "suggestions_count": 3
  },
  "issues": [
    {
      "id": "issue-1",
      "type": "style",
      "severity": "low", 
      "line_number": 1,
      "description": "Missing docstring",
      "suggestion": "Add a docstring to describe the function"
    }
  ]
}
```

## Development

### Project Scripts

```bash
# Development
npm run dev              # Start both frontend and backend
npm run dev:frontend     # Start only frontend
npm run dev:backend      # Start only backend

# Installation
npm run install:all      # Install all dependencies

# Docker
npm run docker:up        # Start Docker containers
npm run docker:down      # Stop Docker containers

# Testing
npm run test:frontend    # Run frontend tests
npm run test:backend     # Run backend tests

# Linting and Formatting
npm run lint:frontend    # Lint frontend code
npm run lint:backend     # Lint backend code
npm run format:backend   # Format backend code
```

### Running Tests
```bash
# Backend tests
cd backend
pytest tests/ -v

# Frontend tests
cd frontend  
npm test

# End-to-end tests
npm run test:e2e
```

### Code Quality Tools
- **ESLint 9** for TypeScript/React code
- **Pylint 3.0.3** for Python code quality
- **Black 23.11.0** for Python code formatting  
- **Pre-commit hooks** for automated checks
- **GitHub Actions** for CI/CD

## Environment Variables

### Backend (.env)
```bash
# AI Model Configuration
MODEL_PATH=./models/deepseek-coder-1.3b-instruct.Q4_K_M.gguf
MODEL_TYPE=gguf
MAX_TOKENS=2048
TEMPERATURE=0.1

# Server Configuration  
PORT=8000
UVICORN_HOST=0.0.0.0
WORKERS=1
TIMEOUT=300

# CORS Settings
CORS_ORIGINS=["http://localhost:3000"]

# Logging
LOG_LEVEL=INFO
PYTHONUNBUFFERED=1
```

### Frontend (.env.local)
```bash
# API Configuration
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000

# App Configuration
NEXT_PUBLIC_APP_NAME="AI Code Reviewer"
NEXT_PUBLIC_APP_VERSION="1.0.0"
```

## Deployment

### Docker Hub
Pre-built image available at: `siddhant004/ai-code-reviewer:latest`

### Railway Deployment
```bash
# Deploy to Railway
railway login
railway init
railway up --image siddhant004/ai-code-reviewer:latest

# Set environment variables
railway variables set PORT=8000
railway variables set MODEL_PATH="/app/models/deepseek-coder-1.3b-instruct.Q4_K_M.gguf"
```

### Render/DigitalOcean
Deploy using the Docker image with the required environment variables.

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Install pre-commit hooks: `pre-commit install`
4. Make your changes and commit: `git commit -m 'Add amazing feature'`
5. Push to the branch: `git push origin feature/amazing-feature`
6. Open a Pull Request

### Development Workflow
- Follow the existing code style and conventions
- Add tests for new features
- Update documentation as needed
- Ensure all checks pass before submitting PR

## License

MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [DeepSeek AI](https://deepseek.com/) for the excellent code models
- [Hugging Face](https://huggingface.co/) for model hosting
- [FastAPI](https://fastapi.tiangolo.com/) for the Python web framework
- [Next.js](https://nextjs.org/) for the React framework

---

**Made with ❤️ by [Siddhant Bhagat](https://github.com/Siddhantbg)**
