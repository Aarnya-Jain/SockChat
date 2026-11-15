/**
 * ChatManager - Handles chat messaging, system alerts, and message UI rendering.
 */
class ChatManager {
  constructor(messagesContainer, formElement, inputElement, transport) {
    this.container = messagesContainer;
    this.form = formElement;
    this.input = inputElement;
    this.transport = transport;
    this.currentUser = null;

    this._setupEvents();
  }

  setCurrentUser(user) {
    this.currentUser = user;
    if (user && user.user_id) {
      const messages = this.container.querySelectorAll(".user-msg");
      messages.forEach(el => {
        if (el.dataset.userId === user.user_id) {
          el.classList.add("my-msg");
        }
      });
    }
  }

  _setupEvents() {
    this.form.addEventListener("submit", (e) => {
      e.preventDefault();
      const text = this.input.value.trim();
      if (!text) return;

      this.transport.sendAction({
        type: "chat",
        text: text
      });

      this.input.value = "";
    });
  }

  receiveMessage(msg) {
    const isMe = Boolean(this.currentUser && msg.user_id && msg.user_id === this.currentUser.user_id);
    const msgEl = document.createElement("div");
    msgEl.className = `chat-msg user-msg ${isMe ? "my-msg" : ""}`;
    if (msg.user_id) {
      msgEl.dataset.userId = msg.user_id;
    }

    const timeStr = msg.timestamp
      ? new Date(msg.timestamp * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
      : "";

    msgEl.innerHTML = `
      <div class="chat-msg-header">
        <span class="chat-author" style="color: ${msg.color || '#38bdf8'};">${this._escape(msg.from || "Anonymous")}</span>
        <span class="chat-time">${timeStr}</span>
      </div>
      <div class="chat-text">${this._escape(msg.text)}</div>
    `;

    this.container.appendChild(msgEl);
    this._scrollToBottom();
  }

  addSystemMessage(text) {
    const sysEl = document.createElement("div");
    sysEl.className = "chat-msg system";
    sysEl.textContent = text;
    this.container.appendChild(sysEl);
    this._scrollToBottom();
  }

  loadHistory(history) {
    this.container.innerHTML = "";
    history.forEach(item => {
      if (item.type === "chat") {
        this.receiveMessage(item);
      }
    });
  }

  _scrollToBottom() {
    this.container.scrollTop = this.container.scrollHeight;
  }

  _escape(str) {
    return (str || "").replace(/[&<>'"]/g,
      tag => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[tag] || tag));
  }
}
