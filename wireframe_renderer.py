import math
import pyxel
from threed import Camera, Mesh, clip_segment_fast


class WireframeRenderer:
    def __init__(self, camera: Camera, color: int = 7):
        self.camera = camera
        self.color = color

    def draw_mesh(self, mesh: Mesh, color: int | None = None):
        if color is None:
            color = self.color

        cam = self.camera

        # ---------------------------------------
        # 1. 頂点: local → world → camera
        # ---------------------------------------
        cam_pts: list[tuple[float, float, float]] = []
        for lx, ly, lz in mesh.points:
            wx, wy, wz = mesh.local_to_world(lx, ly, lz)
            cx, cy, cz = cam.world_to_camera(wx, wy, wz)
            cam_pts.append((cx, cy, cz))

        # ---------------------------------------
        # 2. セグメントが空なら、faces から生成（お好みで）
        # ---------------------------------------
        segments = mesh.segments
        if not segments and mesh.faces:
            edges = set()
            for i0, i1, i2 in mesh.faces:
                e01 = tuple(sorted((i0, i1)))
                e12 = tuple(sorted((i1, i2)))
                e20 = tuple(sorted((i2, i0)))
                edges.add(e01)
                edges.add(e12)
                edges.add(e20)
            segments = list(edges)

        # ---------------------------------------
        # 3. 各セグメントをクリッピング＆描画
        # ---------------------------------------
        for i, j in segments:
            x0, y0, z0 = cam_pts[i]
            x1, y1, z1 = cam_pts[j]

            # 両端ともカメラ後方なら捨てる
            if z0 <= 0 and z1 <= 0:
                continue

            # 視錐台クリッピング
            F, X0c, Y0c, Z0c, X1c, Y1c, Z1c = clip_segment_fast(
                x0,
                y0,
                z0,
                x1,
                y1,
                z1,
                cam.AX,
                cam.AY,
            )

            # F=0 → 描画すべき / F=1 → 描画不要
            if F != 0:
                continue

            # 投影
            sx0, sy0 = cam.project(X0c, Y0c, Z0c)
            sx1, sy1 = cam.project(X1c, Y1c, Z1c)

            pyxel.line(sx0, sy0, sx1, sy1, color)
