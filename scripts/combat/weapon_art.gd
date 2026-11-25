class_name WeaponArt
extends RefCounted
## Draws a unique pixel-art sprite for every generated weapon (seeded).

const OUTLINE := Color("140c1c")
const SHAFTS := [
	[Color("4a2e1e"), Color("6b4430"), Color("8f5d3b")],  # wood
	[Color("8f8470"), Color("c2b59b"), Color("efe6d2")],  # bone
	[Color("2b2832"), Color("4a4656"), Color("6e6a7c")],  # dark metal
	[Color("3a1f78"), Color("5a2fb0"), Color("9a5cf0")],  # crystal
]
const BLADES := {
	"": [Color("7d8796"), Color("b3bcc8"), Color("eef2f6")],
	"fire": [Color("b5321a"), Color("ff8a1f"), Color("ffe07a")],
	"ice": [Color("3f86b8"), Color("a8e4f5"), Color("f0fcff")],
	"acid": [Color("3f7d18"), Color("9be03a"), Color("e7ff8a")],
	"void": [Color("4a2596"), Color("9a5cf0"), Color("e2c8ff")],
}
const GOLD := [Color("8a5a14"), Color("f2c14e"), Color("fff2a8")]


static var _flask_sheet: Image


static func grip_x(type: int) -> int:
	return 6 if type == Weapon.STAFF else 3


static func tip_dist(type: int) -> float:
	if type == Weapon.FLASK:
		return 6.0
	return 14.0 if type == Weapon.STAFF else 10.0


static func make(w: Weapon) -> ImageTexture:
	if w.type == Weapon.FLASK:
		return ImageTexture.create_from_image(_flask(w))
	var r := RandomNumberGenerator.new()
	r.seed = w.seed ^ 0x77
	var img: Image
	match w.type:
		Weapon.WAND:
			img = _wand(w, r)
		Weapon.STAFF:
			img = _staff(w, r)
		_:
			img = _sword(w, r)
	_outline(img)
	return ImageTexture.create_from_image(img)


static func _px(img: Image, x: int, y: int, c: Color) -> void:
	if x >= 0 and y >= 0 and x < img.get_width() and y < img.get_height():
		img.set_pixel(x, y, c)


static func _outline(img: Image) -> void:
	var w := img.get_width()
	var h := img.get_height()
	var src := img.duplicate() as Image
	for y in h:
		for x in w:
			if src.get_pixel(x, y).a > 0.5:
				continue
			var near := false
			for d in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]:
				var q: Vector2i = Vector2i(x, y) + d
				if q.x >= 0 and q.y >= 0 and q.x < w and q.y < h and src.get_pixel(q.x, q.y).a > 0.5:
					near = true
					break
			if near:
				img.set_pixel(x, y, OUTLINE)


static func _gem(img: Image, cx: int, cy: int, col: Color) -> void:
	var dark := col.darkened(0.45)
	var light := col.lightened(0.55)
	_px(img, cx, cy - 1, col)
	_px(img, cx - 1, cy, col)
	_px(img, cx, cy, col)
	_px(img, cx + 1, cy, dark)
	_px(img, cx, cy + 1, dark)
	_px(img, cx - 1, cy - 1, light)


static func _wand(w: Weapon, r: RandomNumberGenerator) -> Image:
	var img := Image.create_empty(16, 8, false, Image.FORMAT_RGBA8)
	var sh: Array = SHAFTS[w.look % SHAFTS.size()]
	var gem := w.main_color()
	var length := r.randi_range(9, 11)
	for x in range(1, length):
		_px(img, x, 3, sh[2] if x % 4 != 0 else sh[1])
		_px(img, x, 4, sh[0] if x % 3 != 0 else sh[1])
	# leather grip
	for x in range(2, 5):
		_px(img, x, 3, Color("6b4430") if x % 2 == 0 else Color("3b2418"))
		_px(img, x, 4, Color("3b2418"))
	# ring
	_px(img, length - 1, 3, GOLD[2])
	_px(img, length - 1, 4, GOLD[0])
	# tip gem
	var gx := length + 1
	match r.randi_range(0, 2):
		0:
			_gem(img, gx, 3, gem)
			_px(img, gx + 1, 3, gem.lightened(0.2))
		1:
			_px(img, gx - 1, 3, gem)
			_px(img, gx, 2, gem.lightened(0.5))
			_px(img, gx, 3, gem)
			_px(img, gx, 4, gem.darkened(0.3))
			_px(img, gx + 1, 3, gem.lightened(0.3))
			_px(img, gx + 2, 3, gem.lightened(0.6))
		_:
			_px(img, gx - 1, 2, GOLD[1])
			_px(img, gx - 1, 5, GOLD[1])
			_gem(img, gx, 3, gem)
			_gem(img, gx, 4, gem)
	return img


static func _staff(w: Weapon, r: RandomNumberGenerator) -> Image:
	var img := Image.create_empty(24, 10, false, Image.FORMAT_RGBA8)
	var sh: Array = SHAFTS[(w.look + 1) % SHAFTS.size()]
	var gem := w.main_color()
	var length := r.randi_range(15, 17)
	for x in range(1, length):
		var wob := 1 if (x * 7 + w.seed) % 9 == 0 else 0
		_px(img, x, 4 + wob, sh[2])
		_px(img, x, 5 + wob, sh[0] if x % 2 == 0 else sh[1])
	for x in range(5, 8):
		_px(img, x, 4, Color("6b4430"))
		_px(img, x, 5, Color("3b2418"))
	var hx := length
	match w.look:
		0:
			for y in range(1, 9):
				for x in range(hx, hx + 6):
					var d := Vector2(x - (hx + 2.5), y - 4.5).length()
					if d <= 2.6:
						_px(img, x, y, gem if d > 1.2 else gem.lightened(0.4))
			_px(img, hx + 1, 3, Color.WHITE)
			_px(img, hx - 1, 2, sh[1])
			_px(img, hx - 1, 7, sh[1])
		1:
			for i in 5:
				_px(img, hx + i, 4 - i / 2, sh[2])
				_px(img, hx + i, 5 + i / 2, sh[1])
			_gem(img, hx + 3, 4, gem)
			_gem(img, hx + 3, 5, gem)
		2:
			for x in range(hx, hx + 7):
				var half := 2.6 - absf(x - (hx + 2.5)) * 0.8
				for y in range(1, 9):
					if absf(y - 4.5) <= half:
						_px(img, x, y, gem.lightened(0.35) if y < 4 else gem)
			_px(img, hx + 2, 3, Color.WHITE)
		_:
			for a in 16:
				var ang := a * TAU / 16.0
				_px(img, int(round(hx + 2.5 + cos(ang) * 3.0)), int(round(4.5 + sin(ang) * 3.2)), GOLD[1])
			_gem(img, hx + 2, 4, gem)
			_gem(img, hx + 3, 5, gem)
	return img


static func _sword(w: Weapon, r: RandomNumberGenerator) -> Image:
	var img := Image.create_empty(20, 9, false, Image.FORMAT_RGBA8)
	var bl: Array = BLADES.get(w.element, BLADES[""])
	var guard: Array = GOLD if r.randf() < 0.5 else [Color("4a4656"), Color("8a8698"), Color("c8c4d6")]
	var blade_end := r.randi_range(16, 18)
	# pommel + grip
	_px(img, 1, 4, guard[1])
	for x in range(2, 5):
		_px(img, x, 4, Color("6b4430") if x % 2 == 0 else Color("3b2418"))
	# crossguard
	var gw := r.randi_range(2, 3)
	for y in range(4 - gw, 5 + gw):
		_px(img, 5, y, guard[1] if y < 4 else guard[0])
	_px(img, 5, 4 - gw, guard[2])
	# blade
	for x in range(6, blade_end):
		_px(img, x, 3, bl[2])
		_px(img, x, 4, bl[1])
		_px(img, x, 5, bl[0])
	_px(img, blade_end, 4, bl[2])
	_px(img, blade_end - 1, 5, Color(0, 0, 0, 0))
	if w.element == "":
		for x in range(7, blade_end - 3):
			_px(img, x, 4, bl[0].lerp(bl[1], 0.6))
	elif w.element == "fire":
		for x in range(7, blade_end, 3):
			_px(img, x, 2, Color("ffb33a"))
	elif w.element == "void":
		for x in range(7, blade_end, 4):
			_px(img, x, 4, Color("140c1c"))
	return img


## Potion flask: glass template (flask.png row 0) over the liquid mask (row 1)
## filled from the bottom according to the amount. Fallback: drawn in code.
static func _flask(w: Weapon) -> Image:
	var img := Image.create_empty(10, 12, false, Image.FORMAT_RGBA8)
	var frac := clampf(w.amount / Weapon.FLASK_MAX, 0.0, 1.0) if w.liquid != 0 else 0.0
	var c0 := Mat.C0[w.liquid] if w.liquid != 0 else Color.WHITE
	var c1 := Mat.C1[w.liquid] if w.liquid != 0 else Color.WHITE
	c0.a = 1.0
	c1.a = 1.0
	if _flask_sheet == null and ResourceLoader.exists("res://assets/sprites/flask.png"):
		var t: Texture2D = load("res://assets/sprites/flask.png")
		_flask_sheet = t.get_image()
		if _flask_sheet.is_compressed():
			_flask_sheet.decompress()
		_flask_sheet.convert(Image.FORMAT_RGBA8)
	if _flask_sheet != null:
		var sx := (w.look % 3) * 10
		var ymin := 99
		var ymax := -1
		for y in 12:
			for x in 10:
				if _flask_sheet.get_pixel(sx + x, 12 + y).a > 0.5:
					ymin = mini(ymin, y)
					ymax = maxi(ymax, y)
		if ymax >= 0 and frac > 0.0:
			var rows := ymax - ymin + 1
			var fill_from := ymax + 1 - int(ceil(rows * frac))
			for y in range(fill_from, ymax + 1):
				for x in 10:
					if _flask_sheet.get_pixel(sx + x, 12 + y).a > 0.5:
						img.set_pixel(x, y, c1.lightened(0.25) if y == fill_from else (c0 if (x + y) % 3 == 0 else c1))
		img.blend_rect(_flask_sheet, Rect2i(sx, 0, 10, 12), Vector2i.ZERO)
		return img
	# fallback flask
	var glass := Color(0.75, 0.88, 1.0)
	for y in range(4, 11):
		_px(img, 2, y, OUTLINE)
		_px(img, 7, y, OUTLINE)
	for x in range(2, 8):
		_px(img, x, 11, OUTLINE)
	_px(img, 4, 1, Color("8f5d3b"))
	_px(img, 5, 1, Color("8f5d3b"))
	for y in range(2, 4):
		_px(img, 3, y, OUTLINE)
		_px(img, 6, y, OUTLINE)
	var filled := int(round(7 * frac))
	for y in range(11 - filled, 11):
		for x in range(3, 7):
			_px(img, x, y, c1 if y > 11 - filled else c1.lightened(0.25))
	_px(img, 3, 5, glass)
	return img
