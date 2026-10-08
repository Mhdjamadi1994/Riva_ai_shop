(() => {
  "use strict";
  const accessKey = "riva.access";
  const refreshKey = "riva.refresh";
  const conversationKey = "riva.conversation";
  const panel = document.querySelector("#assistantWidgetPanel");
  const messages = document.querySelector("#assistantWidgetMessages");
  const input = document.querySelector("#assistantWidgetInput");
  const form = document.querySelector("#assistantWidgetForm");

  function open() {
    if (!sessionStorage.getItem(accessKey)) {
      const next = `${location.pathname}${location.search}${location.hash}`;
      location.assign(`/account/?next=${encodeURIComponent(next)}`);
      return;
    }
    panel.classList.add("is-open");
    panel.setAttribute("aria-hidden", "false");
    panel.inert = false;
    input.focus();
  }
  function close() {
    panel.classList.remove("is-open");
    panel.setAttribute("aria-hidden", "true");
    panel.inert = true;
  }
  function addBubble(text, role) {
    const bubble = document.createElement("div");
    bubble.className = `chat-bubble ${role === "user" ? "user-bubble" : "assistant-bubble"}`;
    bubble.textContent = text;
    messages.append(bubble);
    messages.scrollTop = messages.scrollHeight;
    return bubble;
  }
  async function read(response) {
    try {
      return await response.json();
    } catch {
      return {};
    }
  }
  async function postMessage(text) {
    let token = sessionStorage.getItem(accessKey);
    const send = () =>
      fetch("/api/chat/", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          message: text,
          ...(sessionStorage.getItem(conversationKey)
            ? {
                conversation_id: Number(
                  sessionStorage.getItem(conversationKey),
                ),
              }
            : {}),
        }),
      });
    let response = await send();
    if (response.status === 401 && sessionStorage.getItem(refreshKey)) {
      const refreshed = await fetch("/api/token/refresh/", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh: sessionStorage.getItem(refreshKey) }),
      });
      const tokens = await read(refreshed);
      if (refreshed.ok && tokens.access) {
        token = tokens.access;
        sessionStorage.setItem(accessKey, token);
        if (tokens.refresh) sessionStorage.setItem(refreshKey, tokens.refresh);
        response = await send();
      }
    }
    return response;
  }

  document
    .querySelectorAll("[data-open-assistant]")
    .forEach((button) => button.addEventListener("click", open));
  document
    .querySelector("#assistantWidgetClose")
    .addEventListener("click", close);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    if (!sessionStorage.getItem(accessKey)) return open();
    input.value = "";
    addBubble(text, "user");
    const pending = addBubble("Looking through the catalog...", "assistant");
    const send = form.querySelector("button[type=submit]");
    send.disabled = true;
    try {
      const response = await postMessage(text);
      const data = await read(response);
      if (!response.ok)
        throw new Error(
          data.detail || data.message || "Riva could not answer right now.",
        );
      if (data.conversation_id)
        sessionStorage.setItem(conversationKey, String(data.conversation_id));
      pending.textContent = data.reply || "No reply was returned.";
    } catch (error) {
      pending.textContent = error.message || "Riva could not answer right now.";
    } finally {
      send.disabled = false;
      input.focus();
      messages.scrollTop = messages.scrollHeight;
    }
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") close();
  });
})();
