
"""Simple chat app example built with FastAPI."""

from __future__ import annotations as _annotations

import asyncio
import json
import sqlite3
import uuid
from collections.abc import AsyncIterator, Callable
from concurrent.futures.thread import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from typing import Annotated, Any, Literal, TypeVar

import fastapi
import logfire
from fastapi import Depends, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from typing_extensions import LiteralString, ParamSpec, TypedDict

from pydantic_ai import Agent, UnexpectedModelBehavior
from pydantic_ai.mcp import load_mcp_servers
from pydantic_ai.messages import (
    ModelMessage,
    ModelMessagesTypeAdapter,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)

logfire.configure(send_to_logfire='if-token-present')
logfire.instrument_pydantic_ai()

THIS_DIR = Path(__file__).parent
# Load MCP servers from configuration
mcp_servers = load_mcp_servers(THIS_DIR.parent.parent / 'mcp_config.json')
agent = Agent('openai:gpt-4o', toolsets=mcp_servers)


@asynccontextmanager
async def lifespan(_app: fastapi.FastAPI):
    async with Database.connect() as db:
        yield {'db': db}


app = fastapi.FastAPI(lifespan=lifespan)
logfire.instrument_fastapi(app)


@app.get('/')
async def index() -> FileResponse:
    return FileResponse((THIS_DIR / 'static' / 'chat_app.html'), media_type='text/html')


@app.get('/chat_app.ts')
async def main_ts() -> FileResponse:
    """Get the raw typescript code, it's compiled in the browser, forgive me."""
    return FileResponse((THIS_DIR / 'static' / 'chat_app.ts'), media_type='text/plain')


async def get_db(request: Request) -> 'Database':
    return request.state.db


@app.post('/sessions/')
async def create_session(database: 'Database' = Depends(get_db)) -> dict:
    session_id = await database.create_session()
    return {'session_id': session_id}


@app.get('/sessions/')
async def get_sessions(database: 'Database' = Depends(get_db)) -> dict:
    sessions = await database.get_sessions()
    return {'sessions': sessions}


@app.get('/chat/{session_id}')
async def get_chat(session_id: str, database: 'Database' = Depends(get_db)) -> Response:
    await database.update_session_access(session_id)
    msgs = await database.get_messages(session_id)
    return Response(
        b'\n'.join(json.dumps(to_chat_message(m)).encode('utf-8') for m in msgs),
        media_type='text/plain',
    )


class ChatMessage(TypedDict):
    """Format of messages sent to the browser."""

    role: Literal['user', 'model']
    timestamp: str
    content: str


def to_chat_message(m: ModelMessage) -> ChatMessage:
    first_part = m.parts[0]
    if isinstance(m, ModelRequest):
        if isinstance(first_part, UserPromptPart):
            assert isinstance(first_part.content, str)
            return {
                'role': 'user',
                'timestamp': first_part.timestamp.isoformat(),
                'content': first_part.content,
            }
    elif isinstance(m, ModelResponse):
        if isinstance(first_part, TextPart):
            return {
                'role': 'model',
                'timestamp': m.timestamp.isoformat(),
                'content': first_part.content,
            }
    raise UnexpectedModelBehavior(f'Unexpected message type for chat app: {m}')


@app.post('/chat/{session_id}')
async def post_chat(
    session_id: str,
    prompt: Annotated[str, fastapi.Form()],
    database: 'Database' = Depends(get_db)
) -> StreamingResponse:
    await database.update_session_access(session_id)

    async def stream_messages():
        """Streams new line delimited JSON `Message`s to the client."""
        yield (
            json.dumps(
                {
                    'role': 'user',
                    'timestamp': datetime.now(tz=timezone.utc).isoformat(),
                    'content': prompt,
                }
            ).encode('utf-8')
            + b'\n'
        )
        messages = await database.get_messages(session_id)
        try:
            async with agent:  # Manage MCP server connections
                async with agent.run_stream(prompt, message_history=messages) as result:
                    async for text in result.stream_output(debounce_by=0.01):
                        m = ModelResponse(parts=[TextPart(text)], timestamp=result.timestamp())
                        yield json.dumps(to_chat_message(m)).encode('utf-8') + b'\n'

                await database.add_messages(session_id, result.new_messages_json())
        except Exception as e:  # Fallback if MCP tools fail
            logfire.error("MCP initialization or run failed, falling back to no-tools agent", error=e)
            fallback_agent = Agent('openai:gpt-4o')
            async with fallback_agent.run_stream(prompt, message_history=messages) as result:
                async for text in result.stream_output(debounce_by=0.01):
                    m = ModelResponse(parts=[TextPart(text)], timestamp=result.timestamp())
                    yield json.dumps(to_chat_message(m)).encode('utf-8') + b'\n'

            await database.add_messages(session_id, result.new_messages_json())

    return StreamingResponse(stream_messages(), media_type='text/plain')


P = ParamSpec('P')
R = TypeVar('R')


@dataclass
class Database:
    """Rudimentary database to store chat messages in SQLite."""

    con: sqlite3.Connection
    _loop: asyncio.AbstractEventLoop
    _executor: ThreadPoolExecutor

    @classmethod
    @asynccontextmanager
    async def connect(
        cls, file: Path = THIS_DIR / '.chat_app_messages.sqlite'
    ) -> AsyncIterator['Database']:
        with logfire.span('connect to DB'):
            loop = asyncio.get_event_loop()
            executor = ThreadPoolExecutor(max_workers=1)
            con = await loop.run_in_executor(executor, cls._connect, file)
            slf = cls(con, loop, executor)
        try:
            yield slf
        finally:
            await slf._asyncify(con.close)

    @staticmethod
    def _connect(file: Path) -> sqlite3.Connection:
        con = sqlite3.connect(str(file))
        con = logfire.instrument_sqlite3(con)
        cur = con.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                last_accessed TEXT NOT NULL
            );
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                message_list TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions (id)
            );
        ''')
        con.commit()
        return con

    async def create_session(self) -> str:
        session_id = str(uuid.uuid4())
        now = datetime.now(tz=timezone.utc).isoformat()
        await self._asyncify(
            self._execute,
            'INSERT INTO sessions (id, created_at, last_accessed) VALUES (?, ?, ?)',
            session_id, now, now,
            commit=True
        )
        return session_id

    async def update_session_access(self, session_id: str):
        now = datetime.now(tz=timezone.utc).isoformat()
        await self._asyncify(
            self._execute,
            'UPDATE sessions SET last_accessed = ? WHERE id = ?',
            now, session_id,
            commit=True
        )

    async def get_sessions(self) -> list[dict]:
        c = await self._asyncify(
            self._execute,
            'SELECT id, created_at, last_accessed FROM sessions ORDER BY last_accessed DESC'
        )
        rows = await self._asyncify(c.fetchall)
        return [
            {
                'id': row[0],
                'created_at': row[1],
                'last_accessed': row[2]
            }
            for row in rows
        ]

    async def add_messages(self, session_id: str, messages: bytes):
        now = datetime.now(tz=timezone.utc).isoformat()
        await self._asyncify(
            self._execute,
            'INSERT INTO messages (session_id, message_list, created_at) VALUES (?, ?, ?)',
            session_id, messages, now,
            commit=True,
        )

    async def get_messages(self, session_id: str) -> list[ModelMessage]:
        c = await self._asyncify(
            self._execute,
            'SELECT message_list FROM messages WHERE session_id = ? ORDER BY id',
            session_id
        )
        rows = await self._asyncify(c.fetchall)
        messages: list[ModelMessage] = []
        for row in rows:
            messages.extend(ModelMessagesTypeAdapter.validate_json(row[0]))
        return messages

    def _execute(
        self, sql: LiteralString, *args: Any, commit: bool = False
    ) -> sqlite3.Cursor:
        cur = self.con.cursor()
        cur.execute(sql, args)
        if commit:
            self.con.commit()
        return cur

    async def _asyncify(
        self, func: Callable[P, R], *args: P.args, **kwargs: P.kwargs
    ) -> R:
        return await self._loop.run_in_executor(
            self._executor,
            partial(func, **kwargs),
            *args,
        )