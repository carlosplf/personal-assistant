# Memories folder

This folder stores persistent context for the Telegram assistant.
Each user has their own subfolder named after their Telegram user ID.

## Folder structure

```
memories/
  README.md                 ← This file
  {telegram_user_id}/       ← Per-user subfolder (e.g., 6496576962/)
    personal-assistant.md   ← Agent behavior rules for this user
    about-me.md             ← User profile and preferences
    contacts.csv            ← Contacts list (optional)
    *.md                    ← Any additional memory files
```

## Files per user

### `personal-assistant.md` (agent memory)
- Defines assistant behavior rules: tone, response style, priorities, and safety boundaries.
- This content is injected as agent-level context in every assistant request.

### `about-me.md` (user memory, priority)
- Stores stable user profile information: work, preferences, priorities, routines, and personal context.
- This content is injected selectively when relevant to the current request.

### `contacts.csv`
- CSV contact list with columns: Nome, email, telefone, relacionamento.
- Used by the `search_contacts` tool.

## Optional files

Add any `.md` files inside the user folder (e.g., `work.md`, `health.md`, `family.md`).
The assistant selects the most relevant files for each request.

## Runtime tools

The assistant can read and edit memory files directly using:
- `list_memory_files` — list files in the user's memory folder
- `read_memory_file` — read the contents of a file
- `edit_memory_file` — create or update a file (append or replace)

## Adding a new user

Create a subfolder for the new user's Telegram ID and add their memory files:

```bash
mkdir memories/{telegram_user_id}
cp memories/{existing_user_id}/personal-assistant.md memories/{telegram_user_id}/
# Create their about-me.md with user-specific info
```

## Guidelines

- Keep each file short, factual, and up to date.
- Do not store secrets (passwords, private keys, tokens).
- Use one topic per file for easier maintenance.
