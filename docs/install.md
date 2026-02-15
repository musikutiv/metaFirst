---
title: Setting up metaFirst
---

# Setting up metaFirst

This page walks you through getting metaFirst running on a computer in
your lab. You'll need about 15 minutes and a machine running macOS or
Linux.

## What you'll need

- **Python 3.11 or newer.** Check by opening a terminal and typing
  `python3 --version`. If the number is 3.11 or higher, you're good.
  If not, install it — on macOS the easiest way is
  [Homebrew](https://brew.sh/): `brew install python@3.12`.
- **Node.js 18 or newer** (for the web interface). Check with
  `node --version`. Install via Homebrew (`brew install node`) or
  [the Node.js website](https://nodejs.org/).
- **Git**, to download the code. Most macOS and Linux systems have this
  already (`git --version` to check).

## Step 1 — Get the code

Open a terminal and run:

```
git clone https://github.com/bmc-CompBio/metaFirst.git
cd metaFirst
```

## Step 2 — Run the install script

```
./scripts/install_supervisor.sh
```

This sets up the backend. It will:
- create an isolated Python environment (so it won't touch your system),
- install the required packages, and
- load a small set of demo data (users, projects, sample fields) so you
  can try things out immediately.

When the script finishes it prints the commands you'll need in the next
step.

## Step 3 — Start the backend

Open a terminal and run:

```
cd supervisor
source venv/bin/activate
uvicorn supervisor.main:app --reload --host 0.0.0.0 --port 8000
```

Leave this terminal open — the backend keeps running here.

## Step 4 — Start the web interface

Open a **second** terminal and run:

```
cd supervisor-ui
npm install
npm run dev
```

You should see a message like *"Local: http://localhost:5173"*. Leave
this terminal open too.

## Step 5 — Open it in the browser

Go to **<http://localhost:5173>** in any browser on the same machine.

You'll see a login screen. The demo comes with five test users you can
try right away:

| User    | Password |
|---------|----------|
| alice   | demo123  |
| bob     | demo123  |
| carol   | demo123  |
| david   | demo123  |
| eve     | demo123  |

Pick any of them, log in, and explore — you can browse projects, create
samples, and see how the metadata forms work.

## Letting others on the lab network connect

By default, the web interface only listens on your own machine. To let
colleagues on the same network open it in their browser:

```
cd supervisor-ui
npm install
export VITE_ALLOWED_HOSTS="<YOUR_HOSTNAME_OR_IP>"
npm run dev -- --host 0.0.0.0 --port 5173
```

Replace `<YOUR_HOSTNAME_OR_IP>` with the name or IP address others will
use (e.g. `labpc.local` or `192.168.1.42`). They can then open
`http://<YOUR_HOSTNAME_OR_IP>:5173` in their browser.

## Troubleshooting

**"python3: command not found"** — Python isn't installed or isn't on
your PATH. Install it (see "What you'll need" above).

**"python3 version is too old"** — You need 3.11+. On macOS:
`brew install python@3.12`. You can also point the install script at a
specific Python: `PYTHON_BIN=/path/to/python3.12 ./scripts/install_supervisor.sh`.

**The backend starts but the browser shows nothing** — Make sure both
the backend (port 8000) and the web interface (port 5173) are running in
separate terminals.

**Login fails (401 error)** — The demo database may be missing. Re-run
the install script with `./scripts/install_supervisor.sh --seed`.

**"Host not allowed" in the browser** — You're connecting from another
machine but didn't set `VITE_ALLOWED_HOSTS`. See "Letting others on the
lab network connect" above.

**Port already in use** — Another program is using port 8000 or 5173.
Either stop that program or pick a different port (e.g.
`--port 8001`).
