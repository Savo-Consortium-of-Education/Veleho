class_name WorldGen
extends RefCounted
## Procedural level generator. Deterministic for a given seed (layout, items,
## enemies). Writes directly into PixelWorld.cells.

var world: PixelWorld
var dim: Dictionary
var rng := RandomNumberGenerator.new()
var W := 0
var H := 0
var c := PackedByteArray()
var level := 1
var base := Mat.ROCK
var spawn := Vector2i.ZERO
var portal := Vector2i.ZERO
var path_points: Array[Vector2] = []
var floor_spots: Array[Vector2i] = []
var altar_spots: Array[Vector2i] = []
var info := {}
var boss_level := false
var arena_rect := Rect2()


func generate(w: PixelWorld, seed_value: int, lvl: int, d: Dictionary, boss: bool = false) -> Dictionary:
	world = w
	dim = d
	level = lvl
	boss_level = boss
	arena_rect = Rect2()
	rng.seed = seed_value
	var size: Vector2i = d["size"]
	W = size.x
	H = size.y
	world.setup(W, H)
	c = world.cells
	base = d["base"]
	info = {"enemies": [], "items": [], "spawn": Vector2.ZERO, "portal": Vector2.ZERO}

	_base_terrain()
	_layers()
	_choose_endpoints()
	if dim["mode"] == "islands":
		_island_bridges()
	else:
		_carve_path()
		_rooms()
	_coatings()
	_structures()
	_pools()
	if boss_level:
		_boss_arena()
	_chamber(spawn, 15, 10)
	_chamber(portal, 20, 14)
	_border()
	_collect_floor_spots()
	_place_items()
	_place_enemies()
	info["spawn"] = Vector2(spawn.x, spawn.y + 3)
	info["portal"] = Vector2(portal.x, portal.y - 2)
	# Let loose material settle before the player arrives.
	world.wake_all()
	for i in 60:
		world.step()
	world.tex_dirty = true
	return info


# ---------------------------------------------------------------------------
func _hash(x: int, y: int) -> int:
	var h := (x * 374761393 + y * 668265263) & 0xffffffff
	h = ((h ^ (h >> 13)) * 1274126177) & 0xffffffff
	return (h ^ (h >> 16)) & 0x7fffffff


func _noise(freq: float, octaves: int, kind: int = FastNoiseLite.TYPE_SIMPLEX_SMOOTH) -> FastNoiseLite:
	var n := FastNoiseLite.new()
	n.seed = rng.randi()
	n.noise_type = kind
	n.frequency = freq
	n.fractal_type = FastNoiseLite.FRACTAL_FBM
	n.fractal_octaves = octaves
	return n


func _at(x: int, y: int) -> int:
	if x < 0 or y < 0 or x >= W or y >= H:
		return Mat.BEDROCK
	return c[(y * W + x) << 1]


func _put(x: int, y: int, m: int) -> void:
	if x < 0 or y < 0 or x >= W or y >= H:
		return
	var bi := (y * W + x) << 1
	c[bi] = m
	c[bi + 1] = (_hash(x, y) >> 5) & 127


func _put_if_empty(x: int, y: int, m: int) -> void:
	if _at(x, y) == Mat.EMPTY:
		_put(x, y, m)


func _carve(cx: int, cy: int, r: int) -> void:
	var r2 := r * r
	for y in range(maxi(1, cy - r), mini(H - 1, cy + r + 1)):
		var row := y * W
		var dy := y - cy
		for x in range(maxi(1, cx - r), mini(W - 1, cx + r + 1)):
			var dx := x - cx
			if dx * dx + dy * dy <= r2:
				c[(row + x) << 1] = 0


# ---------------------------------------------------------------------------
func _base_terrain() -> void:
	var n1 := _noise(dim["cave_freq"], 4)
	n1.domain_warp_enabled = true
	n1.domain_warp_amplitude = 45.0
	n1.domain_warp_frequency = 0.007
	var a := n1.get_image(W, H, false, false, true).get_data()
	var islands: bool = dim["mode"] == "islands"
	var b := PackedByteArray()
	if not islands:
		var n2 := _noise(0.0055, 3, FastNoiseLite.TYPE_SIMPLEX)
		n2.fractal_type = FastNoiseLite.FRACTAL_RIDGED
		b = n2.get_image(W, H, false, false, true).get_data()
	var thr_a := int(float(dim["cave_thr"]) * 255.0)
	var thr_b := int(float(dim["ridge_thr"]) * 255.0)
	var bm := base
	for y in H:
		var row := y * W
		# Islands get flatter tops: bias by vertical position inside a band.
		for x in W:
			var i := row + x
			var h := (x * 374761393 + y * 668265263) & 0xffffffff
			h = ((h ^ (h >> 13)) * 1274126177) & 0xffffffff
			var jit := int((h >> 7) & 7) - 3
			var av := int(a[i]) + jit
			var solid := false
			if islands:
				solid = av > thr_a
			else:
				solid = av >= thr_a and b[i] < thr_b
			if solid:
				var bi := i << 1
				c[bi] = bm
				c[bi + 1] = ((h >> 9) & 95) + ((((x >> 1) * 7 + (y >> 1) * 13) & 3) << 3)
	if islands:
		# A glowing aether sea at the bottom of the void.
		for y in range(H - 34, H):
			for x in W:
				if c[(y * W + x) << 1] == 0:
					_put(x, y, Mat.AETHER)


func _layers() -> void:
	var hw := (W + 1) >> 1
	var hh := (H + 1) >> 1
	for layer in dim["layers"]:
		var m: int = layer[0]
		var n := _noise(float(layer[1]) * 2.0, 3)
		var d := n.get_image(hw, hh, false, false, true).get_data()
		var thr := int(float(layer[2]) * 255.0)
		for y in H:
			var row := y * W
			var nrow := (y >> 1) * hw
			for x in W:
				var bi := (row + x) << 1
				if c[bi] != base:
					continue
				if d[nrow + (x >> 1)] > thr:
					c[bi] = m


func _choose_endpoints() -> void:
	var left := rng.randf() < 0.5
	if dim["mode"] == "islands":
		spawn = Vector2i(70 if left else W - 70, int(H * 0.35))
		portal = Vector2i(W - 80 if left else 80, int(H * 0.45))
	else:
		spawn = Vector2i(rng.randi_range(60, 140) if left else W - rng.randi_range(60, 140), rng.randi_range(48, 80))
		portal = Vector2i(W - rng.randi_range(70, 150) if left else rng.randi_range(70, 150), H - rng.randi_range(56, 90))


func _carve_path() -> void:
	var a := Vector2(spawn)
	var b := Vector2(portal)
	var pts: Array[Vector2] = [a]
	var n := rng.randi_range(4, 6)
	for k in range(1, n):
		var t := float(k) / float(n)
		var p := a.lerp(b, t)
		p.x += rng.randf_range(-0.25, 0.25) * W
		p.y += rng.randf_range(-0.06, 0.1) * H
		p.x = clampf(p.x, 50.0, W - 50.0)
		p.y = clampf(p.y, 50.0, H - 50.0)
		if p.y < pts[pts.size() - 1].y - 25.0:
			p.y = pts[pts.size() - 1].y - 25.0
		pts.append(p)
	pts.append(b)
	var wob := _noise(0.012, 2)
	var dist := 0.0
	path_points.clear()
	for k in range(pts.size() - 1):
		var p0 := pts[k]
		var p1 := pts[k + 1]
		var seg := p0.distance_to(p1)
		var steps := maxi(1, int(seg / 2.0))
		var perp := (p1 - p0).normalized().orthogonal()
		for s in steps:
			var t := float(s) / float(steps)
			var p := p0.lerp(p1, t)
			# fade wobble near the end points so chambers stay connected
			var fade := clampf(minf(t, 1.0 - t) * 6.0, 0.0, 1.0)
			p += perp * wob.get_noise_1d(dist) * 34.0 * fade
			var r := 7 + int((wob.get_noise_1d(dist * 0.6 + 500.0) + 1.0) * 3.5)
			_carve(int(p.x), int(p.y), r)
			if s % 12 == 0:
				path_points.append(p)
			dist += 2.0


func _rooms() -> void:
	if path_points.size() < 10:
		return
	var count := rng.randi_range(2, 4)
	for k in count:
		var p := path_points[rng.randi_range(4, path_points.size() - 5)]
		var rx := rng.randi_range(24, 44)
		var ry := rng.randi_range(15, 26)
		for y in range(maxi(2, int(p.y) - ry), mini(H - 2, int(p.y) + ry + 1)):
			for x in range(maxi(2, int(p.x) - rx), mini(W - 2, int(p.x) + rx + 1)):
				var dx := (x - p.x) / rx
				var dy := (y - p.y) / ry
				if dx * dx + dy * dy <= 1.0:
					c[(y * W + x) << 1] = 0
		# flat-ish floor for fights
		var fy := int(p.y) + ry - 2
		for x in range(int(p.x) - rx + 4, int(p.x) + rx - 4):
			for y in range(fy, fy + 3):
				_put_if_empty(x, y, base)


func _island_bridges() -> void:
	# Stepping-stone islands along a path so the void is always crossable.
	var a := Vector2(spawn)
	var b := Vector2(portal)
	var steps := int(a.distance_to(b) / 70.0)
	for k in range(steps + 1):
		var t := float(k) / float(maxi(1, steps))
		var p := a.lerp(b, t) + Vector2(rng.randf_range(-20, 20), rng.randf_range(-40, 40))
		var rw := rng.randi_range(12, 26)
		var rh := rng.randi_range(5, 9)
		for y in range(int(p.y), int(p.y) + rh * 2):
			var shrink := float(y - int(p.y)) / float(rh * 2)
			var half := int(rw * (1.0 - shrink * shrink))
			for x in range(int(p.x) - half, int(p.x) + half):
				if x > 3 and x < W - 3 and y > 3 and y < H - 3:
					_put(x, y, base)
		path_points.append(p)


# ---------------------------------------------------------------------------
func _coatings() -> void:
	var coat: int = dim["coating"]
	var depth: int = dim["coat_depth"]
	var chance: float = dim["coat_chance"]
	var ceil_m: int = dim["ceiling"]
	var ceil_chance: float = dim["ceil_chance"]
	var patch := _noise(0.04, 2)
	var kind := Mat.KIND
	for x in range(2, W - 2):
		var coat_here := (patch.get_noise_1d(x) + 1.0) * 0.5 < chance
		for y in range(2, H - 8):
			var bi := (y * W + x) << 1
			var m := c[bi]
			var above := c[bi - (W << 1)]
			if m != 0 and above == 0:
				if coat_here and kind[m] == Mat.K_STATIC and coat >= 0:
					for k in depth:
						var bk := ((y + k) * W + x) << 1
						if kind[c[bk]] == Mat.K_STATIC:
							c[bk] = coat
			elif m == 0 and above != 0 and ceil_m >= 0 and kind[above] == Mat.K_STATIC:
				if rng.randf() < ceil_chance:
					var length := rng.randi_range(1, 6)
					for k in length:
						var yy := y + k
						if _at(x, yy) != 0:
							break
						_put(x, yy, ceil_m)


func _structures() -> void:
	var st: Dictionary = dim["structures"]
	_platforms(int(st.get("platforms", 0)))
	_ruins(int(st.get("ruins", 0)))
	_kegs(int(st.get("kegs", 0)))
	if st.has("mushrooms"):
		_mushrooms(int(st["mushrooms"]))
	if st.has("crystals"):
		_crystals(int(st["crystals"]))


func _random_empty(margin: int = 20) -> Vector2i:
	for k in 60:
		var x := rng.randi_range(margin, W - margin)
		var y := rng.randi_range(margin, H - margin)
		if _at(x, y) == 0:
			return Vector2i(x, y)
	return Vector2i(-1, -1)


func _drop_to_floor(p: Vector2i) -> Vector2i:
	var x := p.x
	var y := p.y
	while y < H - 4 and _at(x, y + 1) == 0:
		y += 1
	return Vector2i(x, y)


func _platforms(n: int) -> void:
	var mat: int = dim["platform_mat"]
	var placed := 0
	var attempts := 0
	while placed < n and attempts < n * 30:
		attempts += 1
		var p := _random_empty(30)
		if p.x < 0:
			continue
		var xl := p.x
		while xl > 4 and _at(xl - 1, p.y) == 0 and p.x - xl < 70:
			xl -= 1
		var xr := p.x
		while xr < W - 5 and _at(xr + 1, p.y) == 0 and xr - p.x < 70:
			xr += 1
		if p.x - xl >= 70 or xr - p.x >= 70:
			continue
		var span := xr - xl
		if span < 16:
			continue
		# need open space above and below
		if _at(p.x, p.y - 8) != 0 or _at(p.x, p.y + 10) != 0:
			continue
		for x in range(xl - 1, xr + 2):
			_put_if_empty(x, p.y, mat)
			_put_if_empty(x, p.y + 1, mat)
		# posts down to the floor
		var post := xl + rng.randi_range(4, 10)
		while post < xr - 3:
			var y := p.y + 2
			var len := 0
			while _at(post, y) == 0 and len < 50:
				y += 1
				len += 1
			if len < 50:
				for yy in range(p.y + 2, y):
					_put(post, yy, mat)
			post += rng.randi_range(18, 34)
		placed += 1


func _ruins(n: int) -> void:
	var placed := 0
	var attempts := 0
	while placed < n and attempts < n * 40:
		attempts += 1
		var rw := rng.randi_range(30, 46)
		var rh := rng.randi_range(18, 24)
		var x0 := rng.randi_range(20, W - rw - 20)
		var y0 := rng.randi_range(40, H - rh - 30)
		if Rect2i(x0 - 20, y0 - 20, rw + 40, rh + 40).has_point(spawn):
			continue
		if Rect2i(x0 - 24, y0 - 24, rw + 48, rh + 48).has_point(portal):
			continue
		var solid := 0
		for k in 40:
			if _at(x0 + rng.randi_range(0, rw), y0 + rng.randi_range(0, rh)) != 0:
				solid += 1
		if solid > 22:
			continue
		var brick := Mat.BRICK
		for y in range(y0, y0 + rh):
			for x in range(x0, x0 + rw):
				var wall := x < x0 + 2 or x >= x0 + rw - 2 or y < y0 + 2 or y >= y0 + rh - 3
				var door := (x < x0 + 2 or x >= x0 + rw - 2) and y >= y0 + rh - 13 and y < y0 + rh - 3
				if wall and not door:
					_put(x, y, brick)
				else:
					c[(y * W + x) << 1] = 0
		# crumbled roof holes
		for k in rng.randi_range(1, 3):
			var hx := rng.randi_range(x0 + 4, x0 + rw - 8)
			for x in range(hx, hx + rng.randi_range(3, 7)):
				for y in range(y0, y0 + 2):
					c[(y * W + x) << 1] = 0
		# support pillars
		for px in [x0 + 3, x0 + rw - 5]:
			var y := y0 + rh
			var len := 0
			while _at(px, y) == 0 and len < 60:
				y += 1
				len += 1
			if len < 60:
				for yy in range(y0 + rh, y):
					_put(px, yy, brick)
					_put(px + 1, yy, brick)
		altar_spots.append(Vector2i(x0 + rw / 2, y0 + rh - 4))
		placed += 1


func _kegs(n: int) -> void:
	for k in n:
		var p := _random_empty(30)
		if p.x < 0:
			continue
		var f := _drop_to_floor(p)
		if f.distance_to(spawn) < 120:
			continue
		var w := rng.randi_range(6, 9)
		var h := rng.randi_range(6, 8)
		for y in range(f.y - h + 1, f.y + 1):
			for x in range(f.x - w / 2, f.x - w / 2 + w):
				var edge := y == f.y - h + 1 or y == f.y or x == f.x - w / 2 or x == f.x - w / 2 + w - 1
				if _at(x, y) == 0:
					_put(x, y, Mat.WOOD if edge else Mat.GUNPOWDER)


func _mushrooms(n: int) -> void:
	for k in n:
		var p := _random_empty(30)
		if p.x < 0:
			continue
		var f := _drop_to_floor(p)
		var stem_h := rng.randi_range(8, 22)
		var cap_r := rng.randi_range(5, 11)
		if _at(f.x, f.y - stem_h - cap_r) != 0:
			continue
		for y in range(f.y - stem_h, f.y + 1):
			_put_if_empty(f.x, y, Mat.WOOD)
			_put_if_empty(f.x + 1, y, Mat.WOOD)
		var cy := f.y - stem_h
		for y in range(cy - cap_r, cy + 1):
			for x in range(f.x - cap_r * 2, f.x + cap_r * 2 + 1):
				var dx := float(x - f.x) / (cap_r * 2.0)
				var dy := float(y - cy) / float(cap_r)
				if dx * dx + dy * dy <= 1.0:
					_put_if_empty(x, y, Mat.FUNGUS)


func _crystals(n: int) -> void:
	for k in n:
		var p := _random_empty(30)
		if p.x < 0:
			continue
		var f := _drop_to_floor(p)
		var h := rng.randi_range(6, 18)
		var w := rng.randi_range(2, 4)
		var lean := rng.randf_range(-0.4, 0.4)
		for i in h:
			var half := int(w * (1.0 - float(i) / h))
			var cx := f.x + int(lean * i)
			for x in range(cx - half, cx + half + 1):
				_put_if_empty(x, f.y - i, Mat.CRYSTAL)


func _pools() -> void:
	var liquids: Dictionary = dim["liquids"]
	var keys := liquids.keys()
	var weights := PackedFloat32Array()
	for k in keys:
		weights.append(float(liquids[k]))
	var count: int = dim["pools"]
	var placed := 0
	var attempts := 0
	while placed < count and attempts < count * 30:
		attempts += 1
		var p := _random_empty(24)
		if p.x < 0 or p.y < int(H * 0.12):
			continue
		var f := _drop_to_floor(p)
		var x := f.x
		var y := f.y
		for k in 60:
			if _at(x - 1, y + 1) == 0 and _at(x - 1, y) == 0:
				x -= 1
				y += 1
			elif _at(x + 1, y + 1) == 0 and _at(x + 1, y) == 0:
				x += 1
				y += 1
			else:
				break
			while y < H - 4 and _at(x, y + 1) == 0:
				y += 1
		if Mat.KIND[_at(x, y + 1)] == Mat.K_LIQUID:
			continue
		if Vector2i(x, y).distance_to(spawn) < 40:
			continue
		var m: int = keys[rng.rand_weighted(weights)]
		if _fill_basin(x, y, rng.randi_range(4, 13), m, 90) > 25:
			placed += 1


func _fill_basin(x: int, y: int, depth: int, m: int, maxw: int) -> int:
	var filled := 0
	for row in range(y, y - depth, -1):
		if row < 6:
			break
		if _at(x, row) != 0:
			break
		var xl := x
		while xl > 3 and _at(xl - 1, row) == 0 and x - xl < maxw:
			xl -= 1
		var xr := x
		while xr < W - 4 and _at(xr + 1, row) == 0 and xr - x < maxw:
			xr += 1
		if x - xl >= maxw or xr - x >= maxw:
			break
		var ok := true
		for xx in range(xl, xr + 1):
			if _at(xx, row + 1) == 0:
				ok = false
				break
		if not ok:
			break
		for xx in range(xl, xr + 1):
			_put(xx, row, m)
		filled += xr - xl + 1
	return filled


## Large arena in front of the portal for the gate guardian.
func _boss_arena() -> void:
	var side := 1 if portal.x > W / 2 else -1
	var rx := 118
	var ry := 62
	var floor_y := portal.y + 14
	var cx := clampi(portal.x - side * 105, rx + 6, W - rx - 6)
	var cy := clampi(floor_y - 50, ry + 6, H - ry - 12)
	floor_y = cy + 50
	for y in range(cy - ry, cy + ry + 1):
		for x in range(cx - rx, cx + rx + 1):
			var dx := float(x - cx) / rx
			var dy := float(y - cy) / ry
			if dx * dx + dy * dy <= 1.0:
				c[(y * W + x) << 1] = 0
	var fm := base if Mat.HARD[base] >= 40 else Mat.ROCK
	for y in range(floor_y, floor_y + 8):
		for x in range(cx - rx + 6, cx + rx - 5):
			_put(x, y, fm)
	# two floating ledges for vertical play
	for sx in [cx - 55, cx + 55]:
		for y in range(cy + 4, cy + 7):
			for x in range(sx - 16, sx + 17):
				_put(x, y, fm)
	arena_rect = Rect2(cx - rx + 10, cy - ry + 8, rx * 2 - 20, floor_y - (cy - ry + 8) - 2)
	info["boss"] = {"pos": Vector2(cx, cy - 12), "arena": arena_rect}


func _chamber(p: Vector2i, r: int, floor_off: int) -> void:
	_carve(p.x, p.y, r)
	var fm := base
	if Mat.HARD[fm] < 40:
		fm = Mat.ROCK
	for y in range(p.y + floor_off, p.y + floor_off + 4):
		for x in range(p.x - r + 2, p.x + r - 1):
			_put(x, y, fm)
	# keep liquids from pouring in: walls of the chamber are the cave itself


func _border() -> void:
	for y in H:
		for x in [0, 1, 2, W - 3, W - 2, W - 1]:
			_put(x, y, Mat.BEDROCK)
	for x in W:
		for y in [0, 1, 2, H - 3, H - 2, H - 1]:
			_put(x, y, Mat.BEDROCK)


func _collect_floor_spots() -> void:
	floor_spots.clear()
	for k in 900:
		var p := _random_empty(16)
		if p.x < 0:
			continue
		var f := _drop_to_floor(p)
		if f.y >= H - 6:
			continue
		var below := _at(f.x, f.y + 1)
		if Mat.KIND[below] != Mat.K_STATIC and Mat.KIND[below] != Mat.K_POWDER:
			continue
		if not world.rect_free(f.x - 4, f.y - 15, 9, 15):
			continue
		floor_spots.append(f)


func _far_spot(min_dist: float) -> Vector2i:
	for k in 40:
		if floor_spots.is_empty():
			break
		var f := floor_spots[rng.randi_range(0, floor_spots.size() - 1)]
		if f.distance_to(spawn) >= min_dist and f.distance_to(portal) > 40:
			return f
	return Vector2i(-1, -1)


func _place_items() -> void:
	# Weapon altars: prefer ruins, then random floor spots.
	var weapons := 2 + (1 if rng.randf() < 0.5 else 0)
	var spots: Array[Vector2i] = altar_spots.duplicate()
	for k in weapons:
		var s := Vector2i(-1, -1)
		if not spots.is_empty():
			s = spots.pop_back()
		else:
			s = _far_spot(120)
		if s.x < 0:
			continue
		var am := Mat.METAL if rng.randf() < 0.5 else Mat.BRICK
		for y in range(s.y - 1, s.y + 1):
			for x in range(s.x - 4, s.x + 5):
				_put(x, y, am)
		for x in range(s.x - 2, s.x + 3):
			_put(x, s.y - 2, am)
		info["items"].append(["weapon", Vector2(s.x, s.y - 10), rng.randi()])
	var hearts := 1 + (1 if rng.randf() < 0.35 else 0)
	for k in hearts:
		var s := _far_spot(200)
		if s.x >= 0:
			info["items"].append(["heart", Vector2(s.x, s.y - 5), 0])
	var golds := rng.randi_range(14, 26)
	for k in golds:
		var s := _far_spot(60)
		if s.x >= 0:
			info["items"].append(["gold", Vector2(s.x, s.y - 2), rng.randi_range(5, 15) + level * 3])
	if rng.randf() < 0.6:
		var s := _far_spot(150)
		if s.x >= 0:
			info["items"].append(["mana", Vector2(s.x, s.y - 5), 0])
	for k in rng.randi_range(2, 4):
		var s := _far_spot(90)
		if s.x >= 0:
			info["items"].append(["spell", Vector2(s.x, s.y - 6), rng.randi()])
	for k in rng.randi_range(0, 2):
		var s := _far_spot(120)
		if s.x >= 0:
			info["items"].append(["flask", Vector2(s.x, s.y - 6), rng.randi()])


func _place_enemies() -> void:
	var table: Dictionary = dim["enemies"].duplicate()
	if level <= 1:
		table.erase("caster")
		table.erase("golem")
	var keys := table.keys()
	var weights := PackedFloat32Array()
	for k in keys:
		weights.append(float(table[k]))
	var count := mini(36, int(dim["enemy_base"]) + (level - 1) * 3)
	if boss_level:
		count = int(count * 0.7)
	for i in count:
		var t: String = keys[rng.rand_weighted(weights)]
		if t == "bat" or t == "wisp":
			for k in 30:
				var p := _random_empty(30)
				if p.x < 0:
					continue
				if p.distance_to(spawn) < 170:
					continue
				if arena_rect.has_point(Vector2(p)):
					continue
				if not world.rect_free(p.x - 6, p.y - 6, 12, 12):
					continue
				info["enemies"].append([t, Vector2(p.x, p.y)])
				break
		else:
			for k in 30:
				var s := _far_spot(170)
				if s.x < 0:
					break
				if arena_rect.grow(10).has_point(Vector2(s)):
					continue
				var hh := 12 if t == "golem" else 6
				if t == "golem" and not world.rect_free(s.x - 8, s.y - 22, 17, 22):
					continue
				info["enemies"].append([t, Vector2(s.x, s.y - hh)])
				break
