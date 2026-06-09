# VoxIQ — Voice Intelligence Pipeline

A serverless AWS pipeline that transcribes audio files and uses Claude AI to extract call summaries, sentiment, and routing categories. Includes a React dashboard to view results.

## What it does

1. You upload an audio file via the React dashboard
2. It lands in S3 (Amazon's cloud storage)
3. A Lambda function automatically wakes up and sends it to AWS Transcribe
4. AWS Transcribe converts the audio to text
5. A second Lambda sends the transcript to Claude AI
6. Claude extracts: summary, sentiment, caller intent, and routing category
7. Results are saved to DynamoDB and shown on the dashboard

## Project structure

```
voxiq/
├── infrastructure/         # AWS CDK — creates all AWS resources with one command
│   ├── app.py
│   ├── stack.py
│   └── requirements.txt
├── backend/
│   └── lambdas/
│       ├── presign_url/    # Generates a secure upload URL for the browser
│       ├── s3_trigger/     # Fires when audio lands in S3, starts Transcribe
│       ├── claude_analysis/# Runs when transcription completes, calls Claude
│       └── get_calls/      # API endpoint — returns call records for the dashboard
└── frontend/               # React dashboard
    ├── src/
    └── ...
```

## Deploy in 4 steps

### Prerequisites
- AWS account with CLI configured (`aws configure`)
- Node.js 18+ and Python 3.11+
- No Anthropic API key needed — uses AWS Comprehend (free tier)

### 1. Install dependencies

```bash
# Infrastructure
cd infrastructure
pip install -r requirements.txt
npm install -g aws-cdk

# Frontend
cd ../frontend
npm install
```

### 2. Deploy AWS infrastructure

```bash
cd infrastructure
cdk bootstrap   # first time only
cdk deploy
```

CDK will print out your API Gateway URL and CloudFront URL when done.

### 3. Deploy the frontend

```bash
cd ../frontend
# Paste the API Gateway URL printed by CDK
echo "VITE_API_URL=https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com" > .env
npm run build
# CDK already created the S3 + CloudFront hosting — just sync the build:
aws s3 sync dist/ s3://voxiq-frontend-$(aws sts get-caller-identity --query Account --output text) --delete
```

Your dashboard is live at the CloudFront URL printed by `cdk deploy`.

## Tear down (avoid AWS charges)

```bash
cd infrastructure
cdk destroy
```
