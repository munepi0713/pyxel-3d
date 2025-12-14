import math
import pyxel
from threed import Camera, Mesh


class GouraudRenderer:
    """
    Gouraud シェーディング専用レンダラー
    --------------------------------------
    - Mesh の faces（三角形）を塗りつぶす
    - 頂点ごとの diffuse intensity を補間
    """

    def __init__(self, camera: Camera, light_dir=(1, -1, -1), *, ambient: float = 0.2):
        self.camera = camera
        self.ambient = ambient

        # ライト方向は正規化しておく
        lx, ly, lz = light_dir
        L = math.sqrt(lx * lx + ly * ly + lz * lz)
        self.light_dir = (lx / L, ly / L, lz / L)

    # ---------------------------------------------------
    # 頂点法線 → 光強度（0〜1）
    # ---------------------------------------------------
    def compute_intensity(self, nx, ny, nz):
        lx, ly, lz = self.light_dir
        dot = nx * lx + ny * ly + nz * lz
        if dot < 0:
            dot = 0
        return min(1.0, self.ambient + dot * 0.8)

    # ---------------------------------------------------
    # スキャンラインによる Gouraud 三角形描画
    # ---------------------------------------------------
    def draw_gouraud_tri(self, p0, c0, p1, c1, p2, c2):
        # 位置と色を y 昇順に並べる
        pts = sorted([(p0, c0), (p1, c1), (p2, c2)], key=lambda x: x[0][1])
        (x0, y0), c0 = pts[0]
        (x1, y1), c1 = pts[1]
        (x2, y2), c2 = pts[2]

        # 端点が重なる場合の対策
        if y1 == y2:
            part2 = True
        else:
            part2 = False

        def interp(a, b, t):
            return a + (b - a) * t

        # 主ループ（y0→y2を1パスで走査）
        y_start = int(math.ceil(y0))
        y_end = int(math.floor(y2))

        for y in range(y_start, y_end + 1):
            # yに対する t0, t2（長辺）
            t_long = (y - y0) / (y2 - y0) if y2 != y0 else 0
            xl = interp(x0, x2, t_long)
            cl = interp(c0, c2, t_long)

            # yに対する短辺の補間対象は y1 で切り替える
            if y < y1 or part2:
                t_short = (y - y0) / (y1 - y0) if y1 != y0 else 0
                xr = interp(x0, x1, t_short)
                cr = interp(c0, c1, t_short)
            else:
                t_short = (y - y1) / (y2 - y1) if y2 != y1 else 0
                xr = interp(x1, x2, t_short)
                cr = interp(c1, c2, t_short)

            # 左右交換
            if xl > xr:
                xl, xr = xr, xl
                cl, cr = cr, cl

            # 水平線描画
            x_start = int(math.ceil(xl))
            x_end = int(math.floor(xr))

            for x in range(x_start, x_end + 1):
                t = (x - xl) / (xr - xl) if xr != xl else 0
                c = interp(cl, cr, t)
                shade = int(c * 7)
                pyxel.pset(x, y, shade)

    # ---------------------------------------------------
    # メッシュ描画（メイン）
    # ---------------------------------------------------
    def draw_mesh(self, mesh: Mesh):
        cam = self.camera

        # 頂点を world → camera → project
        cam_pts = [cam.world_to_camera(*mesh.local_to_world(*p)) for p in mesh.points]
        proj_pts = [None] * len(cam_pts)

        for i, (x, y, z) in enumerate(cam_pts):
            if z <= 0:
                proj_pts[i] = None
            else:
                proj_pts[i] = cam.project(x, y, z)

        # 頂点光強度
        intens = []
        for nx, ny, nz in mesh.vertex_normals:
            intens.append(self.compute_intensity(nx, ny, nz))

        # face depth ソート（手前を後に描く）
        face_list = []
        for idx, (i0, i1, i2) in enumerate(mesh.faces):
            z0 = cam_pts[i0][2]
            z1 = cam_pts[i1][2]
            z2 = cam_pts[i2][2]
            avgz = (z0 + z1 + z2) / 3
            face_list.append((avgz, i0, i1, i2))

        face_list.sort(reverse=True)  # 奥から描く
        # face_list.sort()

        # 描画
        for avgz, i0, i1, i2 in face_list:
            if proj_pts[i0] is None or proj_pts[i1] is None or proj_pts[i2] is None:
                continue

            # backface culling（カメラ座標系）
            v0 = cam_pts[i0]
            v1 = cam_pts[i1]
            v2 = cam_pts[i2]
            ux, uy, uz = (v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2])
            vx, vy, vz = (v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2])
            nx = uy * vz - uz * vy
            # ny = uz*vx - ux*vz
            nz = ux * vy - uy * vx
            if nz <= 0:
                continue

            p0 = proj_pts[i0]
            p1 = proj_pts[i1]
            p2 = proj_pts[i2]

            c0 = intens[i0]
            c1 = intens[i1]
            c2 = intens[i2]

            self.draw_gouraud_tri(p0, c0, p1, c1, p2, c2)
