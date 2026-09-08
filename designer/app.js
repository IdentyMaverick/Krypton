(function () {
  "use strict";

  const STORAGE_KEY = "krypton-profile-v1";
  const INSTALL_CMD = [
    "@echo off",
    "setlocal EnableExtensions",
    "title Krypton Windows 11 setup",
    'cd /d "%~dp0"',
    "",
    "net session >nul 2>&1",
    "if errorlevel 1 (",
    "  echo Requesting administrator permission...",
    "  powershell -NoProfile -Command \"Start-Process -FilePath '%~f0' -Verb RunAs\"",
    "  exit /b",
    ")",
    "",
    "echo.",
    "echo  Krypton setup",
    "echo  Installing selected apps and applying Windows 11 options.",
    "echo.",
    'powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-Bundle.ps1"',
    'set "EXITCODE=%ERRORLEVEL%"',
    "echo.",
    'if not "%EXITCODE%"=="0" (',
    "  echo Setup finished with errors. Review the log above.",
    ") else (",
    "  echo Setup finished.",
    ")",
    "pause",
    "exit /b %EXITCODE%",
    "",
  ].join("\r\n");

  const state = {
    catalog: null,
    status: null,
    view: "apps",
    category: "all",
    search: "",
    name: "My Windows 11 PC",
    selectedApps: new Set(),
    customApps: {},
    selectedTweaks: new Set(),
  };

  const els = {
    main: document.getElementById("main"),
    search: document.getElementById("search"),
    bundleName: document.getElementById("bundle-name"),
    presetList: document.getElementById("preset-list"),
    cartList: document.getElementById("cart-list"),
    cartCount: document.getElementById("cart-count"),
    statusLine: document.getElementById("status-line"),
    customDialog: document.getElementById("custom-dialog"),
    customForm: document.getElementById("custom-form"),
    toast: document.getElementById("toast"),
  };

  function initials(name) {
    return name
      .split(/\s+/)
      .slice(0, 2)
      .map((part) => part[0])
      .join("")
      .toUpperCase();
  }

  function colorFor(id) {
    let hash = 0;
    for (let i = 0; i < id.length; i += 1) hash = (hash * 33 + id.charCodeAt(i)) >>> 0;
    const hue = hash % 360;
    return `hsl(${hue} 70% 62%)`;
  }

  function slugify(value) {
    return (
      value
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-|-$/g, "") || "bundle"
    );
  }

  function toast(message) {
    els.toast.hidden = false;
    els.toast.textContent = message;
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => {
      els.toast.hidden = true;
    }, 2800);
  }

  function appIndex() {
    return Object.fromEntries(state.catalog.apps.map((app) => [app.id, app]));
  }

  function tweakIndex() {
    return Object.fromEntries(state.catalog.tweaks.map((tweak) => [tweak.id, tweak]));
  }

  function persist() {
    const payload = {
      name: state.name,
      selectedApps: [...state.selectedApps],
      customApps: state.customApps,
      selectedTweaks: [...state.selectedTweaks],
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  }

  function restore() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return;
      const saved = JSON.parse(raw);
      if (saved.name) state.name = saved.name;
      if (Array.isArray(saved.selectedApps)) state.selectedApps = new Set(saved.selectedApps);
      if (saved.customApps && typeof saved.customApps === "object") state.customApps = saved.customApps;
      if (Array.isArray(saved.selectedTweaks)) state.selectedTweaks = new Set(saved.selectedTweaks);
    } catch {
      /* ignore broken local data */
    }
  }

  function selectedCount() {
    return state.selectedApps.size + Object.keys(state.customApps).length;
  }

  function buildProfile() {
    const catalogApps = [...state.selectedApps].map((id) => ({ id }));
    const custom = Object.values(state.customApps);
    return {
      name: state.name.trim() || "My Windows 11 PC",
      version: 1,
      createdAt: new Date().toISOString().replace(/\.\d{3}Z$/, "Z"),
      apps: [...catalogApps, ...custom],
      tweaks: [...state.selectedTweaks],
    };
  }

  function validateClientProfile(profile) {
    if (!profile.apps.length && !profile.tweaks.length) {
      throw new Error("Select at least one app or Windows option.");
    }
    for (const app of profile.apps) {
      if (app.id && !app.source) continue;
      if (app.source === "winget" && !/^[A-Za-z0-9][A-Za-z0-9.+_-]*(\.[A-Za-z0-9][A-Za-z0-9.+_-]*)+$/.test(app.package || "")) {
        throw new Error(`Invalid winget id for ${app.name || app.id}`);
      }
      if (app.source === "url" && !/^https:\/\//.test(app.url || "")) {
        throw new Error("Custom installer URLs must start with https://");
      }
      if (app.source === "local") {
        if (!app.path || app.path.includes("..") || /^[a-zA-Z]:[\\/]/.test(app.path) || app.path.startsWith("/")) {
          throw new Error("Local installer path must stay inside the setup folder.");
        }
      }
    }
    return profile;
  }

  function renderNav() {
    document.querySelectorAll(".nav-btn").forEach((button) => {
      button.classList.toggle("is-active", button.dataset.view === state.view);
    });
  }

  function renderPresets() {
    els.presetList.innerHTML = "";
    for (const preset of state.catalog.presets) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "preset-btn";
      button.innerHTML = `<strong>${preset.name}</strong><span>${preset.apps.length} apps</span>`;
      button.addEventListener("click", () => applyPreset(preset.id));
      els.presetList.appendChild(button);
    }
  }

  function renderCart() {
    const apps = [];
    const known = appIndex();
    for (const id of state.selectedApps) {
      const app = known[id];
      if (app) apps.push({ id, name: app.name, detail: app.package, kind: "app" });
    }
    for (const app of Object.values(state.customApps)) {
      apps.push({ id: app.id, name: app.name, detail: app.package || app.url || app.path, kind: "custom" });
    }
    const tweaks = [...state.selectedTweaks].map((id) => {
      const tweak = tweakIndex()[id];
      return { id, name: tweak ? tweak.name : id, detail: "Windows option", kind: "tweak" };
    });
    els.cartCount.textContent = `${apps.length} apps · ${tweaks.length} options`;
    els.cartList.innerHTML = "";
    for (const item of [...apps, ...tweaks]) {
      const li = document.createElement("li");
      li.innerHTML = `<div><strong>${item.name}</strong><div class="meta">${item.detail}</div></div>`;
      const remove = document.createElement("button");
      remove.type = "button";
      remove.setAttribute("aria-label", `Remove ${item.name}`);
      remove.textContent = "×";
      remove.addEventListener("click", () => {
        if (item.kind === "tweak") state.selectedTweaks.delete(item.id);
        else if (item.kind === "custom") delete state.customApps[item.id];
        else state.selectedApps.delete(item.id);
        persist();
        render();
      });
      li.appendChild(remove);
      els.cartList.appendChild(li);
    }
    if (!apps.length && !tweaks.length) {
      els.cartList.innerHTML = '<li class="empty">Nothing selected yet.</li>';
    }
    document.getElementById("btn-export").disabled = !apps.length && !tweaks.length;
  }

  function filteredApps() {
    const query = state.search.trim().toLowerCase();
    return state.catalog.apps.filter((app) => {
      if (state.category !== "all" && app.category !== state.category) return false;
      if (!query) return true;
      return [app.name, app.publisher, app.package, app.description].join(" ").toLowerCase().includes(query);
    });
  }

  function renderApps() {
    const categories = [{ id: "all", name: "All" }, ...state.catalog.categories];
    const chips = categories
      .map(
        (category) =>
          `<button type="button" class="chip${state.category === category.id ? " is-active" : ""}" data-category="${category.id}">${category.name}</button>`
      )
      .join("");
    const cards = filteredApps()
      .map((app) => {
        const selected = state.selectedApps.has(app.id);
        return `<button type="button" class="card${selected ? " is-selected" : ""}" data-app="${app.id}">
          <span class="avatar" style="background:${colorFor(app.id)}">${initials(app.name)}</span>
          <span>
            <h3>${app.name}</h3>
            <div class="meta">${app.publisher} · ${app.package}</div>
            <p>${app.description}</p>
          </span>
          <span class="check" aria-hidden="true"></span>
        </button>`;
      })
      .join("");
    els.main.innerHTML = `
      <div class="section-head">
        <div>
          <h1>Choose apps</h1>
          <p>Everything you tick is baked into one setup program.</p>
        </div>
      </div>
      <div class="chips">${chips}</div>
      <div class="grid">${cards || '<p class="empty">No apps match that search.</p>'}</div>
    `;
    els.main.querySelectorAll("[data-category]").forEach((chip) => {
      chip.addEventListener("click", () => {
        state.category = chip.dataset.category;
        render();
      });
    });
    els.main.querySelectorAll("[data-app]").forEach((card) => {
      card.addEventListener("click", () => {
        const id = card.dataset.app;
        if (state.selectedApps.has(id)) state.selectedApps.delete(id);
        else state.selectedApps.add(id);
        persist();
        render();
      });
    });
  }

  function renderTweaks() {
    const items = state.catalog.tweaks
      .map((tweak) => {
        const selected = state.selectedTweaks.has(tweak.id);
        return `<button type="button" class="tweak${selected ? " is-selected" : ""}" data-tweak="${tweak.id}">
          <span>
            <h3>${tweak.name}</h3>
            <p>${tweak.description}</p>
            <span class="risk ${tweak.risk}">${tweak.risk} · ${tweak.scope}</span>
          </span>
          <span class="check" aria-hidden="true"></span>
        </button>`;
      })
      .join("");
    els.main.innerHTML = `
      <div class="section-head">
        <div>
          <h1>Windows 11 options</h1>
          <p>Optional Explorer, taskbar, and path tweaks. Applied after the apps install.</p>
        </div>
      </div>
      <div class="tweak-list">${items}</div>
    `;
    els.main.querySelectorAll("[data-tweak]").forEach((row) => {
      row.addEventListener("click", () => {
        const id = row.dataset.tweak;
        if (state.selectedTweaks.has(id)) state.selectedTweaks.delete(id);
        else state.selectedTweaks.add(id);
        persist();
        render();
      });
    });
  }

  function renderReview() {
    const profile = buildProfile();
    const known = appIndex();
    const tweaks = tweakIndex();
    const appItems = profile.apps
      .map((entry) => {
        if (entry.source) return `<li><strong>${entry.name}</strong> — ${entry.source} ${entry.package || entry.url || entry.path}</li>`;
        const app = known[entry.id];
        return `<li><strong>${app.name}</strong> — winget ${app.package}</li>`;
      })
      .join("");
    const tweakItems = profile.tweaks.map((id) => `<li>${tweaks[id].name}</li>`).join("");
    const platform = state.status?.windows
      ? "This designer is running on Windows. Export the setup, then run Install.cmd as administrator on the target PC."
      : "Design here, then copy the exported folder to a Windows 11 PC and run Install.cmd.";
    els.main.innerHTML = `
      <div class="section-head">
        <div>
          <h1>Review &amp; export</h1>
          <p>The setup program includes only what you selected or added.</p>
        </div>
      </div>
      <p class="banner">${platform}</p>
      <div class="review-panel">
        <h2>${profile.name}</h2>
        <p>${profile.apps.length} apps · ${profile.tweaks.length} Windows options</p>
        <h3>Apps</h3>
        <ol>${appItems || "<li>(none)</li>"}</ol>
        <h3>Windows options</h3>
        <ol>${tweakItems || "<li>(none)</li>"}</ol>
      </div>
    `;
  }

  function render() {
    els.bundleName.value = state.name;
    renderNav();
    renderCart();
    if (state.view === "tweaks") renderTweaks();
    else if (state.view === "review") renderReview();
    else renderApps();
  }

  function applyPreset(presetId) {
    const preset = state.catalog.presets.find((item) => item.id === presetId);
    if (!preset) return;
    state.selectedApps = new Set(preset.apps);
    state.selectedTweaks = new Set(preset.tweaks);
    persist();
    render();
    toast(`Loaded ${preset.name} preset`);
  }

  function customSourceFields() {
    const source = document.getElementById("custom-source").value;
    document.getElementById("custom-package-wrap").hidden = source !== "winget";
    document.getElementById("custom-url-wrap").hidden = source !== "url";
    document.getElementById("custom-path-wrap").hidden = source !== "local";
    document.getElementById("custom-args-wrap").hidden = source === "winget";
  }

  function addCustomApp() {
    const error = document.getElementById("custom-error");
    error.hidden = true;
    const name = document.getElementById("custom-name").value.trim();
    const source = document.getElementById("custom-source").value;
    if (!name) {
      error.hidden = false;
      error.textContent = "Name is required.";
      return;
    }
    const existing = new Set([...state.selectedApps, ...Object.keys(state.customApps)]);
    let id = `custom-${slugify(name)}`;
    let n = 2;
    while (existing.has(id)) {
      id = `custom-${slugify(name)}-${n}`;
      n += 1;
    }
    const app = { id, name, source };
    try {
      if (source === "winget") {
        app.package = document.getElementById("custom-package").value.trim();
        if (!app.package) throw new Error("Enter a winget package id such as Vendor.App.");
      } else if (source === "url") {
        app.url = document.getElementById("custom-url").value.trim();
        app.silentArgs = document.getElementById("custom-args").value.trim();
        if (!app.silentArgs) delete app.silentArgs;
      } else {
        app.path = document.getElementById("custom-path").value.trim().replace(/\\/g, "/");
        app.silentArgs = document.getElementById("custom-args").value.trim();
        if (!app.silentArgs) delete app.silentArgs;
      }
      validateClientProfile({ name: "tmp", apps: [app], tweaks: ["show-file-extensions"] });
    } catch (err) {
      error.hidden = false;
      error.textContent = err.message;
      return;
    }
    state.customApps[id] = app;
    persist();
    els.customDialog.close();
    els.customForm.reset();
    customSourceFields();
    render();
    toast(`Added ${name}`);
  }

  function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function readmeFor(profile) {
    const known = appIndex();
    const tweaks = tweakIndex();
    const apps = profile.apps
      .map((entry) => {
        if (entry.source === "winget") return `- ${entry.name} (winget ${entry.package})`;
        if (entry.source === "url") return `- ${entry.name} (${entry.url})`;
        if (entry.source === "local") return `- ${entry.name} (${entry.path})`;
        const app = known[entry.id];
        return `- ${app.name} (winget ${app.package})`;
      })
      .join("\r\n");
    const optionLines = profile.tweaks.map((id) => `- ${tweaks[id].name}`).join("\r\n") || "- (none)";
    return [
      "Krypton setup bundle",
      "====================",
      "",
      `Name: ${profile.name}`,
      "",
      "Copy this folder to a Windows 11 PC and run Install.cmd as administrator.",
      "",
      "Apps",
      "----",
      apps || "- (none)",
      "",
      "Windows options",
      "---------------",
      optionLines,
      "",
    ].join("\r\n");
  }

  async function exportSetup() {
    const profile = validateClientProfile(buildProfile());
    els.statusLine.textContent = "Building setup program…";
    try {
      const response = await fetch("/api/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(profile),
      });
      if (response.ok) {
        const blob = await response.blob();
        downloadBlob(blob, `KryptonSetup-${slugify(profile.name)}.zip`);
        els.statusLine.textContent = "Downloaded setup zip. Extract it and run Install.cmd on Windows 11.";
        toast("Setup program exported");
        return;
      }
      const failure = await response.json().catch(() => ({}));
      if (response.status >= 400 && failure.error) {
        throw new Error(failure.error);
      }
    } catch (err) {
      if (err.message && /select at least|invalid|must/i.test(err.message)) {
        els.statusLine.textContent = err.message;
        toast(err.message);
        return;
      }
    }
    try {
      const scriptResponse = await fetch("/engine/Install-Bundle.ps1");
      if (!scriptResponse.ok) throw new Error("Could not load the installer engine.");
      const installer = await scriptResponse.text();
      const resolvedResponse = await fetch("/api/validate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(profile),
      });
      const resolved = resolvedResponse.ok ? (await resolvedResponse.json()).profile : profile;
      const folder = `KryptonSetup-${slugify(profile.name)}`;
      const zip = window.KryptonZip.createZip([
        { name: `${folder}/bundle.json`, data: JSON.stringify(resolved, null, 2) + "\n" },
        { name: `${folder}/Install.cmd`, data: INSTALL_CMD },
        { name: `${folder}/Install-Bundle.ps1`, data: installer },
        { name: `${folder}/README.txt`, data: readmeFor(resolved) },
      ]);
      downloadBlob(zip, `${folder}.zip`);
      els.statusLine.textContent = "Downloaded setup zip. Extract it and run Install.cmd on Windows 11.";
      toast("Setup program exported");
    } catch (err) {
      els.statusLine.textContent = err.message;
      toast(err.message);
    }
  }

  function saveProfileJson() {
    const profile = buildProfile();
    downloadBlob(
      new Blob([JSON.stringify(profile, null, 2) + "\n"], { type: "application/json" }),
      `${slugify(profile.name)}.krypton.json`
    );
    toast("Profile JSON saved");
  }

  function importProfile(file) {
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const profile = JSON.parse(reader.result);
        state.name = profile.name || state.name;
        state.selectedApps = new Set();
        state.customApps = {};
        state.selectedTweaks = new Set(profile.tweaks || []);
        const known = appIndex();
        for (const entry of profile.apps || []) {
          const id = typeof entry === "string" ? entry : entry.id;
          if (known[id]) state.selectedApps.add(id);
          else if (entry && entry.source) state.customApps[entry.id] = entry;
        }
        persist();
        render();
        toast("Profile imported");
      } catch (err) {
        toast("Could not read that profile");
        els.statusLine.textContent = err.message;
      }
    };
    reader.readAsText(file);
  }

  async function boot() {
    restore();
    els.bundleName.value = state.name;
    const [catalogResponse, statusResponse] = await Promise.all([
      fetch("/api/catalog"),
      fetch("/api/status"),
    ]);
    if (!catalogResponse.ok) throw new Error("Could not load the app catalog.");
    state.catalog = await catalogResponse.json();
    state.status = statusResponse.ok ? await statusResponse.json() : { windows: false };
    const known = new Set(state.catalog.apps.map((app) => app.id));
    state.selectedApps = new Set([...state.selectedApps].filter((id) => known.has(id)));
    els.statusLine.textContent = state.status.windows
      ? "Designer ready. Export a setup program, then run it with administrator rights."
      : "Designer ready. Export works here; the setup program itself runs on Windows 11.";
    renderPresets();
    render();
  }

  document.querySelectorAll(".nav-btn").forEach((button) => {
    button.addEventListener("click", () => {
      state.view = button.dataset.view;
      render();
    });
  });
  els.search.addEventListener("input", () => {
    state.search = els.search.value;
    if (state.view === "apps") renderApps();
  });
  els.bundleName.addEventListener("input", () => {
    state.name = els.bundleName.value;
    persist();
  });
  document.getElementById("btn-add-custom").addEventListener("click", () => {
    customSourceFields();
    els.customDialog.showModal();
  });
  document.getElementById("custom-source").addEventListener("change", customSourceFields);
  document.getElementById("custom-save").addEventListener("click", addCustomApp);
  document.getElementById("btn-export").addEventListener("click", exportSetup);
  document.getElementById("btn-save-profile").addEventListener("click", saveProfileJson);
  document.getElementById("btn-import-profile").addEventListener("click", () => {
    document.getElementById("import-file").click();
  });
  document.getElementById("import-file").addEventListener("change", (event) => {
    const file = event.target.files[0];
    if (file) importProfile(file);
    event.target.value = "";
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "/" && event.target === document.body) {
      event.preventDefault();
      els.search.focus();
    }
  });

  boot().catch((err) => {
    els.main.innerHTML = `<p class="empty">${err.message}</p>`;
    els.statusLine.textContent = err.message;
  });
})();
