(function() {
    'use strict';

    var converter = new showdown.Converter();

    let params = new URLSearchParams(document.location.search);
    let policy_number = params.get('policy_num') ? params.get('policy_num') : params.get('policy_number');
    let policy_year   = params.get('policy_year');

    var messagesDiv = document.getElementById("messages-div");
    var chat = [];
    var chatLog = [];

    document.addEventListener('qChatBefore', function(event) {
        console.log("Before message send:", event.detail.content);
        chat.push({ role: "user", content: event.detail.content });
        sendMessage(chat);

        messagesDiv.scrollTop = messagesDiv.scrollHeight;
    });

    async function sendMessage(msgs) {
        //TODO: I'm reusing `chat` too many times here.
        let newMsg = msgs.at(-1);
        console.log("Sending message:", newMsg);
        console.log("msgs:", msgs);
        console.log("Chatlog:", chatLog);

        chatLog.push(newMsg)

        console.log("Chatlog after first push:", chatLog);

        try {
            const response = await fetch('https://avc.devsic.com/apis/pwrdesk_chat/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Policy-Number': policy_number,
                },
                body: JSON.stringify(chatLog)
            });
            let chat_response = await response.json();
            console.log("Response from server:", chat_response);
            let response_msg = chat_response.at(-1);
            console.log("New response:", response_msg);
            let message = response_msg.content;
            console.log("new message:", message);
            let html = converter.makeHtml(message);
            document.dispatchEvent(new CustomEvent("qChatReceive", {
                detail: { content: html }
            }));

            chatLog.push({role: "assistant", content: message})

            console.log("Chatlog after second push:", chatLog);

            // scroll #messages-div to bottom
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        } catch (error) {
            console.error("Error sending message:", error);
        }
    }

    document.dispatchEvent(new CustomEvent("qChatReceive", {
        detail: { content: "<p>Hello. How can I help?</p>" }
    }));
})();