document.addEventListener('DOMContentLoaded', function() {
    const chatLog = document.getElementById('chat-log');
    const userInput = document.getElementById('user-input');
    const sendButton = document.getElementById('send-button');
    const chatbotCharacter = document.getElementById('chatbot-character');

    let lastMessageDate = null;

    function addDateSeparator(dateString) {
        const date = new Date(dateString);
        const formattedDate = `[${date.getFullYear()}년 ${date.getMonth() + 1}월 ${date.getDate()}일]`;
        
        const separatorDiv = document.createElement('div');
        separatorDiv.classList.add('date-separator');
        separatorDiv.textContent = formattedDate;
        chatLog.appendChild(separatorDiv);
    }

    function appendMessage(sender, message, timestamp) {
        if (timestamp) {
            const messageDate = new Date(timestamp).toDateString();
            if (lastMessageDate !== messageDate) {
                addDateSeparator(timestamp);
                lastMessageDate = messageDate;
            }
        }

        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', `${sender}-message`);
        
        const messageParagraph = document.createElement('p');
        messageParagraph.textContent = message;
        messageDiv.appendChild(messageParagraph);

        if (timestamp) {
            const time = new Date(timestamp);
            const timeString = `(${(time.getHours()).toString().padStart(2, '0')}:${(time.getMinutes()).toString().padStart(2, '0')})`;
            const timeSpan = document.createElement('span');
            timeSpan.classList.add('timestamp');
            timeSpan.textContent = timeString;
            messageDiv.appendChild(timeSpan);
        }
        
        chatLog.appendChild(messageDiv);
        chatLog.scrollTop = chatLog.scrollHeight;
    }

    async function sendMessage() {
        const message = userInput.value.trim();
        if (message === '') return;

        const userTimestamp = new Date().toISOString();
        appendMessage('user', message, userTimestamp);
        userInput.value = '';

        try {
            const response = await fetch('/chat/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: JSON.stringify({ message: message })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            const botResponse = data.message;
            const characterEmotion = data.character_emotion;
            const botTimestamp = data.timestamp;

            setTimeout(() => {
                appendMessage('bot', botResponse, botTimestamp);
                
                chatbotCharacter.src = STATIC_URLS[characterEmotion] || STATIC_URLS.default;

            }, 500);

        } catch (error) {
            console.error('Error sending message:', error);
            appendMessage('bot', '죄송합니다. 메시지를 처리하는 데 문제가 발생했습니다.', new Date().toISOString());
            chatbotCharacter.src = STATIC_URLS.sad;
        }
    }

    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    sendButton.addEventListener('click', sendMessage);
    userInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });

    // 초기 채팅 기록을 타임라인 형식으로 표시
    if (chatHistory) {
        chatHistory.forEach(chat => {
            appendMessage(chat.is_user ? 'user' : 'bot', chat.message, chat.timestamp);
        });
    }
});
