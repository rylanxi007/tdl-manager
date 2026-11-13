(() => {
  "use strict";

  const state = {
    data: null,
    activeTab: "active",
    search: "",
    selectedMedia: new Set(),
    dialogs: [],
    selectedDialogs: new Set(),
    dialogSearch: "",
    pollTimer: null,
    busy: false,
  };

  const byId = (id) => document.getElementById(id);

  const elements = {
    activeTaskList: byId("active-task-list"),
    completedTaskList: byId("completed-task-list"),
    activeEmpty: byId("active-empty"),
    completedEmpty: byId("completed-empty"),
    activePanel: byId("active-panel"),
    completedPanel: byId("completed-panel"),
    metricSpeed: byId("metric-speed"),
    metricSpeedNote: byId("metric-speed-note"),
    metricActive: byId("metric-active"),
    metricCompleted: byId("metric-completed"),
    metricSavePath: byId("metric-save-path"),
    connectionPill: byId("connection-pill"),
    connectionLabel: byId("connection-label"),
    sidebarStatus: byId("sidebar-status"),
    sidebarStatusDot: byId("sidebar-status-dot"),
    primaryAction: byId("primary-action"),
    refreshButton: byId("refresh-button"),
    stopButton: byId("stop-button"),
    mediaChips: byId("media-chips"),
    configStatus: byId("config-status"),
    apiIdValue: byId("api-id-value"),
    apiHashValue: byId("api-hash-value"),
    chatCountValue: byId("chat-count-value"),
    loginNote: byId("login-note"),
    lastUpdated: byId("last-updated"),
    taskSearch: byId("task-search"),
    settingsForm: byId("settings-form"),
    apiIdInput: byId("api-id-input"),
    apiHashInput: byId("api-hash-input"),
    chatsInput: byId("chats-input"),
    savePathInput: byId("save-path-input"),
    maxTaskInput: byId("max-task-input"),
    mediaOptions: byId("media-options"),
    mediaSelectionCount: byId("media-selection-count"),
    dialogList: byId("dialog-list"),
    dialogState: byId("dialog-state"),
    dialogSearch: byId("dialog-search"),
    dialogSelectionCount: byId("dialog-selection-count"),
    saveDialogsButton: byId("save-dialogs-button"),
    toastRegion: byId("toast-region"),
  };

  const escapeHtml = (value) =>
    String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");

  async function api(path, options = {}) {
    const response = await fetch(path, {
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {}),
      },
      ...options,
    });
    let payload = {};
    try {
      payload = await response.json();
    } catch {
      payload = {};
    }
    if (!response.ok) {
      throw new Error(payload.message || `请求失败 (${response.status})`);
    }
    return payload;
  }

  function refreshIcons() {
    if (window.lucide) {
      window.lucide.createIcons({
        attrs: {
          "aria-hidden": "true",
        },
      });
    }
  }

  function toast(message, type = "info") {
    const item = document.createElement("div");
    item.className = `toast${type === "error" ? " is-error" : ""}`;

    const icon = document.createElement("i");
    icon.dataset.lucide = type === "error" ? "circle-alert" : "circle-check";
    const text = document.createElement("span");
    text.textContent = message;

    item.append(icon, text);
    elements.toastRegion.append(item);
    refreshIcons();
    window.setTimeout(() => item.remove(), 4800);
  }

  function setBusy(value) {
    state.busy = value;
    elements.primaryAction.disabled = value;
    elements.refreshButton.disabled = value;
  }

  function setStatusDot(element, mode) {
    element.classList.remove("is-online", "is-warning", "is-error");
    if (mode === "online") element.classList.add("is-online");
    if (mode === "warning") element.classList.add("is-warning");
    if (mode === "error") element.classList.add("is-error");
  }

  function setButton(button, iconName, label) {
    button.innerHTML = `<i data-lucide="${iconName}"></i><span>${escapeHtml(
      label
    )}</span>`;
  }

  function mediaLabel(id) {
    const option = (state.data?.media_options || []).find(
      (item) => item.id === id
    );
    return option?.label || id;
  }

  function fileIcon(filename) {
    const extension = String(filename || "")
      .split(".")
      .pop()
      .toLowerCase();
    if (["mp4", "mkv", "mov", "webm", "avi"].includes(extension)) {
      return "film";
    }
    if (["jpg", "jpeg", "png", "webp", "gif", "heic"].includes(extension)) {
      return "image";
    }
    if (["mp3", "m4a", "flac", "wav", "ogg"].includes(extension)) {
      return "audio-lines";
    }
    return "file";
  }

  function matchesSearch(task) {
    if (!state.search) return true;
    const search = state.search.toLocaleLowerCase();
    return [task.filename, task.chat, task.message_id]
      .join(" ")
      .toLocaleLowerCase()
      .includes(search);
  }

  function renderTaskRows(tasks, input) {
    return tasks
      .map((task) => {
        const filename = task.filename || `媒体文件 ${task.message_id}`;
        const progress = Math.min(100, Math.max(0, Number(task.progress) || 0));
        return `
          <tr>
            <td>
              <div class="file-cell">
                <span class="file-icon"><i data-lucide="${fileIcon(
                  filename
                )}"></i></span>
                <span class="file-copy">
                  <span class="file-name" title="${escapeHtml(filename)}">${escapeHtml(
                    filename
                  )}</span>
                  <span class="file-meta">消息 ${escapeHtml(
                    task.message_id || "-"
                  )}</span>
                </span>
              </div>
            </td>
            <td><span class="source-name" title="${escapeHtml(
              task.chat
            )}">${escapeHtml(task.chat || "-")}</span></td>
            <td>
              <div class="progress-copy">
                <span>${progress.toFixed(1)}%</span>
                <span>${escapeHtml(task.speed || "0 B/s")}</span>
              </div>
              <div class="progress-track">
                <div class="progress-fill ${progress < 20 ? "is-low" : ""}"
                  style="width: ${progress}%"></div>
              </div>
            </td>
            <td><span class="speed-value">${escapeHtml(
              task.speed || "0 B/s"
            )}</span></td>
            <td>${escapeHtml(task.total_size || "-")}</td>
          </tr>`;
      })
      .join("");
  }

  function renderCompletedRows(tasks) {
    return tasks
      .map((task) => {
        const filename = task.filename || `媒体文件 ${task.message_id}`;
        return `
          <tr>
            <td>
              <div class="file-cell">
                <span class="file-icon"><i data-lucide="${fileIcon(
                  filename
                )}"></i></span>
                <span class="file-copy">
                  <span class="file-name" title="${escapeHtml(filename)}">${escapeHtml(
                    filename
                  )}</span>
                  <span class="file-meta">消息 ${escapeHtml(
                    task.message_id || "-"
                  )}</span>
                </span>
              </div>
            </td>
            <td><span class="source-name">${escapeHtml(task.chat || "-")}</span></td>
            <td>${escapeHtml(task.total_size || "-")}</td>
            <td><span class="save-path" title="${escapeHtml(
              task.save_path
            )}">${escapeHtml(task.save_path || "-")}</span></td>
          </tr>`;
      })
      .join("");
  }

  function renderTasks(data) {
    const activeTasks = (data.tasks || []).filter(matchesSearch);
    const completedTasks = (data.completed || []).filter(matchesSearch);

    elements.activeTaskList.innerHTML = renderTaskRows(activeTasks);
    elements.completedTaskList.innerHTML = renderCompletedRows(completedTasks);
    elements.activeEmpty.hidden = activeTasks.length > 0;
    elements.completedEmpty.hidden = completedTasks.length > 0;

    if (state.search && activeTasks.length === 0) {
      elements.activeEmpty.querySelector("strong").textContent =
        "没有匹配的下载任务";
      elements.activeEmpty.querySelector("span:last-child").textContent =
        "请尝试其他文件名或频道名称。";
    } else {
      elements.activeEmpty.querySelector("strong").textContent =
        "暂无下载任务";
      elements.activeEmpty.querySelector("span:last-child").textContent =
        "启动下载器后，任务会显示在这里。";
    }

    byId("active-panel").classList.toggle(
      "is-active",
      state.activeTab === "active"
    );
  }

  function renderConnection(data) {
    const { downloader, config } = data;
    let mode = "error";
    let connectionText = "未连接";
    let sidebarText = "下载器未启动";

    if (downloader.online) {
      mode = "online";
      connectionText = downloader.state_label;
      sidebarText = downloader.session_ready ? "Telegram 已连接" : "等待登录";
    } else if (config.ready) {
      mode = "warning";
      connectionText = "配置就绪";
      sidebarText = "等待启动";
    } else {
      connectionText = "待配置";
      sidebarText = "需要连接设置";
    }

    elements.connectionLabel.textContent = connectionText;
    elements.sidebarStatus.textContent = sidebarText;
    setStatusDot(elements.connectionPill.querySelector(".status-dot"), mode);
    setStatusDot(elements.sidebarStatusDot, mode);
    elements.loginNote.hidden = downloader.state !== "login";
  }

  function renderConfig(data) {
    const { config } = data;
    elements.configStatus.textContent = config.ready ? "配置就绪" : "待配置";
    elements.configStatus.classList.toggle("is-ready", config.ready);
    elements.apiIdValue.textContent = config.api_id || "未填写";
    elements.apiHashValue.textContent = config.api_hash_configured
      ? "已安全配置"
      : "未填写";
    elements.chatCountValue.textContent = `${config.chats.length} 个`;
    elements.metricSavePath.textContent = config.save_path || "downloads";
    elements.metricSavePath.title = config.save_path || "downloads";

    const selected = config.media_types || [];
    if (selected.length === 0) {
      elements.mediaChips.innerHTML =
        '<span class="media-chip is-empty">未选择媒体类型</span>';
    } else {
      elements.mediaChips.innerHTML = selected
        .map(
          (mediaType) =>
            `<span class="media-chip">${escapeHtml(mediaLabel(mediaType))}</span>`
        )
        .join("");
    }
  }

  function renderSummary(data) {
    elements.metricSpeed.textContent = data.summary.speed || "0 B/s";
    elements.metricSpeedNote.textContent = data.summary.active_count
      ? `${data.summary.active_count} 个任务正在传输`
      : "等待任务";
    elements.metricActive.textContent = data.summary.active_count;
    elements.metricCompleted.textContent = data.summary.completed_count;

    const date = new Date(data.updated_at);
    elements.lastUpdated.textContent = Number.isNaN(date.valueOf())
      ? "--:--:--"
      : date.toLocaleTimeString("zh-CN", { hour12: false });

    elements.stopButton.disabled = !data.downloader.managed;
    if (data.downloader.state === "login") {
      setButton(elements.primaryAction, "terminal", "等待登录");
      elements.primaryAction.disabled = true;
    } else if (data.downloader.online && data.downloader.state === "paused") {
      setButton(elements.primaryAction, "play", "继续下载");
      elements.primaryAction.disabled = state.busy;
    } else if (data.downloader.online && data.downloader.state === "running") {
      setButton(elements.primaryAction, "pause", "暂停任务");
      elements.primaryAction.disabled = state.busy;
    } else {
      setButton(elements.primaryAction, "play", "启动下载");
      elements.primaryAction.disabled = state.busy;
    }
  }

  function render(data) {
    state.data = data;
    renderSummary(data);
    renderConnection(data);
    renderConfig(data);
    renderTasks(data);
    refreshIcons();
  }

  async function refresh(options = {}) {
    try {
      const data = await api("/api/status");
      render(data);
    } catch (error) {
      if (!options.silent) {
        toast(error.message, "error");
      }
      elements.connectionLabel.textContent = "连接失败";
      elements.sidebarStatus.textContent = "管理服务无法连接";
      setStatusDot(
        elements.connectionPill.querySelector(".status-dot"),
        "error"
      );
      setStatusDot(elements.sidebarStatusDot, "error");
    }
  }

  async function primaryAction() {
    if (!state.data) return;
    if (!state.data.config.ready) {
      openModal("settings-modal");
      toast("请先填写 API 和聊天 ID。");
      return;
    }

    const { downloader } = state.data;
    setBusy(true);
    try {
      if (!downloader.online) {
        const result = await api("/api/downloader/start", { method: "POST" });
        toast(result.message);
      } else {
        const nextState =
          downloader.state === "paused" ? "continue" : "pause";
        const result = await api("/api/downloads/state", {
          method: "POST",
          body: JSON.stringify({ state: nextState }),
        });
        toast(result.message);
      }
      await refresh({ silent: true });
    } catch (error) {
      toast(error.message, "error");
    } finally {
      setBusy(false);
      render(state.data);
    }
  }

  async function stopDownloader() {
    closeModal("stop-modal");
    setBusy(true);
    try {
      const result = await api("/api/downloader/stop", { method: "POST" });
      toast(result.message);
      await refresh({ silent: true });
    } catch (error) {
      toast(error.message, "error");
    } finally {
      setBusy(false);
    }
  }

  function openModal(id) {
    byId(id).hidden = false;
    document.body.classList.add("modal-open");
    const focusTarget = byId(id).querySelector("input, textarea, button");
    window.setTimeout(() => focusTarget?.focus(), 30);
  }

  function closeModal(id) {
    byId(id).hidden = true;
    if (!document.querySelector(".modal-backdrop:not([hidden])")) {
      document.body.classList.remove("modal-open");
    }
  }

  function closeAllModals() {
    document
      .querySelectorAll(".modal-backdrop:not([hidden])")
      .forEach((modal) => {
        modal.hidden = true;
      });
    document.body.classList.remove("modal-open");
  }

  function populateSettings() {
    if (!state.data) return;
    const { config } = state.data;
    elements.apiIdInput.value = config.api_id || "";
    elements.apiHashInput.value = "";
    elements.apiHashInput.placeholder = config.api_hash_configured
      ? "已配置，留空保持不变"
      : "填写 my.telegram.org 提供的 API Hash";
    elements.chatsInput.value = config.chats.join("\n");
    elements.savePathInput.value = config.save_path || "";
    elements.maxTaskInput.value = config.max_download_task || 5;
  }

  async function saveSettings(event) {
    event.preventDefault();
    if (!state.data) return;

    const apiId = elements.apiIdInput.value.trim();
    const apiHash = elements.apiHashInput.value.trim();
    const chats = elements.chatsInput.value
      .split(/\r?\n|,/)
      .map((item) => item.trim())
      .filter(Boolean);
    const selectedMedia = state.data.config.media_types.length
      ? state.data.config.media_types
      : state.data.media_options.map((item) => item.id);

    const submitButton = elements.settingsForm.querySelector(
      'button[type="submit"]'
    );
    submitButton.disabled = true;
    try {
      const result = await api("/api/config", {
        method: "POST",
        body: JSON.stringify({
          api_id: apiId,
          api_hash: apiHash,
          chats,
          media_types: selectedMedia,
          save_path: elements.savePathInput.value.trim(),
          max_download_task: Number(elements.maxTaskInput.value || 5),
        }),
      });
      closeModal("settings-modal");
      toast(result.message);
      await refresh({ silent: true });
      if (state.data?.downloader.managed) {
        toast("新配置已保存，停止并重新启动下载器后生效。");
      }
    } catch (error) {
      toast(error.message, "error");
    } finally {
      submitButton.disabled = false;
    }
  }

  function updateMediaCount() {
    elements.mediaSelectionCount.textContent =
      `已选择 ${state.selectedMedia.size} 项`;
  }

  function renderMediaModal() {
    if (!state.data) return;
    state.selectedMedia = new Set(state.data.config.media_types || []);
    elements.mediaOptions.innerHTML = state.data.media_options
      .map(
        (item) => `
          <label class="media-option ${
            state.selectedMedia.has(item.id) ? "is-selected" : ""
          }" data-media-id="${escapeHtml(item.id)}">
            <input type="checkbox" value="${escapeHtml(item.id)}" ${
          state.selectedMedia.has(item.id) ? "checked" : ""
        }>
            <span class="checkbox-mark"><i data-lucide="check"></i></span>
            <span class="media-option-copy">
              <strong>${escapeHtml(item.label)}</strong>
              <span>${escapeHtml(item.description)}</span>
            </span>
          </label>`
      )
      .join("");
    updateMediaCount();
    refreshIcons();
  }

  function toggleMediaOption(option) {
    const mediaId = option.dataset.mediaId;
    const checkbox = option.querySelector('input[type="checkbox"]');
    checkbox.checked = !checkbox.checked;
    option.classList.toggle("is-selected", checkbox.checked);
    if (checkbox.checked) {
      state.selectedMedia.add(mediaId);
    } else {
      state.selectedMedia.delete(mediaId);
    }
    updateMediaCount();
  }

  async function saveMediaSelection() {
    if (state.selectedMedia.size === 0) {
      toast("请至少选择一种媒体类型。", "error");
      return;
    }
    const button = byId("save-media-button");
    button.disabled = true;
    try {
      const result = await api("/api/config", {
        method: "POST",
        body: JSON.stringify({
          media_types: [...state.selectedMedia],
        }),
      });
      closeModal("media-modal");
      toast(result.message);
      await refresh({ silent: true });
    } catch (error) {
      toast(error.message, "error");
    } finally {
      button.disabled = false;
    }
  }

  function dialogTypeLabel(type) {
    return (
      {
        private: "私聊",
        bot: "机器人",
        group: "群组",
        supergroup: "超级群组",
        channel: "频道",
      }[type] || "会话"
    );
  }

  function updateDialogSelectionCount() {
    elements.dialogSelectionCount.textContent =
      `已选择 ${state.selectedDialogs.size} 个会话`;
  }

  function renderDialogState(message, loading = false) {
    elements.dialogState.hidden = false;
    elements.dialogState.classList.toggle("is-loading", loading);
    elements.dialogState.innerHTML = `
      <span class="dialog-state-icon">
        <i data-lucide="${loading ? "loader-circle" : "message-circle-more"}"></i>
      </span>
      <strong>${loading ? "正在读取 Telegram 会话" : "暂时无法读取会话"}</strong>
      <span>${escapeHtml(message)}</span>`;
    refreshIcons();
  }

  function renderDialogs() {
    const query = state.dialogSearch.toLocaleLowerCase();
    const dialogs = state.dialogs.filter((dialog) => {
      if (!query) return true;
      return [dialog.title, dialog.username, dialog.id]
        .join(" ")
        .toLocaleLowerCase()
        .includes(query);
    });

    if (dialogs.length === 0) {
      elements.dialogState.hidden = false;
      elements.dialogState.classList.remove("is-loading");
      elements.dialogState.innerHTML = `
        <span class="dialog-state-icon"><i data-lucide="search-x"></i></span>
        <strong>没有匹配的会话</strong>
        <span>请尝试群组名称、用户名或数字 ID。</span>`;
      elements.dialogList.innerHTML = "";
      refreshIcons();
      return;
    }

    elements.dialogState.hidden = true;
    elements.dialogList.innerHTML = dialogs
      .map((dialog) => {
        const selected = state.selectedDialogs.has(dialog.id);
        const meta = [
          dialog.username ? `@${dialog.username}` : "",
          `ID ${dialog.id}`,
        ]
          .filter(Boolean)
          .join(" · ");
        return `
          <label class="dialog-option ${selected ? "is-selected" : ""}"
            data-dialog-id="${escapeHtml(dialog.id)}">
            <input type="checkbox" ${selected ? "checked" : ""}>
            <span class="dialog-avatar">
              <i data-lucide="${
                dialog.type === "channel" ? "megaphone" : "message-circle"
              }"></i>
            </span>
            <span class="dialog-copy">
              <strong>${escapeHtml(dialog.title || dialog.id)}</strong>
              <span>${escapeHtml(meta)}</span>
            </span>
            <span class="dialog-type">${escapeHtml(
              dialogTypeLabel(dialog.type)
            )}</span>
            <span class="checkbox-mark"><i data-lucide="check"></i></span>
          </label>`;
      })
      .join("");
    refreshIcons();
  }

  async function openDialogsModal() {
    state.selectedDialogs = new Set(state.data?.config.chats || []);
    state.dialogs = [];
    state.dialogSearch = "";
    elements.dialogSearch.value = "";
    elements.dialogList.innerHTML = "";
    elements.saveDialogsButton.disabled = true;
    updateDialogSelectionCount();
    openModal("dialogs-modal");
    renderDialogState("正在获取你的群组、频道和私聊列表…", true);

    try {
      const result = await api("/api/dialogs");
      state.dialogs = result.dialogs || [];
      elements.saveDialogsButton.disabled = state.selectedDialogs.size === 0;
      if (state.dialogs.length === 0) {
        renderDialogState("当前 Telegram 账号没有可选择的会话。");
      } else {
        renderDialogs();
      }
    } catch (error) {
      renderDialogState(error.message);
      toast(error.message, "error");
    }
  }

  function toggleDialogOption(option) {
    const dialogId = option.dataset.dialogId;
    const checkbox = option.querySelector('input[type="checkbox"]');
    checkbox.checked = !checkbox.checked;
    option.classList.toggle("is-selected", checkbox.checked);
    if (checkbox.checked) {
      state.selectedDialogs.add(dialogId);
    } else {
      state.selectedDialogs.delete(dialogId);
    }
    elements.saveDialogsButton.disabled = state.selectedDialogs.size === 0;
    updateDialogSelectionCount();
  }

  async function saveDialogSelection() {
    if (state.selectedDialogs.size === 0) {
      toast("请至少选择一个群组或对话。", "error");
      return;
    }

    elements.saveDialogsButton.disabled = true;
    try {
      const selected = [...state.selectedDialogs];
      const result = await api("/api/chats/select", {
        method: "POST",
        body: JSON.stringify({ chats: selected }),
      });
      elements.chatsInput.value = selected.join("\n");
      closeModal("dialogs-modal");
      closeModal("settings-modal");
      toast(result.message);
      await refresh({ silent: true });
    } catch (error) {
      toast(error.message, "error");
    } finally {
      elements.saveDialogsButton.disabled = state.selectedDialogs.size === 0;
    }
  }

  function bindEvents() {
    elements.primaryAction.addEventListener("click", primaryAction);
    elements.refreshButton.addEventListener("click", () => refresh());
    elements.stopButton.addEventListener("click", () =>
      openModal("stop-modal")
    );
    byId("confirm-stop").addEventListener("click", stopDownloader);
    elements.settingsForm.addEventListener("submit", saveSettings);
    byId("save-media-button").addEventListener("click", saveMediaSelection);
    byId("open-dialogs-button").addEventListener("click", openDialogsModal);
    byId("save-dialogs-button").addEventListener(
      "click",
      saveDialogSelection
    );
    byId("dialog-clear").addEventListener("click", () => {
      state.selectedDialogs.clear();
      elements.saveDialogsButton.disabled = true;
      updateDialogSelectionCount();
      renderDialogs();
    });

    document.querySelectorAll('[data-action="open-settings"]').forEach((button) => {
      button.addEventListener("click", () => {
        populateSettings();
        openModal("settings-modal");
      });
    });
    document.querySelectorAll('[data-action="open-media"]').forEach((button) => {
      button.addEventListener("click", () => {
        renderMediaModal();
        openModal("media-modal");
      });
    });

    document.querySelectorAll("[data-close-modal]").forEach((button) => {
      button.addEventListener("click", () =>
        closeModal(button.closest(".modal-backdrop").id)
      );
    });

    document.querySelectorAll(".modal-backdrop").forEach((backdrop) => {
      backdrop.addEventListener("click", (event) => {
        if (event.target === backdrop) closeModal(backdrop.id);
      });
    });

    document.querySelectorAll(".segmented [data-tab]").forEach((button) => {
      button.addEventListener("click", () => {
        state.activeTab = button.dataset.tab;
        document.querySelectorAll(".segmented [data-tab]").forEach((item) => {
          const selected = item === button;
          item.classList.toggle("is-active", selected);
          item.setAttribute("aria-selected", String(selected));
        });
        elements.activePanel.hidden = state.activeTab !== "active";
        elements.completedPanel.hidden = state.activeTab !== "completed";
        elements.completedPanel.classList.toggle(
          "completed-panel",
          state.activeTab === "completed"
        );
      });
    });

    elements.taskSearch.addEventListener("input", (event) => {
      state.search = event.target.value.trim();
      if (state.data) renderTasks(state.data);
      refreshIcons();
    });

    elements.mediaOptions.addEventListener("click", (event) => {
      const option = event.target.closest(".media-option");
      if (!option) return;
      event.preventDefault();
      toggleMediaOption(option);
    });

    elements.dialogList.addEventListener("click", (event) => {
      const option = event.target.closest(".dialog-option");
      if (!option) return;
      event.preventDefault();
      toggleDialogOption(option);
    });

    elements.dialogSearch.addEventListener("input", (event) => {
      state.dialogSearch = event.target.value.trim();
      if (state.dialogs.length) renderDialogs();
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") closeAllModals();
    });

    document.addEventListener("visibilitychange", () => {
      if (document.hidden) {
        window.clearInterval(state.pollTimer);
        state.pollTimer = null;
      } else if (!state.pollTimer) {
        refresh({ silent: true });
        state.pollTimer = window.setInterval(
          () => refresh({ silent: true }),
          1500
        );
      }
    });
  }

  async function init() {
    bindEvents();
    refreshIcons();
    await refresh();
    state.pollTimer = window.setInterval(() => refresh({ silent: true }), 1500);
  }

  init();
})();
