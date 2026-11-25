class_name Particles
extends Node2D
## Free-flying pixels: debris, sparks, splashes. Material particles turn back
## into world cells when they land.

const MAX := 3000

var world: PixelWorld
var px := PackedFloat32Array()
var py := PackedFloat32Array()
var vx := PackedFloat32Array()
var vy := PackedFloat32Array()
var life := PackedFloat32Array()
var maxlife := PackedFloat32Array()
var grav := PackedFloat32Array()
var mat := PackedByteArray()
var col := PackedColorArray()
var count := 0


func _ready() -> void:
	px.resize(MAX)
	py.resize(MAX)
	vx.resize(MAX)
	vy.resize(MAX)
	life.resize(MAX)
	maxlife.resize(MAX)
	grav.resize(MAX)
	mat.resize(MAX)
	col.resize(MAX)
	z_index = 4


func clear() -> void:
	count = 0
	queue_redraw()


func spawn(pos: Vector2, v: Vector2, c: Color, l: float, g: float = 1.0, m: int = 0) -> void:
	if count >= MAX:
		return
	var i := count
	count += 1
	px[i] = pos.x
	py[i] = pos.y
	vx[i] = v.x
	vy[i] = v.y
	life[i] = l
	maxlife[i] = l
	grav[i] = g
	mat[i] = m
	col[i] = c


## Debris that lands as material `place` (0 = vanish), coloured like `color_mat`.
func spawn_material(pos: Vector2, v: Vector2, place: int, color_mat: int) -> void:
	var c := Mat.color_of(color_mat, randf())
	c.a = 1.0
	spawn(pos, v, c, 2.5, 1.0, place)


func burst(pos: Vector2, n: int, c: Color, speed: float, l: float, g: float = 0.6, spread: float = TAU, dir: float = 0.0) -> void:
	for k in n:
		var a := dir + randf_range(-spread * 0.5, spread * 0.5)
		var s := speed * randf_range(0.3, 1.0)
		var cc := c
		cc = cc.lightened(randf_range(0.0, 0.3))
		spawn(pos, Vector2(cos(a), sin(a)) * s, cc, l * randf_range(0.6, 1.2), g)


func _physics_process(delta: float) -> void:
	if world == null:
		return
	var g := 480.0 * delta
	var i := 0
	var solid := Mat.SOLID
	var kind := Mat.KIND
	while i < count:
		life[i] -= delta
		if life[i] <= 0.0:
			if mat[i] != 0:
				_land(i)
			_remove(i)
			continue
		vy[i] += g * grav[i]
		var nx := px[i] + vx[i] * delta
		var ny := py[i] + vy[i] * delta
		var m := world.get_mat(int(nx), int(ny))
		if m != 0:
			var k := kind[m]
			if solid[m] != 0 or (mat[i] != 0 and k == Mat.K_LIQUID):
				if mat[i] != 0:
					_land(i)
				_remove(i)
				continue
		px[i] = nx
		py[i] = ny
		i += 1
	queue_redraw()


func _land(i: int) -> void:
	var x := int(px[i])
	var y := int(py[i])
	for k in 4:
		if world.get_mat(x, y - k) == Mat.EMPTY:
			world.set_cell(x, y - k, mat[i])
			return


func _remove(i: int) -> void:
	count -= 1
	if i == count:
		return
	px[i] = px[count]
	py[i] = py[count]
	vx[i] = vx[count]
	vy[i] = vy[count]
	life[i] = life[count]
	maxlife[i] = maxlife[count]
	grav[i] = grav[count]
	mat[i] = mat[count]
	col[i] = col[count]


func _draw() -> void:
	for i in count:
		var c := col[i]
		if mat[i] == 0:
			c.a = clampf(life[i] / maxlife[i] * 1.5, 0.0, 1.0)
		draw_rect(Rect2(floorf(px[i]), floorf(py[i]), 1, 1), c)
