# React + Vite

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Babel](https://babeljs.io/) for Fast Refresh
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/) for Fast Refresh

## Expanding the ESLint configuration

If you are developing a production application, we recommend using TypeScript with type-aware lint rules enabled. Check out the [TS template](https://github.com/vitejs/vite/tree/main/packages/create-vite/template-react-ts) for information on how to integrate TypeScript and [`typescript-eslint`](https://typescript-eslint.io) in your project.

# Scintilla Frontend

A modern React frontend for the Scintilla federated search system, built with Vite and styled with Tailwind CSS.

## Features

- **Real-time Search**: Stream responses from the Scintilla backend with live updates
- **Modern UI**: Dashworks-inspired interface with Scintilla branding
- **Tool Integration**: Display tool usage and results from MCP servers
- **Connection Status**: Real-time backend connection monitoring
- **Quick Actions**: Pre-defined search queries for common tasks
- **Responsive Design**: Works on desktop and mobile devices

## Architecture

### API Integration
- **Service Layer**: `src/services/api.js` handles all backend communication
- **Custom Hook**: `src/hooks/useScintilla.js` manages state and streaming
- **Components**: Modular React components with real-time updates

### Key Components
- `App.jsx`: Main application layout and chat interface
- `IntegrationDemo.jsx`: Connection testing and validation
- `useScintilla.js`: React hook for backend integration
- `api.js`: API service with streaming support

## Backend Integration

The frontend integrates with the Scintilla backend running on `http://localhost:8000`:

### Endpoints Used
- `GET /health`: Health check and connection status
- `POST /api/query`: Main search/chat endpoint with streaming support

### Features Integrated
- **Streaming Responses**: Real-time message updates via Server-Sent Events
- **Tool Calling**: Display of MCP tool usage and results
- **Search Modes**: Support for conversational and search-focused modes
- **Error Handling**: Graceful error display and retry mechanisms

## Development

### Prerequisites
- Node.js 18+ and npm
- Scintilla backend running on port 8000

### Setup
```bash
cd web
npm install
npm run dev
```

The frontend will be available at `http://localhost:5173`

### Testing Integration
1. Ensure the backend is running: `cd .. && python -m uvicorn src.main:app --reload`
2. Start the frontend: `npm run dev`
3. Use the "Integration Test" button in the sidebar to verify connection
4. Check browser console for automatic connection tests

### Configuration
- **API Base URL**: Configured in `src/services/api.js`
- **CORS**: Backend allows `localhost:5173` for development
- **Authentication**: Currently uses mock token (TODO: implement real auth)

## Production Deployment

For production deployment:

1. Build the frontend: `npm run build`
2. Serve the `dist` folder with a web server
3. Update API base URL for production backend
4. Configure proper authentication tokens

## Integration Status

✅ **Health Checks**: Backend connection monitoring  
✅ **Streaming**: Real-time response streaming  
✅ **Tool Display**: MCP tool usage visualization  
✅ **Error Handling**: Graceful error recovery  
✅ **CORS**: Cross-origin requests configured  
🔄 **Authentication**: Mock tokens (needs real implementation)  
🔄 **Bot Selection**: Static bot ID (needs dynamic selection)  

## Troubleshooting

### Common Issues

**Backend Connection Failed**
- Ensure backend is running on port 8000
- Check CORS configuration in `src/main.py`
- Verify network connectivity

**Streaming Not Working**
- Check browser console for SSE errors
- Verify backend streaming endpoint
- Test with non-streaming mode first

**Authentication Errors**
- Currently using mock tokens
- Check `Authorization` header in API requests
- Implement real authentication as needed
