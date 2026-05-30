# AI Credit Dispute Automation Platform

Automated credit report dispute processing with AI. Takes a credit report PDF and outputs:
- Metro 2 file (ready for credit bureau submission)
- Human-readable reports (TXT, HTML, PDF)

## Features

| Feature | Description |
|---------|-------------|
| **AI Analysis** | Uses local DeepSeek model to detect credit report errors |
| **Batch Processing** | Watch folder for automatic PDF processing |
| **Web Interface** | Self-hosted web UI for drag-and-drop processing |
| **Email Notifications** | Send results via email when processing completes |
| **Metro 2 Output** | Bureau-ready file format |
| **Human Reports** | TXT, HTML, and PDF reports for bank employees |
| **On-Premises** | Runs on your infrastructure. Data never leaves your control. |

## System Requirements

### Hardware

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| RAM | 16GB | 32GB |
| Storage | 20GB | 50GB SSD |
| CPU | 4-core | 8-core |
| GPU | Optional | NVIDIA with 8GB+ VRAM |

### Software

- Python 3.10+
- Ollama (for AI model)
- DeepSeek-Coder-V2:16b model

## Quick Install

Copy and paste these commands one line at a time:

```bash
git clone https://github.com/leonardrougeau-ctrl/credit-dispute-cli.git
cd credit-dispute-cli
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**On Windows, replace `source venv/bin/activate` with:**
```cmd
venv\Scripts\activate
```

## Install AI Model

### Step 1: Install Ollama

**Linux (Ubuntu/Debian) - copy and paste:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

**Windows:**
Download from https://ollama.com/download/windows

**macOS:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### Step 2: Pull the DeepSeek Model

```bash
ollama pull deepseek-coder-v2:16b
```

### Step 3: Verify the Model is Ready

```bash
ollama list
```

### Step 4: Test the Model

```bash
ollama run deepseek-coder-v2:16b "Write a Python function"
```

Press Ctrl+D to exit when done.

### Optional: Keep Model Loaded for Faster Processing

```bash
curl http://localhost:11434/api/generate -d '{"model": "deepseek-coder-v2:16b", "keep_alive": "24h"}'
```

### Offline Installation for Air-Gapped Environments

**Step 1:** On an internet-connected machine:
```bash
ollama pull deepseek-coder-v2:16b
ollama export deepseek-coder-v2:16b -o deepseek-model.tar
```

**Step 2:** Transfer `deepseek-model.tar` to your secure environment

**Step 3:** Import on the target machine:
```bash
ollama import deepseek-coder-v2:16b deepseek-model.tar
```

## Usage

### Command Line (Single PDF)

```bash
python -m ai_dispute_platform.pipeline.cli --pdf report.pdf --output ./results
```

### Batch Processing (Watch Folder)

```bash
python -m ai_dispute_platform.pipeline.cli --watch ./incoming --interval 5
```

### Email Notifications

```bash
python -m ai_dispute_platform.pipeline.cli --pdf report.pdf --notify disputes@bank.com
```

**Configure SMTP via environment variables:**
```bash
export SMTP_SERVER="smtp.yourbank.com"
export SMTP_PORT="25"
export SMTP_USER="username"
export SMTP_PASSWORD="password"
```

### Web Interface (Self-Hosted)

**Run on your internal server:**
```bash
python -m ai_dispute_platform.web --host 127.0.0.1 --port 8080
```

**Open in your browser:**
```
http://127.0.0.1:8080
```

## Output Files

After processing, you will find these files in your output directory:

| File | Purpose |
|------|---------|
| `output` | Metro 2 file (upload to credit bureau) |
| `output_report.txt` | Human-readable text report |
| `output_report.html` | Browser-viewable report |
| `output_report.pdf` | Printable PDF report |

## For US Financial Institutions

### Security & Deployment

This platform is designed for **on-premises deployment** within your secure environment:

- ✅ All processing happens behind your firewall
- ✅ No customer data ever leaves your infrastructure
- ✅ Complete audit trail of all actions
- ✅ Supports air-gapped environments

### Data Residency

Your data stays on your servers. We never receive or store your customer information.

## Pricing

| Plan | Price | Includes |
|------|-------|----------|
| **Community** | $0 | 5 disputes/month (testing only) |
| **Professional** | $299/month | 100 disputes + AI analysis |
| **Enterprise** | Custom | 500+ disputes + priority support |

**Volume pricing:** Additional disputes beyond plan are $5–$15 each depending on volume.

**Contact:** contact@clearwatercodes.com for custom quotes.

## Support

- **Documentation:** This README
- **Email Support:** contact@clearwatercodes.com
- **Paid Support:** Screen-sharing guidance for installation (quote based on complexity)

## License

MIT License with commercial option for volume >100 disputes/month.
```

