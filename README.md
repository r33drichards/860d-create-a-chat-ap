# Chat App with FastAPI

A simple chat app built with FastAPI and pydantic-ai, demonstrating:

- Reusing chat history
- Serializing messages
- Streaming responses
- Modern dependency management with uv and nix

## Prerequisites

- Python 3.8+
- [uv](https://docs.astral.sh/uv/) for Python dependency management
- [nix](https://nixos.org/) for reproducible development environment (optional)
- An OpenAI API key

## Setup

### Using Nix (Recommended)

If you have nix with flakes enabled:

```bash
# Enter the development shell
nix develop

# Install Python dependencies
uv sync

# Set your OpenAI API key
export OPENAI_API_KEY="your-api-key-here"
```

### Using uv only

```bash
# Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync

# Set your OpenAI API key
export OPENAI_API_KEY="your-api-key-here"
```

## Running the Application

```bash
# Run the chat app
uv run python -m chat_app

# Or alternatively
uv run uvicorn chat_app.app:app --reload
```

Then open your browser to [http://localhost:8000](http://localhost:8000)

## Features

- **Real-time chat**: Messages stream in real-time as the AI responds
- **Chat history**: Previous conversations are preserved and provide context
- **Modern UI**: Clean, responsive interface using Bootstrap
- **SQLite storage**: Messages are persisted in a local SQLite database
- **TypeScript frontend**: Modern frontend with TypeScript compiled in the browser

## Project Structure

```
chat_app/
├── __init__.py
├── __main__.py          # Entry point for running the app
├── app.py              # Main FastAPI application
└── static/
    ├── chat_app.html   # Frontend HTML
    └── chat_app.ts     # TypeScript frontend logic
pyproject.toml          # Python project configuration
flake.nix              # Nix development environment
```

## Environment Variables

- `OPENAI_API_KEY`: Required. Your OpenAI API key for the chat functionality.

## Development

The application uses:
- **FastAPI** for the web framework
- **pydantic-ai** for AI agent functionality
- **SQLite** for message persistence
- **uv** for fast Python dependency management
- **nix** for reproducible development environments