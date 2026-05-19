(function () {
  const initial = window.__INITIAL_DATA__ || {};

  const state = {
    vendors: [...(initial.vendors || [])],
    selectedVendors: new Set(initial.selected_vendors || []),
    cities: [...(initial.cities || [])],
    selectedCities: new Set(initial.selected_cities || []),
    mandatoryCards: [...(initial.mandatory_cards || [])],
    optionalCards: [...(initial.optional_cards || [])],
    tagLibrary: [...(initial.tag_library || [])],
    tagConstraints: [...(initial.tag_constraints || [])],
    composerTags: new Set(),
    tagColorLookup: new Map(),
    cardNameSuggestionsList: [],
    cardNameSuggestionIndex: -1,
    cardNameSuggestionsDebounce: null,
  };

  const els = {
    vendorPenalty: document.getElementById("vendorPenalty"),
    minOptionalCards: document.getElementById("minOptionalCards"),
    cityChips: document.getElementById("cityChips"),
    storeGrid: document.getElementById("storeGrid"),
    selectAllStores: document.getElementById("selectAllStores"),
    clearAllStores: document.getElementById("clearAllStores"),
    cardNameInput: document.getElementById("cardNameInput"),
    addCardMandatory: document.getElementById("addCardMandatory"),
    addCardOptional: document.getElementById("addCardOptional"),
    bulkFileInput: document.getElementById("bulkFileInput"),
    bulkInputBtn: document.getElementById("bulkInputBtn"),
    tagPalette: document.getElementById("tagPalette"),
    newTagInput: document.getElementById("newTagInput"),
    addTagBtn: document.getElementById("addTagBtn"),
    mandatoryList: document.getElementById("mandatoryList"),
    optionalList: document.getElementById("optionalList"),
    clearAllCards: document.getElementById("clearAllCards"),
    mandatoryCount: document.getElementById("mandatoryCount"),
    optionalCount: document.getElementById("optionalCount"),
    constraintRows: document.getElementById("constraintRows"),
    addConstraintBtn: document.getElementById("addConstraintBtn"),
    allTags: document.getElementById("allTags"),
    runBtn: document.getElementById("runBtn"),
    runStatus: document.getElementById("runStatus"),
    scrapeProgressWrap: document.getElementById("scrapeProgressWrap"),
    scrapeProgressLabel: document.getElementById("scrapeProgressLabel"),
    scrapeProgressCount: document.getElementById("scrapeProgressCount"),
    scrapeProgressFill: document.getElementById("scrapeProgressFill"),
    scrapeProgressBar: document.querySelector(".scrape-progress-bar"),
    scrapeLogToggle: document.getElementById("scrapeLogToggle"),
    scrapeLogBody: document.getElementById("scrapeLogBody"),
    scrapeLogRows: document.getElementById("scrapeLogRows"),
    scrapeLogCount: document.getElementById("scrapeLogCount"),
    scrapeLogClear: document.getElementById("scrapeLogClear"),
    resultPanel: document.getElementById("resultPanel"),
    resultBody: document.getElementById("resultBody"),
    cardNameSuggestions: document.getElementById("cardNameSuggestions"),
    cardBuilderError: document.getElementById("cardBuilderError"),
  };

  function cleanTag(tag) {
    return String(tag || "").trim().toLowerCase();
  }

  function cleanName(name) {
    return String(name || "").trim();
  }

  const uiHelpers = window.CardUiHelpers || {};
  const TAG_COLOR_PALETTE =
    Array.isArray(uiHelpers.tagColorPalette) && uiHelpers.tagColorPalette.length
      ? uiHelpers.tagColorPalette
      : [{ bg: "#f8fafc", border: "#d5dde8", ink: "#506073", activeBg: "#f1f5f9", activeBorder: "#c3cedd", activeInk: "#455567" }];
  const formatCityLabel =
    typeof uiHelpers.formatCityLabel === "function"
      ? uiHelpers.formatCityLabel
      : (city) => String(city || "");
  const formatStoreLabel =
    typeof uiHelpers.formatStoreLabel === "function"
      ? uiHelpers.formatStoreLabel
      : (store) => String(store || "");

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  /** Create an element with optional class, textContent, type, dataset. */
  function el(tag, className, options = {}) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (options.textContent != null) node.textContent = options.textContent;
    if (options.type) node.setAttribute("type", options.type);
    if (options.dataset) {
      Object.entries(options.dataset).forEach(([k, v]) => {
        node.dataset[k] = v;
      });
    }
    return node;
  }

  /** Create a toggle chip button (e.g. city or tag). */
  function chipButton(label, isActive, onClick) {
    const btn = el("button", "chip", { type: "button", textContent: label });
    if (isActive) btn.classList.add("active");
    btn.addEventListener("click", onClick);
    return btn;
  }

  function hashString(text) {
    let hash = 0;
    for (let i = 0; i < text.length; i++) {
      hash = (hash << 5) - hash + text.charCodeAt(i);
      hash |= 0;
    }
    return Math.abs(hash);
  }

  function refreshTagColorLookup() {
    const lookup = new Map();
    state.tagLibrary.forEach((tag, index) => {
      lookup.set(tag, index % TAG_COLOR_PALETTE.length);
    });
    state.tagColorLookup = lookup;
  }

  function getTagPalette(tag) {
    const key = cleanTag(tag);
    if (!key) return TAG_COLOR_PALETTE[0];
    let paletteIndex = state.tagColorLookup.get(key);
    if (paletteIndex == null) {
      paletteIndex = hashString(key) % TAG_COLOR_PALETTE.length;
    }
    return TAG_COLOR_PALETTE[paletteIndex];
  }

  function applyTagColors(node, tag) {
    const palette = getTagPalette(tag);
    node.style.setProperty("--tag-bg", palette.bg);
    node.style.setProperty("--tag-border", palette.border);
    node.style.setProperty("--tag-ink", palette.ink);
    node.style.setProperty("--tag-active-bg", palette.activeBg);
    node.style.setProperty("--tag-active-border", palette.activeBorder);
    node.style.setProperty("--tag-active-ink", palette.activeInk);
  }

  function syncTagLibrary() {
    const tags = [];
    const seen = new Set();
    const addTag = (rawTag) => {
      const cleaned = cleanTag(rawTag);
      if (!cleaned || seen.has(cleaned)) return;
      seen.add(cleaned);
      tags.push(cleaned);
    };

    state.tagLibrary.forEach(addTag);
    [...state.mandatoryCards, ...state.optionalCards].forEach((card) => {
      (card.tags || []).forEach(addTag);
    });
    (state.tagConstraints || []).forEach((row) => {
      addTag(row.tag);
    });
    state.tagLibrary = tags;
    refreshTagColorLookup();
  }

  function addTagToLibrary(tag) {
    const cleaned = cleanTag(tag);
    if (!cleaned) {
      return;
    }
    if (!state.tagLibrary.includes(cleaned)) {
      state.tagLibrary.push(cleaned);
      refreshTagColorLookup();
    }
  }

  function addComposerTagFromInput() {
    const tag = cleanTag(els.newTagInput.value);
    if (!tag) {
      return;
    }
    addTagToLibrary(tag);
    state.composerTags.add(tag);
    els.newTagInput.value = "";
    renderTagPalette();
    renderTagDataList();
  }

  function setElStatus(element, message, type, baseClass, onlyAddTypeWhenMessage = false) {
    if (!element) return;
    element.textContent = message || "";
    element.className = baseClass;
    if (type && (!onlyAddTypeWhenMessage || message)) {
      element.classList.add(type);
    }
  }

  function setStatus(message, type) {
    setElStatus(els.runStatus, message, type, "status");
  }

  function setCardBuilderError(message, type) {
    setElStatus(els.cardBuilderError, message, type, "card-builder-error", true);
  }

  function renderCities() {
    els.cityChips.innerHTML = "";
    state.cities.forEach((city) => {
      const btn = chipButton(formatCityLabel(city), state.selectedCities.has(city), () => {
        if (state.selectedCities.has(city)) {
          state.selectedCities.delete(city);
        } else {
          state.selectedCities.add(city);
        }
        renderCities();
      });
      els.cityChips.appendChild(btn);
    });
  }

  function renderStores() {
    els.storeGrid.innerHTML = "";
    state.vendors.forEach((vendor) => {
      const item = document.createElement("div");
      item.className = "store-item";

      const input = document.createElement("input");
      input.type = "checkbox";
      input.id = `store-${vendor}`;
      input.checked = state.selectedVendors.has(vendor);
      input.addEventListener("change", () => {
        if (input.checked) {
          state.selectedVendors.add(vendor);
        } else {
          state.selectedVendors.delete(vendor);
        }
      });

      const label = document.createElement("label");
      label.setAttribute("for", input.id);
      label.textContent = formatStoreLabel(vendor);

      item.appendChild(input);
      item.appendChild(label);
      els.storeGrid.appendChild(item);
    });
  }

  function renderTagPalette() {
    els.tagPalette.innerHTML = "";
    if (!state.tagLibrary.length) {
      els.tagPalette.appendChild(el("p", "hint", { textContent: "No tags yet. Add one to start." }));
      return;
    }
    state.tagLibrary.forEach((tag) => {
      const btn = chipButton(`#${tag}`, state.composerTags.has(tag), () => {
        if (state.composerTags.has(tag)) {
          state.composerTags.delete(tag);
        } else {
          state.composerTags.add(tag);
        }
        renderTagPalette();
      });
      btn.classList.add("tag-chip");
      applyTagColors(btn, tag);
      els.tagPalette.appendChild(btn);
    });
  }

  function moveCardBetweenLists(fromKind, fromIndex, toKind) {
    const fromList = fromKind === "mandatory" ? state.mandatoryCards : state.optionalCards;
    const toList = toKind === "mandatory" ? state.mandatoryCards : state.optionalCards;
    if (fromKind === toKind || fromIndex < 0 || fromIndex >= fromList.length) {
      return;
    }
    const [card] = fromList.splice(fromIndex, 1);
    toList.push(card);
    renderCards();
  }

  function findFirstIndexByName(list, name) {
    const key = String(name || "").trim().toLowerCase();
    return list.findIndex((c) => String(c.name || "").trim().toLowerCase() === key);
  }

  /** Group list by card name (case-insensitive); each group has { name, count, tags }. */
  function groupCardsByName(list) {
    const byName = new Map();
    list.forEach((card) => {
      const n = String(card.name || "").trim();
      const key = n.toLowerCase();
      if (!byName.has(key)) {
        byName.set(key, { name: n, count: 0, tags: new Set() });
      }
      const g = byName.get(key);
      g.count += 1;
      (card.tags || []).forEach((t) => g.tags.add(t));
    });
    return [...byName.values()];
  }

  /** Set how many copies of a card are in the list (add or remove entries). */
  function setCardCount(list, cardName, newCount) {
    const key = String(cardName || "").trim().toLowerCase();
    const indices = [];
    list.forEach((card, i) => {
      if (String(card.name || "").trim().toLowerCase() === key) indices.push(i);
    });
    const current = indices.length;
    if (newCount === current) return;
    if (newCount < 1) return;
    if (newCount > current) {
      const template = list[indices[0]];
      for (let i = current; i < newCount; i++) {
        list.push({ name: template.name, tags: [...(template.tags || [])] });
      }
    } else {
      for (let i = 0; i < current - newCount; i++) {
        list.splice(indices[current - 1 - i], 1);
      }
    }
  }

  function removeTagFromCard(list, cardName, tagToRemove) {
    const cardKey = String(cardName || "").trim().toLowerCase();
    const removeKey = cleanTag(tagToRemove);
    if (!cardKey || !removeKey) return;

    list.forEach((card) => {
      const currentKey = String(card.name || "").trim().toLowerCase();
      if (currentKey !== cardKey) return;
      card.tags = (card.tags || []).filter((tag) => cleanTag(tag) !== removeKey);
    });
  }

  function renderCardList(kind) {
    const list = kind === "mandatory" ? state.mandatoryCards : state.optionalCards;
    const container = kind === "mandatory" ? els.mandatoryList : els.optionalList;
    container.innerHTML = "";

    if (!list.length) {
      const empty = document.createElement("p");
      empty.className = "hint";
      empty.textContent = "No cards added.";
      empty.dataset.dropZone = "true";
      container.appendChild(empty);
      return;
    }

    const groups = groupCardsByName(list);
    groups.forEach((group) => {
      const cardItem = document.createElement("div");
      cardItem.className = "card-item";
      cardItem.draggable = true;
      cardItem.dataset.kind = kind;
      cardItem.dataset.cardName = group.name;

      const top = document.createElement("div");
      top.className = "card-top";

      const name = document.createElement("div");
      name.className = "card-name";
      name.textContent = group.name;

      const actions = document.createElement("div");
      actions.className = "card-actions";

      const countWrap = document.createElement("div");
      countWrap.className = "card-count-wrap";
      const btnMinus = document.createElement("button");
      btnMinus.type = "button";
      btnMinus.className = "card-count-btn";
      btnMinus.textContent = "−";
      btnMinus.setAttribute("aria-label", "Decrease quantity");
      const countInput = document.createElement("input");
      countInput.type = "number";
      countInput.min = 1;
      countInput.step = 1;
      countInput.value = group.count;
      countInput.className = "card-count-input";
      countInput.setAttribute("aria-label", `Quantity for ${group.name}`);
      const btnPlus = document.createElement("button");
      btnPlus.type = "button";
      btnPlus.className = "card-count-btn";
      btnPlus.textContent = "+";
      btnPlus.setAttribute("aria-label", "Increase quantity");

      function applyCount(n) {
        const val = Number.isFinite(n) && n >= 1 ? n : 1;
        countInput.value = val;
        setCardCount(list, group.name, val);
        renderCards();
      }
      btnMinus.addEventListener("click", (e) => {
        e.stopPropagation();
        applyCount(group.count - 1);
      });
      btnPlus.addEventListener("click", (e) => {
        e.stopPropagation();
        applyCount(group.count + 1);
      });
      countInput.addEventListener("change", () => {
        const raw = parseInt(countInput.value, 10);
        applyCount(raw);
      });
      countWrap.addEventListener("click", (e) => e.stopPropagation());
      countWrap.appendChild(btnMinus);
      countWrap.appendChild(countInput);
      countWrap.appendChild(btnPlus);

      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "remove-btn";
      remove.textContent = "×";
      remove.setAttribute("aria-label", `Remove ${group.name}`);
      remove.title = "Remove";
      remove.addEventListener("click", (e) => {
        e.stopPropagation();
        const idx = findFirstIndexByName(list, group.name);
        if (idx !== -1) list.splice(idx, 1);
        renderCards();
      });

      actions.appendChild(countWrap);
      actions.appendChild(remove);
      top.appendChild(name);
      top.appendChild(actions);
      cardItem.appendChild(top);

      const tagList = [...group.tags].filter(Boolean);
      if (tagList.length) {
        const tagRow = document.createElement("div");
        tagRow.className = "tag-row";
        tagList.forEach((tag) => {
          const tagEl = document.createElement("span");
          tagEl.className = "mini-tag tag-token";
          tagEl.textContent = `#${tag}`;
          applyTagColors(tagEl, tag);
          tagEl.title = "Click to remove tag from this card";
          tagEl.addEventListener("click", (e) => {
            e.stopPropagation();
            removeTagFromCard(list, group.name, tag);
            renderCards();
          });
          tagRow.appendChild(tagEl);
        });
        cardItem.appendChild(tagRow);
      }

      cardItem.addEventListener("click", (e) => {
        if (e.target.closest(".remove-btn") || e.target.closest(".card-count-wrap")) return;
        const otherKind = kind === "mandatory" ? "optional" : "mandatory";
        const idx = findFirstIndexByName(list, group.name);
        if (idx !== -1) moveCardBetweenLists(kind, idx, otherKind);
      });

      cardItem.addEventListener("dragstart", (e) => {
        if (e.target.closest(".card-count-wrap")) return;
        const idx = findFirstIndexByName(list, group.name);
        if (idx === -1) return;
        e.dataTransfer.effectAllowed = "move";
        e.dataTransfer.setData("application/json", JSON.stringify({ kind, index: idx }));
        e.dataTransfer.setData("text/plain", `${kind}:${idx}`);
        cardItem.classList.add("dragging");
      });

      cardItem.addEventListener("dragend", () => {
        cardItem.classList.remove("dragging");
        document.querySelectorAll(".card-list.drag-over").forEach((el) => el.classList.remove("drag-over"));
      });

      container.appendChild(cardItem);
    });
  }

  function setupListDropZone(container, kind) {
    container.addEventListener("dragover", (e) => {
      e.preventDefault();
      e.dataTransfer.dropEffect = "move";
      container.classList.add("drag-over");
    });
    container.addEventListener("dragleave", (e) => {
      if (!container.contains(e.relatedTarget)) {
        container.classList.remove("drag-over");
      }
    });
    container.addEventListener("drop", (e) => {
      e.preventDefault();
      container.classList.remove("drag-over");
      try {
        const data = JSON.parse(e.dataTransfer.getData("application/json"));
        if (data.kind === kind) return;
        moveCardBetweenLists(data.kind, data.index, kind);
      } catch (_) {
        const text = e.dataTransfer.getData("text/plain");
        const [fromKind, fromIndex] = text.split(":");
        const idx = parseInt(fromIndex, 10);
        if (fromKind && !isNaN(idx) && fromKind !== kind) {
          moveCardBetweenLists(fromKind, idx, kind);
        }
      }
    });
  }

  function renderCards() {
    renderCardList("mandatory");
    renderCardList("optional");
    els.mandatoryCount.textContent = String(state.mandatoryCards.length);
    els.optionalCount.textContent = String(state.optionalCards.length);
    syncTagLibrary();
    renderTagPalette();
    renderTagDataList();
    renderConstraints();
  }

  function renderTagDataList() {
    els.allTags.innerHTML = "";
    state.tagLibrary.forEach((tag) => {
      const opt = document.createElement("option");
      opt.value = tag;
      els.allTags.appendChild(opt);
    });
  }

  function renderConstraints() {
    els.constraintRows.innerHTML = "";
    if (!state.tagConstraints.length) {
      const empty = document.createElement("p");
      empty.className = "hint";
      empty.textContent = "No constraints configured.";
      els.constraintRows.appendChild(empty);
      return;
    }

    state.tagConstraints.forEach((row, index) => {
      const line = document.createElement("div");
      line.className = "constraint-row";

      const tagSelect = document.createElement("select");
      tagSelect.className = "tag-select";
      const currentTag = row.tag || "";
      state.tagLibrary.forEach((tag) => {
        const opt = document.createElement("option");
        opt.value = tag;
        opt.textContent = tag;
        if (tag === currentTag) opt.selected = true;
        tagSelect.appendChild(opt);
      });
      if (!state.tagLibrary.includes(currentTag) && currentTag) {
        const opt = document.createElement("option");
        opt.value = currentTag;
        opt.textContent = currentTag;
        opt.selected = true;
        tagSelect.appendChild(opt);
      }
      tagSelect.addEventListener("change", () => {
        state.tagConstraints[index].tag = cleanTag(tagSelect.value);
      });

      const minInput = document.createElement("input");
      minInput.type = "number";
      minInput.min = "0";
      minInput.step = "1";
      minInput.placeholder = "min";
      minInput.value = row.minimum ?? "";
      minInput.addEventListener("input", () => {
        state.tagConstraints[index].minimum = minInput.value;
      });

      const maxInput = document.createElement("input");
      maxInput.type = "number";
      maxInput.min = "0";
      maxInput.step = "1";
      maxInput.placeholder = "max";
      maxInput.value = row.maximum ?? "";
      maxInput.addEventListener("input", () => {
        state.tagConstraints[index].maximum = maxInput.value;
      });

      const targetInput = document.createElement("input");
      targetInput.type = "number";
      targetInput.min = "0";
      targetInput.step = "1";
      targetInput.placeholder = "target";
      targetInput.value = row.target ?? "";
      targetInput.addEventListener("input", () => {
        state.tagConstraints[index].target = targetInput.value;
      });

      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "remove-btn";
      remove.textContent = "X";
      remove.addEventListener("click", () => {
        state.tagConstraints.splice(index, 1);
        renderConstraints();
      });

      line.appendChild(tagSelect);
      line.appendChild(minInput);
      line.appendChild(maxInput);
      line.appendChild(targetInput);
      line.appendChild(remove);

      els.constraintRows.appendChild(line);
    });
  }

  function buildPayload() {
    return {
      vendor_penalty: Number(els.vendorPenalty.value || 0),
      min_optional_cards: Number(els.minOptionalCards.value || 0),
      use_saved_prices: false,
      pickup_cities: [...state.selectedCities],
      vendors: [...state.selectedVendors],
      mandatory_cards: state.mandatoryCards.map((card) => ({
        name: cleanName(card.name),
        tags: [...new Set((card.tags || []).map(cleanTag).filter(Boolean))],
      })),
      optional_cards: state.optionalCards.map((card) => ({
        name: cleanName(card.name),
        tags: [...new Set((card.tags || []).map(cleanTag).filter(Boolean))],
      })),
      tag_constraints: state.tagConstraints.map((row) => ({
        tag: cleanTag(row.tag),
        minimum: row.minimum,
        maximum: row.maximum,
        target: row.target,
      })),
    };
  }

  function renderResults(summary) {
    const usedVendors = (summary.vendor_summaries || []).filter(
      (v) => v.cards && v.cards.length > 0
    );
    const vendorsHtml = usedVendors
      .map((vendorSummary) => {
        const cardsHtml = vendorSummary.cards
          .map((card) => {
            const label = card.optional ? " [optional]" : "";
            const quantity = Number(card.quantity || 0);
            const quantityLabel = quantity > 1 ? ` x${quantity}` : "";
            return (
              `<li>${escapeHtml(card.name)}${quantityLabel} - ` +
              `$${card.price.toFixed(2)} each (Total: $${card.line_total.toFixed(2)})${label}</li>`
            );
          })
          .join("");

        return `
          <article class="vendor-result">
            <div class="vendor-head">
              <strong>${escapeHtml(formatStoreLabel(vendorSummary.vendor))}</strong>
              <span>Subtotal: $${vendorSummary.subtotal.toFixed(2)} (Shipping: $${vendorSummary.shipping.toFixed(2)})</span>
            </div>
            <div class="vendor-cards">
              <ul>${cardsHtml}</ul>
            </div>
          </article>
        `;
      })
      .join("");

    const optionalNotPurchased = summary.optional_not_purchased.length
      ? `
          <div class="warning-box">
            <strong>Optional cards not purchased</strong>
            <div>${summary.optional_not_purchased.map(escapeHtml).join(", ")}</div>
          </div>
        `
      : "";

    const unavailableCards = summary.unavailable_cards.length
      ? `
          <div class="warning-box">
            <strong>Unavailable cards</strong>
            <div>${summary.unavailable_cards.map(escapeHtml).join(", ")}</div>
          </div>
        `
      : "";

    els.resultBody.innerHTML = `
      <div class="results-summary">
        <div class="metric">
          <div class="label">Total Cost</div>
          <div class="value">$${summary.total_cost.toFixed(2)}</div>
        </div>
        <div class="metric">
          <div class="label">Card Cost</div>
          <div class="value">$${summary.card_cost.toFixed(2)}</div>
        </div>
        <div class="metric">
          <div class="label">Shipping Cost</div>
          <div class="value">$${summary.shipping_cost.toFixed(2)}</div>
        </div>
        <div class="metric">
          <div class="label">Mandatory Purchased</div>
          <div class="value">${summary.mandatory_count}</div>
        </div>
        <div class="metric">
          <div class="label">Optional Purchased</div>
          <div class="value">${summary.optional_count}</div>
        </div>
      </div>
      ${vendorsHtml}
      <p class="hint">Saved to ${escapeHtml(summary.results_file)}</p>
      ${optionalNotPurchased}
      ${unavailableCards}
    `;
    els.resultPanel.classList.remove("hidden");
  }

  /**
   * Parse bulk list text: "4 Card Name" or "4 Card Name [Tag 2]".
   * Empty lines separate sections: first = mandatory, second = optional (e.g. mainboard / sideboard).
   */
  function parseBulkList(text) {
    const blocks = String(text || "")
      .split(/\n\n+/)
      .map((block) =>
        block
          .split(/\n/)
          .map((l) => l.trim())
          .filter(Boolean)
      )
      .filter((lines) => lines.length > 0);

    const mandatory = [];
    const optional = [];
    blocks.forEach((lines, blockIndex) => {
      const target = blockIndex === 0 ? mandatory : optional;
      lines.forEach((line) => {
        const countMatch = line.match(/^(\d+)\s+(.+)$/);
        const count = countMatch ? Math.max(1, parseInt(countMatch[1], 10)) : 1;
        let rest = countMatch ? countMatch[2].trim() : line.trim();
        const tagMatch = rest.match(/\s+\[Tag\s*(\d+)[\]\}]\s*$/i);
        const tag = tagMatch ? tagMatch[1] : null;
        if (tag) {
          rest = rest.replace(/\s+\[Tag\s*\d+[\]\}]\s*$/i, "").trim();
        }
        const name = rest;
        if (!name) return;
        const tags = tag ? [tag] : [];
        for (let i = 0; i < count; i++) {
          target.push({ name, tags: [...tags] });
        }
      });
    });
    return { mandatory, optional };
  }

  async function addCard(target) {
    const name = cleanName(els.cardNameInput.value);
    if (!name) {
      setCardBuilderError("Card name is required.", "error");
      return;
    }

    const list = target === "optional" ? state.optionalCards : state.mandatoryCards;

    let canonicalName = null;
    try {
      const q = encodeURIComponent(name);
      const res = await fetch(`/api/card-names/validate?name=${q}`);
      const data = await res.json();
      if (!data.valid) {
        setCardBuilderError(`"${name}" is not a known card. Use the suggestions to pick a valid card name.`, "error");
        return;
      }
      canonicalName = data.name;
    } catch (_) {
      setCardBuilderError("Could not validate card name. Try again.", "error");
      return;
    }

    const duplicate = list.some((card) => cleanName(card.name).toLowerCase() === canonicalName.toLowerCase());
    if (duplicate) {
      setCardBuilderError(`"${canonicalName}" already exists in ${target} cards.`, "error");
      return;
    }

    const tags = [...state.composerTags];
    list.push({ name: canonicalName, tags });
    tags.forEach(addTagToLibrary);

    state.composerTags.clear();
    els.cardNameInput.value = "";
    hideCardNameSuggestions();
    setCardBuilderError("");
    renderCards();
  }

  async function validateCardName(name) {
    const q = encodeURIComponent(cleanName(name));
    const res = await fetch(`/api/card-names/validate?name=${q}`);
    const data = await res.json();
    return data.valid ? data.name : null;
  }

  async function processBulkFile(file) {
    if (!file || !/\.txt$|text\/plain/i.test(file.name)) {
      setCardBuilderError("Please choose a .txt file.", "error");
      return;
    }
    const text = await new Promise((resolve, reject) => {
      const r = new FileReader();
      r.onload = () => resolve(r.result);
      r.onerror = () => reject(new Error("Could not read file."));
      r.readAsText(file, "UTF-8");
    });

    const { mandatory, optional } = parseBulkList(text);
    const toAdd = [
      ...mandatory.map((c) => ({ ...c, target: "mandatory" })),
      ...optional.map((c) => ({ ...c, target: "optional" })),
    ];
    if (!toAdd.length) {
      setCardBuilderError("No card lines found. Use format: 4 Card Name or 4 Card Name [Tag 2]", "error");
      return;
    }

    // Bulk import replaces the current working card lists.
    state.mandatoryCards.length = 0;
    state.optionalCards.length = 0;

    setCardBuilderError(`Validating ${toAdd.length} card(s)…`);
    els.bulkInputBtn.disabled = true;
    const listByTarget = { mandatory: state.mandatoryCards, optional: state.optionalCards };
    const invalid = [];
    let added = 0;

    for (const item of toAdd) {
      const canonical = await validateCardName(item.name);
      if (!canonical) {
        invalid.push(item.name);
        continue;
      }
      const list = listByTarget[item.target];
      list.push({ name: canonical, tags: item.tags || [] });
      (item.tags || []).forEach(addTagToLibrary);
      added++;
    }

    els.bulkInputBtn.disabled = false;
    els.bulkFileInput.value = "";
    if (invalid.length) {
      setCardBuilderError(
        `Added ${added} card(s). Unknown: ${invalid.slice(0, 5).join(", ")}${invalid.length > 5 ? ` (+${invalid.length - 5} more)` : ""}.`,
        "error"
      );
    } else {
      setCardBuilderError(`Added ${added} card(s) from file.`, "success");
    }
    renderCards();
  }

  function hideCardNameSuggestions() {
    if (!els.cardNameSuggestions) return;
    els.cardNameSuggestions.classList.remove("visible");
    els.cardNameSuggestions.innerHTML = "";
    els.cardNameSuggestions.setAttribute("aria-hidden", "true");
    state.cardNameSuggestionsList = [];
    state.cardNameSuggestionIndex = -1;
    els.cardNameInput.removeAttribute("aria-activedescendant");
  }

  function setCardNameSuggestionIndex(index) {
    state.cardNameSuggestionIndex = index;
    if (!els.cardNameSuggestions) return;
    const options = els.cardNameSuggestions.querySelectorAll(".card-name-suggestion-item");
    options.forEach((option, i) => {
      const isActive = i === index;
      option.classList.toggle("active", isActive);
      option.setAttribute("aria-selected", isActive ? "true" : "false");
      if (isActive) {
        option.scrollIntoView({ block: "nearest" });
        els.cardNameInput.setAttribute("aria-activedescendant", option.id);
      }
    });
    if (index < 0) {
      els.cardNameInput.removeAttribute("aria-activedescendant");
    }
  }

  function chooseCardNameSuggestion(index) {
    const name = state.cardNameSuggestionsList[index];
    if (!name) return false;
    els.cardNameInput.value = name;
    hideCardNameSuggestions();
    return true;
  }

  function stepCardNameSuggestion(delta) {
    const total = state.cardNameSuggestionsList.length;
    if (!total) return false;
    let next = state.cardNameSuggestionIndex;
    if (next < 0) {
      next = delta > 0 ? 0 : total - 1;
    } else {
      next = (next + delta + total) % total;
    }
    setCardNameSuggestionIndex(next);
    return true;
  }

  function showCardNameSuggestions(names) {
    if (!els.cardNameSuggestions) return;
    state.cardNameSuggestionsList = names;
    state.cardNameSuggestionIndex = -1;
    els.cardNameSuggestions.innerHTML = "";
    names.forEach((name, i) => {
      const opt = document.createElement("div");
      opt.className = "card-name-suggestion-item";
      opt.role = "option";
      opt.id = `card-name-suggestion-${i}`;
      opt.setAttribute("aria-selected", "false");
      opt.textContent = name;
      opt.addEventListener("click", (e) => {
        e.preventDefault();
        chooseCardNameSuggestion(i);
        els.cardNameInput.focus();
      });
      els.cardNameSuggestions.appendChild(opt);
    });
    els.cardNameSuggestions.classList.add("visible");
    els.cardNameSuggestions.setAttribute("aria-hidden", "false");
    setCardNameSuggestionIndex(-1);
  }

  function fetchCardNameSuggestions(query) {
    if (!query || query.length < 2) {
      hideCardNameSuggestions();
      return;
    }
    const q = encodeURIComponent(query);
    fetch(`/api/card-names?q=${q}`)
      .then((r) => r.json())
      .then((names) => {
        if (Array.isArray(names) && names.length) {
          showCardNameSuggestions(names);
        } else {
          hideCardNameSuggestions();
        }
      })
      .catch(() => hideCardNameSuggestions());
  }

  function onCardNameInput() {
    if (state.cardNameSuggestionsDebounce) clearTimeout(state.cardNameSuggestionsDebounce);
    const value = cleanName(els.cardNameInput.value);
    if (!value || value.length < 2) {
      hideCardNameSuggestions();
      return;
    }
    state.cardNameSuggestionsDebounce = setTimeout(() => fetchCardNameSuggestions(value), 200);
  }

  function showScrapeProgress(visible) {
    if (visible) {
      els.scrapeProgressWrap.classList.remove("hidden");
      els.scrapeProgressFill.style.width = "0%";
      els.scrapeProgressCount.textContent = "0 / 0";
      if (els.scrapeProgressBar) {
        els.scrapeProgressBar.setAttribute("aria-valuenow", 0);
      }
    } else {
      els.scrapeProgressWrap.classList.add("hidden");
    }
  }

  const SCRAPE_LOG_OK_RESULTS = new Set(["ok"]);
  const SCRAPE_LOG_WARN_RESULTS = new Set(["no-data", "empty", "rate-limited"]);

  function clearScrapeLog() {
    if (!els.scrapeLogRows) return;
    els.scrapeLogRows.innerHTML = "";
    if (els.scrapeLogCount) els.scrapeLogCount.textContent = "0";
  }

  function formatScrapeLogTime(ts) {
    const d = ts ? new Date(ts * 1000) : new Date();
    const pad = (n) => String(n).padStart(2, "0");
    return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
  }

  function appendScrapeLogRow(entry) {
    if (!els.scrapeLogRows) return;
    const tr = document.createElement("tr");
    const result = entry.result || "";
    let rowClass = "scrape-log-row-bad";
    if (SCRAPE_LOG_OK_RESULTS.has(result)) rowClass = "scrape-log-row-ok";
    else if (SCRAPE_LOG_WARN_RESULTS.has(result)) rowClass = "scrape-log-row-warn";
    tr.className = rowClass;

    const headers = entry.headers || {};
    const cells = [
      { cls: "scrape-log-time", text: formatScrapeLogTime(entry.ts) },
      { cls: "scrape-log-card", text: entry.card || "" },
      { cls: "scrape-log-try", text: String(entry.attempt || "") },
      { cls: "scrape-log-status", text: entry.status == null ? "—" : String(entry.status) },
      { cls: "scrape-log-ms", text: entry.ms == null ? "—" : String(entry.ms) },
      { cls: "scrape-log-server", text: headers["server"] || "—" },
      { cls: "scrape-log-cfray", text: headers["cf-ray"] || "—" },
      { cls: "scrape-log-cfmit", text: headers["cf-mitigated"] || "—" },
      { cls: "scrape-log-ct", text: headers["content-type"] || "—" },
      {
        cls: "scrape-log-result",
        text:
          result +
          (entry.found != null ? ` (${entry.found})` : "") +
          (entry.retry_after ? ` — retrying in ${entry.retry_after}s` : "") +
          (entry.error ? ` — ${entry.error}` : ""),
      },
    ];
    for (const { cls, text } of cells) {
      const td = document.createElement("td");
      td.className = cls;
      td.textContent = text;
      if (cls === "scrape-log-card" || cls === "scrape-log-ct" || cls === "scrape-log-result") {
        td.title = text;
      }
      tr.appendChild(td);
    }
    els.scrapeLogRows.appendChild(tr);

    if (els.scrapeLogCount) {
      els.scrapeLogCount.textContent = String(els.scrapeLogRows.children.length);
    }
    if (els.scrapeLogBody && !els.scrapeLogBody.classList.contains("hidden")) {
      els.scrapeLogBody.scrollTop = els.scrapeLogBody.scrollHeight;
    }
  }

  function toggleScrapeLog() {
    if (!els.scrapeLogBody || !els.scrapeLogToggle) return;
    const willExpand = els.scrapeLogBody.classList.contains("hidden");
    els.scrapeLogBody.classList.toggle("hidden", !willExpand);
    els.scrapeLogToggle.setAttribute("aria-expanded", willExpand ? "true" : "false");
  }

  if (els.scrapeLogToggle) els.scrapeLogToggle.addEventListener("click", toggleScrapeLog);
  if (els.scrapeLogClear) els.scrapeLogClear.addEventListener("click", clearScrapeLog);

  function updateScrapeProgress(current, total, card) {
    els.scrapeProgressLabel.textContent = card ? `Scraping: ${card}` : "Scraping prices…";
    els.scrapeProgressCount.textContent = `${current} / ${total}`;
    const pct = total ? Math.round((100 * current) / total) : 0;
    els.scrapeProgressFill.style.width = `${pct}%`;
    if (els.scrapeProgressBar) {
      els.scrapeProgressBar.setAttribute("aria-valuenow", pct);
      els.scrapeProgressBar.setAttribute("aria-valuemax", 100);
    }
  }

  function readScrapeStream(response, onProgress, onRequest) {
    return new Promise((resolve, reject) => {
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let currentEvent = null;
      let currentData = null;

      function tryParseAndHandle() {
        if (currentEvent == null || currentData == null) return false;
        let data;
        try {
          data = JSON.parse(currentData);
        } catch (_) {
          return false;  // probably a partial data line; wait for more
        }
        const eventType = currentEvent;
        // Clear before invoking side effects so we never double-fire on the blank-line terminator
        currentEvent = null;
        currentData = null;
        if (eventType === "progress") {
          onProgress(data.current, data.total, data.card);
        } else if (eventType === "request") {
          if (onRequest && data && data.entry) onRequest(data.entry);
        } else if (eventType === "complete") {
          resolve(data.price_data);
          return true;
        } else if (eventType === "error") {
          reject(new Error(data.error || "Scrape failed"));
          return true;
        }
        return false;
      }

      function processChunk() {
        reader.read().then(({ done, value }) => {
          if (done) {
            if (currentData !== null && tryParseAndHandle()) return;
            if (buffer.trim()) {
              try {
                const idx = buffer.lastIndexOf("data:");
                if (idx >= 0) {
                  const dataStr = buffer.slice(idx + 5).trim();
                  const data = JSON.parse(dataStr);
                  if (data.price_data) {
                    resolve(data.price_data);
                    return;
                  }
                }
              } catch (_) {}
            }
            reject(new Error("Scrape did not return data."));
            return;
          }
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";
          for (const line of lines) {
            if (line.startsWith("event: ")) {
              currentEvent = line.slice(7).trim();
              currentData = null;
            } else if (line.startsWith("data: ")) {
              currentData = line.slice(6);
              if (tryParseAndHandle()) return;
            } else if (line === "" && currentEvent && currentData !== null) {
              if (tryParseAndHandle()) return;
              currentEvent = null;
              currentData = null;
            } else if (currentData !== null && line !== "") {
              currentData += line;
              if (tryParseAndHandle()) return;
            }
          }
          processChunk();
        }).catch(reject);
      }
      processChunk();
    });
  }

  async function runOptimiser() {
    const payload = buildPayload();
    const useScrape = true;

    setStatus(
      useScrape ? "Scraping prices…" : "Running optimisation…",
      "loading"
    );
    els.runBtn.disabled = true;
    els.resultPanel.classList.add("hidden");

    try {
      let priceData = null;
      if (useScrape) {
        showScrapeProgress(true);
        clearScrapeLog();
        const scrapeRes = await fetch("/scrape", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (!scrapeRes.ok) {
          const err = await scrapeRes.json().catch(() => ({}));
          setStatus(err.error || "Scrape request failed.", "error");
          showScrapeProgress(false);
          return;
        }
        try {
          priceData = await readScrapeStream(
            scrapeRes,
            (current, total, card) => updateScrapeProgress(current, total, card),
            (entry) => appendScrapeLogRow(entry)
          );
        } catch (err) {
          setStatus(err.message || "Scrape failed.", "error");
          showScrapeProgress(false);
          return;
        }
        setStatus("Running optimisation…", "loading");
        payload.scraped_price_data = priceData;
      }

      const response = await fetch("/optimise", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await response.json();

      if (useScrape) showScrapeProgress(false);

      if (!response.ok || !data.ok) {
        setStatus(data.error || "Optimisation failed.", "error");
        return;
      }

      renderResults(data.summary);
      setStatus(`Optimisation complete (${data.summary.status}).`, "success");
    } catch (error) {
      setStatus("Request failed. Check terminal logs for details.", "error");
      if (useScrape) showScrapeProgress(false);
    } finally {
      els.runBtn.disabled = false;
    }
  }

  function bindPanelToggle() {
    document.querySelectorAll(".panel.closeable .panel-toggle").forEach((btn) => {
      btn.addEventListener("click", () => {
        const panel = btn.closest(".panel");
        if (panel) {
          panel.classList.toggle("collapsed");
        }
      });
    });
  }

  function bindEvents() {
    els.selectAllStores.addEventListener("click", () => {
      state.selectedVendors = new Set(state.vendors);
      renderStores();
    });

    els.clearAllStores.addEventListener("click", () => {
      state.selectedVendors.clear();
      renderStores();
    });

    if (els.clearAllCards) {
      els.clearAllCards.addEventListener("click", () => {
        state.mandatoryCards.length = 0;
        state.optionalCards.length = 0;
        renderCards();
      });
    }

    els.addCardMandatory.addEventListener("click", () => addCard("mandatory"));
    els.addCardOptional.addEventListener("click", () => addCard("optional"));

    els.bulkInputBtn.addEventListener("click", () => els.bulkFileInput.click());
    els.bulkFileInput.addEventListener("change", (e) => {
      const file = e.target.files && e.target.files[0];
      if (file) processBulkFile(file);
    });

    els.cardNameInput.addEventListener("input", onCardNameInput);
    els.cardNameInput.addEventListener("focus", onCardNameInput);
    els.cardNameInput.addEventListener("blur", () => {
      setTimeout(hideCardNameSuggestions, 150);
    });

    els.cardNameInput.addEventListener("keydown", (event) => {
      if (event.key === "ArrowDown") {
        if (stepCardNameSuggestion(1)) {
          event.preventDefault();
        }
        return;
      }
      if (event.key === "ArrowUp") {
        if (stepCardNameSuggestion(-1)) {
          event.preventDefault();
        }
        return;
      }
      if (event.key === "Enter") {
        if (state.cardNameSuggestionIndex >= 0 && state.cardNameSuggestionsList.length) {
          event.preventDefault();
          chooseCardNameSuggestion(state.cardNameSuggestionIndex);
          return;
        }
        event.preventDefault();
        addCard("mandatory");
      }
      if (event.key === "Escape") {
        hideCardNameSuggestions();
      }
    });

    els.addTagBtn.addEventListener("click", addComposerTagFromInput);
    els.newTagInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        addComposerTagFromInput();
      }
    });

    els.addConstraintBtn.addEventListener("click", () => {
      const nextTag = state.tagLibrary[0] || "";
      state.tagConstraints.push({
        tag: nextTag,
        minimum: "",
        maximum: "",
        target: "",
      });
      renderConstraints();
    });

    els.runBtn.addEventListener("click", runOptimiser);
  }

  function init() {
    els.vendorPenalty.value = Number(initial.vendor_penalty || 0);
    els.minOptionalCards.value = Number(initial.min_optional_cards || 0);

    syncTagLibrary();
    bindPanelToggle();
    bindEvents();
    setupListDropZone(els.mandatoryList, "mandatory");
    setupListDropZone(els.optionalList, "optional");
    renderCities();
    renderStores();
    renderTagPalette();
    renderTagDataList();
    renderCards();
    renderConstraints();
  }

  init();
})();
