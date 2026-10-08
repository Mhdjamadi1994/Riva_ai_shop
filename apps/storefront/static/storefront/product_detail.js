(() => {
  "use strict";
  const id = document.body.dataset.productId;
  const recommendationId = new URLSearchParams(window.location.search).get("recommendation");
  const accessKey = "riva.access";
  const userKey = "riva.username";
  const cartKey = "riva.cart.v1";
  const user = () => sessionStorage.getItem(userKey) || "guest";
  if (recommendationId) {
    fetch("/api/recommendations/events/", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({ query_id: recommendationId, product_id: Number(id) }),
    }).catch(() => {});
  }
  const money = (value) =>
    new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 }).format((Number(value) || 0) / (Number(document.body.dataset.tomanPerUsd) || 265900));
  const priceLabel = document.querySelector("#productDetailPrice");
  if (priceLabel) priceLabel.textContent = money(priceLabel.dataset.tomanPrice);
  const headers = () => {
    const result = { Accept: "application/json" };
    if (sessionStorage.getItem(accessKey))
      result.Authorization = `Bearer ${sessionStorage.getItem(accessKey)}`;
    return result;
  };
  async function read(response) {
    const text = await response.text();
    try {
      return text ? JSON.parse(text) : {};
    } catch {
      return {};
    }
  }
  function openAccount() {
    window.location.href = `/account/?next=${encodeURIComponent(location.pathname)}`;
  }

  const addButton = document.querySelector("#detailAddToCart");
  if (document.body.dataset.productInStock !== "true") {
    addButton.disabled = true;
    addButton.textContent = "Out of stock";
  }

  async function loadEngagement() {
    try {
      const response = await fetch(
        `/api/storefront/products/${id}/engagement/`,
        { headers: headers(), credentials: "same-origin" },
      );
      const data = await read(response);
      if (!response.ok) throw new Error("Could not load product activity.");
      const like = document.querySelector("#detailLike");
      const save = document.querySelector("#detailSave");
      like.setAttribute("aria-pressed", String(data.liked));
      save.setAttribute("aria-pressed", String(data.saved));
      document.querySelector("#detailLikeCount").textContent = data.likes;
      document.querySelector("#detailSaveCount").textContent = data.saves;
    } catch (error) {
      document.querySelector("#engagementMessage").textContent = error.message;
    }
  }

  async function toggle(field) {
    if (!sessionStorage.getItem(accessKey)) return openAccount();
    const button = document.querySelector(
      field === "liked" ? "#detailLike" : "#detailSave",
    );
    button.disabled = true;
    try {
      const response = await fetch(
        `/api/storefront/products/${id}/engagement/`,
        {
          method: "PATCH",
          headers: { ...headers(), "Content-Type": "application/json" },
          credentials: "same-origin",
          body: JSON.stringify({
            [field]: button.getAttribute("aria-pressed") !== "true",
          }),
        },
      );
      const data = await read(response);
      if (!response.ok)
        throw new Error(data.detail || "Could not save this action.");
      const active = field === "liked" ? data.liked : data.saved;
      button.setAttribute("aria-pressed", String(active));
      document.querySelector(
        field === "liked" ? "#detailLikeCount" : "#detailSaveCount",
      ).textContent = field === "liked" ? data.likes : data.saves;
      document.querySelector("#engagementMessage").textContent = active
        ? "Saved to your account."
        : "Removed from your account.";
    } catch (error) {
      document.querySelector("#engagementMessage").textContent = error.message;
    } finally {
      button.disabled = false;
    }
  }

  async function loadReviews() {
    const list = document.querySelector("#reviewList");
    try {
      const response = await fetch(`/api/storefront/products/${id}/reviews/`, {
        headers: headers(),
        credentials: "same-origin",
      });
      const data = await read(response);
      if (!response.ok) throw new Error("Reviews could not be loaded.");
      list.replaceChildren();
      document.querySelector("#detailReviewCount").textContent = data.count;
      document.querySelector("#detailRating").textContent = data.average
        ? `${Number(data.average).toFixed(1)} / 5`
        : "Not rated yet";
      if (!data.results.length) {
        const empty = document.createElement("p");
        empty.textContent =
          "No reviews yet. Be the first to share a useful note.";
        list.append(empty);
        return;
      }
      data.results.forEach((review) => {
        const card = document.createElement("article");
        card.className = "review-card";
        const meta = document.createElement("div");
        meta.className = "review-meta";
        const name = document.createElement("strong");
        name.textContent = review.username;
        const rating = document.createElement("span");
        rating.textContent = `${"?".repeat(review.rating)}${"?".repeat(5 - review.rating)}`;
        const body = document.createElement("p");
        body.textContent = review.body;
        const date = document.createElement("small");
        date.textContent = new Date(review.updated_at).toLocaleDateString();
        meta.append(name, rating);
        card.append(meta, body, date);
        list.append(card);
      });
    } catch (error) {
      list.textContent = error.message;
    }
  }

  addButton.addEventListener("click", () => {
    const key = `${cartKey}:${user()}`;
    let cart = [];
    try {
      cart = JSON.parse(sessionStorage.getItem(key) || "[]");
    } catch {
      cart = [];
    }
    if (!Array.isArray(cart)) cart = [];
    const current = cart.find((item) => Number(item.id) === Number(id));
    if (current) {
      current.quantity = Math.min(20, (Number(current.quantity) || 1) + 1);
      current.image_url = current.image_url || document.body.dataset.productImage || "";
    } else {
      cart.push({
        id: Number(id),
        name: document.body.dataset.productName,
        price: document.body.dataset.productPrice,
        category: document.body.dataset.productCategory || "other",
        image_url: document.body.dataset.productImage || "",
        recommendation_run_id: recommendationId || "",
        quantity: 1,
      });
    }
    sessionStorage.setItem(key, JSON.stringify(cart));
    const button = document.querySelector("#detailAddToCart");
    button.textContent = "Added to bag";
    button.disabled = true;
    window.setTimeout(() => {
      button.textContent = "Add to bag";
      button.disabled = false;
    }, 1400);
  });
  document
    .querySelector("#detailLike")
    .addEventListener("click", () => toggle("liked"));
  document
    .querySelector("#detailSave")
    .addEventListener("click", () => toggle("saved"));
  document
    .querySelector("#reviewForm")
    .addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!sessionStorage.getItem(accessKey)) return openAccount();
      const form = event.currentTarget;
      const message = document.querySelector("#reviewMessage");
      const button = form.querySelector("button[type=submit]");
      button.disabled = true;
      message.textContent = "Saving your review?";
      try {
        const response = await fetch(
          `/api/storefront/products/${id}/reviews/`,
          {
            method: "POST",
            headers: { ...headers(), "Content-Type": "application/json" },
            credentials: "same-origin",
            body: JSON.stringify({
              rating: Number(form.elements.rating.value),
              body: form.elements.body.value.trim(),
            }),
          },
        );
        const data = await read(response);
        if (!response.ok)
          throw new Error(
            data.detail ||
              Object.values(data).flat().join(" ") ||
              "Review could not be saved.",
          );
        message.textContent =
          "Your review is saved. You can update it by submitting again.";
        form.elements.body.value = "";
        await loadReviews();
      } catch (error) {
        message.textContent = error.message;
      } finally {
        button.disabled = false;
      }
    });
  loadEngagement();
  loadReviews();
})();
