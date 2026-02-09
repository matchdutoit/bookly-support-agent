// Navbar scroll behavior
const navbar = document.querySelector('.navbar');
const hero = document.querySelector('.hero');
const heroBg = document.getElementById('hero-bg');

function handleNavbarScroll() {
    if (window.scrollY > hero.offsetHeight - 100) {
        navbar.classList.add('scrolled');
    } else {
        navbar.classList.remove('scrolled');
    }
}

// Parallax scroll effect for hero background
const parallaxSpeed = 0.5; // Background moves at 50% of scroll speed

function handleParallax() {
    if (window.innerWidth > 768) { // Only on desktop
        const scrolled = window.scrollY;
        const heroHeight = hero.offsetHeight;

        // Only apply parallax while hero is visible
        if (scrolled <= heroHeight) {
            const yPos = scrolled * parallaxSpeed;
            heroBg.style.transform = `translate3d(0, ${yPos}px, 0)`;
        }
    } else {
        heroBg.style.transform = 'translate3d(0, 0, 0)';
    }
}

function onScroll() {
    handleNavbarScroll();
    requestAnimationFrame(handleParallax);
}

window.addEventListener('scroll', onScroll);
window.addEventListener('resize', handleParallax);
handleNavbarScroll(); // Check on load
handleParallax(); // Initialize parallax

// Chat drawer elements
const chatFab = document.getElementById('chat-fab');
const chatDrawer = document.getElementById('chat-drawer');
const chatOverlay = document.getElementById('chat-overlay');
const closeDrawer = document.getElementById('close-drawer');

// Chat interface elements
const messagesContainer = document.getElementById('messages');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const resetBtn = document.getElementById('reset-btn');
const typingIndicator = document.getElementById('typing');

// Drawer state
let isDrawerOpen = false;

// Toggle drawer functions
function openChatDrawer() {
    isDrawerOpen = true;
    chatDrawer.classList.add('open');
    chatOverlay.classList.add('active');
    document.body.style.overflow = 'hidden';
    // Focus input when drawer opens
    setTimeout(() => userInput.focus(), 300);
}

function closeChatDrawer() {
    isDrawerOpen = false;
    chatDrawer.classList.remove('open');
    chatOverlay.classList.remove('active');
    document.body.style.overflow = '';
}

// Drawer event listeners
chatFab.addEventListener('click', openChatDrawer);
closeDrawer.addEventListener('click', closeChatDrawer);
chatOverlay.addEventListener('click', closeChatDrawer);

// Close drawer on Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && isDrawerOpen) {
        closeChatDrawer();
    }
});

// Chat functionality
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

// Chat event listeners
sendBtn.addEventListener('click', sendMessage);

userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        sendMessage();
    }
});

resetBtn.addEventListener('click', resetConversation);
