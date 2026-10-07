/**
 * CollaborativeCanvas - Manages drawing gestures, local rendering,
 * and compact vector event synchronization.
 */
class CollaborativeCanvas {
  constructor(canvasElement, transport) {
    this.canvas = canvasElement;
    this.ctx = canvasElement.getContext("2d");
    this.transport = transport;

    // Drawing State
    this.isDrawing = false;
    this.lastX = 0;
    this.lastY = 0;
    this.tool = "pen"; // "pen" or "eraser"
    this.color = "#0f172a";
    this.width = 4;

    this._setupUIControls();
    this._attachEventListeners();
  }

  _setupUIControls() {
    const toolPen = document.getElementById("toolPen");
    const toolEraser = document.getElementById("toolEraser");
    const sizeSlider = document.getElementById("sizeSlider");
    const sizeValue = document.getElementById("sizeValue");
    const clearBtn = document.getElementById("clearBtn");
    const customColor = document.getElementById("customColor");
    const swatches = document.querySelectorAll(".color-swatch");

    // Tool switching
    toolPen.addEventListener("click", () => {
      this.tool = "pen";
      toolPen.classList.add("active");
      toolEraser.classList.remove("active");
    });

    toolEraser.addEventListener("click", () => {
      this.tool = "eraser";
      toolEraser.classList.add("active");
      toolPen.classList.remove("active");
    });

    // Size Slider
    sizeSlider.addEventListener("input", (e) => {
      this.width = parseInt(e.target.value, 10);
      sizeValue.textContent = `${this.width}px`;
    });

    // Palette Swatches
    swatches.forEach(swatch => {
      swatch.addEventListener("click", () => {
        swatches.forEach(s => s.classList.remove("active"));
        swatch.classList.add("active");
        this.color = swatch.getAttribute("data-color");
        customColor.value = this.color;
        // Auto switch back to pen if on eraser
        if (this.tool === "eraser") {
          toolPen.click();
        }
      });
    });

    // Custom Color Input
    customColor.addEventListener("input", (e) => {
      this.color = e.target.value;
      swatches.forEach(s => s.classList.remove("active"));
      if (this.tool === "eraser") {
        toolPen.click();
      }
    });

    // Clear Canvas
    clearBtn.addEventListener("click", () => {
      if (confirm("Are you sure you want to clear the canvas for everyone?")) {
        this.transport.sendAction({ type: "clear" });
      }
    });
  }

  _getCanvasCoordinates(e) {
    const rect = this.canvas.getBoundingClientRect();
    const scaleX = this.canvas.width / rect.width;
    const scaleY = this.canvas.height / rect.height;

    const clientX = e.touches ? e.touches[0].clientX : e.clientX;
    const clientY = e.touches ? e.touches[0].clientY : e.clientY;

    return {
      x: Math.round((clientX - rect.left) * scaleX * 100) / 100,
      y: Math.round((clientY - rect.top) * scaleY * 100) / 100
    };
  }

  _attachEventListeners() {
    // Mouse Events
    this.canvas.addEventListener("mousedown", (e) => this._startDrawing(e));
    window.addEventListener("mousemove", (e) => this._draw(e));
    window.addEventListener("mouseup", () => this._stopDrawing());

    // Touch Events for Tablets & Mobile
    this.canvas.addEventListener("touchstart", (e) => {
      e.preventDefault();
      this._startDrawing(e);
    }, { passive: false });

    window.addEventListener("touchmove", (e) => {
      if (this.isDrawing) e.preventDefault();
      this._draw(e);
    }, { passive: false });

    window.addEventListener("touchend", () => this._stopDrawing());
  }

  _startDrawing(e) {
    this.isDrawing = true;
    const coords = this._getCanvasCoordinates(e);
    this.lastX = coords.x;
    this.lastY = coords.y;

    // Draw single dot if clicked without dragging
    this._renderSegment(coords.x, coords.y, coords.x + 0.1, coords.y + 0.1, 
      this.tool === "eraser" ? "#ffffff" : this.color, this.width);

    this.transport.sendAction({
      type: "draw",
      x1: coords.x,
      y1: coords.y,
      x2: coords.x + 0.1,
      y2: coords.y + 0.1,
      color: this.color,
      width: this.width,
      mode: this.tool
    });
  }

  _draw(e) {
    if (!this.isDrawing) return;

    const coords = this._getCanvasCoordinates(e);
    const strokeColor = this.tool === "eraser" ? "#ffffff" : this.color;

    // Render locally immediately for responsive feedback
    this._renderSegment(this.lastX, this.lastY, coords.x, coords.y, strokeColor, this.width);

    // Send compact segment to TCP Core via Bridge
    this.transport.sendAction({
      type: "draw",
      x1: this.lastX,
      y1: this.lastY,
      x2: coords.x,
      y2: coords.y,
      color: this.color,
      width: this.width,
      mode: this.tool
    });

    this.lastX = coords.x;
    this.lastY = coords.y;
  }

  _stopDrawing() {
    this.isDrawing = false;
  }

  _renderSegment(x1, y1, x2, y2, color, width) {
    this.ctx.beginPath();
    this.ctx.lineCap = "round";
    this.ctx.lineJoin = "round";
    this.ctx.strokeStyle = color;
    this.ctx.lineWidth = width;
    this.ctx.moveTo(x1, y1);
    this.ctx.lineTo(x2, y2);
    this.ctx.stroke();
    this.ctx.closePath();
  }

  drawRemoteSegment(segment) {
    const strokeColor = segment.mode === "eraser" ? "#ffffff" : segment.color;
    this._renderSegment(segment.x1, segment.y1, segment.x2, segment.y2, strokeColor, segment.width);
  }

  clearCanvasLocally() {
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
  }

  loadHistory(strokes) {
    this.clearCanvasLocally();
    strokes.forEach(s => {
      if (s.type === "draw") {
        this.drawRemoteSegment(s);
      }
    });
  }
}
