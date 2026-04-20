#!/bin/bash
set -e

REPO="https://github.com/Siezetheday84/Claude-.git"
DEPLOY_DIR="/opt/ai-video-bot"
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}=== AI Video Bot — Server Setup ===${NC}"

# Docker
if ! command -v docker &>/dev/null; then
  echo -e "${YELLOW}Installing Docker...${NC}"
  apt-get update -q
  apt-get install -y -q ca-certificates curl gnupg
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
    https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -q
  apt-get install -y -q docker-ce docker-ce-cli containerd.io docker-compose-plugin
  systemctl enable docker
  systemctl start docker
  echo -e "${GREEN}Docker installed!${NC}"
else
  echo -e "${GREEN}Docker already installed.${NC}"
fi

# Git
if ! command -v git &>/dev/null; then
  apt-get install -y -q git
fi

# Clone repo
if [ -d "$DEPLOY_DIR" ]; then
  echo -e "${YELLOW}Directory exists, pulling latest code...${NC}"
  cd "$DEPLOY_DIR" && git pull origin main
else
  echo -e "${YELLOW}Cloning repository...${NC}"
  git clone "$REPO" "$DEPLOY_DIR"
  cd "$DEPLOY_DIR"
fi

cd "$DEPLOY_DIR"
mkdir -p data

# .env
if [ ! -f .env ]; then
  echo -e "${YELLOW}Creating .env file...${NC}"
  cp .env.example .env

  echo ""
  echo -e "${YELLOW}Enter your Telegram Bot Token (from @BotFather):${NC}"
  read -r BOT_TOKEN_VAL
  sed -i "s|BOT_TOKEN=.*|BOT_TOKEN=${BOT_TOKEN_VAL}|" .env

  echo -e "${YELLOW}Enter your Anthropic API Key:${NC}"
  read -r ANTHROPIC_KEY_VAL
  sed -i "s|ANTHROPIC_API_KEY=.*|ANTHROPIC_API_KEY=${ANTHROPIC_KEY_VAL}|" .env

  echo -e "${YELLOW}Enter admin Telegram IDs (comma-separated, e.g. 123456789):${NC}"
  read -r ADMIN_IDS_VAL
  sed -i "s|ADMIN_IDS=.*|ADMIN_IDS=${ADMIN_IDS_VAL}|" .env

  echo -e "${GREEN}.env created!${NC}"
else
  echo -e "${GREEN}.env already exists, skipping.${NC}"
fi

# Generate SSH deploy key for GitHub Actions
if [ ! -f /root/.ssh/github_deploy ]; then
  echo -e "${YELLOW}Generating SSH deploy key for GitHub Actions...${NC}"
  ssh-keygen -t ed25519 -f /root/.ssh/github_deploy -N "" -C "github-actions-deploy"
  cat /root/.ssh/github_deploy.pub >> /root/.ssh/authorized_keys
  chmod 600 /root/.ssh/authorized_keys
fi

# Build and start
echo -e "${YELLOW}Building Docker image (first time may take ~2 min)...${NC}"
docker compose build

echo -e "${YELLOW}Starting bot...${NC}"
docker compose up -d

sleep 5
echo ""
echo -e "${GREEN}=== Bot status ===${NC}"
docker compose ps
echo ""
echo -e "${GREEN}=== Last logs ===${NC}"
docker compose logs --tail=20

echo ""
echo -e "${GREEN}=====================================================${NC}"
echo -e "${GREEN}Bot is running!${NC}"
echo ""
echo -e "${YELLOW}IMPORTANT — Add these 3 secrets to GitHub${NC}"
echo -e "(Settings → Secrets → Actions → New repository secret)"
echo ""
echo -e "${GREEN}SSH_PRIVATE_KEY:${NC}"
cat /root/.ssh/github_deploy
echo ""
echo -e "${GREEN}SERVER_IP:${NC}  $(curl -s ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')"
echo -e "${GREEN}SERVER_USER:${NC} root"
echo ""
echo -e "${YELLOW}After adding secrets, every git push to main will auto-deploy!${NC}"
echo -e "${GREEN}=====================================================${NC}"
