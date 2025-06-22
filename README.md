# AI-Powered Code Review Assistant

A web application that uses AI to review code, detect bugs, suggest improvements, and provide security analysis. This tool helps developers identify issues in their code and receive actionable feedback to improve code quality.

(https://github.com/Siddhantbg/ai-code-reviewer/blob/main/assets/ss1.png)
(https://github.com/Siddhantbg/ai-code-reviewer/blob/main/assets/ss2.png)
## Project Structure

```
ai-code-reviewer/
├── frontend/                # Next.js app with TypeScript
│   ├── src/                # Source code
│   │   ├── app/           # Next.js app router
│   │   ├── components/    # React components
│   │   │   ├── ui/        # Reusable UI components
│   │   │   ├── CodeEditor.tsx
│   │   │   └── AnalysisResults.tsx
│   │   └── lib/           # Utility functions and API client
│   └── package.json       # Frontend dependencies
├── backend/               # FastAPI app
│   ├── app/               # Application code
│   │   ├── main.py       # Entry point
│   │   ├── models/       # Request/response models
│   │   ├── routers/      # API endpoints
│   │   ├── services/     # Business logic
│   │   └── utils/        # Utility functions
│   ├── requirements.txt   # Python dependencies
│   └── Dockerfile.dev     # Development container
├── docker-compose.yml     # Development environment
├── package.json           # Root scripts for development workflow
├── README.md
└── .gitignore
```

## Quick Start

### Prerequisites
- Node.js 18+
- Python 3.11+
- Docker (optional)

### Development Setup

1. **Clone and setup the project:**
   ```bash
   git clone https://github.com/your-username/ai-code-reviewer.git
   cd ai-code-reviewer
   ```

2. **Install all dependencies at once:**
   ```bash
   npm run install:all
   ```
   
   This will install:
   - Root dependencies
   - Frontend dependencies
   - Backend dependencies

3. **Start the development servers:**
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

4. **Using Docker (Alternative):**
   ```bash
   npm run docker:up
   ```

5. **Environment Configuration:**
   ```bash
   # Copy the example environment file
   cd backend
   cp .env.example .env
   ```

### Access the Application

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs

## Features (Sprint 1)

- ✅ Interactive code editor with Monaco Editor
  - Syntax highlighting for multiple languages
  - File upload functionality
  - Example code templates
  - Drag and drop support
- ✅ Multi-language support
  - Python, JavaScript, TypeScript, Java, C++, and more
  - Automatic language detection from file extension
- ✅ Comprehensive code analysis
  - Detection of bugs, security issues, and style problems
  - Code metrics (complexity, maintainability)
  - Severity-based issue categorization
  - Suggestions and explanations for each issue
- ✅ Modern, responsive UI with Tailwind CSS
  - Analysis results dashboard
  - Issue breakdown by severity
  - Export functionality for analysis reports
- ✅ RESTful API with FastAPI
  - Health check endpoint
  - Code analysis endpoint
  - Supported languages endpoint
  - Analysis types endpoint

## Tech Stack

### Frontend
- **Framework**: Next.js 14+ with TypeScript and App Router
- **UI/Styling**:
  - Tailwind CSS for styling
  - Radix UI components
  - Lucide React for icons
  - Class Variance Authority for component variants
- **Code Editor**: Monaco Editor (@monaco-editor/react)
- **Utilities**:
  - clsx and tailwind-merge for class name management
  - TypeScript for type safety

### Backend
- **Framework**: FastAPI
- **Language**: Python 3.11+
- **Data Validation**: Pydantic v2
- **Server**: Uvicorn (ASGI)
- **Development Tools**:
  - Docker for containerization
  - Environment variable management
  - Type checking with mypy
  - Code formatting with Black

### DevOps
- Docker and Docker Compose for containerization
- Concurrently for running multiple services

## Development

### Running Tests
```bash
# Backend tests
cd backend
pytest

# Frontend tests
cd frontend
npm test
```

### Project Scripts

The root `package.json` includes several useful scripts:

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

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

MIT License
