#!/usr/bin/env bash
set -euo pipefail

# cli.Snippets installer
# Usage: curl -fsSL https://raw.githubusercontent.com/banglabs-eu/cli.snippets/main/install.sh | bash

REPO="https://github.com/banglabs-eu/cli.snippets.git"
BACKEND_REPO="https://github.com/banglabs-eu/SnippetsBackend.git"
INSTALL_DIR="$HOME/.cli-snippets"
BACKEND_DIR="$HOME/.cli-snippets-backend"
BIN_DIR="$HOME/.local/bin"
COMMAND_NAME="snippets"

# ── Colours ──

BOLD='\033[1m'
GREEN='\033[1;32m'
YELLOW='\033[1;33m'
RED='\033[1;31m'
CYAN='\033[1;36m'
DIM='\033[2m'
RESET='\033[0m'

info()  { printf "${GREEN}%s${RESET}\n" "$*"; }
warn()  { printf "${YELLOW}%s${RESET}\n" "$*"; }
error() { printf "${RED}%s${RESET}\n" "$*" >&2; exit 1; }
dim()   { printf "${DIM}%s${RESET}\n" "$*"; }

# ── OS detection ──

OS="$(uname -s)"

# Read user input even when piped from curl
ask() {
  printf "${CYAN}%s${RESET}" "$1"
  read -r REPLY < /dev/tty
}

# ── Banner ──

echo ""
printf "${GREEN}"
cat << 'BANNER'
       _ _    ____        _                  _
   ___| (_)  / ___| _ __ (_)_ __  _ __   ___| |_ ___
  / __| | |  \___ \| '_ \| | '_ \| '_ \ / _ \ __/ __|
 | (__| | | _ ___) | | | | | |_) | |_) |  __/ |_\__ \
  \___|_|_|(_)____/|_| |_|_| .__/| .__/ \___|\__|___/
                            |_|   |_|
BANNER
printf "${RESET}"
echo ""

# ── Prerequisites ──

if ! command -v git >/dev/null 2>&1; then
  if [ "$OS" = "Darwin" ]; then
    error "git is required but not installed. Run: brew install git  or  xcode-select --install"
  else
    error "git is required but not installed. Install it with your package manager (e.g. apt install git)."
  fi
fi

PYTHON=""
for py in python3 python; do
  if command -v "$py" >/dev/null 2>&1; then
    version=$("$py" -c 'import sys; print(sys.version_info[:2] >= (3, 10))' 2>/dev/null || echo "False")
    if [ "$version" = "True" ]; then
      PYTHON="$py"
      break
    fi
  fi
done
if [ -z "$PYTHON" ]; then
  if [ "$OS" = "Darwin" ]; then
    error "Python 3.10+ is required but not found. Run: brew install python@3.12"
  else
    error "Python 3.10+ is required but not found. Install it with your package manager (e.g. apt install python3)."
  fi
fi

dim "Using $($PYTHON --version)"

# ── Setup mode ──

echo ""
printf "${BOLD}How do you want to connect?${RESET}\n"
echo ""
echo "  1) Connect to backend.snippets.eu (recommended)"
echo "  2) Self-host — run your own backend + database"
echo ""
ask "Choose [1/2]: "
MODE="$REPLY"

case "$MODE" in
  2) SELF_HOST=true ;;
  *) SELF_HOST=false ;;
esac

# ── Install / Update CLI ──

echo ""
if [ -d "$INSTALL_DIR" ]; then
  info "Updating cli.Snippets..."
  git -C "$INSTALL_DIR" pull --ff-only 2>/dev/null || warn "Pull failed — continuing with existing version."
else
  info "Cloning cli.Snippets..."
  git clone --quiet "$REPO" "$INSTALL_DIR"
fi

# ── Virtual environment ──

VENV_DIR="$INSTALL_DIR/.venv"

if [ ! -d "$VENV_DIR" ]; then
  info "Creating virtual environment..."
  $PYTHON -m venv "$VENV_DIR"
fi

# Ensure pip is available inside the venv (Debian/Ubuntu venvs may lack it)
if [ ! -x "$VENV_DIR/bin/pip" ]; then
  info "Bootstrapping pip in virtual environment..."
  if ! "$VENV_DIR/bin/python" -m ensurepip --upgrade 2>/dev/null; then
    warn "ensurepip not available — downloading get-pip.py..."
    curl -fsSL https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py \
      || error "Failed to download get-pip.py. Check your internet connection."
    "$VENV_DIR/bin/python" /tmp/get-pip.py --quiet \
      || error "Failed to install pip. Try: sudo apt install python3-venv"
    rm -f /tmp/get-pip.py
  fi
fi

info "Installing dependencies..."
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"

# ── Backend setup ──

BACKEND_URL=""

if [ "$SELF_HOST" = true ]; then
  # ── Self-host: Docker + Backend ──

  if ! command -v docker >/dev/null 2>&1; then
    if [ "$OS" = "Darwin" ]; then
      error "Docker is required for self-hosting. Install Docker Desktop for Mac: https://docs.docker.com/desktop/install/mac-install/"
    else
      error "Docker is required for self-hosting. Install it from https://docs.docker.com/get-docker/"
    fi
  fi
  docker compose version >/dev/null 2>&1 || error "Docker Compose v2 is required. Update Docker or install the compose plugin."

  echo ""
  printf "${BOLD}Database setup${RESET}\n"
  echo ""
  echo "  1) Use Docker PostgreSQL (easiest — runs everything in containers)"
  echo "  2) Use an existing PostgreSQL database (provide a connection URL)"
  echo ""
  ask "Choose [1/2]: "
  DB_MODE="$REPLY"

  if [ -d "$BACKEND_DIR" ]; then
    info "Updating backend..."
    git -C "$BACKEND_DIR" pull --ff-only 2>/dev/null || warn "Pull failed — continuing with existing version."
  else
    info "Cloning backend..."
    git clone --quiet "$BACKEND_REPO" "$BACKEND_DIR"
  fi

  # Generate a random JWT secret
  JWT_SECRET=$(head -c 32 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9' | head -c 40)

  if [ "$DB_MODE" = "1" ]; then
    # Docker PostgreSQL — write a compose override with a postgres service
    DB_PASS=$(head -c 16 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9' | head -c 20)
    DATABASE_URL="postgresql://snippets:${DB_PASS}@db:5432/snippets"

    cat > "$BACKEND_DIR/docker-compose.override.yml" << COMPOSE
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: snippets
      POSTGRES_PASSWORD: ${DB_PASS}
      POSTGRES_DB: snippets
    volumes:
      - snippets_pgdata:/var/lib/postgresql/data
    restart: unless-stopped

  backend:
    depends_on:
      - db

volumes:
  snippets_pgdata:
COMPOSE

    info "Docker PostgreSQL configured."

  else
    # External database
    echo ""
    ask "PostgreSQL URL (postgresql://user:pass@host:port/dbname): "
    DATABASE_URL="$REPLY"
    [ -n "$DATABASE_URL" ] || error "Database URL is required."
  fi

  # Write backend .env
  cat > "$BACKEND_DIR/.env.dev" << ENVFILE
DATABASE_URL=${DATABASE_URL}
JWT_SECRET=${JWT_SECRET}
JWT_EXPIRY_HOURS=720
ALLOWED_ORIGINS=*
DEBUG=false
DB_POOL_MIN=2
DB_POOL_MAX=10
ENVFILE

  BACKEND_URL="http://localhost:8000"

  info "Starting backend..."
  (cd "$BACKEND_DIR" && docker compose up -d --build) || error "Failed to start backend. Check Docker logs: docker compose -f $BACKEND_DIR/docker-compose.yml logs"

  echo ""
  info "Backend running at $BACKEND_URL"

  # Create a convenience command to manage the backend
  cat > "$BIN_DIR/snippets-backend" << MGMT
#!/usr/bin/env bash
# Manage the cli.Snippets backend
cd "$BACKEND_DIR"
case "\${1:-status}" in
  start)   docker compose up -d ;;
  stop)    docker compose down ;;
  restart) docker compose restart ;;
  logs)    docker compose logs -f --tail=50 ;;
  status)  docker compose ps ;;
  *)       echo "Usage: snippets-backend {start|stop|restart|logs|status}" ;;
esac
MGMT
  chmod +x "$BIN_DIR/snippets-backend"

else
  # ── Connect to backend.snippets.eu ──

  BACKEND_URL="https://api.snippets.eu"
  info "Using backend at $BACKEND_URL"
fi

# ── CLI .env ──

cat > "$INSTALL_DIR/.env" << ENVFILE
BACKEND_URL=${BACKEND_URL}
EXPORT_DIR=${INSTALL_DIR}/exports
SNIPPETS_LANG=en
ENVFILE

mkdir -p "$INSTALL_DIR/exports"

# ── Wrapper script ──

mkdir -p "$BIN_DIR"

cat > "$BIN_DIR/$COMMAND_NAME" << 'WRAPPER'
#!/usr/bin/env bash
exec "$HOME/.cli-snippets/.venv/bin/python" "$HOME/.cli-snippets/main.py" "$@"
WRAPPER
chmod +x "$BIN_DIR/$COMMAND_NAME"

# ── PATH check ──

if ! echo "$PATH" | tr ':' '\n' | grep -qx "$BIN_DIR"; then
  SHELL_NAME="$(basename "${SHELL:-bash}")"
  case "$SHELL_NAME" in
    zsh)  RC="$HOME/.zshrc" ;;
    bash) RC="$HOME/.bashrc" ;;
    fish) RC="$HOME/.config/fish/config.fish" ;;
    *)    RC="$HOME/.profile" ;;
  esac

  if [ "$SHELL_NAME" = "fish" ]; then
    LINE="fish_add_path $BIN_DIR"
  else
    LINE="export PATH=\"\$HOME/.local/bin:\$PATH\""
  fi

  if ! grep -qF "$BIN_DIR" "$RC" 2>/dev/null; then
    echo "$LINE" >> "$RC"
    warn "Added $BIN_DIR to PATH in $RC — restart your shell or run:"
    warn "  $LINE"
  fi
fi

# ── Done ──

echo ""
printf "${GREEN}${BOLD}cli.Snippets installed!${RESET}\n"
echo ""
echo "  Run:            snippets"
echo "  Config:         ~/.cli-snippets/.env"
if [ "$SELF_HOST" = true ]; then
echo "  Backend logs:   snippets-backend logs"
echo "  Stop backend:   snippets-backend stop"
fi
echo "  Update:         re-run this installer"
echo ""
