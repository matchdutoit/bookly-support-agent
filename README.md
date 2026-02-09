# Bookly Support Agent

A customer support AI agent for Bookly, a fictional online bookstore. Built with Flask and OpenAI.

## Features

- **Order Status Inquiries** - Look up orders by ID or email, view tracking and delivery ETA
- **Return/Refund Requests** - Check eligibility, process returns with policy-based refund type (cash vs store credit)
- **Conversation Memory** - Multi-turn conversations with context retention
- **Chat UI** - Clean web interface with typing indicators

## Setup

1. **Clone and enter directory**
   ```bash
   git clone https://github.com/matchdutoit/bookly-support-agent.git
   cd bookly-support-agent
   ```

2. **Create virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Add your OpenAI API key**
   ```bash
   echo "OPENAI_API_KEY=your_key_here" > .env
   ```

5. **Run the app**
   ```bash
   python app.py
   ```

6. **Open in browser**
   ```
   http://127.0.0.1:5000
   ```

## Test Scenarios

| Order ID | Customer | Status | Return Eligible |
|----------|----------|--------|-----------------|
| ORD-1001 | alice@email.com | Delivered | Yes |
| ORD-1002 | bob@email.com | In Transit | No |
| ORD-1003 | alice@email.com | Delivered | No (outside 30-day window) |
| ORD-1004 | carol@email.com | Processing | No |
| ORD-1005 | bob@email.com | Delivered | Yes |

## Project Structure

```
├── app.py              # Flask backend
├── agent.py            # Conversation manager + OpenAI integration
├── tools.py            # Tool functions for order lookup/returns
├── mock_data.py        # Sample order database
├── agents.md           # Agent personality and policies
├── templates/
│   └── index.html      # Chat interface
├── static/
│   ├── style.css
│   └── script.js
└── requirements.txt
```

## Return Policy

- **30-day return window** from delivery date
- **Cash refund**: damaged, wrong item, defective, never arrived
- **Store credit**: didn't like, changed mind, no longer needed
