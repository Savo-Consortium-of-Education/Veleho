extends Node
## Loads sprite sheets, builds SpriteFrames, the bitmap pixel font and the UI theme.

const FONT_SIZE := 12
const FONT_ASCENT := 9
const FONT_DESCENT := 3

const SPRITES: Array[String] = [
	"player", "player_arm", "slime", "bat", "caster", "wisp", "golem",
	"projectiles", "explosion", "slash", "portal", "fx_small", "items",
	"ui", "slot", "crosshair", "logo",
]

var textures := {}
var font: Font
var theme: Theme
var _frames_cache := {}


func _ready() -> void:
	for n in SPRITES:
		textures[n] = _load_tex("res://assets/sprites/%s.png" % n)
	_build_font()
	_build_theme()


func tex(name: String) -> Texture2D:
	if not textures.has(name):
		textures[name] = _load_tex("res://assets/sprites/%s.png" % name)
	return textures[name]


func _load_tex(path: String) -> Texture2D:
	if ResourceLoader.exists(path):
		var t = load(path)
		if t is Texture2D:
			return t
	var img := Image.create_empty(16, 16, false, Image.FORMAT_RGBA8)
	img.fill(Color(1, 0, 1, 0.6))
	return ImageTexture.create_from_image(img)


## anims: Array of [name, row, frame_count, fps, loop]
func frames(sheet: String, fw: int, fh: int, anims: Array, cache_key: String = "") -> SpriteFrames:
	var key := "%s_%d_%d_%s" % [sheet, fw, fh, cache_key]
	if _frames_cache.has(key):
		return _frames_cache[key]
	var sf := SpriteFrames.new()
	var t := tex(sheet)
	for a in anims:
		var an: StringName = a[0]
		if not sf.has_animation(an):
			sf.add_animation(an)
		sf.set_animation_speed(an, float(a[3]))
		sf.set_animation_loop(an, bool(a[4]))
		for i in int(a[2]):
			sf.add_frame(an, region(t, i * fw, int(a[1]) * fh, fw, fh))
	if sf.has_animation("default") and not _has_anim(anims, "default"):
		sf.remove_animation("default")
	_frames_cache[key] = sf
	return sf


func _has_anim(anims: Array, n: String) -> bool:
	for a in anims:
		if String(a[0]) == n:
			return true
	return false


func region(t: Texture2D, x: int, y: int, w: int, h: int) -> AtlasTexture:
	var at := AtlasTexture.new()
	at.atlas = t
	at.region = Rect2(x, y, w, h)
	return at


func icon(index: int) -> AtlasTexture:
	return region(tex("ui"), index * 8, 0, 8, 8)


## 16x16 spell card icon (index from Spells "icon").
func spell_icon(index: int) -> Texture2D:
	if not ResourceLoader.exists("res://assets/sprites/spell_icons.png"):
		return _fallback_spell_icon(index)
	return region(tex("spell_icons"), (index % 8) * 16, (index / 8) * 16, 16, 16)


var _spell_fallbacks := {}


func _fallback_spell_icon(index: int) -> Texture2D:
	if _spell_fallbacks.has(index):
		return _spell_fallbacks[index]
	var img := Image.create_empty(16, 16, false, Image.FORMAT_RGBA8)
	var modifier := index >= 12
	img.fill(Color("1d3156") if modifier else Color("1c1626"))
	var col := Color.from_hsv(fmod(index * 0.137, 1.0), 0.6, 1.0)
	for i in 16:
		img.set_pixel(i, 0, col)
		img.set_pixel(i, 15, col)
		img.set_pixel(0, i, col)
		img.set_pixel(15, i, col)
	img.fill_rect(Rect2i(5, 5, 6, 6), col)
	var t := ImageTexture.create_from_image(img)
	_spell_fallbacks[index] = t
	return t


## UI control graphics (ui_controls.png, 10x10 cells) with generated fallbacks.
func ui_icon(index: int) -> Texture2D:
	if ResourceLoader.exists("res://assets/sprites/ui_controls.png"):
		return region(tex("ui_controls"), index * 10, 0, 10, 10)
	var img := Image.create_empty(10, 10, false, Image.FORMAT_RGBA8)
	match index:
		0, 1:
			img.fill_rect(Rect2i(0, 0, 9, 9), Color("5a4a6e"))
			img.fill_rect(Rect2i(1, 1, 7, 7), Color("140c1c"))
			if index == 1:
				img.fill_rect(Rect2i(2, 2, 5, 5), Color("f2c14e"))
		2, 3:
			img.fill_rect(Rect2i(2, 0, 5, 9), Color("140c1c"))
			img.fill_rect(Rect2i(3, 1, 3, 7), Color("f2c14e") if index == 3 else Color("b3afbd"))
		_:
			img.fill_rect(Rect2i(2, 2, 6, 6), Color("b3afbd"))
	return ImageTexture.create_from_image(img)


# ---------------------------------------------------------------------------
# Bitmap font from assets/fonts/pixel_font.png (8x12 cells, 16 per row)
# ---------------------------------------------------------------------------
func _build_font() -> void:
	var png := "res://assets/fonts/pixel_font.png"
	var txt := "res://assets/fonts/pixel_font_charset.txt"
	if not ResourceLoader.exists(png) or not FileAccess.file_exists(txt):
		font = ThemeDB.fallback_font
		return
	var charset := FileAccess.get_file_as_string(txt).strip_edges(false, true)
	var t: Texture2D = load(png)
	var img := t.get_image()
	if img.is_compressed():
		img.decompress()
	img.convert(Image.FORMAT_RGBA8)
	var f := FontFile.new()
	f.fixed_size = FONT_SIZE
	f.fixed_size_scale_mode = TextServer.FIXED_SIZE_SCALE_INTEGER_ONLY
	f.antialiasing = TextServer.FONT_ANTIALIASING_NONE
	var size := Vector2i(FONT_SIZE, 0)
	f.set_texture_image(0, size, 0, img)
	f.set_cache_ascent(0, FONT_SIZE, FONT_ASCENT)
	f.set_cache_descent(0, FONT_SIZE, FONT_DESCENT)
	for idx in charset.length():
		var ch := charset.unicode_at(idx)
		var cx := (idx % 16) * 8
		var cy := (idx / 16) * 12
		if cy + 12 > img.get_height():
			break
		var minx := 99
		var maxx := -1
		for x in 8:
			for y in 12:
				if img.get_pixel(cx + x, cy + y).a > 0.5:
					minx = mini(minx, x)
					maxx = maxi(maxx, x)
		var w := 0
		var x0 := 0
		var adv := 3
		if maxx >= 0:
			x0 = minx
			w = maxx - minx + 1
			adv = w + 1
		f.set_glyph_advance(0, FONT_SIZE, ch, Vector2(adv, 0))
		f.set_glyph_offset(0, size, ch, Vector2(0, -FONT_ASCENT))
		f.set_glyph_size(0, size, ch, Vector2(w, 12))
		f.set_glyph_uv_rect(0, size, ch, Rect2(cx + x0, cy, w, 12))
		f.set_glyph_texture_idx(0, size, ch, 0)
	font = f


func _box(bg: Color, border: Color, bw: int = 1) -> StyleBoxFlat:
	var sb := StyleBoxFlat.new()
	sb.bg_color = bg
	sb.border_color = border
	sb.set_border_width_all(bw)
	sb.set_content_margin_all(3)
	sb.content_margin_left = 6
	sb.content_margin_right = 6
	sb.anti_aliasing = false
	return sb


func _build_theme() -> void:
	theme = Theme.new()
	theme.default_font = font
	theme.default_font_size = FONT_SIZE
	theme.set_color("font_color", "Label", Color("e8e0d0"))
	theme.set_color("font_shadow_color", "Label", Color(0, 0, 0, 0.8))
	theme.set_constant("shadow_offset_x", "Label", 1)
	theme.set_constant("shadow_offset_y", "Label", 1)
	theme.set_constant("line_spacing", "Label", 0)
	theme.set_stylebox("normal", "Button", _box(Color("1c1626"), Color("5a4a6e")))
	theme.set_stylebox("hover", "Button", _box(Color("2c2140"), Color("f2c14e")))
	theme.set_stylebox("pressed", "Button", _box(Color("3b2d55"), Color("ffe08a")))
	theme.set_stylebox("focus", "Button", _box(Color(0, 0, 0, 0), Color("f2c14e")))
	theme.set_stylebox("disabled", "Button", _box(Color("141019"), Color("3a3245")))
	theme.set_color("font_color", "Button", Color("e8e0d0"))
	theme.set_color("font_hover_color", "Button", Color("ffe9a8"))
	theme.set_color("font_pressed_color", "Button", Color("ffffff"))
	theme.set_color("font_disabled_color", "Button", Color("6b6275"))
	theme.set_stylebox("panel", "Panel", _box(Color(0.06, 0.04, 0.09, 0.92), Color("5a4a6e")))
	theme.set_stylebox("panel", "PanelContainer", _box(Color(0.06, 0.04, 0.09, 0.92), Color("5a4a6e")))
	if ResourceLoader.exists("res://assets/sprites/panel.png"):
		var sbt := StyleBoxTexture.new()
		sbt.texture = load("res://assets/sprites/panel.png")
		sbt.texture_margin_left = 8
		sbt.texture_margin_top = 8
		sbt.texture_margin_right = 8
		sbt.texture_margin_bottom = 8
		sbt.set_content_margin_all(8)
		theme.set_stylebox("panel", "PanelContainer", sbt)
		theme.set_stylebox("panel", "Panel", sbt)
	# Sliders
	var track := StyleBoxFlat.new()
	track.bg_color = Color("140c1c")
	track.border_color = Color("5a4a6e")
	track.set_border_width_all(1)
	track.content_margin_top = 2
	track.content_margin_bottom = 2
	theme.set_stylebox("slider", "HSlider", track)
	var fill := StyleBoxFlat.new()
	fill.bg_color = Color("b07b1f")
	fill.content_margin_top = 2
	fill.content_margin_bottom = 2
	theme.set_stylebox("grabber_area", "HSlider", fill)
	var fill_h := StyleBoxFlat.new()
	fill_h.bg_color = Color("f2c14e")
	fill_h.content_margin_top = 2
	fill_h.content_margin_bottom = 2
	theme.set_stylebox("grabber_area_highlight", "HSlider", fill_h)
	theme.set_icon("grabber", "HSlider", ui_icon(2))
	theme.set_icon("grabber_highlight", "HSlider", ui_icon(3))
	theme.set_icon("grabber_disabled", "HSlider", ui_icon(2))
	# Check boxes
	var empty := StyleBoxEmpty.new()
	for st in ["normal", "hover", "pressed", "focus", "hover_pressed", "disabled"]:
		theme.set_stylebox(st, "CheckBox", empty)
	theme.set_icon("checked", "CheckBox", ui_icon(1))
	theme.set_icon("unchecked", "CheckBox", ui_icon(0))
	theme.set_icon("checked_disabled", "CheckBox", ui_icon(1))
	theme.set_icon("unchecked_disabled", "CheckBox", ui_icon(0))
	theme.set_color("font_color", "CheckBox", Color("e8e0d0"))
	theme.set_color("font_hover_color", "CheckBox", Color("ffe9a8"))
	theme.set_color("font_pressed_color", "CheckBox", Color("ffe9a8"))
	theme.set_color("font_hover_pressed_color", "CheckBox", Color("ffe9a8"))
	ThemeDB.fallback_font = font
	ThemeDB.fallback_font_size = FONT_SIZE
	get_tree().root.theme = theme
