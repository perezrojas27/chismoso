(() => {
  const TOKEN_KEY = "biometrico_edge_admin_token";

  const $ = (id) => document.getElementById(id);
  const viewLogin = $("view-login");
  const viewMain = $("view-main");

  function token() {
    return sessionStorage.getItem(TOKEN_KEY) || "";
  }

  function setToken(value) {
    if (value) sessionStorage.setItem(TOKEN_KEY, value);
    else sessionStorage.removeItem(TOKEN_KEY);
  }

  function authHeaders(extra = {}) {
    const headers = { ...extra };
    const t = token();
    if (t) {
      headers.Authorization = `Bearer ${t}`;
      headers["X-Edge-Admin-Token"] = t;
    }
    return headers;
  }

  async function api(path, options = {}) {
    const res = await fetch(path, {
      ...options,
      headers: authHeaders(options.headers || {}),
    });
    let data = null;
    const text = await res.text();
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = { detail: text };
    }
    if (!res.ok) {
      const detail = data?.detail;
      const msg =
        typeof detail === "string"
          ? detail
          : Array.isArray(detail)
            ? detail.map((d) => d.msg || JSON.stringify(d)).join("; ")
            : data?.message || `Error ${res.status}`;
      const err = new Error(msg);
      err.status = res.status;
      throw err;
    }
    return data;
  }

  function show(el, on) {
    el.hidden = !on;
  }

  function setError(msg) {
    const el = $("error");
    if (!msg) {
      show(el, false);
      el.textContent = "";
      return;
    }
    el.textContent = msg;
    show(el, true);
  }

  function setNotice(msg) {
    const el = $("notice");
    if (!msg) {
      show(el, false);
      el.textContent = "";
      return;
    }
    el.textContent = msg;
    show(el, true);
  }

  function badgeFor(device) {
    if (!device.configured) return ['info', 'Detectado'];
    if (device.online) return ['ok', 'En línea'];
    if (device.reachable && device.auth_ok === false) return ['warn', 'Clave incorrecta'];
    return ['err', 'Sin conexión'];
  }

  function renderDevices(payload) {
    const body = $("devices-body");
    const devices = payload.devices || [];
    $("devices-message").textContent = payload.message || "";
    if (!devices.length) {
      body.innerHTML =
        '<tr><td colspan="6" class="muted">Sin dispositivos. Busque en la red o agregue manualmente.</td></tr>';
      return;
    }
    body.innerHTML = devices
      .map((d) => {
        const [tone, label] = badgeFor(d);
        const name = (d.location || "").trim() || d.device_id || "—";
        const actions = [];
        if (!d.configured) {
          actions.push(
            `<button type="button" class="btn primary btn-configure" data-host="${escapeAttr(
              d.host,
            )}" data-port="${d.port || 80}" data-location="${escapeAttr(
              d.location || "",
            )}">Configurar</button>`,
          );
        }
        if (d.removable) {
          actions.push(
            `<button type="button" class="btn danger btn-remove" data-id="${escapeAttr(
              d.device_id,
            )}">Quitar</button>`,
          );
        }
        return `<tr>
          <td><span class="badge ${tone}">${label}</span></td>
          <td>${escapeHtml(name)}<div class="muted">${escapeHtml(d.device_id || "")}</div></td>
          <td>${escapeHtml(d.host || "")}</td>
          <td>${d.port || "—"}</td>
          <td>${escapeHtml(d.origin || (d.configured ? "—" : "scan"))}</td>
          <td class="row">${actions.join(" ")}</td>
        </tr>`;
      })
      .join("");

    body.querySelectorAll(".btn-configure").forEach((btn) => {
      btn.addEventListener("click", () => configureDiscovered(btn.dataset));
    });
    body.querySelectorAll(".btn-remove").forEach((btn) => {
      btn.addEventListener("click", () => removeDevice(btn.dataset.id));
    });
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
  function escapeAttr(s) {
    return escapeHtml(s).replace(/'/g, "&#39;");
  }

  async function configureDiscovered(ds) {
    setError(null);
    try {
      const result = await api("/api/biometrico/devices", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          host: ds.host,
          port: Number(ds.port || 80),
          location: ds.location || "Ubicación por definir",
        }),
      });
      setNotice(result.message);
      await loadDevices();
    } catch (e) {
      setError(e.message);
    }
  }

  async function removeDevice(id) {
    if (!window.confirm(`¿Quitar el dispositivo ${id}?`)) return;
    setError(null);
    try {
      const result = await api(`/api/biometrico/devices/${encodeURIComponent(id)}`, {
        method: "DELETE",
      });
      setNotice(result.message);
      await loadDevices();
    } catch (e) {
      setError(e.message);
    }
  }

  async function loadDevices() {
    setError(null);
    const data = await api("/api/biometrico/devices");
    renderDevices(data);
    const ok = data.isapi_password_configured
      ? "Clave ISAPI configurada"
      : "Falta clave ISAPI del reloj";
    $("isapi-status").textContent = `${ok} · usuario ${data.user || "admin"}`;
    return data;
  }

  async function loadStatus() {
    return api("/api/edge-admin/status");
  }

  async function enterMain(status) {
    viewLogin.classList.add("hidden");
    viewMain.classList.remove("hidden");
    $("site-title").textContent = status.site_name || status.site_code || "Sede";
    $("session-user").textContent = status.auth_required
      ? `Sesión activa`
      : "Lab abierto (sin clave de consola)";
    $("isapi-user").value = status.isapi_user || "admin";
    $("scan-seed").value = status.scan_seed || "192.168.10.200";
    $("footer-meta").textContent = `Fuente: ${status.source || "—"} · sede ${status.site_code || "—"}`;
    await loadDevices();
  }

  async function boot() {
    let status;
    try {
      status = await loadStatus();
    } catch (e) {
      viewLogin.classList.remove("hidden");
      $("login-error").hidden = false;
      $("login-error").textContent = e.message;
      return;
    }

    if (!status.auth_required) {
      // Lab sin password de consola: entra directo
      if (!token()) {
        const login = await api("/api/edge-admin/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username: "lab-open", password: "lab" }),
        });
        setToken(login.token);
      }
      await enterMain(status);
      return;
    }

    if (token()) {
      try {
        await enterMain(status);
        return;
      } catch (e) {
        if (e.status === 401) setToken("");
      }
    }
    viewLogin.classList.remove("hidden");
    viewMain.classList.add("hidden");
    $("login-user").value = status.default_username || "admin";
  }

  $("form-login").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const err = $("login-error");
    err.hidden = true;
    try {
      const login = await api("/api/edge-admin/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: $("login-user").value.trim(),
          password: $("login-pass").value,
        }),
      });
      setToken(login.token);
      const status = await loadStatus();
      await enterMain(status);
    } catch (e) {
      err.hidden = false;
      err.textContent = e.message;
    }
  });

  $("btn-logout").addEventListener("click", async () => {
    try {
      await api("/api/edge-admin/logout", { method: "POST" });
    } catch (_) {
      /* ignore */
    }
    setToken("");
    location.reload();
  });

  $("form-isapi").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    setError(null);
    try {
      const result = await api("/api/edge-admin/isapi-credentials", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: $("isapi-user").value.trim(),
          password: $("isapi-pass").value,
        }),
      });
      $("isapi-pass").value = "";
      setNotice(result.message);
      await loadDevices();
    } catch (e) {
      setError(e.message);
    }
  });

  $("btn-refresh").addEventListener("click", () => {
    setNotice(null);
    loadDevices().catch((e) => setError(e.message));
  });

  $("btn-add").addEventListener("click", () => {
    $("form-add").classList.remove("hidden");
  });
  $("btn-add-cancel").addEventListener("click", () => {
    $("form-add").classList.add("hidden");
  });

  $("form-add").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    setError(null);
    try {
      const result = await api("/api/biometrico/devices", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          host: $("add-host").value.trim(),
          port: Number($("add-port").value),
          location: $("add-location").value.trim(),
        }),
      });
      setNotice(result.message);
      $("form-add").reset();
      $("add-port").value = "80";
      $("form-add").classList.add("hidden");
      await loadDevices();
    } catch (e) {
      setError(e.message);
    }
  });

  $("btn-scan").addEventListener("click", async () => {
    setError(null);
    setNotice("Buscando en la red…");
    try {
      const seed = $("scan-seed").value.trim();
      const result = await api("/api/biometrico/devices/scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ seed_host: seed }),
      });
      setNotice(result.message);
      // Mezclar: recargar lista completa (incluye discovery habitual)
      await loadDevices();
      if (result.devices?.length) {
        // Si la lista aún no los muestra, pintar hallazgos del scan
        const current = await api("/api/biometrico/devices");
        const hosts = new Set((current.devices || []).map((d) => d.host));
        const extra = result.devices.filter((d) => !hosts.has(d.host));
        if (extra.length) {
          current.devices = [...(current.devices || []), ...extra];
          current.message = result.message;
          renderDevices(current);
        }
      }
    } catch (e) {
      setError(e.message);
    }
  });

  boot().catch((e) => {
    viewLogin.classList.remove("hidden");
    $("login-error").hidden = false;
    $("login-error").textContent = e.message;
  });
})();
