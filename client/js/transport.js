/**
 * NetworkTransport - Client-side abstraction for HTTP / SSE bridge to Python Socket Core.
 * Manages Server-Sent Events stream and HTTP POST action dispatches.
 */
class NetworkTransport {
  constructor() {
    this.sessionId = this._getOrCreateSessionId();
    this.eventSource = null;
    this.messageCallbacks = [];
    this.statusCallbacks = [];
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 10;
    this.isManualClose = false;
  }

  _getOrCreateSessionId() {
    let sid = sessionStorage.getItem("sockchat_session_id");
    if (!sid) {
      sid = "sess_" + Math.random().toString(36).substring(2, 10) + Date.now().toString(36);
      sessionStorage.setItem("sockchat_session_id", sid);
    }
    return sid;
  }

  connect() {
    this.isManualClose = false;
    this._notifyStatus("connecting");

    const streamUrl = `/api/stream?session_id=${encodeURIComponent(this.sessionId)}`;
    this.eventSource = new EventSource(streamUrl);

    this.eventSource.onopen = () => {
      this.reconnectAttempts = 0;
      this._notifyStatus("connected");
    };

    this.eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        this._notifyMessage(data);
      } catch (err) {
        console.error("Failed to parse SSE payload:", event.data, err);
      }
    };

    this.eventSource.onerror = (err) => {
      if (this.isManualClose) return;
      this._notifyStatus("disconnected");
      this.eventSource.close();
      this.eventSource = null;

      if (this.reconnectAttempts < this.maxReconnectAttempts) {
        this.reconnectAttempts++;
        const delay = Math.min(1000 * Math.pow(1.5, this.reconnectAttempts), 8000);
        setTimeout(() => this.connect(), delay);
      }
    };
  }

  async sendAction(action) {
    try {
      const resp = await fetch("/api/action", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          session_id: this.sessionId,
          action: action
        })
      });

      if (!resp.ok) {
        const errorData = await resp.json().catch(() => ({}));
        console.warn("Action delivery warning:", errorData);
      }
    } catch (err) {
      console.error("Failed to transmit action to bridge:", err);
    }
  }

  onMessage(callback) {
    this.messageCallbacks.push(callback);
  }

  onStatusChange(callback) {
    this.statusCallbacks.push(callback);
  }

  _notifyMessage(msg) {
    this.messageCallbacks.forEach(cb => {
      try { cb(msg); } catch (e) { console.error("Error in message callback", e); }
    });
  }

  _notifyStatus(status) {
    this.statusCallbacks.forEach(cb => {
      try { cb(status); } catch (e) { console.error("Error in status callback", e); }
    });
  }

  disconnect() {
    this.isManualClose = true;
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
    this._notifyStatus("disconnected");
  }
}
