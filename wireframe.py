import pyxel
import math

import time

from threed import Camera, Mesh

# from z_gouraud_renderer import ZBufferedGouraudRenderer
# from phong_renderer import PhongRenderer
# from hidden_line_renderer import HiddenLineRenderer
from wireframe_renderer import WireframeRenderer

FPS = 30


def generate_sphere_mesh_with_faces(radius=1.0, lat_steps=12, lon_steps=24):
    """
    球のメッシュ（頂点 + 三角形 faces）を生成する。

    返り値:
        points: [(x, y, z), ...]
        faces : [(i0, i1, i2), ...]    # CCW（反時計回り）で外側向き
    """

    points = []
    faces = []

    # --------------------------------------------
    # 1. 頂点生成
    # lat: 0..lat_steps（北極→南極）
    # lon: 0..lon_steps-1（0度→360度未満）
    # --------------------------------------------
    for lat in range(lat_steps + 1):
        theta = math.pi * lat / lat_steps  # 0..π
        sin_theta = math.sin(theta)
        cos_theta = math.cos(theta)

        for lon in range(lon_steps):
            phi = 2.0 * math.pi * lon / lon_steps  # 0..2π
            sin_phi = math.sin(phi)
            cos_phi = math.cos(phi)

            x = radius * sin_theta * cos_phi
            y = radius * cos_theta
            z = radius * sin_theta * sin_phi

            points.append((x, y, z))

    # インデックス変換
    def idx(lat, lon):
        return lat * lon_steps + (lon % lon_steps)

    # --------------------------------------------
    # 2. faces（三角形）生成
    #    - 各緯度帯ごとに、経度方向で quad（四角形）を2つの三角形に分割
    # --------------------------------------------
    for lat in range(lat_steps):
        for lon in range(lon_steps):
            i0 = idx(lat, lon)
            i1 = idx(lat + 1, lon)
            i2 = idx(lat, lon + 1)
            i3 = idx(lat + 1, lon + 1)

            # Quad → 2 triangles
            # 頂点順序は CCW（法線が外向きになる）
            faces.append((i0, i1, i2))
            faces.append((i2, i1, i3))

    return points, faces


def generate_icosphere_mesh(subdivisions=2, radius=1.0):
    import math

    # --------------------------------------
    # 1. 正二十面体の初期12頂点
    # --------------------------------------
    t = (1.0 + math.sqrt(5.0)) / 2.0  # golden ratio

    verts = [
        (-1, t, 0),
        (1, t, 0),
        (-1, -t, 0),
        (1, -t, 0),
        (0, -1, t),
        (0, 1, t),
        (0, -1, -t),
        (0, 1, -t),
        (t, 0, -1),
        (t, 0, 1),
        (-t, 0, -1),
        (-t, 0, 1),
    ]

    # normalize to radius
    def norm(v):
        x, y, z = v
        l = math.sqrt(x * x + y * y + z * z)
        return (radius * x / l, radius * y / l, radius * z / l)

    verts = [norm(v) for v in verts]

    # --------------------------------------
    # 2. 初期20面（三角形）
    # --------------------------------------
    faces = [
        (0, 11, 5),
        (0, 5, 1),
        (0, 1, 7),
        (0, 7, 10),
        (0, 10, 11),
        (1, 5, 9),
        (5, 11, 4),
        (11, 10, 2),
        (10, 7, 6),
        (7, 1, 8),
        (3, 9, 4),
        (3, 4, 2),
        (3, 2, 6),
        (3, 6, 8),
        (3, 8, 9),
        (4, 9, 5),
        (2, 4, 11),
        (6, 2, 10),
        (8, 6, 7),
        (9, 8, 1),
    ]

    # --------------------------------------
    # 3. midpoint キャッシュ
    # --------------------------------------
    midpoint_cache = {}

    def midpoint(i0, i1):
        """エッジ上の中点を生成し、キャッシュする"""
        key = tuple(sorted((i0, i1)))
        if key in midpoint_cache:
            return midpoint_cache[key]

        v0 = verts[i0]
        v1 = verts[i1]
        mx = (v0[0] + v1[0]) * 0.5
        my = (v0[1] + v1[1]) * 0.5
        mz = (v0[2] + v1[2]) * 0.5

        # 球面上へ正規化
        m = norm((mx, my, mz))
        verts.append(m)
        idx = len(verts) - 1
        midpoint_cache[key] = idx
        return idx

    # --------------------------------------
    # 4. subdivision を N 回
    # --------------------------------------
    for _ in range(subdivisions):
        new_faces = []
        midpoint_cache.clear()

        for i0, i1, i2 in faces:
            a = midpoint(i0, i1)
            b = midpoint(i1, i2)
            c = midpoint(i2, i0)

            # 4つの三角形に分割
            new_faces.append((i0, a, c))
            new_faces.append((i1, b, a))
            new_faces.append((i2, c, b))
            new_faces.append((a, b, c))

        faces = new_faces

    return verts, faces


class Wireframe:
    def __init__(self):
        self.rx = 0
        self.ry = 0
        self.rz = 0

        # points, faces = generate_sphere_mesh_with_faces(radius=1.0, lat_steps=8, lon_steps=16)
        points, faces = generate_icosphere_mesh(subdivisions=2, radius=1.0)
        self.sphere = Mesh(points, faces=faces, tx=0, ty=0, tz=0, scale=1.2)

        self.camera = Camera(
            rx=0,
            ry=0,
            rz=0,
            tx=0,
            ty=0,
            tz=-3,
            fov_y_deg=60,
            aspect_ratio=512 / 512,
            screen_w=512,
            screen_h=512,
            scale=300,
        )

        # self.renderer = WireframeRenderer(self.camera)
        self.renderer = WireframeRenderer(self.camera, color=7)
        # self.renderer = HiddenLineRenderer(
        #     self.camera,
        #     bg_color=0,
        #     light_dir=(1, -1, -1),
        #     shade_levels=5,
        #     base_color=7,
        # )
        # self.renderer = GouraudRenderer(self.camera, light_dir=(1,-1,-1))
        # self.renderer = ZBufferedGouraudRenderer(self.camera, light_dir=(1, -1, -1))
        # self.renderer = PhongRenderer(
        #     self.camera,
        #     light_dir=(1, -1, -1),
        #     ambient=0.2,
        #     diffuse=0.8,
        #     specular=0.4,
        #     shininess=32,
        #     shade_levels=16,   # Gouraudより滑らか
        # )

        self.last_time = time.time()
        self.frame_counter = 0
        self.current_fps = 0
        # self.prev_frame_time = self.last_time
        # self.utilization = 0.0
        self.target_frame_time = 1.0 / FPS  # 60FPS の理論フレーム時間

        self.measure_start = 0.0
        self.frame_compute_time = 0.0

        pyxel.init(512, 512, title="Wireframe", fps=FPS)
        pyxel.run(self.update, self.draw)

    def update(self):
        # 処理測定開始
        self.measure_start = time.time()

        # Update処理
        self.sphere.ry += 1

        # FPS 計測
        now = time.time()
        self.frame_counter += 1
        # now = time.time()
        if now - self.last_time >= 1.0:
            self.current_fps = self.frame_counter
            self.frame_counter = 0
            self.last_time = now

    def draw(self):
        # Draw処理
        pyxel.cls(0)
        # self.renderer.clear_zbuffer()
        self.renderer.draw_mesh(self.sphere)

        # 処理終了
        end = time.time()
        self.frame_compute_time = end - self.measure_start

        # Utliziation%の計算
        utilization = self.frame_compute_time / self.target_frame_time
        if utilization > 1.0:
            utilization = 1.0

        # FPS 表示（左上）
        pyxel.text(5, 5, f"FPS {self.current_fps}", 7)

        # 利用率％（0-100）
        util_percent = int(utilization * 100)
        pyxel.text(5, 15, f"UTIL {util_percent}%", 7)

        # わかりやすいバー表示も可能
        pyxel.rect(5, 25, util_percent, 5, 8)  # 簡易バーグラフ


Wireframe()
