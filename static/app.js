/**
 * MyRemotePC - Ultra-Low Latency Client Engine
 * High-speed binary WebSocket desktop receiver, canvas renderer, and input forwarder.
 */

class RemoteClient {
  constructor() {
    this.ws = null;
    this.token = localStorage.getItem('myremotepc_token') || '';
    this.canvas = document.getElementById('remoteCanvas');
    this.ctx = this.canvas.getContext('2d', { alpha: false });
    this.viewport = document.getElementById('viewport');

    // UI Elements
    this.authOverlay = document.getElementById('authOverlay');
    this.authForm = document.getElementById('authForm');
    this.accessCodeInput = document.getElementById('accessCodeInput');
    this.authErrorMsg = document.getElementById('authErrorMsg');
    this.displayHostName = document.getElementById('displayHostName');
    this.displayMachineId = document.getElementById('displayMachineId');
    this.topToolbar = document.getElementById('topToolbar');
    this.liveDot = document.getElementById('liveDot');
    this.fpsVal = document.getElementById('fpsVal');
    this.hostLabelShort = document.getElementById('hostLabelShort');

    // Stats HUD
    this.statsHud = document.getElementById('statsHud');
    this.hudFps = document.getElementById('hudFps');
    this.hudLatency = document.getElementById('hudLatency');
    this.hudBandwidth = document.getElementById('hudBandwidth');
    this.hudResolution = document.getElementById('hudResolution');

    // Modals & Dropdowns
    this.monitorBtn = document.getElementById('monitorBtn');
    this.monitorDropdown = document.getElementById('monitorDropdown');
    this.qualityBtn = document.getElementById('qualityBtn');
    this.qualityDropdown = document.getElementById('qualityDropdown');
    this.keysBtn = document.getElementById('keysBtn');
    this.keysDropdown = document.getElementById('keysDropdown');
    this.clipboardBtn = document.getElementById('clipboardBtn');
    this.clipboardModal = document.getElementById('clipboardModal');
    this.clipboardText = document.getElementById('clipboardText');

    // State Tracking
    this.isConnected = false;
    this.screenWidth = 1920;
    this.screenHeight = 1080;
    this.monitors = [];
    this.currentMonitor = 0;

    // Metrics Tracking
    this.frameCount = 0;
    this.lastFpsCalc = performance.now();
    this.bytesReceived = 0;
    this.lastBytesCalc = performance.now();
    this.rttLatency = 0;
    this.isHudVisible = false;

    // Input Throttling
    this.lastMouseMoveTime = 0;
    this.mouseMoveThrottleMs = 15; // ~66 Hz mouse reporting

    this.init();
  }

  async init() {
    this.setupEventListeners();
    await this.fetchServerStatus();

    // Auto-connect if token is present
    if (this.token) {
      this.connectWebSocket(this.token);
    }
  }

  async fetchServerStatus() {
    try {
      const res = await fetch('/api/status');
      if (res.ok) {
        const data = await res.json();
        this.displayHostName.innerHTML = `<span class="status-dot"></span> ${data.machine_name}`;
        this.displayMachineId.textContent = data.machine_id;
        this.hostLabelShort.textContent = data.machine_name;
        this.monitors = data.monitors || [];
        this.currentMonitor = data.current_monitor || 0;
        this.renderMonitorMenu();
      }
    } catch (e) {
      console.warn('Error fetching status:', e);
    }
  }

  setupEventListeners() {
    // Auth Form Submit
    this.authForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const code = this.accessCodeInput.value.trim();
      if (!code) return;
      await this.authenticate(code);
    });

    const quickFill = document.getElementById('quickFillBtn');
    if (quickFill) {
      quickFill.addEventListener('click', () => {
        this.accessCodeInput.value = '123456';
        this.authenticate('123456');
      });
    }

    // Toolbar dropdown toggles
    this.setupDropdown(this.monitorBtn, this.monitorDropdown);
    this.setupDropdown(this.qualityBtn, this.qualityDropdown);
    this.setupDropdown(this.keysBtn, this.keysDropdown);

    // Quality selection
    this.qualityDropdown.querySelectorAll('.dropdown-item').forEach(item => {
      item.addEventListener('click', () => {
        this.qualityDropdown.querySelectorAll('.dropdown-item').forEach(i => i.classList.remove('active'));
        item.classList.add('active');
        const q = item.dataset.quality;
        const fps = item.dataset.fps;
        this.sendJson({ type: 'set_quality', quality: parseInt(q), fps: parseInt(fps) });
        this.qualityDropdown.classList.remove('show');
      });
    });

    // Special Keys Menu
    document.getElementById('btnWinKey').addEventListener('click', () => {
      this.sendKeyCombo(['MetaLeft']);
      this.keysDropdown.classList.remove('show');
    });
    document.getElementById('btnShowDesktop').addEventListener('click', () => {
      this.sendJson({ type: 'show_desktop' });
      this.keysDropdown.classList.remove('show');
    });
    document.getElementById('btnLockScreen').addEventListener('click', () => {
      this.sendJson({ type: 'lock_screen' });
      this.keysDropdown.classList.remove('show');
    });
    document.getElementById('btnCtrlAltDel').addEventListener('click', () => {
      // Ctrl+Shift+Esc invokes Task Manager directly on Windows
      this.sendKeyCombo(['ControlLeft', 'ShiftLeft', 'Escape']);
      this.keysDropdown.classList.remove('show');
    });

    // Clipboard Modal Controls
    this.clipboardBtn.addEventListener('click', () => {
      this.clipboardModal.classList.add('show');
      this.sendJson({ type: 'clipboard_read' });
    });
    document.getElementById('clipCloseBtn').addEventListener('click', () => {
      this.clipboardModal.classList.remove('show');
    });
    document.getElementById('clipSendRemoteBtn').addEventListener('click', () => {
      const text = this.clipboardText.value;
      this.sendJson({ type: 'clipboard_write', text: text });
      this.clipboardModal.classList.remove('show');
    });
    document.getElementById('clipFetchRemoteBtn').addEventListener('click', () => {
      this.sendJson({ type: 'clipboard_read' });
    });

    // Stats Toggle
    document.getElementById('statsBtn').addEventListener('click', () => this.toggleHud());

    // Fullscreen Toggle
    document.getElementById('fullscreenBtn').addEventListener('click', () => {
      if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen().catch(() => {});
      } else {
        document.exitFullscreen().catch(() => {});
      }
    });

    // Disconnect Button
    document.getElementById('disconnectBtn').addEventListener('click', () => {
      this.disconnect();
    });

    // Close dropdowns on outside click
    window.addEventListener('click', (e) => {
      if (!e.target.closest('#monitorBtn') && !e.target.closest('#monitorDropdown')) {
        this.monitorDropdown.classList.remove('show');
      }
      if (!e.target.closest('#qualityBtn') && !e.target.closest('#qualityDropdown')) {
        this.qualityDropdown.classList.remove('show');
      }
      if (!e.target.closest('#keysBtn') && !e.target.closest('#keysDropdown')) {
        this.keysDropdown.classList.remove('show');
      }
    });

    // Canvas Mouse & Touch Input Capture
    this.canvas.addEventListener('mousemove', (e) => this.handleMouseMove(e));
    this.canvas.addEventListener('mousedown', (e) => this.handleMouseButton(e, 'down'));
    this.canvas.addEventListener('mouseup', (e) => this.handleMouseButton(e, 'up'));
    this.canvas.addEventListener('contextmenu', (e) => e.preventDefault());
    this.canvas.addEventListener('wheel', (e) => this.handleMouseWheel(e), { passive: false });

    // Touch Support for Mobile / Tablet
    this.setupTouchInput();

    // Keyboard Input Capture
    window.addEventListener('keydown', (e) => this.handleKeyDown(e));
    window.addEventListener('keyup', (e) => this.handleKeyUp(e));

    // Window Resize
    window.addEventListener('resize', () => this.resizeCanvasViewport());
  }

  setupDropdown(btn, menu) {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const isShown = menu.classList.contains('show');
      document.querySelectorAll('.dropdown-menu').forEach(m => m.classList.remove('show'));
      if (!isShown) menu.classList.add('show');
    });
  }

  renderMonitorMenu() {
    this.monitorDropdown.innerHTML = '';
    this.monitors.forEach(m => {
      const btn = document.createElement('button');
      btn.className = `dropdown-item ${m.index === this.currentMonitor ? 'active' : ''}`;
      btn.textContent = `${m.name} (${m.width}x${m.height})`;
      btn.addEventListener('click', () => {
        this.sendJson({ type: 'switch_monitor', index: m.index });
        this.monitorDropdown.classList.remove('show');
      });
      this.monitorDropdown.appendChild(btn);
    });
  }

  async authenticate(accessCode) {
    this.authErrorMsg.style.display = 'none';
    try {
      const res = await fetch('/api/auth', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ access_code: accessCode })
      });
      const data = await res.json();
      if (data.success && data.token) {
        this.token = data.token;
        localStorage.setItem('myremotepc_token', data.token);
        this.connectWebSocket(data.token);
      } else {
        this.authErrorMsg.textContent = data.error || 'Authentication failed';
        this.authErrorMsg.style.display = 'block';
      }
    } catch (e) {
      this.authErrorMsg.textContent = 'Server connection error';
      this.authErrorMsg.style.display = 'block';
    }
  }

  connectWebSocket(token) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws?token=${encodeURIComponent(token)}`;

    if (this.ws) {
      this.ws.close();
    }

    this.ws = new WebSocket(wsUrl);
    this.ws.binaryType = 'arraybuffer';

    this.ws.onopen = () => {
      console.log('[WebSocket] Connected to remote host');
      this.isConnected = true;
      this.authOverlay.classList.add('hidden');
      this.liveDot.style.background = '#10b981';
      this.startMetricsLoop();
    };

    this.ws.onmessage = async (e) => {
      if (typeof e.data === 'string') {
        this.handleTextMessage(JSON.parse(e.data));
      } else if (e.data instanceof ArrayBuffer) {
        await this.handleBinaryFrame(e.data);
      }
    };

    this.ws.onclose = () => {
      console.log('[WebSocket] Connection closed');
      this.isConnected = false;
      this.authOverlay.classList.remove('hidden');
      this.liveDot.style.background = '#ef4444';
    };

    this.ws.onerror = (err) => {
      console.error('[WebSocket] Error:', err);
    };
  }

  handleTextMessage(data) {
    if (data.type === 'screen_init') {
      this.screenWidth = data.width;
      this.screenHeight = data.height;
      this.canvas.width = data.width;
      this.canvas.height = data.height;
      this.monitors = data.monitors || [];
      this.currentMonitor = data.current_monitor || 0;
      this.renderMonitorMenu();
      this.resizeCanvasViewport();
    } else if (data.type === 'monitor_switched') {
      this.screenWidth = data.width;
      this.screenHeight = data.height;
      this.canvas.width = data.width;
      this.canvas.height = data.height;
      this.currentMonitor = data.index;
      this.renderMonitorMenu();
      this.resizeCanvasViewport();
    } else if (data.type === 'clipboard_content') {
      this.clipboardText.value = data.text || '';
    } else if (data.type === 'pong') {
      const now = performance.now();
      this.rttLatency = Math.round(now - data.t);
      this.hudLatency.textContent = `${this.rttLatency} ms`;
    } else if (data.type === 'auth_result' && !data.success) {
      localStorage.removeItem('myremotepc_token');
      this.authErrorMsg.textContent = data.error || 'Session expired. Re-enter code.';
      this.authErrorMsg.style.display = 'block';
      this.authOverlay.classList.remove('hidden');
    }
  }

  async handleBinaryFrame(buffer) {
    this.bytesReceived += buffer.byteLength;
    this.frameCount++;

    if (buffer.byteLength < 12) return;

    const view = new DataView(buffer);
    const magic = String.fromCharCode(view.getUint8(0), view.getUint8(1), view.getUint8(2), view.getUint8(3));
    if (magic !== 'RPC1') return;

    const width = view.getUint16(4, false);
    const height = view.getUint16(6, false);

    if (this.canvas.width !== width || this.canvas.height !== height) {
      this.canvas.width = width;
      this.canvas.height = height;
      this.screenWidth = width;
      this.screenHeight = height;
      this.resizeCanvasViewport();
    }

    // Extract JPEG blob (header is 12 bytes)
    const jpegBlob = new Blob([new Uint8Array(buffer, 12)], { type: 'image/jpeg' });
    try {
      const bitmap = await createImageBitmap(jpegBlob);
      this.ctx.drawImage(bitmap, 0, 0, width, height);
      bitmap.close();
    } catch (err) {
      console.warn('Frame render error:', err);
    }
  }

  resizeCanvasViewport() {
    const vWidth = this.viewport.clientWidth;
    const vHeight = this.viewport.clientHeight;
    const aspect = this.screenWidth / this.screenHeight;

    let targetWidth = vWidth;
    let targetHeight = vWidth / aspect;

    if (targetHeight > vHeight) {
      targetHeight = vHeight;
      targetWidth = vHeight * aspect;
    }

    this.canvas.style.width = `${Math.floor(targetWidth)}px`;
    this.canvas.style.height = `${Math.floor(targetHeight)}px`;
    this.hudResolution.textContent = `${this.screenWidth}x${this.screenHeight}`;
  }

  // Pointer & Input Handling
  handleMouseMove(e) {
    if (!this.isConnected) return;
    const now = performance.now();
    if (now - this.lastMouseMoveTime < this.mouseMoveThrottleMs) return;
    this.lastMouseMoveTime = now;

    const rect = this.canvas.getBoundingClientRect();
    const nx = Math.max(0.0, Math.min(1.0, (e.clientX - rect.left) / rect.width));
    const ny = Math.max(0.0, Math.min(1.0, (e.clientY - rect.top) / rect.height));

    this.sendJson({ type: 'mouse_move', x: nx, y: ny });
  }

  handleMouseButton(e, action) {
    if (!this.isConnected) return;
    e.preventDefault();
    let btn = 'left';
    if (e.button === 2) btn = 'right';
    else if (e.button === 1) btn = 'middle';

    this.sendJson({ type: 'mouse_button', button: btn, action: action });
  }

  handleMouseWheel(e) {
    if (!this.isConnected) return;
    e.preventDefault();
    const dy = Math.sign(e.deltaY);
    const dx = Math.sign(e.deltaX);
    this.sendJson({ type: 'mouse_wheel', delta_y: dy, delta_x: dx });
  }

  setupTouchInput() {
    let touchStartTime = 0;
    this.canvas.addEventListener('touchstart', (e) => {
      if (!this.isConnected || e.touches.length !== 1) return;
      touchStartTime = performance.now();
      const t = e.touches[0];
      const rect = this.canvas.getBoundingClientRect();
      const nx = (t.clientX - rect.left) / rect.width;
      const ny = (t.clientY - rect.top) / rect.height;
      this.sendJson({ type: 'mouse_move', x: nx, y: ny });
      this.sendJson({ type: 'mouse_button', button: 'left', action: 'down' });
    }, { passive: false });

    this.canvas.addEventListener('touchmove', (e) => {
      if (!this.isConnected || e.touches.length !== 1) return;
      e.preventDefault();
      const t = e.touches[0];
      const rect = this.canvas.getBoundingClientRect();
      const nx = (t.clientX - rect.left) / rect.width;
      const ny = (t.clientY - rect.top) / rect.height;
      this.sendJson({ type: 'mouse_move', x: nx, y: ny });
    }, { passive: false });

    this.canvas.addEventListener('touchend', (e) => {
      if (!this.isConnected) return;
      this.sendJson({ type: 'mouse_button', button: 'left', action: 'up' });
    });
  }

  handleKeyDown(e) {
    if (!this.isConnected || this.clipboardModal.classList.contains('show') || !this.authOverlay.classList.contains('hidden')) {
      return;
    }

    if (e.key === 'F2') {
      e.preventDefault();
      this.toggleHud();
      return;
    }

    // Intercept standard browser hotkeys so they pass to remote desktop
    if (['Tab', 'Backspace', 'Enter', 'Escape', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.key) || e.ctrlKey || e.altKey) {
      e.preventDefault();
    }

    this.sendJson({
      type: 'key',
      code: e.code,
      action: 'down',
      char: e.key.length === 1 ? e.key : null
    });
  }

  handleKeyUp(e) {
    if (!this.isConnected || this.clipboardModal.classList.contains('show') || !this.authOverlay.classList.contains('hidden')) {
      return;
    }
    this.sendJson({
      type: 'key',
      code: e.code,
      action: 'up',
      char: e.key.length === 1 ? e.key : null
    });
  }

  sendKeyCombo(keys) {
    keys.forEach(k => this.sendJson({ type: 'key', code: k, action: 'down' }));
    setTimeout(() => {
      keys.reverse().forEach(k => this.sendJson({ type: 'key', code: k, action: 'up' }));
    }, 50);
  }

  sendJson(obj) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(obj));
    }
  }

  toggleHud() {
    this.isHudVisible = !this.isHudVisible;
    this.statsHud.classList.toggle('hidden', !this.isHudVisible);
  }

  startMetricsLoop() {
    setInterval(() => {
      if (!this.isConnected) return;

      const now = performance.now();
      const elapsedSec = (now - this.lastFpsCalc) / 1000;
      const fps = Math.round(this.frameCount / elapsedSec);
      this.frameCount = 0;
      this.lastFpsCalc = now;

      const kbps = Math.round((this.bytesReceived / 1024) / elapsedSec);
      this.bytesReceived = 0;

      this.fpsVal.textContent = `${fps} FPS`;
      this.hudFps.textContent = `${fps}`;
      this.hudBandwidth.textContent = `${kbps} KB/s`;

      // Send ping for RTT latency
      this.sendJson({ type: 'ping', t: now });
    }, 1500);
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.isConnected = false;
    this.authOverlay.classList.remove('hidden');
    this.liveDot.style.background = '#ef4444';
  }
}

// Start client when DOM is ready
window.addEventListener('DOMContentLoaded', () => {
  window.client = new RemoteClient();
});
