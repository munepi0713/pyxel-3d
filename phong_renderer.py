import math
import pyxel
from threed import Camera, Mesh
import random


def hash01(x: int, y: int) -> float:
    return (((x * 73856093) ^ (y * 19349663)) & 0xFF) / 255.0


class PhongRenderer:
    """
    Z-Buffer + Phong Shading Renderer
    --------------------------------------
    - バリセントリック座標で法線を補間
    - 各ピクセルで diffuse + specular 計算
    """

    def __init__(
        self,
        camera,
        light_dir=(1.0, -1.0, -1.0),
        ambient=0.2,
        diffuse=0.8,
        specular=0.4,
        shininess=32,
        shade_levels=16,
        dithering=False,
        highlighting=False,
    ):
        self.camera = camera
        self.ambient = ambient
        self.diffuse = diffuse
        self.specular = specular
        self.shininess = shininess
        self.shade_levels = shade_levels
        self.dithering = dithering
        self.highlighting = highlighting

        # 画面サイズ
        if hasattr(camera, "screen_w"):
            self.width = camera.screen_w
            self.height = camera.screen_h
        else:
            self.width = camera.cx * 2
            self.height = camera.cy * 2

        # ライト方向を正規化（カメラ座標系）
        lx, ly, lz = light_dir
        L = math.sqrt(lx * lx + ly * ly + lz * lz) or 1.0
        self.light_dir = (lx / L, ly / L, lz / L)

        # Z buffer
        self.z_far = 1e9
        self.zbuf = [[self.z_far] * self.width for _ in range(self.height)]

    # -----------------------------
    # フレーム開始時に呼ぶ（Zバッファ初期化）
    # -----------------------------
    def clear_zbuffer(self):
        zf = self.z_far
        for y in range(self.height):
            row = self.zbuf[y]
            for x in range(self.width):
                row[x] = zf

    # -----------------------------
    # ピクセル単位 Phong シェーディング（0〜1）
    # -----------------------------
    def phong_intensity(self, nx, ny, nz):
        lx, ly, lz = self.light_dir

        # Lambert（拡散）
        diff = nx * lx + ny * ly + nz * lz
        if diff < 0:
            diff = 0.0

        # 反射ベクトルを作る必要はない
        # カメラ空間では eye = (0,0,1) として簡略化できる
        view_z = 1.0
        spec = 0.0
        if diff > 0:
            # R = 2(N·L)N - L  （省略形）
            rx = 2 * diff * nx - lx
            ry = 2 * diff * ny - ly
            rz = 2 * diff * nz - lz

            # V·R（視線方向は (0,0,1)）
            vr = rz
            if vr > 0:
                spec = (vr**self.shininess) * self.specular

        i = self.ambient + diff * self.diffuse + spec
        return max(0.0, min(1.0, i))

    # -----------------------------
    # バリセントリック + Zバッファ + Phong
    # -----------------------------
    def _draw_triangle(self, p0, z0, n0, p1, z1, n1, p2, z2, n2):
        (x0, y0) = p0
        (x1, y1) = p1
        (x2, y2) = p2

        denom = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if denom == 0:
            return
        inv_denom = 1.0 / denom

        w = self.width
        h = self.height
        zbuf = self.zbuf

        # bounding box
        min_x = max(int(min(x0, x1, x2)), 0)
        max_x = min(int(max(x0, x1, x2)), w - 1)
        min_y = max(int(min(y0, y1, y2)), 0)
        max_y = min(int(max(y0, y1, y2)), h - 1)

        if min_x > max_x or min_y > max_y:
            return

        # 頂点法線
        nx0, ny0, nz0 = n0
        nx1, ny1, nz1 = n1
        nx2, ny2, nz2 = n2

        for y in range(min_y, max_y + 1):
            yy = y + 0.5
            for x in range(min_x, max_x + 1):
                xx = x + 0.5

                # barycentric
                w0 = ((y1 - y2) * (xx - x2) + (x2 - x1) * (yy - y2)) * inv_denom
                if w0 < 0:
                    continue
                w1 = ((y2 - y0) * (xx - x2) + (x0 - x2) * (yy - y2)) * inv_denom
                if w1 < 0:
                    continue
                w2 = 1.0 - w0 - w1
                if w2 < 0:
                    continue

                # depth
                z = w0 * z0 + w1 * z1 + w2 * z2
                if z <= 0:
                    continue

                if z >= zbuf[y][x]:
                    continue
                zbuf[y][x] = z

                # 法線補間（Phong の本質）
                nx = w0 * nx0 + w1 * nx1 + w2 * nx2
                ny = w0 * ny0 + w1 * ny1 + w2 * ny2
                nz = w0 * nz0 + w1 * nz1 + w2 * nz2

                # normalize
                length = math.sqrt(nx * nx + ny * ny + nz * nz)
                if length > 0:
                    nx /= length
                    ny /= length
                    nz /= length
                else:
                    nx, ny, nz = 0, 0, 1

                # 光強度
                c = self.phong_intensity(nx, ny, nz)

                if self.dithering:
                    v = c * (self.shade_levels - 1)
                    s0 = int(v)
                    frac = v - s0

                    # frac の確率で 1 上の色を選ぶ
                    # if random.random() < frac:
                    if hash01(x, y) < frac:
                        shade = min(s0 + 1, self.shade_levels - 1)
                    else:
                        shade = s0

                else:
                    shade = int(c * (self.shade_levels - 1))
                pyxel.pset(x, y, shade)

    # -----------------------------
    # メッシュメイン描画
    # -----------------------------
    def draw_mesh(self, mesh):
        cam = self.camera

        # ローカル → ワールド → カメラ
        cam_pts = []
        for x, y, z in mesh.points:
            wx, wy, wz = mesh.local_to_world(x, y, z)
            cx, cy, cz = cam.world_to_camera(wx, wy, wz)
            cam_pts.append((cx, cy, cz))

        # 投影
        proj = [None] * len(cam_pts)
        for i, (x, y, z) in enumerate(cam_pts):
            if z <= 0:
                proj[i] = None
            else:
                sx, sy = cam.project(x, y, z)
                proj[i] = (float(sx), float(sy), float(z))

        # 頂点法線（カメラ座標系で）
        vnorm = [(0.0, 0.0, 0.0) for _ in mesh.points]

        for i0, i1, i2 in mesh.faces:
            v0 = cam_pts[i0]
            v1 = cam_pts[i1]
            v2 = cam_pts[i2]

            ux, uy, uz = (v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2])
            vx, vy, vz = (v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2])

            nx = uy * vz - uz * vy
            ny = uz * vx - ux * vz
            nz = ux * vy - uy * vx

            for idx in (i0, i1, i2):
                px, py, pz = vnorm[idx]
                vnorm[idx] = (px + nx, py + ny, pz + nz)

        # 正規化
        for i, (nx, ny, nz) in enumerate(vnorm):
            L = math.sqrt(nx * nx + ny * ny + nz * nz)
            if L > 0:
                vnorm[i] = (nx / L, ny / L, nz / L)
            else:
                vnorm[i] = (0, 0, 1)

        # Zバッファ使用なのでソート不要
        for i0, i1, i2 in mesh.faces:
            if proj[i0] is None or proj[i1] is None or proj[i2] is None:
                continue

            (x0, y0, z0) = proj[i0]
            (x1, y1, z1) = proj[i1]
            (x2, y2, z2) = proj[i2]

            n0 = vnorm[i0]
            n1 = vnorm[i1]
            n2 = vnorm[i2]

            self._draw_triangle(
                (x0, y0),
                z0,
                n0,
                (x1, y1),
                z1,
                n1,
                (x2, y2),
                z2,
                n2,
            )
