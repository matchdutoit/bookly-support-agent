"""
Flask backend for Bookly customer support agent.
"""

from flask import Flask, render_template, request, jsonify, session
from agent import ConversationManager
import uuid
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

conversation_manager = ConversationManager()


@app.route('/')
def index():
    """Serve the chat interface."""
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    return render_template('index.html')


@app.route('/chat', methods=['POST'])
def chat():
    """Handle chat messages from the frontend."""
    data = request.json
    user_message = data.get('message', '')
    session_id = session.get('session_id', str(uuid.uuid4()))

    try:
        response = conversation_manager.chat(session_id, user_message)
        return jsonify({
            'success': True,
            'response': response
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/reset', methods=['POST'])
def reset():
    """Reset the conversation to start fresh."""
    session_id = session.get('session_id')
    if session_id:
        conversation_manager.reset_conversation(session_id)
    session['session_id'] = str(uuid.uuid4())
    return jsonify({'success': True})


if __name__ == '__main__':
    app.run(debug=True, port=5000)
