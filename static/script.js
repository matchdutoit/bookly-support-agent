const messagesContainer = document.getElementById('messages');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const resetBtn = document.getElementById('reset-btn');
const typingIndicator = document.getElementById('typing');

function addMessage(content, sender) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}`;

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.textContent = content;

    messageDiv.appendChild(contentDiv);
    messagesContainer.appendChild(messageDiv);

    // Scroll to bottom
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function showTypingIndicator() {
    typingIndicator.style.display = 'block';
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function hideTypingIndicator() {
    typingIndicator.style.display = 'none';
}

async function sendMessage() {
    const message = userInput.value.trim();
    if (!message) return;

    // Add user message to chat
    addMessage(message, 'user');
    userInput.value = '';

    // Disable input while processing
    userInput.disabled = true;
    sendBtn.disabled = true;

    // Show typing indicator
    showTypingIndicator();

    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ message: message })
        });

        const data = await response.json();
        hideTypingIndicator();

        if (data.success) {
            addMessage(data.response, 'agent');
        } else {
            addMessage('Sorry, something went wrong. Please try again.', 'agent');
            console.error('Error:', data.error);
        }
    } catch (error) {
        hideTypingIndicator();
        addMessage('Connection error. Please try again.', 'agent');
        console.error('Fetch error:', error);
    }

    // Re-enable input
    userInput.disabled = false;
    sendBtn.disabled = false;
    userInput.focus();
}

async function resetConversation() {
    try {
        await fetch('/reset', { method: 'POST' });

        // Clear messages except the first welcome message
        messagesContainer.innerHTML = `
            <div class="message agent">
                <div class="message-content">
                    Hi! I'm the Bookly support assistant. I can help you with order status inquiries and return requests. How can I help you today?
                </div>
            </div>
        `;
    } catch (error) {
        console.error('Reset error:', error);
    }
}

// Event listeners
sendBtn.addEventListener('click', sendMessage);

userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        sendMessage();
    }
});

resetBtn.addEventListener('click', resetConversation);

// Focus input on page load
userInput.focus();
