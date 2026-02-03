# a2ui

This project is a full-stack application with a Python FastAPI backend and React TypeScript frontend, managed with Nx monorepo.

## Project Structure

```
a2ui/
├── apps/
│   └── frontend/          # React TypeScript app
│       ├── src/
│       ├── public/
│       └── package.json
├── backend/               # Python FastAPI (outside Nx)
│   ├── app.py
│   ├── openai_service.py
│   └── requirements.txt
├── libs/                  # Shared libraries (for future use)
├── nx.json               # Nx configuration
└── package.json          # Root package.json
```

## Getting Started

### Prerequisites
- Node.js (v16+)
- Python 3.8+
- npm or yarn

### Installation

1. Install frontend dependencies:
   ```bash
   npm install
   ```

2. Install backend dependencies:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

### Running the Application

**Frontend:**
```bash
npm run frontend:start
# or
nx start frontend
```
The frontend will run on `http://localhost:3000`

**Backend:**
```bash
npm run backend:start
# or
cd backend && python app.py
```
The backend API will run on `http://localhost:8000`

### Building for Production

**Frontend:**
```bash
npm run frontend:build
# or
nx build frontend
```

### Nx Commands

- `nx start frontend` - Start the frontend dev server
- `nx build frontend` - Build the frontend
- `nx test frontend` - Run frontend tests
- `nx graph` - View the project dependency graph

## Backend (Python FastAPI)

The backend is a separate Python application that is not managed by Nx. It provides REST API endpoints for the frontend.

### API Endpoints
- `GET /api` - Welcome message
- `POST /api/openai` - OpenAI completion endpoint

## Frontend (React + TypeScript)

The frontend is a React application with TypeScript, managed by Nx using react-scripts.
