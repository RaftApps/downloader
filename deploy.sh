#!/bin/bash
APP_NAME="video-downloader"
APP_DIR="/home/ubuntu/$APP_NAME"

sudo apt update && sudo apt upgrade -y
sudo apt install python3 python3-venv python3-pip git nginx certbot python3-certbot-nginx -y

if [ ! -d "$APP_DIR" ]; then
    git clone https://github.com/your-repo/video-downloader.git $APP_DIR
fi

cd $APP_DIR
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

SERVICE_FILE=/etc/systemd/system/$APP_NAME.service
sudo bash -c "cat > $SERVICE_FILE" <<EOL
[Unit]
Description=FastAPI Video Downloader
After=network.target

[Service]
User=ubuntu
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/venv/bin/gunicorn -k uvicorn.workers.UvicornWorker main:app --bind 127.0.0.1:8000
Restart=always

[Install]
WantedBy=multi-user.target
EOL

sudo systemctl daemon-reload
sudo systemctl enable $APP_NAME
sudo systemctl restart $APP_NAME

NGINX_FILE=/etc/nginx/sites-available/$APP_NAME
sudo bash -c "cat > $NGINX_FILE" <<EOL
server {
    server_name downloader.hdvideodownload.xyz;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }
}
EOL

sudo ln -sf $NGINX_FILE /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl restart nginx

sudo certbot --nginx -d downloader.hdvideodownload.xyz -n --agree-tos --email contact@raftapps.com
echo "✅ Deployment complete! Visit https://downloader.hdvideodownload.xyz"
