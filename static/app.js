(() => {
  const state = {
    fonts: [],
    styles: [],
    currentJobId: null,
    pollTimer: null,
    selectedStyle: 'hormozi',
    selectedFont: 'montserrat',
    cropMode: 'fill',
    previewWordIdx: 0,
    previewWords: ['ЭТОТ', 'МОМЕНТ', 'ВЗОРВАЛ', 'ТИКТОК!'],
  };

  // DOM elements
  const sourceTabs = document.getElementById('sourceTabs');
  const urlPanel = document.getElementById('urlPanel');
  const filePanel = document.getElementById('filePanel');
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
  const webcamCorner = document.getElementById('webcamCorner');
  const webcamSize = document.getElementById('webcamSize');
  const webcamSizeVal = document.getElementById('webcamSizeVal');
  const styleCards = document.getElementById('styleCards');
  const fontSelect = document.getElementById('fontSelect');
  const fontSize = document.getElementById('fontSize');
  const subPosition = document.getElementById('subPosition');
  const uppercaseToggle = document.getElementById('uppercaseToggle');
  const hookBannerToggle = document.getElementById('hookBannerToggle');
  const jumpCutsToggle = document.getElementById('jumpCutsToggle');
  const fps60Toggle = document.getElementById('fps60Toggle');
  const videoEnhanceToggle = document.getElementById('videoEnhanceToggle');
  const ollamaRow = document.getElementById('ollamaRow');
  const ollamaSelect = document.getElementById('ollamaSelect');
  const hwBadge = document.getElementById('hwBadge');
  const watermarkInput = document.getElementById('watermarkInput');
  const bgMusicSelect = document.getElementById('bgMusicSelect');
  const musicFileInput = document.getElementById('musicFileInput');
  const btnUploadMusic = document.getElementById('btnUploadMusic');
  const btnStart = document.getElementById('btnStart');

  const previewScreen = document.getElementById('previewScreen');
  const previewSplitCam = document.getElementById('previewSplitCam');
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
    applyHardwareInfo(cfg.hardware);

    renderStyleCards();
    renderFontOptions();
    updateLivePreview();
    setInterval(() => {
      state.previewWordIdx = (state.previewWordIdx + 1) % state.previewWords.length;
      updateLivePreview();
    }, 620);

    await refreshMusicList();
    await refreshHistory();
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
    if (models.length > 0 && ollamaRow && ollamaSelect) {
      ollamaRow.classList.remove('hidden');
      ollamaSelect.innerHTML = '<option value="">Выкл (стандартный быстрый анализ)</option>';
      models.forEach((m) => {
        const opt = document.createElement('option');
        opt.value = m;
        opt.textContent = `🧠 ${m} (локально на GPU)`;
        ollamaSelect.appendChild(opt);
      });
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
    previewSplitCam.classList.toggle('hidden', state.cropMode !== 'split_stream');
    previewCenterLabel.textContent =
      state.cropMode === 'split_stream'
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
    previewHookBanner.classList.toggle('hidden', !hookBannerToggle.checked);

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
    if (tab === 'url') {
      urlPanel.classList.remove('hidden');
      filePanel.classList.add('hidden');
    } else {
      urlPanel.classList.add('hidden');
      filePanel.classList.remove('hidden');
      dropZone.classList.remove('hidden');
    }
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
  fontSelect.addEventListener('change', () => {
    state.selectedFont = fontSelect.value;
    updateLivePreview();
  });
  fontSize.addEventListener('change', updateLivePreview);
  subPosition.addEventListener('change', updateLivePreview);
  uppercaseToggle.addEventListener('change', updateLivePreview);
  hookBannerToggle.addEventListener('change', updateLivePreview);
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

  function getCurrentOptions() {
    return {
      clip_count: parseInt(clipCount.value, 10) || 5,
      min_duration: parseFloat(minDuration.value) || 20,
      max_duration: parseFloat(maxDuration.value) || 55,
      whisper_model: whisperModel.value,
      subtitle_style: state.selectedStyle,
      font_id: state.selectedFont,
      font_size: fontSize.value,
      crop_mode: state.cropMode,
      position: subPosition.value,
      uppercase: uppercaseToggle.checked,
      webcam_corner: webcamCorner.value,
      webcam_size: (parseInt(webcamSize.value, 10) || 28) / 100.0,
      show_hook_banner: hookBannerToggle.checked,
      watermark_text: (watermarkInput.value || '').trim() || null,
      watermark_opacity: 0.55,
      jump_cuts: jumpCutsToggle.checked,
      bg_music_id: bgMusicSelect.value || null,
      bg_music_volume: 0.18,
      target_fps: fps60Toggle && fps60Toggle.checked ? 60 : 30,
      video_enhance: !!(videoEnhanceToggle && videoEnhanceToggle.checked),
      ollama_model: ollamaSelect ? ollamaSelect.value || null : null,
    };
  }

  // Start processing
  btnStart.addEventListener('click', async () => {
    if (!state.currentJobId) return;
    const opts = getCurrentOptions();
    if (opts.max_duration < opts.min_duration) {
      showToast('Максимальная длина должна быть больше минимальной');
      return;
    }

    btnStart.disabled = true;
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
      return;
    }
    const job = await res.json();
    updateJobUI(job);
    startPolling(state.currentJobId);
  });

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
        refreshHistory();
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
    editTrimStart.value = clip.trim_start != null ? clip.trim_start : (job.source_type === 'url' ? 0 : clip.start);
    editTrimEnd.value = clip.trim_end != null ? clip.trim_end : (job.source_type === 'url' ? clip.duration : clip.end);
    editTranscriptInput.value = clip.transcript || '';
    clipEditorModal.classList.remove('hidden');
  }

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
      const res = await fetch(`/api/jobs/${job.job_id}/clips/${clip.id}/rerender`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...opts,
          edited_transcript: editTranscriptInput.value,
          edited_hook_text: editHookInput.value,
          trim_start: parseFloat(editTrimStart.value),
          trim_end: parseFloat(editTrimEnd.value),
        }),
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
      closeClipEditor();
      showToast('Клип перерендерен с вашими правками!');
    } catch (err) {
      showToast(err.message || 'Ошибка перерендера');
    } finally {
      btnSaveEditor.disabled = false;
      btnSaveEditor.textContent = '💾 Сохранить и перерендерить';
    }
  });

  function renderClips(job) {
    resultsSection.classList.remove('hidden');
    resultsMeta.textContent = `Проект: ${job.original_filename} • Клипов: ${job.clips.length} • Распознано слов: ${job.words_count || 0}`;
    if (job.clips.length > 0) {
      btnDownloadAllZip.href = `/api/jobs/${job.job_id}/download-all`;
      btnDownloadAllZip.classList.remove('hidden');
    } else {
      btnDownloadAllZip.classList.add('hidden');
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
        </div>
        <div class="clip-body">
          <div class="clip-title">${escapeHtml(clip.title || clip.id)}</div>
          <div class="clip-tags">
            ${(clip.tags || []).map((t) => `<span class="clip-tag">${escapeHtml(t)}</span>`).join('')}
          </div>
          <div class="clip-transcript">${escapeHtml(clip.transcript || 'Без речи')}</div>
          <div class="clip-actions">
            <a class="btn btn-primary btn-sm" href="${dlUrl}" download>⬇ Скачать MP4</a>
            <button type="button" class="btn btn-secondary btn-sm btn-edit">✏️ Редактор</button>
            <button type="button" class="btn btn-ghost btn-sm btn-rerender">🎨 Новый стиль</button>
            <button type="button" class="btn btn-ghost btn-sm btn-copy-cap">📋 Описание</button>
          </div>
        </div>
      `;

      card.querySelector('.btn-edit').addEventListener('click', () => openClipEditor(job, clip, card));

      card.querySelector('.btn-copy-cap').addEventListener('click', async () => {
        const txt = clip.tiktok_caption || `${clip.title}\n\n#нарезки #тикток #shorts`;
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
    let hasUpdateReady = false;
    let dismissedModalOnce = false;

    const closeUpdateModal = () => {
      updateModal.classList.add('hidden');
      dismissedModalOnce = true;
    };

    desk.getVersion().then((v) => {
      if (v) appVersionPill.textContent = `v${v}`;
    }).catch(() => {});

    btnCheckUpdates.addEventListener('click', () => {
      if (hasUpdateReady) {
        updateModal.classList.remove('hidden');
        return;
      }
      manualClick = true;
      dismissedModalOnce = false;
      btnCheckUpdates.disabled = true;
      desk.checkForUpdates().finally(() => {
        setTimeout(() => { btnCheckUpdates.disabled = false; }, 1500);
      });
    });

    btnInstallUpdate.addEventListener('click', () => desk.installUpdate());
    btnModalInstallNow.addEventListener('click', () => desk.installUpdate());
    btnOpenRelease.addEventListener('click', () => desk.openExternal(latestReleaseUrl));
    btnModalOpenRelease.addEventListener('click', () => desk.openExternal(latestReleaseUrl));
    btnDismissUpdate.addEventListener('click', () => updateBanner.classList.add('hidden'));
    btnCloseUpdateModal.addEventListener('click', closeUpdateModal);
    btnUpdateLater.addEventListener('click', closeUpdateModal);
    updateModalBackdrop.addEventListener('click', closeUpdateModal);

    desk.onUpdateStatus((payload) => {
      if (!payload) return;
      const st = payload.state;

      if (st === 'checking') {
        if (manualClick) showToast('Проверка обновлений...');
        return;
      }
      if (st === 'up-to-date') {
        if (manualClick) {
          showToast(payload.message || 'У вас установлена последняя версия!');
          manualClick = false;
        }
        return;
      }
      if (st === 'error') {
        if (manualClick) {
          showToast(payload.message || 'Ошибка проверки обновлений');
          manualClick = false;
        }
        return;
      }

      hasUpdateReady = true;
      if (updateDot) updateDot.classList.remove('hidden');

      // Update top subtle banner
      updateBanner.classList.remove('hidden');
      updateMessage.textContent = payload.message || 'Обновление TikCut Studio';
      updateBarWrap.classList.add('hidden');
      btnInstallUpdate.classList.add('hidden');
      btnOpenRelease.classList.add('hidden');

      // Update Center Modal
      if (payload.version && payload.currentVersion) {
        updateModalVersions.textContent = `v${payload.currentVersion} → v${payload.version}`;
      }
      updateModalStatus.textContent = payload.message || 'Обновление TikCut Studio';
      if (payload.releaseNotes) {
        updateModalNotes.textContent = payload.releaseNotes;
        updateModalNotesWrap.classList.remove('hidden');
      }

      updateModalProgressWrap.classList.add('hidden');
      btnModalInstallNow.classList.add('hidden');
      btnModalOpenRelease.classList.add('hidden');

      if (st === 'available') {
        updateModalTitle.textContent = `Найдено обновление v${payload.version || ''}`;
        if (!dismissedModalOnce) updateModal.classList.remove('hidden');
      } else if (st === 'downloading') {
        const pct = payload.percent || 0;
        updateBarWrap.classList.remove('hidden');
        updateBarFill.style.width = `${pct}%`;
        updateModalTitle.textContent = 'Загрузка обновления...';
        updateModalProgressWrap.classList.remove('hidden');
        updateModalBar.style.width = `${pct}%`;
        if (payload.doneMb && payload.totalMb) {
          updateModalSize.textContent = `${payload.doneMb} / ${payload.totalMb} МБ (${pct}%)`;
        }
        if (payload.speedMb) {
          updateModalSpeed.textContent = `${payload.speedMb} МБ/с`;
        }
      } else if (st === 'downloaded') {
        btnInstallUpdate.classList.remove('hidden');
        btnModalInstallNow.classList.remove('hidden');
        updateModalTitle.textContent = `Обновление v${payload.version || ''} готово!`;
        updateModal.classList.remove('hidden');
      } else if (st === 'manual-download') {
        latestReleaseUrl = payload.releaseUrl || null;
        btnOpenRelease.classList.remove('hidden');
        btnModalOpenRelease.classList.remove('hidden');
        updateModalTitle.textContent = `Доступно обновление v${payload.version || ''}`;
        if (!dismissedModalOnce) updateModal.classList.remove('hidden');
      }
    });
  }

  init();
})();
