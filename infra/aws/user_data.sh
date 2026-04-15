#!/bin/bash
set -euxo pipefail

dnf -y update
dnf -y install git nginx python3 python3-pip python3-devel gcc nodejs postgresql15 jq

python3 -m pip install --upgrade pip virtualenv gunicorn

cat >/etc/nginx/conf.d/ai-scalp.conf <<'EOF'
server {
    listen 80;
    server_name _;
    client_max_body_size 20M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

rm -f /etc/nginx/conf.d/default.conf || true
systemctl enable nginx
systemctl restart nginx

mkdir -p /opt/ai-scalp /var/log/ai-scalp
chown -R ec2-user:ec2-user /opt/ai-scalp /var/log/ai-scalp

cat >/etc/motd <<'EOF'
ai-scalp host bootstrap completed.
Next steps:
1) SSH as ec2-user
2) Deploy code into /opt/ai-scalp
3) Configure backend/.env
4) Run migrations and start gunicorn systemd service
EOF
