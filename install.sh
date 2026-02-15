#!/bin/bash
# Local Pigeon Installer for macOS/Linux
# Usage: curl -sSL https://raw.githubusercontent.com/tradermichael/local_pigeon/main/install.sh | bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

INSTALL_DIR="$HOME/.local_pigeon"
VENV_DIR="$INSTALL_DIR/venv"
REPO_URL="https://github.com/tradermichael/local_pigeon.git"
MIN_PYTHON_VERSION="3.10"

echo -e "${BLUE}"
echo "  _                     _   ____  _                       "
echo " | |    ___   ___ __ _| | |  _ \(_) __ _  ___  ___  _ __  "
echo " | |   / _ \ / __/ _\` | | | |_) | |/ _\` |/ _ \/ _ \| '_ \ "
echo " | |__| (_) | (_| (_| | | |  __/| | (_| |  __/ (_) | | | |"
echo " |_____\___/ \___\__,_|_| |_|   |_|\__, |\___|\___/|_| |_|"
echo "                                   |___/                  "
echo -e "${NC}"
echo "Local AI Agent with Discord/Telegram, Google Workspace & Payments"
echo "=================================================================="
echo ""

# Detect OS
detect_os() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macos"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if [ -f /etc/debian_version ]; then
            echo "debian"
        elif [ -f /etc/redhat-release ]; then
            echo "redhat"
        elif [ -f /etc/arch-release ]; then
            echo "arch"
        else
            echo "linux"
        fi
    else
        echo "unknown"
    fi
}

OS=$(detect_os)
echo -e "${BLUE}Detected OS:${NC} $OS"

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Compare version numbers
version_gte() {
    printf '%s\n%s\n' "$2" "$1" | sort -V -C
}

# Check Python version
check_python() {
    if command_exists python3; then
        PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        if version_gte "$PYTHON_VERSION" "$MIN_PYTHON_VERSION"; then
            echo -e "${GREEN}✓${NC} Python $PYTHON_VERSION found"
            return 0
        fi
    fi
    return 1
}

# Install Python
install_python() {
    echo -e "${YELLOW}Installing Python $MIN_PYTHON_VERSION+...${NC}"
    
    case $OS in
        macos)
            if command_exists brew; then
                brew install python@3.12
            else
                echo -e "${YELLOW}Installing Homebrew first...${NC}"
                /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
                brew install python@3.12
            fi
            ;;
        debian)
            sudo apt-get update
            sudo apt-get install -y python3.12 python3.12-venv python3-pip
            ;;
        redhat)
            sudo dnf install -y python3.12 python3.12-pip
            ;;
        arch)
            sudo pacman -S --noconfirm python python-pip
            ;;
        *)
            echo -e "${RED}Please install Python $MIN_PYTHON_VERSION+ manually${NC}"
            exit 1
            ;;
    esac
}

# Check if Ollama is installed
check_ollama() {
    if command_exists ollama; then
        OLLAMA_VERSION=$(ollama --version 2>/dev/null | head -n1 || echo "unknown")
        echo -e "${GREEN}✓${NC} Ollama found: $OLLAMA_VERSION"
        return 0
    fi
    return 1
}

# Install Ollama
install_ollama() {
    echo -e "${YELLOW}Installing Ollama...${NC}"
    curl -fsSL https://ollama.ai/install.sh | sh
    echo -e "${GREEN}✓${NC} Ollama installed"
}

# Pull default model
pull_model() {
    local model="${1:-llama3.2}"
    echo -e "${BLUE}Pulling model: $model${NC}"
    echo "This may take a while depending on your internet connection..."
    
    # Start Ollama if not running
    if ! pgrep -x "ollama" > /dev/null; then
        echo "Starting Ollama service..."
        ollama serve &
        sleep 3
    fi
    
    ollama pull "$model"
    echo -e "${GREEN}✓${NC} Model $model ready"
}

# Main installation
main() {
    echo -e "${BLUE}Step 1: Checking Python...${NC}"
    if ! check_python; then
        install_python
        if ! check_python; then
            echo -e "${RED}Failed to install Python. Please install Python $MIN_PYTHON_VERSION+ manually.${NC}"
            exit 1
        fi
    fi
    
    echo ""
    echo -e "${BLUE}Step 2: Checking Ollama...${NC}"
    if ! check_ollama; then
        read -p "Ollama not found. Install it now? [Y/n] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]] || [[ -z $REPLY ]]; then
            install_ollama
        else
            echo -e "${YELLOW}Skipping Ollama installation. You'll need to install it manually.${NC}"
        fi
    fi
    
    echo ""
    echo -e "${BLUE}Step 3: Creating installation directory...${NC}"
    mkdir -p "$INSTALL_DIR"
    cd "$INSTALL_DIR"
    echo -e "${GREEN}✓${NC} Directory: $INSTALL_DIR"
    
    echo ""
    echo -e "${BLUE}Step 4: Cloning repository...${NC}"
    if [ -d "$INSTALL_DIR/repo" ]; then
        echo "Updating existing installation..."
        cd "$INSTALL_DIR/repo"
        git pull
    else
        git clone "$REPO_URL" "$INSTALL_DIR/repo"
        cd "$INSTALL_DIR/repo"
    fi
    echo -e "${GREEN}✓${NC} Repository cloned"
    
    echo ""
    echo -e "${BLUE}Step 5: Creating virtual environment...${NC}"
    python3 -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"
    echo -e "${GREEN}✓${NC} Virtual environment created"
    
    echo ""
    echo -e "${BLUE}Step 6: Installing dependencies...${NC}"
    pip install --upgrade pip
    pip install -e "$INSTALL_DIR/repo"
    echo -e "${GREEN}✓${NC} Dependencies installed"
    
    echo ""
    echo -e "${BLUE}Step 6b: Installing Playwright browser...${NC}"
    playwright install chromium
    echo -e "${GREEN}✓${NC} Playwright Chromium installed"
    
    echo ""
    echo -e "${BLUE}Step 7: Setting up configuration...${NC}"
    if [ ! -f "$INSTALL_DIR/.env" ]; then
        cp "$INSTALL_DIR/repo/.env.example" "$INSTALL_DIR/.env"
        echo -e "${GREEN}✓${NC} Created .env file at $INSTALL_DIR/.env"
    else
        echo -e "${YELLOW}!${NC} .env file already exists, keeping existing configuration"
    fi
    
    if [ ! -f "$INSTALL_DIR/config.yaml" ]; then
        cp "$INSTALL_DIR/repo/config.yaml" "$INSTALL_DIR/config.yaml"
        echo -e "${GREEN}✓${NC} Created config.yaml at $INSTALL_DIR/config.yaml"
    fi
    
    # Create shell wrapper
    echo ""
    echo -e "${BLUE}Step 8: Creating command alias...${NC}"
    WRAPPER_PATH="$HOME/.local/bin/local-pigeon"
    mkdir -p "$HOME/.local/bin"
    cat > "$WRAPPER_PATH" << 'WRAPPER'
#!/bin/bash
source "$HOME/.local_pigeon/venv/bin/activate"
cd "$HOME/.local_pigeon"
exec local-pigeon "$@"
WRAPPER
    chmod +x "$WRAPPER_PATH"
    echo -e "${GREEN}✓${NC} Created command: local-pigeon"
    
    # Pull model if Ollama is installed
    echo ""
    if check_ollama; then
        read -p "Pull default model (llama3.2)? [Y/n] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]] || [[ -z $REPLY ]]; then
            pull_model "llama3.2"
        fi
    fi
    
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}   Installation Complete!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "Next steps:"
    echo ""
    echo "1. Add ~/.local/bin to your PATH (if not already):"
    echo "   export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo ""
    echo "2. Configure your settings:"
    echo "   nano $INSTALL_DIR/.env"
    echo ""
    echo "3. Run the setup wizard:"
    echo "   local-pigeon setup"
    echo ""
    echo "4. Start Local Pigeon:"
    echo "   local-pigeon run"
    echo ""
    echo "For help: local-pigeon --help"
    echo ""
}

# Run main
main "$@"
