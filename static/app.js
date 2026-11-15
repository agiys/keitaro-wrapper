const $ = (selector) => document.querySelector(selector);
const offerNames = new Map();
let currentCampaign = null;

async function api(path, options = {}) {
  const response = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = Array.isArray(data.detail) ? data.detail.map((item) => item.msg).join("; ") : data.detail;
    throw new Error(detail || `Ошибка ${response.status}`);
  }
  return data;
}

function notify(message, kind = "success") {
  const box = $("#notice");
  box.textContent = message;
  box.className = kind;
  box.hidden = false;
}

function clearNotice() {
  $("#notice").hidden = true;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
}

document.querySelectorAll("nav button").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll("nav button").forEach((item) => item.classList.toggle("active", item === button));
    $("#create").hidden = button.dataset.tab !== "create";
    $("#edit").hidden = button.dataset.tab !== "edit";
    clearNotice();
    if (button.dataset.tab === "edit") loadCampaignList();
  });
});

function debounce(fn, delay) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

function attachOfferSearch(input) {
  const list = $("#offer-options");
  input.addEventListener("input", debounce(async () => {
    const offers = await api(`/offers?q=${encodeURIComponent(input.value)}&limit=20`).catch(() => []);
    list.innerHTML = "";
    offers.forEach((offer) => {
      offerNames.set(offer.name, offer.id);
      const option = document.createElement("option");
      option.value = offer.name;
      list.appendChild(option);
    });
  }, 250));
}

function resolveOfferId(text) {
  const value = text.trim();
  if (offerNames.has(value)) return offerNames.get(value);
  if (/^\d+$/.test(value)) return Number(value);
  const match = value.match(/^(\d+)\s/);
  if (match) return Number(match[1]);
  throw new Error("Выберите оффер из списка или введите его ID");
}

function fillSelect(select, items, selected) {
  select.innerHTML = `<option value="">— не выбрано —</option>` +
    items.map((item) => `<option value="${item.id}">${escapeHtml(item.name)}</option>`).join("");
  if (selected) select.value = String(selected);
}

async function loadOptions() {
  const data = await api("/options");
  const form = $("#create-form");
  fillSelect(form.group_id, data.groups, data.defaults.group_id);
  fillSelect(form.domain_id, data.domains, data.defaults.domain_id);
  fillSelect(form.source_id, data.sources, data.defaults.source_id);
}

$("#create-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  clearNotice();
  const form = event.target;
  const submit = form.querySelector("button");
  submit.disabled = true;
  try {
    const body = {
      name: form.name.value,
      geo: form.geo.value,
      offer_id: resolveOfferId(form.offer.value),
      group_id: form.group_id.value ? Number(form.group_id.value) : null,
      domain_id: form.domain_id.value ? Number(form.domain_id.value) : null,
      source_id: form.source_id.value ? Number(form.source_id.value) : null,
    };
    const campaign = await api("/campaigns", { method: "POST", body });
    notify(`Кампания создана: ID ${campaign.keitaro_id}, alias ${campaign.alias}`);
    $("#created").innerHTML = `<p><button id="open-created">Открыть в редакторе</button></p>`;
    $("#open-created").addEventListener("click", () => {
      document.querySelector('nav button[data-tab="edit"]').click();
      openCampaign(campaign.keitaro_id);
    });
    form.reset();
    await loadOptions();
  } catch (error) {
    notify(error.message, "error");
  } finally {
    submit.disabled = false;
  }
});

async function loadCampaignList() {
  const campaigns = await api("/campaigns");
  const select = $("#campaign-select");
  select.innerHTML = `<option value="">— созданные здесь —</option>` +
    campaigns.map((item) => `<option value="${item.keitaro_id}">${escapeHtml(item.name)} (${item.keitaro_id})</option>`).join("");
  if (currentCampaign) select.value = String(currentCampaign);
}

$("#campaign-select").addEventListener("change", (event) => {
  if (event.target.value) openCampaign(Number(event.target.value));
});

$("#load").addEventListener("click", () => {
  const id = Number($("#campaign-id").value);
  if (id) openCampaign(id);
});

async function openCampaign(id) {
  clearNotice();
  try {
    render(await api(`/campaigns/${id}`));
  } catch (error) {
    notify(error.message, "error");
  }
}

function statCells(stats) {
  return `<td>${stats.clicks}</td><td>${stats.unique}</td><td>${stats.bots}</td><td>${stats.conversions}</td>`;
}

function render(campaign) {
  currentCampaign = campaign.id;
  const flows = campaign.streams.map((stream) => {
    if (stream.schema !== "landings") {
      const geo = stream.geo.length ? `Страны принимать: ${stream.geo.join(", ")}` : "Без фильтров";
      return `<div class="flow"><h3>${escapeHtml(stream.name)}</h3>
        <div class="meta">${escapeHtml(stream.target || "")} · ${geo}</div>
        <table><tr><th></th><th>Клики</th><th>Уник.</th><th>Боты</th><th>Конв.</th></tr>
        <tr><td>Поток</td>${statCells(stream.stats)}</tr></table></div>`;
    }
    const rows = stream.offers.map((offer) => `<tr data-offer="${offer.offer_id}">
        <td>${escapeHtml(offer.name)}</td>
        <td><input type="number" min="0" max="100" value="${offer.share}" class="share"> %</td>
        ${statCells(offer.stats)}
        <td><button class="remove" title="Удалить оффер" data-offer="${offer.offer_id}">×</button></td></tr>`).join("");
    return `<div class="flow"><h3>${escapeHtml(stream.name)}</h3>
      <table><tr><th>Оффер</th><th>Доля</th><th>Клики</th><th>Уник.</th><th>Боты</th><th>Конв.</th><th></th></tr>${rows}
        <tr><td>Поток целиком</td><td></td>${statCells(stream.stats)}<td></td></tr></table>
      <div class="sum" id="sum"></div>
      <div class="add"><input id="add-offer" list="offer-options" placeholder="добавить оффер: название или ID" autocomplete="off">
        <button id="add-button">Добавить</button> <button id="save-shares">Сохранить доли</button></div></div>`;
  }).join("");

  const history = campaign.history.length
    ? `<ul>${campaign.history.map((item) => `<li>${new Date(item.at).toLocaleString()} — оффер ${item.offer_id}: ${item.action === "added" ? "добавлен" : "удалён"}</li>`).join("")}</ul>`
    : "";
  $("#details").innerHTML = `<h2>${escapeHtml(campaign.name)} <small>#${campaign.id} · ${escapeHtml(campaign.alias)}</small></h2>${flows}
    ${history ? `<div class="history"><b>История изменений офферов</b>${history}</div>` : ""}`;
  bindEditor(campaign);
}

function bindEditor(campaign) {
  const input = $("#add-offer");
  if (!input) return;
  attachOfferSearch(input);
  updateSum();
  document.querySelectorAll(".share").forEach((field) => field.addEventListener("input", updateSum));

  $("#add-button").addEventListener("click", () => mutate(() =>
    api(`/campaigns/${campaign.id}/offers`, { method: "POST", body: { offer_id: resolveOfferId(input.value) } })));

  document.querySelectorAll(".remove").forEach((button) => button.addEventListener("click", () => {
    if (confirm("Удалить оффер из кампании?")) {
      mutate(() => api(`/campaigns/${campaign.id}/offers/${button.dataset.offer}`, { method: "DELETE" }));
    }
  }));

  $("#save-shares").addEventListener("click", () => {
    const shares = [...document.querySelectorAll("tr[data-offer]")].map((row) => ({
      offer_id: Number(row.dataset.offer),
      share: Number(row.querySelector(".share").value),
    }));
    mutate(() => api(`/campaigns/${campaign.id}/shares`, { method: "PUT", body: { shares } }));
  });
}

function updateSum() {
  const total = [...document.querySelectorAll(".share")].reduce((sum, field) => sum + Number(field.value || 0), 0);
  const box = $("#sum");
  box.textContent = `Сумма долей: ${total}%`;
  box.classList.toggle("bad", total !== 100);
  $("#save-shares").disabled = total !== 100;
}

async function mutate(action) {
  clearNotice();
  try {
    render(await action());
    notify("Сохранено");
  } catch (error) {
    notify(error.message, "error");
  }
}

attachOfferSearch(document.querySelector('#create-form [name="offer"]'));
loadOptions().catch((error) => notify(error.message, "error"));
