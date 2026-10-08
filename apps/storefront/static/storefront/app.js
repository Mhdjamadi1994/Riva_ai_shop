const startApp = () => {
  "use strict";
  const body = document.body;
  if (!body) return;
  const bodyData = body.dataset || {};

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [
    ...root.querySelectorAll(selector),
  ];
  const root = document.documentElement;
  const currency = bodyData.currency || "USDT";
  const tomanPerUsd = Number(bodyData.tomanPerUsd) || 265900;
  const initialParams = new URLSearchParams(window.location.search);
  const initialPriceInUsd = (name) => {
    const value = Number(initialParams.get(name));
    return Number.isFinite(value) && value > 0
      ? String(value / tomanPerUsd)
      : "";
  };
  const accessKey = "riva.access";
  const refreshKey = "riva.refresh";
  const userKey = "riva.username";
  const cartKey = "riva.cart.v1";
  const artOptions = {
    laptops: { color: "art-blue", icon: "i-book" },
    keyboards: { color: "art-lilac", icon: "i-keyboard" },
    gaming: { color: "art-coral", icon: "i-gamepad" },
    pcs: { color: "art-blue", icon: "i-gamepad" },
    cpus: { color: "art-lilac", icon: "i-chip" },
    gpus: { color: "art-coral", icon: "i-chip" },
    ram: { color: "art-mint", icon: "i-chip" },
    monitors: { color: "art-blue", icon: "i-monitor" },
    accessories: { color: "art-mint", icon: "i-mouse" },
    other: { color: "art-blue", icon: "i-book" },
    motherboards: { color: "art-lilac", icon: "i-chip" },
    storage: { color: "art-blue", icon: "i-chip" },
    power: { color: "art-coral", icon: "i-chip" },
    cooling: { color: "art-mint", icon: "i-chip" },
    cases: { color: "art-blue", icon: "i-gamepad" },
  };
  const orderStatus = {
    pending: "Pending review",
    awaiting_payment: "Awaiting payment",
    confirmed: "Confirmed",
    preparing: "Preparing",
    shipped: "Shipped",
    delivered: "Delivered",
    cancelled: "Cancelled",
  };

  const state = {
    page: 1,
    pages: 1,
    count: 0,
    search: new URLSearchParams(window.location.search).get("search") || "",
    category: new URLSearchParams(window.location.search).get("category") || "",
    ordering: "-created_at",
    priceMin: initialPriceInUsd("price_min"),
    priceMax: initialPriceInUsd("price_max"),
    minRating:
      new URLSearchParams(window.location.search).get("min_rating") || "",
    products: [],
    cart: loadCart(),
    loadingCatalog: false,
    catalogController: null,
    suggestionController: null,
    suggestionTimer: null,
    afterAuth: null,
  };

  function loadCart() {
    try {
      const owner = sessionStorage.getItem(userKey) || "guest";
      const value = JSON.parse(
        sessionStorage.getItem(`${cartKey}:${owner}`) ||
          (owner === "guest" ? sessionStorage.getItem(cartKey) : "[]") ||
          "[]",
      );
      if (!Array.isArray(value)) return [];
      return value
        .filter(
          (item) =>
            Number.isSafeInteger(Number(item.id)) && Number(item.id) > 0,
        )
        .map((item) => ({
          id: Number(item.id),
          name: String(item.name || "Selected product"),
          price: String(item.price || "0"),
          category: String(item.category || "other"),
          quantity: Math.min(20, Math.max(1, Number(item.quantity) || 1)),
        }));
    } catch {
      return [];
    }
  }

  function saveCart() {
    const owner = sessionStorage.getItem(userKey) || "guest";
    sessionStorage.setItem(`${cartKey}:${owner}`, JSON.stringify(state.cart));
    renderCart();
  }

  function formatMoney(value, unit = currency) {
    const amount = Number(value);
    const formatted = Number.isFinite(amount)
      ? new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(
          amount,
        )
      : "—";
    return unit ? `${formatted} ${unit}` : formatted;
  }

  function formatShopMoney(value) {
    const amount = Number(value);
    const dollars = Number.isFinite(amount) ? amount / tomanPerUsd : NaN;
    return Number.isFinite(dollars)
      ? new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 }).format(dollars)
      : "—";
  }

  function icon(name, className = "") {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    if (className) svg.setAttribute("class", className);
    svg.setAttribute("aria-hidden", "true");
    const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
    use.setAttribute("href", `#${name}`);
    svg.append(use);
    return svg;
  }

  function toast(message, isError = false) {
    const region = $("#toastRegion");
    const item = document.createElement("div");
    item.className = `toast${isError ? " is-error" : ""}`;
    item.textContent = message;
    region.append(item);
    window.setTimeout(() => item.remove(), 3600);
  }

  function flattenErrors(data) {
    if (!data) return "Request failed. Please try again.";
    if (typeof data === "string") return data;
    if (Array.isArray(data)) return data.map(flattenErrors).join(" ");
    if (typeof data === "object") {
      const values = Object.values(data).map(flattenErrors).filter(Boolean);
      return values.join(" ") || "Request failed. Please try again.";
    }
    return String(data);
  }

  async function apiRequest(path, options = {}) {
    if (typeof path !== "string" || !path.trim()) {
      throw new Error("Invalid API path");
    }

    const { auth = false, retry = true, ...fetchOptions } = options;
    const headers = new Headers(fetchOptions.headers || {});

    if (fetchOptions.body && !(fetchOptions.body instanceof FormData)) {
      headers.set("Content-Type", "application/json");
    }

    if (auth && sessionStorage.getItem(accessKey)) {
      headers.set(
        "Authorization",
        `Bearer ${sessionStorage.getItem(accessKey)}`,
      );
    }

    const response = await fetch(path, {
      ...fetchOptions,
      headers,
      credentials: "same-origin",
    });

    if (
      response.status === 401 &&
      auth &&
      retry &&
      (await refreshAccessToken())
    ) {
      return apiRequest(path, { ...options, retry: false });
    }

    return response;
  }

  async function responseData(response) {
    const text = await response.text();
    if (!text) return {};
    try {
      return JSON.parse(text);
    } catch {
      return { detail: "The server response could not be read." };
    }
  }

  async function refreshAccessToken() {
    const refresh = sessionStorage.getItem(refreshKey);
    if (!refresh) return false;
    try {
      const response = await fetch("/api/token/refresh/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ refresh }),
      });
      const data = await responseData(response);
      if (!response.ok || !data.access) throw new Error("refresh rejected");
      sessionStorage.setItem(accessKey, data.access);
      if (data.refresh) sessionStorage.setItem(refreshKey, data.refresh);
      return true;
    } catch {
      clearSession(false);
      return false;
    }
  }

  function setSession(data, username) {
    const guestCart = loadCartFor("guest");
    sessionStorage.setItem(accessKey, data.access);
    sessionStorage.setItem(refreshKey, data.refresh);
    sessionStorage.setItem(userKey, username);
    const ownCart = loadCartFor(username);
    state.cart = ownCart.length ? ownCart : guestCart;
    saveCart();
    sessionStorage.removeItem(`${cartKey}:guest`);
    updateAccountButton();
  }

  function loadCartFor(owner) {
    try {
      const value = JSON.parse(
        sessionStorage.getItem(`${cartKey}:${owner}`) ||
          (owner === "guest" ? sessionStorage.getItem(cartKey) : "[]") ||
          "[]",
      );
      if (!Array.isArray(value)) return [];
      return value
        .filter(
          (item) =>
            Number.isSafeInteger(Number(item.id)) && Number(item.id) > 0,
        )
        .map((item) => ({
          id: Number(item.id),
          name: String(item.name || "Selected product"),
          price: String(item.price || "0"),
          category: String(item.category || "other"),
          quantity: Math.min(20, Math.max(1, Number(item.quantity) || 1)),
        }));
    } catch {
      return [];
    }
  }

  function clearSession(showMessage = true) {
    sessionStorage.removeItem(accessKey);
    sessionStorage.removeItem(refreshKey);
    sessionStorage.removeItem(userKey);
    sessionStorage.removeItem("riva.conversation");
    state.cart = loadCartFor("guest");
    renderCart();
    updateAccountButton();
    if (showMessage) toast("You have signed out.");
  }

  function isSignedIn() {
    return Boolean(sessionStorage.getItem(accessKey));
  }

  function updateAccountButton() {
    const label = $("#accountLabel");
    const button = $("#accountButton");

    if (!label || !button) return;

    const username = sessionStorage.getItem(userKey);
    label.textContent = username || "Sign in / Register";
    button.setAttribute(
      "aria-label",
      username
        ? `Account ${username}, view orders`
        : "Sign in or create an account",
    );
  }

  function createProductCard(product, index) {
    const art =
      artOptions[product.category] ||
      Object.values(artOptions)[index % Object.keys(artOptions).length];
    const card = document.createElement("article");
    card.className = "product-card";

    const visual = document.createElement("div");
    visual.className = `product-visual ${art.color}`;
    const badge = document.createElement("span");
    badge.className = "product-badge";
    badge.textContent = product.in_stock ? "In stock" : "Out of stock";
    const productArt = document.createElement("img");
    productArt.className = "product-photo";
    productArt.src = product.image_url || "/static/storefront/images/products/other.jpg";
    productArt.alt = product.name || "Computer hardware";
    productArt.loading = "lazy";
    productArt.decoding = "async";
    productArt.addEventListener("error", () => {
      productArt.src = "/static/storefront/images/products/other.jpg";
    }, { once: true });
    const imageLink = document.createElement("a");
    imageLink.className = "product-image-link";
    const productHref = `/products/${product.id}/${product.recommendation_run_id ? `?recommendation=${encodeURIComponent(product.recommendation_run_id)}` : ""}`;
    imageLink.href = productHref;
    imageLink.setAttribute("aria-label", `View ${product.name}`);
    imageLink.append(productArt);
    visual.append(imageLink, badge);

    const info = document.createElement("div");
    info.className = "product-info";
    const name = document.createElement("h3");
    name.className = "product-name";
    const detailLink = document.createElement("a");
    detailLink.href = productHref;
    detailLink.textContent = product.name || "Unnamed product";
    name.append(detailLink);
    if (product.recommendation_reason) {
      const reason = document.createElement("small");
      reason.className = "recommendation-reason";
      reason.textContent = product.recommendation_reason;
      info.append(reason);
    }
    const description = document.createElement("p");
    description.className = "product-description";
    description.textContent =
      product.description || "Ask the Riva shopping assistant for details.";
    const rating = document.createElement("p");
    rating.className = "product-rating-preview";
    rating.textContent = product.average_rating
      ? `${Number(product.average_rating).toFixed(1)} / 5 · ${product.review_count || 0} reviews`
      : "Not rated yet";
    const purchase = document.createElement("div");
    purchase.className = "product-purchase";
    const price = document.createElement("span");
    price.className = "product-price";
    price.textContent = formatShopMoney(product.price);
    const priceLabel = document.createElement("small");
    priceLabel.textContent = "Listed price";
    price.append(priceLabel);
    const add = document.createElement("button");
    add.className = "add-to-cart";
    add.type = "button";
    add.setAttribute("aria-label", `Add ${product.name || "product"} to cart`);
    add.disabled = !product.in_stock;
    if (!product.in_stock) add.title = "This item is not currently in stock.";
    add.append(icon("i-bag"));
    add.addEventListener("click", () => addToCart(product));
    const engagement = document.createElement("div");
    engagement.className = "product-engagement";
    for (const [field, label, glyph, count] of [
      ["liked", "Like", "♥", product.like_count || 0],
      ["saved", "Save", "☆", product.favorite_count || 0],
    ]) {
      const action = document.createElement("button");
      action.type = "button";
      action.setAttribute(
        "aria-pressed",
        String(Boolean(product[field === "liked" ? "is_liked" : "is_saved"])),
      );
      action.append(icon(field === "liked" ? "i-heart" : "i-bookmark"));
      const actionLabel = document.createElement("span");
      actionLabel.textContent = label;
      const actionCount = document.createElement("b");
      actionCount.textContent = String(count);
      action.append(actionLabel, actionCount);
      action.setAttribute(
        "aria-label",
        `${label} ${product.name || "product"}; ${count}`,
      );
      action.addEventListener("click", () =>
        toggleProductEngagement(product, field, action),
      );
      engagement.append(action);
    }
    if (product.recommendation_run_id) {
      const feedback = document.createElement("button");
      feedback.type = "button";
      feedback.className = "recommendation-feedback";
      feedback.textContent = "Not relevant";
      feedback.setAttribute("aria-label", `Mark ${product.name || "this recommendation"} as not relevant`);
      feedback.addEventListener("click", async () => {
        feedback.disabled = true;
        try {
          const response = await apiRequest("/api/recommendations/events/", {
            method: "POST",
            body: JSON.stringify({
              query_id: product.recommendation_run_id,
              product_id: Number(product.id),
              kind: "irrelevant",
            }),
          });
          const data = await responseData(response);
          if (!response.ok) throw new Error(flattenErrors(data));
          feedback.textContent = "Feedback received";
          toast("Thanks. We’ll use this to improve recommendations.");
        } catch (error) {
          feedback.disabled = false;
          toast(error.message || "Feedback could not be sent.", true);
        }
      });
      info.append(feedback);
    }
    purchase.append(price, add);
    info.append(name, rating, description, engagement, purchase);
    card.append(visual, info);
    return card;
  }

  async function toggleProductEngagement(product, field, button) {
    if (!isSignedIn()) {
      window.location.href = `/account/?next=${encodeURIComponent(`/products/${product.id}/`)}`;
      return;
    }
    const property = field === "liked" ? "is_liked" : "is_saved";
    const nextValue = !Boolean(product[property]);
    button.disabled = true;
    try {
      const response = await apiRequest(
        `/api/storefront/products/${product.id}/engagement/`,
        {
          method: "PATCH",
          auth: true,
          body: JSON.stringify({ [field]: nextValue }),
        },
      );
      const data = await responseData(response);
      if (!response.ok) throw new Error(flattenErrors(data));
      product[property] = data[field];
      product.like_count = data.likes;
      product.favorite_count = data.saves;
      button.setAttribute("aria-pressed", String(data[field]));
      const count = button.querySelector("b");
      if (count)
        count.textContent = String(field === "liked" ? data.likes : data.saves);
      button.setAttribute(
        "aria-label",
        `${field === "liked" ? "Like" : "Save"} ${product.name || "product"}; ${field === "liked" ? data.likes : data.saves}`,
      );
      toast(
        data[field]
          ? field === "liked"
            ? "Added to your liked products."
            : "Saved to your collection."
          : "Removed from your collection.",
      );
    } catch (error) {
      toast(error.message || "This action could not be saved.", true);
    } finally {
      button.disabled = false;
    }
  }

  function renderProducts(products, target = $("#productGrid")) {
    target.replaceChildren();
    products.forEach((product, index) =>
      target.append(createProductCard(product, index)),
    );
  }

  function showCatalogState(title, description, isError = false) {
    const element = $("#catalogState");
    element.replaceChildren();
    const heading = document.createElement("h3");
    heading.textContent = title;
    const paragraph = document.createElement("p");
    paragraph.textContent = description;
    element.append(heading, paragraph);
    if (isError) {
      const button = document.createElement("button");
      button.className = "button button-outline";
      button.type = "button";
      button.textContent = "Try again";
      button.style.marginTop = "16px";
      button.addEventListener("click", loadCatalog);
      element.append(button);
    }
    element.hidden = false;
  }

  async function loadCatalog() {
    state.catalogController?.abort();
    const controller = new AbortController();
    state.catalogController = controller;
    state.loadingCatalog = true;
    const grid = $("#productGrid");
    const stateBox = $("#catalogState");
    grid.setAttribute("aria-busy", "true");
    grid.replaceChildren(
      ...Array.from({ length: 8 }, () => {
        const skeleton = document.createElement("div");
        skeleton.className = "product-skeleton";
        skeleton.setAttribute("aria-hidden", "true");
        return skeleton;
      }),
    );
    stateBox.hidden = true;
    $("#pagination").hidden = true;
    try {
      const params = new URLSearchParams({
        page: String(state.page),
        ordering: state.ordering,
      });
      if (state.search) params.set("search", state.search);
      if (state.category) params.set("category", state.category);
      if (state.priceMin) params.set("price_min", String(Number(state.priceMin) * tomanPerUsd));
      if (state.priceMax) params.set("price_max", String(Number(state.priceMax) * tomanPerUsd));
      if (state.minRating) params.set("min_rating", state.minRating);
      const headers = { Accept: "application/json" };
      if (sessionStorage.getItem(accessKey))
        headers.Authorization = `Bearer ${sessionStorage.getItem(accessKey)}`;
      const path = `/api/storefront/products/?${params.toString()}`;
      let response = await apiRequest(path, {
        headers,
        auth: Boolean(headers.Authorization),
        signal: controller.signal,
      });
      if (response.status === 401 && headers.Authorization) {
        clearSession(false);
        response = await fetch(path, {
          headers: { Accept: "application/json" },
          credentials: "same-origin",
          signal: controller.signal,
        });
      }
      const data = await responseData(response);
      if (!response.ok) throw new Error(flattenErrors(data));
      state.products = Array.isArray(data.results) ? data.results : [];
      state.count = Number(data.count) || 0;
      state.pages = Math.max(1, Math.ceil(state.count / 12));
      renderProducts(state.products, grid);
      $("#catalogCount").textContent =
        `${new Intl.NumberFormat("en-US").format(state.count)} products available`;
      if (state.products.length === 0) {
        showCatalogState(
          "No products found",
          state.search
            ? "Try another search or clear the search field."
            : "New products will be added soon.",
        );
      }
      if (state.pages > 1) {
        $("#pagination").hidden = false;
        $("#pageLabel").textContent =
          `Page ${new Intl.NumberFormat("en-US").format(state.page)} of ${new Intl.NumberFormat("en-US").format(state.pages)}`;
        $("#previousPage").disabled = state.page <= 1;
        $("#nextPage").disabled = state.page >= state.pages;
      }
    } catch (error) {
      if (error.name === "AbortError") return;
      grid.replaceChildren();
      $("#catalogCount").textContent = "Could not connect to the shop";
      showCatalogState(
        "Products are temporarily unavailable",
        error.message || "Check your connection and try again.",
        true,
      );
    } finally {
      grid.setAttribute("aria-busy", "false");
      if (state.catalogController === controller) state.loadingCatalog = false;
    }
  }

  function scheduleSearchSuggestions(query) {
    window.clearTimeout(state.suggestionTimer);
    state.suggestionController?.abort();
    const panel = $("#headerSearchSuggestions");
    if (query.length < 3) {
      panel.hidden = true;
      panel.replaceChildren();
      return;
    }
    panel.hidden = false;
    const loading = document.createElement("span");
    loading.className = "suggestion-caption";
    loading.textContent = "Finding close matches…";
    panel.replaceChildren(loading);
    state.suggestionTimer = window.setTimeout(async () => {
      const controller = new AbortController();
      state.suggestionController = controller;
      try {
        const params = new URLSearchParams({ search: query, page_size: "4" });
        const response = await fetch(
          `/api/storefront/products/?${params.toString()}`,
          {
            headers: { Accept: "application/json" },
            credentials: "same-origin",
            signal: controller.signal,
          },
        );
        const data = await responseData(response);
        if (!response.ok) throw new Error(flattenErrors(data));
        if (state.search !== query) return;
        panel.replaceChildren();
        const caption = document.createElement("span");
        caption.className = "suggestion-caption";
        caption.textContent = data.results?.length
          ? "PRODUCTS THAT MATCH YOUR SEARCH"
          : "NO CLOSE MATCHES YET";
        panel.append(caption);
        (data.results || []).slice(0, 4).forEach((product) => {
          const link = document.createElement("a");
          link.className = "suggestion-product";
          link.href = `/products/${product.id}/`;
          const copy = document.createElement("span");
          copy.className = "suggestion-product-copy";
          const name = document.createElement("strong");
          name.textContent = product.name;
          const category = document.createElement("small");
          category.textContent = product.category;
          copy.append(name, category);
          const price = document.createElement("span");
          price.className = "suggestion-price";
          price.textContent = formatShopMoney(product.price);
          link.append(copy, price);
          panel.append(link);
        });
        if (data.results?.length) {
          const more = document.createElement("a");
          more.className = "suggestion-more";
          more.href = "#catalog";
          more.textContent = "See all matching products";
          panel.append(more);
        }
      } catch (error) {
        if (error.name !== "AbortError") panel.hidden = true;
      }
    }, 550);
  }

  function applySearch(value, scroll = false) {
    state.search = value.trim();
    state.page = 1;
    $("#searchInput").value = state.search;
    $("#headerSearchInput").value = state.search;
    loadCatalog();
    scheduleSearchSuggestions(state.search);
    if (scroll) {
      window.location.hash = "catalog";
      $("#catalog").scrollIntoView({ behavior: "smooth" });
    }
  }

  function addToCart(product) {
    const item = state.cart.find((entry) => entry.id === Number(product.id));
    if (item) {
      item.quantity = Math.min(20, item.quantity + 1);
      item.name = String(product.name || item.name);
      item.price = String(product.price || item.price);
      item.category = String(product.category || item.category || "other");
      item.image_url = String(product.image_url || item.image_url || "");
      item.recommendation_run_id = product.recommendation_run_id || item.recommendation_run_id || "";
    } else {
      state.cart.push({
        id: Number(product.id),
        name: String(product.name || "Product"),
        price: String(product.price || "0"),
        category: String(product.category || "other"),
        image_url: String(product.image_url || ""),
        recommendation_run_id: product.recommendation_run_id || "",
        quantity: 1,
      });
    }
    saveCart();
    toast("Added to cart.");
    openDrawer();
  }

  function renderCart() {
    const list = $("#cartItems");
    list.replaceChildren();
    const count = state.cart.reduce((sum, item) => sum + item.quantity, 0);
    $("#cartCount").textContent = new Intl.NumberFormat("en-US").format(count);
    $("#cartEmpty").hidden = state.cart.length > 0;
    $("#cartSummary").hidden = state.cart.length === 0;
    let total = 0;
    state.cart.forEach((item) => {
      const art = artOptions[item.category] || artOptions.other;
      const catalogProduct = state.products.find(
        (product) => Number(product.id) === Number(item.id),
      );
      const categoryImage = `/static/storefront/images/products/${art.image || item.category || "other"}.jpg`;
      const imageUrl = item.image_url || catalogProduct?.image_url || categoryImage;
      const price = Number(item.price) || 0;
      total += price * item.quantity;
      const row = document.createElement("article");
      row.className = "cart-item";
      const artwork = document.createElement("span");
      artwork.className = `cart-item-art ${art.color}`;
      const image = document.createElement("img");
      image.className = "cart-item-image";
      image.src = imageUrl;
      image.alt = item.name;
      image.loading = "lazy";
      image.addEventListener("error", () => {
        artwork.replaceChildren(icon(art.icon));
      }, { once: true });
      artwork.append(image);
      const copy = document.createElement("div");
      copy.className = "cart-item-copy";
      const title = document.createElement("strong");
      title.textContent = item.name;
      const line = document.createElement("small");
      line.textContent = formatShopMoney(price * item.quantity);
      const quantity = document.createElement("div");
      quantity.className = "quantity-control";
      const minus = document.createElement("button");
      minus.type = "button";
      minus.setAttribute("aria-label", `Decrease quantity of ${item.name}`);
      minus.append(icon("i-minus"));
      minus.addEventListener("click", () => changeQuantity(item.id, -1));
      const number = document.createElement("span");
      number.textContent = new Intl.NumberFormat("en-US").format(item.quantity);
      const plus = document.createElement("button");
      plus.type = "button";
      plus.setAttribute("aria-label", `Increase quantity of ${item.name}`);
      plus.append(icon("i-plus"));
      plus.addEventListener("click", () => changeQuantity(item.id, 1));
      quantity.append(minus, number, plus);
      copy.append(title, line, quantity);
      const remove = document.createElement("button");
      remove.className = "cart-remove";
      remove.type = "button";
      remove.setAttribute("aria-label", `Remove ${item.name} from cart`);
      remove.append(icon("i-close"));
      remove.addEventListener("click", () => removeFromCart(item.id));
      row.append(artwork, copy, remove);
      list.append(row);
    });
    $("#cartTotal").textContent = formatShopMoney(total);
    $("#checkoutTotal").textContent = formatShopMoney(total);
  }

  function changeQuantity(id, delta) {
    const item = state.cart.find((entry) => entry.id === id);
    if (!item) return;
    item.quantity += delta;
    if (item.quantity < 1)
      state.cart = state.cart.filter((entry) => entry.id !== id);
    if (item.quantity > 20) item.quantity = 20;
    saveCart();
  }

  function removeFromCart(id) {
    state.cart = state.cart.filter((item) => item.id !== id);
    saveCart();
  }

  function openDrawer() {
    $("#backdrop").hidden = false;
    $("#cartDrawer").classList.add("is-open");
    $("#cartDrawer").setAttribute("aria-hidden", "false");
    $("#cartDrawer").inert = false;
    $("#openCart").setAttribute("aria-expanded", "true");
    document.body.style.overflow = "hidden";
  }

  function closeDrawer() {
    $("#cartDrawer").classList.remove("is-open");
    $("#cartDrawer").setAttribute("aria-hidden", "true");
    $("#cartDrawer").inert = true;
    $("#openCart").setAttribute("aria-expanded", "false");
    $("#backdrop").hidden = true;
    document.body.style.overflow = "";
  }

  function openAuth(mode = "login", afterAuth = null) {
    state.afterAuth = afterAuth;
    setAuthMode(mode);
    if (!$("#authDialog").open) $("#authDialog").showModal();
  }

  function setAuthMode(mode) {
    const registering = mode === "register";
    $("#authTitle").textContent = registering
      ? "Create your account"
      : "Sign in";
    $("#authDescription").textContent = registering
      ? "Create an account to chat with the assistant and place orders."
      : "Sign in to chat with the assistant and submit an order.";
    $("#authSubmitText").textContent = registering
      ? "Create account and sign in"
      : "Sign in";
    $("#authForm [name=password]").autocomplete = registering
      ? "new-password"
      : "current-password";
    $$("#authForm .register-only").forEach((field) => {
      field.hidden = !registering;
    });
    $("#authForm [name=email]").required = false;
    $("#authForm [name=phone]").required = registering;
    $$("[data-auth-mode]").forEach((tab) => {
      const selected = tab.dataset.authMode === mode;
      tab.classList.toggle("is-active", selected);
      tab.setAttribute("aria-selected", String(selected));
    });
    $("#authMessage").textContent = "";
    $("#authForm").dataset.mode = mode;
  }

  async function submitAuth(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const message = $("#authMessage");
    const submit = $("#authSubmit");
    const data = new FormData(form);
    const username = String(data.get("username") || "").trim();
    const password = String(data.get("password") || "");
    const registering = form.dataset.mode === "register";
    submit.disabled = true;
    message.textContent = "Checking…";
    try {
      if (registering) {
        const registerResponse = await apiRequest("/api/register/", {
          method: "POST",
          body: JSON.stringify({
            username,
            email: String(data.get("email") || "").trim(),
            phone: String(data.get("phone") || "").trim(),
            password,
          }),
        });
        const registered = await responseData(registerResponse);
        if (!registerResponse.ok) throw new Error(flattenErrors(registered));
      }
      const response = await apiRequest("/api/token/", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });
      const tokens = await responseData(response);
      if (!response.ok || !tokens.access || !tokens.refresh)
        throw new Error(flattenErrors(tokens));
      setSession(tokens, username);
      $("#authDialog").close();
      message.textContent = "";
      const nextUrl = document.body.dataset.nextUrl || "";
      if (nextUrl.startsWith("/") && !nextUrl.startsWith("//")) {
        window.location.assign(nextUrl);
        return;
      }
      toast(
        registering ? "Your account is ready. Welcome!" : "You are signed in.",
      );
      const nextAction = state.afterAuth;
      state.afterAuth = null;
      if (nextAction === "account") await openAccountSection();
      else if (nextAction === "checkout") openCheckout();
      else if (nextAction === "chat") openChat();
      else if (nextAction === "recommend") $("#recommendForm").requestSubmit();
    } catch (error) {
      message.textContent =
        error.message || "Sign-in failed. Please try again.";
    } finally {
      submit.disabled = false;
    }
  }

  function openChat() {
    if (!isSignedIn()) {
      openAuth("login", "chat");
      toast("Sign in first to start a conversation.");
      return;
    }
    $("#chatPanel").classList.add("is-open");
    $("#chatPanel").setAttribute("aria-hidden", "false");
    $("#chatPanel").inert = false;
    $("#chatInput").focus();
  }

  function closeChat() {
    $("#chatPanel").classList.remove("is-open");
    $("#chatPanel").setAttribute("aria-hidden", "true");
    $("#chatPanel").inert = true;
  }

  function addChatBubble(text, role) {
    const bubble = document.createElement("div");
    bubble.className = `chat-bubble ${role === "user" ? "user-bubble" : "assistant-bubble"}`;
    bubble.textContent = text;
    $("#chatMessages").append(bubble);
    $("#chatMessages").scrollTop = $("#chatMessages").scrollHeight;
    return bubble;
  }

  function attachChatProducts(bubble, products, agents = []) {
    if (!Array.isArray(products) || !products.length) return;
    const results = document.createElement("div");
    results.className = "chat-product-results";
    const heading = document.createElement("small");
    heading.className = "chat-product-heading";
    heading.textContent = "Matching products · open a product page";
    results.append(heading);
    products.forEach((product) => {
      const id = Number(product.id);
      if (!Number.isSafeInteger(id) || id < 1) return;
      const link = document.createElement("a");
      link.className = "chat-product-link";
      link.href = `/products/${id}/`;
      const name = document.createElement("strong");
      name.textContent = String(product.name || "View product");
      const detail = document.createElement("small");
      detail.textContent = `${String(product.category || "Hardware")} · ${formatShopMoney(product.price)}`;
      link.append(name, detail);
      results.append(link);
    });
    if (results.querySelector(".chat-product-link")) bubble.append(results);
    if (agents.length) {
      const note = document.createElement("small");
      note.className = "chat-agent-note";
      note.textContent = "Catalog search and product specialist checked these matches.";
      bubble.append(note);
    }
  }

  async function submitChat(event) {
    event.preventDefault();
    if (!isSignedIn()) return openAuth("login");
    const input = $("#chatInput");
    const text = input.value.trim();
    if (!text) return;
    input.value = "";
    addChatBubble(text, "user");
    const pending = addChatBubble("Thinking…", "assistant");
    const send = $("#chatForm button");
    send.disabled = true;
    try {
      const conversationId = sessionStorage.getItem("riva.conversation");
      const response = await apiRequest("/api/chat/", {
        method: "POST",
        auth: true,
        body: JSON.stringify({
          message: text,
          ...(conversationId
            ? { conversation_id: Number(conversationId) }
            : {}),
        }),
      });
      const data = await responseData(response);
      if (!response.ok) throw new Error(flattenErrors(data));
      if (data.conversation_id)
        sessionStorage.setItem(
          "riva.conversation",
          String(data.conversation_id),
        );
      pending.textContent = data.reply || "No reply was returned.";
      attachChatProducts(pending, data.metadata?.products, data.metadata?.agents);
    } catch (error) {
      pending.textContent =
        error.message || "Could not connect to the assistant.";
    } finally {
      send.disabled = false;
      input.focus();
      $("#chatMessages").scrollTop = $("#chatMessages").scrollHeight;
    }
  }

  async function submitRecommendation(event) {
    event.preventDefault();
    const input = $("#recommendInput");
    const message = $("#recommendMessage");
    const query = input.value.trim();
    if (!query) return;
    message.textContent = "Finding products for you…";
    const button = $("#recommendForm button");
    button.disabled = true;
    try {
      const response = await apiRequest("/api/recommendations/", {
        method: "POST",
        body: JSON.stringify({ query }),
      });
      const data = await responseData(response);
      if (!response.ok) throw new Error(flattenErrors(data));
      const results = Array.isArray(data.results) ? data.results : [];
      const container = $("#recommendationResults");
      renderProducts(results, container);
      container.hidden = results.length === 0;
      message.textContent = results.length
        ? `${new Intl.NumberFormat("en-US").format(results.length)} recommendations found.`
        : "No matches. Try a different search.";
      if (results.length)
        container.scrollIntoView({ behavior: "smooth", block: "nearest" });
    } catch (error) {
      message.textContent =
        error.message || "Recommendations could not be loaded.";
    } finally {
      button.disabled = false;
    }
  }

  function openCheckout() {
    if (!state.cart.length) return toast("Your cart is empty.", true);
    if (!isSignedIn()) return openAuth("login", "checkout");
    $("#checkoutDialog").showModal();
  }

  async function submitOrder(event) {
    event.preventDefault();
    if (!isSignedIn()) return openAuth("login");
    const form = event.currentTarget;
    const message = $("#checkoutMessage");
    const submit = $("#checkoutForm button[type=submit]");
    const formData = new FormData(form);
    const items = state.cart.map(({ id, quantity, recommendation_run_id }) => ({
      product_id: id,
      quantity,
      ...(recommendation_run_id ? { recommendation_run_id } : {}),
    }));
    const checkoutKeyName = "riva.checkout.idempotency";
    const checkoutFingerprintName = "riva.checkout.fingerprint";
    const checkoutFingerprint = JSON.stringify({
      full_name: String(formData.get("full_name") || "").trim(),
      phone: String(formData.get("phone") || "").trim(),
      address: String(formData.get("address") || "").trim(),
      items,
    });
    const existingFingerprint = sessionStorage.getItem(checkoutFingerprintName);
    const idempotencyKey = existingFingerprint === checkoutFingerprint
      ? sessionStorage.getItem(checkoutKeyName) || crypto.randomUUID()
      : crypto.randomUUID();
    sessionStorage.setItem(checkoutKeyName, idempotencyKey);
    sessionStorage.setItem(checkoutFingerprintName, checkoutFingerprint);
    submit.disabled = true;
    message.textContent = "Submitting your order…";
    try {
      const response = await apiRequest("/api/storefront/orders/", {
        method: "POST",
        auth: true,
        headers: { "Idempotency-Key": idempotencyKey },
        body: JSON.stringify({
          full_name: String(formData.get("full_name") || "").trim(),
          phone: String(formData.get("phone") || "").trim(),
          address: String(formData.get("address") || "").trim(),
          items,
        }),
      });
      const data = await responseData(response);
      if (response.status === 202) {
        message.textContent = "Your order is saved and checkout is still starting. Please submit again in a moment; your cart and request key are preserved.";
        return;
      }
      if (!response.ok) {
        if (response.status === 409) {
          sessionStorage.removeItem(checkoutKeyName);
          sessionStorage.removeItem(checkoutFingerprintName);
        }
        throw new Error(flattenErrors(data));
      }
      if (!data.checkout_url) throw new Error("Payment setup did not finish. Your cart is unchanged.");
      window.location.assign(data.checkout_url);
    } catch (error) {
      message.textContent =
        error.message || "The order request could not be submitted.";
    } finally {
      submit.disabled = false;
    }
  }

  async function showOrders() {
    if (!isSignedIn()) return openAuth("login", "account");
    $("#ordersDialog").showModal();
    $("#accountSummary").textContent = "Loading your account…";
    try {
     const response = await apiRequest("/api/storefront/account/", {
       auth: true,
     });
     const data = await responseData(response);
     if (!response.ok) throw new Error(flattenErrors(data));
     const profileForm = $("#profileForm");
      Object.entries(data.profile || {}).forEach(([key, value]) => {
        if (profileForm.elements[key])
          profileForm.elements[key].value = value || "";
      });
      $("#accountSummary").textContent =
        `Signed in as ${data.profile.username}. Your account information, wallet, payments, and orders are private to you.`;
      $("#walletBalance").textContent = formatMoney(
        data.wallet.balance,
        "",
      );
      $("#walletCurrency").textContent = data.wallet.currency;
      renderOrderHistory(data.orders || []);
      const returnOrderId = Number(new URLSearchParams(window.location.search).get("order_id"));
      const returnedOrder = data.orders?.find((order) => order.id === returnOrderId);
      if (returnedOrder && returnedOrder.payments?.some((payment) => payment.status === "paid")) {
        state.cart = [];
        saveCart();
        sessionStorage.removeItem("riva.checkout.idempotency");
        sessionStorage.removeItem("riva.checkout.fingerprint");
      }
      renderProductCollection("#likedProducts", data.liked_products || []);
      renderProductCollection("#savedProducts", data.saved_products || []);
      renderSupportTickets(data.support_tickets || []);
      renderAccountRecords("#paymentsList", data.payments || [], (payment) => {
        const provider =
          payment.provider === "crypto"
            ? "Crypto"
            : payment.provider === "wallet"
              ? "Wallet"
              : "Card gateway";
        return `Order ${payment.order_id || "—"} · ${provider} · ${payment.status} · ${formatMoney(payment.amount, payment.currency)}`;
      });
      renderAccountRecords(
        "#walletTransactions",
        data.transactions || [],
        (entry) =>
          `${entry.kind} · ${entry.status} · ${formatMoney(entry.amount, entry.currency)} · ${entry.reference}`,
      );
    } catch (error) {
      $("#accountSummary").textContent =
        error.message || "Your account could not be loaded.";
    }
  }

  async function openAccountSection() {
    await showOrders();
    const section = document.body.dataset.openSection || "profile";
    const tab = $$("[data-account-tab]").find(
      (item) => item.dataset.accountTab === section,
    );
    if (tab) selectAccountTab(tab);
  }

  function renderSupportTickets(tickets) {
    const list = $("#supportTickets");
    list.replaceChildren();
    if (!tickets.length) {
      const empty = document.createElement("p");
      empty.className = "modal-description";
      empty.textContent =
        "No support requests yet. Send a message above and the store team will follow up here.";
      list.append(empty);
      return;
    }
    const labels = {
      open: "Open",
      in_progress: "In progress",
      resolved: "Resolved",
    };
    tickets.forEach((ticket) => {
      const card = document.createElement("article");
      card.className = "support-ticket-card";
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
      const updated = document.createElement("time");
      updated.dateTime = ticket.updated_at;
      updated.textContent = `Updated ${new Date(ticket.updated_at).toLocaleString()}`;
      card.append(updated);
      list.append(card);
    });
  }

  async function submitSupportTicket(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const message = $("#supportTicketMessage");
    const button = form.querySelector('button[type="submit"]');
    button.disabled = true;
    message.textContent = "Sending your request…";
    try {
      const response = await apiRequest("/api/storefront/account/tickets/", {
        method: "POST",
        auth: true,
        body: JSON.stringify({
          subject: form.elements.subject.value.trim(),
          message: form.elements.message.value.trim(),
        }),
      });
      const data = await responseData(response);
      if (!response.ok) throw new Error(flattenErrors(data));
      form.reset();
      message.textContent = `Ticket #${data.id} was sent. You can track it below.`;
      const list = await apiRequest("/api/storefront/account/tickets/", {
        auth: true,
      });
      const tickets = await responseData(list);
      if (list.ok) renderSupportTickets(tickets);
    } catch (error) {
      message.textContent = error.message || "Your request could not be sent.";
    } finally {
      button.disabled = false;
    }
  }

  function renderProductCollection(selector, products) {
    const list = $(selector);
    list.replaceChildren();
    if (!products.length) {
      const empty = document.createElement("p");
      empty.className = "modal-description";
      empty.textContent =
        "Nothing here yet. Like or save products to keep them in this section.";
      list.append(empty);
      return;
    }
    products.forEach((product) => {
      const row = document.createElement("article");
      row.className = "account-record";
      const link = document.createElement("a");
      link.href = `/products/${product.id}/`;
      link.textContent = product.name;
      const price = document.createElement("span");
      price.textContent = formatShopMoney(product.price);
      row.append(link, price);
      list.append(row);
    });
  }

  function renderAccountRecords(selector, records, describe) {
    const list = $(selector);
    list.replaceChildren();
    if (!records.length) {
      const empty = document.createElement("p");
      empty.className = "modal-description";
      empty.textContent = "There are no records yet.";
      list.append(empty);
      return;
    }
    records.forEach((record) => {
      const row = document.createElement("article");
      row.className = "account-record";
      const detail = document.createElement("span");
      detail.textContent = describe(record);
      const date = document.createElement("time");
      date.dateTime = record.created_at;
      date.textContent = new Date(record.created_at).toLocaleString("en-US");
      row.append(detail, date);
      if (record.checkout_url && record.status !== "paid") {
        const link = document.createElement("a");
        link.href = record.checkout_url;
        link.rel = "noopener noreferrer";
        link.textContent = "Continue payment";
        row.append(link);
      }
      list.append(row);
    });
  }

  function renderOrderHistory(orders) {
    const list = $("#ordersList");
    list.replaceChildren();
    if (!orders.length) {
      const empty = document.createElement("p");
      empty.className = "modal-description";
      empty.textContent = "You have not placed any orders yet.";
      list.append(empty);
      return;
    }
    const steps = ["pending", "confirmed", "preparing", "shipped", "delivered"];
    orders.forEach((order) => {
      const card = document.createElement("article");
      card.className = "order-card";
      const head = document.createElement("div");
      head.className = "order-card-head";
      const title = document.createElement("strong");
      title.textContent = `Order ${new Intl.NumberFormat("en-US").format(order.id)}`;
      const status = document.createElement("span");
      status.className = "order-status";
      status.textContent = orderStatus[order.status] || order.status;
      head.append(title, status);
      card.append(head);
      const progress = document.createElement("ol");
      progress.className = `order-progress${order.status === "cancelled" ? " is-cancelled" : ""}`;
      const current = steps.indexOf(order.status);
      steps.forEach((step, index) => {
        const node = document.createElement("li");
        node.className =
          index <= current && order.status !== "cancelled" ? "is-complete" : "";
        node.textContent = orderStatus[step];
        progress.append(node);
      });
      card.append(progress);
      (order.items || []).forEach((item) => {
        const product = document.createElement("p");
        product.className = "order-product-line";
        product.textContent = `${item.product_name} × ${item.quantity} · ${new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 }).format(Number(item.line_total) / (Number(order.fx_rate_toman_per_usd) || tomanPerUsd))} · ${orderStatus[item.order_status] || item.order_status}`;
        card.append(product);
      });
      const total = document.createElement("p");
      total.className = "order-total";
      total.textContent = `Total ${order.quoted_total_usd ? new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 }).format(Number(order.quoted_total_usd)) : formatShopMoney(order.total_amount)} · ${order.payments?.length || 0} payment records`;
      card.append(total);
      list.append(card);
    });
  }

  async function submitProfile(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const message = $("#profileMessage");
    const button = form.querySelector('button[type="submit"]');
    button.disabled = true;
    message.textContent = "Saving your profile…";
    try {
      const response = await apiRequest("/api/storefront/account/profile/", {
        method: "PATCH",
        auth: true,
        body: JSON.stringify({
          display_name: form.elements.display_name.value.trim(),
          phone: form.elements.phone.value.trim(),
          address: form.elements.address.value.trim(),
        }),
      });
      const data = await responseData(response);
      if (!response.ok) throw new Error(flattenErrors(data));
      message.textContent = "Your profile has been saved.";
    } catch (error) {
      message.textContent = error.message || "Your profile could not be saved.";
    } finally {
      button.disabled = false;
    }
  }

  function selectAccountTab(button) {
    $$("[data-account-tab]").forEach((tab) => {
      const active = tab === button;
      tab.classList.toggle("is-active", active);
      tab.setAttribute("aria-selected", String(active));
    });
    $$("[data-account-pane]").forEach((pane) => {
      pane.hidden = pane.dataset.accountPane !== button.dataset.accountTab;
    });
  }

  function bindEvents() {
    $("#searchInput").value = state.search;
    $("#headerSearchInput").value = state.search;
    $$("button[data-category]").forEach((button) => {
      const active = button.dataset.category === state.category;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-pressed", String(active));
    });
    $$('[data-department]').forEach((link) => link.addEventListener("click", () => {
      state.category = link.dataset.department || "";
      state.page = 1;
      $$('button[data-category]').forEach((button) => {
        const active = button.dataset.category === state.category;
        button.classList.toggle("is-active", active);
        button.setAttribute("aria-pressed", String(active));
      });
      loadCatalog();
    }));
    $$(["button[data-category]"]).forEach((button) =>
      button.addEventListener("click", () => {
        state.category = button.dataset.category;
        state.page = 1;
        $$(["button[data-category]"]).forEach((item) => {
          const active = item === button;
          item.classList.toggle("is-active", active);
          item.setAttribute("aria-pressed", String(active));
        });
        loadCatalog();
      }),
    );
    $("#searchForm").addEventListener("submit", (event) => {
      event.preventDefault();
      applySearch($("#searchInput").value, true);
    });
    let searchTimer;
    $("#searchInput").addEventListener("input", () => {
      window.clearTimeout(searchTimer);
      searchTimer = window.setTimeout(() => {
        applySearch($("#searchInput").value);
      }, 380);
    });
    $("#headerSearchInput").addEventListener("input", () => {
      window.clearTimeout(searchTimer);
      searchTimer = window.setTimeout(
        () => applySearch($("#headerSearchInput").value),
        380,
      );
    });
    $("#headerSearch").addEventListener("submit", (event) => {
      event.preventDefault();
      applySearch($("#headerSearchInput").value, true);
    });
    if (state.search.length >= 3) scheduleSearchSuggestions(state.search);
    $("#sortSelect").addEventListener("change", (event) => {
      state.ordering = event.target.value;
      state.page = 1;
      loadCatalog();
    });
    $("#previousPage").addEventListener("click", () => {
      state.page = Math.max(1, state.page - 1);
      loadCatalog();
    });
    $("#nextPage").addEventListener("click", () => {
      state.page = Math.min(state.pages, state.page + 1);
      loadCatalog();
    });
    $$("[data-close-drawer]").forEach((button) =>
      button.addEventListener("click", closeDrawer),
    );
    // Keep the header link as a no-JavaScript fallback, but open the drawer
    // immediately on normal clicks instead of navigating away to /cart/.
    $("#openCart").addEventListener("click", (event) => {
      event.preventDefault();
      openDrawer();
    });
    $$("[data-close-auth]").forEach((button) =>
      button.addEventListener("click", () => $("#authDialog").close()),
    );
    $("#accountButton").addEventListener("click", () => {
      if (isSignedIn()) openAccountSection();
      else openAuth("login", "account");
    });
    $("#backdrop").addEventListener("click", closeDrawer);
    $$("[data-open-chat]").forEach((button) =>
      button.addEventListener("click", openChat),
    );
    $("#closeChat").addEventListener("click", closeChat);
    $("#profileForm").addEventListener("submit", submitProfile);
    $("#signOutButton").addEventListener("click", () => {
      clearSession();
      $("#ordersDialog").close();
    });
    $("#catalogFilters").addEventListener("submit", (event) => {
      event.preventDefault();
      state.priceMin = $("#priceMin").value.trim();
      state.priceMax = $("#priceMax").value.trim();
      state.minRating = $("#minRating").checked ? "4" : "";
      state.page = 1;
      loadCatalog();
    });
    $("#clearFilters").addEventListener("click", () => {
      $("#catalogFilters").reset();
      state.priceMin = "";
      state.priceMax = "";
      state.minRating = "";
      state.page = 1;
      loadCatalog();
    });
    $("#supportTicketForm").addEventListener("submit", submitSupportTicket);
    $$("[data-account-tab]").forEach((button) =>
      button.addEventListener("click", () => selectAccountTab(button)),
    );
    $("#checkoutButton").addEventListener("click", openCheckout);
    $("#authForm").addEventListener("submit", submitAuth);
    $("#toggleAuthPassword").addEventListener("click", (event) => {
      const button = event.currentTarget;
      const input = $("#authPassword");
      const visible = input.type === "password";
      input.type = visible ? "text" : "password";
      button.textContent = visible ? "Hide" : "Show";
      button.setAttribute("aria-pressed", String(visible));
    });
    $("#checkoutForm").addEventListener("submit", submitOrder);
    $("#chatForm").addEventListener("submit", submitChat);
    $("#recommendForm").addEventListener("submit", submitRecommendation);
    $$("[data-auth-mode]").forEach((button) =>
      button.addEventListener("click", () =>
        setAuthMode(button.dataset.authMode),
      ),
    );
    $$("[data-close-dialog]").forEach((button) =>
      button.addEventListener("click", () => button.closest("dialog").close()),
    );
    $("#ordersDialog").addEventListener("click", (event) => {
      if (event.target === event.currentTarget) event.currentTarget.close();
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closeDrawer();
        closeChat();
        $("#headerSearchSuggestions").hidden = true;
      }
    });
    document.addEventListener("click", (event) => {
      if (!$("#headerSearch").contains(event.target))
        $("#headerSearchSuggestions").hidden = true;
    });
  }

  document.documentElement.classList.add("motion-ready");
  if ("IntersectionObserver" in window) {
    const revealObserver = new IntersectionObserver(
      (entries, observer) =>
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            observer.unobserve(entry.target);
          }
        }),
      { threshold: 0.12 },
    );
    $$(".reveal").forEach((element) => revealObserver.observe(element));
  } else {
    $$(".reveal").forEach((element) => element.classList.add("is-visible"));
  }

  updateAccountButton();
  $("#priceMin").value = state.priceMin;
  $("#priceMax").value = state.priceMax;
  $("#minRating").checked = state.minRating === "4";
  bindEvents();
  renderCart();
  loadCatalog();
  if (document.body.dataset.openAccount === "true") {
    if (isSignedIn()) openAccountSection();
    else openAuth("login", "account");
  }
  if (document.body.dataset.openCart === "true") openDrawer();
};

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", startApp, { once: true });
} else {
  startApp();
}
