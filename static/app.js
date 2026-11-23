(() => {
  const state = {
    fonts: [],
    styles: [],
    accounts: [],
    activeAccountId: null,
    accountSessions: {},
    currentJobId: null,
    pollTimer: null,
    selectedStyle: 'hormozi',
    selectedFont: 'montserrat',
    cropMode: 'fill',
    previewWordIdx: 0,
    previewWords: ['ЭТОТ', 'МОМЕНТ', 'ВЗОРВАЛ', 'ТИКТОК!'],
  };

  // Multi-Account TikTok Studio elements
  const accountsPills = document.getElementById('accountsPills');
  const activeAccountSub = document.getElementById('activeAccountSub');
  const btnAddAccount = document.getElementById('btnAddAccount');
  const btnSavePreset = document.getElementById('btnSavePreset');
  const btnOpenTiktokLogin = document.getElementById('btnOpenTiktokLogin');
  const btnEditAccount = document.getElementById('btnEditAccount');
  const accountModal = document.getElementById('accountModal');
  const accountBackdrop = document.getElementById('accountBackdrop');
  const accountModalTitle = document.getElementById('accountModalTitle');
  const btnCloseAccountModal = document.getElementById('btnCloseAccountModal');
  const btnCancelAccount = document.getElementById('btnCancelAccount');
  const btnSaveAccount = document.getElementById('btnSaveAccount');
  const btnAccountLogout = document.getElementById('btnAccountLogout');
  const btnAccountDelete = document.getElementById('btnAccountDelete');
  const accNameInput = document.getElementById('accNameInput');
  const accHandleInput = document.getElementById('accHandleInput');
  const accHashtagsInput = document.getElementById('accHashtagsInput');
  const accTemplateInput = document.getElementById('accTemplateInput');
  const accColorInput = document.getElementById('accColorInput');

  // DOM elements
  const sourceTabs = document.getElementById('sourceTabs');
  const urlPanel = document.getElementById('urlPanel');
  const filePanel = document.getElementById('filePanel');
  const radarPanel = document.getElementById('radarPanel');
  const livePanel = document.getElementById('livePanel');
  const radarStreamerInput = document.getElementById('radarStreamerInput');
  const radarPeriodSelect = document.getElementById('radarPeriodSelect');
  const btnSearchTwitchClips = document.getElementById('btnSearchTwitchClips');
  const radarMeta = document.getElementById('radarMeta');
  const btnRadarTop5Batch = document.getElementById('btnRadarTop5Batch');
  const radarResultsGrid = document.getElementById('radarResultsGrid');
  const liveStreamUrlInput = document.getElementById('liveStreamUrlInput');
  const liveDurationSelect = document.getElementById('liveDurationSelect');
  const btnCaptureLive = document.getElementById('btnCaptureLive');
  const liveStatusText = document.getElementById('liveStatusText');
  const hypeTimelineBox = document.getElementById('hypeTimelineBox');
  const hypeTimelineSource = document.getElementById('hypeTimelineSource');
  const hypeTimelineBars = document.getElementById('hypeTimelineBars');
  const autoCleanWavToggle = document.getElementById('autoCleanWavToggle');
  const urlInput = document.getElementById('urlInput');
  const btnProbeUrl = document.getElementById('btnProbeUrl');
  const dropZone = document.getElementById('dropZone');
  const fileInput = document.getElementById('fileInput');
  const btnPickFile = document.getElementById('btnPickFile');
  const btnChangeVideo = document.getElementById('btnChangeVideo');
  const uploadProgressWrap = document.getElementById('uploadProgressWrap');
  const uploadFileName = document.getElementById('uploadFileName');
  const uploadPct = document.getElementById('uploadPct');
  const uploadBar = document.getElementById('uploadBar');
  const videoReadyBanner = document.getElementById('videoReadyBanner');
  const readyThumb = document.getElementById('readyThumb');
  const readyFileName = document.getElementById('readyFileName');
  const readyFileMeta = document.getElementById('readyFileMeta');
  const readyBadges = document.getElementById('readyBadges');

  const clipCount = document.getElementById('clipCount');
  const clipCountVal = document.getElementById('clipCountVal');
  const whisperModel = document.getElementById('whisperModel');
  const minDuration = document.getElementById('minDuration');
  const maxDuration = document.getElementById('maxDuration');
  const cropModeGroup = document.getElementById('cropModeGroup');
  const splitStreamSettings = document.getElementById('splitStreamSettings');
  const useWebcamPhotoToggle = document.getElementById('useWebcamPhotoToggle');
  const webcamPhotoRow = document.getElementById('webcamPhotoRow');
  const webcamCropRow = document.getElementById('webcamCropRow');
  const webcamPhotoSelect = document.getElementById('webcamPhotoSelect');
  const avatarFileInput = document.getElementById('avatarFileInput');
  const btnUploadAvatar = document.getElementById('btnUploadAvatar');
  const webcamCorner = document.getElementById('webcamCorner');
  const webcamSize = document.getElementById('webcamSize');
  const webcamSizeVal = document.getElementById('webcamSizeVal');
  const styleCards = document.getElementById('styleCards');
  const fontSelect = document.getElementById('fontSelect');
  const fontSize = document.getElementById('fontSize');
  const subPosition = document.getElementById('subPosition');
  const enableSubtitlesToggle = document.getElementById('enableSubtitlesToggle');
  const uppercaseToggle = document.getElementById('uppercaseToggle');
  const hookBannerToggle = document.getElementById('hookBannerToggle');
  const hookPositionSelect = document.getElementById('hookPositionSelect');
  const hookFontSize = document.getElementById('hookFontSize');
  const hookTextColor = document.getElementById('hookTextColor');
  const hookBgColor = document.getElementById('hookBgColor');
  const hookBorderColor = document.getElementById('hookBorderColor');
  const hookTransparentBg = document.getElementById('hookTransparentBg');
  const searchChatToggle = document.getElementById('searchChatToggle');
  const searchLaughterToggle = document.getElementById('searchLaughterToggle');
  const searchScreamsToggle = document.getElementById('searchScreamsToggle');
  const useAiDirectorToggle = document.getElementById('useAiDirectorToggle');
  const jumpCutsToggle = document.getElementById('jumpCutsToggle');
  const fps60Toggle = document.getElementById('fps60Toggle');
  const videoEnhanceToggle = document.getElementById('videoEnhanceToggle');
  const adBannerToggle = document.getElementById('adBannerToggle');
  const adBannerBox = document.getElementById('adBannerBox');
  const adModeSelect = document.getElementById('adModeSelect');
  const adBannerSelect = document.getElementById('adBannerSelect');
  const adBannerFileInput = document.getElementById('adBannerFileInput');
  const btnUploadAdBanner = document.getElementById('btnUploadAdBanner');
  const adAudioRow = document.getElementById('adAudioRow');
  const adAudioSelect = document.getElementById('adAudioSelect');
  const adAudioFileInput = document.getElementById('adAudioFileInput');
  const btnUploadAdAudio = document.getElementById('btnUploadAdAudio');
  const previewAdBanner = document.getElementById('previewAdBanner');
  const previewAdImg = document.getElementById('previewAdImg');
  const previewAdBadge = document.getElementById('previewAdBadge');
  const satisfyingToggle = document.getElementById('satisfyingToggle');
  const satisfyingBox = document.getElementById('satisfyingBox');
  const satisfyingSelect = document.getElementById('satisfyingSelect');
  const satisfyingFileInput = document.getElementById('satisfyingFileInput');
  const btnUploadSatisfying = document.getElementById('btnUploadSatisfying');
  const autoCoverToggle = document.getElementById('autoCoverToggle');
  const uniquifyToggle = document.getElementById('uniquifyToggle');
  const btnCompileSelected = document.getElementById('btnCompileSelected');
  const selectedClipsCount = document.getElementById('selectedClipsCount');
  const btnExportFolder = document.getElementById('btnExportFolder');
  const btnDashboard = document.getElementById('btnDashboard');
  const dashboardModal = document.getElementById('dashboardModal');
  const dashboardBackdrop = document.getElementById('dashboardBackdrop');
  const btnCloseDashboard = document.getElementById('btnCloseDashboard');
  const dashboardBody = document.getElementById('dashboardBody');
  const dashTabs = document.getElementById('dashTabs');
  const dashPlanBody = document.getElementById('dashPlanBody');
  const dashDiskBody = document.getElementById('dashDiskBody');
  const btnToggleSafeZone = document.getElementById('btnToggleSafeZone');
  const safeZoneOverlay = document.getElementById('safeZoneOverlay');
  const btnToggleBatch = document.getElementById('btnToggleBatch');
  const batchQueueBox = document.getElementById('batchQueueBox');
  const batchUrlsInput = document.getElementById('batchUrlsInput');
  const btnStartBatch = document.getElementById('btnStartBatch');
  const batchSummary = document.getElementById('batchSummary');
  const batchStatusList = document.getElementById('batchStatusList');
  const manualTimecodesInput = document.getElementById('manualTimecodesInput');
  const outroToggle = document.getElementById('outroToggle');
  const outroBox = document.getElementById('outroBox');
  const outroSelect = document.getElementById('outroSelect');
  const outroFileInput = document.getElementById('outroFileInput');
  const btnUploadOutro = document.getElementById('btnUploadOutro');
  const btnOpenWebcamCrop = document.getElementById('btnOpenWebcamCrop');
  const webcamRectBadge = document.getElementById('webcamRectBadge');
  const btnResetWebcamRect = document.getElementById('btnResetWebcamRect');
  const webcamCropModal = document.getElementById('webcamCropModal');
  const webcamCropBackdrop = document.getElementById('webcamCropBackdrop');
  const btnCloseWebcamCrop = document.getElementById('btnCloseWebcamCrop');
  const btnCancelWebcamCrop = document.getElementById('btnCancelWebcamCrop');
  const btnSaveWebcamCrop = document.getElementById('btnSaveWebcamCrop');
  const webcamCropCanvas = document.getElementById('webcamCropCanvas');
  const webcamCropCoords = document.getElementById('webcamCropCoords');
  const presetLibraryBar = document.getElementById('presetLibraryBar');
  const btnExportPresetJson = document.getElementById('btnExportPresetJson');
  const btnImportPresetJson = document.getElementById('btnImportPresetJson');
  const importPresetJsonInput = document.getElementById('importPresetJsonInput');
  const btnToggleNetOpts = document.getElementById('btnToggleNetOpts');
  const netOptsBox = document.getElementById('netOptsBox');
  const ytCookiesSelect = document.getElementById('ytCookiesSelect');
  const ytProxyInput = document.getElementById('ytProxyInput');
  const lowCpuToggle = document.getElementById('lowCpuToggle');
  const btnOpenBlurBox = document.getElementById('btnOpenBlurBox');
  const blurRectBadge = document.getElementById('blurRectBadge');
  const btnResetBlurRect = document.getElementById('btnResetBlurRect');
  const btnBestOf60s = document.getElementById('btnBestOf60s');
  const ollamaRow = document.getElementById('ollamaRow');
  const ollamaSelect = document.getElementById('ollamaSelect');
  const geminiKeyInput = document.getElementById('geminiKeyInput');
  const btnCheckGeminiKey = document.getElementById('btnCheckGeminiKey');
  const geminiKeyStatus = document.getElementById('geminiKeyStatus');
  const customClipBar = document.getElementById('customClipBar');
  const customStartInput = document.getElementById('customStartInput');
  const customEndInput = document.getElementById('customEndInput');
  const btnCutCustom = document.getElementById('btnCutCustom');
  const hwBadge = document.getElementById('hwBadge');
  const watermarkInput = document.getElementById('watermarkInput');
  const bgMusicSelect = document.getElementById('bgMusicSelect');
  const musicFileInput = document.getElementById('musicFileInput');
  const btnUploadMusic = document.getElementById('btnUploadMusic');
  const btnStart = document.getElementById('btnStart');

  const previewScreen = document.getElementById('previewScreen');
  const previewSplitCam = document.getElementById('previewSplitCam');
  const previewSplitPhoto = document.getElementById('previewSplitPhoto');
  const previewSplitCamText = document.getElementById('previewSplitCamText');
  const previewCenterLabel = document.getElementById('previewCenterLabel');
  const previewWatermark = document.getElementById('previewWatermark');
  const previewHookBanner = document.getElementById('previewHookBanner');
  const liveSubBox = document.getElementById('liveSubBox');
  const liveSubText = document.getElementById('liveSubText');

  const progressSection = document.getElementById('progressSection');
  const procTitle = document.getElementById('procTitle');
  const procMessage = document.getElementById('procMessage');
  const procPct = document.getElementById('procPct');
  const procBar = document.getElementById('procBar');
  const procError = document.getElementById('procError');

  const resultsSection = document.getElementById('resultsSection');
  const resultsMeta = document.getElementById('resultsMeta');
  const btnShuffleMoments = document.getElementById('btnShuffleMoments');
  const btnDownloadAllZip = document.getElementById('btnDownloadAllZip');
  const clipsGrid = document.getElementById('clipsGrid');

  const clipEditorModal = document.getElementById('clipEditorModal');
  const editorBackdrop = document.getElementById('editorBackdrop');
  const btnCloseEditor = document.getElementById('btnCloseEditor');
  const btnCancelEditor = document.getElementById('btnCancelEditor');
  const btnSaveEditor = document.getElementById('btnSaveEditor');
  const editHookInput = document.getElementById('editHookInput');
  const editTrimStart = document.getElementById('editTrimStart');
  const editTrimEnd = document.getElementById('editTrimEnd');
  const editTranscriptInput = document.getElementById('editTranscriptInput');

  const btnHistory = document.getElementById('btnHistory');
  const historyCount = document.getElementById('historyCount');
  const btnChangelog = document.getElementById('btnChangelog');
  const changelogModal = document.getElementById('changelogModal');
  const changelogBackdrop = document.getElementById('changelogBackdrop');
  const btnCloseChangelog = document.getElementById('btnCloseChangelog');
  const changelogBody = document.getElementById('changelogBody');
  const btnCheckUpdates = document.getElementById('btnCheckUpdates');
  const updateBtnLabel = document.getElementById('updateBtnLabel');
  const updateDot = document.getElementById('updateDot');
  const appVersionPill = document.getElementById('appVersionPill');
  const updateBanner = document.getElementById('updateBanner');
  const updateMessage = document.getElementById('updateMessage');
  const updateBarWrap = document.getElementById('updateBarWrap');
  const updateBarFill = document.getElementById('updateBarFill');
  const btnInstallUpdate = document.getElementById('btnInstallUpdate');
  const btnOpenRelease = document.getElementById('btnOpenRelease');
  const btnDismissUpdate = document.getElementById('btnDismissUpdate');
  const updateModal = document.getElementById('updateModal');
  const updateModalBackdrop = document.getElementById('updateModalBackdrop');
  const btnCloseUpdateModal = document.getElementById('btnCloseUpdateModal');
  const btnUpdateLater = document.getElementById('btnUpdateLater');
  const updateModalTitle = document.getElementById('updateModalTitle');
  const updateModalVersions = document.getElementById('updateModalVersions');
  const updateModalStatus = document.getElementById('updateModalStatus');
  const updateModalProgressWrap = document.getElementById('updateModalProgressWrap');
  const updateModalBar = document.getElementById('updateModalBar');
  const updateModalSize = document.getElementById('updateModalSize');
  const updateModalSpeed = document.getElementById('updateModalSpeed');
  const updateModalNotesWrap = document.getElementById('updateModalNotesWrap');
  const updateModalNotes = document.getElementById('updateModalNotes');
  const btnModalOpenRelease = document.getElementById('btnModalOpenRelease');
  const btnModalInstallNow = document.getElementById('btnModalInstallNow');
  const historyDrawer = document.getElementById('historyDrawer');
  const drawerBackdrop = document.getElementById('drawerBackdrop');
  const btnCloseHistory = document.getElementById('btnCloseHistory');
  const historyList = document.getElementById('historyList');
  const toastEl = document.getElementById('toast');

  function showToast(msg) {
    toastEl.textContent = msg;
    toastEl.classList.remove('hidden');
    clearTimeout(showToast._t);
    showToast._t = setTimeout(() => toastEl.classList.add('hidden'), 3200);
  }

  function formatDuration(sec) {
    const s = Math.max(0, Math.round(sec || 0));
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const r = s % 60;
    if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(r).padStart(2, '0')}`;
    return `${m}:${String(r).padStart(2, '0')}`;
  }

  async function init() {
    if (window.tikcutDesktop) {
      if (window.tikcutDesktop.platform === 'darwin') {
        document.body.classList.add('is-mac-desktop');
      }
      initDesktopUpdater();
    }
    const res = await fetch('/api/config');
    const cfg = await res.json();
    state.fonts = cfg.fonts || [];
    state.styles = cfg.styles || [];
    const savedSettings = cfg.settings || {};
    if (geminiKeyInput && savedSettings.gemini_api_key) {
      geminiKeyInput.value = savedSettings.gemini_api_key;
    }
    if (watermarkInput && savedSettings.watermark_text) {
      watermarkInput.value = savedSettings.watermark_text;
    }
    if (ytProxyInput && savedSettings.yt_proxy) {
      ytProxyInput.value = savedSettings.yt_proxy;
    }
    if (ytCookiesSelect && savedSettings.yt_cookies_browser) {
      ytCookiesSelect.value = savedSettings.yt_cookies_browser;
    }
    if (lowCpuToggle && typeof savedSettings.low_cpu_mode === 'boolean') {
      lowCpuToggle.checked = savedSettings.low_cpu_mode;
    }
    if (autoCleanWavToggle && typeof savedSettings.auto_clean_wav === 'boolean') {
      autoCleanWavToggle.checked = savedSettings.auto_clean_wav;
    }
    applyHardwareInfo(cfg.hardware);

    renderStyleCards();
    renderFontOptions();
    updateLivePreview();
    setInterval(() => {
      state.previewWordIdx = (state.previewWordIdx + 1) % state.previewWords.length;
      updateLivePreview();
    }, 620);

    let saveSettingsTimer = null;
    function persistSettings(patch) {
      clearTimeout(saveSettingsTimer);
      saveSettingsTimer = setTimeout(() => {
        fetch('/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(patch),
        }).catch(() => {});
      }, 450);
    }

    if (geminiKeyInput) {
      geminiKeyInput.addEventListener('input', () => {
        const val = (geminiKeyInput.value || '').trim();
        persistSettings({ gemini_api_key: val });
        if (geminiKeyStatus) geminiKeyStatus.classList.add('hidden');
      });
    }
    if (watermarkInput) {
      watermarkInput.addEventListener('input', () => {
        persistSettings({ watermark_text: (watermarkInput.value || '').trim() });
      });
    }

    if (btnCheckGeminiKey && geminiKeyInput && geminiKeyStatus) {
      btnCheckGeminiKey.addEventListener('click', async () => {
        const key = (geminiKeyInput.value || '').trim();
        if (!key) {
          geminiKeyStatus.textContent = '❌ Сначала вставьте API-ключ';
          geminiKeyStatus.className = 'key-status err';
          return;
        }
        btnCheckGeminiKey.disabled = true;
        btnCheckGeminiKey.textContent = '⏳...';
        geminiKeyStatus.textContent = 'Проверка подключения к Gemini 2.5 Flash...';
        geminiKeyStatus.className = 'key-status';
        try {
          const res = await fetch('/api/check-gemini-key', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ api_key: key }),
          });
          const data = await res.json();
          geminiKeyStatus.textContent = data.message || (data.ok ? '✅ Ключ работает!' : '❌ Ошибка проверки');
          geminiKeyStatus.className = `key-status ${data.ok ? 'ok' : 'err'}`;
        } catch (_) {
          geminiKeyStatus.textContent = '⚠️ Ошибка сети при проверке ключа';
          geminiKeyStatus.className = 'key-status err';
        } finally {
          btnCheckGeminiKey.disabled = false;
          btnCheckGeminiKey.textContent = 'Проверить';
        }
      });
    }

    await refreshMusicList();
    await refreshAvatarList();
    await refreshAdsList();
    await refreshSatisfyingList();
    await refreshAccounts();
    await refreshHistory();

    if (window.tikcutDesktop && window.tikcutDesktop.onTiktokSessionChanged) {
      window.tikcutDesktop.onTiktokSessionChanged(() => {
        refreshAccountSessions();
      });
    }
  }

  async function refreshSatisfyingList() {
    try {
      const res = await fetch('/api/satisfying');
      const data = await res.json();
      const prev = satisfyingSelect.value;
      satisfyingSelect.innerHTML = '<option value="">Видео не выбрано</option>';
      (data.videos || []).forEach((v) => {
        const opt = document.createElement('option');
        opt.value = v.id;
        opt.textContent = `🎮 ${v.name}`;
        satisfyingSelect.appendChild(opt);
      });
      if (prev) satisfyingSelect.value = prev;
      else if (data.videos && data.videos.length > 0) satisfyingSelect.value = data.videos[0].id;
    } catch (_) {}
  }

  if (satisfyingToggle) {
    satisfyingToggle.addEventListener('change', () => {
      satisfyingBox.classList.toggle('hidden', !satisfyingToggle.checked);
    });
  }
  if (btnUploadSatisfying && satisfyingFileInput) {
    btnUploadSatisfying.addEventListener('click', () => satisfyingFileInput.click());
    satisfyingFileInput.addEventListener('change', async () => {
      const file = satisfyingFileInput.files && satisfyingFileInput.files[0];
      if (!file) return;
      const fd = new FormData();
      fd.append('file', file);
      btnUploadSatisfying.disabled = true;
      btnUploadSatisfying.textContent = '⏳...';
      try {
        const res = await fetch('/api/satisfying', { method: 'POST', body: fd });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Ошибка загрузки видео');
        await refreshSatisfyingList();
        satisfyingSelect.value = data.id;
        showToast(`Залипательное видео «${data.name}» добавлено!`);
      } catch (err) {
        showToast(err.message || 'Ошибка загрузки');
      } finally {
        btnUploadSatisfying.disabled = false;
        btnUploadSatisfying.textContent = '+ Залипашка';
        satisfyingFileInput.value = '';
      }
    });
  }

  async function openDashboard() {
    dashboardModal.classList.remove('hidden');
    dashboardBody.innerHTML = '<div class="history-meta">Загрузка статистики...</div>';
    try {
      const res = await fetch('/api/dashboard');
      const d = await res.json();
      const accRows = (d.accounts || [])
        .map(
          (a) => `
          <div class="history-item" style="cursor:default;display:flex;justify-content:space-between;align-items:center;">
            <div>
              <div class="history-name"><span style="color:${a.color || '#7c5cff'}">●</span> ${escapeHtml(a.name)} <span style="color:var(--muted)">${escapeHtml(a.handle || '')}</span></div>
              <div class="history-meta">Хэштеги: ${escapeHtml(a.default_hashtags || '—')}</div>
            </div>
            <div class="pill-count">🚀 ${a.published_count || 0} выложено</div>
          </div>
        `
        )
        .join('');

      const adRows = (d.ad_stats || [])
        .map(
          (ad) => `
          <div class="history-item" style="cursor:default;display:flex;justify-content:space-between;align-items:center;">
            <div class="history-name">📢 ${escapeHtml(ad.banner_id)}</div>
            <div class="history-meta">Отрендерено: <strong>${ad.rendered}</strong> • Опубликовано: <strong>${ad.published}</strong></div>
          </div>
        `
        )
        .join('');

      dashboardBody.innerHTML = `
        <div class="dash-stats-grid">
          <div class="dash-stat-card"><div class="dash-stat-val">${d.total_projects || 0}</div><div class="dash-stat-lbl">Проектов</div></div>
          <div class="dash-stat-card"><div class="dash-stat-val">${d.total_clips || 0}</div><div class="dash-stat-lbl">Клипов создано</div></div>
          <div class="dash-stat-card"><div class="dash-stat-val">${d.published_tiktok || 0}</div><div class="dash-stat-lbl">🎵 TikTok</div></div>
          <div class="dash-stat-card"><div class="dash-stat-val">${d.published_youtube || 0}</div><div class="dash-stat-lbl">▶ Shorts</div></div>
          <div class="dash-stat-card"><div class="dash-stat-val">${d.published_instagram || 0}</div><div class="dash-stat-lbl">📸 Reels</div></div>
        </div>
        <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:10px;">
          <strong style="font-size:13.5px;">Аккаунты студии (${d.accounts_count || 0})</strong>
          <div style="display:flex;gap:6px;">
            <a href="/api/dashboard/export-csv" download="tikcut_studio_report.csv" class="btn btn-secondary btn-sm">📋 Отчёт CSV / Excel</a>
            <button id="btnOpenExportsRoot" type="button" class="btn btn-secondary btn-sm">📂 Папка выгрузок</button>
          </div>
        </div>
        <div class="history-list" style="margin-bottom:12px;">${accRows || '<div class="history-meta">Аккаунты ещё не созданы</div>'}</div>
        <strong style="font-size:13.5px;display:block;margin-bottom:8px;">📢 Учёт рекламных интеграций</strong>
        <div class="history-list">${adRows || '<div class="history-meta">Пока нет клипов с рекламными баннерами</div>'}</div>
      `;
      const btnOpenExp = document.getElementById('btnOpenExportsRoot');
      if (btnOpenExp) {
        btnOpenExp.addEventListener('click', () => {
          if (window.tikcutDesktop && window.tikcutDesktop.openFolder) {
            window.tikcutDesktop.openFolder(d.exports_dir);
          } else {
            showToast(`Папка выгрузок: ${d.exports_dir}`);
          }
        });
      }
    } catch (_) {
      dashboardBody.innerHTML = '<div class="history-meta">Не удалось загрузить статистику.</div>';
    }
  }

  if (btnDashboard) btnDashboard.addEventListener('click', openDashboard);
  if (btnCloseDashboard) btnCloseDashboard.addEventListener('click', () => dashboardModal.classList.add('hidden'));
  if (dashboardBackdrop) dashboardBackdrop.addEventListener('click', () => dashboardModal.classList.add('hidden'));

  function getActiveAccount() {
    return state.accounts.find((a) => a.id === state.activeAccountId) || null;
  }

  async function refreshAccountSessions() {
    const desk = window.tikcutDesktop;
    if (!desk || !desk.tiktokCheckSession) return;
    for (const acc of state.accounts) {
      try {
        state.accountSessions[acc.id] = await desk.tiktokCheckSession(acc.id);
      } catch (_) {
        state.accountSessions[acc.id] = false;
      }
    }
    renderAccountsBar();
  }

  async function refreshAccounts() {
    try {
      const res = await fetch('/api/accounts');
      const data = await res.json();
      state.accounts = data.accounts || [];
      if (!state.activeAccountId && state.accounts.length > 0) {
        state.activeAccountId = state.accounts[0].id;
        applyAccountPreset(state.accounts[0]);
      } else if (state.activeAccountId && !getActiveAccount()) {
        state.activeAccountId = state.accounts[0]?.id || null;
      }
      renderAccountsBar();
      await refreshAccountSessions();
    } catch (_) {}
  }

  function renderAccountsBar() {
    if (!accountsPills) return;
    accountsPills.innerHTML = '';
    const active = getActiveAccount();

    btnSavePreset.classList.toggle('hidden', !active);
    btnOpenTiktokLogin.classList.toggle('hidden', !active);
    btnEditAccount.classList.toggle('hidden', !active);

    if (active) {
      const logged = !!state.accountSessions[active.id];
      btnOpenTiktokLogin.textContent = logged ? '🟢 TikTok Studio' : '🔐 Войти в TikTok';
      activeAccountSub.textContent = `Активный аккаунт: ${active.name} ${active.handle || ''} • Опубликовано: ${active.published_count || 0} • Хэштеги: ${active.default_hashtags || '—'}`;
    } else {
      activeAccountSub.textContent = 'Создайте один или несколько аккаунтов TikTok — у каждого свой пресет стиля, фото, баннер, хэштеги и вход в TikTok Studio';
    }

    state.accounts.forEach((acc) => {
      const pill = document.createElement('button');
      pill.type = 'button';
      pill.className = `account-pill ${acc.id === state.activeAccountId ? 'active' : ''}`;
      const logged = !!state.accountSessions[acc.id];
      pill.innerHTML = `
        <span class="acc-dot ${logged ? 'logged' : ''}" title="${logged ? 'Вход в TikTok выполнен' : 'Не авторизован'}"></span>
        <span style="color:${acc.color || '#fff'}">●</span>
        <span>${escapeHtml(acc.name)}</span>
        ${acc.handle ? `<span style="color:var(--muted);font-weight:500;">${escapeHtml(acc.handle)}</span>` : ''}
        <span class="acc-pub-count">${acc.published_count || 0}</span>
      `;
      pill.addEventListener('click', () => {
        state.activeAccountId = acc.id;
        applyAccountPreset(acc);
        renderAccountsBar();
        showToast(`Переключено на «${acc.name}» — пресет применён!`);
      });
      accountsPills.appendChild(pill);
    });
  }

  function applyAccountPreset(acc) {
    if (!acc || !acc.preset) return;
    const p = acc.preset;
    if (p.subtitle_style) {
      state.selectedStyle = p.subtitle_style;
      document.querySelectorAll('.style-card').forEach((el) => el.classList.toggle('active', el.dataset.id === p.subtitle_style));
    }
    if (p.font_id && fontSelect) {
      state.selectedFont = p.font_id;
      fontSelect.value = p.font_id;
    }
    if (p.font_size && fontSize) fontSize.value = p.font_size;
    if (p.position && subPosition) subPosition.value = p.position;
    if (p.crop_mode) {
      state.cropMode = p.crop_mode;
      cropModeGroup.querySelectorAll('.seg-btn').forEach((b) => b.classList.toggle('active', b.dataset.value === p.crop_mode));
      splitStreamSettings.classList.toggle('hidden', p.crop_mode !== 'split_stream');
    }
    if (typeof p.enable_subtitles === 'boolean' && enableSubtitlesToggle) enableSubtitlesToggle.checked = p.enable_subtitles;
    if (typeof p.uppercase === 'boolean' && uppercaseToggle) uppercaseToggle.checked = p.uppercase;
    if (typeof p.use_webcam_photo === 'boolean' && useWebcamPhotoToggle) {
      useWebcamPhotoToggle.checked = p.use_webcam_photo;
      webcamPhotoRow.classList.toggle('hidden', !p.use_webcam_photo);
      webcamCropRow.classList.toggle('hidden', p.use_webcam_photo);
    }
    if (p.webcam_image_id && webcamPhotoSelect) webcamPhotoSelect.value = p.webcam_image_id;
    if (p.webcam_corner && webcamCorner) webcamCorner.value = p.webcam_corner;
    if (typeof p.show_hook_banner === 'boolean' && hookBannerToggle) hookBannerToggle.checked = p.show_hook_banner;
    if (p.hook_position && hookPositionSelect) hookPositionSelect.value = p.hook_position;
    if (p.hook_font_size && hookFontSize) hookFontSize.value = p.hook_font_size;
    if (p.hook_text_color && hookTextColor) hookTextColor.value = p.hook_text_color;
    if (p.hook_bg_color === 'transparent' && hookTransparentBg) {
      hookTransparentBg.checked = true;
    } else {
      if (hookTransparentBg) hookTransparentBg.checked = false;
      if (p.hook_bg_color && hookBgColor) hookBgColor.value = p.hook_bg_color;
    }
    if (p.hook_border_color && hookBorderColor) hookBorderColor.value = p.hook_border_color;
    if (watermarkInput) watermarkInput.value = p.watermark_text || acc.handle || '';
    if (typeof p.jump_cuts === 'boolean' && jumpCutsToggle) jumpCutsToggle.checked = p.jump_cuts;
    if (typeof p.target_fps === 'number' && fps60Toggle) fps60Toggle.checked = p.target_fps >= 60;
    if (typeof p.video_enhance === 'boolean' && videoEnhanceToggle) videoEnhanceToggle.checked = p.video_enhance;
    if (typeof p.enable_ad_banner === 'boolean' && adBannerToggle) {
      adBannerToggle.checked = p.enable_ad_banner;
      adBannerBox.classList.toggle('hidden', !p.enable_ad_banner);
    }
    if (p.ad_mode && adModeSelect) {
      adModeSelect.value = p.ad_mode;
      adAudioRow.classList.toggle('hidden', p.ad_mode !== 'midroll_pause');
    }
    if (p.ad_banner_id && adBannerSelect) adBannerSelect.value = p.ad_banner_id;
    if (p.ad_audio_id && adAudioSelect) adAudioSelect.value = p.ad_audio_id;
    if (p.bg_music_id && bgMusicSelect) bgMusicSelect.value = p.bg_music_id;
    if (typeof p.enable_satisfying_video === 'boolean' && satisfyingToggle) {
      satisfyingToggle.checked = p.enable_satisfying_video;
      if (satisfyingBox) satisfyingBox.classList.toggle('hidden', !p.enable_satisfying_video);
    }
    if (p.satisfying_video_id && satisfyingSelect) satisfyingSelect.value = p.satisfying_video_id;
    if (typeof p.auto_cover === 'boolean' && autoCoverToggle) autoCoverToggle.checked = p.auto_cover;
    if (typeof p.uniquify_video === 'boolean' && uniquifyToggle) uniquifyToggle.checked = p.uniquify_video;
    if (typeof p.enable_outro === 'boolean' && outroToggle) {
      outroToggle.checked = p.enable_outro;
      if (outroBox) outroBox.classList.toggle('hidden', !p.enable_outro);
    }
    if (p.outro_id && outroSelect) outroSelect.value = p.outro_id;
    state.webcamRect = p.webcam_rect && typeof p.webcam_rect === 'object' ? p.webcam_rect : null;
    if (webcamRectBadge) webcamRectBadge.classList.toggle('hidden', !state.webcamRect);
    if (btnResetWebcamRect) btnResetWebcamRect.classList.toggle('hidden', !state.webcamRect);
    state.blurRect = p.blur_rect && typeof p.blur_rect === 'object' ? p.blur_rect : null;
    if (blurRectBadge) blurRectBadge.classList.toggle('hidden', !state.blurRect);
    if (btnResetBlurRect) btnResetBlurRect.classList.toggle('hidden', !state.blurRect);
    updateLivePreview();
  }

  let editingAccountId = null;

  function openAccountModal(acc = null) {
    editingAccountId = acc ? acc.id : null;
    accountModalTitle.textContent = acc ? `⚙️ Настройки аккаунта: ${acc.name}` : '➕ Новый TikTok аккаунт';
    accNameInput.value = acc ? acc.name : '';
    accHandleInput.value = acc ? (acc.handle || '') : '';
    accHashtagsInput.value = acc ? (acc.default_hashtags || '') : '#нарезки #тикток #стрим #рекомендации #shorts';
    accTemplateInput.value = acc ? (acc.caption_template || '{title} 🔥\n\n{hashtags}') : '{title} 🔥\n\n{hashtags}';
    accColorInput.value = acc ? (acc.color || '#7c5cff') : '#7c5cff';
    btnAccountDelete.classList.toggle('hidden', !acc);
    btnAccountLogout.classList.toggle('hidden', !(acc && window.tikcutDesktop));
    accountModal.classList.remove('hidden');
  }

  function closeAccountModal() {
    accountModal.classList.add('hidden');
    editingAccountId = null;
  }

  if (btnAddAccount) btnAddAccount.addEventListener('click', () => openAccountModal(null));
  if (btnEditAccount) btnEditAccount.addEventListener('click', () => {
    const acc = getActiveAccount();
    if (acc) openAccountModal(acc);
  });
  if (btnCloseAccountModal) btnCloseAccountModal.addEventListener('click', closeAccountModal);
  if (btnCancelAccount) btnCancelAccount.addEventListener('click', closeAccountModal);
  if (accountBackdrop) accountBackdrop.addEventListener('click', closeAccountModal);

  if (btnSavePreset) {
    btnSavePreset.addEventListener('click', async () => {
      const acc = getActiveAccount();
      if (!acc) return;
      const preset = getCurrentOptions(0);
      delete preset.gemini_api_key;
      const res = await fetch(`/api/accounts/${acc.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ preset }),
      });
      if (res.ok) {
        const updated = await res.json();
        Object.assign(acc, updated);
        showToast(`Пресет для «${acc.name}» сохранён!`);
      }
    });
  }

  if (btnOpenTiktokLogin) {
    btnOpenTiktokLogin.addEventListener('click', async () => {
      const acc = getActiveAccount();
      if (!acc) return;
      if (window.tikcutDesktop && window.tikcutDesktop.tiktokOpenLogin) {
        await window.tikcutDesktop.tiktokOpenLogin(acc.id, acc.name);
      } else {
        window.open('https://www.tiktok.com/tiktokstudio/upload', '_blank');
      }
    });
  }

  if (btnSaveAccount) {
    btnSaveAccount.addEventListener('click', async () => {
      const name = (accNameInput.value || '').trim();
      if (!name) {
        showToast('Введите название аккаунта');
        return;
      }
      const preset = getCurrentOptions(0);
      delete preset.gemini_api_key;
      const body = {
        name,
        handle: (accHandleInput.value || '').trim(),
        color: accColorInput.value || '#7c5cff',
        default_hashtags: (accHashtagsInput.value || '').trim(),
        caption_template: (accTemplateInput.value || '').trim(),
        preset,
      };
      const url = editingAccountId ? `/api/accounts/${editingAccountId}` : '/api/accounts';
      const method = editingAccountId ? 'PUT' : 'POST';
      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        showToast('Не удалось сохранить аккаунт');
        return;
      }
      const saved = await res.json();
      state.activeAccountId = saved.id;
      closeAccountModal();
      await refreshAccounts();
      showToast(`Аккаунт «${saved.name}» сохранён с текущим пресетом!`);
    });
  }

  if (btnAccountDelete) {
    btnAccountDelete.addEventListener('click', async () => {
      if (!editingAccountId) return;
      await fetch(`/api/accounts/${editingAccountId}`, { method: 'DELETE' });
      if (state.activeAccountId === editingAccountId) state.activeAccountId = null;
      closeAccountModal();
      await refreshAccounts();
      showToast('Аккаунт удалён');
    });
  }

  if (btnAccountLogout) {
    btnAccountLogout.addEventListener('click', async () => {
      if (!editingAccountId || !window.tikcutDesktop) return;
      await window.tikcutDesktop.tiktokLogout(editingAccountId);
      showToast('Сессия TikTok очищена — можно войти в другой аккаунт');
    });
  }

  function buildCaptionForAccount(clip) {
    const acc = getActiveAccount();
    if (!acc) return clip.tiktok_caption || `${clip.title || ''}\n\n#нарезки #тикток #shorts`;
    const tpl = acc.caption_template || '{title} 🔥\n\n{hashtags}';
    const tags = acc.default_hashtags || '#нарезки #тикток';
    return tpl.replace(/\{title\}/g, clip.title || '').replace(/\{hashtags\}/g, tags).trim();
  }

  async function refreshAdsList() {
    try {
      const res = await fetch('/api/ads');
      const data = await res.json();
      const prevB = adBannerSelect.value;
      const prevA = adAudioSelect.value;
      adBannerSelect.innerHTML = '<option value="">Баннер не выбран</option>';
      (data.banners || []).forEach((b) => {
        const opt = document.createElement('option');
        opt.value = b.id;
        opt.textContent = `🖼️ ${b.name}`;
        adBannerSelect.appendChild(opt);
      });
      if (prevB) adBannerSelect.value = prevB;
      else if (data.banners && data.banners.length > 0) adBannerSelect.value = data.banners[0].id;

      adAudioSelect.innerHTML = '<option value="">Без озвучки (пауза 3.5 сек)</option>';
      (data.audios || []).forEach((a) => {
        const opt = document.createElement('option');
        opt.value = a.id;
        opt.textContent = `🎙 ${a.name} (${a.duration || 0}с)`;
        adAudioSelect.appendChild(opt);
      });
      if (prevA) adAudioSelect.value = prevA;
      else if (data.audios && data.audios.length > 0) adAudioSelect.value = data.audios[0].id;
      updateLivePreview();
    } catch (_) {}
  }

  async function refreshAvatarList() {
    try {
      const res = await fetch('/api/avatars');
      const data = await res.json();
      const prev = webcamPhotoSelect.value;
      webcamPhotoSelect.innerHTML = '<option value="">Фото не выбрано</option>';
      (data.avatars || []).forEach((a) => {
        const opt = document.createElement('option');
        opt.value = a.id;
        opt.textContent = `🖼️ ${a.name}`;
        webcamPhotoSelect.appendChild(opt);
      });
      if (prev) webcamPhotoSelect.value = prev;
      else if (data.avatars && data.avatars.length > 0) webcamPhotoSelect.value = data.avatars[0].id;
      updateLivePreview();
    } catch (_) {}
  }

  function applyHardwareInfo(hw) {
    if (!hw) return;
    if (hwBadge && hw.label) {
      hwBadge.textContent = `${hw.label} • 9:16 + Русские авто-субтитры`;
    }
    // Auto-select Large-v3-Turbo & 60 FPS recommendation on NVIDIA RTX CUDA GPUs
    if (hw.cuda_whisper) {
      whisperModel.value = 'large-v3-turbo';
    }
    const models = hw.ollama_models || [];
    if (models.length > 0 && ollamaSelect) {
      ollamaSelect.innerHTML = '<option value="">Выкл (стандартный локальный анализ)</option>';
      models.forEach((m) => {
        const opt = document.createElement('option');
        opt.value = m;
        opt.textContent = `🧠 ${m} (локально на GPU)`;
        ollamaSelect.appendChild(opt);
      });
      // Auto-select first installed local Ollama model if no Gemini key is set!
      if (!localStorage.getItem('tikcut_gemini_key')) {
        ollamaSelect.value = models[0];
      }
    }
  }

  async function refreshMusicList() {
    try {
      const res = await fetch('/api/music');
      const data = await res.json();
      const prev = bgMusicSelect.value;
      bgMusicSelect.innerHTML = '<option value="">Без музыки</option>';
      (data.tracks || []).forEach((t) => {
        const opt = document.createElement('option');
        opt.value = t.id;
        opt.textContent = `🎵 ${t.name}`;
        bgMusicSelect.appendChild(opt);
      });
      if (prev) bgMusicSelect.value = prev;
    } catch (_) {}
  }

  function renderStyleCards() {
    styleCards.innerHTML = '';
    state.styles.forEach((st) => {
      const card = document.createElement('div');
      card.className = `style-card ${st.id === state.selectedStyle ? 'active' : ''}`;
      card.dataset.id = st.id;
      card.innerHTML = `
        <span class="style-badge">${st.badge || ''}</span>
        <div class="style-swatch" style="color:${st.active_pill_color ? st.active_pill_color : st.active_color}; text-shadow: 0 2px 6px #000;">АБВ</div>
        <div class="style-name">${st.name}</div>
      `;
      card.addEventListener('click', () => {
        state.selectedStyle = st.id;
        uppercaseToggle.checked = st.uppercase !== false;
        document.querySelectorAll('.style-card').forEach((el) => el.classList.toggle('active', el.dataset.id === st.id));
        updateLivePreview();
      });
      styleCards.appendChild(card);
    });
  }

  function renderFontOptions() {
    fontSelect.innerHTML = '';
    state.fonts.forEach((f) => {
      const opt = document.createElement('option');
      opt.value = f.id;
      opt.textContent = f.name;
      fontSelect.appendChild(opt);
    });
    fontSelect.value = state.selectedFont;
  }

  function updateLivePreview() {
    const st = state.styles.find((s) => s.id === state.selectedStyle) || state.styles[0];
    const fnt = state.fonts.find((f) => f.id === state.selectedFont) || state.fonts[0];
    if (!st) return;

    previewScreen.className = `phone-screen mode-${state.cropMode}`;
    liveSubBox.className = `live-sub-box pos-${subPosition.value}`;
    const subsEnabled = !enableSubtitlesToggle || enableSubtitlesToggle.checked;
    liveSubBox.classList.toggle('hidden', !subsEnabled);

    const isSplit = state.cropMode === 'split_stream';
    previewSplitCam.classList.toggle('hidden', !isSplit);
    const usePhoto = isSplit && useWebcamPhotoToggle && useWebcamPhotoToggle.checked && webcamPhotoSelect && webcamPhotoSelect.value;
    if (previewSplitPhoto && previewSplitCamText) {
      if (usePhoto) {
        previewSplitPhoto.src = `/api/avatars/${encodeURIComponent(webcamPhotoSelect.value)}`;
        previewSplitPhoto.classList.remove('hidden');
        previewSplitCamText.classList.add('hidden');
      } else {
        previewSplitPhoto.classList.add('hidden');
        previewSplitCamText.classList.remove('hidden');
      }
    }

    previewCenterLabel.textContent =
      isSplit
        ? '🎮 ГЕЙМПЛЕЙ / ЭКРАН'
        : state.cropMode === 'face_track'
        ? '🤖 AI FACE TRACK 9:16'
        : '9:16 HD 1080×1920';

    const wm = (watermarkInput.value || '').trim();
    if (wm) {
      previewWatermark.textContent = wm;
      previewWatermark.classList.remove('hidden');
    } else {
      previewWatermark.classList.add('hidden');
    }
    const showHook = hookBannerToggle && hookBannerToggle.checked;
    previewHookBanner.classList.toggle('hidden', !showHook);
    const hPos = hookPositionSelect ? hookPositionSelect.value : 'between';
    previewHookBanner.classList.toggle('pos-between', hPos === 'between');
    if (showHook) {
      const hTxtCol = hookTextColor ? hookTextColor.value : '#0c0e18';
      const hBgCol = hookBgColor ? hookBgColor.value : '#ffffff';
      const hBrdCol = hookBorderColor ? hookBorderColor.value : '#ffe600';
      const hTransp = !!(hookTransparentBg && hookTransparentBg.checked);
      const hSz = hookFontSize ? hookFontSize.value : 'medium';
      previewHookBanner.style.fontFamily = fnt ? fnt.css_family : 'sans-serif';
      previewHookBanner.style.color = hTxtCol;
      previewHookBanner.style.fontSize = hSz === 'small' ? '9.5px' : hSz === 'large' ? '13.5px' : '11px';
      if (hTransp) {
        previewHookBanner.style.background = 'transparent';
        previewHookBanner.style.borderColor = 'transparent';
        previewHookBanner.style.boxShadow = 'none';
        previewHookBanner.style.textShadow = `-2px -2px 0 ${hBrdCol}, 2px -2px 0 ${hBrdCol}, -2px 2px 0 ${hBrdCol}, 2px 2px 0 ${hBrdCol}, 0 3px 8px rgba(0,0,0,0.9)`;
      } else {
        previewHookBanner.style.background = hBgCol;
        previewHookBanner.style.borderColor = hBrdCol;
        previewHookBanner.style.boxShadow = '0 6px 18px rgba(0,0,0,0.45)';
        previewHookBanner.style.textShadow = 'none';
      }
    }

    const sizePx = fontSize.value === 'small' ? 16 : fontSize.value === 'large' ? 23 : 19;
    const isUpper = uppercaseToggle.checked;

    liveSubText.style.fontFamily = fnt ? fnt.css_family : 'sans-serif';
    liveSubText.style.fontSize = `${sizePx}px`;
    liveSubText.style.background = st.bg_pill_color || 'transparent';

    liveSubText.innerHTML = '';
    const sample = isUpper
      ? ['ЭТОТ', 'МОМЕНТ', 'ВЗОРВАЛ', 'ТИКТОК!']
      : ['Этот', 'момент', 'взорвал', 'ТикТок!'];

    sample.forEach((word, i) => {
      const span = document.createElement('span');
      span.className = 'live-word';
      span.textContent = word;
      const isActive = i === state.previewWordIdx;
      if (isActive) {
        span.style.color = st.active_color;
        span.style.transform = `scale(${st.active_scale || 1.1})`;
        if (st.active_pill_color) {
          span.style.background = st.active_pill_color;
          span.style.textShadow = 'none';
        } else {
          span.style.textShadow = `-2px -2px 0 ${st.stroke_color}, 2px -2px 0 ${st.stroke_color}, -2px 2px 0 ${st.stroke_color}, 2px 2px 0 ${st.stroke_color}, 0 4px 10px rgba(0,0,0,0.85)`;
        }
      } else {
        span.style.color = st.text_color;
        span.style.textShadow = `-2px -2px 0 ${st.stroke_color}, 2px -2px 0 ${st.stroke_color}, -2px 2px 0 ${st.stroke_color}, 2px 2px 0 ${st.stroke_color}, 0 3px 8px rgba(0,0,0,0.8)`;
      }
      liveSubText.appendChild(span);
    });

    if (previewAdBanner && previewAdImg && previewAdBadge) {
      const adOn = !!(adBannerToggle && adBannerToggle.checked && adBannerSelect && adBannerSelect.value);
      previewAdBanner.classList.toggle('hidden', !adOn);
      if (adOn) {
        const isMid = adModeSelect && adModeSelect.value === 'midroll_pause';
        previewAdBanner.classList.toggle('mode-midroll', isMid);
        previewAdBadge.classList.toggle('hidden', !isMid);
        previewAdImg.src = `/api/ads/${encodeURIComponent(adBannerSelect.value)}`;
      }
    }
  }

  // Upload handlers
  function uploadFile(file) {
    if (!file) return;
    uploadProgressWrap.classList.remove('hidden');
    videoReadyBanner.classList.add('hidden');
    uploadFileName.textContent = file.name;
    uploadPct.textContent = '0%';
    uploadBar.style.width = '0%';
    btnStart.disabled = true;

    const formData = new FormData();
    formData.append('file', file);

    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/upload', true);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        const p = Math.round((e.loaded / e.total) * 100);
        uploadPct.textContent = `${p}%`;
        uploadBar.style.width = `${p}%`;
      }
    };
    xhr.onload = () => {
      uploadProgressWrap.classList.add('hidden');
      if (xhr.status >= 200 && xhr.status < 300) {
        const job = JSON.parse(xhr.responseText);
        state.currentJobId = job.job_id;
        showUploadedJob(job);
        showToast('Видео загружено! Нажмите «Нарезать 9:16»');
        refreshHistory();
      } else {
        let msg = 'Ошибка загрузки';
        try {
          msg = JSON.parse(xhr.responseText).detail || msg;
        } catch (_) {}
        showToast(msg);
      }
    };
    xhr.onerror = () => {
      uploadProgressWrap.classList.add('hidden');
      showToast('Сетевая ошибка при загрузке файла');
    };
    xhr.send(formData);
  }

  function showUploadedJob(job) {
    urlPanel.classList.add('hidden');
    filePanel.classList.add('hidden');
    if (radarPanel) radarPanel.classList.add('hidden');
    if (livePanel) livePanel.classList.add('hidden');
    videoReadyBanner.classList.remove('hidden');
    readyFileName.textContent = job.original_filename;
    const m = job.video_meta || {};
    const parts = [];
    if (m.uploader) parts.push(m.uploader);
    if (m.width && m.height) parts.push(`${m.width}×${m.height}`);
    parts.push(formatDuration(m.duration));
    if (m.extractor && job.source_type === 'url') parts.push(m.extractor);
    readyFileMeta.textContent = parts.join(' • ');

    if (m.thumbnail) {
      readyThumb.src = m.thumbnail;
      readyThumb.classList.remove('hidden');
    } else {
      readyThumb.classList.add('hidden');
    }

    readyBadges.innerHTML = '';
    if (job.source_type === 'url') {
      const bList = ['⚡ Без скачивания всего видео'];
      if (m.has_twitch_chat) bList.push('💬 Пики чата Twitch');
      else if (m.has_heatmap) bList.push('📈 Карта пересмотров YouTube');
      if (m.has_captions) bList.push('📝 Субтитры найдены');
      bList.forEach((txt) => {
        const sp = document.createElement('span');
        sp.className = 'mini-pill';
        sp.textContent = txt;
        readyBadges.appendChild(sp);
      });
    }
    btnStart.disabled = job.status === 'processing';
  }

  function switchSourceTab(tab) {
    sourceTabs.querySelectorAll('.source-tab').forEach((b) => b.classList.toggle('active', b.dataset.tab === tab));
    videoReadyBanner.classList.add('hidden');
    urlPanel.classList.toggle('hidden', tab !== 'url');
    filePanel.classList.toggle('hidden', tab !== 'file');
    if (radarPanel) radarPanel.classList.toggle('hidden', tab !== 'radar');
    if (livePanel) livePanel.classList.toggle('hidden', tab !== 'live');
    if (tab === 'file') dropZone.classList.remove('hidden');
  }

  sourceTabs.querySelectorAll('.source-tab').forEach((btn) => {
    btn.addEventListener('click', () => switchSourceTab(btn.dataset.tab));
  });

  async function probeUrl() {
    const url = (urlInput.value || '').trim();
    if (!url) {
      showToast('Вставьте ссылку на YouTube или запись стрима');
      return;
    }
    btnProbeUrl.disabled = true;
    const origLabel = btnProbeUrl.textContent;
    btnProbeUrl.textContent = '⏳ Анализ ссылки...';
    btnStart.disabled = true;

    try {
      const res = await fetch('/api/probe-url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || 'Не удалось открыть ссылку');
      }
      state.currentJobId = data.job_id;
      showUploadedJob(data);
      showToast('Ссылка готова! Нажмите «Найти лучшие моменты и нарезать 9:16»');
      refreshHistory();
    } catch (err) {
      showToast(err.message || 'Ошибка анализа ссылки');
    } finally {
      btnProbeUrl.disabled = false;
      btnProbeUrl.textContent = origLabel;
    }
  }

  btnProbeUrl.addEventListener('click', probeUrl);
  urlInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') probeUrl();
  });

  btnPickFile.addEventListener('click', (e) => {
    e.stopPropagation();
    fileInput.click();
  });
  dropZone.addEventListener('click', () => fileInput.click());
  fileInput.addEventListener('change', () => {
    if (fileInput.files && fileInput.files[0]) uploadFile(fileInput.files[0]);
  });
  btnChangeVideo.addEventListener('click', () => {
    const activeTab = sourceTabs.querySelector('.source-tab.active')?.dataset.tab || 'url';
    switchSourceTab(activeTab);
    fileInput.value = '';
  });

  ['dragenter', 'dragover'].forEach((ev) => {
    dropZone.addEventListener(ev, (e) => {
      e.preventDefault();
      dropZone.classList.add('dragover');
    });
  });
  ['dragleave', 'drop'].forEach((ev) => {
    dropZone.addEventListener(ev, (e) => {
      e.preventDefault();
      dropZone.classList.remove('dragover');
    });
  });
  dropZone.addEventListener('drop', (e) => {
    const file = e.dataTransfer.files && e.dataTransfer.files[0];
    if (file) uploadFile(file);
  });

  // Settings listeners
  clipCount.addEventListener('input', () => {
    clipCountVal.textContent = clipCount.value;
  });
  cropModeGroup.querySelectorAll('.seg-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      state.cropMode = btn.dataset.value;
      cropModeGroup.querySelectorAll('.seg-btn').forEach((b) => b.classList.toggle('active', b === btn));
      splitStreamSettings.classList.toggle('hidden', state.cropMode !== 'split_stream');
      updateLivePreview();
    });
  });
  webcamSize.addEventListener('input', () => {
    webcamSizeVal.textContent = `${webcamSize.value}%`;
  });
  if (useWebcamPhotoToggle) {
    useWebcamPhotoToggle.addEventListener('change', () => {
      const on = useWebcamPhotoToggle.checked;
      webcamPhotoRow.classList.toggle('hidden', !on);
      webcamCropRow.classList.toggle('hidden', on);
      updateLivePreview();
    });
  }
  if (webcamPhotoSelect) {
    webcamPhotoSelect.addEventListener('change', updateLivePreview);
  }
  if (btnUploadAvatar && avatarFileInput) {
    btnUploadAvatar.addEventListener('click', () => avatarFileInput.click());
    avatarFileInput.addEventListener('change', async () => {
      const file = avatarFileInput.files && avatarFileInput.files[0];
      if (!file) return;
      const fd = new FormData();
      fd.append('file', file);
      btnUploadAvatar.disabled = true;
      try {
        const res = await fetch('/api/avatars', { method: 'POST', body: fd });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Ошибка загрузки фото');
        await refreshAvatarList();
        webcamPhotoSelect.value = data.id;
        if (useWebcamPhotoToggle && !useWebcamPhotoToggle.checked) {
          useWebcamPhotoToggle.checked = true;
          webcamPhotoRow.classList.remove('hidden');
          webcamCropRow.classList.add('hidden');
        }
        updateLivePreview();
        showToast(`Фото «${data.name}» загружено!`);
      } catch (err) {
        showToast(err.message || 'Ошибка загрузки фото');
      } finally {
        btnUploadAvatar.disabled = false;
        avatarFileInput.value = '';
      }
    });
  }
  fontSelect.addEventListener('change', () => {
    state.selectedFont = fontSelect.value;
    updateLivePreview();
  });
  fontSize.addEventListener('change', updateLivePreview);
  subPosition.addEventListener('change', updateLivePreview);
  if (enableSubtitlesToggle) enableSubtitlesToggle.addEventListener('change', updateLivePreview);
  uppercaseToggle.addEventListener('change', updateLivePreview);
  hookBannerToggle.addEventListener('change', updateLivePreview);
  if (hookPositionSelect) hookPositionSelect.addEventListener('change', updateLivePreview);
  if (hookFontSize) hookFontSize.addEventListener('change', updateLivePreview);
  if (hookTextColor) hookTextColor.addEventListener('input', updateLivePreview);
  if (hookBgColor) hookBgColor.addEventListener('input', updateLivePreview);
  if (hookBorderColor) hookBorderColor.addEventListener('input', updateLivePreview);
  if (hookTransparentBg) hookTransparentBg.addEventListener('change', updateLivePreview);
  if (adBannerToggle) {
    adBannerToggle.addEventListener('change', () => {
      adBannerBox.classList.toggle('hidden', !adBannerToggle.checked);
      updateLivePreview();
    });
  }
  if (adModeSelect) {
    adModeSelect.addEventListener('change', () => {
      adAudioRow.classList.toggle('hidden', adModeSelect.value !== 'midroll_pause');
      updateLivePreview();
    });
  }
  if (adBannerSelect) adBannerSelect.addEventListener('change', updateLivePreview);
  if (btnUploadAdBanner && adBannerFileInput) {
    btnUploadAdBanner.addEventListener('click', () => adBannerFileInput.click());
    adBannerFileInput.addEventListener('change', async () => {
      const file = adBannerFileInput.files && adBannerFileInput.files[0];
      if (!file) return;
      const fd = new FormData();
      fd.append('file', file);
      btnUploadAdBanner.disabled = true;
      try {
        const res = await fetch('/api/ads/banner', { method: 'POST', body: fd });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Ошибка загрузки баннера');
        await refreshAdsList();
        adBannerSelect.value = data.id;
        updateLivePreview();
        showToast(`Баннер «${data.name}» загружен!`);
      } catch (err) {
        showToast(err.message || 'Ошибка загрузки баннера');
      } finally {
        btnUploadAdBanner.disabled = false;
        adBannerFileInput.value = '';
      }
    });
  }
  if (btnUploadAdAudio && adAudioFileInput) {
    btnUploadAdAudio.addEventListener('click', () => adAudioFileInput.click());
    adAudioFileInput.addEventListener('change', async () => {
      const file = adAudioFileInput.files && adAudioFileInput.files[0];
      if (!file) return;
      const fd = new FormData();
      fd.append('file', file);
      btnUploadAdAudio.disabled = true;
      try {
        const res = await fetch('/api/ads/audio', { method: 'POST', body: fd });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Ошибка загрузки озвучки');
        await refreshAdsList();
        adAudioSelect.value = data.id;
        showToast(`Озвучка «${data.name}» (${data.duration}с) загружена!`);
      } catch (err) {
        showToast(err.message || 'Ошибка загрузки озвучки');
      } finally {
        btnUploadAdAudio.disabled = false;
        adAudioFileInput.value = '';
      }
    });
  }
  watermarkInput.addEventListener('input', updateLivePreview);

  btnUploadMusic.addEventListener('click', () => musicFileInput.click());
  musicFileInput.addEventListener('change', async () => {
    const file = musicFileInput.files && musicFileInput.files[0];
    if (!file) return;
    const fd = new FormData();
    fd.append('file', file);
    btnUploadMusic.disabled = true;
    try {
      const res = await fetch('/api/music', { method: 'POST', body: fd });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Ошибка загрузки трека');
      let saveSettingsTimer = null;
    function persistSettings(patch) {
      clearTimeout(saveSettingsTimer);
      saveSettingsTimer = setTimeout(() => {
        fetch('/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(patch),
        }).catch(() => {});
      }, 450);
    }

    if (geminiKeyInput) {
      geminiKeyInput.addEventListener('input', () => {
        const val = (geminiKeyInput.value || '').trim();
        persistSettings({ gemini_api_key: val });
        if (geminiKeyStatus) geminiKeyStatus.classList.add('hidden');
      });
    }
    if (watermarkInput) {
      watermarkInput.addEventListener('input', () => {
        persistSettings({ watermark_text: (watermarkInput.value || '').trim() });
      });
    }

    if (btnCheckGeminiKey && geminiKeyInput && geminiKeyStatus) {
      btnCheckGeminiKey.addEventListener('click', async () => {
        const key = (geminiKeyInput.value || '').trim();
        if (!key) {
          geminiKeyStatus.textContent = '❌ Сначала вставьте API-ключ';
          geminiKeyStatus.className = 'key-status err';
          return;
        }
        btnCheckGeminiKey.disabled = true;
        btnCheckGeminiKey.textContent = '⏳...';
        geminiKeyStatus.textContent = 'Проверка подключения к Gemini 2.5 Flash...';
        geminiKeyStatus.className = 'key-status';
        try {
          const res = await fetch('/api/check-gemini-key', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ api_key: key }),
          });
          const data = await res.json();
          geminiKeyStatus.textContent = data.message || (data.ok ? '✅ Ключ работает!' : '❌ Ошибка проверки');
          geminiKeyStatus.className = `key-status ${data.ok ? 'ok' : 'err'}`;
        } catch (_) {
          geminiKeyStatus.textContent = '⚠️ Ошибка сети при проверке ключа';
          geminiKeyStatus.className = 'key-status err';
        } finally {
          btnCheckGeminiKey.disabled = false;
          btnCheckGeminiKey.textContent = 'Проверить';
        }
      });
    }

    await refreshMusicList();
      bgMusicSelect.value = data.id;
      showToast(`Трек «${data.name}» добавлен!`);
    } catch (err) {
      showToast(err.message || 'Ошибка загрузки музыки');
    } finally {
      btnUploadMusic.disabled = false;
      musicFileInput.value = '';
    }
  });

  function getCurrentOptions(shuffleSeed = 0) {
    return {
      clip_count: parseInt(clipCount.value, 10) || 6,
      min_duration: parseFloat(minDuration.value) || 20,
      max_duration: parseFloat(maxDuration.value) || 55,
      whisper_model: whisperModel.value,
      subtitle_style: state.selectedStyle,
      font_id: state.selectedFont,
      font_size: fontSize.value,
      crop_mode: state.cropMode,
      position: subPosition.value,
      uppercase: uppercaseToggle.checked,
      enable_subtitles: enableSubtitlesToggle ? enableSubtitlesToggle.checked : true,
      webcam_corner: webcamCorner.value,
      webcam_size: (parseInt(webcamSize.value, 10) || 28) / 100.0,
      use_webcam_photo: !!(useWebcamPhotoToggle && useWebcamPhotoToggle.checked),
      webcam_image_id: webcamPhotoSelect ? webcamPhotoSelect.value || null : null,
      show_hook_banner: hookBannerToggle.checked,
      hook_position: hookPositionSelect ? hookPositionSelect.value : 'between',
      hook_text_color: hookTextColor ? hookTextColor.value : '#0c0e18',
      hook_bg_color: hookTransparentBg && hookTransparentBg.checked ? 'transparent' : (hookBgColor ? hookBgColor.value : '#ffffff'),
      hook_border_color: hookBorderColor ? hookBorderColor.value : '#ffe600',
      hook_font_size: hookFontSize ? hookFontSize.value : 'medium',
      watermark_text: (watermarkInput.value || '').trim() || null,
      watermark_opacity: 0.55,
      jump_cuts: jumpCutsToggle.checked,
      bg_music_id: bgMusicSelect.value || null,
      bg_music_volume: 0.18,
      target_fps: fps60Toggle && fps60Toggle.checked ? 60 : 30,
      video_enhance: !!(videoEnhanceToggle && videoEnhanceToggle.checked),
      enable_ad_banner: !!(adBannerToggle && adBannerToggle.checked),
      ad_mode: adModeSelect ? adModeSelect.value : 'bottom_overlay',
      ad_banner_id: adBannerSelect ? adBannerSelect.value || null : null,
      ad_audio_id: adAudioSelect ? adAudioSelect.value || null : null,
      enable_satisfying_video: !!(satisfyingToggle && satisfyingToggle.checked),
      satisfying_video_id: satisfyingSelect ? satisfyingSelect.value || null : null,
      uniquify_video: !!(uniquifyToggle && uniquifyToggle.checked),
      auto_cover: !!(autoCoverToggle && autoCoverToggle.checked),
      webcam_rect: state.webcamRect || null,
      blur_rect: state.blurRect || null,
      low_cpu_mode: !!(lowCpuToggle && lowCpuToggle.checked),
      enable_outro: !!(outroToggle && outroToggle.checked),
      outro_id: outroSelect ? outroSelect.value || null : null,
      manual_timecodes: manualTimecodesInput ? (manualTimecodesInput.value || '').trim() || null : null,
      search_chat_activity: searchChatToggle ? searchChatToggle.checked : true,
      search_laughter: searchLaughterToggle ? searchLaughterToggle.checked : true,
      search_screams: searchScreamsToggle ? searchScreamsToggle.checked : true,
      use_ai_director: useAiDirectorToggle ? useAiDirectorToggle.checked : true,
      shuffle_seed: shuffleSeed,
      ollama_model: ollamaSelect ? ollamaSelect.value || null : null,
      gemini_api_key: geminiKeyInput ? (geminiKeyInput.value || '').trim() || null : null,
    };
  }

  async function runJobProcessing(shuffleSeed = 0) {
    if (!state.currentJobId) return;
    const opts = getCurrentOptions(shuffleSeed);
    if (opts.max_duration < opts.min_duration) {
      showToast('Максимальная длина должна быть больше минимальной');
      return;
    }

    btnStart.disabled = true;
    if (btnShuffleMoments) btnShuffleMoments.disabled = true;
    progressSection.classList.remove('hidden');
    procError.classList.add('hidden');
    resultsSection.classList.add('hidden');

    const res = await fetch(`/api/process/${state.currentJobId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(opts),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      showToast(err.detail || 'Не удалось запустить обработку');
      btnStart.disabled = false;
      if (btnShuffleMoments) btnShuffleMoments.disabled = false;
      return;
    }
    const job = await res.json();
    updateJobUI(job);
    startPolling(state.currentJobId);
  }

  if (btnShuffleMoments) {
    btnShuffleMoments.addEventListener('click', () => {
      const seed = Math.floor(Date.now() % 1000000) + 1;
      showToast('🎲 Перемешиваем и подбираем другие моменты...');
      runJobProcessing(seed);
    });
  }

  function parseTimestampInput(str) {
    const clean = (str || '').trim();
    if (!clean) return NaN;
    const parts = clean.split(':').map((p) => parseFloat(p));
    if (parts.some((n) => Number.isNaN(n))) return NaN;
    if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
    if (parts.length === 2) return parts[0] * 60 + parts[1];
    return parts[0];
  }

  if (btnCutCustom) {
    btnCutCustom.addEventListener('click', async () => {
      if (!state.currentJobId) return;
      const s = parseTimestampInput(customStartInput.value);
      const e = parseTimestampInput(customEndInput.value);
      if (Number.isNaN(s) || Number.isNaN(e) || e <= s + 2) {
        showToast('Введите корректные таймкоды, например: 12:30 и 13:05');
        return;
      }
      btnCutCustom.disabled = true;
      btnCutCustom.textContent = '⏳ Нарезка...';
      try {
        const opts = getCurrentOptions();
        const res = await fetch(`/api/jobs/${state.currentJobId}/custom-clip`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ...opts, start_sec: s, end_sec: e }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.detail || 'Ошибка нарезки момента');
        const jobRes = await fetch(`/api/jobs/${state.currentJobId}`);
        if (jobRes.ok) {
          const updatedJob = await jobRes.json();
          renderClips(updatedJob);
        }
        customStartInput.value = '';
        customEndInput.value = '';
        showToast('Свой момент успешно вырезан в 9:16 с субтитрами!');
      } catch (err) {
        showToast(err.message || 'Ошибка нарезки');
      } finally {
        btnCutCustom.disabled = false;
        btnCutCustom.textContent = 'Вырезать 9:16';
      }
    });
  }

  // Start processing
  btnStart.addEventListener('click', () => runJobProcessing(0));

  function startPolling(jobId) {
    clearInterval(state.pollTimer);
    state.pollTimer = setInterval(async () => {
      const res = await fetch(`/api/jobs/${jobId}`);
      if (!res.ok) return;
      const job = await res.json();
      updateJobUI(job);
      if (job.status === 'completed' || job.status === 'failed') {
        clearInterval(state.pollTimer);
        btnStart.disabled = false;
        if (btnShuffleMoments) btnShuffleMoments.disabled = false;
        refreshHistory();
        if (job.status === 'completed') {
          notifyRenderDone('TikCut Studio — Нарезки готовы!', `Создано клипов: ${(job.clips || []).length}`);
        }
      }
    }, 1200);
  }

  const STAGE_ORDER = ['extracting_audio', 'transcribing', 'analyzing', 'rendering', 'completed'];

  function updateJobUI(job) {
    const stageIdx = STAGE_ORDER.indexOf(job.stage);

    if (job.status === 'processing' || job.status === 'failed' || job.status === 'completed') {
      progressSection.classList.remove('hidden');
      procTitle.textContent =
        job.status === 'completed'
          ? '✅ Нарезка завершена!'
          : job.status === 'failed'
          ? '⚠️ Ошибка обработки'
          : '⚙️ Идёт локальная обработка...';
      procMessage.textContent = job.message || '';
      procPct.textContent = `${job.progress || 0}%`;
      procBar.style.width = `${job.progress || 0}%`;

      document.querySelectorAll('.step-pill').forEach((pill) => {
        const sIdx = STAGE_ORDER.indexOf(pill.dataset.stage);
        pill.classList.remove('active', 'done');
        if (job.status === 'completed' || (stageIdx > sIdx && sIdx >= 0)) {
          pill.classList.add('done');
        } else if (stageIdx === sIdx) {
          pill.classList.add('active');
        }
      });

      if (job.error) {
        procError.textContent = job.error;
        procError.classList.remove('hidden');
      } else {
        procError.classList.add('hidden');
      }
    }

    if (job.clips && job.clips.length > 0) {
      renderClips(job);
    }
  }

  let editingContext = null;

  function openClipEditor(job, clip, card) {
    editingContext = { job, clip, card };
    editHookInput.value = clip.hook_text || clip.title || '';
    editTrimStart.value = Math.round(clip.start || 0);
    editTrimEnd.value = Math.round(clip.end || (clip.start || 0) + (clip.duration || 25));
    editTranscriptInput.value = clip.transcript || '';
    clipEditorModal.classList.remove('hidden');
  }

  document.querySelectorAll('.btn-editor-shift').forEach((btn) => {
    btn.addEventListener('click', () => {
      const delta = parseFloat(btn.dataset.delta || '0');
      const curS = parseFloat(editTrimStart.value || '0');
      const curE = parseFloat(editTrimEnd.value || '20');
      const dur = Math.max(2, curE - curS);
      const nextS = Math.max(0, curS + delta);
      editTrimStart.value = Math.round(nextS);
      editTrimEnd.value = Math.round(nextS + dur);
    });
  });

  function closeClipEditor() {
    clipEditorModal.classList.add('hidden');
    editingContext = null;
  }

  btnCloseEditor.addEventListener('click', closeClipEditor);
  btnCancelEditor.addEventListener('click', closeClipEditor);
  editorBackdrop.addEventListener('click', closeClipEditor);

  btnSaveEditor.addEventListener('click', async () => {
    if (!editingContext) return;
    const { job, clip, card } = editingContext;
    btnSaveEditor.disabled = true;
    btnSaveEditor.textContent = '⏳ Перерендер...';
    try {
      const opts = getCurrentOptions();
      const newS = parseFloat(editTrimStart.value);
      const newE = parseFloat(editTrimEnd.value);
      const shifted = Math.abs(newS - (clip.start || 0)) > 0.4 || Math.abs(newE - (clip.end || 0)) > 0.4;
      const bodyPayload = {
        ...opts,
        edited_hook_text: editHookInput.value,
      };
      if (shifted) {
        bodyPayload.source_start = newS;
        bodyPayload.source_end = newE;
      } else {
        bodyPayload.edited_transcript = editTranscriptInput.value;
      }
      const res = await fetch(`/api/jobs/${job.job_id}/clips/${clip.id}/rerender`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(bodyPayload),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Ошибка сохранения');
      }
      const updated = await res.json();
      Object.assign(clip, updated);
      const vid = card.querySelector('video');
      const nv = updated.version || Date.now();
      vid.poster = `/api/jobs/${job.job_id}/clips/${clip.id}/thumb?v=${nv}`;
      vid.src = `/api/jobs/${job.job_id}/clips/${clip.id}/video?v=${nv}`;
      vid.load();
      card.querySelector('.clip-title').textContent = updated.title || clip.id;
      card.querySelector('.clip-transcript').textContent = updated.transcript || 'Без речи';
      card.querySelector('.dur-badge').textContent = `${formatDuration(updated.start)} – ${formatDuration(updated.end)} (${Math.round(updated.duration)}с)`;
      closeClipEditor();
      showToast(shifted ? 'Таймкод сдвинут и клип перерендерен!' : 'Клип перерендерен с вашими правками!');
    } catch (err) {
      showToast(err.message || 'Ошибка перерендера');
    } finally {
      btnSaveEditor.disabled = false;
      btnSaveEditor.textContent = '💾 Сохранить и перерендерить';
    }
  });

  let selectedClipIdsForCompile = new Set();

  function updateCompileBtnUI() {
    if (!btnCompileSelected || !selectedClipsCount) return;
    selectedClipsCount.textContent = String(selectedClipIdsForCompile.size);
    btnCompileSelected.classList.toggle('hidden', selectedClipIdsForCompile.size < 2);
  }

  if (btnCompileSelected) {
    btnCompileSelected.addEventListener('click', async () => {
      if (!state.currentJobId || selectedClipIdsForCompile.size < 2) return;
      btnCompileSelected.disabled = true;
      btnCompileSelected.textContent = '⏳ Склейка...';
      try {
        const res = await fetch(`/api/jobs/${state.currentJobId}/compile`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ clip_ids: Array.from(selectedClipIdsForCompile) }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.detail || 'Ошибка склейки');
        selectedClipIdsForCompile.clear();
        const jobRes = await fetch(`/api/jobs/${state.currentJobId}`);
        if (jobRes.ok) renderClips(await jobRes.json());
        showToast('Подборка склеена и добавлена первой в список!');
      } catch (err) {
        showToast(err.message || 'Ошибка склейки');
      } finally {
        btnCompileSelected.disabled = false;
        btnCompileSelected.innerHTML = '🎞 Склеить выбранные (<span id="selectedClipsCount">0</span>)';
        updateCompileBtnUI();
      }
    });
  }

  if (btnExportFolder) {
    btnExportFolder.addEventListener('click', async () => {
      if (!state.currentJobId) return;
      const acc = getActiveAccount();
      const accName = acc ? acc.name : 'General';
      btnExportFolder.disabled = true;
      try {
        const res = await fetch(`/api/jobs/${state.currentJobId}/export-folder`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ account_name: accName }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.detail || 'Ошибка экспорта');
        showToast(`Экспортировано ${data.count} клипов в папку «${accName}»!`);
        if (window.tikcutDesktop && window.tikcutDesktop.openFolder && data.folder) {
          window.tikcutDesktop.openFolder(data.folder);
        }
      } catch (err) {
        showToast(err.message || 'Ошибка экспорта');
      } finally {
        btnExportFolder.disabled = false;
      }
    });
  }

  function renderClips(job) {
    resultsSection.classList.remove('hidden');
    if (customClipBar) customClipBar.classList.remove('hidden');
    loadHypeTimeline(job.job_id);
    const notice = job.ai_notice ? ` • ⚠️ ${job.ai_notice}` : '';
    resultsMeta.textContent = `Проект: ${job.original_filename} • Клипов: ${job.clips.length} • Распознано слов: ${job.words_count || 0}${notice}`;
    selectedClipIdsForCompile.clear();
    updateCompileBtnUI();
    if (job.clips.length > 0) {
      btnDownloadAllZip.href = `/api/jobs/${job.job_id}/download-all`;
      btnDownloadAllZip.classList.remove('hidden');
      if (btnShuffleMoments) btnShuffleMoments.classList.remove('hidden');
      if (btnExportFolder) btnExportFolder.classList.remove('hidden');
      if (btnBestOf60s) btnBestOf60s.classList.remove('hidden');
    } else {
      btnDownloadAllZip.classList.add('hidden');
      if (btnShuffleMoments) btnShuffleMoments.classList.add('hidden');
      if (btnExportFolder) btnExportFolder.classList.add('hidden');
      if (btnBestOf60s) btnBestOf60s.classList.add('hidden');
    }
    clipsGrid.innerHTML = '';

    job.clips.forEach((clip) => {
      const v = clip.version || 1;
      const videoUrl = `/api/jobs/${job.job_id}/clips/${clip.id}/video?v=${v}`;
      const thumbUrl = `/api/jobs/${job.job_id}/clips/${clip.id}/thumb?v=${v}`;
      const dlUrl = `/api/jobs/${job.job_id}/clips/${clip.id}/download`;

      const card = document.createElement('div');
      card.className = 'clip-card';
      card.innerHTML = `
        <div class="clip-video-wrap">
          <video controls preload="metadata" poster="${thumbUrl}" playsinline>
            <source src="${videoUrl}" type="video/mp4" />
          </video>
          <div class="score-badge">🔥 ${clip.viral_score}/100</div>
          <div class="dur-badge">${formatDuration(clip.start)} – ${formatDuration(clip.end)} (${Math.round(clip.duration)}с)</div>
          <label class="clip-select-check" title="Выбрать для склейки в подборку">
            <input type="checkbox" class="clip-compile-cb" />
            <span>Склеить</span>
          </label>
        </div>
        <div class="clip-body">
          <div class="clip-title">${escapeHtml(clip.title || clip.id)}</div>
          <div class="clip-tags">
            ${(clip.tags || []).map((t) => `<span class="clip-tag">${escapeHtml(t)}</span>`).join('')}
            ${(clip.published_to || []).map((p) => `<span class="published-badge">✅ ${escapeHtml(p.platform || 'tiktok')}: ${escapeHtml(p.account_name || '')}</span>`).join('')}
          </div>
          <div class="clip-transcript">${escapeHtml(clip.transcript || 'Без речи')}</div>
          <div class="clip-shift-row">
            <button type="button" class="btn btn-ghost btn-sm btn-shift-clip" data-delta="-10">⏪ -10с раньше</button>
            <button type="button" class="btn btn-ghost btn-sm btn-shift-clip" data-delta="10">⏩ +10с позже</button>
          </div>
          <div class="social-post-row">
            <button type="button" class="btn btn-tiktok btn-sm btn-social-upload" data-platform="tiktok">🎵 TikTok</button>
            <button type="button" class="btn btn-shorts btn-sm btn-social-upload" data-platform="youtube">▶ Shorts</button>
            <button type="button" class="btn btn-reels btn-sm btn-social-upload" data-platform="instagram">📸 Reels</button>
          </div>
          <div class="clip-actions">
            <a class="btn btn-primary btn-sm" href="${dlUrl}" download>⬇ Скачать MP4</a>
            <button type="button" class="btn btn-secondary btn-sm btn-edit">✏️ Редактор</button>
            <button type="button" class="btn btn-ghost btn-sm btn-rerender">🎨 Новый стиль</button>
            <button type="button" class="btn btn-ghost btn-sm btn-copy-cap">📋 Описание</button>
            <button type="button" class="btn btn-ghost btn-sm btn-add-plan btn-full">📅 Добавить в контент-план</button>
          </div>
        </div>
      `;

      const btnPlan = card.querySelector('.btn-add-plan');
      if (btnPlan) {
        btnPlan.addEventListener('click', async () => {
          const acc = getActiveAccount();
          const today = new Date().toISOString().slice(0, 10);
          try {
            const res = await fetch('/api/plan', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                title: clip.title || 'Клип',
                account_id: acc ? acc.id : '',
                account_name: acc ? acc.name : 'Основной',
                platform: 'tiktok',
                scheduled_date: today,
                scheduled_time: '18:00',
                job_id: job.job_id,
                clip_id: clip.id,
              }),
            });
            if (!res.ok) throw new Error('Ошибка');
            showToast('📅 Клип добавлен в контент-план (Дашборд → Контент-план)');
          } catch (_) {
            showToast('Не удалось добавить в план');
          }
        });
      }

      const compileCb = card.querySelector('.clip-compile-cb');
      if (compileCb) {
        compileCb.addEventListener('change', () => {
          if (compileCb.checked) selectedClipIdsForCompile.add(clip.id);
          else selectedClipIdsForCompile.delete(clip.id);
          updateCompileBtnUI();
        });
      }

      card.querySelectorAll('.btn-social-upload').forEach((sBtn) => {
        sBtn.addEventListener('click', async () => {
          const platform = sBtn.dataset.platform || 'tiktok';
          const acc = getActiveAccount();
          const caption = buildCaptionForAccount(clip);
          try {
            await navigator.clipboard.writeText(caption);
          } catch (_) {}

          const fallbackUrls = {
            tiktok: 'https://www.tiktok.com/tiktokstudio/upload',
            youtube: 'https://studio.youtube.com',
            instagram: 'https://www.instagram.com',
          };

          if (window.tikcutDesktop && (window.tikcutDesktop.socialUploadClip || window.tikcutDesktop.tiktokUploadClip)) {
            let filePath = '';
            try {
              const pRes = await fetch(`/api/jobs/${job.job_id}/clips/${clip.id}/path`);
              if (pRes.ok) filePath = (await pRes.json()).path || '';
            } catch (_) {}
            const accId = acc ? acc.id : 'default';
            const accName = acc ? acc.name : 'Studio';
            const fn = window.tikcutDesktop.socialUploadClip || window.tikcutDesktop.tiktokUploadClip;
            await fn({ accountId: accId, accountName: accName, platform, filePath, caption });
            showToast(`Открыто окно ${platform.toUpperCase()}! Описание с хэштегами скопировано.`);
            if (acc) {
              await fetch(`/api/jobs/${job.job_id}/clips/${clip.id}/mark-published`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ account_id: acc.id, account_name: acc.name, platform }),
              }).catch(() => {});
              await refreshAccounts();
            }
          } else {
            window.open(fallbackUrls[platform], '_blank');
            showToast('Описание и хэштеги скопированы!');
          }
        });
      });

      card.querySelectorAll('.btn-shift-clip').forEach((sBtn) => {
        sBtn.addEventListener('click', async () => {
          const delta = parseFloat(sBtn.dataset.delta || '0');
          const curS = clip.start || 0;
          const curE = clip.end || curS + (clip.duration || 25);
          const dur = Math.max(2, curE - curS);
          const nextS = Math.max(0, curS + delta);
          const nextE = nextS + dur;
          const origTxt = sBtn.textContent;
          card.querySelectorAll('.btn-shift-clip').forEach((b) => { b.disabled = true; });
          sBtn.textContent = '⏳ Сдвиг...';
          try {
            const opts = getCurrentOptions();
            const res = await fetch(`/api/jobs/${job.job_id}/clips/${clip.id}/rerender`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ ...opts, source_start: nextS, source_end: nextE }),
            });
            if (!res.ok) throw new Error('Не удалось сдвинуть таймкод');
            const updated = await res.json();
            Object.assign(clip, updated);
            const vid = card.querySelector('video');
            const nv = updated.version || Date.now();
            vid.poster = `/api/jobs/${job.job_id}/clips/${clip.id}/thumb?v=${nv}`;
            vid.src = `/api/jobs/${job.job_id}/clips/${clip.id}/video?v=${nv}`;
            vid.load();
            card.querySelector('.dur-badge').textContent = `${formatDuration(updated.start)} – ${formatDuration(updated.end)} (${Math.round(updated.duration)}с)`;
            card.querySelector('.clip-transcript').textContent = updated.transcript || 'Без речи';
            showToast(`Таймкод сдвинут на ${delta > 0 ? '+' : ''}${delta} сек!`);
          } catch (err) {
            showToast(err.message || 'Ошибка сдвига');
          } finally {
            sBtn.textContent = origTxt;
            card.querySelectorAll('.btn-shift-clip').forEach((b) => { b.disabled = false; });
          }
        });
      });

      card.querySelector('.btn-edit').addEventListener('click', () => openClipEditor(job, clip, card));

      card.querySelector('.btn-copy-cap').addEventListener('click', async () => {
        const txt = buildCaptionForAccount(clip);
        try {
          await navigator.clipboard.writeText(txt);
          showToast('Описание и хэштеги скопированы!');
        } catch (_) {
          showToast('Не удалось скопировать в буфер');
        }
      });

      const btnRe = card.querySelector('.btn-rerender');
      btnRe.addEventListener('click', async () => {
        btnRe.disabled = true;
        btnRe.textContent = '⏳ Рендер...';
        try {
          const opts = getCurrentOptions();
          const res = await fetch(`/api/jobs/${job.job_id}/clips/${clip.id}/rerender`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(opts),
          });
          if (!res.ok) throw new Error('Не удалось перерендерить');
          const updated = await res.json();
          Object.assign(clip, updated);
          const vid = card.querySelector('video');
          const nv = updated.version || Date.now();
          vid.poster = `/api/jobs/${job.job_id}/clips/${clip.id}/thumb?v=${nv}`;
          vid.src = `/api/jobs/${job.job_id}/clips/${clip.id}/video?v=${nv}`;
          vid.load();
          showToast('Клип обновлён с новым стилем и настройками!');
        } catch (err) {
          showToast(err.message || 'Ошибка перерендера');
        } finally {
          btnRe.disabled = false;
          btnRe.textContent = '🎨 Новый стиль';
        }
      });

      clipsGrid.appendChild(card);
    });
  }

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // History drawer
  async function refreshHistory() {
    const res = await fetch('/api/jobs');
    const data = await res.json();
    const jobs = data.jobs || [];
    historyCount.textContent = String(jobs.length);
    historyList.innerHTML = '';

    if (jobs.length === 0) {
      historyList.innerHTML = '<div class="history-meta">Пока нет загруженных видео.</div>';
      return;
    }

    jobs.forEach((j) => {
      const item = document.createElement('div');
      item.className = 'history-item';
      const statusLabel =
        j.status === 'completed'
          ? `✅ Готово (${(j.clips || []).length} клипов)`
          : j.status === 'processing'
          ? `⚙️ В работе (${j.progress || 0}%)`
          : j.status === 'failed'
          ? '⚠️ Ошибка'
          : '📁 Загружено';

      item.innerHTML = `
        <div class="history-name">${escapeHtml(j.original_filename)}</div>
        <div class="history-meta">${statusLabel} • ${formatDuration(j.video_meta?.duration)}</div>
      `;
      item.addEventListener('click', () => {
        state.currentJobId = j.job_id;
        showUploadedJob(j);
        updateJobUI(j);
        if (j.status === 'processing') startPolling(j.job_id);
        historyDrawer.classList.add('hidden');
      });
      historyList.appendChild(item);
    });
  }

  btnHistory.addEventListener('click', () => {
    refreshHistory();
    historyDrawer.classList.remove('hidden');
  });
  btnCloseHistory.addEventListener('click', () => historyDrawer.classList.add('hidden'));
  drawerBackdrop.addEventListener('click', () => historyDrawer.classList.add('hidden'));

  // Changelog Modal
  function formatInlineMd(str) {
    let s = escapeHtml(str);
    s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    s = s.replace(/\*([^*]+)\*/g, '<em>$1</em>');
    s = s.replace(/`([^`]+)`/g, '<code>$1</code>');
    return s;
  }

  async function openChangelog() {
    changelogModal.classList.remove('hidden');
    changelogBody.innerHTML = '<div class="history-meta">Загрузка ченджлога...</div>';
    try {
      const res = await fetch('/api/changelog');
      const data = await res.json();
      const releases = data.releases || [];
      if (!releases.length) {
        changelogBody.innerHTML = '<div class="history-meta">Список изменений пока пуст.</div>';
        return;
      }
      changelogBody.innerHTML = releases
        .map(
          (rel) => `
          <div class="cl-release">
            <div class="cl-release-head">
              <span class="cl-version">v${escapeHtml(rel.version)}</span>
              <span class="cl-date">${escapeHtml(rel.date || '')}</span>
            </div>
            ${(rel.sections || [])
              .map(
                (sec) => `
                <div class="cl-section">
                  <div class="cl-section-title">${escapeHtml(sec.title)}</div>
                  <ul class="cl-list">
                    ${(sec.items || [])
                      .map(
                        (it) => `<li class="${it.sub ? 'cl-sub' : ''}">${formatInlineMd(it.text)}</li>`
                      )
                      .join('')}
                  </ul>
                </div>
              `
              )
              .join('')}
          </div>
        `
        )
        .join('');
    } catch (_) {
      changelogBody.innerHTML = '<div class="history-meta">Не удалось загрузить ченджлог.</div>';
    }
  }

  btnChangelog.addEventListener('click', openChangelog);
  btnCloseChangelog.addEventListener('click', () => changelogModal.classList.add('hidden'));
  changelogBackdrop.addEventListener('click', () => changelogModal.classList.add('hidden'));

  function initDesktopUpdater() {
    const desk = window.tikcutDesktop;
    if (!desk || !btnCheckUpdates) return;

    btnCheckUpdates.classList.remove('hidden');
    let latestReleaseUrl = null;
    let manualClick = false;
    let updateState = 'idle'; // idle | downloading | downloaded | manual-download

    desk.getVersion().then((v) => {
      if (v) appVersionPill.textContent = `v${v}`;
    }).catch(() => {});

    // Single 1-click button:
    // - If downloaded -> instant silent install & restart!
    // - If manual fallback -> direct download!
    // - Otherwise -> check for updates!
    btnCheckUpdates.addEventListener('click', () => {
      if (updateState === 'downloaded') {
        updateBtnLabel.textContent = 'Перезапуск...';
        btnCheckUpdates.disabled = true;
        desk.installUpdate();
        return;
      }
      if (updateState === 'manual-download') {
        desk.openExternal(latestReleaseUrl);
        return;
      }
      if (updateState === 'downloading') {
        showToast('Обновление скачивается в фоне — скоро появится кнопка установки');
        return;
      }
      manualClick = true;
      btnCheckUpdates.disabled = true;
      updateBtnLabel.textContent = 'Проверка...';
      desk.checkForUpdates().finally(() => {
        setTimeout(() => {
          btnCheckUpdates.disabled = false;
          if (updateState === 'idle') updateBtnLabel.textContent = 'Обновления';
        }, 1500);
      });
    });

    desk.onUpdateStatus((payload) => {
      if (!payload) return;
      const st = payload.state;

      if (st === 'checking') {
        return;
      }
      if (st === 'up-to-date') {
        updateState = 'idle';
        updateBtnLabel.textContent = 'Обновления';
        if (manualClick) {
          showToast(payload.message || 'У вас последняя версия!');
          manualClick = false;
        }
        return;
      }
      if (st === 'error') {
        updateState = 'idle';
        updateBtnLabel.textContent = 'Обновления';
        if (manualClick) {
          showToast(payload.message || 'Ошибка проверки обновлений');
          manualClick = false;
        }
        return;
      }

      if (st === 'available') {
        updateState = 'downloading';
        if (updateDot) updateDot.classList.remove('hidden');
        updateBtnLabel.textContent = 'Загрузка...';
        showToast(`Найдено обновление v${payload.version} — скачивается в фоне`);
      } else if (st === 'downloading') {
        updateState = 'downloading';
        const pct = payload.percent || 0;
        if (updateDot) updateDot.classList.remove('hidden');
        updateBtnLabel.textContent = `Обновление ${pct}%`;
      } else if (st === 'downloaded') {
        updateState = 'downloaded';
        if (updateDot) updateDot.classList.add('hidden');
        btnCheckUpdates.classList.add('btn-update-ready');
        updateBtnLabel.textContent = `⚡ Обновить до v${payload.version || ''}`;
        appVersionPill.textContent = '1 клик';
        showToast(`Обновление v${payload.version} готово — нажмите «⚡ Обновить» сверху!`);
      } else if (st === 'manual-download') {
        updateState = 'manual-download';
        latestReleaseUrl = payload.releaseUrl || null;
        btnCheckUpdates.classList.add('btn-update-ready');
        updateBtnLabel.textContent = `⬇ Скачать v${payload.version || ''}`;
        appVersionPill.textContent = 'NEW';
      }
    });
  }

  // =====================================================================
  // v2.2.0 Features: Safe Zone (#7), Batch Queue (#11), Webcam Crop (#14),
  // Style Presets + JSON (#15), Disk Manager (#18), Content Plan (#19), Outro (#20)
  // =====================================================================

  // #7 Safe Zone Overlay toggle
  if (btnToggleSafeZone && safeZoneOverlay) {
    btnToggleSafeZone.addEventListener('click', () => {
      const hidden = safeZoneOverlay.classList.toggle('hidden');
      btnToggleSafeZone.classList.toggle('active', !hidden);
      btnToggleSafeZone.textContent = hidden ? '📱 Safe Zone' : '📱 Safe Zone: ВКЛ';
    });
  }

  // #20 Outro CTA toggle & uploader
  async function refreshOutrosList() {
    if (!outroSelect) return;
    try {
      const res = await fetch('/api/outros');
      const data = await res.json();
      const cur = outroSelect.value;
      outroSelect.innerHTML = '<option value="">Аутро не выбрано</option>';
      (data.items || []).forEach((it) => {
        const opt = document.createElement('option');
        opt.value = it.id;
        opt.textContent = `${it.name} (${it.ext.replace('.', '').toUpperCase()})`;
        outroSelect.appendChild(opt);
      });
      if (cur) outroSelect.value = cur;
    } catch (_) {}
  }

  if (outroToggle && outroBox) {
    outroToggle.addEventListener('change', () => {
      outroBox.classList.toggle('hidden', !outroToggle.checked);
    });
  }
  if (btnUploadOutro && outroFileInput) {
    btnUploadOutro.addEventListener('click', () => outroFileInput.click());
    outroFileInput.addEventListener('change', async () => {
      const f = outroFileInput.files && outroFileInput.files[0];
      if (!f) return;
      btnUploadOutro.disabled = true;
      try {
        const fd = new FormData();
        fd.append('file', f);
        const res = await fetch('/api/outros', { method: 'POST', body: fd });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Ошибка загрузки аутро');
        await refreshOutrosList();
        outroSelect.value = data.id;
        showToast(`Аутро «${data.name}» добавлено!`);
      } catch (err) {
        showToast(err.message || 'Ошибка загрузки аутро');
      } finally {
        btnUploadOutro.disabled = false;
        outroFileInput.value = '';
      }
    });
  }

  // #15 Built-in Style Presets Library + JSON Export/Import
  const BUILTIN_PRESETS = {
    streamer: {
      subtitle_style: 'hormozi', font_id: 'montserrat', font_size: 'large', position: 'lower_third',
      crop_mode: 'split_stream', enable_subtitles: true, uppercase: true, show_hook_banner: true,
      hook_position: 'between', hook_text_color: '#0c0e18', hook_bg_color: '#ffffff', hook_border_color: '#ffe600',
      jump_cuts: true, target_fps: 60, video_enhance: true, enable_satisfying_video: false, auto_cover: true,
    },
    irl: {
      subtitle_style: 'tiktok_bold', font_id: 'rubik', font_size: 'medium', position: 'lower_third',
      crop_mode: 'face_track', enable_subtitles: true, uppercase: true, show_hook_banner: true,
      hook_position: 'top', hook_text_color: '#ffffff', hook_bg_color: '#ff2e93', hook_border_color: '#ffffff',
      jump_cuts: true, target_fps: 30, video_enhance: true, enable_satisfying_video: false, auto_cover: true,
    },
    cinema: {
      subtitle_style: 'classic', font_id: 'oswald', font_size: 'medium', position: 'bottom',
      crop_mode: 'blur_bg', enable_subtitles: true, uppercase: false, show_hook_banner: true,
      hook_position: 'top', hook_text_color: '#ffe600', hook_bg_color: 'transparent', hook_border_color: '#000000',
      jump_cuts: false, target_fps: 30, video_enhance: true, enable_satisfying_video: false, auto_cover: true,
    },
    hormozi: {
      subtitle_style: 'hormozi', font_id: 'montserrat', font_size: 'large', position: 'center',
      crop_mode: 'face_track', enable_subtitles: true, uppercase: true, show_hook_banner: true,
      hook_position: 'top', hook_text_color: '#ffffff', hook_bg_color: '#11131d', hook_border_color: '#ffe600',
      jump_cuts: true, target_fps: 30, video_enhance: true, enable_satisfying_video: false, auto_cover: true,
    },
    podcast: {
      subtitle_style: 'classic', font_id: 'rubik', font_size: 'medium', position: 'lower_third',
      crop_mode: 'face_track', enable_subtitles: true, uppercase: false, show_hook_banner: true,
      hook_position: 'top', hook_text_color: '#ffffff', hook_bg_color: 'transparent', hook_border_color: '#000000',
      jump_cuts: false, target_fps: 30, video_enhance: false, enable_satisfying_video: false, auto_cover: false,
    },
    minimal: {
      subtitle_style: 'minimal', font_id: 'rubik', font_size: 'small', position: 'lower_third',
      crop_mode: 'fill', enable_subtitles: true, uppercase: false, show_hook_banner: false,
      jump_cuts: false, target_fps: 30, video_enhance: true, enable_satisfying_video: false, auto_cover: false,
    },
    brainrot: {
      subtitle_style: 'neon', font_id: 'unbounded', font_size: 'large', position: 'center',
      crop_mode: 'fill', enable_subtitles: true, uppercase: true, show_hook_banner: true,
      hook_position: 'top', hook_text_color: '#0c0e18', hook_bg_color: '#ffe600', hook_border_color: '#ff2e93',
      jump_cuts: true, target_fps: 60, video_enhance: true, enable_satisfying_video: true, auto_cover: true,
    },
  };

  if (presetLibraryBar) {
    presetLibraryBar.querySelectorAll('.preset-chip').forEach((btn) => {
      btn.addEventListener('click', () => {
        const key = btn.dataset.preset;
        const preset = BUILTIN_PRESETS[key];
        if (!preset) return;
        applyAccountPreset({ preset });
        showToast(`Применён шаблон: ${btn.textContent.trim()}`);
      });
    });
  }

  if (btnExportPresetJson) {
    btnExportPresetJson.addEventListener('click', () => {
      const preset = getCurrentOptions(0);
      delete preset.gemini_api_key;
      const blob = new Blob([JSON.stringify(preset, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `tikcut_preset_${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
      showToast('Настройки экспортированы в JSON!');
    });
  }
  if (btnImportPresetJson && importPresetJsonInput) {
    btnImportPresetJson.addEventListener('click', () => importPresetJsonInput.click());
    importPresetJsonInput.addEventListener('change', async () => {
      const f = importPresetJsonInput.files && importPresetJsonInput.files[0];
      if (!f) return;
      try {
        const text = await f.text();
        const parsed = JSON.parse(text);
        applyAccountPreset({ preset: parsed });
        showToast('Пресет из JSON успешно применён!');
      } catch (_) {
        showToast('Некорректный JSON-файл пресета');
      } finally {
        importPresetJsonInput.value = '';
      }
    });
  }

  // #11 Batch URL Queue
  let batchPollTimer = null;
  function renderBatchStatus(data) {
    if (!batchStatusList || !batchSummary) return;
    const items = data.items || [];
    if (!items.length) return;
    batchStatusList.classList.remove('hidden');
    batchSummary.textContent = data.running
      ? `⏳ В работе: ${data.completed + data.failed}/${data.total}`
      : `✅ Завершено: ${data.completed}/${data.total}${data.failed ? ` (ошибок: ${data.failed})` : ''}`;
    const icons = { queued: '⏳', probing: '🔍', processing: '⚙️', completed: '✅', failed: '❌' };
    batchStatusList.innerHTML = items.map((it) => `
      <div class="batch-item">
        <span>${icons[it.status] || '⏳'}</span>
        <span class="batch-item-url" title="${escapeHtml(it.url)}">${escapeHtml(it.title || it.url)}</span>
        <span class="history-meta">${escapeHtml(it.error || it.status)}</span>
      </div>
    `).join('');
  }

  async function pollBatchStatus() {
    try {
      const res = await fetch('/api/batch-urls');
      const data = await res.json();
      renderBatchStatus(data);
      if (data.running) {
        batchPollTimer = setTimeout(pollBatchStatus, 2500);
      } else {
        refreshHistory();
        if (btnStartBatch) btnStartBatch.disabled = false;
      }
    } catch (_) {}
  }

  if (btnToggleBatch && batchQueueBox) {
    btnToggleBatch.addEventListener('click', () => batchQueueBox.classList.toggle('hidden'));
  }
  if (btnStartBatch && batchUrlsInput) {
    btnStartBatch.addEventListener('click', async () => {
      const urls = (batchUrlsInput.value || '').split('\n').map((s) => s.trim()).filter(Boolean);
      if (!urls.length) {
        showToast('Вставьте хотя бы одну ссылку в очередь');
        return;
      }
      btnStartBatch.disabled = true;
      try {
        const res = await fetch('/api/batch-urls', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ urls, options: getCurrentOptions(0) }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Ошибка запуска очереди');
        renderBatchStatus(data);
        showToast(`Очередь запущена (${urls.length} ссылок)!`);
        clearTimeout(batchPollTimer);
        pollBatchStatus();
      } catch (err) {
        showToast(err.message || 'Ошибка очереди');
        btnStartBatch.disabled = false;
      }
    });
  }

  // #14 Interactive Webcam Crop & #42 Blur Box Drawer Modal
  let cropModalMode = 'webcam'; // 'webcam' | 'blur'
  let cropImg = null;
  let draftRect = null;
  let draggingCrop = false;
  let dragStart = { x: 0, y: 0 };

  function redrawWebcamCanvas() {
    if (!webcamCropCanvas) return;
    const ctx = webcamCropCanvas.getContext('2d');
    const W = webcamCropCanvas.width;
    const H = webcamCropCanvas.height;
    ctx.clearRect(0, 0, W, H);
    if (cropImg && cropImg.complete && cropImg.naturalWidth) {
      ctx.drawImage(cropImg, 0, 0, W, H);
    } else {
      ctx.fillStyle = '#121628';
      ctx.fillRect(0, 0, W, H);
      ctx.fillStyle = '#8b95b3';
      ctx.font = '16px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('Макет 16:9 (загрузите локальное видео для живого кадра)', W / 2, H / 2);
    }
    const r = draftRect || (cropModalMode === 'blur' ? state.blurRect : state.webcamRect);
    if (r && r.w > 0.02 && r.h > 0.02) {
      const rx = r.x * W, ry = r.y * H, rw = r.w * W, rh = r.h * H;
      if (cropModalMode === 'blur') {
        ctx.fillStyle = 'rgba(255, 59, 92, 0.35)';
        ctx.fillRect(rx, ry, rw, rh);
        ctx.strokeStyle = '#ff3b5c';
        ctx.lineWidth = 3;
        ctx.strokeRect(rx, ry, rw, rh);
        if (webcamCropCoords) {
          webcamCropCoords.textContent = `Цензура (Blur): X=${Math.round(r.x * 100)}%, Y=${Math.round(r.y * 100)}%, Ш=${Math.round(r.w * 100)}%, В=${Math.round(r.h * 100)}%`;
        }
      } else {
        ctx.fillStyle = 'rgba(0, 0, 0, 0.45)';
        ctx.fillRect(0, 0, W, H);
        if (cropImg && cropImg.complete && cropImg.naturalWidth) {
          ctx.drawImage(cropImg, r.x * cropImg.naturalWidth, r.y * cropImg.naturalHeight, r.w * cropImg.naturalWidth, r.h * cropImg.naturalHeight, rx, ry, rw, rh);
        } else {
          ctx.clearRect(rx, ry, rw, rh);
        }
        ctx.strokeStyle = '#ffe600';
        ctx.lineWidth = 3;
        ctx.strokeRect(rx, ry, rw, rh);
        if (webcamCropCoords) {
          webcamCropCoords.textContent = `Вебка: X=${Math.round(r.x * 100)}%, Y=${Math.round(r.y * 100)}%, Ш=${Math.round(r.w * 100)}%, В=${Math.round(r.h * 100)}%`;
        }
      }
    }
  }

  function closeWebcamCropModal() {
    if (webcamCropModal) webcamCropModal.classList.add('hidden');
  }

  function openCanvasDrawer(mode) {
    cropModalMode = mode;
    draftRect = mode === 'blur'
      ? (state.blurRect ? { ...state.blurRect } : null)
      : (state.webcamRect ? { ...state.webcamRect } : null);
    const titleEl = webcamCropModal?.querySelector('h3');
    const subEl = webcamCropModal?.querySelector('.modal-sub');
    if (titleEl) {
      titleEl.textContent = mode === 'blur' ? '🌫️ Выделение области цензуры (Blur)' : '📐 Выделение веб-камеры стримера';
    }
    if (subEl) {
      subEl.textContent = mode === 'blur'
        ? 'Обведите прямоугольником чужой баннер, ник или чат — он будет размыт на всех клипах'
        : 'Зажмите левую кнопку мыши и обведите прямоугольником вебку стримера на кадре';
    }
    cropImg = new Image();
    cropImg.onload = redrawWebcamCanvas;
    cropImg.onerror = redrawWebcamCanvas;
    if (state.currentJobId) {
      cropImg.src = `/api/jobs/${state.currentJobId}/preview-frame?t=${Date.now()}`;
    } else {
      redrawWebcamCanvas();
    }
    if (webcamCropModal) webcamCropModal.classList.remove('hidden');
  }

  if (btnOpenWebcamCrop && webcamCropModal && webcamCropCanvas) {
    btnOpenWebcamCrop.addEventListener('click', () => openCanvasDrawer('webcam'));
    if (btnOpenBlurBox) btnOpenBlurBox.addEventListener('click', () => openCanvasDrawer('blur'));

    const getCanvasPos = (ev) => {
      const rect = webcamCropCanvas.getBoundingClientRect();
      return {
        x: Math.max(0, Math.min(1, (ev.clientX - rect.left) / rect.width)),
        y: Math.max(0, Math.min(1, (ev.clientY - rect.top) / rect.height)),
      };
    };
    webcamCropCanvas.addEventListener('mousedown', (ev) => {
      draggingCrop = true;
      dragStart = getCanvasPos(ev);
      draftRect = { x: dragStart.x, y: dragStart.y, w: 0.01, h: 0.01 };
    });
    window.addEventListener('mousemove', (ev) => {
      if (!draggingCrop) return;
      const cur = getCanvasPos(ev);
      draftRect = {
        x: Math.min(dragStart.x, cur.x),
        y: Math.min(dragStart.y, cur.y),
        w: Math.abs(cur.x - dragStart.x),
        h: Math.abs(cur.y - dragStart.y),
      };
      redrawWebcamCanvas();
    });
    window.addEventListener('mouseup', () => { draggingCrop = false; });

    if (btnCloseWebcamCrop) btnCloseWebcamCrop.addEventListener('click', closeWebcamCropModal);
    if (btnCancelWebcamCrop) btnCancelWebcamCrop.addEventListener('click', closeWebcamCropModal);
    if (webcamCropBackdrop) webcamCropBackdrop.addEventListener('click', closeWebcamCropModal);
    if (btnSaveWebcamCrop) {
      btnSaveWebcamCrop.addEventListener('click', () => {
        if (!draftRect || draftRect.w < 0.03 || draftRect.h < 0.03) {
          showToast('Обведите область побольше');
          return;
        }
        const saved = {
          x: Number(draftRect.x.toFixed(4)),
          y: Number(draftRect.y.toFixed(4)),
          w: Number(draftRect.w.toFixed(4)),
          h: Number(draftRect.h.toFixed(4)),
        };
        if (cropModalMode === 'blur') {
          state.blurRect = saved;
          if (blurRectBadge) blurRectBadge.classList.remove('hidden');
          if (btnResetBlurRect) btnResetBlurRect.classList.remove('hidden');
          closeWebcamCropModal();
          showToast('Область размытия (цензуры) сохранена!');
        } else {
          state.webcamRect = saved;
          if (webcamRectBadge) webcamRectBadge.classList.remove('hidden');
          if (btnResetWebcamRect) btnResetWebcamRect.classList.remove('hidden');
          closeWebcamCropModal();
          showToast('Область веб-камеры сохранена!');
        }
      });
    }
  }
  if (btnResetBlurRect) {
    btnResetBlurRect.addEventListener('click', () => {
      state.blurRect = null;
      if (blurRectBadge) blurRectBadge.classList.add('hidden');
      btnResetBlurRect.classList.add('hidden');
      showToast('Область цензуры сброшена');
    });
  }
  if (btnResetWebcamRect) {
    btnResetWebcamRect.addEventListener('click', () => {
      state.webcamRect = null;
      if (webcamRectBadge) webcamRectBadge.classList.add('hidden');
      btnResetWebcamRect.classList.add('hidden');
      showToast('Возвращён стандартный кроп по углу');
    });
  }

  // #18 Disk Manager + #19 Content Plan Tabs inside Dashboard Modal
  async function loadPlanTab() {
    if (!dashPlanBody) return;
    dashPlanBody.innerHTML = '<div class="history-meta">Загрузка контент-плана...</div>';
    try {
      const res = await fetch('/api/plan');
      const data = await res.json();
      const items = data.items || [];
      const today = new Date().toISOString().slice(0, 10);
      const accOpts = (state.accounts || []).map((a) => `<option value="${escapeHtml(a.name)}">${escapeHtml(a.name)}</option>`).join('') || '<option value="Основной">Основной</option>';
      dashPlanBody.innerHTML = `
        <div class="preset-library-bar" style="margin-bottom:10px;">
          <span class="preset-lib-label">🧪 Лучшее время постинга:</span>
          <button type="button" class="preset-chip btn-pick-time" data-t="08:30">🌅 RU 08:30</button>
          <button type="button" class="preset-chip btn-pick-time" data-t="13:00">☀️ RU 13:00</button>
          <button type="button" class="preset-chip btn-pick-time" data-t="18:30">🔥 RU 18:30 (Прайм)</button>
          <button type="button" class="preset-chip btn-pick-time" data-t="21:00">🌙 RU 21:00</button>
          <button type="button" class="preset-chip btn-pick-time" data-t="19:00">🇺🇸 US 19:00 МСК</button>
          <button type="button" class="preset-chip btn-pick-time" data-t="22:00">🇺🇸 US 22:00 МСК</button>
        </div>
        <div class="plan-add-row">
          <input id="planNewTitle" type="text" placeholder="Название клипа / идеи..." />
          <select id="planNewAcc">${accOpts}</select>
          <input id="planNewDate" type="date" value="${today}" />
          <input id="planNewTime" type="time" value="18:00" />
          <button id="btnPlanAdd" type="button" class="btn btn-primary btn-sm">+ Добавить</button>
        </div>
        <div class="plan-list">
          ${items.length ? items.map((it) => `
            <div class="plan-card ${it.status === 'published' ? 'done' : ''}">
              <div>
                <div style="font-weight:700;font-size:13px;">${escapeHtml(it.title)}</div>
                <div class="history-meta">${escapeHtml(it.scheduled_date)} ${escapeHtml(it.scheduled_time)} • ${escapeHtml(it.account_name)} • ${escapeHtml(it.platform.toUpperCase())}</div>
              </div>
              <div style="display:flex;gap:6px;">
                <button type="button" class="btn btn-secondary btn-sm btn-plan-toggle" data-id="${it.id}" data-status="${it.status}">
                  ${it.status === 'published' ? '✅ Выложено' : '⏳ В плане'}
                </button>
                <button type="button" class="btn btn-ghost btn-sm btn-plan-del" data-id="${it.id}">🗑</button>
              </div>
            </div>
          `).join('') : '<div class="history-meta">Пока нет запланированных публикаций. Нажмите «📅 Добавить в контент-план» на любом клипе или добавьте выше.</div>'}
        </div>
      `;
      dashPlanBody.querySelectorAll('.btn-pick-time').forEach((b) => {
        b.addEventListener('click', () => {
          const inp = document.getElementById('planNewTime');
          if (inp) inp.value = b.dataset.t || '18:30';
          showToast(`Выбрано прайм-время: ${b.dataset.t}`);
        });
      });
      const btnAdd = document.getElementById('btnPlanAdd');
      if (btnAdd) {
        btnAdd.addEventListener('click', async () => {
          const title = (document.getElementById('planNewTitle')?.value || '').trim();
          if (!title) return showToast('Введите название');
          await fetch('/api/plan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              title,
              account_name: document.getElementById('planNewAcc')?.value || 'Основной',
              scheduled_date: document.getElementById('planNewDate')?.value || today,
              scheduled_time: document.getElementById('planNewTime')?.value || '18:00',
              platform: 'tiktok',
            }),
          });
          loadPlanTab();
        });
      }
      dashPlanBody.querySelectorAll('.btn-plan-toggle').forEach((b) => {
        b.addEventListener('click', async () => {
          const nextSt = b.dataset.status === 'published' ? 'planned' : 'published';
          await fetch(`/api/plan/${b.dataset.id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: nextSt }),
          });
          loadPlanTab();
        });
      });
      dashPlanBody.querySelectorAll('.btn-plan-del').forEach((b) => {
        b.addEventListener('click', async () => {
          await fetch(`/api/plan/${b.dataset.id}`, { method: 'DELETE' });
          loadPlanTab();
        });
      });
    } catch (_) {
      dashPlanBody.innerHTML = '<div class="history-meta">Ошибка загрузки контент-плана</div>';
    }
  }

  async function loadDiskTab() {
    if (!dashDiskBody) return;
    dashDiskBody.innerHTML = '<div class="history-meta">Подсчёт занятого места...</div>';
    try {
      const res = await fetch('/api/disk');
      const d = await res.json();
      dashDiskBody.innerHTML = `
        <div class="dash-kpi-grid">
          <div class="dash-kpi"><div class="dash-kpi-val">${d.total_mb} МБ</div><div class="dash-kpi-lbl">Всего занято</div></div>
          <div class="dash-kpi"><div class="dash-kpi-val">${d.sources_mb} МБ</div><div class="dash-kpi-lbl">Исходники и аудио</div></div>
          <div class="dash-kpi"><div class="dash-kpi-val">${d.clips_mb} МБ</div><div class="dash-kpi-lbl">Готовые клипы</div></div>
          <div class="dash-kpi"><div class="dash-kpi-val">${d.assets_mb} МБ</div><div class="dash-kpi-lbl">Ассеты (музыка/баннеры)</div></div>
          <div class="dash-kpi"><div class="dash-kpi-val">${d.exports_mb} МБ</div><div class="dash-kpi-lbl">Папка экспортов</div></div>
        </div>
        <div class="history-meta" style="margin-top:8px;">Очистка исходников удаляет только тяжёлые исходные видео и WAV — все ваши готовые клипы 9:16 и обложки остаются нетронутыми!</div>
        <div class="disk-actions-row">
          <button id="btnCleanOld7" type="button" class="btn btn-secondary btn-sm">🧹 Очистить исходники старше 7 дней</button>
          <button id="btnCleanAllSrc" type="button" class="btn btn-secondary btn-sm">🧹 Очистить все исходники</button>
          <button id="btnCleanCache" type="button" class="btn btn-ghost btn-sm">🗑 Очистить временный кэш</button>
        </div>
      `;
      document.getElementById('btnCleanOld7')?.addEventListener('click', async () => {
        const r = await (await fetch('/api/disk/cleanup-sources', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ older_than_days: 7 }) })).json();
        showToast(`Освобождено ${r.freed_mb} МБ (${r.removed_files} файлов)`);
        loadDiskTab();
      });
      document.getElementById('btnCleanAllSrc')?.addEventListener('click', async () => {
        const r = await (await fetch('/api/disk/cleanup-sources', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ older_than_days: 0 }) })).json();
        showToast(`Освобождено ${r.freed_mb} МБ (${r.removed_files} файлов)`);
        loadDiskTab();
      });
      document.getElementById('btnCleanCache')?.addEventListener('click', async () => {
        const r = await (await fetch('/api/disk/cleanup-cache', { method: 'POST' })).json();
        showToast(`Кэш очищен: освобождено ${r.freed_mb} МБ`);
        loadDiskTab();
      });
    } catch (_) {
      dashDiskBody.innerHTML = '<div class="history-meta">Не удалось получить статистику диска</div>';
    }
  }

  if (dashTabs) {
    dashTabs.querySelectorAll('.dash-tab').forEach((tab) => {
      tab.addEventListener('click', () => {
        const key = tab.dataset.dtab;
        dashTabs.querySelectorAll('.dash-tab').forEach((t) => t.classList.toggle('active', t === tab));
        if (dashboardBody) dashboardBody.classList.toggle('hidden', key !== 'stats');
        if (dashPlanBody) dashPlanBody.classList.toggle('hidden', key !== 'plan');
        if (dashDiskBody) dashDiskBody.classList.toggle('hidden', key !== 'disk');
        if (key === 'plan') loadPlanTab();
        if (key === 'disk') loadDiskTab();
      });
    });
  }

  // #56 System + Sound Notification when rendering completes
  function notifyRenderDone(title, body) {
    try {
      const AC = window.AudioContext || window.webkitAudioContext;
      if (AC) {
        const ctx = new AC();
        const now = ctx.currentTime;
        [523.25, 659.25, 783.99].forEach((freq, i) => {
          const osc = ctx.createOscillator();
          const gain = ctx.createGain();
          osc.type = 'sine';
          osc.frequency.setValueAtTime(freq, now + i * 0.11);
          gain.gain.setValueAtTime(0.08, now + i * 0.11);
          gain.gain.exponentialRampToValueAtTime(0.0001, now + i * 0.11 + 0.35);
          osc.connect(gain);
          gain.connect(ctx.destination);
          osc.start(now + i * 0.11);
          osc.stop(now + i * 0.11 + 0.38);
        });
      }
    } catch (_) {}
    try {
      if ('Notification' in window) {
        if (Notification.permission === 'granted') {
          new Notification(title, { body });
        } else if (Notification.permission !== 'denied') {
          Notification.requestPermission().then((p) => {
            if (p === 'granted') new Notification(title, { body });
          });
        }
      }
    } catch (_) {}
  }

  // #59 Proxy & Browser Cookies + #55 Quiet Mode settings persistence
  if (btnToggleNetOpts && netOptsBox) {
    btnToggleNetOpts.addEventListener('click', () => netOptsBox.classList.toggle('hidden'));
  }
  const saveNetSetting = (patch) => {
    fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patch),
    }).catch(() => {});
  };
  if (ytCookiesSelect) {
    ytCookiesSelect.addEventListener('change', () => {
      saveNetSetting({ yt_cookies_browser: ytCookiesSelect.value });
      showToast(ytCookiesSelect.value ? `Cookies браузера: ${ytCookiesSelect.value}` : 'Cookies отключены');
    });
  }
  if (ytProxyInput) {
    let proxyTimer = null;
    ytProxyInput.addEventListener('input', () => {
      clearTimeout(proxyTimer);
      proxyTimer = setTimeout(() => saveNetSetting({ yt_proxy: ytProxyInput.value.trim() }), 500);
    });
  }
  if (lowCpuToggle) {
    lowCpuToggle.addEventListener('change', () => {
      saveNetSetting({ low_cpu_mode: lowCpuToggle.checked });
      showToast(lowCpuToggle.checked ? '🌡️ Тихий фон включён (меньше нагрузки на ПК)' : '⚡ Полная мощность CPU/GPU');
    });
  }

  // #44 Auto Best-Of 60s Montage button
  if (btnBestOf60s) {
    btnBestOf60s.addEventListener('click', async () => {
      if (!state.currentJobId) return;
      btnBestOf60s.disabled = true;
      const origTxt = btnBestOf60s.textContent;
      btnBestOf60s.textContent = '⏳ Сборка Best-Of 60с...';
      try {
        const res = await fetch(`/api/jobs/${state.currentJobId}/best-of-60s`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(getCurrentOptions(0)),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Не удалось собрать Best-Of');
        const jRes = await fetch(`/api/jobs/${state.currentJobId}`);
        if (jRes.ok) renderClips(await jRes.json());
        notifyRenderDone('⚡ Best-Of 60с готов!', data.title || 'Монтаж лучших криков и смеха создан');
        showToast('⚡ Best-Of 60с создан и добавлен первым!');
      } catch (err) {
        showToast(err.message || 'Ошибка сборки Best-Of');
      } finally {
        btnBestOf60s.disabled = false;
        btnBestOf60s.textContent = origTxt;
      }
    });
  }

  // =====================================================================
  // v2.5.0: Twitch Clips Radar (#1), Live Clipper (#3), Hype Timeline (#4), Auto WAV Cleaner (#15)
  // =====================================================================

  // #15 Auto WAV Cleaner setting toggle
  if (autoCleanWavToggle) {
    autoCleanWavToggle.addEventListener('change', () => {
      saveNetSetting({ auto_clean_wav: autoCleanWavToggle.checked });
      showToast(autoCleanWavToggle.checked ? '🧹 Авто-очистка WAV (>24ч) включена' : 'Авто-очистка WAV отключена');
    });
  }

  // #4 Visual Hype Timeline
  async function loadHypeTimeline(jobId) {
    if (!hypeTimelineBox || !hypeTimelineBars) return;
    try {
      const res = await fetch(`/api/jobs/${jobId}/hype-timeline`);
      if (!res.ok) {
        hypeTimelineBox.classList.add('hidden');
        return;
      }
      const data = await res.json();
      const bins = data.bins || [];
      if (!bins.length) {
        hypeTimelineBox.classList.add('hidden');
        return;
      }
      hypeTimelineBox.classList.remove('hidden');
      if (hypeTimelineSource) {
        hypeTimelineSource.textContent = data.source && data.source !== 'none' ? `(${data.source})` : '';
      }
      hypeTimelineBars.innerHTML = '';
      const totalDur = data.duration || 0;
      bins.forEach((b) => {
        const val = Math.max(0.06, Math.min(1, b.value || 0));
        const bar = document.createElement('div');
        bar.className = 'hype-bar';
        bar.style.height = `${Math.round(val * 100)}%`;
        bar.style.background =
          val >= 0.72 ? '#ff3b5c' : val >= 0.45 ? '#ffb800' : 'rgba(124, 92, 255, 0.55)';
        bar.title = `${formatDuration(b.t)} — хайп ${Math.round(val * 100)}% (клик = вырезать)`;
        bar.addEventListener('click', () => {
          const s = Math.max(0, b.t - 18);
          const e = Math.min(totalDur || (b.t + 14), s + 32);
          if (customStartInput) customStartInput.value = formatDuration(s);
          if (customEndInput) customEndInput.value = formatDuration(e);
          showToast(`Выбран пик ${formatDuration(s)} – ${formatDuration(e)}. Нажмите «Вырезать 9:16»!`);
        });
        hypeTimelineBars.appendChild(bar);
      });
    } catch (_) {
      hypeTimelineBox.classList.add('hidden');
    }
  }

  // #1 Twitch Top Clips Radar
  let lastRadarClips = [];
  if (btnSearchTwitchClips && radarStreamerInput) {
    const runRadarSearch = async () => {
      const streamer = (radarStreamerInput.value || '').trim();
      if (!streamer) return showToast('Введите ник стримера Twitch (латиницей)');
      btnSearchTwitchClips.disabled = true;
      btnSearchTwitchClips.textContent = '⏳...';
      try {
        const res = await fetch('/api/twitch-clips/search', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            streamer,
            period: radarPeriodSelect ? radarPeriodSelect.value : '7d',
            limit: 20,
          }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Не удалось загрузить клипы');
        lastRadarClips = data.clips || [];
        if (radarMeta) {
          radarMeta.textContent = lastRadarClips.length
            ? `Найдено ${lastRadarClips.length} топ-клипов канала ${lastRadarClips[0].streamer}`
            : 'За выбранный период клипов не найдено';
        }
        if (btnRadarTop5Batch) btnRadarTop5Batch.classList.toggle('hidden', lastRadarClips.length < 2);
        if (radarResultsGrid) {
          radarResultsGrid.classList.toggle('hidden', !lastRadarClips.length);
          radarResultsGrid.innerHTML = lastRadarClips.map((c, idx) => `
            <div class="radar-card">
              ${c.thumbnail ? `<img src="${escapeHtml(c.thumbnail)}" alt="" loading="lazy" />` : ''}
              <div class="radar-card-body">
                <div class="radar-title" title="${escapeHtml(c.title)}">${escapeHtml(c.title)}</div>
                <div class="radar-meta">👁 ${Number(c.views || 0).toLocaleString('ru-RU')} • ⏱ ${c.duration}с ${c.game ? '• ' + escapeHtml(c.game) : ''}</div>
                <button type="button" class="btn btn-primary btn-sm btn-radar-pick" data-idx="${idx}" style="margin-top:auto;">⚡ В 9:16</button>
              </div>
            </div>
          `).join('');
          radarResultsGrid.querySelectorAll('.btn-radar-pick').forEach((btn) => {
            btn.addEventListener('click', async () => {
              const clip = lastRadarClips[Number(btn.dataset.idx)];
              if (!clip) return;
              switchSourceTab('url');
              urlInput.value = clip.url;
              await probeUrl();
            });
          });
        }
      } catch (err) {
        showToast(err.message || 'Ошибка радара Twitch');
      } finally {
        btnSearchTwitchClips.disabled = false;
        btnSearchTwitchClips.textContent = '🔍 Найти';
      }
    };
    btnSearchTwitchClips.addEventListener('click', runRadarSearch);
    radarStreamerInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') runRadarSearch();
    });
  }

  if (btnRadarTop5Batch) {
    btnRadarTop5Batch.addEventListener('click', async () => {
      const top5 = lastRadarClips.slice(0, 5).map((c) => c.url);
      if (!top5.length) return;
      btnRadarTop5Batch.disabled = true;
      try {
        const res = await fetch('/api/batch-urls', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ urls: top5, options: { ...getCurrentOptions(0), clip_count: 1 } }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Ошибка запуска очереди');
        switchSourceTab('url');
        if (batchQueueBox) batchQueueBox.classList.remove('hidden');
        renderBatchStatus(data);
        pollBatchStatus();
        showToast('🚀 Топ-5 клипов Twitch отправлены в очередь нарезки!');
      } catch (err) {
        showToast(err.message || 'Ошибка очереди');
      } finally {
        btnRadarTop5Batch.disabled = false;
      }
    });
  }

  // #3 Live Stream Instant Clipper
  if (btnCaptureLive && liveStreamUrlInput) {
    btnCaptureLive.addEventListener('click', async () => {
      const url = (liveStreamUrlInput.value || '').trim();
      if (!url) return showToast('Вставьте ссылку на идущий стрим');
      const dur = parseInt(liveDurationSelect ? liveDurationSelect.value : '45', 10) || 45;
      btnCaptureLive.disabled = true;
      btnCaptureLive.textContent = `🔴 Запись ${dur}с...`;
      if (liveStatusText) liveStatusText.textContent = `Захват ${dur} сек прямого эфира... Пожалуйста, подождите.`;
      try {
        const res = await fetch('/api/live-clip', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url, duration_sec: dur, options: getCurrentOptions(0) }),
        });
        const job = await res.json();
        if (!res.ok) throw new Error(job.detail || 'Не удалось захватить эфир');
        state.currentJobId = job.job_id;
        showUploadedJob(job);
        progressSection.classList.remove('hidden');
        startPolling(job.job_id);
        showToast('🔴 Фрагмент эфира захвачен! Идёт распознавание и рендер 9:16...');
      } catch (err) {
        showToast(err.message || 'Ошибка захвата эфира');
        if (liveStatusText) liveStatusText.textContent = err.message || 'Ошибка захвата эфира';
      } finally {
        btnCaptureLive.disabled = false;
        btnCaptureLive.textContent = '🔴 Поймать';
      }
    });
  }

  // v2.4.0 Clean 4-Tab Studio Settings Navigation
  const studioTabsEl = document.getElementById('studioTabs');
  if (studioTabsEl) {
    const panes = document.querySelectorAll('.studio-tab-pane');
    studioTabsEl.querySelectorAll('.studio-tab').forEach((btn) => {
      btn.addEventListener('click', () => {
        const target = btn.dataset.stab;
        studioTabsEl.querySelectorAll('.studio-tab').forEach((b) => b.classList.toggle('active', b === btn));
        panes.forEach((p) => p.classList.toggle('hidden', p.dataset.spane !== target));
      });
    });
  }

  refreshOutrosList();
  init();
})();
