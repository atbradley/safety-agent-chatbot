// ==UserScript==
// @name         PowerDesk Chat
// @namespace    http://avc.safetyinsurance.com/
// @version      0.1
// @description  try to take over the world!
// @author       You
// @match        https://avc.devsic.com/applications/pwrdesk/*
// @grant        GM_getResourceText
// @require      https://avc.devsic.com/applications/pwrdesk_chat/qchat/q-chat.js?6
// @require      https://unpkg.com/showdown/dist/showdown.min.js
// @resource     qchatStyles https://avc.devsic.com/applications/pwrdesk_chat/qchat/q-chat.css
// @resource     mychatStyles https://avc.devsic.com/applications/pwrdesk_chat/screen.css
// ==/UserScript==


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
        console.log("Sending message:", chat);
        console.log("Chatlog:", chatLog);

        chatLog.push(msgs[0])

        console.log("Chatlog after first push:", chatLog);

        try {
            const response = await fetch('https://avc.devsic.com/pwrdchat/chat', {
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

    var style2 = document.createElement('style');
    style2.innerHTML = GM_getResourceText("mychatStyles");
    document.head.appendChild(style2);
})();