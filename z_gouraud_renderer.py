import math
import pyxel
from threed import Camera, Mesh


class ZBufferedGouraudRenderer:
    """
    Z-Buffer + Gouraud Shading Renderer

    - Zバッファで奥行きを正しく判定
    - バリセントリック座標で三角形をラスタライズ
    - 頂点ごとの明度を補間（Gouraud）
    """

    def __init__(
        self,
        camera: Camera,
        light_dir=(1.0, -1.0, -1.0),
        ambient: float = 0.2,
        shade_levels: int = 8,
    ):
        self.camera = camera
        self.ambient = ambient
        self.shade_levels = shade_levels

        # 画面サイズ
        # camera に screen_w, screen_h があればそれを使う
        if hasattr(camera, "screen_w") and hasattr(camera, "screen_h"):
            self.width = camera.screen_w
            self.height = camera.screen_h
        else:
            # cx, cy が画面中心ならこう
            self.width = camera.cx * 2
            self.height = camera.cy * 2

        # ライト方向を正規化（カメラ座標系前提）
        lx, ly, lz = light_dir
        L = math.sqrt(lx * lx + ly * ly + lz * lz) or 1.0
        self.light_dir = (lx / L, ly / L, lz / L)

        # Zバッファ
        self.z_far = 1e9
        self.zbuf = [[self.z_far] * self.width for _ in range(self.height)]

    # 毎フレーム最初に呼ぶ
    def clear_zbuffer(self):
        z_far = self.z_far
        for y in range(self.height):
            row = self.zbuf[y]
            for x in range(self.width):
                row[x] = z_far

    # ---------------------------------------------------
    # 頂点法線 → 光強度（0〜1）
    # ---------------------------------------------------
    def compute_intensity(self, nx, ny, nz):
        lx, ly, lz = self.light_dir
        dot = nx * lx + ny * ly + nz * lz
        if dot < 0:
            dot = 0.0
        # アンビエント込み
        i = self.ambient + dot * (1.0 - self.ambient)
        if i < 0.0:
            i = 0.0
        if i > 1.0:
            i = 1.0
        return i

    # ---------------------------------------------------
    # バリセントリック + Zバッファ付き Gouraud 三角形描画
    # p = (sx, sy), z = depth(>0), c = intensity(0..1)
    # ---------------------------------------------------
    def _draw_triangle(self, p0, z0, c0, p1, z1, c1, p2, z2, c2):
        x0, y0 = p0
        x1, y1 = p1
        x2, y2 = p2

        # 3点が一直線なら描かない
        denom = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if denom == 0:
            return

        w = self.width
        h = self.height
        zbuf = self.zbuf

        # 画面上のバウンディングボックス
        min_x = max(int(math.floor(min(x0, x1, x2))), 0)
        max_x = min(int(math.ceil(max(x0, x1, x2))), w - 1)
        min_y = max(int(math.floor(min(y0, y1, y2))), 0)
        max_y = min(int(math.ceil(max(y0, y1, y2))), h - 1)

        if min_x > max_x or min_y > max_y:
            return

        inv_denom = 1.0 / denom

        for y in range(min_y, max_y + 1):
            # ピクセル中心 (x+0.5, y+0.5) でサンプリング
            yy = y + 0.5
            for x in range(min_x, max_x + 1):
                xx = x + 0.5

                # バリセントリック座標 w0, w1, w2
                w0 = ((y1 - y2) * (xx - x2) + (x2 - x1) * (yy - y2)) * inv_denom
                w1 = ((y2 - y0) * (xx - x2) + (x0 - x2) * (yy - y2)) * inv_denom
                w2 = 1.0 - w0 - w1

                # 三角形の内側だけ描画（>=0 にして境界も含める）
                if w0 < 0.0 or w1 < 0.0 or w2 < 0.0:
                    continue

                # Z補間
                z = w0 * z0 + w1 * z1 + w2 * z2
                if z <= 0.0:
                    continue

                # Zバッファ比較
                if z >= zbuf[y][x]:
                    continue
                zbuf[y][x] = z

                # 明るさ補間
                c = w0 * c0 + w1 * c1 + w2 * c2
                if c < 0.0:
                    c = 0.0
                if c > 1.0:
                    c = 1.0

                shade = int(c * (self.shade_levels - 1))
                pyxel.pset(x, y, shade)

    # ---------------------------------------------------
    # メッシュ描画（メイン）
    # ---------------------------------------------------
    def draw_mesh(self, mesh: Mesh):
        cam = self.camera

        # 1. ローカル → ワールド → カメラ座標
        cam_pts = []
        for x, y, z in mesh.points:
            wx, wy, wz = mesh.local_to_world(x, y, z)
            cx, cy, cz = cam.world_to_camera(wx, wy, wz)
            cam_pts.append((cx, cy, cz))

        # 2. 投影（スクリーン座標）
        proj = [None] * len(cam_pts)
        for i, (x, y, z) in enumerate(cam_pts):
            if z <= 0.0:
                proj[i] = None
            else:
                sx, sy = cam.project(x, y, z)
                proj[i] = (float(sx), float(sy), float(z))

        # 3. 頂点法線（カメラ座標系で再計算）
        #    → Mesh の種類に依存しない汎用版
        vnorm = [(0.0, 0.0, 0.0) for _ in mesh.points]

        for i0, i1, i2 in mesh.faces:
            v0 = cam_pts[i0]
            v1 = cam_pts[i1]
            v2 = cam_pts[i2]

            ux, uy, uz = (v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2])
            vx, vy, vz = (v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2])

            # 面法線
            nx = uy * vz - uz * vy
            ny = uz * vx - ux * vz
            nz = ux * vy - uy * vx

            # 頂点に加算（後で正規化）
            for idx in (i0, i1, i2):
                nnx, nny, nnz = vnorm[idx]
                vnorm[idx] = (nnx + nx, nny + ny, nnz + nz)

        # 正規化＋明度計算
        intens = []
        for nx, ny, nz in vnorm:
            length = math.sqrt(nx * nx + ny * ny + nz * nz)
            if length == 0.0:
                ix = self.compute_intensity(0.0, 0.0, 1.0)
            else:
                ix = self.compute_intensity(nx / length, ny / length, nz / length)
            intens.append(ix)

        # 4. 各三角形を Zバッファ付きで描画
        #    ※ソート不要。順不同でOK。
        for i0, i1, i2 in mesh.faces:
            if proj[i0] is None or proj[i1] is None or proj[i2] is None:
                continue

            x0, y0, z0 = proj[i0]
            x1, y1, z1 = proj[i1]
            x2, y2, z2 = proj[i2]

            c0 = intens[i0]
            c1 = intens[i1]
            c2 = intens[i2]

            self._draw_triangle((x0, y0), z0, c0, (x1, y1), z1, c1, (x2, y2), z2, c2)
