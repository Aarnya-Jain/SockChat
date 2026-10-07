document.addEventListener("DOMContentLoaded", () => {
  const tabCreate = document.getElementById("tabCreate");
  const tabJoin = document.getElementById("tabJoin");
  const joinKeyGroup = document.getElementById("joinKeyGroup");
  const roomKeyInput = document.getElementById("roomKey");
  const nameInput = document.getElementById("displayName");
  const submitBtn = document.getElementById("submitBtn");
  const btnText = document.getElementById("btnText");
  const btnIcon = document.getElementById("btnIcon");
  const lobbyForm = document.getElementById("lobbyForm");
  const toast = document.getElementById("toast");

  let currentMode = "create"; // "create" or "join"

  // Restore cached username if available
  const savedName = localStorage.getItem("sockchat_name");
  if (savedName) {
    nameInput.value = savedName;
  }

  // Check URL parameters (e.g. if arriving via invite link)
  const urlParams = new URLSearchParams(window.location.search);
  const inviteCode = urlParams.get("join") || urlParams.get("room");
  if (inviteCode) {
    setMode("join");
    roomKeyInput.value = inviteCode.toUpperCase();
  }

  function setMode(mode) {
    currentMode = mode;
    if (mode === "create") {
      tabCreate.classList.add("active");
      tabJoin.classList.remove("active");
      joinKeyGroup.style.display = "none";
      roomKeyInput.removeAttribute("required");
      btnText.textContent = "Create New Room";
      btnIcon.textContent = "✨";
    } else {
      tabJoin.classList.add("active");
      tabCreate.classList.remove("active");
      joinKeyGroup.style.display = "block";
      roomKeyInput.setAttribute("required", "true");
      btnText.textContent = "Join Room";
      btnIcon.textContent = "🚪";
      roomKeyInput.focus();
    }
  }

  tabCreate.addEventListener("click", () => setMode("create"));
  tabJoin.addEventListener("click", () => setMode("join"));

  function showToast(message, isError = false) {
    toast.textContent = message;
    toast.className = `toast show ${isError ? "error" : ""}`;
    setTimeout(() => {
      toast.className = "toast";
    }, 3500);
  }

  lobbyForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const name = nameInput.value.trim();
    if (!name) {
      showToast("Please enter a display name", true);
      return;
    }

    localStorage.setItem("sockchat_name", name);

    if (currentMode === "create") {
      // Navigate to room page requesting creation
      window.location.href = `/room?action=create&name=${encodeURIComponent(name)}`;
    } else {
      const roomKey = roomKeyInput.value.trim().toUpperCase();
      if (!roomKey) {
        showToast("Please enter a valid room key", true);
        return;
      }
      window.location.href = `/room?room=${encodeURIComponent(roomKey)}&name=${encodeURIComponent(name)}`;
    }
  });
});
