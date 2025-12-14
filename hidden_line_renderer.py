import math
import pyxel
from threed import Camera, Mesh, normalize


class HiddenLineRenderer:
    def __init__(
        self,
        camera: Camera,
        bg_color=0,
        light_dir=(0, 0, -1),
        shade_levels=5,
        base_color=7,
        shade=False,
        wired=False,
    ):
        self.camera = camera
        self.bg_color = bg_color
        self.light_dir = normalize(light_dir)
        self.shade_levels = shade_levels
        self.base_color = base_color
        self.shade = shade
        self.wired = wired

    def draw_mesh(self, mesh: Mesh):
        cam = self.camera

        # 1. Mesh のローカル点 → ワールド座標へ
        world_pts = mesh.transformed_points()

        # 2. ワールド → カメラ座標
        cam_pts = [cam.world_to_camera(*p) for p in world_pts]

        # 3. 画面座標に投影
        proj_pts = []
        for x, y, z in cam_pts:
            if z <= 0:
                proj_pts.append((-9999, -9999))
            else:
                proj_pts.append(cam.project(x, y, z))

        # 4. 面を深度順に並べる
        face_info = []
        for i0, i1, i2 in mesh.faces:
            v0 = cam_pts[i0]
            v1 = cam_pts[i1]
            v2 = cam_pts[i2]

            if v0[2] <= 0 and v1[2] <= 0 and v2[2] <= 0:
                continue

            depth = (v0[2] + v1[2] + v2[2]) / 3.0

            # 法線をカメラ空間で計算
            ux, uy, uz = (v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2])
            vx, vy, vz = (v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2])
            nx = uy * vz - uz * vy
            ny = uz * vx - ux * vz
            nz = ux * vy - uy * vx

            # カメラ空間の法線（向きだけ必要）
            n_len = math.sqrt(nx * nx + ny * ny + nz * nz)
            if n_len == 0:
                continue
            nx /= n_len
            ny /= n_len
            nz /= n_len

            # ライト計算（ライト方向はカメラ空間に固定）
            intensity = max(
                0,
                nx * self.light_dir[0]
                + ny * self.light_dir[1]
                + nz * self.light_dir[2],
            )

            intensity = math.sqrt(intensity)

            face_info.append((depth, nz, intensity, (i0, i1, i2)))

        # 奥 → 手前ソート
        face_info.sort(key=lambda x: x[0], reverse=True)

        # 5. 描画
        for depth, nz, intensity, (i0, i1, i2) in face_info:
            x0, y0 = proj_pts[i0]
            x1, y1 = proj_pts[i1]
            x2, y2 = proj_pts[i2]

            if self.wired:
                # 輪郭線: 表は白、陰線は暗い色
                if nz <= 0:
                    pyxel.line(x0, y0, x1, y1, 7)
                    pyxel.line(x1, y1, x2, y2, 7)
                    pyxel.line(x2, y2, x0, y0, 7)
                else:
                    pyxel.line(x0, y0, x1, y1, 1)
                    pyxel.line(x1, y1, x2, y2, 1)
                    pyxel.line(x2, y2, x0, y0, 1)
            else:
                # ------ フラットシェーディングによる塗り ------
                # 三角形
                if self.shade:
                    shade = self.base_color - int(intensity * self.shade_levels)
                    shade = max(0, min(15, shade))
                else:
                    shade = 7
                pyxel.tri(x0, y0, x1, y1, x2, y2, shade)

                # 輪郭線を描く（陰線は描かない）
                if nz <= 0:
                    pyxel.line(x0, y0, x1, y1, 0)
                    pyxel.line(x1, y1, x2, y2, 0)
                    pyxel.line(x2, y2, x0, y0, 0)
