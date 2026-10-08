(() => {
  "use strict";
  const accessKey = "riva.access";
  const refreshKey = "riva.refresh";
  const userKey = "riva.username";
  const workspace = document.querySelector("#supportWorkspace");
  const prompt = document.querySelector("#supportLoginPrompt");
  const form = document.querySelector("#supportCenterForm");
  const message = document.querySelector("#supportCenterMessage");
  const ticketList = document.querySelector("#supportCenterTickets");

  async function read(response) {
    try {
      return await response.json();
    } catch {
      return {};
    }
  }

  async function refresh() {
    const token = sessionStorage.getItem(refreshKey);
    if (!token) return false;
    try {
      const response = await fetch("/api/token/refresh/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh: token }),
        credentials: "same-origin",
      });
      const data = await read(response);
      if (!response.ok || !data.access) throw new Error("refresh rejected");
      sessionStorage.setItem(accessKey, data.access);
      if (data.refresh) sessionStorage.setItem(refreshKey, data.refresh);
      return true;
    } catch {
      sessionStorage.removeItem(accessKey);
      sessionStorage.removeItem(refreshKey);
      sessionStorage.removeItem(userKey);
      return false;
    }
  }

  async function request(options = {}) {
    let token = sessionStorage.getItem(accessKey);
    if (!token) return null;
    const send = () =>
      fetch("/api/storefront/account/tickets/", {
        ...options,
        credentials: "same-origin",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          ...(options.headers || {}),
          Authorization: `Bearer ${token}`,
        },
      });
    let response = await send();
    if (response.status === 401 && (await refresh())) {
      token = sessionStorage.getItem(accessKey);
      response = await send();
    }
    if (response.status === 401) {
      sessionStorage.removeItem(accessKey);
      sessionStorage.removeItem(refreshKey);
      sessionStorage.removeItem(userKey);
      return null;
    }
    return response;
  }

  function render(tickets) {
    ticketList.replaceChildren();
    if (!tickets.length) {
      const empty = document.createElement("p");
      empty.className = "support-empty-state";
      empty.textContent =
        "You have no support requests yet. Send a message above and the team will reply here.";
      ticketList.append(empty);
      return;
    }
    const labels = {
      open: "Open",
      in_progress: "In progress",
      resolved: "Resolved",
    };
    tickets.forEach((ticket) => {
      const card = document.createElement("article");
      card.className = "support-center-ticket";
      const head = document.createElement("div");
      head.className = "support-ticket-head";
      const title = document.createElement("strong");
      title.textContent = `#${ticket.id} · ${ticket.subject}`;
      const status = document.createElement("span");
      status.className = `ticket-status ticket-${ticket.status}`;
      status.textContent = labels[ticket.status] || ticket.status;
      head.append(title, status);
      card.append(head);
      const body = document.createElement("p");
      body.textContent = ticket.message;
      card.append(body);
      if (ticket.staff_reply) {
        const reply = document.createElement("blockquote");
        reply.textContent = ticket.staff_reply;
        card.append(reply);
      }
      const time = document.createElement("time");
      time.dateTime = ticket.updated_at;
      time.textContent = `Updated ${new Date(ticket.updated_at).toLocaleString()}`;
      card.append(time);
      ticketList.append(card);
    });
  }

  async function loadTickets() {
    prompt.hidden = Boolean(sessionStorage.getItem(accessKey));
    workspace.hidden = !sessionStorage.getItem(accessKey);
    if (workspace.hidden) return;
    const response = await request();
    if (!response) {
      prompt.hidden = false;
      workspace.hidden = true;
      return;
    }
    const data = await read(response);
    if (!response.ok) {
      ticketList.textContent =
        data.detail || "Support requests could not be loaded.";
      return;
    }
    render(Array.isArray(data) ? data : data.results || []);
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = form.querySelector("button[type=submit]");
    button.disabled = true;
    message.textContent = "Sending your request...";
    try {
      const response = await request({
        method: "POST",
        body: JSON.stringify({
          subject: form.elements.subject.value.trim(),
          message: form.elements.message.value.trim(),
        }),
      });
      if (!response) {
        prompt.hidden = false;
        workspace.hidden = true;
        throw new Error("Your sign-in expired. Sign in again to continue.");
      }
      const data = await read(response);
      if (!response.ok)
        throw new Error(
          Object.values(data).flat().join(" ") ||
            "Your request could not be sent.",
        );
      form.reset();
      message.textContent = "Your request was sent. Replies will appear below.";
      await loadTickets();
    } catch (error) {
      message.textContent = error.message || "Your request could not be sent.";
    } finally {
      button.disabled = false;
    }
  });

  loadTickets();
})();
