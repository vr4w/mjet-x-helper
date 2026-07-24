from __future__ import annotations

import datetime as dt
import queue
import threading
import time
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

try:
    import cv2
except Exception:  # pragma: no cover - depends on local Windows test setup
    cv2 = None

try:
    from PIL import Image, ImageTk
except Exception:  # pragma: no cover - depends on local Windows test setup
    Image = None
    ImageTk = None


APP_TITLE = "DIGITALER FADENZÄHLER - PROTOTYP"
DEFAULT_INTERVAL_SECONDS = 2.0
CAMERA_SCAN_RANGE = range(0, 10)
PREFERRED_RESOLUTIONS = [(3840, 2160), (2560, 1440), (1920, 1080)]


@dataclass
class CameraSource:
    index: int
    label: str


class CameraWorker:
    def __init__(
        self,
        frame_queue: queue.Queue,
        status_callback: callable,
    ):
        self.frame_queue = frame_queue
        self.status_callback = status_callback
        self.capture = None
        self.thread: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.lock = threading.Lock()

    def start(self, index: int) -> None:
        self.stop()
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, args=(index,), daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
        self.thread = None
        with self.lock:
            if self.capture is not None:
                try:
                    self.capture.release()
                except Exception:
                    pass
                self.capture = None

    def _run(self, index: int) -> None:
        if cv2 is None:
            self.status_callback("Kamerafehler: OpenCV ist nicht installiert")
            return

        cap = None
        try:
            cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
            if not cap or not cap.isOpened():
                self.status_callback(f"Kamerafehler: Kamera {index} konnte nicht geöffnet werden")
                return

            with self.lock:
                self.capture = cap

            self._apply_preferred_resolution(cap)
            self.status_callback("Verbunden")

            failed_reads = 0
            while not self.stop_event.is_set():
                ok, frame = cap.read()
                if not ok or frame is None:
                    failed_reads += 1
                    if failed_reads >= 10:
                        self.status_callback("Kamerafehler: kein Bild von der Kamera")
                        break
                    time.sleep(0.05)
                    continue

                failed_reads = 0
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                self._put_latest_frame(frame)
                time.sleep(0.01)
        except Exception as exc:
            self.status_callback(f"Kamerafehler: {exc}")
        finally:
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass
            with self.lock:
                self.capture = None

    def _put_latest_frame(self, frame: object) -> None:
        while True:
            try:
                self.frame_queue.get_nowait()
            except queue.Empty:
                break
        try:
            self.frame_queue.put_nowait(frame)
        except queue.Full:
            pass

    def _apply_preferred_resolution(self, cap: object) -> None:
        for width, height in PREFERRED_RESOLUTIONS:
            try:
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
                actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                if actual_width >= width * 0.8 and actual_height >= height * 0.8:
                    return
            except Exception:
                continue


class DigitalFadenzaehlerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1100x760")
        self.root.minsize(780, 520)
        self.root.configure(bg="#e7e9ec")

        self.frame_queue: queue.Queue = queue.Queue(maxsize=1)
        self.camera_worker = CameraWorker(self.frame_queue, self._threadsafe_status)

        self.camera_sources: list[CameraSource] = []
        self.latest_frame = None
        self.display_frame = None
        self.tk_image = None
        self.running = False
        self.fullscreen = False
        self.mode_var = tk.StringVar(value="LIVE")
        self.interval_var = tk.StringVar(value="2 Sekunden")
        self.zoom_var = tk.IntVar(value=100)
        self.crosshair_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="Nicht verbunden")
        self.camera_var = tk.StringVar(value="")

        self.pan_x = 0.5
        self.pan_y = 0.5
        self.drag_start: tuple[int, int, float, float] | None = None
        self.last_auto_update = 0.0

        self._build_ui()
        self._bind_events()
        self.scan_cameras_async()
        self._poll_frames()
        self._redraw_loop()

    def _build_ui(self) -> None:
        toolbar = tk.Frame(self.root, bg="#f6f7f8", padx=10, pady=8)
        toolbar.pack(fill="x")

        tk.Label(toolbar, text="Kamera", bg="#f6f7f8", fg="#20242a", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w")
        self.camera_combo = ttk.Combobox(toolbar, textvariable=self.camera_var, state="readonly", width=32)
        self.camera_combo.grid(row=1, column=0, sticky="ew", padx=(0, 8))
        ttk.Button(toolbar, text="Kameras neu suchen", command=self.scan_cameras_async).grid(row=1, column=1, padx=(0, 8))
        ttk.Button(toolbar, text="Kamera starten", command=self.start_camera).grid(row=1, column=2, padx=(0, 4))
        ttk.Button(toolbar, text="Kamera stoppen", command=self.stop_camera).grid(row=1, column=3, padx=(0, 10))

        tk.Label(toolbar, textvariable=self.status_var, bg="#f6f7f8", fg="#1d3348", font=("Segoe UI", 10, "bold")).grid(row=1, column=4, sticky="w")
        toolbar.columnconfigure(0, weight=1)

        options = tk.Frame(self.root, bg="#e7e9ec", padx=10, pady=8)
        options.pack(fill="x")

        for label in ("LIVE", "AUTO-STANDBILD", "FREEZE"):
            ttk.Radiobutton(options, text=label, variable=self.mode_var, value=label).pack(side="left", padx=(0, 12))

        tk.Label(options, text="Intervall", bg="#e7e9ec").pack(side="left", padx=(8, 4))
        ttk.Combobox(
            options,
            textvariable=self.interval_var,
            state="readonly",
            width=12,
            values=("0,5 Sekunden", "1 Sekunde", "2 Sekunden", "3 Sekunden", "5 Sekunden"),
        ).pack(side="left", padx=(0, 14))

        tk.Label(options, text="Zoom", bg="#e7e9ec").pack(side="left", padx=(0, 4))
        self.zoom_scale = ttk.Scale(options, from_=100, to=500, variable=self.zoom_var, command=lambda _v: self.redraw_image())
        self.zoom_scale.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.zoom_label = tk.Label(options, text="100%", bg="#e7e9ec", width=6)
        self.zoom_label.pack(side="left", padx=(0, 8))
        ttk.Button(options, text="Zoom zurücksetzen", command=self.reset_zoom).pack(side="left", padx=(0, 8))
        ttk.Checkbutton(options, text="Fadenkreuz", variable=self.crosshair_var, command=self.redraw_image).pack(side="left", padx=(0, 8))
        ttk.Button(options, text="Bild speichern", command=self.save_image).pack(side="left", padx=(0, 8))
        ttk.Button(options, text="Vollbild", command=self.toggle_fullscreen).pack(side="left")

        self.canvas = tk.Canvas(self.root, bg="#20242a", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.canvas_text = self.canvas.create_text(
            20,
            20,
            anchor="nw",
            text="Keine Kamera verbunden",
            fill="#dfe3e7",
            font=("Segoe UI", 16, "bold"),
        )

    def _bind_events(self) -> None:
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.bind("<Escape>", self.exit_fullscreen)
        self.canvas.bind("<Configure>", lambda _event: self.redraw_image())
        self.canvas.bind("<ButtonPress-1>", self._start_drag)
        self.canvas.bind("<B1-Motion>", self._drag_image)
        self.zoom_var.trace_add("write", lambda *_args: self._update_zoom_label())

    def scan_cameras_async(self) -> None:
        self.status_var.set("Kameras werden gesucht...")
        thread = threading.Thread(target=self._scan_cameras_worker, daemon=True)
        thread.start()

    def _scan_cameras_worker(self) -> None:
        sources: list[CameraSource] = []
        if cv2 is not None:
            for index in CAMERA_SCAN_RANGE:
                cap = None
                try:
                    cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
                    if cap and cap.isOpened():
                        label = f"Kamera {index}"
                        sources.append(CameraSource(index=index, label=label))
                except Exception:
                    pass
                finally:
                    if cap is not None:
                        try:
                            cap.release()
                        except Exception:
                            pass
        self.root.after(0, lambda: self._apply_camera_sources(sources))

    def _apply_camera_sources(self, sources: list[CameraSource]) -> None:
        self.camera_sources = sources
        values = [source.label for source in sources]
        self.camera_combo.configure(values=values)
        if values:
            self.camera_var.set(values[0])
            self.status_var.set("Nicht verbunden")
        else:
            self.camera_var.set("")
            if cv2 is None:
                self.status_var.set("Kamerafehler: OpenCV fehlt")
            else:
                self.status_var.set("Keine Kamera gefunden")

    def start_camera(self) -> None:
        source = self._selected_camera_source()
        if source is None:
            messagebox.showwarning(APP_TITLE, "Keine Kamera ausgewählt.")
            return
        self.running = True
        self.status_var.set("Verbinde...")
        self.camera_worker.start(source.index)

    def stop_camera(self) -> None:
        self.running = False
        self.camera_worker.stop()
        self.status_var.set("Nicht verbunden")

    def _selected_camera_source(self) -> CameraSource | None:
        label = self.camera_var.get()
        for source in self.camera_sources:
            if source.label == label:
                return source
        return None

    def _poll_frames(self) -> None:
        try:
            while True:
                self.latest_frame = self.frame_queue.get_nowait()
                if self.mode_var.get() == "LIVE":
                    self.display_frame = self.latest_frame
                elif self.mode_var.get() == "AUTO-STANDBILD":
                    now = time.monotonic()
                    if now - self.last_auto_update >= self._interval_seconds():
                        self.display_frame = self.latest_frame
                        self.last_auto_update = now
                elif self.mode_var.get() == "FREEZE" and self.display_frame is None:
                    self.display_frame = self.latest_frame
        except queue.Empty:
            pass
        self.root.after(25, self._poll_frames)

    def _redraw_loop(self) -> None:
        self.redraw_image()
        self.root.after(80, self._redraw_loop)

    def redraw_image(self) -> None:
        if Image is None or ImageTk is None:
            self.canvas.itemconfigure(self.canvas_text, text="Pillow ist nicht installiert")
            return
        if self.display_frame is None:
            self.canvas.delete("image")
            self.canvas.itemconfigure(self.canvas_text, text=self.status_var.get() or "Kein Bild")
            return

        self.canvas.itemconfigure(self.canvas_text, text="")
        canvas_w = max(1, self.canvas.winfo_width())
        canvas_h = max(1, self.canvas.winfo_height())
        image = Image.fromarray(self.display_frame)
        image = self._cropped_zoom_image(image)
        image.thumbnail((canvas_w, canvas_h), Image.Resampling.LANCZOS)
        self.tk_image = ImageTk.PhotoImage(image)
        self.canvas.delete("image")
        x = (canvas_w - image.width) // 2
        y = (canvas_h - image.height) // 2
        self.canvas.create_image(x, y, anchor="nw", image=self.tk_image, tags="image")
        if self.crosshair_var.get():
            self._draw_crosshair(canvas_w, canvas_h)

    def _cropped_zoom_image(self, image: object) -> object:
        zoom = max(100, min(500, int(float(self.zoom_var.get())))) / 100.0
        if zoom <= 1.0:
            return image
        width, height = image.size
        crop_w = max(1, int(width / zoom))
        crop_h = max(1, int(height / zoom))
        max_x = max(0, width - crop_w)
        max_y = max(0, height - crop_h)
        left = int(max_x * self.pan_x)
        top = int(max_y * self.pan_y)
        return image.crop((left, top, left + crop_w, top + crop_h))

    def _draw_crosshair(self, canvas_w: int, canvas_h: int) -> None:
        self.canvas.delete("crosshair")
        cx = canvas_w // 2
        cy = canvas_h // 2
        self.canvas.create_line(cx - 40, cy, cx + 40, cy, fill="#ff4d4d", width=1, tags=("image", "crosshair"))
        self.canvas.create_line(cx, cy - 40, cx, cy + 40, fill="#ff4d4d", width=1, tags=("image", "crosshair"))

    def _start_drag(self, event: tk.Event) -> None:
        self.drag_start = (event.x, event.y, self.pan_x, self.pan_y)

    def _drag_image(self, event: tk.Event) -> None:
        if not self.drag_start:
            return
        start_x, start_y, start_pan_x, start_pan_y = self.drag_start
        canvas_w = max(1, self.canvas.winfo_width())
        canvas_h = max(1, self.canvas.winfo_height())
        zoom = max(100, min(500, int(float(self.zoom_var.get())))) / 100.0
        if zoom <= 1.0:
            return
        self.pan_x = min(1.0, max(0.0, start_pan_x - (event.x - start_x) / canvas_w / zoom))
        self.pan_y = min(1.0, max(0.0, start_pan_y - (event.y - start_y) / canvas_h / zoom))
        self.redraw_image()

    def _interval_seconds(self) -> float:
        value = self.interval_var.get()
        if value.startswith("0,5"):
            return 0.5
        match = "".join(ch for ch in value if ch.isdigit())
        return float(match or DEFAULT_INTERVAL_SECONDS)

    def _update_zoom_label(self) -> None:
        self.zoom_label.configure(text=f"{int(float(self.zoom_var.get()))}%")

    def reset_zoom(self) -> None:
        self.zoom_var.set(100)
        self.pan_x = 0.5
        self.pan_y = 0.5
        self.redraw_image()

    def save_image(self) -> None:
        if Image is None:
            messagebox.showwarning(APP_TITLE, "Pillow ist nicht installiert.")
            return
        if self.display_frame is None:
            messagebox.showwarning(APP_TITLE, "Kein Bild zum Speichern vorhanden.")
            return
        default_name = f"fadenzaehler_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        path = filedialog.asksaveasfilename(
            title="Bild speichern",
            defaultextension=".png",
            initialfile=default_name,
            filetypes=[("PNG", "*.png")],
        )
        if not path:
            return
        Image.fromarray(self.display_frame).save(path)
        self.status_var.set(f"Bild gespeichert: {Path(path).name}")

    def toggle_fullscreen(self) -> None:
        self.fullscreen = not self.fullscreen
        self.root.attributes("-fullscreen", self.fullscreen)

    def exit_fullscreen(self, _event: tk.Event | None = None) -> None:
        if self.fullscreen:
            self.fullscreen = False
            self.root.attributes("-fullscreen", False)

    def _threadsafe_status(self, text: str) -> None:
        self.root.after(0, lambda: self.status_var.set(text))

    def on_close(self) -> None:
        self.camera_worker.stop()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    DigitalFadenzaehlerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
