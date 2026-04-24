"""
문제집 PDF -> 문제별 이미지 저장 프로그램
GUI 버전 (tkinter)
"""

import sys
import re
import os
import io
import threading
from pathlib import Path
from tkinter import filedialog, messagebox
import tkinter as tk
from tkinter import ttk

try:
    import fitz
    from PIL import Image, ImageTk, ImageDraw
except ImportError:
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    tk.messagebox.showerror("오류", "필요한 라이브러리가 없습니다.\n\npip install pymupdf Pillow")
    sys.exit(1)


# ─────────────────────────────────────────
# 상수
# ─────────────────────────────────────────
TOP_MARGIN  = 25
DPI         = 200
OUTPUT_FMT  = "png"
MAX_PAGE_GAP = 1
SAMPLE_W    = 280   # 샘플 이미지 너비(픽셀)
SAMPLE_H    = 360   # 샘플 이미지 높이(픽셀)


# ─────────────────────────────────────────
# 분석 함수들
# ─────────────────────────────────────────

def analyze_pdf(pdf_path):
    """
    PDF를 분석해서 반환:
      - groups: {font_size: [(num, page, x, y), ...], ...}
      - page_width: PDF 페이지 너비
    """
    groups = {}
    doc = fitz.open(pdf_path)
    page_width = doc[0].rect.width

    for page_num, page in enumerate(doc):
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span["text"].strip()
                    size = round(span["size"], 1)
                    # 숫자만 있는 텍스트
                    if not re.match(r'^\d+$', text):
                        continue
                    num = int(text)
                    if num < 1 or num > 9999:
                        continue
                    x = span["origin"][0]
                    y = span["bbox"][1]
                    groups.setdefault(size, []).append((num, page_num, x, y))

    doc.close()
    return groups, page_width


def detect_columns(positions, page_width):
    """
    문제 번호 x좌표 분포로 1단/2단 감지.
    반환: (column_count, split_x)
    """
    xs = [p[2] for p in positions]
    if not xs:
        return 1, page_width / 2

    mid = page_width / 2
    left  = [x for x in xs if x < mid]
    right = [x for x in xs if x >= mid]

    # 양쪽에 20% 이상 분포하면 2단
    ratio = len(right) / len(xs) if xs else 0
    if 0.2 <= ratio <= 0.8:
        return 2, mid
    return 1, mid


def make_sample_image(pdf_path, positions, col_count, split_x, sample_idx):
    """
    positions 중 처음/중간/끝 중 하나를 골라 샘플 이미지 반환.
    sample_idx: 0=처음, 1=중간, 2=끝
    """
    if not positions:
        return None

    n = len(positions)
    idx = [0, n // 2, n - 1][sample_idx]
    idx = min(idx, n - 1)

    q_num, q_page, q_x, q_y = positions[idx]

    # 다음 문제 위치
    if idx + 1 < n:
        _, nxt_page, nxt_x, nxt_y = positions[idx + 1]
    else:
        doc_tmp = fitz.open(pdf_path)
        nxt_page = q_page
        nxt_y    = doc_tmp[q_page].rect.height
        nxt_x    = q_x
        doc_tmp.close()

    doc = fitz.open(pdf_path)
    scale = DPI / 72

    def page_to_img(pn):
        mat = fitz.Matrix(DPI / 72, DPI / 72)
        pix = doc[pn].get_pixmap(matrix=mat)
        return Image.open(io.BytesIO(pix.tobytes("png")))

    col = 0 if q_x < split_x else 1
    nxt_col = 0 if nxt_x < split_x else 1

    qt = int(q_y   * scale) - TOP_MARGIN
    nt = int(nxt_y * scale) - TOP_MARGIN

    img_cur = page_to_img(q_page)
    page_gap = nxt_page - q_page

    def safe_crop(img, c, top, bottom):
        if col_count == 2:
            mid_px = img.width // 2
            x0 = 0 if c == 0 else mid_px
            x1 = mid_px if c == 0 else img.width
        else:
            x0, x1 = 0, img.width
        top    = max(0, top)
        bottom = min(img.height, bottom)
        if top >= bottom:
            bottom = img.height
        return img.crop((x0, top, x1, bottom))

    if q_page == nxt_page and col == nxt_col:
        cropped = safe_crop(img_cur, col, qt, nt)
    elif q_page == nxt_page and col == 0 and nxt_col == 1:
        cropped = safe_crop(img_cur, 0, qt, img_cur.height)
    elif page_gap <= MAX_PAGE_GAP:
        parts = []
        if col_count == 2:
            if col == 0:
                parts.append(safe_crop(img_cur, 0, qt, img_cur.height))
                parts.append(safe_crop(img_cur, 1, 0,  img_cur.height))
            else:
                parts.append(safe_crop(img_cur, 1, qt, img_cur.height))
        else:
            parts.append(safe_crop(img_cur, 0, qt, img_cur.height))
        img_nxt = page_to_img(nxt_page)
        if col_count == 2:
            if nxt_col == 0:
                parts.append(safe_crop(img_nxt, 0, 0, nt))
            else:
                parts.append(safe_crop(img_nxt, 0, 0, img_nxt.height))
                parts.append(safe_crop(img_nxt, 1, 0, nt))
        else:
            parts.append(safe_crop(img_nxt, 0, 0, nt))
        parts = [p for p in parts if p.height > 0]
        total_h = sum(p.height for p in parts)
        max_w   = max(p.width  for p in parts)
        combined = Image.new("RGB", (max_w, total_h), "white")
        yo = 0
        for p in parts:
            combined.paste(p, (0, yo)); yo += p.height
        cropped = combined
    else:
        if col_count == 2:
            if col == 0:
                p1 = safe_crop(img_cur, 0, qt, img_cur.height)
                p2 = safe_crop(img_cur, 1, 0,  img_cur.height)
                combined = Image.new("RGB", (max(p1.width, p2.width), p1.height + p2.height), "white")
                combined.paste(p1, (0, 0)); combined.paste(p2, (0, p1.height))
                cropped = combined
            else:
                cropped = safe_crop(img_cur, 1, qt, img_cur.height)
        else:
            cropped = safe_crop(img_cur, 0, qt, img_cur.height)

    doc.close()

    # 미리보기 크기로 리사이즈
    cropped.thumbnail((SAMPLE_W, SAMPLE_H), Image.LANCZOS)
    result = Image.new("RGB", (SAMPLE_W, SAMPLE_H), "#f0f0f0")
    offset_x = (SAMPLE_W - cropped.width)  // 2
    offset_y = (SAMPLE_H - cropped.height) // 2
    result.paste(cropped, (offset_x, offset_y))
    return result


def get_positions_from_group(groups, size_key, split_x=None):
    """
    선택된 폰트 크기 그룹에서 positions 리스트 반환.
    split_x 제공 시 (페이지, 컬럼, y) 순 정렬 → 2단 레이아웃 정확 처리.
    미제공 시 (페이지, y, x) 순 정렬.
    """
    items = groups.get(size_key, [])
    seen = set()
    result = []
    for num, page, x, y in items:
        # 같은 페이지·좌표의 완전 중복만 제거 (단원 재시작으로 인한 번호 중복은 유지)
        key = (num, page, round(x, 1), round(y, 1))
        if key not in seen:
            seen.add(key)
            result.append((num, page, x, y))
    if split_x is not None:
        result.sort(key=lambda p: (p[1], 0 if p[2] < split_x else 1, p[3]))
    else:
        result.sort(key=lambda p: (p[1], p[3], p[2]))
    return result


def detect_runs(positions):
    """
    페이지 순서 positions에서 연속 증가 시퀀스(런)를 감지.
    번호가 이전보다 작아질 때 새 런(=새 단원)으로 분리.
    반환: list of position-lists (각 런별 positions)
    """
    if not positions:
        return []
    runs, current = [], [positions[0]]
    for pos in positions[1:]:
        if pos[0] > current[-1][0]:
            current.append(pos)
        else:
            runs.append(current)
            current = [pos]
    runs.append(current)
    return runs


def group_run_info(positions):
    """
    그룹의 런 분석 정보 반환.
    반환: (runs, overall_max, label_text)
      - overall_max : 모든 런 중 가장 큰 문제 번호
      - label_text  : "1~23, 1~20  (총 2단원 / 43문제)" 형식
    """
    runs = detect_runs(positions)
    if not runs:
        return [], 0, ""
    run_maxes = [max(p[0] for p in r) for r in runs]
    overall_max = max(run_maxes)
    if len(runs) == 1:
        label = f"1~{run_maxes[0]}  ({len(positions)}문제)"
    else:
        parts = [f"1~{m}" for m in run_maxes[:4]]
        if len(runs) > 4:
            parts.append(f"... 외 {len(runs) - 4}단원")
        label = ", ".join(parts) + f"  (총 {len(runs)}단원 / {len(positions)}문제)"
    return runs, overall_max, label


# ─────────────────────────────────────────
# 이미지 저장 함수
# ─────────────────────────────────────────

def save_all_questions(pdf_path, positions, col_count, split_x, output_dir, progress_cb):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    doc   = fitz.open(pdf_path)
    scale = DPI / 72
    cache = {}

    def get_img(pn):
        # 이전 페이지 캐시 삭제 (메모리 확보)
        keys_to_remove = [k for k in cache.keys() if k < pn]
        for k in keys_to_remove:
            del cache[k]
        
        if pn not in cache:
            mat = fitz.Matrix(DPI / 72, DPI / 72)
            pix = doc[pn].get_pixmap(matrix=mat)
            cache[pn] = Image.open(io.BytesIO(pix.tobytes("png")))
        return cache[pn]

    def safe_crop(img, col, top, bottom):
        if col_count == 2:
            mid_px = img.width // 2
            x0 = 0 if col == 0 else mid_px
            x1 = mid_px if col == 0 else img.width
        else:
            x0, x1 = 0, img.width
        top    = max(0, top)
        bottom = min(img.height, bottom)
        if top >= bottom:
            bottom = img.height
        return img.crop((x0, top, x1, bottom))

    def stack(parts):
        parts = [p for p in parts if p and p.height > 0]
        if not parts: return None
        th = sum(p.height for p in parts)
        mw = max(p.width  for p in parts)
        out = Image.new("RGB", (mw, th), "white")
        yo = 0
        for p in parts:
            out.paste(p, (0, yo)); yo += p.height
        return out

    total = len(positions)
    num_count = {}
    for i, (q_num, q_page, q_x, q_y) in enumerate(positions):
        col = 0 if q_x < split_x else 1

        if i + 1 < total:
            _, nxt_page, nxt_x, nxt_y = positions[i + 1]
            nxt_col = 0 if nxt_x < split_x else 1
        else:
            nxt_page = q_page
            nxt_col  = col
            nxt_y    = doc[q_page].rect.height
            nxt_x    = q_x

        qt = int(q_y   * scale) - TOP_MARGIN
        nt = int(nxt_y * scale) - TOP_MARGIN
        page_gap = nxt_page - q_page
        img_cur  = get_img(q_page)

        if q_page == nxt_page and col == nxt_col:
            cropped = safe_crop(img_cur, col, qt, nt)
        elif q_page == nxt_page and col == 0 and nxt_col == 1:
            cropped = safe_crop(img_cur, 0, qt, img_cur.height)
        elif page_gap <= MAX_PAGE_GAP:
            parts = []
            if col_count == 2:
                if col == 0:
                    parts.append(safe_crop(img_cur, 0, qt, img_cur.height))
                    parts.append(safe_crop(img_cur, 1, 0,  img_cur.height))
                else:
                    parts.append(safe_crop(img_cur, 1, qt, img_cur.height))
            else:
                parts.append(safe_crop(img_cur, 0, qt, img_cur.height))
            img_nxt = get_img(nxt_page)
            if col_count == 2:
                if nxt_col == 0:
                    parts.append(safe_crop(img_nxt, 0, 0, nt))
                else:
                    parts.append(safe_crop(img_nxt, 0, 0, img_nxt.height))
                    parts.append(safe_crop(img_nxt, 1, 0, nt))
            else:
                parts.append(safe_crop(img_nxt, 0, 0, nt))
            cropped = stack(parts)
        else:
            if col_count == 2:
                if col == 0:
                    cropped = stack([
                        safe_crop(img_cur, 0, qt, img_cur.height),
                        safe_crop(img_cur, 1, 0,  img_cur.height),
                    ])
                else:
                    cropped = safe_crop(img_cur, 1, qt, img_cur.height)
            else:
                cropped = safe_crop(img_cur, 0, qt, img_cur.height)

        if cropped:
            cnt = num_count.get(q_num, 0) + 1
            num_count[q_num] = cnt
            suffix = f"_{cnt}" if cnt > 1 else ""
            cropped.save(output_dir / f"P{q_page+1:04d}_Q{q_num:04d}{suffix}.{OUTPUT_FMT}")

        progress_cb(i + 1, total)

    doc.close()


# ─────────────────────────────────────────
# GUI
# ─────────────────────────────────────────

class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("문제집 이미지 변환기")
        self.root.resizable(False, False)

        self.pdf_path   = None
        self.groups     = {}
        self.page_width = 0
        self.selected_size = tk.DoubleVar()
        self.col_var    = tk.IntVar(value=2)
        self.split_x    = 0
        self.positions  = []

        self._show_step1()
        self.root.mainloop()

    # ── 공통 헬퍼 ──────────────────────────────────────────────

    def _clear(self):
        for w in self.root.winfo_children():
            w.destroy()

    def _title(self, text, step):
        frm = tk.Frame(self.root, bg="#2c3e50", pady=12)
        frm.pack(fill="x")
        tk.Label(frm, text=f"STEP {step}  |  {text}",
                 bg="#2c3e50", fg="white",
                 font=("맑은 고딕", 13, "bold")).pack()

    def _btn(self, parent, text, cmd, primary=True):
        bg = "#2980b9" if primary else "#7f8c8d"
        b = tk.Button(parent, text=text, command=cmd,
                      bg=bg, fg="white", relief="flat",
                      font=("맑은 고딕", 10, "bold"),
                      padx=20, pady=8, cursor="hand2")
        b.bind("<Enter>", lambda e: b.config(bg="#1a6fa3" if primary else "#636e72"))
        b.bind("<Leave>", lambda e: b.config(bg=bg))
        return b

    # ── STEP 1: PDF 선택 ───────────────────────────────────────

    def _show_step1(self):
        self._clear()
        self.root.geometry("480x280")
        self._title("PDF 파일 선택", 1)

        body = tk.Frame(self.root, bg="white", padx=30, pady=30)
        body.pack(fill="both", expand=True)

        tk.Label(body, text="변환할 문제집 PDF 파일을 선택하세요",
                 bg="white", font=("맑은 고딕", 11)).pack(pady=(0, 20))

        self.path_var = tk.StringVar(value="선택된 파일 없음")
        tk.Label(body, textvariable=self.path_var,
                 bg="#f8f9fa", relief="solid", bd=1,
                 font=("맑은 고딕", 9), fg="#555",
                 wraplength=380, pady=8, padx=8).pack(fill="x", pady=(0, 20))

        btn_frm = tk.Frame(body, bg="white")
        btn_frm.pack()
        self._btn(btn_frm, "📂  파일 선택", self._pick_file).pack(side="left", padx=6)
        self._btn(btn_frm, "다음 →", self._step1_next, primary=True).pack(side="left", padx=6)

    def _pick_file(self):
        path = filedialog.askopenfilename(
            title="PDF 선택",
            filetypes=[("PDF 파일", "*.pdf")]
        )
        if path:
            self.pdf_path = path
            self.path_var.set(Path(path).name)

    def _step1_next(self):
        if not self.pdf_path:
            messagebox.showwarning("알림", "PDF 파일을 먼저 선택해주세요.")
            return
        # 분석 시작
        self._show_loading("PDF 분석 중...")
        threading.Thread(target=self._analyze_thread, daemon=True).start()

    def _show_loading(self, msg):
        self._clear()
        self.root.geometry("480x180")
        body = tk.Frame(self.root, bg="white", pady=50)
        body.pack(fill="both", expand=True)
        tk.Label(body, text=msg, bg="white",
                 font=("맑은 고딕", 12)).pack()
        pb = ttk.Progressbar(body, mode="indeterminate", length=300)
        pb.pack(pady=16)
        pb.start(10)

    def _analyze_thread(self):
        try:
            groups, pw = analyze_pdf(self.pdf_path)
            self.groups     = groups
            self.page_width = pw
            self.root.after(0, self._show_step2)
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("오류", str(e)))

    # ── STEP 2: 1단/2단 확인 ──────────────────────────────────

    def _show_step2(self, col_override=None):
        self._clear()
        self.root.geometry("560x480")
        self._title("문제집 구성 확인", 2)

        # 가장 많은 그룹의 positions로 감지
        best_size = max(self.groups, key=lambda s: len(self.groups[s]))
        positions = get_positions_from_group(self.groups, best_size)
        col_count, split_x = detect_columns(positions, self.page_width)
        self.split_x = split_x
        # 사용자가 직접 선택한 경우 자동감지 결과를 덮어쓰지 않음
        if col_override is not None:
            self.col_var.set(col_override)
        else:
            self.col_var.set(col_count)

        body = tk.Frame(self.root, bg="white", padx=24, pady=16)
        body.pack(fill="both", expand=True)

        tk.Label(body,
                 text=f"자동 감지 결과: {'2단' if col_count == 2 else '1단'} 구성",
                 bg="white", font=("맑은 고딕", 11, "bold"),
                 fg="#2c3e50").pack(pady=(0, 12))

        # 샘플 페이지 이미지 (컬럼 구분선 표시)
        sample_frm = tk.Frame(body, bg="#e0e0e0", relief="solid", bd=1)
        sample_frm.pack(pady=(0, 16))

        try:
            doc = fitz.open(self.pdf_path)
            page = doc[min(2, len(doc)-1)]
            mat  = fitz.Matrix(1.2, 1.2)
            pix  = page.get_pixmap(matrix=mat)
            doc.close()
            img  = Image.open(io.BytesIO(pix.tobytes("png")))
            img.thumbnail((460, 260), Image.LANCZOS)

            # 2단이면 가운데 구분선 그리기
            if self.col_var.get() == 2:
                draw = ImageDraw.Draw(img)
                mx   = img.width // 2
                draw.line([(mx, 0), (mx, img.height)], fill="red", width=2)

            self._step2_photo = ImageTk.PhotoImage(img)
            tk.Label(sample_frm, image=self._step2_photo, bg="white").pack()
        except Exception:
            tk.Label(sample_frm, text="미리보기 불가",
                     bg="white", width=50, height=8).pack()

        # 라디오 버튼
        radio_frm = tk.Frame(body, bg="white")
        radio_frm.pack(pady=(0, 16))
        tk.Radiobutton(radio_frm, text="1단 구성", variable=self.col_var,
                       value=1, bg="white",
                       font=("맑은 고딕", 11), command=self._update_step2_line).pack(side="left", padx=20)
        tk.Radiobutton(radio_frm, text="2단 구성", variable=self.col_var,
                       value=2, bg="white",
                       font=("맑은 고딕", 11), command=self._update_step2_line).pack(side="left", padx=20)

        btn_frm = tk.Frame(body, bg="white")
        btn_frm.pack()
        self._btn(btn_frm, "← 이전", self._show_step1, primary=False).pack(side="left", padx=6)
        self._btn(btn_frm, "다음 →", self._step2_next).pack(side="left", padx=6)

    def _update_step2_line(self):
        # 라디오 변경 시 구분선 업데이트를 위해 step2 재렌더
        self._show_step2_with_col(self.col_var.get())

    def _show_step2_with_col(self, col_count):
        self._show_step2(col_override=col_count)

    def _step2_next(self):
        self._show_step3()

    # ── STEP 3: 문제 번호 그룹 선택 ───────────────────────────

    def _show_step3(self):
        self._clear()
        col_count = self.col_var.get()

        # 런 최대값 >= 6인 그룹만 유효 (답지 번호 1~5 등 제외)
        MIN_RUN_MAX = 6
        valid = {}
        for s in self.groups:
            pos = get_positions_from_group(self.groups, s, self.split_x)
            if len(pos) < 5:
                continue
            _, run_max, _ = group_run_info(pos)
            if run_max >= MIN_RUN_MAX:
                valid[s] = pos

        if not valid:
            messagebox.showerror("오류", "문제 번호를 감지하지 못했습니다.")
            return

        # 그룹 수에 따라 창 높이 조정
        n_groups = len(valid)
        win_h    = min(200 + n_groups * 440, 860)
        self.root.geometry(f"1000x{win_h}")
        self._title("문제 번호 그룹 선택", 3)

        # 스크롤 가능한 캔버스
        outer = tk.Frame(self.root, bg="white")
        outer.pack(fill="both", expand=True)

        canvas = tk.Canvas(outer, bg="white", highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        scroll_frm = tk.Frame(canvas, bg="white")
        canvas_win = canvas.create_window((0, 0), window=scroll_frm, anchor="nw")

        def on_resize(e):
            canvas.itemconfig(canvas_win, width=e.width)
        canvas.bind("<Configure>", on_resize)

        scroll_frm.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        # 마우스 휠 스크롤
        canvas.bind_all("<MouseWheel>",
            lambda e: canvas.yview_scroll(-1 * (e.delta // 120), "units"))

        # 기본 선택: 런 최대값이 가장 큰 그룹 (문제 번호다운 그룹 우선)
        default_size = max(valid, key=lambda s: group_run_info(valid[s])[1])
        self.selected_size.set(default_size)

        self._step3_photos = []

        for size in sorted(valid.keys(), reverse=True):
            pos = valid[size]
            _, run_max, run_label = group_run_info(pos)

            grp_frm = tk.Frame(scroll_frm, bg="white",
                                relief="solid", bd=1, padx=12, pady=12)
            grp_frm.pack(fill="x", padx=16, pady=8)

            # 라디오 + 정보
            top_frm = tk.Frame(grp_frm, bg="white")
            top_frm.pack(fill="x", pady=(0, 10))

            tk.Radiobutton(top_frm,
                           text=f"폰트 크기 {size}  →  {run_label}",
                           variable=self.selected_size, value=size,
                           bg="white", font=("맑은 고딕", 10, "bold"),
                           fg="#2c3e50").pack(side="left")

            # 샘플 이미지 3개
            img_frm = tk.Frame(grp_frm, bg="white")
            img_frm.pack()

            labels = ["처음", "중간", "끝"]
            for idx in range(3):
                cell = tk.Frame(img_frm, bg="white")
                cell.pack(side="left", padx=8)

                tk.Label(cell, text=labels[idx],
                         bg="white", font=("맑은 고딕", 9),
                         fg="#888").pack(pady=(0, 4))

                try:
                    img = make_sample_image(
                        self.pdf_path, pos,
                        col_count, self.split_x, idx
                    )
                    photo = ImageTk.PhotoImage(img)
                    self._step3_photos.append(photo)
                    lbl = tk.Label(cell, image=photo,
                                   relief="solid", bd=1, bg="white")
                    lbl.pack()
                except Exception:
                    tk.Label(cell, text="미리보기\n불가",
                             width=18, height=10,
                             bg="#f0f0f0", relief="solid", bd=1).pack()

        # 하단 버튼
        btn_frm = tk.Frame(self.root, bg="white", pady=12)
        btn_frm.pack(fill="x")
        self._btn(btn_frm, "← 이전", self._show_step2, primary=False).pack(side="left", padx=16)
        self._btn(btn_frm, "선택 완료 →", self._step3_next).pack(side="right", padx=16)

    def _step3_next(self):
        size = self.selected_size.get()
        self.positions = get_positions_from_group(self.groups, size, self.split_x)
        if not self.positions:
            messagebox.showwarning("알림", "선택된 그룹에 문제가 없습니다.")
            return
        self._show_step4()

    # ── STEP 4: 출력 폴더 선택 ────────────────────────────────

    def _show_step4(self):
        self._clear()
        self.root.geometry("480x260")
        self._title("저장 폴더 선택", 4)

        body = tk.Frame(self.root, bg="white", padx=30, pady=30)
        body.pack(fill="both", expand=True)

        tk.Label(body, text="이미지를 저장할 폴더를 선택하세요",
                 bg="white", font=("맑은 고딕", 11)).pack(pady=(0, 16))

        default_out = str(Path(self.pdf_path).parent / (Path(self.pdf_path).stem + "_questions"))
        self.out_var = tk.StringVar(value=default_out)
        tk.Label(body, textvariable=self.out_var,
                 bg="#f8f9fa", relief="solid", bd=1,
                 font=("맑은 고딕", 9), fg="#555",
                 wraplength=380, pady=8, padx=8).pack(fill="x", pady=(0, 16))

        btn_frm = tk.Frame(body, bg="white")
        btn_frm.pack()
        self._btn(btn_frm, "📁  폴더 선택", self._pick_folder).pack(side="left", padx=6)
        self._btn(btn_frm, "← 이전", self._show_step3, primary=False).pack(side="left", padx=6)
        self._btn(btn_frm, "변환 시작 ▶", self._step4_next).pack(side="left", padx=6)

    def _pick_folder(self):
        folder = filedialog.askdirectory(title="저장 폴더 선택")
        if folder:
            self.out_var.set(folder)

    def _step4_next(self):
        self._show_step5()
        threading.Thread(target=self._convert_thread, daemon=True).start()

    # ── STEP 5: 진행바 ────────────────────────────────────────

    def _show_step5(self):
        self._clear()
        self.root.geometry("480x220")
        self._title("변환 중...", 5)

        body = tk.Frame(self.root, bg="white", padx=30, pady=30)
        body.pack(fill="both", expand=True)

        self.progress_label = tk.Label(body, text="변환 준비 중...",
                                        bg="white", font=("맑은 고딕", 10))
        self.progress_label.pack(pady=(0, 12))

        self.progress_bar = ttk.Progressbar(body, length=380,
                                             mode="determinate", maximum=100)
        self.progress_bar.pack()

    def _progress_cb(self, done, total):
        pct = int(done / total * 100)
        self.root.after(0, lambda: self.progress_bar.config(value=pct))
        self.root.after(0, lambda: self.progress_label.config(
            text=f"{done} / {total} 저장 중..."))

    def _convert_thread(self):
        try:
            save_all_questions(
                self.pdf_path,
                self.positions,
                self.col_var.get(),
                self.split_x,
                self.out_var.get(),
                self._progress_cb
            )
            self.root.after(0, self._show_done)
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("오류", str(e)))

    def _show_done(self):
        self._clear()
        self.root.geometry("480x240")
        self._title("완료!", 5)

        body = tk.Frame(self.root, bg="white", padx=30, pady=30)
        body.pack(fill="both", expand=True)

        tk.Label(body, text=f"✅  {len(self.positions)}개 문제 이미지 저장 완료!",
                 bg="white", font=("맑은 고딕", 12, "bold"),
                 fg="#27ae60").pack(pady=(0, 8))

        tk.Label(body, textvariable=self.out_var,
                 bg="white", font=("맑은 고딕", 9),
                 fg="#555", wraplength=380).pack(pady=(0, 20))

        btn_frm = tk.Frame(body, bg="white")
        btn_frm.pack()
        self._btn(btn_frm, "📂  폴더 열기", self._open_folder).pack(side="left", padx=6)
        self._btn(btn_frm, "처음으로", self._show_step1, primary=False).pack(side="left", padx=6)

    def _open_folder(self):
        os.startfile(self.out_var.get())


# ─────────────────────────────────────────
# 진입점
# ─────────────────────────────────────────

if __name__ == "__main__":
    App()
