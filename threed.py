import math


class Camera:
    def __init__(
        self,
        rx=0,
        ry=0,
        rz=0,
        tx=0,
        ty=0,
        tz=0,
        fov_y_deg=60,
        aspect_ratio=160 / 120,
        screen_w=160,
        screen_h=120,
        scale=50,
    ):
        # カメラ位置
        self.tx = tx
        self.ty = ty
        self.tz = tz

        # 回転（度）
        self.rx = rx
        self.ry = ry
        self.rz = rz  # 通常は0で使うことが多い

        # FOV設定（縦方向）
        self.fov_y = math.radians(fov_y_deg)
        self.aspect = aspect_ratio

        # FOVから AX/AY を自動生成
        self.AY = math.tan(self.fov_y / 2)
        self.AX = self.AY * self.aspect

        # 描画座標変換
        self.cx = screen_w // 2
        self.cy = screen_h // 2
        self.scale = scale

    # ---------------------------------------
    # look_at: カメラを指定ターゲットに向ける
    # ---------------------------------------
    def look_at(self, tx, ty, tz):
        dx = tx - self.tx
        dy = ty - self.ty
        dz = tz - self.tz

        # yaw（y軸回転） 左右方向
        self.ry = math.degrees(math.atan2(dx, dz))

        # pitch（x軸回転） 上下方向
        dist = math.sqrt(dx * dx + dz * dz)
        self.rx = -math.degrees(math.atan2(dy, dist))

        # roll は通常使わない
        # self.rz = 0

    # ---------------------------------------
    # 世界座標 → カメラ座標
    # ---------------------------------------
    def world_to_camera(self, x, y, z):
        # カメラ位置で平行移動
        x -= self.tx
        y -= self.ty
        z -= self.tz

        # カメラ回転を適用
        return rotate_xyz_fast(x, y, z, self.rx, self.ry, self.rz)

    # ---------------------------------------
    # カメラ座標 → 投影座標（画面座標）
    # ---------------------------------------
    def project(self, x, y, z):
        sx = x / z
        sy = y / z
        return (int(self.cx + sx * self.scale), int(self.cy - sy * self.scale))


class Mesh:
    def __init__(
        self,
        points=None,
        segments=None,
        faces=None,
        tx=0,
        ty=0,
        tz=0,
        rx=0,
        ry=0,
        rz=0,
        scale=1.0,
    ):
        self.points = points or []
        self.segments = segments or []
        self.faces = faces or []
        self.vertex_normals = compute_vertex_normals(points)

        # ローカル変換
        self.tx = tx
        self.ty = ty
        self.tz = tz

        self.rx = rx
        self.ry = ry
        self.rz = rz

        self.scale = scale

    # ------------------------------------------------
    # ローカル座標 → ワールド座標
    # ------------------------------------------------
    def local_to_world(self, x, y, z):
        # スケール
        x *= self.scale
        y *= self.scale
        z *= self.scale

        # ローカル回転
        x, y, z = rotate_xyz_fast(x, y, z, self.rx, self.ry, self.rz)

        # ワールドへ平行移動
        return (x + self.tx, y + self.ty, z + self.tz)

    # ------------------------------------------------
    # メッシュ全体をワールド座標へ変換
    # ------------------------------------------------
    def transformed_points(self):
        out = []
        for x, y, z in self.points:
            out.append(self.local_to_world(x, y, z))
        return out


def rotate_xyz(X: int, Y: int, Z: int, RX: int, RY: int, RZ: int):
    """
    BASICコードと同じ回転行列処理を行い、
    (X, Y, Z) を RX, RY, RZ（度数法）の回転で変換する。
    """

    # --- matrix generation (degree → radian)
    CRX = math.cos(RX * math.pi / 180)
    SRX = math.sin(RX * math.pi / 180)

    CRY = math.cos(RY * math.pi / 180)
    SRY = math.sin(RY * math.pi / 180)

    CRZ = math.cos(RZ * math.pi / 180)
    SRZ = math.sin(RZ * math.pi / 180)

    # --- rotation matrix (BASIC と完全対応)
    R00 = CRY * CRZ
    R01 = SRX * SRY * CRZ - CRX * SRZ
    R02 = CRX * SRY * CRZ + SRX * SRZ

    R10 = CRY * SRZ
    R11 = SRX * SRY * SRZ + CRX * CRZ
    R12 = CRX * SRY * SRZ - SRX * CRZ

    R20 = -SRY
    R21 = SRX * CRY
    R22 = CRX * CRY

    # --- matrix multiply
    X1 = X * R00 + Y * R01 + Z * R02
    Y1 = X * R10 + Y * R11 + Z * R12
    Z1 = X * R20 + Y * R21 + Z * R22

    return X1, Y1, Z1


rotate_xyz_fast = rotate_xyz


def clip_segment(
    X0: int, Y0: int, Z0: int, X1: int, Y1: int, Z1: int, AX: int, AY: int
):
    """
    Python版クリッピングルーチン（BASIC のリスト1-2を忠実に移植）

    入力:
        (X0,Y0,Z0)-(X1,Y1,Z1): 線分
        AX, AY: 視野パラメータ
    出力:
        F, X0, Y0, Z0, X1, Y1, Z1
            F=0 → 描画すべき（線分が残った）
            F=1 → 描画不要（完全に視野外）
    """

    for _ in range(1, 100):
        # --- 4bit region code for point 1
        C1 = 0
        if X1 < -AX * Z1:
            C1 |= 1
        if X1 > AX * Z1:
            C1 |= 2
        if Y1 < -AY * Z1:
            C1 |= 4
        if Y1 > AY * Z1:
            C1 |= 8

        # --- 4bit region code for point 0
        C0 = 0
        if X0 < -AX * Z0:
            C0 |= 1
        if X0 > AX * Z0:
            C0 |= 2
        if Y0 < -AY * Z0:
            C0 |= 4
        if Y0 > AY * Z0:
            C0 |= 8  # BASIC の 1150行のバグを修正

        # どちらも領域コード 0 → 完全に視野内（クリップ不要）
        if (C0 | C1) == 0:
            return 0, X0, Y0, Z0, X1, Y1, Z1

        # 論理積が非0 → 完全に視野外（交わらない）
        if (C0 & C1) != 0:
            return 1, X0, Y0, Z0, X1, Y1, Z1

        # C0 を clipping する点にする
        if C0 == 0:
            # SWAP (X0,Y0,Z0) ⇔ (X1,Y1,Z1)
            X0, X1 = X1, X0
            Y0, Y1 = Y1, Y0
            Z0, Z1 = Z1, Z0
            C0, C1 = C1, C0

        # --- クリップ面との交点割合 T を計算（BASIC そのまま）
        if (C0 & 1) != 0:  # X < -AX*Z
            T = (-X0 - AX * Z0) / ((X1 - X0) + AX * (Z1 - Z0))

        elif (C0 & 2) != 0:  # X > AX*Z
            T = (AX * Z0 - X0) / ((X1 - X0) - AX * (Z1 - Z0))

        elif (C0 & 4) != 0:  # Y < -AY*Z
            T = (-Y0 - AY * Z0) / ((Y1 - Y0) + AY * (Z1 - Z0))

        else:  # (C0 & 8) != 0: Y > AY*Z
            T = (AY * Z0 - Y0) / ((Y1 - Y0) - AY * (Z1 - Z0))

        # --- 線分をクリップされた交点に更新
        X0 = X0 + (X1 - X0) * T
        Y0 = Y0 + (Y1 - Y0) * T
        Z0 = Z0 + (Z1 - Z0) * T

        # 再判定へ（BASIC の GOTO 1110）
    else:
        return 1, X0, Y0, Z0, X1, Y1, Z1


clip_segment_fast = clip_segment


def normalize(v):
    x, y, z = v
    d = math.sqrt(x * x + y * y + z * z)
    if d == 0:
        return (0, 0, 1)
    return (x / d, y / d, z / d)


# def compute_vertex_normals(points, faces):
#     normals = [(0.0, 0.0, 0.0) for _ in points]

#     for i0, i1, i2 in faces:
#         p0 = points[i0]
#         p1 = points[i1]
#         p2 = points[i2]

#         # face normal
#         ux, uy, uz = (p1[0]-p0[0], p1[1]-p0[1], p1[2]-p0[2])
#         vx, vy, vz = (p2[0]-p0[0], p2[1]-p0[1], p2[2]-p0[2])
#         nx = uy*vz - uz*vy
#         ny = uz*vx - ux*vz
#         nz = ux*vy - uy*vx

#         # accumulate
#         for idx in (i0, i1, i2):
#             nx0, ny0, nz0 = normals[idx]
#             normals[idx] = (nx0+nx, ny0+ny, nz0+nz)

#     # normalize
#     out = []
#     for nx, ny, nz in normals:
#         l = math.sqrt(nx*nx + ny*ny + nz*nz)
#         if l == 0:
#             out.append((0,1,0))
#         else:
#             out.append((nx/l, ny/l, nz/l))
#     return out


def compute_vertex_normals(points):
    normals = []
    for x, y, z in points:
        # 頂点そのものが球面上にあるので、その方向が法線
        length = math.sqrt(x * x + y * y + z * z)
        if length == 0:
            normals.append((0, 0, 1))
        else:
            normals.append((x / length, y / length, z / length))
    return normals
