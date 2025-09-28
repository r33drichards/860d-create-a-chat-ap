import { marked } from 'https://cdnjs.cloudflare.com/ajax/libs/marked/15.0.0/lib/marked.esm.js'
const convElement = document.getElementById('conversation')
const promptInput = document.getElementById('prompt-input') as HTMLInputElement
const spinner = document.getElementById('spinner')
const sessionsContainer = document.getElementById('sessions-container')
const newSessionBtn = document.getElementById('new-session-btn')
const currentSessionElement = document.getElementById('current-session')

let currentSessionId: string = null

async function onFetchResponse(response: Response): Promise<void> {
  let text = ''
  let decoder = new TextDecoder()
  if (response.ok) {
    const reader = response.body.getReader()
    while (true) {
      const {done, value} = await reader.read()
      if (done) {
        break
      }
      text += decoder.decode(value)
      addMessages(text)
      spinner.classList.remove('active')
    }
    addMessages(text)
    promptInput.disabled = false
    promptInput.focus()
  } else {
    const text = await response.text()
    console.error(`Unexpected response: ${response.status}`, {response, text})
    throw new Error(`Unexpected response: ${response.status}`)
  }
}

interface Message {
  role: string
  content: string
  timestamp: string
}

function addMessages(responseText: string) {
  const lines = responseText.split('\n')
  const messages: Message[] = lines.filter(line => line.length > 1).map(j => JSON.parse(j))
  for (const message of messages) {
    const {timestamp, role, content} = message
    const id = `msg-${timestamp}`
    let msgDiv = document.getElementById(id)
    if (!msgDiv) {
      msgDiv = document.createElement('div')
      msgDiv.id = id
      msgDiv.title = `${role} at ${timestamp}`
      msgDiv.classList.add('border-top', 'pt-2', role)
      convElement.appendChild(msgDiv)
    }
    msgDiv.innerHTML = marked.parse(content)
  }
  window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' })
}

function onError(error: any) {
  console.error(error)
  document.getElementById('error').classList.remove('d-none')
  document.getElementById('spinner').classList.remove('active')
}

async function createNewSession(): Promise<string> {
  const response = await fetch('/sessions/', { method: 'POST' })
  const data = await response.json()
  return data.session_id
}

async function loadSessions(): Promise<void> {
  const response = await fetch('/sessions/')
  const data = await response.json()

  sessionsContainer.innerHTML = ''

  for (const session of data.sessions) {
    const sessionDiv = document.createElement('div')
    sessionDiv.classList.add('session-item', 'p-2', 'border-bottom')
    sessionDiv.innerHTML = `
      <div class="d-flex justify-content-between align-items-center">
        <div>
          <small class="text-muted">Session: ${session.id.substring(0, 8)}...</small><br>
          <small>Last accessed: ${new Date(session.last_accessed).toLocaleString()}</small>
        </div>
        <button class="btn btn-sm btn-outline-primary load-session-btn" data-session-id="${session.id}">
          Load
        </button>
      </div>
    `
    sessionsContainer.appendChild(sessionDiv)
  }

  document.querySelectorAll('.load-session-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const sessionId = (e.target as HTMLElement).getAttribute('data-session-id')
      loadSession(sessionId)
    })
  })
}

async function loadSession(sessionId: string): Promise<void> {
  currentSessionId = sessionId
  currentSessionElement.textContent = `Session: ${sessionId.substring(0, 8)}...`

  convElement.innerHTML = ''

  const response = await fetch(`/chat/${sessionId}`)
  await onFetchResponse(response)
}

async function onSubmit(e: SubmitEvent): Promise<void> {
  e.preventDefault()

  if (!currentSessionId) {
    currentSessionId = await createNewSession()
    currentSessionElement.textContent = `Session: ${currentSessionId.substring(0, 8)}...`
    await loadSessions()
  }

  spinner.classList.add('active')
  const body = new FormData(e.target as HTMLFormElement)

  promptInput.value = ''
  promptInput.disabled = true

  const response = await fetch(`/chat/${currentSessionId}`, {method: 'POST', body})
  await onFetchResponse(response)
}

document.querySelector('form').addEventListener('submit', (e) => onSubmit(e).catch(onError))

newSessionBtn?.addEventListener('click', async () => {
  currentSessionId = await createNewSession()
  currentSessionElement.textContent = `Session: ${currentSessionId.substring(0, 8)}...`
  convElement.innerHTML = ''
  await loadSessions()
})

loadSessions().catch(onError)