# AWS Deployment Guide (Beginner Friendly)

This guide deploys your system on AWS with:
- 1 EC2 instance for frontend + backend
- 1 PostgreSQL RDS database
- 1 Elastic IP for direct website + API access

Terraform files are in: `infra/aws/`

## 0) Important Notes Before You Start

1. `t3.small` is usually **not** Free Tier eligible.  
   Free Tier is typically `t2.micro`/`t3.micro`-class (check your AWS account’s current offer).
2. Both website and API are served from the same EC2 Elastic IP.
3. RDS is private (not internet-accessible), only EC2 can connect to it.

## 1) Prerequisites

Install these on your local machine (or use AWS CloudShell):
- AWS CLI
- Terraform (>= 1.6)
- SSH client
- Git

Also have:
- An AWS account
- A key pair you control (we generate one below)

## 2) Prepare Terraform Variables

From project root:

```bash
cd infra/aws
cp terraform.tfvars.example terraform.tfvars
```

Generate SSH key pair (if you do not already have one):

```bash
ssh-keygen -t ed25519 -f ~/.ssh/ai-scalp-aws
```

Edit `infra/aws/terraform.tfvars` and set at minimum:
- `key_pair_name`
- `public_key_path`
- `db_password`
- `ssh_allowed_cidr` (set to your IP/32, recommended)

Get your current public IP:

```bash
curl ifconfig.me
```

Then set:

```hcl
ssh_allowed_cidr = "YOUR_PUBLIC_IP/32"
```

## 3) Configure AWS Credentials

If running locally:

```bash
aws configure
```

Provide:
- AWS Access Key ID
- AWS Secret Access Key
- Region (for example `us-east-1`)

If running from AWS CloudShell, credentials are usually already available.

## 4) Create Infrastructure with Terraform

From `infra/aws`:

```bash
terraform init
terraform plan
terraform apply
```

Type `yes` when prompted.

After apply, Terraform prints important outputs:
- `website_url`
- `api_url`
- `ec2_elastic_ip`
- `rds_endpoint`
- `database_url_template`

## 5) SSH Into EC2

```bash
ssh -i ~/.ssh/ai-scalp-aws ec2-user@<EC2_ELASTIC_IP>
```

Replace `<EC2_ELASTIC_IP>` with Terraform output value.

## 6) Deploy Application Code on EC2

The Terraform bootstrap already installed:
- Nginx
- Python
- Node.js
- Gunicorn

Now deploy your project:

```bash
cd /opt
git clone <YOUR_REPO_URL> ai-scalp
cd ai-scalp
```

## 7) Backend Setup (Django + RDS)

```bash
cd /opt/ai-scalp/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`:

```bash
nano .env
```

Set these required values:
- `DEBUG=False`
- `DJANGO_SECRET_KEY=<your-secret>`
- `DATABASE_URL=postgresql://<db_username>:<db_password>@<rds_endpoint>:5432/<db_name>`
- `BROKER_PROVIDER=capital`
- `CAPITAL_TRADING_MODE=demo`
- `CAPITAL_DEMO_API_KEY=...`
- `CAPITAL_DEMO_IDENTIFIER=...`
- `CAPITAL_DEMO_PASSWORD=...`
- `CAPITAL_LIVE_API_KEY=...`
- `CAPITAL_LIVE_IDENTIFIER=...`
- `CAPITAL_LIVE_PASSWORD=...`

Run migrations:

```bash
python manage.py migrate
```

Collect static files:

```bash
python manage.py collectstatic --noinput
```

## 8) Frontend Build

```bash
cd /opt/ai-scalp
npm ci
npm run build
```

Your Django app serves the built frontend from `dist/`.

## 9) Create Systemd Service for Gunicorn

Create service file:

```bash
sudo tee /etc/systemd/system/ai-scalp.service >/dev/null <<'EOF'
[Unit]
Description=ai-scalp Django Gunicorn
After=network.target

[Service]
Type=simple
User=ec2-user
Group=ec2-user
WorkingDirectory=/opt/ai-scalp/backend
EnvironmentFile=/opt/ai-scalp/backend/.env
ExecStart=/opt/ai-scalp/backend/.venv/bin/gunicorn trading_platform.wsgi:application --bind 127.0.0.1:8000 --workers 3 --timeout 120
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
```

Start service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable ai-scalp
sudo systemctl start ai-scalp
sudo systemctl status ai-scalp --no-pager
```

Nginx is already configured by Terraform user-data to proxy port 80 -> `127.0.0.1:8000`.

## 10) Validate Endpoints

From your own machine:

Website via EIP:

```bash
curl -I http://<EC2_ELASTIC_IP>
```

API health via EIP:

```bash
curl http://<EC2_ELASTIC_IP>/api/health/
```

Open in browser:
- `http://<EC2_ELASTIC_IP>` (main app)
- `http://<EC2_ELASTIC_IP>/api/health/` (API health check)

## 11) Update Workflow (After First Deploy)

On EC2:

```bash
cd /opt/ai-scalp
git pull

cd backend
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput

cd /opt/ai-scalp
npm ci
npm run build

sudo systemctl restart ai-scalp
sudo systemctl restart nginx
```

## 12) Troubleshooting

Gunicorn logs:

```bash
sudo journalctl -u ai-scalp -n 200 --no-pager
```

Nginx logs:

```bash
sudo tail -n 200 /var/log/nginx/error.log
```

Check EC2 can reach RDS:

```bash
nc -zv <RDS_ENDPOINT> 5432
```

## 13) Destroy Infrastructure (When Needed)

From `infra/aws`:

```bash
terraform destroy
```

This removes EC2, RDS, networking, and EIP created by this stack.
