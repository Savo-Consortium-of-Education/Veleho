class_name PixelWorld
extends Node2D
## Falling-sand style cellular simulation.
## cells: 2 bytes per cell -> [material, data]. data bits 0-6 = shade for
## solids/powders, idle counter for liquids, remaining life for gas/fire/burning.
## Every 32x32 chunk keeps a dirty rectangle; only those regions are simulated.
## stamp[i] = last frame a cell was processed/moved (prevents double updates).

const CH := 32
const CS := 5  # log2(CH)
const EMPTY_RECT := 1 << 30
const LIQUID_SLEEP := 48
const MAX_PARTICLE_SPAWN := 400
const N8X: Array[int] = [-1, 0, 1, -1, 1, -1, 0, 1]
const N8Y: Array[int] = [-1, -1, -1, 0, 0, 1, 1, 1]

var W := 0
var H := 0
var cells := PackedByteArray()
var stamp := PackedInt32Array()
var cw := 0
var chh := 0
# current-frame dirty rects (world coords, inclusive). Empty: x0 > x1.
var rx0 := PackedInt32Array()
var ry0 := PackedInt32Array()
var rx1 := PackedInt32Array()
var ry1 := PackedInt32Array()
# next-frame dirty rects
var nx0 := PackedInt32Array()
var ny0 := PackedInt32Array()
var nx1 := PackedInt32Array()
var ny1 := PackedInt32Array()
var frame := 1
var tex_dirty := true
var pending_explosions: Array[Vector3i] = []
var particles: Node = null  # Particles node (optional)
var render: Sprite2D
var tex: ImageTexture
var shader_mat: ShaderMaterial
var active_count := 0

var _kind := Mat.KIND
var _solid := Mat.SOLID
var _dens := Mat.DENSITY
var _flam := Mat.FLAM
var _disp := Mat.DISPERSION
var _visc := Mat.VISCOUS
var _diss := Mat.DISSOLVE
var _hard := Mat.HARD
var _debris := Mat.DEBRIS


func setup(w: int, h: int) -> void:
	W = w
	H = h
	cells = PackedByteArray()
	cells.resize(W * H * 2)
	stamp = PackedInt32Array()
	stamp.resize(W * H)
	cw = (W + CH - 1) >> CS
	chh = (H + CH - 1) >> CS
	var n := cw * chh
	rx0.resize(n)
	ry0.resize(n)
	rx1.resize(n)
	ry1.resize(n)
	nx0.resize(n)
	ny0.resize(n)
	nx1.resize(n)
	ny1.resize(n)
	_clear_rects(rx0, ry0, rx1, ry1)
	_clear_rects(nx0, ny0, nx1, ny1)
	frame = 1
	pending_explosions.clear()
	if render == null:
		render = Sprite2D.new()
		render.centered = false
		render.name = "Render"
		shader_mat = ShaderMaterial.new()
		shader_mat.shader = load("res://shaders/world.gdshader")
		shader_mat.set_shader_parameter("palette", Mat.palette())
		render.material = shader_mat
		add_child(render)
	var img := Image.create_from_data(W, H, false, Image.FORMAT_RG8, cells)
	tex = ImageTexture.create_from_image(img)
	render.texture = tex
	shader_mat.set_shader_parameter("cells", tex)
	tex_dirty = true


func _clear_rects(a0: PackedInt32Array, b0: PackedInt32Array, a1: PackedInt32Array, b1: PackedInt32Array) -> void:
	a0.fill(EMPTY_RECT)
	b0.fill(EMPTY_RECT)
	a1.fill(-1)
	b1.fill(-1)


func set_background(dark: Color, light: Color, stars: bool) -> void:
	shader_mat.set_shader_parameter("bg_dark", dark)
	shader_mat.set_shader_parameter("bg_light", light)
	shader_mat.set_shader_parameter("bg_stars", 1.0 if stars else 0.0)


func upload() -> void:
	if not tex_dirty:
		return
	tex_dirty = false
	tex.update(Image.create_from_data(W, H, false, Image.FORMAT_RG8, cells))


# ---------------------------------------------------------------------------
# Cell access
# ---------------------------------------------------------------------------
func in_bounds(x: int, y: int) -> bool:
	return x >= 0 and y >= 0 and x < W and y < H


func get_mat(x: int, y: int) -> int:
	if x < 0 or y < 0 or x >= W or y >= H:
		return Mat.BEDROCK
	return cells[(y * W + x) << 1]


func is_solid_at(x: int, y: int) -> bool:
	if x < 0 or y < 0 or x >= W or y >= H:
		return true
	return _solid[cells[(y * W + x) << 1]] != 0


func set_cell(x: int, y: int, m: int, data: int = -1) -> void:
	if x < 0 or y < 0 or x >= W or y >= H:
		return
	var i := y * W + x
	cells[i << 1] = m
	if data < 0:
		data = 0 if _kind[m] == Mat.K_LIQUID else (randi() & 127)
	cells[(i << 1) + 1] = data & 127
	stamp[i] = frame
	_wake(x, y)


func _wake(x: int, y: int) -> void:
	var lx := x & (CH - 1)
	var ly := y & (CH - 1)
	if lx > 0 and lx < CH - 1 and ly > 0 and ly < CH - 1:
		var c := (y >> CS) * cw + (x >> CS)
		if x - 1 < nx0[c]:
			nx0[c] = x - 1
		if x + 1 > nx1[c]:
			nx1[c] = x + 1
		if y - 1 < ny0[c]:
			ny0[c] = y - 1
		if y + 1 > ny1[c]:
			ny1[c] = y + 1
	else:
		wake_rect(x - 1, y - 1, x + 1, y + 1)


func wake_rect(x0: int, y0: int, x1: int, y1: int) -> void:
	x0 = maxi(x0, 0)
	y0 = maxi(y0, 0)
	x1 = mini(x1, W - 1)
	y1 = mini(y1, H - 1)
	if x0 > x1 or y0 > y1:
		return
	for cy in range(y0 >> CS, (y1 >> CS) + 1):
		var by0 := cy << CS
		var by1 := by0 + CH - 1
		var a0 := maxi(y0, by0)
		var a1 := mini(y1, by1)
		for cx in range(x0 >> CS, (x1 >> CS) + 1):
			var bx0 := cx << CS
			var bx1 := bx0 + CH - 1
			var c := cy * cw + cx
			var b0 := maxi(x0, bx0)
			var b1 := mini(x1, bx1)
			if b0 < nx0[c]:
				nx0[c] = b0
			if b1 > nx1[c]:
				nx1[c] = b1
			if a0 < ny0[c]:
				ny0[c] = a0
			if a1 > ny1[c]:
				ny1[c] = a1


func wake_all() -> void:
	wake_rect(0, 0, W - 1, H - 1)


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------
func step() -> void:
	frame += 1
	var fr := frame
	var t0 := rx0
	rx0 = nx0
	nx0 = t0
	var t1 := ry0
	ry0 = ny0
	ny0 = t1
	var t2 := rx1
	rx1 = nx1
	nx1 = t2
	var t3 := ry1
	ry1 = ny1
	ny1 = t3
	_clear_rects(nx0, ny0, nx1, ny1)

	var c := cells
	var st := stamp
	var kind := _kind
	var flip := (fr & 1) == 1
	var any := false
	var count := 0
	for cy in range(chh - 1, -1, -1):
		var rb := cy * cw
		var ymax := -1
		var ymin := EMPTY_RECT
		for cx in cw:
			var ci := rb + cx
			if rx0[ci] <= rx1[ci]:
				count += 1
				if ry1[ci] > ymax:
					ymax = ry1[ci]
				if ry0[ci] < ymin:
					ymin = ry0[ci]
		if ymax < 0:
			continue
		any = true
		for y in range(ymax, ymin - 1, -1):
			var row := y * W
			for k in cw:
				var ci := rb + ((cw - 1 - k) if flip else k)
				if y < ry0[ci] or y > ry1[ci]:
					continue
				if flip:
					for x in range(rx1[ci], rx0[ci] - 1, -1):
						var i := row + x
						var m := c[i << 1]
						if m == 0:
							continue
						var kd := kind[m]
						if kd < 2 or st[i] == fr:
							continue
						st[i] = fr
						_dispatch(x, y, m, kd)
				else:
					for x in range(rx0[ci], rx1[ci] + 1):
						var i := row + x
						var m := c[i << 1]
						if m == 0:
							continue
						var kd := kind[m]
						if kd < 2 or st[i] == fr:
							continue
						st[i] = fr
						_dispatch(x, y, m, kd)
	active_count = count
	if any:
		tex_dirty = true


func _dispatch(x: int, y: int, m: int, kd: int) -> void:
	if kd == Mat.K_LIQUID:
		_upd_liquid(x, y, m)
	elif kd == Mat.K_POWDER:
		_upd_powder(x, y, m)
	elif kd == Mat.K_GAS:
		_upd_gas(x, y, m)
	elif kd == Mat.K_FIRE:
		_upd_fire(x, y)
	else:
		_upd_burning(x, y)


## Swap two cells. The cell that moves from (x,y) is stamped as processed.
func _move(x: int, y: int, nx: int, ny: int) -> void:
	var ia := y * W + x
	var ib := ny * W + nx
	var a := ia << 1
	var b := ib << 1
	var c := cells
	var m := c[a]
	var d := c[a + 1]
	c[a] = c[b]
	c[a + 1] = c[b + 1]
	c[b] = m
	c[b + 1] = d
	stamp[ib] = frame
	_wake(x, y)
	_wake(nx, ny)


func _passable_for(m: int, target: int) -> bool:
	if target == 0:
		return true
	var kt := _kind[target]
	if kt == Mat.K_GAS or kt == Mat.K_FIRE:
		return true
	if kt == Mat.K_LIQUID and _dens[target] < _dens[m]:
		return true
	return false


func _upd_powder(x: int, y: int, m: int) -> void:
	if y >= H - 1:
		return
	var c := cells
	var b := (y + 1) * W + x
	var mb := c[b << 1]
	if mb == 0:
		_move(x, y, x, y + 1)
		return
	var kb := _kind[mb]
	if kb == Mat.K_GAS or kb == Mat.K_FIRE:
		_move(x, y, x, y + 1)
		return
	if kb == Mat.K_LIQUID and _dens[mb] < _dens[m]:
		if (randi() & 1) == 0:
			_move(x, y, x, y + 1)
		else:
			_wake(x, y)
		return
	var dir := 1 if (randi() & 1) == 0 else -1
	var nx := x + dir
	if nx >= 0 and nx < W and _passable_for(m, c[(b + dir) << 1]) and _passable_for(m, c[(y * W + nx) << 1]):
		_move(x, y, nx, y + 1)
		return
	nx = x - dir
	if nx >= 0 and nx < W and _passable_for(m, c[(b - dir) << 1]) and _passable_for(m, c[(y * W + nx) << 1]):
		_move(x, y, nx, y + 1)


func _fell(x: int, y: int) -> void:
	# Reset the idle counter of a liquid that just fell.
	cells[((y * W + x) << 1) + 1] = 0


func _upd_liquid(x: int, y: int, m: int) -> void:
	var c := cells
	if m == Mat.ACID:
		if _react_acid(x, y):
			return
	elif m == Mat.LAVA:
		if _react_lava(x, y):
			return
	var visc := _visc[m]
	if visc > 0 and randi() % 100 < visc:
		# Viscous: skip this tick but stay awake while it can still flow.
		if y < H - 1 and _passable_for(m, c[((y + 1) * W + x) << 1]):
			_wake(x, y)
		return
	if y < H - 1:
		var b := (y + 1) * W + x
		var mb := c[b << 1]
		if mb == 0:
			_move(x, y, x, y + 1)
			_fell(x, y + 1)
			return
		var kb := _kind[mb]
		if kb == Mat.K_GAS or kb == Mat.K_FIRE:
			_move(x, y, x, y + 1)
			_fell(x, y + 1)
			return
		if kb == Mat.K_LIQUID and _dens[mb] < _dens[m] and (randi() & 3) == 0:
			_move(x, y, x, y + 1)
			_fell(x, y + 1)
			return
		var dir := 1 if (randi() & 1) == 0 else -1
		var nx := x + dir
		if nx >= 0 and nx < W:
			var md := c[(b + dir) << 1]
			if md == 0 or _kind[md] == Mat.K_GAS:
				_move(x, y, nx, y + 1)
				_fell(nx, y + 1)
				return
		nx = x - dir
		if nx >= 0 and nx < W:
			var md2 := c[(b - dir) << 1]
			if md2 == 0 or _kind[md2] == Mat.K_GAS:
				_move(x, y, nx, y + 1)
				_fell(nx, y + 1)
				return
	# Sideways flow. Cells that only drift sideways eventually fall asleep.
	var idle := c[((y * W + x) << 1) + 1]
	if idle >= LIQUID_SLEEP:
		return
	var disp := _disp[m]
	var sdir := 1 if (randi() & 1) == 0 else -1
	for attempt in 2:
		var best := -1
		var drop := false
		for s in range(1, disp + 1):
			var tx := x + sdir * s
			if tx < 0 or tx >= W:
				break
			var mt := c[(y * W + tx) << 1]
			if mt == 0 or _kind[mt] == Mat.K_GAS:
				best = tx
				if y < H - 1 and c[((y + 1) * W + tx) << 1] == 0:
					drop = true
					break
			else:
				break
		if best >= 0:
			_move(x, y, best, y)
			c[((y * W + best) << 1) + 1] = 0 if drop else idle + 1
			return
		sdir = -sdir


func _upd_gas(x: int, y: int, m: int) -> void:
	var c := cells
	var bi := (y * W + x) << 1
	var life := c[bi + 1] & 127
	if (randi() & 3) == 0:
		life -= 1
		if life <= 0:
			if m == Mat.STEAM and randi() % 3 == 0:
				set_cell(x, y, Mat.WATER)
			else:
				set_cell(x, y, Mat.EMPTY, 0)
			return
		c[bi + 1] = life
	_wake(x, y)
	if y > 0:
		var a := (y - 1) * W + x
		var ma := c[a << 1]
		if ma == 0:
			if (randi() & 3) != 0:
				_move(x, y, x, y - 1)
				return
		elif _kind[ma] == Mat.K_LIQUID or _kind[ma] == Mat.K_POWDER:
			if (randi() & 3) == 0:
				_move(x, y, x, y - 1)
				return
		var dir := 1 if (randi() & 1) == 0 else -1
		var nx := x + dir
		if nx >= 0 and nx < W and c[(a + dir) << 1] == 0:
			_move(x, y, nx, y - 1)
			return
	var sx := x + (1 if (randi() & 1) == 0 else -1)
	if sx >= 0 and sx < W and c[(y * W + sx) << 1] == 0:
		_move(x, y, sx, y)


func _upd_fire(x: int, y: int) -> void:
	var c := cells
	var bi := (y * W + x) << 1
	var r := randi()
	var life := (c[bi + 1] & 127) - 1 - (r & 1)
	if life <= 0:
		if (r & 12) == 0:
			set_cell(x, y, Mat.SMOKE, 20 + ((r >> 4) & 31))
		else:
			set_cell(x, y, Mat.EMPTY, 0)
		return
	c[bi + 1] = life
	_wake(x, y)
	# Interact with a random neighbour
	var dir := (r >> 6) & 3
	var nx := x + (1 if dir == 0 else (-1 if dir == 1 else 0))
	var ny := y + (1 if dir == 2 else (-1 if dir == 3 else 0))
	if nx >= 0 and ny >= 0 and nx < W and ny < H:
		var mn := c[(ny * W + nx) << 1]
		if mn == Mat.WATER or mn == Mat.BLOOD or mn == Mat.AETHER:
			set_cell(x, y, Mat.STEAM, 40 + ((r >> 9) & 31))
			if (r & 0x400) != 0:
				set_cell(nx, ny, Mat.STEAM, 30 + ((r >> 11) & 31))
			return
		if mn == Mat.ICE or mn == Mat.SNOW:
			if ((r >> 12) & 3) == 0:
				set_cell(nx, ny, Mat.WATER)
		elif mn != 0:
			var fl := _flam[mn]
			if fl > 0 and ((r >> 14) % 100) < fl:
				ignite(nx, ny)
	# Rise and flicker
	if y > 0:
		var up := (y - 1) * W + x
		if c[up << 1] == 0 and ((r >> 20) & 3) != 0:
			_move(x, y, x, y - 1)
			return
		var dx := 1 if ((r >> 22) & 1) == 0 else -1
		if x + dx >= 0 and x + dx < W and c[(up + dx) << 1] == 0:
			_move(x, y, x + dx, y - 1)


func _upd_burning(x: int, y: int) -> void:
	var c := cells
	var bi := (y * W + x) << 1
	var r := randi()
	var life := c[bi + 1] & 127
	if (r & 3) == 0:
		life -= 1
		if life <= 0:
			var roll := (r >> 2) & 7
			if roll < 3:
				set_cell(x, y, Mat.ASH)
			elif roll < 5:
				set_cell(x, y, Mat.SMOKE, 30 + ((r >> 5) & 31))
			else:
				set_cell(x, y, Mat.EMPTY, 0)
			return
		c[bi + 1] = life
	_wake(x, y)
	# Flames above
	if y > 0 and c[((y - 1) * W + x) << 1] == 0 and ((r >> 8) & 3) == 0:
		set_cell(x, y - 1, Mat.FIRE, 12 + ((r >> 10) & 31))
	# Spread / react with one random neighbour (8 directions)
	var d := (r >> 15) & 7
	var nx := x + N8X[d]
	var ny := y + N8Y[d]
	if nx < 0 or ny < 0 or nx >= W or ny >= H:
		return
	var mn := c[(ny * W + nx) << 1]
	if mn == 0:
		return
	if mn == Mat.WATER or mn == Mat.BLOOD:
		set_cell(x, y, Mat.ASH)
		if ((r >> 18) & 1) == 0:
			set_cell(nx, ny, Mat.STEAM, 40)
		return
	if mn == Mat.ICE or mn == Mat.SNOW:
		set_cell(nx, ny, Mat.WATER)
		return
	var fl := _flam[mn]
	if fl > 0 and ((r >> 19) % 100) < fl:
		ignite(nx, ny)


func _react_acid(x: int, y: int) -> bool:
	var r := randi()
	if (r & 3) != 0:
		return false
	var d := (r >> 2) & 3
	var nx := x + (1 if d == 0 else (-1 if d == 1 else 0))
	var ny := y + (1 if d >= 2 else 0)
	if nx < 0 or ny < 0 or nx >= W or ny >= H:
		return false
	var mn := cells[(ny * W + nx) << 1]
	if mn == 0 or mn == Mat.ACID or _diss[mn] == 0:
		return false
	var kn := _kind[mn]
	if kn == Mat.K_GAS or kn == Mat.K_FIRE:
		return false
	if kn == Mat.K_LIQUID and mn != Mat.WATER and mn != Mat.BLOOD:
		return false
	if ((r >> 4) & 7) == 0:
		set_cell(nx, ny, Mat.TOXIC, 30 + ((r >> 7) & 31))
	else:
		set_cell(nx, ny, Mat.EMPTY, 0)
	if ((r >> 12) % 100) < 30:
		set_cell(x, y, Mat.EMPTY, 0)
		return true
	_wake(x, y)
	return false


func _react_lava(x: int, y: int) -> bool:
	var r := randi()
	var d := r & 3
	var nx := x + (1 if d == 0 else (-1 if d == 1 else 0))
	var ny := y + (1 if d == 2 else (-1 if d == 3 else 0))
	if nx < 0 or ny < 0 or nx >= W or ny >= H:
		return false
	var mn := cells[(ny * W + nx) << 1]
	if mn == 0:
		return false
	if mn == Mat.WATER or mn == Mat.BLOOD or mn == Mat.AETHER:
		set_cell(x, y, Mat.OBSIDIAN)
		set_cell(nx, ny, Mat.STEAM, 50 + ((r >> 4) & 31))
		return true
	if mn == Mat.ICE or mn == Mat.SNOW:
		set_cell(nx, ny, Mat.WATER)
		return false
	if _flam[mn] > 0 and ((r >> 9) & 3) == 0:
		ignite(nx, ny)
	return false


# ---------------------------------------------------------------------------
# World manipulation API (used by spells, explosions, generator)
# ---------------------------------------------------------------------------
func ignite(x: int, y: int) -> void:
	var m := get_mat(x, y)
	if m == Mat.GUNPOWDER:
		set_cell(x, y, Mat.FIRE, 40)
		pending_explosions.append(Vector3i(x, y, 7))
		return
	var k := _kind[m]
	if k == Mat.K_LIQUID:
		set_cell(x, y, Mat.FIRE, 70 + (randi() & 31))
	elif k == Mat.K_STATIC or k == Mat.K_POWDER:
		var life := 60
		if m == Mat.WOOD:
			life = 90 + (randi() & 31)
		elif m == Mat.COAL:
			life = 127
		elif m == Mat.MOSS:
			life = 25 + (randi() & 15)
		elif m == Mat.FUNGUS:
			life = 45 + (randi() & 31)
		set_cell(x, y, Mat.BURNING, life)
	elif m == Mat.EMPTY:
		set_cell(x, y, Mat.FIRE, 30 + (randi() & 31))


func place_fire(x: int, y: int, life: int = 40) -> void:
	if get_mat(x, y) == Mat.EMPTY:
		set_cell(x, y, Mat.FIRE, life)


func emit_gas(x: int, y: int, m: int, life: int = 50) -> void:
	if get_mat(x, y) == Mat.EMPTY:
		set_cell(x, y, m, life)


## Fill empty cells inside a circle with a material (liquids, powders...).
func spawn_blob(cx: int, cy: int, r: int, m: int, chance: float = 1.0) -> int:
	var count := 0
	var r2 := r * r
	var gas := _kind[m] == Mat.K_GAS
	for y in range(cy - r, cy + r + 1):
		for x in range(cx - r, cx + r + 1):
			var dx := x - cx
			var dy := y - cy
			if dx * dx + dy * dy > r2:
				continue
			if get_mat(x, y) != Mat.EMPTY:
				continue
			if chance < 1.0 and randf() > chance:
				continue
			set_cell(x, y, m, (60 + (randi() & 63)) if gas else -1)
			count += 1
	return count


func _raw_set(i: int, m: int, data: int) -> void:
	cells[i << 1] = m
	cells[(i << 1) + 1] = data
	stamp[i] = frame


## Remove cells inside a circle whose hardness <= max_hard. Returns removed count.
func carve_circle(cx: int, cy: int, r: int, max_hard: int, debris_chance: float = 0.0, only_soft: bool = false) -> int:
	var count := 0
	var r2 := r * r
	for y in range(maxi(0, cy - r), mini(H, cy + r + 1)):
		for x in range(maxi(0, cx - r), mini(W, cx + r + 1)):
			var dx := x - cx
			var dy := y - cy
			if dx * dx + dy * dy > r2:
				continue
			var i := y * W + x
			var m := cells[i << 1]
			if m == 0:
				continue
			if _hard[m] > max_hard:
				continue
			if only_soft and Mat.SOFT[m] == 0:
				continue
			var k := _kind[m]
			if k == Mat.K_GAS or k == Mat.K_FIRE:
				continue
			_raw_set(i, 0, 0)
			count += 1
			if debris_chance > 0.0 and particles and randf() < debris_chance:
				var deb := m if k == Mat.K_POWDER or k == Mat.K_LIQUID else int(_debris[m])
				particles.spawn_material(Vector2(x, y), Vector2(randf_range(-40, 40), randf_range(-70, -10)), deb, m)
	wake_rect(cx - r - 1, cy - r - 1, cx + r + 1, cy + r + 1)
	tex_dirty = true
	return count


## Explosion: destroys terrain based on hardness, throws debris and liquids.
func explode(cx: int, cy: int, r: int, power: float, fire: bool = false) -> void:
	var r2 := r * r
	var spawned := 0
	for y in range(maxi(0, cy - r), mini(H, cy + r + 1)):
		for x in range(maxi(0, cx - r), mini(W, cx + r + 1)):
			var dx := x - cx
			var dy := y - cy
			var d2 := dx * dx + dy * dy
			if d2 > r2:
				continue
			var i := y * W + x
			var m := cells[i << 1]
			var falloff := 1.0 - sqrt(float(d2)) / float(r + 1)
			if m != 0:
				var hard := _hard[m]
				if hard >= 255:
					continue
				var k := _kind[m]
				var eff := power * (0.45 + 0.55 * falloff)
				if k == Mat.K_STATIC or k == Mat.K_BURNING:
					if hard <= eff:
						_raw_set(i, 0, 0)
						if particles and spawned < MAX_PARTICLE_SPAWN and randf() < 0.1:
							spawned += 1
							var dir := Vector2(dx, dy).normalized() if d2 > 0 else Vector2.UP
							particles.spawn_material(Vector2(x, y), dir * randf_range(60, 190) * (0.4 + falloff) + Vector2(0, -40), int(_debris[m]), m)
					elif hard <= eff * 1.6 and _debris[m] != 0 and randf() < 0.5:
						_raw_set(i, _debris[m], randi() & 127)
						continue
					else:
						continue
				elif k == Mat.K_POWDER or k == Mat.K_LIQUID:
					_raw_set(i, 0, 0)
					if particles and spawned < MAX_PARTICLE_SPAWN and randf() < 0.45:
						spawned += 1
						var dir2 := Vector2(dx, dy).normalized() if d2 > 0 else Vector2.UP
						particles.spawn_material(Vector2(x, y), dir2 * randf_range(50, 170) * (0.3 + falloff) + Vector2(0, -50), m, m)
					if m == Mat.GUNPOWDER:
						pending_explosions.append(Vector3i(x, y, 6))
				else:
					_raw_set(i, 0, 0)
			if cells[i << 1] == 0:
				if fire and randf() < 0.2 * falloff + 0.03:
					_raw_set(i, Mat.FIRE, 20 + (randi() & 63))
				elif randf() < 0.05:
					_raw_set(i, Mat.SMOKE, 30 + (randi() & 31))
			elif fire and _flam[cells[i << 1]] > 0 and randf() < 0.5:
				ignite(x, y)
	wake_rect(cx - r - 2, cy - r - 2, cx + r + 2, cy + r + 2)
	tex_dirty = true


## Turn solids inside a circle into their loose debris (they collapse).
func crumble(cx: int, cy: int, r: int, max_hard: int) -> int:
	var count := 0
	var r2 := r * r
	for y in range(maxi(0, cy - r), mini(H, cy + r + 1)):
		for x in range(maxi(0, cx - r), mini(W, cx + r + 1)):
			var dx := x - cx
			var dy := y - cy
			if dx * dx + dy * dy > r2:
				continue
			var i := y * W + x
			var m := cells[i << 1]
			if m == 0 or _kind[m] != Mat.K_STATIC or _hard[m] > max_hard:
				continue
			var deb := int(_debris[m])
			if deb == 0:
				deb = Mat.GRAVEL if m != Mat.WOOD else Mat.ASH
			_raw_set(i, deb, randi() & 127)
			count += 1
	wake_rect(cx - r - 1, cy - r - 1, cx + r + 1, cy + r + 1)
	tex_dirty = true
	return count


## Freeze liquids, extinguish fire.
func freeze(cx: int, cy: int, r: int) -> void:
	var r2 := r * r
	for y in range(maxi(0, cy - r), mini(H, cy + r + 1)):
		for x in range(maxi(0, cx - r), mini(W, cx + r + 1)):
			var dx := x - cx
			var dy := y - cy
			if dx * dx + dy * dy > r2:
				continue
			var i := y * W + x
			var m := cells[i << 1]
			if m == Mat.WATER or m == Mat.BLOOD:
				_raw_set(i, Mat.ICE, randi() & 127)
			elif m == Mat.LAVA:
				_raw_set(i, Mat.OBSIDIAN, randi() & 127)
			elif m == Mat.FIRE or m == Mat.STEAM:
				_raw_set(i, Mat.EMPTY, 0)
			elif m == Mat.BURNING:
				_raw_set(i, Mat.ASH, randi() & 127)
			elif (m == Mat.SLUDGE or m == Mat.ACID) and randf() < 0.5:
				_raw_set(i, Mat.ICE, randi() & 127)
	wake_rect(cx - r - 1, cy - r - 1, cx + r + 1, cy + r + 1)
	tex_dirty = true


func extinguish(cx: int, cy: int, r: int) -> void:
	var r2 := r * r
	for y in range(maxi(0, cy - r), mini(H, cy + r + 1)):
		for x in range(maxi(0, cx - r), mini(W, cx + r + 1)):
			var dx := x - cx
			var dy := y - cy
			if dx * dx + dy * dy > r2:
				continue
			var i := y * W + x
			var m := cells[i << 1]
			if m == Mat.FIRE:
				_raw_set(i, Mat.STEAM, 30)
			elif m == Mat.BURNING:
				_raw_set(i, Mat.ASH, randi() & 127)
	wake_rect(cx - r - 1, cy - r - 1, cx + r + 1, cy + r + 1)


# ---------------------------------------------------------------------------
# Queries for actors
# ---------------------------------------------------------------------------
func rect_free(x: int, y: int, w: int, h: int) -> bool:
	if x < 0 or y < 0 or x + w > W or y + h > H:
		return false
	var c := cells
	var s := _solid
	for yy in range(y, y + h):
		var row := yy * W
		for xx in range(x, x + w):
			if s[c[(row + xx) << 1]] != 0:
				return false
	return true


func col_free(x: int, y0: int, y1: int) -> bool:
	if x < 0 or x >= W or y0 < 0 or y1 >= H:
		return false
	var c := cells
	var s := _solid
	for yy in range(y0, y1 + 1):
		if s[c[(yy * W + x) << 1]] != 0:
			return false
	return true


func row_free(y: int, x0: int, x1: int) -> bool:
	if y < 0 or y >= H or x0 < 0 or x1 >= W:
		return false
	var c := cells
	var s := _solid
	var row := y * W
	for xx in range(x0, x1 + 1):
		if s[c[(row + xx) << 1]] != 0:
			return false
	return true


## True when the straight line between two points is free of solids.
func line_clear(a: Vector2, b: Vector2) -> bool:
	var d := b - a
	var n := int(maxf(absf(d.x), absf(d.y)))
	if n <= 0:
		return true
	var st := d / float(n)
	var p := a
	for i in n:
		p += st
		if is_solid_at(int(p.x), int(p.y)):
			return false
	return true


## Returns the last free point along a ray before hitting a solid.
func raycast(a: Vector2, dir: Vector2, max_dist: float) -> Vector2:
	var p := a
	var st := dir.normalized()
	var n := int(max_dist)
	for i in n:
		var q := p + st
		if is_solid_at(int(q.x), int(q.y)):
			return p
		p = q
	return p


func mat_at_point(p: Vector2) -> int:
	return get_mat(int(floor(p.x)), int(floor(p.y)))
