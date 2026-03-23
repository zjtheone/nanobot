# Star-Office-UI Integration Guide

## Overview

This document describes how to integrate [Star-Office-UI](https://github.com/ringhyacinth/Star-Office-UI) with nanobot to provide real-time AI agent status visualization.

**Star-Office-UI**: A pixel office for your OpenClaw - turn invisible work states into a cozy little space with characters, daily notes, and guest agents.

## Integration Options

### Option 1: Lightweight Integration (Recommended)

Embed status dashboard components directly into nanobot's Streamlit Web Console.

#### Implementation Steps

1. **Create status dashboard module**
   ```bash
   touch web_console/status_dashboard.py
   ```

2. **Add state mapping logic**
   ```python
   # Map nanobot agent states to office zones
   STATE_TO_ZONE = {
       "idle": "lounge",      # 🛋 Rest area
       "writing": "desk",     # 💻 Work area
       "researching": "desk",
       "executing": "desk",
       "syncing": "desk",
       "error": "bug_zone",   # 🐛 Bug area
   }
   ```

3. **Integrate with agent_loop**
   - Modify `nanobot/core/agent_loop.py` to emit state changes
   - Use WebSocket or Server-Sent Events for real-time updates

4. **Add to Streamlit sidebar**
   ```python
   # web_console/app.py
   from status_dashboard import render_status_dashboard
   
   def render_sidebar():
       with st.sidebar:
           # ... existing code ...
           render_status_dashboard()
   ```

**Pros**:
- Minimal changes to existing architecture
- No additional dependencies
- Maintains nanobot's lightweight philosophy

**Cons**:
- Limited to Streamlit's UI capabilities
- No pixel animation (can add static icons)

---

### Option 2: Deep Integration

Run Star-Office-UI as a separate service and sync via API.

#### Architecture

```
┌─────────────┐         ┌──────────────────┐
│  nanobot    │ ──────▶ │  Star-Office-UI  │
│  Agent Loop │  POST   │  Flask Backend   │
│             │ /set_state│  (Port 19000)  │
└─────────────┘         └──────────────────┘
                              │
                              ▼
                        ┌─────────────┐
                        │  Frontend   │
                        │  (Pixel UI) │
                        └─────────────┘
```

#### Implementation Steps

1. **Install Star-Office-UI**
   ```bash
   git clone https://github.com/ringhyacinth/Star-Office-UI.git
   cd Star-Office-UI
   pip install -r backend/requirements.txt
   ```

2. **Configure state synchronization**
   ```bash
   # Create state.json
   cp state.sample.json state.json
   ```

3. **Add state hooks to nanobot**
   ```python
   # nanobot/core/agent_loop.py
   import requests
   
   class AgentLoop:
       def __init__(self, ...):
           self.office_url = os.getenv("STAR_OFFICE_URL", "http://127.0.0.1:19000")
       
       def _set_state(self, state: str, description: str):
           """Report agent state to Star-Office-UI."""
           try:
               requests.post(
                   f"{self.office_url}/set_state",
                   json={"state": state, "description": description},
                   timeout=2
               )
           except Exception:
               pass  # Non-critical, don't block agent
   ```

4. **Add to nanobot config**
   ```json
   {
     "integrations": {
       "star_office": {
         "enabled": true,
         "url": "http://127.0.0.1:19000",
         "auto_sync": true
       }
     }
   }
   ```

**Pros**:
- Full pixel animation experience
- Independent deployment
- Can integrate with other Agent systems

**Cons**:
- Additional service to maintain
- Requires Flask + frontend hosting

---

### Option 3: Skill-Based Integration

Create a nanobot skill that pushes status to Star-Office-UI.

#### Skill Structure

```
skills/
  star-office/
    __init__.py      # StarOfficeSkill class
    SKILL.md         # Skill documentation
    examples/
      demo.py        # Usage examples
```

#### Implementation

```python
# skills/star-office/__init__.py
class StarOfficeSkill:
    """Push nanobot status to Star-Office-UI."""
    
    def __init__(self, workspace: str):
        self.workspace = workspace
        self.office_url = self._load_config()
    
    def execute(self, command: str, **kwargs):
        """Execute Star-Office commands."""
        commands = {
            "set_state": self._set_state,
            "push_status": self._push_status,
            "get_agents": self._get_agents,
            "help": self._show_help,
        }
        
        if command not in commands:
            return {"error": f"Unknown command: {command}"}
        
        return commands[command](**kwargs)
    
    def _set_state(self, state: str, description: str):
        """Set agent state in Star-Office-UI."""
        response = requests.post(
            f"{self.office_url}/set_state",
            json={"state": state, "description": description},
        )
        return response.json()
    
    def _show_help(self):
        """Show available commands."""
        return {
            "commands": {
                "set_state": "Set agent state (idle/writing/researching/executing/syncing/error)",
                "push_status": "Push current status to office",
                "get_agents": "Get list of active agents",
            }
        }
```

#### Usage

```bash
# In nanobot chat
nanobot> Install skill: star-office
nanobot> star-office set_state writing "正在整理文档"
nanobot> star-office push_status
```

**Pros**:
- Follows nanobot skill architecture
- Optional installation
- Easy to maintain and update

**Cons**:
- Requires manual state updates
- Less automatic than Option 2

---

## State Mapping

### nanobot Agent States → Star-Office-UI Zones

| nanobot State | Trigger Scenario | Office Zone | Icon |
|--------------|------------------|-------------|------|
| `idle` | Waiting for tasks | 🛋 Lounge (Sofa) | 😌 |
| `writing` | Writing code/docs | 💻 Desk | ✍️ |
| `researching` | Web search/research | 💻 Desk | 🔍 |
| `executing` | Running commands | 💻 Desk | ⚡ |
| `syncing` | Syncing data/pushing | 💻 Desk | 🔄 |
| `error` | Error/exception | 🐛 Bug Zone | 🐛 |

### nanobot Tools → Star-Office-UI States

```python
# Automatic state mapping based on tool usage
TOOL_TO_STATE = {
    "read_file": "writing",
    "write_file": "writing",
    "edit_file": "writing",
    "web_search": "researching",
    "web_fetch": "researching",
    "exec": "executing",
    "shell": "executing",
    "git_commit": "syncing",
    "git_push": "syncing",
    # ... more mappings
}
```

---

## Implementation Roadmap

### Phase 1: Core Integration (Week 1)
- [ ] Add state emission to `agent_loop.py`
- [ ] Create `status_dashboard.py` for Streamlit
- [ ] Test state synchronization
- [ ] Document integration in `README.md`

### Phase 2: Enhanced Features (Week 2)
- [ ] Add yesterday memo display from `memory/HISTORY.md`
- [ ] Implement subagent status tracking
- [ ] Add state-based notifications
- [ ] Create demo video/GIF

### Phase 3: Polish & Deployment (Week 3)
- [ ] Add configuration options
- [ ] Create Docker Compose setup
- [ ] Write integration tests
- [ ] Publish to nanobot docs

---

## Configuration

### Environment Variables

```bash
# Star-Office-UI Integration
STAR_OFFICE_ENABLED=true
STAR_OFFICE_URL=http://127.0.0.1:19000
STAR_OFFICE_AUTO_SYNC=true
STAR_OFFICE_AGENT_NAME="nanobot"
```

### nanobot Config (`~/.nanobot/config.json`)

```json
{
  "integrations": {
    "star_office": {
      "enabled": true,
      "url": "http://127.0.0.1:19000",
      "agent_name": "nanobot",
      "auto_sync": true,
      "state_mapping": {
        "idle": "idle",
        "coding": "writing",
        "searching": "researching",
        "executing": "executing",
        "syncing": "syncing",
        "error": "error"
      }
    }
  }
}
```

---

## API Reference

### Star-Office-UI Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/status` | GET | Get main agent status |
| `/set_state` | POST | Set agent state |
| `/agents` | GET | Get multi-agent list |
| `/join-agent` | POST | Guest agent joins office |
| `/agent-push` | POST | Guest agent pushes status |
| `/leave-agent` | POST | Guest agent leaves |
| `/yesterday-memo` | GET | Get yesterday's memo |

### Example: Set State

```python
import requests

response = requests.post(
    "http://127.0.0.1:19000/set_state",
    json={
        "state": "writing",
        "description": "正在整理文档"
    }
)
print(response.json())
```

---

## Troubleshooting

### Issue: State not syncing

**Solution**:
1. Check Star-Office-UI backend is running: `curl http://127.0.0.1:19000/health`
2. Verify network connectivity: `ping 127.0.0.1`
3. Check nanobot logs for errors

### Issue: Pixel characters not appearing

**Solution**:
1. Ensure `state.json` is properly configured
2. Check browser console for JavaScript errors
3. Clear browser cache and reload

### Issue: Multi-agent not working

**Solution**:
1. Verify `join-keys.json` exists and contains valid keys
2. Ensure guest agents use correct `OFFICE_URL`
3. Check firewall settings allow connections

---

## Credits

- **Star-Office-UI**: Created by [Ring Hyacinth](https://x.com/ring_hyacinth) & [Simon Lee](https://x.com/simonxxoo)
- **License**: Code under MIT; Art assets for non-commercial learning only
- **Repository**: https://github.com/ringhyacinth/Star-Office-UI

---

## See Also

- [nanobot Web Console Documentation](../web_console/README.md)
- [nanobot Skills System](../skills/README.md)
- [Star-Office-UI Official Docs](https://github.com/ringhyacinth/Star-Office-UI)
