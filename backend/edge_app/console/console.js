(() => {
  const TOKEN_KEY = "biometrico_edge_admin_token";

  const $ = (id) => document.getElementById(id);
  const viewLogin = $("view-login");
  const viewMain = $("view-main");

  let authRequired = false;
  let editingDeviceId = null;

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
    if (!device.configured) return ["info", "Detectado"];
    if (device.online) return ["ok", "En línea"];
    if (device.reachable && device.auth_ok === false) return ["warn", "Clave incorrecta"];
    return ["err", "Sin conexión"];
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

  function resetAddForm() {
    editingDeviceId = null;
    $("add-device-id").value = "";
    $("form-add-title").textContent = "Nuevo dispositivo";
    $("btn-save-device").textContent = "Guardar dispositivo";
    $("form-add").reset();
    $("add-port").value = "80";
    $("form-add").classList.add("hidden");
  }

  function openEditForm(d) {
    editingDeviceId = d.device_id || null;
    $("add-device-id").value = editingDeviceId || "";
    $("form-add-title").textContent = editingDeviceId
      ? `Editar ${editingDeviceId}`
      : "Editar dispositivo";
    $("btn-save-device").textContent = "Guardar cambios";
    $("add-host").value = d.host || "";
    $("add-port").value = String(d.port || 80);
    $("add-location").value = d.location || "";
    $("form-add").classList.remove("hidden");
    $("add-host").focus();
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
        } else {
          if (d.editable !== false) {
            actions.push(
              `<button type="button" class="btn btn-edit" data-id="${escapeAttr(
                d.device_id,
              )}" data-host="${escapeAttr(d.host || "")}" data-port="${
                d.port || 80
              }" data-location="${escapeAttr(d.location || "")}">Editar</button>`,
            );
          }
          actions.push(
            `<button type="button" class="btn accent btn-probe" data-id="${escapeAttr(
              d.device_id,
            )}">Probar</button>`,
          );
          if (d.removable) {
            actions.push(
              `<button type="button" class="btn danger btn-remove" data-id="${escapeAttr(
                d.device_id,
              )}" data-env="${d.still_in_env ? "1" : "0"}">Quitar</button>`,
            );
          }
        }
        return `<tr>
          <td><span class="badge ${tone}">${label}</span></td>
          <td>${escapeHtml(name)}<div class="muted">${escapeHtml(d.device_id || "")}</div></td>
          <td>${escapeHtml(d.host || "")}</td>
          <td>${d.port || "—"}</td>
          <td>${escapeHtml(d.origin || (d.configured ? "—" : "scan"))}</td>
          <td class="row actions">${actions.join(" ")}</td>
        </tr>`;
      })
      .join("");

    body.querySelectorAll(".btn-configure").forEach((btn) => {
      btn.addEventListener("click", () => configureDiscovered(btn.dataset));
    });
    body.querySelectorAll(".btn-edit").forEach((btn) => {
      btn.addEventListener("click", () =>
        openEditForm({
          device_id: btn.dataset.id,
          host: btn.dataset.host,
          port: btn.dataset.port,
          location: btn.dataset.location,
        }),
      );
    });
    body.querySelectorAll(".btn-probe").forEach((btn) => {
      btn.addEventListener("click", () => probeDevice(btn.dataset.id));
    });
    body.querySelectorAll(".btn-remove").forEach((btn) => {
      btn.addEventListener("click", () =>
        removeDevice(btn.dataset.id, btn.dataset.env === "1"),
      );
    });
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

  async function removeDevice(id, stillInEnv) {
    const extra = stillInEnv
      ? "\n\nNota: si también está en el .env, puede seguir activo hasta quitarlo allí."
      : "";
    if (!window.confirm(`¿Quitar el dispositivo ${id} del registro de la consola?${extra}`)) {
      return;
    }
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

  async function probeDevice(id) {
    setError(null);
    setNotice(`Probando ${id}…`);
    try {
      const result = await api(
        `/api/biometrico/devices/${encodeURIComponent(id)}/probe`,
        { method: "POST" },
      );
      setNotice(`${id}: ${result.message}`);
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

  function applyConsoleAuthHints(status) {
    authRequired = !!status.auth_required;
    $("console-user").value = status.default_username || "admin";
    const currentLabel = $("label-console-current");
    const currentInput = $("console-current");
    if (authRequired) {
      currentLabel.classList.remove("hidden");
      currentInput.required = true;
      $("console-auth-hint").textContent =
        "Debe indicar la contraseña actual para cambiarla.";
    } else {
      currentLabel.classList.add("hidden");
      currentInput.required = false;
      currentInput.value = "";
      $("console-auth-hint").textContent =
        "La consola está abierta (sin clave). Defina una nueva para proteger el acceso.";
    }
  }

  async function enterMain(status) {
    viewLogin.classList.add("hidden");
    viewMain.classList.remove("hidden");
    $("site-title").textContent = status.site_name || status.site_code || "Sede";
    $("session-user").textContent = status.auth_required
      ? "Sesión activa"
      : "Lab abierto (sin clave de consola)";
    $("isapi-user").value = status.isapi_user || "admin";
    $("scan-seed").value = status.scan_seed || "192.168.10.200";
    $("footer-meta").textContent = `Fuente: ${status.source || "—"} · sede ${status.site_code || "—"}`;
    applyConsoleAuthHints(status);
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

  $("form-console-auth").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    setError(null);
    const neu = $("console-new").value;
    const conf = $("console-confirm").value;
    if (neu !== conf) {
      setError("La nueva contraseña y la confirmación no coinciden.");
      return;
    }
    try {
      const result = await api("/api/edge-admin/change-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          current_password: $("console-current").value,
          new_password: neu,
          new_username: $("console-user").value.trim() || "admin",
        }),
      });
      if (result.token) setToken(result.token);
      $("console-current").value = "";
      $("console-new").value = "";
      $("console-confirm").value = "";
      setNotice(result.message);
      const status = await loadStatus();
      $("session-user").textContent = "Sesión activa";
      applyConsoleAuthHints(status);
    } catch (e) {
      setError(e.message);
    }
  });

  $("btn-refresh").addEventListener("click", () => {
    setNotice(null);
    loadDevices().catch((e) => setError(e.message));
  });

  $("btn-add").addEventListener("click", () => {
    editingDeviceId = null;
    $("add-device-id").value = "";
    $("form-add-title").textContent = "Nuevo dispositivo";
    $("btn-save-device").textContent = "Guardar dispositivo";
    $("form-add").classList.remove("hidden");
  });
  $("btn-add-cancel").addEventListener("click", () => resetAddForm());

  $("form-add").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    setError(null);
    const host = $("add-host").value.trim();
    const port = Number($("add-port").value);
    const location = $("add-location").value.trim();
    const deviceId = ($("add-device-id").value || editingDeviceId || "").trim();
    try {
      let result;
      if (deviceId) {
        result = await api(`/api/biometrico/devices/${encodeURIComponent(deviceId)}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ host, port, location, device_id: deviceId }),
        });
      } else {
        result = await api("/api/biometrico/devices", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ host, port, location }),
        });
      }
      setNotice(result.message);
      resetAddForm();
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
      await loadDevices();
      if (result.devices?.length) {
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
