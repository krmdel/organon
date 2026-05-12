# Extracting Substack Credentials

`tool-substack` needs three env vars in `.env` to authenticate against
Substack's private draft API. All three come from your logged-in browser
session — there is no OAuth flow.

## Required

```bash
SUBSTACK_PUBLICATION_URL=https://your-publication.substack.com
SUBSTACK_SESSION_TOKEN=s%3A...      # substack.sid cookie value
SUBSTACK_USER_ID=123456789           # integer user id
```

## Step-by-step

### 1. SUBSTACK_PUBLICATION_URL

The root URL of the publication you want to push drafts to. For a sandbox
this will be something like `https://organon-sandbox.substack.com`. **Do
not include a trailing slash.**

### 2. SUBSTACK_SESSION_TOKEN

1. Log into your publication at `https://{your-pub}.substack.com` in Chrome
2. Open DevTools (⌘⌥I on macOS)
3. Go to **Application** → **Cookies** → select `https://substack.com` in
   the left pane
4. Find the row named **`substack.sid`**
5. Copy the **Value** column — it will start with `s%3A` and be a long
   URL-encoded string
6. That's your `SUBSTACK_SESSION_TOKEN`

> **The token rotates** on any logout. If pushes start failing with 401,
> re-extract the cookie.

### 3. SUBSTACK_USER_ID

1. Still in DevTools, switch to the **Network** tab
2. Refresh the page
3. Filter for `subscription`
4. Click any matching request
5. In the response body, look for `"user_id": 123456789`
6. That integer is your `SUBSTACK_USER_ID`

Alternative: open any Substack page where you're logged in and run in the
JavaScript console:

```javascript
fetch('/api/v1/subscription').then(r => r.json()).then(d => console.log(d.user_id))
```

## Verify

Once all three are in `.env`:

```bash
python3 .claude/skills/tool-substack/scripts/substack_ops.py test-auth
```

Expected output ends with `session valid ✓`. If it says session invalid,
re-extract the cookie.

## Security

- `.env` is gitignored — never commit it
- The session token is as sensitive as your Substack password — treat it
  as a credential
- Use a **sandbox** publication for first runs, not production
- The token rotates on logout; if you log out of Substack in Chrome, the
  token in `.env` is dead and needs re-extraction
