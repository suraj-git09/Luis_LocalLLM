// ==================== AUTH + CHAT (Professional Flow) ====================
const authOverlay = document.getElementById("authOverlay");
const mainApp = document.getElementById("mainApp");

const messagesEl = document.getElementById("messages");
const chatForm = document.getElementById("chatForm");
const messageInput = document.getElementById("messageInput");
const sendBtn = document.getElementById("sendBtn");
const clearBtn = document.getElementById("clearBtn");
const statusDot = document.getElementById("statusDot");
const statusText = document.getElementById("statusText");
const logoutBtn = document.getElementById("logoutBtn");

let currentToken = localStorage.getItem("luis_token") || null;
let currentUser = JSON.parse(localStorage.getItem("luis_user") || "null");
let currentConversationId = null;

// --- Auth UI Logic ---
function showAuth() {
  authOverlay.style.display = "flex";
  mainApp.style.display = "none";
}

function showApp(user = null) {
  authOverlay.style.display = "none";
  mainApp.style.display = "grid";
  if (user) {
    document.getElementById("userStatus").textContent = user.is_guest ? "Guest session" : (user.name || user.email || "Signed in");
  }
}

function switchAuthTab(tab) {
  document.querySelectorAll(".auth-tab").forEach(t => t.classList.remove("active"));
  document.querySelectorAll(".auth-form").forEach(f => f.classList.remove("active"));

  if (tab === "login") {
    document.querySelector('[data-tab="login"]').classList.add("active");
    document.getElementById("loginForm").classList.add("active");
  } else {
    document.querySelector('[data-tab="signup"]').classList.add("active");
    document.getElementById("signupForm").classList.add("active");
  }
}

// Tab switching
document.querySelectorAll(".auth-tab").forEach(tab => {
  tab.addEventListener("click", () => {
    switchAuthTab(tab.dataset.tab);
  });
});

// Login
document.getElementById("loginBtn").addEventListener("click", async () => {
  const email = document.getElementById("loginEmail").value.trim();
  const password = document.getElementById("loginPassword").value;
  if (!email || !password) return alert("Please enter email and password");

  const res = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password })
  });
  const data = await res.json();
  if (!res.ok) return alert(data.error || "Login failed");

  completeAuth(data.token, data.user);
});

// Signup
document.getElementById("signupBtn").addEventListener("click", async () => {
  const email = document.getElementById("signupEmail").value.trim();
  const password = document.getElementById("signupPassword").value;
  const name = document.getElementById("signupName").value.trim();

  if (!email || !password) return alert("Email and password required");

  const res = await fetch("/api/auth/signup", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, name })
  });
  const data = await res.json();
  if (!res.ok) return alert(data.error || "Signup failed");

  // Show OTP screen
  document.getElementById("signupForm").style.display = "none";
  document.getElementById("otpForm").style.display = "block";
  document.getElementById("otpEmailDisplay").textContent = email;
  window.pendingEmail = email;

  // Dev mode support: if no real email is configured on the server, the code is returned directly.
  const devCodeEl = document.getElementById("otpDevCode");
  if (devCodeEl) devCodeEl.style.display = "none";

  if (data.dev_code) {
    if (devCodeEl) {
      devCodeEl.textContent = `DEV MODE — Your code is: ${data.dev_code}`;
      devCodeEl.style.display = "block";
    } else {
      // Fallback if the element isn't in the HTML yet
      alert(`Development mode: verification code is ${data.dev_code} (also printed in server console)`);
    }
    // Convenience: pre-fill for local testing
    const codeInput = document.getElementById("otpCode");
    if (codeInput) codeInput.value = data.dev_code;
  }
});

// Verify OTP
document.getElementById("verifyOtpBtn").addEventListener("click", async () => {
  const code = document.getElementById("otpCode").value.trim();
  if (!code || !window.pendingEmail) return;

  const res = await fetch("/api/auth/verify-otp", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: window.pendingEmail, code })
  });
  const data = await res.json();
  if (!res.ok) return alert(data.error || "Verification failed");

  completeAuth(data.token, data.user);
});

document.getElementById("resendOtpBtn").addEventListener("click", async () => {
  if (!window.pendingEmail) return;
  const res = await fetch("/api/auth/signup", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: window.pendingEmail, password: "dummy" }) // backend now treats existing as resend
  });
  const data = await res.json().catch(() => ({}));
  const devCodeEl = document.getElementById("otpDevCode");
  if (data && data.dev_code) {
    if (devCodeEl) {
      devCodeEl.textContent = `DEV MODE — Your code is: ${data.dev_code}`;
      devCodeEl.style.display = "block";
    }
    const codeInput = document.getElementById("otpCode");
    if (codeInput) codeInput.value = data.dev_code;
  }
  alert(data && data.message ? data.message : "New code sent!");
});

// Guest
document.getElementById("guestBtn").addEventListener("click", async () => {
  const res = await fetch("/api/auth/guest", { method: "POST" });
  const data = await res.json();
  completeAuth(data.token, data.user);
});

// Complete login flow
function completeAuth(token, user) {
  currentToken = token;
  currentUser = user;
  localStorage.setItem("luis_token", token);
  localStorage.setItem("luis_user", JSON.stringify(user));

  showApp(user);
  initChatAfterAuth();
}

// Logout
logoutBtn.addEventListener("click", async () => {
  const token = currentToken;
  // Best-effort server-side revoke
  if (token) {
    try {
      await fetch("/api/auth/logout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token })
      });
    } catch (_) { /* ignore network errors on logout */ }
  }
  localStorage.removeItem("luis_token");
  localStorage.removeItem("luis_user");
  currentToken = null;
  currentUser = null;
  location.reload();
});

// --- Chat (now sends token) ---
function escapeHtml(text) {
  return text.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
}

function formatMessage(text) {
  const parts = text.split(/(```[\s\S]*?```)/g);
  return parts.map(part => {
    if (part.startsWith("```") && part.endsWith("```")) {
      const code = part.slice(3, -3).replace(/^[a-z]+\n/i, "");
      return `<pre><code>${escapeHtml(code.trim())}</code></pre>`;
    }
    return `<p>${escapeHtml(part).replace(/\n/g, "<br>")}</p>`;
  }).join("");
}

function appendMessage(role, text, { typing = false } = {}) {
  const article = document.createElement("article");
  article.className = `message ${role}`;
  article.innerHTML = `
    <div class="avatar">${role === "user" ? "You" : "L"}</div>
    <div class="bubble">${typing ? '<div class="typing"><span></span><span></span><span></span></div>' : formatMessage(text)}</div>
  `;
  messagesEl.appendChild(article);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return article;
}

async function sendMessage(text) {
  const trimmed = text.trim();
  if (!trimmed) return;

  appendMessage("user", trimmed);
  messageInput.value = "";
  messageInput.style.height = "auto";
  sendBtn.disabled = true;

  const pending = appendMessage("assistant", "", { typing: true });

  try {
    const body = { message: trimmed };
    if (currentToken) body.token = currentToken;
    if (currentConversationId) body.conversation_id = currentConversationId;

    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    pending.remove();

    if (!res.ok) {
      appendMessage("assistant", data.error || "Something went wrong.");
      return;
    }
    if (data.conversation_id) {
      currentConversationId = data.conversation_id;
    }
    appendMessage("assistant", data.response);

    // Refresh history list so new/updated conv appears (for account users)
    if (currentToken && currentUser && !currentUser.is_guest) {
      loadHistoryList();
    }
  } catch (err) {
    pending.remove();
    appendMessage("assistant", "Could not reach the server.");
  } finally {
    sendBtn.disabled = false;
    messageInput.focus();
  }
}

async function refreshHealth() {
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    statusDot.className = "status-dot " + (data.status === "healthy" ? "healthy" : "degraded");
    statusText.textContent = data.status === "healthy" ? "All systems operational" : "Some checks degraded";
  } catch {
    statusDot.className = "status-dot degraded";
    statusText.textContent = "Server unreachable";
  }
}

function initChatAfterAuth() {
  chatForm.addEventListener("submit", (e) => {
    e.preventDefault();
    sendMessage(messageInput.value);
  });

  messageInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(messageInput.value);
    }
  });

  messageInput.addEventListener("input", () => {
    messageInput.style.height = "auto";
    messageInput.style.height = `${Math.min(messageInput.scrollHeight, 160)}px`;
  });

  clearBtn.addEventListener("click", () => {
    messagesEl.innerHTML = "";
    currentConversationId = null;
    appendMessage("assistant", "Chat cleared. Ask me anything — context is fresh.");
  });

  // New chat button (prominent for account users, works for all)
  const newChatBtn = document.getElementById("newChatBtn");
  if (newChatBtn) {
    newChatBtn.addEventListener("click", () => {
      startNewChat();
    });
  }

  document.querySelectorAll(".chip").forEach(chip => {
    chip.addEventListener("click", () => {
      const prompt = chip.dataset.prompt;
      messageInput.value = prompt;
      sendMessage(prompt);
    });
  });

  refreshHealth();
  setInterval(refreshHealth, 30000);
  messageInput.focus();

  // Show and load History only for real account users (not guests)
  const isAccount = currentToken && currentUser && !currentUser.is_guest;
  const historySection = document.getElementById("historySection");
  if (historySection) {
    historySection.style.display = isAccount ? "block" : "none";
  }
  if (isAccount) {
    loadHistoryList();
  }
}

// --- History (recent conversations) + New Chat for account users ---
async function loadHistoryList() {
  const listEl = document.getElementById("historyList");
  if (!listEl || !currentToken) return;
  listEl.innerHTML = `<div style="color:var(--muted);font-size:0.75rem;padding:4px 8px;">Loading…</div>`;
  try {
    const res = await fetch(`/api/history?token=${encodeURIComponent(currentToken)}`);
    const data = await res.json();
    if (!res.ok || !data.conversations) {
      listEl.innerHTML = `<div style="color:var(--muted);font-size:0.75rem;padding:4px 8px;">No history yet</div>`;
      return;
    }
    renderHistoryList(data.conversations, listEl);
  } catch (e) {
    listEl.innerHTML = `<div style="color:var(--muted);font-size:0.75rem;padding:4px 8px;">Unable to load</div>`;
  }
}

function renderHistoryList(conversations, container) {
  container.innerHTML = "";
  if (!conversations || conversations.length === 0) {
    container.innerHTML = `<div style="color:var(--muted);font-size:0.75rem;padding:4px 8px;">No conversations yet</div>`;
    return;
  }
  conversations.forEach((c) => {
    const item = document.createElement("div");
    item.className = "history-item";
    const title = (c.title || "Untitled").replace(/</g, "&lt;");
    const when = c.updated_at ? new Date(c.updated_at).toLocaleDateString() : "";
    item.innerHTML = `<span class="title">${title}</span><span class="meta">${when}</span>`;
    item.title = title;
    item.addEventListener("click", () => {
      loadConversation(c.id);
    });
    container.appendChild(item);
  });
}

async function loadConversation(convId) {
  if (!currentToken) return;
  try {
    const res = await fetch(`/api/history/${convId}?token=${encodeURIComponent(currentToken)}`);
    const data = await res.json();
    if (!res.ok || !data.messages) {
      alert(data.error || "Failed to load conversation");
      return;
    }
    // Replace current chat view with loaded history
    messagesEl.innerHTML = "";
    currentConversationId = convId;
    data.messages.forEach((m) => {
      appendMessage(m.role === "user" ? "user" : "assistant", m.content);
    });
    // Scroll to bottom
    messagesEl.scrollTop = messagesEl.scrollHeight;
  } catch (e) {
    alert("Could not load conversation.");
  }
}

function startNewChat() {
  messagesEl.innerHTML = "";
  currentConversationId = null;
  appendMessage("assistant", "New chat started. What would you like to talk about?");
  // Optional: refresh list (no change but keeps UI fresh)
  if (currentToken && currentUser && !currentUser.is_guest) {
    loadHistoryList();
  }
}

// Boot
(function init() {
  if (currentToken && currentUser) {
    showApp(currentUser);
    initChatAfterAuth();
  } else {
    showAuth();
  }
})();