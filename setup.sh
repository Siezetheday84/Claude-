#!/bin/bash
set -e

REPO="https://github.com/Siezetheday84/Claude-.git"
DEPLOY_DIR="/opt/ai-video-bot"
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== AI Video Bot — Server Setup ===${NC}"

# Validate required env vars
if [ -z "$BOT_TOKEN" ] || [ -z "$ANTHROPIC_API_KEY" ] || [ -z "$ADMIN_IDS" ]; then
  echo "Usage:"
  echo "  BOT_TOKEN=xxx ANTHROPIC_API_KEY=yyy ADMIN_IDS=zzz bash setup.sh"
  exit 1
fi

# Install Docker if missing
if ! command -v docker &>/dev/null; then
  echo -e "${YELLOW}Installing Docker...${NC}"
  apt-get update -q
  apt-get install -y -q ca-certificates curl gnupg
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  . /etc/os-release
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -q
  apt-get install -y -q docker-ce docker-ce-cli containerd.io docker-compose-plugin
  systemctl enable docker
  systemctl start docker
  echo -e "${GREEN}Docker installed!${NC}"
else
  echo -e "${GREEN}Docker already installed.${NC}"
fi

# Install git if missing
if ! command -v git &>/dev/null; then
  apt-get install -y -q git
fi

# Clone or update repo
if [ -d "$DEPLOY_DIR/.git" ]; then
  echo -e "${YELLOW}Updating code...${NC}"
  git -C "$DEPLOY_DIR" pull origin main
else
  echo -e "${YELLOW}Cloning repository...${NC}"
  git clone "$REPO" "$DEPLOY_DIR"
fi

cd "$DEPLOY_DIR"
mkdir -p data

# Write .env
cat > .env <<EOF
BOT_TOKEN=${BOT_TOKEN}
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
ADMIN_IDS=${ADMIN_IDS}
DATABASE_URL=sqlite+aiosqlite:///data/video_service.db
TIMEZONE=Europe/Moscow
EOF
echo -e "${GREEN}.env created!${NC}"

# Generate SSH deploy key for GitHub Actions (if not exists)
if [ ! -f /root/.ssh/github_deploy ]; then
  mkdir -p /root/.ssh
  chmod 700 /root/.ssh
  ssh-keygen -t ed25519 -f /root/.ssh/github_deploy -N "" -C "github-actions-deploy"
  cat /root/.ssh/github_deploy.pub >> /root/.ssh/authorized_keys
  chmod 600 /root/.ssh/authorized_keys
fi

# Build and start
echo -e "${YELLOW}Building Docker image (first build ~2 min)...${NC}"
docker compose build

echo -e "${YELLOW}Starting bot...${NC}"
docker compose up -d

sleep 6
echo ""
echo -e "${GREEN}=== Container status ===${NC}"
docker compose ps
echo ""
echo -e "${GREEN}=== Last logs ===${NC}"
docker compose logs --tail=20

echo ""
echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}Bot is running!${NC}"
echo ""
echo -e "${YELLOW}Add these secrets to GitHub for auto-deploy on git push:${NC}"
echo -e "GitHub → Settings → Secrets → Actions → New repository secret"
echo ""
echo -e "${GREEN}Secret name: SSH_PRIVATE_KEY${NC}"
echo "Value:"
cat /root/.ssh/github_deploy
echo ""
echo -e "${GREEN}Secret name: SERVER_IP${NC}"
echo "Value: $(curl -s ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')"
echo ""
echo -e "${GREEN}Secret name: SERVER_USER${NC}"
echo "Value: root"
echo -e "${GREEN}============================================================${NC}"
