#!/bin/bash
# Install YouTube Archive Manager as a system service
# Run with: bash install_startup_service.sh

set -e

# Configuration
APP_NAME="youtube-archive-manager"
APP_DIR="/home/mm"
SERVICE_USER="mm"
PYTHON_PATH="/usr/bin/python3"

echo "Installing YouTube Archive Manager as a system service..."

# Create systemd service file
sudo tee /etc/systemd/system/${APP_NAME}.service > /dev/null <<EOF
[Unit]
Description=Medical Medium YouTube Archive Manager
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=${SERVICE_USER}
Group=${SERVICE_USER}
WorkingDirectory=${APP_DIR}
Environment=PYTHONPATH=${APP_DIR}
Environment=DISPLAY=:0
ExecStart=${PYTHON_PATH} ${APP_DIR}/youtube_archive_manager.py --headless
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Security settings
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=no
ReadWritePaths=${APP_DIR}
ReadWritePaths=/mnt/MM/MedicalMediumArchive

[Install]
WantedBy=multi-user.target
EOF

# Create desktop autostart entry for GUI mode
mkdir -p /home/${SERVICE_USER}/.config/autostart

tee /home/${SERVICE_USER}/.config/autostart/${APP_NAME}.desktop > /dev/null <<EOF
[Desktop Entry]
Type=Application
Name=YouTube Archive Manager
Comment=Medical Medium YouTube Archive Manager
Exec=${PYTHON_PATH} ${APP_DIR}/youtube_archive_manager.py
Icon=video
Terminal=false
StartupNotify=true
Categories=Network;AudioVideo;
EOF

chown ${SERVICE_USER}:${SERVICE_USER} /home/${SERVICE_USER}/.config/autostart/${APP_NAME}.desktop

# Create cron job for daily midnight checks
echo "Adding cron job for daily checks..."
(crontab -u ${SERVICE_USER} -l 2>/dev/null || echo ""; echo "0 0 * * * ${PYTHON_PATH} ${APP_DIR}/youtube_archive_manager.py --check-only") | crontab -u ${SERVICE_USER} -

# Reload systemd and enable service
sudo systemctl daemon-reload
sudo systemctl enable ${APP_NAME}.service

echo "Installation complete!"
echo ""
echo "Service commands:"
echo "  Start:   sudo systemctl start ${APP_NAME}"
echo "  Stop:    sudo systemctl stop ${APP_NAME}"
echo "  Status:  sudo systemctl status ${APP_NAME}"
echo "  Logs:    journalctl -u ${APP_NAME} -f"
echo ""
echo "The service will start automatically on boot."
echo "The GUI will also start automatically when you log in."
echo "Daily checks are scheduled for midnight via cron."