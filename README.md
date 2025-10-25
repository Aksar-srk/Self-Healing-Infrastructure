# 🛠️ Self-Healing Infrastructure with Prometheus, Alertmanager & Ansible

This project demonstrates a **closed-loop, self-healing infrastructure** on AWS using **Prometheus**, **Alertmanager**, and **Ansible**.  
It automatically detects and recovers from service failures — for example, restarting a crashed Nginx server without manual intervention.

---

## 🚀 Project Objective

To build a system that can **automatically detect a service failure** (like Nginx going down) and **trigger an automated recovery** process using Ansible.  
This reduces downtime and improves system reliability.

---

## 🏗️ Architecture

### The system operates on two EC2 instances:

**1️⃣ Monitoring Server (Control Node)**  
- **Prometheus:** Scrapes metrics from the web server  
- **Alertmanager:** Receives alerts from Prometheus  
- **Ansible:** Executes automated recovery playbooks  
- **Webhook Receiver (Flask):** Triggers Ansible playbook when alert fires  

**2️⃣ Web Server (Managed Node)**  
- **Nginx:** Target service being monitored  
- **Node Exporter:** Exposes metrics to Prometheus  

---

## ⚙️ Self-Healing Flow

1. **Failure:** Nginx service stops on the web server  
2. **Detection:** Prometheus detects `up == 0` from Node Exporter  
3. **Alerting:** Prometheus fires `InstanceDown` alert to Alertmanager  
4. **Trigger:** Alertmanager sends alert (JSON) to Flask webhook  
5. **Action:** Webhook triggers `restart_nginx.yml` Ansible playbook  
6. **Recovery:** Ansible restarts Nginx service  
7. **Resolution:** Prometheus confirms service restored, alert resolves  

---

## 🧰 Tools Used

| Tool | Purpose |
|------|----------|
| **AWS EC2 (Amazon Linux 2)** | Compute Instances |
| **Prometheus** | Monitoring |
| **Alertmanager** | Alerting |
| **Ansible** | Automation |
| **Node Exporter** | Metrics Collection |
| **Python (Flask)** | Webhook Receiver |
| **Nginx** | Web Service |
| **systemd** | Service Management |

---

## 📂 GitHub Repository Structure

```
self-healing-infrastructure/
│
├── ansible/
│   ├── inventory
│   └── restart_nginx.yml
│
├── services/
│   ├── prometheus.service
│   ├── alertmanager.service
│   ├── webhook.service
│   └── node_exporter.service
│
├── configs/
│   ├── prometheus.yml
│   ├── alert.rules.yml
│   └── alertmanager.yml
│
├── webhook_receiver.py
├── README.md
└── screenshots/
    ├── prometheus_targets.png
    ├── alertmanager_alerts.png
    ├── webhook_log.png
    └── nginx_recovery.png
```

---

## 📖 Step-by-Step Setup Guide

### 🧩 Prerequisites

#### EC2 Instances
- `monitoring-server`
- `web-server`

#### User & SSH Setup
- Create `ansible` user on both servers
- Configure passwordless SSH from monitoring-server → web-server
- Add passwordless sudo for ansible:
  ```
  ansible ALL=(ALL) NOPASSWD: ALL
  ```

#### Security Groups
- **Web Server:** Ports `80`, `9100` (from monitoring-server)
- **Monitoring Server:** Ports `9090`, `9093`, `3000` (optional Grafana)

---

## 🖥️ Step 1: Configure Web Server (Managed Node)

### Install Nginx
```bash
sudo yum update -y
sudo amazon-linux-extras install nginx1 -y
sudo systemctl start nginx
sudo systemctl enable nginx
```

### Install Node Exporter
```bash
wget https://github.com/prometheus/node_exporter/releases/download/v1.7.0/node_exporter-1.7.0.linux-amd64.tar.gz
tar xvf node_exporter-1.7.0.linux-amd64.tar.gz
sudo mv node_exporter-1.7.0.linux-amd64/node_exporter /usr/local/bin/
rm -rf node_exporter*
```

### Create Service File
`/etc/systemd/system/node_exporter.service`
```
[Unit]
Description=Prometheus Node Exporter
Wants=network-online.target
After=network-online.target

[Service]
User=ansible
ExecStart=/usr/local/bin/node_exporter

[Install]
WantedBy=default.target
```

Enable Service:
```bash
sudo systemctl daemon-reload
sudo systemctl start node_exporter
sudo systemctl enable node_exporter
```

---

## 🧠 Step 2: Install Prometheus & Alertmanager (Monitoring Server)

### Install Prometheus
```bash
wget https://github.com/prometheus/prometheus/releases/download/v2.51.2/prometheus-2.51.2.linux-amd64.tar.gz
tar xvf prometheus-2.51.2.linux-amd64.tar.gz
sudo useradd --no-create-home --shell /bin/false prometheus
sudo mkdir /etc/prometheus /var/lib/prometheus
sudo mv prometheus-2.51.2.linux-amd64/{prometheus,promtool} /usr/local/bin/
sudo mv prometheus-2.51.2.linux-amd64/{consoles,console_libraries} /etc/prometheus/
sudo chown -R prometheus:prometheus /etc/prometheus /var/lib/prometheus
rm -rf prometheus*
```

### Install Alertmanager
```bash
wget https://github.com/prometheus/alertmanager/releases/download/v0.27.0/alertmanager-0.27.0.linux-amd64.tar.gz
tar xvf alertmanager-0.27.0.linux-amd64.tar.gz
sudo useradd --no-create-home --shell /bin/false alertmanager
sudo mkdir /etc/alertmanager
sudo mv alertmanager-0.27.0.linux-amd64/{alertmanager,amtool} /usr/local/bin/
sudo chown -R alertmanager:alertmanager /etc/alertmanager
rm -rf alertmanager*
```

---

## ⚙️ Step 3: Prometheus Configuration

**`/etc/prometheus/prometheus.yml`**
```yaml
global:
  scrape_interval: 15s

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['localhost:9093']

rule_files:
  - 'alert.rules.yml'

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'node_exporter'
    static_configs:
      - targets: ['<WEB_SERVER_PRIVATE_IP>:9100']
```

**`/etc/prometheus/alert.rules.yml`**
```yaml
groups:
  - name: AllInstances
    rules:
      - alert: InstanceDown
        expr: up == 0
        for: 1m
        labels:
          severity: 'critical'
        annotations:
          summary: 'Instance {{ $labels.instance }} down'
          description: '{{ $labels.instance }} of job {{ $labels.job }} has been down for more than 1 minute.'
```

---

## ⚡ Step 4: Alertmanager Configuration

**`/etc/alertmanager/alertmanager.yml`**
```yaml
route:
  receiver: 'ansible-webhook'

receivers:
  - name: 'ansible-webhook'
    webhook_configs:
      - url: 'http://127.0.0.1:5001/webhook'
```

---

## 🤖 Step 5: Ansible Setup

**`~/ansible/inventory`**
```
[webservers]
<WEB_SERVER_PRIVATE_IP>
```

**`~/ansible/restart_nginx.yml`**
```yaml
---
- name: Restart Nginx Service
  hosts: webservers
  become: yes
  tasks:
    - name: Restart nginx
      ansible.builtin.systemd:
        name: nginx
        state: restarted
```

Test:
```bash
ansible-playbook -i inventory restart_nginx.yml
```

---

## 🧩 Step 6: Webhook Receiver

**Install Flask**
```bash
sudo yum install python3-pip -y
pip3 install flask --user
```

**`~/webhook_receiver.py`**
```python
from flask import Flask, request
import subprocess, json

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    if data and data['alerts'][0]['labels']['alertname'] == 'InstanceDown':
        print("InstanceDown alert received! Triggering Ansible playbook...")
        subprocess.run(['/usr/local/bin/ansible-playbook',
                        '-i', '/home/ansible/ansible/inventory',
                        '/home/ansible/ansible/restart_nginx.yml'])
    return 'Alert processed', 200

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5001)
```

---

## 🧾 Step 7: Service Files (in `/services/`)

### 🔹 `prometheus.service`
```
[Unit]
Description=Prometheus Monitoring
After=network-online.target

[Service]
User=prometheus
ExecStart=/usr/local/bin/prometheus \
  --config.file /etc/prometheus/prometheus.yml \
  --storage.tsdb.path /var/lib/prometheus/ \
  --web.console.templates=/etc/prometheus/consoles \
  --web.console.libraries=/etc/prometheus/console_libraries

[Install]
WantedBy=multi-user.target
```

### 🔹 `alertmanager.service`
```
[Unit]
Description=Prometheus Alertmanager
After=network-online.target

[Service]
User=alertmanager
ExecStart=/usr/local/bin/alertmanager \
  --config.file /etc/alertmanager/alertmanager.yml

[Install]
WantedBy=multi-user.target
```

### 🔹 `webhook.service`
```
[Unit]
Description=Ansible Webhook Receiver
After=network.target

[Service]
User=ansible
ExecStart=/usr/bin/python3 /home/ansible/webhook_receiver.py
Restart=always

[Install]
WantedBy=multi-user.target
```

### 🔹 `node_exporter.service`
```
[Unit]
Description=Prometheus Node Exporter
After=network-online.target

[Service]
User=ansible
ExecStart=/usr/local/bin/node_exporter

[Install]
WantedBy=default.target
```

Enable and Start All:
```bash
sudo systemctl daemon-reload
sudo systemctl enable prometheus alertmanager webhook node_exporter
sudo systemctl start prometheus alertmanager webhook node_exporter
```

---

## ✅ Step 8: Testing the Self-Healing System

1. **Prometheus UI:**  
   http://<monitoring-server-ip>:9090 → “Targets” → Node Exporter = UP  
2. **Simulate Failure (on web-server):**
   ```bash
   sudo systemctl stop nginx
   sudo systemctl stop node_exporter
   ```
3. **Watch Webhook Logs:**
   ```bash
   journalctl -u webhook -f
   ```
4. **Expected Output:**
   ```
   InstanceDown alert received! Triggering Ansible playbook...
   PLAY [Restart Nginx Service] ...
   ```
5. **Verify:**
   ```bash
   systemctl status nginx
   ```
   Should show **active (running)** again.

   ![CI/CD Architecture Diagram](images/vs.png)

---

## 🧯 Troubleshooting

- Check if alert fires in Prometheus & Alertmanager UIs  
- Use:
  ```bash
  journalctl -u webhook -f
  ```
- Manually test Ansible if automation fails  

---

## 📸 Recommended Screenshots

| Screenshot | Description |
|-------------|--------------|
| prometheus_targets.png | Prometheus showing target UP/DOWN |
| alertmanager_alerts.png | InstanceDown alert in Alertmanager |
| webhook_log.png | Webhook triggering Ansible playbook |
| nginx_recovery.png | Nginx restarted successfully |

---

## 📜 License

This project is open-source under the **MIT License**.  
You can freely use or modify it for learning or demonstration purposes.

---

**Author:** Aksar  
**Project:** Self-Healing Infrastructure (Prometheus + Alertmanager + Ansible)
